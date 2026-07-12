# Voice Glasses — AI Development Workflow

## Purpose

This document defines the development workflow used for Voice Glasses when working with an AI coding assistant.

The goal is to keep changes grounded in the actual repository, preserve working behavior, and make each milestone easy to test and continue across development sessions.

The repository, running application, physical tests, and Git history are the sources of truth. Conversation history is supporting context only.

---

## Project Owner

Zach Maness

---

## Project Purpose

Voice Glasses is an accessibility-focused Android prototype that reads incoming messages aloud using sender-specific familiar voices.

The project was inspired by Zach's father and grandmother, who are blind.

The current MVP combines:

- Android and Kotlin,
- NotificationListenerService,
- Jetpack Compose,
- Python 3.12,
- FastAPI,
- ElevenLabs text-to-speech,
- sender-specific voice routing,
- and Android media playback through connected audio devices.

---

## Sources of Truth

Use the following order when determining the current project state.

### 1. Working code

The checked-out source code is the primary implementation reference.

Do not assume an older conversation or plan still matches the current code.

### 2. Physical test results

Behavior that has been tested on real devices takes priority over untested assumptions.

Document which device, message source, backend state, and audio route were used.

### 3. Git status and Git history

Before changing files, check:

```powershell
git status
```

Review recent work when context is unclear:

```powershell
git log --oneline -10
```

A clean working tree should be preserved between completed milestones whenever practical.

### 4. Project documentation

Use these files for project context:

- `README.md` — public project overview and demo entry point
- `DEMO.md` — demo behavior and testing notes
- `PROJECT_STATE.md` — current proven working state
- `ARCHITECTURE.md` — technical architecture and boundaries
- `ROADMAP.md` — completed and planned milestones

---

## Coding Rules

### Full-file replacements

When a source file needs meaningful editing, provide or apply the complete replacement file rather than a disconnected patch fragment.

This reduces copy-and-paste errors and makes the resulting project state easier to review.

### Protect secrets

Never place API keys or private voice IDs directly in committed source code.

Current private configuration belongs in a local `.env` file:

```text
ELEVENLABS_API_KEY
ZACH_VOICE_ID
EMILY_VOICE_ID
```

The committed `.env.example` file contains placeholders only.

### Prefer simple working code

For the MVP, prefer direct implementations that are easy to understand and test.

Avoid adding frameworks, abstractions, or infrastructure unless they solve a demonstrated problem.

### Preserve working behavior

Before changing code, identify what already works and avoid unrelated rewrites.

After a change, retest the specific behavior affected by that change.

---

## Milestone Workflow

Each technical milestone should follow this sequence:

```text
Check repository state
        ↓
Read the current implementation
        ↓
Define one small behavior change
        ↓
Make the change
        ↓
Run focused tests
        ↓
Run a real-device test when hardware behavior is involved
        ↓
Update documentation when project state changed
        ↓
Review git diff and status
        ↓
Commit with a descriptive milestone message
        ↓
Push to GitHub
```

Milestones should be small enough that a failure can be isolated quickly.

---

## Testing Rules

Use the smallest test that proves the current change.

Examples:

- backend route change → test the FastAPI endpoint,
- voice-routing change → test mapped and unmapped senders,
- Android listener change → test a real notification,
- speech-control change → test enabled, paused, and restart persistence,
- audio-routing change → verify Android playback and the selected connected media output,
- filtering change → test both accepted and rejected notifications.

Do not mark behavior as working only because the code looks correct.

---

## Current MVP Boundary

The current project is a working local prototype, not a production application.

Important current boundaries include:

- local FastAPI backend,
- hard-coded development server address in Android,
- cleartext HTTP for local testing,
- Google Messages-only notification support,
- hard-coded sender matching logic,
- no persistent contact database,
- no production authentication layer,
- limited network retry handling,
- no guaranteed ordered audio queue,
- and limited device testing.

These are documented limitations rather than hidden behavior.

---

## AI Collaboration Standard

An AI coding assistant should:

1. inspect current repository state before proposing code changes,
2. distinguish proven behavior from assumptions,
3. avoid inventing test results,
4. preserve environment-variable secret handling,
5. provide complete files for meaningful source changes,
6. explain commands and code in a way that supports learning,
7. keep changes scoped to the active milestone,
8. use Git history and documentation to maintain continuity,
9. be explicit when a limitation remains unresolved,
10. treat successful physical testing as evidence that must not be casually broken by unrelated refactoring.

---

## Current Development Direction

The working MVP and demo package are complete.

The next major technical direction is moving from a local development prototype toward a hosted and configurable system, including:

- hosted backend deployment,
- HTTPS communication,
- configurable backend addresses,
- persistent contact-to-voice mappings,
- contact and voice-assignment controls,
- stronger reliability behavior,
- privacy and consent controls,
- and automated testing.

The project should continue to advance through small, testable milestones rather than large unverified rewrites.
