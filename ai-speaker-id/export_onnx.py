#!/usr/bin/env python3
"""Export the fine-tuned single-logit candidate scorer to dynamic INT8 ONNX."""
import argparse
import os
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer
from onnxruntime.quantization import QuantType, quantize_dynamic


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    os.makedirs(args.output, exist_ok=True)

    model = AutoModelForSequenceClassification.from_pretrained(args.checkpoint).cpu().eval()
    tokenizer = AutoTokenizer.from_pretrained(args.checkpoint)
    sample = tokenizer(
        "[QUOTE] Привет. [LEFT CONTEXT] Он вошёл. [RIGHT CONTEXT] Она ответила. [CANDIDATE] Нико",
        return_tensors="pt", truncation=True, max_length=512
    )
    float_path = os.path.join(args.output, "speaker-csn-fp32.onnx")
    torch.onnx.export(
        model, (sample["input_ids"], sample["attention_mask"]), float_path,
        input_names=["input_ids", "attention_mask"], output_names=["logits"],
        dynamic_axes={
            "input_ids": {0: "batch", 1: "sequence"},
            "attention_mask": {0: "batch", 1: "sequence"},
            "logits": {0: "batch"},
        },
        opset_version=17, do_constant_folding=True
    )
    int8_path = os.path.join(args.output, "speaker-csn-int8.onnx")
    quantize_dynamic(float_path, int8_path, weight_type=QuantType.QInt8)
    tokenizer.save_pretrained(args.output)
    os.remove(float_path)
    print("Exported", int8_path)
    print("Copy the complete output directory into a versioned, SHA-256-pinned model pack.")


if __name__ == "__main__":
    main()
