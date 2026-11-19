from pathlib import Path

base = Path("app/src/main/java/ru/fbaudioprep")
p = base / "TeraTtsV2PackImporter.kt"
s = p.read_text(encoding="utf-8")
s = s.replace("""            backup.deleteRecursively()
            staging.deleteRecursively()
            return installed""", """            // Keep the previous model until ONNX sessions load successfully.
            staging.deleteRecursively()
            return installed""")
if "fun commitInstall()" not in s:
    s = s.replace("""    fun install(context: Context, uri: Uri): File {""", """    fun commitInstall(context: Context) {
        File(context.filesDir, "voice-models/.teratts-v2-previous").deleteRecursively()
    }

    fun rollbackInstall(context: Context) {
        val root = File(context.filesDir, "voice-models")
        val installed = File(root, "teratts-v2")
        val backup = File(root, ".teratts-v2-previous")
        installed.deleteRecursively()
        if (backup.exists()) backup.renameTo(installed)
    }

    fun install(context: Context, uri: Uri): File {""")
p.write_text(s, encoding="utf-8")

p = base / "TeraTtsV2OnnxEngine.kt"
s = p.read_text(encoding="utf-8")
old = """                    val written = output.write(pcm, 0, pcm.size, AudioTrack.WRITE_BLOCKING)
                    check(written >= 0) { "Ошибка AudioTrack: " + written }
                    emitted += count"""
new = """                    var offset = 0
                    while (offset < pcm.size && !cancelled.get()) {
                        val written = output.write(pcm, offset, pcm.size - offset, AudioTrack.WRITE_BLOCKING)
                        check(written > 0) { "Ошибка AudioTrack: " + written }
                        offset += written
                        emitted += written
                    }"""
assert old in s, "AudioTrack write anchor missing"
s = s.replace(old, new, 1)
old = """            if (cancelled.get()) {
                output.pause()
                output.flush()
            }
            try { if (output.playState == AudioTrack.PLAYSTATE_PLAYING) output.stop() } catch (_: Throwable) {}"""
new = """            // WRITE_BLOCKING only confirms that PCM entered the device buffer.
            // Wait for the playback head to consume it before releasing AudioTrack,
            // otherwise the last syllables of every short chunk can be clipped.
            while (!cancelled.get() &&
                java.lang.Integer.toUnsignedLong(output.playbackHeadPosition) < emitted.toLong()) {
                try { Thread.sleep(20) } catch (_: InterruptedException) {
                    Thread.currentThread().interrupt()
                    cancelled.set(true)
                }
            }
            if (cancelled.get()) {
                output.pause()
                output.flush()
            }
            try { if (output.playState == AudioTrack.PLAYSTATE_PLAYING) output.stop() } catch (_: Throwable) {}"""
assert old in s, "AudioTrack drain anchor missing"
s = s.replace(old, new, 1)
p.write_text(s, encoding="utf-8")

p = base / "MainActivity.kt"
s = p.read_text(encoding="utf-8")
if "private var ttsResumeIndex = 0" not in s:
    s = s.replace("""    private var selectedTtsVoice = "ru_f1"
    private lateinit var installTtsModelButton""", """    private var selectedTtsVoice = "ru_f1"
    private var ttsResumeIndex = 0
    private var ttsBookKey = ""
    private lateinit var installTtsModelButton""")

# Restore already-installed models after app updates/restarts, without downloading again.
anchor = "        setContentView(AudiotomeHomeLayout.compose(this, root))"
assert anchor in s
if "restoreInstalledTtsModel()" not in s:
    s = s.replace(anchor, anchor + "\n        restoreInstalledTtsModel()", 1)

anchor = "    private fun installTeraTtsV2Pack(uri: Uri) {"
restore = r'''    private fun restoreInstalledTtsModel() {
        val directory = File(filesDir, "voice-models/teratts-v2")
        if (!directory.isDirectory) return
        installTtsModelButton.isEnabled = false
        status.text = "Обнаружена установленная TeraTTSv2. Загружаю локальную модель…"
        Thread({
            var engine: TeraTtsV2OnnxEngine? = null
            try {
                engine = TeraTtsV2OnnxEngine()
                val loaded = engine.load(directory)
                runOnUiThread {
                    ttsEngine?.close()
                    ttsEngine = engine
                    installTtsModelButton.isEnabled = true
                    playBookButton.isEnabled = originalText.isNotBlank()
                    status.text = loaded.message + "\nМодель восстановлена из памяти устройства.\nГолоса: " + loaded.voices.joinToString()
                }
            } catch (e: Throwable) {
                try { engine?.close() } catch (_: Throwable) {}
                runOnUiThread {
                    installTtsModelButton.isEnabled = true
                    status.text = "Сохранённая модель найдена, но не загрузилась: " + (e.message ?: "ошибка")
                }
            }
        }, "tts-model-restore").start()
    }

'''
if "private fun restoreInstalledTtsModel()" not in s:
    s = s.replace(anchor, restore + anchor, 1)

# Model installation becomes transactional: keep old package until ONNX loads.
old = """                val loaded = engine.load(directory)
                runOnUiThread {"""
new = """                val loaded = engine.load(directory)
                TeraTtsV2PackImporter.commitInstall(applicationContext)
                runOnUiThread {"""
assert old in s
s = s.replace(old, new, 1)
old = """            } catch (e: Throwable) {
                runOnUiThread {
                    installTtsModelButton.isEnabled = true
                    status.text = "Ошибка установки модели: " + (e.message ?: "неизвестно")"""
new = """            } catch (e: Throwable) {
                TeraTtsV2PackImporter.rollbackInstall(applicationContext)
                runOnUiThread {
                    installTtsModelButton.isEnabled = true
                    status.text = "Ошибка установки модели: " + (e.message ?: "неизвестно")"""
assert old in s
s = s.replace(old, new, 1)

# Keep the playback checkpoint per book, so Stop / app restart can resume.
old = """                    sourceName = book.sourceName
                    originalText = book.text"""
new = """                    sourceName = book.sourceName
                    originalText = book.text
                    ttsBookKey = MessageDigest.getInstance("SHA-256")
                        .digest(book.text.toByteArray(Charsets.UTF_8))
                        .joinToString("") { "%02x".format(it) }
                    ttsResumeIndex = getSharedPreferences("audiobook_playback", MODE_PRIVATE)
                        .getInt("resume_" + ttsBookKey, 0)"""
assert old in s
s = s.replace(old, new, 1)
old = """                    playBookButton.isEnabled = ttsEngine?.status()?.ready == true
                    dialogueButton.isEnabled = true"""
new = """                    playBookButton.isEnabled = ttsEngine?.status()?.ready == true
                    playBookButton.text = if (ttsResumeIndex > 0) "▶ Продолжить озвучивание" else "▶ Озвучить книгу"
                    dialogueButton.isEnabled = true"""
assert old in s
s = s.replace(old, new, 1)

# Replace playback loop with resumable chunk queue and persistent progress.
start = s.index("    private fun startBookPlayback() {")
end = s.index("    private fun stopBookPlayback() {", start)
replacement = r'''    private fun startBookPlayback() {
        val engine = ttsEngine ?: return
        if (ttsWorker?.isAlive == true) return
        val paragraphs = processedText.ifBlank { originalText }
            .split(Regex("\\n\\s*\\n")).map { it.trim() }.filter { it.isNotBlank() }
        val chunks = paragraphs.flatMap { SpeechTextChunker.chunk(it, 180) }
        if (chunks.isEmpty()) return
        val startAt = ttsResumeIndex.coerceIn(0, chunks.size)
        ttsStopRequested = false
        playBookButton.isEnabled = false
        stopBookButton.isEnabled = true
        val voice = selectedTtsVoice
        ttsWorker = Thread({
            var completed = false
            try {
                for (index in startAt until chunks.size) {
                    if (ttsStopRequested) break
                    runOnUiThread {
                        status.text = "Озвучивание: " + (index + 1) + " из " + chunks.size +
                            "\nГолос: " + voice
                    }
                    engine.synthesizeAndPlay(TeraTtsTextFormatter.russian(chunks[index]), voice, seed = 1234L + index)
                    if (ttsStopRequested) break
                    ttsResumeIndex = index + 1
                    getSharedPreferences("audiobook_playback", MODE_PRIVATE).edit()
                        .putInt("resume_" + ttsBookKey, ttsResumeIndex).apply()
                }
                completed = !ttsStopRequested && ttsResumeIndex >= chunks.size
                if (completed) {
                    ttsResumeIndex = 0
                    getSharedPreferences("audiobook_playback", MODE_PRIVATE).edit()
                        .putInt("resume_" + ttsBookKey, 0).apply()
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
s = s[:start] + replacement + s[end:]
p.write_text(s, encoding="utf-8")
print("v39: restore local model, transactional install, lossless AudioTrack drain, resumable playback.")
