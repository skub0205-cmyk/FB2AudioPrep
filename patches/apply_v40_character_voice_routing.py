from pathlib import Path

root = Path("app/src/main/java/ru/fbaudioprep")
(root / "TeraTtsV2SpeechSegmenter.kt").write_text("package ru.fbaudioprep\n\n/**\n * Turns paragraph-level dialogue findings into TTS pieces. Only reliable\n * speaker attributions affect quoted/direct speech; all narration stays on\n * the selected narrator preset. Vocatives are never treated as speakers.\n */\ndata class TeraTtsSpeechPiece(val text: String, val voiceId: String, val kind: String)\n\nobject TeraTtsV2SpeechSegmenter {\n    private val quoteRegex = Regex(\"«([^»]+)»|“([^”]+)”|\\\"([^\\\"]+)\\\"\")\n\n    fun build(\n        bookText: String,\n        findings: List<DialogueFinding>,\n        profiles: List<CharacterProfile>,\n        narratorVoice: String,\n        availableVoices: List<String>,\n        maxChars: Int = 180\n    ): List<TeraTtsSpeechPiece> {\n        val profileByName = profiles.flatMap { p -> (p.aliases + p.name).map { normalize(it) to p } }\n            .toMap()\n        val findingByFragment = findings.associateBy { normalize(it.fragment) }\n        val paragraphs = bookText.replace(\"\\r\n\", \"\n\").replace('\\r', '\n')\n            .split(Regex(\"\\\n\\\\s*\\\n\")).map { it.trim() }.filter { it.isNotBlank() }\n        val output = mutableListOf<TeraTtsSpeechPiece>()\n\n        paragraphs.forEach { paragraph ->\n            val finding = findingByFragment[normalize(paragraph)]\n            val gender = reliableGender(finding, profileByName)\n            val dialogueVoice = gender?.let { chooseVoice(it, narratorVoice, availableVoices) } ?: narratorVoice\n\n            val matches = quoteRegex.findAll(paragraph).toList()\n            if (matches.isNotEmpty()) {\n                var cursor = 0\n                for (match in matches) {\n                    if (match.range.first > cursor) addChunks(output, paragraph.substring(cursor, match.range.first), narratorVoice, \"narration\", maxChars)\n                    val spoken = match.groups.drop(1).firstOrNull { it?.value != null }?.value ?: match.value\n                    addChunks(output, spoken, dialogueVoice, if (gender == null) \"dialogue-fallback\" else \"dialogue\", maxChars)\n                    cursor = match.range.last + 1\n                }\n                if (cursor < paragraph.length) addChunks(output, paragraph.substring(cursor), narratorVoice, \"narration\", maxChars)\n            } else if (paragraph.firstOrNull() in listOf('—', '–')) {\n                val first = paragraph.indexOfFirst { it == '—' || it == '–' }\n                val second = paragraph.indexOfAny(charArrayOf('—', '–'), first + 1)\n                val spokenEnd = if (second > first) second else paragraph.length\n                val spoken = paragraph.substring(first + 1, spokenEnd).trim()\n                if (spoken.isNotBlank()) addChunks(output, spoken, dialogueVoice, if (gender == null) \"dialogue-fallback\" else \"dialogue\", maxChars)\n                if (second >= 0 && second < paragraph.length - 1) {\n                    addChunks(output, paragraph.substring(second + 1), narratorVoice, \"narration\", maxChars)\n                }\n            } else {\n                addChunks(output, paragraph, narratorVoice, \"narration\", maxChars)\n            }\n        }\n        return output\n    }\n\n    private fun reliableGender(\n        finding: DialogueFinding?,\n        profiles: Map<String, CharacterProfile>\n    ): String? {\n        finding ?: return null\n        val manual = finding.reason.contains(\"пользовател\", true) ||\n            finding.reason.contains(\"ручн\", true)\n        val explicit = finding.reason.contains(\"автор\", true) ||\n            finding.reason.contains(\"раздал\", true) ||\n            finding.reason.contains(\"послыш\", true) ||\n            finding.reason.contains(\"голос\", true)\n        if (!manual && !explicit && finding.confidence < 0.78f) return null\n        val profileGender = finding.speaker?.let { profiles[normalize(it)]?.voice }\n        val gender = profileGender?.takeIf { it == \"женский\" || it == \"мужской\" }\n            ?: finding.voice?.takeIf { it == \"женский\" || it == \"мужской\" }\n        return gender\n    }\n\n    private fun chooseVoice(gender: String, narrator: String, available: List<String>): String {\n        val candidates = if (gender == \"женский\") listOf(\"ru_f2\", \"ru_f1\") else listOf(\"ru_m5\", \"ru_m1\")\n        return candidates.firstOrNull { it in available && it != narrator }\n            ?: candidates.firstOrNull { it in available }\n            ?: narrator\n    }\n\n    private fun addChunks(\n        target: MutableList<TeraTtsSpeechPiece>,\n        text: String,\n        voice: String,\n        kind: String,\n        maxChars: Int\n    ) {\n        SpeechTextChunker.chunk(text, maxChars).forEach { target += TeraTtsSpeechPiece(it, voice, kind) }\n    }\n\n    private fun normalize(value: String): String = value.lowercase()\n        .replace('ё', 'е')\n        .replace(Regex(\"[\\\\u0300-\\\\u036f]\"), \"\")\n        .replace(Regex(\"[^\\\\p{L}\\\\p{N}]\"), \"\")\n}\n", encoding="utf-8")
# Normalize Kotlin escape sequences in the generated paragraph splitter.
_segmenter = root / "TeraTtsV2SpeechSegmenter.kt"
_segmenter_text = _segmenter.read_text(encoding="utf-8")
_split_start = _segmenter_text.index("        val paragraphs = bookText.replace(")
_split_end = _segmenter_text.index("        val output = mutableListOf", _split_start)
_segmenter_text = _segmenter_text[:_split_start] + r'''        val paragraphs = bookText.replace("\\r\\n", "\\n").replace('\\r', '\\n')
            .split(Regex("\\\\n\\\\s*\\\\n")).map { it.trim() }.filter { it.isNotBlank() }
''' + _segmenter_text[_split_end:]
_segmenter.write_text(_segmenter_text, encoding="utf-8")

(root / "DialogueFindingsStore.kt").write_text("package ru.fbaudioprep\n\nimport android.content.Context\nimport org.json.JSONArray\nimport org.json.JSONObject\nimport java.security.MessageDigest\n\n/** Persists the completed AI attribution per exact book text, so updates/restarts do not require re-analysis. */\nobject DialogueFindingsStore {\n    private const val PREFS = \"fb2audioprep_dialogue_findings\"\n\n    fun save(context: Context, bookText: String, findings: List<DialogueFinding>) {\n        if (bookText.isBlank()) return\n        val array = JSONArray()\n        findings.forEach { f ->\n            array.put(JSONObject()\n                .put(\"fragment\", f.fragment)\n                .put(\"speaker\", f.speaker ?: JSONObject.NULL)\n                .put(\"voice\", f.voice ?: JSONObject.NULL)\n                .put(\"confidence\", f.confidence.toDouble())\n                .put(\"reason\", f.reason)\n                .put(\"addressedTo\", f.addressedTo ?: JSONObject.NULL)\n                .put(\"contextBefore\", f.contextBefore)\n                .put(\"contextAfter\", f.contextAfter))\n        }\n        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()\n            .putString(key(bookText), array.toString()).apply()\n    }\n\n    fun load(context: Context, bookText: String): List<DialogueFinding> {\n        if (bookText.isBlank()) return emptyList()\n        val raw = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString(key(bookText), null)\n            ?: return emptyList()\n        return try {\n            val array = JSONArray(raw)\n            (0 until array.length()).mapNotNull { i ->\n                val o = array.optJSONObject(i) ?: return@mapNotNull null\n                fun nullable(name: String): String? =\n                    if (o.isNull(name)) null else o.optString(name).takeIf { it.isNotBlank() }\n                DialogueFinding(\n                    fragment = o.optString(\"fragment\"),\n                    speaker = nullable(\"speaker\"),\n                    voice = nullable(\"voice\"),\n                    confidence = o.optDouble(\"confidence\", 0.0).toFloat().coerceIn(0f, 1f),\n                    reason = o.optString(\"reason\"),\n                    addressedTo = nullable(\"addressedTo\"),\n                    contextBefore = o.optString(\"contextBefore\"),\n                    contextAfter = o.optString(\"contextAfter\")\n                )\n            }\n        } catch (_: Exception) {\n            emptyList()\n        }\n    }\n\n    private fun key(text: String): String {\n        val bytes = MessageDigest.getInstance(\"SHA-256\").digest(text.toByteArray(Charsets.UTF_8))\n        return \"book_\" + bytes.joinToString(\"\") { \"%02x\".format(it) }\n    }\n}\n", encoding="utf-8")

p = root / "MainActivity.kt"
s = p.read_text(encoding="utf-8")
if "private var ttsResumeStorageKey = \"\"" not in s:
    s = s.replace('    private var ttsBookKey = ""', '    private var ttsBookKey = ""\n    private var ttsResumeStorageKey = ""', 1)

# Stable queue fingerprint prevents resuming at a wrong offset after dialogue routing changes.
anchor = "    private fun startBookPlayback() {"
helpers = r"""
    private fun buildTtsSpeechQueue(): List<TeraTtsSpeechPiece> {
        val text = processedText.ifBlank { originalText }
        if (text.isBlank()) return emptyList()
        val voices = ttsEngine?.status()?.voices.orEmpty()
        return TeraTtsV2SpeechSegmenter.build(
            bookText = text,
            findings = dialogueFindings,
            profiles = loadCharactersForBook(originalText),
            narratorVoice = selectedTtsVoice,
            availableVoices = voices,
            maxChars = 180
        )
    }

    private fun refreshTtsResumeKey(loadSaved: Boolean) {
        val queue = buildTtsSpeechQueue()
        val fingerprint = MessageDigest.getInstance("SHA-256")
            .digest(queue.joinToString("\n") { it.voiceId + "|" + it.text }.toByteArray(Charsets.UTF_8))
            .joinToString("") { "%02x".format(it) }
        ttsResumeStorageKey = "resume_" + ttsBookKey + "_" + fingerprint
        if (loadSaved) {
            ttsResumeIndex = getSharedPreferences("audiobook_playback", MODE_PRIVATE)
                .getInt(ttsResumeStorageKey, 0).coerceIn(0, queue.size)
        } else {
            ttsResumeIndex = 0
            getSharedPreferences("audiobook_playback", MODE_PRIVATE).edit()
                .putInt(ttsResumeStorageKey, 0).apply()
        }
        if (::playBookButton.isInitialized) {
            playBookButton.text = if (ttsResumeIndex > 0) "▶ Продолжить озвучивание" else "▶ Озвучить книгу"
        }
    }

"""
if "private fun buildTtsSpeechQueue()" not in s:
    assert anchor in s
    s = s.replace(anchor, helpers + anchor, 1)

# Replace the single-voice paragraph queue with a routed queue.
start = s.index("    private fun startBookPlayback() {")
end = s.index("    private fun stopBookPlayback() {", start)
new_method = r'''    private fun startBookPlayback() {
        val engine = ttsEngine ?: return
        if (ttsWorker?.isAlive == true) return
        val queue = buildTtsSpeechQueue()
        if (queue.isEmpty()) return
        if (ttsResumeStorageKey.isBlank()) refreshTtsResumeKey(loadSaved = true)
        val startAt = ttsResumeIndex.coerceIn(0, queue.size)
        if (startAt >= queue.size) {
            ttsResumeIndex = 0
            refreshTtsResumeKey(loadSaved = false)
        }
        val actualStart = ttsResumeIndex
        ttsStopRequested = false
        playBookButton.isEnabled = false
        stopBookButton.isEnabled = true
        ttsWorker = Thread({
            var completed = false
            try {
                for (index in actualStart until queue.size) {
                    if (ttsStopRequested) break
                    val piece = queue[index]
                    runOnUiThread {
                        status.text = "Озвучивание: " + (index + 1) + " из " + queue.size +
                            "\n" + (if (piece.kind == "narration") "Диктор" else "Персонаж") +
                            "\nГолос: " + piece.voiceId
                    }
                    engine.synthesizeAndPlay(
                        TeraTtsTextFormatter.russian(piece.text),
                        piece.voiceId,
                        seed = 1234L + index
                    )
                    if (ttsStopRequested) break
                    ttsResumeIndex = index + 1
                    getSharedPreferences("audiobook_playback", MODE_PRIVATE).edit()
                        .putInt(ttsResumeStorageKey, ttsResumeIndex).apply()
                }
                completed = !ttsStopRequested && ttsResumeIndex >= queue.size
                if (completed) {
                    ttsResumeIndex = 0
                    getSharedPreferences("audiobook_playback", MODE_PRIVATE).edit()
                        .putInt(ttsResumeStorageKey, 0).apply()
                }
                runOnUiThread {
                    status.text = when {
                        completed -> "Озвучивание книги завершено."
                        ttsStopRequested -> "Озвучивание остановлено. Можно продолжить с этого места."
                        else -> "Озвучивание приостановлено."
                    }
                    playBookButton.text = if (ttsResumeIndex > 0) "▶ Продолжить озвучивание" else "▶ Озвучить книгу"
                }
            } catch (e: Throwable) {
                runOnUiThread { status.text = "Ошибка озвучивания: " + (e.message ?: "неизвестно") }
            } finally {
                runOnUiThread {
                    playBookButton.isEnabled = originalText.isNotBlank() && (ttsEngine?.status()?.ready == true)
                    stopBookButton.isEnabled = false
                }
            }
        }, "teratts-v2-playback").also { it.start() }
    }

'''
s = s[:start] + new_method + s[end:]

# Restore persisted dialogue findings for this exact book, and apply any later user corrections.
old = '''                    ttsResumeIndex = getSharedPreferences("audiobook_playback", MODE_PRIVATE)
                        .getInt("resume_" + ttsBookKey, 0)'''
new = '''                    dialogueFindings = DialogueCorrectionStore.apply(
                        this@MainActivity, book.text, DialogueFindingsStore.load(this@MainActivity, book.text)
                    )
                    ttsResumeStorageKey = ""
                    ttsResumeIndex = 0'''
assert old in s
s = s.replace(old, new, 1)
# Refresh queue fingerprint after text and stored findings have been assigned.
anchor = '''                    dialogueFindings = DialogueCorrectionStore.apply(
                        this@MainActivity, book.text, DialogueFindingsStore.load(this@MainActivity, book.text)
                    )'''
s = s.replace(anchor, anchor + '''
                    refreshTtsResumeKey(loadSaved = true)''', 1)
# A restored report should be reviewable immediately.
s = s.replace('''                    reviewDialoguesButton.isEnabled = true
                    teraManualPackButton.isEnabled = true''',
'''                    reviewDialoguesButton.isEnabled = dialogueFindings.isNotEmpty()
                    teraManualPackButton.isEnabled = true''', 1)

# Persist the completed analysis so users never need to run a long analysis again after app updates.
anchor = '''                    dialogueFindings = findings
                    reviewDialoguesButton.isEnabled = originalText.isNotBlank()'''
replacement = '''                    dialogueFindings = findings
                    DialogueFindingsStore.save(this@MainActivity, bookText, findings)
                    ttsResumeStorageKey = ""
                    refreshTtsResumeKey(loadSaved = true)
                    reviewDialoguesButton.isEnabled = originalText.isNotBlank()'''
assert anchor in s
s = s.replace(anchor, replacement, 1)

# Save manual corrections to the durable complete findings snapshot as well.
anchor = '''        dialogueFindings = dialogueFindings.toMutableList().also { it[index] = corrected }
        DialogueCorrectionStore.save(this, originalText, index, corrected)'''
replacement = '''        dialogueFindings = dialogueFindings.toMutableList().also { it[index] = corrected }
        DialogueCorrectionStore.save(this, originalText, index, corrected)
        DialogueFindingsStore.save(this, originalText, dialogueFindings)
        ttsResumeStorageKey = ""
        refreshTtsResumeKey(loadSaved = true)'''
assert anchor in s
s = s.replace(anchor, replacement, 1)

p.write_text(s, encoding="utf-8")
print("v40: persisted dialogue analysis and routed dialogue/narration to gender-matched TeraTTSv2 voices.")
