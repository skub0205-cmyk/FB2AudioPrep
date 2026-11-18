from pathlib import Path
import re

root = Path("app/src/main/java/ru/fbaudioprep")
main = root / "MainActivity.kt"
m = main.read_text(encoding="utf-8")

start = m.find("    private fun downloadTeraRoleModel() {")
end = m.find("\n    private fun ", start + 10)
if start < 0 or end < 0:
    raise SystemExit("Cannot locate downloadTeraRoleModel()")
download = r'''    private fun downloadTeraRoleModel() {
        val progressDialog = android.app.ProgressDialog(this).apply {
            setTitle("Загрузка ИИ-модели TeraTTS")
            setMessage("Подготовка загрузки…")
            setProgressStyle(android.app.ProgressDialog.STYLE_HORIZONTAL)
            max = 100
            progress = 0
            setCancelable(false)
            setCanceledOnTouchOutside(false)
            show()
        }
        val handler = android.os.Handler(mainLooper)
        val poll = object : Runnable {
            override fun run() {
                val fraction = RoleModel.progress
                if (fraction != null && progressDialog.isShowing) {
                    val percent = (fraction * 100f).toInt().coerceIn(0, 100)
                    progressDialog.progress = percent
                    progressDialog.setMessage("Загрузка модели: " + percent + "%")
                    handler.postDelayed(this, 350)
                }
            }
        }
        status.text = "Загружаю модель TeraTTS m10b…"
        handler.post(poll)
        Thread {
            try {
                kotlinx.coroutines.runBlocking {
                    RoleModel.download(applicationContext)
                }
                RoleModel.setWanted(applicationContext, true)
                runOnUiThread {
                    handler.removeCallbacks(poll)
                    progressDialog.progress = 100
                    progressDialog.dismiss()
                    status.text = "ИИ-модель установлена. Следующий анализ будет работать офлайн."
                    analyzeDialogues(allowWithoutModel = true)
                }
            } catch (error: Throwable) {
                runOnUiThread {
                    handler.removeCallbacks(poll)
                    progressDialog.dismiss()
                    AlertDialog.Builder(this@MainActivity)
                        .setTitle("Не удалось загрузить ИИ-модель")
                        .setMessage((error.message ?: "Проверьте подключение и попробуйте ещё раз.") +
                            "\n\nМожно продолжить анализ без нейросети.")
                        .setPositiveButton("Анализ без ИИ") { _, _ ->
                            analyzeDialogues(allowWithoutModel = true)
                        }
                        .setNegativeButton("Закрыть", null)
                        .show()
                }
            }
        }.start()
    }

'''
m = m[:start] + download + m[end:]

needle = '''        status.text = "TeraTTS: анализирую всю книгу и определяю говорящих…"

        Thread {'''
replacement = '''        status.text = "TeraTTS: анализирую всю книгу и определяю говорящих…"
        val analysisProgress = android.app.ProgressDialog(this).apply {
            setTitle("Проверка книги на диалоги")
            setMessage("Подготовка текста…")
            setProgressStyle(android.app.ProgressDialog.STYLE_HORIZONTAL)
            max = 100
            progress = 0
            setCancelable(false)
            setCanceledOnTouchOutside(false)
            show()
        }

        Thread {'''
if needle not in m:
    raise SystemExit("Cannot locate analysis start UI")
m = m.replace(needle, replacement, 1)

old_call = '''                val analysis = TeraRoleEngine.analyze(this@MainActivity, bookText) {
                    token != dialogueAnalysisToken
                }'''
new_call = '''                val analysis = TeraRoleEngine.analyze(
                    this@MainActivity,
                    bookText,
                    stop = { token != dialogueAnalysisToken },
                    onProgress = { percent, stage ->
                        runOnUiThread {
                            if (token == dialogueAnalysisToken && analysisProgress.isShowing) {
                                analysisProgress.progress = percent.coerceIn(0, 100)
                                analysisProgress.setMessage(stage + "\\n" + percent + "%")
                            }
                        }
                    }
                )'''
if old_call not in m:
    raise SystemExit("Cannot locate TeraRoleEngine call")
m = m.replace(old_call, new_call, 1)

success_marker = '''                    dialogueFindings = findings
                    reviewDialoguesButton.isEnabled = findings.isNotEmpty()'''
if success_marker not in m:
    raise SystemExit("Cannot locate analysis success callback")
m = m.replace(success_marker, '''                    if (analysisProgress.isShowing) analysisProgress.dismiss()
                    dialogueFindings = findings
                    reviewDialoguesButton.isEnabled = findings.isNotEmpty()''', 1)

error_marker = '''                    dialogueAnalysisInProgress = false
                    openReviewAfterAnalysis = false
                    dialogueButton.isEnabled = true'''
if error_marker not in m:
    raise SystemExit("Cannot locate analysis error callback")
m = m.replace(error_marker, '''                    if (analysisProgress.isShowing) analysisProgress.dismiss()
                    dialogueAnalysisInProgress = false
                    openReviewAfterAnalysis = false
                    dialogueButton.isEnabled = true''', 1)
main.write_text(m, encoding="utf-8")

engine = root / "teratts/TeraRoleEngine.kt"
e = engine.read_text(encoding="utf-8")
e = e.replace(
    "fun analyze(context: Context, text: String, stop: () -> Boolean = { false }): Analysis {",
    "fun analyze(context: Context, text: String, stop: () -> Boolean = { false }, onProgress: (Int, String) -> Unit = { _, _ -> }): Analysis {"
)
if "onProgress: (Int, String)" not in e:
    raise SystemExit("Could not extend TeraRoleEngine progress callback")
e = e.replace(
    "        val (rulesResult, probes) = DialogueAnalyzer2.analyzeLines(text)",
    "        onProgress(2, \"Разбираю структуру книги и авторские ремарки…\")\n        val (rulesResult, probes) = DialogueAnalyzer2.analyzeLines(text)\n        onProgress(10, \"Структура книги разобрана. Подготавливаю фрагменты диалогов…\")",
    1
)
old_guesses = '''                compute = true, threads = 2, stop = stop
            ).orEmpty()'''
new_guesses = '''                compute = true, threads = 2, stop = stop,
                onStart = { onProgress(10, "Загружаю ИИ-модель и начинаю проверку…") },
                onWindow = { done, total ->
                    val percent = 10 + (80f * done / total.coerceAtLeast(1)).toInt()
                    onProgress(percent, "Проверено фрагментов ИИ: $done из $total")
                }
            ).orEmpty()'''
if old_guesses not in e:
    raise SystemExit("Cannot locate RoleModel.guesses call")
e = e.replace(old_guesses, new_guesses, 1)
e = e.replace(
    "        return Analysis(findings, improved.characters, improved.aliases, guesses.size, available)",
    "        onProgress(100, \"Проверка завершена. Формирую список диалогов…\")\n        return Analysis(findings, improved.characters, improved.aliases, guesses.size, available)",
    1
)
engine.write_text(e, encoding="utf-8")

gradle = Path("app/build.gradle.kts")
g = gradle.read_text(encoding="utf-8")
g, count = re.subn(r'versionCode\s*=\s*(\d+);\s*versionName\s*=\s*"2\.1\.0"',
                   lambda x: f'versionCode = {int(x.group(1)) + 1}; versionName = "2.1.1"', g, count=1)
if count != 1:
    raise SystemExit("Could not bump version to 2.1.1")
gradle.write_text(g, encoding="utf-8")
print("Added real model-download percentage and per-window book-analysis progress; bumped to 2.1.1.")
