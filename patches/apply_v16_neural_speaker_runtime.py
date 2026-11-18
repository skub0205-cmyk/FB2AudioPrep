from pathlib import Path
import re

root = Path("app/src/main/java/ru/fbaudioprep")
root.mkdir(parents=True, exist_ok=True)
target = root / "NeuralSpeakerRanker.kt"
target.write_text(r'''package ru.fbaudioprep

import ai.djl.huggingface.tokenizers.HuggingFaceTokenizer
import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession
import java.io.Closeable
import java.io.File
import java.nio.LongBuffer
import kotlin.math.exp

data class NeuralSpeakerCandidate(
    val name: String,
    val aliases: List<String> = emptyList(),
    val gender: String = "unknown"
)

data class NeuralSpeakerScore(
    val candidate: NeuralSpeakerCandidate,
    val rawScore: Float,
    val probability: Float
)

/**
 * Offline ONNX candidate ranker.
 *
 * The ONNX model and tokenizer.json must come from the same verified model pack
 * that was used during training. Call rank() from a background dispatcher.
 */
class NeuralSpeakerRanker(
    modelFile: File,
    tokenizerFile: File,
    private val maxTokens: Int = 512,
    private val padTokenId: Long = 50283L
) : Closeable {
    private val environment = OrtEnvironment.getEnvironment()
    private val options = OrtSession.SessionOptions()
    private val session: OrtSession
    private val tokenizer: HuggingFaceTokenizer
    @Volatile private var closed = false

    init {
        require(modelFile.isFile) { "Speaker ONNX model is missing" }
        require(tokenizerFile.isFile) { "Speaker tokenizer.json is missing" }
        require(maxTokens in 32..2048) { "Invalid max token length" }
        options.setIntraOpNumThreads(2)
        session = environment.createSession(modelFile.absolutePath, options)
        tokenizer = HuggingFaceTokenizer.newInstance(tokenizerFile.toPath())
    }

    @Synchronized
    fun rank(
        quote: String,
        contextBefore: String,
        contextAfter: String,
        candidates: List<NeuralSpeakerCandidate>
    ): List<NeuralSpeakerScore> {
        check(!closed) { "Speaker ranker is closed" }
        if (candidates.isEmpty()) return emptyList()
        require(quote.isNotBlank()) { "Quote must not be blank" }

        val encodings = candidates.map { candidate ->
            val aliases = candidate.aliases.joinToString(", ")
            val input = buildString {
                append("[QUOTE] ").append(quote)
                append(" [LEFT CONTEXT] ").append(contextBefore)
                append(" [RIGHT CONTEXT] ").append(contextAfter)
                append(" [CANDIDATE] ").append(candidate.name)
                append(" [ALIASES] ").append(aliases)
                append(" [CANDIDATE GENDER] ").append(candidate.gender)
            }
            tokenizer.encode(input)
        }

        val sequenceLength = encodings.maxOf { it.ids.size }.coerceAtMost(maxTokens)
        val batchSize = candidates.size
        val flattenedIds = LongArray(batchSize * sequenceLength) { padTokenId }
        val flattenedMask = LongArray(batchSize * sequenceLength)

        for (row in encodings.indices) {
            val ids = encodings[row].ids
            val mask = encodings[row].attentionMask
            val count = minOf(sequenceLength, ids.size)
            val offset = row * sequenceLength
            for (column in 0 until count) {
                flattenedIds[offset + column] = ids[column]
                flattenedMask[offset + column] = mask[column]
            }
        }

        val shape = longArrayOf(batchSize.toLong(), sequenceLength.toLong())
        OnnxTensor.createTensor(environment, LongBuffer.wrap(flattenedIds), shape).use { idsTensor ->
            OnnxTensor.createTensor(environment, LongBuffer.wrap(flattenedMask), shape).use { maskTensor ->
                session.run(mapOf(
                    "input_ids" to idsTensor,
                    "attention_mask" to maskTensor
                )).use { result ->
                    val logits = (result[0] as OnnxTensor).floatBuffer
                    val rawScores = FloatArray(batchSize) { index -> logits.get(index) }
                    val maxScore = rawScores.maxOrNull() ?: 0f
                    val exponentials = rawScores.map { exp((it - maxScore).toDouble()) }
                    val denominator = exponentials.sum().coerceAtLeast(1e-12)
                    return candidates.indices.map { index ->
                        NeuralSpeakerScore(
                            candidate = candidates[index],
                            rawScore = rawScores[index],
                            probability = (exponentials[index] / denominator).toFloat()
                        )
                    }.sortedByDescending { it.probability }
                }
            }
        }
    }

    override fun close() {
        if (closed) return
        closed = true
        tokenizer.close()
        session.close()
        options.close()
    }
}
''', encoding="utf-8")

gradle = Path("app/build.gradle.kts")
g = gradle.read_text(encoding="utf-8")
dependencies = '''
dependencies {
    implementation("com.microsoft.onnxruntime:onnxruntime-android:1.20.0")
    implementation("ai.djl.huggingface:tokenizers:0.30.0")
}
'''
if "onnxruntime-android" not in g:
    g += "\n" + dependencies
g, n = re.subn(r'versionCode\s*=\s*(\d+);\s*versionName\s*=\s*"2\.0\.7"',
               lambda m: f'versionCode = {int(m.group(1)) + 1}; versionName = "2.0.8"', g, count=1)
if n != 1:
    raise SystemExit("Could not bump app version to 2.0.8")
gradle.write_text(g, encoding="utf-8")
print("Added offline ONNX speaker ranker and Android tokenizer/runtime dependencies.")
