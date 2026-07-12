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

Status: In Progress 🟡

Goal:

Prepare the repository to become public and recruiter-ready.

Current work includes:

- removing hard-coded environment-specific Android backend configuration,
- documenting local Android configuration through `android/local.properties.example`,
- adding optional app-key protection for hosted TTS endpoints,
- updating README and demo documentation,
- reviewing current source for secrets and privacy issues,
- and deciding how to handle historical custom voice IDs before publication.

---

## Phase 4 — Contact and Voice Management

### Milestone 15 — Persistent Voice Mappings

Status: Not Started ⬜

Replace hard-coded sender mappings with persistent storage.

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

---

## Current Priority

The immediate priority is public-readiness:

```text
security/config cleanup
    ↓
secret and privacy audit
    ↓
documentation consistency check
    ↓
public/recruiter-ready decision
```

After the repository is safe to make public, development can return to product features such as contact-to-voice management and reliability improvements.
