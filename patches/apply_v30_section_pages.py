from pathlib import Path

p = Path("app/src/main/java/ru/fbaudioprep/AudiotomeHomeLayout.kt")
s = p.read_text(encoding="utf-8")

old = '''        paper.addView(paperScroll, FrameLayout.LayoutParams(-1, -1))
        content.addView(paper, LinearLayout.LayoutParams(-1, 0, 1f))

        val footer = LinearLayout(activity).apply {'''
new = '''        paper.addView(paperScroll, FrameLayout.LayoutParams(-1, -1))
        val sectionHost = FrameLayout(activity)
        sectionHost.addView(paper, FrameLayout.LayoutParams(-1, -1))
        content.addView(sectionHost, LinearLayout.LayoutParams(-1, 0, 1f))

        fun showSection(sectionTitle: String, actions: List<Button>, emptyMessage: String? = null) {
            sectionHost.removeAllViews()
            val scroll = ScrollView(activity).apply {
                isFillViewport = true
                clipToPadding = false
            }
            val panel = LinearLayout(activity).apply {
                orientation = LinearLayout.VERTICAL
                setPadding(dp(activity, 3), dp(activity, 5), dp(activity, 3), dp(activity, 18))
            }
            val heading = TextView(activity).apply {
                text = sectionTitle
                textSize = 23f
                setTextColor(AudiotomeTheme.text)
                typeface = Typeface.create("sans-serif-medium", Typeface.NORMAL)
                setPadding(dp(activity, 3), dp(activity, 8), dp(activity, 3), dp(activity, 5))
            }
            panel.addView(heading)
            val subtitle = TextView(activity).apply {
                text = when (sectionTitle) {
                    "Книги" -> "Ваша библиотека и импорт новых книг"
                    "Герои" -> "Персонажи, говорящие роли и назначение голосов"
                    "ИИ-анализ" -> "Автоматическое распознавание реплик и говорящих"
                    "Текст" -> "Подготовка текста и управление ударениями"
                    "Голоса" -> "Профили голосов и экспорт настроек"
                    else -> "Инструменты и параметры FB2AudioPrep"
                }
                textSize = 12f
                setTextColor(AudiotomeTheme.muted)
                setPadding(dp(activity, 3), 0, dp(activity, 3), dp(activity, 16))
            }
            panel.addView(subtitle)
            if (actions.isEmpty()) {
                val empty = TextView(activity).apply {
                    text = emptyMessage ?: "Раздел будет расширен в следующем обновлении."
                    textSize = 14f
                    setTextColor(AudiotomeTheme.text)
                    setPadding(dp(activity, 14), dp(activity, 16), dp(activity, 14), dp(activity, 16))
                    background = GradientDrawable().apply {
                        setColor(AudiotomeTheme.surfaceRaised)
                        cornerRadius = dp(activity, 14).toFloat()
                        setStroke(dp(activity, 1), AudiotomeTheme.line)
                    }
                }
                panel.addView(empty, LinearLayout.LayoutParams(-1, -2))
            } else {
                actions.forEachIndexed { index, action ->
                    val label = action.text.toString()
                    val card = LinearLayout(activity).apply {
                        orientation = LinearLayout.VERTICAL
                        setPadding(dp(activity, 15), dp(activity, 13), dp(activity, 15), dp(activity, 13))
                        background = GradientDrawable().apply {
                            setColor(AudiotomeTheme.surfaceRaised)
                            cornerRadius = dp(activity, 14).toFloat()
                            setStroke(dp(activity, 1), AudiotomeTheme.line)
                        }
                        isClickable = true
                        isFocusable = true
                        setOnClickListener { action.performClick() }
                    }
                    val actionTitle = TextView(activity).apply {
                        text = label
                        textSize = 15f
                        setTextColor(AudiotomeTheme.text)
                        typeface = Typeface.create("sans-serif-medium", Typeface.NORMAL)
                    }
                    card.addView(actionTitle)
                    val hint = TextView(activity).apply {
                        text = when {
                            label.contains("Открыть книгу", true) -> "Импорт FB2, TXT или ZIP"
                            label.contains("Персонаж", true) -> "Список героев и параметры их голосов"
                            label.contains("диалог", true) || label.contains("говорящ", true) -> "Найти реплики и проверить назначение говорящих"
                            label.contains("ударен", true) || label.contains("словар", true) -> "Редактирование словаря и подготовка произношения"
                            label.contains("экспорт", true) -> "Сохранить настройки для внешнего синтезатора"
                            else -> "Открыть инструмент"
                        }
                        textSize = 11f
                        setTextColor(AudiotomeTheme.muted)
                        setPadding(0, dp(activity, 4), 0, 0)
                    }
                    card.addView(hint)
                    val params = LinearLayout.LayoutParams(-1, -2)
                    params.bottomMargin = dp(activity, 9)
                    panel.addView(card, params)
                }
            }
            scroll.addView(panel, ViewGroup.LayoutParams(-1, -2))
            sectionHost.addView(scroll, FrameLayout.LayoutParams(-1, -1))
        }

        val footer = LinearLayout(activity).apply {'''
if old not in s:
    raise SystemExit("Could not find reader paper host insertion point")
s = s.replace(old, new, 1)

old2 = '''            item.setOnClickListener {
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
            }'''
new2 = '''            item.setOnClickListener {
                showSection(caption, actions, emptyMessage)
            }'''
if old2 not in s:
    raise SystemExit("Could not find old navigation dialog click handler")
s = s.replace(old2, new2, 1)

p.write_text(s, encoding="utf-8")
print("v30: sidebar navigation opens full in-app section pages with actionable cards.")
