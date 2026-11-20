from pathlib import Path
import re

root = Path("app/src/main/java/ru/fbaudioprep")

(root / "CharacterVoiceAssignmentStore.kt").write_text(r'''package ru.fbaudioprep

import android.content.Context
import org.json.JSONObject
import java.security.MessageDigest

/**
 * Stable per-book character -> voice assignment.
 * Automatic choices are remembered; explicit user choices are never replaced.
 */
object CharacterVoiceAssignmentStore {
    private const val PREFS = "fb2_character_voice_assignments"

    private fun bookKey(bookText: String): String {
        val digest = MessageDigest.getInstance("SHA-256").digest(bookText.toByteArray(Charsets.UTF_8))
        return "book_" + digest.joinToString("") { "%02x".format(it) }
    }

    private fun normalize(value: String): String = value.lowercase()
        .replace('ё', 'е')
        .replace(Regex("[\\u0300-\\u036f]"), "")
        .replace(Regex("[^\\p{L}\\p{N}]"), "")

    private fun read(context: Context, bookText: String): MutableMap<String, String> {
        val raw = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString(bookKey(bookText), null) ?: return linkedMapOf()
        return try {
            val json = JSONObject(raw)
            buildMap {
                val keys = json.keys()
                while (keys.hasNext()) {
                    val key = keys.next()
                    val voice = json.optString(key)
                    if (key.isNotBlank() && voice.isNotBlank()) put(key, voice)
                }
            }.toMutableMap()
        } catch (_: Exception) {
            linkedMapOf()
        }
    }

    private fun write(context: Context, bookText: String, values: Map<String, String>) {
        val json = JSONObject()
        values.forEach { (name, voice) -> if (name.isNotBlank() && voice.isNotBlank()) json.put(name, voice) }
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
            .putString(bookKey(bookText), json.toString()).apply()
    }

    /** Save an explicit voice choice for one character in this book. */
    fun setVoice(context: Context, bookText: String, character: String, voiceId: String) {
        require(character.isNotBlank() && voiceId.isNotBlank())
        val values = read(context, bookText)
        values[normalize(character)] = voiceId
        write(context, bookText, values)
    }

    /** Remove a character's saved voice so it can be assigned automatically again. */
    fun clearVoice(context: Context, bookText: String, character: String) {
        val values = read(context, bookText)
        values.remove(normalize(character))
        write(context, bookText, values)
    }

    /**
     * Allocate distinct available voices in character order and persist them per book.
     * If a gender has no unused voice left, the best matching voice is shared as a fallback.
     */
    fun assign(
        context: Context,
        bookText: String,
        profiles: List<CharacterProfile>,
        narratorVoice: String,
        availableVoices: List<String>
    ): Map<String, String> {
        if (bookText.isBlank() || profiles.isEmpty() || availableVoices.isEmpty()) return emptyMap()
        val saved = read(context, bookText)
        val used = saved.values.toMutableSet()
        val output = linkedMapOf<String, String>()

        fun voiceGender(id: String): String? {
            val base = id.substringBeforeLast('.').lowercase()
            return when {
                Regex("""(^|[_-])f\d""").containsMatchIn(base) -> "женский"
                Regex("""(^|[_-])m\d""").containsMatchIn(base) -> "мужской"
                else -> null
            }
        }

        profiles.forEach { profile ->
            val gender = profile.voice.takeIf { it == "женский" || it == "мужской" }
            val names = (profile.aliases + profile.name).map(::normalize).filter { it.isNotBlank() }.distinct()
            if (names.isEmpty() || gender == null) return@forEach

            val existing = names.firstNotNullOfOrNull { saved[it] }
                ?.takeIf { it in availableVoices && voiceGender(it) == gender }
            val chosen = existing ?: run {
                val candidates = availableVoices.filter { voiceGender(it) == gender }
                candidates.firstOrNull { it != narratorVoice && it !in used }
                    ?: candidates.firstOrNull { it != narratorVoice }
                    ?: candidates.firstOrNull()
            } ?: return@forEach

            names.forEach { name ->
                output[name] = chosen
                if (saved[name] == null) saved[name] = chosen
            }
            used += chosen
        }

        // Retain saved aliases even when the character is absent from this chapter's profile list.
        saved.forEach { (name, voice) -> output.putIfAbsent(name, voice) }
        write(context, bookText, saved)
        return output
    }
}
''', encoding="utf-8")

(root / "TeraTtsV2SpeechSegmenter.kt").write_text(r'''package ru.fbaudioprep

/**
 * Splits narration and spoken lines, matching each utterance to the most relevant
 * dialogue finding. Authorial voice descriptions outrank inferred gender and names.
 */
data class TeraTtsSpeechPiece(val text: String, val voiceId: String, val kind: String)

object TeraTtsV2SpeechSegmenter {
    private val quoteRegex = Regex("«([^»]+)»|“([^”]+)”|\"([^\"]+)\"")
    private val speechTagStart = Regex(
        """(?iu)\b(?:раздал(?:ся|ась|ось|ись)|прозвучал(?:а|о|и)?|сказал(?:а|и)?|произнёс|произнес(?:ла|ли)?|ответил(?:а|и)?|крикнул(?:а|и)?|спросил(?:а|и)?|прошептал(?:а|и)?|проговорил(?:а|и)?|буркнул(?:а|и)?|проворчал(?:а|и)?)\b"""
    )
    private val femaleCue = Regex(
        """(?iu)(?:женск\w*\s+голос|голос\w*\s+женщин\w*|женщин\w*\s+голос)"""
    )
    private val maleCue = Regex(
        """(?iu)(?:мужск\w*\s+голос|голос\w*\s+мужчин\w*|мужчин\w*\s+голос)"""
    )

    fun build(
        bookText: String,
        findings: List<DialogueFinding>,
        profiles: List<CharacterProfile>,
        narratorVoice: String,
        availableVoices: List<String>,
        maxChars: Int = 180,
        characterVoiceAssignments: Map<String, String> = emptyMap()
    ): List<TeraTtsSpeechPiece> {
        val profileByName = profiles.flatMap { profile ->
            (profile.aliases + profile.name).map { normalize(it) to profile }
        }.toMap()
        val assignmentByName = characterVoiceAssignments.entries.associate { normalize(it.key) to it.value }
        val paragraphs = bookText.replace("\r\n", "\n").replace('\r', '\n')
            .split(Regex("\\n\\s*\\n")).map { it.trim() }.filter { it.isNotBlank() }
        val output = mutableListOf<TeraTtsSpeechPiece>()

        fun appendSpeech(spoken: String, localContext: String, paragraph: String) {
            if (spoken.isBlank()) return
            val finding = bestFinding(findings, paragraph, spoken)
            val speaker = finding?.speaker
            val profile = speaker?.let { profileByName[normalize(it)] }
            val gender = explicitGender(localContext)
                ?: finding?.voice?.takeIf { it == "женский" || it == "мужской" }
                ?: profile?.voice?.takeIf { it == "женский" || it == "мужской" }
            val assigned = speaker?.let { assignmentByName[normalize(it)] }
                ?: profile?.let { assignmentByName[normalize(it.name)] }
            val voice = assigned?.takeIf { it in availableVoices }
                ?: gender?.let { chooseVoice(it, narratorVoice, availableVoices) }
                ?: narratorVoice
            val kind = if (gender == null && assigned == null) "dialogue-fallback" else "dialogue"
            addChunks(output, spoken, voice, kind, maxChars)
        }

        paragraphs.forEach { paragraph ->
            val matches = quoteRegex.findAll(paragraph).toList()
            if (matches.isNotEmpty()) {
                var cursor = 0
                matches.forEachIndexed { index, match ->
                    if (match.range.first > cursor) {
                        addChunks(output, paragraph.substring(cursor, match.range.first), narratorVoice, "narration", maxChars)
                    }
                    val spoken = match.groups.drop(1).firstOrNull { it?.value != null }?.value ?: match.value
                    val tailEnd = matches.getOrNull(index + 1)?.range?.first ?: paragraph.length
                    val tail = paragraph.substring(match.range.last + 1, tailEnd)
                    val before = paragraph.substring(0, match.range.first)
                    appendSpeech(spoken, tail + " " + before, paragraph)
                    cursor = match.range.last + 1
                }
                if (cursor < paragraph.length) {
                    addChunks(output, paragraph.substring(cursor), narratorVoice, "narration", maxChars)
                }
            } else {
                val trimmed = paragraph.trimStart()
                if (trimmed.startsWith("—") || trimmed.startsWith("–")) {
                    val dash = paragraph.indexOfFirst { it == '—' || it == '–' }
                    val start = dash + 1
                    val afterDash = paragraph.substring(start)
                    val tag = speechTagStart.find(afterDash)
                    val spokenEnd = if (tag != null) start + tag.range.first else paragraph.length
                    val spoken = paragraph.substring(start, spokenEnd).trim()
                    val tail = if (spokenEnd < paragraph.length) paragraph.substring(spokenEnd) else ""
                    appendSpeech(spoken, tail, paragraph)
                    if (tail.isNotBlank()) addChunks(output, tail, narratorVoice, "narration", maxChars)
                } else {
                    addChunks(output, paragraph, narratorVoice, "narration", maxChars)
                }
            }
        }
        return output
    }

    private fun bestFinding(
        findings: List<DialogueFinding>,
        paragraph: String,
        spoken: String
    ): DialogueFinding? {
        val p = normalize(paragraph)
        val s = normalize(spoken)
        if (s.isBlank()) return null
        return findings.asSequence().map { finding ->
            val f = normalize(finding.fragment)
            val score = when {
                f.isBlank() -> 0
                f == p -> 1000
                f.contains(s) -> 900 + s.length.coerceAtMost(90)
                s.contains(f) -> 800 + f.length.coerceAtMost(90)
                p.contains(f) -> 500 + f.length.coerceAtMost(90)
                else -> {
                    val tokens = s.split(Regex("[^\\p{L}\\p{N}]+")).filter { it.length >= 3 }.toSet()
                    val matched = tokens.count { f.contains(it) }
                    if (tokens.isEmpty()) 0 else (matched * 100 / tokens.size)
                }
            }
            finding to score
        }.maxByOrNull { it.second }?.takeIf { it.second >= 30 }?.first
    }

    private fun explicitGender(context: String): String? = when {
        femaleCue.containsMatchIn(context) -> "женский"
        maleCue.containsMatchIn(context) -> "мужской"
        else -> null
    }

    private fun chooseVoice(gender: String, narrator: String, available: List<String>): String {
        fun matches(id: String): Boolean {
            val base = id.substringBeforeLast('.').lowercase()
            return if (gender == "женский") Regex("""(^|[_-])f\d""").containsMatchIn(base)
            else Regex("""(^|[_-])m\d""").containsMatchIn(base)
        }
        val candidates = available.filter(::matches)
        return candidates.firstOrNull { it != narrator } ?: candidates.firstOrNull() ?: narrator
    }

    private fun addChunks(
        target: MutableList<TeraTtsSpeechPiece>,
        text: String,
        voice: String,
        kind: String,
        maxChars: Int
    ) {
        SpeechTextChunker.chunk(text, maxChars).forEach {
            if (it.isNotBlank()) target += TeraTtsSpeechPiece(it, voice, kind)
        }
    }

    private fun normalize(value: String): String = value.lowercase()
        .replace('ё', 'е')
        .replace(Regex("[\\u0300-\\u036f]"), "")
        .replace(Regex("[^\\p{L}\\p{N}]"), "")
}
''', encoding="utf-8")

# Connect the persistent per-book character voice map to the existing playback queue.
p = root / "MainActivity.kt"
s = p.read_text(encoding="utf-8")
old = '''        return TeraTtsV2SpeechSegmenter.build(
            bookText = text,
            findings = dialogueFindings,
            profiles = loadCharactersForBook(originalText),
            narratorVoice = selectedTtsVoice,
            availableVoices = voices,
            maxChars = 180
        )'''
new = '''        val profiles = loadCharactersForBook(originalText)
        val assignments = CharacterVoiceAssignmentStore.assign(
            this, originalText, profiles, selectedTtsVoice, voices
        )
        return TeraTtsV2SpeechSegmenter.build(
            bookText = text,
            findings = dialogueFindings,
            profiles = profiles,
            narratorVoice = selectedTtsVoice,
            availableVoices = voices,
            maxChars = 180,
            characterVoiceAssignments = assignments
        )'''
if old not in s:
    raise SystemExit("v49: cannot find the existing speech queue builder call")
s = s.replace(old, new, 1)
p.write_text(s, encoding="utf-8")

tests = Path("app/src/test/java/ru/fbaudioprep/TeraTtsV2SpeechSegmenterTest.kt")
tests.parent.mkdir(parents=True, exist_ok=True)
tests.write_text(r'''package ru.fbaudioprep

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class TeraTtsV2SpeechSegmenterTest {
    private val voices = listOf("ru_f1", "ru_f2", "ru_m1", "ru_m5")

    @Test
    fun quotedNikoLineUsesExplicitFemaleVoiceFromAuthorTag() {
        val text = "«Нико, добро пожаловать!» раздался в голове приветливый женский голос."
        val findings = listOf(
            DialogueFinding(
                fragment = text,
                speaker = null,
                voice = null,
                confidence = 0.4f,
                reason = "Недостаточно контекста"
            )
        )
        val pieces = TeraTtsV2SpeechSegmenter.build(
            text, findings, emptyList(), "ru_m5", voices
        )
        val spoken = pieces.first { it.kind == "dialogue" }
        assertEquals("Нико, добро пожаловать!", spoken.text)
        assertEquals("ru_f1", spoken.voiceId)
    }

    @Test
    fun dashNikoLineUsesExplicitFemaleVoiceFromAuthorTag() {
        val text = "— Нико! Нико, мать твою! раздался снаружи раздражённый женский голос с лёгкими рычащими нотками."
        val findings = listOf(
            DialogueFinding(
                fragment = text,
                speaker = null,
                voice = null,
                confidence = 0.4f,
                reason = "Недостаточно контекста"
            )
        )
        val pieces = TeraTtsV2SpeechSegmenter.build(
            text, findings, emptyList(), "ru_m5", voices
        )
        val spoken = pieces.first { it.kind == "dialogue" }
        assertEquals("Нико! Нико, мать твою!", spoken.text)
        assertEquals("ru_f1", spoken.voiceId)
    }

    @Test
    fun explicitCharacterVoiceAssignmentWinsOverGenderDefault() {
        val text = "— ИсКин, ответь. — Сейчас."
        val findings = listOf(
            DialogueFinding(
                fragment = "— ИсКин, ответь.",
                speaker = "ИсКин",
                voice = "мужской",
                confidence = 0.98f,
                reason = "Говорящий определён по контексту"
            )
        )
        val pieces = TeraTtsV2SpeechSegmenter.build(
            text, findings, emptyList(), "ru_f1", voices,
            characterVoiceAssignments = mapOf("искин" to "ru_m1")
        )
        assertTrue(pieces.any { it.voiceId == "ru_m1" && it.kind == "dialogue" })
    }
}
''', encoding="utf-8")

# Bump the human-readable version; the workflow computes versionCode from its run number.
gradle = Path("app/build.gradle.kts")
g = gradle.read_text(encoding="utf-8")
if 'versionName = "2.1.6"' not in g:
    raise SystemExit("v49: expected versionName 2.1.6")
g = g.replace('versionName = "2.1.6"', 'versionName = "2.1.7"', 1)
gradle.write_text(g, encoding="utf-8")

print("v49: match individual utterances, prioritize explicit voice cues, persist per-book character voice assignments, add Nico/IsKin regression tests, version 2.1.7.")
