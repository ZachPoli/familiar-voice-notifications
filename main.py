import hmac
import os
import re
from contextlib import asynccontextmanager
from typing import NoReturn

import uvicorn
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
from fastapi import (
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Request,
    Response,
)
from fastapi.exception_handlers import (
    request_validation_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, field_validator, model_validator

from voice_mapping_store import (
    ProfileKeyConflictError,
    SenderAliasConflictError,
    SenderAliasNotFoundError,
    VoiceProfileNotFoundError,
    add_sender_alias,
    add_voice_profile,
    delete_sender_alias,
    delete_voice_profile,
    find_voice_id_for_sender,
    get_voice_profile,
    initialize_database,
    list_voice_profiles,
    normalize_alias,
    update_sender_alias,
    update_voice_profile,
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


# Separate administrator key for the voice-mapping management API.
# Management is disabled unless this value is configured.
VOICE_MAPPINGS_ADMIN_KEY = os.getenv("VOICE_MAPPINGS_ADMIN_KEY")


PROFILE_KEY_PATTERN = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}")


class Notification(BaseModel):
    sender: str
    app: str
    message: str


def validate_profile_key(value: str) -> str:
    cleaned_value = value.strip()
    if not PROFILE_KEY_PATTERN.fullmatch(cleaned_value):
        raise ValueError("Invalid profile key.")
    return cleaned_value


def validate_display_name(value: str) -> str:
    cleaned_value = value.strip()
    if not cleaned_value or len(cleaned_value) > 100:
        raise ValueError("Invalid display name.")
    return cleaned_value


def validate_voice_id(value: str) -> str:
    cleaned_value = value.strip()
    if not cleaned_value or len(cleaned_value) > 255:
        raise ValueError("Invalid voice ID.")
    return cleaned_value


def validate_sender_alias(value: str) -> str:
    normalized_alias = normalize_alias(value)
    if not normalized_alias or len(normalized_alias) > 200:
        raise ValueError("Invalid sender alias.")
    return normalized_alias


class VoiceProfileCreate(BaseModel):
    profile_key: str
    display_name: str
    voice_id: str
    aliases: list[str]

    _validate_profile_key = field_validator("profile_key")(
        validate_profile_key
    )
    _validate_display_name = field_validator("display_name")(
        validate_display_name
    )
    _validate_voice_id = field_validator("voice_id")(validate_voice_id)

    @field_validator("aliases")
    @classmethod
    def validate_aliases(cls, aliases: list[str]) -> list[str]:
        normalized_aliases = []
        seen_aliases = set()

        for alias in aliases:
            normalized_alias = validate_sender_alias(alias)
            if normalized_alias not in seen_aliases:
                normalized_aliases.append(normalized_alias)
                seen_aliases.add(normalized_alias)

        if not normalized_aliases:
            raise ValueError("At least one sender alias is required.")

        return normalized_aliases


class VoiceProfileUpdate(BaseModel):
    profile_key: str | None = None
    display_name: str | None = None
    voice_id: str | None = None

    @field_validator("profile_key")
    @classmethod
    def validate_optional_profile_key(cls, value: str | None):
        return None if value is None else validate_profile_key(value)

    @field_validator("display_name")
    @classmethod
    def validate_optional_display_name(cls, value: str | None):
        return None if value is None else validate_display_name(value)

    @field_validator("voice_id")
    @classmethod
    def validate_optional_voice_id(cls, value: str | None):
        return None if value is None else validate_voice_id(value)

    @model_validator(mode="after")
    def require_supplied_values(self):
        if not self.model_fields_set:
            raise ValueError("At least one profile field is required.")

        if any(
            getattr(self, field_name) is None
            for field_name in self.model_fields_set
        ):
            raise ValueError("Profile fields cannot be null.")

        return self


class SenderAliasCreate(BaseModel):
    alias: str

    _validate_alias = field_validator("alias")(validate_sender_alias)


class SenderAliasUpdate(BaseModel):
    alias: str

    _validate_alias = field_validator("alias")(validate_sender_alias)


class SenderAliasResponse(BaseModel):
    id: int
    normalized_alias: str


class VoiceProfileResponse(BaseModel):
    id: int
    profile_key: str
    display_name: str
    voice_id_configured: bool
    aliases: list[SenderAliasResponse]


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


def require_voice_mappings_admin_key(
    x_voice_mappings_admin_key: str | None = Header(default=None),
) -> None:
    """Require the separate administrator key for mapping management."""

    if not VOICE_MAPPINGS_ADMIN_KEY:
        raise HTTPException(
            status_code=503,
            detail="Voice mapping management is not configured.",
        )

    if not x_voice_mappings_admin_key or not hmac.compare_digest(
        x_voice_mappings_admin_key,
        VOICE_MAPPINGS_ADMIN_KEY,
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid voice mapping management credentials.",
        )


def raise_voice_mapping_http_error(error: ValueError) -> NoReturn:
    """Translate storage-domain errors without exposing private data."""

    if isinstance(error, VoiceProfileNotFoundError):
        raise HTTPException(
            status_code=404,
            detail="Voice profile not found.",
        ) from error

    if isinstance(error, SenderAliasNotFoundError):
        raise HTTPException(
            status_code=404,
            detail="Sender alias not found.",
        ) from error

    if isinstance(error, ProfileKeyConflictError):
        raise HTTPException(
            status_code=409,
            detail="A voice profile with that profile key already exists.",
        ) from error

    if isinstance(error, SenderAliasConflictError):
        raise HTTPException(
            status_code=409,
            detail="That sender alias is already assigned.",
        ) from error

    raise HTTPException(
        status_code=422,
        detail="Invalid voice mapping request.",
    ) from error


def is_management_path(path: str) -> bool:
    return path.startswith("/voice-profiles") or path.startswith(
        "/sender-aliases"
    )


@app.exception_handler(RequestValidationError)
async def safe_request_validation_error(
    request: Request,
    error: RequestValidationError,
):
    """Prevent management validation responses from echoing private input."""

    if is_management_path(request.url.path):
        return JSONResponse(
            status_code=422,
            content={"detail": "Invalid management request."},
        )

    return await request_validation_exception_handler(request, error)


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


@app.get(
    "/voice-profiles",
    response_model=list[VoiceProfileResponse],
)
def read_voice_profiles(
    _: None = Depends(require_voice_mappings_admin_key),
):
    """List voice profiles without exposing their voice IDs."""

    return list_voice_profiles()


@app.post(
    "/voice-profiles",
    response_model=VoiceProfileResponse,
    status_code=201,
)
def create_voice_profile(
    profile: VoiceProfileCreate,
    _: None = Depends(require_voice_mappings_admin_key),
):
    """Create a voice profile and its initial aliases."""

    try:
        profile_id = add_voice_profile(
            profile.profile_key,
            profile.display_name,
            profile.voice_id,
            profile.aliases,
        )
        return get_voice_profile(profile_id)
    except ValueError as error:
        raise_voice_mapping_http_error(error)


@app.get(
    "/voice-profiles/{profile_id}",
    response_model=VoiceProfileResponse,
)
def read_voice_profile(
    profile_id: int,
    _: None = Depends(require_voice_mappings_admin_key),
):
    """Read one voice profile without exposing its voice ID."""

    try:
        return get_voice_profile(profile_id)
    except ValueError as error:
        raise_voice_mapping_http_error(error)


@app.patch(
    "/voice-profiles/{profile_id}",
    response_model=VoiceProfileResponse,
)
def edit_voice_profile(
    profile_id: int,
    profile: VoiceProfileUpdate,
    _: None = Depends(require_voice_mappings_admin_key),
):
    """Update supplied voice-profile fields."""

    updates = profile.model_dump(
        exclude_unset=True,
        exclude_none=True,
    )

    try:
        return update_voice_profile(profile_id, **updates)
    except ValueError as error:
        raise_voice_mapping_http_error(error)


@app.delete(
    "/voice-profiles/{profile_id}",
    status_code=204,
)
def remove_voice_profile(
    profile_id: int,
    _: None = Depends(require_voice_mappings_admin_key),
):
    """Delete a voice profile and its aliases."""

    try:
        delete_voice_profile(profile_id)
    except ValueError as error:
        raise_voice_mapping_http_error(error)

    return Response(status_code=204)


@app.post(
    "/voice-profiles/{profile_id}/aliases",
    response_model=SenderAliasResponse,
    status_code=201,
)
def create_sender_alias(
    profile_id: int,
    alias: SenderAliasCreate,
    _: None = Depends(require_voice_mappings_admin_key),
):
    """Add a normalized sender alias to a voice profile."""

    try:
        return add_sender_alias(profile_id, alias.alias)
    except ValueError as error:
        raise_voice_mapping_http_error(error)


@app.patch(
    "/sender-aliases/{alias_id}",
    response_model=SenderAliasResponse,
)
def edit_sender_alias(
    alias_id: int,
    alias: SenderAliasUpdate,
    _: None = Depends(require_voice_mappings_admin_key),
):
    """Replace one sender alias with a normalized value."""

    try:
        return update_sender_alias(alias_id, alias.alias)
    except ValueError as error:
        raise_voice_mapping_http_error(error)


@app.delete(
    "/sender-aliases/{alias_id}",
    status_code=204,
)
def remove_sender_alias(
    alias_id: int,
    _: None = Depends(require_voice_mappings_admin_key),
):
    """Delete one sender alias, including a profile's final alias."""

    try:
        delete_sender_alias(alias_id)
    except ValueError as error:
        raise_voice_mapping_http_error(error)

    return Response(status_code=204)


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
