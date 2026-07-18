import json

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import main


ADMIN_KEY = "synthetic-admin-key"
ADMIN_HEADERS = {
    "X-Voice-Mappings-Admin-Key": ADMIN_KEY,
}


def profile_payload(
    profile_key="sender_one_profile",
    alias="Sender One",
):
    return {
        "profile_key": profile_key,
        "display_name": "Synthetic Sender",
        "voice_id": "synthetic-voice-identifier",
        "aliases": [alias, f"{alias} Full Name"],
    }


def assert_voice_id_is_private(value):
    if isinstance(value, dict):
        assert "voice_id" not in value
        for child in value.values():
            assert_voice_id_is_private(child)
    elif isinstance(value, list):
        for child in value:
            assert_voice_id_is_private(child)


@pytest.fixture
def management_client(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "VOICE_MAPPINGS_DB_PATH",
        str(tmp_path / "api-mappings.sqlite3"),
    )
    monkeypatch.setenv("ZACH_VOICE_ID", "")
    monkeypatch.setenv("ZACH_SENDER_ALIASES", "")
    monkeypatch.setenv("EMILY_VOICE_ID", "")
    monkeypatch.setenv("EMILY_SENDER_ALIASES", "")
    monkeypatch.setattr(main, "VOICE_MAPPINGS_ADMIN_KEY", ADMIN_KEY)

    with TestClient(main.app) as client:
        yield client


def test_management_authentication_behavior(management_client, monkeypatch):
    monkeypatch.setattr(main, "VOICE_MAPPINGS_ADMIN_KEY", None)
    unavailable = management_client.get("/voice-profiles")
    assert unavailable.status_code == 503
    assert unavailable.json() == {
        "detail": "Voice mapping management is not configured."
    }

    monkeypatch.setattr(main, "VOICE_MAPPINGS_ADMIN_KEY", ADMIN_KEY)
    missing = management_client.get("/voice-profiles")
    incorrect = management_client.get(
        "/voice-profiles",
        headers={"X-Voice-Mappings-Admin-Key": "incorrect-key"},
    )
    correct = management_client.get(
        "/voice-profiles",
        headers=ADMIN_HEADERS,
    )

    assert missing.status_code == 401
    assert incorrect.status_code == 401
    assert correct.status_code == 200


def test_management_rejects_tts_key_without_admin_key(
    management_client,
    monkeypatch,
):
    monkeypatch.setattr(main, "VOICE_GLASSES_API_KEY", "synthetic-tts-key")

    response = management_client.get(
        "/voice-profiles",
        headers={"X-Voice-Glasses-Key": "synthetic-tts-key"},
    )

    assert response.status_code == 401


def test_existing_tts_authentication_dependency(monkeypatch):
    monkeypatch.setattr(main, "VOICE_GLASSES_API_KEY", "synthetic-tts-key")

    assert main.require_voice_glasses_api_key("synthetic-tts-key") is None

    with pytest.raises(HTTPException) as error:
        main.require_voice_glasses_api_key("incorrect-key")

    assert error.value.status_code == 401


def test_unexpected_storage_failure_returns_generic_response(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv(
        "VOICE_MAPPINGS_DB_PATH",
        str(tmp_path / "failure-mappings.sqlite3"),
    )
    monkeypatch.setenv("ZACH_VOICE_ID", "")
    monkeypatch.setenv("ZACH_SENDER_ALIASES", "")
    monkeypatch.setenv("EMILY_VOICE_ID", "")
    monkeypatch.setenv("EMILY_SENDER_ALIASES", "")
    monkeypatch.setattr(main, "VOICE_MAPPINGS_ADMIN_KEY", ADMIN_KEY)

    def raise_synthetic_storage_failure():
        raise RuntimeError(
            r"synthetic SQLite failure at C:\private\voice_mappings.sqlite3"
        )

    monkeypatch.setattr(
        main,
        "list_voice_profiles",
        raise_synthetic_storage_failure,
    )

    with TestClient(main.app, raise_server_exceptions=False) as client:
        response = client.get(
            "/voice-profiles",
            headers=ADMIN_HEADERS,
        )

    assert response.status_code == 500
    assert response.text == "Internal Server Error"

    lowered_response = response.text.casefold()
    for forbidden_text in (
        "sqlite",
        "private",
        "voice_mappings.sqlite3",
        "synthetic",
        "sql",
        "voice_id",
        "alias",
        "traceback",
    ):
        assert forbidden_text not in lowered_response


def test_profile_and_alias_crud(management_client):
    created = management_client.post(
        "/voice-profiles",
        headers=ADMIN_HEADERS,
        json=profile_payload(),
    )
    assert created.status_code == 201
    created_profile = created.json()
    profile_id = created_profile["id"]
    first_alias_id = created_profile["aliases"][0]["id"]
    assert created_profile["voice_id_configured"] is True
    assert_voice_id_is_private(created_profile)

    listed = management_client.get(
        "/voice-profiles",
        headers=ADMIN_HEADERS,
    )
    read = management_client.get(
        f"/voice-profiles/{profile_id}",
        headers=ADMIN_HEADERS,
    )
    assert listed.status_code == 200
    assert read.status_code == 200
    assert listed.json() == [read.json()]
    assert_voice_id_is_private(listed.json())

    updated = management_client.patch(
        f"/voice-profiles/{profile_id}",
        headers=ADMIN_HEADERS,
        json={
            "profile_key": "updated_profile",
            "display_name": "Updated Synthetic Sender",
            "voice_id": "updated-synthetic-voice-identifier",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["profile_key"] == "updated_profile"
    assert updated.json()["display_name"] == "Updated Synthetic Sender"
    assert_voice_id_is_private(updated.json())

    alias_created = management_client.post(
        f"/voice-profiles/{profile_id}/aliases",
        headers=ADMIN_HEADERS,
        json={"alias": "  Added   Synthetic Alias "},
    )
    assert alias_created.status_code == 201
    assert alias_created.json()["normalized_alias"] == "added synthetic alias"

    alias_id = alias_created.json()["id"]
    alias_updated = management_client.patch(
        f"/sender-aliases/{alias_id}",
        headers=ADMIN_HEADERS,
        json={"alias": "Replacement Synthetic Alias"},
    )
    assert alias_updated.status_code == 200
    assert (
        alias_updated.json()["normalized_alias"]
        == "replacement synthetic alias"
    )

    alias_deleted = management_client.delete(
        f"/sender-aliases/{alias_id}",
        headers=ADMIN_HEADERS,
    )
    assert alias_deleted.status_code == 204
    assert alias_deleted.content == b""

    final_alias_deleted = management_client.delete(
        f"/sender-aliases/{first_alias_id}",
        headers=ADMIN_HEADERS,
    )
    assert final_alias_deleted.status_code == 204

    profile_deleted = management_client.delete(
        f"/voice-profiles/{profile_id}",
        headers=ADMIN_HEADERS,
    )
    assert profile_deleted.status_code == 204
    assert profile_deleted.content == b""


def test_duplicate_profile_key_returns_conflict(management_client):
    first = management_client.post(
        "/voice-profiles",
        headers=ADMIN_HEADERS,
        json=profile_payload(),
    )
    duplicate = management_client.post(
        "/voice-profiles",
        headers=ADMIN_HEADERS,
        json=profile_payload(alias="Different Alias"),
    )

    assert first.status_code == 201
    assert duplicate.status_code == 409
    assert "synthetic-voice-identifier" not in duplicate.text


def test_duplicate_alias_returns_conflict(management_client):
    first = management_client.post(
        "/voice-profiles",
        headers=ADMIN_HEADERS,
        json=profile_payload(),
    )
    second = management_client.post(
        "/voice-profiles",
        headers=ADMIN_HEADERS,
        json=profile_payload(
            profile_key="sender_two_profile",
            alias="Sender Two",
        ),
    )

    duplicate = management_client.post(
        f"/voice-profiles/{second.json()['id']}/aliases",
        headers=ADMIN_HEADERS,
        json={"alias": first.json()["aliases"][0]["normalized_alias"]},
    )

    assert duplicate.status_code == 409


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("get", "/voice-profiles/999", None),
        ("patch", "/voice-profiles/999", {"display_name": "Missing"}),
        ("delete", "/voice-profiles/999", None),
        ("post", "/voice-profiles/999/aliases", {"alias": "Missing"}),
        ("patch", "/sender-aliases/999", {"alias": "Missing"}),
        ("delete", "/sender-aliases/999", None),
    ],
)
def test_unknown_ids_return_not_found(
    management_client,
    method,
    path,
    body,
):
    response = management_client.request(
        method,
        path,
        headers=ADMIN_HEADERS,
        json=body,
    )
    assert response.status_code == 404


@pytest.mark.parametrize(
    "payload",
    [
        {
            "profile_key": "MixedCase",
            "display_name": "Synthetic",
            "voice_id": "synthetic-private-value",
            "aliases": ["Alias"],
        },
        {
            "profile_key": "valid_key",
            "display_name": "   ",
            "voice_id": "synthetic-private-value",
            "aliases": ["Alias"],
        },
        {
            "profile_key": "valid_key",
            "display_name": "Synthetic",
            "voice_id": "   ",
            "aliases": ["Alias"],
        },
        {
            "profile_key": "valid_key",
            "display_name": "Synthetic",
            "voice_id": "synthetic-private-value",
            "aliases": ["   "],
        },
    ],
)
def test_invalid_create_payloads_return_safe_validation_error(
    management_client,
    payload,
):
    response = management_client.post(
        "/voice-profiles",
        headers=ADMIN_HEADERS,
        json=payload,
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "Invalid management request."}
    assert "synthetic-private-value" not in response.text


@pytest.mark.parametrize(
    ("field_name", "field_value"),
    [
        ("profile_key", "a" * 65),
        ("display_name", "D" * 101),
        ("voice_id", "v" * 256),
        ("aliases", ["a" * 201]),
    ],
)
def test_oversized_create_values_are_rejected_without_echo(
    management_client,
    field_name,
    field_value,
):
    payload = profile_payload()
    payload[field_name] = field_value

    response = management_client.post(
        "/voice-profiles",
        headers=ADMIN_HEADERS,
        json=payload,
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "Invalid management request."}


@pytest.mark.parametrize("payload", [{}, {"voice_id": None}])
def test_empty_or_null_patch_returns_safe_validation_error(
    management_client,
    payload,
):
    response = management_client.patch(
        "/voice-profiles/1",
        headers=ADMIN_HEADERS,
        json=payload,
    )
    assert response.status_code == 422
    assert response.json() == {"detail": "Invalid management request."}


@pytest.mark.parametrize(
    "payload",
    [
        {"profile_key": "MixedCase"},
        {"profile_key": None},
        {"display_name": None},
        {"voice_id": None},
    ],
)
def test_invalid_patch_values_are_rejected(
    management_client,
    payload,
):
    response = management_client.patch(
        "/voice-profiles/1",
        headers=ADMIN_HEADERS,
        json=payload,
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "Invalid management request."}


def test_duplicate_aliases_in_create_are_deduplicated(management_client):
    payload = profile_payload()
    payload["aliases"] = ["Synthetic Alias", " SYNTHETIC   ALIAS "]

    response = management_client.post(
        "/voice-profiles",
        headers=ADMIN_HEADERS,
        json=payload,
    )

    assert response.status_code == 201
    assert len(response.json()["aliases"]) == 1


def test_actual_final_alias_can_be_deleted(management_client):
    payload = profile_payload()
    payload["aliases"] = ["Only Synthetic Alias"]
    created = management_client.post(
        "/voice-profiles",
        headers=ADMIN_HEADERS,
        json=payload,
    )
    assert created.status_code == 201

    profile_id = created.json()["id"]
    alias_id = created.json()["aliases"][0]["id"]
    deleted = management_client.delete(
        f"/sender-aliases/{alias_id}",
        headers=ADMIN_HEADERS,
    )
    profile = management_client.get(
        f"/voice-profiles/{profile_id}",
        headers=ADMIN_HEADERS,
    )

    assert deleted.status_code == 204
    assert deleted.content == b""
    assert profile.status_code == 200
    assert profile.json()["aliases"] == []


def test_public_status_endpoints_remain_unchanged(management_client):
    health = management_client.get("/health")
    root = management_client.get("/")

    assert health.status_code == 200
    assert health.json() == {
        "status": "ok",
        "service": "familiar-voice-notifications",
    }
    assert root.status_code == 200
    assert "FamiliarVoice Notifications API" in root.text
    assert "voice_id" not in json.dumps(health.json())
