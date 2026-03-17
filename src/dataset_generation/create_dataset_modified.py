import argparse
import asyncio
import importlib
import json
import os
import subprocess
import threading
import time
from multiprocessing import Process
from typing import Any

from scapy.all import rdpcap, TCP, Raw  # ← add this

from src.cfg import DATASET_DUMPS, DATASET_PARSED, EXPERIMENTS
from src.dataset_generation.parse import parse_with_file
from src.dataset_generation.split import split
from src.finetune.model.finetuner_model import FinetunerModel


def count_modbus_packets(pcap_path: str) -> int:
    """Count only valid Modbus/TCP packets in a pcap file."""
    try:
        packets = rdpcap(pcap_path)
        count = 0
        for pkt in packets:
            if TCP not in pkt or Raw not in pkt:
                continue
            payload = bytes(pkt[Raw].load)
            if len(payload) < 8:
                continue
            if int.from_bytes(payload[2:4], "big") != 0:  # protocol ID must be 0
                continue
            fc = payload[7]
            if not (1 <= fc <= 127):
                continue
            count += 1
        return count
    except Exception:
        return 0


def parse_packets(port: int, protocol: str, context_length: int, output_filename: str, experiment: str):
    if protocol == "s7comm":
        parse_with_file(protocol, "tpkt", port, "temp", output_filename, context_length, False, experiment)
    else:
        parse_with_file(protocol, protocol, port, "temp", output_filename, context_length, False, experiment)
    split(output_filename, experiment)


async def main(port: int, interface: str, model: str, experiment: str, overwrite: bool = False):
    try:
        connection_ip_addr = "192.168.170.24"
        print(f"Starting experiment {experiment} with model {model} on port {port} and interface {interface} on ip {connection_ip_addr}")

        with open(f"{EXPERIMENTS}/{model}/{experiment}", "r") as cfg:
            config = json.loads(cfg.read())
            finetuner_model = FinetunerModel(experiment, **config)
            finetuner_model.experiment = experiment

        print(f'Passed experiment configuration: {finetuner_model}')

        for i, dataset in enumerate(finetuner_model.datasets):
            print(f'Experiment {dataset} running...')

            if os.path.exists(f"{DATASET_PARSED}/{experiment}/{dataset}.csv") and overwrite is False:
                print(f'Experiment {dataset} already exists. Skipping...')
                continue
            elif overwrite:
                print(f'Experiment {dataset} already exists. Overwriting...')

            finetuner_model.current_dataset = dataset

            if finetuner_model.current_dataset.server:
                server_class_str = ''.join(word.title() for word in finetuner_model.current_dataset.server.name.split('_'))
                client_class_str = ''.join(word.title() for word in finetuner_model.current_dataset.client.split('_'))
                client_class = getattr(
                    importlib.import_module(f"src.dataset_generation.{finetuner_model.current_dataset.protocol}.{finetuner_model.current_dataset.client}"),
                    client_class_str
                )

            pcap_path = f"{DATASET_DUMPS}/temp_{dataset.size}.pcap"

            # Start tshark with NO packet count limit
            tshark_process = subprocess.Popen([
                "tshark",
                "-i", interface,
                "-w", pcap_path,
                "-f", f"tcp port {port}",
            ])
            print(f"Started tshark PID {tshark_process.pid} → {pcap_path}")

            time.sleep(2)  # give tshark time to initialize

            args = getattr(finetuner_model.current_dataset, f"{finetuner_model.current_dataset.protocol}_args")
            print(*args)

            client_inst = client_class(
                connection_ip_addr, port,
                finetuner_model.current_dataset.size,
                finetuner_model.current_dataset.functions,
                finetuner_model.current_dataset.addresses,
                finetuner_model.current_dataset.values,
                finetuner_model.current_dataset.multi_elements
            )

            client_inst.start_client()
            print(f'Client prepared {len(client_inst._functions)} requests.')

            # thread = threading.Thread(target=client_inst.execute_functions, daemon=True)
            thread = threading.Thread(
                target=client_inst.execute_functions,
                kwargs={
                    "delay":       0.01,    # 10ms between requests
                    "batch_size":  200,     # reconnect every 200 requests
                    "batch_pause": 3.0,     # wait 3s between batches
                },
                daemon=True
            )
            thread.start()
            print(f"Client thread started.")
            thread.join()
            print(f"Client thread finished.")

            # Wait for last responses + tshark flush
            time.sleep(3)

            tshark_process.terminate()
            tshark_process.wait()
            print(f"tshark stopped.")

            # ── Verify actual Modbus packet count ──────────────────────────
            modbus_count = count_modbus_packets(pcap_path)
            print(f"\n{'='*50}")
            print(f"  Dataset target  : {dataset.size} Modbus packets")
            print(f"  Modbus captured : {modbus_count}")
            print(f"  Coverage        : {100 * modbus_count // max(dataset.size, 1)}%")

            if modbus_count < dataset.size * 0.8:
                print(f"  ⚠️  WARNING: Less than 80% of target captured!")
                print(f"  Consider re-running this dataset size.")
            else:
                print(f"  ✅ Sufficient Modbus packets captured.")
            print(f"{'='*50}\n")

            print(f'Experiment {dataset} finished.')

    finally:
        if os.path.exists(f"{DATASET_DUMPS}/temp_{dataset.size}.pcap"):
            print("Pcap left for debugging — remove manually from dataset_dumps if needed.")


def init():
    parser = argparse.ArgumentParser()
    parser.add_argument('-p',     default=502,                                    type=int,  required=False)
    parser.add_argument('-intrf', default="Ethernet",                             type=str,  required=False)
    parser.add_argument('-model', default="byt5-small",                           type=str,  required=False)
    parser.add_argument('-exp',   default="s7comm-protocol-emulation.json",       type=str,  required=False)
    parser.add_argument('-o',     default=False,                                  type=bool, required=False)
    args = parser.parse_args()

    asyncio.run(main(
        port=args.p,
        interface=args.intrf,
        model=args.model,
        experiment=args.exp,
        overwrite=args.o
    ))


if __name__ == '__main__':
    init()