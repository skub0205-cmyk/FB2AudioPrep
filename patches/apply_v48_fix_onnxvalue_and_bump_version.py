from pathlib import Path

engine = Path("app/src/main/java/ru/fbaudioprep/TeraTtsV2OnnxEngine.kt")
s = engine.read_text(encoding="utf-8")

old = '''                val output = result.values.firstOrNull()
                    ?: error("ONNX-модель не вернула выходных данных")
                val tensor = output as? OnnxTensor ?: error(
                    "ONNX output is not a tensor: " + output.javaClass.name +
                        "; outputs=" + result.keys.joinToString()
                )
'''
new = '''                // OrtSession.Result.get(index) already returns OnnxValue.
                // Do NOT access its .value property: that unwraps the tensor into
                // a Java array, which caused the reported "output is not a tensor".
                check(result.size() > 0) { "ONNX-модель не вернула выходных данных" }
                val output = result.get(0)
                val tensor = output as? OnnxTensor ?: error(
                    "ONNX output is not a tensor: type=" + output.type +
                        ", class=" + output.javaClass.name +
                        ", sessionOutputs=" + session.outputInfo.keys.joinToString()
                )
'''
assert old in s, "v48: expected v47 output extraction block not found"
s = s.replace(old, new, 1)
engine.write_text(s, encoding="utf-8")

gradle = Path("app/build.gradle.kts")
if not gradle.exists():
    gradle = Path("build.gradle.kts")
g = gradle.read_text(encoding="utf-8")
assert 'versionCode = 37; versionName = "2.1.5"' in g, "v48: version config anchor not found"
g = g.replace('versionCode = 37; versionName = "2.1.5"', 'versionCode = 38; versionName = "2.1.6"', 1)
gradle.write_text(g, encoding="utf-8")
print("v48: use OrtSession.Result.get(0) as OnnxValue (no .value unwrap); bump app version to 2.1.6.")
