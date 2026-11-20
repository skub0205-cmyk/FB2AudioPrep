from pathlib import Path

path = Path("app/src/main/java/ru/fbaudioprep/TeraTtsV2SpeechSegmenter.kt")
if not path.exists():
    raise SystemExit("v50: speech segmenter not found")
source = path.read_text(encoding="utf-8")

start = source.find("    private val femaleCue = Regex(")
end_marker = "    )"
male_start = source.find("    private val maleCue = Regex(", start)
if start < 0 or male_start < 0:
    raise SystemExit("v50: voice cue declarations not found")
male_end = source.find(end_marker, male_start)
if male_end < 0:
    raise SystemExit("v50: male voice cue declaration is malformed")
male_end += len(end_marker)

replacement = r'''    // Explicit descriptions may contain intervening words: "приветливый женский голос".
    private val femaleCue = Regex(
        """(?iu)(?:женск\p{L}*(?:\s+\p{L}+){0,3}\s+голос|голос(?:\s+\p{L}+){0,3}\s+женщин\p{L}*|женщин\p{L}*(?:\s+\p{L}+){0,3}\s+голос)"""
    )
    private val maleCue = Regex(
        """(?iu)(?:мужск\p{L}*(?:\s+\p{L}+){0,3}\s+голос|голос(?:\s+\p{L}+){0,3}\s+мужчин\p{L}*|мужчин\p{L}*(?:\s+\p{L}+){0,3}\s+голос)"""
    )'''
source = source[:start] + replacement + source[male_end:]
path.write_text(source, encoding="utf-8")

test_path = Path("app/src/test/java/ru/fbaudioprep/TeraTtsV2SpeechSegmenterTest.kt")
if test_path.exists():
    tests = test_path.read_text(encoding="utf-8")
    if "приветливый женский голос" not in tests or "раздражённый женский голос" not in tests:
        raise SystemExit("v50: Nico regression fixtures are missing")
print("v50: widened explicit gender voice cues using Unicode-aware matching.")
