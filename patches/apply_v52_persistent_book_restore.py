from pathlib import Path

base = Path("app/src/main/java/ru/fbaudioprep")
main = base / "MainActivity.kt"
s = main.read_text(encoding="utf-8")

store = r'''package ru.fbaudioprep

import android.content.Context
import java.io.File

/** Durable last-opened book snapshot; a SAF URI grant alone does not restore app state after process death. */
object BookSessionStore {
    data class Snapshot(val name: String, val text: String, val isFb2: Boolean, val originalBytes: ByteArray?)
    private fun root(context: Context) = File(context.filesDir, "book-session").apply { mkdirs() }

    fun save(context: Context, name: String, text: String, isFb2: Boolean, originalBytes: ByteArray?) {
        require(text.isNotBlank()) { "Пустой текст книги" }
        val dir = root(context)
        writeAtomic(File(dir, "book.txt"), text.toByteArray(Charsets.UTF_8))
        val fb2 = File(dir, "original.fb2")
        if (isFb2 && originalBytes != null) writeAtomic(fb2, originalBytes) else fb2.delete()
        context.getSharedPreferences("last_opened_book", Context.MODE_PRIVATE).edit()
            .putString("name", name).putBoolean("is_fb2", isFb2)
            .putBoolean("has_original", isFb2 && originalBytes != null)
            .putLong("text_length", text.length.toLong()).commit()
    }

    fun restore(context: Context): Snapshot? {
        val prefs = context.getSharedPreferences("last_opened_book", Context.MODE_PRIVATE)
        val name = prefs.getString("name", null) ?: return null
        val textFile = File(root(context), "book.txt")
        if (!textFile.isFile || textFile.length() == 0L) return null
        val text = textFile.readText(Charsets.UTF_8)
        if (text.isBlank() || text.length.toLong() != prefs.getLong("text_length", -1L)) return null
        val bytes = if (prefs.getBoolean("has_original", false))
            File(textFile.parentFile, "original.fb2").takeIf { it.isFile }?.readBytes() else null
        return Snapshot(name, text, prefs.getBoolean("is_fb2", false), bytes)
    }

    private fun writeAtomic(target: File, bytes: ByteArray) {
        val tmp = File(target.parentFile, target.name + ".tmp")
        tmp.writeBytes(bytes)
        if (target.exists() && !target.delete()) error("Не удалось заменить сохранённую книгу")
        if (!tmp.renameTo(target)) error("Не удалось сохранить книгу во внутреннюю память")
    }
}
'''
(base / "BookSessionStore.kt").write_text(store, encoding="utf-8")

anchor = "                    sourceName = book.sourceName\n                    originalText = book.text"
if "BookSessionStore.save" not in s:
    if anchor not in s: raise SystemExit("v52: cannot find successful import assignment")
    s = s.replace(anchor, anchor + '''
                    try {
                        BookSessionStore.save(applicationContext, book.sourceName, book.text, book.isFb2, book.originalBytes)
                    } catch (saveError: Throwable) {
                        android.util.Log.e("BookSessionStore", "Could not persist imported book", saveError)
                    }''', 1)

layout_anchor = "        setContentView(AudiotomeHomeLayout.compose(this, root))"
if "restoreLastOpenedBook()" not in s:
    if layout_anchor not in s: raise SystemExit("v52: cannot locate home layout initialization")
    s = s.replace(layout_anchor, layout_anchor + "\n        restoreLastOpenedBook()", 1)

method = r'''    private fun restoreLastOpenedBook() {
        Thread({
            try {
                val saved = BookSessionStore.restore(applicationContext) ?: return@Thread
                runOnUiThread {
                    sourceName = saved.name
                    originalText = saved.text
                    originalFb2Bytes = saved.originalBytes
                    processedFb2Bytes = null
                    currentBookIsFb2 = saved.isFb2
                    processedText = ""
                    dialogueFindings = DialogueCorrectionStore.apply(
                        this@MainActivity, saved.text, DialogueFindingsStore.load(this@MainActivity, saved.text)
                    )
                    dialogueReport = ""
                    dialogueAnalysisInProgress = false
                    openReviewAfterAnalysis = false
                    accentButton.isEnabled = true
                    dialogueButton.isEnabled = true
                    reviewDialoguesButton.isEnabled = dialogueFindings.isNotEmpty()
                    teraManualPackButton.isEnabled = true
                    saveTextButton.isEnabled = false
                    saveFb2Button.isEnabled = false
                    ttsBookKey = MessageDigest.getInstance("SHA-256")
                        .digest(saved.text.toByteArray(Charsets.UTF_8))
                        .joinToString("") { "%02x".format(it) }
                    ttsResumeStorageKey = ""
                    ttsResumeIndex = 0
                    runCatching { refreshTtsResumeKey(loadSaved = true) }
                    status.text = "Книга восстановлена: " + saved.name +
                        "\nСимволов: " + saved.text.length +
                        "\nСохранённые результаты ИИ: " + dialogueFindings.size
                    syncReaderContent()
                }
            } catch (e: Throwable) {
                android.util.Log.e("BookSessionStore", "Could not restore last book", e)
                runOnUiThread {
                    status.text = "Не удалось восстановить последнюю книгу: " +
                        (e.message ?: e.javaClass.simpleName) + "\nОткройте файл книги повторно."
                }
            }
        }, "restore-last-book").start()
    }

'''
if "private fun restoreLastOpenedBook()" not in s:
    marker = "    private fun load(uri: Uri) {"
    if marker not in s: raise SystemExit("v52: cannot locate load(uri) insertion point")
    s = s.replace(marker, method + marker, 1)

main.write_text(s, encoding="utf-8")
print("v52: persist the last imported book in filesDir and restore it, including saved dialogue findings, on app launch.")
