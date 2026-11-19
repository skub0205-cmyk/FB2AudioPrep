from pathlib import Path
base = Path("app/src/main/java/ru/fbaudioprep")
p = base / "TeraTtsV2PackImporter.kt"
p.write_text(r'''package ru.fbaudioprep
import android.content.Context
import android.net.Uri
import java.io.File
import java.io.FileOutputStream
import java.util.zip.ZipInputStream

object TeraTtsV2PackImporter {
    fun install(context: Context, uri: Uri): File {
        val root = File(context.filesDir, "voice-models").apply { mkdirs() }
        val staging = File(root, ".teratts-v2-importing")
        staging.deleteRecursively()
        staging.mkdirs()
        try {
            val input = context.contentResolver.openInputStream(uri) ?: error("Не удалось открыть ZIP модели")
            input.use { source -> ZipInputStream(source.buffered()).use { zip ->
                var expanded = 0L
                while (true) {
                    val entry = zip.nextEntry ?: break
                    val name = entry.name.replace('\\', '/')
                    check(!name.startsWith("/") && !name.split('/').contains("..")) { "Небезопасный путь в ZIP" }
                    val out = File(staging, name)
                    check(out.canonicalPath.startsWith(staging.canonicalPath + File.separator)) { "Недопустимый путь в ZIP" }
                    if (entry.isDirectory) out.mkdirs() else {
                        out.parentFile?.mkdirs()
                        FileOutputStream(out).use { target ->
                            val buffer = ByteArray(65536)
                            while (true) {
                                val count = zip.read(buffer)
                                if (count < 0) break
                                expanded += count
                                check(expanded <= 4L * 1024 * 1024 * 1024) { "Архив модели слишком большой" }
                                target.write(buffer, 0, count)
                            }
                        }
                    }
                    zip.closeEntry()
                }
            } }
            var sourceRoot = staging
            if (!File(sourceRoot, "models").isDirectory) {
                val dirs = staging.listFiles()?.filter { it.isDirectory }.orEmpty()
                if (dirs.size == 1 && File(dirs[0], "models").isDirectory) sourceRoot = dirs[0]
            }
            val required = listOf("models/text_encoder.onnx","models/duration_predictor.onnx",
                "models/sampler_distilled_cfg3_8step.onnx","models/vocoder.onnx",
                "styles/ru_f1/style_ttl.npy","styles/ru_f1/style_dp.npy","unicode_indexer.json")
            val missing = required.filterNot { File(sourceRoot, it).isFile }
            check(missing.isEmpty()) { "Неполный пакет TeraTTSv2: " + missing.joinToString() }
            val installed = File(root, "teratts-v2")
            val backup = File(root, ".teratts-v2-previous")
            backup.deleteRecursively()
            if (installed.exists()) check(installed.renameTo(backup)) { "Не удалось сохранить предыдущую модель" }
            if (!sourceRoot.renameTo(installed)) {
                if (backup.exists()) backup.renameTo(installed)
                error("Не удалось завершить установку модели")
            }
            backup.deleteRecursively()
            staging.deleteRecursively()
            return installed
        } catch (e: Throwable) {
            staging.deleteRecursively()
            throw e
        }
    }
}
''', encoding="utf-8")

p = base / "MainActivity.kt"
s = p.read_text(encoding="utf-8")
if "private val importTtsModelId = 107" not in s:
    s = s.replace("    private val exportTeraManualPackId = 106", """    private val exportTeraManualPackId = 106
    private val importTtsModelId = 107
    @Volatile private var ttsEngine: TeraTtsV2OnnxEngine? = null
    @Volatile private var ttsWorker: Thread? = null
    @Volatile private var ttsStopRequested = false
    private var selectedTtsVoice = "ru_f1"
    private lateinit var installTtsModelButton: Button
    private lateinit var playBookButton: Button
    private lateinit var stopBookButton: Button""")
anchor = "        root.addView(teraManualPackButton)\n\n        accentButton = Button(this).apply {"
insert = """        root.addView(teraManualPackButton)

        installTtsModelButton = Button(this).apply {
            text = "Установить модель озвучивания TeraTTSv2 (ZIP)"
            setOnClickListener {
                val intent = Intent(Intent.ACTION_OPEN_DOCUMENT).apply {
                    addCategory(Intent.CATEGORY_OPENABLE)
                    type = "application/zip"
                    putExtra(Intent.EXTRA_MIME_TYPES, arrayOf("application/zip", "application/octet-stream"))
                }
                startActivityForResult(intent, importTtsModelId)
            }
        }
        root.addView(installTtsModelButton)
        playBookButton = Button(this).apply {
            text = "▶ Озвучить книгу"
            isEnabled = false
            setOnClickListener { chooseAndPlayBook() }
        }
        root.addView(playBookButton)
        stopBookButton = Button(this).apply {
            text = "■ Остановить озвучивание"
            isEnabled = false
            setOnClickListener { stopBookPlayback() }
        }
        root.addView(stopBookButton)

        accentButton = Button(this).apply {"""
assert anchor in s
s = s.replace(anchor, insert, 1)
anchor = """            exportTeraManualPackId -> saveBytes(
                uri,
                TeraTtsManualPackExporter.encode(sourceName, loadCharacters(), dialogueFindings),
                "Карта персонажей сохранена. Это справочный ZIP, не импорт TeraTTS."
            )
        }"""
replace = """            exportTeraManualPackId -> saveBytes(
                uri,
                TeraTtsManualPackExporter.encode(sourceName, loadCharacters(), dialogueFindings),
                "Карта персонажей сохранена. Это справочный ZIP, не импорт TeraTTS."
            )
            importTtsModelId -> installTeraTtsV2Pack(uri)
        }"""
assert anchor in s
s = s.replace(anchor, replace, 1)
anchor = "    private fun load(uri: Uri) {"
methods = r'''    private fun installTeraTtsV2Pack(uri: Uri) {
        installTtsModelButton.isEnabled = false
        status.text = "Устанавливаю TeraTTSv2…"
        Thread({
            try {
                val directory = TeraTtsV2PackImporter.install(applicationContext, uri)
                val engine = TeraTtsV2OnnxEngine()
                val loaded = engine.load(directory)
                runOnUiThread {
                    ttsEngine?.close()
                    ttsEngine = engine
                    installTtsModelButton.isEnabled = true
                    playBookButton.isEnabled = originalText.isNotBlank()
                    status.text = loaded.message + "\nГолоса: " + loaded.voices.joinToString()
                }
            } catch (e: Throwable) {
                runOnUiThread {
                    installTtsModelButton.isEnabled = true
                    status.text = "Ошибка установки модели: " + (e.message ?: "неизвестно")
                }
            }
        }, "tts-model-install").start()
    }

    private fun chooseAndPlayBook() {
        if (originalText.isBlank()) return
        val engine = ttsEngine
        if (engine == null || !engine.status().ready) {
            Toast.makeText(this, "Сначала установите ZIP-пакет TeraTTSv2", Toast.LENGTH_LONG).show()
            return
        }
        val voices = engine.status().voices
        val labels = voices.map { id -> when (id) {
            "ru_f1" -> "Женский 1"; "ru_f2" -> "Женский 2"
            "ru_m1" -> "Мужской 1"; "ru_m5" -> "Мужской 5"; else -> id
        } }.toTypedArray()
        AlertDialog.Builder(this).setTitle("Голос диктора")
            .setSingleChoiceItems(labels, voices.indexOf(selectedTtsVoice).coerceAtLeast(0)) { dialog, which ->
                selectedTtsVoice = voices[which]
                dialog.dismiss()
                startBookPlayback()
            }.setNegativeButton("Отмена", null).show()
    }

    private fun startBookPlayback() {
        val engine = ttsEngine ?: return
        if (ttsWorker?.isAlive == true) return
        val paragraphs = processedText.ifBlank { originalText }
            .split(Regex("\\n\\s*\\n")).map { it.trim() }.filter { it.isNotBlank() }
        val chunks = paragraphs.flatMap { SpeechTextChunker.chunk(it, 180) }
        if (chunks.isEmpty()) return
        ttsStopRequested = false
        playBookButton.isEnabled = false
        stopBookButton.isEnabled = true
        val voice = selectedTtsVoice
        ttsWorker = Thread({
            try {
                chunks.forEachIndexed { index, chunk ->
                    if (ttsStopRequested) return@forEachIndexed
                    runOnUiThread { status.text = "Озвучивание: " + (index + 1) + " из " + chunks.size + "\nГолос: " + voice }
                    engine.synthesizeAndPlay(TeraTtsTextFormatter.russian(chunk), voice, seed = 1234L + index)
                }
                runOnUiThread { status.text = if (ttsStopRequested) "Озвучивание остановлено." else "Озвучивание книги завершено." }
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

    private fun stopBookPlayback() {
        ttsStopRequested = true
        ttsEngine?.cancelPlayback()
        stopBookButton.isEnabled = false
        status.text = "Останавливаю озвучивание…"
    }

'''
assert anchor in s
s = s.replace(anchor, methods + anchor, 1)
needle = "                    accentButton.isEnabled = true"
if "playBookButton.isEnabled = ttsEngine" not in s:
    s = s.replace(needle, needle + "\n                    playBookButton.isEnabled = ttsEngine?.status()?.ready == true", 1)
if "override fun onDestroy()" not in s:
    end = s.rfind("}")
    s = s[:end] + """
    override fun onDestroy() {
        ttsStopRequested = true
        ttsEngine?.cancelPlayback()
        val worker = ttsWorker
        if (worker != null && worker.isAlive) {
            try { worker.join(1000) } catch (_: InterruptedException) { Thread.currentThread().interrupt() }
        }
        ttsEngine?.close()
        ttsEngine = null
        super.onDestroy()
    }
""" + s[end:]
p.write_text(s, encoding="utf-8")
print("v38 TeraTTSv2 model import and audiobook playback wired.")
