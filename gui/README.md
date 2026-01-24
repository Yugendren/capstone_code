# 20×12 Force Sensing Grid - GUI Application

Real-time pressure visualization for the piezoelectric force sensing grid with hardware setup mode.

## Features

- **Real-time 20×12 Heatmap** - Color-coded pressure display (blue=low, red=high)
- **Hardware Setup Mode** - Interactive GPIO/ADC pin configuration tool
- **Force vs Time Waveform** - Click any cell to see its pressure history
- **Demo Mode** - Test the GUI without hardware
- **Dark Theme** - Modern, professional appearance
- **Binary Protocol** - Efficient 486 bytes/frame communication

## Quick Start

### 1. Install Dependencies

```bash
cd gui
pip install -r requirements.txt
```

### 2. Run the Application

```bash
python grid_gui.py
```

### 3. Connect to Hardware

1. Connect STM32 Nucleo via USB
2. Select the COM port from the dropdown
3. Click **Connect**

### 4. Demo Mode (No Hardware)

Click **Demo Mode** to see simulated pressure data for testing.

## Usage

| Action | Description |
|--------|-------------|
| Click heatmap | Select cell for waveform display |
| Connect | Start receiving data from STM32 |
| Demo Mode | Simulate pressure data (including spine palpation) |
| **⚙ Hardware Setup Mode** | Configure GPIO/ADC pin mappings interactively |
| **Calibrate Spine** | Start wizard to detect L1-L5 landmarks |
| Load/Save | Save calibration for specific patients |

## Hardware Setup Mode (New!)

The Hardware Setup Mode allows you to configure GPIO and ADC pin mappings by physically testing your grid. This makes initial setup and debugging much easier.

### Workflow

1. **Open Setup Mode**
   - Click "⚙ Hardware Setup Mode" button
   - Connect to your device or use Demo mode

2. **Configure Row GPIO Pins**
   - **Auto-Detection (Recommended)**:
     - Click "🔍 Auto-Detect" button
     - Press firmly on the physical grid row you want to configure
     - System detects which row (0-11) is active
     - Enter the GPIO pin name (e.g., "GPIOA_0", "PB1")
     - Click "✓ Assign GPIO to Row"
   - **Manual Assignment**:
     - Select row number (0-11)
     - Enter GPIO pin name
     - Assign to row

3. **Configure ADC Channels**
   - Enter ADC channel names for column scanning
   - Example: ADC1_IN0, ADC1_IN1

4. **Validate & Save**
   - Click "🔍 Validate Config" to check for issues
   - Click "💾 Save Configuration" to save as JSON
   - Optionally "📤 Export C Header" for firmware integration

### Configuration Files

The hardware configuration is saved to `hardware_config.json`:

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

You can also export as a C header file for direct firmware integration.

## Spinal Landmark Detection

The GUI includes a teaching system for spinal palpation:

### 1. Calibration Wizard
1. Click **Calibrate Spine**
2. Click **Start Recording**
3. Drag finger firmly along the spine (top to bottom)
4. The system detects the midline and segments L1-L5 automatically

### 2. Teaching Feedback Zones
Based on velostat capabilities (0-15N range):

| Zone | Feedback | Color |
|------|----------|-------|
| **< 0.5N** | No Contact | Grey |
| **0.5 - 2N** | Too Light | 🟡 Yellow |
| **2 - 8N** | **Correct Palpation** | 🟢 Green |
| **8 - 12N** | Firm Contact | 🟠 Orange |
| **> 12N** | Too Hard | 🔴 Red |

### 3. Movement Speed
Optimized for steady scanning speed (5-12 cells/sec). Quick movements or being stationary will trigger warnings.

## Data Protocol

The GUI expects binary packets from the STM32:

```
Header:  0xAA 0x55          (2 bytes)
Payload: 240 × uint16_le    (480 bytes)
Footer:  checksum + CRLF    (4 bytes)
Total:   486 bytes per frame
```

Grid layout: 20 columns × 12 rows = 240 cells

## Requirements

- Python 3.9+
- PyQt6
- pyqtgraph
- pyserial
- numpy

## Troubleshooting

**No COM ports shown:**
- Check USB connection
- Install STM32 VCP drivers if needed

**Data not displaying:**
- Verify STM32 firmware is flashed
- Check baud rate (115200)
- Use Demo Mode to verify GUI works

**Slow performance:**
- Close other applications
- Check CPU usage
- Reduce window size if needed
