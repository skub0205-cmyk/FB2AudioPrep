# Neural speaker identification for Russian novels

This directory contains the **training/evaluation pipeline** for the next automatic speaker-attribution engine in FB2AudioPrep. It is not yet an Android runtime model and does not claim a Russian accuracy score.

## Method

Use a candidate-scoring network (CSN): for every dialogue utterance, score each known character against the quote and its left/right context. Select the top candidate only when its score is sufficiently separated from the runner-up; otherwise abstain. Keep explicit authorial speech tags as high-confidence evidence and use the model to resolve implicit attribution.

Research baseline: Yue Chen et al., *A Neural-Network-Based Approach to Identifying Speakers in Novels*, INTERSPEECH 2021. The paper reports 82.5% on one Chinese novel dataset, not Russian books. That number is a research reference, **not** a measured FB2AudioPrep result. See https://www.isca-archive.org/interspeech_2021/chen21s_interspeech.pdf and https://github.com/YueChenkkk/CSN-SAPR.

Russian encoder candidate: [deepvk/RuModernBERT-small](https://huggingface.co/deepvk/RuModernBERT-small), 35M parameters, Apache-2.0. The encoder alone does not solve speaker identification; it must be fine-tuned with labeled Russian quote/candidate examples.

## Dataset format

Use JSONL, one dialogue instance per line:

```json
{
  "quote_id": "book1-ch1-q17",
  "book_id": "book1",
  "quote": "«Нико, добро пожаловать!»",
  "context_before": "…",
  "context_after": "— Можно подумать, я так надолго отключался, — проворчал я.",
  "candidates": [
    {"name": "ИсКин", "aliases": ["ИскИн", "ИскИнн"]},
    {"name": "Нико", "aliases": ["Ник"]}
  ],
  "speaker": "ИсКин"
}
```

The correct speaker must be present in candidates. Add **all plausible candidates**, not only the correct one. Use book-level separation between train/dev/test; never split neighbouring quotes from the same chapter randomly across sets. Explicit tags (e.g. «сказала Нурина») can provide seed labels, but check ambiguous cases before training.

## Train

```bash
python -m pip install -r requirements.txt
python train_csn.py --train train.jsonl --dev dev.jsonl --model deepvk/RuModernBERT-small --output ./checkpoint
```

The script reports quote-level top-1 accuracy and abstention coverage on the dev set. These are the metrics that matter; candidate-pair accuracy is not a substitute.

## Export for Android

```bash
python export_onnx.py --checkpoint ./checkpoint --output ./android-model
```

The export contains a dynamically quantized ONNX scorer and the tokenizer files. Before integrating the pack into the APK, validate that Android ONNX Runtime reproduces the Python scores and measure memory, latency, and APK/model size on a real phone.

## Acceptance criteria

1. Report top-1 accuracy, coverage, and accuracy at 70/80/90% confidence on a held-out Russian book set.
2. Include the known hard cases: vocative «Нико» must not be mistaken for the speaker; passive tag «раздался женский голос»; later attribution «всё тем же голосом»; aliases/case variants of «ИсКин».
3. Compare the neural ranker with the existing rule-based analyzer and a combined rule+model pipeline.
4. Only then set default confidence thresholds and ship model weights.

The Android app should remain fully offline after the user installs the verified model pack once. This directory only prepares that pack; the Kotlin inference/runtime integration is a separate next step.
