"""
================================================================================
Hardware Configuration Module
================================================================================

Manages GPIO and ADC pin mapping configuration for the pressure sensing grid.

Features:
- Row GPIO pin mapping (physical row -> GPIO pin)
- ADC channel mapping (column group -> ADC channel)
- Configuration save/load to JSON
- Validation and testing utilities

Author: Capstone Project
Date: 2026-01-24
================================================================================
"""

import json
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional
from pathlib import Path
from datetime import datetime


@dataclass
class HardwareConfig:
    """
    Complete hardware configuration for the sensing grid.

    Attributes:
        row_gpio_map: Maps physical row index (0-11) to GPIO pin name
        adc_channel_map: Maps ADC channel index to physical description
        grid_rows: Number of rows in the grid
        grid_cols: Number of columns in the grid
        notes: User notes about the configuration
        created_at: Timestamp of configuration creation
        last_modified: Timestamp of last modification
    """

    grid_rows: int = 12
    grid_cols: int = 20
    row_gpio_map: Dict[int, str] = field(default_factory=dict)
    adc_channel_map: Dict[int, str] = field(default_factory=dict)
    notes: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_modified: str = field(default_factory=lambda: datetime.now().isoformat())

    def __post_init__(self):
        """Initialize with default mappings if empty."""
        if not self.row_gpio_map:
            # Default GPIO mapping - user should configure this
            self.row_gpio_map = {i: f"GPIO_UNDEFINED_{i}" for i in range(self.grid_rows)}

        if not self.adc_channel_map:
            # Default ADC mapping - typically ADC1 for columns
            self.adc_channel_map = {0: "ADC1_IN0", 1: "ADC1_IN1"}

    @property
    def is_configured(self) -> bool:
        """Check if configuration is complete (no undefined pins)."""
        for gpio in self.row_gpio_map.values():
            if "UNDEFINED" in gpio:
                return False
        return True

    def set_row_gpio(self, row_index: int, gpio_pin: str):
        """Set GPIO pin for a specific row."""
        if 0 <= row_index < self.grid_rows:
            self.row_gpio_map[row_index] = gpio_pin
            self.last_modified = datetime.now().isoformat()
        else:
            raise ValueError(f"Row index {row_index} out of range (0-{self.grid_rows-1})")

    def set_adc_channel(self, channel_index: int, adc_name: str):
        """Set ADC channel mapping."""
        self.adc_channel_map[channel_index] = adc_name
        self.last_modified = datetime.now().isoformat()

    def get_row_gpio(self, row_index: int) -> Optional[str]:
        """Get GPIO pin for a specific row."""
        return self.row_gpio_map.get(row_index)

    def get_adc_channel(self, channel_index: int) -> Optional[str]:
        """Get ADC channel name."""
        return self.adc_channel_map.get(channel_index)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "grid_rows": self.grid_rows,
            "grid_cols": self.grid_cols,
            "row_gpio_map": {str(k): v for k, v in self.row_gpio_map.items()},
            "adc_channel_map": {str(k): v for k, v in self.adc_channel_map.items()},
            "notes": self.notes,
            "created_at": self.created_at,
            "last_modified": self.last_modified
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'HardwareConfig':
        """Create from dictionary."""
        return cls(
            grid_rows=data.get("grid_rows", 12),
            grid_cols=data.get("grid_cols", 20),
            row_gpio_map={int(k): v for k, v in data.get("row_gpio_map", {}).items()},
            adc_channel_map={int(k): v for k, v in data.get("adc_channel_map", {}).items()},
            notes=data.get("notes", ""),
            created_at=data.get("created_at", datetime.now().isoformat()),
            last_modified=data.get("last_modified", datetime.now().isoformat())
        )

    def save(self, filepath: str):
        """Save configuration to JSON file."""
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, filepath: str) -> 'HardwareConfig':
        """Load configuration from JSON file."""
        with open(filepath, 'r') as f:
            data = json.load(f)
        return cls.from_dict(data)

    def export_c_header(self, filepath: str):
        """Export configuration as C header file for firmware."""
        with open(filepath, 'w') as f:
            f.write("/* Auto-generated hardware configuration */\n")
            f.write(f"/* Generated: {datetime.now().isoformat()} */\n\n")
            f.write("#ifndef HARDWARE_CONFIG_H\n")
            f.write("#define HARDWARE_CONFIG_H\n\n")
            f.write(f"#define GRID_ROWS {self.grid_rows}\n")
            f.write(f"#define GRID_COLS {self.grid_cols}\n\n")

            # Row GPIO mapping
            f.write("/* Row GPIO Pin Mapping */\n")
            for row_idx in sorted(self.row_gpio_map.keys()):
                gpio = self.row_gpio_map[row_idx]
                f.write(f"#define ROW_{row_idx}_GPIO {gpio}\n")

            f.write("\n/* ADC Channel Mapping */\n")
            for adc_idx in sorted(self.adc_channel_map.keys()):
                adc = self.adc_channel_map[adc_idx]
                f.write(f"#define ADC_CHANNEL_{adc_idx} {adc}\n")

            f.write("\n#endif /* HARDWARE_CONFIG_H */\n")

    def validate(self) -> List[str]:
        """
        Validate configuration and return list of issues.

        Returns:
            List of validation error messages (empty if valid)
        """
        issues = []

        # Check all rows are mapped
        if len(self.row_gpio_map) != self.grid_rows:
            issues.append(f"Missing row mappings: {self.grid_rows - len(self.row_gpio_map)} rows undefined")

        # Check for undefined pins
        undefined_rows = [row for row, gpio in self.row_gpio_map.items() if "UNDEFINED" in gpio]
        if undefined_rows:
            issues.append(f"Undefined GPIO pins for rows: {undefined_rows}")

        # Check for duplicate GPIO pins
        gpio_pins = [gpio for gpio in self.row_gpio_map.values() if "UNDEFINED" not in gpio]
        if len(gpio_pins) != len(set(gpio_pins)):
            issues.append("Duplicate GPIO pins detected")

        return issues


# Default configuration file location
DEFAULT_CONFIG_PATH = Path(__file__).parent / "hardware_config.json"


def get_default_config() -> HardwareConfig:
    """Get default configuration (loads from file if exists, otherwise creates new)."""
    if DEFAULT_CONFIG_PATH.exists():
        try:
            return HardwareConfig.load(str(DEFAULT_CONFIG_PATH))
        except Exception as e:
            print(f"Error loading default config: {e}")

    return HardwareConfig()


def save_default_config(config: HardwareConfig):
    """Save as default configuration."""
    config.save(str(DEFAULT_CONFIG_PATH))
