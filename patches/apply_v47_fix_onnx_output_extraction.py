from pathlib import Path

p = Path("app/src/main/java/ru/fbaudioprep/TeraTtsV2OnnxEngine.kt")
s = p.read_text(encoding="utf-8")

old = '''            session.run(inputs).use { result ->
                val tensor = result.get(0).value as? OnnxTensor ?: error("ONNX output is not a tensor")
                val shape = (tensor.info as TensorInfo).shape
                val buffer = tensor.floatBuffer
                val values = FloatArray(buffer.remaining())
                buffer.get(values)
                return TensorData(shape, values)
            }
'''
new = '''            session.run(inputs).use { result ->
                // OrtSession.Result is a Map-like collection of named OnnxValue objects.
                // Calling get(0).value can unwrap the underlying Java value (FloatArray /
                // nested array) instead of returning the OnnxTensor wrapper on some
                // ONNX Runtime Android versions. Read the OnnxValue from values directly.
                val output = result.values.firstOrNull()
                    ?: error("ONNX-модель не вернула выходных данных")
                val tensor = output as? OnnxTensor ?: error(
                    "ONNX output is not a tensor: " + output.javaClass.name +
                        "; outputs=" + result.keys.joinToString()
                )
                val shape = (tensor.info as TensorInfo).shape
                val buffer = tensor.floatBuffer
                val values = FloatArray(buffer.remaining())
                buffer.get(values)
                return TensorData(shape, values)
            }
'''
assert old in s, "v47: expected runFloat output extraction block not found"
s = s.replace(old, new, 1)
p.write_text(s, encoding="utf-8")
print("v47: read ONNX output as OnnxValue from Result.values before casting to OnnxTensor.")
