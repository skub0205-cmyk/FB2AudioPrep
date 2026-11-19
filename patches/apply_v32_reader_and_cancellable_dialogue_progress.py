from pathlib import Path
import re

base = Path("app/src/main/java/ru/fbaudioprep")
main = base / "MainActivity.kt"
s = main.read_text(encoding="utf-8")

# Keep imported books in the central reader surface instead of launching a second Activity.
start = s.find("    private fun openBookPreview() {")
end = s.find("\n    private fun openBook()", start)
if start < 0 or end < 0:
    raise SystemExit("v32: cannot locate openBookPreview()")
reader_method = '''    private fun openBookPreview() {
        if (originalText.isBlank()) {
            Toast.makeText(this, "Сначала откройте книгу", Toast.LENGTH_SHORT).show()
            return
        }
        preview.text = processedText.ifBlank { originalText }.take(8000)
        status.text = status.text.toString()
            .replace("\\nОткрываю читалку…", "")
            .replace("\\nОткрываю книгу в читалке…", "")
    }

'''
s = s[:start] + reader_method + s[end:]

marker = "    private var dialogueFindings: List<DialogueFinding> = emptyList()"
if "dialogueBlocksDone" not in s:
    if marker not in s:
        raise SystemExit("v32: cannot locate dialogue state")
    s = s.replace(marker, marker + "\n    private var dialogueBlocksDone = 0\n    private var dialogueBlocksTotal = 0", 1)

old_dialog = '''        val analysisProgress = android.app.ProgressDialog(this).apply {
            setTitle("Проверка книги на диалоги")
            setMessage("Подготовка текста…")
            setProgressStyle(android.app.ProgressDialog.STYLE_HORIZONTAL)
            max = 100
            progress = 0
            setCancelable(false)
            setCanceledOnTouchOutside(false)
            show()
        }'''
new_dialog = '''        dialogueBlocksDone = 0
        dialogueBlocksTotal = 0
        val analysisProgress = android.app.ProgressDialog(this).apply {
            setTitle("Проверка книги на диалоги")
            setMessage("Подготовка текста…\\nПроверено блоков: 0 из 0\\\\nОсталось: —")
            setProgressStyle(android.app.ProgressDialog.STYLE_HORIZONTAL)
            max = 100
            progress = 0
            setCancelable(true)
            setCanceledOnTouchOutside(false)
            setButton(AlertDialog.BUTTON_NEGATIVE, "Отменить") { _, _ -> cancel() }
            setOnCancelListener {
                if (dialogueAnalysisInProgress) {
                    dialogueAnalysisToken += 1
                    dialogueAnalysisInProgress = false
                    openReviewAfterAnalysis = false
                    dialogueButton.isEnabled = true
                    characterButton.isEnabled = true
                    reviewDialoguesButton.isEnabled = dialogueFindings.isNotEmpty()
                    status.text = "Анализ диалогов отменён.\\nПроверено блоков: " +
                        dialogueBlocksDone + " из " + dialogueBlocksTotal +
                        ". Можно запустить проверку повторно."
                }
            }
            show()
        }'''
if old_dialog not in s:
    raise SystemExit("v32: cannot find dialogue progress dialog to make cancellable")
s = s.replace(old_dialog, new_dialog, 1)

progress_match = re.search(r'(?m)^(\\s*)analysisProgress\\.setMessage\\(stage \\+ .*? \\+ percent \\+ "%"\\)\\s*$', s)
if not progress_match:
    raise SystemExit("v32: cannot locate progress message update")
indent = progress_match.group(1)
counter_update = (
    indent + 'Regex("Проверено блоков: (\\\\d+) из (\\\\d+)").find(stage)?.let { match ->\\n' +
    indent + '    dialogueBlocksDone = match.groupValues[1].toIntOrNull() ?: dialogueBlocksDone\\n' +
    indent + '    dialogueBlocksTotal = match.groupValues[2].toIntOrNull() ?: dialogueBlocksTotal\\n' +
    indent + '}\\n'
)
s = s[:progress_match.start()] + counter_update + s[progress_match.start():]
main.write_text(s, encoding="utf-8")

role_model = base / "teratts/RoleModel.kt"
r = role_model.read_text(encoding="utf-8")
old_count = '''            val had = done.size
            val first = ws.indexOfFirst'''
new_count = '''            val had = done.size
            onWindow(done.size, ws.size)
            val first = ws.indexOfFirst'''
if old_count not in r:
    raise SystemExit("v32: cannot locate RoleModel block-plan counter insertion")
r = r.replace(old_count, new_count, 1)
role_model.write_text(r, encoding="utf-8")

engine = base / "teratts/TeraRoleEngine.kt"
e = engine.read_text(encoding="utf-8")
old_stage = 'onProgress(percent, "Проверено фрагментов ИИ: $done из $total")'
new_stage = 'onProgress(percent, "Проверено блоков: $done из $total\\nОсталось: ${total - done}")'
if old_stage not in e:
    raise SystemExit("v32: cannot locate TeraRoleEngine progress stage")
e = e.replace(old_stage, new_stage, 1)
engine.write_text(e, encoding="utf-8")

print("v32: keep imported books on the main reader; add cancellable dialogue analysis and checked/remaining block counters.")
