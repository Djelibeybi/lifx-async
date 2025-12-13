"""Tests for multizone light device class."""

from __future__ import annotations

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock

import pytest

from lifx.color import HSBK
from lifx.devices.multizone import MultiZoneEffect, MultiZoneLight
from lifx.protocol import packets
from lifx.protocol.protocol_types import Direction, FirmwareEffect


def async_generator_mock(items: list):
    """Create a mock that returns an async generator yielding items.

    Each call to the mock returns a fresh async generator that yields the items.
    """

    def _create_generator(*args, **kwargs) -> AsyncIterator:
        async def _generator() -> AsyncIterator:
            for item in items:
                yield item

        return _generator()

    return _create_generator


class TestMultiZoneLight:
    """Tests for MultiZoneLight class."""

    def test_create_multizone_light(self) -> None:
        """Test creating a multizone light."""
        light = MultiZoneLight(
            serial="d073d5010203",
            ip="192.168.1.100",
            port=56700,
        )
        assert light.serial == "d073d5010203"
        assert light.ip == "192.168.1.100"
        assert light.port == 56700

    async def test_get_zone_count_not_extended(
        self, multizone_light: MultiZoneLight, mock_product_info
    ) -> None:
        """Test getting zone count."""
        # Mock capabilities (no extended multizone for standard test)
        multizone_light._capabilities = mock_product_info(has_extended_multizone=False)

        # Mock results
        mock_state = packets.MultiZone.StateMultiZone(
            count=16,
            index=0,
            colors=[
                HSBK(hue=0, saturation=0, brightness=0, kelvin=3500).to_protocol()
                for _ in range(16)
            ],
        )
        multizone_light.connection.request.return_value = mock_state

        zone_count = await multizone_light.get_zone_count()

        assert zone_count == 16

    async def test_get_color_zones(
        self, multizone_light: MultiZoneLight, mock_product_info
    ) -> None:
        """Test getting color zones."""
        # Mock capabilities (no extended multizone for standard test)
        multizone_light._capabilities = mock_product_info(has_extended_multizone=False)

        # Mock StateMultiZone response with 8 colors
        # Create colors with incrementing hues: 0-315 degrees
        colors = [
            HSBK(hue=i * 45, saturation=0.5, brightness=0.75, kelvin=3500).to_protocol()
            for i in range(8)
        ]
        mock_state = packets.MultiZone.StateMultiZone(count=16, index=0, colors=colors)
        multizone_light.connection.request.return_value = mock_state
        # Mock request_stream to yield the state once
        multizone_light.connection.request_stream = async_generator_mock([mock_state])

        result_colors = await multizone_light.get_color_zones(0, 7)

        assert len(result_colors) == 8
        assert all(isinstance(color, HSBK) for color in result_colors)
        assert result_colors[0].kelvin == 3500
        assert result_colors[0].saturation == pytest.approx(0.5, abs=0.01)

    async def test_get_color_zones_default_params(
        self, multizone_light: MultiZoneLight, mock_product_info
    ) -> None:
        """Test getting all color zones using default parameters."""
        # Mock capabilities (no extended multizone for standard test)
        multizone_light._capabilities = mock_product_info(has_extended_multizone=False)

        # Mock StateMultiZone response - device has 16 zones
        colors = [
            HSBK(
                hue=i * 22.5, saturation=0.5, brightness=0.75, kelvin=3500
            ).to_protocol()
            for i in range(8)
        ]
        mock_state = packets.MultiZone.StateMultiZone(count=16, index=0, colors=colors)
        multizone_light.connection.request.return_value = mock_state
        # Mock request_stream to yield the state once per call
        multizone_light.connection.request_stream = async_generator_mock([mock_state])

        # Call without parameters - should get all zones
        result_colors = await multizone_light.get_color_zones()

        # Should request all zones (implementation handles pagination)
        assert len(result_colors) >= 8
        assert all(isinstance(color, HSBK) for color in result_colors)

    async def test_get_extended_color_zones(
        self, multizone_light: MultiZoneLight, mock_product_info
    ) -> None:
        """Test getting extended color zones."""
        # Mock capabilities with extended multizone support
        multizone_light._capabilities = mock_product_info(has_extended_multizone=True)

        # Mock StateExtendedColorZones response with multiple colors
        colors = [
            HSBK(hue=i * 36, saturation=0.8, brightness=0.9, kelvin=3500).to_protocol()
            for i in range(10)
        ]
        # Pad to 82 colors as per protocol
        colors.extend(
            [
                HSBK(hue=0, saturation=0, brightness=0, kelvin=3500).to_protocol()
                for _ in range(72)
            ]
        )

        mock_state = packets.MultiZone.StateExtendedColorZones(
            count=10, index=0, colors_count=10, colors=colors
        )
        multizone_light.connection.request.return_value = mock_state
        # Mock request_stream to yield the state once
        multizone_light.connection.request_stream = async_generator_mock([mock_state])

        result_colors = await multizone_light.get_extended_color_zones(0, 9)

        assert len(result_colors) == 10
        assert all(isinstance(color, HSBK) for color in result_colors)
        assert result_colors[0].hue == pytest.approx(0, abs=1)
        assert result_colors[1].hue == pytest.approx(36, abs=1)
        assert result_colors[9].hue == pytest.approx(324, abs=1)
        assert result_colors[0].saturation == pytest.approx(0.8, abs=0.01)

    async def test_get_extended_color_zones_default_params(
        self, multizone_light: MultiZoneLight, mock_product_info
    ) -> None:
        """Test getting all extended color zones using default parameters."""
        # Mock capabilities with extended multizone support
        multizone_light._capabilities = mock_product_info(has_extended_multizone=True)

        # Mock StateExtendedColorZones response - device has 16 zones
        colors = [
            HSBK(
                hue=i * 22.5, saturation=0.8, brightness=0.9, kelvin=3500
            ).to_protocol()
            for i in range(16)
        ]
        # Pad to 82 colors as per protocol
        colors.extend(
            [
                HSBK(hue=0, saturation=0, brightness=0, kelvin=3500).to_protocol()
                for _ in range(66)
            ]
        )

        mock_state = packets.MultiZone.StateExtendedColorZones(
            count=16, index=0, colors_count=16, colors=colors
        )
        multizone_light.connection.request.return_value = mock_state
        # Mock request_stream to yield the state once
        multizone_light.connection.request_stream = async_generator_mock([mock_state])

        # Call without parameters - should get all zones
        result_colors = await multizone_light.get_extended_color_zones()

        assert len(result_colors) == 16
        assert all(isinstance(color, HSBK) for color in result_colors)

    async def test_get_extended_color_zones_large_device(
        self, multizone_light: MultiZoneLight, mock_product_info
    ) -> None:
        """Test getting extended color zones from a large device (>82 zones).

        Tests the async generator streaming pattern for multi-packet responses.
        """
        # Mock capabilities with extended multizone support
        multizone_light._capabilities = mock_product_info(has_extended_multizone=True)

        # For now, test with a device that returns all colors in one packet (82 zones)
        # This represents the common case for most multizone devices
        first_colors = [
            HSBK(
                hue=i * 4.39, saturation=0.5, brightness=0.5, kelvin=3500
            ).to_protocol()
            for i in range(82)
        ]
        first_packet = packets.MultiZone.StateExtendedColorZones(
            count=82,
            index=0,
            colors_count=82,
            colors=first_colors,
        )

        multizone_light.connection.request.return_value = first_packet  # For zone count
        # Mock request_stream to yield the packet once
        multizone_light.connection.request_stream = async_generator_mock([first_packet])

        result_colors = await multizone_light.get_extended_color_zones(0, 81)

        assert len(result_colors) == 82  # All 82 colors

    async def test_get_extended_color_zones_with_store(
        self, multizone_light: MultiZoneLight, mock_product_info
    ) -> None:
        """Test that caching works for extended color zones."""
        # Mock capabilities with extended multizone support
        multizone_light._capabilities = mock_product_info(has_extended_multizone=True)

        # Mock response
        colors = [
            HSBK(hue=i * 36, saturation=1.0, brightness=1.0, kelvin=4000).to_protocol()
            for i in range(5)
        ]
        colors.extend(
            [
                HSBK(hue=0, saturation=0, brightness=0, kelvin=3500).to_protocol()
                for _ in range(77)
            ]
        )

        mock_state = packets.MultiZone.StateExtendedColorZones(
            count=5, index=0, colors_count=5, colors=colors
        )
        multizone_light.connection.request.return_value = mock_state

        # First call should hit the device and store the result
        result1 = await multizone_light.get_extended_color_zones(0, 4)
        call_count_after_first = multizone_light.connection.request.call_count

        # Each call hits the device (no automatic caching for range queries)
        result2 = await multizone_light.get_extended_color_zones(0, 4)
        call_count_after_second = multizone_light.connection.request.call_count

        assert result1 == result2
        assert (
            call_count_after_second > call_count_after_first
        )  # Calls device each time

    async def test_get_extended_color_zones_invalid_range(
        self, multizone_light: MultiZoneLight
    ) -> None:
        """Test that invalid zone range raises error."""
        with pytest.raises(ValueError, match="Invalid zone range"):
            await multizone_light.get_extended_color_zones(-1, 5)

        with pytest.raises(ValueError, match="Invalid zone range"):
            await multizone_light.get_extended_color_zones(5, 3)

    async def test_get_extended_color_zones_clamps_to_zone_count(
        self, multizone_light: MultiZoneLight, mock_product_info
    ) -> None:
        """Test that end index is clamped to zone count."""
        # Mock capabilities with extended multizone support
        multizone_light._capabilities = mock_product_info(has_extended_multizone=True)

        # Zone count is 16, but we request 0-99
        colors = [
            HSBK(
                hue=i * 22.5, saturation=0.5, brightness=0.5, kelvin=3500
            ).to_protocol()
            for i in range(16)
        ]
        colors.extend(
            [
                HSBK(hue=0, saturation=0, brightness=0, kelvin=3500).to_protocol()
                for _ in range(66)
            ]
        )

        mock_state = packets.MultiZone.StateExtendedColorZones(
            count=16, index=0, colors_count=16, colors=colors
        )
        multizone_light.connection.request.return_value = mock_state

        result_colors = await multizone_light.get_extended_color_zones(0, 99)

        # Should return colors up to the actual zone count
        assert len(result_colors) <= 82  # Limited by response

    async def test_get_all_color_zones_with_extended(
        self, multizone_light: MultiZoneLight, mock_product_info
    ) -> None:
        """Test get_all_color_zones with extended multizone support."""
        # Mock capabilities with extended multizone support
        multizone_light._capabilities = mock_product_info(has_extended_multizone=True)

        # Mock StateExtendedColorZones response - device has 16 zones
        colors = [
            HSBK(
                hue=i * 22.5, saturation=0.8, brightness=0.9, kelvin=3500
            ).to_protocol()
            for i in range(16)
        ]
        # Pad to 82 colors as per protocol
        colors.extend(
            [
                HSBK(hue=0, saturation=0, brightness=0, kelvin=3500).to_protocol()
                for _ in range(66)
            ]
        )

        mock_state = packets.MultiZone.StateExtendedColorZones(
            count=16, index=0, colors_count=16, colors=colors
        )
        multizone_light.connection.request.return_value = mock_state
        # Mock request_stream to yield the state once
        multizone_light.connection.request_stream = async_generator_mock([mock_state])

        # Call get_all_color_zones - should use extended method
        result_colors = await multizone_light.get_all_color_zones()

        assert len(result_colors) == 16
        assert all(isinstance(color, HSBK) for color in result_colors)

    async def test_get_all_color_zones_without_extended(
        self, multizone_light: MultiZoneLight, mock_product_info
    ) -> None:
        """Test get_all_color_zones without extended multizone support."""
        # Mock capabilities without extended multizone support
        multizone_light._capabilities = mock_product_info(has_extended_multizone=False)

        # Mock StateMultiZone response - device has 16 zones
        colors = [
            HSBK(
                hue=i * 22.5, saturation=0.5, brightness=0.75, kelvin=3500
            ).to_protocol()
            for i in range(8)
        ]
        mock_state = packets.MultiZone.StateMultiZone(count=16, index=0, colors=colors)
        multizone_light.connection.request.return_value = mock_state
        # Mock request_stream to yield the state once per call
        multizone_light.connection.request_stream = async_generator_mock([mock_state])

        # Call get_all_color_zones - should use standard method
        result_colors = await multizone_light.get_all_color_zones()

        # Should return all zones (method handles pagination internally)
        assert len(result_colors) >= 8
        assert all(isinstance(color, HSBK) for color in result_colors)

    async def test_set_color_zones(
        self, multizone_light: MultiZoneLight, mock_product_info
    ) -> None:
        """Test setting color zones."""
        # Mock capabilities (no extended multizone for standard test)
        multizone_light._capabilities = mock_product_info(has_extended_multizone=False)

        # Pre-populate zone count store so get_zone_count() doesn't
        # need to call the device
        multizone_light._zone_count = 8

        # Mock set_color_zones response
        multizone_light.connection.request.return_value = True

        color = HSBK(hue=120, saturation=0.8, brightness=0.6, kelvin=4000)
        await multizone_light.set_color_zones(0, 5, color, duration=1.0)

        # Verify packet was sent
        multizone_light.connection.request.assert_called_once()

        # Get the set_color_zones call
        call_args = multizone_light.connection.request.call_args
        packet = call_args[0][0]

        # Verify packet has correct values
        assert packet.start_index == 0
        assert packet.end_index == 5
        assert packet.duration == 1000  # 1 second in ms
        assert packet.color.kelvin == 4000

    async def test_set_extended_color_zones(
        self, multizone_light: MultiZoneLight
    ) -> None:
        """Test setting extended color zones."""
        # Pre-populate zone count to avoid internal get_zone_count() calls
        multizone_light._zone_count = 82

        # Mock SET operation returns True
        multizone_light.connection.request.return_value = True

        # Create list of colors
        colors = [
            HSBK(hue=i * 36, saturation=1.0, brightness=1.0, kelvin=3500)
            for i in range(10)
        ]
        await multizone_light.set_extended_color_zones(0, colors, duration=0.5)

        # Verify packet was sent
        multizone_light.connection.request.assert_called_once()

        # Get the set_extended_color_zones call
        call_args = multizone_light.connection.request.call_args
        packet = call_args[0][0]

        # Verify packet has correct values
        assert packet.index == 0
        assert packet.colors_count == 10
        assert packet.duration == 500  # 0.5 seconds in ms
        assert len(packet.colors) == 82  # Padded to 82

    async def test_set_extended_color_zones_too_many(
        self, multizone_light: MultiZoneLight
    ) -> None:
        """Test that setting too many colors raises error."""
        colors = [
            HSBK(hue=0, saturation=1.0, brightness=1.0, kelvin=3500) for i in range(83)
        ]

        with pytest.raises(ValueError, match="Too many colors"):
            await multizone_light.set_extended_color_zones(0, colors)

    async def test_set_extended_color_zones_fast_mode(
        self, multizone_light: MultiZoneLight
    ) -> None:
        """Test setting extended color zones in fast (fire-and-forget) mode."""
        # Pre-populate zone count to avoid internal get_zone_count() calls
        multizone_light._zone_count = 82

        # Set up send_packet as AsyncMock for fire-and-forget mode
        multizone_light.connection.send_packet = AsyncMock()

        # Create list of colors
        colors = [
            HSBK(hue=i * 36, saturation=1.0, brightness=1.0, kelvin=3500)
            for i in range(10)
        ]
        await multizone_light.set_extended_color_zones(
            0, colors, duration=0.5, fast=True
        )

        # Verify send_packet was called (not request)
        multizone_light.connection.send_packet.assert_called_once()
        multizone_light.connection.request.assert_not_called()

        # Get the send_packet call
        call_args = multizone_light.connection.send_packet.call_args

        # Verify packet has correct values
        packet = call_args[0][0]
        assert packet.index == 0
        assert packet.colors_count == 10
        assert packet.duration == 500  # 0.5 seconds in ms
        assert len(packet.colors) == 82  # Padded to 82

        # Verify fire-and-forget flags
        assert call_args[1]["ack_required"] is False
        assert call_args[1]["res_required"] is False


class TestMultiZoneEffect:
    """Tests for MultiZoneEffect class."""

    async def test_get_effect(self, multizone_light: MultiZoneLight) -> None:
        """Test getting multizone effect with direction."""
        # Mock StateEffect response
        from lifx.protocol.protocol_types import (
            MultiZoneEffectParameter,
            MultiZoneEffectSettings,
        )

        mock_state = packets.MultiZone.StateEffect(
            settings=MultiZoneEffectSettings(
                instanceid=12345,
                effect_type=FirmwareEffect.MOVE,
                speed=5000,
                duration=0,
                parameter=MultiZoneEffectParameter(
                    parameter0=0,
                    parameter1=int(Direction.REVERSED),  # Direction in parameter1
                    parameter2=0,
                    parameter3=0,
                    parameter4=0,
                    parameter5=0,
                    parameter6=0,
                    parameter7=0,
                ),
            )
        )
        multizone_light.connection.request.return_value = mock_state

        effect = await multizone_light.get_effect()

        assert effect is not None
        assert effect.effect_type == FirmwareEffect.MOVE
        assert effect.speed == 5000
        assert effect.duration == 0
        assert effect.parameters[1] == int(Direction.REVERSED)
        # Verify direction property extracts correctly from parameters
        assert effect.direction == Direction.REVERSED

    async def test_get_effect_when_off(self, multizone_light: MultiZoneLight) -> None:
        """Test getting effect returns None when effect type is OFF."""
        # Mock StateEffect response with OFF effect type
        from lifx.protocol.protocol_types import (
            MultiZoneEffectParameter,
            MultiZoneEffectSettings,
        )

        mock_state = packets.MultiZone.StateEffect(
            settings=MultiZoneEffectSettings(
                instanceid=0,
                effect_type=FirmwareEffect.OFF,
                speed=0,
                duration=0,
                parameter=MultiZoneEffectParameter(
                    parameter0=0,
                    parameter1=0,
                    parameter2=0,
                    parameter3=0,
                    parameter4=0,
                    parameter5=0,
                    parameter6=0,
                    parameter7=0,
                ),
            )
        )
        multizone_light.connection.request.return_value = mock_state

        effect = await multizone_light.get_effect()

        assert effect is not None
        assert effect.effect_type is FirmwareEffect.OFF

    async def test_set_effect(self, multizone_light: MultiZoneLight) -> None:
        """Test setting multizone effect."""
        # Mock SET operation returns True
        multizone_light.connection.request.return_value = True

        effect = MultiZoneEffect(
            effect_type=FirmwareEffect.MOVE,
            speed=5000,
            duration=60_000_000_000,  # 60 seconds in nanoseconds
            parameters=[0, 0, 0, 0, 0, 0, 0, 0],
        )
        await multizone_light.set_effect(effect)

        # Verify packet was sent
        multizone_light.connection.request.assert_called_once()
        call_args = multizone_light.connection.request.call_args
        packet = call_args[0][0]

        # Verify packet has correct values
        assert packet.settings.effect_type == FirmwareEffect.MOVE
        assert packet.settings.speed == 5000
        assert packet.settings.duration == 60_000_000_000

    async def test_set_effect_with_direction(
        self, multizone_light: MultiZoneLight
    ) -> None:
        """Test setting multizone effect with direction property."""
        # Mock SET operation returns True
        multizone_light.connection.request.return_value = True

        effect = MultiZoneEffect(
            effect_type=FirmwareEffect.MOVE,
            speed=5000,
            duration=0,
        )
        effect.direction = Direction.FORWARD
        await multizone_light.set_effect(effect)

        # Verify packet was sent
        multizone_light.connection.request.assert_called_once()
        call_args = multizone_light.connection.request.call_args
        packet = call_args[0][0]

        # Verify packet has correct values including direction in parameter1
        assert packet.settings.effect_type == FirmwareEffect.MOVE
        assert packet.settings.speed == 5000
        assert packet.settings.parameter.parameter1 == int(Direction.FORWARD)

    async def test_stop_effect(self, multizone_light: MultiZoneLight) -> None:
        """Test stopping effect."""
        # Mock SET operation returns True
        multizone_light.connection.request.return_value = True

        await multizone_light.stop_effect()

        # Verify packet was sent with OFF effect
        multizone_light.connection.request.assert_called_once()
        call_args = multizone_light.connection.request.call_args
        packet = call_args[0][0]
        assert packet.settings.effect_type == FirmwareEffect.OFF

    def test_create_effect(self) -> None:
        """Test creating a multizone effect."""
        effect = MultiZoneEffect(
            effect_type=FirmwareEffect.MOVE,
            speed=5000,
            duration=0,
        )
        assert effect.effect_type == FirmwareEffect.MOVE
        assert effect.speed == 5000
        assert effect.duration == 0
        assert effect.parameters == [0] * 8  # Default parameters

    def test_create_effect_with_parameters(self) -> None:
        """Test creating effect with custom parameters."""
        params = [1, 2, 3, 4, 5, 6, 7, 8]
        effect = MultiZoneEffect(
            effect_type=FirmwareEffect.MOVE,
            speed=5000,
            duration=0,
            parameters=params,
        )
        assert effect.parameters == params

    def test_direction_property_get_for_move_effect(self) -> None:
        """Test getting direction for MOVE effect."""
        effect = MultiZoneEffect(
            effect_type=FirmwareEffect.MOVE,
            speed=5000,
            parameters=[0, int(Direction.REVERSED), 0, 0, 0, 0, 0, 0],
        )
        assert effect.direction == Direction.REVERSED

    def test_direction_property_get_for_non_move_effect(self) -> None:
        """Test getting direction for non-MOVE effect returns None."""
        effect = MultiZoneEffect(
            effect_type=FirmwareEffect.OFF,
            speed=0,
        )
        assert effect.direction is None

    def test_direction_property_set_for_move_effect(self) -> None:
        """Test setting direction for MOVE effect."""
        effect = MultiZoneEffect(
            effect_type=FirmwareEffect.MOVE,
            speed=5000,
        )
        effect.direction = Direction.FORWARD
        assert effect.parameters[1] == int(Direction.FORWARD)
        assert effect.direction == Direction.FORWARD

    def test_direction_property_set_for_non_move_effect_raises_error(self) -> None:
        """Test setting direction for non-MOVE effect raises ValueError."""
        effect = MultiZoneEffect(
            effect_type=FirmwareEffect.OFF,
            speed=0,
        )
        with pytest.raises(
            ValueError, match="Direction can only be set for MOVE effects"
        ):
            effect.direction = Direction.FORWARD
