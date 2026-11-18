#!/usr/bin/env python3
"""Train a candidate-scoring network for Russian novel speaker attribution.

Each JSONL row is one quote and its complete candidate list. The model scores
each (quote, context, candidate) tuple; evaluation is quote-level top-1 and
confidence/coverage after softmax over the candidate set.
"""
import argparse
import json
import os
import random
import re
from collections import defaultdict

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
            matches = []
            for candidate in row["candidates"]:
                name = candidate if isinstance(candidate, str) else candidate["name"]
                aliases = [] if isinstance(candidate, str) else candidate.get("aliases", [])
                matches.append(target == norm(name) or target in [norm(x) for x in aliases])
            if sum(matches) != 1:
                raise ValueError(
                    f"{path}:{line_no}: speaker must match exactly one candidate; "
                    f"matched {sum(matches)}"
                )
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
    with torch.no_grad():
        for batch in loader:
            batch.pop("labels")
            batch = {key: value.to(device) for key, value in batch.items()}
            logits = model(**batch).logits.squeeze(-1).float().cpu().tolist()
            scores.extend(logits)

    groups = defaultdict(list)
    for sample, score in zip(samples, scores):
        groups[sample["quote_id"]].append((float(score), sample["label"], sample["candidate"]))

    total = len(groups)
    correct = 0
    threshold_counts = {
        threshold: {"accepted": 0, "correct": 0}
        for threshold in (0.70, 0.80, 0.90)
    }
    for candidates in groups.values():
        candidates.sort(key=lambda item: item[0], reverse=True)
        max_score = candidates[0][0]
        exps = [math_exp(item[0] - max_score) for item in candidates]
        denominator = sum(exps) or 1.0
        probabilities = [value / denominator for value in exps]
        is_correct = candidates[0][1] == 1.0
        correct += int(is_correct)
        confidence = probabilities[0]
        for threshold, values in threshold_counts.items():
            if confidence >= threshold:
                values["accepted"] += 1
                values["correct"] += int(is_correct)

    result = {"top1_accuracy": correct / max(total, 1), "quotes": total}
    for threshold, values in threshold_counts.items():
        key = str(int(threshold * 100))
        result[f"coverage_at_{key}"] = values["accepted"] / max(total, 1)
        result[f"accuracy_at_{key}"] = values["correct"] / max(values["accepted"], 1)
    return result


def math_exp(value):
    # Avoid importing numpy; clipping prevents overflow on unusually large logits.
    import math
    return math.exp(max(-60.0, min(60.0, value)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", required=True)
    parser.add_argument("--dev", required=True)
    parser.add_argument("--model", default="deepvk/RuModernBERT-small")
    parser.add_argument("--revision", default="patched-tokenizer")
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
    train_books = {row["book_id"] for row in train_rows}
    dev_books = {row["book_id"] for row in dev_rows}
    overlap = train_books & dev_books
    if overlap:
        raise ValueError("Book leakage between train and dev: " + ", ".join(sorted(overlap)))

    tokenizer = AutoTokenizer.from_pretrained(args.model, revision=args.revision)
    model = AutoModelForSequenceClassification.from_pretrained(
        args.model, revision=args.revision, num_labels=1
    )
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
            batch = {key: value.to(device) for key, value in batch.items()}
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
            with open(os.path.join(args.output, "metrics.json"), "w", encoding="utf-8") as output:
                json.dump(metrics, output, ensure_ascii=False, indent=2)

    print(f"Best held-out-book top1 accuracy: {best:.4f}")


if __name__ == "__main__":
    main()
