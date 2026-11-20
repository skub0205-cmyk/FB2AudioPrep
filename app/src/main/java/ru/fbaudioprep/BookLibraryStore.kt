package ru.fbaudioprep

import android.content.Context
import android.util.Base64
import android.util.Xml
import org.json.JSONArray
import org.json.JSONObject
import org.xmlpull.v1.XmlPullParser
import java.io.ByteArrayInputStream
import java.io.File
import java.security.MessageDigest
import java.util.Locale

/** Persistent app-private library. Its files are independent from model storage. */
object BookLibraryStore {
    data class Book(
        val id: String, val title: String, val author: String, val sourceName: String,
        val isFb2: Boolean, val textLength: Int, val importedAt: Long, val lastOpenedAt: Long
    )
    private fun root(c: Context) = File(c.filesDir, "book-library-v1").apply { mkdirs() }
    private fun folder(c: Context, id: String) = File(root(c), id)
    private fun index(c: Context) = File(root(c), "library.json")

    @Synchronized fun add(c: Context, sourceName: String, text: String, isFb2: Boolean, original: ByteArray): Book {
        require(text.isNotBlank()) { "Пустой текст книги" }
        val id = MessageDigest.getInstance("SHA-256").digest(original).joinToString("") { "%02x".format(it) }
        val meta = if (isFb2) readFb2Metadata(original) else (sourceName.substringBeforeLast('.', sourceName) to "")
        val dir = folder(c, id)
        if (!dir.exists() && !dir.mkdirs()) error("Не удалось создать папку книги")
        atomic(File(dir, if (isFb2) "original.fb2" else "original.txt"), original)
        atomic(File(dir, "text.txt"), text.toByteArray(Charsets.UTF_8))
        val old = readAll(c).firstOrNull { it.id == id }
        val book = Book(id, meta.first.ifBlank { sourceName }, meta.second, sourceName, isFb2,
            text.length, old?.importedAt ?: System.currentTimeMillis(), old?.lastOpenedAt ?: 0L)
        writeIndex(c, (readAll(c).filterNot { it.id == id } + book))
        return book
    }

    fun list(c: Context): List<Book> = readAll(c).sortedWith(
        compareByDescending<Book> { it.lastOpenedAt }.thenByDescending { it.importedAt }
    )
    fun text(c: Context, id: String): String = File(folder(c, id), "text.txt")
        .takeIf { it.isFile }?.readText(Charsets.UTF_8) ?: error("Текст книги не найден")
    fun original(c: Context, id: String): ByteArray? {
        val d = folder(c, id)
        return listOf(File(d, "original.fb2"), File(d, "original.txt")).firstOrNull { it.isFile }?.readBytes()
    }
    @Synchronized fun markOpened(c: Context, id: String) {
        val now = System.currentTimeMillis()
        writeIndex(c, readAll(c).map { if (it.id == id) it.copy(lastOpenedAt = now) else it })
    }
    @Synchronized fun remove(c: Context, id: String) {
        require(id.matches(Regex("[a-f0-9]{64}")))
        folder(c, id).deleteRecursively()
        writeIndex(c, readAll(c).filterNot { it.id == id })
    }

    private fun readAll(c: Context): List<Book> = runCatching {
        val a = JSONArray(index(c).takeIf { it.isFile }?.readText(Charsets.UTF_8) ?: "[]")
        (0 until a.length()).mapNotNull { i -> runCatching {
            val o = a.getJSONObject(i)
            Book(o.getString("id"), o.optString("title"), o.optString("author"), o.optString("sourceName"),
                o.optBoolean("isFb2"), o.optInt("textLength"), o.optLong("importedAt"), o.optLong("lastOpenedAt"))
        }.getOrNull() }
    }.getOrDefault(emptyList())

    private fun writeIndex(c: Context, books: List<Book>) {
        val a = JSONArray()
        books.forEach { b -> a.put(JSONObject().put("id", b.id).put("title", b.title).put("author", b.author)
            .put("sourceName", b.sourceName).put("isFb2", b.isFb2).put("textLength", b.textLength)
            .put("importedAt", b.importedAt).put("lastOpenedAt", b.lastOpenedAt)) }
        atomic(index(c), a.toString().toByteArray(Charsets.UTF_8))
    }
    private fun atomic(file: File, bytes: ByteArray) {
        val tmp = File(file.parentFile, file.name + ".tmp")
        tmp.writeBytes(bytes)
        if (file.exists() && !file.delete()) error("Не удалось обновить файл библиотеки")
        if (!tmp.renameTo(file)) error("Не удалось сохранить файл библиотеки")
    }

    /** Reads title, author and embedded cover from FB2 metadata; the source remains untouched. */
    private fun readFb2Metadata(bytes: ByteArray): Pair<String, String> {
        var title = ""; var first = ""; var middle = ""; var last = ""
        return runCatching {
            val p = Xml.newPullParser()
            p.setInput(ByteArrayInputStream(bytes), null)
            var target = ""; var depth = -1
            val value = StringBuilder()
            var event = p.eventType
            while (event != XmlPullParser.END_DOCUMENT) {
                when (event) {
                    XmlPullParser.START_TAG -> {
                        val n = p.name.lowercase(Locale.ROOT)
                        if (n in setOf("book-title", "first-name", "middle-name", "last-name")) {
                            target = n; depth = p.depth; value.setLength(0)
                        }
                    }
                    XmlPullParser.TEXT, XmlPullParser.CDSECT -> if (target.isNotBlank()) value.append(p.text)
                    XmlPullParser.END_TAG -> if (depth == p.depth && target.isNotBlank()) {
                        when (target) {
                            "book-title" -> title = value.toString().trim()
                            "first-name" -> first = value.toString().trim()
                            "middle-name" -> middle = value.toString().trim()
                            "last-name" -> last = value.toString().trim()
                        }
                        target = ""; depth = -1
                    }
                }
                event = p.next()
            }
            title to listOf(first, middle, last).filter { it.isNotBlank() }.joinToString(" ")
        }.getOrDefault("" to "")
    }
}
