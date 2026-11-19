from pathlib import Path

base = Path("app/src/main/java/ru/fbaudioprep")
main = base / "MainActivity.kt"
s = main.read_text(encoding="utf-8")
old_scroll = """setContentView(ScrollView(this).apply {
            isFillViewport = true
            addView(root)
        })"""
if "AudiotomeHomeLayout.compose(this, root)" not in s:
    if old_scroll in s:
        s = s.replace(old_scroll, """setContentView(AudiotomeHomeLayout.compose(this, root))
        AudiotomeTheme.apply(this)""", 1)
    elif "setContentView(root)" in s:
        s = s.replace("setContentView(root)", "setContentView(AudiotomeHomeLayout.compose(this, root))\\n        AudiotomeTheme.apply(this)", 1)
    else:
        raise SystemExit("Could not locate MainActivity root container")
main.write_text(s, encoding="utf-8")

layout = r'''package ru.fbaudioprep

import android.app.Activity
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView

/** Re-composes existing controls; their click listeners and state remain intact. */
object AudiotomeHomeLayout {
    fun compose(activity: Activity, oldRoot: LinearLayout): View {
        val children = (0 until oldRoot.childCount).map { oldRoot.getChildAt(it) }
        oldRoot.removeAllViews()
        val scroll = ScrollView(activity).apply { isFillViewport = true; clipToPadding = false }
        val page = LinearLayout(activity).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(activity, 20), dp(activity, 22), dp(activity, 20), dp(activity, 28))
            setBackgroundColor(AudiotomeTheme.background)
        }
        scroll.addView(page, ScrollView.LayoutParams(-1, -2))

        val title = children.firstOrNull { it is TextView } as? TextView
        val status = children.drop(1).firstOrNull { it is TextView } as? TextView
        val preview = children.firstOrNull { it is ScrollView } as? ScrollView
        val buttons = children.filterIsInstance<Button>()

        val brand = LinearLayout(activity).apply { orientation = LinearLayout.VERTICAL; setPadding(0, dp(activity, 4), 0, dp(activity, 16)) }
        brand.addView(TextView(activity).apply {
            text = "FB2 AUDIOPREP"; textSize = 25f; letterSpacing = 0.08f
            setTextColor(AudiotomeTheme.goldBright)
            typeface = Typeface.create("sans-serif-medium", Typeface.NORMAL)
        })
        brand.addView(TextView(activity).apply {
            text = "Подготовка книг и создание аудиокниг"; textSize = 13f
            setTextColor(AudiotomeTheme.muted); setPadding(0, dp(activity, 5), 0, 0)
        })
        page.addView(brand)
        title?.visibility = View.GONE
        status?.let {
            it.setTextColor(AudiotomeTheme.text); it.textSize = 14f
            it.setPadding(dp(activity, 14), dp(activity, 12), dp(activity, 14), dp(activity, 12))
            card(page, activity, "ТЕКУЩАЯ КНИГА").addView(it)
        }

        val library = mutableListOf<Button>()
        val people = mutableListOf<Button>()
        val process = mutableListOf<Button>()
        val exports = mutableListOf<Button>()
        buttons.forEach { b ->
            val label = b.text?.toString().orEmpty().lowercase()
            when {
                label.contains("открыть книгу") -> library.add(b)
                listOf("персонаж", "голос", "диалог", "говорящ").any { label.contains(it) } -> people.add(b)
                listOf("сохран", "экспорт", "отчёт", "отчет").any { label.contains(it) } -> exports.add(b)
                else -> process.add(b)
            }
        }
        section(page, activity, "БИБЛИОТЕКА", library)
        section(page, activity, "ПЕРСОНАЖИ И ДИАЛОГИ", people)
        section(page, activity, "ОБРАБОТКА КНИГИ", process)
        section(page, activity, "ЭКСПОРТ И ОТЧЁТЫ", exports)
        preview?.let {
            val c = card(page, activity, "ПРЕДПРОСМОТР")
            c.addView(it, LinearLayout.LayoutParams(-1, dp(activity, 260)))
        }
        return scroll
    }

    private fun section(page: LinearLayout, activity: Activity, heading: String, controls: List<Button>) {
        if (controls.isEmpty()) return
        val c = card(page, activity, heading)
        controls.forEach { b ->
            val lp = LinearLayout.LayoutParams(-1, -2); lp.topMargin = dp(activity, 7)
            c.addView(b, lp)
        }
    }

    private fun card(page: LinearLayout, activity: Activity, heading: String): LinearLayout {
        val c = LinearLayout(activity).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(activity, 14), dp(activity, 13), dp(activity, 14), dp(activity, 14))
            background = GradientDrawable().apply {
                setColor(AudiotomeTheme.surface); cornerRadius = dp(activity, 18).toFloat()
                setStroke(dp(activity, 1), AudiotomeTheme.line)
            }
        }
        c.addView(TextView(activity).apply {
            text = heading; textSize = 11f; letterSpacing = 0.12f
            setTextColor(AudiotomeTheme.gold)
            typeface = Typeface.create("sans-serif-medium", Typeface.NORMAL)
        })
        val lp = LinearLayout.LayoutParams(-1, -2); lp.bottomMargin = dp(activity, 12)
        page.addView(c, lp)
        return c
    }
    private fun dp(a: Activity, v: Int) = (v * a.resources.displayMetrics.density).toInt()
}
'''
(base / "AudiotomeHomeLayout.kt").write_text(layout, encoding="utf-8")
print("v26: created structured Audiotome home screen cards without changing existing actions.")
