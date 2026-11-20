from pathlib import Path
import re

p = Path("app/src/main/java/ru/fbaudioprep/MainActivity.kt")
s = p.read_text(encoding="utf-8")
start = s.find("    private fun showBookLibrary() {")
end = s.find("    private fun showLibraryRemoveDialog() {", start)
if start < 0 or end < 0:
    raise SystemExit("v54: cannot locate library dialog methods")
if "v54-searchable-library" in s:
    print("v54 already applied")
    raise SystemExit(0)

method = r'''    // v54-searchable-library: searchable, scrollable library instead of a fixed AlertDialog item list.
    private fun showBookLibrary() {
        val allBooks = BookLibraryStore.list(applicationContext)
        val panel = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding((20 * resources.displayMetrics.density).toInt(), (8 * resources.displayMetrics.density).toInt(),
                (20 * resources.displayMetrics.density).toInt(), 0)
        }
        val search = EditText(this).apply {
            hint = "Поиск по названию, автору или имени файла"
            singleLine = true
            textSize = 15f
        }
        panel.addView(search, LinearLayout.LayoutParams(-1, -2))
        val count = TextView(this).apply {
            textSize = 12f
            setPadding(0, (8 * resources.displayMetrics.density).toInt(), 0, (8 * resources.displayMetrics.density).toInt())
            setTextColor(0xFF9AA8B5.toInt())
        }
        panel.addView(count)
        val list = android.widget.ListView(this).apply {
            dividerHeight = (resources.displayMetrics.density).toInt()
        }
        panel.addView(list, LinearLayout.LayoutParams(-1, 0, 1f))
        val dialog = AlertDialog.Builder(this)
            .setTitle("Моя библиотека")
            .setView(panel)
            .setPositiveButton("Добавить книгу", null)
            .setNeutralButton("Удалить", null)
            .setNegativeButton("Закрыть", null)
            .create()

        var visibleBooks = allBooks
        fun render(query: String) {
            val q = query.trim().lowercase(java.util.Locale.ROOT)
            visibleBooks = if (q.isBlank()) allBooks else allBooks.filter { b ->
                b.title.lowercase(java.util.Locale.ROOT).contains(q) ||
                    b.author.lowercase(java.util.Locale.ROOT).contains(q) ||
                    b.sourceName.lowercase(java.util.Locale.ROOT).contains(q)
            }
            count.text = if (q.isBlank()) "Книг в библиотеке: ${allBooks.size}" else
                "Найдено: ${visibleBooks.size} из ${allBooks.size}"
            val labels = visibleBooks.map { b ->
                buildString {
                    append(b.title.ifBlank { b.sourceName })
                    if (b.author.isNotBlank()) append("\n").append(b.author)
                    append("\n").append(if (b.isFb2) "FB2" else "TXT")
                    append(" · ").append(String.format(java.util.Locale.getDefault(), "%,d", b.textLength)).append(" знаков")
                }
            }
            list.adapter = android.widget.ArrayAdapter(this, android.R.layout.simple_list_item_1, labels)
        }
        render("")
        search.addTextChangedListener(object : android.text.TextWatcher {
            override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) = Unit
            override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) = render(s?.toString().orEmpty())
            override fun afterTextChanged(s: android.text.Editable?) = Unit
        })
        list.setOnItemClickListener { _, _, position, _ ->
            val selected = visibleBooks.getOrNull(position) ?: return@setOnItemClickListener
            dialog.dismiss()
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
                        status.text = "Книга открыта из библиотеки: ${selected.title}\nСимволов: ${text.length}"
                        syncReaderContent()
                    }
                } catch (e: Throwable) {
                    runOnUiThread {
                        Toast.makeText(this, "Не удалось открыть книгу: ${e.message}", Toast.LENGTH_LONG).show()
                    }
                }
            }, "open-library-book").start()
        }
        dialog.setOnShowListener {
            dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener {
                dialog.dismiss()
                openBook()
            }
            dialog.getButton(AlertDialog.BUTTON_NEUTRAL).setOnClickListener {
                dialog.dismiss()
                showLibraryRemoveDialog()
            }
        }
        dialog.show()
    }

'''
s = s[:start] + method + s[end:]
p.write_text(s, encoding="utf-8")
print("v54: searchable library, live filtering by title/author/file name, scrollable book list, add/remove actions.")
