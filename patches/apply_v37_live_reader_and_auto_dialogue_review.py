from pathlib import Path
import re

base = Path("app/src/main/java/ru/fbaudioprep")
main = base / "MainActivity.kt"
s = main.read_text(encoding="utf-8")

# The primary analysis action must open the review workspace after analysis,
# rather than leaving the user in the old status-only screen.
old_click = 'setOnClickListener { analyzeDialogues() }'
if old_click not in s:
    raise SystemExit("v37: cannot find primary dialogue-analysis click handler")
s = s.replace(old_click, 'setOnClickListener { openDialogueBrowser() }', 1)

# Keep the actual reader TextView and its visible tagged counterpart synchronized.
helper = '''    private fun syncReaderContent() {
        val bookText = processedText.ifBlank { originalText }
        val visibleText = if (bookText.isBlank()) "Откройте книгу, чтобы начать чтение." else bookText
        preview.text = visibleText
        preview.visibility = android.view.View.VISIBLE
        val content = findViewById<android.view.ViewGroup>(android.R.id.content)
        val readerText = content?.findViewWithTag("audiotome-paper-text") as? TextView
        if (readerText != null) {
            readerText.text = visibleText
            readerText.visibility = android.view.View.VISIBLE
            readerText.requestLayout()
            readerText.post { (readerText.parent as? ScrollView)?.scrollTo(0, 0) }
        }
        val title = content?.findViewWithTag("audiotome-book-title") as? TextView
        if (title != null && sourceName.isNotBlank()) title.text = sourceName
    }

'''
if "private fun syncReaderContent()" not in s:
    anchor = "    private fun openBookPreview() {"
    if anchor not in s:
        raise SystemExit("v37: cannot locate reader entry point")
    s = s.replace(anchor, helper + anchor, 1)

# Reader entry point always updates both the backing TextView and the rendered paper view.
start = s.find("    private fun openBookPreview() {")
end = s.find("\n    private fun openBook()", start)
if start < 0 or end < 0:
    raise SystemExit("v37: cannot isolate openBookPreview()")
method = '''    private fun openBookPreview() {
        if (originalText.isBlank()) {
            Toast.makeText(this, "Сначала откройте книгу", Toast.LENGTH_SHORT).show()
            return
        }
        syncReaderContent()
        status.text = status.text.toString()
            .replace("\\nОткрываю читалку…", "")
            .replace("\\nОткрываю книгу в читалке…", "")
    }
'''
s = s[:start] + method + s[end:]

# Ensure later text processing and manual corrections update the visible reader too.
s = s.replace("            preview.text = processedText\n            Toast.makeText", "            syncReaderContent()\n            Toast.makeText")
s = s.replace("                    preview.text = processedText.ifBlank { originalText }\n                    dialogueAnalysisInProgress", "                    syncReaderContent()\n                    dialogueAnalysisInProgress")
s = s.replace("        preview.text = processedText.ifBlank { originalText }\n    }", "        syncReaderContent()\n    }")
# Import calls openBookPreview immediately after assigning originalText; retain that path.
# The visible paper header also needs the newly imported book title.
main.write_text(s, encoding="utf-8")

layout = base / "AudiotomeHomeLayout.kt"
ls = layout.read_text(encoding="utf-8")
anchor = '''        val bookTitle = TextView(activity).apply {
            text = if (status?.text.isNullOrBlank()) "Ваша библиотека" else status?.text?.toString()?.lineSequence()?.firstOrNull().orEmpty()
'''
if anchor not in ls:
    raise SystemExit("v37: cannot locate book title view")
ls = ls.replace(anchor, '''        val bookTitle = TextView(activity).apply {
            tag = "audiotome-book-title"
            text = if (status?.text.isNullOrBlank()) "Ваша библиотека" else status?.text?.toString()?.lineSequence()?.firstOrNull().orEmpty()
''', 1)

# Guarantee the original preview is the rendered paper TextView, not a detached fallback.
old = '''        val previewText = previewScroll?.let { sc ->
            (0 until sc.childCount).map { sc.getChildAt(it) }.firstOrNull { it is TextView } as? TextView
        }
'''
new = '''        fun findTextView(view: View): TextView? {
            if (view is TextView) return view
            if (view is ViewGroup) {
                for (i in 0 until view.childCount) {
                    val found = findTextView(view.getChildAt(i))
                    if (found != null) return found
                }
            }
            return null
        }
        val previewText = previewScroll?.let { findTextView(it) }
'''
if old not in ls:
    raise SystemExit("v37: cannot locate preview TextView extraction")
ls = ls.replace(old, new, 1)
layout.write_text(ls, encoding="utf-8")
print("v37: bind the visible paper reader to the live book text and open dialogue review after analysis.")
