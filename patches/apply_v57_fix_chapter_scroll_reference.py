from pathlib import Path
p = Path("app/src/main/java/ru/fbaudioprep/AudiotomeHomeLayout.kt")
s = p.read_text(encoding="utf-8")
if "v57-paper-scroll-forward-reference" in s:
    print("v57 already applied")
    raise SystemExit(0)
anchor = "        // v55-fb2-chapter-navigation: chapter list is derived from the complete book,"
if anchor not in s:
    raise SystemExit("v57: cannot locate chapter navigation")
s = s.replace(anchor, "        // v57-paper-scroll-forward-reference\n        lateinit var paperScroll: ScrollView\n" + anchor, 1)
old = "        val paperScroll = ScrollView(activity).apply {"
if old not in s:
    raise SystemExit("v57: cannot locate ScrollView declaration")
s = s.replace(old, "        paperScroll = ScrollView(activity).apply {", 1)
p.write_text(s, encoding="utf-8")
print("v57: declare the reader ScrollView before the chapter button captures it.")
