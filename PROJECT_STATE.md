# Voice Glasses — Project State

## Project Purpose

Voice Glasses is an accessibility-focused Android prototype that reads incoming messages aloud using sender-specific familiar voices.

The project was inspired by Zach's father and grandmother, who are blind. The goal is to make digital messaging feel more personal by allowing messages from family and friends to be heard in familiar voices instead of only a generic synthetic text-to-speech voice.

---

## Current Status

The first complete end-to-end MVP prototype is working. Milestone 15A's
SQLite voice-mapping storage foundation, Milestone 15B's voice-mapping
management API, and Milestone 15C-1's local persistent-mapping verification
are complete.

The project has now demonstrated:

- real SMS notification detection,
- Android notification filtering,
- sender and message extraction,
- Android-to-FastAPI communication,
- hosted backend deployment,
- ElevenLabs text-to-speech generation,
- sender-specific voice routing,
- persistent SQLite voice-mapping storage,
- authenticated voice-profile and sender-alias management,
- MP3 return to Android,
- Android MediaPlayer playback,
- and audio output through Ray-Ban Meta glasses.

The public-readiness security pass is complete. A clean public
recruiter-facing repository was created and audited. Product development
has resumed with persistent voice mappings. The current automated suite
has 68 passing tests. Milestone 15C remains in progress, with hosted
persistence and Android verification as the next development target.

---

## Proven End-to-End Flow

The following workflow has been tested on physical hardware:

```text
Real SMS arrives on Pixel 10a
        ↓
Android NotificationListenerService detects notification
        ↓
Master Voice Glasses switch is checked
        ↓
Notification source is filtered
        ↓
Background notifications without senders are rejected
        ↓
Sender and message are extracted
        ↓
Android sends JSON to FastAPI /notification
        ↓
FastAPI maps sender to a voice ID
        ↓
ElevenLabs generates MP3 audio
        ↓
Android receives the audio response
        ↓
MediaPlayer plays the audio
        ↓
Android routes media audio to Ray-Ban Meta glasses
```

The backend has been tested both locally and through a hosted deployment.

---

## Current Runtime Components

### Android App

Primary files:

```text
android/app/src/main/java/com/zachpoli/voiceglasses/MainActivity.kt
android/app/src/main/java/com/zachpoli/voiceglasses/VoiceNotificationListener.kt
```

Responsibilities:

- display the master speech control,
- persist enabled/paused state with SharedPreferences,
- listen for Android notifications,
- allow only supported app packages,
- extract sender and message text,
- send notification data to the backend,
- receive MP3 audio,
- and play the result through Android's active media route.

### FastAPI Backend

Primary file:

```text
main.py
```

Responsibilities:

- expose a health/status route,
- receive notification data,
- optionally require a private app-to-backend key,
- validate message content,
- select a voice based on sender name,
- provide authenticated profile listing,
- create, read, update, and delete voice profiles,
- create, update, and delete sender aliases,
- accept voice IDs as write-only management values,
- return safe conflict and not-found responses,
- call ElevenLabs text-to-speech,
- and stream MP3 audio back to Android.

### SQLite Voice-Mapping Storage

Primary file:

```text
voice_mapping_store.py
```

Responsibilities:

- initialize the SQLite schema during FastAPI startup,
- store voice profiles with multiple normalized sender aliases,
- resolve incoming senders to stored voice mappings,
- preserve the default voice fallback for unknown senders,
- and enforce transactional bootstrap and mapping writes.

On the first startup of a new, empty database, explicitly configured
environment mappings can seed initial profiles. Each seed requires both a
voice ID and at least one sender alias. Bootstrap runs only once; SQLite is
the source of truth afterward, so later environment changes do not
overwrite or recreate stored mappings. A populated database is treated as
user-owned and is not overwritten.

### Local Persistence Verification

Milestone 15C-1 verified synthetic bootstrap, persistent CRUD operations,
notification lookup, normalization, fallback behavior, and authentication
separation using temporary SQLite databases. Mappings survived repeated
FastAPI lifespan startups and separate Uvicorn process restarts; updates and
deletions also remained persistent.

The real local configuration successfully bootstrapped into an isolated
disposable database through a count-and-boolean-only verification report.
The normal local database was not modified. No production or Android changes
were required, and all 68 automated tests pass.

### ElevenLabs

Used for sender-specific speech generation.

Private values are configured through environment variables, not committed source code.

---

## Configuration Model

Backend private values:

```text
ELEVENLABS_API_KEY
ZACH_VOICE_ID
EMILY_VOICE_ID
VOICE_GLASSES_API_KEY
VOICE_MAPPINGS_ADMIN_KEY
```

Android private/local values:

```text
VOICE_GLASSES_SERVER_URL
VOICE_GLASSES_API_KEY
```

Android reads local values from:

```text
android/local.properties
```

That file is ignored by Git.

### Authentication Boundaries

The existing Android and TTS request flow is protected by
`VOICE_GLASSES_API_KEY`. Administrator voice-mapping operations use the
separate `VOICE_MAPPINGS_ADMIN_KEY`. The administrator key must never be
embedded in Android or placed in Android configuration.

This is prototype administrator authentication, not a final end-user
authentication and authorization system. Management currently requires
direct developer or administrator API access.

---

## Current Limitations

Voice Glasses is still a prototype, not a production app.

Known limitations:

- only Google Messages is currently supported,
- there is no Android contact or voice-assignment UI yet,
- there is no end-user authentication system yet,
- management currently requires developer or administrator API access,
- the SQLite database is not encrypted,
- hosted persistence requires durable mounted storage,
- there is no explicit message queue,
- retry/offline behavior is limited,
- TalkBack coexistence has not yet been tested,
- current automatic playback may duplicate or overlap TalkBack speech,
- accessible on-demand playback is planned,
- the product must remain usable with TalkBack enabled,
- automated coverage includes 68 storage, management API, authentication,
  validation, privacy, persistence, and compatibility tests,
- free-tier hosted backend cold starts can affect latency,
- and the current app-key protection is a prototype security measure, not a full production auth system.

---

## Future Accessibility and Release Work

TalkBack coexistence and accessible playback require dedicated design and
physical testing. Future work will preserve original notifications,
provide an accessible on-demand playback option, test audio focus and
screen-reader navigation, and validate the experience with blind users.

Google Play internal testing, closed beta, and production release are
planned but have not started. Release readiness requires privacy and
consent work, Play Console declarations, a signed Android App Bundle,
compliance with the target-SDK requirement current at release time,
accessibility testing, and meaningful beta feedback.

The current build is a working prototype and is not yet ready for a Google
Play production release.

---

## Immediate Priority

Milestone 15C-2 — Hosted Persistence and Android Verification:

```text
identify the Render source repository and deployed commit
        ↓
determine and configure a durable hosted-storage approach
        ↓
prove a synthetic hosted mapping survives restart or redeployment
        ↓
run a controlled real SMS test through the Android app
```

Hosted persistence and the real Android SMS test remain incomplete. This
work will preserve the working Android notification flow while verifying
known-sender routing and unknown-sender fallback on physical hardware.
