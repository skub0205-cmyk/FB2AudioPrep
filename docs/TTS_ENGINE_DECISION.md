# TTS engine decision — TeraTTSv2

**Decision date:** 2026-11-18  
**Status:** Selected as the primary speech-synthesis engine for FB2AudioPrep.

## Product decision

FB2AudioPrep will use **TeraTTSv2 as its primary TTS engine**. Silero is not the primary engine and must not be used as a fallback without an explicit future product decision.

The reason is the product's priority: natural, expressive audiobook narration and dialogue take precedence over choosing the smallest or easiest model. The app must preserve the user's two playback modes:

1. Character mode: each detected/edited character is assigned a selected voice style.
2. Single-voice mode: one selected voice reads the entire book.

Speaker identity and voice assignment remain controlled by FB2AudioPrep. Do not rely on TeraTTS automatic gender guessing to resolve book dialogue.

## Verified upstream facts

Based on the current TeraSpace/TeraTTSv2 ONNX model card:

- ONNX Runtime inference; CPU provider is documented.
- Distilled sampler is the default eight-step path; a teacher sampler is also available.
- Output is mono float32 at 44,100 Hz.
- Streaming generation is documented.
- Russian text inside `<ru>…</ru>` receives automatic stress annotation; explicit `+` stress markers take precedence.
- Ten voice styles are listed in total, but only four are explicitly Russian styles: `ru_f1`, `ru_m5`, `ru_f2`, `ru_m1`. The other six styles are English reference prompts and must not be counted toward the requirement for Russian voices.
- The model card documents selection of bundled, precomputed voice styles. It does not establish arbitrary user-recording voice cloning.

Upstream model: https://huggingface.co/TeraSpace/TeraTTSv2

## Important release gaps

The user's requirements remain:

- At least five Russian female and five Russian male voices.
- Ability to add a user's own voice from a recording captured/imported on the phone.
- Fully offline synthesis after one-time model download.

The four explicitly Russian preset styles do **not** satisfy the 5+5 requirement. Do not silently count English prompts as Russian voices. Research and validate additional TeraTTSv2-compatible Russian voice prompts/styles, or a licensed extension/fine-tuning path, before claiming the catalog is complete.

Recording/importing a sample is not voice cloning. A separate, genuinely compatible speaker-conditioning or cloning implementation is required to synthesize unseen text in the recorded voice. Keep that feature marked experimental/unavailable until it passes an on-device offline test.

## Android integration plan

1. Pin a specific upstream model revision and record SHA-256 for every downloaded file. Do not load mutable remote code at runtime.
2. Audit the model's ONNX graph inputs/outputs, preprocessing, text normalization, style conditioning, and vocoder pipeline.
3. Implement a Kotlin/Android ONNX Runtime inference adapter. Load model sessions once, run synthesis off the UI thread, and feed generated 44.1 kHz mono PCM into the app's audio player.
4. Start with the distilled sampler for mobile performance; benchmark teacher separately for quality/performance before exposing it as an option.
5. Wrap Russian text in the required `<ru>…</ru>` language tags. Preserve user-supplied explicit stress markers and test automatic stress on Russian names, homographs, numbers, abbreviations, and dialogue.
6. Cache synthesized chunks locally, support cancellation/resume, and retain book position and playback mode.
7. Benchmark on a physical Android phone: cold/warm load time, peak RAM, real-time factor, thermal behavior, battery use, long-book stability, and airplane-mode operation.

## Voice and dialogue policy

- Character-to-voice mapping belongs to the book's editable character profile, not an automatic gender guess.
- Dialogue attribution must use nearby speech tags and narrative context. A vocative such as “Нико!” is not proof that Nico is speaking.
- The test corpus must include the known “Нико” and “ИсКин” passages and confirm the voice selected for each utterance.
- The catalog must distinguish verified Russian voices from experimental styles. Never infer voice gender from a voice ID or character name; audition and verify.

## Licensing and attribution

The model card states Open RAIL-M with an additional commercial attribution condition. Preserve upstream license notices and use the required public product credit when applicable, e.g. “Text-to-speech powered by TeraTTSv2 by TeraSpace.” Review the full model and upstream component licenses before redistributing model weights or derivatives. RUAccent-derived assets retain their separate notice/license.

## Acceptance criteria

The TeraTTSv2 integration is not considered complete until:

- All required model files are pinned, hashed, licensed, downloaded once, and verified before installation.
- A Russian test passage synthesizes after app restart in airplane mode.
- Streaming playback, pause/resume, seeking, background playback, and cancellation work on-device.
- The 5 male + 5 female Russian voice requirement is met with ten genuinely Russian, auditioned, licensed styles.
- Character mapping can be manually corrected and persists per book.
- The “Нико” and “ИсКин” regression passages use the intended voices.
- Voice cloning remains hidden or explicitly experimental until a recording can create a speaker profile that synthesizes a previously unseen Russian sentence fully offline.
