from pathlib import Path

root = Path("app/src/main/java/ru/fbaudioprep")
accentizer = root / "TeraTtsV2DictionaryAccentizer.kt"
s = accentizer.read_text(encoding="utf-8")

# Android SQLiteDatabase.execSQL() cannot execute statements that return rows.
# PRAGMA journal_mode returns a result cursor, which caused the runtime error:
# "Queries can be performed using SQLiteDatabase.query or rawQuery methods only."
old = '                    db.execSQL("PRAGMA journal_mode=DELETE")'
new = '                    db.rawQuery("PRAGMA journal_mode=DELETE", null).use { cursor -> cursor.moveToFirst() }'
assert old in s, "Expected v42 journal_mode statement was not found"
s = s.replace(old, new, 1)

# Add an explicit integrity check before the read-only database is exposed.
old = '''                db.close()
                metaFile.writeText(signature)
'''
new = '''                db.close()
                SQLiteDatabase.openDatabase(dbFile.absolutePath, null, SQLiteDatabase.OPEN_READONLY).use { checkDb ->
                    checkDb.rawQuery("PRAGMA quick_check", null).use { cursor ->
                        check(cursor.moveToFirst() && cursor.getString(0) == "ok") {
                            "Проверка базы словаря SQLite не пройдена"
                        }
                    }
                    checkDb.rawQuery("SELECT COUNT(*) FROM accents", null).use { cursor ->
                        check(cursor.moveToFirst() && cursor.getLong(0) > 0L) {
                            "Словарь ударений пуст"
                        }
                    }
                }
                metaFile.writeText(signature)
'''
assert old in s, "Expected database close/metadata block was not found"
s = s.replace(old, new, 1)
accentizer.write_text(s, encoding="utf-8")

# Bump app version for a distinct install/update build.
gradle = Path("app/build.gradle.kts")
g = gradle.read_text(encoding="utf-8")
import re
m = re.search(r'versionCode\\s*=\\s*(\\d+)\\s*;\\s*versionName\\s*=\\s*"([^"]+)"', g)
if m and m.group(2) != "2.1.6":
    g = g[:m.start()] + f'versionCode = {int(m.group(1)) + 1}; versionName = "2.1.6"' + g[m.end():]
    gradle.write_text(g, encoding="utf-8")

print("v43: use rawQuery for row-returning PRAGMA, validate SQLite integrity and dictionary contents.")
