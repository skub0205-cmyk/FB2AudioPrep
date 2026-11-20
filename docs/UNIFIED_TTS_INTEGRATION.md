# Unified TTS controls for FB2AudioPrep

## Product direction

FB2AudioPrep remains the primary application and keeps its Audiotome book-first interface. TeraTTS Android is the primary technical reference for dialogue attribution, book-wide character rosters, manual speaker corrections, per-character voice assignment, voice import, and audiobook playback. RuVoice TTS is a secondary reference for the settings experience and text preparation tools.

This is an integration of capabilities into FB2AudioPrep, not a copy of either application's screen layout.

## Reference projects

- TeraTTS Android: https://github.com/9208499-ship-it/teratts-android (branch teratts)
- RuVoice TTS: https://github.com/kost-t-human/ruvoice-tts (branch master)

## Audiotome presentation

Keep the existing dark navy / warm gold theme, book-first reader, left icon rail, and current navigation sections. Settings should open as FB2AudioPrep pages/cards within the existing sections, not as a separate cloned app.

Proposed sections:
- **Озвучивание**: active engine, installed model state, narrator voice, playback controls, duration/rate, output level, pauses, queue and sleep timer.
- **Голоса**: narrator, common male/female/unknown voices, per-character cast, voice preview, import and voice eligibility.
- **ИИ-анализ**: dialogue analysis model, progress, confidence threshold, manual corrections, aliases and book roster.
- **Текст**: stress dictionary, replacement dictionary, normalization/splitting rules, test/analyze preview.
- **Профили**: named settings profiles, optional voice-to-profile binding, JSON export/import.
- **Ещё**: storage, model management, diagnostics, accessibility and app information.

## Feature mapping

| Reference capability | FB2AudioPrep destination | Implementation rule |
|---|---|---|
| TeraTTS RoleCast / RolePrefs | Голоса | Preserve book-wide character identity and explicit overrides |
| TeraTTS SpeakerOverrides | ИИ-анализ / Голоса | Manual corrections outrank automatic inference |
| TeraTTS VoiceImport / VoicePrep | Голоса | Only expose formats the selected engine can actually use |
| TeraTTS playback and queue | Озвучивание | Background playback, resume and bounded prebuffer |
| RuVoice voice/rate/pitch/volume | Озвучивание | Expose only controls supported by the active engine |
| RuVoice pauses | Озвучивание | Implement at the audio segment boundary |
| RuVoice stress / replacements | Текст | Keep editable per-user dictionaries and test before synthesis |
| RuVoice rules | Текст | Each rule has a real processing effect and a clear default |
| RuVoice profiles | Профили | Store snapshots independently from shared dictionaries |
| RuVoice preview / analyze | Озвучивание and Текст | Show exact normalized, accented and segmented text before synthesis |
| RuVoice import/export | Профили | Versioned JSON with validation and safe rollback |

## Current implementation baseline

- TeraTTSv2 ONNX is the active engine in FB2AudioPrep.
- TeraTTS RuModernBERT role analysis is already integrated.
- Character-to-voice assignments are stored per book.
- v50 expands matching of explicit author descriptions such as a friendly female voice or an irritated female voice.
- v51 introduces a first Audiotome settings dialog for narrator, common female/male voices, role-based reading, duration scale, output gain and inter-fragment pause. It also routes actual playback through the utterance segmenter instead of forcing every chunk to the narrator voice.
- These v51 changes are provisional until GitHub Actions unit tests and APK build succeed.

## Compatibility and safety rules

1. Do not change the Android applicationId or persistent signing key.
2. Keep model packs in app-private persistent storage that survives APK updates.
3. Never show a setting as available unless the active engine consumes it.
4. Keep TeraTTS as the primary implementation reference; do not substitute a different engine silently.
5. Treat Pocket/Shtorm voice import as engine-specific. A reference recording is not proof that every engine can clone arbitrary voices.
6. Preserve attribution and license notices for any reused implementation or model.

## Licensing note

RuVoice TTS repository declares CC BY-NC-SA 4.0. Its README separately identifies model and bundled-data licenses. Use its behavior and settings as a reference; before copying or adapting source code or redistributing model assets, verify the applicable license and attribution/share-alike/non-commercial conditions for each component.
