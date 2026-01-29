"""
LLMPot ByT5 inference script
Loads a trained .ckpt produced by multi_trainer.py
and sends raw hex inputs to the model.

Author: Abdelaziz Neamatallah
"""

import json
import torch
from transformers import ByT5Tokenizer, T5ForConditionalGeneration

from src.cfg import EXPERIMENTS
from src.finetune.byt5 import Byt5
from src.finetune.model.finetuner_model import FinetunerModel


# ============================================================
# 1) USER CONFIGURATION
# ============================================================

MODEL_NAME = "byt5-small"
EXPERIMENT_CFG = "wdt_attack1_c0_5000.json"

CHECKPOINT_PATH = (
    "checkpoints/byt5-small/"
    "wdt_attack1_c0_5000.json/"
    "mbtcp-client-c0-s5000-f1_3_5_6-v0_0-a1_49-sc26-sr5/"
    "20260127T1417/checkpoints/best-2.ckpt"
)

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


# ============================================================
# 2) LOAD EXPERIMENT CONFIG (same as training)
# ============================================================

with open(f"{EXPERIMENTS}/{MODEL_NAME}/{EXPERIMENT_CFG}", "r") as f:
    config = json.load(f)

finetuner_model = FinetunerModel(EXPERIMENT_CFG, **config)

print("[INFO] Experiment loaded")
print("[INFO] Model:", finetuner_model.model_name)
print("[INFO] Device:", DEVICE)


# ============================================================
# 3) TOKENIZER (must match training)
# ============================================================

tokenizer = ByT5Tokenizer.from_pretrained(
    f"{finetuner_model.model_type}/{finetuner_model.model_name}"
)


# ============================================================
# 4) REBUILD MODEL EXACTLY LIKE TRAINING
# ============================================================

print("[INFO] Rebuilding ByT5 model structure")

# This creates:
# - HF base model
# - LoRA adapters (if enabled)
# - LightningModule wrapper
byt5_finetuner = Byt5(finetuner_model)

lightning_model = byt5_finetuner._custom_module
lightning_model.to(DEVICE)


# ============================================================
# 5) LOAD CHECKPOINT WEIGHTS (MANUAL)
# ============================================================

print("[INFO] Loading checkpoint:", CHECKPOINT_PATH)

checkpoint = torch.load(CHECKPOINT_PATH, map_location="cpu")

lightning_model.load_state_dict(checkpoint["state_dict"], strict=True)
lightning_model.eval()

print("[INFO] Checkpoint loaded successfully")


# ============================================================
# 6) INFERENCE FUNCTION
# ============================================================

def run_inference(hex_input: str, max_length: int = 512) -> str:
    """
    Send a hex-encoded protocol message to the model
    and return the generated response.
    """

    inputs = tokenizer(
        hex_input,
        return_tensors="pt",
        padding=True,
        truncation=True
    ).to(DEVICE)

    with torch.no_grad():
        output_ids = lightning_model.model.generate(
            **inputs,
            max_length=max_length
        )

    return tokenizer.decode(
        output_ids[0],
        skip_special_tokens=True
    )



# ============================================================
# 7.1) Helper functions
# ============================================================
def hex_to_bytes(hex_str: str):
    """
    Convert hex string to list of byte integers.
    Assumes even-length hex string.
    """
    hex_str = hex_str.strip().lower()
    if len(hex_str) % 2 != 0:
        hex_str = hex_str[:-1]  # safety trim
    return [int(hex_str[i:i+2], 16) for i in range(0, len(hex_str), 2)]


def compute_bca(pred_hex: str, gt_hex: str) -> float:
    """
    Byte Correct Accuracy
    """
    pred_bytes = hex_to_bytes(pred_hex)
    gt_bytes = hex_to_bytes(gt_hex)

    L = min(len(pred_bytes), len(gt_bytes))
    if L == 0:
        return 0.0

    correct = sum(
        1 for i in range(L) if pred_bytes[i] == gt_bytes[i]
    )
    return correct / L


def compute_rva(pred_hex: str, gt_hex: str) -> float:
    """
    Relative Value Accuracy (normalized byte distance)
    """
    pred_bytes = hex_to_bytes(pred_hex)
    gt_bytes = hex_to_bytes(gt_hex)

    L = min(len(pred_bytes), len(gt_bytes))
    if L == 0:
        return 0.0

    abs_diff_sum = sum(
        abs(pred_bytes[i] - gt_bytes[i]) for i in range(L)
    )

    return 1.0 - (abs_diff_sum / (L * 255.0))

# ============================================================
# 7) CSV inference runner
# ============================================================
import csv


def run_csv_inference(csv_path: str):
    bca_scores = []
    rva_scores = []

    print(f"[INFO] Running inference on CSV: {csv_path}")

    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError("CSV file has no header row")

        if "source_text" not in reader.fieldnames:
            raise ValueError("CSV must contain 'source_text' column")

        if "target_text" not in reader.fieldnames:
            raise ValueError("CSV must contain 'target_text' column")


        for idx, row in enumerate(reader):
            src = row["source_text"].strip()
            gt = row["target_text"].strip()

            pred = run_inference(src)

            bca = compute_bca(pred, gt)
            rva = compute_rva(pred, gt)

            bca_scores.append(bca)
            rva_scores.append(rva)

            print(
                f"[{idx:04d}] "
                f"BCA={bca:.4f} | RVA={rva:.4f}"
            )

    mean_bca = sum(bca_scores) / len(bca_scores)
    mean_rva = sum(rva_scores) / len(rva_scores)

    print("\n================ SUMMARY ================\n")
    print(f"Samples : {len(bca_scores)}")
    print(f"Mean BCA: {mean_bca:.6f}")
    print(f"Mean RVA: {mean_rva:.6f}")
    print("\n=========================================\n")


# ============================================================
# 7) EXAMPLE RUN
# ============================================================

## Interactive mode
if __name__ == "__main__":
    # to run: python -m src.inference.my_byt5_inference
    # test_input = "04ad000000150010001700070e02d4f6905690f2fc5bc71801e123"
    # read the test_input from the user
    while(True):
        print("\n================ INFERENCE ================\n")
        test_input = input("Enter hex-encoded input: ").strip()
        if test_input == 'exit':
            break
        print(f'read test input is: {test_input}')
        print("Input : ", test_input)
        output = run_inference(test_input)

        print("Output:", output)
        print("\n==========================================\n")
