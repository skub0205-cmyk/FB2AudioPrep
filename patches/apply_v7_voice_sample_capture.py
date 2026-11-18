from pathlib import Path

root = Path("app/src/main/java/ru/fbaudioprep")
root.mkdir(parents=True, exist_ok=True)
(root / "VoiceSampleCapture.kt").write_text(r'''package ru.fbaudioprep

import android.content.Context
import android.content.Intent
import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioPlaybackCaptureConfiguration
import android.media.AudioRecord
import android.media.MediaRecorder
import android.media.projection.MediaProjection
import android.media.projection.MediaProjectionManager
import android.os.Build
import java.io.File
import java.io.RandomAccessFile
import java.util.concurrent.atomic.AtomicBoolean

/**
 * Records a short PCM16 mono WAV sample from the microphone or permitted app playback.
 *
 * Playback capture requires Android 10+, the system MediaProjection consent dialog,
 * and a source app that allows capture. This helper intentionally does not bypass
 * protected audio or source-app capture policy.
 */
class VoiceSampleCapture(
    private val sampleRateHz: Int = 16_000
) {
    private var audioRecord: AudioRecord? = null
    private var outputFile: File? = null
    private var writerThread: Thread? = null
    private val running = AtomicBoolean(false)
    @Volatile private var recordingFailure: Throwable? = null

    companion object {
        const val CHANNEL_COUNT = 1
        const val BITS_PER_SAMPLE = 16

        fun createPlaybackCaptureIntent(context: Context): Intent {
            val manager = context.getSystemService(Context.MEDIA_PROJECTION_SERVICE)
                    as MediaProjectionManager
            return manager.createScreenCaptureIntent()
        }
    }

    @Synchronized
    fun startMicrophone(output: File) {
        check(Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            "Microphone recording requires Android 6.0 or newer"
        }
        val minBuffer = AudioRecord.getMinBufferSize(
            sampleRateHz,
            AudioFormat.CHANNEL_IN_MONO,
            AudioFormat.ENCODING_PCM_16BIT
        )
        check(minBuffer > 0) { "Unsupported microphone audio format" }
        val recorder = AudioRecord(
            MediaRecorder.AudioSource.MIC,
            sampleRateHz,
            AudioFormat.CHANNEL_IN_MONO,
            AudioFormat.ENCODING_PCM_16BIT,
            maxOf(minBuffer * 2, sampleRateHz)
        )
        startInternal(recorder, output)
    }

    @Synchronized
    fun startPlaybackCapture(projection: MediaProjection, output: File) {
        check(Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            "System playback capture requires Android 10 or newer"
        }
        val format = AudioFormat.Builder()
            .setEncoding(AudioFormat.ENCODING_PCM_16BIT)
            .setSampleRate(sampleRateHz)
            .setChannelMask(AudioFormat.CHANNEL_IN_MONO)
            .build()

        val config = AudioPlaybackCaptureConfiguration.Builder(projection)
            .addMatchingUsage(AudioAttributes.USAGE_MEDIA)
            .addMatchingUsage(AudioAttributes.USAGE_GAME)
            .addMatchingUsage(AudioAttributes.USAGE_UNKNOWN)
            .build()

        val minBuffer = AudioRecord.getMinBufferSize(
            sampleRateHz,
            AudioFormat.CHANNEL_IN_MONO,
            AudioFormat.ENCODING_PCM_16BIT
        )
        check(minBuffer > 0) { "Unsupported playback capture audio format" }

        val recorder = AudioRecord.Builder()
            .setAudioFormat(format)
            .setBufferSizeInBytes(maxOf(minBuffer * 2, sampleRateHz))
            .setAudioPlaybackCaptureConfig(config)
            .build()

        startInternal(recorder, output)
    }

    @Synchronized
    private fun startInternal(recorder: AudioRecord, output: File) {
        check(!running.get()) { "A voice sample is already being recorded" }
        output.parentFile?.mkdirs()
        check(!output.exists() || output.delete()) { "Cannot replace output sample" }

        try {
            RandomAccessFile(output, "rw").use { file ->
                file.setLength(0)
                file.write(ByteArray(44))
            }
            recorder.startRecording()
            check(recorder.recordingState == AudioRecord.RECORDSTATE_RECORDING) {
                "Audio recording did not start"
            }
            audioRecord = recorder
            outputFile = output
            recordingFailure = null
            running.set(true)

            writerThread = Thread({
                try {
                    RandomAccessFile(output, "rw").use { file ->
                        file.seek(44)
                        val buffer = ByteArray(4096)
                        while (running.get()) {
                            val count = recorder.read(buffer, 0, buffer.size)
                            if (count > 0) file.write(buffer, 0, count)
                            else if (count < 0) throw IllegalStateException(
                                "AudioRecord read failed: $count"
                            )
                        }
                        val dataSize = (file.length() - 44L).toInt()
                        writeWavHeader(file, dataSize, sampleRateHz)
                    }
                } catch (error: Throwable) {
                    recordingFailure = error
                }
            }, "VoiceSampleWriter").apply {
                isDaemon = true
                start()
            }
        } catch (error: Throwable) {
            running.set(false)
            try { recorder.stop() } catch (_: Throwable) { }
            recorder.release()
            audioRecord = null
            throw error
        }
    }

    @Synchronized
    fun stop(): File {
        check(running.get()) { "No voice sample is being recorded" }
        running.set(false)
        val recorder = audioRecord
        try { recorder?.stop() } catch (_: Throwable) { }
        writerThread?.join(2_000)
        recorder?.release()
        audioRecord = null
        writerThread = null

        recordingFailure?.let { throw IllegalStateException("Voice sample recording failed", it) }
        val file = outputFile ?: error("Missing output file")
        check(file.exists() && file.length() > 44L) { "The recording is empty" }
        return file
    }

    @Synchronized
    fun cancel() {
        if (!running.get()) return
        running.set(false)
        try { audioRecord?.stop() } catch (_: Throwable) { }
        writerThread?.join(2_000)
        audioRecord?.release()
        audioRecord = null
        writerThread = null
        outputFile?.delete()
        outputFile = null
    }

    private fun writeWavHeader(file: RandomAccessFile, dataSize: Int, sampleRate: Int) {
        val byteRate = sampleRate * CHANNEL_COUNT * BITS_PER_SAMPLE / 8
        file.seek(0)
        file.writeBytes("RIFF")
        writeIntLe(file, 36 + dataSize)
        file.writeBytes("WAVE")
        file.writeBytes("fmt ")
        writeIntLe(file, 16)
        writeShortLe(file, 1)
        writeShortLe(file, CHANNEL_COUNT)
        writeIntLe(file, sampleRate)
        writeIntLe(file, byteRate)
        writeShortLe(file, CHANNEL_COUNT * BITS_PER_SAMPLE / 8)
        writeShortLe(file, BITS_PER_SAMPLE)
        file.writeBytes("data")
        writeIntLe(file, dataSize)
    }

    private fun writeIntLe(file: RandomAccessFile, value: Int) {
        file.write(value and 0xff)
        file.write((value shr 8) and 0xff)
        file.write((value shr 16) and 0xff)
        file.write((value shr 24) and 0xff)
    }

    private fun writeShortLe(file: RandomAccessFile, value: Int) {
        file.write(value and 0xff)
        file.write((value shr 8) and 0xff)
    }
}
''', encoding="utf-8")

manifest = Path("app/src/main/AndroidManifest.xml")
if manifest.exists():
    text = manifest.read_text(encoding="utf-8")
    permission = '    <uses-permission android:name="android.permission.RECORD_AUDIO" />\n'
    if "android.permission.RECORD_AUDIO" not in text:
        marker = "<application"
        if marker not in text:
            raise SystemExit("AndroidManifest.xml has no application tag")
        text = text.replace(marker, permission + "    " + marker, 1)
        manifest.write_text(text, encoding="utf-8")
else:
    raise SystemExit("AndroidManifest.xml not found; cannot add microphone permission")

print("Added microphone and permitted playback WAV capture helper.")
