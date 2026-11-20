from pathlib import Path
import re

# A structural FB2 reader: keeps section headings and exact character offsets,
# while preserving paragraph and verse boundaries for the TTS text stream.
parser = r'''package ru.fbaudioprep

import android.util.Base64
import android.util.Xml
import org.xmlpull.v1.XmlPullParser
import java.io.ByteArrayInputStream
import java.util.Locale

object Fb2DocumentParser {
    data class Chapter(val title: String, val offset: Int, val level: Int)
    data class Document(
        val text: String,
        val chapters: List<Chapter>,
        val title: String,
        val author: String,
        val coverBytes: ByteArray?
    )
    private data class Section(val level: Int)

    fun parse(bytes: ByteArray): Document {
        val p = Xml.newPullParser()
        p.setInput(ByteArrayInputStream(bytes), null)
        val out = StringBuilder()
        val chapters = mutableListOf<Chapter>()
        val sections = mutableListOf<Section>()
        var title = ""
        var first = ""
        var middle = ""
        var last = ""
        var metaTarget = ""
        var metaDepth = -1
        val meta = StringBuilder()
        var titleDepth = -1
        var titleBuffer = StringBuilder()
        var titleSectionLevel = 0
        var blockDepth = -1
        var blockBuffer = StringBuilder()
        var coverId = ""
        var binaryId = ""
        var binaryBuffer = StringBuilder()
        var cover: ByteArray? = null

        fun clean(value: String): String = value.replace(Regex("[\\t\\r ]+"), " ")
            .replace(Regex("\\s+"), " ").trim()
        fun appendParagraph(value: String): Int {
            val normalized = clean(value)
            if (normalized.isEmpty()) return -1
            val offset = out.length
            out.append(normalized).append("\n\n")
            return offset
        }

        var event = p.eventType
        while (event != XmlPullParser.END_DOCUMENT) {
            when (event) {
                XmlPullParser.START_TAG -> {
                    val n = p.name.lowercase(Locale.ROOT)
                    when (n) {
                        "section" -> sections.add(Section(sections.size + 1))
                        "title" -> if (sections.isNotEmpty() && titleDepth < 0) {
                            titleDepth = p.depth
                            titleBuffer = StringBuilder()
                            titleSectionLevel = sections.size
                        }
                        "p", "v", "subtitle", "text-author", "date" -> if (titleDepth < 0 && blockDepth < 0) {
                            blockDepth = p.depth
                            blockBuffer = StringBuilder()
                        }
                        "empty-line" -> if (titleDepth < 0 && blockDepth < 0) out.append("\n")
                        "book-title", "first-name", "middle-name", "last-name" -> {
                            metaTarget = n; metaDepth = p.depth; meta.setLength(0)
                        }
                        "coverpage" -> Unit
                        "image" -> {
                            for (i in 0 until p.attributeCount) {
                                val name = p.getAttributeName(i).lowercase(Locale.ROOT)
                                if (name.endsWith("href")) coverId = p.getAttributeValue(i).removePrefix("#")
                            }
                        }
                        "binary" -> {
                            binaryId = p.getAttributeValue(null, "id").orEmpty()
                            binaryBuffer = StringBuilder()
                        }
                    }
                }
                XmlPullParser.TEXT, XmlPullParser.CDSECT -> {
                    val value = p.text.orEmpty()
                    if (titleDepth >= 0) titleBuffer.append(value)
                    else if (blockDepth >= 0) blockBuffer.append(value)
                    if (metaTarget.isNotBlank()) meta.append(value)
                    if (binaryId.isNotBlank() && binaryBuffer.length < 28_000_000) binaryBuffer.append(value.trim())
                }
                XmlPullParser.END_TAG -> {
                    val n = p.name.lowercase(Locale.ROOT)
                    if (n == "title" && titleDepth == p.depth) {
                        val heading = clean(titleBuffer.toString())
                        if (heading.isNotBlank()) {
                            val offset = appendParagraph(heading)
                            if (offset >= 0) chapters.add(Chapter(heading, offset, titleSectionLevel))
                        }
                        titleDepth = -1
                    }
                    if (blockDepth == p.depth && n in setOf("p", "v", "subtitle", "text-author", "date")) {
                        appendParagraph(blockBuffer.toString())
                        blockDepth = -1
                    }
                    if (metaDepth == p.depth && metaTarget.isNotBlank()) {
                        when (metaTarget) {
                            "book-title" -> title = meta.toString().trim()
                            "first-name" -> first = meta.toString().trim()
                            "middle-name" -> middle = meta.toString().trim()
                            "last-name" -> last = meta.toString().trim()
                        }
                        metaTarget = ""; metaDepth = -1
                    }
                    if (n == "binary") {
                        if (binaryId.isNotBlank() && binaryId == coverId) {
                            cover = runCatching { Base64.decode(binaryBuffer.toString(), Base64.DEFAULT) }.getOrNull()
                        }
                        binaryId = ""; binaryBuffer = StringBuilder()
                    }
                    if (n == "section" && sections.isNotEmpty()) sections.removeAt(sections.lastIndex)
                }
            }
            event = p.next()
        }
        return Document(
            out.toString().trim(),
            chapters.distinctBy { it.offset },
            title,
            listOf(first, middle, last).filter { it.isNotBlank() }.joinToString(" "),
            cover?.takeIf { it.isNotEmpty() }
        )
    }
}
'''

Path("app/src/main/java/ru/fbaudioprep/Fb2DocumentParser.kt").write_text(parser, encoding="utf-8")

# Use the structural parser for the actual FB2 text imported by the application.
p = Path("app/src/main/java/ru/fbaudioprep/BookImporter.kt")
s = p.read_text(encoding="utf-8")
start = s.find("    private fun fb2(bytes: ByteArray): String {")
if start < 0:
    raise SystemExit("v60: cannot find FB2 text extraction method")
end_marker = "\n    }\n\n}"
end = s.find(end_marker, start)
if end < 0:
    raise SystemExit("v60: cannot locate end of FB2 text extraction method")
s = s[:start] + "    private fun fb2(bytes: ByteArray): String = Fb2DocumentParser.parse(bytes).text" + s[end + len("\n    }"):]
p.write_text(s, encoding="utf-8")

# Store chapter offsets and the embedded cover alongside each book's original file.
p = Path("app/src/main/java/ru/fbaudioprep/BookLibraryStore.kt")
s = p.read_text(encoding="utf-8")
if "v60-fb2-structure" not in s:
    s = s.replace(
        "    data class Book(\n",
        "    // v60-fb2-structure: offsets refer to the exact extracted text, not guessed headings.\n    data class Chapter(val title: String, val offset: Int, val level: Int)\n    data class Book(\n", 1)
    anchor = '''        atomic(File(dir, "text.txt"), text.toByteArray(Charsets.UTF_8))
        val old = readAll(c).firstOrNull { it.id == id }'''
    replacement = '''        atomic(File(dir, "text.txt"), text.toByteArray(Charsets.UTF_8))
        if (isFb2) {
            val structure = Fb2DocumentParser.parse(original)
            val chapterJson = JSONArray()
            structure.chapters.forEach { chapter ->
                chapterJson.put(JSONObject().put("title", chapter.title).put("offset", chapter.offset).put("level", chapter.level))
            }
            atomic(File(dir, "chapters.json"), chapterJson.toString().toByteArray(Charsets.UTF_8))
            structure.coverBytes?.let { atomic(File(dir, "cover.bin"), it) }
        }
        val old = readAll(c).firstOrNull { it.id == id }'''
    if anchor not in s: raise SystemExit("v60: cannot find library write anchor")
    s = s.replace(anchor, replacement, 1)
    anchor = '''    fun original(c: Context, id: String): ByteArray? {
        val d = folder(c, id)
        return listOf(File(d, "original.fb2"), File(d, "original.txt")).firstOrNull { it.isFile }?.readBytes()
    }'''
    replacement = anchor + '''
    fun chapters(c: Context, id: String): List<Chapter> = runCatching {
        val file = File(folder(c, id), "chapters.json")
        val array = JSONArray(file.takeIf { it.isFile }?.readText(Charsets.UTF_8) ?: "[]")
        (0 until array.length()).map { i ->
            val item = array.getJSONObject(i)
            Chapter(item.getString("title"), item.getInt("offset"), item.optInt("level", 1))
        }
    }.getOrDefault(emptyList())
    fun coverFile(c: Context, id: String): File? =
        File(folder(c, id), "cover.bin").takeIf { it.isFile && it.length() > 0L }
'''
    if anchor not in s: raise SystemExit("v60: cannot find original file accessor")
    s = s.replace(anchor, replacement, 1)
    p.write_text(s, encoding="utf-8")

# Wire the real FB2 TOC into the reader, keeping a regex fallback for TXT books.
p = Path("app/src/main/java/ru/fbaudioprep/AudiotomeHomeLayout.kt")
s = p.read_text(encoding="utf-8")
s = s.replace(
    'fun compose(activity: Activity, oldRoot: LinearLayout, bookContent: () -> String = { "" }): View {',
    'fun compose(activity: Activity, oldRoot: LinearLayout, bookContent: () -> String = { "" }, bookChapters: () -> List<BookLibraryStore.Chapter> = { emptyList() }, onChapterSelected: (Int) -> Unit = {}): View {',
    1
)
# Replace the old guessed-heading list with actual FB2 section offsets.
start = s.find("                    val chapters = mutableListOf<Pair<String, Int>>()")
end = s.find("                    if (chapters.isEmpty())", start)
if start < 0 or end < 0: raise SystemExit("v60: cannot locate chapter heuristic boundaries")
new = """                    val structured = bookChapters()
                    val chapters = if (structured.isNotEmpty()) {
                        structured.map { it.title to it.offset }
                    } else {
                        val fallback = mutableListOf<Pair<String, Int>>()
                        var offset = 0
                        fullText.split('\\n').forEach { line ->
                            val value = line.trim()
                            val isHeading = value.matches(Regex("(?i)^(глава|часть|пролог|эпилог|интерлюдия)(\\\\s+.*)?$")) ||
                                value.matches(Regex("^\\\\d{1,3}[.)]?\\\\s+.{2,90}$"))
                            if (isHeading && value.length <= 110) fallback.add(value to offset)
                            offset += line.length + 1
                        }
                        fallback
                    }
"""
s = s[:start] + new + s[end:]
# Replace chapter selection with the callback into MainActivity's progressive renderer.
start = s.find("                                val start = chapters[which].second")
end = s.find('                            .setNegativeButton("Закрыть", null)', start)
if start < 0 or end < 0: raise SystemExit("v60: cannot locate chapter selection boundaries")
s = s[:start] + """                                val start = chapters[which].second.coerceIn(0, fullText.length)
                                onChapterSelected(start)
                            }
""" + s[end:]
p.write_text(s, encoding="utf-8")

# Connect the reader's chapter selection callback to the progressive renderer.
p = Path("app/src/main/java/ru/fbaudioprep/MainActivity.kt")
s = p.read_text(encoding="utf-8")
old = 'setContentView(AudiotomeHomeLayout.compose(this, root) { processedText.ifBlank { originalText } })'
new = '''setContentView(AudiotomeHomeLayout.compose(
            this, root,
            { processedText.ifBlank { originalText } },
            { currentLibraryBookId?.let { BookLibraryStore.chapters(applicationContext, it) } ?: emptyList() },
            { offset ->
                readerStartOffset = offset
                lastObservedReaderOffset = offset
                lastPersistedReaderOffset = offset
                val content = findViewById<android.view.ViewGroup>(android.R.id.content)
                (content?.findViewWithTag("audiotome-paper-scroll") as? ScrollView)?.contentDescription = null
                syncReaderContent()
            }
        ))'''
if old not in s: raise SystemExit("v60: cannot find reader layout construction")
s = s.replace(old, new, 1)
p.write_text(s, encoding="utf-8")

print("v60: parse FB2 section hierarchy, persist exact chapter offsets and embedded cover, and use the real TOC in the reader.")
