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
purple = HSBK.from_rgb(0.5, 0.0, 0.5)

# Convert to RGB
r, g, b = purple.to_rgb()
```

| METHOD              | DESCRIPTION                                                           |
| ------------------- | --------------------------------------------------------------------- |
| `__eq__`            | Two colors are equal if they have the same HSBK values.               |
| `__hash__`          | Returns a hash of this color as an integer.                           |
| `__str__`           | Return a string representation of the HSBK values for this color.     |
| `__repr__`          | Return a string representation of the HSBK values for this color.     |
| `from_rgb`          | Create HSBK from RGB values.                                          |
| `to_rgb`            | Convert HSBK to RGB values.                                           |
| `to_protocol`       | Convert to protocol HSBK for packet serialization.                    |
| `from_protocol`     | Create HSBK from protocol HSBK.                                       |
| `with_hue`          | Create a new HSBK with modified hue.                                  |
| `with_saturation`   | Create a new HSBK with modified saturation.                           |
| `with_brightness`   | Create a new HSBK with modified brightness.                           |
| `with_kelvin`       | Create a new HSBK with modified color temperature.                    |
| `lerp_hsb`          | Interpolate to another color via shortest-path HSB blending.          |
| `lerp_oklab`        | Interpolate to another color through Oklab perceptual color space.    |
| `clone`             | Create a copy of this color.                                          |
| `as_tuple`          | Return HSBK values as a tuple of protocol uint16 values.              |
| `as_dict`           | Return HSBK values as a dictionary of user-friendly values.           |
| `limit_distance_to` | Return a new color with hue limited to 90 degrees from another color. |
| `average`           | Calculate the average color of a list of HSBK colors.                 |

Source code in `src/lifx/color.py`

```python
def __init__(
    self, hue: float, saturation: float, brightness: float, kelvin: int
) -> None:
    """Instantiate a color using hue, saturation, brightness and kelvin."""

    validate_hue(hue)
    validate_saturation(saturation)
    validate_brightness(brightness)
    validate_kelvin(kelvin)

    self._hue = hue
    self._saturation = saturation
    self._brightness = brightness
    self._kelvin = kelvin
```

#### Attributes

##### hue

```python
hue: float
```

Return hue (rounded to nearest integer degree for display).

##### saturation

```python
saturation: float
```

Return saturation (rounded to 2 decimal places for display).

##### brightness

```python
brightness: float
```

Return brightness (rounded to 2 decimal places for display).

##### kelvin

```python
kelvin: int
```

Return kelvin.

#### Functions

##### __eq__

```python
__eq__(other: object) -> bool
```

Two colors are equal if they have the same HSBK values.

Source code in `src/lifx/color.py`

```python
def __eq__(self, other: object) -> bool:
    """Two colors are equal if they have the same HSBK values."""
    if not isinstance(other, HSBK):  # pragma: no cover
        return NotImplemented
    return (
        other.hue == self.hue
        and other.saturation == self.saturation
        and other.brightness == self.brightness
        and other.kelvin == self.kelvin
    )
```

##### __hash__

```python
__hash__() -> int
```

Returns a hash of this color as an integer.

Source code in `src/lifx/color.py`

```python
def __hash__(self) -> int:
    """Returns a hash of this color as an integer."""
    return hash(
        (self.hue, self.saturation, self.brightness, self.kelvin)
    )  # pragma: no cover
```

##### __str__

```python
__str__() -> str
```

Return a string representation of the HSBK values for this color.

Source code in `src/lifx/color.py`

```python
def __str__(self) -> str:
    """Return a string representation of the HSBK values for this color."""
    string = (
        f"Hue: {self.hue}, Saturation: {self.saturation:.4f}, "
        f"Brightness: {self.brightness:.4f}, Kelvin: {self.kelvin}"
    )
    return string
```

##### __repr__

```python
__repr__() -> str
```

Return a string representation of the HSBK values for this color.

Source code in `src/lifx/color.py`

```python
def __repr__(self) -> str:
    """Return a string representation of the HSBK values for this color."""
    repr = (
        f"HSBK(hue={self.hue}, saturation={self.saturation:.2f}, "
        f"brightness={self.brightness:.2f}, kelvin={self.kelvin})"
    )
    return repr
```

##### from_rgb

```python
from_rgb(red: float, green: float, blue: float) -> HSBK
```

Create HSBK from RGB values.

| PARAMETER | DESCRIPTION                                 |
| --------- | ------------------------------------------- |
| `red`     | Red component (0.0-1.0) **TYPE:** `float`   |
| `green`   | Green component (0.0-1.0) **TYPE:** `float` |
| `blue`    | Blue component (0.0-1.0) **TYPE:** `float`  |

| RETURNS | DESCRIPTION   |
| ------- | ------------- |
| `HSBK`  | HSBK instance |

| RAISES       | DESCRIPTION                              |
| ------------ | ---------------------------------------- |
| `ValueError` | If RGB values are out of range (0.0-1.0) |

Example

```python
# Pure red
red = HSBK.from_rgb(1.0, 0.0, 0.0)

# Purple
purple = HSBK.from_rgb(0.5, 0.0, 0.5)
```

Source code in `src/lifx/color.py`

````python
@classmethod
def from_rgb(cls, red: float, green: float, blue: float) -> HSBK:
    """Create HSBK from RGB values.

    Args:
        red: Red component (0.0-1.0)
        green: Green component (0.0-1.0)
        blue: Blue component (0.0-1.0)

    Returns:
        HSBK instance

    Raises:
        ValueError: If RGB values are out of range (0.0-1.0)

    Example:
        ```python
        # Pure red
        red = HSBK.from_rgb(1.0, 0.0, 0.0)

        # Purple
        purple = HSBK.from_rgb(0.5, 0.0, 0.5)
        ```
    """

    def _validate_rgb_component(value: float, name: str) -> None:
        if not (0.0 <= value <= 1.0):
            raise ValueError(f"{name} must be between 0.0 and 1.0, got {value}")

    _validate_rgb_component(red, "Red")
    _validate_rgb_component(green, "Green")
    _validate_rgb_component(blue, "Blue")

    # Convert to HSV using colorsys (already 0-1 range)
    h, s, v = colorsys.rgb_to_hsv(red, green, blue)

    return cls(
        hue=h * 360,  # 0-1 -> 0-360
        saturation=s,
        brightness=v,
        kelvin=KELVIN_NEUTRAL,
    )
````

##### to_rgb

```python
to_rgb() -> tuple[float, float, float]
```

Convert HSBK to RGB values.

Color temperature (kelvin) is not considered in this conversion, as it only affects the white point of the device.

| RETURNS                      | DESCRIPTION                                     |
| ---------------------------- | ----------------------------------------------- |
| `tuple[float, float, float]` | Tuple of (red, green, blue) with values 0.0-1.0 |

Example

```python
color = HSBK(hue=120, saturation=1.0, brightness=1.0, kelvin=3500)
r, g, b = color.to_rgb()  # Returns (0.0, 1.0, 0.0) - green
```

Source code in `src/lifx/color.py`

````python
def to_rgb(self) -> tuple[float, float, float]:
    """Convert HSBK to RGB values.

    Color temperature (kelvin) is not considered in this conversion,
    as it only affects the white point of the device.

    Returns:
        Tuple of (red, green, blue) with values 0.0-1.0

    Example:
        ```python
        color = HSBK(hue=120, saturation=1.0, brightness=1.0, kelvin=3500)
        r, g, b = color.to_rgb()  # Returns (0.0, 1.0, 0.0) - green
        ```
    """
    h = self._hue / 360  # 0-360 -> 0-1
    return colorsys.hsv_to_rgb(h, self._saturation, self._brightness)
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
    hue_u16 = int(round(0x10000 * self._hue) / 360) % 0x10000
    saturation_u16 = int(round(0xFFFF * self._saturation))
    brightness_u16 = int(round(0xFFFF * self._brightness))

    return LightHsbk(
        hue=hue_u16,
        saturation=saturation_u16,
        brightness=brightness_u16,
        kelvin=self._kelvin,
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
    hue = round(float(protocol.hue) * 360 / 0x10000)
    saturation = round(float(protocol.saturation) / 0xFFFF, 2)
    brightness = round(float(protocol.brightness) / 0xFFFF, 2)

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
        saturation=self._saturation,
        brightness=self._brightness,
        kelvin=self._kelvin,
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
        hue=self._hue,
        saturation=saturation,
        brightness=self._brightness,
        kelvin=self._kelvin,
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
        hue=self._hue,
        saturation=self._saturation,
        brightness=brightness,
        kelvin=self._kelvin,
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
        hue=self._hue,
        saturation=self._saturation,
        brightness=self._brightness,
        kelvin=kelvin,
    )
```

##### lerp_hsb

```python
lerp_hsb(other: HSBK, blend: float) -> HSBK
```

Interpolate to another color via shortest-path HSB blending.

| PARAMETER | DESCRIPTION                                                                      |
| --------- | -------------------------------------------------------------------------------- |
| `other`   | Target color to interpolate towards. **TYPE:** `HSBK`                            |
| `blend`   | Blend factor from 0.0 (self) to 1.0 (other), clamped to range. **TYPE:** `float` |

| RETURNS | DESCRIPTION                                                                |
| ------- | -------------------------------------------------------------------------- |
| `HSBK`  | New HSBK instance with interpolated values. Kelvin is preserved from self. |

Source code in `src/lifx/color.py`

```python
def lerp_hsb(self, other: HSBK, blend: float) -> HSBK:
    """Interpolate to another color via shortest-path HSB blending.

    Args:
        other: Target color to interpolate towards.
        blend: Blend factor from 0.0 (self) to 1.0 (other), clamped to range.

    Returns:
        New HSBK instance with interpolated values. Kelvin is preserved from self.
    """
    blend = max(0.0, min(1.0, blend))
    diff = other._hue - self._hue
    if diff > 180:
        diff -= 360
    elif diff < -180:
        diff += 360
    hue = round(self._hue + diff * blend) % 360
    sat = self._saturation + (other._saturation - self._saturation) * blend
    bri = self._brightness + (other._brightness - self._brightness) * blend
    return HSBK(
        hue=hue,
        saturation=round(sat, 2),
        brightness=round(bri, 2),
        kelvin=self._kelvin,
    )
```

##### lerp_oklab

```python
lerp_oklab(other: HSBK, blend: float) -> HSBK
```

Interpolate to another color through Oklab perceptual color space.

Oklab produces perceptually uniform transitions without brightness dips or muddy intermediates that occur with naive HSB blending.

| PARAMETER | DESCRIPTION                                                                      |
| --------- | -------------------------------------------------------------------------------- |
| `other`   | Target color to interpolate towards. **TYPE:** `HSBK`                            |
| `blend`   | Blend factor from 0.0 (self) to 1.0 (other), clamped to range. **TYPE:** `float` |

| RETURNS | DESCRIPTION                                                                |
| ------- | -------------------------------------------------------------------------- |
| `HSBK`  | New HSBK instance with interpolated values. Kelvin is preserved from self. |

Source code in `src/lifx/color.py`

```python
def lerp_oklab(self, other: HSBK, blend: float) -> HSBK:
    """Interpolate to another color through Oklab perceptual color space.

    Oklab produces perceptually uniform transitions without brightness
    dips or muddy intermediates that occur with naive HSB blending.

    Args:
        other: Target color to interpolate towards.
        blend: Blend factor from 0.0 (self) to 1.0 (other), clamped to range.

    Returns:
        New HSBK instance with interpolated values. Kelvin is preserved from self.
    """
    blend = max(0.0, min(1.0, blend))
    r1, g1, b1 = colorsys.hsv_to_rgb(
        self._hue / 360.0, self._saturation, self._brightness
    )
    r2, g2, b2 = colorsys.hsv_to_rgb(
        other._hue / 360.0, other._saturation, other._brightness
    )
    l1, a1, ob1 = _srgb_to_oklab(r1, g1, b1)
    l2, a2, ob2 = _srgb_to_oklab(r2, g2, b2)
    l_interp = l1 + (l2 - l1) * blend
    a_interp = a1 + (a2 - a1) * blend
    ob_interp = ob1 + (ob2 - ob1) * blend
    r, g, b = _oklab_to_srgb(l_interp, a_interp, ob_interp)
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    return HSBK(
        hue=round(h * 360) % 360,
        saturation=round(s, 2),
        brightness=round(v, 2),
        kelvin=self._kelvin,
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
    hue = round(hue)
    saturation = round(saturation_total / len(colors), 2)
    brightness = round(brightness_total / len(colors), 2)
    kelvin = round(kelvin_total / len(colors))

    return cls(hue, saturation, brightness, kelvin)
````

## Colors Class

The `Colors` class provides convenient color presets for common colors.

### Colors

Common color presets for convenience.

Includes all 140 standard HTML/CSS named colors plus white temperature variants and pastel variations.

HTML color reference: https://www.w3.org/TR/css-color-3/#svg-color

## Examples

### Creating Colors

```python
from lifx import HSBK, Colors

# Use built-in color presets
color = Colors.BLUE

# Create custom colors
custom = HSBK(hue=180.0, saturation=1.0, brightness=0.8, kelvin=3500)

# Create from RGB (0.0-1.0)
red = HSBK.from_rgb(1.0, 0.0, 0.0)

# Convert to RGB (returns 0.0-1.0)
r, g, b = Colors.BLUE.to_rgb()
print(f"RGB: ({r:.2f}, {g:.2f}, {b:.2f})")
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
- `Colors.WARM` - Warm white (2500K)
- `Colors.COOL` - Cool white (6500K)

## Color Conversion Notes

### RGB to HSBK

When converting from RGB to HSBK, note that:

- RGB values are floats in the range 0.0-1.0
- Kelvin defaults to 3500K (neutral)
- Conversion uses standard HSV formulas via Python's `colorsys`

### HSBK to RGB

When converting from HSBK to RGB:

- Returns tuple of (r, g, b) with float values 0.0-1.0
- Kelvin temperature is not represented in RGB
- White colors (saturation=0) will be pure gray values
- Round-trip conversion (`from_rgb` -> `to_rgb`) preserves values within floating-point epsilon
