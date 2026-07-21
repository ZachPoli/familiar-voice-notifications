# Milestone 16 Plan — Contact Voice Assignment UI

## Goal

Give users an accessible Android interface for managing which familiar voice
is assigned to a contact. Build it in small, testable slices so the working
notification flow stays unchanged.

## First Vertical Slice — Open an Empty Voice Assignments Screen

This first slice is navigation and layout only:

1. Add a clearly labeled **Voice assignments** button to the existing home
   screen.
2. Selecting the button opens a basic **Voice Assignments** screen.
3. The new screen shows an empty-state message explaining that no assignments
   are displayed yet, plus a clearly labeled **Back** button.
4. The Back button returns to the existing home screen without changing the
   notification-speech switch.
5. Give headings and controls useful text labels, sensible focus order, and
   touch targets suitable for TalkBack and double-tap activation.

This slice will not request contact permission, read contacts, call the
backend, store assignments, expose administrator credentials, or add voice
selection logic.

## Files for the First Slice

- `android/app/src/main/java/com/zachpoli/voiceglasses/MainActivity.kt` — add
  the home-screen button and simple screen-selection state.
- `android/app/src/main/java/com/zachpoli/voiceglasses/VoiceAssignmentsScreen.kt`
  — keep the new screen's Compose UI separate and easy to understand.
- Android UI test files, if added — verify navigation, visible labels, and
  Back behavior without contacts or network access.

No Gradle dependency should be needed for this small slice because the app
already uses Jetpack Compose and Material 3. A later review can introduce a
navigation library only if the growing screen flow justifies it.

## First-Slice Acceptance Criteria

- The existing home screen still shows and controls notification speech.
- An accessible **Voice assignments** button is visible on the home screen.
- Activating it opens a screen titled **Voice Assignments**.
- The screen displays a clear empty-state message and a **Back** button.
- Back returns to the home screen and preserves the switch state.
- TalkBack can focus, announce, and activate every new control in a logical
  order.
- No contact permission is requested and no contacts are accessed.
- No backend or ElevenLabs request is made.
- No voice-selection or assignment persistence logic is added.
- The Android project builds and relevant UI tests pass.

## Later Follow-Up Slices

1. **Read-only mapping list:** retrieve safe mapping summaries through an
   appropriate mobile-safe backend boundary and show loading, empty, success,
   and error states.
2. **Contact permission education:** explain why contact access is useful,
   request it only after user action, and handle denial accessibly.
3. **Contact selection:** show a searchable, accessible contact list while
   minimizing collected contact data.
4. **Assignment flow:** choose an existing voice profile and create or update
   a sender alias through a mobile-safe API.
5. **Edit and remove:** review, change, and delete assignments with clear
   confirmation and recovery-friendly behavior.
6. **Accessibility and reliability:** test TalkBack navigation, large text,
   rotation, process recreation, offline behavior, and backend errors.

Before any network-enabled slice, design a safe authorization approach. The
administrator management key must never be embedded in the Android app.
