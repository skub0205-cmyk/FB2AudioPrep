from pathlib import Path

targets = [
    Path("app/src/main/java/ru/fbaudioprep/DialogueAnalyzer.kt"),
    Path("app/src/main/java/ru/fbaudioprep/DialogueCorrectionStore.kt"),
    Path("app/src/main/java/ru/fbaudioprep/AccentEngine.kt"),
]
for path in targets:
    print("\\n" + "=" * 24 + " " + str(path) + " " + "=" * 24)
    if not path.exists():
        print("MISSING")
        continue
    lines = path.read_text(encoding="utf-8").splitlines()
    print(f"LINES={len(lines)}")
    limit = 900 if "DialogueAnalyzer" in path.name else 500
    for number, line in enumerate(lines[:limit], 1):
        print(f"{number:04d}: {line}")
    if len(lines) > limit:
        print(f"... TRUNCATED after {limit} lines")
