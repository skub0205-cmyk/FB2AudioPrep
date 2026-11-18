package ru.fbaudioprep.teratts

import android.content.Context
import ru.fbaudioprep.DialogueFinding
import java.security.MessageDigest

/**
 * Adapts the original TeraTTS 1.59 rules + RuModernBERT m10b pipeline to FB2AudioPrep.
 * The book is analysed as a whole, so character aliases and evidence from later chapters
 * can help identify an earlier speaker. Model inference is only run on a worker thread.
 */
object TeraRoleEngine {
    data class Analysis(
        val findings: List<DialogueFinding>,
        val characters: List<DialogueAnalyzer2.Character>,
        val aliases: Map<String, String>,
        val modelGuesses: Int,
        val modelAvailable: Boolean
    )

    fun bookScope(text: String): String {
        val digest = MessageDigest.getInstance("SHA-256").digest(text.toByteArray(Charsets.UTF_8))
        return digest.joinToString("") { "%02x".format(it) }
    }

    private fun linesOf(
        result: DialogueAnalyzer2.Result,
        probes: List<DialogueAnalyzer2.Probe>,
        aliases: Map<String, String>
    ): List<RoleWindows.Line> {
        fun resolve(name: String): String {
            var current = name
            repeat(8) { current = aliases[current] ?: return current }
            return current
        }
        val speakerAt = HashMap<Int, String>()
        for (span in result.spans) {
            if (span.role != DialogueAnalyzer2.Role.NARRATOR) speakerAt[span.start] = span.speaker ?: ""
        }
        return probes.map { probe ->
            RoleWindows.Line(
                probe.ps, probe.pe, probe.kind, probe.quoted, probe.speech, probe.authors,
                if (probe.speech.isEmpty()) "" else resolve(speakerAt[probe.speech[0][0]] ?: "")
            )
        }
    }

    fun analyze(context: Context, text: String, stop: () -> Boolean = { false }): Analysis {
        val (rulesResult, probes) = DialogueAnalyzer2.analyzeLines(text)
        val aliases = rulesResult.aliases
        val lines = linesOf(rulesResult, probes, aliases)
        val names = rulesResult.characters.map { it.name }.distinct().filter { it !in aliases }
        val available = RoleModel.enabled(context)
        val scope = bookScope(text)

        val guesses = if (available && names.isNotEmpty()) {
            RoleModel.guesses(
                context, scope, text, lines, names, aliases,
                compute = true, threads = 2, stop = stop
            ).orEmpty()
        } else emptyMap()

        val improved = if (guesses.isNotEmpty()) {
            RoleModel.improve(
                rulesResult, text, lines, guesses, aliases, emptyMap()
            ) { name ->
                rulesResult.characters.firstOrNull { it.name == name }?.role
            }
        } else rulesResult

        val paragraphStarts = HashMap<Int, Int>()
        var offset = 0
        text.split('\n').forEachIndexed { index, paragraph ->
            paragraphStarts[offset] = index
            offset += paragraph.length + 1
        }

        val findings = probes.mapNotNull { probe ->
            if (probe.speech.isEmpty()) return@mapNotNull null
            val speechSpans = improved.spans.filter { span ->
                span.role != DialogueAnalyzer2.Role.NARRATOR &&
                    probe.speech.any { span.start >= it[0] && span.start < it[1] }
            }
            val selected = speechSpans.firstOrNull { !it.speaker.isNullOrBlank() }
                ?: speechSpans.firstOrNull()
            val speaker = selected?.speaker ?: probe.speaker
            val role = selected?.role ?: improved.characters.firstOrNull { it.name == speaker }?.role
            val paragraphIndex = paragraphStarts[probe.ps]
                ?: text.substring(0, probe.ps.coerceIn(0, text.length)).count { it == '\n' }
            val guess = guesses[paragraphIndex]
            val modelChoseSpeaker = guess != null && speaker.equals(guess.speaker, ignoreCase = true)
            val voice = when (role) {
                DialogueAnalyzer2.Role.MALE -> "мужской"
                DialogueAnalyzer2.Role.FEMALE -> "женский"
                else -> null
            }
            val spoken = probe.speech.joinToString(" ") { range ->
                text.substring(range[0].coerceIn(0, text.length), range[1].coerceIn(0, text.length))
            }
            val addressee = Regex("""^\s*([А-ЯЁ][а-яёА-ЯЁ-]{1,29})(?=[,!?:…])""")
                .find(spoken)?.groupValues?.get(1)
                ?.takeUnless { it.equals(speaker, ignoreCase = true) }
            val confidence = when {
                modelChoseSpeaker -> guess!!.prob
                speaker != null -> 0.90f
                voice != null -> 0.60f
                else -> 0.0f
            }
            val reason = when {
                modelChoseSpeaker -> "TeraTTS m10b: нейросеть выбрала «${guess!!.speaker}» с вероятностью ${(guess.prob * 100).toInt()}%"
                speaker != null -> "Правила анализа TeraTTS 1.59: говорящий определён по авторской ремарке и контексту"
                voice != null -> "Определён пол голоса по тексту; личность говорящего не установлена"
                else -> "Недостаточно контекста для надёжного определения говорящего"
            }
            DialogueFinding(
                fragment = text.substring(probe.ps.coerceIn(0, text.length), probe.pe.coerceIn(0, text.length)),
                speaker = speaker,
                voice = voice,
                confidence = confidence,
                reason = reason,
                addressedTo = addressee
            )
        }

        return Analysis(findings, improved.characters, improved.aliases, guesses.size, available)
    }
}
