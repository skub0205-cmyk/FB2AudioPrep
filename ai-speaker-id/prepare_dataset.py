#!/usr/bin/env python3
"""Build a weakly supervised Russian novel speaker-attribution dataset.

Only explicit, local authorial attributions are auto-labelled. Ambiguous passive
voice descriptions and pronouns are exported to an unresolved review file, never
silently assigned to the nearest name. Source book text is read locally and is
not copied into the repository.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

SPEECH_VERBS = (
    "сказал|сказала|сказали|произнес|произнёс|произнесла|произнесли|"
    "ответил|ответила|ответили|спросил|спросила|спросили|"
    "крикнул|крикнула|крикнули|прошептал|прошептала|прошептали|"
    "буркнул|буркнула|буркнули|проворчал|проворчала|"
    "поинтересовался|поинтересовалась|заявил|заявила|"
    "выдал|выдала|отозвался|отозвалась|добавил|добавила|"
    "воскликнул|воскликнула|уточнил|уточнила|возразил|возразила|"
    "проговорил|проговорила|усмехнулся|усмехнулась|"
    "пообещал|пообещала|подтвердил|подтвердила"
)
VERB_RE = re.compile(rf"(?iu)\b(?:{SPEECH_VERBS})\b")
NAME_RE = re.compile(r"(?u)^[А-ЯЁ][а-яё-]{1,29}$")
DIALOGUE_RE = re.compile(r"(?u)(?:^|[—–]\s*)([^—–]{2,1200})")
NAME_BEFORE_VERB = re.compile(
    rf"(?iu)\b([А-ЯЁ][а-яё-]{{1,29}})(?:\s*,)?(?:\s+[а-яё-]+){{0,5}}\s+({SPEECH_VERBS})\b"
)
PRONOUN_TAG = re.compile(r"(?iu)\b(?:сказал|сказала|ответил|ответила|спросил|спросила|"
                         r"буркнул|буркнула|проворчал|проворчала)\s+(я|он|она)\b")
PASSIVE_VOICE = re.compile(r"(?iu)\b(?:раздался|раздалось|прозвучал|прозвучало)\b.*\bголос")
QUOTE_RE = re.compile(r"[«“\"]([^»”\"]{2,1200})[»”\"]")
NAME_CANON = lambda s: re.sub(r"[^а-яё]", "", s.casefold())


def decode_book(path):
    raw = Path(path).read_bytes()
    for encoding in ("utf-8-sig", "cp1251", "utf-16"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            pass
    raise UnicodeError("Unsupported text encoding; save the book as UTF-8 or Windows-1251")


def split_paragraphs(text):
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    return [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n\s*\n+", text) if p.strip()]


def extract_speaker(tag):
    # First-person narration is a useful stable candidate but needs a book-level alias
    # mapping (e.g. "я" -> protagonist) before the model is trained.
    pronoun = PRONOUN_TAG.search(tag)
    if pronoun:
        return pronoun.group(1).casefold(), "pronoun_tag"
    match = NAME_BEFORE_VERB.search(tag)
    if match:
        return match.group(1), "explicit_name_and_speech_verb"
    return None, None


def extract_rows(text, book_id, aliases):
    paragraphs = split_paragraphs(text)
    labelled, unresolved = [], []
    known = set()
    for p_index, paragraph in enumerate(paragraphs):
        if not re.search(r"[—–«“\"]", paragraph):
            continue
        # A paragraph may contain several dash-delimited turns. Each attribution
        # is considered separately; only a named speaker immediately after a turn
        # is accepted as a weak label.
        spans = list(re.finditer(r"(?u)(?:^|[—–]\s*)(.{2,1400}?)(?=(?:\s+[—–]\s*)|$)", paragraph))
        if not spans:
            continue
        quote_candidates = QUOTE_RE.findall(paragraph)
        for local_index, match in enumerate(spans):
            segment = match.group(1).strip()
            if not segment:
                continue
            # Identify dialogue text from either a dash turn or a quoted utterance.
            is_dash = paragraph[max(0, match.start()-2):match.start()+1].find("—") >= 0 or \
                      paragraph[max(0, match.start()-2):match.start()+1].find("–") >= 0
            quoted = quote_candidates[0] if quote_candidates and (local_index == 0 or "«" in paragraph) else None
            has_verb = VERB_RE.search(segment)
            if not has_verb:
                if PASSIVE_VOICE.search(segment):
                    unresolved.append({
                        "quote_id": hashlib.sha1(f"{book_id}:{p_index}:{local_index}".encode()).hexdigest()[:16],
                        "book_id": book_id, "paragraph_index": p_index,
                        "quote": quoted or (segment if is_dash else ""),
                        "context": paragraph,
                        "reason": "passive_voice_without_named_speaker"
                    })
                continue
            speaker, source = extract_speaker(segment)
            if not speaker:
                unresolved.append({
                    "quote_id": hashlib.sha1(f"{book_id}:{p_index}:{local_index}".encode()).hexdigest()[:16],
                    "book_id": book_id, "paragraph_index": p_index,
                    "quote": quoted or (segment if is_dash else ""),
                    "context": paragraph,
                    "reason": "speech_verb_without_explicit_name"
                })
                continue
            if speaker in ("я", "он", "она"):
                # Pronouns are not character identities without a validated coreference map.
                unresolved.append({
                    "quote_id": hashlib.sha1(f"{book_id}:{p_index}:{local_index}".encode()).hexdigest()[:16],
                    "book_id": book_id, "paragraph_index": p_index,
                    "quote": quoted or segment, "context": paragraph,
                    "reason": "pronoun_requires_coreference_resolution"
                })
                continue
            known.add(speaker)
            qid = hashlib.sha1(f"{book_id}:{p_index}:{local_index}".encode()).hexdigest()[:16]
            before = " ".join(paragraphs[max(0, p_index-2):p_index])
            after = " ".join(paragraphs[p_index+1:p_index+3])
            labelled.append({
                "quote_id": qid, "book_id": book_id,
                "quote": quoted or segment,
                "context_before": before[-1800:],
                "context_after": after[:1800],
                "speaker": aliases.get(NAME_CANON(speaker), speaker),
                "label_source": source,
                "candidate_names": []
            })

    candidates = sorted(known, key=str.casefold)
    # Candidate names are deliberately limited to explicit names found in the book.
    # Add protagonist/aliases using --aliases JSON; do not guess identity links.
    for row in labelled:
        row["candidate_names"] = candidates
    return labelled, unresolved, candidates


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", required=True, help="Local TXT/FB2-extracted text, UTF-8 or CP1251")
    ap.add_argument("--book-id", required=True, help="Stable unique ID for this book")
    ap.add_argument("--out", default="weak_labels.jsonl")
    ap.add_argument("--unresolved", default="unresolved_review.jsonl")
    ap.add_argument("--aliases", help="Optional JSON object mapping normalized aliases to canonical character names")
    args = ap.parse_args()
    aliases = json.loads(Path(args.aliases).read_text(encoding="utf-8")) if args.aliases else {}
    text = decode_book(args.book)
    labelled, unresolved, candidates = extract_rows(text, args.book_id, aliases)
    with open(args.out, "w", encoding="utf-8") as out:
        for row in labelled:
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
    with open(args.unresolved, "w", encoding="utf-8") as out:
        for row in unresolved:
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(json.dumps({
        "book_id": args.book_id, "paragraphs": len(split_paragraphs(text)),
        "labelled_explicit_attributions": len(labelled),
        "unresolved_for_review": len(unresolved),
        "candidate_names": candidates,
        "warning": "Weak labels are noisy. Review and split by whole book before training."
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
