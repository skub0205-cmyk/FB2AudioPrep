# TTS engine evaluation and selection (2026-11-18)

## Decision

Do not ship a single model as if it satisfies every requirement. Use a two-engine design:

1. **Preset Russian voices:** evaluate Piper ONNX through sherpa-onnx Android first, with TeraTTSv2 as a separate higher-quality/stress-aware candidate.
2. **User voice cloning:** keep a dedicated cloning adapter. No model is accepted until it can create a profile from a local recording and synthesize unseen Russian text on a physical Android device with networking disabled.

## Evidence and limits

### TeraTTSv2

- The published ONNX release lists four Russian voice styles: `ru_f1`, `ru_m5`, `ru_f2`, and `ru_m1`.
- Russian text gets automatic stress annotation; explicit `+` stress markers take precedence.
- It streams audio and uses ONNX Runtime.
- Four Russian styles do not satisfy the product's minimum of five male and five female voices. The README documents fixed voice-style selection, not arbitrary user-reference cloning.
- Model weights have an Open RAIL-M license with an additional attribution condition for commercial products. Preserve the license and attribution.

Status: **candidate for Russian speech quality and stress; not the voice-cloning solution and not the ten-voice catalog by itself.**

### Piper / sherpa-onnx

The current Russian Piper catalog lists 20 Russian models. The four official Piper voices surfaced in the sherpa-onnx model list are:

| Voice ID | Initial catalog label | License note |
|---|---|---|
| `ru_RU-denis-medium` | Denis | Check upstream MODEL_CARD |
| `ru_RU-dmitri-medium` | Dmitri | Check upstream MODEL_CARD |
| `ru_RU-irina-medium` | Irina | Check upstream MODEL_CARD |
| `ru_RU-ruslan-medium` | Ruslan | CC-BY-NC-SA-4.0 in the catalog mirror; non-commercial only |

Community Piper catalog entries include additional Russian voices (for example April420, Dict, Kat580, Nara426, Sova200, Fr6800, Sushkov V4, Igm3804, Terra5871, Mari, Luka, Puriso and Lecturer). Their names do not establish gender, quality, redistribution rights, or commercial compatibility. Each candidate must be auditioned and its original model card checked before packaging.

Piper is a useful lightweight preset-voice candidate, but its ordinary single-speaker models do not clone a user's voice.

Status: **best first route to a low-memory multi-voice Russian preset catalog, subject to per-model licensing and listening tests.**

### Qwen3-TTS and mobile conversion

- Qwen3-TTS Base models advertise short-reference voice cloning and list Russian among supported languages.
- The community LiteRT conversion of Qwen3-TTS 12Hz 0.6B demonstrates Android execution on recent flagship devices, but the published benchmark reports roughly 1.44–1.90 GB peak process memory on Galaxy S26 / Pixel 10 Pro, and model bundles around 2.24–2.44 GB.
- That mobile conversion ships a single demo speaker. Its documentation says custom speaker enrollment requires an x-vector extracted off-device. Therefore this converted bundle does **not** meet the requirement for fully offline voice-profile creation on the phone.
- Benchmarks are on recent flagship devices; they do not establish acceptable speed or memory use on this project's minimum Android device.

Status: **research candidate only; not selected as the first on-device cloning engine.**

### Pocket TTS / ZipVoice

- sherpa-onnx documents Pocket TTS reference-audio cloning without a transcript, and ZipVoice cloning with reference audio plus its exact transcript.
- The standard Pocket TTS example is English-oriented; do not infer Russian support from the model family or from unrelated third-party multilingual ports.
- A Russian-capable model pack must be identified, licensed, and tested before this path is enabled.

Status: **not yet accepted for Russian cloning.**

## Implementation sequence

1. Add sherpa-onnx Android runtime behind `RussianTtsEngine`; begin with the four established Piper Russian voices, each with its own model pack manifest.
2. Build a candidate audition screen and collect listening results. Do not label voices male/female based only on their names.
3. Expand the built-in list to five male and five female only after voice gender, naturalness, pronunciation, license, model hash, and redistribution terms have been verified.
4. Keep TeraTTSv2 as an optional second preset engine if its Android ONNX integration and storage/performance tests pass.
5. Keep the cloning UI hidden until a genuinely Russian-capable model passes local recording -> profile creation -> unseen Russian sentence synthesis with airplane mode enabled.

## Required acceptance tests

- All selected packs have pinned upstream revisions, SHA-256 hashes, original model cards, license files, and attribution.
- The app downloads each pack once, verifies its hash, installs atomically, and can synthesize after restart in airplane mode.
- Each voice is auditioned using the same Russian test paragraph containing ё, names, numerals, abbreviations, punctuation, and stress-sensitive homographs.
- The clone test uses a reference recording and a sentence not present in the recording; replaying or transforming the original clip does not count.
- Measure peak memory, synthesis real-time factor, heat, battery draw, and failure behavior on a physical target phone.

## Android playback capture

System playback capture remains an optional source path, never the only one. It requires Android system consent and compatible source-app audio policy. If the source app blocks capture or the audio is protected, report that capture is unavailable and offer microphone recording or file import. Do not bypass OS restrictions or DRM.
