from pathlib import Path
import re

root = Path("app/src/main/java/ru/fbaudioprep")
root.mkdir(parents=True, exist_ok=True)

(root / "CharacterDiscovery.kt").write_text(r'''package ru.fbaudioprep

/**
 * Discovers character candidates from explicit authorial speech tags.
 * A vocative inside the spoken text is never sufficient evidence of a speaker.
 */
object CharacterDiscovery {
    private const val verbs =
        "сказал|сказала|сказали|произнёс|произнес|произнесла|произнесли|" +
        "ответил|ответила|ответили|спросил|спросила|спросили|крикнул|крикнула|" +
        "прошептал|прошептала|буркнул|буркнула|проворчал|проворчала|" +
        "поинтересовался|поинтересовалась|заявил|заявила|выдал|выдала|" +
        "высказал|высказала|продолжил|продолжила|подхватил|подхватила|" +
        "отрапортовал|отрапортовала|процедил|процедила|пробормотал|пробормотала|" +
        "пояснил|пояснила|объяснил|объяснила|предложил|предложила|напомнил|напомнила|" +
        "попросил|попросила|потребовал|потребовала|посоветовал|посоветовала|" +
        "признался|призналась|отметил|отметила|заметил|заметила|переспросил|переспросила|" +
        "закричал|закричала|рявкнул|рявкнула|отчеканил|отчеканила|" +
        "прокомментировал|прокомментировала|отозвался|отозвалась|хмыкнул|хмыкнула|" +
        "вздохнул|вздохнула|вставил|вставила|согласился|согласилась|" +
        "воскликнул|воскликнула|добавил|добавила|уточнил|уточнила|возразил|возразила|" +
        "проговорил|проговорила|усмехнулся|усмехнулась|пообещал|пообещала|" +
        "подтвердил|подтвердила|объявил|объявила|распорядился|распорядилась|" +
        "пожаловался|пожаловалась|пошутил|пошутила|отмахнулся|отмахнулась"

    private val speechVerb = Regex("(?iu)(?<![\\p{L}\\p{M}])(?:$verbs)(?![\\p{L}\\p{M}])")
    private val namePattern = "([А-ЯЁ][а-яёА-ЯЁ\\p{M}-]{1,29})"
    private val afterVerb = Regex(
        "(?iu:$verbs)(?:\\s+[а-яё\\p{M}-]+){0,2}\\s+$namePattern"
    )
    private val beforeVerb = Regex(
        "(?<![\\p{L}\\p{M}])$namePattern(?:\\s+[а-яё\\p{M}-]+){0,2}\\s+(?iu:$verbs)"
    )
    private val stopWords = setOf(
        "что", "кто", "как", "зачем", "почему", "куда", "где", "когда", "это",
        "я", "он", "она", "ты", "мы", "вы", "мне", "меня", "тебе", "ему", "ей",
        "они", "них", "него", "нее", "неё", "зато", "ну", "после", "вот", "ведь",
        "тогда", "потом", "тут", "там", "да", "нет", "если", "хотя", "пока",
        "уже", "еще", "ещё", "просто", "сейчас", "конечно", "наверное", "однако",
        "поэтому", "впрочем", "значит", "кстати", "между", "раз", "наконец",
        "вдруг", "вместо", "но", "парень", "парня", "парню", "военный", "военного",
        "лига", "лиги", "лиге", "ранг", "ранга", "охотник", "охотника", "охотницу",
        "девушка", "девушки", "девушке", "мужчина", "мужчины", "женщина", "женщины",
        "старик", "старика", "старуха", "человек", "человека", "первый", "первая",
        "второй", "вторая", "один", "одна", "другой", "другая", "другие",
        "всё", "все", "сам", "сама", "сами", "лишь", "только", "разве",
        "может", "возможно", "словно", "будто", "рядом", "вокруг", "далеко",
        "последний", "следующий", "этот", "эта", "эти", "тот", "та", "те",
        "е-ранга", "с-ранга", "боковым", "боковой", "бокового", "слабейшее",
        "оружие", "член", "лидер", "капитан", "лейтенант", "сержант", "доктор",
        "командир", "командующий", "командующего", "начальник", "начальника",
        "генерал", "генерала", "следователь", "следователя",
        "юноша", "юноши", "юноше", "юношу", "мальчик", "мальчика"
    )

    private data class Accumulator(
        val name: String,
        val aliases: MutableSet<String> = linkedSetOf(),
        val genders: MutableMap<String, Int> = mutableMapOf()
    )

    private fun normalize(value: String): String = value.lowercase()
        .replace('ё', 'е')
        .filter { it.isLetterOrDigit() }

    private fun genderFromVerb(verb: String): String {
        val value = verb.lowercase()
        return when {
            value in setOf("произнёс", "произнес") -> "мужской"
            value.endsWith("лась") || value.endsWith("ла") -> "женский"
            value.endsWith("лся") || value.endsWith("л") -> "мужской"
            else -> "не задан"
        }
    }

    fun discover(bookText: String): List<CharacterProfile> {
        var paragraphs = bookText.replace("\r\n", "\n").replace("\r", "\n")
            .split(Regex("\n\\s*\n")).map { it.trim() }.filter { it.isNotBlank() }
        if (paragraphs.size < 50) {
            paragraphs = bookText.replace("\r\n", "\n").replace("\r", "\n")
                .split(Regex("\n+")).map { it.trim() }.filter { it.isNotBlank() }
        }

        val found = linkedMapOf<String, Accumulator>()
        for (paragraph in paragraphs) {
            if (!paragraph.contains('—') && !paragraph.contains('–')) continue
            val segments = paragraph.split(Regex("\\s*[—–]\\s*")).filter { it.isNotBlank() }
            for (segment in segments) {
                val verb = speechVerb.find(segment) ?: continue
                val nameMatch = afterVerb.find(segment) ?: beforeVerb.find(segment) ?: continue
                val surfaceName = nameMatch.groupValues[1].trim()
                val key = normalize(surfaceName)
                if (key.isBlank() || key in stopWords) continue

                val profile = found.getOrPut(key) { Accumulator(surfaceName) }
                profile.aliases += surfaceName
                val gender = genderFromVerb(verb.value)
                if (gender != "не задан") {
                    profile.genders[gender] = (profile.genders[gender] ?: 0) + 1
                }
            }
        }

        return found.values.map { profile ->
            val votes = profile.genders.values.sum()
            val gender = if (votes == 0) {
                "не задан"
            } else {
                val best = profile.genders.maxByOrNull { it.value }!!
                if (best.value.toFloat() / votes >= 0.8f) best.key else "не задан"
            }
            CharacterProfile(
                name = profile.name,
                aliases = profile.aliases.filterNot { normalize(it) == normalize(profile.name) },
                voice = gender
            )
        }.sortedByDescending { it.aliases.size }
    }
}
''', encoding="utf-8")

dialogue = root / "DialogueAnalyzer.kt"
s = dialogue.read_text(encoding="utf-8")
old_fields = '''    /** Character being addressed in the spoken words; this is not the speaker. */
    val addressedTo: String? = null
)'''
new_fields = '''    /** Character being addressed in the spoken words; this is not the speaker. */
    val addressedTo: String? = null,
    val contextBefore: String = "",
    val contextAfter: String = ""
)'''
if new_fields not in s:
    if old_fields not in s:
        raise SystemExit("Cannot locate DialogueFinding data class")
    s = s.replace(old_fields, new_fields, 1)

old_split = '''        val sourceParagraphs = text.split(Regex("\\\\r?\\\\n\\\\s*\\\\r?\\\\n"))
            .map { it.trim() }'''
new_split = '''        var sourceParagraphs = text.split(Regex("\\\\r?\\\\n\\\\s*\\\\r?\\\\n"))
            .map { it.trim() }.filter { it.isNotBlank() }
        if (sourceParagraphs.size < 50) {
            sourceParagraphs = text.split(Regex("\\\\r?\\\\n+"))
                .map { it.trim() }.filter { it.isNotBlank() }
        }'''
if new_split not in s:
    if old_split not in s:
        raise SystemExit("Cannot locate source paragraph splitting")
    s = s.replace(old_split, new_split, 1)

old_findings = '''        val findings = candidates.map { (_, paragraph) -> analyzeParagraph(paragraph) }.toMutableList()'''
new_findings = '''        val findings = candidates.map { (sourceIndex, paragraph) ->
            analyzeParagraph(paragraph).copy(
                contextBefore = sourceParagraphs.take(sourceIndex).takeLast(2)
                    .joinToString("\\\\n").takeLast(1800),
                contextAfter = sourceParagraphs.drop(sourceIndex + 1).take(2)
                    .joinToString("\\\\n").take(1800)
            )
        }.toMutableList()'''
if new_findings not in s:
    if old_findings not in s:
        raise SystemExit("Cannot locate DialogueFinding candidate mapping")
    s = s.replace(old_findings, new_findings, 1)
dialogue.write_text(s, encoding="utf-8")

main = root / "MainActivity.kt"
m = main.read_text(encoding="utf-8")
start = m.find("    private fun analyzeDialogues() {")
end = m.find("    private fun showDialogueReview()", start)
if start < 0 or end < 0:
    raise SystemExit("Cannot locate analyzeDialogues()")

method = r'''    private fun analyzeDialogues() {
        if (originalText.isBlank()) return

        val manualProfiles = loadCharacters()
        val discoveredProfiles = CharacterDiscovery.discover(originalText)
        val profiles = mergeCharacterProfiles(discoveredProfiles, manualProfiles)
        if (profiles != manualProfiles) saveCharacters(profiles)

        val analyzed = DialogueAnalyzer(profiles).analyzeBook(originalText)
        val neuralFindings = applyNeuralSpeakerRanker(analyzed, profiles)
        val findings = DialogueCorrectionStore.apply(this, originalText, neuralFindings)
        dialogueFindings = findings
        reviewDialoguesButton.isEnabled = findings.isNotEmpty()
        val known = findings.count { it.speaker != null }
        val uncertain = findings.size - known
        val neural = findings.count { it.reason.startsWith("Нейросеть:") }
        dialogueReport = buildString {
            appendLine("FB2 AudioPrep 2.0.9 — автоматический анализ говорящих")
            appendLine("Файл: " + sourceName)
            appendLine("Персонажей найдено автоматически: " + discoveredProfiles.size)
            appendLine("Найдено фрагментов: " + findings.size)
            appendLine("Определён говорящий: " + known)
            appendLine("Определено нейросетью: " + neural)
            appendLine("Требуют дополнительного анализа: " + uncertain)
            appendLine()
            findings.forEachIndexed { index, finding ->
                appendLine("Фрагмент " + (index + 1))
                appendLine("Говорящий: " + (finding.speaker ?: "не определён"))
                appendLine("Обращение: " + (finding.addressedTo ?: "не найдено"))
                appendLine("Голос: " + (finding.voice ?: "не определён"))
                appendLine("Уверенность: " + (finding.confidence * 100).toInt() + "%")
                appendLine("Причина: " + finding.reason)
                appendLine(finding.fragment)
                appendLine()
            }
            appendLine("Низкая уверенность не приводит к автоматическому назначению персонажа.")
        }
        report = if (report.isBlank()) dialogueReport else report + "\n\n" + dialogueReport
        status.text = "Автоматический анализ завершён.\nПерсонажей: " + discoveredProfiles.size +
            "\nФрагментов: " + findings.size + "\nГоворящий определён: " + known +
            "\nНужен дополнительный анализ: " + uncertain
        preview.text = dialogueReport.take(8000)
    }

    private fun normalizeCharacterName(value: String): String = value.lowercase()
        .replace('ё', 'е')
        .filter { it.isLetterOrDigit() }

    private fun mergeCharacterProfiles(
        discovered: List<CharacterProfile>,
        manual: List<CharacterProfile>
    ): List<CharacterProfile> {
        val merged = linkedMapOf<String, CharacterProfile>()
        discovered.forEach { profile ->
            merged[normalizeCharacterName(profile.name)] = profile
        }
        manual.forEach { profile ->
            val key = normalizeCharacterName(profile.name)
            val automatic = merged[key]
            merged[key] = if (automatic == null) {
                profile
            } else {
                profile.copy(
                    aliases = (automatic.aliases + profile.aliases + automatic.name)
                        .distinctBy { normalizeCharacterName(it) },
                    voice = profile.voice.takeUnless { it.isBlank() || it == "не задан" }
                        ?: automatic.voice
                )
            }
        }
        return merged.values.toList()
    }

    private fun applyNeuralSpeakerRanker(
        findings: List<DialogueFinding>,
        profiles: List<CharacterProfile>
    ): List<DialogueFinding> {
        if (profiles.size < 2) return findings
        val modelDirectory = File(filesDir, "voice-models/speaker-csn-v1")
        val modelFile = File(modelDirectory, "speaker-csn-int8.onnx")
        val tokenizerFile = File(modelDirectory, "tokenizer.json")
        if (!modelFile.isFile || !tokenizerFile.isFile) return findings

        return try {
            NeuralSpeakerRanker(modelFile, tokenizerFile).use { ranker ->
                findings.map { finding ->
                    if (finding.speaker != null) return@map finding
                    val candidates = profiles.filterNot { profile ->
                        finding.addressedTo?.let {
                            normalizeCharacterName(profile.name) == normalizeCharacterName(it)
                        } ?: false
                    }.map { profile ->
                        val gender = when (profile.voice.lowercase()) {
                            "женский", "female", "f" -> "female"
                            "мужской", "male", "m" -> "male"
                            else -> "unknown"
                        }
                        NeuralSpeakerCandidate(profile.name, profile.aliases, gender)
                    }
                    if (candidates.size < 2) return@map finding

                    val quote = extractSpeechForNeuralModel(finding.fragment)
                    if (quote.isBlank()) return@map finding
                    val ranking = ranker.rank(
                        quote,
                        finding.contextBefore,
                        finding.contextAfter,
                        candidates
                    )
                    val top = ranking.firstOrNull() ?: return@map finding
                    val secondProbability = ranking.getOrNull(1)?.probability ?: 0f
                    val margin = top.probability - secondProbability
                    if (top.probability < 0.80f || margin < 0.20f) return@map finding

                    val profile = profiles.firstOrNull {
                        normalizeCharacterName(it.name) == normalizeCharacterName(top.candidate.name)
                    } ?: return@map finding
                    finding.copy(
                        speaker = profile.name,
                        voice = profile.voice.takeUnless { it.isBlank() || it == "не задан" }
                            ?: finding.voice,
                        confidence = top.probability,
                        reason = "Нейросеть: кандидат " + profile.name + " получил " +
                            (top.probability * 100).toInt() + "%, отрыв " +
                            (margin * 100).toInt() + " п.п."
                    )
                }
            }
        } catch (_: Exception) {
            findings
        }
    }

    private fun extractSpeechForNeuralModel(fragment: String): String {
        val quoted = Regex("«([^»]*)»|“([^”]*)”|\\\"([^\\\"]*)\\\"")
            .findAll(fragment)
            .mapNotNull { match -> match.groupValues.drop(1).firstOrNull { it.isNotEmpty() } }
            .joinToString(" ")
        if (quoted.isNotBlank()) return quoted

        val firstDash = fragment.indexOfFirst { it == '—' || it == '–' }
        if (firstDash < 0) return fragment
        val tail = fragment.substring(firstDash + 1)
        val secondDash = tail.indexOfFirst { it == '—' || it == '–' }
        if (secondDash >= 0) return tail.substring(0, secondDash).trim()
        val passive = Regex("(?iu)(раздался|раздалась|раздались|послышался|послышалась|прозвучал|прозвучала|донёсся|донесся)")
            .find(tail)
        return (if (passive == null) tail else tail.substring(0, passive.range.first)).trim()
    }

'''
m = m[:start] + method + m[end:]
main.write_text(m, encoding="utf-8")

tests = Path("app/src/test/java/ru/fbaudioprep/CharacterDiscoveryTest.kt")
tests.parent.mkdir(parents=True, exist_ok=True)
tests.write_text(r'''package ru.fbaudioprep

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Test

class CharacterDiscoveryTest {
    @Test
    fun discoversNamedSpeakersAndTheirGrammaticalGender() {
        val profiles = CharacterDiscovery.discover(
            """
            — Привет! — сказала Нурина.

            — Добрый день! — ответил Дима.
            """.trimIndent()
        )
        val nurina = profiles.first { it.name == "Нурина" }
        val dima = profiles.first { it.name == "Дима" }
        assertEquals("женский", nurina.voice)
        assertEquals("мужской", dima.voice)
    }

    @Test
    fun vocativeAndPassiveFemaleVoiceDoNotCreateNikoAsSpeaker() {
        val profiles = CharacterDiscovery.discover(
            "— Нико! Нико, мать твою! — раздался снаружи раздражённый женский голос."
        )
        assertFalse(profiles.any { it.name.equals("Нико", ignoreCase = true) })
    }

    @Test
    fun mixedCaseAiCharacterNameIsDiscovered() {
        val profiles = CharacterDiscovery.discover(
            "«На две минуты и тридцать семь секунд», — тут же выдал отчет ИмИн."
        )
        assertEquals("ИмИн", profiles.single().name)
        assertEquals("мужской", profiles.single().voice)
    }

    @Test
    fun firstPersonPronounIsNotInventedAsCharacter() {
        val profiles = CharacterDiscovery.discover("— Не начинай, — буркнул я.")
        assertEquals(emptyList<CharacterProfile>(), profiles)
    }
}
''', encoding="utf-8")

gpath = Path("app/build.gradle.kts")
g = gpath.read_text(encoding="utf-8")
g, n = re.subn(r'versionCode\s*=\s*(\d+);\s*versionName\s*=\s*"2\.0\.8"',
               lambda m: f'versionCode = {int(m.group(1)) + 1}; versionName = "2.0.9"', g, count=1)
if n != 1:
    raise SystemExit("Could not bump app version to 2.0.9")
gpath.write_text(g, encoding="utf-8")
print("Added automatic character discovery, context-aware neural fallback and regression tests; version 2.0.9.")
