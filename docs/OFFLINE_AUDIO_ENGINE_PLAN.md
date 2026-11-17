# Offline audio engine: implementation plan

## User-facing promise

FB2AudioPrep will support two playback modes:

1. **Characters** — dialogue is split into speaker turns; each known character uses the selected voice. Uncertain turns use the configured fallback voice and remain editable.
2. **One voice** — the complete book is read by one selected voice, regardless of dialogue attribution.

The app must not show an active play button until a compatible voice pack is installed and the playback service can synthesize and play a test phrase.

## Runtime architecture

Keep the playback pipeline independent from the reader UI:

- `BookRepository`: normalized chapter/paragraph stream from FB2 or TXT.
- `SpeechPreparation`: text cleanup, abbreviation/number expansion, preservation of explicit stress marks, and chunking at sentence/paragraph boundaries.
- `SpeakerResolver`: maps a paragraph to a character only when dialogue evidence is strong; narration and uncertain dialogue use a fallback. A vocative (for example, “Нико!”) is not by itself evidence that Nico is speaking.
- `VoiceProfileStore`: local character-to-voice assignments, one-voice preference, speed and fallback settings.
- `TtsEngine`: small interface for installed engines; model-specific code stays behind this boundary.
- `AudioPlaybackService`: Android foreground media playback, queue, pause/resume, seek, audio focus, headset controls and notification.
- `ModelPackManager`: one-time download, checksum verification, storage check, atomic install and offline readiness.
- `PlaybackStateStore`: chapter, paragraph, queue position and playback preferences persisted locally.

## Model integration requirements

Evaluate TeraTTSv2 as the primary neural candidate because it has Russian voices and explicit stress support. Before shipping, pin an upstream revision, record file hashes and license notices, and download only runtime-required assets. Keep model weights outside the APK; the app installer must remain small.

The model adapter must prove all of the following on a physical Android device before release:

- Load the verified model pack without network access.
- Synthesize Russian text with all supported voice profiles.
- Preserve manually supplied stress marks and handle ё/е consistently.
- Stream or chunk long books without exhausting memory.
- Recover cleanly from pause, interruption, low storage and process recreation.
- Report model incompatibility and download errors in plain Russian.

Do not claim that a model is integrated based only on a successful Gradle build.

## Dialogue attribution rules

- Prefer explicit speech tags (“сказал Нико”, “ответила она”, “женским голосом”) and previously confirmed character mappings.
- Use nearby context only as supporting evidence, not as an unconditional override.
- Do not infer the speaker from a name used as an address/vocative.
- Keep confidence with each assignment; low-confidence turns are editable and use fallback voice.
- Store corrections per book and offer an exportable correction set.
- Include regression tests for the user's known “Нико” and “ИсКин” examples before changing the resolver.

## Playback UX

- Mini-player appears only while audio is active or paused.
- Full player: play/pause, previous/next paragraph, seek, speed, sleep timer and chapter title.
- Mode switch: “Персонажи” / “Один голос”.
- Character assignments are edited in a separate compact cast screen, not in the middle of playback.
- Model setup has explicit states: not installed, downloading, verifying, ready offline, insufficient storage and failed.
- Remember the last position independently for each book and mode.

## Delivery sequence

1. Keep the reader UX build green.
2. Add repository and playback state interfaces with unit tests; no fake audio controls.
3. Add model pack manager and checksum/license manifest.
4. Integrate the selected Android inference runtime and verify a short offline sample.
5. Add foreground playback service and media controls.
6. Add character/single-voice player UI.
7. Run long-book, interruption, offline-restart and regression tests on a physical device.

## Release gate

A release may be called “audio-enabled” only after a physical-device test demonstrates actual Russian speech synthesis and playback with Wi-Fi/mobile data disabled. A successful APK compilation alone is not sufficient.
