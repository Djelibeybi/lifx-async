"""Built-in theme library generated from the LIFX app's own palettes.

The theme data is generated from ``data/themes.jsonl`` by
``scripts/generate_theme_data.py``, synced from the LIFX app via hardware capture on
2026-08-14. The library carries 168 resolvable names: 138 app theme slugs,
28 pre-6.4.0 keys with no app counterpart (category ``Library``), and 2
rename aliases (``forest`` and ``aurora_borealis``) that resolve to their
renamed targets.

Palette order carries no meaning: the app shuffles the order on every
application, so palettes are stored canonically sorted and all palette
comparison is unordered.

Attribution: the 28 ``Library`` records are not app captures. They ship
byte-identical at uint16 to the palettes this library carried before 6.4.0,
which came from two upstream projects:

* https://github.com/Djelibeybi/aiolifx-themes
* https://github.com/pkivolowitz/lifx — the palette themes (``fire``,
  ``water``, ``neon``, ``tropical``, ``arctic``, and the rest of that set),
  each originally a ``(hue_a, hue_b, hue_c, saturation)`` tuple expanded to
  three HSBK colours.
"""

from __future__ import annotations

from lifx.theme.data import THEMES, ThemeRecord
from lifx.theme.slug import derive_slug
from lifx.theme.theme import Theme

#: Pre-6.4.0 legacy category names and their locked fates — a migration shim,
#: deliberately private and unexported (D-03), not taxonomy. Each legacy name
#: maps to ``(replacement app category, resolves)``: a ``True`` entry returns
#: the replacement category's themes; a ``False`` entry raises, and its
#: replacement exists so the raising branch can name it (D-02). Keys MUST be
#: derive_slug-form: the lookup probes this dict with the derive_slug-normalised
#: caller input, so a future non-slug-form key would silently never match and
#: fall through to the unknown-category error (review F4).
_LEGACY_CATEGORIES: dict[str, tuple[str, bool]] = {
    "holiday": ("Holidays", True),
    "mood": ("Moods", True),
    "seasonal": ("Nature", False),
    "ambient": ("Play", False),
    "functional": ("Library", False),
    "atmosphere": ("Moods", False),
}


class ThemeLibrary:
    """Collection of built-in colour themes for LIFX devices.

    Provides access to every theme in the LIFX app (sport themes excluded)
    plus the pre-6.4.0 library keys, organised by the app's own categories.

    Example:
        ```python
        # Get a specific theme
        evening_theme = ThemeLibrary.get("evening")

        # List all available themes
        all_themes = ThemeLibrary.get_available_themes()

        # Get themes by category
        categories = ThemeLibrary.get_categories()
        holidays = ThemeLibrary.get_by_category("Holidays")

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
    def get_categories(cls) -> list[str]:
        """Get every category present in the library's data.

        Returns:
            Sorted ``list[str]`` of the category names present in the
            library's theme records.

        Example:
            ```python
            from lifx.theme import ThemeLibrary

            for category in ThemeLibrary.get_categories():
                print(f"- {category}")
            ```
        """
        return sorted({record.category for record in cls._THEMES.values()})

    @classmethod
    def _slugs_for_category(cls, key: str) -> set[str]:
        """Collect the slugs of every record whose category normalises to key.

        The set comprehension dedups the two rename-alias keys that bind a
        shared record, so an aliased theme appears once in the result.

        Args:
            key: A derive_slug-normalised category name.

        Returns:
            Set of theme slugs in the matching category; empty if none match.
        """
        return {
            record.slug
            for record in cls._THEMES.values()
            if derive_slug(record.category) == key
        }

    @classmethod
    def get_by_category(cls, category: str) -> dict[str, Theme]:
        """Get all themes in a category.

        Args:
            category: Category name. Matching is case- and punctuation-
                insensitive — both sides are normalised by the slug rule, so
                ``"Art Series"``, ``"art series"`` and ``"art_series"`` all
                resolve. The categories are Archives, Art Series, Holidays,
                Library (pre-6.4.0 keys with no app counterpart, defined by
                this library rather than the LIFX app), Moods, Music, Nature,
                Play and Space. Two pre-6.4.0 legacy names still map:
                ``holiday`` (to Holidays) and ``mood`` (to Moods).

        Returns:
            Dictionary of Theme objects in the category, keyed by slug and
            sorted by slug.

        Raises:
            ValueError: If the category name is unknown, or is one of the
                four pre-6.4.0 names (``seasonal``, ``ambient``,
                ``functional``, ``atmosphere``) that no longer exist — the
                message names the closest replacement.
        """
        key = derive_slug(category)

        # App taxonomy first, legacy map second (no current name collides).
        slugs = cls._slugs_for_category(key)
        if slugs:
            return {slug: cls.get(slug) for slug in sorted(slugs)}

        if key in _LEGACY_CATEGORIES:
            replacement, resolves = _LEGACY_CATEGORIES[key]
            if resolves:
                replacement_slugs = cls._slugs_for_category(derive_slug(replacement))
                return {slug: cls.get(slug) for slug in sorted(replacement_slugs)}
            raise ValueError(
                f"Category '{category}' is a pre-6.4.0 category name that no "
                f"longer exists. Its closest replacement is '{replacement}'."
            )

        raise ValueError(
            f"Category '{category}' is not recognised. "
            f"Available categories: {', '.join(cls.get_categories())}"
        )


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
