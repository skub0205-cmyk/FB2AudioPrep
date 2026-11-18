from pathlib import Path

target = Path("app/src/main/java/ru/fbaudioprep/RussianVoiceCandidates.kt")
target.write_text(r'''package ru.fbaudioprep

/**
 * Audition queue. No CIS speaker gender is inferred from a person's name.
 * All candidates remain unavailable until the pack is installed, checksum-checked,
 * listened to on-device, and its license notice has been verified.
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

    private fun cis(id: String) = RussianVoiceCandidate(
        id = "cis_$id",
        displayName = id.removePrefix("ru_").replaceFirstChar { it.uppercase() },
        gender = VoiceGender.NEUTRAL,
        genderVerified = false,
        modelPackId = SILERO_CIS_RU_PACK,
        licenseId = "MIT",
        stressMode = "manual-or-preprocessed",
        evidence = "Listed as a Russian-language speaker in RuVoice CIS pack; gender and accent require listening test"
    )

    val all: List<RussianVoiceCandidate> = listOf(
        RussianVoiceCandidate(
            "silero_aidar", "Aidar", VoiceGender.NEUTRAL, false,
            SILERO_RU_PACK, "CC-BY-NC-SA-4.0", "automatic",
            "Official Silero v5.6 Russian speaker; gender label must be confirmed by audition"
        ),
        RussianVoiceCandidate(
            "silero_baya", "Baya", VoiceGender.NEUTRAL, false,
            SILERO_RU_PACK, "CC-BY-NC-SA-4.0", "automatic",
            "Official Silero v5.6 Russian speaker; gender label must be confirmed by audition"
        ),
        RussianVoiceCandidate(
            "silero_kseniya", "Kseniya", VoiceGender.NEUTRAL, false,
            SILERO_RU_PACK, "CC-BY-NC-SA-4.0", "automatic",
            "Official Silero v5.6 Russian speaker; gender label must be confirmed by audition"
        ),
        RussianVoiceCandidate(
            "silero_xenia", "Xenia", VoiceGender.NEUTRAL, false,
            SILERO_RU_PACK, "CC-BY-NC-SA-4.0", "automatic",
            "Official Silero v5.6 Russian speaker; gender label must be confirmed by audition"
        ),
        RussianVoiceCandidate(
            "silero_eugene", "Eugene", VoiceGender.NEUTRAL, false,
            SILERO_RU_PACK, "CC-BY-NC-SA-4.0", "automatic",
            "Official Silero v5.6 Russian speaker; gender label must be confirmed by audition"
        ),
        cis("ru_aigul"), cis("ru_albina"), cis("ru_alexandr"),
        cis("ru_alfia"), cis("ru_alfia2"), cis("ru_bogdan"),
        cis("ru_dmitriy"), cis("ru_eduard"), cis("ru_ekaterina"),
        cis("ru_gamat"), cis("ru_igor"), cis("ru_karina"),
        cis("ru_kejilgan"), cis("ru_kermen"), cis("ru_marat"),
        cis("ru_miyau"), cis("ru_nurgul"), cis("ru_oksana"),
        cis("ru_onaoy"), cis("ru_ramilia"), cis("ru_roman"),
        cis("ru_safarhuja"), cis("ru_saida"), cis("ru_sibday"),
        cis("ru_vika"), cis("ru_zara"), cis("ru_zhadyra"),
        cis("ru_zhazira"), cis("ru_zinaida")
    )

    fun validationErrors(): List<String> {
        val errors = mutableListOf<String>()
        if (all.map { it.id }.distinct().size != all.size) {
            errors += "Candidate IDs must be unique"
        }
        if (all.any { it.modelPackId.isBlank() || it.licenseId.isBlank() }) {
            errors += "Every candidate needs a model pack and license"
        }
        return errors
    }

    fun releaseReady(): Boolean =
        validationErrors().isEmpty() &&
            all.none { it.requiresAudition || !it.genderVerified }
}
''', encoding="utf-8")
print("Added verified five Silero RU + all 29 CIS RU voices as unclassified audition candidates.")
