from pathlib import Path

layout = Path("app/src/main/java/ru/fbaudioprep/AudiotomeHomeLayout.kt")
s = layout.read_text(encoding="utf-8")

needle = '''        addNav("⚙", "Ещё", preparation.filter { it !in preparation.filter { b -> b.text.toString().contains("ударен", true) || b.text.toString().contains("словар", true) } })
'''
replacement = needle + '''
        // Keep the app version visible at the foot of the icon rail.
        val appVersion = try {
            activity.packageManager.getPackageInfo(activity.packageName, 0).versionName ?: "?"
        } catch (_: Throwable) {
            "?"
        }
        val versionLabel = TextView(activity).apply {
            text = "v$appVersion"
            textSize = 10f
            setTextColor(Color.rgb(126, 143, 160))
            gravity = Gravity.CENTER
            maxLines = 1
            setPadding(0, dp(activity, 5), 0, dp(activity, 9))
            contentDescription = "Версия приложения $appVersion"
        }
        rail.addView(versionLabel, LinearLayout.LayoutParams(-1, -2))
'''
assert needle in s, "v46: navigation rail end anchor not found"
if "contentDescription = \"Версия приложения $appVersion\"" not in s:
    s = s.replace(needle, replacement, 1)

layout.write_text(s, encoding="utf-8")
print("v46: show installed app version at the bottom of the left icon rail.")
