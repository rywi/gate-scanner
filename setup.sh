#!/bin/bash
# ─────────────────────────────────────────────────────────────────
# MotoSport Gate Scanner — One-command setup for Ubuntu/Debian
# Usage: bash <(curl -sSL https://raw.githubusercontent.com/rywi/gate-scanner/main/setup.sh)
# ─────────────────────────────────────────────────────────────────
set -euo pipefail

REPO_URL="https://github.com/rywi/gate-scanner.git"
INSTALL_DIR="$HOME/gate-scanner"
SERVICE_NAME="gate-scanner"

echo "══════════════════════════════════════════════════"
echo "  🏍  MotoSport Gate Scanner — Setup"
echo "══════════════════════════════════════════════════"
echo ""

# 1. System packages
echo "[1/5] Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y -qq python3 python3-pip python3-venv git alsa-utils > /dev/null

# 2. Clone or update repo
echo "[2/5] Downloading scanner..."
if [ -d "$INSTALL_DIR/.git" ]; then
    cd "$INSTALL_DIR" && git pull --quiet
else
    git clone --quiet "$REPO_URL" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

SCRIPT_DIR="$INSTALL_DIR"

# 3. Python venv + deps
echo "[3/5] Creating Python environment..."
python3 -m venv venv
source venv/bin/activate
pip install --quiet requests

# 4. Config
CONFIG_FILE="$SCRIPT_DIR/.env"
if [ ! -f "$CONFIG_FILE" ]; then
    echo "[4/5] Creating config (.env)..."
    cat > "$CONFIG_FILE" <<EOF
DEVICE_ID=yoga-gate-1
GATE_ID=gate-main
RESET_DELAY=3
EOF
    echo "  → Edit .env to change device/gate ID"
else
    echo "[4/5] Config .env already exists, skipping."
fi

# 5. Systemd service (auto-start + restart on failure)
echo "[5/5] Installing systemd service..."

CURRENT_USER=$(whoami)
sudo tee /etc/systemd/system/${SERVICE_NAME}.service > /dev/null <<EOF
[Unit]
Description=MotoSport Gate Scanner
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${CURRENT_USER}
WorkingDirectory=${SCRIPT_DIR}
EnvironmentFile=${SCRIPT_DIR}/.env
ExecStart=${SCRIPT_DIR}/venv/bin/python3 ${SCRIPT_DIR}/scanner.py
Restart=on-failure
RestartSec=5
StandardInput=tty
TTYPath=/dev/tty1
TTYReset=yes
TTYVHangup=yes

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable ${SERVICE_NAME}

echo ""
echo "══════════════════════════════════════════════════"
echo "  ✅ Setup complete!"
echo ""
echo "  Run manually (for testing):"
echo "    cd $SCRIPT_DIR"
echo "    source venv/bin/activate"
echo "    python3 scanner.py"
echo ""
echo "  Run as service (auto-start on boot):"
echo "    sudo systemctl start gate-scanner"
echo "    sudo systemctl status gate-scanner"
echo ""
echo "  Logs:"
echo "    journalctl -u gate-scanner -f"
echo ""
echo "  Config: $SCRIPT_DIR/.env"
echo "══════════════════════════════════════════════════"
