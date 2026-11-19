from pathlib import Path
import re

root = Path("app/src/main/java/ru/fbaudioprep")
root.mkdir(parents=True, exist_ok=True)

theme = r'''package ru.fbaudioprep

import android.app.Activity
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.os.Build
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ProgressBar
import android.widget.TextView

/**
 * Audiotome visual system: deep midnight surfaces, restrained gold accents,
 * high-contrast typography and rounded controls. Applied after screens build
 * their existing view trees so business logic and navigation remain untouched.
 */
object AudiotomeTheme {
    val background = Color.rgb(5, 15, 27)
    val surface = Color.rgb(12, 26, 42)
    val surfaceRaised = Color.rgb(17, 35, 53)
    val gold = Color.rgb(231, 190, 103)
    val goldBright = Color.rgb(255, 211, 117)
    val text = Color.rgb(231, 237, 243)
    val muted = Color.rgb(145, 161, 176)
    val line = Color.rgb(43, 61, 78)

    fun apply(activity: Activity) {
        activity.window.statusBarColor = background
        activity.window.navigationBarColor = background
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            activity.window.decorView.systemUiVisibility = 0
        }
        val content = activity.findViewById<ViewGroup>(android.R.id.content) ?: return
        content.post { styleTree(content, 0) }
    }

    private fun styleTree(group: ViewGroup, depth: Int) {
        group.setBackgroundColor(if (depth == 0) background else Color.TRANSPARENT)
        for (index in 0 until group.childCount) {
            val child = group.getChildAt(index)
            when (child) {
                is Button -> styleButton(child)
                is EditText -> styleInput(child)
                is ProgressBar -> {
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
                        child.progressTintList = android.content.res.ColorStateList.valueOf(gold)
                        child.indeterminateTintList = android.content.res.ColorStateList.valueOf(gold)
                        child.progressBackgroundTintList = android.content.res.ColorStateList.valueOf(line)
                    }
                }
                is TextView -> styleText(child)
            }
            if (child is ViewGroup) styleTree(child, depth + 1)
        }
    }

    private fun styleText(view: TextView) {
        val originalSize = view.textSize / view.resources.displayMetrics.scaledDensity
        view.setTextColor(if (originalSize <= 12f) muted else text)
        if (originalSize >= 18f) {
            view.typeface = Typeface.create("sans-serif", Typeface.NORMAL)
        }
        view.highlightColor = gold
    }

    private fun styleButton(view: Button) {
        val label = view.text?.toString().orEmpty()
        val prominent = label.contains("Открыть", true) ||
            label.contains("Сохранить", true) ||
            label.contains("Начать", true) ||
            label.contains("Озвуч", true) ||
            label.contains("Продолж", true)
        view.setTextColor(if (prominent) background else goldBright)
        view.textSize = 13f
        view.typeface = Typeface.create("sans-serif-medium", Typeface.NORMAL)
        view.isAllCaps = false
        view.background = roundedFor(view,
            if (prominent) gold else surfaceRaised,
            if (prominent) gold else line,
            13f
        )
        view.setPadding(dp(view, 16), dp(view, 10), dp(view, 16), dp(view, 10))
        view.minHeight = dp(view, 44)
        view.stateListAnimator = null
    }

    private fun styleInput(view: EditText) {
        view.setTextColor(text)
        view.setHintTextColor(muted)
        view.background = roundedFor(view, surfaceRaised, line, 12f)
        view.setPadding(dp(view, 13), dp(view, 11), dp(view, 13), dp(view, 11))
    }

    private fun dp(view: View, value: Int): Int =
        (value * view.resources.displayMetrics.density).toInt()

    private fun roundedFor(view: View, fill: Int, stroke: Int, radius: Float) =
        GradientDrawable().apply {
            val density = view.resources.displayMetrics.density
            setColor(fill)
            cornerRadius = radius * density
            setStroke((density).toInt().coerceAtLeast(1), stroke)
        }
}
'''
# Remove the unused helper that depends on global density; keep the view-specific drawable.
theme = theme.replace('''    private fun rounded(fill: Int, stroke: Int, radius: Float) = GradientDrawable().apply {
        setColor(fill)
        cornerRadius = radius *  viewDensity
        setStroke((viewDensity).toInt().coerceAtLeast(1), stroke)
    }

    private var viewDensity = 1f

''','')
theme = theme.replace('view.background = rounded(\n            if (prominent) gold else surfaceRaised,\n            if (prominent) gold else line,\n            13f\n        )','view.background = roundedFor(view,\n            if (prominent) gold else surfaceRaised,\n            if (prominent) gold else line,\n            13f\n        )')
theme = theme.replace('view.background = rounded(surfaceRaised, line, 12f)','view.background = roundedFor(view, surfaceRaised, line, 12f)')
(root / "AudiotomeTheme.kt").write_text(theme, encoding="utf-8")

# Apply the same design system to the main screen after its existing content tree is installed.
main = root / "MainActivity.kt"
if not main.exists():
    raise SystemExit("v25: MainActivity.kt missing")
s = main.read_text(encoding="utf-8")
if "AudiotomeTheme.apply(this)" not in s:
    lines = s.splitlines()
    out = []
    for line in lines:
        out.append(line)
        if re.match(r"\s*setContentView\(", line):
            out.append(re.match(r"\s*", line).group(0) + "AudiotomeTheme.apply(this)")
    if not any("AudiotomeTheme.apply(this)" in line for line in out):
        raise SystemExit("v25: no setContentView call found in MainActivity")
    main.write_text("\n".join(out) + "\n", encoding="utf-8")

# Match the reader to the same midnight/gold palette, retaining its reader controls and behavior.
reader = root / "BookReaderActivity.kt"
if reader.exists():
    r = reader.read_text(encoding="utf-8")
    r = r.replace(
        'Colors(Color.rgb(250,248,243), Color.rgb(43,40,35), Color.rgb(125,117,105), Color.rgb(242,238,229), Color.rgb(139,104,68)),\n        Colors(Color.rgb(30,32,35), Color.rgb(229,228,222), Color.rgb(160,162,164), Color.rgb(39,42,46), Color.rgb(208,174,119)),\n        Colors(Color.rgb(239,229,207), Color.rgb(75,58,42), Color.rgb(137,112,84), Color.rgb(230,216,189), Color.rgb(139,94,54))',
        'Colors(Color.rgb(5,15,27), Color.rgb(231,237,243), Color.rgb(145,161,176), Color.rgb(12,26,42), Color.rgb(231,190,103)),\n        Colors(Color.rgb(3,10,19), Color.rgb(239,243,247), Color.rgb(130,148,166), Color.rgb(9,21,34), Color.rgb(255,211,117)),\n        Colors(Color.rgb(16,25,34), Color.rgb(235,229,215), Color.rgb(164,153,132), Color.rgb(25,37,48), Color.rgb(231,190,103))'
    )
    if "AudiotomeTheme.apply(this)" not in r:
        lines = r.splitlines()
        out = []
        for line in lines:
            out.append(line)
            if re.match(r"\s*setContentView\(", line):
                out.append(re.match(r"\s*", line).group(0) + "AudiotomeTheme.apply(this)")
        r = "\n".join(out) + "\n"
    reader.write_text(r, encoding="utf-8")

# Keep app identity/version coherent with the redesigned interface.
gradle = Path("app/build.gradle.kts")
g = gradle.read_text(encoding="utf-8")
m = re.search(r'versionCode\s*=\s*(\d+)\s*;\s*versionName\s*=\s*"([^"]+)"', g)
if m and m.group(2) == "2.1.3":
    g = g[:m.start()] + f'versionCode = {int(m.group(1)) + 1}; versionName = "2.1.4"' + g[m.end():]
    gradle.write_text(g, encoding="utf-8")

print("v25: applied the Audiotome midnight-and-gold visual system to the main app and reader.")
