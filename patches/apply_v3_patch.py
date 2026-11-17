from pathlib import Path
import re

main = Path('app/src/main/java/ru/fbaudioprep/MainActivity.kt')
manifest = Path('app/src/main/AndroidManifest.xml')
gradle = Path('app/build.gradle.kts')

s = main.read_text(encoding='utf-8')
if 'private fun openBookPreview()' not in s:
    anchor = '''        root.addView(Button(this).apply {
            text = "Открыть книгу"
            setOnClickListener { openBook() }
        })
'''
    if anchor not in s:
        raise SystemExit('Cannot find Open book button insertion point')
    s = s.replace(anchor, anchor + '''
        root.addView(Button(this).apply {
            text = "Открыть книгу для чтения"
            setOnClickListener { openBookPreview() }
        })
''', 1)

old_preview = '''        root.addView(
            ScrollView(this).apply { addView(preview) },
            LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f)
        )
        setContentView(root)
'''
new_preview = '''        // The book is no longer squeezed into a tiny scrolling strip on the home screen.
        // The preview TextView remains as an internal status buffer; reading happens in
        // the dedicated full-screen BookReaderActivity.
        setContentView(ScrollView(this).apply {
            isFillViewport = true
            addView(root)
        })
'''
if old_preview in s:
    s = s.replace(old_preview, new_preview, 1)
elif 'dedicated full-screen BookReaderActivity' not in s:
    raise SystemExit('Cannot find old preview strip to replace')

if 'private fun openBookPreview()' not in s:
    anchor = '''    private fun openBook() {
'''
    function = '''    private fun openBookPreview() {
        if (originalText.isBlank()) {
            Toast.makeText(this, "Сначала откройте книгу", Toast.LENGTH_SHORT).show()
            return
        }
        val text = processedText.ifBlank { originalText }
        startActivity(Intent(this, BookReaderActivity::class.java).apply {
            putExtra(BookReaderActivity.EXTRA_TITLE, sourceName.ifBlank { "Книга" })
            putExtra(BookReaderActivity.EXTRA_TEXT, text)
        })
    }

'''
    if anchor not in s:
        raise SystemExit('Cannot find openBook() insertion point')
    s = s.replace(anchor, function + anchor, 1)

s = re.sub(r'FB2 AudioPrep [0-9.]+', 'FB2 AudioPrep 2.0.1', s)
main.write_text(s, encoding='utf-8')

activity = Path('app/src/main/java/ru/fbaudioprep/BookReaderActivity.kt')
activity.write_text(r'''package ru.fbaudioprep

import android.app.Activity
import android.graphics.Color
import android.os.Bundle
import android.view.Gravity
import android.view.ViewGroup
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import kotlin.math.roundToInt

/** A dedicated, readable full-screen book preview. */
class BookReaderActivity : Activity() {
    private lateinit var scroll: ScrollView
    private lateinit var body: TextView
    private lateinit var progress: TextView
    private var fontSize = 19f

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val title = intent.getStringExtra(EXTRA_TITLE).orEmpty().ifBlank { "Книга" }
        val content = intent.getStringExtra(EXTRA_TEXT).orEmpty()

        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(Color.rgb(250, 248, 242))
        }
        val toolbar = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(dp(12), dp(8), dp(12), dp(8))
            setBackgroundColor(Color.rgb(239, 235, 225))
        }
        toolbar.addView(Button(this).apply {
            text = "‹ Назад"
            setOnClickListener { finish() }
        })
        toolbar.addView(TextView(this).apply {
            text = title
            textSize = 17f
            setTextColor(Color.rgb(35, 35, 35))
            maxLines = 2
            setPadding(dp(12), 0, 0, 0)
        }, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        root.addView(toolbar)

        scroll = ScrollView(this).apply {
            isFillViewport = true
            setBackgroundColor(Color.rgb(250, 248, 242))
        }
        body = TextView(this).apply {
            text = content
            textSize = fontSize
            setTextColor(Color.rgb(38, 36, 32))
            setPadding(dp(25), dp(22), dp(25), dp(34))
            setLineSpacing(dp(5).toFloat(), 1.12f)
            setTextIsSelectable(true)
            includeFontPadding = true
        }
        scroll.addView(body)
        root.addView(scroll, LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f
        ))

        val footer = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(dp(12), dp(5), dp(12), dp(8))
            setBackgroundColor(Color.rgb(239, 235, 225))
        }
        footer.addView(Button(this).apply {
            text = "А−"
            setOnClickListener { changeFont(-1f) }
        })
        footer.addView(Button(this).apply {
            text = "А+"
            setOnClickListener { changeFont(1f) }
        })
        progress = TextView(this).apply {
            text = "0%"
            textSize = 13f
            setTextColor(Color.DKGRAY)
            gravity = Gravity.CENTER
        }
        footer.addView(progress, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        root.addView(footer)
        scroll.setOnScrollChangeListener { v: ScrollView, _, y, _, _ ->
            val range = (body.height - v.height).coerceAtLeast(1)
            progress.text = "${((y.toFloat() / range) * 100).roundToInt().coerceIn(0, 100)}%"
        }
        setContentView(root)
    }

    private fun changeFont(delta: Float) {
        val y = scroll.scrollY
        fontSize = (fontSize + delta).coerceIn(14f, 32f)
        body.textSize = fontSize
        scroll.post { scroll.scrollTo(0, y) }
    }

    private fun dp(value: Int): Int = (value * resources.displayMetrics.density).roundToInt()

    companion object {
        const val EXTRA_TITLE = "book_title"
        const val EXTRA_TEXT = "book_text"
    }
}
''', encoding='utf-8')

m = manifest.read_text(encoding='utf-8')
m = re.sub(r'FB2 AudioPrep [0-9.]+', 'FB2 AudioPrep 2.0.1', m)
if 'BookReaderActivity' not in m:
    marker = '<activity android:name=".MainActivity"'
    if marker not in m:
        raise SystemExit('Cannot find MainActivity manifest declaration')
    m = m.replace(marker, '<activity android:name=".BookReaderActivity" android:exported="false"/><activity android:name=".MainActivity"', 1)
manifest.write_text(m, encoding='utf-8')

g = gradle.read_text(encoding='utf-8')
g = g.replace('versionCode = 21; versionName = "2.0.0"', 'versionCode = 22; versionName = "2.0.1"')
g = g.replace('versionCode = 20; versionName = "1.9.0"', 'versionCode = 22; versionName = "2.0.1"')
gradle.write_text(g, encoding='utf-8')
print('Applied FB2AudioPrep 2.0.1 full-screen reader UI patch.')
