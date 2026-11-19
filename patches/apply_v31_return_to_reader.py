from pathlib import Path

p = Path("app/src/main/java/ru/fbaudioprep/AudiotomeHomeLayout.kt")
s = p.read_text(encoding="utf-8")
needle = '''            panel.addView(subtitle)
            if (actions.isEmpty()) {'''
replacement = '''            panel.addView(subtitle)
            val returnToReader = TextView(activity).apply {
                text = "←  Вернуться к чтению"
                textSize = 13f
                setTextColor(AudiotomeTheme.goldBright)
                setPadding(dp(activity, 14), dp(activity, 11), dp(activity, 14), dp(activity, 11))
                background = GradientDrawable().apply {
                    setColor(AudiotomeTheme.surfaceRaised)
                    cornerRadius = dp(activity, 11).toFloat()
                    setStroke(dp(activity, 1), AudiotomeTheme.line)
                }
                isClickable = true
                isFocusable = true
                setOnClickListener {
                    sectionHost.removeAllViews()
                    sectionHost.addView(paper, FrameLayout.LayoutParams(-1, -1))
                }
            }
            val returnParams = LinearLayout.LayoutParams(-1, -2)
            returnParams.bottomMargin = dp(activity, 12)
            panel.addView(returnToReader, returnParams)
            if (actions.isEmpty()) {'''
if needle not in s:
    raise SystemExit("Could not find section subtitle insertion point")
s=s.replace(needle,replacement,1)
p.write_text(s,encoding="utf-8")
print("v31: add a clear return-to-book action on every section page.")
