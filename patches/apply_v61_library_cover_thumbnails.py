from pathlib import Path

p = Path("app/src/main/java/ru/fbaudioprep/MainActivity.kt")
s = p.read_text(encoding="utf-8")
if "v61-library-cover-thumbnails" not in s:
    anchor = "        var visibleBooks = allBooks\n        fun render(query: String) {"
    replacement = """        var visibleBooks = allBooks
        // v61-library-cover-thumbnails: cache downsampled embedded FB2 covers for list rows.
        val coverCache = HashMap<String, android.graphics.Bitmap?>()
        fun render(query: String) {"""
    if anchor not in s: raise SystemExit("v61: cannot find searchable library render function")
    s = s.replace(anchor, replacement, 1)

    start = s.find("            val labels = visibleBooks.map { b ->")
    adapter = "            list.adapter = android.widget.ArrayAdapter(this, android.R.layout.simple_list_item_1, labels)"
    end = s.find(adapter, start)
    if start < 0 or end < 0: raise SystemExit("v61: cannot find simple library list adapter")
    end = s.find(chr(10), end)
    if end < 0: raise SystemExit("v61: cannot find end of simple list adapter")
    replacement = """            list.adapter = object : android.widget.BaseAdapter() {
                override fun getCount(): Int = visibleBooks.size
                override fun getItem(position: Int): Any = visibleBooks[position]
                override fun getItemId(position: Int): Long = visibleBooks[position].id.hashCode().toLong()
                override fun getView(position: Int, convertView: android.view.View?, parent: android.view.ViewGroup): android.view.View {
                    val book = visibleBooks[position]
                    val row = (convertView as? LinearLayout) ?: LinearLayout(this@MainActivity).apply {
                        orientation = LinearLayout.HORIZONTAL
                        gravity = android.view.Gravity.CENTER_VERTICAL
                        setPadding((8 * resources.displayMetrics.density).toInt(), (6 * resources.displayMetrics.density).toInt(),
                            (8 * resources.displayMetrics.density).toInt(), (6 * resources.displayMetrics.density).toInt())
                        minimumHeight = (84 * resources.displayMetrics.density).toInt()
                    }
                    row.removeAllViews()
                    val cover = ImageView(this@MainActivity).apply {
                        scaleType = ImageView.ScaleType.CENTER_CROP
                        setBackgroundColor(0xFF26384A.toInt())
                        val size = (58 * resources.displayMetrics.density).toInt()
                        layoutParams = LinearLayout.LayoutParams(size, (76 * resources.displayMetrics.density).toInt()).apply {
                            marginEnd = (12 * resources.displayMetrics.density).toInt()
                        }
                    }
                    val bitmap = coverCache.getOrPut(book.id) {
                        BookLibraryStore.coverFile(applicationContext, book.id)?.let { file ->
                            runCatching {
                                val bounds = android.graphics.BitmapFactory.Options().apply { inJustDecodeBounds = true }
                                android.graphics.BitmapFactory.decodeFile(file.absolutePath, bounds)
                                var sample = 1
                                while (bounds.outWidth / sample > 220 || bounds.outHeight / sample > 220) sample *= 2
                                val options = android.graphics.BitmapFactory.Options().apply { inSampleSize = sample }
                                android.graphics.BitmapFactory.decodeFile(file.absolutePath, options)
                            }.getOrNull()
                        }
                    }
                    if (bitmap != null) cover.setImageBitmap(bitmap)
                    else cover.setImageResource(android.R.drawable.ic_menu_gallery)
                    row.addView(cover)
                    val details = TextView(this@MainActivity).apply {
                        text = buildString {
                            append(book.title.ifBlank { book.sourceName })
                            if (book.author.isNotBlank()) append("\\n").append(book.author)
                            append("\\n").append(if (book.isFb2) "FB2" else "TXT")
                            append(" · ").append(String.format(java.util.Locale.getDefault(), "%,d", book.textLength)).append(" знаков")
                        }
                        textSize = 13f
                        setTextColor(0xFFE7EAF0.toInt())
                        maxLines = 3
                        ellipsize = android.text.TextUtils.TruncateAt.END
                        setPadding(0, (2 * resources.displayMetrics.density).toInt(), 0, (2 * resources.displayMetrics.density).toInt())
                    }
                    row.addView(details, LinearLayout.LayoutParams(0, -2, 1f))
                    return row
                }
            }"""
    s = s[:start] + replacement + s[end+1:]
    p.write_text(s, encoding="utf-8")

# Show the hierarchy of nested FB2 sections in the table of contents.
p = Path("app/src/main/java/ru/fbaudioprep/AudiotomeHomeLayout.kt")
s = p.read_text(encoding="utf-8")
old = "structured.map { it.title to it.offset }"
new = 'structured.map { ("   ".repeat((it.level - 1).coerceIn(0, 4)) + it.title) to it.offset }'
if old not in s: raise SystemExit("v61: cannot find structured chapter labels")
s = s.replace(old, new, 1)
p.write_text(s, encoding="utf-8")

print("v61: display embedded FB2 cover thumbnails in the searchable library and indent nested sections in the TOC.")
