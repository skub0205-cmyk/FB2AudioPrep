from pathlib import Path

base = Path("app/src/main/java/ru/fbaudioprep")
layout_path = base / "AudiotomeHomeLayout.kt"
layout = r'''package ru.fbaudioprep

import android.app.Activity
import android.app.AlertDialog
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView

/**
 * Book-first Audiotome shell. Existing action buttons are retained and opened
 * from compact icon navigation, while the book preview becomes the main surface.
 */
object AudiotomeHomeLayout {
    private fun dp(a: Activity, value: Int): Int =
        (value * a.resources.displayMetrics.density).toInt()

    fun compose(activity: Activity, oldRoot: LinearLayout): View {
        val children = (0 until oldRoot.childCount).map { oldRoot.getChildAt(it) }
        oldRoot.removeAllViews()

        val title = children.firstOrNull { it is TextView } as? TextView
        val status = children.drop(1).firstOrNull { it is TextView } as? TextView
        val previewScroll = children.firstOrNull { it is ScrollView } as? ScrollView
        val previewText = previewScroll?.let { sc ->
            (0 until sc.childCount).map { sc.getChildAt(it) }.firstOrNull { it is TextView } as? TextView
        }
        val buttons = children.filterIsInstance<Button>()
        val library = buttons.filter { it.text.toString().contains("Открыть книгу", true) }
        val people = buttons.filter {
            listOf("Персонажи", "голос", "диалог", "говорящ").any { token -> it.text.toString().contains(token, true) }
        }
        val preparation = buttons.filter { it !in library && it !in people }

        title?.visibility = View.GONE
        previewScroll?.removeAllViews()

        val shell = LinearLayout(activity).apply {
            orientation = LinearLayout.HORIZONTAL
            setBackgroundColor(AudiotomeTheme.background)
            layoutParams = ViewGroup.LayoutParams(-1, -1)
        }

        val rail = LinearLayout(activity).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.TOP or Gravity.CENTER_HORIZONTAL
            setPadding(dp(activity, 5), dp(activity, 14), dp(activity, 5), dp(activity, 10))
            setBackgroundColor(Color.rgb(8, 20, 34))
        }
        shell.addView(rail, LinearLayout.LayoutParams(dp(activity, 62), -1))

        val content = LinearLayout(activity).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(activity, 12), dp(activity, 12), dp(activity, 12), dp(activity, 10))
            setBackgroundColor(AudiotomeTheme.background)
        }
        shell.addView(content, LinearLayout.LayoutParams(0, -1, 1f))

        val header = LinearLayout(activity).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(activity, 4), dp(activity, 2), dp(activity, 4), dp(activity, 10))
        }
        val appTitle = TextView(activity).apply {
            text = "AUDIOTOME"
            textSize = 10f
            letterSpacing = 0.22f
            setTextColor(AudiotomeTheme.gold)
            typeface = Typeface.create("sans-serif-medium", Typeface.NORMAL)
        }
        header.addView(appTitle)
        val bookTitle = TextView(activity).apply {
            text = if (status?.text.isNullOrBlank()) "Ваша библиотека" else status?.text?.toString()?.lineSequence()?.firstOrNull().orEmpty()
            textSize = 18f
            setTextColor(AudiotomeTheme.text)
            typeface = Typeface.create("sans-serif-medium", Typeface.NORMAL)
            setPadding(0, dp(activity, 3), 0, 0)
            maxLines = 1
            ellipsize = android.text.TextUtils.TruncateAt.END
        }
        header.addView(bookTitle)
        content.addView(header, LinearLayout.LayoutParams(-1, -2))

        val paper = FrameLayout(activity).apply {
            background = GradientDrawable().apply {
                setColor(Color.rgb(239, 232, 216))
                cornerRadius = dp(activity, 15).toFloat()
                setStroke(dp(activity, 1), Color.rgb(205, 194, 172))
            }
            setPadding(dp(activity, 17), dp(activity, 16), dp(activity, 17), dp(activity, 16))
        }
        val paperScroll = ScrollView(activity).apply {
            tag = "audiotome-paper-scroll"
            isFillViewport = false
            clipToPadding = false
            setBackgroundColor(Color.TRANSPARENT)
        }
        val readingText = previewText ?: TextView(activity).apply {
            text = "Откройте книгу, чтобы начать чтение."
        }
        readingText.apply {
            tag = "audiotome-paper-text"
            textSize = 18f
            setTextColor(Color.rgb(48, 43, 36))
            typeface = Typeface.create("serif", Typeface.NORMAL)
            setLineSpacing(dp(activity, 5).toFloat(), 1.04f)
            setPadding(0, 0, 0, dp(activity, 12))
        }
        paperScroll.addView(readingText, ViewGroup.LayoutParams(-1, -2))
        paper.addView(paperScroll, FrameLayout.LayoutParams(-1, -1))
        content.addView(paper, LinearLayout.LayoutParams(-1, 0, 1f))

        val footer = LinearLayout(activity).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(activity, 4), dp(activity, 9), dp(activity, 4), 0)
        }
        val footerText = TextView(activity).apply {
            text = "ЧТЕНИЕ  ·  ПОДГОТОВКА ТЕКСТА  ·  ОФЛАЙН"
            textSize = 9f
            letterSpacing = 0.08f
            setTextColor(AudiotomeTheme.muted)
        }
        footer.addView(footerText)
        content.addView(footer, LinearLayout.LayoutParams(-1, -2))

        fun addNav(glyph: String, caption: String, actions: List<Button>, emptyMessage: String? = null) {
            val item = LinearLayout(activity).apply {
                orientation = LinearLayout.VERTICAL
                gravity = Gravity.CENTER
                setPadding(0, dp(activity, 9), 0, dp(activity, 9))
                isClickable = true
                isFocusable = true
                background = GradientDrawable().apply {
                    setColor(Color.TRANSPARENT)
                    cornerRadius = dp(activity, 12).toFloat()
                }
                contentDescription = caption
            }
            val icon = TextView(activity).apply {
                text = glyph
                textSize = 22f
                gravity = Gravity.CENTER
                setTextColor(AudiotomeTheme.goldBright)
                typeface = Typeface.create("sans-serif", Typeface.NORMAL)
            }
            item.addView(icon, LinearLayout.LayoutParams(-1, dp(activity, 29)))
            val label = TextView(activity).apply {
                text = caption
                textSize = 8f
                gravity = Gravity.CENTER
                setTextColor(AudiotomeTheme.muted)
                maxLines = 1
            }
            item.addView(label)
            item.setOnClickListener {
                if (actions.isEmpty()) {
                    AlertDialog.Builder(activity)
                        .setTitle(caption)
                        .setMessage(emptyMessage ?: "Этот раздел будет подключён в следующем этапе.")
                        .setPositiveButton("Понятно", null)
                        .show()
                } else {
                    val names = actions.map { it.text.toString() }.toTypedArray()
                    AlertDialog.Builder(activity)
                        .setTitle(caption)
                        .setItems(names) { _, which -> actions[which].performClick() }
                        .setNegativeButton("Закрыть", null)
                        .show()
                }
            }
            rail.addView(item, LinearLayout.LayoutParams(-1, -2))
        }

        addNav("▤", "Книги", library, "Здесь можно открыть новую книгу.")
        addNav("♙", "Герои", people)
        addNav("✧", "ИИ-анализ", buttons.filter { it.text.toString().contains("диалог", true) || it.text.toString().contains("говорящ", true) })
        addNav("Aa", "Текст", preparation.filter { it.text.toString().contains("ударен", true) || it.text.toString().contains("словар", true) })
        addNav("♫", "Голоса", people.filter { it.text.toString().contains("персонаж", true) || it.text.toString().contains("голос", true) },
            "Настройка персонажей и голосов доступна. Самостоятельный движок озвучивания ещё разрабатывается.")
        val spacer = View(activity)
        rail.addView(spacer, LinearLayout.LayoutParams(1, 0, 1f))
        addNav("⚙", "Ещё", preparation.filter { it !in preparation.filter { b -> b.text.toString().contains("ударен", true) || b.text.toString().contains("словар", true) } })

        return shell
    }
}
'''
layout_path.write_text(layout, encoding="utf-8")

# Preserve the warm paper reading surface when the global theme styles the view tree.
theme_path = base / "AudiotomeTheme.kt"
if theme_path.exists():
    theme = theme_path.read_text(encoding="utf-8")
    theme = theme.replace(
        'if (depth == 0 || group is LinearLayout || group is ScrollView) group.setBackgroundColor(background)',
        'if (group.tag != "audiotome-paper-scroll" && (depth == 0 || group is LinearLayout || group is ScrollView)) group.setBackgroundColor(background)'
    )
    theme = theme.replace(
        'private fun styleText(view: TextView) {\n        val originalSize',
        'private fun styleText(view: TextView) {\n        if (view.tag == "audiotome-paper-text") { view.setTextColor(Color.rgb(48, 43, 36)); return }\n        val originalSize'
    )
    theme_path.write_text(theme, encoding="utf-8")

print("v27: replaced button-dashboard with a book-first reader shell and persistent icon rail.")
