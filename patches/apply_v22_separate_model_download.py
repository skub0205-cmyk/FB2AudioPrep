from pathlib import Path
import re

main = Path("app/src/main/java/ru/fbaudioprep/MainActivity.kt")
s = main.read_text(encoding="utf-8")

old = '''                    status.text = "ИИ-модель установлена. Следующий анализ будет работать офлайн."
                    analyzeDialogues(allowWithoutModel = true)'''
new = '''                    status.text = "ИИ-модель установлена. Нажмите «Проверить диалоги», когда будете готовы к анализу."'''
if new in s:
    print("v22 already applied")
elif old in s:
    s = s.replace(old, new, 1)
    main.write_text(s, encoding="utf-8")
    print("v22: model download completion no longer starts dialogue analysis")
else:
    raise SystemExit("v22: expected successful model-download callback was not found")

gradle = Path("app/build.gradle.kts")
g = gradle.read_text(encoding="utf-8")
m = re.search(r'versionCode\\s*=\\s*(\\d+);\\s*versionName\\s*=\\s*"([^"]+)"', g)
if not m:
    raise SystemExit("v22: cannot locate Android versionCode/versionName")
if m.group(2) != "2.1.2":
    g = g[:m.start()] + f'versionCode = {int(m.group(1)) + 1}; versionName = "2.1.2"' + g[m.end():]
    gradle.write_text(g, encoding="utf-8")
