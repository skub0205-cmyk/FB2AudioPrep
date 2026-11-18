from pathlib import Path
import re

source = Path("app/src/main/java/ru/fbaudioprep/DialogueAnalyzer.kt")
text = source.read_text(encoding="utf-8")

old = """    private fun hasSpeechVerb(text: String): Boolean = Regex(
        "(?iu)(?<![\\\\p{L}\\\\p{M}])(?:$speechVerbPattern)(?![\\\\p{L}\\\\p{M}])"
    ).containsMatchIn(text)
"""
new = old + """
    private fun hasPassiveVoiceVerb(text: String): Boolean = Regex(
        "(?iu)(?<![\\\\p{L}\\\\p{M}])(?:$passiveVerbPattern)(?![\\\\p{L}\\\\p{M}])"
    ).containsMatchIn(text)
"""
if "private fun hasPassiveVoiceVerb" not in text:
    if old not in text:
        raise SystemExit("Cannot locate hasSpeechVerb()")
    text = text.replace(old, new, 1)

old_candidate = """                    (hasQuotedSpeech && hasSpeechVerb(paragraph)) ||
"""
new_candidate = """                    // Quoted dialogue followed by passive attribution ("a female voice sounded")
                    // is still a dialogue candidate even though "раздался" is not a speech verb.
                    (hasQuotedSpeech && (hasSpeechVerb(paragraph) || hasPassiveVoiceVerb(paragraph))) ||
"""
if old_candidate in text:
    text = text.replace(old_candidate, new_candidate, 1)
elif "hasQuotedSpeech && (hasSpeechVerb(paragraph) || hasPassiveVoiceVerb(paragraph))" not in text:
    raise SystemExit("Cannot locate quoted-speech candidate condition")

marker = """    private fun sameVoiceGender(profile: CharacterProfile, voice: String): Boolean {
"""
if "private val sameVoiceContinuation" not in text:
    insert = """    // Explicit authorial continuity ("всё тем же ровным голосом") is stronger
    // than simply choosing the next character with the same gender.
    private val sameVoiceContinuation = Regex(
        """ + '"""(?iu)\\b(?:все|всё)?\\s*(?:тем же|таким же|прежним|тем самым|таким самым)\\s+(?:[\p{L}\p{M}-]+\s+){0,3}голосом\\b"""' + """
    )

"""
    if marker not in text:
        raise SystemExit("Cannot locate sameVoiceGender()")
    text = text.replace(marker, insert + marker, 1)

start = text.find("        // Some books identify a voice only a few dialogue turns later")
end = text.find("        return findings", start)
if start < 0 or end < 0:
    raise SystemExit("Cannot locate forward voice attribution block")
new_block = """        // Link an anonymous voice to a later named speaker when the author explicitly
        // says it is the same voice. This outranks proximity: the next speaker may be
        // a listener replying to that voice (e.g. Nurina answers, then Samuru continues).
        for (index in findings.indices) {
            val current = findings[index]
            if (current.speaker != null || current.voice == null || !current.fragment.contains("голос", true)) continue
            val end = (index + 15).coerceAtMost(findings.lastIndex)
            var sameVoiceOwner: CharacterProfile? = null
            for (next in (index + 1)..end) {
                val candidate = findings[next]
                if (!sameVoiceContinuation.containsMatchIn(candidate.fragment)) continue
                val candidateName = candidate.speaker ?: continue
                val profile = characters.firstOrNull { normalize(it.name) == normalize(candidateName) } ?: continue
                if (!sameVoiceGender(profile, current.voice)) continue
                sameVoiceOwner = profile
                break
            }
            if (sameVoiceOwner != null) {
                findings[index] = current.copy(
                    speaker = sameVoiceOwner.name,
                    confidence = 0.88f,
                    reason = "Авторское указание «тем же голосом» связывает реплику с персонажем " + sameVoiceOwner.name
                )
                continue
            }
        }

        // Conservative fallback for a voice in a clearly marked location (for example,
        // "в голове") followed shortly by a named response from that same location.
        // A vocative is never treated as the speaker; gender and location must both fit.
        for (index in findings.indices) {
            val current = findings[index]
            if (current.speaker != null || current.voice == null || !current.fragment.contains("голос", true)) continue
            val location = inferredVoiceLocation(findings, index) ?: continue
            val end = (index + 3).coerceAtMost(findings.lastIndex)
            var inferred: CharacterProfile? = null
            for (next in (index + 1)..end) {
                val candidate = findings[next]
                val candidateName = candidate.speaker ?: continue
                val profile = characters.firstOrNull { normalize(it.name) == normalize(candidateName) } ?: continue
                if (!sameVoiceGender(profile, current.voice)) continue
                val candidateLocation = inferredVoiceLocation(findings, next)
                if (candidateLocation != location) continue
                inferred = profile
                break
            }
            if (inferred != null) {
                findings[index] = current.copy(
                    speaker = inferred.name,
                    confidence = 0.62f,
                    reason = "Предположительный владелец голоса по совпадающему месту звучания и ближайшей авторской ремарке; проверьте вручную"
                )
            }
        }
"""
text = text[:start] + new_block + text[end:]
source.write_text(text, encoding="utf-8")

tests = Path("app/src/test/java/ru/fbaudioprep/DialogueAnalyzerRegressionTest.kt")
tests.parent.mkdir(parents=True, exist_ok=True)
tests.write_text(r'''package ru.fbaudioprep

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Test

class DialogueAnalyzerRegressionTest {
    private val characters = listOf(
        CharacterProfile("Нико", listOf("Ник", "Нико"), "мужской"),
        CharacterProfile("Нурина", listOf("Нурина"), "женский"),
        CharacterProfile("Самуру", listOf("Самуру"), "женский"),
        CharacterProfile("ИмИн", listOf("ИмИн"), "женский"),
        CharacterProfile("ИскИн", listOf("ИсКин"), "мужской")
    )

    @Test
    fun femaleCallToNikoDoesNotMakeNikoTheSpeaker() {
        val text = """
            — Нико! Нико, мать твою! — раздался снаружи раздраженный женский голос с легкими рычащими нотками.

            — Да тут я, ту… АЙ! Да чтоб тебе ежики спинами теребонькали…
        """.trimIndent()

        val findings = DialogueAnalyzer(characters).analyzeBook(text)
        val call = findings.first()
        val reply = findings[1]

        assertEquals("Нико", call.addressedTo)
        assertNull("Имя в обращении не должно становиться говорящим", call.speaker)
        assertEquals("женский", call.voice)
        assertEquals("Нико", reply.speaker)
    }

    @Test
    fun quotedWelcomeWithPassiveAttributionIsDetectedAndLinkedToImIn() {
        val text = """
            «Нико, добро пожаловать!» — раздался в голове приветливый женский голос.

            — Можно подумать, я так надолго отключался, — проворчал я.

            «На две минуты и тридцать семь секунд», — тут же выдал отчет ИмИн.
        """.trimIndent()

        val findings = DialogueAnalyzer(characters).analyzeBook(text)
        val welcome = findings.firstOrNull { it.fragment.contains("Нико, добро пожаловать") }

        assertNotNull("Цитата с ремаркой «раздался голос» должна попасть в анализ", welcome)
        assertEquals("Нико", welcome!!.addressedTo)
        assertEquals("ИмИн", welcome.speaker)
        assertEquals("женский", welcome.voice)
    }

    @Test
    fun sameVoiceContinuationOutranksTheFemaleListenerWhoRepliesFirst() {
        val text = """
            — Пришел сигнал от командования, — раздался на общей волне второй женский голос.

            — Да, мэм, — сказала Нурина.

            — Зато вполне возможно общее потомство, — все тем же равномерным голосом заявила лейтенант Самуру.
        """.trimIndent()

        val findings = DialogueAnalyzer(characters).analyzeBook(text)
        val anonymousVoice = findings.first()

        assertEquals("Самуру", anonymousVoice.speaker)
        assertEquals("женский", anonymousVoice.voice)
        assertEquals(0.88f, anonymousVoice.confidence, 0.001f)
    }

    @Test
    fun explicitIskinSpeechTagIdentifiesIskinRatherThanTheAddressee() {
        val text = "«Проверка завершена», — сообщил ИскИн."
        val finding = DialogueAnalyzer(characters).analyzeBook(text).first()

        assertEquals("ИскИн", finding.speaker)
        assertEquals("мужской", finding.voice)
    }
}
''', encoding="utf-8")

gradle = Path("app/build.gradle.kts")
g = gradle.read_text(encoding="utf-8")
if 'testImplementation("junit:junit:4.13.2")' not in g:
    g += '\n\ndependencies {\n    testImplementation("junit:junit:4.13.2")\n}\n'
g, n = re.subn(r'versionCode\s*=\s*(\d+);\s*versionName\s*=\s*"2\.0\.2"',
               lambda m: f'versionCode = {int(m.group(1)) + 1}; versionName = "2.0.3"', g, count=1)
if n != 1:
    raise SystemExit("Could not bump app version to 2.0.3")
gradle.write_text(g, encoding="utf-8")
print("Applied dialogue attribution regression improvements; added four JVM tests; version 2.0.3.")
