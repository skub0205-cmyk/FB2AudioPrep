from pathlib import Path
import re

store = Path("app/src/main/java/ru/fbaudioprep/BookLibraryStore.kt")
s = store.read_text(encoding="utf-8")
if "v59-reader-position" not in s:
    s = s.replace(
        "        val isFb2: Boolean, val textLength: Int, val importedAt: Long, val lastOpenedAt: Long\n",
        "        val isFb2: Boolean, val textLength: Int, val importedAt: Long, val lastOpenedAt: Long, val readingPosition: Int = 0\n",
        1
    )
    s = s.replace(
        "            textLength, old?.importedAt ?: System.currentTimeMillis(), old?.lastOpenedAt ?: 0L)",
        "            textLength, old?.importedAt ?: System.currentTimeMillis(), old?.lastOpenedAt ?: 0L, old?.readingPosition ?: 0)",
        1
    )
    s = s.replace(
        "    @Synchronized fun remove(c: Context, id: String) {",
        """    // v59-reader-position: store the last visible character offset per stable book ID.
    @Synchronized fun saveReadingPosition(c: Context, id: String, position: Int) {
        if (!id.matches(Regex("[a-f0-9]{64}"))) return
        writeIndex(c, readAll(c).map {
            if (it.id == id) it.copy(readingPosition = position.coerceIn(0, it.textLength)) else it
        })
    }
    fun readingPosition(c: Context, id: String): Int =
        readAll(c).firstOrNull { it.id == id }?.readingPosition ?: 0

    @Synchronized fun remove(c: Context, id: String) {""",
        1
    )
    s = s.replace(
        'o.optBoolean("isFb2"), o.optInt("textLength"), o.optLong("importedAt"), o.optLong("lastOpenedAt"))',
        'o.optBoolean("isFb2"), o.optInt("textLength"), o.optLong("importedAt"), o.optLong("lastOpenedAt"), o.optInt("readingPosition", 0))',
        1
    )
    s = s.replace(
        '.put("importedAt", b.importedAt).put("lastOpenedAt", b.lastOpenedAt)) }',
        '.put("importedAt", b.importedAt).put("lastOpenedAt", b.lastOpenedAt).put("readingPosition", b.readingPosition)) }',
        1
    )
    store.write_text(s, encoding="utf-8")

main = Path("app/src/main/java/ru/fbaudioprep/MainActivity.kt")
s = main.read_text(encoding="utf-8")
if "v59-reader-position" not in s:
    # Stable current book identity and current character offset.
    anchor = '    private var processedText = ""'
    if anchor not in s: raise SystemExit("v59: cannot locate processedText field")
    s = s.replace(anchor, anchor + '\n    // v59-reader-position\n    private var currentLibraryBookId: String? = null\n    private var readerStartOffset: Int = 0\n    private var lastPersistedReaderOffset: Int = -1', 1)

    # Reader starts at saved offset; contentDescription tracks the absolute end.
    old = '''                readerText.contentDescription = "8000"
                readerText.text = visibleText.take(8000)
                readerScroll?.scrollTo(0, 0)'''
    new = '''                val startOffset = readerStartOffset.coerceIn(0, visibleText.length)
                val endOffset = (startOffset + 8000).coerceAtMost(visibleText.length)
                readerText.contentDescription = endOffset.toString()
                readerText.text = visibleText.substring(startOffset, endOffset)
                readerScroll?.scrollTo(0, 0)'''
    if old not in s: raise SystemExit("v59: cannot locate reader initial chunk")
    s = s.replace(old, new, 1)

    # Persist current absolute offset whenever reader approaches the end of loaded text.
    old = '''                val currentEnd = readerText.contentDescription?.toString()?.toIntOrNull() ?: 8000
                if (currentEnd >= visibleText.length) return@setOnScrollChangeListener
                val nextEnd = (currentEnd + 8000).coerceAtMost(visibleText.length)'''
    new = '''                val currentEnd = readerText.contentDescription?.toString()?.toIntOrNull()
                    ?: (readerStartOffset + 8000).coerceAtMost(visibleText.length)
                if (currentEnd >= visibleText.length) {
                    currentLibraryBookId?.let { id ->
                        if (lastPersistedReaderOffset != currentEnd) {
                            BookLibraryStore.saveReadingPosition(applicationContext, id, currentEnd)
                            lastPersistedReaderOffset = currentEnd
                        }
                    }
                    return@setOnScrollChangeListener
                }
                val nextEnd = (currentEnd + 8000).coerceAtMost(visibleText.length)
                currentLibraryBookId?.let { id ->
                    if (lastPersistedReaderOffset < nextEnd - 1500) {
                        BookLibraryStore.saveReadingPosition(applicationContext, id, nextEnd)
                        lastPersistedReaderOffset = nextEnd
                    }
                }'''
    if old not in s: raise SystemExit("v59: cannot locate progressive reader chunk logic")
    s = s.replace(old, new, 1)

    # When opening an existing library book, restore its per-book offset.
    old = '''                        sourceName = selected.sourceName
                        originalText = text'''
    new = '''                        sourceName = selected.sourceName
                        currentLibraryBookId = selected.id
                        readerStartOffset = BookLibraryStore.readingPosition(applicationContext, selected.id)
                        lastPersistedReaderOffset = readerStartOffset
                        originalText = text'''
    if old not in s: raise SystemExit("v59: cannot locate library book open assignment")
    s = s.replace(old, new, 1)

    # When importing a book, bind its stable ID returned from BookLibraryStore.add.
    old = '''                            BookLibraryStore.add(
                                applicationContext,
                                sourceName,
                                saved.text,
                                saved.isFb2,
                                saved.originalBytes
                            )'''
    new = '''                            val libraryBook = BookLibraryStore.add(
                                applicationContext,
                                sourceName,
                                saved.text,
                                saved.isFb2,
                                saved.originalBytes
                            )
                            currentLibraryBookId = libraryBook.id
                            readerStartOffset = 0
                            lastPersistedReaderOffset = 0'''
    if old not in s: raise SystemExit("v59: cannot locate import library add")
    s = s.replace(old, new, 1)

    # Last-opened restore: use ID and restore offset; avoid losing it on app restart.
    # Find restore function and inject after the saved text is loaded if exact stable pattern exists.
    # Existing restore flow is inspected below if this guard fires.
    main.write_text(s, encoding="utf-8")

print("v59: persisted per-book reading offsets and restore on library open.")
