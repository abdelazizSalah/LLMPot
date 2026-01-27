#!/usr/bin/env python3
r"""
LLMPot WDT pipeline automation (Windows paths).

What it does:
1) Accept: pcap filename, output csv name, context length, experiment_folder_name, max_iteration
2) Run parse step in conda env "llmpot"
3) Create experiment folders in outputs/datasets/{train,validation,test}/<experiment_name>
4) Move parsed CSV splits from parsed_custom/<experiment_name>/ to those folders
5) Run WDT main_Configuration_extractor.py in the WDT pcap directory
6) Read the generated *_modbus_summary.txt and extract Modbus summary fields
7) Create experiments/byt5-small/<experiment_name>.json with those extracted fields

Usage example (PowerShell):
python .\run_llmpot_wdt_pipeline.py `
  --pcap "E:\GitHub\LLMPot\Modbus_dataset\WDT\WDT\Network_dataset\pcap\capture.pcap" `
  --out-csv "mbtcp-client-c0-s10000.csv" `
  --context-len 512 `
  --experiment-name "wdt-dataset-mbtcp-protocol-emulation-attack1-c0-10000" `
  --max-iteration 10000
"""

from __future__ import annotations

import argparse
import json
from locale import currency
import re
import shutil
import subprocess
from pathlib import Path
from typing import List, Tuple


# ---------------------------
# Config: adjust if your repo layout differs
# ---------------------------

# get the current working directory
curr_dir = Path.cwd()
LLMPOT_ROOT = Path(f"{curr_dir}")
OUTPUTS_DIR = LLMPOT_ROOT / "outputs" / "datasets"
PARSED_CUSTOM_DIR = OUTPUTS_DIR / "parsed_custom"
TRAIN_DIR = OUTPUTS_DIR / "train"
VAL_DIR = OUTPUTS_DIR / "validation"
TEST_DIR = OUTPUTS_DIR / "test"

WDT_PCAP_DIR = LLMPOT_ROOT / "Modbus_dataset" / "WDT" / "WDT" / "Network_dataset" / "pcap"
CONFIG_EXTRACTOR = WDT_PCAP_DIR / "main_Configuration_extractor.py"

EXPERIMENTS_BYT5_DIR = LLMPOT_ROOT / "experiments" / "byt5-small"

CONDA_ENV_NAME = "llmpot"

import time

def run_cmd_capture(cmd: list[str], cwd: Path | None = None) -> str:
    """Run command and return combined stdout/stderr (also prints live)."""
    print(f"\n[RUN] {' '.join(cmd)}")
    proc = subprocess.Popen(
        cmd,
        cwd=str(cwd) if cwd else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        universal_newlines=True,
    )
    assert proc.stdout is not None
    out_lines = []
    for line in proc.stdout:
        print(line, end="")
        out_lines.append(line)
    rc = proc.wait()
    if rc != 0:
        raise subprocess.CalledProcessError(rc, cmd, output="".join(out_lines))
    return "".join(out_lines)


def find_latest_run_id(checkpoints_dir: Path) -> str:
    """
    Find the run folder name like YYYYMMDDThhmm... inside checkpoints_dir.
    Returns the newest by filesystem mtime.
    """
    if not checkpoints_dir.exists():
        raise FileNotFoundError(f"Checkpoints dir not found: {checkpoints_dir}")

    candidates = [p for p in checkpoints_dir.iterdir() if p.is_dir() and re.match(r"^\d{8}T\d{4}", p.name)]
    if not candidates:
        # show debug listing
        kids = [p.name for p in checkpoints_dir.iterdir()]
        raise FileNotFoundError(
            f"No run-id folders (YYYYMMDDThhmm) found under: {checkpoints_dir}\n"
            f"Found: {kids}"
        )

    latest = max(candidates, key=lambda p: p.stat().st_mtime)
    return latest.name


def create_plot_script(exp_name: str, run_id: str, plots_dir: Path) -> Path:
    """
    Create src/plots/mbtcp/bca_rva_wdt_<experiment_name>.py with the template.
    """
    ensure_dir(plots_dir)
    # make a safe python module name (hyphens not allowed)
    safe_exp = re.sub(r"[^0-9a-zA-Z_]", "_", exp_name)
    script_name = f"bca_rva_wdt_{safe_exp}.py"
    script_path = plots_dir / script_name

    content = f"""from src.plots.from_csv import NATURE, Plots

    plot = Plots("{exp_name}", "{run_id}")
    colors = {{dataset.functions_str(): NATURE[i] for i, dataset in enumerate(plot.finetuner.datasets)}}
    labels = [dataset.functions_str() for dataset in plot.finetuner.datasets]
    plot.accuracy_per_epoch(colors, labels)
    plot.loss_per_epoch(colors, labels)
    """
    script_path.write_text(content, encoding="utf-8")
    print(f"[PLOT] wrote: {script_path}")
    return script_path



def run_cmd(cmd: List[str], cwd: Path | None = None) -> None:
    """Run a command, streaming output; raise on error."""
    print(f"\n[RUN] {' '.join(cmd)}")
    subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=True)


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def move_split_files(parsed_exp_dir: Path, exp_name: str) -> Tuple[int, int, int]:
    """
    Move:
      *train.csv -> outputs/datasets/train/<exp_name>/
      *val.csv   -> outputs/datasets/validation/<exp_name>/
      *test.csv  -> outputs/datasets/test/<exp_name>/
    Returns counts moved.
    """
    train_dest = TRAIN_DIR / exp_name
    val_dest = VAL_DIR / exp_name
    test_dest = TEST_DIR / exp_name

    for d in (train_dest, val_dest, test_dest):
        ensure_dir(d)

    train_files = list(parsed_exp_dir.glob("*train.csv"))
    val_files = list(parsed_exp_dir.glob("*val.csv"))
    test_files = list(parsed_exp_dir.glob("*test.csv"))

    def _move(files: List[Path], dest: Path) -> int:
        n = 0
        for f in files:
            target = dest / f.name
            print(f"[MOVE] {f} -> {target}")
            shutil.move(str(f), str(target))
            n += 1
        return n

    return _move(train_files, train_dest), _move(val_files, val_dest), _move(test_files, test_dest)


def parse_modbus_summary(summary_path: Path) -> dict:
    """
    Extracts from the section:
    === MODBUS/TCP PCAP SUMMARY ===
    function_codes: [1, 3, 5, 6]
    min_value: 0
    max_value: 24
    min_address: 1
    max_address: 49
    sc: 26
    sr: 5
    """
    text = summary_path.read_text(encoding="utf-8", errors="replace")

    # Grab the MODBUS/TCP SUMMARY section (until next === ... === or EOF)
    m = re.search(
        r"===\s*MODBUS/TCP PCAP SUMMARY\s*===\s*(.*?)(?:\n===|\Z)",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if not m:
        raise ValueError(f"Could not find MODBUS/TCP summary section in: {summary_path}")

    block = m.group(1)

    def _get_int(key: str) -> int:
        mm = re.search(rf"{re.escape(key)}\s*:\s*([0-9]+)\s*$", block, flags=re.MULTILINE)
        if not mm:
            raise ValueError(f"Missing '{key}:' in summary block.")
        return int(mm.group(1))

    fc_m = re.search(r"function_codes\s*:\s*\[([^\]]+)\]", block)
    if not fc_m:
        raise ValueError("Missing 'function_codes: [...]' in summary block.")
    function_codes = [int(x.strip()) for x in fc_m.group(1).split(",") if x.strip()]

    out = {
        "function_codes": function_codes,
        "min_value": _get_int("min_value"),
        "max_value": _get_int("max_value"),
        "min_address": _get_int("min_address"),
        "max_address": _get_int("max_address"),
        "sc": _get_int("sc"),
        "sr": _get_int("sr"),
    }
    return out


def write_experiment_json(
    exp_name: str,
    context_len: int,
    size: int,
    summary_vals: dict,
    out_path: Path,
) -> None:
    payload = {
        "model_type": "google",
        "model_name": "byt5-small",
        "max_epochs": 30,
        "target_max_token_len": 512,
        "source_max_token_len": 512,
        "batch_size": 1,
        "datasets": [
            {
                "protocol": "mbtcp",
                "size": size,
                "client": "client",
                "functions": summary_vals["function_codes"],
                "values": {"low": summary_vals["min_value"], "high": summary_vals["max_value"]},
                "addresses": {"low": summary_vals["min_address"], "high": summary_vals["max_address"]},
                "server": {
                    "name": "no_logic_server",
                    "coils": summary_vals["sc"],
                    "registers": summary_vals["sr"],
                },
                "context": context_len,
            }
        ],
    }

    ensure_dir(out_path.parent)
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"[JSON] wrote: {out_path}")


def resolve_pcap_path(pcap_arg: str) -> Path:
    p = Path(pcap_arg)
    if p.exists():
        return p

    # If user passed "attack_1" (no extension), try dumps/<name>.pcap
    candidate = LLMPOT_ROOT / "outputs" / "datasets" / "dumps" / f"{pcap_arg}.pcap"
    if candidate.exists():
        return candidate

    # If user passed "attack_1.pcap" but not a full path, try dumps/<name>
    candidate2 = LLMPOT_ROOT / "outputs" / "datasets" / "dumps" / p.name
    if candidate2.exists():
        return candidate2

    raise FileNotFoundError(
        f"PCAP not found. Tried:\n"
        f"- {p.resolve()}\n"
        f"- {candidate}\n"
        f"- {candidate2}\n"
        f"Pass a full path, or put the file in outputs/datasets/dumps/"
    )


def main() -> None:
    r'''
    Example
     python .\wdt_training_script.py --pcap attack_1 --csv wdt_attack_1_c1_10000 --p 502  --clen 1 --exp wdt_attack1_c1_10000 --max_iter 10000
    '''

    ap = argparse.ArgumentParser()
    ap.add_argument("--max_iter", required=True, type=int, help="max_iter / max_iteration")
    ap.add_argument("--exp", required=True, help="Experiment folder name (exp)")
    args = ap.parse_args()



    exp_name = args.exp
        # ---------------------------
    # 10) Fine-tune (multi_trainer)
    # ---------------------------
    # NOTE: command you requested had typos; using corrected module path: src.finetune.multi_trainer
    cfg_path = EXPERIMENTS_BYT5_DIR / f"{exp_name}.json"
    if not cfg_path.exists():
        raise FileNotFoundError(f"Config JSON not found: {cfg_path}")

    # Fine-tune
    run_cmd(
        [
            "python", "-u", "-m", "src.finetune.multi_trainer",
            "-p", f"{args.max_iter}:1",
            "-model", "byt5-small",
            "-cfg", str(cfg_path),
        ],
        cwd=LLMPOT_ROOT,
    )

    # ---------------------------
    # 11) Compute results (BCA/RVA)
    # ---------------------------
    run_cmd(
        [
            "python", "-u", "-m", "src.results.bca_rva_per_model_size",
            "-model", "byt5-small",
            "-cfg", str(cfg_path),
        ],
        cwd=LLMPOT_ROOT,
    )

    # ---------------------------
    # 12) Discover checkpoint run id
    # ---------------------------
    ckpt_root = LLMPOT_ROOT / "checkpoints" / "byt5-small" / exp_name
    run_id = find_latest_run_id(ckpt_root)
    print(f"[CKPT] latest run id: {run_id}")

    # ---------------------------
    # 13) Generate plot script + run it
    # ---------------------------
    plots_dir = LLMPOT_ROOT / "src" / "plots" / "mbtcp"
    plot_script = create_plot_script(exp_name, run_id, plots_dir)

    # Run as module: src.plots.mbtcp.<module_name_without_py>
    module_name = plot_script.stem  # bca_rva_wdt_<safe_exp>
    run_cmd(
        [
            "conda", "run", "-n", CONDA_ENV_NAME,
            "python", "-u", "-m", f"src.plots.mbtcp.{module_name}",
        ],
        cwd=LLMPOT_ROOT,
    )



    print("\n[DONE] Pipeline finished successfully.")


if __name__ == "__main__":
    main()
