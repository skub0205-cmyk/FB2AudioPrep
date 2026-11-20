from pathlib import Path

engine = Path("app/src/main/java/ru/fbaudioprep/teratts/TeraRoleEngine.kt")
s = engine.read_text(encoding="utf-8")

old_sig = '''    fun analyze(context: Context, text: String, stop: () -> Boolean = { false }, onProgress: (Int, String) -> Unit = { _, _ -> }): Analysis {'''
new_sig = '''    fun analyze(
        context: Context,
        text: String,
        chapterOffsets: List<Int> = emptyList(),
        stop: () -> Boolean = { false },
        onProgress: (Int, String) -> Unit = { _, _ -> }
    ): Analysis {'''
if s.count(old_sig) != 1:
    raise SystemExit("v66: analyze signature not found exactly once")
s = s.replace(old_sig, new_sig, 1)

old_block = '''        val guesses = if (available && names.isNotEmpty()) {
            RoleModel.guesses(
                context, scope, text, lines, names, aliases,
                compute = true, threads = 2, stop = stop,
                onStart = { onProgress(10, "Загружаю ИИ-модель и начинаю проверку…") },
                onWindow = { done, total ->
                    val percent = 10 + (80f * done / total.coerceAtLeast(1)).toInt()
                    onProgress(percent, "Проверено блоков: $done из $total\\nОсталось: ${total - done}")
                },
                low = false
            ).orEmpty()
        } else emptyMap()
'''
new_block = '''        // TeraTTS 1.59 keeps role-model results per chapter. Keep the book-wide
        // rule pass (it discovers aliases and character genders using later chapters),
        // then run/cache the neural windows independently for each chapter.
        val guesses = HashMap<Int, RoleModel.Guess>()
        if (available && names.isNotEmpty()) {
            val starts = (listOf(0) + chapterOffsets.filter { it > 0 && it < text.length })
                .distinct().sorted()
            val chapters = starts.mapIndexedNotNull { index, start ->
                val end = starts.getOrNull(index + 1) ?: text.length
                if (end > start) start to end else null
            }.ifEmpty { listOf(0 to text.length) }
            var paragraphBase = 0
            chapters.forEachIndexed { chapterIndex, (chapterStart, chapterEnd) ->
                if (stop()) return@forEachIndexed
                val chapterText = text.substring(chapterStart, chapterEnd)
                val localLines = lines.asSequence()
                    .filter { it.start >= chapterStart && it.start < chapterEnd }
                    .map { line ->
                        fun localRanges(ranges: List<IntArray>): List<IntArray> = ranges.mapNotNull { range ->
                            val a = maxOf(range[0], chapterStart)
                            val b = minOf(range[1], chapterEnd)
                            if (b > a) intArrayOf(a - chapterStart, b - chapterStart) else null
                        }
                        RoleWindows.Line(
                            line.start - chapterStart,
                            (line.end.coerceAtMost(chapterEnd) - chapterStart).coerceAtLeast(0),
                            line.kind, line.quoted, localRanges(line.speech), localRanges(line.authors), line.rules
                        )
                    }.toList()
                val chapterGuesses = RoleModel.guesses(
                    context, scope, chapterText, localLines, names, aliases,
                    compute = true, threads = 2, stop = stop,
                    onStart = { onProgress(10 + (80 * chapterIndex / chapters.size), "Загружаю ИИ-модель для главы ${chapterIndex + 1} из ${chapters.size}…") },
                    onWindow = { done, total ->
                        val fraction = (chapterIndex + done.toFloat() / total.coerceAtLeast(1)) / chapters.size
                        val percent = 10 + (80f * fraction).toInt()
                        onProgress(percent, "Глава ${chapterIndex + 1} из ${chapters.size}: проверено блоков $done из $total\\nОсталось в главе: ${total - done}")
                    },
                    low = false
                ).orEmpty()
                chapterGuesses.forEach { (localParagraph, guess) ->
                    guesses[paragraphBase + localParagraph] = guess
                }
                paragraphBase += chapterText.count { it == '\\n' }
            }
        }
'''
if s.count(old_block) != 1:
    raise SystemExit("v66: whole-book RoleModel block not found exactly once")
s = s.replace(old_block, new_block, 1)
engine.write_text(s, encoding="utf-8")

activity = Path("app/src/main/java/ru/fbaudioprep/MainActivity.kt")
a = activity.read_text(encoding="utf-8")
old_call = '''                val analysis = TeraRoleEngine.analyze(
                    this@MainActivity,
                    bookText,
                    stop = { token != dialogueAnalysisToken },'''
new_call = '''                val analysisBookId = currentLibraryBookId
                val chapterOffsets = analysisBookId?.let { id ->
                    BookLibraryStore.chapters(applicationContext, id).map { it.offset }
                }.orEmpty()
                val analysis = TeraRoleEngine.analyze(
                    this@MainActivity,
                    bookText,
                    chapterOffsets = chapterOffsets,
                    stop = { token != dialogueAnalysisToken },'''
if a.count(old_call) != 1:
    raise SystemExit("v66: dialogue analysis call not found exactly once")
a = a.replace(old_call, new_call, 1)
activity.write_text(a, encoding="utf-8")
print("v66: use whole-book character rules with chapter-scoped, resumable neural inference caches.")
