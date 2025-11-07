"""Theme support for LIFX devices.

This module provides theme support for applying coordinated color schemes
across LIFX devices. Themes enable applying color palettes to single-zone
lights, multi-zone lights (strips/beams), and tile devices.

Example:
    ```python
    from lifx.theme import Theme, ThemeLibrary, get_theme
    from lifx.color import HSBK

    # Use a built-in theme
    theme = get_theme("evening")

    # Or create a custom theme
    custom_theme = Theme(
        [
            HSBK(hue=0, saturation=1.0, brightness=1.0, kelvin=3500),  # Red
            HSBK(hue=120, saturation=1.0, brightness=1.0, kelvin=3500),  # Green
            HSBK(hue=240, saturation=1.0, brightness=1.0, kelvin=3500),  # Blue
        ]
    )

    # Apply to a light
    await light.apply_theme(theme, power_on=True)

    # List available themes
    all_themes = ThemeLibrary.list()
    ```
"""

from __future__ import annotations

from lifx.theme.canvas import Canvas
from lifx.theme.generators import (
    MatrixGenerator,
    MultiZoneGenerator,
    SingleZoneGenerator,
)
from lifx.theme.library import ThemeLibrary, get_theme
from lifx.theme.theme import Theme

__all__ = [
    "Canvas",
    "MatrixGenerator",
    "MultiZoneGenerator",
    "SingleZoneGenerator",
    "Theme",
    "ThemeLibrary",
    "get_theme",
]
