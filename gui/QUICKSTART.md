# Quick Start Guide - 20×12 Grid GUI

## Installation

```bash
cd GUI
pip install -r requirements.txt
```

## First Time Setup

### Step 1: Launch GUI

```bash
python grid_gui.py
```

### Step 2: Configure Hardware (One-Time Setup)

1. Click **"⚙ Hardware Setup Mode"** button
2. Click **"🔍 Auto-Detect"** to start monitoring
3. **For each row (0-11):**
   - Press firmly on that physical grid row
   - System shows: "✓ Row X detected"
   - Enter the GPIO pin name (e.g., "GPIOA_0")
   - Click **"✓ Assign GPIO to Row"**
4. **Configure ADC channels:**
   - Enter ADC names (e.g., "ADC1_IN0", "ADC1_IN1")
5. Click **"🔍 Validate Config"** to check for errors
6. Click **"💾 Save Configuration"**
7. Click **"Close"**

### Step 3: Connect and Test

1. Select your **COM port** from dropdown
2. Click **"▶ Connect"**
3. Press on the grid - you should see the heatmap update!

## Using Demo Mode (No Hardware)

Click **"🎮 Demo"** to test the GUI with simulated data.

## Hardware Configuration File

Your configuration is saved to `hardware_config.json` and automatically loaded on startup.

**Example structure:**
```json
{
  "grid_rows": 12,
  "grid_cols": 20,
  "row_gpio_map": {
    "0": "GPIOA_0",
    "1": "GPIOA_1",
    ...
  },
  "adc_channel_map": {
    "0": "ADC1_IN0",
    "1": "ADC1_IN1"
  }
}
```

## Exporting for Firmware

1. In Setup Mode, click **"📤 Export C Header"**
2. Save as `hardware_config.h`
3. Include in your STM32 firmware:

```c
#include "hardware_config.h"

// Use the defined constants
#define ROW_0_GPIO GPIOA_0  // Auto-generated from your config
#define ROW_1_GPIO GPIOA_1
...
```

## Grid Layout

```
        Columns (0-19)
        →→→→→→→→→→
Rows  ┌──────────────┐
(0-   │              │
11)   │   20 × 12    │
↓     │   Grid       │
      └──────────────┘
```

## Troubleshooting

### Setup Mode Not Detecting Rows

- **Cause**: Not connected to device
- **Fix**: Connect to device first, or use Demo mode

### "No ports found"

- **Cause**: No USB serial device connected
- **Fix**:
  1. Connect your STM32 via USB
  2. Click the 🔄 refresh button
  3. Check device manager (Windows) or `ls /dev/ttyACM*` (Linux)

### Configuration Not Saving

- **Cause**: File permissions issue
- **Fix**: Run from a directory where you have write permissions

### Wrong Row Detected

- **Cause**: Multiple rows activated or wiring issue
- **Fix**:
  1. Press only one row at a time
  2. Check your hardware connections
  3. Use Manual Assignment mode if needed

## Serial Protocol Details

- **Baud Rate**: 115200
- **Packet Format**: `[0xAA][0x55][240×uint16][checksum][CR][LF]`
- **Packet Size**: 486 bytes
- **Frame Rate**: ~25 Hz (adjustable in firmware)

## Features Overview

| Feature | Description |
|---------|-------------|
| **Hardware Setup** | Configure GPIO/ADC pins interactively |
| **Heatmap** | Real-time 20×12 pressure visualization |
| **Waveform** | Click any cell to see pressure over time |
| **Spine Calibration** | Detect L1-L5 vertebrae for training |
| **Feedback** | Real-time pressure and speed guidance |
| **Demo Mode** | Test without hardware |

## Next Steps

- **For Hardware Testing**: Use Setup Mode to configure pins
- **For Physiotherapy Training**: Use Spine Calibration
- **For Development**: Export config as C header for firmware

See `README.md` for full documentation and `CHANGES.md` for technical details.
