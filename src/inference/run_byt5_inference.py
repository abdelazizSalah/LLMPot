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
# 7) EXAMPLE RUN
# ============================================================

if __name__ == "__main__":

    test_input = "04ad000000150010001700070e02d4f6905690f2fc5bc71801e123"

    print("\n================ INFERENCE ================\n")
    print("Input : ", test_input)

    output = run_inference(test_input)

    print("Output:", output)
    print("\n==========================================\n")
