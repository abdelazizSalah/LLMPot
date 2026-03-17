import subprocess
import sys
import os


PIPELINE = [
    {
        "name":    "Step 1 — Dataset Generation",
        "command": [
            # sys.executable, "-m", "src.dataset_generation.create_dataset",
            # "-exp", "CustomGeneration-mbtcp-protocol-emulation-c0-400_800_1600_ReadOnlyFunc.json"
            sys.executable, "-m", "src.dataset_generation.create_dataset_modified",
            "-exp", "CustomGeneration-mbtcp-protocol-emulation-c0-400_800_1600.json"
        ],
    },
    {
        "name":    "Step 2 — Modbus/TCP Filter",
        "command": [sys.executable, "-m", "outputs.datasets.dumps.modbus_tcp_extractor"],
    },
    {
        "name":    "Step 3 — Correlate Pairs",
        "command": [sys.executable, "-m", "outputs.datasets.dumps.correlate_filtered_pcaps"],
    },
]


def run_pipeline():
    print(f"\n{'='*60}")
    print(f"  LLMPot Dataset Pipeline")
    print(f"  Working dir: {os.getcwd()}")
    print(f"{'='*60}\n")

    for i, step in enumerate(PIPELINE):
        print(f"\n{'─'*60}")
        print(f"  [{i+1}/{len(PIPELINE)}] {step['name']}")
        print(f"  CMD: {' '.join(step['command'])}")
        print(f"{'─'*60}\n")

        result = subprocess.run(step["command"])

        if result.returncode != 0:
            print(f"\n❌ Pipeline failed at step {i+1}: {step['name']}")
            print(f"   Exit code: {result.returncode}")
            print(f"   Stopping pipeline.")
            sys.exit(result.returncode)

        print(f"\n✅ Step {i+1} completed successfully.")

    print(f"\n{'='*60}")
    print(f"  ✅ Pipeline completed successfully!")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    run_pipeline()