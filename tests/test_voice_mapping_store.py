import sqlite3
from contextlib import closing, contextmanager

import pytest

import voice_mapping_store as store


PRIVATE_ENVIRONMENT_VARIABLES = (
    "ZACH_VOICE_ID",
    "ZACH_SENDER_ALIASES",
    "EMILY_VOICE_ID",
    "EMILY_SENDER_ALIASES",
)


@contextmanager
def database_connection(database_path):
    with closing(store.connect_database(database_path)) as connection:
        with connection:
            yield connection


@pytest.fixture(autouse=True)
def clear_seed_environment(monkeypatch):
    for variable in PRIVATE_ENVIRONMENT_VARIABLES:
        monkeypatch.delenv(variable, raising=False)


def test_schema_creation_and_repeated_initialization(tmp_path):
    database_path = tmp_path / "mappings.sqlite3"

    assert store.initialize_database(database_path) == database_path
    store.initialize_database(database_path)

    with database_connection(database_path) as connection:
        tables = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        foreign_keys_enabled = connection.execute(
            "PRAGMA foreign_keys"
        ).fetchone()[0]

    assert {
        "voice_profiles",
        "sender_aliases",
        "storage_metadata",
    } <= tables
    assert foreign_keys_enabled == 1


def test_configurable_relative_path_is_backend_relative(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(store, "BACKEND_DIRECTORY", tmp_path)
    monkeypatch.setenv(
        "VOICE_MAPPINGS_DB_PATH",
        "custom/mappings.sqlite3",
    )

    expected_path = tmp_path / "custom" / "mappings.sqlite3"

    assert store.initialize_database() == expected_path
    assert expected_path.exists()


def test_multiple_aliases_are_normalized_and_matched(tmp_path):
    database_path = tmp_path / "mappings.sqlite3"
    store.initialize_database(database_path)
    store.add_voice_profile(
        "family",
        "Family Member",
        "voice-one",
        ["  Primary   Name ", "SECONDARY Name"],
        database_path,
    )

    assert (
        store.find_voice_id_for_sender(
            "PRIMARY NAME",
            database_path,
        )
        == "voice-one"
    )
    assert (
        store.find_voice_id_for_sender(
            " secondary   name ",
            database_path,
        )
        == "voice-one"
    )

    with database_connection(database_path) as connection:
        aliases = {
            row["normalized_alias"]
            for row in connection.execute(
                "SELECT normalized_alias FROM sender_aliases"
            )
        }

    assert aliases == {"primary name", "secondary name"}


def test_unknown_and_blank_sender_return_none(tmp_path):
    database_path = tmp_path / "mappings.sqlite3"
    store.initialize_database(database_path)

    assert store.find_voice_id_for_sender("Unknown", database_path) is None
    assert store.find_voice_id_for_sender("   ", database_path) is None


def test_duplicate_alias_is_rejected_transactionally(tmp_path):
    database_path = tmp_path / "mappings.sqlite3"
    store.initialize_database(database_path)
    store.add_voice_profile(
        "first",
        "First",
        "voice-one",
        ["Shared Alias"],
        database_path,
    )

    with pytest.raises(ValueError, match="normalized sender alias"):
        store.add_voice_profile(
            "second",
            "Second",
            "voice-two",
            [" shared   alias ", "Unique Alias"],
            database_path,
        )

    with database_connection(database_path) as connection:
        second_profile = connection.execute(
            "SELECT id FROM voice_profiles WHERE profile_key = 'second'"
        ).fetchone()
        unique_alias = connection.execute(
            """
            SELECT id FROM sender_aliases
            WHERE normalized_alias = 'unique alias'
            """
        ).fetchone()

    assert second_profile is None
    assert unique_alias is None


def test_deleting_profile_cascades_to_aliases(tmp_path):
    database_path = tmp_path / "mappings.sqlite3"
    store.initialize_database(database_path)
    profile_id = store.add_voice_profile(
        "family",
        "Family",
        "voice-one",
        ["Family Alias"],
        database_path,
    )

    with database_connection(database_path) as connection:
        connection.execute(
            "DELETE FROM voice_profiles WHERE id = ?",
            (profile_id,),
        )

    with database_connection(database_path) as connection:
        alias_count = connection.execute(
            "SELECT COUNT(*) FROM sender_aliases"
        ).fetchone()[0]

    assert alias_count == 0


def test_first_run_environment_bootstrap(tmp_path, monkeypatch):
    database_path = tmp_path / "mappings.sqlite3"
    monkeypatch.setenv("ZACH_VOICE_ID", "voice-z")
    monkeypatch.setenv(
        "ZACH_SENDER_ALIASES",
        " Example Name, EXAMPLE   NICKNAME ",
    )
    monkeypatch.setenv("EMILY_VOICE_ID", "voice-e")
    monkeypatch.setenv("EMILY_SENDER_ALIASES", "Second Name")

    store.initialize_database(database_path)

    assert (
        store.find_voice_id_for_sender("example name", database_path)
        == "voice-z"
    )
    assert (
        store.find_voice_id_for_sender("example nickname", database_path)
        == "voice-z"
    )
    assert (
        store.find_voice_id_for_sender("SECOND NAME", database_path)
        == "voice-e"
    )


def test_invalid_seed_values_are_skipped(tmp_path, monkeypatch):
    database_path = tmp_path / "mappings.sqlite3"
    monkeypatch.setenv("ZACH_VOICE_ID", "")
    monkeypatch.setenv("ZACH_SENDER_ALIASES", "Valid Alias")
    monkeypatch.setenv("EMILY_VOICE_ID", "voice-e")
    monkeypatch.setenv("EMILY_SENDER_ALIASES", " ,  ")

    store.initialize_database(database_path)

    with database_connection(database_path) as connection:
        profile_count = connection.execute(
            "SELECT COUNT(*) FROM voice_profiles"
        ).fetchone()[0]
        marker = connection.execute(
            """
            SELECT value FROM storage_metadata
            WHERE key = ?
            """,
            (store.BOOTSTRAP_METADATA_KEY,),
        ).fetchone()

    assert profile_count == 0
    assert marker["value"] == "complete"


def test_repeated_startup_does_not_overwrite_mapping(
    tmp_path,
    monkeypatch,
):
    database_path = tmp_path / "mappings.sqlite3"
    monkeypatch.setenv("ZACH_VOICE_ID", "original-voice")
    monkeypatch.setenv("ZACH_SENDER_ALIASES", "Original Alias")
    store.initialize_database(database_path)

    with database_connection(database_path) as connection:
        connection.execute(
            """
            UPDATE voice_profiles
            SET voice_id = 'user-edited-voice'
            WHERE profile_key = 'zach'
            """
        )

    monkeypatch.setenv("ZACH_VOICE_ID", "changed-environment-voice")
    store.initialize_database(database_path)

    assert (
        store.find_voice_id_for_sender("Original Alias", database_path)
        == "user-edited-voice"
    )


def test_repeated_startup_does_not_recreate_deleted_mapping(
    tmp_path,
    monkeypatch,
):
    database_path = tmp_path / "mappings.sqlite3"
    monkeypatch.setenv("ZACH_VOICE_ID", "voice-z")
    monkeypatch.setenv("ZACH_SENDER_ALIASES", "Deleted Alias")
    store.initialize_database(database_path)

    with database_connection(database_path) as connection:
        connection.execute("DELETE FROM voice_profiles")

    store.initialize_database(database_path)

    assert (
        store.find_voice_id_for_sender("Deleted Alias", database_path)
        is None
    )


def test_populated_unmarked_database_is_protected(
    tmp_path,
    monkeypatch,
):
    database_path = tmp_path / "mappings.sqlite3"
    database_path.parent.mkdir(parents=True, exist_ok=True)

    with closing(sqlite3.connect(database_path)) as connection:
        with connection:
            connection.executescript(store.SCHEMA)
            connection.execute(
                """
                INSERT INTO voice_profiles (
                    profile_key,
                    display_name,
                    voice_id
                ) VALUES ('user-profile', 'User Profile', 'user-voice')
                """
            )
            profile_id = connection.execute(
                """
                SELECT id FROM voice_profiles
                WHERE profile_key = 'user-profile'
                """
            ).fetchone()[0]
            connection.execute(
                """
                INSERT INTO sender_aliases (
                    voice_profile_id,
                    normalized_alias
                ) VALUES (?, 'user alias')
                """,
                (profile_id,),
            )

    monkeypatch.setenv("ZACH_VOICE_ID", "environment-voice")
    monkeypatch.setenv("ZACH_SENDER_ALIASES", "Environment Alias")

    store.initialize_database(database_path)

    assert (
        store.find_voice_id_for_sender("User Alias", database_path)
        == "user-voice"
    )
    assert (
        store.find_voice_id_for_sender("Environment Alias", database_path)
        is None
    )

    with database_connection(database_path) as connection:
        marker = connection.execute(
            """
            SELECT value FROM storage_metadata
            WHERE key = ?
            """,
            (store.BOOTSTRAP_METADATA_KEY,),
        ).fetchone()

    assert marker["value"] == "complete"


def test_conflicting_bootstrap_aliases_roll_back(tmp_path, monkeypatch):
    database_path = tmp_path / "mappings.sqlite3"
    monkeypatch.setenv("ZACH_VOICE_ID", "voice-z")
    monkeypatch.setenv("ZACH_SENDER_ALIASES", "Shared Alias")
    monkeypatch.setenv("EMILY_VOICE_ID", "voice-e")
    monkeypatch.setenv("EMILY_SENDER_ALIASES", " shared   alias ")

    with pytest.raises(ValueError, match="conflicting sender aliases"):
        store.initialize_database(database_path)

    with database_connection(database_path) as connection:
        profile_count = connection.execute(
            "SELECT COUNT(*) FROM voice_profiles"
        ).fetchone()[0]
        marker = connection.execute(
            """
            SELECT value FROM storage_metadata
            WHERE key = ?
            """,
            (store.BOOTSTRAP_METADATA_KEY,),
        ).fetchone()

    assert profile_count == 0
    assert marker is None
