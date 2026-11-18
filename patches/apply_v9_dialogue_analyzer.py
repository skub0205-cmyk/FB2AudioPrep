from pathlib import Path

target = Path("app/src/main/java/ru/fbaudioprep/RussianDialogueAnalyzer.kt")
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(r'''package ru.fbaudioprep

/**
 * Automatic-first Russian dialogue attribution.
 *
 * This is a deterministic first-pass analyzer, not a full NLP/LLM coreference model.
 * It deliberately abstains when the text does not identify a speaker instead of
 * mistaking a vocative/addressee for the person speaking.
 */
data class DialogueUtterance(
    val text: String,
    val speakerName: String?,
    val addresseeName: String?,
    val gender: VoiceGender,
    val confidence: Float,
    val evidence: List<String>,
    val needsReview: Boolean
)

object RussianDialogueAnalyzer {
    private val femaleVoice = Regex(
        """(?iu)\b(?:женск\w*\s+голос|голос\w*\s+женщин\w*|женщина\s+(?:сказал|произнес|ответил|крикнул|спросил)\w*)"""
    )
    private val maleVoice = Regex(
        """(?iu)\b(?:мужск\w*\s+голос|голос\w*\s+мужчин\w*|мужчина\s+(?:сказал|произнес|ответил|крикнул|спросил)\w*)"""
    )
    private val femaleTag = Regex(
        """(?iu)\b(?:сказала|произнесла|ответила|крикнула|спросила|прошептала|проговорила|воскликнула)\s+(?:она|девушк\w*|женщин\w*)"""
    )
    private val maleTag = Regex(
        """(?iu)\b(?:сказал|произнёс|произнес|ответил|крикнул|спросил|прошептал|проговорил|воскликнул)\s+(?:он|мужчин\w*|парен\w*)"""
    )
    private val namedSpeaker = Regex(
        """(?iu)\b([А-ЯЁ][а-яё-]{1,30})\s+(сказал|сказала|произнёс|произнес|произнесла|ответил|ответила|крикнул|крикнула|спросил|спросила|прошептал|прошептала)\b"""
    )
    private val postDashTag = Regex(
        """(?iu)^\s*(?:раздался|раздалось|прозвучал|прозвучало|сказал|сказала|произнёс|произнес|произнесла|ответил|ответила|крикнул|крикнула|спросил|спросила|прошептал|прошептала)\b"""
    )
    private val quoted = Regex("""[«"]([^»"]{1,1200})[»"]\s*(?:[,—]\s*)?([^«»\n]{0,220})""")
    private val dashWithTag = Regex(
        """(?m)(?:^|\n)\s*—\s*(.{1,1200}?)\s+—\s*((?:раздался|раздалось|прозвучал|прозвучало|сказал|сказала|произнёс|произнес|произнесла|ответил|ответила|крикнул|крикнула|спросил|спросила|прошептал|прошептала)\b[^。\n]{0,220})"""
    )
    private val dashLine = Regex("""(?m)(?:^|\n)\s*—\s*(.{1,700}?)(?=\n|$)""")
    private val vocative = Regex("""^\s*([А-ЯЁ][а-яё-]{1,30})(?=[,!?:…])""")

    fun analyze(text: String): List<DialogueUtterance> {
        if (text.isBlank()) return emptyList()
        val result = mutableListOf<DialogueUtterance>()
        val occupied = mutableListOf<IntRange>()

        // First attach explicit post-quote speech tags to the quote they immediately follow.
        quoted.findAll(text).forEach { match ->
            val tag = match.groupValues[2]
            if (tag.isBlank() || !looksLikeSpeechTag(tag)) return@forEach
            occupied += match.range
            result += classify(match.groupValues[1], tag)
        }

        // Handle the common Russian construction: — words — раздался женский голос.
        dashWithTag.findAll(text).forEach { match ->
            if (occupied.any { it.first <= match.range.first && it.last >= match.range.first }) return@forEach
            occupied += match.range
            result += classify(match.groupValues[1], match.groupValues[2])
        }

        // Preserve dialogue-only dash lines when no explicit attribution was found.
        dashLine.findAll(text).forEach { match ->
            if (occupied.any { it.first <= match.range.first && it.last >= match.range.first }) return@forEach
            val line = match.groupValues[1].trim()
            if (line.isNotBlank()) result += classify(line, "")
        }
        return result
    }

    fun analyzeParagraphs(paragraphs: List<String>): List<DialogueUtterance> =
        paragraphs.flatMap(::analyze)

    private fun classify(dialogue: String, tag: String): DialogueUtterance {
        val evidence = mutableListOf<String>()
        val gender = when {
            femaleVoice.containsMatchIn(tag) || femaleTag.containsMatchIn(tag) -> {
                evidence += "Явное указание на женский голос/говорящую в авторской ремарке"
                VoiceGender.FEMALE
            }
            maleVoice.containsMatchIn(tag) || maleTag.containsMatchIn(tag) -> {
                evidence += "Явное указание на мужской голос/говорящего в авторской ремарке"
                VoiceGender.MALE
            }
            else -> VoiceGender.NEUTRAL
        }

        val named = namedSpeaker.find(tag)
        val speaker = if (named != null) {
            evidence += "Имя связано с глаголом речи в авторской ремарке"
            named.groupValues[1]
        } else null

        val addressee = vocative.find(dialogue)?.groupValues?.get(1)
        if (addressee != null) evidence += "Начальная форма распознана как возможное обращение; не считается говорящим"

        if (gender == VoiceGender.NEUTRAL && speaker == null) {
            evidence += "Недостаточно явных данных о говорящем; требуется контекст соседних реплик"
        }

        val confidence = when {
            gender != VoiceGender.NEUTRAL && speaker != null -> 0.96f
            gender != VoiceGender.NEUTRAL -> 0.91f
            speaker != null -> 0.88f
            else -> 0.35f
        }
        return DialogueUtterance(
            text = dialogue.trim(),
            speakerName = speaker,
            addresseeName = addressee,
            gender = gender,
            confidence = confidence,
            evidence = evidence,
            needsReview = confidence < 0.75f
        )
    }

    private fun looksLikeSpeechTag(value: String): Boolean =
        postDashTag.containsMatchIn(value) ||
            femaleVoice.containsMatchIn(value) ||
            maleVoice.containsMatchIn(value) ||
            femaleTag.containsMatchIn(value) ||
            maleTag.containsMatchIn(value) ||
            namedSpeaker.containsMatchIn(value)
}
''', encoding="utf-8")
print("Added automatic Russian dialogue attribution analyzer.")
