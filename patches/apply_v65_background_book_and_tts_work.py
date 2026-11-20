from pathlib import Path

p = Path("app/src/main/java/ru/fbaudioprep/MainActivity.kt")
s = p.read_text(encoding="utf-8")

def replace_once(old, new, label):
    global s
    count = s.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one match, found {count}")
    s = s.replace(old, new, 1)

# Restore all potentially expensive book-derived data on the restore worker.
replace_once(
'''                val restoredRecord = BookLibraryStore.list(applicationContext)
                    .firstOrNull { it.id == restoredId }
                runOnUiThread {
''',
'''                val restoredRecord = BookLibraryStore.list(applicationContext)
                    .firstOrNull { it.id == restoredId }
                val restoredBookKey = MessageDigest.getInstance("SHA-256")
                    .digest(saved.text.toByteArray(Charsets.UTF_8))
                    .joinToString("") { "%02x".format(it) }
                val restoredFindings = DialogueCorrectionStore.apply(
                    applicationContext, saved.text, DialogueFindingsStore.load(applicationContext, saved.text)
                )
                runOnUiThread {
''',
'move restore digest and dialogue cache off UI')

replace_once(
'''                    dialogueFindings = DialogueCorrectionStore.apply(
                        this@MainActivity, saved.text, DialogueFindingsStore.load(this@MainActivity, saved.text)
                    )
''',
'''                    dialogueFindings = restoredFindings
''',
'use preloaded restore findings')

replace_once(
'''                    ttsBookKey = MessageDigest.getInstance("SHA-256")
                        .digest(saved.text.toByteArray(Charsets.UTF_8))
                        .joinToString("") { "%02x".format(it) }
                    ttsResumeStorageKey = ""
                    ttsResumeIndex = 0
                    runCatching { refreshTtsResumeKey(loadSaved = true) }
''',
'''                    ttsBookKey = restoredBookKey
                    ttsResumeStorageKey = ""
                    ttsResumeIndex = 0
''',
'remove full speech queue build from restore')

# Library selection already runs on a worker: keep all book hashing, saved findings and index writes there.
replace_once(
'''                    val text = BookLibraryStore.text(applicationContext, selected.id)
                    val original = BookLibraryStore.original(applicationContext, selected.id)
                    runOnUiThread {
''',
'''                    val text = BookLibraryStore.text(applicationContext, selected.id)
                    val original = BookLibraryStore.original(applicationContext, selected.id)
                    val bookKey = MessageDigest.getInstance("SHA-256")
                        .digest(text.toByteArray(Charsets.UTF_8))
                        .joinToString("") { "%02x".format(it) }
                    val findings = DialogueCorrectionStore.apply(
                        applicationContext, text, DialogueFindingsStore.load(applicationContext, text)
                    )
                    BookLibraryStore.markOpened(applicationContext, selected.id)
                    runOnUiThread {
''',
'move library bookkeeping off UI')

replace_once(
'''                        readerStartOffset = BookLibraryStore.readingPosition(applicationContext, selected.id)
''',
'''                        readerStartOffset = selected.readingPosition
''',
'use already loaded library position')

replace_once(
'''                        ttsBookKey = MessageDigest.getInstance("SHA-256")
                            .digest(text.toByteArray(Charsets.UTF_8))
                            .joinToString("") { "%02x".format(it) }
                        dialogueFindings = DialogueCorrectionStore.apply(
                            this@MainActivity, text, DialogueFindingsStore.load(this@MainActivity, text)
                        )
                        BookLibraryStore.markOpened(applicationContext, selected.id)
''',
'''                        ttsBookKey = bookKey
                        dialogueFindings = findings
''',
'use worker-computed library values')

replace_once(
'''                        refreshTtsResumeKey(loadSaved = true)
''',
'''                        ttsResumeStorageKey = ""
                        ttsResumeIndex = 0
''',
'invalidate resume key on library open')

# Import: persist session and calculate book-derived values before posting to UI.
replace_once(
'''                require(book.text.isNotBlank()) {
                    "Файл прочитан, но текст книги не найден. Проверьте, что это FB2/TXT."
                }

                runOnUiThread {
''',
'''                require(book.text.isNotBlank()) {
                    "Файл прочитан, но текст книги не найден. Проверьте, что это FB2/TXT."
                }
                BookLibraryStore.markOpened(applicationContext, libraryRecord.id)
                BookSessionStore.save(applicationContext, book.sourceName, book.text, book.isFb2, book.originalBytes)
                val importedBookKey = MessageDigest.getInstance("SHA-256")
                    .digest(book.text.toByteArray(Charsets.UTF_8))
                    .joinToString("") { "%02x".format(it) }
                val importedFindings = DialogueCorrectionStore.apply(
                    applicationContext, book.text, DialogueFindingsStore.load(applicationContext, book.text)
                )

                runOnUiThread {
''',
'move import persistence and book-derived work to worker')

replace_once(
'''                    BookLibraryStore.markOpened(applicationContext, libraryRecord.id)
                    originalText = book.text
                    try {
                        BookSessionStore.save(applicationContext, book.sourceName, book.text, book.isFb2, book.originalBytes)
                    } catch (saveError: Throwable) {
                        android.util.Log.e("BookSessionStore", "Could not persist imported book", saveError)
                    }
                    ttsBookKey = MessageDigest.getInstance("SHA-256")
                        .digest(book.text.toByteArray(Charsets.UTF_8))
                        .joinToString("") { "%02x".format(it) }
                    dialogueFindings = DialogueCorrectionStore.apply(
                        this@MainActivity, book.text, DialogueFindingsStore.load(this@MainActivity, book.text)
                    )
                    refreshTtsResumeKey(loadSaved = true)
                    ttsResumeStorageKey = ""
                    ttsResumeIndex = 0
''',
'''                    originalText = book.text
                    ttsBookKey = importedBookKey
                    dialogueFindings = importedFindings
                    ttsResumeStorageKey = ""
                    ttsResumeIndex = 0
''',
'remove import disk writes and queue build from UI')

# The queue can be very large and depends on character profiles, dialogue findings and voice routing.
# Build it only on the playback worker, never during activity restoration or a UI callback.
start = s.index("    private fun startBookPlayback() {")
end = s.index("\n    private fun stopBookPlayback()", start)
new_func = '''    private fun startBookPlayback() {
        val engine = ttsEngine ?: return
        if (ttsWorker?.isAlive == true) return
        val settings = getSharedPreferences("fb2audioprep_tts_settings", MODE_PRIVATE)
        val durationScale = settings.getFloat("duration_scale", 1f).coerceIn(0.75f, 1.35f)
        val gain = settings.getFloat("gain", 1f).coerceIn(0.2f, 1f)
        val pauseMs = settings.getInt("pause_ms", 100).coerceIn(0, 800)
        ttsStopRequested = false
        playBookButton.isEnabled = false
        stopBookButton.isEnabled = true
        status.text = "Подготавливаю очередь озвучивания в фоне…"

        ttsWorker = Thread({
            var completed = false
            try {
                val queue = buildTtsSpeechQueue()
                if (queue.isEmpty()) {
                    runOnUiThread {
                        status.text = "Нет текста для озвучивания."
                        Toast.makeText(this, "Нет текста для озвучивания", Toast.LENGTH_SHORT).show()
                    }
                    return@Thread
                }
                val fingerprint = MessageDigest.getInstance("SHA-256")
                    .digest(queue.joinToString("\\n") { it.voiceId + "|" + it.text }.toByteArray(Charsets.UTF_8))
                    .joinToString("") { "%02x".format(it) }
                val resumeKey = "resume_" + ttsBookKey + "_" + fingerprint
                ttsResumeStorageKey = resumeKey
                val startAt = getSharedPreferences("audiobook_playback", MODE_PRIVATE)
                    .getInt(resumeKey, 0).coerceIn(0, queue.size)
                ttsResumeIndex = startAt
                runOnUiThread {
                    playBookButton.text = if (startAt > 0) "▶ Продолжить озвучивание" else "▶ Озвучить книгу"
                    status.text = "Очередь готова: ${queue.size} фрагментов. Начинаю озвучивание…"
                }

                val pieces = queue.iterator()
                var skipped = 0
                while (skipped < startAt && pieces.hasNext()) {
                    pieces.next()
                    skipped++
                }
                val prebuffer = java.util.ArrayDeque<TeraTtsSpeechPiece>(3)
                fun fillPrebuffer() {
                    while (prebuffer.size < 3 && pieces.hasNext()) prebuffer.addLast(pieces.next())
                }
                fillPrebuffer()
                var played = startAt
                while (prebuffer.isNotEmpty() && !ttsStopRequested) {
                    val next = prebuffer.removeFirst()
                    fillPrebuffer()
                    runOnUiThread {
                        status.text = "Озвучивание: фрагмент " + (played + 1) + " из " + queue.size +
                            "\\nГолос: " + next.voiceId + "\\nРежим: " + next.kind
                    }
                    engine.synthesizeAndPlay(
                        TeraTtsTextFormatter.russian(next.text),
                        next.voiceId,
                        durationScale = durationScale,
                        seed = 1234L + played,
                        gain = gain
                    )
                    if (ttsStopRequested) break
                    played++
                    ttsResumeIndex = played
                    getSharedPreferences("audiobook_playback", MODE_PRIVATE).edit()
                        .putInt(resumeKey, ttsResumeIndex).apply()
                    if (pauseMs > 0 && prebuffer.isNotEmpty() && !ttsStopRequested) {
                        try { Thread.sleep(pauseMs.toLong()) } catch (_: InterruptedException) {
                            Thread.currentThread().interrupt()
                            ttsStopRequested = true
                        }
                    }
                }
                completed = !ttsStopRequested && prebuffer.isEmpty() && !pieces.hasNext()
                if (completed) {
                    ttsResumeIndex = 0
                    getSharedPreferences("audiobook_playback", MODE_PRIVATE).edit()
                        .putInt(resumeKey, 0).apply()
                }
                runOnUiThread {
                    status.text = when {
                        completed -> "Озвучивание книги завершено."
                        ttsStopRequested -> "Озвучивание остановлено. Можно продолжить с этого места."
                        else -> "Озвучивание приостановлено."
                    }
                    playBookButton.text = if (ttsResumeIndex > 0)
                        "▶ Продолжить озвучивание" else "▶ Озвучить книгу"
                }
            } catch (e: Throwable) {
                runOnUiThread {
                    status.text = "Ошибка озвучивания: " + (e.message ?: "неизвестно")
                }
            } finally {
                runOnUiThread {
                    playBookButton.isEnabled = originalText.isNotBlank()
                    stopBookButton.isEnabled = false
                }
            }
        }, "teratts-v2-playback").also { it.start() }
    }
'''
s = s[:start] + new_func + s[end:]

# Do not rebuild a full audiobook queue when dialogue analysis or manual corrections finish.
s = s.replace('''                    refreshTtsResumeKey(loadSaved = true)
''', '''                    ttsResumeStorageKey = ""
''')
s = s.replace('''        refreshTtsResumeKey(loadSaved = true)
''', '''        ttsResumeStorageKey = ""
''')

p.write_text(s, encoding="utf-8")
print("v65: move restore/import bookkeeping and audiobook queue generation off the UI thread.")
