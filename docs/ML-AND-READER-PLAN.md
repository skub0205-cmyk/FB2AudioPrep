# ML architecture decision (November 2026)

## 1. Russian stress placement

Selected candidate: **RUAccent INT8 ONNX pipeline**, distributed through the Apache-2.0 `stressonnx` project.

Why:
- contextual stress and homograph handling, not just a word list;
- ONNX Runtime inference, so the target runtime can be native Android and offline;
- the INT8 pipeline is reported at about 144 MB download / 313 MB RSS, with 0.946 word accuracy and 0.825 on homographs in the project's own benchmark;
- upstream attribution and model licenses are documented.

Sources:
- https://github.com/TigreGotico/stressonnx
- https://github.com/TigreGotico/stressonnx/blob/dev/docs/models.md
- https://github.com/Den4ikAI/ruaccent (MIT)

Integration requirements before enabling it:
1. Pin exact model revision and SHA-256 for every ONNX/tokenizer/vocabulary file.
2. Verify all model inputs, tokenization and output-to-source offset mapping on Android.
3. Keep the current dictionary as the final override; user corrections must win over model output.
4. Preserve original punctuation, line breaks, XML markup and all non-Russian text.
5. Add a review mode for uncertain or unknown names.
6. Benchmark on a manually stressed Russian book corpus, including proper names, е/ё, hyphenated words and homographs. Upstream benchmark figures are not a promise of accuracy on novels.

Do not mark every multi-vowel word automatically unless the model is confident. Keep service words and already accented words intact. Never silently replace a user's explicit stress dictionary entry.

## 2. Dialogue speaker attribution

The most directly relevant reference is TeraTTS 1.59's `DialogueAnalyzer2` + `RoleModel` (RuModernBERT-based ONNX role classifier). It is purpose-built for speaker attribution and is a much better reference than a generic chat model.

However, the TeraTTS repository/model release does not expose a clear reuse license in the inspected repository metadata. Therefore FB2AudioPrep must **not redistribute its code or model weights** without explicit permission.

Chosen implementation route:
- keep deterministic dialogue parsing and the user's manual corrections as the source of truth;
- use `deepvk/RuModernBERT-small` (Apache-2.0 base) as the candidate encoder for a separately trained speaker-attribution head;
- train/evaluate that head on properly licensed, manually annotated dialogue examples;
- export to ONNX and run through ONNX Runtime Android;
- use manual anchors as hard constraints; explicit author attribution overrides inferred turn-taking; vocatives are never treated as speaker evidence by themselves;
- when confidence is low, leave the line unresolved rather than inventing a speaker.

The role model is a separate optional download. Core import/export, dictionary, reader and rule-based analysis must continue to work fully offline without it.

## 3. Reader interface

The book preview is moved out of the home screen into a dedicated full-screen reader:
- full-width text area and comfortable page margins;
- adjustable font size;
- scroll progress;
- separate home screen that itself scrolls, without a narrow embedded book strip.

This is the first UI pass. A later pass should add night/sepia themes, table of contents, chapter navigation, bookmarks and search.

## 4. Quality gates

Before a model is enabled by default:
- verify licenses and checksums;
- test on low-memory Android devices;
- compare against human annotations, not just another model's predictions;
- include regression tests for the user's examples (Niko and IsKin) and stress ambiguities;
- make model download optional and keep inference entirely local after download.

## 5. Model installation and analysis must be separate actions

User acceptance requirement (November 2026):
- Downloading/installing the dialogue role model must **never automatically start dialogue recognition**.
- After a successful download, show a short confirmation that the model is ready and return to the book screen / analysis screen in an idle state.
- Keep the currently opened book and its selection/state; do not silently launch a long-running task.
- Dialogue recognition starts only after the user explicitly presses the **“Проверить диалоги”** action.
- If the user requests analysis before the model is installed, explain that the model is required and offer a separate **“Загрузить модель”** action. Once download finishes, wait for a second explicit tap on **“Проверить диалоги”**; do not chain download completion into analysis.
- On subsequent launches, model presence must not trigger analysis. Loading or initializing the model is not the same as running book analysis.
- Keep download progress and analysis progress as separate indicators with separate cancellation/lifecycle handling.
- Add regression tests for: first-time model download, successful download, failed/interrupted download, app restart with model already installed, and explicit user-started analysis. Assert that analysis is not invoked in any case until the user taps the analysis action.


## 6. Dialogue-analysis performance work (measured baseline)

Observed on the user's Android device with a Russian book of 506,000 characters / 76,268 words:
- 129 model fragments;
- full analysis completed in approximately 20–25 minutes;
- this is the baseline to compare against, not a claimed benchmark for other devices.

Optimization order:
1. For explicit, user-started analysis, use normal CPU priority. Keep background priority for analysis scheduled beside active TTS playback.
2. Measure 2 vs 4 ONNX intra-op threads on the target device before choosing a default. Do not assume more threads are always faster; thermal throttling and memory bandwidth can reverse the result.
3. Record elapsed time per model window, tokenizer time, inference time, number of windows, cache hits, and device thread count.
4. Only after profiling, reduce duplicated overlap work. Keep the current 4,000-character core and 1,800-character side context until regression tests show that any change preserves attribution quality.
5. Compare identical book/model/device runs and inspect the user's difficult cases (Niko and IsKin) before accepting a speed change.

Acceptance: no regression in dialogue speaker/voice attribution or manual corrections; progress remains accurate; model download never starts analysis automatically.
