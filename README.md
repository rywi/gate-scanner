# MotoSport Gate Scanner 🏍

Standalone QR gate scanner for Ubuntu/Debian. Reads USB barcode/QR scanner (HID keyboard mode), validates tickets via MotoSport Cloud Function.

## One-command setup

```bash
bash <(curl -sSL https://raw.githubusercontent.com/rywi/gate-scanner/main/setup.sh)
```

Or manually:

```bash
git clone https://github.com/rywi/gate-scanner.git
cd gate-scanner
bash setup.sh
```

## How it works

1. USB QR scanner acts as keyboard — scans QR code → types URL + Enter
2. Python script reads the input, extracts `passId` and `token` from URL
3. Calls `validateGatePass` Cloud Function
4. Shows full-screen green **WJAZD OK** or red **ODMOWA** in terminal
5. Plays beep sound (speaker-test)
6. Auto-resets after 3 seconds

## Manual run (testing)

```bash
cd ~/gate-scanner
source venv/bin/activate
python3 scanner.py
```

Then paste a QR URL to test:

```
https://moto-862a0.web.app/bilet?p=PASS_ID&t=RAW_TOKEN
```

## Auto-start as service

```bash
sudo systemctl start gate-scanner
sudo systemctl status gate-scanner
journalctl -u gate-scanner -f
```

## Config (.env)

| Variable | Default | Description |
|----------|---------|-------------|
| `DEVICE_ID` | `yoga-gate-1` | Device identifier (logged server-side) |
| `GATE_ID` | `gate-main` | Gate identifier |
| `RESET_DELAY` | `3` | Seconds before screen resets to idle |

## Requirements

- Ubuntu/Debian with Python 3
- USB QR/Barcode scanner (HID keyboard mode)
- Internet connection
