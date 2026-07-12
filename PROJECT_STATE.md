# Voice Glasses — Project State

## Project Purpose

Voice Glasses is an accessibility-focused Android prototype that reads incoming messages aloud using sender-specific familiar voices.

The project was inspired by Zach's father and grandmother, who are blind. The goal is to make digital messaging feel more personal by allowing messages from family and friends to be heard in familiar voices instead of only a generic synthetic text-to-speech voice.

---

## Current Status

The first complete end-to-end MVP prototype is working.

The project has now demonstrated:

- real SMS notification detection,
- Android notification filtering,
- sender and message extraction,
- Android-to-FastAPI communication,
- hosted backend deployment,
- ElevenLabs text-to-speech generation,
- sender-specific voice routing,
- MP3 return to Android,
- Android MediaPlayer playback,
- and audio output through Ray-Ban Meta glasses.

The current portfolio phase is public-readiness cleanup: security, privacy, configuration, and documentation review before making the repository public.

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
- sender-to-voice mappings are hard-coded,
- there is no database,
- there is no contact-management UI,
- there is no voice-assignment UI,
- there is no explicit message queue,
- retry/offline behavior is limited,
- automated tests are not yet added,
- free-tier hosted backend cold starts can affect latency,
- and the current app-key protection is a prototype security measure, not a full production auth system.

---

## Immediate Priority

Before public release:

```text
finish security/config cleanup
        ↓
set hosted VOICE_GLASSES_API_KEY
        ↓
pull and configure Android local.properties
        ↓
rebuild and retest real SMS
        ↓
review historical custom voice ID issue
        ↓
final public-readiness decision
```
