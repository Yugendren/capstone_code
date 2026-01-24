"""
================================================================================
Styles Package - Visual Design System
================================================================================

This package defines the visual language of the application, including
colors, typography, and component styles.

Design Philosophy:
    "Design is not just what it looks like and feels like.
     Design is how it works." - Steve Jobs

The color palette and typography choices create a friendly, approachable
interface that reduces cognitive load and helps users focus on their task.

Modules:
    theme: Color palette, fonts, and heatmap colors
"""

try:
    from .theme import (
        # Color palette
        COLORS,
        HEATMAP_COLORS,
        # Typography
        FONT_FAMILY,
        # Helper functions
        get_button_style,
        get_card_style,
    )
except ImportError:
    from styles.theme import (
        COLORS,
        HEATMAP_COLORS,
        FONT_FAMILY,
        get_button_style,
        get_card_style,
    )

__all__ = [
    'COLORS',
    'HEATMAP_COLORS',
    'FONT_FAMILY',
    'get_button_style',
    'get_card_style',
]
