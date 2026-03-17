import socket
import time

IP   = "192.168.170.24"
PORT = 502
TID  = 0x0001
UNIT = 0xFF  # 255

def send_request(fc: int, start_address: int, quantity: int) -> bytes | None:
    """Send a Modbus request and return raw response bytes."""
    # Build MBAP header + PDU
    pdu = bytes([fc]) + start_address.to_bytes(2, "big") + quantity.to_bytes(2, "big")
    length = 1 + len(pdu)  # unit_id + pdu
    mbap = (
        TID.to_bytes(2, "big") +        # Transaction ID
        b'\x00\x00' +                    # Protocol ID
        length.to_bytes(2, "big") +      # Length
        bytes([UNIT])                    # Unit ID
    )
    payload = mbap + pdu

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(3)
        try:
            s.connect((IP, PORT))
            s.sendall(payload)
            return s.recv(1024)
        except Exception:
            return None


def is_exception(response: bytes) -> tuple[bool, int]:
    """Returns (is_exception, exception_code)."""
    if not response or len(response) < 9:
        return True, -1
    fc = response[7]
    if fc > 127:
        return True, response[8]
    return False, 0


def scan_addresses(fc: int, fc_name: str, max_address: int = 2000, step: int = 1):
    """
    Scan all addresses for a given FC to find which ones are valid.
    Returns (first_valid, last_valid, total_valid_count)
    """
    print(f"\n{'='*60}")
    print(f"  Scanning FC{fc} — {fc_name}")
    print(f"  Range: 0 to {max_address}, step={step}")
    print(f"{'='*60}")

    valid_addresses  = []
    first_valid      = None
    last_valid       = None

    for addr in range(0, max_address + 1, step):
        response = send_request(fc, addr, 1)

        if response is None:
            print(f"  [{addr:>6}] No response (timeout)")
            time.sleep(0.5)
            continue

        exc, code = is_exception(response)

        if not exc:
            valid_addresses.append(addr)
            if first_valid is None:
                first_valid = addr
            last_valid = addr
            if addr % 100 == 0 or addr == 0:
                print(f"  [{addr:>6}] ✅ Valid")
        else:
            # Exception code 2 = Illegal Data Address (out of range)
            # Exception code 1 = Illegal Function (FC not supported at all)
            if code == 1:
                print(f"  [{addr:>6}] ❌ FC not supported — stopping scan.")
                break
            # code 2 = just this address is invalid, continue scanning

        time.sleep(0.01)  # small delay between requests

    return first_valid, last_valid, valid_addresses


def discover_modbus_map():
    print(f"\n{'#'*60}")
    print(f"  OPTA Modbus TCP Address Discovery")
    print(f"  Target: {IP}:{PORT}  Unit ID: {UNIT}")
    print(f"{'#'*60}")

    results = {}

    # FC1 — Read Coils
    first, last, valid = scan_addresses(1, "Read Coils", max_address=200)
    results["coils"] = {"first": first, "last": last, "count": len(valid), "addresses": valid}

    # FC2 — Read Discrete Inputs
    first, last, valid = scan_addresses(2, "Read Discrete Inputs", max_address=200)
    results["discrete_inputs"] = {"first": first, "last": last, "count": len(valid), "addresses": valid}

    # FC3 — Read Holding Registers
    first, last, valid = scan_addresses(3, "Read Holding Registers", max_address=200)
    results["holding_registers"] = {"first": first, "last": last, "count": len(valid), "addresses": valid}

    # FC4 — Read Input Registers
    first, last, valid = scan_addresses(4, "Read Input Registers", max_address=200)
    results["input_registers"] = {"first": first, "last": last, "count": len(valid), "addresses": valid}

    # ── Print Summary ──────────────────────────────────────────
    print(f"\n{'#'*60}")
    print(f"  DISCOVERY RESULTS")
    print(f"{'#'*60}\n")

    area_map = {
        "coils":             ("FC1/FC5/FC15",  "Coils"),
        "discrete_inputs":   ("FC2",           "Discrete Inputs"),
        "holding_registers": ("FC3/FC6/FC16",  "Holding Registers"),
        "input_registers":   ("FC4",           "Input Registers"),
    }

    for key, (fcs, label) in area_map.items():
        r = results[key]
        if r["first"] is None:
            print(f"  {label:<25} ({fcs}): ❌ No valid addresses found")
        else:
            print(f"  {label:<25} ({fcs}): ✅ {r['count']} addresses  [{r['first']} → {r['last']}]")

    # ── Print recommended JSON config ──────────────────────────
    print(f"\n{'#'*60}")
    print(f"  RECOMMENDED JSON CONFIG")
    print(f"{'#'*60}\n")

    coil_high = results["coils"]["last"]       or 0
    reg_high  = results["holding_registers"]["last"] or 0

    print(f'''{{
  "addresses": {{
    "low": 0,
    "high": {max(coil_high, reg_high)}
  }},
  "server": {{
    "coils":     {results["coils"]["count"]},
    "registers": {results["holding_registers"]["count"]}
  }}
}}''')

    print(f"\n  ⚠️  Set addresses.high to the LOWEST of:")
    print(f"      coil last address     : {coil_high}")
    print(f"      register last address : {reg_high}")
    print(f"      → Use: {min(coil_high, reg_high) if coil_high and reg_high else 'N/A'}")

    return results


if __name__ == "__main__":
    discover_modbus_map()