# FamiliarVoice Notifications

**An accessibility-focused Android prototype that reads incoming messages aloud using sender-specific familiar voices through connected audio devices.**

Originally developed under the working name Voice Glasses, this MVP was physically tested with Ray-Ban Meta glasses, but the core concept is not limited to glasses. It can support smart glasses, Bluetooth earbuds, phone speakers, hearing devices, and other Android media outputs.

> Built from a personal idea: my father and grandmother are blind, and I wanted messages from family to feel more personal than hearing every message through the same generic synthetic voice.

---

## Demo

Watch the finished MVP demo:

- [`demo/voice-glasses-mvp-demo.mp4`](demo/voice-glasses-mvp-demo.mp4)
- [`DEMO.md`](DEMO.md) for the demo flow, technical explanation, and testing notes.

The approximately 31-second recording demonstrates the FamiliarVoice Notifications master speech control, a real SMS notification arriving, sender-specific speech generation, the FastAPI and ElevenLabs processing path, and the connected Ray-Ban Meta media route used during physical testing.

---

## Current Status

**Working end-to-end MVP prototype**

FamiliarVoice Notifications has been physically tested with:

- a Google Pixel 10a as the receiving device,
- a Google Pixel 7a as the SMS sender,
- real SMS messages through Google Messages,
- a Python FastAPI backend,
- a hosted backend deployment,
- ElevenLabs text-to-speech,
- sender-specific custom and cloned voices,
- and Ray-Ban Meta glasses for audio playback.

The current working flow is:

```text
Real text message arrives
        ↓
Android notification listener detects it
        ↓
The app checks whether speech is enabled
        ↓
Unsupported notifications are filtered out
        ↓
Sender and message text are extracted
        ↓
Android sends the message data to FastAPI
        ↓
Backend validates the request
        ↓
Backend selects the sender's assigned voice
        ↓
ElevenLabs generates speech
        ↓
MP3 audio returns to Android
        ↓
Android plays the audio through the active media route
        ↓
Audio is heard through Ray-Ban Meta glasses
```

---

## Why I Built This

FamiliarVoice Notifications was inspired by my father and grandmother, who are blind.

Modern devices can already read notifications aloud, but the experience is usually impersonal: every message is spoken using the same system-generated voice.

The idea behind the project is simple:

> What if a message from someone you love could sound like that person?

The current prototype explores that idea by connecting Android notification processing with sender-specific voice mappings and generated speech.

The broader concept could eventually support familiar-voice messaging through smart glasses, Bluetooth earbuds, phone speakers, hearing devices, and other accessible audio outputs.

---

## What the MVP Does

The current MVP can:

- detect incoming Android notifications,
- process real Google Messages notifications,
- ignore notifications from unsupported applications,
- reject background notifications that do not contain a real sender,
- extract sender and message text,
- pause or enable message speech with a master switch,
- preserve the switch state across app restarts,
- send message data to a FastAPI backend,
- optionally require a private app-to-backend key for TTS endpoints,
- map different senders to different voices,
- use a default voice for unmapped senders,
- generate speech through ElevenLabs,
- return MP3 audio to Android,
- play generated audio through Android's active media route,
- and output speech through connected Ray-Ban Meta glasses.

---

## Example

A message arrives from a contact named Zach:

```text
Sender: Zach
Message: Message one.
```

The backend identifies the sender mapping:

```text
Zach
    ↓
Zach voice profile
```

The spoken result is generated as:

```text
Zach says: Message one.
```

The resulting audio is returned to the Android phone and played through the current media output.

---

## Architecture

```text
┌──────────────────────────────┐
│        Android Phone         │
│                              │
│ Google Messages notification │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│     FamiliarVoice Android    │
│                              │
│ NotificationListenerService  │
│ Master switch check          │
│ Package filtering            │
│ Sender/message extraction    │
└──────────────┬───────────────┘
               │
               │ HTTPS POST /notification
               ▼
┌──────────────────────────────┐
│       FastAPI Backend        │
│                              │
│ Request validation           │
│ Optional app-key check       │
│ Sender → voice mapping       │
│ TTS request preparation      │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│          ElevenLabs          │
│                              │
│   Text-to-speech generation  │
└──────────────┬───────────────┘
               │
               │ MP3 audio
               ▼
┌──────────────────────────────┐
│        Android Phone         │
│                              │
│ Temporary audio file         │
│ MediaPlayer playback         │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│    Android Media Output      │
│                              │
│    Ray-Ban Meta glasses      │
└──────────────────────────────┘
```

For deeper technical notes, see:

- [`ARCHITECTURE.md`](ARCHITECTURE.md)
- [`PROJECT_STATE.md`](PROJECT_STATE.md)
- [`ROADMAP.md`](ROADMAP.md)
- [`AI_WORKFLOW.md`](AI_WORKFLOW.md)

---

## Technology Stack

### Android

- Kotlin
- Android SDK
- Jetpack Compose
- NotificationListenerService
- SharedPreferences
- HttpURLConnection
- MediaPlayer

### Backend

- Python 3.12
- FastAPI
- Uvicorn
- Pydantic
- python-dotenv
- Render for hosted deployment testing

### Voice Generation

- ElevenLabs text-to-speech
- sender-specific voice IDs
- custom voice testing
- cloned voice testing
- MP3 streaming responses

### Development and Testing

- Windows 11
- Android Studio
- Git
- GitHub
- physical Android devices
- Ray-Ban Meta glasses

---

## Backend Configuration

The backend reads private configuration from environment variables.

Create a local `.env` file for development:

```text
ELEVENLABS_API_KEY=your_api_key
ZACH_VOICE_ID=your_zach_voice_id
EMILY_VOICE_ID=your_emily_voice_id
ZACH_SENDER_ALIASES=sender_one,sender_one_full_name
EMILY_SENDER_ALIASES=sender_two
VOICE_GLASSES_API_KEY=your_private_shared_app_key
VOICE_MAPPINGS_ADMIN_KEY=your_private_management_admin_key
VOICE_MAPPINGS_DB_PATH=data/voice_mappings.sqlite3
```

Do not commit `.env`.

`VOICE_GLASSES_API_KEY` is optional for local development. When it is set, `/speak` and `/notification` require clients to send the same value in this HTTP header:

```text
X-Voice-Glasses-Key
```

This protects the hosted backend from random public requests triggering ElevenLabs text-to-speech generation.

### Voice-Mapping Storage

The backend stores sender-to-voice mappings in SQLite. On the first
startup of a completely empty database, the current `ZACH_*` and
`EMILY_*` environment values can bootstrap voice profiles and normalized
sender aliases. Each profile requires both a nonblank voice-ID variable
and at least one explicitly configured alias; no implicit default aliases
are assigned. After that one-time bootstrap, SQLite is the source of truth:
later environment changes do not overwrite, resynchronize, or recreate
database mappings.

The default local database path is:

```text
data/voice_mappings.sqlite3
```

That generated file and its SQLite sidecar files are ignored by Git.
Set `VOICE_MAPPINGS_DB_PATH` to use a different location. Hosted
environments need to place the database on durable mounted storage if
mappings must survive deployments or instance replacement.

This SQLite database is prototype storage and is not encrypted. Voice
IDs and private sender aliases must not be committed or placed in public
documentation.

### Voice-Mapping Management API

The backend provides a prototype administrator API for managing voice
profiles and sender aliases:

```text
GET    /voice-profiles
POST   /voice-profiles
GET    /voice-profiles/{profile_id}
PATCH  /voice-profiles/{profile_id}
DELETE /voice-profiles/{profile_id}
POST   /voice-profiles/{profile_id}/aliases
PATCH  /sender-aliases/{alias_id}
DELETE /sender-aliases/{alias_id}
```

These routes use a separate `VOICE_MAPPINGS_ADMIN_KEY`, sent in the
`X-Voice-Mappings-Admin-Key` header. When the server key is not configured,
management routes are disabled and return `503`. Missing or incorrect
credentials return `401`.

Voice IDs are write-only: create and update requests can supply them, but
management responses return only whether a voice ID is configured. This
is prototype administrator authentication, not final user authentication.
The management admin key must never be embedded in the Android app or
placed in Android configuration.

Install backend dependencies:

```powershell
py -3.12 -m pip install -r requirements.txt
```

Run locally:

```powershell
py -3.12 -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Useful backend routes:

```text
GET  /          public status page
GET  /health    lightweight health check
POST /speak     protected TTS test endpoint when VOICE_GLASSES_API_KEY is set
POST /notification protected notification-to-speech endpoint when VOICE_GLASSES_API_KEY is set
GET/POST/PATCH/DELETE voice-mapping management routes protected by VOICE_MAPPINGS_ADMIN_KEY
```

---

## Android Configuration

The Android project is located in:

```text
android/
```

The application requires Android notification access.

Android-specific private values are read from:

```text
android/local.properties
```

This file is ignored by Git and should not be committed.

Use [`android/local.properties.example`](android/local.properties.example) as a template.

Required values for the Android prototype:

```text
VOICE_GLASSES_SERVER_URL=https://your-backend-host/notification
VOICE_GLASSES_API_KEY=your_private_shared_app_key
```

`VOICE_GLASSES_API_KEY` should match the backend's `VOICE_GLASSES_API_KEY` value when backend auth is enabled.

---

## Android Notification Flow

```text
Notification posted
        ↓
Is FamiliarVoice Notifications enabled?
        │
        ├── No → stop
        │
        └── Yes
               ↓
Is the app allowed?
        │
        ├── No → stop
        │
        └── Yes
               ↓
Extract sender and message
               ↓
Is sender blank?
        │
        ├── Yes → stop
        │
        └── No
               ↓
Is message blank?
        │
        ├── Yes → stop
        │
        └── No
               ↓
Send message to backend
```

The current MVP supports Google Messages:

```text
com.google.android.apps.messaging
```

Additional applications can be supported in later milestones.

---

## Privacy and Consent Notes

FamiliarVoice Notifications processes message text by sending it from the Android phone to a backend service and then to ElevenLabs for speech generation.

That means message content can leave the device during the current prototype flow.

The current public-readiness cleanup adds a private app-to-backend key for the hosted TTS endpoints, but this is still a prototype-level security control, not a full production authentication system.

Voice cloning and familiar-voice features should be used only with appropriate consent from the person whose voice is being represented.

---

## Important Testing Note

Ray-Ban Meta glasses include their own message announcement and automatic message readout features.

During clean FamiliarVoice Notifications testing, those built-in features are disabled so that the Meta reader and FamiliarVoice Notifications do not both announce the same message.

FamiliarVoice Notifications and Meta's built-in message reader are separate systems.

FamiliarVoice Notifications does not use a private or custom Ray-Ban Meta API. The prototype uses standard Android media playback through the active media route.

---

## Physical MVP Tests Completed

The prototype has successfully demonstrated:

- FastAPI server startup,
- hosted FastAPI deployment,
- ElevenLabs speech generation,
- MP3 streaming response,
- Android notification-listener connection,
- notification sender extraction,
- notification message extraction,
- Android-to-FastAPI communication,
- real SMS notification detection,
- sender-specific voice selection,
- cloned voice playback,
- Ray-Ban Meta audio playback,
- master switch enable/disable behavior,
- saved switch-state persistence,
- real-message pause behavior,
- application-package filtering,
- blank-sender background-notification filtering,
- basic rapid-message testing,
- and a recorded, captioned MVP demo.

---

## Current Limitations

FamiliarVoice Notifications is a working technical prototype, not a production application.

Current limitations include:

- only Google Messages is supported,
- SQLite voice-mapping storage has no user-facing management workflow,
- the prototype SQLite database is not encrypted,
- there is no full production authentication system,
- there is no contact-management interface,
- there is no voice-assignment interface,
- there is no explicit guaranteed audio queue,
- network retry behavior is limited,
- offline behavior is not yet implemented,
- automated coverage is currently focused on the storage foundation,
- hosted free-tier services may have cold starts,
- and testing has been performed on a limited number of devices.

These limitations define the next engineering milestones.

---

## Roadmap

### Completed

- Core FastAPI foundation
- Notification endpoint
- Sender-to-voice mapping
- Android notification listener
- Android-to-backend connection
- Ray-Ban Meta audio playback
- voice enrollment testing
- master speech control
- real-world MVP testing
- hosted backend deployment
- HTTPS backend communication
- project-state documentation
- development workflow documentation
- architecture documentation
- roadmap documentation
- professional README
- demo package

### Current Portfolio Phase

- public-readiness audit
- privacy and configuration cleanup
- recruiter-facing project presentation

### Next Major Technical Phase

- persistent contact-to-voice mappings
- contact voice-assignment UI
- unknown-sender controls
- voice enrollment workflow
- improved retry behavior
- explicit ordered audio queue

### Later Product Work

- accessibility-focused UI review
- testing with target users
- broader audio-device testing
- reliability improvements
- network failure handling
- stronger privacy and consent controls
- production authentication and authorization

---

## Project Goal

The goal of this project is to explore whether familiar, sender-specific voices can make notification readouts feel more personal and useful for blind and low-vision users.

The current repository documents the path from a basic FastAPI experiment to a physically tested Android and smart-glasses MVP.

---

## Author

Built by Zachary Maness as a portfolio project focused on accessibility, Android development, backend development, AI voice integration, and practical product prototyping.
