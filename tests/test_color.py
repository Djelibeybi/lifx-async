"""Tests for color utilities."""

from __future__ import annotations

import pytest

from lifx.color import HSBK, Colors
from lifx.const import KELVIN_COOL, KELVIN_DAYLIGHT, KELVIN_NEUTRAL, KELVIN_WARM
from lifx.protocol.protocol_types import LightHsbk


class TestHSBK:
    """Tests for HSBK color class."""

    def test_create_hsbk(self) -> None:
        """Test creating HSBK color."""
        color = HSBK(hue=180, saturation=0.5, brightness=0.75, kelvin=3500)
        assert color.hue == 180
        assert color.saturation == 0.5
        assert color.brightness == 0.75
        assert color.kelvin == 3500
        assert repr(color) == (
            f"HSBK(hue={color.hue}, saturation={color.saturation:.2f}, "
            f"brightness={color.brightness:.2f}, kelvin={color.kelvin})"
        )

    def test_validate_hue_range(self) -> None:
        """Test hue validation."""
        with pytest.raises(ValueError, match="Hue must be"):
            HSBK(hue=-10, saturation=0.5, brightness=0.5, kelvin=3500)

        with pytest.raises(ValueError, match="Hue must be"):
            HSBK(hue=400, saturation=0.5, brightness=0.5, kelvin=3500)

    def test_validate_saturation_range(self) -> None:
        """Test saturation validation."""
        with pytest.raises(ValueError, match="Saturation must be"):
            HSBK(hue=180, saturation=-0.1, brightness=0.5, kelvin=3500)

        with pytest.raises(ValueError, match="Saturation must be"):
            HSBK(hue=180, saturation=1.5, brightness=0.5, kelvin=3500)

    def test_validate_brightness_range(self) -> None:
        """Test brightness validation."""
        with pytest.raises(ValueError, match="Brightness must be"):
            HSBK(hue=180, saturation=0.5, brightness=-0.1, kelvin=3500)

        with pytest.raises(ValueError, match="Brightness must be"):
            HSBK(hue=180, saturation=0.5, brightness=1.5, kelvin=3500)

    def test_validate_kelvin_range(self) -> None:
        """Test kelvin validation."""
        with pytest.raises(ValueError, match="Kelvin must be"):
            HSBK(hue=180, saturation=0.5, brightness=0.5, kelvin=1000)

        with pytest.raises(ValueError, match="Kelvin must be"):
            HSBK(hue=180, saturation=0.5, brightness=0.5, kelvin=10000)

    def test_from_rgb_red(self) -> None:
        """Test RGB to HSBK conversion for red."""
        color = HSBK.from_rgb(255, 0, 0)
        assert color.hue == pytest.approx(0, abs=1)
        assert color.saturation == pytest.approx(1.0, abs=0.01)
        assert color.brightness == pytest.approx(1.0, abs=0.01)
        assert color.kelvin == KELVIN_NEUTRAL

    def test_from_rgb_green(self) -> None:
        """Test RGB to HSBK conversion for green."""
        color = HSBK.from_rgb(0, 255, 0)
        assert color.hue == pytest.approx(120, abs=1)
        assert color.saturation == pytest.approx(1.0, abs=0.01)
        assert color.brightness == pytest.approx(1.0, abs=0.01)

    def test_from_rgb_blue(self) -> None:
        """Test RGB to HSBK conversion for blue."""
        color = HSBK.from_rgb(0, 0, 255)
        assert color.hue == pytest.approx(240, abs=1)
        assert color.saturation == pytest.approx(1.0, abs=0.01)
        assert color.brightness == pytest.approx(1.0, abs=0.01)

    def test_from_rgb_white(self) -> None:
        """Test RGB to HSBK conversion for white."""
        color = HSBK.from_rgb(255, 255, 255)
        assert color.saturation == pytest.approx(0.0, abs=0.01)
        assert color.brightness == pytest.approx(1.0, abs=0.01)

    def test_from_rgb_black(self) -> None:
        """Test RGB to HSBK conversion for black."""
        color = HSBK.from_rgb(0, 0, 0)
        assert color.saturation == pytest.approx(0.0, abs=0.01)
        assert color.brightness == pytest.approx(0.0, abs=0.01)

    def test_from_rgb_invalid_values(self) -> None:
        """Test RGB validation."""
        with pytest.raises(ValueError, match="Red must be between"):
            HSBK.from_rgb(-1, 0, 0)

        with pytest.raises(ValueError, match="Green must be between"):
            HSBK.from_rgb(0, 256, 0)

        with pytest.raises(ValueError, match="Blue must be between"):
            HSBK.from_rgb(0, 0, 300)

    def test_to_rgb_red(self) -> None:
        """Test HSBK to RGB conversion for red."""
        color = HSBK(hue=0, saturation=1.0, brightness=1.0, kelvin=3500)
        r, g, b = color.to_rgb()
        assert r == 255
        assert g == 0
        assert b == 0

    def test_to_rgb_green(self) -> None:
        """Test HSBK to RGB conversion for green."""
        color = HSBK(hue=120, saturation=1.0, brightness=1.0, kelvin=3500)
        r, g, b = color.to_rgb()
        assert r == 0
        assert g == 255
        assert b == 0

    def test_to_rgb_blue(self) -> None:
        """Test HSBK to RGB conversion for blue."""
        color = HSBK(hue=240, saturation=1.0, brightness=1.0, kelvin=3500)
        r, g, b = color.to_rgb()
        assert r == 0
        assert g == 0
        assert b == 255

    def test_to_rgb_white(self) -> None:
        """Test HSBK to RGB conversion for white."""
        color = HSBK(hue=0, saturation=0.0, brightness=1.0, kelvin=3500)
        r, g, b = color.to_rgb()
        assert r == 255
        assert g == 255
        assert b == 255

    def test_to_rgb_black(self) -> None:
        """Test HSBK to RGB conversion for black."""
        color = HSBK(hue=0, saturation=0.0, brightness=0.0, kelvin=3500)
        r, g, b = color.to_rgb()
        assert r == 0
        assert g == 0
        assert b == 0

    def test_rgb_roundtrip(self) -> None:
        """Test RGB -> HSBK -> RGB roundtrip."""
        original = (255, 128, 64)
        color = HSBK.from_rgb(*original)
        result = color.to_rgb()

        # Allow small differences due to floating point
        assert result[0] == pytest.approx(original[0], abs=2)
        assert result[1] == pytest.approx(original[1], abs=2)
        assert result[2] == pytest.approx(original[2], abs=2)

    def test_to_protocol(self) -> None:
        """Test conversion to protocol HSBK."""
        color = HSBK(hue=180, saturation=0.5, brightness=0.75, kelvin=3500)
        protocol = color.to_protocol()

        assert isinstance(protocol, LightHsbk)
        # Hue: 180/360 * 65535 = 32767.5
        assert protocol.hue == pytest.approx(32768, abs=1)
        # Saturation: 0.5 * 65535 = 32767.5
        assert protocol.saturation == pytest.approx(32768, abs=1)
        # Brightness: 0.75 * 65535 = 49151.25
        assert protocol.brightness == pytest.approx(49151, abs=1)
        assert protocol.kelvin == 3500

    def test_from_protocol(self) -> None:
        """Test conversion from protocol HSBK."""
        protocol = LightHsbk(hue=32768, saturation=32768, brightness=49151, kelvin=3500)
        color = HSBK.from_protocol(protocol)

        assert color.hue == pytest.approx(180, abs=1)
        assert color.saturation == pytest.approx(0.5, abs=0.01)
        assert color.brightness == pytest.approx(0.75, abs=0.01)
        assert color.kelvin == 3500

    def test_protocol_roundtrip(self) -> None:
        """Test HSBK -> Protocol -> HSBK roundtrip."""
        original = HSBK(hue=120, saturation=0.8, brightness=0.6, kelvin=4000)
        protocol = original.to_protocol()
        result = HSBK.from_protocol(protocol)

        assert result.hue == pytest.approx(original.hue, abs=1)
        assert result.saturation == pytest.approx(original.saturation, abs=0.01)
        assert result.brightness == pytest.approx(original.brightness, abs=0.01)
        assert result.kelvin == original.kelvin

    def test_with_hue(self) -> None:
        """Test creating color with modified hue."""
        original = HSBK(hue=0, saturation=0.5, brightness=0.75, kelvin=3500)
        modified = original.with_hue(180)

        assert modified.hue == 180
        assert modified.saturation == 0.5
        assert modified.brightness == 0.75
        assert modified.kelvin == 3500
        # Original unchanged
        assert original.hue == 0

    def test_with_saturation(self) -> None:
        """Test creating color with modified saturation."""
        original = HSBK(hue=180, saturation=0.5, brightness=0.75, kelvin=3500)
        modified = original.with_saturation(1.0)

        assert modified.hue == 180
        assert modified.saturation == 1.0
        assert modified.brightness == 0.75
        assert modified.kelvin == 3500

    def test_with_brightness(self) -> None:
        """Test creating color with modified brightness."""
        original = HSBK(hue=180, saturation=0.5, brightness=0.75, kelvin=3500)
        modified = original.with_brightness(0.25)

        assert modified.hue == 180
        assert modified.saturation == 0.5
        assert modified.brightness == 0.25
        assert modified.kelvin == 3500

    def test_with_kelvin(self) -> None:
        """Test creating color with modified kelvin."""
        original = HSBK(hue=180, saturation=0.5, brightness=0.75, kelvin=3500)
        modified = original.with_kelvin(6500)

        assert modified.hue == 180
        assert modified.saturation == 0.5
        assert modified.brightness == 0.75
        assert modified.kelvin == 6500


class TestColors:
    """Tests for Colors presets."""

    def test_primary_colors(self) -> None:
        """Test primary color presets."""
        assert Colors.RED.hue == 0
        assert Colors.GREEN.hue == 120
        assert Colors.BLUE.hue == 240
        assert Colors.RED.saturation == 1.0
        assert Colors.RED.brightness == 1.0

    def test_white_variants(self) -> None:
        """Test white color presets."""
        assert Colors.WHITE_WARM.saturation == 0.0
        assert Colors.WHITE_WARM.kelvin == KELVIN_WARM
        assert Colors.WHITE_COOL.kelvin == KELVIN_COOL
        assert Colors.WHITE_DAYLIGHT.kelvin == KELVIN_DAYLIGHT

    def test_pastel_colors(self) -> None:
        """Test pastel color presets."""
        assert Colors.PASTEL_RED.hue == 0
        assert Colors.PASTEL_RED.saturation == 0.3
        assert Colors.PASTEL_GREEN.hue == 120
        assert Colors.PASTEL_BLUE.hue == 240


class TestHSBKThemeMethods:
    """Tests for theme-specific HSBK methods."""

    def test_clone(self) -> None:
        """Test cloning a color."""
        original = HSBK(hue=180, saturation=0.5, brightness=0.75, kelvin=3500)
        cloned = original.clone()

        # Values should be the same
        assert cloned.hue == original.hue
        assert cloned.saturation == original.saturation
        assert cloned.brightness == original.brightness
        assert cloned.kelvin == original.kelvin

        # Should be different objects
        assert cloned is not original

    def test_as_tuple(self) -> None:
        """Test converting color to protocol tuple."""
        color = HSBK(hue=180, saturation=0.5, brightness=0.75, kelvin=3500)
        hue_u16, sat_u16, bri_u16, kelvin = color.as_tuple()

        # Should return protocol uint16 values
        assert isinstance(hue_u16, int)
        assert isinstance(sat_u16, int)
        assert isinstance(bri_u16, int)
        assert isinstance(kelvin, int)

        # Values should be in valid ranges
        assert 0 <= hue_u16 <= 65535
        assert 0 <= sat_u16 <= 65535
        assert 0 <= bri_u16 <= 65535
        assert 1500 <= kelvin <= 9000

        # Verify approximate values
        assert hue_u16 == pytest.approx(32768, abs=1)  # 180/360 * 65535
        assert sat_u16 == pytest.approx(32768, abs=1)  # 0.5 * 65535
        assert bri_u16 == pytest.approx(49151, abs=1)  # 0.75 * 65535

    def test_as_dict(self) -> None:
        """Test converting color to dictionary."""
        color = HSBK(hue=180, saturation=0.5, brightness=0.75, kelvin=3500)
        color_dict = color.as_dict()

        assert isinstance(color_dict, dict)
        assert color_dict["hue"] == 180
        assert color_dict["saturation"] == 0.5
        assert color_dict["brightness"] == 0.75
        assert color_dict["kelvin"] == 3500

    def test_limit_distance_to_no_adjustment_needed(self) -> None:
        """Test limit_distance_to when hue is already within range."""
        color1 = HSBK(hue=100, saturation=1.0, brightness=1.0, kelvin=3500)
        color2 = HSBK(hue=120, saturation=1.0, brightness=1.0, kelvin=3500)

        result = color1.limit_distance_to(color2)
        # Difference is only 20 degrees, so no adjustment needed
        assert result.hue == color1.hue

    def test_limit_distance_to_adjustment_needed(self) -> None:
        """Test limit_distance_to when hue adjustment is needed."""
        red = HSBK(hue=10, saturation=1.0, brightness=1.0, kelvin=3500)
        blue = HSBK(hue=240, saturation=1.0, brightness=1.0, kelvin=3500)

        result = red.limit_distance_to(blue)
        # Hue should be adjusted when difference is > 90 degrees
        # The result should be different from the original
        assert abs(result.hue - red.hue) == 90

    def test_average_single_color(self) -> None:
        """Test averaging a single color."""
        color = HSBK(hue=180, saturation=0.5, brightness=0.75, kelvin=3500)
        avg = HSBK.average([color])

        assert avg.hue == pytest.approx(color.hue, abs=1)
        assert avg.saturation == pytest.approx(color.saturation, abs=0.01)
        assert avg.brightness == pytest.approx(color.brightness, abs=0.01)
        assert avg.kelvin == color.kelvin

    def test_average_two_colors(self) -> None:
        """Test averaging two colors."""
        red = HSBK(hue=0, saturation=1.0, brightness=1.0, kelvin=3500)
        blue = HSBK(hue=240, saturation=1.0, brightness=1.0, kelvin=3500)

        avg = HSBK.average([red, blue])

        # Average saturation and brightness should be simple mean
        assert avg.saturation == pytest.approx(1.0, abs=0.01)
        assert avg.brightness == pytest.approx(1.0, abs=0.01)
        assert avg.kelvin == 3500

        # Hue should use circular mean (average of 0 and 240 should be 300 or 120)
        assert avg.hue == pytest.approx(120, abs=5) or avg.hue == pytest.approx(
            300, abs=5
        )

    def test_average_multiple_colors(self) -> None:
        """Test averaging multiple colors."""
        red = HSBK(hue=0, saturation=1.0, brightness=1.0, kelvin=3500)
        yellow = HSBK(hue=60, saturation=1.0, brightness=1.0, kelvin=3500)
        green = HSBK(hue=120, saturation=1.0, brightness=1.0, kelvin=3500)

        avg = HSBK.average([red, yellow, green])

        # All saturation and brightness should be 1.0
        assert avg.saturation == pytest.approx(1.0, abs=0.01)
        assert avg.brightness == pytest.approx(1.0, abs=0.01)

        # Hue should be somewhere between 0 and 120
        assert 0 <= avg.hue <= 120

    def test_average_wraparound_hues(self) -> None:
        """Test circular mean handles hue wraparound correctly."""
        # Hues close to 0 and 360 should average near 0, not 180
        color1 = HSBK(hue=10, saturation=1.0, brightness=1.0, kelvin=3500)
        color2 = HSBK(hue=350, saturation=1.0, brightness=1.0, kelvin=3500)

        avg = HSBK.average([color1, color2])

        # Average should be close to 0 (or 360), not 180
        assert avg.hue == pytest.approx(0, abs=10) or avg.hue == pytest.approx(
            360, abs=10
        )

    def test_average_empty_list(self) -> None:
        """Test averaging empty list raises error."""
        with pytest.raises(ValueError, match="Cannot average an empty list"):
            HSBK.average([])
