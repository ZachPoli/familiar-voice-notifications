# Voice Glasses — Roadmap

## Purpose

This document tracks the development roadmap for Voice Glasses.

The roadmap is organized around small milestones that can be completed, tested, committed, and pushed cleanly.

---

## Project Vision

Voice Glasses is an accessibility-focused Android prototype that reads incoming messages aloud using sender-specific familiar voices.

The project was inspired by Zach's father and grandmother, who are blind.

The core idea is:

> Messages from family and friends should be able to sound like the people who sent them instead of always being read by a generic synthetic voice.

The current prototype has proven that a real Android message can be:

```text
detected
    ↓
filtered
    ↓
associated with a sender
    ↓
mapped to a voice
    ↓
converted to speech
    ↓
played through Ray-Ban Meta glasses
```

---

## Phase 1 — Core MVP

### Milestone 0 — Foundation

Status: Complete ✅

Created the initial Python 3.12 FastAPI project, repository, and local development environment.

### Milestone 1 — Notification Endpoint

Status: Complete ✅

Created a backend endpoint capable of receiving Android-style notification data.

### Milestone 2 — Sender-to-Voice Mapping

Status: Complete ✅

Added prototype sender-to-voice routing for known senders and a default voice for unknown senders.

### Milestone 3 — Android Notification Listener

Status: Complete ✅

Created an Android `NotificationListenerService` capable of detecting notifications and extracting sender/message text.

### Milestone 4 — Phone-to-Server Connection

Status: Complete ✅

Connected the Android listener to the FastAPI backend and returned MP3 audio for playback.

### Milestone 5 — Ray-Ban Meta Audio Playback

Status: Complete ✅

Proved that Voice Glasses-generated speech can play through Ray-Ban Meta glasses using Android's active media route.

### Milestone 6 — Voice Enrollment Testing

Status: Complete ✅

Tested sender-specific familiar voice playback using custom and cloned ElevenLabs voices.

### Milestone 7 — User Controls

Status: Complete ✅

Added a master Voice Glasses enable/pause switch and SharedPreferences persistence.

### Milestone 8 — MVP Testing

Status: Complete ✅

Validated real SMS detection, sender-specific routing, cloned voice playback, Ray-Ban Meta playback, package filtering, blank-sender filtering, pause behavior, and rapid-message behavior.

---

## Phase 2 — Workflow and Portfolio Presentation

### Milestone 9 — Project State Document

Status: Complete ✅

Created project-state documentation to describe what works, current limitations, test results, and next priorities.

### Milestone 10 — Development Workflow System

Status: Complete ✅

Added workflow documentation so future development sessions can understand the repository without relying only on long conversation history.

### Milestone 11 — Architecture Documentation

Status: Complete ✅

Added architecture documentation explaining the Android app, FastAPI backend, ElevenLabs integration, media playback path, and prototype boundaries.

### Milestone 12 — Demo Package

Status: Complete ✅

Recorded, captioned, reviewed, and committed the MVP demo video with supporting demo documentation.

---

## Phase 3 — Hosted Backend and Configuration Cleanup

### Milestone 13 — Hosted Backend Deployment

Status: Complete ✅

Deployed the FastAPI backend to a hosted environment and tested the full flow with a real SMS message.

Current hosted architecture:

```text
Pixel 10a
    ↓
Internet
    ↓
Hosted FastAPI backend
    ↓
ElevenLabs
    ↓
Hosted FastAPI backend
    ↓
Pixel 10a
    ↓
Ray-Ban Meta glasses
```

### Milestone 14 — Public-Readiness Security Pass

Status: Complete ✅

Completed the security, privacy, configuration, and documentation review
needed for public release. A clean public recruiter-facing repository was
created and audited.

The completed work includes environment-based private configuration,
optional protection for hosted TTS endpoints, public documentation, and
repository secret/privacy review.

---

## Phase 4 — Contact and Voice Management

### Milestone 15 — Persistent Voice Mappings

Status: In Progress 🟡

Replace hard-coded sender mappings with persistent storage.

### Milestone 15A — SQLite Storage Foundation

Status: Complete ✅

Added persistent voice-mapping storage with Python's built-in `sqlite3`.
Voice profiles can own multiple normalized sender aliases. Environment
mappings seed an empty database only once, after which SQLite becomes the
source of truth. Automated tests verify initialization, normalization,
transactions, bootstrap protection, and unknown-sender fallback behavior.

### Milestone 15B — Voice Mapping Management API

Status: Complete ✅

Added eight authenticated CRUD endpoints. Voice profiles can be listed,
created, read, updated, and deleted, while sender aliases can be added,
updated, and deleted. Management uses the separate
`VOICE_MAPPINGS_ADMIN_KEY`. Voice IDs are write-only and are never returned
through management responses. Automated tests cover validation,
authentication separation, transaction safety, privacy-safe errors, and
CRUD behavior.

### Milestone 15C — End-to-End Persistent Mapping Verification

Status: In Progress 🟡

Verify persistent mappings with the existing Android notification workflow
and with hosted and local deployment behavior.

### Milestone 15C-1 — Local Persistent Mapping Verification

Status: Complete ✅

Verified synthetic bootstrap behavior and persistence across repeated
FastAPI lifespans and separate Uvicorn process restarts. CRUD updates and
deletions remained persistent, notification lookup used stored SQLite
mappings, case and whitespace normalization worked, and unknown senders
retained the default-voice fallback. Management and notification
authentication remained separate.

The real local configuration also bootstrapped successfully into an isolated
disposable database, with reporting limited to counts and booleans. All 68
automated tests pass. The verification scripts refuse unsafe or pre-existing
database files and clean up only files they create.

### Milestone 15C-2 — Hosted Persistence and Android Verification

Status: Not Started ⬜

This milestone will identify the current Render source repository and
deployed commit, determine whether durable persistent storage is available,
and configure a durable SQLite path or choose another safe hosted-storage
approach. It will then deploy the reviewed public repository, prove that a
synthetic hosted mapping survives restart or redeployment, and perform a
controlled real SMS test through the Android app. Physical-hardware testing
will verify known-sender routing and unknown-sender fallback.

### Milestone 16 — Contact Voice Assignment UI

Status: Not Started ⬜

Allow the user to view contacts and assign voices through an Android UI.

### Milestone 17 — Unknown Sender Controls

Status: Not Started ⬜

Define user-controlled behavior for messages from people without a custom voice mapping.

Possible behaviors:

- use default voice,
- use system voice,
- do not read,
- ask user to assign a voice later.

### Milestone 18 — Voice Enrollment Workflow

Status: Not Started ⬜

Design a consent-aware workflow for adding or assigning familiar voices.

---

## Phase 5 — Reliability and Product Hardening

### Milestone 19 — Message Queue

Status: Not Started ⬜

Add explicit ordering for rapid message playback.

### Milestone 20 — Retry and Offline Behavior

Status: Not Started ⬜

Handle network failures, backend cold starts, and offline behavior more gracefully.

### Milestone 21 — Production Authentication

Status: Not Started ⬜

Replace prototype app-key protection with a stronger production authentication and authorization strategy.

### Milestone 22 — Accessibility Testing

Status: Not Started ⬜

Review the app with accessibility-first UI expectations and eventually test with target users.

### Milestone 22A — TalkBack Coexistence and Accessible Playback

Status: Not Started ⬜

Goal:

Ensure FamiliarVoice Notifications works alongside Android TalkBack
without confusing duplicate or overlapping speech.

This milestone includes:

- testing how TalkBack announces original message notifications while
  FamiliarVoice is active,
- providing user-selectable automatic, accessible on-demand, and paused
  playback modes,
- adding a TalkBack-accessible notification action such as
  "Play in familiar voice",
- supporting double-tap activation and complete screen-reader navigation,
- testing Android audio-focus behavior,
- preserving the original notification without interfering with TalkBack,
- and completing physical testing with blind users.

This work is required before a public production release, but it is not
the current development priority.

---

## Phase 6 — Google Play Beta and Public Release

### Milestone 23 — Play Console and Publisher Setup

Status: Not Started ⬜

- create and verify the Google Play developer account,
- decide between a personal or organization publishing identity,
- finalize the public app name, publisher name, application ID, and support
  contact,
- and treat the application ID as permanent before the first public release.

### Milestone 24 — Privacy, Consent, and Store Policy Readiness

Status: Not Started ⬜

- publish a public privacy-policy webpage,
- provide the privacy policy in the app,
- add prominent disclosure and affirmative consent before notification
  message processing,
- complete an accurate Google Play Data safety declaration,
- define data retention and deletion policies,
- disclose backend and third-party speech processing,
- and prepare Play Store listing text, icon, screenshots, feature graphic,
  and reviewer instructions.

### Milestone 25 — Release Build and Play Signing

Status: Not Started ⬜

- upgrade compile and target SDKs to the Google Play requirement current at
  release time,
- currently plan for Android 16 / API 36,
- finalize release `versionCode` and `versionName`,
- configure release signing and Play App Signing,
- generate and validate an Android App Bundle,
- and run release-mode testing and pre-launch checks.

### Milestone 26 — Google Play Internal Testing

Status: Not Started ⬜

- upload the first release bundle to the internal-testing track,
- distribute it to trusted testers,
- verify installation, upgrading, onboarding, TalkBack use, notification
  access, voice mapping, and audio playback,
- and collect and triage feedback before wider testing.

### Milestone 27 — Closed Beta and Production Access

Status: Not Started ⬜

- recruit the tester count required by the developer-account type,
- for a qualifying new personal account, plan for at least 12 continuously
  opted-in testers for 14 days,
- gather meaningful accessibility, reliability, privacy, and usability
  feedback,
- fix beta findings,
- and complete the Google Play production-access application.

### Milestone 28 — Public Production Release

Status: Not Started ⬜

- complete all Play Console declarations,
- resolve policy and pre-launch findings,
- submit the production release,
- monitor crashes, reviews, backend reliability, privacy issues, and support
  requests,
- use a staged rollout if appropriate,
- and maintain update and incident-response procedures.

Google Play requirements must be rechecked against current official
documentation when each release milestone begins.

---

## Current Priority

The immediate priority is Milestone 15C-2 — Hosted Persistence and Android
Verification:

```text
identify the Render source repository and deployed commit
    ↓
confirm or configure durable hosted storage
    ↓
deploy and verify persistence across restart or redeployment
    ↓
run a controlled Android SMS test on physical hardware
```

Hosted persistence and the real Android SMS workflow remain unverified and
are the remaining work for Milestone 15C.
