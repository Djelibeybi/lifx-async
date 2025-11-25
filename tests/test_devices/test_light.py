"""Tests for light device class."""

from __future__ import annotations

import time

import pytest

from lifx.color import HSBK
from lifx.devices.light import Light
from lifx.protocol import packets
from lifx.protocol.protocol_types import LightWaveform


class TestLight:
    """Tests for Light class."""

    def test_create_light(self) -> None:
        """Test creating a light."""
        light = Light(
            serial="d073d5010203",
            ip="192.168.1.100",
            port=56700,
        )
        assert light.serial == "d073d5010203"
        assert light.ip == "192.168.1.100"
        assert light.port == 56700

    async def test_get_color(self, light: Light) -> None:
        """Test getting light color."""
        # Mock LightState response with decoded label
        # HSBK: hue=180°, sat=50%, bri=75%, kelvin=3500
        mock_state = packets.Light.StateColor(
            color=HSBK(
                hue=180, saturation=0.5, brightness=0.75, kelvin=3500
            ).to_protocol(),
            power=65535,
            label="Test Light",
        )
        light.connection.request.return_value = mock_state

        color, power, label = await light.get_color()

        assert isinstance(color, HSBK)
        assert color.hue == pytest.approx(180, abs=1)
        assert color.saturation == pytest.approx(0.5, abs=0.01)
        assert color.brightness == pytest.approx(0.75, abs=0.01)
        assert color.kelvin == 3500
        assert power == 65535
        assert label == "Test Light"

    async def test_set_color(self, light: Light) -> None:
        """Test setting light color."""
        # Mock SET operation returns True
        light.connection.request.return_value = True

        color = HSBK(hue=120, saturation=0.8, brightness=0.6, kelvin=4000)
        await light.set_color(color, duration=1.0)

        # Verify packet was sent
        light.connection.request.assert_called_once()
        call_args = light.connection.request.call_args
        packet = call_args[0][0]

        # Verify packet has correct values
        assert packet.duration == 1000  # 1 second in ms
        assert packet.color.kelvin == 4000

    async def test_set_brightness(self, light: Light) -> None:
        """Test setting brightness."""
        # Mock set_waveform_optional response (returns True)
        light.connection.request.return_value = True

        await light.set_brightness(0.25, duration=2.0)

        # Verify set_waveform_optional was called with only brightness set
        light.connection.request.assert_called_once()
        call_args = light.connection.request.call_args
        packet = call_args[0][0]

        # Verify it's a SetWaveformOptional packet
        assert isinstance(packet, packets.Light.SetWaveformOptional)

        # Verify brightness is set correctly
        result_color = HSBK.from_protocol(packet.color)
        assert result_color.brightness == pytest.approx(0.25, abs=0.01)

        # Verify only brightness flag is set
        assert packet.set_brightness is True
        assert packet.set_hue is False
        assert packet.set_saturation is False
        assert packet.set_kelvin is False

        # Verify duration is passed as period
        assert packet.period == 2000  # 2 seconds in ms

    async def test_set_brightness_invalid(self, light: Light) -> None:
        """Test setting invalid brightness."""
        light._color = (
            HSBK(hue=0, saturation=1, brightness=1, kelvin=3500),
            time.time(),
        )

        with pytest.raises(ValueError, match="Brightness must be between"):
            await light.set_brightness(1.5)

    async def test_set_kelvin(self, light: Light) -> None:
        """Test setting color temperature."""
        # Mock set_waveform_optional response (returns True)
        light.connection.request.return_value = True

        await light.set_kelvin(6500, duration=1.0)

        # Verify set_waveform_optional was called with only kelvin set
        light.connection.request.assert_called_once()
        call_args = light.connection.request.call_args
        packet = call_args[0][0]

        # Verify it's a SetWaveformOptional packet
        assert isinstance(packet, packets.Light.SetWaveformOptional)

        # Verify saturation and kelvin are set correctly
        assert packet.color.saturation == 0
        assert packet.color.kelvin == 6500

        # Verify both saturation and kelvin flags are set
        assert packet.set_kelvin is True
        assert packet.set_hue is False
        assert packet.set_saturation is True
        assert packet.set_brightness is False

        # Verify duration is passed as period
        assert packet.period == 1000  # 1 second in ms

    async def test_set_kelvin_invalid(self, light: Light) -> None:
        """Test setting invalid temperature."""
        light._color = (
            HSBK(hue=0, saturation=1, brightness=1, kelvin=3500),
            time.time(),
        )

        with pytest.raises(ValueError, match="Kelvin must be"):
            await light.set_kelvin(10000)

    async def test_set_hue(self, light: Light) -> None:
        """Test setting hue."""
        # Mock set_waveform_optional response (returns True)
        light.connection.request.return_value = True

        await light.set_hue(240)

        # Verify set_waveform_optional was called with only hue set
        light.connection.request.assert_called_once()
        call_args = light.connection.request.call_args
        packet = call_args[0][0]

        # Verify it's a SetWaveformOptional packet
        assert isinstance(packet, packets.Light.SetWaveformOptional)

        # Verify hue is set correctly
        result_color = HSBK.from_protocol(packet.color)
        assert result_color.hue == pytest.approx(240, abs=1)

        # Verify only hue flag is set
        assert packet.set_hue is True
        assert packet.set_saturation is False
        assert packet.set_brightness is False
        assert packet.set_kelvin is False

    async def test_set_saturation(self, light: Light) -> None:
        """Test setting saturation."""
        # Mock set_waveform_optional response (returns True)
        light.connection.request.return_value = True

        await light.set_saturation(1.0)

        # Verify set_waveform_optional was called with only saturation set
        light.connection.request.assert_called_once()
        call_args = light.connection.request.call_args
        packet = call_args[0][0]

        # Verify it's a SetWaveformOptional packet
        assert isinstance(packet, packets.Light.SetWaveformOptional)

        # Verify saturation is set correctly
        result_color = HSBK.from_protocol(packet.color)
        assert result_color.saturation == pytest.approx(1.0, abs=0.01)

        # Verify only saturation flag is set
        assert packet.set_saturation is True
        assert packet.set_hue is False
        assert packet.set_brightness is False
        assert packet.set_kelvin is False

    async def test_get_power(self, light: Light) -> None:
        """Test getting light power state."""
        # Mock response with power on (65535)
        mock_state = packets.Light.StatePower(level=65535)
        light.connection.request.return_value = mock_state

        power = await light.get_power()

        assert power == 65535

    async def test_get_ambient_light_level(self, light: Light) -> None:
        """Test getting ambient light level from sensor."""
        # Mock response with lux reading
        mock_state = packets.Sensor.StateAmbientLight(lux=125.5)
        light.connection.request.return_value = mock_state

        lux = await light.get_ambient_light_level()

        assert lux == 125.5
        light.connection.request.assert_called_once()
        call_args = light.connection.request.call_args
        packet = call_args[0][0]
        assert isinstance(packet, packets.Sensor.GetAmbientLight)

    async def test_get_ambient_light_level_zero(self, light: Light) -> None:
        """Test getting zero ambient light level (dark)."""
        # Mock response with zero lux (dark)
        mock_state = packets.Sensor.StateAmbientLight(lux=0.0)
        light.connection.request.return_value = mock_state

        lux = await light.get_ambient_light_level()

        assert lux == 0.0

    async def test_get_ambient_light_level_high(self, light: Light) -> None:
        """Test getting high ambient light level (bright)."""
        # Mock response with high lux (bright daylight)
        mock_state = packets.Sensor.StateAmbientLight(lux=10000.0)
        light.connection.request.return_value = mock_state

        lux = await light.get_ambient_light_level()

        assert lux == 10000.0

    async def test_set_power(self, light: Light) -> None:
        """Test setting light power."""
        # Mock SET operation returns True
        light.connection.request.return_value = True

        await light.set_power(True, duration=2.0)

        # Verify packet was sent
        light.connection.request.assert_called_once()
        call_args = light.connection.request.call_args
        packet = call_args[0][0]
        assert packet.level == 65535
        assert packet.duration == 2000  # 2 seconds in ms

    async def test_set_waveform(self, light: Light) -> None:
        """Test setting waveform effect."""
        # Mock SET operation returns True
        light.connection.request.return_value = True

        color = HSBK(hue=0, saturation=1.0, brightness=1.0, kelvin=3500)
        await light.set_waveform(
            color=color,
            period=1.0,
            cycles=5,
            waveform=LightWaveform.SINE,
            transient=True,
            skew_ratio=0.5,
        )

        # Verify packet was sent
        light.connection.request.assert_called_once()
        call_args = light.connection.request.call_args
        packet = call_args[0][0]
        assert packet.period == 1000  # 1 second in ms
        assert packet.cycles == 5
        assert packet.transient == 1
        assert packet.waveform == LightWaveform.SINE

    async def test_set_waveform_invalid_period(self, light: Light) -> None:
        """Test setting waveform with invalid period."""
        with pytest.raises(ValueError, match="Period must be positive"):
            await light.set_waveform(
                color=HSBK(hue=0, saturation=1, brightness=1, kelvin=3500),
                period=-1.0,
                cycles=1,
                waveform=LightWaveform.SINE,
            )

    async def test_set_waveform_invalid_cycles(self, light: Light) -> None:
        """Test setting waveform with invalid cycles."""
        with pytest.raises(ValueError, match="Cycles must be 1 or higher"):
            await light.set_waveform(
                color=HSBK(hue=0, saturation=1, brightness=1, kelvin=3500),
                period=1.0,
                cycles=-1,
                waveform=LightWaveform.SINE,
            )

    async def test_set_waveform_optional(self, light: Light) -> None:
        """Test setting waveform with optional component control."""
        # Mock SET operation returns True
        light.connection.request.return_value = True

        color = HSBK(hue=0, saturation=1.0, brightness=1.0, kelvin=3500)
        await light.set_waveform_optional(
            color=color,
            period=1.0,
            cycles=5,
            waveform=LightWaveform.SINE,
            transient=True,
            skew_ratio=0.5,
            set_hue=True,
            set_saturation=True,
            set_brightness=True,
            set_kelvin=True,
        )

        # Verify packet was sent
        light.connection.request.assert_called_once()
        call_args = light.connection.request.call_args
        packet = call_args[0][0]

        assert isinstance(packet, packets.Light.SetWaveformOptional)
        assert packet.period == 1000  # 1 second in ms
        assert packet.cycles == 5
        assert packet.transient is True
        assert packet.waveform == LightWaveform.SINE
        assert packet.set_hue is True
        assert packet.set_saturation is True
        assert packet.set_brightness is True
        assert packet.set_kelvin is True

    async def test_set_waveform_optional_brightness_only(self, light: Light) -> None:
        """Test waveform affecting only brightness."""
        # Mock SET operation returns True
        light.connection.request.return_value = True

        color = HSBK(hue=180, saturation=1.0, brightness=1.0, kelvin=3500)
        await light.set_waveform_optional(
            color=color,
            period=1.0,
            cycles=3,
            waveform=LightWaveform.SINE,
            set_hue=False,
            set_saturation=False,
            set_brightness=True,
            set_kelvin=False,
        )

        # Verify packet was sent with correct flags
        light.connection.request.assert_called_once()
        call_args = light.connection.request.call_args
        packet = call_args[0][0]

        assert packet.set_hue is False
        assert packet.set_saturation is False
        assert packet.set_brightness is True
        assert packet.set_kelvin is False

    async def test_set_waveform_optional_hue_only(self, light: Light) -> None:
        """Test waveform affecting only hue."""
        # Mock SET operation returns True
        light.connection.request.return_value = True

        color = HSBK(hue=180, saturation=1.0, brightness=1.0, kelvin=3500)
        await light.set_waveform_optional(
            color=color,
            period=5.0,
            cycles=0,  # Infinite
            waveform=LightWaveform.SAW,
            set_hue=True,
            set_saturation=False,
            set_brightness=False,
            set_kelvin=False,
        )

        # Verify packet was sent with correct flags
        light.connection.request.assert_called_once()
        call_args = light.connection.request.call_args
        packet = call_args[0][0]

        assert packet.set_hue is True
        assert packet.set_saturation is False
        assert packet.set_brightness is False
        assert packet.set_kelvin is False
        assert packet.waveform == LightWaveform.SAW
        assert packet.cycles == 0

    async def test_set_waveform_optional_invalid_period(self, light: Light) -> None:
        """Test setting waveform_optional with invalid period."""
        with pytest.raises(ValueError, match="Period must be positive"):
            await light.set_waveform_optional(
                color=HSBK(hue=0, saturation=1, brightness=1, kelvin=3500),
                period=-1.0,
                cycles=1,
                waveform=LightWaveform.SINE,
            )

    async def test_set_waveform_optional_invalid_cycles(self, light: Light) -> None:
        """Test setting waveform_optional with invalid cycles."""
        with pytest.raises(ValueError, match="Cycles must be non-negative"):
            await light.set_waveform_optional(
                color=HSBK(hue=0, saturation=1, brightness=1, kelvin=3500),
                period=1.0,
                cycles=-1,
                waveform=LightWaveform.SINE,
            )

    async def test_set_waveform_optional_invalid_skew_ratio(self, light: Light) -> None:
        """Test setting waveform_optional with invalid skew ratio."""
        with pytest.raises(ValueError, match="Skew ratio must be between"):
            await light.set_waveform_optional(
                color=HSBK(hue=0, saturation=1, brightness=1, kelvin=3500),
                period=1.0,
                cycles=1,
                waveform=LightWaveform.SINE,
                skew_ratio=1.5,
            )

    async def test_set_waveform_optional_multiple_components(
        self, light: Light
    ) -> None:
        """Test waveform affecting multiple selected components."""
        # Mock SET operation returns True
        light.connection.request.return_value = True

        color = HSBK(hue=240, saturation=0.8, brightness=0.5, kelvin=4000)
        await light.set_waveform_optional(
            color=color,
            period=2.0,
            cycles=10,
            waveform=LightWaveform.TRIANGLE,
            transient=False,
            skew_ratio=0.3,
            set_hue=True,
            set_saturation=True,
            set_brightness=False,
            set_kelvin=False,
        )

        # Verify packet was sent with correct values
        light.connection.request.assert_called_once()
        call_args = light.connection.request.call_args
        packet = call_args[0][0]

        assert packet.period == 2000  # 2 seconds in ms
        assert packet.cycles == 10
        assert packet.transient is False
        assert packet.waveform == LightWaveform.TRIANGLE
        assert packet.set_hue is True
        assert packet.set_saturation is True
        assert packet.set_brightness is False
        assert packet.set_kelvin is False

    async def test_pulse(self, light: Light) -> None:
        """Test pulse convenience method."""
        color = HSBK(hue=0, saturation=1.0, brightness=1.0, kelvin=3500)
        await light.pulse(color, period=1.0, cycles=3)

        # Verify waveform was set
        light.connection.request.assert_called_once()
        call_args = light.connection.request.call_args
        packet = call_args[0][0]
        assert packet.waveform == LightWaveform.PULSE
        assert packet.cycles == 3

    async def test_breathe(self, light: Light) -> None:
        """Test breathe convenience method."""
        color = HSBK(hue=0, saturation=1.0, brightness=1.0, kelvin=3500)
        await light.breathe(color, period=2.0, cycles=1)

        # Verify waveform was set
        light.connection.request.assert_called_once()
        call_args = light.connection.request.call_args
        packet = call_args[0][0]
        assert packet.waveform == LightWaveform.SINE
        assert packet.cycles == 1
        assert packet.transient is True  # Return to original

    def test_repr(self, light: Light) -> None:
        """Test string representation."""
        repr_str = repr(light)
        assert "Light" in repr_str
        assert "192.168.1.100" in repr_str


class TestLightStateUnhandled:
    """Tests for Light methods raising LifxUnsupportedCommandError on StateUnhandled."""

    @pytest.mark.emulator
    async def test_get_color_raises_on_state_unhandled(self, switch_device) -> None:
        """Test get_color() raises LifxUnsupportedCommandError for unsupported device.

        Switch devices don't support Light commands, so get_color() should
        raise LifxUnsupportedCommandError when the device returns StateUnhandled.
        """
        from lifx.exceptions import LifxUnsupportedCommandError

        # Create a Light instance using the switch connection (without context manager)
        light = Light(
            serial=switch_device.serial,
            ip=switch_device.ip,
            port=switch_device.port,
        )

        # Manually open the connection
        await light.connection.open()

        try:
            # get_color() should raise LifxUnsupportedCommandError
            with pytest.raises(LifxUnsupportedCommandError) as exc_info:
                await light.get_color()

            # Verify the exception message contains the packet type
            assert "packet type" in str(exc_info.value).lower()
        finally:
            await light.connection.close()

    @pytest.mark.emulator
    async def test_set_color_raises_on_state_unhandled(self, switch_device) -> None:
        """Test set_color() raises LifxUnsupportedCommandError for unsupported device.

        Switch devices don't support Light commands, so set_color() should
        raise LifxUnsupportedCommandError when the device returns StateUnhandled.
        """
        from lifx.exceptions import LifxUnsupportedCommandError

        # Create a Light instance using the switch connection (without context manager)
        light = Light(
            serial=switch_device.serial,
            ip=switch_device.ip,
            port=switch_device.port,
        )

        # Manually open the connection
        await light.connection.open()

        try:
            color = HSBK(hue=120, saturation=1.0, brightness=1.0, kelvin=3500)

            # set_color() should raise LifxUnsupportedCommandError
            with pytest.raises(LifxUnsupportedCommandError) as exc_info:
                await light.set_color(color)

            # Verify the exception message indicates unsupported command
            assert "does not support" in str(exc_info.value).lower()
        finally:
            await light.connection.close()
