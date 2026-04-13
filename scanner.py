#!/usr/bin/env python3
"""
MotoSport Gate Scanner v2 \u2014 USB QR/Barcode reader
Reads QR codes from USB HID scanner, validates via Cloud Function.
Full-screen terminal UI with color feedback + file logging.
"""

import sys
import os
import time
import select
import signal
import logging
import threading
from datetime import datetime
import requests
from urllib.parse import urlparse, parse_qs

# \u2500\u2500 Config \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
GATE_ENDPOINT = "https://europe-west1-moto-862a0.cloudfunctions.net/validateGatePass"
DEVICE_ID = os.environ.get("DEVICE_ID", "yoga-gate-1")
GATE_ID = os.environ.get("GATE_ID", "gate-main")
RESET_DELAY = float(os.environ.get("RESET_DELAY", "3"))
DEBUG = os.environ.get("DEBUG", "1") == "1"  # default ON
DEDUP_SECONDS = float(os.environ.get("DEDUP_SECONDS", "5"))  # ignore same code within N seconds

# \u2500\u2500 Logging to file \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(SCRIPT_DIR, "scanner.log")

logging.basicConfig(
    level=logging.DEBUG if DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ],
)
log = logging.getLogger("gate")

# \u2500\u2500 ANSI colors \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
RST = "\033[0m"
BOLD = "\033[1m"
GREEN_BG = "\033[42;97;1m"
RED_BG = "\033[41;97;1m"
YELLOW = "\033[33;1m"
CYAN = "\033[36m"
DIM = "\033[2m"
GREEN = "\033[32;1m"
RED = "\033[31;1m"


def clear():
    os.system("clear")


def ts():
    return datetime.now().strftime("%H:%M:%S")


def get_terminal_size():
    try:
        cols, rows = os.get_terminal_size()
    except OSError:
        cols, rows = 80, 24
    return cols, rows


def center(text: str, width: int) -> str:
    return text.center(width)


def show_idle(scan_count: int = 0):
    clear()
    cols, rows = get_terminal_size()
    mid = rows // 2
    lines = []
    lines.append(f"{CYAN}{BOLD}\U0001f3cd  MOTOSPORT GATE SCANNER  \U0001f3cd{RST}")
    lines.append("")
    lines.append(f"{GREEN}\u25cf GOTOWY{RST} \u2014 czekam na skan...")
    lines.append("")
    lines.append(f"{DIM}Device: {DEVICE_ID} | Gate: {GATE_ID}{RST}")
    lines.append(f"{DIM}Skan\u00f3w: {scan_count} | Czas: {ts()}{RST}")
    lines.append(f"{DIM}Log: {LOG_FILE}{RST}")
    lines.append(f"{DIM}Ctrl+C = wyj\u015bcie{RST}")

    print("\n" * max(0, mid - len(lines) // 2 - 1))
    for line in lines:
        print(center(line, cols + 20))

    log.debug("Idle screen \u2014 waiting for scanner input")


def show_result(allowed: bool, reason: str, extra: str = ""):
    clear()
    cols, rows = get_terminal_size()
    mid = rows // 2
    print("\n" * max(0, mid - 4))
    if allowed:
        bg = GREEN_BG
        icon = "\u2705"
        label = "WJAZD OK"
    else:
        bg = RED_BG
        icon = "\u274c"
        label = "ODMOWA"
    print(center(f"{bg}  {icon}  {label}  {icon}  {RST}", cols + 30))
    print()
    print(center(f"{BOLD}{reason}{RST}", cols + 10))
    if extra:
        print(center(f"{DIM}{extra}{RST}", cols + 10))
    print()
    print(center(f"{DIM}Reset za {RESET_DELAY:.0f}s...{RST}", cols + 10))


def play_sound(ok: bool):
    """Play beep via system speaker."""
    try:
        if ok:
            os.system("(speaker-test -t sine -f 880 -l 1 & pid=$!; sleep 0.15; kill $pid) 2>/dev/null")
            os.system("(speaker-test -t sine -f 1100 -l 1 & pid=$!; sleep 0.15; kill $pid) 2>/dev/null")
        else:
            os.system("(speaker-test -t sine -f 220 -l 1 & pid=$!; sleep 0.5; kill $pid) 2>/dev/null")
    except Exception:
        pass


def parse_qr(qr_data: str):
    """Extract passId and token from QR URL. Handles concatenated URLs from rapid scanning."""
    qr_data = qr_data.strip()
    log.debug(f"Raw input ({len(qr_data)} chars): {qr_data[:120]}")

    # Handle concatenated URLs \u2014 scanner in continuous mode may glue them together
    # Split on "https://" and take only the FIRST valid one
    if qr_data.count("https://") > 1:
        parts = qr_data.split("https://")
        # parts[0] is empty string before first https://
        qr_data = "https://" + parts[1]
        log.info(f"Split concatenated input ({len(parts)-1} URLs), using first: {qr_data[:80]}")

    try:
        parsed = urlparse(qr_data)
        params = parse_qs(parsed.query)
        pass_id = params.get("p", [None])[0]
        token = params.get("t", [None])[0]
        if pass_id and token:
            log.info(f"Parsed OK \u2014 passId={pass_id[:8]}... token={token[:8]}...")
        else:
            log.warning(f"Missing p or t in URL: {qr_data[:80]}")
        return pass_id, token
    except Exception as e:
        log.error(f"Parse error: {e}")
        return None, None


def validate(pass_id: str, token: str) -> dict:
    """Call Cloud Function to validate gate pass."""
    log.info(f"Calling API \u2014 passId={pass_id[:8]}...")
    t0 = time.time()
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
        data = resp.json()
        elapsed = time.time() - t0
        log.info(f"API response ({elapsed:.1f}s): allowed={data.get('allowed')} reason={data.get('reason')}")
        return data
    except requests.Timeout:
        log.error("API TIMEOUT (8s)")
        return {"allowed": False, "reason": "TIMEOUT", "passStatus": "unknown"}
    except Exception as e:
        log.error(f"API error: {e}")
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


def flush_stdin():
    """Discard any buffered stdin input (from rapid scanning during processing)."""
    import termios
    try:
        termios.tcflush(sys.stdin, termios.TCIFLUSH)
        log.debug("Flushed stdin buffer")
    except Exception:
        # Fallback: read available data without blocking
        try:
            while select.select([sys.stdin], [], [], 0)[0]:
                sys.stdin.readline()
                log.debug("Flushed 1 queued line from stdin")
        except Exception:
            pass


def main():
    scan_count = 0
    last_pass_id = None
    last_scan_time = 0.0
    processing = threading.Lock()

    signal.signal(signal.SIGINT, lambda *_: (log.info(f"Shutdown \u2014 {scan_count} scans total"), print(f"\n{RST}Bye!"), sys.exit(0)))

    log.info("=" * 60)
    log.info(f"STARTUP \u2014 device={DEVICE_ID} gate={GATE_ID} debug={DEBUG}")
    log.info(f"Endpoint: {GATE_ENDPOINT}")
    log.info(f"Reset delay: {RESET_DELAY}s, Dedup: {DEDUP_SECONDS}s")

    # \u2500\u2500 Startup info (visible before fullscreen) \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
    print(f"{BOLD}MotoSport Gate Scanner v2{RST}")
    print(f"{'\u2500' * 40}")
    print(f"Endpoint: {GATE_ENDPOINT}")
    print(f"Device:   {DEVICE_ID}")
    print(f"Gate:     {GATE_ID}")
    print(f"Debug:    {'ON' if DEBUG else 'OFF'}")
    print(f"Dedup:    {DEDUP_SECONDS}s")
    print(f"Log:      {LOG_FILE}")
    print(f"{'\u2500' * 40}")
    print()

    # Test connectivity with real request
    print(f"{DIM}Sprawdzam po\u0142\u0105czenie z serwerem...{RST}")
    try:
        t0 = time.time()
        resp = requests.post(GATE_ENDPOINT, json={"passId": "test", "token": "test"}, timeout=5)
        elapsed = time.time() - t0
        print(f"{GREEN_BG} ONLINE {RST} Serwer OK ({elapsed:.1f}s, HTTP {resp.status_code})")
        log.info(f"Connectivity OK ({elapsed:.1f}s)")
    except Exception as e:
        print(f"{RED_BG} OFFLINE {RST} Brak po\u0142\u0105czenia!")
        print(f"  {RED}{e}{RST}")
        log.error(f"Connectivity FAILED: {e}")

    print()
    print(f"{YELLOW}USB skaner gotowy \u2014 czekam na dane...{RST}")
    print(f"{DIM}Skaner HID = wpisuje tekst + Enter automatycznie.{RST}")
    print(f"{DIM}Mo\u017cesz te\u017c wklei\u0107/wpisa\u0107 URL r\u0119cznie do testu.{RST}")
    print()
    time.sleep(2)
    show_idle(scan_count)

    while True:
        try:
            # USB HID scanner sends text + Enter = readline
            qr_data = input()
        except EOFError:
            log.info("EOF \u2014 exiting")
            break

        if not qr_data.strip():
            continue

        # \u2500\u2500 Prevent processing overlap \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
        if not processing.acquire(blocking=False):
            log.debug("Skipped input \u2014 still processing previous scan")
            continue

        try:
            scan_count += 1
            log.info(f"{'\u2500' * 40}")
            log.info(f"SCAN #{scan_count} \u2014 input: {qr_data[:100]}")

            pass_id, token = parse_qr(qr_data)

            if not pass_id or not token:
                msg = f"Nieprawid\u0142owy format (skan #{scan_count})"
                show_result(False, msg, f"Otrzymano: {qr_data[:60]}")
                log.warning(f"DENIED \u2014 invalid format, scan #{scan_count}")
                play_sound(False)
                time.sleep(RESET_DELAY)
                flush_stdin()
                show_idle(scan_count)
                continue

            # \u2500\u2500 Dedup: ignore same passId within DEDUP_SECONDS \u2500\u2500\u2500\u2500\u2500\u2500
            now = time.time()
            if pass_id == last_pass_id and (now - last_scan_time) < DEDUP_SECONDS:
                elapsed_since = now - last_scan_time
                log.info(f"DEDUP \u2014 same passId={pass_id[:8]}... ({elapsed_since:.1f}s ago), skipping")
                flush_stdin()
                show_idle(scan_count)
                continue

            last_pass_id = pass_id
            last_scan_time = now

            # \u2500\u2500 Validate \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
            data = validate(pass_id, token)
            allowed = data.get("allowed", False)
            reason = data.get("reason", "UNKNOWN")
            human_reason = DENY_MESSAGES.get(reason, reason)

            extra = f"Skan #{scan_count} | {ts()}"
            if allowed and data.get("validUntil"):
                extra += f" | Wa\u017cny do: {data['validUntil'][:16].replace('T', ' ')}"

            log.info(f"RESULT: {'ALLOWED' if allowed else 'DENIED'} \u2014 reason={reason}")

            show_result(allowed, human_reason if not allowed else "Bilet wa\u017cny \u2713", extra)
            play_sound(allowed)
            time.sleep(RESET_DELAY)

            # Flush any scans that came in while showing result
            flush_stdin()
            show_idle(scan_count)

        finally:
            processing.release()


if __name__ == "__main__":
    main()
