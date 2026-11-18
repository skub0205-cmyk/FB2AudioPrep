# Third-party notices

## TeraTTS Android — Russian dialogue and speaker-role analysis

The following files in `app/src/main/java/ru/fbaudioprep/teratts/` are derived from TeraTTS Android:

- `DialogueAnalyzer2.kt`
- `NameGender.kt`
- `RoleWindows.kt`
- `RoleTokenizer.kt`
- `RoleModel.kt`

Upstream project: https://github.com/9208499-ship-it/teratts-android  
Upstream revision: `ec0537f99d14f953beb64b1cf93a7b868e0c4720` (TeraTTS 1.59, role model m10b)  
Upstream license: GNU General Public License, version 3 (GPL-3.0-only).

These files were adapted for FB2AudioPrep: package names were changed; app-specific logging, cache keys, and model progress handling were decoupled from TeraTTS's reader UI. The model architecture, tokenizer, text-window construction, and dialogue-analysis logic are derived from the upstream project. Changes are dated 2026-11-18.

The m10b model assets are fetched from the upstream `role-model-m10b` release by the application only after the user requests installation. Their expected file sizes and SHA-256 digests are checked before activation. The model files are not embedded in the APK.

FB2AudioPrep is distributed under GPL-3.0. See `LICENSE`.
