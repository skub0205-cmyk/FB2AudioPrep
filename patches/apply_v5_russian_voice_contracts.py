from pathlib import Path

# Stable Kotlin contracts for the Russian voice catalog and offline engines.
# This patch deliberately adds no fake voice entries and no non-functional play button.
target = Path("app/src/main/java/ru/fbaudioprep/RussianVoiceContracts.kt")
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(r'''package ru.fbaudioprep

import java.io.File

/**
 * Shared contracts for preset Russian TTS and reference-audio voice cloning.
 * Implementations must be local after their model pack has been installed.
 */
enum class VoiceGender { MALE, FEMALE, NEUTRAL }

data class RussianVoice(
    val id: String,
    val displayName: String,
    val gender: VoiceGender,
    val engineId: String,
    val modelPackId: String,
    val sampleText: String,
    val isBuiltIn: Boolean = true,
    val isAvailableOffline: Boolean = false
) {
    init {
        require(id.isNotBlank()) { "Voice id must not be blank" }
        require(displayName.isNotBlank()) { "Voice name must not be blank" }
        require(engineId.isNotBlank()) { "Engine id must not be blank" }
        require(modelPackId.isNotBlank()) { "Model pack id must not be blank" }
        require(sampleText.isNotBlank()) { "Voice preview text must not be blank" }
    }

    val locale: String get() = "ru-RU"
}

data class VoiceModelPack(
    val id: String,
    val version: String,
    val downloadSizeBytes: Long,
    val sha256: String,
    val licenseId: String,
    val attribution: String,
    val supportsOfflineInference: Boolean
) {
    init {
        require(id.isNotBlank())
        require(version.isNotBlank())
        require(downloadSizeBytes >= 0L)
        require(sha256.matches(Regex("^[a-fA-F0-9]{64}$"))) {
            "Model pack must provide a SHA-256 checksum"
        }
        require(licenseId.isNotBlank())
    }
}

data class VoiceProfile(
    val id: String,
    val displayName: String,
    val engineId: String,
    val modelPackId: String,
    val createdAtEpochMillis: Long,
    val sourceRecording: File?,
    val speakerEmbedding: File,
    val isSyntheticVoice: Boolean = true
)

data class VoiceCloneConsent(
    val userOwnsVoiceOrHasPermission: Boolean,
    val confirmedAtEpochMillis: Long
) {
    fun isValid(): Boolean =
        userOwnsVoiceOrHasPermission && confirmedAtEpochMillis > 0L
}

enum class VoiceSampleSource { MICROPHONE, IMPORTED_FILE, SYSTEM_PLAYBACK_CAPTURE }

enum class CaptureAvailability {
    AVAILABLE,
    USER_CONSENT_REQUIRED,
    SOURCE_APP_BLOCKED,
    PROTECTED_AUDIO,
    UNSUPPORTED_ANDROID_VERSION,
    STOPPED
}

/** A preset-voice synthesizer. Voice cloning is intentionally a separate capability. */
interface RussianTtsEngine {
    val engineId: String
    suspend fun loadModel(pack: VoiceModelPack, modelDirectory: File)
    suspend fun synthesize(
        text: String,
        voice: RussianVoice,
        outputWav: File,
        speed: Float = 1.0f
    )
    fun isModelReady(packId: String): Boolean
}

/** Implement only for models proven to synthesize unseen text from reference audio. */
interface RussianVoiceCloningEngine {
    val engineId: String
    suspend fun createProfile(
        referenceAudio: File,
        transcript: String?,
        profileDirectory: File,
        consent: VoiceCloneConsent
    ): VoiceProfile

    suspend fun synthesizeWithProfile(
        text: String,
        profile: VoiceProfile,
        outputWav: File,
        speed: Float = 1.0f
    )
}

/** Validation is run against real, licensed catalog entries before a release. */
object RussianVoiceCatalogValidator {
    fun validateBuiltIns(voices: List<RussianVoice>): List<String> {
        val errors = mutableListOf<String>()
        val builtIns = voices.filter { it.isBuiltIn }

        if (builtIns.map { it.id }.distinct().size != builtIns.size) {
            errors += "Built-in voice IDs must be unique"
        }
        if (builtIns.any { it.locale != "ru-RU" }) {
            errors += "Only Russian ru-RU voices may be included"
        }
        if (builtIns.count { it.gender == VoiceGender.MALE } < 5) {
            errors += "At least five built-in male Russian voices are required"
        }
        if (builtIns.count { it.gender == VoiceGender.FEMALE } < 5) {
            errors += "At least five built-in female Russian voices are required"
        }
        if (builtIns.any { it.sampleText.isBlank() || it.modelPackId.isBlank() }) {
            errors += "Every built-in voice needs a preview and a model pack"
        }
        return errors
    }
}
''', encoding="utf-8")
print("Added RussianVoiceContracts.kt")
