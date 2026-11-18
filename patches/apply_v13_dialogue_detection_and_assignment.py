from pathlib import Path
import re

p = Path("app/src/main/java/ru/fbaudioprep/DialogueAnalyzer.kt")
s = p.read_text(encoding="utf-8")
anchor = """    fun analyzeBook(text: String): List<DialogueFinding> {
        val sourceParagraphs = text.split(Regex("\\\\r?\\\\n\\\\s*\\\\r?\\\\n"))
            .map { it.trim() }
"""
replacement = """    private fun splitIntoDialogueUnits(text: String): List<String> {
        val units = mutableListOf<String>()
        val current = StringBuilder()
        fun flush() {
            val value = current.toString().trim()
            if (value.isNotEmpty()) units.add(value)
            current.setLength(0)
        }
        for (line in text.lines()) {
            val trimmed = line.trim()
            if (trimmed.isEmpty()) { flush(); continue }
            val startsDashDialogue = trimmed.startsWith("—") || trimmed.startsWith("–")
            if (startsDashDialogue && current.isNotEmpty()) flush()
            if (current.isNotEmpty()) current.append(System.lineSeparator())
            current.append(trimmed)
        }
        flush()
        return units
    }

    fun analyzeBook(text: String): List<DialogueFinding> {
        val sourceParagraphs = splitIntoDialogueUnits(text)
"""
if "private fun splitIntoDialogueUnits" not in s:
    if anchor not in s: raise SystemExit("Cannot locate analyzeBook paragraph split")
    s = s.replace(anchor, replacement, 1)
s = s.replace("""                    isDialogueLine(paragraph) ||
                    (hasQuotedSpeech && hasSpeechVerb(paragraph)) ||
""", """                    isDialogueLine(paragraph) ||
                    (hasQuotedSpeech && hasSpeechVerb(paragraph)) ||
""", 1)
p.write_text(s, encoding="utf-8")

p = Path("app/src/main/java/ru/fbaudioprep/MainActivity.kt")
s = p.read_text(encoding="utf-8")
s = s.replace("private fun editCharacter(existing: CharacterProfile?) {",
              "private fun editCharacter(existing: CharacterProfile?, onSaved: ((CharacterProfile) -> Unit)? = null) {", 1)
old = """                val variants = aliases.text.toString().split(",").map { it.trim() }.filter { it.isNotBlank() }
                val updated = loadCharacters().filterNot { it.name == existing?.name }.toMutableList()
                updated.add(CharacterProfile(canonical, variants, voice.selectedItem.toString()))
                saveCharacters(updated)
                showCharacters()
"""
new = """                val variants = aliases.text.toString().split(",").map { it.trim() }.filter { it.isNotBlank() }
                val created = CharacterProfile(canonical, variants, voice.selectedItem.toString())
                val updated = loadCharacters().filterNot { it.name == existing?.name }.toMutableList()
                updated.add(created)
                saveCharacters(updated)
                if (onSaved != null) onSaved(created) else showCharacters()
"""
if new not in s:
    if old not in s: raise SystemExit("Cannot locate character save block")
    s = s.replace(old, new, 1)
start = s.find("    private fun editFindingSpeaker(index: Int, profiles: List<CharacterProfile>) {")
end = s.find("\n    private fun refreshDialogueReport()", start)
if start < 0 or end < 0: raise SystemExit("Cannot locate editFindingSpeaker()")
method = """    private fun editFindingSpeaker(index: Int, profiles: List<CharacterProfile>) {
        val finding = dialogueFindings[index]
        val choices = mutableListOf("Не назначать персонажа")
        choices.addAll(profiles.map { "\${it.name} — \${it.voice}" })
        choices.add("＋ Создать нового персонажа")
        val current = finding.speaker?.let { name -> profiles.indexOfFirst { it.name == name } } ?: -1
        AlertDialog.Builder(this)
            .setTitle("Кто произносит эту реплику?")
            .setMessage(finding.fragment.take(900))
            .setSingleChoiceItems(choices.toTypedArray(), current + 1) { dialog, selected ->
                if (selected == choices.lastIndex) {
                    dialog.dismiss()
                    createCharacterForFinding(index)
                    return@setSingleChoiceItems
                }
                val profile = if (selected == 0) null else profiles[selected - 1]
                assignFindingToProfile(index, profile)
                dialog.dismiss()
                showDialogueReview()
            }
            .setNegativeButton("Отмена", null)
            .show()
    }

    private fun createCharacterForFinding(index: Int) {
        editCharacter(null) { created ->
            assignFindingToProfile(index, created)
            showDialogueReview()
        }
    }

    private fun assignFindingToProfile(index: Int, profile: CharacterProfile?) {
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
s = s.replace("        reviewDialoguesButton.isEnabled = findings.isNotEmpty()",
              "        reviewDialoguesButton.isEnabled = originalText.isNotBlank()", 1)
p.write_text(s, encoding="utf-8")

p = Path("app/build.gradle.kts")
g = p.read_text(encoding="utf-8")
m = re.search(r'versionCode\s*=\s*(\d+)', g)
if not m or 'versionName = "2.0.4"' not in g:
    raise SystemExit("Could not bump version to 2.0.5")
g = g[:m.start()] + "versionCode = " + str(int(m.group(1)) + 1) + g[m.end():]
g = g.replace('versionName = "2.0.4"', 'versionName = "2.0.5"', 1)
p.write_text(g, encoding="utf-8")
print("Added single-newline dialogue segmentation and create-character-from-reply assignment; version 2.0.5.")
