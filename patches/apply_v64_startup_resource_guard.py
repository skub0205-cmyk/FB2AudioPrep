from pathlib import Path

p = Path("app/src/main/java/ru/fbaudioprep/MainActivity.kt")
s = p.read_text(encoding="utf-8")

def replace_once(old: str, new: str, label: str):
    global s
    count = s.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match, found {count}")
    s = s.replace(old, new, 1)

replace_once(
'''    @Volatile private var ttsModelDownloader: TeraTtsV2ModelDownloader? = null
''',
'''    @Volatile private var ttsModelDownloader: TeraTtsV2ModelDownloader? = null
    @Volatile private var ttsModelRestoreInProgress = false
''',
'add lazy model restore state')

replace_once(
'''        restoreLastOpenedBook()
        restoreInstalledTtsModel()
        AudiotomeTheme.apply(this)
''',
'''        // Keep startup lightweight: restoring a multi-hundred-megabyte ONNX model
        // alongside a large FB2 can exhaust memory and make Android report an ANR.
        // The installed model is restored only when the user starts audiobook playback.
        restoreLastOpenedBook()
        AudiotomeTheme.apply(this)
''',
'defer ONNX model restore at startup')

replace_once(
'''    private fun restoreInstalledTtsModel() {
        val directory = File(filesDir, "voice-models/teratts-v2")
        if (!directory.isDirectory) return
        installTtsModelButton.isEnabled = false
        status.text = "Обнаружена установленная TeraTTSv2. Загружаю локальную модель…"
        Thread({
''',
'''    private fun restoreInstalledTtsModel(onLoaded: (() -> Unit)? = null) {
        val directory = File(filesDir, "voice-models/teratts-v2")
        if (!directory.isDirectory || ttsModelRestoreInProgress) return
        ttsModelRestoreInProgress = true
        installTtsModelButton.isEnabled = false
        status.text = "Обнаружена установленная TeraTTSv2. Загружаю локальную модель по запросу…"
        Thread({
''',
'make model restore explicit and guarded')

replace_once(
'''                    ttsEngine?.close()
                    ttsEngine = engine
                    installTtsModelButton.isEnabled = true
                    playBookButton.isEnabled = originalText.isNotBlank()
                    status.text = loaded.message + "\\nМодель восстановлена из памяти устройства.\\nГолоса: " + loaded.voices.joinToString()
''',
'''                    ttsEngine?.close()
                    ttsEngine = engine
                    ttsModelRestoreInProgress = false
                    installTtsModelButton.isEnabled = true
                    playBookButton.isEnabled = originalText.isNotBlank()
                    status.text = loaded.message + "\\nМодель восстановлена из памяти устройства.\\nГолоса: " + loaded.voices.joinToString()
                    onLoaded?.invoke()
''',
'mode restore success callback')

replace_once(
'''                    installTtsModelButton.isEnabled = true
                    status.text = "Сохранённая модель найдена, но не загрузилась: " + (e.message ?: "ошибка")
''',
'''                    ttsModelRestoreInProgress = false
                    installTtsModelButton.isEnabled = true
                    playBookButton.isEnabled = originalText.isNotBlank()
                    status.text = "Сохранённая модель найдена, но не загрузилась: " + (e.message ?: "ошибка")
''',
'mode restore failure cleanup')

replace_once(
'''    private fun chooseAndPlayBook() {
        if (originalText.isBlank()) return
        val engine = ttsEngine
        if (engine == null || !engine.status().ready) {
            Toast.makeText(this, "Сначала установите ZIP-пакет TeraTTSv2", Toast.LENGTH_LONG).show()
            return
        }
''',
'''    private fun chooseAndPlayBook() {
        if (originalText.isBlank()) return
        val engine = ttsEngine
        if (engine == null || !engine.status().ready) {
            val installedDirectory = File(filesDir, "voice-models/teratts-v2")
            if (installedDirectory.isDirectory) {
                if (!ttsModelRestoreInProgress) {
                    playBookButton.isEnabled = false
                    restoreInstalledTtsModel { chooseAndPlayBook() }
                }
                return
            }
            Toast.makeText(this, "Сначала установите модель TeraTTSv2", Toast.LENGTH_LONG).show()
            return
        }
''',
'lazy-load model from playback action')

replace_once(
'''                    currentLibraryBookId = restoredRecord?.id
                    readerStartOffset = restoredRecord?.let {
                        BookLibraryStore.readingPosition(applicationContext, it.id)
                    } ?: 0
''',
'''                    currentLibraryBookId = restoredRecord?.id
                    readerStartOffset = restoredRecord?.readingPosition ?: 0
''',
'use restored record position without extra index read')

replace_once(
'''                val restoredRecord = if (!saved.isFb2 || saved.originalBytes != null) {
                    runCatching {
                        BookLibraryStore.add(
                            applicationContext, saved.name, saved.text, saved.isFb2,
                            saved.originalBytes ?: saved.text.toByteArray(Charsets.UTF_8)
                        )
                    }.getOrNull()
                } else null
''',
'''                val restoredBytes = saved.originalBytes ?: saved.text.toByteArray(Charsets.UTF_8)
                val restoredId = MessageDigest.getInstance("SHA-256")
                    .digest(restoredBytes).joinToString("") { "%02x".format(it) }
                // Do not call BookLibraryStore.add() here: it reparses the entire FB2,
                // rewrites cover/TOC files and the library index on every cold start.
                val restoredRecord = BookLibraryStore.list(applicationContext)
                    .firstOrNull { it.id == restoredId }
''',
'avoid reparsing FB2 during every cold start')

s = s.replace('playBookButton.isEnabled = originalText.isNotBlank() &&\n                        (ttsEngine?.status()?.ready == true)', 'playBookButton.isEnabled = originalText.isNotBlank()')
s = s.replace('playBookButton.isEnabled = ttsEngine?.status()?.ready == true', 'playBookButton.isEnabled = originalText.isNotBlank()')

p.write_text(s, encoding="utf-8")
print("v64: defer ONNX restore until playback; avoid duplicate FB2 parsing and index writes during startup.")
