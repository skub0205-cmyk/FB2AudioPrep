# Offline TTS playback integration plan

## Product behavior

FB2AudioPrep will expose two playback modes over the same locally stored book text:

1. **Character audiobook** — dialogue segments carry a resolved speaker ID. Each character profile maps to a voice style. Explicit narration cues and user corrections take priority over automatic attribution. A vocative (for example, “Нико!”) is never evidence that Нико is speaking.
2. **Single voice** — every segment uses one selected Russian voice, regardless of speaker metadata.

Both modes must work after the model pack has been downloaded once. No text, audio, or book metadata is sent to a server.

## Primary model candidate

TeraTTSv2 ONNX, pinned to a reviewed Hugging Face commit rather than the moving `main` branch. Initial Russian styles: `ru_f1` and `ru_m5`; additional styles can be exposed after device testing.

The upstream release provides an eight-step distilled sampler, shared ONNX graphs, Russian stress processing, and 44.1 kHz mono float audio. The full repository is about 1.17 GB; the app must not bundle it in the APK. The pack installer should fetch only the distilled sampler and required shared/style/stress assets. Teacher sampler and unused voices are optional downloads.

License handling is mandatory: preserve the TeraTTSv2 model license, Open RAIL-M license, RUAccent notice and any component notices in the downloaded pack. If the model is ever used in a commercial product, the public product description must include the upstream attribution and model link.

## Android implementation sequence

### A. Model pack manager
- Store files in app-private storage; do not place partial downloads in the active model directory.
- Download a pinned manifest and verify every file's SHA-256 before activation.
- Support resumable downloads, progress, pause/cancel, low-storage checks, and retry.
- Activate atomically only after every required file passes verification.
- Show model version, installed size, free-space requirement, and license notices.
- After activation, synthesis must not require network permission or a network connection.

### B. ONNX inference port
- Add ONNX Runtime Android for the supported ABI(s).
- Port the upstream preprocessing and inference pipeline to Kotlin/JVM: language tags, number expansion, Unicode indexing, text encoder, distilled sampler, duration predictor, vocoder, and RUAccent-derived stress handling.
- Pin and review upstream source code before porting; do not execute unpinned remote Python code inside the app.
- Add golden tests comparing normalized text and waveform properties against upstream reference outputs. Do not mark the engine “ready” until those tests pass on a physical ARM64 device.

### C. Playback
- Generate bounded text chunks instead of synthesizing an entire book into memory.
- Queue audio chunks through Android audio output; keep a foreground media service for screen-off playback.
- Implement play/pause, previous/next paragraph, seek by paragraph, speed, voice selection, and resume position.
- Keep playback state and selected mode per book.

### D. Character routing
- Convert the dialogue analysis into stable paragraph/segment records.
- Apply priority: explicit author attribution → saved user correction → reliable propagated speaker anchor → unresolved/default voice.
- Preserve user-assigned character voices across reopening the same book.
- In character mode, unresolved dialogue uses the configured fallback voice; never infer a speaker from a name being addressed.
- In single-voice mode, bypass character voice routing but retain text normalization and stress processing.

## Release gates

- Offline cold-start after first successful model installation.
- SHA-256 verification and interrupted-download recovery.
- At least 30 minutes of continuous screen-off playback without audio gaps or service termination.
- Correct voice routing on regression cases for “Нико”, “ИсКин”, explicit “женский голос” / “мужской голос”, and adjacent dialogue turns.
- Test on the user's target Android device before claiming performance or battery results.

## Current status

This document is an implementation specification, not a claim that TeraTTSv2 inference or playback is already integrated. The current APK still contains the reader and text-preparation functionality; the neural model runtime and playback service remain to be implemented and tested.
