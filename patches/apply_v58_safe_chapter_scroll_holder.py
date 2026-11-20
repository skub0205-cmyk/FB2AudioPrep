from pathlib import Path
p = Path("app/src/main/java/ru/fbaudioprep/AudiotomeHomeLayout.kt")
s = p.read_text(encoding="utf-8")
if "v58-scroll-view-reference-holder" in s:
    print("v58 already applied")
    raise SystemExit(0)
s = s.replace(
    "        lateinit var paperScroll: ScrollView",
    "        // v58-scroll-view-reference-holder\n        val paperScrollRef = arrayOfNulls<ScrollView>(1)",
    1
)
s = s.replace("                                paperScroll.scrollTo(0, 0)\n                                paperScroll.post { paperScroll.scrollTo(0, 0) }",
              "                                paperScrollRef[0]?.scrollTo(0, 0)\n                                paperScrollRef[0]?.post { paperScrollRef[0]?.scrollTo(0, 0) }", 1)
s = s.replace("        paperScroll = ScrollView(activity).apply {", "        val paperScroll = ScrollView(activity).apply {", 1)
anchor = '''            setBackgroundColor(Color.TRANSPARENT)
        }
        readingText.apply {'''
if anchor not in s:
    raise SystemExit("v58: cannot find ScrollView construction end")
s = s.replace(anchor, '''            setBackgroundColor(Color.TRANSPARENT)
        }
        paperScrollRef[0] = paperScroll
        readingText.apply {''', 1)
p.write_text(s, encoding="utf-8")
print("v58: use a nullable holder for the ScrollView captured before its construction.")
