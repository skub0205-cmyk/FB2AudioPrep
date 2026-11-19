from pathlib import Path

p = Path("app/src/main/java/ru/fbaudioprep/AudiotomeHomeLayout.kt")
s = p.read_text(encoding="utf-8")

old = '''        header.addView(bookTitle)
        status?.let { liveStatus ->
            liveStatus.textSize = 11f
            liveStatus.setTextColor(AudiotomeTheme.muted)
            liveStatus.setPadding(0, dp(activity, 3), 0, 0)
            liveStatus.maxLines = 2
            header.addView(liveStatus, LinearLayout.LayoutParams(-1, -2))
        }
        content.addView(header, LinearLayout.LayoutParams(-1, -2))

        val paper = FrameLayout(activity).apply {
            background = GradientDrawable().apply {
                setColor(Color.rgb(239, 232, 216))
                cornerRadius = dp(activity, 15).toFloat()
                setStroke(dp(activity, 1), Color.rgb(205, 194, 172))
            }
            setPadding(dp(activity, 17), dp(activity, 16), dp(activity, 17), dp(activity, 16))
        }'''
new = '''        val headerRow = LinearLayout(activity).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
        }
        headerRow.addView(bookTitle, LinearLayout.LayoutParams(0, -2, 1f))
        val paper = FrameLayout(activity).apply {
            background = GradientDrawable().apply {
                setColor(Color.rgb(239, 232, 216))
                cornerRadius = dp(activity, 15).toFloat()
                setStroke(dp(activity, 1), Color.rgb(205, 194, 172))
            }
            setPadding(dp(activity, 17), dp(activity, 16), dp(activity, 17), dp(activity, 16))
        }
        val readingText = previewText ?: TextView(activity).apply {
            text = "Откройте книгу, чтобы начать чтение."
        }
        var darkPaper = false
        val themeToggle = TextView(activity).apply {
            text = "Aa"
            textSize = 16f
            gravity = Gravity.CENTER
            setTextColor(AudiotomeTheme.goldBright)
            setPadding(dp(activity, 12), dp(activity, 7), dp(activity, 12), dp(activity, 7))
            background = GradientDrawable().apply {
                setColor(AudiotomeTheme.surfaceRaised)
                cornerRadius = dp(activity, 10).toFloat()
                setStroke(dp(activity, 1), AudiotomeTheme.line)
            }
            contentDescription = "Переключить тему страницы"
            setOnClickListener {
                darkPaper = !darkPaper
                val pageColor = if (darkPaper) Color.rgb(26, 35, 45) else Color.rgb(239, 232, 216)
                val inkColor = if (darkPaper) Color.rgb(229, 232, 235) else Color.rgb(48, 43, 36)
                val borderColor = if (darkPaper) Color.rgb(58, 72, 88) else Color.rgb(205, 194, 172)
                paper.background = GradientDrawable().apply {
                    setColor(pageColor)
                    cornerRadius = dp(activity, 15).toFloat()
                    setStroke(dp(activity, 1), borderColor)
                }
                readingText.setTextColor(inkColor)
            }
        }
        headerRow.addView(themeToggle, LinearLayout.LayoutParams(-2, -2))
        header.addView(headerRow, LinearLayout.LayoutParams(-1, -2))
        status?.let { liveStatus ->
            liveStatus.textSize = 11f
            liveStatus.setTextColor(AudiotomeTheme.muted)
            liveStatus.setPadding(0, dp(activity, 3), 0, 0)
            liveStatus.maxLines = 2
            header.addView(liveStatus, LinearLayout.LayoutParams(-1, -2))
        }
        content.addView(header, LinearLayout.LayoutParams(-1, -2))'''
if old not in s:
    raise SystemExit("Could not find reader header/paper block for theme switch")
s = s.replace(old, new, 1)

old2 = '''        val readingText = previewText ?: TextView(activity).apply {
            text = "Откройте книгу, чтобы начать чтение."
        }
        readingText.apply {'''
# Remove second declaration now moved above paper toggle
if old2 not in s:
    raise SystemExit("Could not find duplicate reading text declaration")
s = s.replace(old2, '''        readingText.apply {''', 1)

p.write_text(s, encoding="utf-8")
print("v29: add a one-tap warm-paper/dark-paper reader switch.")
