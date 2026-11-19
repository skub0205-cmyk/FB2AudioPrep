from pathlib import Path
import re

root = Path("app/src/main/java/ru/fbaudioprep")

# Fix the actual memory failure: accents.json.gz expands to a very large JSON
# document. Never read the decompressed dictionary into one giant String/Map.
accentizer = root / "TeraTtsV2DictionaryAccentizer.kt"
accentizer.write_text(r'''package ru.fbaudioprep

import android.database.Cursor
import android.database.sqlite.SQLiteDatabase
import android.util.JsonReader
import android.util.JsonToken
import java.io.File
import java.io.FileInputStream
import java.io.InputStreamReader
import java.util.Locale
import java.util.zip.GZIPInputStream

/**
 * Disk-backed RUAccent dictionary. The upstream accents JSON expands to hundreds
 * of megabytes; streaming it into SQLite avoids a single huge String and an
 * equally huge in-memory HashMap on Android devices.
 */
class TeraTtsV2DictionaryAccentizer private constructor(
    private val database: SQLiteDatabase
) : AutoCloseable {
    companion object {
        private const val DB_NAME = "teratts-dictionary.sqlite"
        private const val META_NAME = "teratts-dictionary.meta"

        fun load(dictionaryDirectory: File): TeraTtsV2DictionaryAccentizer {
            val accents = File(dictionaryDirectory, "accents.json.gz")
            val yo = File(dictionaryDirectory, "yo_words.json.gz")
            require(accents.isFile && yo.isFile) {
                "Не найдены словари ударений TeraTTSv2"
            }
            val dbFile = File(dictionaryDirectory, DB_NAME)
            val metaFile = File(dictionaryDirectory, META_NAME)
            val signature = listOf(accents, yo).joinToString("|") {
                it.name + ":" + it.length() + ":" + it.lastModified()
            }
            if (!dbFile.isFile || !metaFile.isFile || metaFile.readText() != signature) {
                dbFile.delete()
                File(dbFile.parentFile, dbFile.name + "-journal").delete()
                val db = SQLiteDatabase.openOrCreateDatabase(dbFile.absolutePath, null)
                try {
                    db.execSQL("PRAGMA journal_mode=DELETE")
                    db.execSQL("PRAGMA synchronous=NORMAL")
                    db.execSQL("CREATE TABLE accents (word TEXT PRIMARY KEY NOT NULL, value TEXT NOT NULL)")
                    db.execSQL("CREATE TABLE yo_words (word TEXT PRIMARY KEY NOT NULL, value TEXT NOT NULL)")
                    importJsonObject(db, accents, "accents")
                    importJsonObject(db, yo, "yo_words")
                } catch (error: Throwable) {
                    db.close()
                    dbFile.delete()
                    throw error
                }
                db.close()
                metaFile.writeText(signature)
            }
            return TeraTtsV2DictionaryAccentizer(
                SQLiteDatabase.openDatabase(dbFile.absolutePath, null, SQLiteDatabase.OPEN_READONLY)
            )
        }

        private fun importJsonObject(db: SQLiteDatabase, file: File, table: String) {
            require(table == "accents" || table == "yo_words")
            val statement = db.compileStatement(
                "INSERT OR REPLACE INTO $table(word, value) VALUES (?, ?)"
            )
            var pending = 0
            db.beginTransaction()
            try {
                GZIPInputStream(FileInputStream(file), 64 * 1024).use { gzip ->
                    JsonReader(InputStreamReader(gzip, Charsets.UTF_8)).use { reader ->
                        reader.beginObject()
                        while (reader.hasNext()) {
                            val key = reader.nextName().lowercase(Locale.ROOT)
                            if (reader.peek() == JsonToken.STRING) {
                                val value = reader.nextString()
                                if (value.isNotEmpty()) {
                                    statement.clearBindings()
                                    statement.bindString(1, key)
                                    statement.bindString(2, value)
                                    statement.executeInsert()
                                    pending++
                                    if (pending >= 20_000) {
                                        db.setTransactionSuccessful()
                                        db.endTransaction()
                                        db.beginTransaction()
                                        pending = 0
                                    }
                                }
                            } else {
                                reader.skipValue()
                            }
                        }
                        reader.endObject()
                    }
                }
                db.setTransactionSuccessful()
            } finally {
                db.endTransaction()
                statement.close()
            }
        }
    }

    override fun close() {
        try { database.close() } catch (_: Throwable) {}
    }

    fun processTaggedRussian(text: String): String {
        val word = Regex("[A-Za-zА-Яа-яЁё]+")
        return word.replace(text) { match -> accentWord(match.value) }
    }

    private fun lookup(table: String, word: String): String? {
        require(table == "accents" || table == "yo_words")
        var cursor: Cursor? = null
        return try {
            cursor = database.rawQuery(
                "SELECT value FROM $table WHERE word = ? LIMIT 1",
                arrayOf(word.lowercase(Locale.ROOT))
            )
            if (cursor.moveToFirst()) cursor.getString(0) else null
        } finally {
            cursor?.close()
        }
    }

    private fun accentWord(source: String): String {
        if (source.contains('+') || source.any { it.code == 769 }) return source
        val yo = lookup("yo_words", source) ?: source
        val normalized = preserveCase(source, yo)
        val accented = lookup("accents", normalized) ?: normalized.lowercase(Locale.ROOT)
        if (accented == normalized.lowercase(Locale.ROOT) || !accented.contains('+')) return normalized
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
            letters.isNotEmpty() && letters == letters.uppercase(Locale.ROOT) -> target.uppercase(Locale.ROOT)
            source.firstOrNull()?.isUpperCase() == true -> target.replaceFirstChar { it.titlecase(Locale.ROOT) }
            else -> target
        }
    }
}
''', encoding="utf-8")

engine = root / "TeraTtsV2OnnxEngine.kt"
engine_text = engine.read_text(encoding="utf-8")
old_close = """        tokenTable = null; dictionaryAccentizer = null; release = null
"""
new_close = """        tokenTable = null
        try { dictionaryAccentizer?.close() } catch (_: Throwable) {}
        dictionaryAccentizer = null
        release = null
"""
if new_close not in engine_text:
    assert old_close in engine_text
    engine_text = engine_text.replace(old_close, new_close, 1)
    engine.write_text(engine_text, encoding="utf-8")

layout = root / "AudiotomeHomeLayout.kt"
s = layout.read_text(encoding="utf-8")

old = '''        val people = buttons.filter {
            listOf("Персонажи", "голос", "диалог", "говорящ").any { token -> it.text.toString().contains(token, true) }
        }
        val preparation = buttons.filter { it !in library && it !in people }
'''
new = '''        val audio = buttons.filter {
            val label = it.text.toString()
            listOf("TeraTTS", "озвуч", "загрузк", "модель озвучивания").any { token -> label.contains(token, true) }
        }
        val people = buttons.filter {
            it !in audio && listOf("Персонажи", "голос", "диалог", "говорящ").any { token -> it.text.toString().contains(token, true) }
        }
        val preparation = buttons.filter { it !in library && it !in people && it !in audio }
'''
assert old in s
s = s.replace(old, new, 1)

old = '''        val rail = LinearLayout(activity).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.TOP or Gravity.CENTER_HORIZONTAL
            setPadding(dp(activity, 5), dp(activity, 14), dp(activity, 5), dp(activity, 10))
            setBackgroundColor(Color.rgb(8, 20, 34))
        }
        shell.addView(rail, LinearLayout.LayoutParams(dp(activity, 62), -1))
'''
new = '''        val rail = LinearLayout(activity).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.TOP or Gravity.CENTER_HORIZONTAL
            setPadding(dp(activity, 5), 0, dp(activity, 5), 0)
            setBackgroundColor(Color.rgb(8, 20, 34))
        }
        shell.addView(rail, LinearLayout.LayoutParams(dp(activity, 62), -1))
        val navScroll = ScrollView(activity).apply {
            isFillViewport = true
            clipToPadding = false
            overScrollMode = View.OVER_SCROLL_NEVER
            setPadding(0, dp(activity, 30), 0, dp(activity, 18))
        }
        val navItems = LinearLayout(activity).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.TOP or Gravity.CENTER_HORIZONTAL
        }
        navScroll.addView(navItems, ViewGroup.LayoutParams(-1, -2))
        rail.addView(navScroll, LinearLayout.LayoutParams(-1, 0, 1f))
'''
assert old in s
s = s.replace(old, new, 1)

s = s.replace('''                    "Голоса" -> "Профили голосов и экспорт настроек"
                    else -> "Инструменты и параметры FB2AudioPrep"''', '''                    "Голоса" -> "Профили голосов и экспорт настроек"
                    "Озвучивание" -> "Офлайн-синтез речи, модель и управление воспроизведением"
                    else -> "Инструменты и параметры FB2AudioPrep"''', 1)
s = s.replace('''                            label.contains("экспорт", true) -> "Сохранить настройки для внешнего синтезатора"
                            else -> "Открыть инструмент"''', '''                            label.contains("экспорт", true) -> "Сохранить настройки для внешнего синтезатора"
                            label.contains("скачать модель", true) -> "Загрузить модель для автономной озвучки"
                            label.contains("установить модель", true) || label.contains("импортировать модель", true) -> "Установить ранее сохранённый ZIP-файл модели"
                            label.contains("озвуч", true) -> "Управление воспроизведением книги"
                            else -> "Открыть инструмент"''', 1)
s = s.replace('''                setPadding(0, dp(activity, 9), 0, dp(activity, 9))
                isClickable = true''', '''                setPadding(0, dp(activity, 8), 0, dp(activity, 8))
                minimumHeight = dp(activity, 58)
                isClickable = true''', 1)
s = s.replace('''            rail.addView(item, LinearLayout.LayoutParams(-1, -2))''', '''            navItems.addView(item, LinearLayout.LayoutParams(-1, -2))''', 1)

old = '''        addNav("▤", "Книги", library, "Здесь можно открыть новую книгу.")
        addNav("♙", "Герои", people)
        addNav("✧", "ИИ-анализ", buttons.filter { it.text.toString().contains("диалог", true) || it.text.toString().contains("говорящ", true) })
        addNav("Aa", "Текст", preparation.filter { it.text.toString().contains("ударен", true) || it.text.toString().contains("словар", true) })
        addNav("♫", "Голоса", people.filter { it.text.toString().contains("персонаж", true) || it.text.toString().contains("голос", true) },
            "Настройка персонажей и голосов доступна. Самостоятельный движок озвучивания ещё разрабатывается.")
        val spacer = View(activity)
        rail.addView(spacer, LinearLayout.LayoutParams(1, 0, 1f))
        addNav("⚙", "Ещё", preparation.filter { it !in preparation.filter { b -> b.text.toString().contains("ударен", true) || b.text.toString().contains("словар", true) } })
'''
new = '''        addNav("▤", "Книги", library, "Здесь можно открыть новую книгу.")
        addNav("♙", "Герои", people.filter { it.text.toString().contains("персонаж", true) })
        addNav("✧", "ИИ-анализ", people.filter { it.text.toString().contains("диалог", true) || it.text.toString().contains("говорящ", true) })
        addNav("Aa", "Текст", preparation.filter { it.text.toString().contains("ударен", true) || it.text.toString().contains("словар", true) })
        addNav("♫", "Голоса", people.filter { it.text.toString().contains("голос", true) },
            "Здесь находятся профили персонажей и настройки голосов.")
        addNav("▶", "Озвучивание", audio,
            "Здесь находятся загрузка и установка модели TeraTTSv2, запуск и остановка озвучивания книги.")
        addNav("⚙", "Ещё", preparation.filter { it !in preparation.filter { b -> b.text.toString().contains("ударен", true) || b.text.toString().contains("словар", true) } })
'''
assert old in s
s = s.replace(old, new, 1)
layout.write_text(s, encoding="utf-8")

main = root / "MainActivity.kt"
m = main.read_text(encoding="utf-8")
m = m.replace('Установить модель озвучивания TeraTTSv2 (ZIP)', 'Импортировать модель TeraTTSv2 из ZIP-файла')
main.write_text(m, encoding="utf-8")

manifest = Path("app/src/main/AndroidManifest.xml")
manifest_text = manifest.read_text(encoding="utf-8")
if 'android:largeHeap="true"' not in manifest_text:
    manifest_text = manifest_text.replace('<application ', '<application android:largeHeap="true" ', 1)
manifest.write_text(manifest_text, encoding="utf-8")

gradle = Path("app/build.gradle.kts")
g = gradle.read_text(encoding="utf-8")
m = re.search(r'versionCode\s*=\s*(\d+)\s*;\s*versionName\s*=\s*"([^"]+)"', g)
if not m:
    raise SystemExit("v42: cannot locate app version")
if m.group(2) != "2.1.5":
    g = g[:m.start()] + f'versionCode = {int(m.group(1)) + 1}; versionName = "2.1.5"' + g[m.end():]
    gradle.write_text(g, encoding="utf-8")

print("v42: stream RUAccent dictionaries into SQLite; add dedicated audio navigation; improve rail safe area and hit targets; clarify ZIP import; enable large heap for ONNX.")
