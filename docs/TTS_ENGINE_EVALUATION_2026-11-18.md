# TTS engine evaluation (superseded)

**This document is retained as historical research only. Its earlier provisional recommendation of Silero/Piper is superseded.**

The current product decision is documented in [TTS_ENGINE_DECISION.md](TTS_ENGINE_DECISION.md): **TeraTTSv2 is the selected primary TTS engine for FB2AudioPrep.** Silero is not the primary engine.

Key constraints that remain open:
- The upstream model card lists only four explicitly Russian preset styles (`ru_f1`, `ru_m5`, `ru_f2`, `ru_m1`); the other six listed styles are English prompts and do not count toward the required five Russian male and five Russian female voices.
- Built-in precomputed voice styles do not by themselves provide arbitrary voice cloning from a user's recording.
- Android integration, model packaging, performance, offline operation, licensing, and the ten-voice catalog must be validated before release.

The selection prioritizes expressive audiobook narration. See the decision document for the Android ONNX Runtime implementation plan, dialogue/voice-mapping requirements, licensing notes, and release acceptance criteria.
