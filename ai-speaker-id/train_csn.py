#!/usr/bin/env python3
"""Train a candidate-scoring network for novel dialogue speaker attribution.

Each JSONL row is one quote and its complete candidate list. The model scores
each (quote, context, candidate) tuple; evaluation is quote-level top-1.
"""
import argparse
import json
import os
import random
import re
from collections import defaultdict
from dataclasses import dataclass

import torch
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModelForSequenceClassification, AutoTokenizer


def norm(value):
    return re.sub(r"[^a-zа-яё0-9]+", "", value.casefold())


def read_rows(path):
    rows = []
    with open(path, encoding="utf-8") as stream:
        for line_no, line in enumerate(stream, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            required = ("quote_id", "book_id", "quote", "candidates", "speaker")
            missing = [key for key in required if key not in row]
            if missing:
                raise ValueError(f"{path}:{line_no}: missing {missing}")
            if not row["candidates"]:
                raise ValueError(f"{path}:{line_no}: empty candidates")
            target = norm(row["speaker"])
            matched = any(
                target == norm(c["name"] if isinstance(c, dict) else c)
                or target in [norm(x) for x in (c.get("aliases", []) if isinstance(c, dict) else [])]
                for c in row["candidates"]
            )
            if not matched:
                raise ValueError(f"{path}:{line_no}: speaker not in candidates")
            rows.append(row)
    if not rows:
        raise ValueError(f"No rows in {path}")
    return rows


def candidate_text(candidate):
    if isinstance(candidate, str):
        return candidate, ""
    return candidate["name"], ", ".join(candidate.get("aliases", []))


def flatten(rows):
    samples = []
    for row in rows:
        target = norm(row["speaker"])
        for candidate in row["candidates"]:
            name, aliases = candidate_text(candidate)
            positive = target == norm(name) or target in [norm(x) for x in aliases.split(", ") if x]
            text = (
                "[QUOTE] " + row["quote"] +
                " [LEFT CONTEXT] " + row.get("context_before", "") +
                " [RIGHT CONTEXT] " + row.get("context_after", "") +
                " [CANDIDATE] " + name +
                " [ALIASES] " + aliases
            )
            samples.append({
                "quote_id": str(row["quote_id"]),
                "text": text,
                "label": 1.0 if positive else 0.0,
                "book_id": row["book_id"],
                "speaker": row["speaker"],
                "candidate": name,
            })
    return samples


class PairDataset(Dataset):
    def __init__(self, samples, tokenizer, max_length):
        self.samples = samples
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, index):
        sample = self.samples[index]
        encoded = self.tokenizer(
            sample["text"], truncation=True, max_length=self.max_length,
            padding="max_length", return_tensors="pt"
        )
        return {
            "input_ids": encoded["input_ids"].squeeze(0),
            "attention_mask": encoded["attention_mask"].squeeze(0),
            "labels": torch.tensor(sample["label"], dtype=torch.float32),
        }


def evaluate(model, loader, samples, device):
    model.eval()
    scores = []
    offset = 0
    with torch.no_grad():
        for batch in loader:
            labels = batch.pop("labels")
            batch = {k: v.to(device) for k, v in batch.items()}
            logits = model(**batch).logits.squeeze(-1).float().cpu().tolist()
            count = len(logits)
            scores.extend(logits)
            offset += count
    groups = defaultdict(list)
    for sample, score in zip(samples, scores):
        groups[sample["quote_id"]].append((score, sample["label"], sample["candidate"]))
    correct = 0
    total = 0
    accepted = 0
    accepted_correct = 0
    for candidates in groups.values():
        candidates.sort(key=lambda x: x[0], reverse=True)
        total += 1
        correct += int(candidates[0][1] == 1.0)
        margin = candidates[0][0] - (candidates[1][0] if len(candidates) > 1 else -99.0)
        if margin >= 0.75:
            accepted += 1
            accepted_correct += int(candidates[0][1] == 1.0)
    return {
        "top1_accuracy": correct / max(total, 1),
        "coverage_margin_0_75": accepted / max(total, 1),
        "accuracy_on_accepted": accepted_correct / max(accepted, 1),
        "quotes": total,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", required=True)
    parser.add_argument("--dev", required=True)
    parser.add_argument("--model", default="deepvk/RuModernBERT-small")
    parser.add_argument("--output", required=True)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--lr", type=float, default=2e-5)
    parser.add_argument("--max-length", type=int, default=512)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    random.seed(args.seed)
    torch.manual_seed(args.seed)
    train_rows, dev_rows = read_rows(args.train), read_rows(args.dev)
    train_books = {r["book_id"] for r in train_rows}
    dev_books = {r["book_id"] for r in dev_rows}
    overlap = train_books & dev_books
    if overlap:
        raise ValueError("Book leakage between train and dev: " + ", ".join(sorted(overlap)))

    tokenizer = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForSequenceClassification.from_pretrained(args.model, num_labels=1)
    train_samples, dev_samples = flatten(train_rows), flatten(dev_rows)
    train_ds = PairDataset(train_samples, tokenizer, args.max_length)
    dev_ds = PairDataset(dev_samples, tokenizer, args.max_length)
    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True)
    dev_loader = DataLoader(dev_ds, batch_size=args.batch_size, shuffle=False)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr)
    best = -1.0

    for epoch in range(args.epochs):
        model.train()
        running, steps = 0.0, 0
        for batch in train_loader:
            labels = batch.pop("labels").to(device)
            batch = {k: v.to(device) for k, v in batch.items()}
            logits = model(**batch).logits.squeeze(-1)
            loss = torch.nn.functional.binary_cross_entropy_with_logits(logits, labels)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            optimizer.zero_grad()
            running += float(loss.detach())
            steps += 1
        metrics = evaluate(model, dev_loader, dev_samples, device)
        print(json.dumps({
            "epoch": epoch + 1, "train_loss": running / max(steps, 1), **metrics
        }, ensure_ascii=False))
        if metrics["top1_accuracy"] > best:
            best = metrics["top1_accuracy"]
            os.makedirs(args.output, exist_ok=True)
            model.save_pretrained(args.output)
            tokenizer.save_pretrained(args.output)
            with open(os.path.join(args.output, "metrics.json"), "w", encoding="utf-8") as out:
                json.dump(metrics, out, ensure_ascii=False, indent=2)

    print(f"Best held-out-book top1 accuracy: {best:.4f}")


if __name__ == "__main__":
    main()
