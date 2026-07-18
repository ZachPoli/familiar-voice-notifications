# Voice Glasses — Project State

## Project Purpose

Voice Glasses is an accessibility-focused Android prototype that reads incoming messages aloud using sender-specific familiar voices.

The project was inspired by Zach's father and grandmother, who are blind. The goal is to make digital messaging feel more personal by allowing messages from family and friends to be heard in familiar voices instead of only a generic synthetic text-to-speech voice.

---

## Current Status

The first complete end-to-end MVP prototype is working, and the Milestone
15A SQLite voice-mapping storage foundation is complete.

The project has now demonstrated:

- real SMS notification detection,
- Android notification filtering,
- sender and message extraction,
- Android-to-FastAPI communication,
- hosted backend deployment,
- ElevenLabs text-to-speech generation,
- sender-specific voice routing,
- persistent SQLite voice-mapping storage,
- MP3 return to Android,
- Android MediaPlayer playback,
- and audio output through Ray-Ban Meta glasses.

The public-readiness security pass is complete. A clean public
recruiter-facing repository was created and audited. Product development
has resumed with persistent voice mappings, and Milestone 15B is the next
target.

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

---

## Current Limitations

Voice Glasses is still a prototype, not a production app.

Known limitations:

- only Google Messages is currently supported,
- there is not yet a voice-mapping management API,
- there is not yet a contact-assignment UI,
- the SQLite database is not encrypted,
- hosted persistence requires durable mounted storage,
- there is no explicit message queue,
- retry/offline behavior is limited,
- automated coverage is currently focused on the SQLite storage foundation,
- free-tier hosted backend cold starts can affect latency,
- and the current app-key protection is a prototype security measure, not a full production auth system.

---

## Immediate Priority

Milestone 15B — Voice Mapping Management API:

```text
define safe mapping operations
        ↓
add backend create/read/update/delete behavior
        ↓
test validation and persistent changes
        ↓
prepare Milestone 15C end-to-end verification
```
