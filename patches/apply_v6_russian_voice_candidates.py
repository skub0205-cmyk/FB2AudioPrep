from pathlib import Path

target = Path("app/src/main/java/ru/fbaudioprep/RussianVoiceCandidates.kt")
target.write_text(r'''package ru.fbaudioprep

/**
 * Audition queue, not an assertion that all models are already bundled.
 * Candidates remain unavailable until their model pack is installed, hash-checked,
 * auditioned on-device, and their original license notice has been verified.
 */
data class RussianVoiceCandidate(
    val id: String,
    val displayName: String,
    val gender: VoiceGender,
    val genderVerified: Boolean,
    val modelPackId: String,
    val licenseId: String,
    val stressMode: String,
    val evidence: String,
    val requiresAudition: Boolean = true
)

object RussianVoiceCandidates {
    const val SILERO_RU_PACK = "silero-v5_6_ru"
    const val SILERO_CIS_RU_PACK = "silero-v5_cis_base_nostress"

    val all: List<RussianVoiceCandidate> = listOf(
        RussianVoiceCandidate(
            "silero_aidar", "Aidar", VoiceGender.MALE, true,
            SILERO_RU_PACK, "CC-BY-NC-SA-4.0", "automatic",
            "Silero v5.6 Russian speaker list; male voice documented by RuVoice/Silero aliases"
        ),
        RussianVoiceCandidate(
            "silero_eugene", "Eugene", VoiceGender.MALE, true,
            SILERO_RU_PACK, "CC-BY-NC-SA-4.0", "automatic",
            "Silero v5.6 Russian speaker list; male voice documented"
        ),
        RussianVoiceCandidate(
            "silero_baya", "Baya", VoiceGender.FEMALE, true,
            SILERO_RU_PACK, "CC-BY-NC-SA-4.0", "automatic",
            "Silero v5.6 Russian speaker list; female voice documented"
        ),
        RussianVoiceCandidate(
            "silero_kseniya", "Kseniya", VoiceGender.FEMALE, true,
            SILERO_RU_PACK, "CC-BY-NC-SA-4.0", "automatic",
            "Silero v5.6 Russian speaker list; female voice documented"
        ),
        RussianVoiceCandidate(
            "silero_xenia", "Xenia", VoiceGender.FEMALE, true,
            SILERO_RU_PACK, "CC-BY-NC-SA-4.0", "automatic",
            "Silero v5.6 Russian speaker list; female voice documented"
        ),
        RussianVoiceCandidate(
            "cis_ru_alexandr", "Alexandr", VoiceGender.MALE, true,
            SILERO_CIS_RU_PACK, "MIT", "manual-or-preprocessed",
            "CIS pack alias maps ru_alexandr to the documented male Ruslan voice"
        ),
        RussianVoiceCandidate(
            "cis_ru_eduard", "Eduard", VoiceGender.MALE, true,
            SILERO_CIS_RU_PACK, "MIT", "manual-or-preprocessed",
            "CIS pack alias maps ru_eduard to the documented male Aidar voice"
        ),
        RussianVoiceCandidate(
            "cis_ru_dmitriy", "Dmitriy", VoiceGender.MALE, false,
            SILERO_CIS_RU_PACK, "MIT", "manual-or-preprocessed",
            "Provisional gender label from speaker name; must be confirmed by audition"
        ),
        RussianVoiceCandidate(
            "cis_ru_albina", "Albina", VoiceGender.FEMALE, true,
            SILERO_CIS_RU_PACK, "MIT", "manual-or-preprocessed",
            "CIS pack alias maps ru_albina to the documented female Natasha voice"
        ),
        RussianVoiceCandidate(
            "cis_ru_ramilia", "Ramilia", VoiceGender.FEMALE, true,
            SILERO_CIS_RU_PACK, "MIT", "manual-or-preprocessed",
            "CIS pack alias maps ru_ramilia to the documented female Irina voice"
        )
    )

    fun validationErrors(): List<String> {
        val errors = mutableListOf<String>()
        if (all.map { it.id }.distinct().size != all.size) {
            errors += "Candidate IDs must be unique"
        }
        if (all.count { it.gender == VoiceGender.MALE } < 5) {
            errors += "Need at least five male Russian voice candidates"
        }
        if (all.count { it.gender == VoiceGender.FEMALE } < 5) {
            errors += "Need at least five female Russian voice candidates"
        }
        if (all.any { it.licenseId.isBlank() || it.modelPackId.isBlank() }) {
            errors += "Every candidate needs a model pack and license"
        }
        return errors
    }

    fun releaseReady(): Boolean =
        validationErrors().isEmpty() && all.none { it.requiresAudition || !it.genderVerified }
}
''', encoding="utf-8")
print("Added ten Russian Silero voice candidates with explicit verification state.")
