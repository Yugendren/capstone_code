# Piezoelectric Force Sensing Grid (Physiotherapy Training)

A 40×24 velostat-based pressure sensing grid for spinal physiotherapy training, featuring real-time visualization, spinal landmark detection, and palpation feedback.

## System Overview

*   **Hardware**: STM32F303RE Nucleo + 8x CD4051 Multiplexers + Velostat Grid
*   **Grid Dimensions**: 40 Rows × 24 Columns (5mm spacing)
*   **Resolution**: 960 sensing points
*   **Communication**: Binary protocol over UART (USB Serial) @ 115200 baud
*   **Software**: Python Desktop GUI (PyQt6 + PyQtGraph)

## Directory Structure

*   `Core/` - STM32 Firmware source code
    *   `Inc/grid_mux.h` - Multiplexer configuration & pin definitions
    *   `Inc/grid_scan.h` - Scanning engine & binary protocol
    *   `Src/main.c` - Main application entry
*   `gui/` - PC Application
    *   `grid_gui.py` - Main GUI application
    *   `spine_detector.py` - Spinal landmark detection logic
    *   `README.md` - GUI-specific usage instructions
*   `docs/` - Documentation
    *   `schematics/` - Wiring diagrams and system overview
    *   `CUBEIDE_SETUP.md` - STM32CubeIDE configuration guide

## Quick Start

### 1. Hardware Setup
Connect the 40x24 grid to the STM32 via the multiplexer circuitry.
*   **5 Row Muxes**: Enable pins PC0-PC4
*   **3 Column Muxes**: Enable pins PC5-PC7
*   **Select Lines**: PB0 (S0), PB1 (S1), PB2 (S2)
*   **Analog**: PA1 (Drive), PA0 (Sense)

### 2. Firmware
1.  Open project in **STM32CubeIDE**.
2.  Compile and flash to the Nucleo board.
3.  Reset the board.

### 3. Software
1.  Install Python dependencies: `pip install -r gui/requirements.txt`
2.  Run the GUI: `python gui/grid_gui.py`
3.  Select COM port and click **Connect**.

## Key Features

*   **Real-time Heatmap**: Visualizes pressure distribution @ ~25 Hz.
*   **Spinal Calibration**: Detects L1-L5 vertebrae from a simple drag gesture.
*   **Teaching Feedback**:
    *   **Pressure**: Color-coded feedback (Yellow < Green < Red) for palpation force (0-15N).
    *   **Speed**: Monitors scanning speed for optimal technique.
*   **Waveform Analysis**: View force-over-time for any selected cell.
