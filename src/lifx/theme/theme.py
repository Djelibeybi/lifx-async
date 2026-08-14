"""Theme support for LIFX devices.

This module provides the Theme class for managing collections of colors
that can be applied to LIFX devices.
"""

from __future__ import annotations

import random
from collections import Counter
from collections.abc import Iterator

from lifx.color import HSBK, Colors


class Theme:
    """A collection of colors representing a theme or color palette.

    Themes can be applied to LIFX devices to coordinate colors across
    multiple lights. Supports both single-zone and multi-zone devices.

    Attributes:
        colors: List of HSBK colors in the theme
        slug: Library key for a theme from ``ThemeLibrary`` (None for a
            caller-constructed theme)
        name: Display name for a theme from ``ThemeLibrary`` (None for a
            caller-constructed theme)
        category: Category for a theme from ``ThemeLibrary`` (None for a
            caller-constructed theme)

    Note:
        ``shuffled()`` and ``random()`` return identity-less copies: slug,
        name and category do not propagate. This is a known deferred
        limitation of the identity round-trip guarantee.

    Example:
        ```python
        # Create a theme with specific colors
        theme = Theme(
            [
                HSBK(hue=0, saturation=1.0, brightness=1.0, kelvin=3500),  # Red
                HSBK(hue=120, saturation=1.0, brightness=1.0, kelvin=3500),  # Green
                HSBK(hue=240, saturation=1.0, brightness=1.0, kelvin=3500),  # Blue
            ]
        )

        # Access colors
        for color in theme:
            print(f"Color: {color.hue}°")

        # Get a specific color
        first_color = theme[0]

        # Add more colors
        theme.add_color(HSBK(hue=180, saturation=1.0, brightness=1.0, kelvin=3500))
        ```
    """

    def __init__(
        self,
        colors: list[HSBK] | None = None,
        *,
        slug: str | None = None,
        name: str | None = None,
        category: str | None = None,
    ) -> None:
        """Create a new theme with the given colors.

        Args:
            colors: List of HSBK colors (defaults to white if None or empty)
            slug: Library key for the theme (attached by ``ThemeLibrary``)
            name: Display name for the theme (attached by ``ThemeLibrary``)
            category: Category for the theme (attached by ``ThemeLibrary``)

        Example:
            ```python
            # Create from list of colors
            theme = Theme([color1, color2, color3])

            # Create with default white color
            theme = Theme()
            ```
        """
        if colors and len(colors) > 0:
            # Copied, never aliased: a Theme built over a caller's list would
            # otherwise mutate that list through add_color(), and a Theme
            # built over a cached or shared list would let add_color() corrupt
            # the source. Every construction path gets the isolation, not just
            # ThemeLibrary.get().
            self.colors: list[HSBK] = list(colors)
        else:
            # Default to white if no colors provided
            self.colors = [Colors.WHITE_NEUTRAL]
        self.slug = slug
        self.name = name
        self.category = category

    def add_color(self, color: HSBK) -> None:
        """Add a color to the theme.

        Args:
            color: HSBK color to add

        Example:
            ```python
            theme = Theme()
            theme.add_color(HSBK(hue=0, saturation=1.0, brightness=1.0, kelvin=3500))
            ```
        """
        self.colors.append(color)

    def random(self) -> HSBK:
        """Get a random color from the theme.

        Returns:
            A random HSBK color from the theme

        Example:
            ```python
            theme = Theme([red, green, blue])
            color = theme.random()
            ```
        """
        return random.choice(self.colors)

    def shuffled(self) -> Theme:
        """Get a new theme with colors in random order.

        Returns:
            New Theme instance with shuffled colors

        Example:
            ```python
            theme = Theme([color1, color2, color3])
            shuffled_theme = theme.shuffled()
            ```
        """
        shuffled_colors = self.colors.copy()
        random.shuffle(shuffled_colors)
        return Theme(shuffled_colors)

    def get_next_bounds_checked(self, index: int) -> HSBK:
        """Get the next color after index or the last color if at end.

        Args:
            index: Index of current color

        Returns:
            Next HSBK color or the last color if index is at the end

        Example:
            ```python
            theme = Theme([red, green, blue])
            color = theme.get_next_bounds_checked(0)  # green
            color = theme.get_next_bounds_checked(2)  # blue (last color)
            ```
        """
        if index + 1 < len(self.colors):
            return self.colors[index + 1]
        return self.colors[-1]

    def ensure_color(self) -> None:
        """Ensure the theme has at least one color.

        If the theme is empty, adds a default white color.
        """
        if not self.colors:
            self.colors.append(
                HSBK(hue=0, saturation=0, brightness=1.0, kelvin=3500)
            )  # pragma: no cover

    def __len__(self) -> int:
        """Get the number of colors in the theme."""
        return len(self.colors)

    def __iter__(self) -> Iterator[HSBK]:
        """Iterate over colors in the theme."""
        return iter(self.colors)

    def __getitem__(self, index: int) -> HSBK:
        """Get a color by index.

        Args:
            index: Index of the color (0-based)

        Returns:
            HSBK color at the given index

        Raises:
            IndexError: If index is out of range

        Example:
            ```python
            theme = Theme([red, green, blue])
            color = theme[1]  # green
            ```
        """
        return self.colors[index]

    def __contains__(self, color: HSBK) -> bool:
        """Check if a color is in the theme.

        Args:
            color: HSBK color to check

        Returns:
            True if color is in theme (by value comparison)

        Example:
            ```python
            theme = Theme([red, green, blue])
            if red in theme:
                print("Red is in the theme")
            ```
        """
        return any(c == color for c in self.colors)

    def __eq__(self, other: object) -> bool:
        """Two themes are equal if their palettes are the same multiset of colors.

        Order is never compared because the app shuffles palette order on
        every application, so two orderings of one palette are the same
        theme. Identity (slug, name, category) is also excluded: an
        identity-bearing library theme and a caller-built theme with the
        same palette are the same theme. Colors compare at uint16
        (protocol) granularity via HSBK equality, and duplicate counts
        matter — a multiset comparison, not a set comparison.

        Note:
            Defining ``__eq__`` without ``__hash__`` deliberately makes
            Theme unhashable: its palette is mutable via ``add_color()``,
            so a stable hash cannot be provided.
        """
        if not isinstance(other, Theme):
            return NotImplemented
        return Counter(self.colors) == Counter(other.colors)

    def __repr__(self) -> str:
        """Return a string representation of the theme."""
        color_count = len(self.colors)
        return f"Theme({color_count} colors)"
