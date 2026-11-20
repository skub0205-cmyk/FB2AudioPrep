from pathlib import Path

base = Path("app/src/main/java/ru/fbaudioprep")

p = base / "TeraTtsV2SpeechSegmenter.kt"
s = p.read_text(encoding="utf-8")
old = """        characterVoiceAssignments: Map<String, String> = emptyMap()
    ): List<TeraTtsSpeechPiece> {"""
new = """        characterVoiceAssignments: Map<String, String> = emptyMap(),
        useCharacterVoices: Boolean = true,
        maleVoiceId: String? = null,
        femaleVoiceId: String? = null
    ): List<TeraTtsSpeechPiece> {"""
if old not in s: raise SystemExit("v51: segmenter signature not found")
s = s.replace(old, new, 1)
old = """            val voice = assigned?.takeIf { it in availableVoices }
                ?: gender?.let { chooseVoice(it, narratorVoice, availableVoices) }
                ?: narratorVoice"""
new = """            val voice = if (!useCharacterVoices) narratorVoice else
                assigned?.takeIf { it in availableVoices }
                    ?: gender?.let {
                        val preferred = if (it == "женский") femaleVoiceId else maleVoiceId
                        chooseVoice(it, narratorVoice, availableVoices, preferred)
                    }
                    ?: narratorVoice"""
if old not in s: raise SystemExit("v51: segmenter voice routing block not found")
s = s.replace(old, new, 1)
old = """    private fun chooseVoice(gender: String, narrator: String, available: List<String>): String {
        fun matches(id: String): Boolean {"""
new = """    private fun chooseVoice(
        gender: String,
        narrator: String,
        available: List<String>,
        preferred: String? = null
    ): String {
        if (preferred != null && preferred in available && preferred != narrator) return preferred
        fun matches(id: String): Boolean {"""
if old not in s: raise SystemExit("v51: chooseVoice signature not found")
s = s.replace(old, new, 1)
p.write_text(s, encoding="utf-8")

p = base / "CharacterVoiceAssignmentStore.kt"
s = p.read_text(encoding="utf-8")
old = """        narratorVoice: String,
        availableVoices: List<String>
    ): Map<String, String> {"""
new = """        narratorVoice: String,
        availableVoices: List<String>,
        maleVoiceId: String? = null,
        femaleVoiceId: String? = null
    ): Map<String, String> {"""
if old not in s: raise SystemExit("v51: assignment store signature not found")
s = s.replace(old, new, 1)
old = """                val candidates = availableVoices.filter { voiceGender(it) == gender }
                candidates.firstOrNull { it != narratorVoice && it !in used }
                    ?: candidates.firstOrNull { it != narratorVoice }
                    ?: candidates.firstOrNull()"""
new = """                val candidates = availableVoices.filter { voiceGender(it) == gender }
                val preferred = if (gender == "женский") femaleVoiceId else maleVoiceId
                candidates.firstOrNull { it == preferred && it != narratorVoice }
                    ?: candidates.firstOrNull { it != narratorVoice && it !in used }
                    ?: candidates.firstOrNull { it != narratorVoice }
                    ?: candidates.firstOrNull()"""
if old not in s: raise SystemExit("v51: assignment candidate block not found")
s = s.replace(old, new, 1)
p.write_text(s, encoding="utf-8")

p = base / "TeraTtsV2OnnxEngine.kt"
s = p.read_text(encoding="utf-8")
old = """        seed: Long = 1234L,
        onStarted: (() -> Unit)? = null
    ) {"""
new = """        seed: Long = 1234L,
        onStarted: (() -> Unit)? = null,
        gain: Float = 1f
    ) {"""
if old not in s: raise SystemExit("v51: engine synthesis signature not found")
s = s.replace(old, new, 1)
s = s.replace("            val output = createTrack()", "            val output = createTrack(gain)", 1)
old = """    private fun createTrack(): AudioTrack {
        val minimum = AudioTrack.getMinBufferSize("""
new = """    private fun createTrack(gain: Float): AudioTrack {
        val minimum = AudioTrack.getMinBufferSize("""
if old not in s: raise SystemExit("v51: createTrack signature not found")
s = s.replace(old, new, 1)
old = """            .setTransferMode(AudioTrack.MODE_STREAM)
            .build()
    }"""
new = """            .setTransferMode(AudioTrack.MODE_STREAM)
            .build()
            .apply { setVolume(gain.coerceIn(0f, 1f)) }
    }"""
if old not in s: raise SystemExit("v51: AudioTrack builder tail not found")
s = s.replace(old, new, 1)
p.write_text(s, encoding="utf-8")

p = base / "MainActivity.kt"
s = p.read_text(encoding="utf-8")
old = """        root.addView(stopBookButton)

        accentButton = Button(this).apply {"""
new = """        root.addView(stopBookButton)

        root.addView(Button(this).apply {
            text = "⚙ Настройки озвучивания"
            setOnClickListener { showAudiobookSettings() }
        })

        accentButton = Button(this).apply {"""
if old not in s: raise SystemExit("v51: playback controls insertion point not found")
s = s.replace(old, new, 1)

marker = "    private fun chooseAndPlayBook() {"
if marker not in s: raise SystemExit("v51: chooseAndPlayBook marker not found")
settings_method = r'''    private fun showAudiobookSettings() {
        val voices = ttsEngine?.status()?.voices.orEmpty()
        if (voices.isEmpty()) {
            Toast.makeText(this, "Сначала установите модель TeraTTSv2", Toast.LENGTH_LONG).show()
            return
        }
        val prefs = getSharedPreferences("fb2audioprep_tts_settings", MODE_PRIVATE)
        val panel = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(24, 8, 24, 0)
        }
        fun addLabel(value: String) {
            panel.addView(TextView(this).apply {
                text = value
                textSize = 13f
                setPadding(0, 12, 0, 4)
            })
        }
        fun voiceSpinner(label: String, key: String, fallback: String): Spinner {
            addLabel(label)
            val spinner = Spinner(this)
            spinner.adapter = ArrayAdapter(
                this, android.R.layout.simple_spinner_dropdown_item, voices
            )
            val selected = prefs.getString(key, fallback) ?: fallback
            spinner.setSelection(voices.indexOf(selected).coerceAtLeast(0))
            panel.addView(spinner)
            return spinner
        }
        val narratorDefault = selectedTtsVoice.takeIf { it in voices } ?: voices.first()
        val femaleDefault = voices.firstOrNull { Regex("""(^|[_-])f\d""").containsMatchIn(it) } ?: narratorDefault
        val maleDefault = voices.firstOrNull { Regex("""(^|[_-])m\d""").containsMatchIn(it) } ?: narratorDefault
        val narrator = voiceSpinner("Голос рассказчика", "narrator_voice", narratorDefault)
        val female = voiceSpinner("Общий голос женских реплик", "female_voice", femaleDefault)
        val male = voiceSpinner("Общий голос мужских реплик", "male_voice", maleDefault)

        val roles = Switch(this).apply {
            text = "Использовать разные голоса персонажей"
            isChecked = prefs.getBoolean("roles_enabled", true)
            setPadding(0, 14, 0, 4)
        }
        panel.addView(roles)

        fun addSeek(label: String, max: Int, initial: Int, valueText: (Int) -> String): SeekBar {
            addLabel(label)
            val value = TextView(this).apply { text = valueText(initial); textSize = 12f }
            panel.addView(value)
            val seek = SeekBar(this).apply {
                this.max = max
                progress = initial.coerceIn(0, max)
                setOnSeekBarChangeListener(object : SeekBar.OnSeekBarChangeListener {
                    override fun onProgressChanged(bar: SeekBar?, progress: Int, fromUser: Boolean) {
                        value.text = valueText(progress)
                    }
                    override fun onStartTrackingTouch(bar: SeekBar?) {}
                    override fun onStopTrackingTouch(bar: SeekBar?) {}
                })
            }
            panel.addView(seek)
            return seek
        }
        val durationInitial = ((prefs.getFloat("duration_scale", 1f) - 0.75f) * 100f).toInt().coerceIn(0, 60)
        val duration = addSeek("Длительность фразы (меньше — быстрее)", 60, durationInitial) {
            "×" + String.format(java.util.Locale.US, "%.2f", 0.75f + it / 100f)
        }
        val gainInitial = (prefs.getFloat("gain", 1f) * 100f).toInt().coerceIn(20, 100)
        val gain = addSeek("Громкость синтезированной речи", 100, gainInitial) { "$it%" }
        val pauseInitial = prefs.getInt("pause_ms", 100).coerceIn(0, 800)
        val pause = addSeek("Пауза между фрагментами", 800, pauseInitial) { "$it мс" }

        AlertDialog.Builder(this)
            .setTitle("Настройки озвучивания")
            .setView(ScrollView(this).apply { addView(panel) })
            .setNegativeButton("Отмена", null)
            .setPositiveButton("Сохранить") { _, _ ->
                selectedTtsVoice = narrator.selectedItem?.toString()?.takeIf { it in voices } ?: narratorDefault
                prefs.edit()
                    .putString("narrator_voice", selectedTtsVoice)
                    .putString("female_voice", female.selectedItem?.toString() ?: femaleDefault)
                    .putString("male_voice", male.selectedItem?.toString() ?: maleDefault)
                    .putBoolean("roles_enabled", roles.isChecked)
                    .putFloat("duration_scale", 0.75f + duration.progress / 100f)
                    .putFloat("gain", gain.progress.coerceIn(20, 100) / 100f)
                    .putInt("pause_ms", pause.progress)
                    .apply()
                ttsResumeStorageKey = ""
                Toast.makeText(this, "Настройки озвучивания сохранены", Toast.LENGTH_SHORT).show()
            }
            .show()
    }

'''
s = s.replace(marker, settings_method + marker, 1)

old = """        val voices = engine.status().voices
        val labels = voices.map { id -> when (id) {"""
new = """        val voices = engine.status().voices
        selectedTtsVoice = getSharedPreferences("fb2audioprep_tts_settings", MODE_PRIVATE)
            .getString("narrator_voice", selectedTtsVoice)?.takeIf { it in voices } ?: voices.first()
        val labels = voices.map { id -> when (id) {"""
if old not in s: raise SystemExit("v51: narrator selection block not found")
s = s.replace(old, new, 1)

old = """        val assignments = CharacterVoiceAssignmentStore.assign(
            this, originalText, profiles, selectedTtsVoice, voices
        )
        return TeraTtsV2SpeechSegmenter.build("""
new = """        val settings = getSharedPreferences("fb2audioprep_tts_settings", MODE_PRIVATE)
        val rolesEnabled = settings.getBoolean("roles_enabled", true)
        val femaleVoice = settings.getString("female_voice", null)
        val maleVoice = settings.getString("male_voice", null)
        val assignments = if (rolesEnabled) CharacterVoiceAssignmentStore.assign(
            this, originalText, profiles, selectedTtsVoice, voices, maleVoice, femaleVoice
        ) else emptyMap()
        return TeraTtsV2SpeechSegmenter.build("""
if old not in s: raise SystemExit("v51: assignment builder block not found")
s = s.replace(old, new, 1)
old = """            maxChars = 180,
            characterVoiceAssignments = assignments
        )"""
new = """            maxChars = 180,
            characterVoiceAssignments = assignments,
            useCharacterVoices = rolesEnabled,
            maleVoiceId = maleVoice,
            femaleVoiceId = femaleVoice
        )"""
if old not in s: raise SystemExit("v51: segmenter invocation tail not found")
s = s.replace(old, new, 1)

start = s.find("    private fun startBookPlayback() {")
end = s.find("    private fun stopBookPlayback() {", start)
if start < 0 or end < 0: raise SystemExit("v51: playback method boundaries not found")
playback = r'''    private fun startBookPlayback() {
        val engine = ttsEngine ?: return
        if (ttsWorker?.isAlive == true) return
        val queue = buildTtsSpeechQueue()
        if (queue.isEmpty()) {
            Toast.makeText(this, "Нет текста для озвучивания", Toast.LENGTH_SHORT).show()
            return
        }
        if (ttsResumeStorageKey.isBlank()) refreshTtsResumeKey(loadSaved = true)
        val resumeKey = ttsResumeStorageKey.ifBlank { "resume_" + ttsBookKey }
        val startAt = ttsResumeIndex.coerceIn(0, queue.size)
        val settings = getSharedPreferences("fb2audioprep_tts_settings", MODE_PRIVATE)
        val durationScale = settings.getFloat("duration_scale", 1f).coerceIn(0.75f, 1.35f)
        val gain = settings.getFloat("gain", 1f).coerceIn(0.2f, 1f)
        val pauseMs = settings.getInt("pause_ms", 100).coerceIn(0, 800)
        ttsStopRequested = false
        playBookButton.isEnabled = false
        stopBookButton.isEnabled = true

        ttsWorker = Thread({
            var completed = false
            try {
                val pieces = queue.iterator()
                var skipped = 0
                while (skipped < startAt && pieces.hasNext()) {
                    pieces.next()
                    skipped++
                }
                val prebuffer = java.util.ArrayDeque<TeraTtsSpeechPiece>(3)
                fun fillPrebuffer() {
                    while (prebuffer.size < 3 && pieces.hasNext()) prebuffer.addLast(pieces.next())
                }
                fillPrebuffer()
                var played = startAt
                while (prebuffer.isNotEmpty() && !ttsStopRequested) {
                    val next = prebuffer.removeFirst()
                    fillPrebuffer()
                    runOnUiThread {
                        status.text = "Озвучивание: фрагмент " + (played + 1) + " из " + queue.size +
                            "\nГолос: " + next.voiceId + "\nРежим: " + next.kind
                    }
                    engine.synthesizeAndPlay(
                        TeraTtsTextFormatter.russian(next.text),
                        next.voiceId,
                        durationScale = durationScale,
                        seed = 1234L + played,
                        gain = gain
                    )
                    if (ttsStopRequested) break
                    played++
                    ttsResumeIndex = played
                    getSharedPreferences("audiobook_playback", MODE_PRIVATE).edit()
                        .putInt(resumeKey, ttsResumeIndex).apply()
                    if (pauseMs > 0 && prebuffer.isNotEmpty() && !ttsStopRequested) {
                        try { Thread.sleep(pauseMs.toLong()) } catch (_: InterruptedException) {
                            Thread.currentThread().interrupt()
                            ttsStopRequested = true
                        }
                    }
                }
                completed = !ttsStopRequested && prebuffer.isEmpty() && !pieces.hasNext()
                if (completed) {
                    ttsResumeIndex = 0
                    getSharedPreferences("audiobook_playback", MODE_PRIVATE).edit()
                        .putInt(resumeKey, 0).apply()
                }
                runOnUiThread {
                    status.text = when {
                        completed -> "Озвучивание книги завершено."
                        ttsStopRequested -> "Озвучивание остановлено. Можно продолжить с этого места."
                        else -> "Озвучивание приостановлено."
                    }
                    playBookButton.text = if (ttsResumeIndex > 0)
                        "▶ Продолжить озвучивание" else "▶ Озвучить книгу"
                }
            } catch (e: Throwable) {
                runOnUiThread {
                    status.text = "Ошибка озвучивания: " + (e.message ?: "неизвестно")
                }
            } finally {
                runOnUiThread {
                    playBookButton.isEnabled = originalText.isNotBlank() &&
                        (ttsEngine?.status()?.ready == true)
                    stopBookButton.isEnabled = false
                }
            }
        }, "teratts-v2-playback").also { it.start() }
    }

'''
s = s[:start] + playback + s[end:]
p.write_text(s, encoding="utf-8")

print("v51: add Audiotome voice settings and route actual playback through per-utterance voice assignments.")
