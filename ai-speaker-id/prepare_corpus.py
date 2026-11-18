#!/usr/bin/env python3
"""Batch-extract weak speaker labels from a local directory of TXT books."""
import argparse
import json
from pathlib import Path

from prepare_dataset import decode_book, extract


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", required=True, help="Directory containing local .txt books")
    parser.add_argument("--out", default="weak_labels.jsonl")
    parser.add_argument("--unresolved", default="unresolved_review.jsonl")
    parser.add_argument("--aliases", help="Optional JSON map of normalized aliases to canonical names")
    args = parser.parse_args()

    root = Path(args.input_dir)
    books = sorted(root.glob("*.txt"))
    if not books:
        raise SystemExit(f"No .txt files found in {root}")
    aliases = json.loads(Path(args.aliases).read_text(encoding="utf-8")) if args.aliases else {}
    all_labelled, all_unresolved = [], []
    report = []
    for book in books:
        book_id = book.stem
        labelled, unresolved, candidates, paragraphs = extract(decode_book(book), book_id, aliases)
        all_labelled.extend(labelled)
        all_unresolved.extend(unresolved)
        report.append({
            "book_id": book_id, "paragraphs": paragraphs,
            "weak_labels": len(labelled), "unresolved": len(unresolved),
            "candidate_count": len(candidates)
        })
    for path, rows in ((args.out, all_labelled), (args.unresolved, all_unresolved)):
        with open(path, "w", encoding="utf-8") as output:
            for row in rows:
                output.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(json.dumps({
        "books": len(books), "total_weak_labels": len(all_labelled),
        "total_unresolved": len(all_unresolved), "per_book": report,
        "warning": "Review weak labels; split train/dev/test by whole book."
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
