# 40×40 Force Sensing Grid - GUI Application

Real-time pressure visualization for the piezoelectric force sensing grid.

## Features

- **Real-time 40×40 Heatmap** - Color-coded pressure display (blue=low, red=high)
- **Force vs Time Waveform** - Click any cell to see its pressure history
- **Demo Mode** - Test the GUI without hardware
- **Dark Theme** - Modern, professional appearance
- **Binary Protocol** - Efficient 3206 bytes/frame communication

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
| **Calibrate Spine** | Start wizard to detect L1-L5 landmarks |
| Load/Save | Save calibration for specific patients |

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
Payload: 1600 × uint16_le   (3200 bytes)  
Footer:  checksum + CRLF    (4 bytes)
Total:   3206 bytes per frame
```

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
