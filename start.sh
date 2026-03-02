#!/usr/bin/env bash
# Pressure Matrix Startup Script
# Checks ESP32 connection, fixes permissions, optionally compiles/uploads, and launches GUI.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SERIAL_PORT="/dev/ttyACM0"
BAUD_RATE=115200
FQBN="esp32:esp32:esp32s3:PSRAM=opi,FlashSize=16M,PartitionScheme=app3M_fat9M_16MB"
SKETCH_DIR="$SCRIPT_DIR/tests/t7_6x6"
GUI_DIR="$SCRIPT_DIR/tests/gui"
BIN_DIR="$SCRIPT_DIR/bin"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

ok()   { echo -e "  ${GREEN}[OK]${NC} $1"; }
fail() { echo -e "  ${RED}[FAIL]${NC} $1"; }
warn() { echo -e "  ${YELLOW}[WARN]${NC} $1"; }

echo "==========================================="
echo " Pressure Matrix - Startup"
echo "==========================================="
echo ""

# --- 1. Check serial port ---
echo "1) Checking serial port..."
if [ -e "$SERIAL_PORT" ]; then
    ok "$SERIAL_PORT exists"
else
    fail "$SERIAL_PORT not found"
    echo ""
    echo "   In Windows PowerShell, run:"
    echo "     usbipd list              (find the ESP32 bus ID)"
    echo "     usbipd attach --wsl --busid <BUSID>"
    echo ""
    exit 1
fi

# --- 2. Fix permissions ---
echo "2) Fixing serial permissions..."
if [ -r "$SERIAL_PORT" ] && [ -w "$SERIAL_PORT" ]; then
    ok "Already readable/writable"
else
    sudo chmod 666 "$SERIAL_PORT"
    if [ -r "$SERIAL_PORT" ] && [ -w "$SERIAL_PORT" ]; then
        ok "Permissions fixed (chmod 666)"
    else
        fail "Could not fix permissions"
        exit 1
    fi
fi

# --- 3. Check arduino-cli ---
echo "3) Checking arduino-cli..."
export PATH="$PATH:$BIN_DIR"
if command -v arduino-cli &>/dev/null; then
    ok "arduino-cli found ($(arduino-cli version 2>/dev/null | head -1))"
else
    fail "arduino-cli not found in PATH or $BIN_DIR"
    exit 1
fi

# --- 4. Detect board ---
echo "4) Detecting ESP32 board..."
BOARD_LIST=$(arduino-cli board list 2>/dev/null)
if echo "$BOARD_LIST" | grep -q "$SERIAL_PORT"; then
    ok "Board detected on $SERIAL_PORT"
else
    warn "Board not auto-detected (may still work)"
fi

# --- 5. Compile & upload (optional) ---
echo ""
read -p "Compile and upload t7_6x6 sketch? [y/N] " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "5a) Compiling..."
    arduino-cli compile --fqbn "$FQBN" "$SKETCH_DIR"
    ok "Compilation successful"

    echo "5b) Uploading..."
    arduino-cli upload --fqbn "$FQBN" -p "$SERIAL_PORT" "$SKETCH_DIR"
    ok "Upload successful"
    sleep 2  # let ESP32 reboot
else
    echo "   Skipping compile/upload"
fi

# --- 6. Check Python dependencies ---
echo ""
echo "6) Checking Python dependencies..."
MISSING=""
python3 -c "import serial" 2>/dev/null || MISSING="$MISSING pyserial"
python3 -c "import websockets" 2>/dev/null || MISSING="$MISSING websockets"
if [ -z "$MISSING" ]; then
    ok "All Python packages installed"
else
    warn "Missing packages:$MISSING - installing..."
    pip3 install $MISSING
    ok "Installed"
fi

# --- 7. Launch GUI server ---
echo ""
echo "7) Launching GUI server..."
echo "   WebSocket: ws://localhost:8765"
echo "   Browser:   http://localhost:8080"
echo ""
echo "   Press Ctrl+C to stop"
echo "==========================================="
echo ""

cd "$GUI_DIR"
python3 server.py
