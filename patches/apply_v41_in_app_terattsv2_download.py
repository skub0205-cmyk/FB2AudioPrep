from pathlib import Path

root = Path("app/src/main/java/ru/fbaudioprep")
(root / "TeraTtsV2ModelDownloader.kt").write_text("package ru.fbaudioprep\n\nimport android.content.Context\nimport android.os.StatFs\nimport java.io.File\nimport java.io.FileOutputStream\nimport java.net.HttpURLConnection\nimport java.net.URL\nimport java.util.concurrent.atomic.AtomicBoolean\n\n/** Downloads a pinned TeraTTSv2 ONNX package into private storage; partial files resume via HTTP Range. */\nclass TeraTtsV2ModelDownloader {\n    data class Progress(val fileIndex: Int, val fileCount: Int, val fileName: String, val filePercent: Int, val completedFiles: Int)\n    private val cancelled = AtomicBoolean(false)\n    fun cancel() { cancelled.set(true) }\n\n    fun downloadAndInstall(context: Context, onProgress: (Progress) -> Unit): File {\n        cancelled.set(false)\n        val root = File(context.filesDir, \"voice-models\").apply { mkdirs() }\n        val staging = File(root, \".teratts-v2-downloading\").apply { mkdirs() }\n        val files = modelFiles()\n        val already = staging.walkTopDown().filter { it.isFile }.sumOf { it.length() }\n        val free = StatFs(context.filesDir.absolutePath).availableBytes\n        val remaining = (ESTIMATED_TOTAL_BYTES - already).coerceAtLeast(0L)\n        check(free >= remaining + 24L * 1024 * 1024) {\n            \"Недостаточно свободного места. Нужно примерно ещё \" + ((remaining + 24L * 1024 * 1024) / (1024 * 1024)) + \" МБ.\"\n        }\n        var completed = 0\n        files.forEachIndexed { index, relative ->\n            check(!cancelled.get()) { \"Загрузка отменена\" }\n            val target = File(staging, relative)\n            target.parentFile?.mkdirs()\n            if (target.isFile && target.length() > minimumSize(relative)) {\n                completed++\n                onProgress(Progress(index + 1, files.size, relative, 100, completed))\n                return@forEachIndexed\n            }\n            val part = File(target.parentFile, target.name + \".part\")\n            downloadOne(relative, part) { percent ->\n                onProgress(Progress(index + 1, files.size, relative, percent, completed))\n            }\n            check(!cancelled.get()) { \"Загрузка отменена\" }\n            check(part.length() > minimumSize(relative)) { \"Файл модели повреждён или неполный: $relative\" }\n            if (target.exists()) target.delete()\n            check(part.renameTo(target)) { \"Не удалось сохранить файл модели: $relative\" }\n            completed++\n            onProgress(Progress(index + 1, files.size, relative, 100, completed))\n        }\n        validate(staging)\n        val installed = File(root, \"teratts-v2\")\n        val backup = File(root, \".teratts-v2-previous\")\n        backup.deleteRecursively()\n        if (installed.exists()) check(installed.renameTo(backup)) { \"Не удалось сохранить ранее установленную модель\" }\n        if (!staging.renameTo(installed)) {\n            if (backup.exists()) backup.renameTo(installed)\n            error(\"Не удалось завершить установку модели\")\n        }\n        File(root, \".teratts-v2-install-pending\").writeText(\"1\")\n        return installed\n    }\n\n    private fun downloadOne(relative: String, part: File, progress: (Int) -> Unit) {\n        var offset = if (part.isFile) part.length() else 0L\n        val connection = (URL(\"$BASE_URL/$REVISION/$relative?download=true\").openConnection() as HttpURLConnection).apply {\n            connectTimeout = 20000\n            readTimeout = 45000\n            instanceFollowRedirects = true\n            requestMethod = \"GET\"\n            setRequestProperty(\"User-Agent\", \"FB2AudioPrep-Android/2.0\")\n            if (offset > 0L) setRequestProperty(\"Range\", \"bytes=$offset-\")\n        }\n        try {\n            val code = connection.responseCode\n            check(code == HttpURLConnection.HTTP_OK || code == HttpURLConnection.HTTP_PARTIAL) {\n                \"Сервер модели вернул HTTP $code для $relative\"\n            }\n            if (offset > 0L && code == HttpURLConnection.HTTP_OK) offset = 0L\n            val total = if (code == HttpURLConnection.HTTP_PARTIAL) {\n                connection.getHeaderField(\"Content-Range\")?.substringAfterLast('/')?.toLongOrNull()\n            } else connection.contentLengthLong.takeIf { it > 0L }\n            connection.inputStream.use { input ->\n                FileOutputStream(part, offset > 0L && code == HttpURLConnection.HTTP_PARTIAL).use { output ->\n                    val buffer = ByteArray(128 * 1024)\n                    var current = offset\n                    var last = -1\n                    while (true) {\n                        check(!cancelled.get()) { \"Загрузка отменена\" }\n                        val count = input.read(buffer)\n                        if (count < 0) break\n                        if (count == 0) continue\n                        output.write(buffer, 0, count)\n                        current += count\n                        val percent = if (total != null && total > 0L) ((current * 100L) / total).toInt().coerceIn(0, 100) else -1\n                        if (percent != last) { last = percent; progress(percent) }\n                    }\n                    output.fd.sync()\n                }\n            }\n        } finally { connection.disconnect() }\n    }\n\n    private fun validate(dir: File) {\n        val required = listOf(\n            \"models/text_encoder.onnx\", \"models/duration_predictor.onnx\",\n            \"models/sampler_distilled_cfg3_8step.onnx\", \"models/vocoder.onnx\",\n            \"unicode_indexer.json\", \"ruaccent/dictionary/accents.json.gz\",\n            \"ruaccent/dictionary/yo_words.json.gz\", \"LICENSE\", \"LICENSE-OPENRAIL\", \"RUACCENT_NOTICE.txt\"\n        ) + VOICES.flatMap { listOf(\"styles/$it/style_ttl.npy\", \"styles/$it/style_dp.npy\") }\n        val missing = required.filterNot { File(dir, it).isFile && File(dir, it).length() > minimumSize(it) }\n        check(missing.isEmpty()) { \"Пакет модели неполный: \" + missing.joinToString() }\n    }\n\n    private fun minimumSize(path: String): Long = when {\n        path.endsWith(\".onnx\") -> 100_000L\n        path == \"unicode_indexer.json\" -> 10_000L\n        path.endsWith(\".npy\") -> 100L\n        path.endsWith(\".gz\") -> 100_000L\n        else -> 100L\n    }\n\n    private fun modelFiles(): List<String> {\n        val result = mutableListOf(\n            \"models/text_encoder.onnx\", \"models/duration_predictor.onnx\",\n            \"models/sampler_distilled_cfg3_8step.onnx\", \"models/vocoder.onnx\",\n            \"unicode_indexer.json\", \"ruaccent/dictionary/accents.json.gz\",\n            \"ruaccent/dictionary/yo_words.json.gz\", \"LICENSE\", \"LICENSE-OPENRAIL\", \"RUACCENT_NOTICE.txt\"\n        )\n        VOICES.forEach { result += \"styles/$it/style_ttl.npy\"; result += \"styles/$it/style_dp.npy\" }\n        return result\n    }\n\n    companion object {\n        private const val BASE_URL = \"https://huggingface.co/TeraSpace/TeraTTSv2/resolve\"\n        private const val REVISION = \"4c3bf2eb99c148cb657af10bd3bf717befb714c8\"\n        private const val ESTIMATED_TOTAL_BYTES = 430L * 1024 * 1024\n        private val VOICES = listOf(\"ru_f1\", \"ru_f2\", \"ru_m1\", \"ru_m5\")\n    }\n}\n", encoding="utf-8")
# Reject truncated files using the upstream release sizes and Content-Length/Range metadata.
_downloader = root / "TeraTtsV2ModelDownloader.kt"
_ds = _downloader.read_text(encoding="utf-8")
_old = '''            val total = if (code == HttpURLConnection.HTTP_PARTIAL) {
                connection.getHeaderField("Content-Range")?.substringAfterLast('/')?.toLongOrNull()
            } else connection.contentLengthLong.takeIf { it > 0L }
            connection.inputStream.use { input ->
'''
_new = '''            val total = if (code == HttpURLConnection.HTTP_PARTIAL) {
                connection.getHeaderField("Content-Range")?.substringAfterLast('/')?.toLongOrNull()
            } else connection.contentLengthLong.takeIf { it > 0L }
            connection.inputStream.use { input ->
'''
assert _old in _ds
# Check the final byte count after the response stream ends.
_old_end = '''                        if (percent != last) { last = percent; progress(percent) }
                    }
                    output.fd.sync()
'''
_new_end = '''                        if (percent != last) { last = percent; progress(percent) }
                    }
                    if (total != null) check(current >= total) {
                        "Файл загрузился не полностью: $relative (" + current + " из " + total + " байт)"
                    }
                    output.fd.sync()
'''
assert _old_end in _ds
_ds = _ds.replace(_old_end, _new_end, 1)
_old_min = '''    private fun minimumSize(path: String): Long = when {
        path.endsWith(".onnx") -> 100_000L
        path == "unicode_indexer.json" -> 10_000L
        path.endsWith(".npy") -> 100L
        path.endsWith(".gz") -> 100_000L
        else -> 100L
    }
'''
_new_min = '''    private fun minimumSize(path: String): Long = when {
        path.endsWith("sampler_distilled_cfg3_8step.onnx") -> 200L * 1024 * 1024
        path.endsWith("vocoder.onnx") -> 80L * 1024 * 1024
        path.endsWith("text_encoder.onnx") -> 20L * 1024 * 1024
        path.endsWith("duration_predictor.onnx") -> 1L * 1024 * 1024
        path.endsWith("accents.json.gz") -> 15L * 1024 * 1024
        path.endsWith("yo_words.json.gz") -> 400L * 1024
        path == "unicode_indexer.json" -> 200L * 1024
        path.endsWith("style_ttl.npy") -> 30L * 1024
        path.endsWith("style_dp.npy") -> 500L
        else -> 100L
    }
'''
assert _old_min in _ds
_ds = _ds.replace(_old_min, _new_min, 1)
_downloader.write_text(_ds, encoding="utf-8")

p = root / "MainActivity.kt"
s = p.read_text(encoding="utf-8")

if "private lateinit var downloadTtsModelButton: Button" not in s:
    s = s.replace(
        "    private lateinit var installTtsModelButton: Button",
        """    private lateinit var installTtsModelButton: Button
    private lateinit var downloadTtsModelButton: Button
    private lateinit var cancelTtsDownloadButton: Button
    @Volatile private var ttsModelDownloader: TeraTtsV2ModelDownloader? = null"""
    )

anchor = "        installTtsModelButton = Button(this).apply {"
insert = """        downloadTtsModelButton = Button(this).apply {
            text = "⬇ Скачать модель озвучивания TeraTTSv2 (~430 МБ)"
            setOnClickListener { downloadTeraTtsV2Model() }
        }
        root.addView(downloadTtsModelButton)
        cancelTtsDownloadButton = Button(this).apply {
            text = "Отменить загрузку модели"
            visibility = android.view.View.GONE
            setOnClickListener {
                ttsModelDownloader?.cancel()
                status.text = "Отменяю загрузку… Уже скачанные части сохранятся для продолжения."
                isEnabled = false
            }
        }
        root.addView(cancelTtsDownloadButton)

"""
if "Скачать модель озвучивания TeraTTSv2" not in s:
    assert anchor in s
    s = s.replace(anchor, insert + anchor, 1)

anchor = "    private fun restoreInstalledTtsModel() {"
method = r'''    private fun downloadTeraTtsV2Model() {
        if (ttsWorker?.isAlive == true) {
            Toast.makeText(this, "Дождитесь завершения текущей операции.", Toast.LENGTH_SHORT).show()
            return
        }
        val downloader = TeraTtsV2ModelDownloader()
        ttsModelDownloader = downloader
        downloadTtsModelButton.isEnabled = false
        installTtsModelButton.isEnabled = false
        cancelTtsDownloadButton.visibility = android.view.View.VISIBLE
        cancelTtsDownloadButton.isEnabled = true
        status.text = "Подготовка загрузки TeraTTSv2… Для первого скачивания потребуется интернет."
        ttsWorker = Thread({
            var loadedEngine: TeraTtsV2OnnxEngine? = null
            try {
                val directory = downloader.downloadAndInstall(applicationContext) { progress ->
                    runOnUiThread {
                        val percent = if (progress.filePercent >= 0) " (" + progress.filePercent + "%)" else ""
                        status.text = "Загрузка TeraTTSv2: файл " + progress.fileIndex + "/" + progress.fileCount + percent +
                            "\n" + progress.fileName + "\nГотово файлов: " + progress.completedFiles + "/" + progress.fileCount +
                            "\nНе закрывайте приложение до окончания установки."
                    }
                }
                runOnUiThread { status.text = "Загрузка завершена. Проверяю и загружаю ONNX-модель…" }
                val engine = TeraTtsV2OnnxEngine()
                loadedEngine = engine
                val loaded = engine.load(directory)
                TeraTtsV2PackImporter.commitInstall(applicationContext)
                runOnUiThread {
                    ttsEngine?.close()
                    ttsEngine = engine
                    downloadTtsModelButton.isEnabled = true
                    installTtsModelButton.isEnabled = true
                    cancelTtsDownloadButton.visibility = android.view.View.GONE
                    cancelTtsDownloadButton.isEnabled = true
                    playBookButton.isEnabled = originalText.isNotBlank()
                    status.text = loaded.message + "\nTeraTTSv2 загружена и установлена. В следующий раз интернет не потребуется.\nГолоса: " +
                        loaded.voices.joinToString()
                }
            } catch (e: Throwable) {
                try { loadedEngine?.close() } catch (_: Throwable) {}
                TeraTtsV2PackImporter.rollbackInstall(applicationContext)
                runOnUiThread {
                    downloadTtsModelButton.isEnabled = true
                    installTtsModelButton.isEnabled = true
                    cancelTtsDownloadButton.visibility = android.view.View.GONE
                    cancelTtsDownloadButton.isEnabled = true
                    status.text = if (e.message?.contains("отменена", true) == true) {
                        "Загрузка отменена. Уже загруженные файлы сохранены — можно продолжить позже."
                    } else {
                        "Не удалось скачать/установить TeraTTSv2: " + (e.message ?: "неизвестная ошибка") +
                            "\nПроверьте интернет и свободное место. Повторная попытка продолжит загрузку."
                    }
                }
            } finally {
                ttsModelDownloader = null
                runOnUiThread {
                    downloadTtsModelButton.isEnabled = true
                    installTtsModelButton.isEnabled = true
                    cancelTtsDownloadButton.visibility = android.view.View.GONE
                    cancelTtsDownloadButton.isEnabled = true
                }
            }
        }, "teratts-v2-download").also { it.start() }
    }

'''
if "private fun downloadTeraTtsV2Model()" not in s:
    assert anchor in s
    s = s.replace(anchor, method + anchor, 1)

p.write_text(s, encoding="utf-8")
print("v41: added pinned in-app model download with resume, progress, cancel, validation and transactional installation.")
