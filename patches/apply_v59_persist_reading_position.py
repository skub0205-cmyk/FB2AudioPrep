from pathlib import Path

store = Path("app/src/main/java/ru/fbaudioprep/BookLibraryStore.kt")
s = store.read_text(encoding="utf-8")
if "v59-reader-position" not in s:
    s = s.replace(
        "        val isFb2: Boolean, val textLength: Int, val importedAt: Long, val lastOpenedAt: Long\n",
        "        val isFb2: Boolean, val textLength: Int, val importedAt: Long, val lastOpenedAt: Long, val readingPosition: Int = 0\n", 1)
    s = s.replace(
        "            text.length, old?.importedAt ?: System.currentTimeMillis(), old?.lastOpenedAt ?: 0L)",
        "            text.length, old?.importedAt ?: System.currentTimeMillis(), old?.lastOpenedAt ?: 0L, old?.readingPosition ?: 0)", 1)
    s = s.replace(
        "    @Synchronized fun remove(c: Context, id: String) {",
        """    // v59-reader-position: persist the last visible character offset for each stable book ID.
    @Synchronized fun saveReadingPosition(c: Context, id: String, position: Int) {
        if (!id.matches(Regex("[a-f0-9]{64}"))) return
        writeIndex(c, readAll(c).map {
            if (it.id == id) it.copy(readingPosition = position.coerceIn(0, it.textLength)) else it
        })
    }
    fun readingPosition(c: Context, id: String): Int =
        readAll(c).firstOrNull { it.id == id }?.readingPosition ?: 0

    @Synchronized fun remove(c: Context, id: String) {""", 1)
    s = s.replace(
        'o.optBoolean("isFb2"), o.optInt("textLength"), o.optLong("importedAt"), o.optLong("lastOpenedAt"))',
        'o.optBoolean("isFb2"), o.optInt("textLength"), o.optLong("importedAt"), o.optLong("lastOpenedAt"), o.optInt("readingPosition", 0))', 1)
    s = s.replace(
        '.put("importedAt", b.importedAt).put("lastOpenedAt", b.lastOpenedAt)) }',
        '.put("importedAt", b.importedAt).put("lastOpenedAt", b.lastOpenedAt).put("readingPosition", b.readingPosition)) }', 1)
    store.write_text(s, encoding="utf-8")

main = Path("app/src/main/java/ru/fbaudioprep/MainActivity.kt")
s = main.read_text(encoding="utf-8")
if "v59-reader-position" not in s:
    anchor = '    private var processedText = ""'
    if anchor not in s: raise SystemExit("v59: cannot locate processedText field")
    s = s.replace(anchor, anchor + '''
    // v59-reader-position
    private var currentLibraryBookId: String? = null
    private var readerStartOffset: Int = 0
    private var lastPersistedReaderOffset: Int = -1
    private var lastObservedReaderOffset: Int = 0''', 1)

    old = '''                readerText.contentDescription = "8000"
                readerText.text = visibleText.take(8000)
                readerScroll?.scrollTo(0, 0)'''
    new = '''                val startOffset = readerStartOffset.coerceIn(0, visibleText.length)
                val endOffset = (startOffset + 8000).coerceAtMost(visibleText.length)
                readerText.contentDescription = endOffset.toString()
                readerText.text = visibleText.substring(startOffset, endOffset)
                lastObservedReaderOffset = startOffset
                readerScroll?.scrollTo(0, 0)'''
    if old not in s: raise SystemExit("v59: cannot locate reader initial chunk")
    s = s.replace(old, new, 1)

    old = '''                val currentEnd = readerText.contentDescription?.toString()?.toIntOrNull() ?: 8000
                if (currentEnd >= visibleText.length) return@setOnScrollChangeListener
                val nextEnd = (currentEnd + 8000).coerceAtMost(visibleText.length)'''
    new = '''                val currentEnd = readerText.contentDescription?.toString()?.toIntOrNull()
                    ?: (readerStartOffset + 8000).coerceAtMost(visibleText.length)
                val scrollRange = (child.height - scroll.height).coerceAtLeast(1)
                val fraction = (scrollY.toFloat() / scrollRange).coerceIn(0f, 1f)
                val estimatedOffset = readerStartOffset +
                    ((currentEnd - readerStartOffset).coerceAtLeast(0) * fraction).toInt()
                lastObservedReaderOffset = estimatedOffset.coerceIn(0, visibleText.length)
                currentLibraryBookId?.let { id ->
                    if (kotlin.math.abs(lastObservedReaderOffset - lastPersistedReaderOffset) >= 500) {
                        BookLibraryStore.saveReadingPosition(applicationContext, id, lastObservedReaderOffset)
                        lastPersistedReaderOffset = lastObservedReaderOffset
                    }
                }
                if (currentEnd >= visibleText.length) return@setOnScrollChangeListener
                val nextEnd = (currentEnd + 8000).coerceAtMost(visibleText.length)'''
    if old not in s: raise SystemExit("v59: cannot locate progressive reader chunk logic")
    s = s.replace(old, new, 1)

    old = '''                        sourceName = selected.sourceName
                        originalText = text'''
    new = '''                        sourceName = selected.sourceName
                        currentLibraryBookId = selected.id
                        readerStartOffset = BookLibraryStore.readingPosition(applicationContext, selected.id)
                        lastPersistedReaderOffset = readerStartOffset
                        lastObservedReaderOffset = readerStartOffset
                        originalText = text'''
    if old not in s: raise SystemExit("v59: cannot locate library book open assignment")
    s = s.replace(old, new, 1)

    old = '''                val libraryRecord = BookLibraryStore.add(
                    applicationContext, book.sourceName, book.text, book.isFb2, book.originalBytes
                )'''
    new = '''                val libraryRecord = BookLibraryStore.add(
                    applicationContext, book.sourceName, book.text, book.isFb2, book.originalBytes
                )'''
    if old not in s: raise SystemExit("v59: cannot locate imported library record")
    # Bind the active ID on the UI thread before reader content is synchronized.
    anchor = '''                    sourceName = book.sourceName
                    BookLibraryStore.markOpened(applicationContext, libraryRecord.id)'''
    replacement = '''                    sourceName = book.sourceName
                    currentLibraryBookId = libraryRecord.id
                    readerStartOffset = 0
                    lastPersistedReaderOffset = 0
                    lastObservedReaderOffset = 0
                    BookLibraryStore.markOpened(applicationContext, libraryRecord.id)'''
    if anchor not in s: raise SystemExit("v59: cannot bind newly imported library ID")
    s = s.replace(anchor, replacement, 1)

    # Restoring the last session also restores/creates its stable library record.
    old = '''                    if (!saved.isFb2 || saved.originalBytes != null) {
                        runCatching {
                            BookLibraryStore.add(
                                applicationContext, saved.name, saved.text, saved.isFb2,
                                saved.originalBytes ?: saved.text.toByteArray(Charsets.UTF_8)
                            )
                        }
                    }'''
    new = '''                    val restoredRecord = if (!saved.isFb2 || saved.originalBytes != null) {
                        runCatching {
                            BookLibraryStore.add(
                                applicationContext, saved.name, saved.text, saved.isFb2,
                                saved.originalBytes ?: saved.text.toByteArray(Charsets.UTF_8)
                            )
                        }.getOrNull()
                    } else null
                    currentLibraryBookId = restoredRecord?.id
                    readerStartOffset = restoredRecord?.let {
                        BookLibraryStore.readingPosition(applicationContext, it.id)
                    } ?: 0
                    lastPersistedReaderOffset = readerStartOffset
                    lastObservedReaderOffset = readerStartOffset'''
    if old not in s: raise SystemExit("v59: cannot locate last-session library restore")
    s = s.replace(old, new, 1)

    # Flush the most recent estimated position when the activity leaves the foreground.
    anchor = '''    override fun onDestroy() {'''
    addition = '''    override fun onStop() {
        currentLibraryBookId?.let { id ->
            runCatching {
                BookLibraryStore.saveReadingPosition(applicationContext, id, lastObservedReaderOffset)
            }
        }
        super.onStop()
    }

'''
    if anchor not in s: raise SystemExit("v59: cannot locate lifecycle insertion point")
    s = s.replace(anchor, addition + anchor, 1)
    main.write_text(s, encoding="utf-8")

print("v59: per-book reading positions are saved during scrolling and on app backgrounding.")
