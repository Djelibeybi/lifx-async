"""Built-in theme library generated from the LIFX app's own palettes.

The theme data is generated from ``data/themes.jsonl`` by
``scripts/generate_theme_data.py``, synced from the LIFX app via hardware capture on
2026-08-14. The library carries 168 resolvable names: 138 app theme slugs,
28 pre-6.3.0 keys with no app counterpart (category ``Library``), and 2
rename aliases (``forest`` and ``aurora_borealis``) that resolve to their
renamed targets. Every name reports its fate in ``disposition``, including
the two aliases, which carry ``"renamed"`` and name the canonical key in
``replaced_by``.

Colours are stored in source order. For most themes the order carries no
meaning, but for a grid or stripe theme it is the layout, so it is never
reordered. Palette comparison (``Theme.palette_equals()``) stays unordered.

Attribution: the 28 ``Library`` records are not app captures. They ship
byte-identical at uint16 to the palettes this library carried before 6.3.0
(the release that replaced the hand-written library with this generated
data), which came from two upstream projects:

* https://github.com/Djelibeybi/aiolifx-themes
* https://github.com/pkivolowitz/lifx — the palette themes (``fire``,
  ``water``, ``neon``, ``tropical``, ``arctic``, and the rest of that set),
  each originally a ``(hue_a, hue_b, hue_c, saturation)`` tuple expanded to
  three HSBK colours.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Literal

from lifx.theme.data import THEMES, ThemeRecord
from lifx.theme.schema import tag_sort_key
from lifx.theme.slug import derive_slug
from lifx.theme.theme import Theme


class ThemeLibrary:
    """Collection of built-in colour themes for LIFX devices.

    Provides access to every theme in the LIFX app (sport themes excluded)
    plus the pre-6.3.0 library keys, organised by the app's own categories.

    Example:
        ```python
        # Get a specific theme
        evening_theme = ThemeLibrary.get("evening")

        # List all available themes
        all_themes = ThemeLibrary.get_available_themes()

        # Get themes by category
        categories = ThemeLibrary.get_categories()
        holidays = ThemeLibrary.get_by_category("Holidays")

        # Find themes by tag, category and effect mode
        calm = ThemeLibrary.get_by_tag("Calm")
        cosy_grids = ThemeLibrary.find(
            tags=["Calm", "Cozy"], match="any", static_mode="grid_static"
        )

        # Apply to a light
        await light.apply_theme(evening_theme, power_on=True)
        ```
    """

    # The generated theme registry. Every lookup classmethod reads this class
    # attribute rather than the module-global `THEMES`, so a subclass that
    # rebinds it sees a consistent library across get(), get_available_themes(),
    # get_categories() and get_by_category().
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
        record = cls._THEMES.get(name.lower())
        if record is None:
            raise KeyError(
                f"Theme '{name}' not found. Use "
                f"ThemeLibrary.get_available_themes() to list the "
                f"available themes."
            )
        # Theme.__init__ copies the palette, so mutating a returned Theme can
        # never corrupt the library's own record.
        return Theme(
            list(record.colors),
            slug=record.slug,
            name=record.name,
            category=record.category,
            disposition=record.disposition,
            replaced_by=record.replaced_by,
            static_mode=record.static_mode,
            dynamic_mode=record.dynamic_mode,
            tags=record.tags,
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

        The slug rule is applied to the *distinct* category names (nine
        today), never once per record: a 168-record scan would run 168
        regex substitutions to answer a question with nine possible
        answers.

        Rename-alias records are skipped. An alias key carries
        ``disposition == "renamed"`` and its target's category, so
        including it would list one theme twice in its own category —
        once under the canonical slug and once under the dead one.

        Args:
            key: A derive_slug-normalised category name.

        Returns:
            Set of theme slugs in the matching category; empty if none match.
        """
        matching = {
            category
            for category in {record.category for record in cls._THEMES.values()}
            if derive_slug(category) == key
        }
        if not matching:
            return set()
        return {
            record.slug
            for record in cls._THEMES.values()
            if record.category in matching and record.disposition != "renamed"
        }

    @classmethod
    def get_by_category(cls, category: str) -> dict[str, Theme]:
        """Get all themes in a category.

        Args:
            category: Category name. Matching is case- and punctuation-
                insensitive: both sides are normalised by the slug rule, so
                ``"Art Series"``, ``"art series"`` and ``"art_series"`` all
                resolve. The categories are Archives, Art Series, Holidays,
                Library (pre-6.3.0 keys with no app counterpart, defined by
                this library rather than the LIFX app), Moods, Music, Nature,
                Play and Space.

        Returns:
            Dictionary of Theme objects in the category, keyed by slug and
            sorted by slug.

        Raises:
            ValueError: If ``category`` is not a string, or names no category
                in the library. The pre-6.4.0 names (``seasonal``, ``holiday``,
                ``mood``, ``ambient``, ``functional``, ``atmosphere``) are
                among the unrecognised: they were never a taxonomy this data
                carries, and the message lists the categories that exist.
        """
        slugs = cls._require_category_slugs(category)
        return {slug: cls.get(slug) for slug in sorted(slugs)}

    @classmethod
    def _require_category_slugs(cls, category: object) -> set[str]:
        """Slugs in ``category``, raising the documented ValueError otherwise."""
        if type(category) is not str:
            # derive_slug() would raise AttributeError on a non-string, which
            # contradicts the documented ValueError and reads as a library
            # bug rather than a bad argument.
            raise ValueError(
                f"Category must be a string, got {type(category).__name__}. "
                f"Available categories: {', '.join(cls.get_categories())}"
            )
        slugs = cls._slugs_for_category(derive_slug(category))
        if not slugs:
            raise ValueError(
                f"Category '{category}' is not recognised. "
                f"Available categories: {', '.join(cls.get_categories())}"
            )
        return slugs

    @classmethod
    def _records(cls) -> list[ThemeRecord]:
        """Every record except rename aliases, which would list a theme twice."""
        return [r for r in cls._THEMES.values() if r.disposition != "renamed"]

    @classmethod
    def get_tags(cls) -> list[str]:
        """Get every tag present in the library's data.

        Tags are the LIFX app's search tags, such as ``"Calm"`` or
        ``"Date night"``. A theme with no app source carries none.

        Returns:
            Distinct tags, sorted case-insensitively.
        """
        return sorted({tag for r in cls._records() for tag in r.tags}, key=tag_sort_key)

    @classmethod
    def _require_tag_slugs(cls, tag: object) -> set[str]:
        """Slugs of every theme carrying ``tag``, matched by the slug rule.

        Raises:
            ValueError: If ``tag`` is not a string or matches no tag.
        """
        available = cls.get_tags()
        if type(tag) is not str:
            raise ValueError(
                f"Tag must be a string, got {type(tag).__name__}. "
                f"Available tags: {', '.join(available)}"
            )
        key = derive_slug(tag)
        matching = {t for t in available if derive_slug(t) == key}
        if not matching:
            raise ValueError(
                f"Tag '{tag}' is not recognised. Available tags: {', '.join(available)}"
            )
        return {r.slug for r in cls._records() if matching.intersection(r.tags)}

    @classmethod
    def get_by_tag(cls, tag: str) -> dict[str, Theme]:
        """Get all themes carrying a tag.

        Args:
            tag: Tag name. Matching is case- and punctuation-insensitive:
                both sides are normalised by the slug rule, so
                ``"Date night"``, ``"date night"`` and ``"date_night"`` all
                resolve.

        Returns:
            Dictionary of Theme objects keyed by slug and sorted by slug.

        Raises:
            ValueError: If ``tag`` is not a string, or matches no tag in the
                library. The message lists the tags that exist.
        """
        return {slug: cls.get(slug) for slug in sorted(cls._require_tag_slugs(tag))}

    @classmethod
    def find(
        cls,
        *,
        tags: Iterable[str] = (),
        match: Literal["all", "any"] = "all",
        category: str | None = None,
        static_mode: str | None = None,
    ) -> dict[str, Theme]:
        """Find themes by tags, category and static mode together.

        Every given criterion must hold. ``match`` decides only how the
        tags combine: ``"all"`` requires every tag, ``"any"`` at least one.
        With no criteria, every theme is returned.

        Args:
            tags: Tag names, matched as ``get_by_tag()`` matches them.
            match: ``"all"`` or ``"any"``.
            category: Category name, matched as ``get_by_category()``
                matches it.
            static_mode: Exact static mode, such as ``"grid_static"``.

        Returns:
            Dictionary of matching Theme objects keyed by slug and sorted by
            slug; empty when valid criteria select nothing.

        Raises:
            TypeError: If ``tags`` is a single string rather than an
                iterable of tags.
            ValueError: If ``match`` is invalid, or a tag, category or
                static mode names nothing in the library.

        Example:
            ```python
            from lifx.theme import ThemeLibrary

            calm_grids = ThemeLibrary.find(tags=["Calm"], static_mode="grid_static")
            ```
        """
        if isinstance(tags, str):
            raise TypeError(
                "tags must be an iterable of tags, not a single string; "
                "pass ['Calm'] for one tag"
            )
        if match not in ("all", "any"):
            raise ValueError(f"match must be 'all' or 'any', got {match!r}")
        records = cls._records()
        selected = {r.slug for r in records}
        tag_sets = [cls._require_tag_slugs(tag) for tag in tags]
        if tag_sets:
            if match == "all":
                selected &= set.intersection(*tag_sets)
            else:
                selected &= set.union(*tag_sets)
        if category is not None:
            selected &= cls._require_category_slugs(category)
        if static_mode is not None:
            modes = sorted({r.static_mode for r in records})
            if static_mode not in modes:
                raise ValueError(
                    f"static_mode '{static_mode}' is not recognised. "
                    f"Available static modes: {', '.join(modes)}"
                )
            selected &= {r.slug for r in records if r.static_mode == static_mode}
        return {slug: cls.get(slug) for slug in sorted(selected)}


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
