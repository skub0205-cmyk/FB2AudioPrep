from pathlib import Path
import re

base = Path("app/src/main/java/ru/fbaudioprep")
main = base / "MainActivity.kt"
s = main.read_text(encoding="utf-8")

# Keep the complete book on the reader page; reports must not replace the book text.
reader = '''    private fun openBookPreview() {
        if (originalText.isBlank()) {
            Toast.makeText(this, "Сначала откройте книгу", Toast.LENGTH_SHORT).show()
            return
        }
        preview.text = processedText.ifBlank { originalText }
        preview.visibility = android.view.View.VISIBLE
        preview.requestLayout()
        preview.post { (preview.parent as? ScrollView)?.scrollTo(0, 0) }
        status.text = status.text.toString()
            .replace("\\nОткрываю читалку…", "")
            .replace("\\nОткрываю книгу в читалке…", "")
    }

'''
start_reader = s.find("    private fun openBookPreview() {")
end_reader = s.find("    private fun openBook()", start_reader)
if start_reader < 0 or end_reader < 0:
    raise SystemExit("v36: cannot replace openBookPreview()")
s = s[:start_reader] + reader + s[end_reader:]

s = s.replace("preview.text = dialogueReport.take(8000)", "preview.text = processedText.ifBlank { originalText }")
s = s.replace("preview.text = processedText.take(8000)", "preview.text = processedText")

# v27 expects the preview TextView to be attached inside a ScrollView before it
# re-composes the home screen. v10 removed that container when it moved reading
# to BookReaderActivity; v32 later restored in-place reading but did not restore
# this view attachment. This missing parent was the blank-book regression.
if 'root.addView(ScrollView(this).apply { addView(preview) }' not in s:
    attach_anchor = '''        preview = TextView(this).apply {
            textSize = 14f
            setPadding(0, 14, 0, 14)
            text = "Здесь появится предпросмотр книги."
        }
'''
    attach = attach_anchor + '''        root.addView(
            ScrollView(this).apply {
                isFillViewport = false
                addView(preview)
            },
            LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f)
        )
'''
    if attach_anchor not in s:
        raise SystemExit("v36: cannot find preview TextView initialization")
    s = s.replace(attach_anchor, attach, 1)

# Full-screen review workspace: replica cards, character cards and uncertainty filters.
start = s.find("    private fun showDialogueReview() {")
end = s.find("\n    private fun editFindingSpeaker", start)
if start < 0 or end < 0:
    raise SystemExit("v36: cannot locate showDialogueReview()")
method = r'''    private fun showDialogueReview() {
        if (dialogueFindings.isEmpty()) {
            Toast.makeText(this, "Сначала запустите анализ диалогов", Toast.LENGTH_SHORT).show()
            return
        }
        val dialog = android.app.Dialog(this)
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(18, 16, 18, 12)
            setBackgroundColor(AudiotomeTheme.background)
        }
        fun textView(value: String, size: Float, color: Int, bold: Boolean = false): TextView =
            TextView(this).apply {
                text = value
                textSize = size
                setTextColor(color)
                if (bold) typeface = android.graphics.Typeface.create("sans-serif-medium", android.graphics.Typeface.NORMAL)
                setPadding(2, 3, 2, 3)
            }
        fun actionButton(value: String, onClick: () -> Unit): Button = Button(this).apply {
            text = value
            isAllCaps = false
            setOnClickListener { onClick() }
        }
        root.addView(textView("Проверка диалогов", 21f, AudiotomeTheme.text, true))
        val summary = textView("", 12f, AudiotomeTheme.muted)
        root.addView(summary)
        val tabs = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        root.addView(tabs)
        val filters = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        root.addView(filters)
        val scroll = ScrollView(this).apply { isFillViewport = true }
        val cards = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(0, 6, 0, 8)
        }
        scroll.addView(cards, ViewGroup.LayoutParams(-1, -2))
        root.addView(scroll, LinearLayout.LayoutParams(-1, 0, 1f))
        val footer = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        footer.addView(actionButton("Отчёт TXT") {
            dialog.dismiss()
            if (report.isBlank()) refreshDialogueReport()
            createDocument(saveReportId, "text/plain", "FB2AudioPrep-dialogues.txt")
        }, LinearLayout.LayoutParams(0, -2, 1f))
        footer.addView(actionButton("Готово") {
            refreshDialogueReport()
            dialog.dismiss()
        }, LinearLayout.LayoutParams(0, -2, 1f))
        root.addView(footer)

        var selectedTab = 0
        var selectedFilter = 0
        val filterNames = listOf("Все", "Сомнительные", "Без говорящего")
        lateinit var render: () -> Unit

        fun card(titleText: String): LinearLayout = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(14, 12, 14, 12)
            background = android.graphics.drawable.GradientDrawable().apply {
                setColor(AudiotomeTheme.surfaceRaised)
                cornerRadius = 14f
                setStroke(1, AudiotomeTheme.line)
            }
            addView(textView(titleText, 15f, AudiotomeTheme.text, true))
        }
        fun addLine(parent: LinearLayout, value: String) {
            parent.addView(textView(value, 12f, AudiotomeTheme.muted))
        }
        fun refreshTabs() {
            tabs.removeAllViews()
            listOf("Реплики (${dialogueFindings.size})", "Персонажи (${loadCharactersForBook(originalText).size})")
                .forEachIndexed { index, label ->
                    val button = actionButton(label) {
                        selectedTab = index
                        render.invoke()
                    }
                    button.alpha = if (selectedTab == index) 1f else 0.65f
                    tabs.addView(button, LinearLayout.LayoutParams(0, -2, 1f))
                }
        }
        fun refreshFilters() {
            filters.removeAllViews()
            if (selectedTab != 0) return
            filterNames.forEachIndexed { index, label ->
                val button = actionButton(label) {
                    selectedFilter = index
                    render.invoke()
                }
                button.alpha = if (selectedFilter == index) 1f else 0.6f
                filters.addView(button, LinearLayout.LayoutParams(0, -2, 1f))
            }
        }
        render = {
            val findings = dialogueFindings
            val assigned = findings.count { !it.speaker.isNullOrBlank() }
            val uncertain = findings.count { it.speaker.isNullOrBlank() || it.confidence < 0.70f }
            summary.text = "Найдено: ${findings.size}   ·   Назначено: $assigned   ·   Проверить: $uncertain"
            refreshTabs()
            refreshFilters()
            cards.removeAllViews()
            if (selectedTab == 0) {
                val visible = findings.mapIndexed { index, finding -> index to finding }.filter { (_, finding) ->
                    when (selectedFilter) {
                        1 -> finding.speaker.isNullOrBlank() || finding.confidence < 0.70f
                        2 -> finding.speaker.isNullOrBlank()
                        else -> true
                    }
                }
                if (visible.isEmpty()) {
                    cards.addView(card("Ничего не найдено по выбранному фильтру").apply {
                        addLine(this, "Попробуйте выбрать «Все».")
                    })
                }
                visible.forEach { (index, finding) ->
                    val item = card("${index + 1}. ${finding.speaker ?: "Не определён"}")
                    addLine(item, "Голос: ${finding.voice ?: "не определён"}   ·   Уверенность: ${(finding.confidence * 100).toInt()}%")
                    if (!finding.addressedTo.isNullOrBlank()) addLine(item, "Обращение к: ${finding.addressedTo}")
                    addLine(item, "Основание: ${finding.reason}")
                    item.addView(textView(finding.fragment, 14f, AudiotomeTheme.text))
                    item.addView(actionButton("Изменить говорящего / голос") {
                        dialog.dismiss()
                        editFindingSpeaker(index, loadCharactersForBook(originalText))
                    })
                    val lp = LinearLayout.LayoutParams(-1, -2)
                    lp.bottomMargin = 9
                    cards.addView(item, lp)
                }
            } else {
                val profiles = loadCharactersForBook(originalText)
                if (profiles.isEmpty()) {
                    cards.addView(card("Персонажи пока не найдены").apply {
                        addLine(this, "Можно добавить персонажа вручную.")
                    })
                }
                profiles.forEach { profile ->
                    val count = findings.count { it.speaker == profile.name }
                    val item = card(profile.name)
                    addLine(item, "Голос: ${profile.voice}   ·   Реплик: $count")
                    if (profile.aliases.isNotEmpty()) addLine(item, "Варианты имени: ${profile.aliases.joinToString()}")
                    item.addView(actionButton("Настроить персонажа и голос") {
                        dialog.dismiss()
                        editCharacter(profile) { showDialogueReview() }
                    })
                    val lp = LinearLayout.LayoutParams(-1, -2)
                    lp.bottomMargin = 9
                    cards.addView(item, lp)
                }
                cards.addView(actionButton("＋ Добавить персонажа") {
                    dialog.dismiss()
                    editCharacter(null) { showDialogueReview() }
                })
            }
        }
        render.invoke()
        dialog.setContentView(root)
        dialog.setOnDismissListener { refreshDialogueReport() }
        dialog.show()
        dialog.window?.setLayout(
            (resources.displayMetrics.widthPixels * 0.96f).toInt(),
            (resources.displayMetrics.heightPixels * 0.92f).toInt()
        )
    }
'''
s = s[:start] + method + s[end:]

# Keep report generation separate from the book reader.
s = s.replace("preview.text = dialogueReport.take(8000)", "preview.text = processedText.ifBlank { originalText }")
s = s.replace("reviewDialoguesButton.isEnabled = findings.isNotEmpty()", "reviewDialoguesButton.isEnabled = originalText.isNotBlank()")

main.write_text(s, encoding="utf-8")

gradle = Path("app/build.gradle.kts")
g = gradle.read_text(encoding="utf-8")
m = re.search(r'versionCode\s*=\s*(\d+)\s*;\s*versionName\s*=\s*"([^"]+)"', g)
if not m:
    raise SystemExit("v36: cannot locate versionCode/versionName")
g = g[:m.start()] + f'versionCode = {int(m.group(1)) + 1}; versionName = "2.1.4"' + g[m.end():]
gradle.write_text(g, encoding="utf-8")
print("v36: preserve full book reading and add dialogue/character review workspace.")
