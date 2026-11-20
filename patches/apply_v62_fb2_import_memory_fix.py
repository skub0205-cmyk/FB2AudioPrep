from pathlib import Path

base = Path("app/src/main/java/ru/fbaudioprep")

# Avoid accumulating every embedded image in memory; only decode the image referenced by coverpage.
p = base / "Fb2DocumentParser.kt"
s = p.read_text(encoding="utf-8")
old = 'if (binaryId.isNotBlank() && binaryBuffer.length < 28_000_000) binaryBuffer.append(value.trim())'
new = 'if (binaryId.isNotBlank() && binaryId == coverId && binaryBuffer.length < 12_000_000) binaryBuffer.append(value.trim())'
if old not in s: raise SystemExit("v62: parser binary accumulation anchor not found")
s = s.replace(old, new, 1)
p.write_text(s, encoding="utf-8")

# Return the already-parsed FB2 structure from the importer so the library does not parse
# the same large XML file a second time during import.
p = base / "BookImporter.kt"
s = p.read_text(encoding="utf-8")
old = """        val importNote: String
    )"""
new = """        val importNote: String,
        val fb2Document: Fb2DocumentParser.Document? = null
    )"""
if old not in s: raise SystemExit("v62: ImportedBook data class anchor not found")
s = s.replace(old, new, 1)
old = """        val isFb2 = selected.name.endsWith(".fb2", true)
        val decoded = if (isFb2) null else BookImportSupport.decodeText(selected.bytes)
        val text = if (isFb2) fb2(selected.bytes) else {"""
new = """        val isFb2 = selected.name.endsWith(".fb2", true)
        val fb2Document = if (isFb2) Fb2DocumentParser.parse(selected.bytes) else null
        val decoded = if (isFb2) null else BookImportSupport.decodeText(selected.bytes)
        val text = if (isFb2) fb2Document!!.text else {"""
if old not in s: raise SystemExit("v62: importer parse flow anchor not found")
s = s.replace(old, new, 1)
old = """        return ImportedBook(name, text, selected.name, isFb2, selected.bytes, note)"""
new = """        return ImportedBook(name, text, selected.name, isFb2, selected.bytes, note, fb2Document)"""
if old not in s: raise SystemExit("v62: importer return anchor not found")
s = s.replace(old, new, 1)
# Remove now-unused helper to keep the parser path unambiguous.
old = """    /** XML Pull Parser detects BOM and the encoding declaration itself when encoding is null. */
    private fun fb2(bytes: ByteArray): String = Fb2DocumentParser.parse(bytes).text

"""
s = s.replace(old, "", 1)
p.write_text(s, encoding="utf-8")

# Persist chapters and cover from the already parsed structure, not a second XML pass.
p = base / "BookLibraryStore.kt"
s = p.read_text(encoding="utf-8")
old = """    @Synchronized fun add(c: Context, sourceName: String, text: String, isFb2: Boolean, original: ByteArray): Book {"""
new = """    @Synchronized fun add(c: Context, sourceName: String, text: String, isFb2: Boolean, original: ByteArray,
        fb2Document: Fb2DocumentParser.Document? = null): Book {"""
if old not in s: raise SystemExit("v62: library add signature anchor not found")
s = s.replace(old, new, 1)
old = """        if (isFb2) {
            val structure = Fb2DocumentParser.parse(original)
            val chapterJson = JSONArray()"""
new = """        if (isFb2) {
            val structure = fb2Document ?: Fb2DocumentParser.parse(original)
            val chapterJson = JSONArray()"""
if old not in s: raise SystemExit("v62: library structure parse anchor not found")
s = s.replace(old, new, 1)
p.write_text(s, encoding="utf-8")

# Pass the one-time parse result from import into the library.
p = base / "MainActivity.kt"
s = p.read_text(encoding="utf-8")
old = """                    applicationContext, book.sourceName, book.text, book.isFb2, book.originalBytes
                )"""
new = """                    applicationContext, book.sourceName, book.text, book.isFb2, book.originalBytes,
                    book.fb2Document
                )"""
if old not in s: raise SystemExit("v62: MainActivity library call anchor not found")
s = s.replace(old, new, 1)
p.write_text(s, encoding="utf-8")

print("v62: optimize FB2 import memory and parse each FB2 document only once.")
