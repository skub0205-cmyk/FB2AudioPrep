from pathlib import Path

p = Path("app/src/main/java/ru/fbaudioprep/MainActivity.kt")
s = p.read_text(encoding="utf-8")
if "showBookLibrary()" in s:
    print("v53 MainActivity changes already present")
    raise SystemExit(0)

open_button = '''        root.addView(Button(this).apply {
            text = "Открыть книгу"
            setOnClickListener { openBook() }
        })'''
if open_button not in s:
    raise SystemExit("v53: cannot find Open book button")
s = s.replace(open_button, open_button + '''

        root.addView(Button(this).apply {
            text = "Моя библиотека"
            setOnClickListener { showBookLibrary() }
        })''', 1)

import_anchor = '''                val book = BookImporter.read(contentResolver, uri, name)
                require(book.text.isNotBlank()) {'''
if import_anchor not in s:
    raise SystemExit("v53: cannot find import result")
s = s.replace(import_anchor, '''                val book = BookImporter.read(contentResolver, uri, name)
                val libraryRecord = BookLibraryStore.add(
                    applicationContext, book.sourceName, book.text, book.isFb2, book.originalBytes
                )
                require(book.text.isNotBlank()) {''', 1)

active_anchor = '''                    sourceName = book.sourceName
                    originalText = book.text'''
if active_anchor not in s:
    raise SystemExit("v53: cannot find active book assignment")
s = s.replace(active_anchor, '''                    sourceName = book.sourceName
                    BookLibraryStore.markOpened(applicationContext, libraryRecord.id)
                    originalText = book.text''', 1)

restore_anchor = '''                    sourceName = saved.name
                    originalText = saved.text'''
if restore_anchor in s:
    s = s.replace(restore_anchor, '''                    sourceName = saved.name
                    if (!saved.isFb2 || saved.originalBytes != null) {
                        runCatching {
                            BookLibraryStore.add(
                                applicationContext, saved.name, saved.text, saved.isFb2,
                                saved.originalBytes ?: saved.text.toByteArray(Charsets.UTF_8)
                            )
                        }
                    }
                    originalText = saved.text''', 1)

method = r'''    private fun showBookLibrary() {
        val books = BookLibraryStore.list(applicationContext)
        if (books.isEmpty()) {
            AlertDialog.Builder(this).setTitle("Моя библиотека")
                .setMessage("Пока нет добавленных книг. Нажмите «Открыть книгу», чтобы импортировать FB2 или TXT.")
                .setPositiveButton("Понятно", null).show()
            return
        }
        val labels = books.map { b ->
            buildString {
                append(b.title.ifBlank { b.sourceName })
                if (b.author.isNotBlank()) append("\\n").append(b.author)
                append("  ·  ").append(if (b.isFb2) "FB2" else "TXT")
                append("  ·  ").append(String.format(java.util.Locale.getDefault(), "%,d", b.textLength)).append(" знаков")
            }
        }.toTypedArray()
        AlertDialog.Builder(this).setTitle("Моя библиотека · ${books.size}")
            .setItems(labels) { _, which ->
                val selected = books[which]
                Thread({
                    try {
                        val text = BookLibraryStore.text(applicationContext, selected.id)
                        val original = BookLibraryStore.original(applicationContext, selected.id)
                        runOnUiThread {
                            sourceName = selected.sourceName
                            originalText = text
                            originalFb2Bytes = original.takeIf { selected.isFb2 }
                            processedFb2Bytes = null
                            currentBookIsFb2 = selected.isFb2
                            processedText = ""
                            ttsBookKey = MessageDigest.getInstance("SHA-256")
                                .digest(text.toByteArray(Charsets.UTF_8))
                                .joinToString("") { "%02x".format(it) }
                            dialogueFindings = DialogueCorrectionStore.apply(
                                this@MainActivity, text, DialogueFindingsStore.load(this@MainActivity, text)
                            )
                            BookLibraryStore.markOpened(applicationContext, selected.id)
                            accentButton.isEnabled = true
                            dialogueButton.isEnabled = true
                            reviewDialoguesButton.isEnabled = dialogueFindings.isNotEmpty()
                            teraManualPackButton.isEnabled = true
                            saveTextButton.isEnabled = false
                            saveFb2Button.isEnabled = false
                            refreshTtsResumeKey(loadSaved = true)
                            status.text = "Книга открыта из библиотеки: ${selected.title}\\nСимволов: ${text.length}"
                            syncReaderContent()
                        }
                    } catch (e: Throwable) {
                        runOnUiThread {
                            Toast.makeText(this, "Не удалось открыть книгу: ${e.message}", Toast.LENGTH_LONG).show()
                        }
                    }
                }, "open-library-book").start()
            }
            .setNegativeButton("Закрыть", null)
            .setNeutralButton("Удалить книгу") { _, _ -> showLibraryRemoveDialog() }
            .show()
    }

    private fun showLibraryRemoveDialog() {
        val books = BookLibraryStore.list(applicationContext)
        if (books.isEmpty()) return
        AlertDialog.Builder(this).setTitle("Удалить книгу из библиотеки")
            .setItems(books.map { it.title.ifBlank { it.sourceName } }.toTypedArray()) { _, which ->
                val book = books[which]
                AlertDialog.Builder(this).setTitle("Удалить книгу?")
                    .setMessage("Будут удалены только файлы книги «${book.title}». Скачанные модели и настройки приложения останутся.")
                    .setNegativeButton("Отмена", null)
                    .setPositiveButton("Удалить") { _, _ ->
                        BookLibraryStore.remove(applicationContext, book.id)
                        Toast.makeText(this, "Книга удалена из библиотеки", Toast.LENGTH_SHORT).show()
                    }.show()
            }.setNegativeButton("Отмена", null).show()
    }

'''
load_anchor = "    private fun load(uri: Uri) {"
if load_anchor not in s:
    raise SystemExit("v53: cannot find load(uri) insertion point")
s = s.replace(load_anchor, method + load_anchor, 1)
p.write_text(s, encoding="utf-8")
print("v53: persistent library UI and import/restore integration applied")
