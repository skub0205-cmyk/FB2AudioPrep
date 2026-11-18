from pathlib import Path

main = Path("app/src/main/java/ru/fbaudioprep/MainActivity.kt")
m = main.read_text(encoding="utf-8")

property_marker = "    private var dialogueFindings: List<DialogueFinding> = emptyList()"
if "dialogueAnalysisInProgress" not in m:
    if property_marker not in m:
        raise SystemExit("Cannot locate dialogue state properties")
    m = m.replace(
        property_marker,
        property_marker + "\n    private var dialogueAnalysisInProgress = false\n    private var dialogueAnalysisToken = 0\n    private var openReviewAfterAnalysis = false",
        1
    )

load_marker = "                    sourceName = book.sourceName\n                    originalText = book.text"
load_replacement = "                    dialogueAnalysisToken += 1\n                    dialogueAnalysisInProgress = false\n                    openReviewAfterAnalysis = false\n" + load_marker
if load_replacement not in m:
    if load_marker not in m:
        raise SystemExit("Cannot locate successful book import assignment")
    m = m.replace(load_marker, load_replacement, 1)

open_start = m.find("    private fun openDialogueBrowser() {")
open_end = m.find("    private fun showDialogueReview()", open_start)
if open_start < 0 or open_end < 0:
    raise SystemExit("Cannot locate asynchronous dialogue browser entry point")
open_method = """    private fun openDialogueBrowser() {
        if (originalText.isBlank()) {
            Toast.makeText(this, "Сначала откройте книгу", Toast.LENGTH_SHORT).show()
            return
        }
        if (dialogueAnalysisInProgress) {
            openReviewAfterAnalysis = true
            return
        }
        if (dialogueFindings.isEmpty()) {
            openReviewAfterAnalysis = true
            analyzeDialogues()
            return
        }
        showDialogueReview()
    }

"""
m = m[:open_start] + open_method + m[open_end:]

start = m.find("    private fun analyzeDialogues() {")
end = m.find("    private fun normalizeCharacterName", start)
if start < 0 or end < 0:
    raise SystemExit("Cannot locate analyzeDialogues() for background conversion")

method = r"""    private fun analyzeDialogues() {
        val bookText = originalText
        val bookName = sourceName
        if (bookText.isBlank() || dialogueAnalysisInProgress) return

        dialogueAnalysisInProgress = true
        val token = ++dialogueAnalysisToken
        dialogueButton.isEnabled = false
        characterButton.isEnabled = false
        reviewDialoguesButton.isEnabled = false
        status.text = "Автоматически анализирую книгу и персонажей…"

        Thread {
            try {
                val manualProfiles = loadCharactersForBook(bookText)
                val discoveredProfiles = CharacterDiscovery.discover(bookText)
                val profiles = mergeCharacterProfiles(discoveredProfiles, manualProfiles)
                if (profiles != manualProfiles) saveCharactersForBook(bookText, profiles)

                val analyzed = DialogueAnalyzer(profiles).analyzeBook(bookText)
                val neuralFindings = applyNeuralSpeakerRanker(analyzed, profiles)
                val findings = DialogueCorrectionStore.apply(this, bookText, neuralFindings)
                val known = findings.count { it.speaker != null }
                val uncertain = findings.size - known
                val neural = findings.count { it.reason.startsWith("Нейросеть:") }
                val reportText = buildString {
                    appendLine("FB2 AudioPrep 2.0.9 — автоматический анализ говорящих")
                    appendLine("Файл: " + bookName)
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

                runOnUiThread {
                    if (token != dialogueAnalysisToken) return@runOnUiThread
                    dialogueFindings = findings
                    reviewDialoguesButton.isEnabled = findings.isNotEmpty()
                    dialogueReport = reportText
                    report = if (report.isBlank()) dialogueReport else report + "\n\n" + dialogueReport
                    status.text = "Автоматический анализ завершён.\nПерсонажей: " +
                        discoveredProfiles.size + "\nФрагментов: " + findings.size +
                        "\nГоворящий определён: " + known + "\nНейросетью: " + neural +
                        "\nТребует дополнительного анализа: " + uncertain
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
                                .setMessage("Не удалось выделить реплики в этой книге.")
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
                    status.text = "Ошибка автоматического анализа: " + (error.message ?: "неизвестная ошибка")
                }
            }
        }.start()
    }

"""
m = m[:start] + method + m[end:]
main.write_text(m, encoding="utf-8")
print("Moved automatic dialogue discovery and optional ONNX ranking to a background thread.")
