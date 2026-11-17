from pathlib import Path
p = Path("app/src/main/java/ru/fbaudioprep/BookReaderActivity.kt")
if not p.exists(): raise SystemExit("Reader source missing")
p.write_text(r'''package ru.fbaudioprep

import android.app.Activity
import android.app.AlertDialog
import android.graphics.Color
import android.graphics.Typeface
import android.os.Bundle
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import kotlin.math.roundToInt

class BookReaderActivity : Activity() {
    private lateinit var scroll: ScrollView
    private lateinit var body: TextView
    private lateinit var progress: TextView
    private var title = "Книга"
    private var content = ""
    private var key = "book"
    private var font = 19f
    private var spacing = 1.18f
    private var theme = 0
    private data class Colors(val bg: Int, val fg: Int, val muted: Int, val panel: Int, val accent: Int)
    private val palettes = listOf(
        Colors(Color.rgb(250,248,243), Color.rgb(43,40,35), Color.rgb(125,117,105), Color.rgb(242,238,229), Color.rgb(139,104,68)),
        Colors(Color.rgb(30,32,35), Color.rgb(229,228,222), Color.rgb(160,162,164), Color.rgb(39,42,46), Color.rgb(208,174,119)),
        Colors(Color.rgb(239,229,207), Color.rgb(75,58,42), Color.rgb(137,112,84), Color.rgb(230,216,189), Color.rgb(139,94,54))
    )
    private val c get() = palettes[theme]
    private var chapters: List<Pair<String, Int>> = emptyList()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        title = intent.getStringExtra(EXTRA_TITLE).orEmpty().ifBlank { "Книга" }
        content = intent.getStringExtra(EXTRA_TEXT).orEmpty()
        key = "reader_" + title.hashCode() + "_" + content.length
        val prefs = getSharedPreferences("reader_preferences", MODE_PRIVATE)
        font = prefs.getFloat(key+"_font", 19f).coerceIn(15f,30f)
        spacing = prefs.getFloat(key+"_spacing", 1.18f).coerceIn(1f,1.7f)
        theme = prefs.getInt(key+"_theme",0).coerceIn(0,2)
        chapters = findChapters(content)
        buildUi()
        scroll.post { scroll.scrollTo(0, prefs.getInt(key+"_scroll",0).coerceAtLeast(0)) }
    }

    private fun buildUi() {
        val root = LinearLayout(this).apply { orientation=LinearLayout.VERTICAL; setBackgroundColor(c.bg) }
        val bar = LinearLayout(this).apply {
            orientation=LinearLayout.HORIZONTAL; gravity=Gravity.CENTER_VERTICAL
            setPadding(dp(14),dp(8),dp(14),dp(8)); setBackgroundColor(c.bg)
        }
        bar.addView(action("‹",30){ finish() }, LinearLayout.LayoutParams(dp(42),dp(46)))
        val heading = LinearLayout(this).apply { orientation=LinearLayout.VERTICAL; gravity=Gravity.CENTER_VERTICAL }
        heading.addView(TextView(this).apply {
            text=title; textSize=16f; setTextColor(c.fg); maxLines=1
            typeface=Typeface.create("sans-serif-medium",Typeface.NORMAL)
            ellipsize=android.text.TextUtils.TruncateAt.END
        })
        heading.addView(TextView(this).apply {
            text="ЧТЕНИЕ"; textSize=9f; letterSpacing=.18f; setTextColor(c.muted)
        })
        bar.addView(heading,LinearLayout.LayoutParams(0,-2,1f))
        bar.addView(action("Aa",17){ settings() },LinearLayout.LayoutParams(dp(48),dp(46)))
        bar.addView(action("⋮",24){ menu() },LinearLayout.LayoutParams(dp(38),dp(46)))
        root.addView(bar)

        scroll=ScrollView(this).apply { isFillViewport=true; overScrollMode=View.OVER_SCROLL_NEVER; setBackgroundColor(c.bg) }
        body=TextView(this).apply {
            text=content; textSize=font; setTextColor(c.fg)
            typeface=Typeface.create("serif",Typeface.NORMAL)
            setPadding(dp(25),dp(22),dp(25),dp(52))
            setLineSpacing(dp(4).toFloat(),spacing); includeFontPadding=true
            setTextIsSelectable(true)
        }
        scroll.addView(body)
        root.addView(scroll,LinearLayout.LayoutParams(-1,0,1f))
        val footer=LinearLayout(this).apply {
            orientation=LinearLayout.VERTICAL; setBackgroundColor(c.panel)
            setPadding(dp(18),dp(9),dp(18),dp(12))
        }
        val row=LinearLayout(this).apply { gravity=Gravity.CENTER_VERTICAL }
        progress=TextView(this).apply { text="0%"; textSize=11f; setTextColor(c.muted) }
        row.addView(progress,LinearLayout.LayoutParams(0,-2,1f))
        row.addView(TextView(this).apply {
            text=if(chapters.isEmpty()) "Книга" else "\${chapters.size} разделов"
            textSize=11f; setTextColor(c.muted)
        })
        footer.addView(row)
        val track=LinearLayout(this).apply { setBackgroundColor(c.muted) }
        val fill=View(this).apply { setBackgroundColor(c.accent); tag="progress_fill" }
        track.addView(fill,LinearLayout.LayoutParams(0,dp(3)))
        footer.addView(track,LinearLayout.LayoutParams(-1,dp(3)).apply { topMargin=dp(8) })
        root.addView(footer)
        scroll.setOnScrollChangeListener { _,_,y,_,_ ->
            val range=(body.height-scroll.height).coerceAtLeast(1)
            val f=(y.toFloat()/range).coerceIn(0f,1f)
            progress.text="\${(f*100).roundToInt()}%"
            fill.layoutParams=LinearLayout.LayoutParams((track.width*f).roundToInt(),dp(3))
            fill.requestLayout()
            getSharedPreferences("reader_preferences",MODE_PRIVATE).edit().putInt(key+"_scroll",y).apply()
        }
        setContentView(root)
    }

    private fun settings() {
        AlertDialog.Builder(this).setTitle("Настройки чтения")
            .setItems(arrayOf("Размер текста","Межстрочный интервал","Цветовая тема")) { _,i ->
                when(i){ 0->fontDialog(); 1->spacingDialog(); 2->themeDialog() }
            }.show()
    }
    private fun fontDialog() {
        val sizes=floatArrayOf(16f,19f,22f,26f)
        AlertDialog.Builder(this).setTitle("Размер текста")
            .setSingleChoiceItems(arrayOf("Маленький","Обычный","Крупный","Очень крупный"),sizes.indexOf(font).coerceAtLeast(1)){d,i->
                font=sizes[i]; body.textSize=font; save(); d.dismiss()
            }.setNegativeButton("Закрыть",null).show()
    }
    private fun spacingDialog() {
        val values=floatArrayOf(1.05f,1.18f,1.38f)
        AlertDialog.Builder(this).setTitle("Межстрочный интервал")
            .setSingleChoiceItems(arrayOf("Компактный","Обычный","Свободный"),values.indexOf(spacing).coerceAtLeast(1)){d,i->
                spacing=values[i]; body.setLineSpacing(dp(4).toFloat(),spacing); save(); d.dismiss()
            }.setNegativeButton("Закрыть",null).show()
    }
    private fun themeDialog() {
        AlertDialog.Builder(this).setTitle("Цветовая тема")
            .setSingleChoiceItems(arrayOf("Светлая бумага","Тёмная","Сепия"),theme){d,i->
                theme=i; save(); recreate(); d.dismiss()
            }.setNegativeButton("Закрыть",null).show()
    }
    private fun menu() {
        AlertDialog.Builder(this).setItems(arrayOf("Содержание","Найти в книге","Сохранить закладку","К закладке")){_,i->
            when(i){0->contents();1->search();2->bookmark(false);3->bookmark(true)}
        }.show()
    }
    private fun contents() {
        if(chapters.isEmpty()){ Toast.makeText(this,"Заголовки глав не найдены",Toast.LENGTH_SHORT).show(); return }
        AlertDialog.Builder(this).setTitle("Содержание")
            .setItems(chapters.map{it.first}.toTypedArray()){_,i-> jump(chapters[i].second) }
            .setNegativeButton("Закрыть",null).show()
    }
    private fun search() {
        val field=EditText(this).apply { hint="Слово или фраза" }
        AlertDialog.Builder(this).setTitle("Найти в книге").setView(field)
            .setPositiveButton("Найти"){_,_->
                val q=field.text.toString().trim()
                if(q.isNotEmpty()){
                    val at=content.indexOf(q,ignoreCase=true)
                    if(at>=0) jump(at) else Toast.makeText(this,"Ничего не найдено",Toast.LENGTH_SHORT).show()
                }
            }.setNegativeButton("Отмена",null).show()
    }
    private fun bookmark(go:Boolean) {
        val prefs=getSharedPreferences("reader_preferences",MODE_PRIVATE)
        if(go){ scroll.post{scroll.smoothScrollTo(0,prefs.getInt(key+"_bookmark",0))} }
        else { prefs.edit().putInt(key+"_bookmark",scroll.scrollY).apply(); Toast.makeText(this,"Закладка сохранена",Toast.LENGTH_SHORT).show() }
    }
    private fun jump(offset:Int) {
        body.post {
            val safe=offset.coerceIn(0,body.text.length)
            val line=body.text.subSequence(0,safe).count{it=='\n'}.coerceIn(0,(body.lineCount-1).coerceAtLeast(0))
            val layout=body.layout ?: return@post
            scroll.smoothScrollTo(0,layout.getLineTop(line)+body.paddingTop)
        }
    }
    private fun findChapters(text:String):List<Pair<String,Int>> {
        val out=mutableListOf<Pair<String,Int>>(); var pos=0
        text.split('\n').forEach { line ->
            val s=line.trim()
            if(s.matches(Regex("(?i)^(глава|часть|пролог|эпилог|интерлюдия)(\\s+.*)?$")) ||
                s.matches(Regex("^\\d{1,3}[.)]?\\s+.{2,70}$"))) out.add(s.take(90) to pos)
            pos+=line.length+1
        }
        return out
    }
    private fun save() {
        getSharedPreferences("reader_preferences",MODE_PRIVATE).edit()
            .putFloat(key+"_font",font).putFloat(key+"_spacing",spacing).putInt(key+"_theme",theme).apply()
    }
    private fun action(label:String,size:Int,run:()->Unit)=TextView(this).apply {
        text=label; textSize=size.toFloat(); gravity=Gravity.CENTER; setTextColor(c.fg)
        isClickable=true; isFocusable=true; setOnClickListener{run()}
    }
    private fun dp(v:Int)=(v*resources.displayMetrics.density).roundToInt()
    override fun onPause(){ super.onPause(); if(::scroll.isInitialized){getSharedPreferences("reader_preferences",MODE_PRIVATE).edit().putInt(key+"_scroll",scroll.scrollY).apply();save()} }

    companion object {
        const val EXTRA_TITLE="book_title"
        const val EXTRA_TEXT="book_text"
    }
}
''', encoding="utf-8")
print("Applied reader UX v2.")
