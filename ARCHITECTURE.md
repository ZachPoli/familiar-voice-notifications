# Voice Glasses — Architecture

## Purpose

This document describes the current technical architecture of the Voice Glasses MVP.

It explains:

- what components exist,
- what each component does,
- how message data moves through the system,
- how audio is generated and played,
- where private configuration lives,
- and which parts are still prototype limitations.

---

## System Overview

Voice Glasses currently consists of four major runtime components:

```text
Android Phone
    │
    │ notification detected
    ▼
Voice Glasses Android App
    │
    │ HTTPS POST with sender/app/message
    ▼
FastAPI Backend
    │
    │ ElevenLabs TTS request
    ▼
ElevenLabs
    │
    │ MP3 audio stream
    ▼
FastAPI Backend
    │
    │ audio/mpeg response
    ▼
Android App
    │
    │ MediaPlayer playback
    ▼
Android Active Media Route
    │
    ▼
Ray-Ban Meta Glasses
```

The current prototype has been tested end-to-end using real SMS messages and physical hardware.

---

## Android App

Primary files:

```text
android/app/src/main/java/com/zachpoli/voiceglasses/MainActivity.kt
android/app/src/main/java/com/zachpoli/voiceglasses/VoiceNotificationListener.kt
```

The Android app has two main responsibilities:

1. Provide a simple master enable/pause control.
2. Listen for supported notifications and send valid message data to the backend.

The master switch is stored with Android SharedPreferences so the selected state survives app restarts.

---

## Android Notification Listener

The listener is implemented with:

```text
NotificationListenerService
```

The listener performs this decision flow:

```text
Android notification posted
        ↓
Read master switch preference
        ↓
Is Voice Glasses enabled?
        │
        ├── No → stop
        │
        └── Yes
               ↓
Check package name
        ↓
Is package allowed?
        │
        ├── No → stop
        │
        └── Yes
               ↓
Extract title as sender
        ↓
Extract text as message
        ↓
Reject blank sender/message
        ↓
POST valid notification to backend
        ↓
Receive MP3 bytes
        ↓
Play with MediaPlayer
```

The current MVP only allows Google Messages:

```text
com.google.android.apps.messaging
```

This prevents unrelated notifications from being sent to the backend and converted into speech.

---

## Android Configuration

Environment-specific Android values are not hard-coded in source.

The Android Gradle build reads private local configuration from:

```text
android/local.properties
```

The committed template is:

```text
android/local.properties.example
```

Current Android configuration values:

```text
VOICE_GLASSES_SERVER_URL
VOICE_GLASSES_API_KEY
```

`VOICE_GLASSES_SERVER_URL` points to the backend `/notification` endpoint.

`VOICE_GLASSES_API_KEY` is sent as this HTTP header when present:

```text
X-Voice-Glasses-Key
```

`android/local.properties` is ignored by Git.

---

## Backend

Primary file:

```text
main.py
```

Runtime:

```text
Python 3.12
```

Main backend technologies:

- FastAPI
- Uvicorn
- Pydantic
- Python `sqlite3`
- ElevenLabs Python client
- python-dotenv

Current backend routes:

```text
GET  /              public status page
GET  /health        lightweight health check
POST /speak         text-to-speech test endpoint
POST /notification  notification-to-speech endpoint
GET/POST/PATCH/DELETE /voice-profiles management endpoints
POST   /voice-profiles/{profile_id}/aliases
PATCH/DELETE /sender-aliases/{alias_id}
```

When `VOICE_GLASSES_API_KEY` is set on the backend, `/speak` and `/notification` require the matching `X-Voice-Glasses-Key` request header.

Voice-mapping management uses a separate administrator boundary.
Management routes require `VOICE_MAPPINGS_ADMIN_KEY` through the
`X-Voice-Mappings-Admin-Key` request header. If the server key is not
configured, management is disabled with a `503` response. This admin key
must not be embedded in the Android app.

---

## Backend Configuration

The backend loads private configuration from environment variables:

```text
ELEVENLABS_API_KEY
ZACH_VOICE_ID
EMILY_VOICE_ID
ZACH_SENDER_ALIASES
EMILY_SENDER_ALIASES
VOICE_GLASSES_API_KEY
VOICE_MAPPINGS_ADMIN_KEY
VOICE_MAPPINGS_DB_PATH
```

`ELEVENLABS_API_KEY` is required for speech generation.

The `ZACH_*` and `EMILY_*` values are optional first-run seed inputs for
the SQLite voice-mapping database. They are not reapplied after bootstrap.

`VOICE_GLASSES_API_KEY` protects hosted TTS endpoints from unauthenticated public use.

`VOICE_MAPPINGS_ADMIN_KEY` separately protects profile and alias management.
It is prototype administrator authentication rather than production user
authentication. Management responses never return full or partial voice
IDs; they report only whether a voice ID is configured.

`VOICE_MAPPINGS_DB_PATH` selects the SQLite database location. Its local
default is `data/voice_mappings.sqlite3`, resolved from the backend
directory rather than the current shell directory. The default database
and its sidecar files are ignored by Git. Hosted environments require a
durable mounted location if mappings must persist across deployments.

---

## Voice Routing

The backend uses SQLite voice profiles and sender aliases. One voice
profile can own multiple aliases. Aliases are stripped, case-folded, and
have repeated whitespace collapsed before they are stored or matched.

On the first startup of a completely empty database, environment mappings
can seed the initial profiles and aliases. SQLite becomes the source of
truth after that bootstrap. Later environment changes do not overwrite,
resynchronize, or recreate user-edited mappings. A populated database
without bootstrap metadata is treated as user-owned and is not seeded.

Current logical behavior:

```text
normalized sender matches a stored alias
    ↓
stored voice ID

unknown sender
    ↓
DEFAULT_VOICE_ID
```

The SQLite file contains private sender aliases and voice IDs. It is
prototype storage and is not encrypted. A contact-management and
voice-assignment interface is not part of this foundation milestone.

---

## Voice-Mapping Management Flow

```text
Administrator request
        ↓
X-Voice-Mappings-Admin-Key validation
        ↓
Pydantic request validation
        ↓
Transactional SQLite profile or alias operation
        ↓
Response with normalized aliases and voice-ID configured state
```

Profile creation and updates accept voice IDs as write-only values. Reads
return profile IDs, profile keys, display names, normalized aliases, and a
boolean configured state. Profile deletion uses the SQLite foreign key to
cascade-delete aliases. Duplicate profile keys or aliases return safe
client errors without exposing SQLite details or private values.

Notification authentication and management authentication remain separate:
the Android notification flow continues to use `VOICE_GLASSES_API_KEY`,
while only administrator tooling should use `VOICE_MAPPINGS_ADMIN_KEY`.
SQLite remains unencrypted prototype storage, and hosted deployments still
need durable mounted storage for persistence.

---

## Local Persistence Verification

Milestone 15C-1 exercises the storage and management layers without using
the normal local database. Integration tests create synthetic mappings in
temporary SQLite files, cross multiple FastAPI lifespan contexts, mock the
audio-generation boundary, and verify that notification and management
credentials cannot substitute for one another.

The count-only bootstrap helper requires an explicit new temporary path. It
may load local environment configuration but returns only approved counts
and boolean validation results. It does not return profile identifiers,
display names, aliases, voice IDs, credentials, environment values, or
database rows.

The process-restart verifier launches separate short-lived Uvicorn
processes against the same synthetic temporary database. It creates a
mapping, stops the first process, verifies persistence from a second
process, deletes the mapping, stops the server, and removes the database
and SQLite sidecars even when verification fails.

Hosted persistence assessment and the real Android SMS test are deferred
to Milestone 15C-2. Before those tests, the deployed repository source,
durable disk, mount path, and hosted database configuration must be
confirmed. The existing Android notification flow remains unchanged.

---

## Audio Generation and Playback

The backend sends text to ElevenLabs and returns the generated MP3 stream to Android.

Android writes the returned MP3 bytes to a temporary cache file and plays that file through MediaPlayer.

The audio then follows Android's active media route. During physical testing, that route was Ray-Ban Meta glasses.

Voice Glasses does not use a private Ray-Ban Meta API.

---

## Privacy Boundary

The current prototype sends message content through this path:

```text
Android phone
    ↓
FastAPI backend
    ↓
ElevenLabs
    ↓
FastAPI backend
    ↓
Android phone
```

This means message content can leave the device during speech generation.

The current public-readiness security pass adds app-key protection for hosted TTS endpoints, but the project does not yet include full user accounts, per-user authorization, or production-grade secret management.

Voice cloning and familiar-voice features should be used only with appropriate consent.

---

## Current Prototype Limitations

The current implementation is intentionally simple.

Known limitations:

- only Google Messages is supported,
- SQLite mappings do not yet have a user-facing management workflow,
- the prototype SQLite database is not encrypted,
- no contact-management UI exists yet,
- no voice-assignment UI exists yet,
- no explicit audio queue exists yet,
- network retry behavior is limited,
- offline behavior is not implemented,
- automated coverage is currently focused on SQLite storage behavior,
- and the current app-key protection is not a full production authentication system.

---

## Next Architecture Priorities

The next major architecture improvements are:

```text
persistent contact-to-voice mappings
        ↓
contact voice-assignment UI
        ↓
explicit audio queue
        ↓
retry/offline behavior
        ↓
stronger production authentication
```
