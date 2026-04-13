#!/usr/bin/env python3
"""
MotoSport Gate Scanner — USB QR/Barcode reader
Reads QR codes from USB HID scanner, validates via Cloud Function.
Full-screen terminal UI with color feedback.
"""

import sys
import os
import time
import signal
import requests
from urllib.parse import urlparse, parse_qs

# ── Config ──────────────────────────────────────────────────────────────────
GATE_ENDPOINT = "https://europe-west1-moto-862a0.cloudfunctions.net/validateGatePass"
DEVICE_ID = os.environ.get("DEVICE_ID", "yoga-gate-1")
GATE_ID = os.environ.get("GATE_ID", "gate-main")
RESET_DELAY = float(os.environ.get("RESET_DELAY", "3"))  # seconds before reset

# ── ANSI colors ─────────────────────────────────────────────────────────────
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN_BG = "\033[42;97;1m"   # green bg, white text, bold
RED_BG = "\033[41;97;1m"     # red bg, white text, bold
YELLOW = "\033[33;1m"
CYAN = "\033[36m"
DIM = "\033[2m"


def clear():
    os.system("clear")


def center(text: str, width: int) -> str:
    return text.center(width)


def get_terminal_size():
    try:
        cols, rows = os.get_terminal_size()
    except OSError:
        cols, rows = 80, 24
    return cols, rows


def show_idle():
    clear()
    cols, rows = get_terminal_size()
    mid = rows // 2
    print("\n" * (mid - 3))
    print(center(f"{CYAN}{BOLD}\U0001f3cd  MOTOSPORT GATE SCANNER  \U0001f3cd{RESET}", cols + 20))
    print()
    print(center(f"{DIM}Zeskanuj kod QR biletu...{RESET}", cols + 10))
    print()
    print(center(f"{DIM}Device: {DEVICE_ID} | Gate: {GATE_ID}{RESET}", cols + 10))
    print(center(f"{DIM}Ctrl+C aby zako\u0144czy\u0107{RESET}", cols + 10))


def show_result(allowed: bool, reason: str, extra: str = ""):
    clear()
    cols, rows = get_terminal_size()
    mid = rows // 2
    print("\n" * (mid - 3))
    if allowed:
        bg = GREEN_BG
        icon = "\u2705"
        label = "WJAZD OK"
    else:
        bg = RED_BG
        icon = "\u274c"
        label = "ODMOWA"
    print(center(f"{bg}  {icon}  {label}  {icon}  {RESET}", cols + 30))
    print()
    print(center(f"{BOLD}{reason}{RESET}", cols + 10))
    if extra:
        print(center(f"{DIM}{extra}{RESET}", cols + 10))


def play_sound(ok: bool):
    """Play beep via system speaker (optional)."""
    try:
        if ok:
            os.system("(speaker-test -t sine -f 880 -l 1 & pid=$!; sleep 0.15; kill $pid) 2>/dev/null")
            os.system("(speaker-test -t sine -f 1100 -l 1 & pid=$!; sleep 0.15; kill $pid) 2>/dev/null")
        else:
            os.system("(speaker-test -t sine -f 220 -l 1 & pid=$!; sleep 0.5; kill $pid) 2>/dev/null")
    except Exception:
        pass


def parse_qr(qr_data: str):
    """Extract passId and token from QR URL."""
    qr_data = qr_data.strip()
    try:
        parsed = urlparse(qr_data)
        params = parse_qs(parsed.query)
        pass_id = params.get("p", [None])[0]
        token = params.get("t", [None])[0]
        return pass_id, token
    except Exception:
        return None, None


def validate(pass_id: str, token: str) -> dict:
    """Call Cloud Function to validate gate pass."""
    try:
        resp = requests.post(
            GATE_ENDPOINT,
            json={
                "passId": pass_id,
                "token": token,
                "deviceId": DEVICE_ID,
                "gateId": GATE_ID,
            },
            timeout=8,
        )
        return resp.json()
    except requests.Timeout:
        return {"allowed": False, "reason": "TIMEOUT", "passStatus": "unknown"}
    except Exception as e:
        return {"allowed": False, "reason": f"ERROR: {e}", "passStatus": "unknown"}


DENY_MESSAGES = {
    "PASS_REVOKED": "Bilet uniewa\u017cniony",
    "PASS_USED": "Bilet ju\u017c wykorzystany",
    "PASS_EXPIRED": "Bilet wygas\u0142",
    "INVALID_TOKEN": "Nieprawid\u0142owy kod",
    "PASS_NOT_FOUND": "Nieznany bilet",
    "NOT_YET_VALID": "Bilet nieaktywny",
    "MAX_SCANS_REACHED": "Przekroczono limit",
    "MISSING_PASS_ID": "B\u0142\u0105d: brak ID",
    "MISSING_TOKEN": "B\u0142\u0105d: brak tokenu",
    "TIMEOUT": "Brak po\u0142\u0105czenia z serwerem",
}


def main():
    signal.signal(signal.SIGINT, lambda *_: (print(f"\n{RESET}Bye!"), sys.exit(0)))

    print(f"{BOLD}MotoSport Gate Scanner starting...{RESET}")
    print(f"Endpoint: {GATE_ENDPOINT}")
    print(f"Device: {DEVICE_ID} | Gate: {GATE_ID}")
    print()

    # Test connectivity
    try:
        requests.head(GATE_ENDPOINT, timeout=5)
        print(f"{GREEN_BG} ONLINE {RESET} Po\u0142\u0105czenie z serwerem OK")
    except Exception:
        print(f"{RED_BG} OFFLINE {RESET} Brak po\u0142\u0105czenia \u2014 sprawd\u017a internet!")

    time.sleep(1)
    show_idle()

    while True:
        try:
            # USB HID scanner sends text + Enter key = readline
            qr_data = input()
        except EOFError:
            break

        if not qr_data.strip():
            continue

        pass_id, token = parse_qr(qr_data)

        if not pass_id or not token:
            show_result(False, "Nieprawid\u0142owy format QR", qr_data[:60])
            play_sound(False)
            time.sleep(RESET_DELAY)
            show_idle()
            continue

        # Validate
        data = validate(pass_id, token)
        allowed = data.get("allowed", False)
        reason = data.get("reason", "UNKNOWN")
        human_reason = DENY_MESSAGES.get(reason, reason)

        extra = ""
        if allowed and data.get("validUntil"):
            extra = f"Wa\u017cny do: {data['validUntil'][:16].replace('T', ' ')}"

        show_result(allowed, human_reason if not allowed else "Bilet wa\u017cny \u2713", extra)
        play_sound(allowed)
        time.sleep(RESET_DELAY)
        show_idle()


if __name__ == "__main__":
    main()
