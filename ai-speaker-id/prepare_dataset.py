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
    "поинтересовался|поинтересовалась|заявил|заявила|выдал|выдала|высказал|высказала|продолжил|продолжила|подхватил|подхватила|отрапортовал|отрапортовала|процедил|процедила|пробормотал|пробормотала|пояснил|пояснила|объяснил|объяснила|предложил|предложила|напомнил|напомнила|попросил|попросила|потребовал|потребовала|посоветовал|посоветовала|признался|призналась|отметил|отметила|заметил|заметила|переспросил|переспросила|закричал|закричала|рявкнул|рявкнула|отчеканил|отчеканила|прокомментировал|прокомментировала|отозвался|отозвалась|хмыкнул|хмыкнула|вздохнул|вздохнула|отшутился|отшутился|вставил|вставила|согласился|согласилась|воскликнул|воскликнула|подтвердил|подтвердила|объявил|объявила|распорядился|распорядилась|пожаловался|пожаловалась|пошутил|пошутила|отмахнулся|отмахнулась|"
    "отозвался|отозвалась|добавил|добавила|воскликнул|воскликнула|"
    "уточнил|уточнила|возразил|возразила|проговорил|проговорила|"
    "усмехнулся|усмехнулась|пообещал|пообещала|подтвердил|подтвердила"
)
VERB_RE = re.compile(rf"(?iu)\b(?:{VERBS})\b")
NAME = r"([А-ЯЁ][а-яёА-ЯЁ\u0300-\u036f-]{1,29})"
NAME_AFTER_VERB = re.compile(rf"(?iu:\b(?:{VERBS})\b)(?:\s+[а-яё\u0300-\u036f-]+){{0,2}}\s+{NAME}")
NAME_BEFORE_VERB = re.compile(rf"\b{NAME}(?:\s+[а-яё\u0300-\u036f-]+){{0,2}}\s+(?iu:{VERBS})\b")
PRONOUN_TAG = re.compile(rf"(?iu)\b(?:{VERBS})\s+(я|он|она)\b")
PASSIVE = re.compile(r"(?iu)\b(?:раздался|раздалось|прозвучал|прозвучало)\b.*\bголос")
QUOTE = re.compile(r"[«“\"]([^»”\"]{2,1200})[»”\"]")
NORM = lambda s: re.sub(r"[^а-яё]", "", s.casefold())
STOPWORDS = {
    "что", "кто", "как", "зачем", "почему", "куда", "где", "когда", "это",
    "я", "он", "она", "ты", "мы", "вы", "мне", "меня", "тебе", "ему", "ей",
    "они", "них", "него", "нее", "неё", "зато", "ну", "после", "вот", "ведь",
    "тогда", "потом", "тут", "там", "да", "нет", "если", "хотя", "пока",
    "уже", "еще", "ещё", "просто", "сейчас", "конечно", "наверное", "однако",
    "поэтому", "впрочем", "значит", "кстати", "между", "раз", "наконец"
}


def decode_book(path):
    raw = Path(path).read_bytes()
    # FB2 may be plain XML or a ZIP container holding one XML document.
    if raw.startswith(b"PK"):
        import io
        import zipfile
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            members = [name for name in archive.namelist() if name.lower().endswith(".fb2")]
            if not members:
                raise ValueError("ZIP archive contains no .fb2 document")
            raw = archive.read(members[0])
    if b"<FictionBook" in raw[:4096]:
        import xml.etree.ElementTree as ET
        root = ET.fromstring(raw)
        paragraphs = []
        for element in root.iter():
            if element.tag.rsplit("}", 1)[-1] == "p":
                value = "".join(element.itertext()).strip()
                if value:
                    paragraphs.append(value)
        if paragraphs:
            return "\n\n".join(paragraphs)
    for encoding in ("utf-8-sig", "cp1251", "utf-16"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            pass
    raise UnicodeError("Unsupported input; expected TXT or FB2 in UTF-8/Windows-1251")


def paragraphs_of(text):
    # Some TTS export files store escaped newlines as literal backslash sequences.
    text = text.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\r", "\n")
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    paragraphs = [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n\s*\n+", text) if p.strip()]
    # Some TTS exports use one newline per paragraph and only a few blank lines.
    if len(paragraphs) < 50:
        paragraphs = [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n+", text) if p.strip()]
    return paragraphs


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
            mapped_alias = aliases.get(NORM(speaker)) if speaker else None
            if not speaker or (speaker.casefold() in STOPWORDS and not mapped_alias):
                unresolved.append({
                    "quote_id": hashlib.sha1(f"{book_id}:{pi}:{si}".encode()).hexdigest()[:16],
                    "book_id": book_id, "paragraph_index": pi,
                    "quote": utterance, "context": paragraph, "reason": reason
                })
                continue
            canonical = mapped_alias or speaker
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
