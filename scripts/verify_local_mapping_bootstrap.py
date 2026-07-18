import argparse
import logging
import os
import sys
from contextlib import closing
from pathlib import Path

from dotenv import load_dotenv


PROJECT_DIRECTORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIRECTORY))

from voice_mapping_store import (  # noqa: E402
    BOOTSTRAP_METADATA_KEY,
    DEFAULT_DATABASE_PATH,
    connect_database,
    initialize_database,
)


class SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ValueError("Invalid verification arguments.")


def parse_arguments() -> argparse.Namespace:
    parser = SafeArgumentParser(
        description=(
            "Verify one-time voice-mapping bootstrap without printing "
            "private mapping data."
        )
    )
    parser.add_argument(
        "--database",
        required=True,
        help="Explicit path to a new temporary SQLite database.",
    )
    parser.add_argument(
        "--environment-file",
        help=(
            "Optional environment file. Defaults to the project's local "
            "configuration file."
        ),
    )
    return parser.parse_args()


def fail(message: str) -> int:
    print(message, file=sys.stderr)
    return 1


def run_verification() -> int:
    arguments = parse_arguments()
    database_path = Path(arguments.database).expanduser().resolve()
    database_sidecars = (
        Path(f"{database_path}-wal"),
        Path(f"{database_path}-shm"),
    )
    default_database_path = (
        PROJECT_DIRECTORY / DEFAULT_DATABASE_PATH
    ).resolve()

    if database_path == default_database_path:
        raise ValueError("Unsafe database target.")

    if any(
        candidate.exists()
        for candidate in (database_path, *database_sidecars)
    ):
        raise ValueError("Unsafe database target.")

    if not database_path.parent.is_dir():
        raise ValueError("Unsafe database target.")

    environment_file = (
        Path(arguments.environment_file).expanduser().resolve()
        if arguments.environment_file
        else PROJECT_DIRECTORY / ".env"
    )
    dotenv_logger = logging.getLogger("dotenv.main")
    dotenv_logging_was_disabled = dotenv_logger.disabled
    dotenv_logger.disabled = True
    try:
        load_dotenv(environment_file)
    finally:
        dotenv_logger.disabled = dotenv_logging_was_disabled

    os.environ["VOICE_MAPPINGS_DB_PATH"] = str(database_path)

    initialize_database(database_path)

    with closing(connect_database(database_path)) as connection:
        marker_present = connection.execute(
            """
            SELECT EXISTS(
                SELECT 1
                FROM storage_metadata
                WHERE key = ?
            )
            """,
            (BOOTSTRAP_METADATA_KEY,),
        ).fetchone()[0]
        profile_count = connection.execute(
            "SELECT COUNT(*) FROM voice_profiles"
        ).fetchone()[0]
        alias_count = connection.execute(
            "SELECT COUNT(*) FROM sender_aliases"
        ).fetchone()[0]
        configured_voice_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM voice_profiles
            WHERE TRIM(voice_id) != ''
            """
        ).fetchone()[0]
        blank_alias_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM sender_aliases
            WHERE TRIM(normalized_alias) = ''
            """
        ).fetchone()[0]
        duplicate_alias_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM (
                SELECT normalized_alias
                FROM sender_aliases
                GROUP BY normalized_alias
                HAVING COUNT(*) > 1
            )
            """
        ).fetchone()[0]

    database_created = database_path.is_file()
    blank_aliases_found = blank_alias_count > 0
    duplicate_aliases_found = duplicate_alias_count > 0

    print(f"database created: {'yes' if database_created else 'no'}")
    print(
        "bootstrap marker present: "
        f"{'yes' if marker_present else 'no'}"
    )
    print(f"profile count: {profile_count}")
    print(f"alias count: {alias_count}")
    print(
        "profiles with configured voice IDs: "
        f"{configured_voice_count}"
    )
    print(
        "blank aliases found: "
        f"{'yes' if blank_aliases_found else 'no'}"
    )
    print(
        "duplicate aliases found: "
        f"{'yes' if duplicate_aliases_found else 'no'}"
    )

    is_valid = (
        database_created
        and bool(marker_present)
        and profile_count > 0
        and alias_count > 0
        and configured_voice_count == profile_count
        and not blank_aliases_found
        and not duplicate_aliases_found
    )
    return 0 if is_valid else 1


def main() -> int:
    try:
        return run_verification()
    except Exception:
        return fail("Bootstrap verification failed.")


if __name__ == "__main__":
    raise SystemExit(main())
