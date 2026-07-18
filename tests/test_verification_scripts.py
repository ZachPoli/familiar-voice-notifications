import os
import shutil
import socket
import subprocess
import sys
from pathlib import Path

import pytest


PROJECT_DIRECTORY = Path(__file__).resolve().parents[1]
BOOTSTRAP_HELPER = (
    PROJECT_DIRECTORY / "scripts" / "verify_local_mapping_bootstrap.py"
)
RESTART_SCRIPT = (
    PROJECT_DIRECTORY / "scripts" / "verify_process_restart.ps1"
)
SENSITIVE_ENVIRONMENT_NAMES = (
    "VOICE_MAPPINGS_DB_PATH",
    "VOICE_MAPPINGS_ADMIN_KEY",
    "VOICE_GLASSES_API_KEY",
    "ZACH_VOICE_ID",
    "ZACH_SENDER_ALIASES",
    "EMILY_VOICE_ID",
    "EMILY_SENDER_ALIASES",
)
POWERSHELL = shutil.which("powershell.exe")


def synthetic_subprocess_environment():
    environment = os.environ.copy()
    for name in SENSITIVE_ENVIRONMENT_NAMES:
        environment.pop(name, None)
    environment["PYTHONIOENCODING"] = "utf-8"
    return environment


def write_synthetic_environment_file(tmp_path):
    environment_file = tmp_path / "synthetic.env"
    environment_file.write_text(
        "\n".join(
            (
                "ZACH_VOICE_ID=synthetic-helper-voice",
                "ZACH_SENDER_ALIASES=synthetic_sender,synthetic_alternate",
                "EMILY_VOICE_ID=",
                "EMILY_SENDER_ALIASES=",
            )
        ),
        encoding="utf-8",
    )
    return environment_file


def run_bootstrap_helper(database_path, environment_file):
    return subprocess.run(
        (
            sys.executable,
            str(BOOTSTRAP_HELPER),
            "--database",
            str(database_path),
            "--environment-file",
            str(environment_file),
        ),
        cwd=PROJECT_DIRECTORY,
        env=synthetic_subprocess_environment(),
        capture_output=True,
        text=True,
        check=False,
    )


def assert_safe_helper_failure(result, *private_values):
    assert result.returncode != 0
    assert result.stdout == ""
    assert result.stderr.strip() == "Bootstrap verification failed."
    combined_output = result.stdout + result.stderr
    for private_value in private_values:
        assert str(private_value) not in combined_output


def test_bootstrap_helper_success_output_is_count_and_boolean_only(tmp_path):
    database_path = tmp_path / "helper.sqlite3"
    environment_file = write_synthetic_environment_file(tmp_path)

    result = run_bootstrap_helper(database_path, environment_file)

    assert result.returncode == 0
    assert result.stderr == ""
    assert result.stdout.splitlines() == [
        "database created: yes",
        "bootstrap marker present: yes",
        "profile count: 1",
        "alias count: 2",
        "profiles with configured voice IDs: 1",
        "blank aliases found: no",
        "duplicate aliases found: no",
    ]
    for private_value in (
        database_path,
        "synthetic-helper-voice",
        "synthetic_sender",
        "synthetic_alternate",
    ):
        assert str(private_value) not in result.stdout


def test_bootstrap_helper_rejects_default_database_path(tmp_path):
    environment_file = write_synthetic_environment_file(tmp_path)
    default_database_path = (
        PROJECT_DIRECTORY / "data" / "voice_mappings.sqlite3"
    )

    result = run_bootstrap_helper(default_database_path, environment_file)

    assert_safe_helper_failure(
        result,
        default_database_path,
        "synthetic-helper-voice",
    )


def test_bootstrap_helper_preserves_existing_database(tmp_path):
    database_path = tmp_path / "existing.sqlite3"
    original_content = b"synthetic-existing-database"
    database_path.write_bytes(original_content)
    environment_file = write_synthetic_environment_file(tmp_path)

    result = run_bootstrap_helper(database_path, environment_file)

    assert_safe_helper_failure(result, database_path, original_content)
    assert database_path.read_bytes() == original_content


@pytest.mark.parametrize("sidecar_suffix", ["-wal", "-shm"])
def test_bootstrap_helper_preserves_existing_sidecars(
    tmp_path,
    sidecar_suffix,
):
    database_path = tmp_path / "sidecar.sqlite3"
    sidecar_path = Path(f"{database_path}{sidecar_suffix}")
    original_content = b"synthetic-existing-sidecar"
    sidecar_path.write_bytes(original_content)
    environment_file = write_synthetic_environment_file(tmp_path)

    result = run_bootstrap_helper(database_path, environment_file)

    assert_safe_helper_failure(result, database_path, original_content)
    assert not database_path.exists()
    assert sidecar_path.read_bytes() == original_content


def test_workflow_module_import_blocks_real_dotenv_loading(tmp_path):
    workflow_path = (
        PROJECT_DIRECTORY / "tests" / "test_persistent_mapping_workflow.py"
    )
    check_script = tmp_path / "check_import.py"
    check_script.write_text(
        "\n".join(
            (
                "import dotenv",
                "import runpy",
                "import sys",
                f"sys.path.insert(0, {str(PROJECT_DIRECTORY)!r})",
                "def forbidden(*args, **kwargs):",
                "    raise RuntimeError('real dotenv access attempted')",
                "dotenv.load_dotenv = forbidden",
                f"runpy.run_path({str(workflow_path)!r}, run_name='safe_import')",
            )
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        (sys.executable, str(check_script)),
        cwd=PROJECT_DIRECTORY,
        env=synthetic_subprocess_environment(),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "real dotenv access attempted" not in result.stdout
    assert "real dotenv access attempted" not in result.stderr


def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def port_is_available(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
        return client.connect_ex(("127.0.0.1", port)) != 0


def run_restart_script(database_path, port, *additional_arguments):
    if POWERSHELL is None:
        pytest.skip("Windows PowerShell is unavailable.")

    environment = synthetic_subprocess_environment()
    environment["VOICE_MAPPINGS_ADMIN_KEY"] = "previous-admin-value"
    environment["VOICE_GLASSES_API_KEY"] = ""

    return subprocess.run(
        (
            POWERSHELL,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(RESTART_SCRIPT),
            "-DatabasePath",
            str(database_path),
            "-Port",
            str(port),
            *additional_arguments,
        ),
        cwd=PROJECT_DIRECTORY,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def assert_safe_restart_failure(result, database_path, port):
    assert result.returncode != 0
    assert "passed" not in result.stdout.casefold()
    assert result.stderr.strip() == "Process restart verification failed."
    assert str(database_path) not in result.stdout + result.stderr
    assert "synthetic-admin-key" not in result.stdout + result.stderr
    assert "synthetic-notification-key" not in result.stdout + result.stderr
    assert port_is_available(port)


@pytest.mark.parametrize("existing_suffix", ["", "-wal", "-shm"])
def test_restart_script_preserves_preexisting_database_files(
    tmp_path,
    existing_suffix,
):
    database_path = tmp_path / "restart-existing.sqlite3"
    existing_path = Path(f"{database_path}{existing_suffix}")
    original_content = b"synthetic-preexisting-content"
    existing_path.write_bytes(original_content)
    port = find_free_port()

    result = run_restart_script(database_path, port)

    assert_safe_restart_failure(result, database_path, port)
    assert existing_path.read_bytes() == original_content
    for candidate in (
        database_path,
        Path(f"{database_path}-wal"),
        Path(f"{database_path}-shm"),
    ):
        if candidate != existing_path:
            assert not candidate.exists()


def test_restart_script_cleans_up_after_first_startup_failure(tmp_path):
    database_path = tmp_path / "startup-failure.sqlite3"
    unrelated_path = tmp_path / "unrelated.txt"
    unrelated_path.write_text("preserve", encoding="utf-8")
    port = find_free_port()

    result = run_restart_script(
        database_path,
        port,
        "-SimulateStartupFailure",
    )

    assert_safe_restart_failure(result, database_path, port)
    assert unrelated_path.read_text(encoding="utf-8") == "preserve"
    assert not database_path.exists()
    assert not Path(f"{database_path}-wal").exists()
    assert not Path(f"{database_path}-shm").exists()


def test_restart_script_attempts_all_cleanup_after_simulated_failure(
    tmp_path,
):
    database_path = tmp_path / "cleanup-failure.sqlite3"
    port = find_free_port()

    result = run_restart_script(
        database_path,
        port,
        "-SimulateCleanupFailure",
    )

    assert_safe_restart_failure(result, database_path, port)
    assert not database_path.exists()
    assert not Path(f"{database_path}-wal").exists()
    assert not Path(f"{database_path}-shm").exists()


def test_restart_script_success_cleans_files_environment_and_port(tmp_path):
    database_path = tmp_path / "restart-success.sqlite3"
    port = find_free_port()

    result = run_restart_script(database_path, port)

    assert result.returncode == 0
    assert result.stderr == ""
    assert result.stdout.splitlines() == [
        "first process profile creation: passed",
        "second process persistence read: passed",
        "second process profile deletion: passed",
        "environment restoration: passed",
        "port cleanup: passed",
        "temporary database cleanup: passed",
    ]
    assert port_is_available(port)
    assert not database_path.exists()
    assert not Path(f"{database_path}-wal").exists()
    assert not Path(f"{database_path}-shm").exists()
