import json
import torch
from transformers import ByT5Tokenizer

from src.cfg import EXPERIMENTS
from src.finetune.custom_lightning.byt5_lightning_module import Byt5LightningModule
from src.finetune.model.finetuner_model import FinetunerModel

# -------------------------------------------------
# 1) CONFIG – adjust these
# -------------------------------------------------
MODEL_NAME = "byt5-small"
EXPERIMENT_CFG = "wdt_attack1_c0_5000.json"
CHECKPOINT_PATH = (
    "checkpoints/byt5-small/"
    "wdt_attack1_c0_5000.json/"
    "mbtcp-client-c0-s5000-f1_3_5_6-v0_0-a1_49-sc26-sr5/"
    "20260127T1417/checkpoints/best-2.ckpt"
)

# -------------------------------------------------
# 2) Load experiment config (same as training)
# -------------------------------------------------
with open(f"{EXPERIMENTS}/{MODEL_NAME}/{EXPERIMENT_CFG}", "r") as f:
    config = json.load(f)

finetuner_model = FinetunerModel(EXPERIMENT_CFG, **config)

# -------------------------------------------------
# 3) Tokenizer (must match training!)
# -------------------------------------------------
tokenizer = ByT5Tokenizer.from_pretrained(
    f"{finetuner_model.model_type}/{finetuner_model.model_name}"
)

# -------------------------------------------------
# 4) Load trained Lightning model
# -------------------------------------------------
model = Byt5LightningModule.load_from_checkpoint(
    CHECKPOINT_PATH,
    tokenizer=tokenizer,
    model_name=finetuner_model.model_name,
    model_type=finetuner_model.model_type,
    config=finetuner_model,
)

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device)
model.eval()

# -------------------------------------------------
# 5) Send input and get response
# -------------------------------------------------
def run_inference(hex_input: str):
    inputs = tokenizer(
        hex_input,
        return_tensors="pt",
        padding=True,
        truncation=True
    ).to(device)

    with torch.no_grad():
        output_ids = model.model.generate(
            **inputs,
            max_length=512
        )

    return tokenizer.decode(
        output_ids[0],
        skip_special_tokens=True
    )

# -------------------------------------------------
# 6) Example
# -------------------------------------------------
if __name__ == "__main__":
    test_input = "04ad000000150010001700070e02d4f6905690f2fc5bc71801e123"
    response = run_inference(test_input)
    print("Input :", test_input)
    print("Output:", response)
