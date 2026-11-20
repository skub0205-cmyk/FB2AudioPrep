from pathlib import Path

p = Path("app/src/main/java/ru/fbaudioprep/MainActivity.kt")
s = p.read_text(encoding="utf-8")
old = """                val saved = BookSessionStore.restore(applicationContext) ?: return@Thread
                runOnUiThread {
                    sourceName = saved.name
                    val restoredRecord = if (!saved.isFb2 || saved.originalBytes != null) {
                        runCatching {
                            BookLibraryStore.add(
                                applicationContext, saved.name, saved.text, saved.isFb2,
                                saved.originalBytes ?: saved.text.toByteArray(Charsets.UTF_8)
                            )
                        }.getOrNull()
                    } else null
                    currentLibraryBookId = restoredRecord?.id"""
new = """                val saved = BookSessionStore.restore(applicationContext) ?: return@Thread
                // Never parse or persist a restored FB2 on Android's main/UI thread.
                // A large FB2 can take seconds to parse and would block every button,
                // including the system document picker launch.
                val restoredRecord = if (!saved.isFb2 || saved.originalBytes != null) {
                    runCatching {
                        BookLibraryStore.add(
                            applicationContext, saved.name, saved.text, saved.isFb2,
                            saved.originalBytes ?: saved.text.toByteArray(Charsets.UTF_8)
                        )
                    }.getOrNull()
                } else null
                runOnUiThread {
                    sourceName = saved.name
                    currentLibraryBookId = restoredRecord?.id"""
if old not in s: raise SystemExit("v63: restoreLastOpenedBook UI-thread persistence block not found")
s = s.replace(old, new, 1)
p.write_text(s, encoding="utf-8")
print("v63: move restored FB2 parsing and library persistence off the main/UI thread.")
