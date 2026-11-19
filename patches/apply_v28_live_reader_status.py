from pathlib import Path

p = Path("app/src/main/java/ru/fbaudioprep/AudiotomeHomeLayout.kt")
s = p.read_text(encoding="utf-8")
old = '''        header.addView(bookTitle)
        content.addView(header, LinearLayout.LayoutParams(-1, -2))'''
new = '''        header.addView(bookTitle)
        status?.let { liveStatus ->
            liveStatus.textSize = 11f
            liveStatus.setTextColor(AudiotomeTheme.muted)
            liveStatus.setPadding(0, dp(activity, 3), 0, 0)
            liveStatus.maxLines = 2
            header.addView(liveStatus, LinearLayout.LayoutParams(-1, -2))
        }
        content.addView(header, LinearLayout.LayoutParams(-1, -2))'''
if old not in s:
    raise SystemExit("Could not find Audiotome header insertion point")
s = s.replace(old, new, 1)
s = s.replace('text = "ЧТЕНИЕ  ·  ПОДГОТОВКА ТЕКСТА  ·  ОФЛАЙН"', 'text = "ЧТЕНИЕ  ·  ПОДГОТОВКА ТЕКСТА"')
p.write_text(s, encoding="utf-8")
print("v28: keep live book/import status visible in the reader header.")
