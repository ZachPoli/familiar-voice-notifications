import main


def test_get_voice_id_returns_stored_mapping(monkeypatch):
    monkeypatch.setattr(
        main,
        "find_voice_id_for_sender",
        lambda sender: "stored-voice",
    )

    assert main.get_voice_id("Known Sender") == "stored-voice"


def test_get_voice_id_uses_default_for_unknown_sender(monkeypatch):
    monkeypatch.setattr(
        main,
        "find_voice_id_for_sender",
        lambda sender: None,
    )

    assert main.get_voice_id("Unknown Sender") == main.DEFAULT_VOICE_ID
