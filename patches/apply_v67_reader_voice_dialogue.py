from pathlib import Path

B = Path("app/src/main/java/ru/fbaudioprep")

def replace(path, old, new, label):
    p = path if isinstance(path, Path) else B / path
    s = p.read_text(encoding="utf-8")
    if s.count(old) != 1:
        raise SystemExit(f"v67: {label} anchor count={s.count(old)}")
    p.write_text(s.replace(old, new, 1), encoding="utf-8")

replace("AudiotomeHomeLayout.kt",
'''        val paper = FrameLayout(activity).apply {
            background = GradientDrawable().apply {''',
'''        val paper = FrameLayout(activity).apply {
            tag = "audiotome-paper-reader"
            background = GradientDrawable().apply {''', "paper tag")
replace("AudiotomeHomeLayout.kt",
'''        val sectionHost = FrameLayout(activity)
        sectionHost.addView(paper, FrameLayout.LayoutParams(-1, -1))''',
'''        val sectionHost = FrameLayout(activity).apply { tag = "audiotome-section-host" }
        sectionHost.addView(paper, FrameLayout.LayoutParams(-1, -1))''', "reader host tag")
replace("AudiotomeHomeLayout.kt",
'''        fun showSection(sectionTitle: String, actions: List<Button>, emptyMessage: String? = null) {
            sectionHost.removeAllViews()
            val scroll = ScrollView(activity).apply {''',
'''        fun showSection(sectionTitle: String, actions: List<Button>, emptyMessage: String? = null) {
            sectionHost.removeAllViews()
            paper.visibility = View.GONE
            sectionHost.addView(paper, FrameLayout.LayoutParams(-1, -1))
            val scroll = ScrollView(activity).apply {''', "tool section overlay")
replace("AudiotomeHomeLayout.kt",
'''                setOnClickListener {
                    sectionHost.removeAllViews()
                    sectionHost.addView(paper, FrameLayout.LayoutParams(-1, -1))
                }''',
'''                setOnClickListener {
                    sectionHost.removeAllViews()
                    paper.visibility = View.VISIBLE
                    sectionHost.addView(paper, FrameLayout.LayoutParams(-1, -1))
                }''', "return to reader")

p = B / "MainActivity.kt"
s = p.read_text(encoding="utf-8")
anchor = "    private fun openBookPreview() {"
helper = '''    private fun showBookReaderSurface() {
        val content = findViewById<ViewGroup>(android.R.id.content) ?: return
        val host = content.findViewWithTag<android.widget.FrameLayout>("audiotome-section-host") ?: return
        val paper = content.findViewWithTag<android.widget.FrameLayout>("audiotome-paper-reader") ?: return
        for (index in host.childCount - 1 downTo 0) {
            if (host.getChildAt(index) !== paper) host.removeViewAt(index)
        }
        if (paper.parent !== host) {
            (paper.parent as? ViewGroup)?.removeView(paper)
            host.addView(paper, android.widget.FrameLayout.LayoutParams(-1, -1))
        }
        paper.visibility = android.view.View.VISIBLE
    }

'''
if s.count(anchor) != 1: raise SystemExit("v67: reader entry point missing")
if "private fun showBookReaderSurface()" not in s: s = s.replace(anchor, helper + anchor, 1)
old = '''                    preview.text = book.text.take(8000)
                    openBookPreview()'''
new = '''                    preview.text = book.text.take(8000)
                    showBookReaderSurface()
                    openBookPreview()'''
if s.count(old) != 1: raise SystemExit("v67: import-to-reader handoff missing")
s = s.replace(old, new, 1)

label_helper = '''    private fun ttsVoiceLabel(id: String): String = when (id) {
        "ru_f1" -> "Женский 1 · русский"
        "ru_f2" -> "Женский 2 · русский"
        "ru_m1" -> "Мужской 1 · русский"
        "ru_m5" -> "Мужской 5 · русский"
        "eng_f3" -> "Женский · мультиязычный (русский текст)"
        "eng_f5" -> "Женский 2 · мультиязычный (русский текст)"
        "eng_m3" -> "Мужской · мультиязычный (русский текст)"
        "eng_m4" -> "Мужской 2 · мультиязычный (русский текст)"
        "eng_f4_whisper" -> "Женский · шёпот (мультиязычный)"
        "eng_m2_whisper" -> "Мужской · шёпот (мультиязычный)"
        else -> id
    }

'''
anchor = "    private fun showAudiobookSettings() {"
if s.count(anchor) != 1: raise SystemExit("v67: audiobook settings missing")
if "private fun ttsVoiceLabel" not in s: s = s.replace(anchor, label_helper + anchor, 1)
s = s.replace('''            spinner.adapter = ArrayAdapter(
                this, android.R.layout.simple_spinner_dropdown_item, voices
            )''', '''            spinner.adapter = ArrayAdapter(
                this, android.R.layout.simple_spinner_dropdown_item, voices.map(::ttsVoiceLabel)
            )''', 1)
s = s.replace('''        val femaleDefault = voices.firstOrNull { Regex("""(^|[_-])f\\d""").containsMatchIn(it) } ?: narratorDefault
        val maleDefault = voices.firstOrNull { Regex("""(^|[_-])m\\d""").containsMatchIn(it) } ?: narratorDefault''', '''        val femaleDefault = voices.firstOrNull { it == "ru_f1" }
            ?: voices.firstOrNull { Regex("""(^|[_-])f\\d""").containsMatchIn(it) } ?: narratorDefault
        val maleDefault = voices.firstOrNull { it == "ru_m5" }
            ?: voices.firstOrNull { Regex("""(^|[_-])m\\d""").containsMatchIn(it) } ?: narratorDefault''', 1)
s = s.replace('''                selectedTtsVoice = narrator.selectedItem?.toString()?.takeIf { it in voices } ?: narratorDefault
                prefs.edit()
                    .putString("narrator_voice", selectedTtsVoice)
                    .putString("female_voice", female.selectedItem?.toString() ?: femaleDefault)
                    .putString("male_voice", male.selectedItem?.toString() ?: maleDefault)''', '''                selectedTtsVoice = voices.getOrNull(narrator.selectedItemPosition) ?: narratorDefault
                prefs.edit()
                    .putString("narrator_voice", selectedTtsVoice)
                    .putString("female_voice", voices.getOrNull(female.selectedItemPosition) ?: femaleDefault)
                    .putString("male_voice", voices.getOrNull(male.selectedItemPosition) ?: maleDefault)''', 1)
s = s.replace('''        val labels = voices.map { id -> when (id) {
            "ru_f1" -> "Женский 1"; "ru_f2" -> "Женский 2"
            "ru_m1" -> "Мужской 1"; "ru_m5" -> "Мужской 5"; else -> id
        } }.toTypedArray()''', '''        val labels = voices.map(::ttsVoiceLabel).toTypedArray()''', 1)
s = s.replace('''                        durationScale = durationScale,
                        seed = 1234L + played,''', '''                        durationScale = if (next.voiceId.startsWith("eng_")) (durationScale * 0.8f).coerceIn(0.6f, 1.1f) else durationScale,
                        seed = 1234L + played,''', 1)
p.write_text(s, encoding="utf-8")

replace("CharacterVoiceAssignmentStore.kt",
'                val candidates = availableVoices.filter { voiceGender(it) == gender }',
'                val candidates = availableVoices.filter { voiceGender(it) == gender && !it.contains("whisper", ignoreCase = true) }',
"automatic voice filter")

voice_ids = '"ru_f1", "ru_m5", "ru_f2", "ru_m1", "eng_f3", "eng_f4_whisper", "eng_f5", "eng_m2_whisper", "eng_m3", "eng_m4"'
replace("TeraTtsV2OnnxEngine.kt",
'        val RUSSIAN_VOICES = listOf("ru_f1", "ru_m5", "ru_f2", "ru_m1")',
'        // Ten styles supported by TeraTTS; ru_f1/ru_m5 are its recommended Russian prompts.\n        val RUSSIAN_VOICES = listOf(' + voice_ids + ')',
"engine voice catalog")
replace("AudiobookSpeechPipeline.kt",
'    val all: List<String> = listOf(FEMALE_1, MALE_5, FEMALE_2, MALE_1)',
'    val all: List<String> = listOf(FEMALE_1, MALE_5, FEMALE_2, MALE_1, "eng_f3", "eng_f4_whisper", "eng_f5", "eng_m2_whisper", "eng_m3", "eng_m4")',
"speech voice catalog")

downloader = B / "TeraTtsV2ModelDownloader.kt"
s = downloader.read_text(encoding="utf-8")
old = '        private val VOICES = listOf("ru_f1", "ru_f2", "ru_m1", "ru_m5")'
new = '        private val VOICES = listOf(' + voice_ids + ')'
if s.count(old) != 1: raise SystemExit("v67: downloader voice catalog missing")
s = s.replace(old, new, 1)
anchor = '    private fun downloadOne(relative: String, part: File, progress: (Int) -> Unit) {'
method = '''    fun downloadMissingVoiceStyles(context: Context, onProgress: (String, Int) -> Unit = { _, _ -> }): List<String> {
        cancelled.set(false)
        val installed = File(context.filesDir, "voice-models/teratts-v2")
        if (!installed.isDirectory) return emptyList()
        VOICES.forEach { voice ->
            listOf("style_ttl.npy", "style_dp.npy").forEach { fileName ->
                check(!cancelled.get()) { "Загрузка голосов отменена" }
                val relative = "styles/$voice/$fileName"
                val target = File(installed, relative)
                if (!(target.isFile && target.length() > minimumSize(relative))) {
                    target.parentFile?.mkdirs()
                    val part = File(target.parentFile, target.name + ".part")
                    downloadOne(relative, part) { percent -> onProgress(voice, percent) }
                    check(part.length() > minimumSize(relative)) { "Профиль голоса загружен не полностью: $voice" }
                    if (target.exists()) target.delete()
                    check(part.renameTo(target)) { "Не удалось сохранить профиль голоса: $voice" }
                }
            }
        }
        return VOICES.filter { voice ->
            listOf("style_ttl.npy", "style_dp.npy").all { name ->
                val f = File(installed, "styles/$voice/$name")
                f.isFile && f.length() > minimumSize("styles/$voice/$name")
            }
        }
    }

'''
if s.count(anchor) != 1: raise SystemExit("v67: downloader insertion point missing")
s = s.replace(anchor, method + anchor, 1)
downloader.write_text(s, encoding="utf-8")

role = B / "teratts/RoleModel.kt"
s = role.read_text(encoding="utf-8")
s = s.replace('''                if (!room(c)) {
                    Log.i(TAG, "little free memory: the chapter is read by the rules")''', '''                if (enc == null && !room(c)) {
                    Log.i(TAG, "little free memory: the chapter is read by the rules")''', 1)
s = s.replace('''                from: Int = 0, limit: Int = Int.MAX_VALUE, patience: Long = Long.MAX_VALUE,
                onStart: () -> Unit = {}, onWindow: (Int, Int) -> Unit = { _, _ -> }, low: Boolean = true): Map<Int, Guess>? {''', '''                from: Int = 0, limit: Int = Int.MAX_VALUE, patience: Long = Long.MAX_VALUE,
                onStart: () -> Unit = {}, onWindow: (Int, Int) -> Unit = { _, _ -> }, low: Boolean = true,
                keepLoaded: Boolean = false): Map<Int, Guess>? {''', 1)
s = s.replace('''                } finally {
                    unload()     // ~300 MB: not kept while the book is read
                    try { android.os.Process.setThreadPriority(pri0) } catch (_: Throwable) { }
                }''', '''                } finally {
                    if (!keepLoaded) unload()
                    try { android.os.Process.setThreadPriority(pri0) } catch (_: Throwable) { }
                }''', 1)
anchor = '    private fun save(f: File, m: Map<Int, Guess>) {'
release = '''    fun releaseAfterBatch() {
        lock.lock()
        try { unload() } finally { lock.unlock() }
    }

'''
if s.count(anchor) != 1: raise SystemExit("v67: role-model cache insertion point missing")
s = s.replace(anchor, release + anchor, 1)
role.write_text(s, encoding="utf-8")

engine = B / "teratts/TeraRoleEngine.kt"
s = engine.read_text(encoding="utf-8")
s = s.replace('''            var paragraphBase = 0
            chapters.forEachIndexed { chapterIndex, (chapterStart, chapterEnd) ->
                if (stop()) return@forEachIndexed''', '''            val inferenceThreads = Runtime.getRuntime().availableProcessors().coerceIn(2, 4)
            try {
                chapters.forEachIndexed { chapterIndex, (chapterStart, chapterEnd) ->
                if (stop()) return@forEachIndexed''', 1)
old_progress = '''                    compute = true, threads = 2, stop = stop,
                    onStart = { onProgress(10 + (80 * chapterIndex / chapters.size), "Загружаю ИИ-модель для главы ''' + chr(36) + '''{chapterIndex + 1} из ''' + chr(36) + '''{chapters.size}…") },'''
new_progress = '''                    compute = true, threads = inferenceThreads, stop = stop,
                    onStart = { onProgress(10 + (80 * chapterIndex / chapters.size), "Обрабатываю главу " + (chapterIndex + 1) + " из " + chapters.size + "…") },'''
if s.count(old_progress) != 1: raise SystemExit("v67: chapter progress replacement missing")
s = s.replace(old_progress, new_progress, 1)
s = s.replace('''                    low = false
                ).orEmpty()
                chapterGuesses.forEach { (localParagraph, guess) ->
                    guesses[paragraphBase + localParagraph] = guess
                }
                paragraphBase += chapterText.count { it == '\\n' }
            }
        }''', '''                    low = false,
                    keepLoaded = true
                ).orEmpty()
                val paragraphBase = text.substring(0, chapterStart).count { it == '\\n' }
                chapterGuesses.forEach { (localParagraph, guess) ->
                    guesses[paragraphBase + localParagraph] = guess
                }
                }
            } finally {
                RoleModel.releaseAfterBatch()
            }
        }''', 1)
engine.write_text(s, encoding="utf-8")

manifest = Path("app/src/main/AndroidManifest.xml")
ms = manifest.read_text(encoding="utf-8")
if "android.permission.ACCESS_NETWORK_STATE" not in ms:
    ms = ms.replace('<uses-permission android:name="android.permission.INTERNET" />', '<uses-permission android:name="android.permission.INTERNET" />\n    <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />', 1)
manifest.write_text(ms, encoding="utf-8")

s = p.read_text(encoding="utf-8")
anchor = '    private fun restoreInstalledTtsModel(onLoaded: (() -> Unit)? = null) {'
helper = '''    private fun hasValidatedInternet(): Boolean {
        return try {
            val manager = getSystemService(android.content.Context.CONNECTIVITY_SERVICE) as android.net.ConnectivityManager
            val network = manager.activeNetwork ?: return false
            val capabilities = manager.getNetworkCapabilities(network) ?: return false
            capabilities.hasCapability(android.net.NetworkCapabilities.NET_CAPABILITY_INTERNET) &&
                capabilities.hasCapability(android.net.NetworkCapabilities.NET_CAPABILITY_VALIDATED)
        } catch (_: Throwable) { false }
    }

'''
if s.count(anchor) != 1: raise SystemExit("v67: model restore insertion point missing")
s = s.replace(anchor, helper + anchor, 1)
s = s.replace('''            try {
                engine = TeraTtsV2OnnxEngine()
                val loaded = engine.load(directory)''', '''            try {
                var voiceUpdateNote = ""
                val online = hasValidatedInternet()
                if (!online) voiceUpdateNote = "\\nСеть недоступна; оставлены ранее установленные голоса."
                if (online) {
                    try {
                        val available = TeraTtsV2ModelDownloader().downloadMissingVoiceStyles(applicationContext) { voice, percent ->
                            runOnUiThread { status.text = "Добавляю голосовые профили TeraTTS: $voice · $percent%" }
                        }
                        voiceUpdateNote = "\\nДоступно профилей: " + available.size
                    } catch (_: Throwable) {
                        voiceUpdateNote = "\\nДополнительные профили пока не загружены; использую установленные."
                    }
                }
                engine = TeraTtsV2OnnxEngine()
                val loaded = engine.load(directory)''', 1)
s = s.replace('''                    status.text = loaded.message + "\\nМодель восстановлена из памяти устройства.\\nГолоса: " + loaded.voices.joinToString()''', '''                    status.text = loaded.message + "\\nМодель восстановлена из памяти устройства." + voiceUpdateNote + "\\nГолоса: " + loaded.voices.joinToString()''', 1)
p.write_text(s, encoding="utf-8")

print("v67: automatic reader handoff, expanded Tera voice styles, and faster chapter-batched dialogue inference applied.")
