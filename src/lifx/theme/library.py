"""Built-in theme library generated from the LIFX app's own palettes.

The theme data is generated from ``data/themes.jsonl`` by
``scripts/generate_theme_data.py``, synced from the LIFX app via hardware capture on
2026-08-14. The library carries 168 resolvable names: 138 app theme slugs,
28 pre-v1.2 keys with no app counterpart (category ``Library``), and 2
rename aliases (``forest`` and ``aurora_borealis``) that resolve to their
renamed targets.

Palette order carries no meaning: the app shuffles the order on every
application, so palettes are stored canonically sorted and all palette
comparison is unordered.

Attribution: the 28 ``Library`` records are not app captures. They ship
byte-identical at uint16 to the palettes this library carried before v1.2,
which came from two upstream projects:

* https://github.com/Djelibeybi/aiolifx-themes
* https://github.com/pkivolowitz/lifx — the palette themes (``fire``,
  ``water``, ``neon``, ``tropical``, ``arctic``, and the rest of that set),
  each originally a ``(hue_a, hue_b, hue_c, saturation)`` tuple expanded to
  three HSBK colours.
"""

from __future__ import annotations

from lifx.theme.data import THEMES, ThemeRecord
from lifx.theme.theme import Theme


class ThemeLibrary:
    """Collection of built-in colour themes for LIFX devices.

    Provides access to every theme in the LIFX app (sport themes excluded)
    plus the pre-v1.2 library keys, organised by the app's own categories.

    Example:
        ```python
        # Get a specific theme
        evening_theme = ThemeLibrary.get("evening")

        # List all available themes
        all_themes = ThemeLibrary.get_available_themes()

        # Get themes by category
        seasonal = ThemeLibrary.get_by_category("seasonal")

        # Apply to a light
        await light.apply_theme(evening_theme, power_on=True)
        ```
    """

    # The generated theme registry. Every lookup classmethod reads this class
    # attribute rather than the module-global `THEMES`, so a subclass that
    # rebinds it sees a consistent library across get(), get_available_themes()
    # and get_by_category(). Phase 7 owns replacing its taxonomy (META-04).
    _THEMES: dict[str, ThemeRecord] = THEMES

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
            raise KeyError(
                f"Theme '{name}' not found. Use "
                f"ThemeLibrary.get_available_themes() to list the "
                f"available themes."
            )
        record = cls._THEMES[normalized_name]
        # Theme.__init__ copies the palette, so mutating a returned Theme can
        # never corrupt the library's own record.
        return Theme(
            list(record.colors),
            slug=record.slug,
            name=record.name,
            category=record.category,
            disposition=record.disposition,
            replaced_by=record.replaced_by,
        )

    @classmethod
    def get_available_themes(cls) -> list[str]:
        """Get all available themes by name.

        Returns:
            Sorted list of theme names

        Example:
            ```python
            from lifx.theme import ThemeLibrary

            all_themes = ThemeLibrary.get_available_themes()
            for theme_name in all_themes:
                print(f"- {theme_name}")
            ```
        """
        return sorted(cls._THEMES)

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
