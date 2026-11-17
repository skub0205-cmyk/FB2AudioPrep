# Russian voice library and custom voice capture requirements

## Product requirements

- The shipped voice catalog is Russian-only (locale `ru-RU`).
- The first complete voice-library release must contain at least 10 distinct built-in Russian voices: at least 5 masculine-presenting and 5 feminine-presenting voices.
- Every voice must have a preview phrase, a stable ID, display name, voice type, model/runtime compatibility and license/source metadata.
- Users can select a narrator voice for single-voice playback and assign a voice independently to each character in character mode.
- Users can create, rename, audition, export and delete their own voice profiles in the app.
- Voice profiles and downloaded model packs are stored locally. After initial download, synthesis and profile management must work offline.
- The app must not silently substitute a non-Russian voice. If a Russian voice is unavailable, show a clear error.

## Custom voice creation flow

1. User chooses **Create my voice**.
2. User selects a source: microphone recording, audio file import, or system playback capture.
3. Explain that the recording must be the user's voice or a voice they have explicit permission to use. Require confirmation before profile creation.
4. Record/import a clean sample and show a waveform, duration, clipping/noise checks and playback.
5. Ask for the exact transcript of the reference speech when required by the chosen model.
6. Trim silence, normalize sample rate/channel format and run voice-quality checks.
7. Create a local speaker embedding / reference conditioning package using the selected cloning model.
8. Generate a short Russian test phrase, let the user compare it with the reference and save the profile only after explicit confirmation.
9. Store profile metadata, model version and hashes locally; allow deletion of both profile and source recording.

## Capturing audio from another app

On Android 10/API 29 and later, implement system playback capture through `MediaProjection` and `AudioPlaybackCaptureConfiguration`, subject to OS permission. Capture is not guaranteed for every app: the source app must expose capturable playback (supported usage and capture policy), and protected/opted-out streams cannot be captured. The UI must explain this limitation and provide microphone/file-import alternatives.

The app must show an explicit recording/capture indicator, provide a stop button, and stop immediately when the projection is revoked. Never attempt to bypass DRM, secure playback, app capture restrictions or OS consent.

## Voice cloning model selection

Do not equate a TTS model with a voice-cloning model. A candidate is accepted only after testing:
- Russian-language pronunciation and prosody.
- Voice similarity from short reference recordings.
- Robustness to different recording conditions.
- CPU/RAM/thermal performance on target Android devices.
- Fully offline inference after one-time model download.
- Model and training-data license compatibility, including redistribution and user-generated voice profiles.

TeraTTSv2 is a candidate for high-quality Russian preset voices and stress handling, but its documented selectable voice styles alone do not prove arbitrary reference-audio voice cloning. Keep preset TTS and custom voice cloning as separate adapters unless an actual supported cloning path is validated.

## Privacy, consent and misuse prevention

- Only create profiles from audio the user owns or has permission to use.
- Do not provide identity verification or claim that a clone is the real speaker.
- Store all recordings and embeddings locally by default.
- Require a clear confirmation that the user has rights/consent to clone the voice.
- Provide deletion controls for source recordings and generated profiles.
- Clearly label generated speech as synthetic when exported/shared.

## Release gates

The feature is not complete until:
- The built-in catalog contains at least five tested male and five tested female Russian voices.
- The playback capture works on a test browser/device where capture is allowed and fails gracefully where it is blocked.
- Microphone and file-import alternatives work.
- A custom voice profile can synthesize previously unseen Russian sentences fully offline.
- Voice quality and similarity are tested on the minimum supported phone, not just an emulator.
