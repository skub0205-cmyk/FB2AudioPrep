#!/usr/bin/env python3
"""Deterministically split speaker-attribution JSONL by whole book."""
import argparse
import json
import random
from collections import defaultdict
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", action="append", required=True, help="JSONL input; repeat for multiple files")
    parser.add_argument("--train", default="train.jsonl")
    parser.add_argument("--dev", default="dev.jsonl")
    parser.add_argument("--test", default="test.jsonl")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    books = defaultdict(list)
    for filename in args.input:
        with open(filename, encoding="utf-8") as source:
            for line_no, line in enumerate(source, 1):
                if not line.strip():
                    continue
                row = json.loads(line)
                if not row.get("book_id"):
                    raise ValueError(f"{filename}:{line_no}: missing book_id")
                books[row["book_id"]].append(row)
    if len(books) < 3:
        raise SystemExit(
            f"Need at least 3 distinct books for train/dev/test; found {len(books)}. "
            "One book must never be split randomly across the sets."
        )

    book_ids = sorted(books)
    random.Random(args.seed).shuffle(book_ids)
    n_test = max(1, round(len(book_ids) * 0.15))
    n_dev = max(1, round(len(book_ids) * 0.15))
    while n_test + n_dev >= len(book_ids):
        if n_test > 1:
            n_test -= 1
        else:
            n_dev -= 1
    test_ids = set(book_ids[:n_test])
    dev_ids = set(book_ids[n_test:n_test + n_dev])
    train_ids = set(book_ids[n_test + n_dev:])

    outputs = (
        (args.train, train_ids),
        (args.dev, dev_ids),
        (args.test, test_ids),
    )
    for filename, selected in outputs:
        with open(filename, "w", encoding="utf-8") as output:
            for book_id in sorted(selected):
                for row in books[book_id]:
                    output.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(json.dumps({
        "books": len(book_ids),
        "train_books": sorted(train_ids),
        "dev_books": sorted(dev_ids),
        "test_books": sorted(test_ids),
        "train_quotes": sum(len(books[x]) for x in train_ids),
        "dev_quotes": sum(len(books[x]) for x in dev_ids),
        "test_quotes": sum(len(books[x]) for x in test_ids),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
