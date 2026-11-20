from pathlib import Path
p = Path("app/src/main/java/ru/fbaudioprep/MainActivity.kt")
s = p.read_text(encoding="utf-8")
old = "            singleLine = true"
if old in s:
    s = s.replace(old, "            setSingleLine(true)", 1)
    p.write_text(s, encoding="utf-8")
    print("v56: corrected EditText single-line configuration for Android Kotlin API")
else:
    print("v56: no correction needed")
