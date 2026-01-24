# GUI Updates - 2026-01-24

## Summary

Updated the Force Sensing Grid GUI from 32×16 to 20×12 grid configuration and added comprehensive hardware setup mode for easier debugging and configuration.

## Changes Made

### 1. Grid Size Changes

**File: `grid_gui.py`**

- Changed `GRID_ROWS` from 16 to 12
- Changed `GRID_COLS` from 32 to 20
- Updated `GRID_TOTAL` from 512 to 240 cells
- Updated `PAYLOAD_SIZE` from 3200 to 480 bytes
- Updated `PACKET_SIZE` from 3206 to 486 bytes
- Updated window title and documentation strings

### 2. New Hardware Configuration Module

**File: `hardware_config.py` (NEW)**

Features:
- `HardwareConfig` dataclass for storing GPIO/ADC mappings
- Row GPIO pin mapping (physical row 0-11 → GPIO pin name)
- ADC channel mapping for column scanning
- JSON save/load functionality
- C header file export for firmware integration
- Configuration validation with error reporting
- Default configuration management

### 3. Hardware Setup Mode Dialog

**File: `setup_dialog.py` (NEW)**

Features:
- Interactive visual grid showing real-time pressure data
- Auto-detection mode - press on physical grid to detect active row
- Manual GPIO pin assignment per row
- ADC channel configuration interface
- Real-time validation of configuration
- Configuration table showing status of all rows
- Save configuration to JSON
- Export configuration as C header file for firmware

UI Components:
- Grid activity monitor with heatmap
- Detection status display
- Row configuration table
- Current row setup controls
- ADC channel configuration
- Validation panel
- Save/Export buttons

### 4. Main GUI Integration

**File: `grid_gui.py`**

Added:
- Import of `hardware_config` and `setup_dialog` modules
- Hardware configuration instance (`self.hardware_config`)
- Setup mode dialog reference (`self.setup_dialog`)
- "⚙ Hardware Setup Mode" button in controls panel
- Frame routing to setup dialog when active
- Configuration update handling
- Auto-save of hardware configuration

### 5. Documentation Updates

**File: `README.md`**

Updated:
- Title reflects 20×12 grid size
- Added Hardware Setup Mode section with detailed workflow
- Updated data protocol specifications (486 bytes/frame)
- Added configuration file format documentation
- Added troubleshooting for setup mode

**File: `hardware_config_example.json` (NEW)**

- Example configuration template
- Shows GPIO pin mapping format
- Shows ADC channel mapping format
- Includes helpful notes

**File: `CHANGES.md` (NEW)**

- This document summarizing all changes

## Usage Workflow

### First-Time Setup

1. **Launch GUI**
   ```bash
   python grid_gui.py
   ```

2. **Configure Hardware**
   - Click "⚙ Hardware Setup Mode"
   - Connect to device or use Demo mode
   - Click "🔍 Auto-Detect"
   - Press on each physical grid row (0-11)
   - Enter GPIO pin name when detected
   - Click "✓ Assign GPIO to Row"
   - Repeat for all rows

3. **Configure ADC**
   - Enter ADC channel names in the table
   - Example: ADC1_IN0, ADC1_IN1

4. **Save Configuration**
   - Click "🔍 Validate Config" to check for issues
   - Click "💾 Save Configuration"
   - Configuration saved to `hardware_config.json`

### Exporting for Firmware

1. In Setup Mode, click "📤 Export C Header"
2. Save as `hardware_config.h`
3. Include in your STM32 firmware project
4. Use the defined constants for GPIO/ADC pin references

## File Structure

```
GUI/
├── grid_gui.py                      # Main application (MODIFIED)
├── spine_detector.py                # Spine calibration module (unchanged)
├── hardware_config.py               # Hardware config module (NEW)
├── setup_dialog.py                  # Setup mode dialog (NEW)
├── requirements.txt                 # Python dependencies (unchanged)
├── README.md                        # Documentation (MODIFIED)
├── CHANGES.md                       # This file (NEW)
└── hardware_config_example.json     # Example config (NEW)
```

## Breaking Changes

### Serial Protocol

The packet size has changed due to grid size reduction:

**Before (32×16):**
- Payload: 512 cells × 2 bytes = 1024 bytes
- Total packet: 1030 bytes

**After (20×12):**
- Payload: 240 cells × 2 bytes = 480 bytes
- Total packet: 486 bytes

**Firmware must be updated to match new grid dimensions.**

### Configuration Files

Calibration files from 32×16 grid are **not compatible** with 20×12 grid. You will need to recalibrate.

## Benefits

1. **Easier Debugging**
   - Visual feedback when testing physical grid
   - See exactly which row is being activated
   - No need to manually trace wiring

2. **Easier Setup**
   - Interactive configuration process
   - Auto-detection reduces errors
   - Real-time validation catches issues early

3. **Better Documentation**
   - Configuration saved as human-readable JSON
   - Can export as C header for firmware
   - Track configuration changes with timestamps

4. **Flexibility**
   - Easy to reconfigure if wiring changes
   - Multiple configurations can be saved
   - No hardcoding of pin assignments

## Testing Recommendations

1. **Test Setup Mode**
   - Use Demo mode first to verify UI works
   - Connect to real hardware
   - Test auto-detection by pressing each row
   - Verify detected row matches physical row

2. **Test Configuration**
   - Save configuration
   - Restart GUI
   - Verify configuration loads correctly
   - Export C header and check format

3. **Test Grid Operation**
   - Press on grid while connected
   - Verify heatmap updates correctly
   - Check that row/column mapping is correct
   - Test spine calibration workflow

## Future Enhancements

Potential improvements for future versions:

1. **Column Configuration**
   - Add similar auto-detection for columns
   - Map individual columns to ADC channels

2. **Automated Calibration**
   - Automatic full-grid test sequence
   - Detect all rows/columns systematically
   - Generate calibration report

3. **Configuration Profiles**
   - Save multiple hardware configurations
   - Quick switching between profiles
   - Compare configurations

4. **Live Pin Testing**
   - Test individual GPIO pins
   - Verify ADC readings in real-time
   - Diagnostic tools for troubleshooting

## Notes

- All new code follows the existing dark theme styling
- Maintains compatibility with existing spine calibration features
- No changes to serial communication protocol structure (only packet size)
- Configuration files use JSON for easy editing and version control
