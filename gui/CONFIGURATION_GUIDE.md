# Grid Configuration Guide

## System Architecture Overview

The physiotherapy training system uses a **separation of concerns** architecture:

- **STM32 Firmware**: Reads raw sensor values and transmits them as a linear array
- **Python GUI**: Maps the raw values to grid positions using a configuration file

This design allows you to change the grid layout without reflashing the firmware.

---

## Hardware Configuration

### ADC Resolution

- **ADC Type**: ADS1220 (24-bit external ADC via SPI)
- **Value Range**:
  - Raw: 24-bit (0 - 16,777,215)
  - Transmitted: 16-bit (0 - 65,535) - scaled by right-shift 8 bits
  - Displayed: 16-bit (0 - 65,535)

### Grid Dimensions

The physical grid size is configured in `hardware_config.json`:

```json
{
  "grid_rows": 12,
  "grid_cols": 20,
  "row_gpio_map": {
    "0": "PC0",
    "1": "PC1",
    ...
  },
  "adc_channel_map": {
    "0": "ADS1220_CH0",
    ...
  }
}
```

---

## Binary Communication Protocol

### Packet Structure

```
[ 0xAA ][ 0x55 ][ PAYLOAD ][ CHECKSUM ][ 0x0D 0x0A ]
  Sync1   Sync2   Data       2 bytes     CR    LF
```

### Packet Details

- **Header**: 2 bytes (`0xAA 0x55` - sync markers)
- **Payload**: `grid_rows × grid_cols × 2` bytes
  - Each sensor value is 16-bit little-endian
  - Total for 12×20 grid: 480 bytes
- **Footer**: 4 bytes
  - 2 bytes: Checksum (sum of payload bytes & 0xFFFF)
  - 2 bytes: CR LF (0x0D 0x0A)

**Total Packet Size**: 2 + 480 + 4 = **486 bytes** (for 12×20 grid)

---

## Configuration Steps

### 1. Open Setup Dialog

In the GUI main window, click **"Setup Mode"** in the Settings card.

### 2. Configure Grid Size

At the top of the Setup dialog:
- Set **Rows** to your physical grid row count (e.g., 12)
- Set **Columns** to your physical grid column count (e.g., 20)
- Observe the **Grid Preview** update in real-time
- Check **Total sensors** count

### 3. Map GPIO Pins

Two methods available:

#### Method A: Guided Sequence (Recommended)
1. Enter GPIO prefix (e.g., `PC` for Port C pins)
2. Click **"Start Sequence"**
3. Press on each row when highlighted
4. System auto-detects and assigns GPIO pins

#### Method B: Manual Assignment
1. Select row number
2. Enter GPIO pin name (e.g., `PC5`)
3. Click **"Assign"**

### 4. Validate Configuration

Click **"Validate Configuration"** to check for:
- Missing GPIO mappings
- Duplicate pin assignments
- Complete row coverage

### 5. Save Configuration

Click **"Save Configuration"** to write `hardware_config.json`.

This file becomes the **single source of truth** for all grid dimensions and pin mappings.

---

## Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  STM32 Firmware                                             │
│  ├── Scan sensors row-by-row                               │
│  ├── Read ADC values (ADS1220, 24-bit)                     │
│  ├── Scale to 16-bit (>> 8)                                │
│  └── Transmit as linear array                              │
│                                                             │
│           ↓ UART (Binary Protocol)                          │
│                                                             │
│  Python GUI                                                 │
│  ├── Read hardware_config.json                             │
│  ├── Parse binary packets                                  │
│  ├── Map values to (row, col) based on config              │
│  └── Visualize on heatmap                                  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Firmware Notes

The STM32 firmware **only sends raw sensor data**. It does not need to know:
- How the GUI displays the grid
- Row/column layout interpretation
- Sensor names or labels

The GUI handles all visualization logic using the config file.

---

## Troubleshooting

### Grid size mismatch error

**Symptom**: GUI shows corrupted data or "sync lost" errors

**Solution**:
1. Verify `hardware_config.json` matches firmware grid size
2. Check packet size calculation:
   - Expected: `2 + (rows × cols × 2) + 4` bytes
3. Recompile firmware if grid dimensions changed

### ADC values out of range

**Symptom**: Heatmap shows all white or all black

**Solution**:
1. Check ADC wiring to ADS1220 chips
2. Verify SPI communication (use oscilloscope if available)
3. Check `ADC_MAX = 65535` in `constants.py`

### No data received

**Symptom**: Heatmap remains static

**Solution**:
1. Verify serial port connection
2. Check baud rate (should be 115200)
3. Confirm STM32 is powered and running
4. Use serial monitor to verify data transmission

---

## Advanced: Firmware Modification

If you need to change the grid size in the firmware:

1. Edit `agent-core/Core/Inc/grid_scan.h`:
   ```c
   #define GRID_NUM_ROWS 12U
   #define GRID_NUM_COLS 20U
   ```

2. Recompile and flash the firmware

3. Update `hardware_config.json` to match

4. Restart the GUI application

---

## Files Reference

- **GUI Config**: `agent-gui/gui/hardware_config.json`
- **GUI Constants**: `agent-gui/gui/utils/constants.py`
- **Firmware Config**: `agent-core/Core/Inc/grid_scan.h`
- **Setup Dialog**: `agent-gui/gui/setup_dialog.py`

---

*Last updated: 2026-01-25*
