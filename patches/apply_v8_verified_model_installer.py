from pathlib import Path

root = Path("app/src/main/java/ru/fbaudioprep")
root.mkdir(parents=True, exist_ok=True)
(root / "VoiceModelPackInstaller.kt").write_text(r'''package ru.fbaudioprep

import android.content.Context
import java.io.BufferedInputStream
import java.io.BufferedOutputStream
import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest
import java.util.zip.ZipInputStream

/**
 * One-time model pack download with SHA-256 verification and atomic installation.
 * Synthesis never uses this class and must work without network access once installed.
 *
 * Call from a background dispatcher/thread. Only provide trusted, pinned HTTPS URLs
 * and checksums from the reviewed model manifest.
 */
object VoiceModelPackInstaller {
    data class DownloadProgress(val bytesDownloaded: Long, val totalBytes: Long) {
        val fraction: Float?
            get() = if (totalBytes > 0L) {
                (bytesDownloaded.toFloat() / totalBytes).coerceIn(0f, 1f)
            } else null
    }

    fun downloadAndInstall(
        context: Context,
        packId: String,
        downloadUrl: String,
        expectedSha256: String,
        onProgress: (DownloadProgress) -> Unit = {}
    ): File {
        require(packId.matches(Regex("^[a-zA-Z0-9._-]+$"))) { "Invalid pack ID" }
        require(URL(downloadUrl).protocol.equals("https", ignoreCase = true)) {
            "Model packs must be downloaded over HTTPS"
        }
        require(expectedSha256.matches(Regex("^[a-fA-F0-9]{64}$"))) {
            "A valid SHA-256 checksum is required"
        }

        val root = File(context.filesDir, "voice-models").apply { mkdirs() }
        val installed = File(root, packId)
        val marker = File(installed, ".verified-sha256")
        if (installed.isDirectory && marker.isFile &&
            marker.readText().trim().equals(expectedSha256, ignoreCase = true)
        ) return installed

        val archive = File(root, ".$packId.download")
        val connection = (URL(downloadUrl).openConnection() as HttpURLConnection).apply {
            connectTimeout = 20_000
            readTimeout = 60_000
            instanceFollowRedirects = true
            requestMethod = "GET"
        }

        try {
            connection.connect()
            check(connection.responseCode in 200..299) {
                "Model download failed: HTTP " + connection.responseCode
            }
            val total = connection.contentLengthLong
            BufferedInputStream(connection.inputStream).use { input ->
                FileOutputStream(archive).use { fileOut ->
                    BufferedOutputStream(fileOut).use { output ->
                        val buffer = ByteArray(64 * 1024)
                        var downloaded = 0L
                        while (true) {
                            val count = input.read(buffer)
                            if (count < 0) break
                            output.write(buffer, 0, count)
                            downloaded += count
                            onProgress(DownloadProgress(downloaded, total))
                        }
                        output.flush()
                        fileOut.fd.sync()
                    }
                }
            }
        } catch (error: Throwable) {
            archive.delete()
            throw error
        } finally {
            connection.disconnect()
        }

        val actualHash = sha256(archive)
        if (!actualHash.equals(expectedSha256, ignoreCase = true)) {
            archive.delete()
            error("Model pack checksum mismatch")
        }

        val staging = File(root, ".$packId.installing").apply {
            deleteRecursively()
            mkdirs()
        }
        try {
            extractZipSafely(archive, staging)
            File(staging, ".verified-sha256").writeText(actualHash)
            if (installed.exists()) check(installed.deleteRecursively()) {
                "Cannot replace previous model pack"
            }
            check(staging.renameTo(installed)) { "Cannot finalize model pack installation" }
            archive.delete()
            return installed
        } catch (error: Throwable) {
            staging.deleteRecursively()
            throw error
        }
    }

    private fun sha256(file: File): String {
        val digest = MessageDigest.getInstance("SHA-256")
        FileInputStream(file).use { input ->
            val buffer = ByteArray(64 * 1024)
            while (true) {
                val count = input.read(buffer)
                if (count < 0) break
                digest.update(buffer, 0, count)
            }
        }
        return digest.digest().joinToString("") { "%02x".format(it) }
    }

    private fun extractZipSafely(archive: File, destination: File) {
        val rootPath = destination.canonicalPath + File.separator
        var expandedBytes = 0L
        val maxExpandedBytes = 4L * 1024L * 1024L * 1024L
        ZipInputStream(BufferedInputStream(FileInputStream(archive))).use { zip ->
            while (true) {
                val entry = zip.nextEntry ?: break
                val out = File(destination, entry.name)
                val canonical = out.canonicalPath
                check(canonical.startsWith(rootPath)) { "Unsafe path in model archive" }
                if (entry.isDirectory) {
                    out.mkdirs()
                } else {
                    out.parentFile?.mkdirs()
                    FileOutputStream(out).use { output ->
                        val buffer = ByteArray(64 * 1024)
                        while (true) {
                            val count = zip.read(buffer)
                            if (count < 0) break
                            expandedBytes += count
                            check(expandedBytes <= maxExpandedBytes) {
                                "Model archive exceeds extraction size limit"
                            }
                            output.write(buffer, 0, count)
                        }
                    }
                }
                zip.closeEntry()
            }
        }
    }
}
''', encoding="utf-8")

manifest = Path("app/src/main/AndroidManifest.xml")
text = manifest.read_text(encoding="utf-8")
permission = '    <uses-permission android:name="android.permission.INTERNET" />\n'
if "android.permission.INTERNET" not in text:
    marker = "<application"
    if marker not in text:
        raise SystemExit("AndroidManifest.xml has no application tag")
    text = text.replace(marker, permission + "    " + marker, 1)
manifest.write_text(text, encoding="utf-8")
print("Added HTTPS model download, SHA-256 verification, safe extraction and offline installation.")
