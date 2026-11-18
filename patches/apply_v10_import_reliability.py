from pathlib import Path
import re

main = Path("app/src/main/java/ru/fbaudioprep/MainActivity.kt")
reader = Path("app/src/main/java/ru/fbaudioprep/BookReaderActivity.kt")
gradle = Path("app/build.gradle.kts")
s = main.read_text(encoding="utf-8")

if "import java.io.File" not in s:
    s = s.replace("import org.json.JSONObject\n", "import org.json.JSONObject\nimport java.io.File\n")

old = "            openId -> load(uri)"
new = """            openId -> {
                val readFlag = data.flags and Intent.FLAG_GRANT_READ_URI_PERMISSION
                if (readFlag != 0) {
                    try { contentResolver.takePersistableUriPermission(uri, readFlag) }
                    catch (_: SecurityException) { }
                    catch (_: IllegalArgumentException) { }
                }
                load(uri)
            }"""
if old in s:
    s = s.replace(old, new, 1)
elif "takePersistableUriPermission(uri, readFlag)" not in s:
    raise SystemExit("Cannot locate openId result branch")

replacement = r'''    private fun load(uri: Uri) {
        status.text = "Открываю книгу…\nЧитаю файл и извлекаю текст."
        preview.text = ""
        accentButton.isEnabled = false
        dialogueButton.isEnabled = false
        reviewDialoguesButton.isEnabled = false
        teraManualPackButton.isEnabled = false
        saveTextButton.isEnabled = false
        saveFb2Button.isEnabled = false

        Thread({
            try {
                val mime = contentResolver.getType(uri).orEmpty()
                val displayName = contentResolver.query(
                    uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null
                )?.use { cursor ->
                    if (cursor.moveToFirst()) cursor.getString(0)?.takeIf { it.isNotBlank() } else null
                } ?: uri.lastPathSegment?.substringAfterLast('/')?.takeIf { it.isNotBlank() } ?: "book"
                val name = when {
                    displayName.endsWith(".fb2", true) ||
                        displayName.endsWith(".txt", true) ||
                        displayName.endsWith(".zip", true) -> displayName
                    mime.equals("application/x-fictionbook+xml", true) -> displayName + ".fb2"
                    mime.equals("text/plain", true) -> displayName + ".txt"
                    else -> displayName
                }
                val book = BookImporter.read(contentResolver, uri, name)
                require(book.text.isNotBlank()) {
                    "Файл прочитан, но текст книги не найден. Проверьте, что это FB2/TXT."
                }

                runOnUiThread {
                    sourceName = book.sourceName
                    originalText = book.text
                    originalFb2Bytes = book.originalBytes.takeIf { book.isFb2 }
                    processedFb2Bytes = null
                    currentBookIsFb2 = book.isFb2
                    processedText = ""
                    accentButton.isEnabled = true
                    dialogueButton.isEnabled = true
                    reviewDialoguesButton.isEnabled = false
                    teraManualPackButton.isEnabled = true
                    dialogueFindings = emptyList()
                    dialogueReport = ""
                    saveTextButton.isEnabled = false
                    saveFb2Button.isEnabled = false
                    report = buildString {
                        appendLine("FB2 AudioPrep 2.0.2")
                        appendLine("Файл: " + name)
                        appendLine("Внутренний файл: " + book.sourceName)
                        appendLine("Символов: " + book.text.length)
                        appendLine("Строк: " + book.text.lines().size)
                        if (book.importNote.isNotBlank()) appendLine(book.importNote)
                        appendLine()
                        appendLine("Книга загружена. Ударения ещё не расставлены.")
                    }
                    status.text = "Книга загружена: " + name + "\nФормат: " +
                        (if (book.isFb2) "FB2" else "TXT") + "\nСимволов: " + book.text.length +
                        (if (book.importNote.isNotBlank()) "\n" + book.importNote else "") +
                        "\nОткрываю читалку…"
                    preview.text = book.text.take(8000)
                    openBookPreview()
                }
            } catch (e: Exception) {
                val detail = e.message?.takeIf { it.isNotBlank() } ?: e.javaClass.simpleName
                runOnUiThread {
                    status.text = "Не удалось открыть книгу: " + detail
                    preview.text = ""
                    report = ""
                    originalText = ""
                    processedText = ""
                    accentButton.isEnabled = false
                    dialogueButton.isEnabled = false
                    reviewDialoguesButton.isEnabled = false
                    saveTextButton.isEnabled = false
                    saveFb2Button.isEnabled = false
                    originalFb2Bytes = null
                    processedFb2Bytes = null
                    currentBookIsFb2 = false
                    AlertDialog.Builder(this@MainActivity)
                        .setTitle("Не удалось открыть книгу")
                        .setMessage(detail)
                        .setPositiveButton("Понятно", null)
                        .show()
                }
            }
        }, "fb2-book-import").start()
    }

'''
pattern = r"    private fun load\(uri: Uri\) \{.*?\n    \}\n\n    private fun accentBook\(\)"
s, n = re.subn(pattern, replacement + "    private fun accentBook()", s, count=1, flags=re.S)
if n != 1:
    raise SystemExit("Could not replace load(uri) safely")

reader_function = r'''    private fun openBookPreview() {
        if (originalText.isBlank()) {
            Toast.makeText(this, "Сначала откройте книгу", Toast.LENGTH_SHORT).show()
            return
        }
        val text = processedText.ifBlank { originalText }
        try {
            val file = File(cacheDir, "reader-book-" + System.currentTimeMillis() + ".txt")
            file.writeText(text, Charsets.UTF_8)
            startActivity(Intent(this, BookReaderActivity::class.java).apply {
                putExtra(BookReaderActivity.EXTRA_TITLE, sourceName.ifBlank { "Книга" })
                putExtra(BookReaderActivity.EXTRA_FILE_PATH, file.absolutePath)
            })
        } catch (e: Exception) {
            Toast.makeText(this, "Не удалось подготовить книгу для чтения: " + e.message, Toast.LENGTH_LONG).show()
        }
    }

'''
p = r"    private fun openBookPreview\(\) \{.*?\n    \}\n\n    private fun openBook\(\)"
s, n = re.subn(p, reader_function + "    private fun openBook()", s, count=1, flags=re.S)
if n != 1:
    raise SystemExit("Could not replace openBookPreview() safely")
s = re.sub(r"FB2 AudioPrep [0-9.]+", "FB2 AudioPrep 2.0.2", s)
main.write_text(s, encoding="utf-8")

r = reader.read_text(encoding="utf-8")
if "import java.io.File" not in r:
    r = r.replace("import kotlin.math.roundToInt\n", "import kotlin.math.roundToInt\nimport java.io.File\n")
old = '        content = intent.getStringExtra(EXTRA_TEXT).orEmpty()'
new = '''        val contentPath = intent.getStringExtra(EXTRA_FILE_PATH)
        content = if (!contentPath.isNullOrBlank()) {
            runCatching { File(contentPath).takeIf { it.isFile }?.readText(Charsets.UTF_8).orEmpty() }
                .getOrElse { "" }
        } else {
            intent.getStringExtra(EXTRA_TEXT).orEmpty()
        }
        if (content.isBlank()) {
            Toast.makeText(this, "Не удалось прочитать подготовленный файл книги", Toast.LENGTH_LONG).show()
            finish()
            return
        }'''
if old not in r:
    raise SystemExit("Reader content initialization not found")
r = r.replace(old, new, 1)
old_companion = '        const val EXTRA_TEXT="book_text"'
new_companion = '        const val EXTRA_TEXT="book_text"\n        const val EXTRA_FILE_PATH="book_file_path"'
if old_companion not in r:
    raise SystemExit("Reader companion constant not found")
r = r.replace(old_companion, new_companion, 1)
reader.write_text(r, encoding="utf-8")

g = gradle.read_text(encoding="utf-8")
g = re.sub(r'versionCode = (\d+); versionName = "[^"]+"',
           lambda m: f'versionCode = {int(m.group(1))+1}; versionName = "2.0.2"', g, count=1)
gradle.write_text(g, encoding="utf-8")
print("Applied FB2AudioPrep 2.0.2 reliable asynchronous import and file-backed reader patch.")
