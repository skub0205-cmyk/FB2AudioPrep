from pathlib import Path
import re

path = Path("app/src/main/java/ru/fbaudioprep/TeraTtsV2SpeechSegmenter.kt")
if not path.exists():
    raise SystemExit("v50: speech segmenter not found")

source = path.read_text(encoding="utf-8")
old = '''    private val femaleCue = Regex(
        """(?iu)(?:женск\\w*\\s+голос|голос\\w*\\s+женщин\\w*|женщин\\w*\\s+голос)"""
    )
    private val maleCue = Regex(
        """(?iu)(?:мужск\\w*\\s+голос|голос\\w*\\s+мужчин\\w*|мужчин\\w*\\s+голос)"""
    )'''
new = '''    // Voice descriptions often contain intervening adverbs/adjectives:
    // "раздался в голове приветливый женский голос",
    // "раздался снаружи раздражённый женский голос".
    private val femaleCue = Regex(
        """(?iu)(?:женск\\w*(?:\\s+\\p{L}+){0,3}\\s+голос|голос(?:\\s+\\p{L}+){0,3}\\s+женщин\\w*|женщин\\w*(?:\\s+\\p{L}+){0,3}\\s+голос)"""
    )
    private val maleCue = Regex(
        """(?iu)(?:мужск\\w*(?:\\s+\\p{L}+){0,3}\\s+голос|голос(?:\\s+\\p{L}+){0,3}\\s+мужчин\\w*|мужчин\\w*(?:\\s+\\p{L}+){0,3}\\s+голос)"""
    )'''
if old not in source:
    raise SystemExit("v50: expected voice cue patterns not found; refusing to overwrite")
source = source.replace(old, new, 1)
path.write_text(source, encoding="utf-8")

# Keep the regression tests explicit about descriptions separated by several words.
test_path = Path("app/src/test/java/ru/fbaudioprep/TeraTtsV2SpeechSegmenterTest.kt")
if test_path.exists():
    tests = test_path.read_text(encoding="utf-8")
    if "приветливый женский голос" not in tests or "раздражённый женский голос" not in tests:
        raise SystemExit("v50: expected Nico regression fixtures missing")
print("v50: recognize explicit gendered voice descriptions with intervening descriptive words.")
