"""
================================================================================
Widgets Package - Custom UI Components
================================================================================

This package contains all custom widgets used in the application.
Each widget is designed to be self-contained, reusable, and animated.

Design Philosophy:
    "The best interface is no interface." - Golden Krishna

    Our widgets provide clear visual feedback with smooth animations,
    making the interface feel responsive and alive while remaining
    unobtrusive to the user's workflow.

Modules:
    animated_button: Buttons with press/hover animations
    cards: Container widgets with shadows and rounded corners
    indicators: Status indicators (pulsing dot, progress bars)
    overlays: Graphics overlays for the heatmap
    warnings: Alert and warning display widgets
"""

try:
    from .animated_button import AnimatedButton
    from .cards import FriendlyCard, StatDisplay
    from .indicators import PulsingDot, ColorLegendWidget
    from .overlays import LandmarkOverlay
    from .warnings import DriftWarningWidget
except ImportError:
    from widgets.animated_button import AnimatedButton
    from widgets.cards import FriendlyCard, StatDisplay
    from widgets.indicators import PulsingDot, ColorLegendWidget
    from widgets.overlays import LandmarkOverlay
    from widgets.warnings import DriftWarningWidget

__all__ = [
    'AnimatedButton',
    'FriendlyCard',
    'StatDisplay',
    'PulsingDot',
    'ColorLegendWidget',
    'LandmarkOverlay',
    'DriftWarningWidget',
]
