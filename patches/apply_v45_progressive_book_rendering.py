from pathlib import Path
import re

base = Path("app/src/main/java/ru/fbaudioprep")
main = base / "MainActivity.kt"
s = main.read_text(encoding="utf-8")

# The book was assigned to one enormous TextView. Android then had to measure
# and lay out hundreds of thousands of characters in one UI pass. Keep the
# complete source in memory for search/TTS, but render it progressively.
start = s.find("    private fun syncReaderContent() {")
end = s.find("\n    private fun openBookPreview()", start)
if start < 0 or end < 0:
    raise SystemExit("v45: cannot locate syncReaderContent()")
method = r'''    private fun syncReaderContent() {
        val bookText = processedText.ifBlank { originalText }
        val visibleText = if (bookText.isBlank()) "Откройте книгу, чтобы начать чтение." else bookText
        preview.text = visibleText.take(8000)
        preview.visibility = android.view.View.VISIBLE

        val content = findViewById<android.view.ViewGroup>(android.R.id.content)
        val readerText = content?.findViewWithTag("audiotome-paper-text") as? TextView
        val readerScroll = content?.findViewWithTag("audiotome-paper-scroll") as? ScrollView
        if (readerText != null) {
            val signature = visibleText.length.toString() + ":" + visibleText.hashCode()
            val previousSignature = readerScroll?.contentDescription?.toString()
            if (previousSignature != signature) {
                readerScroll?.contentDescription = signature
                readerText.contentDescription = "8000"
                readerText.text = visibleText.take(8000)
                readerScroll?.scrollTo(0, 0)
            }

            readerScroll?.setOnScrollChangeListener { view: ScrollView, _, scrollY, _, _ ->
                val child = view.getChildAt(0) ?: return@setOnScrollChangeListener
                if (scrollY + view.height < child.height - 500) return@setOnScrollChangeListener
                val currentEnd = readerText.contentDescription?.toString()?.toIntOrNull() ?: 8000
                if (currentEnd >= visibleText.length) return@setOnScrollChangeListener
                val nextEnd = (currentEnd + 8000).coerceAtMost(visibleText.length)
                readerText.contentDescription = nextEnd.toString()
                readerText.post {
                    if (readerScroll.contentDescription?.toString() == signature) {
                        readerText.append(visibleText.substring(currentEnd, nextEnd))
                    }
                }
            }
            readerText.visibility = android.view.View.VISIBLE
        }
        val title = content?.findViewWithTag("audiotome-book-title") as? TextView
        if (title != null && sourceName.isNotBlank()) title.text = sourceName
    }

'''
s = s[:start] + method + s[end:]
main.write_text(s, encoding="utf-8")
print("v45: render book text progressively in 8k-character pages; keep full text available to processing and TTS.")
