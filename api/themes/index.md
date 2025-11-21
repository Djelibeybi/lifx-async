# Themes API Reference

The theme system provides professionally-curated color palettes for coordinated lighting across LIFX devices.

## Theme Class

The `Theme` class represents a collection of HSBK colors forming a coordinated palette.

### Theme

```python
Theme(colors: list[HSBK] | None = None)
```

A collection of colors representing a theme or color palette.

Themes can be applied to LIFX devices to coordinate colors across multiple lights. Supports both single-zone and multi-zone devices.

| ATTRIBUTE | DESCRIPTION                                             |
| --------- | ------------------------------------------------------- |
| `colors`  | List of HSBK colors in the theme **TYPE:** `list[HSBK]` |

Example

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

| PARAMETER | DESCRIPTION                                                                     |
| --------- | ------------------------------------------------------------------------------- |
| `colors`  | List of HSBK colors (defaults to white if None or empty) **TYPE:** \`list[HSBK] |

Example

```python
# Create from list of colors
theme = Theme([color1, color2, color3])

# Create with default white color
theme = Theme()
```

| METHOD                    | DESCRIPTION                                                 |
| ------------------------- | ----------------------------------------------------------- |
| `add_color`               | Add a color to the theme.                                   |
| `random`                  | Get a random color from the theme.                          |
| `shuffled`                | Get a new theme with colors in random order.                |
| `get_next_bounds_checked` | Get the next color after index or the last color if at end. |
| `ensure_color`            | Ensure the theme has at least one color.                    |
| `__len__`                 | Get the number of colors in the theme.                      |
| `__iter__`                | Iterate over colors in the theme.                           |
| `__getitem__`             | Get a color by index.                                       |
| `__contains__`            | Check if a color is in the theme.                           |
| `__repr__`                | Return a string representation of the theme.                |

Source code in `src/lifx/theme/theme.py`

````python
def __init__(self, colors: list[HSBK] | None = None) -> None:
    """Create a new theme with the given colors.

    Args:
        colors: List of HSBK colors (defaults to white if None or empty)

    Example:
        ```python
        # Create from list of colors
        theme = Theme([color1, color2, color3])

        # Create with default white color
        theme = Theme()
        ```
    """
    if colors and len(colors) > 0:
        self.colors: list[HSBK] = colors
    else:
        # Default to white if no colors provided
        self.colors = [Colors.WHITE_NEUTRAL]
````

#### Functions

##### add_color

```python
add_color(color: HSBK) -> None
```

Add a color to the theme.

| PARAMETER | DESCRIPTION                        |
| --------- | ---------------------------------- |
| `color`   | HSBK color to add **TYPE:** `HSBK` |

Example

```python
theme = Theme()
theme.add_color(HSBK(hue=0, saturation=1.0, brightness=1.0, kelvin=3500))
```

Source code in `src/lifx/theme/theme.py`

````python
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
````

##### random

```python
random() -> HSBK
```

Get a random color from the theme.

| RETURNS | DESCRIPTION                        |
| ------- | ---------------------------------- |
| `HSBK`  | A random HSBK color from the theme |

Example

```python
theme = Theme([red, green, blue])
color = theme.random()
```

Source code in `src/lifx/theme/theme.py`

````python
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
    return random.choice(self.colors)  # nosec
````

##### shuffled

```python
shuffled() -> Theme
```

Get a new theme with colors in random order.

| RETURNS | DESCRIPTION                             |
| ------- | --------------------------------------- |
| `Theme` | New Theme instance with shuffled colors |

Example

```python
theme = Theme([color1, color2, color3])
shuffled_theme = theme.shuffled()
```

Source code in `src/lifx/theme/theme.py`

````python
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
````

##### get_next_bounds_checked

```python
get_next_bounds_checked(index: int) -> HSBK
```

Get the next color after index or the last color if at end.

| PARAMETER | DESCRIPTION                            |
| --------- | -------------------------------------- |
| `index`   | Index of current color **TYPE:** `int` |

| RETURNS | DESCRIPTION                                              |
| ------- | -------------------------------------------------------- |
| `HSBK`  | Next HSBK color or the last color if index is at the end |

Example

```python
theme = Theme([red, green, blue])
color = theme.get_next_bounds_checked(0)  # green
color = theme.get_next_bounds_checked(2)  # blue (last color)
```

Source code in `src/lifx/theme/theme.py`

````python
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
````

##### ensure_color

```python
ensure_color() -> None
```

Ensure the theme has at least one color.

If the theme is empty, adds a default white color.

Source code in `src/lifx/theme/theme.py`

```python
def ensure_color(self) -> None:
    """Ensure the theme has at least one color.

    If the theme is empty, adds a default white color.
    """
    if not self.colors:
        self.colors.append(
            HSBK(hue=0, saturation=0, brightness=1.0, kelvin=3500)
        )  # pragma: no cover
```

##### __len__

```python
__len__() -> int
```

Get the number of colors in the theme.

Source code in `src/lifx/theme/theme.py`

```python
def __len__(self) -> int:
    """Get the number of colors in the theme."""
    return len(self.colors)
```

##### __iter__

```python
__iter__() -> Iterator[HSBK]
```

Iterate over colors in the theme.

Source code in `src/lifx/theme/theme.py`

```python
def __iter__(self) -> Iterator[HSBK]:
    """Iterate over colors in the theme."""
    return iter(self.colors)
```

##### __getitem__

```python
__getitem__(index: int) -> HSBK
```

Get a color by index.

| PARAMETER | DESCRIPTION                                  |
| --------- | -------------------------------------------- |
| `index`   | Index of the color (0-based) **TYPE:** `int` |

| RETURNS | DESCRIPTION                   |
| ------- | ----------------------------- |
| `HSBK`  | HSBK color at the given index |

| RAISES       | DESCRIPTION              |
| ------------ | ------------------------ |
| `IndexError` | If index is out of range |

Example

```python
theme = Theme([red, green, blue])
color = theme[1]  # green
```

Source code in `src/lifx/theme/theme.py`

````python
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
````

##### __contains__

```python
__contains__(color: HSBK) -> bool
```

Check if a color is in the theme.

| PARAMETER | DESCRIPTION                          |
| --------- | ------------------------------------ |
| `color`   | HSBK color to check **TYPE:** `HSBK` |

| RETURNS | DESCRIPTION                                     |
| ------- | ----------------------------------------------- |
| `bool`  | True if color is in theme (by value comparison) |

Example

```python
theme = Theme([red, green, blue])
if red in theme:
    print("Red is in the theme")
```

Source code in `src/lifx/theme/theme.py`

````python
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
    return any(
        c.hue == color.hue
        and c.saturation == color.saturation
        and c.brightness == color.brightness
        and c.kelvin == color.kelvin
        for c in self.colors
    )
````

##### __repr__

```python
__repr__() -> str
```

Return a string representation of the theme.

Source code in `src/lifx/theme/theme.py`

```python
def __repr__(self) -> str:
    """Return a string representation of the theme."""
    color_count = len(self.colors)
    return f"Theme({color_count} colors)"
```

## ThemeLibrary Class

The `ThemeLibrary` provides access to 42 official LIFX app themes organized into 6 categories.

### ThemeLibrary

Collection of built-in color themes for LIFX devices.

Provides access to 60+ professionally designed themes organized by mood, season, occasion, and time of day.

Example

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

| METHOD            | DESCRIPTION                     |
| ----------------- | ------------------------------- |
| `get`             | Get a theme by name.            |
| `list`            | List all available theme names. |
| `get_by_category` | Get all themes in a category.   |

#### Functions

##### get

```python
get(name: str) -> Theme
```

Get a theme by name.

| PARAMETER | DESCRIPTION                                   |
| --------- | --------------------------------------------- |
| `name`    | Theme name (case-insensitive) **TYPE:** `str` |

| RETURNS | DESCRIPTION  |
| ------- | ------------ |
| `Theme` | Theme object |

| RAISES     | DESCRIPTION                |
| ---------- | -------------------------- |
| `KeyError` | If theme name is not found |

Example

```python
from lifx.theme import ThemeLibrary

evening_theme = ThemeLibrary.get("evening")
await light.apply_theme(evening_theme, power_on=True)
```

Source code in `src/lifx/theme/library.py`

````python
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
````

##### list

```python
list() -> list[str]
```

List all available theme names.

| RETURNS     | DESCRIPTION                |
| ----------- | -------------------------- |
| `list[str]` | Sorted list of theme names |

Example

```python
from lifx.theme import ThemeLibrary

all_themes = ThemeLibrary.list()
for theme_name in all_themes:
    print(f"- {theme_name}")
```

Source code in `src/lifx/theme/library.py`

````python
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
````

##### get_by_category

```python
get_by_category(category: str) -> dict[str, Theme]
```

Get all themes in a category.

| PARAMETER  | DESCRIPTION                                                         |
| ---------- | ------------------------------------------------------------------- |
| `category` | Category name (seasonal, mood, holiday, time, etc.) **TYPE:** `str` |

| RETURNS            | DESCRIPTION                                 |
| ------------------ | ------------------------------------------- |
| `dict[str, Theme]` | Dictionary of Theme objects in the category |

| RAISES       | DESCRIPTION                   |
| ------------ | ----------------------------- |
| `ValueError` | If category is not recognized |

Source code in `src/lifx/theme/library.py`

```python
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
```

## Canvas Class

The `Canvas` class provides 2D sparse grid functionality for tile device color interpolation.

### Canvas

```python
Canvas()
```

A Canvas is a collection of points with methods for interacting with those points

The points are stored as (i, j) in a dictionary. The value for each point is an HSBK color.

| METHOD                | DESCRIPTION                                                                   |
| --------------------- | ----------------------------------------------------------------------------- |
| `add_points_for_tile` | Create points on the canvas around where a tile is.                           |
| `surrounding_colors`  | Return the colors that surround this (i, j) point.                            |
| `has_neighbour`       | Return whether there are any points around this (i, j) position.              |
| `shuffle_points`      | Take all the points and move them around a random amount.                     |
| `blur`                | For each point, find the average colour of that point plus all surrounding    |
| `blur_by_distance`    | Similar to blur but will find the 8 closest points as opposed to the 8        |
| `points_for_tile`     | Return a list of HSBK values for this tile.                                   |
| `fill_in_points`      | Fill in the gaps on this canvas by blurring the points on the provided canvas |
| `closest_points`      | Return [(distance, color), ...] for the closest consider amount of            |
| `__iter__`            | Yield ((i, j), color) pairs for all our points.                               |
| `__getitem__`         | Return the color at point where point is (i, j).                              |
| `__setitem__`         | Set the color at point where point is (i, j).                                 |
| `__contains__`        | Return whether this point has a color where point is (i, j).                  |
| `__repr__`            | Return string representation.                                                 |

Source code in `src/lifx/theme/canvas.py`

```python
def __init__(self) -> None:
    """Initialize the canvas."""
    self.points: dict[tuple[int, int], HSBK] = {}
```

#### Functions

##### add_points_for_tile

```python
add_points_for_tile(tile: tuple[int, int] | None, theme: Theme) -> None
```

Create points on the canvas around where a tile is.

We create an area that's half the tile width/height beyond the boundary of the tile. We also spread the points out in a random manner and try to avoid having points next to each other.

Multiple calls to this function will not override existing points on the canvas.

| PARAMETER | DESCRIPTION                                                                 |
| --------- | --------------------------------------------------------------------------- |
| `tile`    | Tile coordinates (x, y) or None for single tile **TYPE:** \`tuple[int, int] |
| `theme`   | Theme containing colors to distribute **TYPE:** `Theme`                     |

Source code in `src/lifx/theme/canvas.py`

```python
def add_points_for_tile(self, tile: tuple[int, int] | None, theme: Theme) -> None:
    """Create points on the canvas around where a tile is.

    We create an area that's half the tile width/height beyond the boundary
    of the tile. We also spread the points out in a random manner and try to avoid
    having points next to each other.

    Multiple calls to this function will not override existing points on the canvas.

    Args:
        tile: Tile coordinates (x, y) or None for single tile
        theme: Theme containing colors to distribute
    """
    tile_x, tile_y = tile if tile else (0, 0)
    tile_width = 8  # Standard tile width
    tile_height = 8  # Standard tile height

    from_x = int(tile_x - tile_width * 1.5)
    to_x = int(tile_x + tile_width * 1.5)
    from_y = int(tile_y - tile_height * 1.5)
    to_y = int(tile_y + tile_height * 1.5)

    i = from_x
    while i < to_x:
        j = from_y
        while j < to_y:
            if (i, j) not in self.points:
                if not self.has_neighbour(i, j):
                    random_color = theme.random()
                    self[(i, j)] = random_color
            j += random.choice([1, 2, 3])  # nosec
        i += random.choice([1, 2, 3])  # nosec
```

##### surrounding_colors

```python
surrounding_colors(i: int, j: int) -> list[HSBK]
```

Return the colors that surround this (i, j) point.

This will only return points that exist.

Source code in `src/lifx/theme/canvas.py`

```python
def surrounding_colors(self, i: int, j: int) -> list[HSBK]:
    """Return the colors that surround this (i, j) point.

    This will only return points that exist.
    """
    return [self[(x, y)] for x, y in surrounding_points(i, j) if (x, y) in self]
```

##### has_neighbour

```python
has_neighbour(i: int, j: int) -> bool
```

Return whether there are any points around this (i, j) position.

Source code in `src/lifx/theme/canvas.py`

```python
def has_neighbour(self, i: int, j: int) -> bool:
    """Return whether there are any points around this (i, j) position."""
    return any(self.surrounding_colors(i, j))
```

##### shuffle_points

```python
shuffle_points() -> None
```

Take all the points and move them around a random amount.

Source code in `src/lifx/theme/canvas.py`

```python
def shuffle_points(self) -> None:
    """Take all the points and move them around a random amount."""
    new_points = {}
    for (i, j), color in self:
        new_points[shuffle_point(i, j)] = color

    self.points = new_points
```

##### blur

```python
blur() -> None
```

For each point, find the average colour of that point plus all surrounding points.

Source code in `src/lifx/theme/canvas.py`

```python
def blur(self) -> None:
    """
    For each point, find the average colour of that point plus all surrounding
    points.
    """
    new_points = {}
    for (i, j), original in self:
        colors = [original for _ in range(2)]
        for color in self.surrounding_colors(i, j):
            colors.append(color)
        new_points[(i, j)] = HSBK.average(colors)
    self.points = new_points
```

##### blur_by_distance

```python
blur_by_distance() -> None
```

Similar to blur but will find the 8 closest points as opposed to the 8 surrounding points.

Source code in `src/lifx/theme/canvas.py`

```python
def blur_by_distance(self) -> None:
    """Similar to blur but will find the 8 closest points as opposed to the 8
    surrounding points."""
    new_points = {}
    for (i, j), _ in self:
        distances = self.closest_points(i, j, 8)
        weighted = list(color_weighting(distances))
        if weighted:
            new_points[(i, j)] = HSBK.average(weighted)
    self.points = new_points
```

##### points_for_tile

```python
points_for_tile(
    tile: tuple[int, int] | None, width: int = 8, height: int = 8
) -> list[HSBK]
```

Return a list of HSBK values for this tile.

For any point on the tile that doesn't have a corresponding point on the canvas return a grey value. This is useful for when we tell the applier to not fill in the gaps.

| PARAMETER | DESCRIPTION                                                                 |
| --------- | --------------------------------------------------------------------------- |
| `tile`    | Tile coordinates (x, y) or None for single tile **TYPE:** \`tuple[int, int] |
| `width`   | Grid width (typically 8) **TYPE:** `int` **DEFAULT:** `8`                   |
| `height`  | Grid height (typically 8) **TYPE:** `int` **DEFAULT:** `8`                  |

| RETURNS      | DESCRIPTION                            |
| ------------ | -------------------------------------- |
| `list[HSBK]` | List of HSBK colors in row-major order |

Source code in `src/lifx/theme/canvas.py`

```python
def points_for_tile(
    self, tile: tuple[int, int] | None, width: int = 8, height: int = 8
) -> list[HSBK]:
    """Return a list of HSBK values for this tile.

    For any point on the tile that doesn't have a corresponding point on the
    canvas return a grey value. This is useful for when we tell the applier
    to not fill in the gaps.

    Args:
        tile: Tile coordinates (x, y) or None for single tile
        width: Grid width (typically 8)
        height: Grid height (typically 8)

    Returns:
        List of HSBK colors in row-major order
    """
    tile_x, tile_y = tile if tile else (0, 0)
    result = []
    grey = HSBK(hue=0, saturation=0, brightness=0.3, kelvin=3500)

    for j in range(tile_y, tile_y + height):
        for i in range(tile_x, tile_x + width):
            if (i, j) in self.points:
                result.append(self.points[(i, j)])
            else:
                result.append(grey)

    return result
```

##### fill_in_points

```python
fill_in_points(
    canvas: Canvas, left_x: int, top_y: int, tile_width: int, tile_height: int
) -> None
```

Fill in the gaps on this canvas by blurring the points on the provided canvas

We blur by finding the 4 closest points for each point on our tile and averaging them.

| PARAMETER     | DESCRIPTION                                          |
| ------------- | ---------------------------------------------------- |
| `canvas`      | Source canvas to interpolate from **TYPE:** `Canvas` |
| `left_x`      | Left x coordinate of tile **TYPE:** `int`            |
| `top_y`       | Top y coordinate of tile **TYPE:** `int`             |
| `tile_width`  | Width of tile **TYPE:** `int`                        |
| `tile_height` | Height of tile **TYPE:** `int`                       |

Source code in `src/lifx/theme/canvas.py`

```python
def fill_in_points(
    self, canvas: Canvas, left_x: int, top_y: int, tile_width: int, tile_height: int
) -> None:
    """Fill in the gaps on this canvas by blurring the points on the provided canvas

    We blur by finding the 4 closest points for each point on our tile and
    averaging them.

    Args:
        canvas: Source canvas to interpolate from
        left_x: Left x coordinate of tile
        top_y: Top y coordinate of tile
        tile_width: Width of tile
        tile_height: Height of tile
    """
    for j in range(top_y, top_y + tile_height):
        for i in range(left_x, left_x + tile_width):
            distances = canvas.closest_points(i, j, 4)
            weighted = list(color_weighting(distances))
            if weighted:
                self[(i, j)] = HSBK.average(weighted)
```

##### closest_points

```python
closest_points(i: int, j: int, consider: int) -> list[tuple[int, HSBK]]
```

Return [(distance, color), ...] for the closest consider amount of points to (i, j).

Source code in `src/lifx/theme/canvas.py`

```python
def closest_points(self, i: int, j: int, consider: int) -> list[tuple[int, HSBK]]:
    """Return [(distance, color), ...] for the closest consider amount of
    points to (i, j)."""
    distances: list[tuple[int, HSBK]] = []

    for (x, y), color in self:
        distances.append(((x - i) ** 2 + (y - j) ** 2, color))

    def get_key(
        dc: tuple[int, HSBK],
    ) -> tuple[int, tuple[float, float, float, int]]:
        return (
            dc[0],
            (dc[1].hue, dc[1].saturation, dc[1].brightness, dc[1].kelvin),
        )

    distances = sorted(distances, key=get_key)
    return distances[:consider]
```

##### __iter__

```python
__iter__() -> Iterator[tuple[tuple[int, int], HSBK]]
```

Yield ((i, j), color) pairs for all our points.

Source code in `src/lifx/theme/canvas.py`

```python
def __iter__(self) -> Iterator[tuple[tuple[int, int], HSBK]]:
    """Yield ((i, j), color) pairs for all our points."""
    yield from self.points.items()
```

##### __getitem__

```python
__getitem__(point: tuple[int, int]) -> HSBK
```

Return the color at point where point is (i, j).

Source code in `src/lifx/theme/canvas.py`

```python
def __getitem__(self, point: tuple[int, int]) -> HSBK:
    """Return the color at point where point is (i, j)."""
    return self.points[point]
```

##### __setitem__

```python
__setitem__(key: tuple[int, int], color: HSBK) -> None
```

Set the color at point where point is (i, j).

Source code in `src/lifx/theme/canvas.py`

```python
def __setitem__(self, key: tuple[int, int], color: HSBK) -> None:
    """Set the color at point where point is (i, j)."""
    self.points[key] = color
```

##### __contains__

```python
__contains__(point: tuple[int, int]) -> bool
```

Return whether this point has a color where point is (i, j).

Source code in `src/lifx/theme/canvas.py`

```python
def __contains__(self, point: tuple[int, int]) -> bool:
    """Return whether this point has a color where point is (i, j)."""
    return point in self.points
```

##### __repr__

```python
__repr__() -> str
```

Return string representation.

Source code in `src/lifx/theme/canvas.py`

```python
def __repr__(self) -> str:
    """Return string representation."""
    return f"Canvas({len(self.points)} points)"
```

## Convenience Function

### get_theme

```python
get_theme(name: str) -> Theme
```

Get a theme by name.

Convenience function equivalent to ThemeLibrary.get(name).

| PARAMETER | DESCRIPTION                                   |
| --------- | --------------------------------------------- |
| `name`    | Theme name (case-insensitive) **TYPE:** `str` |

| RETURNS | DESCRIPTION  |
| ------- | ------------ |
| `Theme` | Theme object |

Example

```python
from lifx.theme import get_theme

evening = get_theme("evening")
await light.apply_theme(evening, power_on=True)
```

Source code in `src/lifx/theme/library.py`

````python
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
````

## Available Themes (42 Total)

### Seasonal (3 themes)

- spring, autumn, winter

### Holiday (9 themes)

- christmas, halloween, hanukkah, kwanzaa, shamrock, thanksgiving, calaveras, pumpkin, santa

### Mood (16 themes)

- peaceful, serene, relaxing, mellow, gentle, soothing, blissful, cheerful, romantic, romance, love, energizing, exciting, epic, intense, powerful, warming

### Ambient (6 themes)

- dream, fantasy, spacey, stardust, zombie, party

### Functional (3 themes)

- focusing, evening, bias_lighting

### Atmosphere (3 themes)

- hygge, tranquil, sports
