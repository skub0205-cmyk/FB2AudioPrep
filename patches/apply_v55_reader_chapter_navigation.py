from pathlib import Path

p = Path("app/src/main/java/ru/fbaudioprep/AudiotomeHomeLayout.kt")
s = p.read_text(encoding="utf-8")
if "v55-fb2-chapter-navigation" in s:
    print("v55 already applied")
    raise SystemExit(0)

s = s.replace(
    "fun compose(activity: Activity, oldRoot: LinearLayout): View {",
    "fun compose(activity: Activity, oldRoot: LinearLayout, bookContent: () -> String = { \"\" }): View {",
    1
)
anchor = '''        headerRow.addView(themeToggle, LinearLayout.LayoutParams(-2, -2))
        header.addView(headerRow, LinearLayout.LayoutParams(-1, -2))'''
if anchor not in s:
    raise SystemExit("v55: cannot find reader header controls")

replacement = '''        // v55-fb2-chapter-navigation: chapter list is derived from the complete book,
        // while only the selected 8K-character window is rendered to keep large books light.
        val contentsButton = TextView(activity).apply {
            text = "☷"
            textSize = 20f
            gravity = Gravity.CENTER
            setTextColor(AudiotomeTheme.goldBright)
            setPadding(dp(activity, 10), dp(activity, 7), dp(activity, 10), dp(activity, 7))
            contentDescription = "Содержание книги"
            setOnClickListener {
                val fullText = bookContent()
                if (fullText.isBlank()) {
                    android.widget.Toast.makeText(activity, "Сначала откройте книгу", android.widget.Toast.LENGTH_SHORT).show()
                } else {
                    val chapters = mutableListOf<Pair<String, Int>>()
                    var offset = 0
                    fullText.split('\\n').forEach { line ->
                        val value = line.trim()
                        val isHeading = value.matches(Regex("(?i)^(глава|часть|пролог|эпилог|интерлюдия)(\\\\s+.*)?$")) ||
                            value.matches(Regex("^\\\\d{1,3}[.)]?\\\\s+.{2,90}$"))
                        if (isHeading && value.length <= 110) chapters.add(value to offset)
                        offset += line.length + 1
                    }
                    if (chapters.isEmpty()) {
                        android.widget.Toast.makeText(activity, "Заголовки глав не найдены", android.widget.Toast.LENGTH_SHORT).show()
                    } else {
                        val labels = chapters.map { it.first }.toTypedArray()
                        AlertDialog.Builder(activity)
                            .setTitle("Содержание · ${chapters.size} разделов")
                            .setItems(labels) { dialog, which ->
                                val start = chapters[which].second.coerceIn(0, fullText.length)
                                val end = (start + 8000).coerceAtMost(fullText.length)
                                readingText.text = fullText.substring(start, end)
                                readingText.contentDescription = end.toString()
                                paperScroll.scrollTo(0, 0)
                                paperScroll.post { paperScroll.scrollTo(0, 0) }
                            }
                            .setNegativeButton("Закрыть", null)
                            .show()
                    }
                }
            }
        }
        headerRow.addView(contentsButton, LinearLayout.LayoutParams(-2, -2))
        headerRow.addView(themeToggle, LinearLayout.LayoutParams(-2, -2))
        header.addView(headerRow, LinearLayout.LayoutParams(-1, -2))'''
s = s.replace(anchor, replacement, 1)
p.write_text(s, encoding="utf-8")

p = Path("app/src/main/java/ru/fbaudioprep/MainActivity.kt")
s = p.read_text(encoding="utf-8")
old = "setContentView(AudiotomeHomeLayout.compose(this, root))"
if old not in s:
    raise SystemExit("v55: cannot find AudiotomeHomeLayout.compose call")
s = s.replace(old, "setContentView(AudiotomeHomeLayout.compose(this, root) { processedText.ifBlank { originalText } })", 1)
p.write_text(s, encoding="utf-8")
print("v55: added FB2/text chapter navigation to the main book-first reader.")
