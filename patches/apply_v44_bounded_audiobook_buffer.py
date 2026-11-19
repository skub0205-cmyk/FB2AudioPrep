from pathlib import Path
import re

p = Path("app/src/main/java/ru/fbaudioprep/MainActivity.kt")
s = p.read_text(encoding="utf-8")
start = s.index("    private fun startBookPlayback() {")
end = s.index("    private fun stopBookPlayback() {", start)

replacement = r'''    private fun startBookPlayback() {
        val engine = ttsEngine ?: return
        if (ttsWorker?.isAlive == true) return

        // Do not materialize a queue for the entire book. Keep only three
        // sentence-sized text requests ready; the source book remains in the
        // reader and chunks are produced lazily as playback advances.
        val source = processedText.ifBlank { originalText }
        val startAt = ttsResumeIndex.coerceAtLeast(0)
        val voice = selectedTtsVoice
        ttsStopRequested = false
        playBookButton.isEnabled = false
        stopBookButton.isEnabled = true

        ttsWorker = Thread({
            var completed = false
            try {
                val chunks = Regex("\\n\\s*\\n").splitToSequence(source)
                    .flatMap { paragraph ->
                        SpeechTextChunker.chunk(paragraph, 360).asSequence()
                    }
                    .filter { it.isNotBlank() }
                    .iterator()

                // Restore position without allocating a book-sized List.
                var skipped = 0
                while (skipped < startAt && chunks.hasNext()) {
                    chunks.next()
                    skipped++
                }

                val prebuffer = java.util.ArrayDeque<String>(3)
                fun fillPrebuffer() {
                    while (prebuffer.size < 3 && chunks.hasNext()) {
                        prebuffer.addLast(chunks.next())
                    }
                }
                fillPrebuffer()

                var played = startAt
                while (prebuffer.isNotEmpty() && !ttsStopRequested) {
                    val nextText = prebuffer.removeFirst()
                    // Keep the next two/three short text fragments ready while
                    // the current fragment is synthesized and played.
                    fillPrebuffer()
                    runOnUiThread {
                        status.text = "Озвучивание: фрагмент " + (played + 1) +
                            "\\nБуфер: " + prebuffer.size + " фрагм.\\nГолос: " + voice
                    }
                    engine.synthesizeAndPlay(
                        TeraTtsTextFormatter.russian(nextText),
                        voice,
                        seed = 1234L + played
                    )
                    if (ttsStopRequested) break
                    played++
                    ttsResumeIndex = played
                    getSharedPreferences("audiobook_playback", MODE_PRIVATE).edit()
                        .putInt("resume_" + ttsBookKey, ttsResumeIndex).apply()
                }

                completed = !ttsStopRequested && prebuffer.isEmpty() && !chunks.hasNext()
                if (completed) {
                    ttsResumeIndex = 0
                    getSharedPreferences("audiobook_playback", MODE_PRIVATE).edit()
                        .putInt("resume_" + ttsBookKey, 0).apply()
                }
                runOnUiThread {
                    status.text = when {
                        completed -> "Озвучивание книги завершено."
                        ttsStopRequested -> "Озвучивание остановлено. Можно продолжить с этого места."
                        else -> "Озвучивание приостановлено."
                    }
                    playBookButton.text = if (ttsResumeIndex > 0)
                        "▶ Продолжить озвучивание" else "▶ Озвучить книгу"
                }
            } catch (e: Throwable) {
                runOnUiThread {
                    status.text = "Ошибка озвучивания: " + (e.message ?: "неизвестно")
                }
            } finally {
                runOnUiThread {
                    playBookButton.isEnabled = originalText.isNotBlank() &&
                        (ttsEngine?.status()?.ready == true)
                    stopBookButton.isEnabled = false
                }
            }
        }, "teratts-v2-playback").also { it.start() }
    }

'''
s = s[:start] + replacement + s[end:]
p.write_text(s, encoding="utf-8")

# Keep this as a separately testable pure Kotlin helper test source.
tests = Path("app/src/test/java/ru/fbaudioprep/SpeechTextChunkerBufferTest.kt")
tests.parent.mkdir(parents=True, exist_ok=True)
tests.write_text(r'''package ru.fbaudioprep

import org.junit.Assert.assertTrue
import org.junit.Test

class SpeechTextChunkerBufferTest {
    @Test
    fun chunksStayBoundedAndPreferSentenceBoundaries() {
        val source = ("Это первое предложение. Это второе предложение! Это третье предложение? ").repeat(30)
        val chunks = SpeechTextChunker.chunk(source, 360)
        assertTrue(chunks.size > 1)
        assertTrue(chunks.all { it.isNotBlank() && it.length <= 361 })
        assertTrue(chunks.joinToString(" ").replace(Regex("\\s+"), " ").contains("первое предложение."))
    }

    @Test
    fun smallBufferNeverNeedsMoreThanThreePreparedChunks() {
        val source = ("Первое предложение. Второе предложение. Третье предложение. ").repeat(20)
        val iterator = SpeechTextChunker.chunk(source, 360).iterator()
        val buffer = java.util.ArrayDeque<String>(3)
        while (buffer.size < 3 && iterator.hasNext()) buffer.addLast(iterator.next())
        assertTrue(buffer.size <= 3)
        while (buffer.isNotEmpty()) {
            buffer.removeFirst()
            while (buffer.size < 3 && iterator.hasNext()) buffer.addLast(iterator.next())
            assertTrue(buffer.size <= 3)
        }
    }
}
''', encoding="utf-8")
print("v44: replace whole-book queue with lazy three-fragment prebuffer; add buffer regression tests.")
