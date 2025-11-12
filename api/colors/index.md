# Color Utilities

lifx-async provides comprehensive color utilities for working with LIFX's HSBK color model and converting to/from RGB.

## HSBK Class

The `HSBK` class represents colors in the Hue, Saturation, Brightness, Kelvin color model used by LIFX devices.

### HSBK

```python
HSBK(hue: float, saturation: float, brightness: float, kelvin: int)
```

User-friendly HSBK color representation.

LIFX devices use HSBK (Hue, Saturation, Brightness, Kelvin) color space. This class provides a convenient interface with normalized values and conversion to/from RGB.

| ATTRIBUTE    | DESCRIPTION                                                                           |
| ------------ | ------------------------------------------------------------------------------------- |
| `hue`        | Hue value in degrees (0-360) **TYPE:** `float`                                        |
| `saturation` | Saturation (0.0-1.0, where 0 is white and 1 is fully saturated) **TYPE:** `float`     |
| `brightness` | Brightness (0.0-1.0, where 0 is off and 1 is full brightness) **TYPE:** `float`       |
| `kelvin`     | Color temperature in Kelvin (1500-9000, typically 2500-9000 for LIFX) **TYPE:** `int` |

Example

```python
# Create a red color
red = HSBK(hue=0, saturation=1.0, brightness=1.0, kelvin=3500)

# Create from RGB
purple = HSBK.from_rgb(128, 0, 128)

# Convert to RGB
r, g, b = purple.to_rgb()
```

| METHOD              | DESCRIPTION                                                           |
| ------------------- | --------------------------------------------------------------------- |
| `__post_init__`     | Validate all fields after initialization.                             |
| `from_rgb`          | Create HSBK from RGB values.                                          |
| `to_rgb`            | Convert HSBK to RGB values.                                           |
| `to_protocol`       | Convert to protocol HSBK for packet serialization.                    |
| `from_protocol`     | Create HSBK from protocol HSBK.                                       |
| `with_hue`          | Create a new HSBK with modified hue.                                  |
| `with_saturation`   | Create a new HSBK with modified saturation.                           |
| `with_brightness`   | Create a new HSBK with modified brightness.                           |
| `with_kelvin`       | Create a new HSBK with modified color temperature.                    |
| `clone`             | Create a copy of this color.                                          |
| `as_tuple`          | Return HSBK values as a tuple of protocol uint16 values.              |
| `as_dict`           | Return HSBK values as a dictionary of user-friendly values.           |
| `limit_distance_to` | Return a new color with hue limited to 90 degrees from another color. |
| `average`           | Calculate the average color of a list of HSBK colors.                 |

#### Functions

##### __post_init__

```python
__post_init__() -> None
```

Validate all fields after initialization.

Source code in `src/lifx/color.py`

```python
def __post_init__(self) -> None:
    """Validate all fields after initialization."""
    self._validate_hue(self.hue)
    self._validate_saturation(self.saturation)
    self._validate_brightness(self.brightness)
    self._validate_kelvin(self.kelvin)
```

##### from_rgb

```python
from_rgb(r: int, g: int, b: int, kelvin: int = KELVIN_NEUTRAL) -> HSBK
```

Create HSBK from RGB values.

| PARAMETER | DESCRIPTION                                                                               |
| --------- | ----------------------------------------------------------------------------------------- |
| `r`       | Red component (0-255) **TYPE:** `int`                                                     |
| `g`       | Green component (0-255) **TYPE:** `int`                                                   |
| `b`       | Blue component (0-255) **TYPE:** `int`                                                    |
| `kelvin`  | Color temperature in Kelvin (default: 3500) **TYPE:** `int` **DEFAULT:** `KELVIN_NEUTRAL` |

| RETURNS | DESCRIPTION   |
| ------- | ------------- |
| `HSBK`  | HSBK instance |

| RAISES       | DESCRIPTION                            |
| ------------ | -------------------------------------- |
| `ValueError` | If RGB values are out of range (0-255) |

Example

```python
# Pure red
red = HSBK.from_rgb(255, 0, 0)

# Purple with warm white
purple = HSBK.from_rgb(128, 0, 128, kelvin=2500)
```

Source code in `src/lifx/color.py`

````python
@classmethod
def from_rgb(
    cls,
    r: int,
    g: int,
    b: int,
    kelvin: int = KELVIN_NEUTRAL,
) -> HSBK:
    """Create HSBK from RGB values.

    Args:
        r: Red component (0-255)
        g: Green component (0-255)
        b: Blue component (0-255)
        kelvin: Color temperature in Kelvin (default: 3500)

    Returns:
        HSBK instance

    Raises:
        ValueError: If RGB values are out of range (0-255)

    Example:
        ```python
        # Pure red
        red = HSBK.from_rgb(255, 0, 0)

        # Purple with warm white
        purple = HSBK.from_rgb(128, 0, 128, kelvin=2500)
        ```
    """
    cls._validate_rgb_component(r, "Red")
    cls._validate_rgb_component(g, "Green")
    cls._validate_rgb_component(b, "Blue")

    # Normalize to 0-1
    r_norm = r / 255.0
    g_norm = g / 255.0
    b_norm = b / 255.0

    # Convert to HSV using colorsys
    h, s, v = colorsys.rgb_to_hsv(r_norm, g_norm, b_norm)

    # Convert to LIFX ranges
    hue = h * 360.0  # 0-1 -> 0-360
    saturation = s  # Already 0-1
    brightness = v  # Already 0-1

    return cls(hue=hue, saturation=saturation, brightness=brightness, kelvin=kelvin)
````

##### to_rgb

```python
to_rgb() -> tuple[int, int, int]
```

Convert HSBK to RGB values.

Color temperature (kelvin) is not considered in this conversion, as it only affects the white point of the device.

| RETURNS                | DESCRIPTION                                   |
| ---------------------- | --------------------------------------------- |
| `tuple[int, int, int]` | Tuple of (red, green, blue) with values 0-255 |

Example

```python
color = HSBK(hue=120, saturation=1.0, brightness=1.0, kelvin=3500)
r, g, b = color.to_rgb()  # Returns (0, 255, 0) - green
```

Source code in `src/lifx/color.py`

````python
def to_rgb(self) -> tuple[int, int, int]:
    """Convert HSBK to RGB values.

    Color temperature (kelvin) is not considered in this conversion,
    as it only affects the white point of the device.

    Returns:
        Tuple of (red, green, blue) with values 0-255

    Example:
        ```python
        color = HSBK(hue=120, saturation=1.0, brightness=1.0, kelvin=3500)
        r, g, b = color.to_rgb()  # Returns (0, 255, 0) - green
        ```
    """
    # Convert to colorsys ranges
    h = self.hue / 360.0  # 0-360 -> 0-1
    s = self.saturation  # Already 0-1
    v = self.brightness  # Already 0-1

    # Convert using colorsys
    r_norm, g_norm, b_norm = colorsys.hsv_to_rgb(h, s, v)

    # Scale to 0-255 and round
    r = int(round(r_norm * 255))
    g = int(round(g_norm * 255))
    b = int(round(b_norm * 255))

    return (r, g, b)
````

##### to_protocol

```python
to_protocol() -> LightHsbk
```

Convert to protocol HSBK for packet serialization.

LIFX protocol uses uint16 values for all HSBK components:

- Hue: 0-65535 (represents 0-360 degrees)
- Saturation: 0-65535 (represents 0-100%)
- Brightness: 0-65535 (represents 0-100%)
- Kelvin: Direct value in Kelvin

| RETURNS     | DESCRIPTION                                 |
| ----------- | ------------------------------------------- |
| `LightHsbk` | LightHsbk instance for packet serialization |

Example

```python
color = HSBK(hue=180, saturation=0.5, brightness=0.75, kelvin=3500)
protocol_color = color.to_protocol()
# Use in packet: LightSetColor(color=protocol_color, ...)
```

Source code in `src/lifx/color.py`

````python
def to_protocol(self) -> LightHsbk:
    """Convert to protocol HSBK for packet serialization.

    LIFX protocol uses uint16 values for all HSBK components:
    - Hue: 0-65535 (represents 0-360 degrees)
    - Saturation: 0-65535 (represents 0-100%)
    - Brightness: 0-65535 (represents 0-100%)
    - Kelvin: Direct value in Kelvin

    Returns:
        LightHsbk instance for packet serialization

    Example:
        ```python
        color = HSBK(hue=180, saturation=0.5, brightness=0.75, kelvin=3500)
        protocol_color = color.to_protocol()
        # Use in packet: LightSetColor(color=protocol_color, ...)
        ```
    """
    # Convert to uint16 ranges with overflow protection
    # Clamp values to prevent overflow
    hue_u16 = max(0, min(65535, int(round((self.hue / 360.0) * 65535))))
    saturation_u16 = max(0, min(65535, int(round(self.saturation * 65535))))
    brightness_u16 = max(0, min(65535, int(round(self.brightness * 65535))))

    return LightHsbk(
        hue=hue_u16,
        saturation=saturation_u16,
        brightness=brightness_u16,
        kelvin=self.kelvin,
    )
````

##### from_protocol

```python
from_protocol(protocol: LightHsbk) -> HSBK
```

Create HSBK from protocol HSBK.

| PARAMETER  | DESCRIPTION                                                          |
| ---------- | -------------------------------------------------------------------- |
| `protocol` | LightHsbk instance from packet deserialization **TYPE:** `LightHsbk` |

| RETURNS | DESCRIPTION                 |
| ------- | --------------------------- |
| `HSBK`  | User-friendly HSBK instance |

Example

```python
# After receiving LightState packet
state = await device.get_state()
color = HSBK.from_protocol(state.color)
print(f"Hue: {color.hue}°, Brightness: {color.brightness * 100}%")
```

Source code in `src/lifx/color.py`

````python
@classmethod
def from_protocol(cls, protocol: LightHsbk) -> HSBK:
    """Create HSBK from protocol HSBK.

    Args:
        protocol: LightHsbk instance from packet deserialization

    Returns:
        User-friendly HSBK instance

    Example:
        ```python
        # After receiving LightState packet
        state = await device.get_state()
        color = HSBK.from_protocol(state.color)
        print(f"Hue: {color.hue}°, Brightness: {color.brightness * 100}%")
        ```
    """
    # Convert from uint16 ranges to user-friendly ranges
    hue = (protocol.hue / 65535.0) * 360.0
    saturation = protocol.saturation / 65535.0
    brightness = protocol.brightness / 65535.0

    return cls(
        hue=hue,
        saturation=saturation,
        brightness=brightness,
        kelvin=protocol.kelvin,
    )
````

##### with_hue

```python
with_hue(hue: float) -> HSBK
```

Create a new HSBK with modified hue.

| PARAMETER | DESCRIPTION                             |
| --------- | --------------------------------------- |
| `hue`     | New hue value (0-360) **TYPE:** `float` |

| RETURNS | DESCRIPTION       |
| ------- | ----------------- |
| `HSBK`  | New HSBK instance |

Source code in `src/lifx/color.py`

```python
def with_hue(self, hue: float) -> HSBK:
    """Create a new HSBK with modified hue.

    Args:
        hue: New hue value (0-360)

    Returns:
        New HSBK instance
    """
    return HSBK(
        hue=hue,
        saturation=self.saturation,
        brightness=self.brightness,
        kelvin=self.kelvin,
    )
```

##### with_saturation

```python
with_saturation(saturation: float) -> HSBK
```

Create a new HSBK with modified saturation.

| PARAMETER    | DESCRIPTION                                      |
| ------------ | ------------------------------------------------ |
| `saturation` | New saturation value (0.0-1.0) **TYPE:** `float` |

| RETURNS | DESCRIPTION       |
| ------- | ----------------- |
| `HSBK`  | New HSBK instance |

Source code in `src/lifx/color.py`

```python
def with_saturation(self, saturation: float) -> HSBK:
    """Create a new HSBK with modified saturation.

    Args:
        saturation: New saturation value (0.0-1.0)

    Returns:
        New HSBK instance
    """
    return HSBK(
        hue=self.hue,
        saturation=saturation,
        brightness=self.brightness,
        kelvin=self.kelvin,
    )
```

##### with_brightness

```python
with_brightness(brightness: float) -> HSBK
```

Create a new HSBK with modified brightness.

| PARAMETER    | DESCRIPTION                                      |
| ------------ | ------------------------------------------------ |
| `brightness` | New brightness value (0.0-1.0) **TYPE:** `float` |

| RETURNS | DESCRIPTION       |
| ------- | ----------------- |
| `HSBK`  | New HSBK instance |

Source code in `src/lifx/color.py`

```python
def with_brightness(self, brightness: float) -> HSBK:
    """Create a new HSBK with modified brightness.

    Args:
        brightness: New brightness value (0.0-1.0)

    Returns:
        New HSBK instance
    """
    return HSBK(
        hue=self.hue,
        saturation=self.saturation,
        brightness=brightness,
        kelvin=self.kelvin,
    )
```

##### with_kelvin

```python
with_kelvin(kelvin: int) -> HSBK
```

Create a new HSBK with modified color temperature.

| PARAMETER | DESCRIPTION                                  |
| --------- | -------------------------------------------- |
| `kelvin`  | New kelvin value (1500-9000) **TYPE:** `int` |

| RETURNS | DESCRIPTION       |
| ------- | ----------------- |
| `HSBK`  | New HSBK instance |

Source code in `src/lifx/color.py`

```python
def with_kelvin(self, kelvin: int) -> HSBK:
    """Create a new HSBK with modified color temperature.

    Args:
        kelvin: New kelvin value (1500-9000)

    Returns:
        New HSBK instance
    """
    return HSBK(
        hue=self.hue,
        saturation=self.saturation,
        brightness=self.brightness,
        kelvin=kelvin,
    )
```

##### clone

```python
clone() -> HSBK
```

Create a copy of this color.

| RETURNS | DESCRIPTION                            |
| ------- | -------------------------------------- |
| `HSBK`  | New HSBK instance with the same values |

Source code in `src/lifx/color.py`

```python
def clone(self) -> HSBK:
    """Create a copy of this color.

    Returns:
        New HSBK instance with the same values
    """
    return HSBK(
        hue=self.hue,
        saturation=self.saturation,
        brightness=self.brightness,
        kelvin=self.kelvin,
    )
```

##### as_tuple

```python
as_tuple() -> tuple[int, int, int, int]
```

Return HSBK values as a tuple of protocol uint16 values.

| RETURNS | DESCRIPTION                                                |
| ------- | ---------------------------------------------------------- |
| `int`   | Tuple of (hue_u16, saturation_u16, brightness_u16, kelvin) |
| `int`   | where u16 values are in range 0-65535                      |

Example

```python
color = HSBK(hue=180, saturation=0.5, brightness=0.75, kelvin=3500)
hue, sat, bri, kel = color.as_tuple()
# Use in protocol operations
```

Source code in `src/lifx/color.py`

````python
def as_tuple(self) -> tuple[int, int, int, int]:
    """Return HSBK values as a tuple of protocol uint16 values.

    Returns:
        Tuple of (hue_u16, saturation_u16, brightness_u16, kelvin)
        where u16 values are in range 0-65535

    Example:
        ```python
        color = HSBK(hue=180, saturation=0.5, brightness=0.75, kelvin=3500)
        hue, sat, bri, kel = color.as_tuple()
        # Use in protocol operations
        ```
    """
    protocol = self.to_protocol()
    return (protocol.hue, protocol.saturation, protocol.brightness, protocol.kelvin)
````

##### as_dict

```python
as_dict() -> dict[str, float | int]
```

Return HSBK values as a dictionary of user-friendly values.

| RETURNS            | DESCRIPTION |
| ------------------ | ----------- |
| \`dict\[str, float | int\]\`     |
| \`dict\[str, float | int\]\`     |

Example

```python
color = HSBK(hue=180, saturation=0.5, brightness=0.75, kelvin=3500)
color_dict = color.as_dict()
# {'hue': 180.0, 'saturation': 0.5, 'brightness': 0.75, 'kelvin': 3500}
```

Source code in `src/lifx/color.py`

````python
def as_dict(self) -> dict[str, float | int]:
    """Return HSBK values as a dictionary of user-friendly values.

    Returns:
        Dictionary with keys: hue (float), saturation (float),
        brightness (float), kelvin (int)

    Example:
        ```python
        color = HSBK(hue=180, saturation=0.5, brightness=0.75, kelvin=3500)
        color_dict = color.as_dict()
        # {'hue': 180.0, 'saturation': 0.5, 'brightness': 0.75, 'kelvin': 3500}
        ```
    """
    return {
        "hue": self.hue,
        "saturation": self.saturation,
        "brightness": self.brightness,
        "kelvin": self.kelvin,
    }
````

##### limit_distance_to

```python
limit_distance_to(other: HSBK) -> HSBK
```

Return a new color with hue limited to 90 degrees from another color.

This is useful for preventing large hue jumps when interpolating between colors. If the hue difference is greater than 90 degrees, the hue is adjusted to be within 90 degrees of the target hue.

| PARAMETER | DESCRIPTION                                           |
| --------- | ----------------------------------------------------- |
| `other`   | Reference color to limit distance to **TYPE:** `HSBK` |

| RETURNS | DESCRIPTION                                 |
| ------- | ------------------------------------------- |
| `HSBK`  | New HSBK instance with limited hue distance |

Example

```python
red = HSBK(hue=10, saturation=1.0, brightness=1.0, kelvin=3500)
blue = HSBK(hue=240, saturation=1.0, brightness=1.0, kelvin=3500)

# Limit red's hue to be within 90 degrees of blue's hue
adjusted = red.limit_distance_to(blue)
# Result: hue is adjusted to be within 90 degrees of 240
```

Source code in `src/lifx/color.py`

````python
def limit_distance_to(self, other: HSBK) -> HSBK:
    """Return a new color with hue limited to 90 degrees from another color.

    This is useful for preventing large hue jumps when interpolating between colors.
    If the hue difference is greater than 90 degrees, the hue is adjusted to be
    within 90 degrees of the target hue.

    Args:
        other: Reference color to limit distance to

    Returns:
        New HSBK instance with limited hue distance

    Example:
        ```python
        red = HSBK(hue=10, saturation=1.0, brightness=1.0, kelvin=3500)
        blue = HSBK(hue=240, saturation=1.0, brightness=1.0, kelvin=3500)

        # Limit red's hue to be within 90 degrees of blue's hue
        adjusted = red.limit_distance_to(blue)
        # Result: hue is adjusted to be within 90 degrees of 240
        ```
    """
    raw_dist = (
        self.hue - other.hue if self.hue > other.hue else other.hue - self.hue
    )
    dist = 360 - raw_dist if raw_dist > 180 else raw_dist
    if abs(dist) > 90:
        h = self.hue + 90 if (other.hue + dist) % 360 == self.hue else self.hue - 90
        h = h + 360 if h < 0 else h
        return HSBK(h, self.saturation, self.brightness, self.kelvin)
    else:
        return self
````

##### average

```python
average(colors: list[HSBK]) -> HSBK
```

Calculate the average color of a list of HSBK colors.

Uses circular mean for hue to correctly handle hue wraparound (e.g., average of 10° and 350° is 0°, not 180°).

| PARAMETER | DESCRIPTION                                                               |
| --------- | ------------------------------------------------------------------------- |
| `colors`  | List of HSBK colors to average (must not be empty) **TYPE:** `list[HSBK]` |

| RETURNS | DESCRIPTION                            |
| ------- | -------------------------------------- |
| `HSBK`  | New HSBK instance with averaged values |

| RAISES       | DESCRIPTION             |
| ------------ | ----------------------- |
| `ValueError` | If colors list is empty |

Example

```python
red = HSBK(hue=0, saturation=1.0, brightness=1.0, kelvin=3500)
green = HSBK(hue=120, saturation=1.0, brightness=1.0, kelvin=3500)
blue = HSBK(hue=240, saturation=1.0, brightness=1.0, kelvin=3500)

avg_color = HSBK.average([red, green, blue])
# Result: average of the three primary colors
```

Source code in `src/lifx/color.py`

````python
@classmethod
def average(cls, colors: list[HSBK]) -> HSBK:
    """Calculate the average color of a list of HSBK colors.

    Uses circular mean for hue to correctly handle hue wraparound
    (e.g., average of 10° and 350° is 0°, not 180°).

    Args:
        colors: List of HSBK colors to average (must not be empty)

    Returns:
        New HSBK instance with averaged values

    Raises:
        ValueError: If colors list is empty

    Example:
        ```python
        red = HSBK(hue=0, saturation=1.0, brightness=1.0, kelvin=3500)
        green = HSBK(hue=120, saturation=1.0, brightness=1.0, kelvin=3500)
        blue = HSBK(hue=240, saturation=1.0, brightness=1.0, kelvin=3500)

        avg_color = HSBK.average([red, green, blue])
        # Result: average of the three primary colors
        ```
    """
    if not colors:
        raise ValueError("Cannot average an empty list of colors")

    hue_x_total = 0.0
    hue_y_total = 0.0
    saturation_total = 0.0
    brightness_total = 0.0
    kelvin_total = 0.0

    for color in colors:
        hue_x_total += math.sin(color.hue * 2.0 * math.pi / 360)
        hue_y_total += math.cos(color.hue * 2.0 * math.pi / 360)
        saturation_total += color.saturation
        brightness_total += color.brightness
        kelvin_total += color.kelvin

    hue = math.atan2(hue_x_total, hue_y_total) / (2.0 * math.pi)
    if hue < 0.0:
        hue += 1.0
    hue *= 360
    hue = round(hue, 4)
    saturation = round(saturation_total / len(colors), 4)
    brightness = round(brightness_total / len(colors), 4)
    kelvin = round(kelvin_total / len(colors))

    return cls(hue, saturation, brightness, kelvin)
````

## Colors Class

The `Colors` class provides convenient color presets for common colors.

### Colors

Common color presets for convenience.

## Examples

### Creating Colors

```python
from lifx import HSBK, Colors

# Use built-in color presets
color = Colors.BLUE

# Create custom colors
custom = HSBK(hue=180.0, saturation=1.0, brightness=0.8, kelvin=3500)

# Create from RGB
red = HSBK.from_rgb(255, 0, 0, kelvin=3500)

# Convert to RGB
r, g, b = Colors.BLUE.to_rgb()
print(f"RGB: ({r}, {g}, {b})")
```

### Color Components

```python
from lifx import HSBK

color = HSBK(hue=240.0, saturation=1.0, brightness=0.5, kelvin=3500)

# Hue: 0-360 degrees (0=red, 120=green, 240=blue)
print(f"Hue: {color.hue}°")

# Saturation: 0.0-1.0 (0=white, 1=full color)
print(f"Saturation: {color.saturation * 100}%")

# Brightness: 0.0-1.0 (0=off, 1=full brightness)
print(f"Brightness: {color.brightness * 100}%")

# Kelvin: 1500-9000 (warm white to cool white)
print(f"Temperature: {color.kelvin}K")
```

### Color Manipulation

```python
from lifx import HSBK, Light


async def cycle_hue(light: Light):
    """Cycle through the color spectrum"""
    for hue in range(0, 360, 10):
        color = HSBK(hue=float(hue), saturation=1.0, brightness=0.8, kelvin=3500)
        await light.set_color(color, duration=0.1)
```

### White Balance

```python
from lifx import HSBK

# Warm white (sunset, candlelight)
warm = HSBK(hue=0, saturation=0, brightness=1.0, kelvin=2500)

# Neutral white (daylight)
neutral = HSBK(hue=0, saturation=0, brightness=1.0, kelvin=4000)

# Cool white (overcast, shade)
cool = HSBK(hue=0, saturation=0, brightness=1.0, kelvin=6500)
```

## Available Color Presets

The `Colors` class provides these preset colors:

- `Colors.WHITE` - Pure white (3500K)
- `Colors.RED` - Red
- `Colors.ORANGE` - Orange
- `Colors.YELLOW` - Yellow
- `Colors.GREEN` - Green
- `Colors.CYAN` - Cyan
- `Colors.BLUE` - Blue
- `Colors.PURPLE` - Purple
- `Colors.PINK` - Pink
- `Colors.WARM_WHITE` - Warm white (2500K)
- `Colors.COOL_WHITE` - Cool white (6500K)

## Color Conversion Notes

### RGB to HSBK

When converting from RGB to HSBK, note that:

- RGB values are 0-255
- The Kelvin value must be specified (default: 3500K)
- Some RGB colors may not have exact HSBK equivalents
- Conversion uses standard HSV formulas with brightness mapping

### HSBK to RGB

When converting from HSBK to RGB:

- Returns tuple of (r, g, b) with values 0-255
- Kelvin temperature is not represented in RGB
- White colors (saturation=0) will be pure gray values
- Conversion is lossy - converting back may not yield the same HSBK
