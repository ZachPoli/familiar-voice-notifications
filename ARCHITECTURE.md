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
- ElevenLabs Python client
- python-dotenv

Current backend routes:

```text
GET  /              public status page
GET  /health        lightweight health check
POST /speak         text-to-speech test endpoint
POST /notification  notification-to-speech endpoint
```

When `VOICE_GLASSES_API_KEY` is set on the backend, `/speak` and `/notification` require the matching `X-Voice-Glasses-Key` request header.

---

## Backend Configuration

The backend loads private configuration from environment variables:

```text
ELEVENLABS_API_KEY
ZACH_VOICE_ID
EMILY_VOICE_ID
VOICE_GLASSES_API_KEY
```

`ELEVENLABS_API_KEY` is required for speech generation.

`ZACH_VOICE_ID` and `EMILY_VOICE_ID` are prototype sender-specific voice mappings.

`VOICE_GLASSES_API_KEY` protects hosted TTS endpoints from unauthenticated public use.

---

## Voice Routing

The backend currently performs simple case-insensitive sender-name matching.

Current logical behavior:

```text
sender = Emily
    ↓
EMILY_VOICE_ID

sender = Zach
    ↓
ZACH_VOICE_ID

any other sender
    ↓
DEFAULT_VOICE_ID
```

This is an MVP-level routing system. Future versions should replace hard-coded sender names with persistent user-managed contact-to-voice mappings.

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
- sender-to-voice mappings are hard-coded,
- no persistent database is implemented,
- no contact-management UI exists yet,
- no voice-assignment UI exists yet,
- no explicit audio queue exists yet,
- network retry behavior is limited,
- offline behavior is not implemented,
- automated tests are not yet added,
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
