from pathlib import Path

root = Path("app/src/main/java/ru/fbaudioprep")
engine = root / "TeraTtsV2OnnxEngine.kt"
if not engine.is_file():
    raise SystemExit("v34 ONNX engine source is missing")

accentizer = root / "TeraTtsV2DictionaryAccentizer.kt"
accentizer.write_text(r'''package ru.fbaudioprep

import org.json.JSONObject
import java.io.File
import java.io.FileInputStream
import java.io.InputStreamReader
import java.util.Locale
import java.util.zip.GZIPInputStream

/**
 * Lightweight port of TeraTTSv2's RUAccent dictionary mode.
 * It deliberately leaves unknown words and ambiguous homographs unchanged.
 * Neural stress prediction remains a separate optional model pack.
 */
class TeraTtsV2DictionaryAccentizer private constructor(
    private val accents: Map<String, String>,
    private val yoWords: Map<String, String>
) {
    companion object {
        fun load(dictionaryDirectory: File): TeraTtsV2DictionaryAccentizer {
            val accentsFile = File(dictionaryDirectory, "accents.json.gz")
            val yoFile = File(dictionaryDirectory, "yo_words.json.gz")
            require(accentsFile.isFile && yoFile.isFile) {
                "Не найдены словари ударений TeraTTSv2"
            }
            return TeraTtsV2DictionaryAccentizer(
                readGzipJson(accentsFile),
                readGzipJson(yoFile)
            )
        }

        private fun readGzipJson(file: File): Map<String, String> {
            val jsonText = GZIPInputStream(FileInputStream(file)).use { input ->
                InputStreamReader(input, Charsets.UTF_8).use { it.readText() }
            }
            val json = JSONObject(jsonText)
            val result = HashMap<String, String>(json.length())
            val keys = json.keys()
            while (keys.hasNext()) {
                val key = keys.next()
                val value = json.optString(key, "")
                if (value.isNotEmpty()) result[key.lowercase(Locale.ROOT)] = value
            }
            return result
        }
    }

    fun processTaggedRussian(text: String): String {
        val word = Regex("[A-Za-zА-Яа-яЁё]+")
        return word.replace(text) { match ->
            accentWord(match.value)
        }
    }

    private fun accentWord(source: String): String {
        if (source.contains('+') || source.any { it.code == 769 }) return source
        val lower = source.lowercase(Locale.ROOT)
        val yo = yoWords[lower] ?: source
        val normalized = preserveCase(source, yo)
        val accented = accents[normalized.lowercase(Locale.ROOT)] ?: normalized.lowercase(Locale.ROOT)
        if (accented == normalized.lowercase(Locale.ROOT) || !accented.contains('+')) {
            return normalized
        }
        val output = StringBuilder(normalized)
        var inserted = 0
        accented.forEachIndexed { index, ch ->
            if (ch == '+') {
                output.insert(index + inserted, '+')
                inserted++
            }
        }
        return output.toString()
    }

    private fun preserveCase(source: String, target: String): String {
        val letters = source.filter { it.isLetter() }
        return when {
            letters.isNotEmpty() && letters == letters.uppercase(Locale.ROOT) ->
                target.uppercase(Locale.ROOT)
            source.firstOrNull()?.isUpperCase() == true ->
                target.replaceFirstChar { it.titlecase(Locale.ROOT) }
            else -> target
        }
    }
}
''', encoding="utf-8")

s = engine.read_text(encoding="utf-8")
s = s.replace(
    '    private var tokenTable: IntArray? = null\n',
    '    private var tokenTable: IntArray? = null\n    private var dictionaryAccentizer: TeraTtsV2DictionaryAccentizer? = null\n'
)
s = s.replace(
    '        release = directory\n        tokenTable = table\n',
    '''        release = directory
        tokenTable = table
        val dictionaryDirectory = File(directory, "ruaccent/dictionary")
        dictionaryAccentizer = if (
            File(dictionaryDirectory, "accents.json.gz").isFile &&
            File(dictionaryDirectory, "yo_words.json.gz").isFile
        ) TeraTtsV2DictionaryAccentizer.load(dictionaryDirectory) else null
'''
)
s = s.replace(
    '            val prepared = TeraTtsV2Text.prepare(taggedText, tokenTable!!)\n',
    '            val accentedInput = dictionaryAccentizer?.processTaggedRussian(taggedText) ?: taggedText\n            val prepared = TeraTtsV2Text.prepare(accentedInput, tokenTable!!)\n'
)
s = s.replace(
    '        tokenTable = null; release = null\n',
    '        tokenTable = null; dictionaryAccentizer = null; release = null\n'
)
old = '''        val body = text.substring(4, text.length - 5)
        require(body.isNotBlank()) { "Пустой текст" }
        val spaced = body
            .replace(Regex("([,.!?;:…])(?=[^\\\\s])"), "$1 ")
'''
new = '''        val body = text.substring(4, text.length - 5)
        require(body.isNotBlank()) { "Пустой текст" }
        // AccentEngine in FB2AudioPrep stores stress as U+0301 after a vowel.
        // TeraTTSv2 expects its explicit '+' marker immediately before that vowel.
        val terattsMarked = buildString {
            var index = 0
            while (index < body.length) {
                val current = body[index]
                if (index + 1 < body.length && body[index + 1].code == 769) {
                    append('+')
                    append(current)
                    index += 2
                } else {
                    append(current)
                    index++
                }
            }
        }
        val spaced = terattsMarked
            .replace(Regex("([,.!?;:…])(?=[^\\\\s])"), "$1 ")
'''
if old not in s:
    raise SystemExit("Could not find TeraTtsV2Text stress-normalization insertion point")
s = s.replace(old, new)
engine.write_text(s, encoding="utf-8")
print("Added dictionary-mode RUAccent, acute-to-plus stress conversion, and offline Russian preprocessing.")
