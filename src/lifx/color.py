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

# ---------------------------------------------------------------------------
# sRGB gamma (IEC 61966-2-1)
# ---------------------------------------------------------------------------

_SRGB_LINEAR_THRESHOLD: float = 0.04045
_SRGB_LINEAR_SCALE: float = 12.92
_SRGB_GAMMA: float = 2.4
_SRGB_OFFSET: float = 0.055
_SRGB_DIVISOR: float = 1.055


def _srgb_to_linear(c: float) -> float:
    """Remove sRGB gamma curve from a single channel.

    Args:
        c: sRGB channel value in [0.0, 1.0].

    Returns:
        Linear-light value in [0.0, 1.0].
    """
    if c <= _SRGB_LINEAR_THRESHOLD:
        return c / _SRGB_LINEAR_SCALE
    return ((c + _SRGB_OFFSET) / _SRGB_DIVISOR) ** _SRGB_GAMMA


def _linear_to_srgb(c: float) -> float:
    """Apply sRGB gamma curve to a single channel.

    Args:
        c: Linear-light value in [0.0, 1.0].

    Returns:
        sRGB channel value in [0.0, 1.0].
    """
    if c <= 0.0031308:
        return c * _SRGB_LINEAR_SCALE
    return _SRGB_DIVISOR * (c ** (1.0 / _SRGB_GAMMA)) - _SRGB_OFFSET


# ---------------------------------------------------------------------------
# sRGB <-> Oklab (Bjorn Ottosson, 2020)
# ---------------------------------------------------------------------------

# sRGB linear -> LMS cone responses (M1).
_OK_M1: list[list[float]] = [
    [0.4122214708, 0.5363325363, 0.0514459929],
    [0.2119034982, 0.6806995451, 0.1073969566],
    [0.0883024619, 0.2817188376, 0.6299787005],
]

# LMS cube root -> Oklab (M2).
_OK_M2: list[list[float]] = [
    [0.2104542553, 0.7936177850, -0.0040720468],
    [1.9779984951, -2.4285922050, 0.4505937099],
    [0.0259040371, 0.7827717662, -0.8086757660],
]

# Oklab -> LMS cube root (M2 inverse).
_OK_M2_INV: list[list[float]] = [
    [1.0000000000, 0.3963377774, 0.2158037573],
    [1.0000000000, -0.1055613458, -0.0638541728],
    [1.0000000000, -0.0894841775, -1.2914855480],
]

# LMS -> sRGB linear (M1 inverse).
_OK_M1_INV: list[list[float]] = [
    [4.0767416621, -3.3077115913, 0.2309699292],
    [-1.2684380046, 2.6097574011, -0.3413193965],
    [-0.0041960863, -0.7034186147, 1.7076147010],
]

_ONE_THIRD: float = 1.0 / 3.0


def _srgb_to_oklab(r: float, g: float, b: float) -> tuple[float, float, float]:
    """Convert sRGB to Oklab.

    Args:
        r, g, b: sRGB channels in [0.0, 1.0].

    Returns:
        Tuple of (L, a, b) in Oklab space. L is 0-1.
    """
    rl = _srgb_to_linear(r)
    gl = _srgb_to_linear(g)
    bl = _srgb_to_linear(b)

    lms_l = _OK_M1[0][0] * rl + _OK_M1[0][1] * gl + _OK_M1[0][2] * bl
    m = _OK_M1[1][0] * rl + _OK_M1[1][1] * gl + _OK_M1[1][2] * bl
    s = _OK_M1[2][0] * rl + _OK_M1[2][1] * gl + _OK_M1[2][2] * bl

    l_ = math.copysign(abs(lms_l) ** _ONE_THIRD, lms_l) if lms_l != 0.0 else 0.0
    m_ = math.copysign(abs(m) ** _ONE_THIRD, m) if m != 0.0 else 0.0
    s_ = math.copysign(abs(s) ** _ONE_THIRD, s) if s != 0.0 else 0.0

    ok_l = _OK_M2[0][0] * l_ + _OK_M2[0][1] * m_ + _OK_M2[0][2] * s_
    ok_a = _OK_M2[1][0] * l_ + _OK_M2[1][1] * m_ + _OK_M2[1][2] * s_
    ok_b = _OK_M2[2][0] * l_ + _OK_M2[2][1] * m_ + _OK_M2[2][2] * s_

    return (ok_l, ok_a, ok_b)


def _oklab_to_srgb(ok_l: float, ok_a: float, ok_b: float) -> tuple[float, float, float]:
    """Convert Oklab to sRGB.

    Args:
        ok_l: Lightness (0-1).
        ok_a: Green-red axis.
        ok_b: Blue-yellow axis.

    Returns:
        Tuple of (r, g, b) each in [0.0, 1.0], clamped to gamut.
    """
    l_ = _OK_M2_INV[0][0] * ok_l + _OK_M2_INV[0][1] * ok_a + _OK_M2_INV[0][2] * ok_b
    m_ = _OK_M2_INV[1][0] * ok_l + _OK_M2_INV[1][1] * ok_a + _OK_M2_INV[1][2] * ok_b
    s_ = _OK_M2_INV[2][0] * ok_l + _OK_M2_INV[2][1] * ok_a + _OK_M2_INV[2][2] * ok_b

    lms_l = l_ * l_ * l_
    m = m_ * m_ * m_
    s = s_ * s_ * s_

    rl = _OK_M1_INV[0][0] * lms_l + _OK_M1_INV[0][1] * m + _OK_M1_INV[0][2] * s
    gl = _OK_M1_INV[1][0] * lms_l + _OK_M1_INV[1][1] * m + _OK_M1_INV[1][2] * s
    bl = _OK_M1_INV[2][0] * lms_l + _OK_M1_INV[2][1] * m + _OK_M1_INV[2][2] * s

    rl = max(0.0, min(1.0, rl))
    gl = max(0.0, min(1.0, gl))
    bl = max(0.0, min(1.0, bl))

    return (_linear_to_srgb(rl), _linear_to_srgb(gl), _linear_to_srgb(bl))


def validate_hue(value: float) -> None:
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
        purple = HSBK.from_rgb(0.5, 0.0, 0.5)

        # Convert to RGB
        r, g, b = purple.to_rgb()
        ```
    """

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
    def hue(self) -> float:
        """Return hue."""
        return self._hue

    @property
    def saturation(self) -> float:
        """Return saturation."""
        return self._saturation

    @property
    def brightness(self) -> float:
        """Return brightness."""
        return self._brightness

    @property
    def kelvin(self) -> int:
        """Return kelvin."""
        return self._kelvin

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
    ALICE_BLUE = HSBK.from_rgb(0.9411764706, 0.9725490196, 1.0)
    ANTIQUE_WHITE = HSBK.from_rgb(0.9803921569, 0.9215686275, 0.8431372549)
    AQUA = HSBK.from_rgb(0.0, 1.0, 1.0)
    AQUAMARINE = HSBK.from_rgb(0.4980392157, 1.0, 0.831372549)
    AZURE = HSBK.from_rgb(0.9411764706, 1.0, 1.0)
    BEIGE = HSBK.from_rgb(0.9607843137, 0.9607843137, 0.862745098)
    BISQUE = HSBK.from_rgb(1.0, 0.8941176471, 0.768627451)
    BLACK = HSBK.from_rgb(0.0, 0.0, 0.0)
    BLANCHED_ALMOND = HSBK.from_rgb(1.0, 0.9215686275, 0.8039215686)
    BLUE = HSBK.from_rgb(0.0, 0.0, 1.0)
    BLUE_VIOLET = HSBK.from_rgb(0.5411764706, 0.168627451, 0.8862745098)
    BROWN = HSBK.from_rgb(0.6470588235, 0.1647058824, 0.1647058824)
    BURLYWOOD = HSBK.from_rgb(0.8705882353, 0.7215686275, 0.5294117647)
    CADET_BLUE = HSBK.from_rgb(0.3725490196, 0.6196078431, 0.6274509804)
    CHARTREUSE = HSBK.from_rgb(0.4980392157, 1.0, 0.0)
    CHOCOLATE = HSBK.from_rgb(0.8235294118, 0.4117647059, 0.1176470588)
    CORAL = HSBK.from_rgb(1.0, 0.4980392157, 0.3137254902)
    CORNFLOWER_BLUE = HSBK.from_rgb(0.3921568627, 0.5843137255, 0.9294117647)
    CORNSILK = HSBK.from_rgb(1.0, 0.9725490196, 0.862745098)
    CRIMSON = HSBK.from_rgb(0.862745098, 0.0784313725, 0.2352941176)
    CYAN = HSBK.from_rgb(0.0, 1.0, 1.0)
    DARK_BLUE = HSBK.from_rgb(0.0, 0.0, 0.5450980392)
    DARK_CYAN = HSBK.from_rgb(0.0, 0.5450980392, 0.5450980392)
    DARK_GOLDENROD = HSBK.from_rgb(0.7215686275, 0.5254901961, 0.0431372549)
    DARK_GRAY = HSBK.from_rgb(0.662745098, 0.662745098, 0.662745098)
    DARK_GREEN = HSBK.from_rgb(0.0, 0.3921568627, 0.0)
    DARK_GREY = HSBK.from_rgb(0.662745098, 0.662745098, 0.662745098)
    DARK_KHAKI = HSBK.from_rgb(0.7411764706, 0.7176470588, 0.4196078431)
    DARK_MAGENTA = HSBK.from_rgb(0.5450980392, 0.0, 0.5450980392)
    DARK_OLIVE_GREEN = HSBK.from_rgb(0.3333333333, 0.4196078431, 0.1843137255)
    DARK_ORANGE = HSBK.from_rgb(1.0, 0.5490196078, 0.0)
    DARK_ORCHID = HSBK.from_rgb(0.6, 0.1960784314, 0.8)
    DARK_RED = HSBK.from_rgb(0.5450980392, 0.0, 0.0)
    DARK_SALMON = HSBK.from_rgb(0.9137254902, 0.5882352941, 0.4784313725)
    DARK_SEA_GREEN = HSBK.from_rgb(0.5607843137, 0.737254902, 0.5607843137)
    DARK_SLATE_BLUE = HSBK.from_rgb(0.2823529412, 0.2392156863, 0.5450980392)
    DARK_SLATE_GRAY = HSBK.from_rgb(0.1843137255, 0.3098039216, 0.3098039216)
    DARK_SLATE_GREY = HSBK.from_rgb(0.1843137255, 0.3098039216, 0.3098039216)
    DARK_TURQUOISE = HSBK.from_rgb(0.0, 0.8078431373, 0.8196078431)
    DARK_VIOLET = HSBK.from_rgb(0.5803921569, 0.0, 0.8274509804)
    DEEP_PINK = HSBK.from_rgb(1.0, 0.0784313725, 0.5764705882)
    DEEP_SKY_BLUE = HSBK.from_rgb(0.0, 0.7490196078, 1.0)
    DIM_GRAY = HSBK.from_rgb(0.4117647059, 0.4117647059, 0.4117647059)
    DIM_GREY = HSBK.from_rgb(0.4117647059, 0.4117647059, 0.4117647059)
    DODGER_BLUE = HSBK.from_rgb(0.1176470588, 0.5647058824, 1.0)
    FIREBRICK = HSBK.from_rgb(0.6980392157, 0.1333333333, 0.1333333333)
    FLORAL_WHITE = HSBK.from_rgb(1.0, 0.9803921569, 0.9411764706)
    FOREST_GREEN = HSBK.from_rgb(0.1333333333, 0.5450980392, 0.1333333333)
    FUCHSIA = HSBK.from_rgb(1.0, 0.0, 1.0)
    GAINSBORO = HSBK.from_rgb(0.862745098, 0.862745098, 0.862745098)
    GHOST_WHITE = HSBK.from_rgb(0.9725490196, 0.9725490196, 1.0)
    GOLD = HSBK.from_rgb(1.0, 0.8431372549, 0.0)
    GOLDENROD = HSBK.from_rgb(0.8549019608, 0.6470588235, 0.1254901961)
    GRAY = HSBK.from_rgb(0.5019607843, 0.5019607843, 0.5019607843)
    GREEN = HSBK.from_rgb(0.0, 0.5019607843, 0.0)
    GREEN_YELLOW = HSBK.from_rgb(0.6784313725, 1.0, 0.1843137255)
    GREY = HSBK.from_rgb(0.5019607843, 0.5019607843, 0.5019607843)
    HONEYDEW = HSBK.from_rgb(0.9411764706, 1.0, 0.9411764706)
    HOT_PINK = HSBK.from_rgb(1.0, 0.4117647059, 0.7058823529)
    INDIAN_RED = HSBK.from_rgb(0.8039215686, 0.3607843137, 0.3607843137)
    INDIGO = HSBK.from_rgb(0.2941176471, 0.0, 0.5098039216)
    IVORY = HSBK.from_rgb(1.0, 1.0, 0.9411764706)
    KHAKI = HSBK.from_rgb(0.9411764706, 0.9019607843, 0.5490196078)
    LAVENDER = HSBK.from_rgb(0.9019607843, 0.9019607843, 0.9803921569)
    LAVENDER_BLUSH = HSBK.from_rgb(1.0, 0.9411764706, 0.9607843137)
    LAWN_GREEN = HSBK.from_rgb(0.4862745098, 0.9882352941, 0.0)
    LEMON_CHIFFON = HSBK.from_rgb(1.0, 0.9803921569, 0.8039215686)
    LIGHT_BLUE = HSBK.from_rgb(0.6784313725, 0.8470588235, 0.9019607843)
    LIGHT_CORAL = HSBK.from_rgb(0.9411764706, 0.5019607843, 0.5019607843)
    LIGHT_CYAN = HSBK.from_rgb(0.8784313725, 1.0, 1.0)
    LIGHT_GOLDENROD_YELLOW = HSBK.from_rgb(0.9803921569, 0.9803921569, 0.8235294118)
    LIGHT_GRAY = HSBK.from_rgb(0.8274509804, 0.8274509804, 0.8274509804)
    LIGHT_GREEN = HSBK.from_rgb(0.5647058824, 0.9333333333, 0.5647058824)
    LIGHT_GREY = HSBK.from_rgb(0.8274509804, 0.8274509804, 0.8274509804)
    LIGHT_PINK = HSBK.from_rgb(1.0, 0.7137254902, 0.7568627451)
    LIGHT_SALMON = HSBK.from_rgb(1.0, 0.6274509804, 0.4784313725)
    LIGHT_SEA_GREEN = HSBK.from_rgb(0.1254901961, 0.6980392157, 0.6666666667)
    LIGHT_SKY_BLUE = HSBK.from_rgb(0.5294117647, 0.8078431373, 0.9803921569)
    LIGHT_SLATE_GRAY = HSBK.from_rgb(0.4666666667, 0.5333333333, 0.6)
    LIGHT_SLATE_GREY = HSBK.from_rgb(0.4666666667, 0.5333333333, 0.6)
    LIGHT_STEEL_BLUE = HSBK.from_rgb(0.6901960784, 0.768627451, 0.8705882353)
    LIGHT_YELLOW = HSBK.from_rgb(1.0, 1.0, 0.8784313725)
    LIME = HSBK.from_rgb(0.0, 1.0, 0.0)
    LIME_GREEN = HSBK.from_rgb(0.1960784314, 0.8039215686, 0.1960784314)
    LINEN = HSBK.from_rgb(0.9803921569, 0.9411764706, 0.9019607843)
    MAGENTA = HSBK.from_rgb(1.0, 0.0, 1.0)
    MAROON = HSBK.from_rgb(0.5019607843, 0.0, 0.0)
    MEDIUM_AQUAMARINE = HSBK.from_rgb(0.4, 0.8039215686, 0.6666666667)
    MEDIUM_BLUE = HSBK.from_rgb(0.0, 0.0, 0.8039215686)
    MEDIUM_ORCHID = HSBK.from_rgb(0.7294117647, 0.3333333333, 0.8274509804)
    MEDIUM_PURPLE = HSBK.from_rgb(0.5764705882, 0.4392156863, 0.8588235294)
    MEDIUM_SEA_GREEN = HSBK.from_rgb(0.2352941176, 0.7019607843, 0.4431372549)
    MEDIUM_SLATE_BLUE = HSBK.from_rgb(0.4823529412, 0.4078431373, 0.9333333333)
    MEDIUM_SPRING_GREEN = HSBK.from_rgb(0.0, 0.9803921569, 0.6039215686)
    MEDIUM_TURQUOISE = HSBK.from_rgb(0.2823529412, 0.8196078431, 0.8)
    MEDIUM_VIOLET_RED = HSBK.from_rgb(0.7803921569, 0.0823529412, 0.5215686275)
    MIDNIGHT_BLUE = HSBK.from_rgb(0.0980392157, 0.0980392157, 0.4392156863)
    MINT_CREAM = HSBK.from_rgb(0.9607843137, 1.0, 0.9803921569)
    MISTY_ROSE = HSBK.from_rgb(1.0, 0.8941176471, 0.8823529412)
    MOCCASIN = HSBK.from_rgb(1.0, 0.8941176471, 0.7098039216)
    NAVAJO_WHITE = HSBK.from_rgb(1.0, 0.8705882353, 0.6784313725)
    NAVY = HSBK.from_rgb(0.0, 0.0, 0.5019607843)
    OLD_LACE = HSBK.from_rgb(0.9921568627, 0.9607843137, 0.9019607843)
    OLIVE = HSBK.from_rgb(0.5019607843, 0.5019607843, 0.0)
    OLIVE_DRAB = HSBK.from_rgb(0.4196078431, 0.5568627451, 0.137254902)
    ORANGE = HSBK.from_rgb(1.0, 0.6470588235, 0.0)
    ORANGE_RED = HSBK.from_rgb(1.0, 0.2705882353, 0.0)
    ORCHID = HSBK.from_rgb(0.8549019608, 0.4392156863, 0.8392156863)
    PALE_GOLDENROD = HSBK.from_rgb(0.9333333333, 0.9098039216, 0.6666666667)
    PALE_GREEN = HSBK.from_rgb(0.5960784314, 0.9843137255, 0.5960784314)
    PALE_TURQUOISE = HSBK.from_rgb(0.6862745098, 0.9333333333, 0.9333333333)
    PALE_VIOLET_RED = HSBK.from_rgb(0.8588235294, 0.4392156863, 0.5764705882)
    PAPAYA_WHIP = HSBK.from_rgb(1.0, 0.937254902, 0.8352941176)
    PEACH_PUFF = HSBK.from_rgb(1.0, 0.8549019608, 0.7254901961)
    PERU = HSBK.from_rgb(0.8039215686, 0.5215686275, 0.2470588235)
    PINK = HSBK.from_rgb(1.0, 0.7529411765, 0.7960784314)
    PLUM = HSBK.from_rgb(0.8666666667, 0.6274509804, 0.8666666667)
    POWDER_BLUE = HSBK.from_rgb(0.6901960784, 0.8784313725, 0.9019607843)
    PURPLE = HSBK.from_rgb(0.5019607843, 0.0, 0.5019607843)
    REBECCA_PURPLE = HSBK.from_rgb(0.4, 0.2, 0.6)
    RED = HSBK.from_rgb(1.0, 0.0, 0.0)
    ROSY_BROWN = HSBK.from_rgb(0.737254902, 0.5607843137, 0.5607843137)
    ROYAL_BLUE = HSBK.from_rgb(0.2549019608, 0.4117647059, 0.8823529412)
    SADDLE_BROWN = HSBK.from_rgb(0.5450980392, 0.2705882353, 0.0745098039)
    SALMON = HSBK.from_rgb(0.9803921569, 0.5019607843, 0.4470588235)
    SANDY_BROWN = HSBK.from_rgb(0.9568627451, 0.6431372549, 0.3764705882)
    SEA_GREEN = HSBK.from_rgb(0.1803921569, 0.5450980392, 0.3411764706)
    SEASHELL = HSBK.from_rgb(1.0, 0.9607843137, 0.9333333333)
    SIENNA = HSBK.from_rgb(0.6274509804, 0.3215686275, 0.1764705882)
    SILVER = HSBK.from_rgb(0.7529411765, 0.7529411765, 0.7529411765)
    SKY_BLUE = HSBK.from_rgb(0.5294117647, 0.8078431373, 0.9215686275)
    SLATE_BLUE = HSBK.from_rgb(0.4156862745, 0.3529411765, 0.8039215686)
    SLATE_GRAY = HSBK.from_rgb(0.4392156863, 0.5019607843, 0.5647058824)
    SLATE_GREY = HSBK.from_rgb(0.4392156863, 0.5019607843, 0.5647058824)
    SNOW = HSBK.from_rgb(1.0, 0.9803921569, 0.9803921569)
    SPRING_GREEN = HSBK.from_rgb(0.0, 1.0, 0.4980392157)
    STEEL_BLUE = HSBK.from_rgb(0.2745098039, 0.5098039216, 0.7058823529)
    TAN = HSBK.from_rgb(0.8235294118, 0.7058823529, 0.5490196078)
    TEAL = HSBK.from_rgb(0.0, 0.5019607843, 0.5019607843)
    THISTLE = HSBK.from_rgb(0.8470588235, 0.7490196078, 0.8470588235)
    TOMATO = HSBK.from_rgb(1.0, 0.3882352941, 0.2784313725)
    TURQUOISE = HSBK.from_rgb(0.2509803922, 0.8784313725, 0.8156862745)
    VIOLET = HSBK.from_rgb(0.9333333333, 0.5098039216, 0.9333333333)
    WHEAT = HSBK.from_rgb(0.9607843137, 0.8705882353, 0.7019607843)
    WHITE = HSBK.from_rgb(1.0, 1.0, 1.0)
    WHITE_SMOKE = HSBK.from_rgb(0.9607843137, 0.9607843137, 0.9607843137)
    YELLOW = HSBK.from_rgb(1.0, 1.0, 0.0)
    YELLOW_GREEN = HSBK.from_rgb(0.6039215686, 0.8039215686, 0.1960784314)

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
