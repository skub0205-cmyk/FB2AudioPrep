from pathlib import Path
import re

old_target_class = '''    class Target(val pi: Int, val span: IntArray, val speech: List<IntArray>, val kind: Int, val rules: String) {
        val hard get() = kind == 0
    }'''
new_target_class = '''    class Target(val pi: Int, val span: IntArray, val speech: List<IntArray>, val kind: Int, val rules: String,
                 val quoted: Boolean = false) {
        val hard get() = kind == 0
    }'''
if old_target_class not in s:
    raise SystemExit("Cannot locate RoleWindows.Target")
s = s.replace(old_target_class, new_target_class, 1)

old_target_create = '''                Target(pi, sh(paras[pi]), l.speech.map { sh(it) }, l.kind, l.rules)'''
new_target_create = '''                Target(pi, sh(paras[pi]), l.speech.map { sh(it) }, l.kind, l.rules, l.quoted)'''
if old_target_create not in s:
    raise SystemExit("Cannot locate RoleWindows.Target construction")
s = s.replace(old_target_create, new_target_create, 1)
role_windows.write_text(s, encoding="utf-8")

role_model = Path("app/src/main/java/ru/fbaudioprep/teratts/RoleModel.kt")
rm = role_model.read_text(encoding="utf-8")
old_filter = '''        val ws = RoleWindows.build(text, lines, names, aliases).filter { w -> w.targets.any { it.hard || it.rules.isEmpty() } }'''
new_filter = '''        val ws = RoleWindows.build(text, lines, names, aliases).filter { w ->
            w.targets.any { it.hard || it.rules.isEmpty() || it.quoted }
        }'''
if old_filter not in rm:
    raise SystemExit("Cannot locate RoleModel window filter")
rm = rm.replace(old_filter, new_filter, 1)
role_model.write_text(rm, encoding="utf-8")

role_windows = Path("app/src/main/java/ru/fbaudioprep/teratts/RoleWindows.kt")
s = role_windows.read_text(encoding="utf-8")
old = '''        val targets = byPi.filter { (_, l) -> !l.quoted && !((l.kind == 1 || l.kind == 5) && l.rules.isNotEmpty()) }.keys'''
new = '''        // Attributed quotes must also be read by m10b with their surrounding context.
        // Unattributed thoughts/messages remain excluded. improve() still protects quoted
        // lines from model overrides, so this pass supplies contextual confirmation only.
        val targets = byPi.filter { (_, l) ->
            (l.quoted && l.authors.isNotEmpty()) ||
                (!l.quoted && !((l.kind == 1 || l.kind == 5) && l.rules.isNotEmpty()))
        }.keys'''
if old not in s:
    raise SystemExit("Cannot locate RoleWindows target selection")
s = s.replace(old, new, 1)
role_windows.write_text(s, encoding="utf-8")

engine = Path("app/src/main/java/ru/fbaudioprep/teratts/TeraRoleEngine.kt")
e = engine.read_text(encoding="utf-8")
old_reason = '''                modelChoseSpeaker -> "TeraTTS m10b: нейросеть выбрала «\${guess!!.speaker}» с вероятностью \${(guess.prob * 100).toInt()}%"'''
new_reason = '''                modelChoseSpeaker && probe.quoted ->
                    "TeraTTS m10b: ИИ подтвердил говорящего «\${guess!!.speaker}» по контексту цитаты и авторской ремарке (\${(guess.prob * 100).toInt()}%)"
                modelChoseSpeaker ->
                    "TeraTTS m10b: нейросеть выбрала «\${guess!!.speaker}» с вероятностью \${(guess.prob * 100).toInt()}%"'''
if old_reason not in e:
    raise SystemExit("Cannot locate neural attribution reason")
e = e.replace(old_reason, new_reason, 1)
engine.write_text(e, encoding="utf-8")

test = Path("app/src/test/java/ru/fbaudioprep/teratts/RoleWindowsContextTest.kt")
test.parent.mkdir(parents=True, exist_ok=True)
test.write_text(r'''package ru.fbaudioprep.teratts

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class RoleWindowsContextTest {
    @Test
    fun attributedQuotedSpeechIsSentToContextModel() {
        val text = """
            Перед этим героиня осмотрелась и прислушалась.
            «Нико, добро пожаловать!» раздался в голове приветливый женский голос.
            Нико понял, что с ним говорит незнакомка.
        """.trimIndent()
        val start = text.indexOf("«Нико")
        val end = text.indexOf("»", start) + 1
        val authorStart = text.indexOf("раздался", end)
        val lineStart = text.indexOf("«Нико")
        val lineEnd = text.indexOf('\n', lineStart).let { if (it < 0) text.length else it }

        val line = RoleWindows.Line(
            lineStart, lineEnd, 5, true,
            listOf(intArrayOf(start, end)),
            listOf(intArrayOf(authorStart, lineEnd)),
            "Голос в голове"
        )
        val windows = RoleWindows.build(
            text,
            listOf(line),
            listOf("Нико", "Голос в голове"),
            emptyMap()
        )

        assertTrue("Attributed quote must become a model target", windows.any { w ->
            w.targets.any { it.pi == 1 }
        })
        assertTrue("Model window must retain the female-voice clue", windows.any { w ->
            w.text.contains("приветливый женский голос") &&
                w.text.contains("Нико, добро пожаловать")
        })
        assertTrue("Model window must retain neighbouring narrative context", windows.any { w ->
            w.text.contains("героиня осмотрелась") &&
                w.text.contains("Нико понял")
        })
    }

    @Test
    fun unattributedQuotedThoughtIsNotForcedIntoSpeakerClassification() {
        val text = "«Нико, добро пожаловать!»"
        val line = RoleWindows.Line(
            0, text.length, 0, true,
            listOf(intArrayOf(1, text.length - 1)),
            emptyList(),
            ""
        )

        val windows = RoleWindows.build(text, listOf(line), listOf("Нико"), emptyMap())

        assertFalse("An unattributed quote must not be guessed from its addressee", windows.any { w ->
            w.targets.isNotEmpty()
        })
    }
}
''', encoding="utf-8")

doc = Path("docs/DIALOGUE_ATTRIBUTION_AUTO_FIRST.md")
d = doc.read_text(encoding="utf-8")
addition = '''
## Context-aware neural pass (m10b integration)

RuModernBERT m10b also receives quoted utterances when they have an attached
authorial attribution. The complete model window retains the utterance, its
attribution, and neighbouring paragraphs, including voice-gender descriptions.

An attributed quote is a model target for contextual confirmation, but the
existing RoleModel.improve guard for quoted lines remains in force: the model
cannot replace an explicit rule-based speaker on a quoted line. The model can
therefore add contextual evidence without turning a vocative (“Нико”) into
the speaker or overriding an explicit “женский голос” clue. Unattributed
quoted thoughts remain outside this pass rather than receiving a speculative
speaker.

Regression tests verify that attributed quotes enter the model window with
both neighbouring context and the voice-gender clue, while unattributed quotes
are not forced into speaker classification.
'''
if "## Context-aware neural pass (m10b integration)" not in d:
    d += addition
doc.write_text(d, encoding="utf-8")

gpath = Path("app/build.gradle.kts")
g = gpath.read_text(encoding="utf-8")
m = re.search(r'versionCode\s*=\s*(\d+)\s*;\s*versionName\s*=\s*"([^"]+)"', g)
if not m:
    raise SystemExit("Cannot locate app version")
g = g[:m.start()] + f'versionCode = {int(m.group(1)) + 1}; versionName = "2.1.1"' + g[m.end():]
gpath.write_text(g, encoding="utf-8")

print("Added contextual m10b targets for attributed quotes, protected explicit quote attribution, added regression tests, bumped app to 2.1.1.")
