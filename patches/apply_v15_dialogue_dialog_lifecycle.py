from pathlib import Path
import re

p = Path("app/src/main/java/ru/fbaudioprep/MainActivity.kt")
s = p.read_text(encoding="utf-8")

old = '.setItems(labels.toTypedArray()) { _, which -> editFindingSpeaker(which, profiles) }'
new = '.setItems(labels.toTypedArray()) { dialog, which ->\n                dialog.dismiss()\n                window.decorView.post { editFindingSpeaker(which, profiles) }\n            }'
if new not in s:
    if old not in s:
        raise SystemExit("Cannot locate dialogue list click handler")
    s = s.replace(old, new, 1)

start = s.find("    private fun editFindingSpeaker(index: Int, profiles: List<CharacterProfile>) {")
end = s.find("\n    private fun refreshDialogueReport()", start)
if start < 0 or end < 0:
    raise SystemExit("Cannot locate editFindingSpeaker()")

method = """    private fun editFindingSpeaker(index: Int, profiles: List<CharacterProfile>) {
        if (index !in dialogueFindings.indices) return
        val finding = dialogueFindings[index]
        val choices = mutableListOf("Не назначать персонажа")
        choices.addAll(profiles.map { "${it.name} — ${it.voice}" })
        choices.add("＋ Создать нового персонажа")

        AlertDialog.Builder(this)
            .setTitle("Кто произносит эту реплику?")
            .setMessage(finding.fragment.take(900))
            .setItems(choices.toTypedArray()) { dialog, selected ->
                dialog.dismiss()
                // Wait until Android has dismissed this dialog before opening another one.
                window.decorView.post {
                    when {
                        selected == 0 -> {
                            assignFindingToProfile(index, null)
                            Toast.makeText(this, "Реплика оставлена без персонажа", Toast.LENGTH_SHORT).show()
                            refreshDialogueReport()
                            showDialogueReview()
                        }
                        selected == choices.lastIndex -> createCharacterForFinding(index)
                        selected in 1..profiles.size -> {
                            val profile = profiles[selected - 1]
                            assignFindingToProfile(index, profile)
                            Toast.makeText(this, "Говорящий назначен: ${profile.name}", Toast.LENGTH_SHORT).show()
                            refreshDialogueReport()
                            showDialogueReview()
                        }
                    }
                }
            }
            .setNegativeButton("Отмена", null)
            .show()
    }

    private fun createCharacterForFinding(index: Int) {
        editCharacter(null) { created ->
            // The editor's positive-button dialog must close before the review list is shown.
            window.decorView.post {
                assignFindingToProfile(index, created)
                Toast.makeText(this, "Персонаж ${created.name} создан и назначен", Toast.LENGTH_SHORT).show()
                refreshDialogueReport()
                showDialogueReview()
            }
        }
    }

    private fun assignFindingToProfile(index: Int, profile: CharacterProfile?) {
        if (index !in dialogueFindings.indices) return
        val finding = dialogueFindings[index]
        val corrected = finding.copy(
            speaker = profile?.name,
            voice = profile?.voice?.takeUnless { it.isBlank() || it == "не задан" },
            confidence = if (profile == null) 0f else 1f,
            reason = if (profile == null) "Оставлено без назначения вручную" else "Говорящий назначен пользователем"
        )
        dialogueFindings = dialogueFindings.toMutableList().also { it[index] = corrected }
        DialogueCorrectionStore.save(this, originalText, index, corrected)
    }
"""
s = s[:start] + method + s[end:]
p.write_text(s, encoding="utf-8")

gpath = Path("app/build.gradle.kts")
g = gpath.read_text(encoding="utf-8")
if 'versionName = "2.0.6"' not in g:
    raise SystemExit("Expected app version 2.0.6 before bump")
m = re.search(r'versionCode\\s*=\\s*(\\d+)', g)
if not m:
    raise SystemExit("Could not locate versionCode")
g = g[:m.start()] + "versionCode = " + str(int(m.group(1)) + 1) + g[m.end():]
g = g.replace('versionName = "2.0.6"', 'versionName = "2.0.7"', 1)
gpath.write_text(g, encoding="utf-8")
print("Deferred dialogue and character editor dialogs until the previous dialog is dismissed; version 2.0.7.")
