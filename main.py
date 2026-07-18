import hmac
import os
from contextlib import asynccontextmanager

import uvicorn
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

from voice_mapping_store import (
    find_voice_id_for_sender,
    initialize_database,
)


load_dotenv()


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Initialize local voice-mapping storage once at startup."""

    initialize_database()
    yield


app = FastAPI(lifespan=lifespan)


# Default ElevenLabs voice.
# Unknown senders use this voice.
DEFAULT_VOICE_ID = "pNInz6obpgDQGcFmaJgB"


# Optional shared key for protecting hosted TTS endpoints.
# When this variable is set, clients must send the same value in
# the X-Voice-Glasses-Key request header.
VOICE_GLASSES_API_KEY = os.getenv("VOICE_GLASSES_API_KEY")


class Notification(BaseModel):
    sender: str
    app: str
    message: str


def require_voice_glasses_api_key(
    x_voice_glasses_key: str | None = Header(default=None),
) -> None:
    """
    Require a private app-to-backend key when one is configured.

    Local development can run without VOICE_GLASSES_API_KEY set.
    Hosted deployments should set VOICE_GLASSES_API_KEY so that
    random public requests cannot trigger ElevenLabs generation.
    """

    if not VOICE_GLASSES_API_KEY:
        return

    if not x_voice_glasses_key:
        raise HTTPException(
            status_code=401,
            detail="Missing FamiliarVoice Notifications API key.",
        )

    if not hmac.compare_digest(
        x_voice_glasses_key,
        VOICE_GLASSES_API_KEY,
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid FamiliarVoice Notifications API key.",
        )


def get_voice_id(sender: str) -> str:
    """
    Return the voice assigned to a sender.

    Sender matching uses persistent SQLite mappings. Unknown senders
    use the default voice.
    """

    return find_voice_id_for_sender(sender) or DEFAULT_VOICE_ID


def create_audio_stream(
    text: str,
    voice_id: str,
):
    """
    Create a streaming MP3 response from ElevenLabs.
    """

    api_key = os.getenv("ELEVENLABS_API_KEY")

    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="ELEVENLABS_API_KEY is not set.",
        )

    elevenlabs = ElevenLabs(
        api_key=api_key,
    )

    return elevenlabs.text_to_speech.stream(
        voice_id=voice_id,
        output_format="mp3_44100_128",
        text=text,
        model_id="eleven_flash_v2_5",
    )


@app.get("/")
def home():
    """
    Simple public status page.

    The original browser TTS test page was useful during local
    development, but the hosted service should not expose a public
    button that can trigger paid text-to-speech requests.
    """

    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>FamiliarVoice Notifications API</title>
    </head>
    <body>
        <h1>FamiliarVoice Notifications API</h1>
        <p>
            The FamiliarVoice Notifications backend is running.
        </p>
        <p>
            Text-to-speech endpoints are intended for the paired
            Android prototype and can be protected with a private
            app-to-backend key.
        </p>
    </body>
    </html>
    """

    return HTMLResponse(html)


@app.get("/health")
def health():
    """
    Lightweight health check that does not call ElevenLabs.
    """

    return {
        "status": "ok",
        "service": "familiar-voice-notifications",
    }


@app.post("/speak")
def speak(
    text: str,
    _: None = Depends(require_voice_glasses_api_key),
):
    """
    Speak plain text using the default voice.
    """

    if not text.strip():
        raise HTTPException(
            status_code=400,
            detail="Text cannot be empty.",
        )

    audio_stream = create_audio_stream(
        text=text,
        voice_id=DEFAULT_VOICE_ID,
    )

    return StreamingResponse(
        audio_stream,
        media_type="audio/mpeg",
        headers={
            "Content-Disposition":
                'inline; filename="speech.mp3"'
        },
    )


@app.post("/notification")
def notification(
    notification_data: Notification,
    _: None = Depends(require_voice_glasses_api_key),
):
    """
    Convert a notification into speech using
    the voice assigned to its sender.
    """

    if not notification_data.message.strip():
        raise HTTPException(
            status_code=400,
            detail="Notification message cannot be empty.",
        )

    voice_id = get_voice_id(
        notification_data.sender,
    )

    spoken_text = (
        f"{notification_data.sender} says: "
        f"{notification_data.message}"
    )

    audio_stream = create_audio_stream(
        text=spoken_text,
        voice_id=voice_id,
    )

    return StreamingResponse(
        audio_stream,
        media_type="audio/mpeg",
        headers={
            "Content-Disposition":
                'inline; filename="notification.mp3"'
        },
    )


if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
    )
