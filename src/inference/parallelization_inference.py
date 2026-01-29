"""
LLMPot ByT5 inference + evaluation script

- Loads trained ByT5 checkpoint
- Runs inference on CSV (source_text,target_text)
- Computes BCA & RVA manually
- Safe parallelism (GPU-safe)
- Writes results to files (no console spam)

Author: Abdelaziz Neamatallah
"""
from tqdm import tqdm
import json
import csv
import torch
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from transformers import ByT5Tokenizer
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
# 2) LOAD EXPERIMENT CONFIG
# ============================================================

with open(f"{EXPERIMENTS}/{MODEL_NAME}/{EXPERIMENT_CFG}", "r") as f:
    config = json.load(f)

finetuner_model = FinetunerModel(EXPERIMENT_CFG, **config)

# ============================================================
# 3) TOKENIZER
# ============================================================

tokenizer = ByT5Tokenizer.from_pretrained(
    f"{finetuner_model.model_type}/{finetuner_model.model_name}"
)

# ============================================================
# 4) REBUILD MODEL (EXACT TRAINING STRUCTURE)
# ============================================================

byt5_finetuner = Byt5(finetuner_model)
lightning_model = byt5_finetuner._custom_module
lightning_model.to(DEVICE)

# ============================================================
# 5) LOAD CHECKPOINT
# ============================================================

checkpoint = torch.load(CHECKPOINT_PATH, map_location="cpu")
lightning_model.load_state_dict(checkpoint["state_dict"], strict=True)
lightning_model.eval()

# ============================================================
# 6) INFERENCE FUNCTION (GPU-SAFE)
# ============================================================

def run_inference(hex_input: str, max_length: int = 512) -> str:
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

    return tokenizer.decode(output_ids[0], skip_special_tokens=True)

# ============================================================
# 7) METRICS
# ============================================================

def hex_to_bytes(hex_str: str):
    hex_str = hex_str.strip().lower()
    if len(hex_str) % 2 != 0:
        hex_str = hex_str[:-1]
    return [int(hex_str[i:i+2], 16) for i in range(0, len(hex_str), 2)]

def compute_bca(pred_hex: str, gt_hex: str) -> float:
    pb = hex_to_bytes(pred_hex)
    gb = hex_to_bytes(gt_hex)
    L = min(len(pb), len(gb))
    if L == 0:
        return 0.0
    return sum(pb[i] == gb[i] for i in range(L)) / L

def compute_rva(pred_hex: str, gt_hex: str) -> float:
    pb = hex_to_bytes(pred_hex)
    gb = hex_to_bytes(gt_hex)
    L = min(len(pb), len(gb))
    if L == 0:
        return 0.0
    return 1.0 - sum(abs(pb[i] - gb[i]) for i in range(L)) / (L * 255.0)

def process_metrics(idx, pred, gt):
    bca = compute_bca(pred, gt)
    rva = compute_rva(pred, gt)
    return {
        "index": idx,
        "bca": bca,
        "rva": rva,
        "perfect": (bca == 1.0 and rva == 1.0)
    }

# ============================================================
# 8) PARALLEL CSV INFERENCE PIPELINE
# ============================================================

def run_csv_inference(csv_path: str):
    csv_path = Path(csv_path)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    out_dir = csv_path.parent / f"inference_results_{timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    results_csv = out_dir / "results.csv"
    bad_txt = out_dir / "non_perfect_indices.txt"
    summary_txt = out_dir / "summary.txt"

    # ---------- Load CSV ----------
    rows = []
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError("CSV has no header")

        if "source_text" not in reader.fieldnames or "target_text" not in reader.fieldnames:
            raise ValueError("CSV must contain source_text,target_text")

        for idx, row in enumerate(reader):
            rows.append((idx, row["source_text"].strip(), row["target_text"].strip()))

    # ---------- GPU inference (SERIAL) ----------
    # predictions = []
    # for idx, src, gt in rows:
    #     pred = run_inference(src)
    #     predictions.append((idx, pred, gt))
    predictions = []

    for idx, src, gt in tqdm(
        rows,
        desc="GPU inference",
        total=len(rows),
        ncols=80
    ):
        pred = run_inference(src)
        predictions.append((idx, pred, gt))


    # ---------- Metrics (PARALLEL CPU) ----------
    results = []
    # with ThreadPoolExecutor(max_workers=8) as pool:
    #     futures = [
    #         pool.submit(process_metrics, idx, pred, gt)
    #         for idx, pred, gt in predictions
    #     ]
    #     for f in as_completed(futures):
    #         results.append(f.result())
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [
            pool.submit(process_metrics, idx, pred, gt)
            for idx, pred, gt in predictions
        ]

        for f in tqdm(
            as_completed(futures),
            total=len(futures),
            desc="Metric computation",
            ncols=80
        ):
            results.append(f.result())

    results.sort(key=lambda x: x["index"])

    # ---------- Write results.csv ----------
    with open(results_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["index", "BCA", "RVA", "perfect"])
        for r in results:
            writer.writerow([
                r["index"],
                f"{r['bca']:.6f}",
                f"{r['rva']:.6f}",
                int(r["perfect"])
            ])

    # ---------- Write non-perfect ----------
    bad = [r for r in results if not r["perfect"]]
    with open(bad_txt, "w") as f:
        for r in bad:
            f.write(f"index={r['index']} BCA={r['bca']:.6f} RVA={r['rva']:.6f}\n")

    # ---------- Summary ----------
    mean_bca = sum(r["bca"] for r in results) / len(results)
    mean_rva = sum(r["rva"] for r in results) / len(results)

    with open(summary_txt, "w") as f:
        f.write(f"Samples           : {len(results)}\n")
        f.write(f"Mean BCA          : {mean_bca:.6f}\n")
        f.write(f"Mean RVA          : {mean_rva:.6f}\n")
        f.write(f"Non-perfect count : {len(bad)}\n")

    print(f"[DONE] Results written to: {out_dir}")

# ============================================================
# 9) ENTRY POINT
# ============================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("Usage: python -m src.inference.my_byt5_inference <csv_path>")
        sys.exit(1)

    run_csv_inference(sys.argv[1])
