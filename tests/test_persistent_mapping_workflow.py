from contextlib import closing
from unittest.mock import patch

from fastapi.testclient import TestClient

import voice_mapping_store as store


with patch("dotenv.load_dotenv", return_value=False):
    import main


ADMIN_KEY = "synthetic-admin-key"
NOTIFICATION_KEY = "synthetic-notification-key"
ADMIN_HEADERS = {
    "X-Voice-Mappings-Admin-Key": ADMIN_KEY,
}
NOTIFICATION_HEADERS = {
    "X-Voice-Glasses-Key": NOTIFICATION_KEY,
}


def configure_temporary_database(monkeypatch, database_path):
    monkeypatch.setenv("VOICE_MAPPINGS_DB_PATH", str(database_path))
    monkeypatch.setenv("ZACH_VOICE_ID", "")
    monkeypatch.setenv("ZACH_SENDER_ALIASES", "")
    monkeypatch.setenv("EMILY_VOICE_ID", "")
    monkeypatch.setenv("EMILY_SENDER_ALIASES", "")
    monkeypatch.setattr(main, "VOICE_MAPPINGS_ADMIN_KEY", ADMIN_KEY)
    monkeypatch.setattr(main, "VOICE_GLASSES_API_KEY", NOTIFICATION_KEY)


def test_synthetic_bootstrap_persists_and_does_not_recreate(
    tmp_path,
    monkeypatch,
):
    database_path = tmp_path / "bootstrap.sqlite3"
    monkeypatch.setenv("ZACH_VOICE_ID", "synthetic-voice-one")
    monkeypatch.setenv(
        "ZACH_SENDER_ALIASES",
        " Synthetic Sender, SYNTHETIC   FULL NAME ",
    )
    monkeypatch.setenv("EMILY_VOICE_ID", "synthetic-voice-two")
    monkeypatch.setenv(
        "EMILY_SENDER_ALIASES",
        "Second Synthetic Sender",
    )

    store.initialize_database(database_path)

    profiles = store.list_voice_profiles(database_path)
    aliases = [
        alias["normalized_alias"]
        for profile in profiles
        for alias in profile["aliases"]
    ]
    assert len(profiles) == 2
    assert len(aliases) == 3
    assert aliases == [
        "synthetic full name",
        "synthetic sender",
        "second synthetic sender",
    ]
    assert (
        store.find_voice_id_for_sender(
            "synthetic sender",
            database_path,
        )
        == "synthetic-voice-one"
    )
    assert (
        store.find_voice_id_for_sender(
            "SECOND SYNTHETIC SENDER",
            database_path,
        )
        == "synthetic-voice-two"
    )

    with closing(store.connect_database(database_path)) as connection:
        marker = connection.execute(
            """
            SELECT value
            FROM storage_metadata
            WHERE key = ?
            """,
            (store.BOOTSTRAP_METADATA_KEY,),
        ).fetchone()
    assert marker["value"] == "complete"

    monkeypatch.setenv("ZACH_VOICE_ID", "replacement-voice")
    monkeypatch.setenv("ZACH_SENDER_ALIASES", "Replacement Sender")
    store.initialize_database(database_path)

    assert (
        store.find_voice_id_for_sender(
            "synthetic sender",
            database_path,
        )
        == "synthetic-voice-one"
    )
    assert (
        store.find_voice_id_for_sender(
            "Replacement Sender",
            database_path,
        )
        is None
    )

    first_profile_id = profiles[0]["id"]
    store.delete_voice_profile(first_profile_id, database_path)
    store.initialize_database(database_path)

    assert (
        store.find_voice_id_for_sender(
            "synthetic sender",
            database_path,
        )
        is None
    )
    assert len(store.list_voice_profiles(database_path)) == 1


def test_crud_persists_across_application_lifespans(
    tmp_path,
    monkeypatch,
):
    database_path = tmp_path / "lifespans.sqlite3"
    configure_temporary_database(monkeypatch, database_path)
    initialization_count = 0
    original_initialize_database = main.initialize_database

    def counted_initialize_database():
        nonlocal initialization_count
        initialization_count += 1
        return original_initialize_database()

    monkeypatch.setattr(
        main,
        "initialize_database",
        counted_initialize_database,
    )

    with TestClient(main.app) as client:
        created = client.post(
            "/voice-profiles",
            headers=ADMIN_HEADERS,
            json={
                "profile_key": "persistent_profile",
                "display_name": "Persistent Profile",
                "voice_id": "synthetic-persistent-voice",
                "aliases": [
                    "Persistent Sender",
                    "Persistent Alternate",
                ],
            },
        )
        assert created.status_code == 201
        profile = created.json()
        assert "voice_id" not in profile
        profile_id = profile["id"]
        first_alias_id = profile["aliases"][0]["id"]
        second_alias_id = profile["aliases"][1]["id"]

        read = client.get(
            f"/voice-profiles/{profile_id}",
            headers=ADMIN_HEADERS,
        )
        assert read.status_code == 200
        assert "voice_id" not in read.json()
        assert len(read.json()["aliases"]) == 2

    with TestClient(main.app) as client:
        persisted = client.get(
            f"/voice-profiles/{profile_id}",
            headers=ADMIN_HEADERS,
        )
        assert persisted.status_code == 200
        assert "voice_id" not in persisted.json()
        assert len(persisted.json()["aliases"]) == 2

        updated = client.patch(
            f"/voice-profiles/{profile_id}",
            headers=ADMIN_HEADERS,
            json={
                "display_name": "Updated Persistent Profile",
                "voice_id": "updated-synthetic-voice",
            },
        )
        alias_updated = client.patch(
            f"/sender-aliases/{first_alias_id}",
            headers=ADMIN_HEADERS,
            json={"alias": "Updated Persistent Sender"},
        )
        alias_deleted = client.delete(
            f"/sender-aliases/{second_alias_id}",
            headers=ADMIN_HEADERS,
        )
        assert updated.status_code == 200
        assert alias_updated.status_code == 200
        assert alias_deleted.status_code == 204

    with TestClient(main.app) as client:
        persisted_update = client.get(
            f"/voice-profiles/{profile_id}",
            headers=ADMIN_HEADERS,
        )
        assert persisted_update.status_code == 200
        assert "voice_id" not in persisted_update.json()
        assert (
            persisted_update.json()["display_name"]
            == "Updated Persistent Profile"
        )
        assert persisted_update.json()["voice_id_configured"] is True
        assert persisted_update.json()["aliases"] == [
            {
                "id": first_alias_id,
                "normalized_alias": "updated persistent sender",
            }
        ]
        assert (
            store.find_voice_id_for_sender(
                "Updated Persistent Sender",
                database_path,
            )
            == "updated-synthetic-voice"
        )

        deleted = client.delete(
            f"/voice-profiles/{profile_id}",
            headers=ADMIN_HEADERS,
        )
        assert deleted.status_code == 204

    with TestClient(main.app) as client:
        missing = client.get(
            f"/voice-profiles/{profile_id}",
            headers=ADMIN_HEADERS,
        )
        assert missing.status_code == 404
        assert client.get(
            "/voice-profiles",
            headers=ADMIN_HEADERS,
        ).json() == []

    with closing(store.connect_database(database_path)) as connection:
        alias_count = connection.execute(
            "SELECT COUNT(*) FROM sender_aliases"
        ).fetchone()[0]
    assert alias_count == 0
    assert initialization_count == 4


def test_notification_uses_persistent_mapping_and_preserves_response(
    tmp_path,
    monkeypatch,
):
    database_path = tmp_path / "notification.sqlite3"
    configure_temporary_database(monkeypatch, database_path)
    store.initialize_database(database_path)
    store.add_voice_profile(
        "notification_profile",
        "Notification Profile",
        "synthetic-stored-voice",
        ["Synthetic Known Sender"],
        database_path,
    )

    audio_calls = []

    def synthetic_audio_stream(text, voice_id):
        audio_calls.append({"text": text, "voice_id": voice_id})
        return iter([b"synthetic-mp3-bytes"])

    monkeypatch.setattr(main, "create_audio_stream", synthetic_audio_stream)

    senders_and_expected_voices = (
        ("Synthetic Known Sender", "synthetic-stored-voice"),
        ("SYNTHETIC KNOWN SENDER", "synthetic-stored-voice"),
        ("  Synthetic   Known   Sender  ", "synthetic-stored-voice"),
        ("Unknown Synthetic Sender", main.DEFAULT_VOICE_ID),
    )

    with TestClient(main.app) as client:
        for sender, expected_voice_id in senders_and_expected_voices:
            response = client.post(
                "/notification",
                headers=NOTIFICATION_HEADERS,
                json={
                    "sender": sender,
                    "app": "synthetic.messaging",
                    "message": "Synthetic message.",
                },
            )

            assert response.status_code == 200
            assert response.headers["content-type"] == "audio/mpeg"
            assert response.content == b"synthetic-mp3-bytes"
            assert audio_calls[-1] == {
                "text": f"{sender} says: Synthetic message.",
                "voice_id": expected_voice_id,
            }

        empty_message = client.post(
            "/notification",
            headers=NOTIFICATION_HEADERS,
            json={
                "sender": "Synthetic Known Sender",
                "app": "synthetic.messaging",
                "message": "   ",
            },
        )
        assert empty_message.status_code == 400
        assert len(audio_calls) == len(senders_and_expected_voices)


def test_authentication_boundaries_remain_separate(
    tmp_path,
    monkeypatch,
):
    database_path = tmp_path / "authentication.sqlite3"
    configure_temporary_database(monkeypatch, database_path)

    def synthetic_audio_stream(text, voice_id):
        return iter([b"synthetic-mp3-bytes"])

    monkeypatch.setattr(main, "create_audio_stream", synthetic_audio_stream)
    notification_body = {
        "sender": "Synthetic Sender",
        "app": "synthetic.messaging",
        "message": "Synthetic message.",
    }

    with TestClient(main.app) as client:
        management_missing = client.get("/voice-profiles")
        management_with_tts_key = client.get(
            "/voice-profiles",
            headers=NOTIFICATION_HEADERS,
        )
        management_allowed = client.get(
            "/voice-profiles",
            headers=ADMIN_HEADERS,
        )

        notification_missing = client.post(
            "/notification",
            json=notification_body,
        )
        notification_with_admin_key = client.post(
            "/notification",
            headers=ADMIN_HEADERS,
            json=notification_body,
        )
        notification_allowed = client.post(
            "/notification",
            headers=NOTIFICATION_HEADERS,
            json=notification_body,
        )

    assert management_missing.status_code == 401
    assert management_with_tts_key.status_code == 401
    assert management_allowed.status_code == 200
    assert notification_missing.status_code == 401
    assert notification_with_admin_key.status_code == 401
    assert notification_allowed.status_code == 200

    combined_responses = " ".join(
        response.text
        for response in (
            management_missing,
            management_with_tts_key,
            management_allowed,
            notification_missing,
            notification_with_admin_key,
            notification_allowed,
        )
    )
    assert ADMIN_KEY not in combined_responses
    assert NOTIFICATION_KEY not in combined_responses
