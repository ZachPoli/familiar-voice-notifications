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


def test_list_profiles_is_empty_and_then_ordered(tmp_path):
    database_path = tmp_path / "mappings.sqlite3"
    store.initialize_database(database_path)

    assert store.list_voice_profiles(database_path) == []

    first_id = store.add_voice_profile(
        "first_profile",
        "First Profile",
        "voice-one",
        ["First Alias"],
        database_path,
    )
    second_id = store.add_voice_profile(
        "second_profile",
        "Second Profile",
        "voice-two",
        ["Second Alias", "Second Alternate"],
        database_path,
    )

    profiles = store.list_voice_profiles(database_path)

    assert [profile["id"] for profile in profiles] == [first_id, second_id]
    assert [
        alias["id"]
        for alias in profiles[1]["aliases"]
    ] == sorted(alias["id"] for alias in profiles[1]["aliases"])
    assert "voice_id" not in profiles[0]
    assert profiles[0]["voice_id_configured"] is True


def test_create_read_and_update_voice_profile(tmp_path):
    database_path = tmp_path / "mappings.sqlite3"
    store.initialize_database(database_path)
    profile_id = store.add_voice_profile(
        "original_profile",
        "Original Name",
        "original-voice",
        ["Primary Alias", "Alternate Alias"],
        database_path,
    )

    created_profile = store.get_voice_profile(profile_id, database_path)
    updated_profile = store.update_voice_profile(
        profile_id,
        profile_key="updated_profile",
        display_name="Updated Name",
        voice_id="updated-voice",
        database_path=database_path,
    )

    assert created_profile["profile_key"] == "original_profile"
    assert len(created_profile["aliases"]) == 2
    assert updated_profile["profile_key"] == "updated_profile"
    assert updated_profile["display_name"] == "Updated Name"
    assert updated_profile["voice_id_configured"] is True
    assert "voice_id" not in updated_profile
    assert (
        store.find_voice_id_for_sender("Primary Alias", database_path)
        == "updated-voice"
    )


def test_add_update_same_value_and_delete_sender_alias(tmp_path):
    database_path = tmp_path / "mappings.sqlite3"
    store.initialize_database(database_path)
    profile_id = store.add_voice_profile(
        "profile",
        "Profile",
        "voice-one",
        ["Initial Alias"],
        database_path,
    )

    alias = store.add_sender_alias(
        profile_id,
        "  Added   Alias ",
        database_path,
    )
    same_alias = store.update_sender_alias(
        alias["id"],
        "ADDED ALIAS",
        database_path,
    )
    updated_alias = store.update_sender_alias(
        alias["id"],
        "Replacement Alias",
        database_path,
    )
    store.delete_sender_alias(alias["id"], database_path)

    assert alias["normalized_alias"] == "added alias"
    assert same_alias == alias
    assert updated_alias["normalized_alias"] == "replacement alias"
    assert (
        store.find_voice_id_for_sender("Replacement Alias", database_path)
        is None
    )


def test_delete_profile_cascades_all_aliases(tmp_path):
    database_path = tmp_path / "mappings.sqlite3"
    store.initialize_database(database_path)
    profile_id = store.add_voice_profile(
        "profile",
        "Profile",
        "voice-one",
        ["First Alias", "Second Alias"],
        database_path,
    )

    store.delete_voice_profile(profile_id, database_path)

    assert store.list_voice_profiles(database_path) == []
    with database_connection(database_path) as connection:
        alias_count = connection.execute(
            "SELECT COUNT(*) FROM sender_aliases"
        ).fetchone()[0]
    assert alias_count == 0


def test_unknown_management_ids_raise_not_found(tmp_path):
    database_path = tmp_path / "mappings.sqlite3"
    store.initialize_database(database_path)

    with pytest.raises(store.VoiceProfileNotFoundError):
        store.get_voice_profile(999, database_path)
    with pytest.raises(store.VoiceProfileNotFoundError):
        store.update_voice_profile(
            999,
            display_name="Missing",
            database_path=database_path,
        )
    with pytest.raises(store.VoiceProfileNotFoundError):
        store.delete_voice_profile(999, database_path)
    with pytest.raises(store.VoiceProfileNotFoundError):
        store.add_sender_alias(999, "Alias", database_path)
    with pytest.raises(store.SenderAliasNotFoundError):
        store.update_sender_alias(999, "Alias", database_path)
    with pytest.raises(store.SenderAliasNotFoundError):
        store.delete_sender_alias(999, database_path)


def test_duplicate_profile_key_fails_without_partial_update(tmp_path):
    database_path = tmp_path / "mappings.sqlite3"
    store.initialize_database(database_path)
    first_id = store.add_voice_profile(
        "first_profile",
        "First",
        "voice-one",
        ["First Alias"],
        database_path,
    )
    second_id = store.add_voice_profile(
        "second_profile",
        "Second",
        "voice-two",
        ["Second Alias"],
        database_path,
    )

    with pytest.raises(store.ProfileKeyConflictError):
        store.update_voice_profile(
            second_id,
            profile_key="first_profile",
            display_name="Should Not Persist",
            database_path=database_path,
        )

    assert store.get_voice_profile(first_id, database_path)[
        "display_name"
    ] == "First"
    second_profile = store.get_voice_profile(second_id, database_path)
    assert second_profile["profile_key"] == "second_profile"
    assert second_profile["display_name"] == "Second"


def test_duplicate_alias_update_fails_without_partial_change(tmp_path):
    database_path = tmp_path / "mappings.sqlite3"
    store.initialize_database(database_path)
    first_id = store.add_voice_profile(
        "first_profile",
        "First",
        "voice-one",
        ["First Alias"],
        database_path,
    )
    second_id = store.add_voice_profile(
        "second_profile",
        "Second",
        "voice-two",
        ["Second Alias"],
        database_path,
    )
    first_alias_id = store.get_voice_profile(first_id, database_path)[
        "aliases"
    ][0]["id"]
    second_alias_id = store.get_voice_profile(second_id, database_path)[
        "aliases"
    ][0]["id"]

    with pytest.raises(store.SenderAliasConflictError):
        store.update_sender_alias(
            second_alias_id,
            "First Alias",
            database_path,
        )

    second_profile = store.get_voice_profile(second_id, database_path)
    assert second_profile["aliases"][0]["normalized_alias"] == "second alias"
    assert first_alias_id != second_alias_id


def test_management_operations_close_every_connection(tmp_path, monkeypatch):
    database_path = tmp_path / "mappings.sqlite3"
    store.initialize_database(database_path)
    original_connect_database = store.connect_database
    tracked_connections = []

    class TrackingConnection:
        def __init__(self, connection):
            self.connection = connection
            self.closed = False

        def __getattr__(self, name):
            return getattr(self.connection, name)

        def __enter__(self):
            self.connection.__enter__()
            return self

        def __exit__(self, *arguments):
            return self.connection.__exit__(*arguments)

        def close(self):
            self.closed = True
            self.connection.close()

    def tracking_connect_database(path=None):
        tracked = TrackingConnection(original_connect_database(path))
        tracked_connections.append(tracked)
        return tracked

    monkeypatch.setattr(store, "connect_database", tracking_connect_database)

    profile_id = store.add_voice_profile(
        "profile",
        "Profile",
        "voice-one",
        ["First Alias"],
        database_path,
    )
    store.list_voice_profiles(database_path)
    profile = store.get_voice_profile(profile_id, database_path)
    store.update_voice_profile(
        profile_id,
        display_name="Updated",
        database_path=database_path,
    )
    alias = store.add_sender_alias(profile_id, "Second Alias", database_path)
    store.update_sender_alias(alias["id"], "Third Alias", database_path)
    store.delete_sender_alias(alias["id"], database_path)
    store.delete_voice_profile(profile["id"], database_path)

    assert tracked_connections
    assert all(connection.closed for connection in tracked_connections)
