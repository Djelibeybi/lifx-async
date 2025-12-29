"""Color utilities for LIFX devices.

This module provides user-friendly color conversion utilities for working with
LIFX devices, which use the HSBK (Hue, Saturation, Brightness, Kelvin) color space.
"""

from __future__ import annotations

import colorsys
import math

from lifx.const import (
    KELVIN_AMBER,
    KELVIN_BLUE_DAYLIGHT,
    KELVIN_BLUE_ICE,
    KELVIN_BLUE_OVERCAST,
    KELVIN_BRIGHT_DAYLIGHT,
    KELVIN_CANDLELIGHT,
    KELVIN_CLOUDY_DAYLIGHT,
    KELVIN_COOL,
    KELVIN_COOL_DAYLIGHT,
    KELVIN_DAYLIGHT,
    KELVIN_INCANDESCENT,
    KELVIN_NEUTRAL,
    KELVIN_NEUTRAL_WARM,
    KELVIN_NOON_DAYLIGHT,
    KELVIN_SOFT_DAYLIGHT,
    KELVIN_SUNSET,
    KELVIN_ULTRA_WARM,
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
    """Common color presets for convenience.

    Includes all 140 standard HTML/CSS named colors plus white temperature
    variants and pastel variations.

    HTML color reference: https://www.w3.org/TR/css-color-3/#svg-color
    """

    # Off / Black (brightness=0 turns light off or sets zone to black)
    OFF = HSBK(hue=0, saturation=0.0, brightness=0.0, kelvin=KELVIN_NEUTRAL)

    # HTML Named Colors (alphabetical order)
    ALICE_BLUE = HSBK.from_rgb(240, 248, 255)
    ANTIQUE_WHITE = HSBK.from_rgb(250, 235, 215)
    AQUA = HSBK.from_rgb(0, 255, 255)
    AQUAMARINE = HSBK.from_rgb(127, 255, 212)
    AZURE = HSBK.from_rgb(240, 255, 255)
    BEIGE = HSBK.from_rgb(245, 245, 220)
    BISQUE = HSBK.from_rgb(255, 228, 196)
    BLACK = HSBK.from_rgb(0, 0, 0)
    BLANCHED_ALMOND = HSBK.from_rgb(255, 235, 205)
    BLUE = HSBK.from_rgb(0, 0, 255)
    BLUE_VIOLET = HSBK.from_rgb(138, 43, 226)
    BROWN = HSBK.from_rgb(165, 42, 42)
    BURLYWOOD = HSBK.from_rgb(222, 184, 135)
    CADET_BLUE = HSBK.from_rgb(95, 158, 160)
    CHARTREUSE = HSBK.from_rgb(127, 255, 0)
    CHOCOLATE = HSBK.from_rgb(210, 105, 30)
    CORAL = HSBK.from_rgb(255, 127, 80)
    CORNFLOWER_BLUE = HSBK.from_rgb(100, 149, 237)
    CORNSILK = HSBK.from_rgb(255, 248, 220)
    CRIMSON = HSBK.from_rgb(220, 20, 60)
    CYAN = HSBK.from_rgb(0, 255, 255)
    DARK_BLUE = HSBK.from_rgb(0, 0, 139)
    DARK_CYAN = HSBK.from_rgb(0, 139, 139)
    DARK_GOLDENROD = HSBK.from_rgb(184, 134, 11)
    DARK_GRAY = HSBK.from_rgb(169, 169, 169)
    DARK_GREEN = HSBK.from_rgb(0, 100, 0)
    DARK_GREY = HSBK.from_rgb(169, 169, 169)
    DARK_KHAKI = HSBK.from_rgb(189, 183, 107)
    DARK_MAGENTA = HSBK.from_rgb(139, 0, 139)
    DARK_OLIVE_GREEN = HSBK.from_rgb(85, 107, 47)
    DARK_ORANGE = HSBK.from_rgb(255, 140, 0)
    DARK_ORCHID = HSBK.from_rgb(153, 50, 204)
    DARK_RED = HSBK.from_rgb(139, 0, 0)
    DARK_SALMON = HSBK.from_rgb(233, 150, 122)
    DARK_SEA_GREEN = HSBK.from_rgb(143, 188, 143)
    DARK_SLATE_BLUE = HSBK.from_rgb(72, 61, 139)
    DARK_SLATE_GRAY = HSBK.from_rgb(47, 79, 79)
    DARK_SLATE_GREY = HSBK.from_rgb(47, 79, 79)
    DARK_TURQUOISE = HSBK.from_rgb(0, 206, 209)
    DARK_VIOLET = HSBK.from_rgb(148, 0, 211)
    DEEP_PINK = HSBK.from_rgb(255, 20, 147)
    DEEP_SKY_BLUE = HSBK.from_rgb(0, 191, 255)
    DIM_GRAY = HSBK.from_rgb(105, 105, 105)
    DIM_GREY = HSBK.from_rgb(105, 105, 105)
    DODGER_BLUE = HSBK.from_rgb(30, 144, 255)
    FIREBRICK = HSBK.from_rgb(178, 34, 34)
    FLORAL_WHITE = HSBK.from_rgb(255, 250, 240)
    FOREST_GREEN = HSBK.from_rgb(34, 139, 34)
    FUCHSIA = HSBK.from_rgb(255, 0, 255)
    GAINSBORO = HSBK.from_rgb(220, 220, 220)
    GHOST_WHITE = HSBK.from_rgb(248, 248, 255)
    GOLD = HSBK.from_rgb(255, 215, 0)
    GOLDENROD = HSBK.from_rgb(218, 165, 32)
    GRAY = HSBK.from_rgb(128, 128, 128)
    GREEN = HSBK.from_rgb(0, 128, 0)
    GREEN_YELLOW = HSBK.from_rgb(173, 255, 47)
    GREY = HSBK.from_rgb(128, 128, 128)
    HONEYDEW = HSBK.from_rgb(240, 255, 240)
    HOT_PINK = HSBK.from_rgb(255, 105, 180)
    INDIAN_RED = HSBK.from_rgb(205, 92, 92)
    INDIGO = HSBK.from_rgb(75, 0, 130)
    IVORY = HSBK.from_rgb(255, 255, 240)
    KHAKI = HSBK.from_rgb(240, 230, 140)
    LAVENDER = HSBK.from_rgb(230, 230, 250)
    LAVENDER_BLUSH = HSBK.from_rgb(255, 240, 245)
    LAWN_GREEN = HSBK.from_rgb(124, 252, 0)
    LEMON_CHIFFON = HSBK.from_rgb(255, 250, 205)
    LIGHT_BLUE = HSBK.from_rgb(173, 216, 230)
    LIGHT_CORAL = HSBK.from_rgb(240, 128, 128)
    LIGHT_CYAN = HSBK.from_rgb(224, 255, 255)
    LIGHT_GOLDENROD_YELLOW = HSBK.from_rgb(250, 250, 210)
    LIGHT_GRAY = HSBK.from_rgb(211, 211, 211)
    LIGHT_GREEN = HSBK.from_rgb(144, 238, 144)
    LIGHT_GREY = HSBK.from_rgb(211, 211, 211)
    LIGHT_PINK = HSBK.from_rgb(255, 182, 193)
    LIGHT_SALMON = HSBK.from_rgb(255, 160, 122)
    LIGHT_SEA_GREEN = HSBK.from_rgb(32, 178, 170)
    LIGHT_SKY_BLUE = HSBK.from_rgb(135, 206, 250)
    LIGHT_SLATE_GRAY = HSBK.from_rgb(119, 136, 153)
    LIGHT_SLATE_GREY = HSBK.from_rgb(119, 136, 153)
    LIGHT_STEEL_BLUE = HSBK.from_rgb(176, 196, 222)
    LIGHT_YELLOW = HSBK.from_rgb(255, 255, 224)
    LIME = HSBK.from_rgb(0, 255, 0)
    LIME_GREEN = HSBK.from_rgb(50, 205, 50)
    LINEN = HSBK.from_rgb(250, 240, 230)
    MAGENTA = HSBK.from_rgb(255, 0, 255)
    MAROON = HSBK.from_rgb(128, 0, 0)
    MEDIUM_AQUAMARINE = HSBK.from_rgb(102, 205, 170)
    MEDIUM_BLUE = HSBK.from_rgb(0, 0, 205)
    MEDIUM_ORCHID = HSBK.from_rgb(186, 85, 211)
    MEDIUM_PURPLE = HSBK.from_rgb(147, 112, 219)
    MEDIUM_SEA_GREEN = HSBK.from_rgb(60, 179, 113)
    MEDIUM_SLATE_BLUE = HSBK.from_rgb(123, 104, 238)
    MEDIUM_SPRING_GREEN = HSBK.from_rgb(0, 250, 154)
    MEDIUM_TURQUOISE = HSBK.from_rgb(72, 209, 204)
    MEDIUM_VIOLET_RED = HSBK.from_rgb(199, 21, 133)
    MIDNIGHT_BLUE = HSBK.from_rgb(25, 25, 112)
    MINT_CREAM = HSBK.from_rgb(245, 255, 250)
    MISTY_ROSE = HSBK.from_rgb(255, 228, 225)
    MOCCASIN = HSBK.from_rgb(255, 228, 181)
    NAVAJO_WHITE = HSBK.from_rgb(255, 222, 173)
    NAVY = HSBK.from_rgb(0, 0, 128)
    OLD_LACE = HSBK.from_rgb(253, 245, 230)
    OLIVE = HSBK.from_rgb(128, 128, 0)
    OLIVE_DRAB = HSBK.from_rgb(107, 142, 35)
    ORANGE = HSBK.from_rgb(255, 165, 0)
    ORANGE_RED = HSBK.from_rgb(255, 69, 0)
    ORCHID = HSBK.from_rgb(218, 112, 214)
    PALE_GOLDENROD = HSBK.from_rgb(238, 232, 170)
    PALE_GREEN = HSBK.from_rgb(152, 251, 152)
    PALE_TURQUOISE = HSBK.from_rgb(175, 238, 238)
    PALE_VIOLET_RED = HSBK.from_rgb(219, 112, 147)
    PAPAYA_WHIP = HSBK.from_rgb(255, 239, 213)
    PEACH_PUFF = HSBK.from_rgb(255, 218, 185)
    PERU = HSBK.from_rgb(205, 133, 63)
    PINK = HSBK.from_rgb(255, 192, 203)
    PLUM = HSBK.from_rgb(221, 160, 221)
    POWDER_BLUE = HSBK.from_rgb(176, 224, 230)
    PURPLE = HSBK.from_rgb(128, 0, 128)
    REBECCA_PURPLE = HSBK.from_rgb(102, 51, 153)
    RED = HSBK.from_rgb(255, 0, 0)
    ROSY_BROWN = HSBK.from_rgb(188, 143, 143)
    ROYAL_BLUE = HSBK.from_rgb(65, 105, 225)
    SADDLE_BROWN = HSBK.from_rgb(139, 69, 19)
    SALMON = HSBK.from_rgb(250, 128, 114)
    SANDY_BROWN = HSBK.from_rgb(244, 164, 96)
    SEA_GREEN = HSBK.from_rgb(46, 139, 87)
    SEASHELL = HSBK.from_rgb(255, 245, 238)
    SIENNA = HSBK.from_rgb(160, 82, 45)
    SILVER = HSBK.from_rgb(192, 192, 192)
    SKY_BLUE = HSBK.from_rgb(135, 206, 235)
    SLATE_BLUE = HSBK.from_rgb(106, 90, 205)
    SLATE_GRAY = HSBK.from_rgb(112, 128, 144)
    SLATE_GREY = HSBK.from_rgb(112, 128, 144)
    SNOW = HSBK.from_rgb(255, 250, 250)
    SPRING_GREEN = HSBK.from_rgb(0, 255, 127)
    STEEL_BLUE = HSBK.from_rgb(70, 130, 180)
    TAN = HSBK.from_rgb(210, 180, 140)
    TEAL = HSBK.from_rgb(0, 128, 128)
    THISTLE = HSBK.from_rgb(216, 191, 216)
    TOMATO = HSBK.from_rgb(255, 99, 71)
    TURQUOISE = HSBK.from_rgb(64, 224, 208)
    VIOLET = HSBK.from_rgb(238, 130, 238)
    WHEAT = HSBK.from_rgb(245, 222, 179)
    WHITE = HSBK.from_rgb(255, 255, 255)
    WHITE_SMOKE = HSBK.from_rgb(245, 245, 245)
    YELLOW = HSBK.from_rgb(255, 255, 0)
    YELLOW_GREEN = HSBK.from_rgb(154, 205, 50)

    # White temperature variants (kelvin-based, warmest to coolest)
    CANDLELIGHT = HSBK(hue=0, saturation=0.0, brightness=1.0, kelvin=KELVIN_CANDLELIGHT)
    SUNSET = HSBK(hue=0, saturation=0.0, brightness=1.0, kelvin=KELVIN_SUNSET)
    AMBER = HSBK(hue=0, saturation=0.0, brightness=1.0, kelvin=KELVIN_AMBER)
    ULTRA_WARM = HSBK(hue=0, saturation=0.0, brightness=1.0, kelvin=KELVIN_ULTRA_WARM)
    INCANDESCENT = HSBK(
        hue=0, saturation=0.0, brightness=1.0, kelvin=KELVIN_INCANDESCENT
    )
    WARM = HSBK(hue=0, saturation=0.0, brightness=1.0, kelvin=KELVIN_WARM)
    NEUTRAL_WARM = HSBK(
        hue=0, saturation=0.0, brightness=1.0, kelvin=KELVIN_NEUTRAL_WARM
    )
    NEUTRAL = HSBK(hue=0, saturation=0.0, brightness=1.0, kelvin=KELVIN_NEUTRAL)
    COOL = HSBK(hue=0, saturation=0.0, brightness=1.0, kelvin=KELVIN_COOL)
    COOL_DAYLIGHT = HSBK(
        hue=0, saturation=0.0, brightness=1.0, kelvin=KELVIN_COOL_DAYLIGHT
    )
    SOFT_DAYLIGHT = HSBK(
        hue=0, saturation=0.0, brightness=1.0, kelvin=KELVIN_SOFT_DAYLIGHT
    )
    DAYLIGHT = HSBK(hue=0, saturation=0.0, brightness=1.0, kelvin=KELVIN_DAYLIGHT)
    NOON_DAYLIGHT = HSBK(
        hue=0, saturation=0.0, brightness=1.0, kelvin=KELVIN_NOON_DAYLIGHT
    )
    BRIGHT_DAYLIGHT = HSBK(
        hue=0, saturation=0.0, brightness=1.0, kelvin=KELVIN_BRIGHT_DAYLIGHT
    )
    CLOUDY_DAYLIGHT = HSBK(
        hue=0, saturation=0.0, brightness=1.0, kelvin=KELVIN_CLOUDY_DAYLIGHT
    )
    BLUE_DAYLIGHT = HSBK(
        hue=0, saturation=0.0, brightness=1.0, kelvin=KELVIN_BLUE_DAYLIGHT
    )
    BLUE_OVERCAST = HSBK(
        hue=0, saturation=0.0, brightness=1.0, kelvin=KELVIN_BLUE_OVERCAST
    )
    BLUE_ICE = HSBK(hue=0, saturation=0.0, brightness=1.0, kelvin=KELVIN_BLUE_ICE)

    # Pastel variants (reduced saturation)
    PASTEL_RED = HSBK(hue=0, saturation=0.3, brightness=1.0, kelvin=KELVIN_NEUTRAL)
    PASTEL_ORANGE = HSBK(hue=39, saturation=0.3, brightness=1.0, kelvin=KELVIN_NEUTRAL)
    PASTEL_YELLOW = HSBK(hue=60, saturation=0.3, brightness=1.0, kelvin=KELVIN_NEUTRAL)
    PASTEL_GREEN = HSBK(hue=120, saturation=0.3, brightness=1.0, kelvin=KELVIN_NEUTRAL)
    PASTEL_CYAN = HSBK(hue=180, saturation=0.3, brightness=1.0, kelvin=KELVIN_NEUTRAL)
    PASTEL_BLUE = HSBK(hue=240, saturation=0.3, brightness=1.0, kelvin=KELVIN_NEUTRAL)
    PASTEL_PURPLE = HSBK(hue=300, saturation=0.3, brightness=1.0, kelvin=KELVIN_NEUTRAL)
    PASTEL_MAGENTA = HSBK(
        hue=300, saturation=0.3, brightness=1.0, kelvin=KELVIN_NEUTRAL
    )
    PASTEL_PINK = HSBK(hue=350, saturation=0.3, brightness=1.0, kelvin=KELVIN_NEUTRAL)

    # Backwards compatibility aliases
    WHITE_WARM = WARM
    WHITE_NEUTRAL = NEUTRAL
    WHITE_COOL = COOL
    WHITE_DAYLIGHT = DAYLIGHT
