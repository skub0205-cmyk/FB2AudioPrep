from pathlib import Path
import re

main = Path("app/src/main/java/ru/fbaudioprep/MainActivity.kt")
m = main.read_text(encoding="utf-8")

# The model source is ported from TeraTTS 1.59 and is kept in its own package.
imports = [
    "import ru.fbaudioprep.teratts.RoleModel",
    "import ru.fbaudioprep.teratts.TeraRoleEngine"
]
for line in imports:
    if line not in m:
        package_end = m.find("\n\n")
        if package_end < 0:
            raise SystemExit("Cannot locate MainActivity package/import section")
        m = m[:package_end] + "\n" + line + m[package_end:]

start = m.find("    private fun analyzeDialogues() {")
end = m.find("    private fun normalizeCharacterName", start)
if start < 0 or end < 0:
    raise SystemExit("Cannot locate analyzeDialogues() replacement range")

method = r"""    private fun analyzeDialogues(allowWithoutModel: Boolean = false) {
        if (originalText.isBlank() || dialogueAnalysisInProgress) return

        if (!RoleModel.upToDate(this) && !allowWithoutModel) {
            val installed = RoleModel.installed(this)
            AlertDialog.Builder(this)
                .setTitle(if (installed) "Обновить ИИ-модель TeraTTS" else "Установить ИИ-модель TeraTTS")
                .setMessage(
                    "Для автоматического определения говорящих используется RuModernBERT m10b из TeraTTS 1.59. " +
                    "Размер загрузки — около 216 МБ. Модель сохраняется на устройстве и после установки работает без интернета."
                )
                .setPositiveButton("Загрузить модель") { _, _ -> downloadTeraRoleModel() }
                .setNegativeButton("Пока без ИИ") { _, _ -> analyzeDialogues(allowWithoutModel = true) }
                .setNeutralButton("Отмена") { _, _ -> openReviewAfterAnalysis = false }
                .show()
            return
        }

        if (RoleModel.upToDate(this)) RoleModel.setWanted(this, true)
        val bookText = originalText
        val bookName = sourceName
        dialogueAnalysisInProgress = true
        val token = ++dialogueAnalysisToken
        dialogueButton.isEnabled = false
        characterButton.isEnabled = false
        reviewDialoguesButton.isEnabled = false
        status.text = "TeraTTS: анализирую всю книгу и определяю говорящих…"

        Thread {
            try {
                val analysis = TeraRoleEngine.analyze(this@MainActivity, bookText) {
                    token != dialogueAnalysisToken
                }
                if (token != dialogueAnalysisToken) return@Thread

                val manualProfiles = loadCharactersForBook(bookText)
                val discoveredProfiles = analysis.characters.map { character ->
                    val voice = when (character.role) {
                        ru.fbaudioprep.teratts.DialogueAnalyzer2.Role.MALE -> "мужской"
                        ru.fbaudioprep.teratts.DialogueAnalyzer2.Role.FEMALE -> "женский"
                        else -> "не задан"
                    }
                    val aliases = analysis.aliases.filterValues { it == character.name }.keys.toList()
                    CharacterProfile(character.name, aliases, voice)
                }
                val profiles = mergeCharacterProfiles(discoveredProfiles, manualProfiles)
                if (profiles != manualProfiles) saveCharactersForBook(bookText, profiles)

                val findings = DialogueCorrectionStore.apply(this@MainActivity, bookText, analysis.findings)
                val known = findings.count { it.speaker != null }
                val uncertain = findings.size - known
                val neural = findings.count { it.reason.startsWith("TeraTTS m10b:") }
                val reportText = buildString {
                    appendLine("FB2 AudioPrep 2.1.0 — автоматический анализ TeraTTS 1.59")
                    appendLine("Книга: " + bookName)
                    appendLine("Модель RuModernBERT m10b: " + if (analysis.modelAvailable) "установлена и включена" else "не используется")
                    appendLine("Персонажей по всей книге: " + discoveredProfiles.size)
                    appendLine("Фрагментов диалога: " + findings.size)
                    appendLine("Говорящий определён: " + known)
                    appendLine("Назначений с участием нейросети: " + neural)
                    appendLine("Требуют проверки: " + uncertain)
                    appendLine()
                    findings.forEachIndexed { index, finding ->
                        appendLine("Фрагмент " + (index + 1))
                        appendLine("Говорящий: " + (finding.speaker ?: "не определён"))
                        appendLine("Обращение: " + (finding.addressedTo ?: "не найдено"))
                        appendLine("Голос: " + (finding.voice ?: "не определён"))
                        appendLine("Уверенность: " + (finding.confidence * 100).toInt() + "%")
                        appendLine("Основание: " + finding.reason)
                        appendLine(finding.fragment)
                        appendLine()
                    }
                    appendLine("Нейросеть дополняет правила TeraTTS и не переопределяет явные авторские указания при недостаточной уверенности.")
                }

                runOnUiThread {
                    if (token != dialogueAnalysisToken) return@runOnUiThread
                    dialogueFindings = findings
                    reviewDialoguesButton.isEnabled = findings.isNotEmpty()
                    dialogueReport = reportText
                    report = if (report.isBlank()) dialogueReport else report + "\n\n" + dialogueReport
                    status.text = "Анализ TeraTTS завершён.\nПерсонажей: " +
                        discoveredProfiles.size + "\nФрагментов: " + findings.size +
                        "\nГоворящий определён: " + known + "\nНейросеть: " + neural +
                        "\nТребуют проверки: " + uncertain
                    preview.text = dialogueReport.take(8000)
                    dialogueAnalysisInProgress = false
                    dialogueButton.isEnabled = true
                    characterButton.isEnabled = true
                    if (openReviewAfterAnalysis) {
                        openReviewAfterAnalysis = false
                        if (findings.isNotEmpty()) {
                            showDialogueReview()
                        } else {
                            AlertDialog.Builder(this@MainActivity)
                                .setTitle("Диалоги не найдены")
                                .setMessage("TeraTTS не выделил реплики в этой книге.")
                                .setPositiveButton("Закрыть", null)
                                .show()
                        }
                    }
                }
            } catch (error: Throwable) {
                runOnUiThread {
                    if (token != dialogueAnalysisToken) return@runOnUiThread
                    dialogueAnalysisInProgress = false
                    openReviewAfterAnalysis = false
                    dialogueButton.isEnabled = true
                    characterButton.isEnabled = true
                    status.text = "Ошибка анализа TeraTTS: " + (error.message ?: "неизвестная ошибка")
                    AlertDialog.Builder(this@MainActivity)
                        .setTitle("Не удалось проанализировать книгу")
                        .setMessage(error.message ?: "Неизвестная ошибка")
                        .setPositiveButton("Закрыть", null)
                        .show()
                }
            }
        }.start()
    }

    private fun downloadTeraRoleModel() {
        val progressDialog = android.app.ProgressDialog(this).apply {
            setTitle("Загрузка ИИ-модели")
            setMessage("Загружается RuModernBERT m10b (около 216 МБ). Загрузка возобновляется после обрыва соединения.")
            setProgressStyle(android.app.ProgressDialog.STYLE_SPINNER)
            setCancelable(false)
            show()
        }
        status.text = "Загружаю модель TeraTTS m10b…"
        Thread {
            try {
                kotlinx.coroutines.runBlocking {
                    RoleModel.download(applicationContext)
                }
                RoleModel.setWanted(applicationContext, true)
                runOnUiThread {
                    progressDialog.dismiss()
                    status.text = "ИИ-модель установлена. Следующий анализ будет работать офлайн."
                    analyzeDialogues(allowWithoutModel = true)
                }
            } catch (error: Throwable) {
                runOnUiThread {
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

"""
m = m[:start] + method + m[end:]
main.write_text(m, encoding="utf-8")

# The original Tera tokenizer is byte-level BPE and needs no DJL tokenizer dependency.
ranker = Path("app/src/main/java/ru/fbaudioprep/NeuralSpeakerRanker.kt")
if ranker.exists():
    ranker.unlink()

gradle = Path("app/build.gradle.kts")
g = gradle.read_text(encoding="utf-8")
g = g.replace('    implementation("ai.djl.huggingface:tokenizers:0.30.0")\n', "")
if "onnxruntime-android" not in g:
    g += '\ndependencies {\n    implementation("com.microsoft.onnxruntime:onnxruntime-android:1.20.0")\n}\n'
if "kotlinx-coroutines-android" not in g:
    g += '\ndependencies {\n    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.9.0")\n}\n'
# Increment versionCode and move the visible version to 2.1.0.
pattern = r'versionCode\s*=\s*(\d+)\s*;\s*versionName\s*=\s*"[^"]+"'
mver = re.search(pattern, g)
if not mver:
    raise SystemExit("Could not locate versionCode/versionName for 2.1.0")
g = g[:mver.start()] + f'versionCode = {int(mver.group(1)) + 1}; versionName = "2.1.0"' + g[mver.end():]
gradle.write_text(g, encoding="utf-8")

manifest = Path("app/src/main/AndroidManifest.xml")
if manifest.exists():
    xml = manifest.read_text(encoding="utf-8")
    if "android.permission.INTERNET" not in xml:
        xml = xml.replace("<manifest", '<manifest', 1)
        pos = xml.find(">")
        xml = xml[:pos+1] + '\n    <uses-permission android:name="android.permission.INTERNET" />' + xml[pos+1:]
        manifest.write_text(xml, encoding="utf-8")

print("Integrated TeraTTS 1.59 dialogue rules and RuModernBERT m10b; added one-time model download and offline analysis.")
