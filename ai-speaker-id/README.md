# Neural speaker identification for Russian novels

This directory contains the **training and evaluation pipeline** for FB2AudioPrep's automatic speaker attribution. It is not yet an Android runtime model and does not claim a Russian accuracy score.

## Method

Use a candidate-scoring network (CSN): for every dialogue utterance, score each known character against the quote and its left/right context. Select the top candidate only when its calibrated confidence is high enough; otherwise abstain. Explicit authorial speech tags remain strong evidence, while the model resolves implicit attribution and dialogue continuity.

Research baseline: Yue Chen et al., *A Neural-Network-Based Approach to Identifying Speakers in Novels*, INTERSPEECH 2021. The paper reports 82.5% on one Chinese novel dataset, not Russian books. That number is a research reference, **not** a measured FB2AudioPrep result. See https://www.isca-archive.org/interspeech_2021/chen21s_interspeech.pdf and https://github.com/YueChenkkk/CSN-SAPR.

Russian encoder: [deepvk/RuModernBERT-small](https://huggingface.co/deepvk/RuModernBERT-small), 35M parameters, Apache-2.0. Use revision patched-tokenizer: the model authors document that the original tokenizer split several frequent lowercase Russian letters into subwords and provide a patched revision for better Russian word segmentation. The encoder alone does not solve speaker identification; it must be fine-tuned with labeled Russian quote/candidate examples.

## Prepare data from local books

The source book is processed locally and is **not copied into this repository**.

\`\`\`bash
python ai-speaker-id/prepare_dataset.py \\
  --book /path/to/book.txt \\
  --book-id book_001 \\
  --out weak_labels.jsonl \\
  --unresolved unresolved_review.jsonl
\`\`\`

The extractor only weak-labels an utterance when it finds a nearby explicit character name and speech verb. Passive descriptions such as «раздался женский голос» and unresolved pronouns are sent to unresolved_review.jsonl, not guessed. Review these records and add verified labels before training. An optional JSON alias map can merge confirmed name variants:

\`\`\`json
{
  "я": "Нико",
  "искин": "ИскИн",
  "искинн": "ИскИн"
}
\`\`\`

Run extraction tests:

\`\`\`bash
python -m unittest discover -s ai-speaker-id -p "test_*.py" -v
\`\`\`

For several books, use the batch extractor:

\`\`\`bash
python ai-speaker-id/prepare_corpus.py \\
  --input-dir ./books \\
  --aliases aliases.json \\
  --out weak_labels.jsonl \\
  --unresolved unresolved_review.jsonl
\`\`\`

The optional book-ID map matters when two files are different exports/chunks of the **same novel**. Give both filename stems the same canonical ID so they cannot leak across train/dev/test:

~~~json
{
  "edition_a": "same_novel_01",
  "edition_b": "same_novel_01"
}
~~~

Then split by whole books (the splitter refuses to use fewer than three distinct books):

\`\`\`bash
python ai-speaker-id/split_by_book.py \\
  --input weak_labels.jsonl \\
  --train train.jsonl \\
  --dev dev.jsonl \\
  --test test.jsonl
\`\`\`

## Dataset format

JSONL, one dialogue instance per line:

\`\`\`json
{
  "quote_id": "book1-ch1-q17",
  "book_id": "book1",
  "quote": "«Нико, добро пожаловать!»",
  "context_before": "…",
  "context_after": "— Можно подумать, я так надолго отключался, — проворчал я.",
  "candidates": [
    {"name": "ИсКин", "aliases": ["ИскИн"]},
    {"name": "Нико", "aliases": ["Ник"]}
  ],
  "speaker": "ИсКин"
}
\`\`\`

The correct speaker must be present in candidates. Add all plausible candidates, not only the correct one. The alias map can explicitly resolve the first-person narrator (for this particular book, «я» to «Нико»); pronouns are otherwise left unresolved. Keep the entire book in exactly one split; never randomly split neighbouring quotes from the same book across train/dev/test. A single novel is useful for parser validation and error analysis, but **not sufficient** to establish generalization or a trustworthy held-out accuracy.

## Train

\`\`\`bash
python -m pip install -r ai-speaker-id/requirements.txt
python ai-speaker-id/train_csn.py \\
  --train train.jsonl \\
  --dev dev.jsonl \\
  --model deepvk/RuModernBERT-small \\
  --revision patched-tokenizer \\
  --output ./checkpoint
\`\`\`

The script reports quote-level top-1 accuracy plus confidence/coverage at 70%, 80%, and 90% on held-out books. Candidate-pair accuracy is not a substitute. Confidence is computed by softmax over the candidate set; it must still be calibrated and checked on real Russian books before being used to make automatic voice assignments.

## Export for Android

\`\`\`bash
python ai-speaker-id/export_onnx.py --checkpoint ./checkpoint --output ./android-model
\`\`\`

The export contains a dynamically quantized ONNX scorer and tokenizer files. Before integrating the pack into the APK, validate that Android ONNX Runtime reproduces Python scores and measure memory, latency, and model size on a real phone. Tokenizer parity is mandatory: Android must use the same patched tokenizer revision as training.

## Acceptance criteria

1. Report top-1 accuracy, coverage, and accuracy at 70/80/90% confidence on a held-out Russian book set.
2. Include hard cases: vocative «Нико» must not be mistaken for the speaker; passive tag «раздался женский голос»; later attribution «всё тем же голосом»; aliases/case variants of «ИсКин».
3. Compare the neural ranker with the existing rule-based analyzer and a combined rule+model pipeline.
4. Only then set default confidence thresholds and ship model weights.

The Android app should remain fully offline after the user installs the verified model pack once. This directory prepares and evaluates that pack; Kotlin ONNX inference/runtime integration is a separate step.
