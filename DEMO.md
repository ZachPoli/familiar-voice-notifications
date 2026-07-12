# Voice Glasses — MVP Demo

## Demo Overview

This demo shows the working Voice Glasses MVP processing a real incoming SMS message and converting it into sender-specific generated speech.

The recorded demo shows the real user-facing flow:

```text
Voice Glasses enabled
        ↓
Real SMS arrives
        ↓
Android notification listener detects the message
        ↓
Sender and message text are extracted
        ↓
FastAPI receives the notification data
        ↓
Backend maps the sender to an assigned voice
        ↓
ElevenLabs generates the speech
        ↓
MP3 audio is returned to Android
        ↓
Android plays the audio through the active media route
```

The prototype has been physically tested with Ray-Ban Meta glasses as the active Android media output.

---

## Demo Video

The repository includes the finished MVP demo at:

```text
demo/voice-glasses-mvp-demo.mp4
```

The approximately 31-second recording demonstrates:

- the Voice Glasses Android application,
- the master notification-speech control,
- speech being paused and re-enabled,
- the Ray-Ban Meta connection visible in Android,
- a real SMS notification arriving,
- generated speech being triggered,
- the backend and ElevenLabs processing path explained through captions,
- and the real Google Messages conversation being opened after the test.

The video is intentionally short and focused on proving the working end-to-end experience rather than providing a complete technical tutorial.

---

## What the Demo Proves

The demo represents this working implementation:

```text
Google Messages
        ↓
NotificationListenerService
        ↓
master switch check
        ↓
package filtering
        ↓
sender + message extraction
        ↓
POST /notification
        ↓
FastAPI
        ↓
sender-to-voice mapping
        ↓
ElevenLabs TTS
        ↓
MP3 response
        ↓
Android MediaPlayer
        ↓
active Android media output
```

This pipeline has been tested with:

- a Google Pixel 10a as the receiving device,
- a Google Pixel 7a as the SMS sender,
- real SMS messages through Google Messages,
- a locally hosted FastAPI backend during development,
- a hosted FastAPI backend during Milestone 13 testing,
- ElevenLabs text-to-speech,
- sender-specific custom and cloned voices,
- and Ray-Ban Meta glasses for audio playback.

---

## Ray-Ban Meta Audio Routing

Voice Glasses does not use a private or custom Ray-Ban Meta API.

The current prototype returns generated speech to the Android application, and Android plays that audio through the active media route.

Conceptually:

```text
ElevenLabs-generated MP3
        ↓
FastAPI response
        ↓
Android temporary audio file
        ↓
MediaPlayer
        ↓
Android active media output
        ↓
Ray-Ban Meta glasses
```

This distinction is important because the prototype uses standard Android media routing rather than claiming a direct software integration with the glasses.

---

## Demo Notes

Ray-Ban Meta glasses play audio close to the user's ears, so a phone screen recording cannot independently prove where the physical sound is heard.

For that reason, the demo combines:

1. visible application behavior,
2. visible real-message arrival,
3. generated speech playback,
4. visible connected-device state,
5. technical captions explaining the request path,
6. and documentation of the physically tested Ray-Ban Meta audio route.

The demo is intended to show the working MVP honestly without overstating the current implementation.

---

## Current Demo Status

```text
Demo planned                 ✅
Physical MVP tested          ✅
Demo video recorded          ✅
Demo video reviewed          ✅
Captions added               ✅
Demo video added to repo     ✅
README demo link             ✅
Hosted backend tested        ✅
```

The MVP demo package is complete.
