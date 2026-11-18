from pathlib import Path
import re

p = Path("app/src/main/java/ru/fbaudioprep/MainActivity.kt")
s = p.read_text(encoding="utf-8")

# Put a direct entry point near "Open book", so it is not buried below the fold.
anchor = """        root.addView(Button(this).apply {
            text = "Открыть книгу"
            setOnClickListener { openBook() }
        })
"""
new = anchor + """
        reviewDialoguesButton = Button(this).apply {
            text = "Просмотреть диалоги и говорящих"
            isEnabled = false
            setOnClickListener { openDialogueBrowser() }
        }
        root.addView(reviewDialoguesButton)
"""
if "text = \"Просмотреть диалоги и говорящих\"" not in s:
    if anchor not in s:
        raise SystemExit("Cannot find Open book button insertion point")
    s = s.replace(anchor, new, 1)

# Remove the old duplicate review button, if present.
old = """
        reviewDialoguesButton = Button(this).apply {
            text = "Проверить и исправить говорящих"
            isEnabled = false
            setOnClickListener { showDialogueReview() }
        }
        root.addView(reviewDialoguesButton)
"""
if old in s:
    s = s.replace(old, "", 1)

# Opening the dialogue browser runs analysis automatically if needed.
if "private fun openDialogueBrowser()" not in s:
    marker = "    private fun showDialogueReview() {"
    method = """    private fun openDialogueBrowser() {
        if (originalText.isBlank()) {
            Toast.makeText(this, "Сначала откройте книгу", Toast.LENGTH_SHORT).show()
            return
        }
        if (dialogueFindings.isEmpty()) {
            analyzeDialogues()
        }
        if (dialogueFindings.isEmpty()) {
            AlertDialog.Builder(this)
                .setTitle("Диалоги не найдены")
                .setMessage("В текущей книге не удалось выделить реплики. Сохраните отчёт, чтобы посмотреть подробности диагностики.")
                .setPositiveButton("Закрыть", null)
                .show()
            return
        }
        showDialogueReview()
    }

"""
    if marker not in s:
        raise SystemExit("Cannot find dialogue review method")
    s = s.replace(marker, method + marker, 1)

# Viewing must not require pre-populating the character list.
guard = """        val profiles = loadCharacters()
        if (profiles.isEmpty()) {
            AlertDialog.Builder(this)
                .setMessage("Сначала добавьте персонажей и назначьте им голоса.")
                .setPositiveButton("Открыть персонажей") { _, _ -> showCharacters() }
                .setNegativeButton("Закрыть", null)
                .show()
            return
        }
"""
if guard in s:
    s = s.replace(guard, "        val profiles = loadCharacters()\n", 1)
elif "val profiles = loadCharacters()" not in s:
    raise SystemExit("Cannot find character profile check in dialogue review")

# The browser is available as soon as a book is loaded.
s = s.replace("            reviewDialoguesButton.isEnabled = false\n", "            reviewDialoguesButton.isEnabled = true\n", 1)

# Keep the direct entry point disabled only when there is no loaded book.
# Catch path already resets controls; insert if not present.
catch_anchor = """            accentButton.isEnabled = false
            saveTextButton.isEnabled = false
"""
if catch_anchor in s:
    s = s.replace(catch_anchor, """            accentButton.isEnabled = false
            reviewDialoguesButton.isEnabled = false
            saveTextButton.isEnabled = false
""", 1)

p.write_text(s, encoding="utf-8")

gpath = Path("app/build.gradle.kts")
g = gpath.read_text(encoding="utf-8")
g, n = re.subn(r'versionName\s*=\s*"2\.0\.3"', 'versionName = "2.0.4"', g, count=1)
if n != 1:
    raise SystemExit("Could not bump app version to 2.0.4")
gpath.write_text(g, encoding="utf-8")
print("Added an always-visible dialogue browser; removed the requirement to pre-create characters; version 2.0.4.")
