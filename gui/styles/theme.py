"""
================================================================================
Theme - Application Visual Design System
================================================================================

This module defines the complete visual design system for the physiotherapy
training application. The design prioritizes friendliness and clarity.

Design Philosophy:
    "Simplicity is the ultimate sophistication." - Leonardo da Vinci

Color Psychology:
    - Purple (Primary): Creativity, wisdom, trust
    - Teal (Success): Health, healing, growth
    - Soft backgrounds: Reduces eye strain during extended use

Typography:
    Comic Sans MS is chosen for its friendly, approachable appearance.
    While often criticized, it's actually excellent for dyslexic users
    and creates a welcoming, non-intimidating interface.
"""

from typing import Dict, Tuple

# =============================================================================
# Color Palette
# =============================================================================

COLORS: Dict[str, str] = {
    # -------------------------------------------------------------------------
    # Background Colors
    # Soft, easy on the eyes for extended use
    # -------------------------------------------------------------------------
    'bg_main': '#f5f7fa',           # Light gray-blue - main background
    'bg_card': '#ffffff',           # Pure white - card backgrounds
    'bg_sidebar': '#2d3436',        # Dark charcoal - sidebar
    'bg_header': '#6c5ce7',         # Purple - header accent

    # -------------------------------------------------------------------------
    # Text Colors
    # High contrast ratios for accessibility
    # -------------------------------------------------------------------------
    'text_dark': '#2d3436',         # Near-black - primary text
    'text_light': '#636e72',        # Medium gray - secondary text
    'text_white': '#ffffff',        # White - text on dark backgrounds
    'text_muted': '#b2bec3',        # Light gray - disabled/placeholder

    # -------------------------------------------------------------------------
    # Accent Colors
    # Vibrant but not overwhelming
    # -------------------------------------------------------------------------
    'primary': '#6c5ce7',           # Purple - primary actions
    'secondary': '#00b894',         # Teal - secondary actions
    'success': '#00b894',           # Teal - success states
    'warning': '#fdcb6e',           # Yellow - warnings
    'danger': '#d63031',            # Red - errors/recording
    'info': '#0984e3',              # Blue - information

    # -------------------------------------------------------------------------
    # Button States
    # Clear visual feedback for interactions
    # -------------------------------------------------------------------------
    'btn_primary': '#6c5ce7',
    'btn_primary_hover': '#5b4cdb',
    'btn_success': '#00b894',
    'btn_success_hover': '#00a187',
    'btn_danger': '#d63031',
    'btn_danger_hover': '#c0392b',
    'btn_secondary': '#dfe6e9',
    'btn_secondary_hover': '#b2bec3',

    # -------------------------------------------------------------------------
    # Utility Colors
    # -------------------------------------------------------------------------
    'shadow': 'rgba(0, 0, 0, 0.1)',
    'border': '#dfe6e9',
    'highlight': '#74b9ff',
}

# =============================================================================
# Heatmap Color Gradient
# =============================================================================

# RGB tuples for pressure visualization
# Progresses from cool (low pressure) to warm (high pressure)
HEATMAP_COLORS: list[Tuple[int, int, int]] = [
    (99, 110, 114),     # Gray - no pressure (baseline)
    (116, 185, 255),    # Light blue - very light touch
    (0, 184, 148),      # Teal - light pressure
    (253, 203, 110),    # Yellow - moderate pressure
    (255, 118, 117),    # Salmon - firm pressure
    (214, 48, 49),      # Red - high pressure
]

# =============================================================================
# Typography
# =============================================================================

# Primary font family with fallbacks
# Comic Sans creates a friendly, non-intimidating interface
FONT_FAMILY: str = "Comic Sans MS, Comic Sans, cursive, sans-serif"


# =============================================================================
# Style Helper Functions
# =============================================================================

def get_button_style(color_scheme: str, font_family: str = FONT_FAMILY) -> str:
    """
    Generate CSS stylesheet for animated buttons.

    Args:
        color_scheme: One of 'primary', 'success', 'danger', 'secondary'
        font_family: Font family to use

    Returns:
        CSS stylesheet string for QPushButton

    Example:
        >>> style = get_button_style('primary')
        >>> button.setStyleSheet(style)
    """
    bg_color = COLORS.get(f'btn_{color_scheme}', COLORS['btn_primary'])
    text_color = COLORS['text_white'] if color_scheme != 'secondary' else COLORS['text_dark']

    return f"""
        QPushButton {{
            background-color: {bg_color};
            color: {text_color};
            border: none;
            border-radius: 12px;
            padding: 12px 24px;
            font-family: {font_family};
            font-weight: bold;
            font-size: 12px;
        }}
    """


def get_card_style() -> str:
    """
    Generate CSS stylesheet for card widgets.

    Returns:
        CSS stylesheet string for FriendlyCard

    Example:
        >>> style = get_card_style()
        >>> card.setStyleSheet(style)
    """
    return f"""
        FriendlyCard {{
            background-color: {COLORS['bg_card']};
            border-radius: 16px;
            border: 1px solid {COLORS['border']};
        }}
    """
