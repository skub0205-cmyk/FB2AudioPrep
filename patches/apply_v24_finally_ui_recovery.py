from pathlib import Path

main = Path("app/src/main/java/ru/fbaudioprep/MainActivity.kt")
s = main.read_text(encoding="utf-8")
start = s.find("    private fun analyzeDialogues(allowWithoutModel: Boolean = false) {")
end = s.find("    private fun normalizeCharacterName", start)
if start < 0 or end < 0:
    raise SystemExit("v24: cannot locate TeraRole analysis method")
method = s[start:end]
if "v24-finally-ui-recovery" in method:
    print("v24 already applied")
else:
    close = method.rfind("        }.start()")
    if close < 0 or "val analysisProgress" not in method:
        raise SystemExit("v24: cannot locate worker closure or progress dialog")
    recovery = """        finally {
            // Always release the analysis UI after the worker has actually exited.
            // Posted after success/error callbacks, so it cannot dismiss the dialog early.
            runOnUiThread {
                if (token == dialogueAnalysisToken) {
                    if (analysisProgress.isShowing) analysisProgress.dismiss()
                    dialogueAnalysisInProgress = false
                    dialogueButton.isEnabled = true
                    characterButton.isEnabled = true
                }
            }
        }
        // v24-finally-ui-recovery
"""
    method = method[:close] + recovery + method[close + len("        }.start()"):]
    s = s[:start] + method + s[end:]
    main.write_text(s, encoding="utf-8")
    print("v24: guaranteed UI cleanup in worker finally")

gradle = Path("app/build.gradle.kts")
g = gradle.read_text(encoding="utf-8")
import re
m = re.search(r'versionCode\s*=\s*(\d+)\s*;\s*versionName\s*=\s*"([^"]+)"', g)
if not m:
    raise SystemExit("v24: cannot locate app version")
if m.group(2) != "2.1.3":
    g = g[:m.start()] + f'versionCode = {int(m.group(1)) + 1}; versionName = "2.1.3"' + g[m.end():]
    gradle.write_text(g, encoding="utf-8")
