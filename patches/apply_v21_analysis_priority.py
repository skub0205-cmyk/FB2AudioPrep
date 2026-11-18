from pathlib import Path

p = Path("app/src/main/java/ru/fbaudioprep/teratts/TeraRoleEngine.kt")
s = p.read_text(encoding="utf-8")

old = """compute = true, threads = 2, stop = stop
"""
new = """compute = true, threads = 2, stop = stop, low = false
"""
if new in s:
    print("v21 already applied")
elif old in s:
    s = s.replace(old, new, 1)
    p.write_text(s, encoding="utf-8")
    print("v21: manual book analysis now runs at normal CPU priority; background TTS callers retain low priority")
else:
    raise SystemExit("v21: expected RoleModel.guesses call was not found; refusing to guess")

# Keep a small source-level regression check so a future refactor cannot silently restore
# the background priority for explicit, user-started whole-book analysis.
s = p.read_text(encoding="utf-8")
assert "compute = true, threads = 2, stop = stop, low = false" in s
