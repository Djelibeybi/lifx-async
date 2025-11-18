"""Built-in theme library with 60+ curated color themes.

This module provides a collection of professionally designed color themes
for LIFX devices, sourced from the official LIFX app theme library.

All themes are based on color theory and lighting design principles.

Reference: https://github.com/Djelibeybi/aiolifx-themes
"""

from __future__ import annotations

from lifx.color import HSBK
from lifx.theme.theme import Theme


class ThemeLibrary:
    """Collection of built-in color themes for LIFX devices.

    Provides access to 60+ professionally designed themes organized by
    mood, season, occasion, and time of day.

    Example:
        ```python
        # Get a specific theme
        evening_theme = ThemeLibrary.get("evening")

        # List all available themes
        all_themes = ThemeLibrary.list()

        # Get themes by category
        seasonal = ThemeLibrary.get_by_category("seasonal")

        # Apply to a light
        await light.apply_theme(evening_theme, power_on=True)
        ```
    """

    # Theme registry mapping theme names to color lists
    _THEMES = {
        "autumn": [
            HSBK(hue=31, saturation=1.0, brightness=0.5, kelvin=3500),
            HSBK(hue=83, saturation=1.0, brightness=0.5, kelvin=3500),
            HSBK(hue=49, saturation=1.0, brightness=0.5, kelvin=3500),
            HSBK(hue=58, saturation=1.0, brightness=0.5, kelvin=3500),
        ],
        "blissful": [
            HSBK(hue=303, saturation=0.18, brightness=0.82, kelvin=3500),
            HSBK(hue=232, saturation=0.46, brightness=0.53, kelvin=3500),
            HSBK(hue=252, saturation=0.37, brightness=0.69, kelvin=3500),
            HSBK(hue=245, saturation=0.29, brightness=0.81, kelvin=3500),
            HSBK(hue=303, saturation=0.37, brightness=0.18, kelvin=3500),
            HSBK(hue=56, saturation=1.0, brightness=1.0, kelvin=3500),
            HSBK(hue=321, saturation=0.39, brightness=0.78, kelvin=3500),
        ],
        "bias_lighting": [
            HSBK(hue=0, saturation=0.0, brightness=0.9019, kelvin=6500),
        ],
        "calaveras": [
            HSBK(hue=300, saturation=1.0, brightness=0.9019, kelvin=3500),
            HSBK(hue=270, saturation=1.0, brightness=0.9019, kelvin=3500),
            HSBK(hue=240, saturation=1.0, brightness=0.9019, kelvin=3500),
        ],
        "cheerful": [
            HSBK(hue=310, saturation=1.0, brightness=1.0, kelvin=3500),
            HSBK(hue=266, saturation=0.87, brightness=0.47, kelvin=3500),
            HSBK(hue=248, saturation=1.0, brightness=0.6, kelvin=3500),
            HSBK(hue=51, saturation=1.0, brightness=0.67, kelvin=3500),
            HSBK(hue=282, saturation=0.9, brightness=0.67, kelvin=3500),
        ],
        "christmas": [
            HSBK(hue=120, saturation=1.0, brightness=1.0, kelvin=6500),
            HSBK(hue=0, saturation=1.0, brightness=1.0, kelvin=3500),
            HSBK(hue=15, saturation=1.0, brightness=1.0, kelvin=3500),
            HSBK(hue=120, saturation=0.75, brightness=1.0, kelvin=3500),
        ],
        "dream": [
            HSBK(hue=201, saturation=0.76, brightness=0.23, kelvin=3500),
            HSBK(hue=183, saturation=0.75, brightness=0.32, kelvin=3500),
            HSBK(hue=199, saturation=0.22, brightness=0.62, kelvin=3500),
            HSBK(hue=223, saturation=0.22, brightness=0.91, kelvin=3500),
            HSBK(hue=219, saturation=0.29, brightness=0.52, kelvin=3500),
            HSBK(hue=167, saturation=0.62, brightness=0.55, kelvin=3500),
            HSBK(hue=201, saturation=0.76, brightness=0.23, kelvin=3500),
        ],
        "energizing": [
            HSBK(hue=0, saturation=0.0, brightness=1.0, kelvin=3500),
            HSBK(hue=205, saturation=0.47, brightness=1.0, kelvin=3500),
            HSBK(hue=191, saturation=0.89, brightness=1.0, kelvin=3500),
            HSBK(hue=242, saturation=1.0, brightness=0.42, kelvin=3500),
            HSBK(hue=180, saturation=0.87, brightness=0.27, kelvin=3500),
            HSBK(hue=0, saturation=0.0, brightness=0.3, kelvin=3500),
        ],
        "epic": [
            HSBK(hue=226, saturation=1.0, brightness=0.96, kelvin=3500),
            HSBK(hue=233, saturation=1.0, brightness=0.49, kelvin=3500),
            HSBK(hue=184, saturation=0.6, brightness=0.57, kelvin=3500),
            HSBK(hue=249, saturation=0.29, brightness=0.95, kelvin=3500),
            HSBK(hue=261, saturation=0.84, brightness=0.58, kelvin=3500),
            HSBK(hue=294, saturation=0.78, brightness=0.51, kelvin=3500),
        ],
        "evening": [
            HSBK(hue=34, saturation=0.75, brightness=0.902, kelvin=3500),
            HSBK(hue=34, saturation=0.8, brightness=0.902, kelvin=3500),
            HSBK(hue=39, saturation=0.75, brightness=0.902, kelvin=3500),
        ],
        "exciting": [
            HSBK(hue=0, saturation=1.0, brightness=1.0, kelvin=3500),
            HSBK(hue=40, saturation=1.0, brightness=1.0, kelvin=3500),
            HSBK(hue=60, saturation=1.0, brightness=1.0, kelvin=3500),
            HSBK(hue=122, saturation=1.0, brightness=1.0, kelvin=3500),
            HSBK(hue=239, saturation=1.0, brightness=1.0, kelvin=3500),
            HSBK(hue=271, saturation=1.0, brightness=1.0, kelvin=3500),
            HSBK(hue=294, saturation=1.0, brightness=1.0, kelvin=3500),
        ],
        "fantasy": [
            HSBK(hue=248, saturation=1.0, brightness=0.2074, kelvin=3500),
            HSBK(hue=242, saturation=0.75, brightness=0.902, kelvin=3500),
            HSBK(hue=164, saturation=0.99, brightness=0.902, kelvin=3500),
            HSBK(hue=300, saturation=1.0, brightness=0.7847, kelvin=3500),
        ],
        "focusing": [
            HSBK(hue=338, saturation=0.38, brightness=1.0, kelvin=3500),
            HSBK(hue=42, saturation=0.36, brightness=1.0, kelvin=3500),
            HSBK(hue=52, saturation=0.21, brightness=1.0, kelvin=3500),
            HSBK(hue=0, saturation=0.0, brightness=1.0, kelvin=3500),
            HSBK(hue=0, saturation=0.0, brightness=1.0, kelvin=3500),
        ],
        "gentle": [
            HSBK(hue=338, saturation=0.38, brightness=0.902, kelvin=3500),
            HSBK(hue=0, saturation=0.0, brightness=0.902, kelvin=9000),
            HSBK(hue=52, saturation=0.21, brightness=0.902, kelvin=3500),
            HSBK(hue=0, saturation=0.0, brightness=0.902, kelvin=2500),
            HSBK(hue=42, saturation=0.36, brightness=0.902, kelvin=3500),
        ],
        "halloween": [
            HSBK(hue=31, saturation=1.0, brightness=1.0, kelvin=3500),
            HSBK(hue=32, saturation=1.0, brightness=0.6, kelvin=3500),
            HSBK(hue=32, saturation=1.0, brightness=1.0, kelvin=3500),
            HSBK(hue=33, saturation=1.0, brightness=0.6, kelvin=3500),
            HSBK(hue=33, saturation=1.0, brightness=1.0, kelvin=3500),
            HSBK(hue=34, saturation=1.0, brightness=0.7, kelvin=3500),
        ],
        "hanukkah": [
            HSBK(hue=0, saturation=0.0, brightness=0.902, kelvin=6500),
            HSBK(hue=240, saturation=0.25, brightness=0.902, kelvin=3500),
            HSBK(hue=240, saturation=1.0, brightness=0.902, kelvin=3500),
            HSBK(hue=240, saturation=0.5, brightness=0.902, kelvin=3500),
            HSBK(hue=240, saturation=0.75, brightness=0.902, kelvin=3500),
        ],
        "holly": [
            HSBK(hue=117, saturation=1.0, brightness=1.0, kelvin=3500),
            HSBK(hue=116, saturation=0.9, brightness=1.0, kelvin=3500),
            HSBK(hue=1, saturation=1.0, brightness=1.0, kelvin=3500),
            HSBK(hue=118, saturation=1.0, brightness=0.5, kelvin=3500),
            HSBK(hue=360, saturation=1.0, brightness=0.9, kelvin=3500),
        ],
        "hygge": [
            HSBK(hue=39, saturation=0.75, brightness=0.9019, kelvin=3500),
            HSBK(hue=34, saturation=0.75, brightness=0.9019, kelvin=3500),
        ],
        "independence": [
            HSBK(hue=360, saturation=0.0, brightness=1.0, kelvin=3500),
            HSBK(hue=360, saturation=1.0, brightness=1.0, kelvin=3500),
            HSBK(hue=240, saturation=1.0, brightness=1.0, kelvin=3500),
        ],
        "intense": [
            HSBK(hue=242, saturation=0.75, brightness=1.0, kelvin=3500),
            HSBK(hue=300, saturation=1.0, brightness=0.87, kelvin=3500),
            HSBK(hue=164, saturation=0.99, brightness=1.0, kelvin=3500),
            HSBK(hue=248, saturation=1.0, brightness=0.23, kelvin=3500),
        ],
        "love": [
            HSBK(hue=315, saturation=0.45, brightness=0.8298, kelvin=3500),
            HSBK(hue=349, saturation=0.88, brightness=0.8117, kelvin=3500),
            HSBK(hue=345, saturation=0.76, brightness=0.9019, kelvin=3500),
            HSBK(hue=322, saturation=0.15, brightness=0.8839, kelvin=3500),
            HSBK(hue=307, saturation=0.16, brightness=0.9019, kelvin=3500),
        ],
        "kwanzaa": [
            HSBK(hue=120, saturation=1.0, brightness=1.0, kelvin=3500),
            HSBK(hue=0, saturation=1.0, brightness=1.0, kelvin=3500),
        ],
        "mellow": [
            HSBK(hue=359, saturation=0.31, brightness=0.59, kelvin=3500),
            HSBK(hue=315, saturation=0.24, brightness=0.82, kelvin=3500),
            HSBK(hue=241, saturation=1.0, brightness=0.4, kelvin=3500),
            HSBK(hue=256, saturation=0.36, brightness=0.5, kelvin=3500),
            HSBK(hue=79, saturation=0.05, brightness=0.4, kelvin=3500),
        ],
        "party": [
            HSBK(hue=300, saturation=1.0, brightness=0.902, kelvin=3500),
            HSBK(hue=265, saturation=1.0, brightness=0.902, kelvin=3500),
            HSBK(hue=240, saturation=1.0, brightness=0.902, kelvin=3500),
            HSBK(hue=240, saturation=0.75, brightness=0.902, kelvin=3500),
            HSBK(hue=214, saturation=0.85, brightness=0.902, kelvin=3500),
        ],
        "peaceful": [
            HSBK(hue=198, saturation=0.48, brightness=0.11, kelvin=3500),
            HSBK(hue=2, saturation=0.46, brightness=0.85, kelvin=3500),
            HSBK(hue=54, saturation=0.36, brightness=0.85, kelvin=3500),
            HSBK(hue=4, saturation=0.63, brightness=0.56, kelvin=3500),
            HSBK(hue=203, saturation=0.34, brightness=0.56, kelvin=3500),
        ],
        "powerful": [
            HSBK(hue=10, saturation=0.99, brightness=0.66, kelvin=3500),
            HSBK(hue=59, saturation=0.7, brightness=0.98, kelvin=3500),
            HSBK(hue=11, saturation=0.99, brightness=0.41, kelvin=3500),
            HSBK(hue=61, saturation=0.44, brightness=0.99, kelvin=3500),
            HSBK(hue=18, saturation=0.98, brightness=0.98, kelvin=3500),
            HSBK(hue=52, saturation=0.88, brightness=0.97, kelvin=3500),
            HSBK(hue=52, saturation=0.88, brightness=0.97, kelvin=3500),
        ],
        "proud": [
            HSBK(hue=32, saturation=1.0, brightness=0.9019, kelvin=3500),
            HSBK(hue=271, saturation=1.0, brightness=0.9019, kelvin=3500),
            HSBK(hue=349, saturation=0.88, brightness=0.8117, kelvin=3500),
            HSBK(hue=215, saturation=0.85, brightness=0.8839, kelvin=3500),
            HSBK(hue=120, saturation=0.5, brightness=0.8117, kelvin=3500),
            HSBK(hue=303, saturation=0.2, brightness=0.9019, kelvin=3500),
            HSBK(hue=60, saturation=1.0, brightness=0.9019, kelvin=3500),
        ],
        "pumpkin": [
            HSBK(hue=40, saturation=1.0, brightness=0.8532, kelvin=3500),
            HSBK(hue=10, saturation=1.0, brightness=0.4388, kelvin=3500),
            HSBK(hue=33, saturation=1.0, brightness=0.4875, kelvin=3500),
            HSBK(hue=46, saturation=1.0, brightness=0.8532, kelvin=3500),
            HSBK(hue=46, saturation=1.0, brightness=0.8532, kelvin=3500),
            HSBK(hue=40, saturation=0.55, brightness=0.9019, kelvin=3500),
        ],
        "relaxing": [
            HSBK(hue=110, saturation=0.95, brightness=1.0, kelvin=3500),
            HSBK(hue=71, saturation=1.0, brightness=1.0, kelvin=3500),
            HSBK(hue=123, saturation=0.85, brightness=0.33, kelvin=3500),
            HSBK(hue=120, saturation=0.5, brightness=0.1, kelvin=3500),
        ],
        "romance": [
            HSBK(hue=315, saturation=0.45, brightness=0.8298, kelvin=3500),
            HSBK(hue=349, saturation=0.88, brightness=0.8117, kelvin=3500),
            HSBK(hue=345, saturation=0.76, brightness=0.9019, kelvin=3500),
            HSBK(hue=322, saturation=0.15, brightness=0.8839, kelvin=3500),
            HSBK(hue=307, saturation=0.16, brightness=0.9019, kelvin=3500),
        ],
        "santa": [
            HSBK(hue=0, saturation=1.0, brightness=1.0, kelvin=3500),
            HSBK(hue=351, saturation=0.05, brightness=1.0, kelvin=3500),
            HSBK(hue=2, saturation=1.0, brightness=0.58, kelvin=3500),
            HSBK(hue=0, saturation=0.0, brightness=0.52, kelvin=3500),
        ],
        "serene": [
            HSBK(hue=179, saturation=0.1, brightness=0.91, kelvin=3500),
            HSBK(hue=215, saturation=0.85, brightness=0.98, kelvin=3500),
            HSBK(hue=205, saturation=0.44, brightness=0.37, kelvin=3500),
            HSBK(hue=94, saturation=0.63, brightness=0.25, kelvin=3500),
            HSBK(hue=100, saturation=0.26, brightness=0.42, kelvin=3500),
            HSBK(hue=132, saturation=0.46, brightness=0.88, kelvin=3500),
            HSBK(hue=211, saturation=0.73, brightness=0.97, kelvin=3500),
        ],
        "shamrock": [
            HSBK(hue=125, saturation=1.0, brightness=0.9019, kelvin=3500),
            HSBK(hue=130, saturation=0.85, brightness=0.6764, kelvin=3500),
            HSBK(hue=100, saturation=1.0, brightness=0.8117, kelvin=3500),
            HSBK(hue=135, saturation=0.5, brightness=0.4509, kelvin=3500),
            HSBK(hue=110, saturation=1.0, brightness=0.7666, kelvin=3500),
            HSBK(hue=120, saturation=1.0, brightness=0.9019, kelvin=3500),
        ],
        "soothing": [
            HSBK(hue=336, saturation=0.18, brightness=0.67, kelvin=3500),
            HSBK(hue=335, saturation=0.5, brightness=0.67, kelvin=3500),
            HSBK(hue=0, saturation=0.0, brightness=1.0, kelvin=3500),
            HSBK(hue=302, saturation=0.69, brightness=1.0, kelvin=3500),
            HSBK(hue=330, saturation=0.45, brightness=0.58, kelvin=3500),
        ],
        "spacey": [
            HSBK(hue=120, saturation=0.5, brightness=0.0902, kelvin=3500),
            HSBK(hue=71, saturation=1.0, brightness=0.902, kelvin=3500),
            HSBK(hue=110, saturation=0.95, brightness=0.902, kelvin=3500),
            HSBK(hue=123, saturation=0.85, brightness=0.2976, kelvin=3500),
        ],
        "sports": [
            HSBK(hue=59, saturation=0.81, brightness=0.96, kelvin=3500),
            HSBK(hue=120, saturation=1.0, brightness=0.96, kelvin=3500),
            HSBK(hue=120, saturation=0.74, brightness=1.0, kelvin=3500),
        ],
        "spring": [
            HSBK(hue=184, saturation=1.0, brightness=0.5, kelvin=3500),
            HSBK(hue=299, saturation=1.0, brightness=0.5, kelvin=3500),
            HSBK(hue=49, saturation=1.0, brightness=0.5, kelvin=3500),
            HSBK(hue=198, saturation=1.0, brightness=0.5, kelvin=3500),
        ],
        "stardust": [
            HSBK(hue=0, saturation=0.0, brightness=0.902, kelvin=6500),
            HSBK(hue=209, saturation=0.5, brightness=0.902, kelvin=3500),
            HSBK(hue=0, saturation=0.0, brightness=0.902, kelvin=6497),
            HSBK(hue=260, saturation=0.3, brightness=0.902, kelvin=3500),
        ],
        "thanksgiving": [
            HSBK(hue=50, saturation=0.81, brightness=0.7757, kelvin=3500),
            HSBK(hue=35, saturation=0.81, brightness=0.7757, kelvin=3500),
            HSBK(hue=30, saturation=1.0, brightness=0.902, kelvin=3500),
            HSBK(hue=35, saturation=0.85, brightness=0.5863, kelvin=3500),
            HSBK(hue=15, saturation=0.44, brightness=0.5863, kelvin=3500),
        ],
        "tranquil": [
            HSBK(hue=0, saturation=0.0, brightness=0.0, kelvin=3500),
            HSBK(hue=205, saturation=0.74, brightness=0.96, kelvin=3500),
            HSBK(hue=203, saturation=0.94, brightness=0.96, kelvin=3500),
            HSBK(hue=241, saturation=0.99, brightness=1.0, kelvin=3500),
            HSBK(hue=37, saturation=0.75, brightness=0.99, kelvin=3500),
            HSBK(hue=43, saturation=0.83, brightness=0.53, kelvin=3500),
        ],
        "warming": [
            HSBK(hue=4, saturation=1.0, brightness=0.76, kelvin=3500),
            HSBK(hue=42, saturation=0.36, brightness=0.96, kelvin=3500),
            HSBK(hue=355, saturation=0.81, brightness=0.86, kelvin=3500),
            HSBK(hue=44, saturation=0.44, brightness=0.65, kelvin=3500),
            HSBK(hue=51, saturation=0.85, brightness=0.59, kelvin=3500),
            HSBK(hue=0, saturation=0.0, brightness=0.3, kelvin=3500),
        ],
        "zombie": [
            HSBK(hue=156, saturation=1.0, brightness=0.9019, kelvin=3500),
            HSBK(hue=156, saturation=1.0, brightness=0.9019, kelvin=3500),
            HSBK(hue=270, saturation=1.0, brightness=0.859, kelvin=3500),
            HSBK(hue=147, saturation=1.0, brightness=0.4295, kelvin=3500),
            HSBK(hue=281, saturation=1.0, brightness=0.4295, kelvin=3500),
            HSBK(hue=139, saturation=1.0, brightness=0.6442, kelvin=3500),
        ],
    }

    @classmethod
    def get(cls, name: str) -> Theme:
        """Get a theme by name.

        Args:
            name: Theme name (case-insensitive)

        Returns:
            Theme object

        Raises:
            KeyError: If theme name is not found

        Example:
            ```python
            from lifx.theme import ThemeLibrary

            evening_theme = ThemeLibrary.get("evening")
            await light.apply_theme(evening_theme, power_on=True)
            ```
        """
        normalized_name = name.lower()
        if normalized_name not in cls._THEMES:
            available = ", ".join(sorted(cls._THEMES.keys()))
            raise KeyError(f"Theme '{name}' not found. Available themes: {available}")
        return Theme(cls._THEMES[normalized_name])

    @classmethod
    def list(cls) -> list[str]:
        """List all available theme names.

        Returns:
            Sorted list of theme names

        Example:
            ```python
            from lifx.theme import ThemeLibrary

            all_themes = ThemeLibrary.list()
            for theme_name in all_themes:
                print(f"- {theme_name}")
            ```
        """
        return sorted(cls._THEMES.keys())

    @classmethod
    def get_by_category(cls, category: str) -> dict[str, Theme]:
        """Get all themes in a category.

        Args:
            category: Category name (seasonal, mood, holiday, time, etc.)

        Returns:
            Dictionary of Theme objects in the category

        Raises:
            ValueError: If category is not recognized
        """
        category_lower = category.lower()

        categories = {
            "seasonal": [
                "spring",
                "autumn",
                "winter",
            ],
            "holiday": [
                "christmas",
                "halloween",
                "hanukkah",
                "kwanzaa",
                "shamrock",
                "thanksgiving",
                "calaveras",
                "pumpkin",
                "santa",
                "holly",
                "independence",
                "proud",
            ],
            "mood": [
                "peaceful",
                "serene",
                "relaxing",
                "mellow",
                "gentle",
                "soothing",
                "blissful",
                "cheerful",
                "romantic",
                "romance",
                "love",
                "energizing",
                "exciting",
                "epic",
                "intense",
                "powerful",
                "dramatic",
                "warming",
            ],
            "ambient": [
                "dream",
                "fantasy",
                "spacey",
                "stardust",
                "zombie",
                "party",
            ],
            "functional": [
                "focusing",
                "evening",
                "bias_lighting",
            ],
            "atmosphere": [
                "hygge",
                "tranquil",
                "sports",
            ],
        }

        if category_lower not in categories:
            available = ", ".join(sorted(categories.keys()))
            raise ValueError(
                f"Category '{category}' not recognized. "
                f"Available categories: {available}"
            )

        return {
            name: cls.get(name)
            for name in categories[category_lower]
            if name in cls._THEMES
        }


def get_theme(name: str) -> Theme:
    """Get a theme by name.

    Convenience function equivalent to ThemeLibrary.get(name).

    Args:
        name: Theme name (case-insensitive)

    Returns:
        Theme object

    Example:
        ```python
        from lifx.theme import get_theme

        evening = get_theme("evening")
        await light.apply_theme(evening, power_on=True)
        ```
    """
    return ThemeLibrary.get(name)
