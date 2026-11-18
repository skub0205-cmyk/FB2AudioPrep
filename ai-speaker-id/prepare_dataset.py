#!/usr/bin/env python3
"""Build a weakly supervised Russian novel speaker-attribution dataset.

Only explicit local authorial attributions are auto-labelled. Passive voice
descriptions and unresolved pronouns are exported separately, never guessed.
The input book remains local; its copyrighted text is not copied to this repo.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

VERBS = (
    "сказал|сказала|сказали|произнес|произнёс|произнесла|произнесли|"
    "ответил|ответила|ответили|спросил|спросила|спросили|крикнул|крикнула|"
    "прошептал|прошептала|буркнул|буркнула|проворчал|проворчала|"
    "поинтересовался|поинтересовалась|заявил|заявила|выдал|выдала|"
    "отозвался|отозвалась|добавил|добавила|воскликнул|воскликнула|"
    "уточнил|уточнила|возразил|возразила|проговорил|проговорила|"
    "усмехнулся|усмехнулась|пообещал|пообещала|подтвердил|подтвердила"
)
VERB_RE = re.compile(rf"(?iu)\b(?:{VERBS})\b")
NAME = r"([А-ЯЁ][а-яёА-ЯЁ-]{1,29})"
NAME_AFTER_VERB = re.compile(rf"(?iu)\b(?:{VERBS})\b[^.!?]{{0,100}}?\b{NAME}")
NAME_BEFORE_VERB = re.compile(rf"(?iu)\b{NAME}(?:\s+[а-яё-]+){{0,4}}\s+(?:{VERBS})\b")
PRONOUN_TAG = re.compile(r"(?iu)\b(?:сказал|сказала|ответил|ответила|спросил|спросила|буркнул|буркнула|проворчал|проворчала)\s+(я|он|она)\b")
PASSIVE = re.compile(r"(?iu)\b(?:раздался|раздалось|прозвучал|прозвучало)\b.*\bголос")
QUOTE = re.compile(r"[«“\"]([^»”\"]{2,1200})[»”\"]")
NORM = lambda s: re.sub(r"[^а-яё]", "", s.casefold())


def decode_book(path):
    raw = Path(path).read_bytes()
    for encoding in ("utf-8-sig", "cp1251", "utf-16"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            pass
    raise UnicodeError("Unsupported text encoding; use UTF-8 or Windows-1251")


def paragraphs_of(text):
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    return [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n\s*\n+", text) if p.strip()]


def speaker_from(tag):
    pronoun = PRONOUN_TAG.search(tag)
    if pronoun:
        return pronoun.group(1).casefold(), "pronoun"
    match = NAME_AFTER_VERB.search(tag) or NAME_BEFORE_VERB.search(tag)
    if match:
        return match.group(1), "explicit_name_and_speech_verb"
    return None, None


def extract(text, book_id, aliases):
    paragraphs = paragraphs_of(text)
    labelled, unresolved = [], []
    candidate_aliases = {}
    for pi, paragraph in enumerate(paragraphs):
        if not re.search(r"[—–«“\"]", paragraph):
            continue
        # Em-dash dialogue and its following attribution are separate spans.
        parts = [x.strip() for x in re.split(r"\s*[—–]\s*", paragraph) if x.strip()]
        quote_matches = QUOTE.findall(paragraph)
        for si, tag in enumerate(parts):
            if not VERB_RE.search(tag) and not PASSIVE.search(tag):
                continue
            utterance = parts[si - 1] if si > 0 else (quote_matches[0] if quote_matches else tag)
            # Strip surrounding quote marks and punctuation without changing content.
            utterance = utterance.strip(" \t,;—–")
            utterance = re.sub(r"^[«“\"]|[»”\"]$", "", utterance).strip()
            if PASSIVE.search(tag) and not VERB_RE.search(tag):
                reason = "passive_voice_without_named_speaker"
                speaker, source = None, None
            else:
                speaker, source = speaker_from(tag)
                reason = "pronoun_requires_coreference" if speaker in ("я", "он", "она") else "speech_verb_without_explicit_name"
            if not speaker or speaker in ("я", "он", "она"):
                unresolved.append({
                    "quote_id": hashlib.sha1(f"{book_id}:{pi}:{si}".encode()).hexdigest()[:16],
                    "book_id": book_id, "paragraph_index": pi,
                    "quote": utterance, "context": paragraph, "reason": reason
                })
                continue
            canonical = aliases.get(NORM(speaker), speaker)
            candidate_aliases.setdefault(canonical, set()).add(speaker)
            before = " ".join(paragraphs[max(0, pi - 2):pi])
            after = " ".join(paragraphs[pi + 1:pi + 3])
            labelled.append({
                "quote_id": hashlib.sha1(f"{book_id}:{pi}:{si}".encode()).hexdigest()[:16],
                "book_id": book_id,
                "quote": utterance or tag,
                "context_before": before[-1800:],
                "context_after": after[:1800],
                "speaker": canonical,
                "label_source": source,
            })

    candidates = [
        {"name": name, "aliases": sorted(values, key=str.casefold)}
        for name, values in sorted(candidate_aliases.items(), key=lambda item: item[0].casefold())
    ]
    for row in labelled:
        row["candidates"] = candidates
    return labelled, unresolved, candidates, len(paragraphs)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--book", required=True, help="Local TXT, UTF-8 or Windows-1251")
    parser.add_argument("--book-id", required=True, help="Stable unique book ID")
    parser.add_argument("--out", default="weak_labels.jsonl")
    parser.add_argument("--unresolved", default="unresolved_review.jsonl")
    parser.add_argument("--aliases", help="JSON map: normalized alias -> canonical character name")
    args = parser.parse_args()
    aliases = json.loads(Path(args.aliases).read_text(encoding="utf-8")) if args.aliases else {}
    labelled, unresolved, candidates, paragraph_count = extract(decode_book(args.book), args.book_id, aliases)
    for path, rows in ((args.out, labelled), (args.unresolved, unresolved)):
        with open(path, "w", encoding="utf-8") as output:
            for row in rows:
                output.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(json.dumps({
        "book_id": args.book_id, "paragraphs": paragraph_count,
        "weakly_labelled_quotes": len(labelled),
        "unresolved_quotes": len(unresolved),
        "candidate_count": len(candidates),
        "candidates": [item["name"] for item in candidates],
        "warning": "Weak labels are noisy. Review them and split train/dev/test by whole book."
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
