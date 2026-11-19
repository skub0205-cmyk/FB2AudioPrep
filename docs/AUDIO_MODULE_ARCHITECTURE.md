# Audio module architecture — FB2AudioPrep

**Status:** implementation branch, 2026-11-19  
**Reference:** TeraTTS Android 1.59; inspected the linked fork's current `teratts` branch (1.60-tera) to identify later engine and voice-import work.

## Product goals

- Offline Russian audiobook playback after a one-time model download.
- Two modes: one narrator for the whole book; character mode with per-character voice assignment.
- Natural Russian narration and dialogue take priority over smallest APK/model size.
- Custom voice profiles from a 10–30 second recording, with microphone, imported audio, and permitted Android playback capture.
- Model files and custom voice profiles survive APK updates. Re-download only when the model version actually changes or files fail integrity checks.

## Engine roles

### 1. Main Russian narrator: TeraTTSv2

Use the pinned TeraSpace/TeraTTSv2 ONNX release as the first preset-voice engine candidate. It has Russian-specific voice prompts, Russian automatic stress annotation for text wrapped in `<ru>…</ru>`, an eight-step distilled sampler, and streaming output at 44.1 kHz mono.

The upstream card identifies four Russian prompts: `ru_f1`, `ru_m5`, `ru_f2`, `ru_m1`. The other six styles are English and must not be presented as Russian voices. Audition and validate all Russian prompts on the target phone.

### 2. Custom Russian voices: Shtorm-PocketTTS-RU v2

Use ArtShtorm/Shtorm-PocketTTS-RU v2 as the dedicated reference-audio cloning candidate. This is a Russian fine-tune of Pocket TTS, specifically described for audiobook narration and short-reference voice cloning. The model offers fast and slow configurations and is published under CC-BY-4.0.

Important constraints:
- The official Kyutai Pocket TTS release itself lists English, French, German, Portuguese, Italian, Spanish and Dutch, not Russian. Do not use the generic Kyutai model for Russian; use the Russian Shtorm fine-tune.
- Shtorm's published example recommends about five seconds of clean speech, chunks around 120–180 characters, explicit acute-accent stress marks, and normalization of Latin words/numbers. The UI may accept 10–30 seconds, then select the cleanest 5–10 second section for the voice reference.
- Shtorm weights are about 1.31 GB for the repository containing fast/slow variants. This is a separate one-time model pack.
- The model card documents a Python/Pocket-TTS inference API, not a ready-made Android ONNX runtime. Android inference is a technical gate: investigate an efficient native/ONNX/ExecuTorch port and prove it on ARM64 before exposing the feature as available. Do not claim Android/offline support merely because the model can run on desktop CPU.

### 3. Optional extra preset voices: Supertonic 3

The linked TeraTTS fork (current branch version 1.60-tera) uses TeraTTSv2 and also exposes Supertonic 3 voice styles. Treat these as optional additional preset voices, not as voice cloning. Verify Russian pronunciation, accent, prosody, and licensing on-device before listing them as Russian choices.

## Voice capture and profile creation

1. Offer **Record with microphone**, **Import audio file**, and **Capture app audio**.
2. Accept common Android-decodable audio formats (WAV, M4A, MP3, OGG, FLAC, AAC, WebM).
3. For app/browser playback capture, use Android `MediaProjection` + `AudioPlaybackCaptureConfiguration` on Android 10+. The OS consent dialog is mandatory; source apps can disallow capture and protected/DRM audio cannot be captured. Never bypass those restrictions. File import and microphone remain fallbacks.
4. Show recording duration and waveform; let the user listen, trim, and confirm.
5. Clean and validate the sample: mono conversion, resampling, rumble removal, silence trimming, loudness normalization, clipping/noise checks. Do not use aggressive denoising that changes the timbre.
6. Require confirmation that the user owns the voice or has permission to clone it.
7. Generate a local Shtorm speaker/reference state. This is reference conditioning, not model fine-tuning or retraining.
8. Synthesize an unseen Russian test phrase, audition it, then save the profile locally.
9. Let the user rename, preview, export, and delete the profile and its source recording independently.

## Android architecture

- `TtsEngine` interface: engine ID, model pack ID, supported locales, supported voice capabilities, load/unload, streaming synthesis, cancellation, and readiness.
- Separate adapters: `TeraTtsV2Engine` for preset voices; `ShtormRuCloneEngine` for reference-audio profiles; optional `Supertonic3Engine` for extra preset styles.
- `ModelPackManager`: pinned revision, manifest, per-file SHA-256, resumable download, .part files, atomic activation, storage preflight, and no redownload when a verified pack is already installed.
- Store model packs in app-private persistent files storage, not cache or APK assets. Keep the model directory and custom voice profiles untouched by ordinary APK updates.
- `VoiceProfileStore`: metadata + engine-specific local conditioning files, versioned by model revision.
- `AudioPlaybackService`: bounded text chunks, streaming audio queue, pause/resume/seek, foreground media playback, sleep timer, and playback position per book.
- `BookSpeechRouter`: narrator mode bypasses speaker routing; character mode maps stable speaker IDs to preset or custom profiles. Keep the existing dialogue-analysis work independent.

## User experience

New section: **Озвучка** with:
- Playback mode: **Один диктор** / **Персонажи**.
- Engine/model status and one-time download action.
- Voice catalog with a preview button and clearly marked Russian-tested voices.
- **Мои голоса** with create, preview, rename, assign, and delete.
- Recording/import/capture wizard with explicit consent and a clear capture indicator.
- Quality and storage status; model version and installed size.
- No automatic download or analysis on app launch. The user starts downloads and voice creation explicitly.

## Implementation order

1. Inspect current FB2AudioPrep reader entry points and existing voice/model contracts; preserve the existing dialogue-analysis module.
2. Implement durable model-pack storage/versioning and the TeraTTSv2 ONNX adapter.
3. Implement streaming playback service and the two playback modes using existing dialogue segment metadata.
4. Finish microphone/file import and permitted browser/app playback capture; improve the existing sample capture prototype.
5. Prototype Shtorm Android inference. Do not expose clone-profile creation as production-ready until it synthesizes unseen Russian text fully offline on the target ARM64 phone.
6. Add voice audition, profile persistence, assignment, and deletion.
7. Run real-device quality/performance tests: naturalness, pronunciation/stress, voice similarity, real-time factor, peak RAM, heat, battery, long-book stability, and airplane-mode operation.

## Release gates

- TeraTTSv2 Russian passage plays in airplane mode after first download and app restart.
- Model files are hash-verified and retained across APK updates.
- Playback supports screen-off, pause/resume, seeking, cancellation, and long books without unbounded memory use.
- At least five male and five female Russian preset voices are listed only after actual audition and verification; do not count English styles.
- A 10–30 second user sample can create a reusable local profile that generates a previously unseen Russian sentence offline on the target phone.
- Browser/app capture fails gracefully when the source blocks capture and always offers microphone/file import.
- All model, code, voice-library, and sample assets retain their required licenses and attribution.

## Licensing and privacy

- TeraTTSv2: Open RAIL-M with an additional commercial attribution condition; preserve the model license and RUAccent notice.
- Shtorm-PocketTTS-RU v2: CC-BY-4.0; preserve attribution and the model card's voice-consent restrictions.
- Generic Kyutai Pocket TTS: CC-BY-4.0 but not Russian in the official language list; not the Russian cloning choice.
- Custom recordings and speaker profiles remain on-device by default. Require explicit permission for voices belonging to other people and provide deletion controls.
