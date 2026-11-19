from pathlib import Path

root = Path("app/src/main/java/ru/fbaudioprep")
root.mkdir(parents=True, exist_ok=True)

target = root / "AudiobookSpeechPipeline.kt"
target.write_text(r'''package ru.fbaudioprep

/**
 * Pure Kotlin speech preparation layer. It deliberately has no Android/UI dependency:
 * the ONNX engine and the playback service can be added without changing book parsing
 * or dialogue analysis.
 */
enum class AudiobookMode {
    SINGLE_NARRATOR,
    CHARACTERS
}

enum class SpeakerEvidence {
    USER_CONFIRMED,
    EXPLICIT_AUTHOR_TAG,
    CONTEXT_INFERRED,
    UNRESOLVED
}

data class AudiobookSpeechSegment(
    val id: String,
    val chapterIndex: Int,
    val paragraphIndex: Int,
    val text: String,
    val speakerId: String? = null,
    val evidence: SpeakerEvidence = SpeakerEvidence.UNRESOLVED,
    val confidence: Float = 0f
) {
    init {
        require(id.isNotBlank()) { "Segment id must not be blank" }
        require(chapterIndex >= 0 && paragraphIndex >= 0) {
            "Chapter and paragraph indexes must be non-negative"
        }
        require(confidence in 0f..1f) { "Confidence must be between 0 and 1" }
    }
}

data class CharacterVoiceAssignment(
    val speakerId: String,
    val voiceId: String
) {
    init {
        require(speakerId.isNotBlank() && voiceId.isNotBlank())
    }
}

data class AudiobookVoiceSettings(
    val mode: AudiobookMode,
    val narratorVoiceId: String,
    val fallbackVoiceId: String,
    val characterVoices: Map<String, String> = emptyMap(),
    val minimumInferenceConfidence: Float = 0.78f
) {
    init {
        require(narratorVoiceId.isNotBlank())
        require(fallbackVoiceId.isNotBlank())
        require(minimumInferenceConfidence in 0f..1f)
    }
}

data class RoutedSpeechSegment(
    val segment: AudiobookSpeechSegment,
    val voiceId: String,
    val routeReason: String
)

/**
 * Priority is intentionally conservative:
 * user correction > explicit author speech tag > high-confidence contextual speaker.
 * Unresolved or low-confidence turns use the configured fallback voice.
 * A vocative/name being addressed is never used as a speaker signal here.
 */
object BookSpeechRouter {
    fun route(
        segment: AudiobookSpeechSegment,
        settings: AudiobookVoiceSettings
    ): RoutedSpeechSegment {
        if (settings.mode == AudiobookMode.SINGLE_NARRATOR) {
            return RoutedSpeechSegment(segment, settings.narratorVoiceId, "single-narrator")
        }

        val speaker = segment.speakerId
        val reliable = when (segment.evidence) {
            SpeakerEvidence.USER_CONFIRMED,
            SpeakerEvidence.EXPLICIT_AUTHOR_TAG -> true
            SpeakerEvidence.CONTEXT_INFERRED ->
                segment.confidence >= settings.minimumInferenceConfidence
            SpeakerEvidence.UNRESOLVED -> false
        }

        if (!reliable || speaker.isNullOrBlank()) {
            return RoutedSpeechSegment(segment, settings.fallbackVoiceId, "fallback-unresolved")
        }

        val assigned = settings.characterVoices[speaker]
        return if (assigned.isNullOrBlank()) {
            RoutedSpeechSegment(segment, settings.fallbackVoiceId, "fallback-unassigned")
        } else {
            val reason = when (segment.evidence) {
                SpeakerEvidence.USER_CONFIRMED -> "user-assignment"
                SpeakerEvidence.EXPLICIT_AUTHOR_TAG -> "explicit-author-tag"
                SpeakerEvidence.CONTEXT_INFERRED -> "high-confidence-context"
                SpeakerEvidence.UNRESOLVED -> "fallback-unresolved"
            }
            RoutedSpeechSegment(segment, assigned, reason)
        }
    }
}

/**
 * Splits long book paragraphs into bounded TTS requests without cutting words.
 * It prefers sentence boundaries, then clause boundaries, and only then whitespace.
 */
object SpeechTextChunker {
    fun chunk(text: String, maxChars: Int = 220): List<String> {
        require(maxChars >= 40) { "maxChars must be at least 40" }
        val normalized = text
            .replace('\u0000', ' ')
            .replace(Regex("[\\t\\r ]+"), " ")
            .replace(Regex(" *\\n+ *"), "\n")
            .trim()
        if (normalized.isEmpty()) return emptyList()

        val result = mutableListOf<String>()
        val paragraphParts = normalized.split('\n').filter { it.isNotBlank() }
        for (paragraph in paragraphParts) {
            var remaining = paragraph.trim()
            while (remaining.length > maxChars) {
                val limit = remaining.lastIndexOf(' ', maxChars)
                val floor = (maxChars * 0.55f).toInt()
                val cut = findBoundary(remaining, limit, floor)
                if (cut <= 0) {
                    val safe = remaining.indexOf(' ', maxChars)
                    if (safe <= 0) {
                        result += remaining
                        remaining = ""
                    } else {
                        result += remaining.substring(0, safe).trim()
                        remaining = remaining.substring(safe).trim()
                    }
                } else {
                    result += remaining.substring(0, cut).trim()
                    remaining = remaining.substring(cut).trim()
                }
            }
            if (remaining.isNotBlank()) result += remaining
        }
        return result
    }

    private fun findBoundary(text: String, from: Int, floor: Int): Int {
        if (from <= 0) return -1
        val sentenceMarks = charArrayOf('.', '!', '?', '…', '。')
        for (i in from downTo floor) {
            if (text[i] in sentenceMarks) return i + 1
        }
        for (i in from downTo floor) {
            if (text[i] == ';' || text[i] == ':' || text[i] == ',') return i + 1
        }
        return from
    }
}

/** TeraTTSv2 requires explicit language tags around Russian text. */
object TeraTtsTextFormatter {
    fun russian(text: String): String {
        val clean = text.trim()
        if (clean.isEmpty()) return ""
        if (clean.startsWith("<ru>") && clean.endsWith("</ru>")) return clean
        require(!clean.contains("<en>") || clean.contains("</en>")) {
            "Unbalanced English language tag"
        }
        return "<ru>$clean</ru>"
    }
}

/** Immutable queue records ready for an engine adapter and the audio output layer. */
data class AudiobookQueueItem(
    val segmentId: String,
    val chapterIndex: Int,
    val paragraphIndex: Int,
    val chunkIndex: Int,
    val text: String,
    val taggedText: String,
    val voiceId: String
)

object AudiobookQueueBuilder {
    fun build(
        segments: List<AudiobookSpeechSegment>,
        settings: AudiobookVoiceSettings,
        maxChunkChars: Int = 220
    ): List<AudiobookQueueItem> {
        val queue = ArrayList<AudiobookQueueItem>()
        segments.forEach { segment ->
            val routed = BookSpeechRouter.route(segment, settings)
            SpeechTextChunker.chunk(segment.text, maxChunkChars).forEachIndexed { index, chunk ->
                queue += AudiobookQueueItem(
                    segmentId = segment.id,
                    chapterIndex = segment.chapterIndex,
                    paragraphIndex = segment.paragraphIndex,
                    chunkIndex = index,
                    text = chunk,
                    taggedText = TeraTtsTextFormatter.russian(chunk),
                    voiceId = routed.voiceId
                )
            }
        }
        return queue
    }
}

/** The only Russian preset IDs currently documented by the TeraTTSv2 model card. */
object TeraTtsV2RussianVoices {
    const val FEMALE_1 = "ru_f1"
    const val MALE_5 = "ru_m5"
    const val FEMALE_2 = "ru_f2"
    const val MALE_1 = "ru_m1"

    val all: List<String> = listOf(FEMALE_1, MALE_5, FEMALE_2, MALE_1)
}
''', encoding="utf-8")

print("v33: added conservative speaker routing, bounded speech chunking, Russian language tagging and audiobook queue construction.")
