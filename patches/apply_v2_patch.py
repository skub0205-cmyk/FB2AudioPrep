from pathlib import Path

main = Path("app/src/main/java/ru/fbaudioprep/MainActivity.kt")
store = Path("app/src/main/java/ru/fbaudioprep/DialogueCorrectionStore.kt")
gradle = Path("app/build.gradle.kts")

text = main.read_text(encoding="utf-8")
start = text.index("    private fun editFindingSpeaker(")
end = text.index("\n    private fun refreshDialogueReport()", start)
replacement = r'''    private fun editFindingSpeaker(index: Int, profiles: List<CharacterProfile>) {
        val finding = dialogueFindings[index]
        val choices = mutableListOf("Не назначать персонажа")
        choices.addAll(profiles.map { "${it.name} — ${it.voice}" })
        val current = finding.speaker?.let { name -> profiles.indexOfFirst { it.name == name } } ?: -1
        var selectedChoice = current + 1
        AlertDialog.Builder(this)
            .setTitle("Кто произносит эту реплику?")
            .setMessage(finding.fragment.take(900) + "\n\nВыберите персонажа и нажмите «Сохранить».")
            .setSingleChoiceItems(choices.toTypedArray(), selectedChoice) { _, selected ->
                selectedChoice = selected
            }
            .setPositiveButton("Сохранить") { dialog, _ ->
                val selectedProfile = if (selectedChoice == 0) null else profiles[selectedChoice - 1]
                val corrected = finding.copy(
                    speaker = selectedProfile?.name,
                    voice = selectedProfile?.voice?.takeUnless { it == "не задан" },
                    confidence = if (selectedProfile == null) 0f else 1f,
                    reason = if (selectedProfile == null) "Пользователь сохранил: не назначать персонажа"
                        else "Говорящий назначен пользователем и сохранён для этой книги"
                )
                dialogueFindings = dialogueFindings.toMutableList().also { it[index] = corrected }
                DialogueCorrectionStore.save(this, originalText, index, corrected)
                refreshDialogueReport()
                Toast.makeText(
                    this,
                    if (selectedProfile == null) "Назначение сохранено: персонаж не выбран"
                    else "Сохранено: ${selectedProfile.name} (${selectedProfile.voice})",
                    Toast.LENGTH_LONG
                ).show()
                dialog.dismiss()
                showDialogueReview()
            }
            .setNegativeButton("Отмена", null)
            .show()
    }
'''
text = text[:start] + replacement + text[end:]
text = text.replace("FB2 AudioPrep 1.9.0", "FB2 AudioPrep 2.0.0")
main.write_text(text, encoding="utf-8")

s = store.read_text(encoding="utf-8")
old = 'prefs.edit().putString(key, root.toString()).apply()'
new = '''// Commit before reopening the review dialog so the assignment survives
        // immediate refreshes and Activity recreation.
        check(prefs.edit().putString(key, root.toString()).commit()) {
            "Не удалось сохранить ручное назначение говорящего"
        }'''
if old not in s:
    raise SystemExit("Expected persistence line not found; refusing to patch.")
store.write_text(s.replace(old, new), encoding="utf-8")

g = gradle.read_text(encoding="utf-8")
if 'versionName = "1.9.0"' not in g:
    raise SystemExit("Expected version 1.9.0 not found in app/build.gradle.kts")
gradle.write_text(g.replace('versionCode = 20; versionName = "1.9.0"',
                            'versionCode = 21; versionName = "2.0.0"'),
                  encoding="utf-8")

print("Applied FB2AudioPrep 2.0.0 manual speaker-assignment patch.")
