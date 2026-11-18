from pathlib import Path

p = Path("app/src/main/java/ru/fbaudioprep/teratts/TeraRoleEngine.kt")
s = p.read_text(encoding="utf-8")

# v20 adds progress callbacks after the original stop argument. Insert the named
# low=false argument after the callback block; do not alter background TTS callers.
needle = '''                onWindow = { done, total ->
                    val percent = 10 + (80f * done / total.coerceAtLeast(1)).toInt()
                    onProgress(percent, "Проверено фрагментов ИИ: $done из $total")
                }
            ).orEmpty()'''
replacement = '''                onWindow = { done, total ->
                    val percent = 10 + (80f * done / total.coerceAtLeast(1)).toInt()
                    onProgress(percent, "Проверено фрагментов ИИ: $done из $total")
                },
                low = false
            ).orEmpty()'''

if replacement in s:
    print("v21 already applied")
elif needle in s:
    s = s.replace(needle, replacement, 1)
    p.write_text(s, encoding="utf-8")
    print("v21: explicit whole-book analysis now runs at normal CPU priority")
else:
    raise SystemExit("v21: expected progress-enabled RoleModel.guesses call was not found")

s = p.read_text(encoding="utf-8")
assert "low = false" in s
