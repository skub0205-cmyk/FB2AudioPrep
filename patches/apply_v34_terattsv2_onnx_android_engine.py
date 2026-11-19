from pathlib import Path

root = Path("app/src/main/java/ru/fbaudioprep")
root.mkdir(parents=True, exist_ok=True)
target = root / "TeraTtsV2OnnxEngine.kt"
target.write_text(r'''package ru.fbaudioprep

import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioTrack
import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession
import ai.onnxruntime.TensorInfo
import org.json.JSONArray
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.text.Normalizer
import java.util.Random
import java.util.concurrent.atomic.AtomicBoolean
import kotlin.math.PI
import kotlin.math.ceil
import kotlin.math.cos
import kotlin.math.ln
import kotlin.math.max
import kotlin.math.min
import kotlin.math.sqrt

/**
 * Native Android ONNX adapter for TeraTTSv2.
 * Release layout: ONNX model files, voice style arrays, and unicode_indexer.json.
 * Load and synthesize on a worker thread. One instance reuses model sessions.
 */
class TeraTtsV2OnnxEngine(private val cpuThreads: Int = 4) : AutoCloseable {
    companion object {
        const val SAMPLE_RATE = 44_100
        private const val FRAME_SAMPLES = 3_072
        private const val CONTEXT_FRAMES = 20
        private const val STREAM_FRAMES = 16
        const val ENGINE_ID = "teratts_v2_onnx"
        val RUSSIAN_VOICES = listOf("ru_f1", "ru_m5", "ru_f2", "ru_m1")
    }

    data class Status(val ready: Boolean, val voices: List<String>, val message: String)
    private data class TensorData(val shape: LongArray, val values: FloatArray)

    private val env = OrtEnvironment.getEnvironment()
    private var encoder: OrtSession? = null
    private var duration: OrtSession? = null
    private var diffusion: OrtSession? = null
    private var vocoder: OrtSession? = null
    private var release: File? = null
    private var tokenTable: IntArray? = null
    private var track: AudioTrack? = null
    private val cancelled = AtomicBoolean(false)
    @Volatile private var isPlaying = false

    @Synchronized
    fun load(directory: File): Status {
        closeSessions()
        require(directory.isDirectory) { "Папка TeraTTSv2 не найдена" }
        val models = File(directory, "models")
        val files = listOf(
            "text_encoder.onnx", "duration_predictor.onnx",
            "sampler_distilled_cfg3_8step.onnx", "vocoder.onnx"
        )
        val missing = files.filter { !File(models, it).isFile }
        require(missing.isEmpty()) { "Не найдены ONNX-файлы: " + missing.joinToString() }
        val voices = RUSSIAN_VOICES.filter { voice ->
            File(directory, "styles/" + voice + "/style_ttl.npy").isFile &&
                File(directory, "styles/" + voice + "/style_dp.npy").isFile
        }
        require(voices.isNotEmpty()) { "Не найдены русские профили голосов" }
        val indexFile = File(directory, "unicode_indexer.json")
        require(indexFile.isFile) { "Не найдена таблица unicode_indexer.json" }
        val json = JSONArray(indexFile.readText(Charsets.UTF_8))
        require(json.length() == 65_536) { "Таблица Unicode должна содержать 65 536 элементов" }
        val table = IntArray(65_536) { json.getInt(it) }

        val options = OrtSession.SessionOptions()
        options.setIntraOpNumThreads(max(1, cpuThreads))
        try {
            encoder = env.createSession(File(models, files[0]).absolutePath, options)
            duration = env.createSession(File(models, files[1]).absolutePath, options)
            diffusion = env.createSession(File(models, files[2]).absolutePath, options)
            vocoder = env.createSession(File(models, files[3]).absolutePath, options)
        } catch (error: Throwable) {
            closeSessions()
            throw error
        } finally {
            options.close()
        }
        release = directory
        tokenTable = table
        return Status(true, voices, "TeraTTSv2 готов к офлайн-синтезу")
    }

    fun status(): Status {
        val base = release
        val voices = if (base == null) emptyList() else RUSSIAN_VOICES.filter { voice ->
            File(base, "styles/" + voice + "/style_ttl.npy").isFile &&
                File(base, "styles/" + voice + "/style_dp.npy").isFile
        }
        val ready = encoder != null && voices.isNotEmpty()
        return Status(ready, voices, if (ready) "Модель загружена" else "Модель не установлена")
    }

    /**
     * Synthesizes one tagged Russian segment and streams decoded PCM to Android AudioTrack.
     * Diffusion latent is generated first; vocoder output is then streamed in bounded chunks.
     */
    @Synchronized
    fun synthesizeAndPlay(
        taggedText: String,
        voice: String = "ru_f1",
        durationScale: Float = 1f,
        seed: Long = 1234L,
        onStarted: (() -> Unit)? = null
    ) {
        check(!isPlaying) { "Озвучивание уже выполняется" }
        require(durationScale > 0f && durationScale.isFinite())
        val base = release ?: error("Сначала установите модель TeraTTSv2")
        val textEncoder = encoder ?: error("Текстовый энкодер не загружен")
        val durationModel = duration ?: error("Предсказатель длительности не загружен")
        val sampler = diffusion ?: error("Генератор речи не загружен")
        val vocoderModel = vocoder ?: error("Вокодер не загружен")
        val styleDirectory = File(base, "styles/" + voice)
        require(styleDirectory.isDirectory) { "Неизвестный голос: " + voice }
        cancelled.set(false)
        isPlaying = true
        try {
            val prepared = TeraTtsV2Text.prepare(taggedText, tokenTable!!)
            val styleTtl = NpyStyle.read(File(styleDirectory, "style_ttl.npy"), longArrayOf(1, 50, 256))
            val styleDp = NpyStyle.read(File(styleDirectory, "style_dp.npy"), longArrayOf(1, 8, 16))
            val textMask = FloatArray(prepared.ids.size) { 1f }
            val durationMask = FloatArray(prepared.durationIds.size) { 1f }

            val embedding = runFloat(textEncoder, mapOf(
                "text_ids" to longTensor(prepared.ids, longArrayOf(1, prepared.ids.size.toLong())),
                "style_ttl" to floatTensor(styleTtl.values, styleTtl.shape),
                "text_mask" to floatTensor(textMask, longArrayOf(1, 1, textMask.size.toLong()))
            ))
            val rawDuration = runFloat(durationModel, mapOf(
                "text_ids" to longTensor(prepared.durationIds, longArrayOf(1, prepared.durationIds.size.toLong())),
                "style_dp" to floatTensor(styleDp.values, styleDp.shape),
                "text_mask" to floatTensor(durationMask, longArrayOf(1, 1, durationMask.size.toLong()))
            )).values.firstOrNull()?.toDouble() ?: error("Нет результата предсказания длительности")
            val seconds = rawDuration * durationScale.toDouble() / 1.05
            require(seconds.isFinite() && seconds > 0.0) { "Некорректная длительность синтеза" }
            val latentFrames = max(1, ceil(seconds * SAMPLE_RATE / FRAME_SAMPLES).toInt())
            val latent = gaussian(144 * latentFrames, seed)
            val latentMask = FloatArray(latentFrames) { 1f }
            val generated = runFloat(sampler, mapOf(
                "initial_latent" to floatTensor(latent, longArrayOf(1, 144, latentFrames.toLong())),
                "text_emb" to floatTensor(embedding.values, embedding.shape),
                "style_ttl" to floatTensor(styleTtl.values, styleTtl.shape),
                "latent_mask" to floatTensor(latentMask, longArrayOf(1, 1, latentFrames.toLong())),
                "text_mask" to floatTensor(textMask, longArrayOf(1, 1, textMask.size.toLong())),
                "guidance" to floatTensor(floatArrayOf(3f), longArrayOf(1))
            ))
            val frames = generated.shape.last().toInt()
            require(frames > 0 && generated.values.size == 144 * frames) {
                "Генератор вернул неверный размер латентного аудио"
            }

            val output = createTrack()
            track = output
            output.play()
            onStarted?.invoke()
            val maxSamples = (seconds * SAMPLE_RATE).toInt()
            var emitted = 0
            var start = 0
            while (start < frames && !cancelled.get()) {
                val end = min(start + STREAM_FRAMES, frames)
                val inputStart = max(0, start - CONTEXT_FRAMES)
                val inputFrames = end - inputStart
                val chunk = sliceLatent(generated.values, frames, inputStart, end)
                val decoded = runFloat(vocoderModel, mapOf(
                    "latent" to floatTensor(chunk, longArrayOf(1, 144, inputFrames.toLong()))
                )).values
                val discard = (start - inputStart) * FRAME_SAMPLES
                val expected = (end - start) * FRAME_SAMPLES
                require(decoded.size - discard >= expected) { "Вокодер вернул неполный аудиоблок" }
                val count = min(expected, maxSamples - emitted)
                if (count > 0) {
                    val pcm = decoded.copyOfRange(discard, discard + count)
                    val written = output.write(pcm, 0, pcm.size, AudioTrack.WRITE_BLOCKING)
                    check(written >= 0) { "Ошибка AudioTrack: " + written }
                    emitted += count
                }
                start = end
            }
            if (cancelled.get()) {
                output.pause()
                output.flush()
            }
            try { if (output.playState == AudioTrack.PLAYSTATE_PLAYING) output.stop() } catch (_: Throwable) {}
        } finally {
            try { track?.release() } catch (_: Throwable) {}
            track = null
            isPlaying = false
        }
    }

    fun cancelPlayback() {
        cancelled.set(true)
        try { track?.pause(); track?.flush() } catch (_: Throwable) {}
    }

    private fun createTrack(): AudioTrack {
        val minimum = AudioTrack.getMinBufferSize(
            SAMPLE_RATE, AudioFormat.CHANNEL_OUT_MONO, AudioFormat.ENCODING_PCM_FLOAT
        )
        check(minimum > 0) { "PCM float 44,1 кГц не поддерживается" }
        return AudioTrack.Builder()
            .setAudioAttributes(AudioAttributes.Builder()
                .setUsage(AudioAttributes.USAGE_MEDIA)
                .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build())
            .setAudioFormat(AudioFormat.Builder()
                .setEncoding(AudioFormat.ENCODING_PCM_FLOAT)
                .setSampleRate(SAMPLE_RATE)
                .setChannelMask(AudioFormat.CHANNEL_OUT_MONO).build())
            .setBufferSizeInBytes(max(minimum * 4, SAMPLE_RATE * 2))
            .setTransferMode(AudioTrack.MODE_STREAM)
            .build()
    }

    private fun runFloat(session: OrtSession, inputs: Map<String, OnnxTensor>): TensorData {
        try {
            session.run(inputs).use { result ->
                val tensor = result.get(0).value as? OnnxTensor ?: error("ONNX output is not a tensor")
                val shape = (tensor.info as TensorInfo).shape
                val buffer = tensor.floatBuffer
                val values = FloatArray(buffer.remaining())
                buffer.get(values)
                return TensorData(shape, values)
            }
        } finally {
            inputs.values.forEach { it.close() }
        }
    }

    private fun floatTensor(values: FloatArray, shape: LongArray): OnnxTensor {
        val buffer = ByteBuffer.allocateDirect(values.size * 4)
            .order(ByteOrder.nativeOrder()).asFloatBuffer()
        buffer.put(values).flip()
        return OnnxTensor.createTensor(env, buffer, shape)
    }

    private fun longTensor(values: LongArray, shape: LongArray): OnnxTensor {
        val buffer = ByteBuffer.allocateDirect(values.size * 8)
            .order(ByteOrder.nativeOrder()).asLongBuffer()
        buffer.put(values).flip()
        return OnnxTensor.createTensor(env, buffer, shape)
    }

    private fun gaussian(size: Int, seed: Long): FloatArray {
        val random = Random(seed)
        val result = FloatArray(size)
        var index = 0
        while (index < size) {
            val u1 = max(random.nextDouble(), 1e-12)
            val u2 = random.nextDouble()
            val radius = sqrt(-2.0 * ln(u1))
            val angle = 2.0 * PI * u2
            result[index++] = (radius * cos(angle)).toFloat()
            if (index < size) result[index++] = (radius * kotlin.math.sin(angle)).toFloat()
        }
        return result
    }

    private fun sliceLatent(source: FloatArray, totalFrames: Int, start: Int, end: Int): FloatArray {
        val count = end - start
        val result = FloatArray(144 * count)
        for (channel in 0 until 144) {
            source.copyInto(result, channel * count, channel * totalFrames + start, channel * totalFrames + end)
        }
        return result
    }

    @Synchronized
    private fun closeSessions() {
        listOf(encoder, duration, diffusion, vocoder).forEach { try { it?.close() } catch (_: Throwable) {} }
        encoder = null; duration = null; diffusion = null; vocoder = null
        tokenTable = null; release = null
    }

    override fun close() {
        cancelPlayback()
        try { track?.release() } catch (_: Throwable) {}
        track = null
        closeSessions()
    }
}

object TeraTtsV2Text {
    data class Prepared(val ids: LongArray, val durationIds: LongArray)

    fun prepare(tagged: String, unicodeTable: IntArray): Prepared {
        require(unicodeTable.size == 65_536)
        val text = tagged.trim()
        require(text.startsWith("<ru>") && text.endsWith("</ru>")) {
            "Оберните русский текст в <ru>...</ru>"
        }
        val body = text.substring(4, text.length - 5)
        require(body.isNotBlank()) { "Пустой текст" }
        val spaced = body
            .replace(Regex("([,.!?;:…])(?=[^\\s])"), "$1 ")
            .replace(Regex("(?<=\\d)(?=[A-Za-zА-Яа-яЁё])"), " ")
        val normalized = Normalizer.normalize(spaced, Normalizer.Form.NFKD)
        val all = ArrayList<Long>()
        val withoutStress = ArrayList<Long>()
        normalized.forEach { ch ->
            val code = ch.code
            val token = if (code in 0..65535) unicodeTable[code] else -1
            if (token >= 0) {
                all += token.toLong()
                if (ch != '+') withoutStress += token.toLong()
            }
        }
        require(all.isNotEmpty() && withoutStress.isNotEmpty()) { "Нет символов словаря TeraTTSv2" }
        return Prepared(all.toLongArray(), withoutStress.toLongArray())
    }
}

private object NpyStyle {
    data class Data(val shape: LongArray, val values: FloatArray)

    fun read(file: File, expected: LongArray): Data {
        require(file.isFile) { "Нет файла стиля " + file.name }
        val bytes = file.readBytes()
        require(bytes.size > 10 && bytes[0] == 0x93.toByte()) { "Повреждённый NPY " + file.name }
        val version = bytes[6].toInt() and 0xff
        val headerLength: Int
        val offset: Int
        if (version == 1) {
            headerLength = (bytes[8].toInt() and 255) or ((bytes[9].toInt() and 255) shl 8)
            offset = 10 + headerLength
        } else {
            require(bytes.size >= 12)
            headerLength = ByteBuffer.wrap(bytes, 8, 4).order(ByteOrder.LITTLE_ENDIAN).int
            offset = 12 + headerLength
        }
        require(offset in 1 until bytes.size)
        val headerStart = if (version == 1) 10 else 12
        val header = String(bytes, headerStart, headerLength, Charsets.US_ASCII)
        require(header.contains("<f4") || header.contains("|f4") || header.contains("=f4")) {
            "Файл стиля должен быть float32"
        }
        val shapeText = Regex("'shape'\\s*:\\s*\\(([^)]*)\\)").find(header)?.groupValues?.get(1)
            ?: error("Не найдена форма массива NPY")
        val shape = shapeText.split(",").mapNotNull {
            it.trim().takeIf { value -> value.isNotEmpty() }?.toLong()
        }.toLongArray()
        require(shape.contentEquals(expected)) { "Неверная форма массива стиля: " + shape.contentToString() }
        val count = expected.fold(1L) { a, b -> a * b }.toInt()
        require(offset + count * 4 <= bytes.size) { "Обрезан файл стиля" }
        val buffer = ByteBuffer.wrap(bytes, offset, count * 4)
            .order(ByteOrder.LITTLE_ENDIAN).asFloatBuffer()
        val values = FloatArray(count)
        buffer.get(values)
        return Data(shape, values)
    }
}
''', encoding="utf-8")

gradle = Path("app/build.gradle.kts")
s = gradle.read_text(encoding="utf-8")
if "onnxruntime-android" not in s:
    s += '\n\ndependencies {\n    implementation("ai.onnxruntime:onnxruntime-android:1.32.0")\n}\n'
    gradle.write_text(s, encoding="utf-8")
print("Added TeraTTSv2 ONNX Runtime inference and AudioTrack streaming adapter.")
