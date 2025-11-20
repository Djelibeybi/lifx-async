"""Color utilities for LIFX devices.

This module provides user-friendly color conversion utilities for working with
LIFX devices, which use the HSBK (Hue, Saturation, Brightness, Kelvin) color space.
"""

from __future__ import annotations

import colorsys
import math

from lifx.const import (
    KELVIN_COOL,
    KELVIN_DAYLIGHT,
    KELVIN_NEUTRAL,
    KELVIN_WARM,
    MAX_BRIGHTNESS,
    MAX_HUE,
    MAX_KELVIN,
    MAX_SATURATION,
    MIN_BRIGHTNESS,
    MIN_HUE,
    MIN_KELVIN,
    MIN_SATURATION,
)
from lifx.protocol.protocol_types import LightHsbk


def validate_hue(value: int) -> None:
    """Validate hue value is in range 0-360 degrees.

    Args:
        value: Hue value to validate

    Raises:
        ValueError: If hue is out of range
    """
    if not (MIN_HUE <= value <= MAX_HUE):
        raise ValueError(f"Hue must be between {MIN_HUE} and {MAX_HUE}, got {value}")


def validate_saturation(value: float) -> None:
    """Validate saturation value is in range 0.0-1.0.

    Args:
        value: Saturation value to validate

    Raises:
        ValueError: If saturation is out of range
    """
    if not (MIN_SATURATION <= value <= MAX_SATURATION):
        raise ValueError(f"Saturation must be 0.0-1.0, got {value}")


def validate_brightness(value: float) -> None:
    """Validate brightness value is in range 0.0-1.0.

    Args:
        value: Brightness value to validate

    Raises:
        ValueError: If brightness is out of range
    """
    if not (MIN_BRIGHTNESS <= value <= MAX_BRIGHTNESS):
        raise ValueError(f"Brightness must be 0.0-1.0, got {value}")


def validate_kelvin(value: int) -> None:
    """Validate kelvin temperature is in range 1500-9000.

    Args:
        value: Kelvin temperature to validate

    Raises:
        ValueError: If kelvin is out of range
    """
    if not (MIN_KELVIN <= value <= MAX_KELVIN):
        raise ValueError(f"Kelvin must be 1500-9000, got {value}")


class HSBK:
    """User-friendly HSBK color representation.

    LIFX devices use HSBK (Hue, Saturation, Brightness, Kelvin) color space.
    This class provides a convenient interface with normalized values and
    conversion to/from RGB.

    Attributes:
        hue: Hue value in degrees (0-360)
        saturation: Saturation (0.0-1.0, where 0 is white and 1 is fully saturated)
        brightness: Brightness (0.0-1.0, where 0 is off and 1 is full brightness)
        kelvin: Color temperature in Kelvin (1500-9000, typically 2500-9000 for LIFX)

    Example:
        ```python
        # Create a red color
        red = HSBK(hue=0, saturation=1.0, brightness=1.0, kelvin=3500)

        # Create from RGB
        purple = HSBK.from_rgb(128, 0, 128)

        # Convert to RGB
        r, g, b = purple.to_rgb()
        ```
    """

    def __init__(
        self, hue: int, saturation: float, brightness: float, kelvin: int
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

    def __hash__(self) -> int:
        """Returns a hash of this color as an integer."""
        return hash(
            (self.hue, self.saturation, self.brightness, self.kelvin)
        )  # pragma: no cover

    def __str__(self) -> str:
        """Return a string representation of the HSBK values for this color."""
        string = (
            f"Hue: {self.hue}, Saturation: {self.saturation:.4f}, "
            f"Brightness: {self.brightness:.4f}, Kelvin: {self.kelvin}"
        )
        return string

    def __repr__(self) -> str:
        """Return a string representation of the HSBK values for this color."""
        repr = (
            f"HSBK(hue={self.hue}, saturation={self.saturation:.2f}, "
            f"brightness={self.brightness:.2f}, kelvin={self.kelvin})"
        )
        return repr

    @property
    def hue(self) -> int:
        """Return hue."""
        return round(self._hue)

    @property
    def saturation(self) -> float:
        """Return saturation."""
        return round(self._saturation, 2)

    @property
    def brightness(self) -> float:
        """Return brightness."""
        return round(self._brightness, 2)

    @property
    def kelvin(self) -> int:
        """Return kelvin."""
        return self._kelvin

    @classmethod
    def from_rgb(cls, red: int, green: int, blue: int) -> HSBK:
        """Create HSBK from RGB values.

        Args:
            red: Red component (0-255)
            green: Green component (0-255)
            blue: Blue component (0-255)

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

        def _validate_rgb_component(value: int, name: str) -> None:
            if not (0 <= value <= 255):
                raise ValueError(f"{name} must be between 0 and 255, got {value}")

        _validate_rgb_component(red, "Red")
        _validate_rgb_component(green, "Green")
        _validate_rgb_component(blue, "Blue")

        # Normalize to 0-1
        red_norm = red / 255
        green_norm = green / 255
        blue_norm = blue / 255

        # Convert to HSV using colorsys
        h, s, v = colorsys.rgb_to_hsv(red_norm, green_norm, blue_norm)

        # Convert to LIFX ranges
        hue = round(h * 360)  # 0-1 -> 0-360
        saturation = round(s, 2)  # Already 0-1
        brightness = round(v, 2)  # Already 0-1

        return cls(
            hue=hue,
            saturation=saturation,
            brightness=brightness,
            kelvin=KELVIN_NEUTRAL,
        )

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
        h = self._hue / 360  # 0-360 -> 0-1
        s = self._saturation  # Already 0-1
        v = self._brightness  # Already 0-1

        # Convert using colorsys
        red_norm, green_norm, blue_norm = colorsys.hsv_to_rgb(h, s, v)

        # Scale to 0-255 and round
        red = int(round(red_norm * 255))
        green = int(round(green_norm * 255))
        blue = int(round(blue_norm * 255))

        return red, green, blue

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

    def with_hue(self, hue: int) -> HSBK:
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


# Common color presets
class Colors:
    """Common color presets for convenience."""

    # Primary colors
    RED = HSBK(hue=0, saturation=1.0, brightness=1.0, kelvin=KELVIN_NEUTRAL)
    ORANGE = HSBK(hue=30, saturation=1.0, brightness=1.0, kelvin=KELVIN_NEUTRAL)
    YELLOW = HSBK(hue=60, saturation=1.0, brightness=1.0, kelvin=KELVIN_NEUTRAL)
    GREEN = HSBK(hue=120, saturation=1.0, brightness=1.0, kelvin=KELVIN_NEUTRAL)
    CYAN = HSBK(hue=180, saturation=1.0, brightness=1.0, kelvin=KELVIN_NEUTRAL)
    BLUE = HSBK(hue=240, saturation=1.0, brightness=1.0, kelvin=KELVIN_NEUTRAL)
    PURPLE = HSBK(hue=270, saturation=1.0, brightness=1.0, kelvin=KELVIN_NEUTRAL)
    MAGENTA = HSBK(hue=300, saturation=1.0, brightness=1.0, kelvin=KELVIN_NEUTRAL)
    PINK = HSBK(hue=330, saturation=1.0, brightness=1.0, kelvin=KELVIN_NEUTRAL)

    # White variants
    WHITE_WARM = HSBK(hue=0, saturation=0.0, brightness=1.0, kelvin=KELVIN_WARM)
    WHITE_NEUTRAL = HSBK(hue=0, saturation=0.0, brightness=1.0, kelvin=KELVIN_NEUTRAL)
    WHITE_COOL = HSBK(hue=0, saturation=0.0, brightness=1.0, kelvin=KELVIN_COOL)
    WHITE_DAYLIGHT = HSBK(hue=0, saturation=0.0, brightness=1.0, kelvin=KELVIN_DAYLIGHT)

    # Pastels
    PASTEL_RED = HSBK(hue=0, saturation=0.3, brightness=1.0, kelvin=KELVIN_NEUTRAL)
    PASTEL_ORANGE = HSBK(hue=30, saturation=0.3, brightness=1.0, kelvin=KELVIN_NEUTRAL)
    PASTEL_YELLOW = HSBK(hue=60, saturation=0.3, brightness=1.0, kelvin=KELVIN_NEUTRAL)
    PASTEL_GREEN = HSBK(hue=120, saturation=0.3, brightness=1.0, kelvin=KELVIN_NEUTRAL)
    PASTEL_CYAN = HSBK(hue=180, saturation=0.3, brightness=1.0, kelvin=KELVIN_NEUTRAL)
    PASTEL_BLUE = HSBK(hue=240, saturation=0.3, brightness=1.0, kelvin=KELVIN_NEUTRAL)
    PASTEL_PURPLE = HSBK(hue=270, saturation=0.3, brightness=1.0, kelvin=KELVIN_NEUTRAL)
    PASTEL_MAGENTA = HSBK(
        hue=300, saturation=0.3, brightness=1.0, kelvin=KELVIN_NEUTRAL
    )
    PASTEL_PINK = HSBK(hue=330, saturation=0.3, brightness=1.0, kelvin=KELVIN_NEUTRAL)
