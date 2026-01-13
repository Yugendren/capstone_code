# Piezoelectric Force Sensing Grid (Physiotherapy Training)

A 16×32 force sensing grid using ADS1220 24-bit ADCs for spinal physiotherapy training.

## System Overview

| Component | Details |
|-----------|---------|
| **MCU** | STM32F303RE Nucleo |
| **ADCs** | 8× ADS1220 (4 channels each = 32 columns) |
| **Grid Size** | 16 rows × 32 columns = **512 cells** |
| **Physical Size** | 80mm × 160mm (at 5mm spacing) |
| **Communication** | Binary protocol over UART @ 115200 baud |
| **GUI** | Python (PyQt6 + PyQtGraph) |

## Pin Assignments

```
ROW DRIVERS (PC0-PC15):
┌─────────────────────────────────────┐
│  PC0  → Row 0      PC8  → Row 8    │
│  PC1  → Row 1      PC9  → Row 9    │
│  PC2  → Row 2      PC10 → Row 10   │
│  PC3  → Row 3      PC11 → Row 11   │
│  PC4  → Row 4      PC12 → Row 12   │
│  PC5  → Row 5      PC13 → Row 13   │
│  PC6  → Row 6      PC14 → Row 14   │
│  PC7  → Row 7      PC15 → Row 15   │
└─────────────────────────────────────┘

SPI BUS (to all 8 ADS1220):
┌─────────────────────────────────────┐
│  PB13 → SCK                        │
│  PB14 → MISO (DOUT)                │
│  PB15 → MOSI (DIN)                 │
└─────────────────────────────────────┘

CHIP SELECT (Active LOW):
┌─────────────────────────────────────┐
│  PA0 → CS0 (Cols 0-3)              │
│  PA1 → CS1 (Cols 4-7)              │
│  PA4 → CS2 (Cols 8-11)             │
│  PA5 → CS3 (Cols 12-15)            │
│  PA6 → CS4 (Cols 16-19)            │
│  PA7 → CS5 (Cols 20-23)            │
│  PA8 → CS6 (Cols 24-27)            │
│  PA9 → CS7 (Cols 28-31)            │
└─────────────────────────────────────┘

UART (USB Serial):
  PA2 → TX, PA3 → RX
```

## Quick Start

### Firmware
1. Open in STM32CubeIDE
2. Configure SPI2 (PB13/14/15)
3. Configure GPIO outputs (PC0-PC15, PA0/1/4-9)
4. Build and flash

### GUI
```bash
cd gui
pip install -r requirements.txt
python grid_gui.py
```

## Files

| Path | Description |
|------|-------------|
| `Core/Inc/ads1220.h` | ADS1220 driver header |
| `Core/Src/ads1220.c` | ADS1220 SPI driver |
| `Core/Inc/grid_scan.h` | Grid scanning header |
| `Core/Src/grid_scan.c` | 16×32 scanning engine |
| `gui/grid_gui.py` | Main GUI application |
| `gui/spine_detector.py` | Spinal landmark detection |
