"""Tests for multizone light device class."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lifx.color import HSBK
from lifx.const import KELVIN_SATURATED
from lifx.devices.base import WifiInfo
from lifx.devices.multizone import MultiZoneEffect, MultiZoneLight, MultiZoneLightState
from lifx.exceptions import LifxTimeoutError
from lifx.protocol import packets
from lifx.protocol.protocol_types import (
    Direction,
    FirmwareEffect,
    LightHsbk,
    MultiZoneApplicationRequest,
)
from lifx.protocol.protocol_types import (
    MultiZoneApplicationRequest as ExtendedAppReq,
)


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
        multizone_light.connection.request.assert_awaited_once()

    async def test_get_zone_count_always_refreshes_stored_count(
        self, multizone_light: MultiZoneLight, mock_product_info
    ) -> None:
        """Each call queries the device and replaces the stored zone count."""
        multizone_light._capabilities = mock_product_info(has_extended_multizone=True)
        first_state = packets.MultiZone.StateMultiZone(
            count=16,
            index=0,
            colors=[HSBK(hue=0, saturation=0, brightness=0, kelvin=3500).to_protocol()],
        )
        updated_state = packets.MultiZone.StateMultiZone(
            count=32,
            index=0,
            colors=[HSBK(hue=0, saturation=0, brightness=0, kelvin=3500).to_protocol()],
        )
        multizone_light.connection.request.side_effect = [first_state, updated_state]

        assert await multizone_light.get_zone_count() == 16
        assert multizone_light.zone_count == 16
        assert await multizone_light.get_zone_count() == 32
        assert multizone_light.zone_count == 32
        assert multizone_light.connection.request.await_count == 2
        for call in multizone_light.connection.request.await_args_list:
            packet = call.args[0]
            assert isinstance(packet, packets.MultiZone.GetColorZones)
            assert packet.start_index == 0
            assert packet.end_index == 0

    async def test_get_color_zones_learns_count_without_count_request(
        self, multizone_light: MultiZoneLight, mock_product_info
    ) -> None:
        """The colour response supplies count without a separate round trip."""
        multizone_light._capabilities = mock_product_info(has_extended_multizone=False)
        colors = [
            HSBK(hue=i * 45, saturation=0.5, brightness=0.75, kelvin=3500).to_protocol()
            for i in range(8)
        ]
        mock_state = packets.MultiZone.StateMultiZone(count=8, index=0, colors=colors)
        multizone_light.connection.request_stream = async_generator_mock([mock_state])

        result = await multizone_light.get_color_zones()

        assert len(result) == 8
        assert multizone_light.zone_count == 8
        multizone_light.connection.request.assert_not_awaited()

    async def test_get_color_zones_accepts_saturated_kelvin(
        self, multizone_light: MultiZoneLight, mock_product_info
    ) -> None:
        """A StateMultiZone carrying kelvin 0 parses instead of raising."""
        multizone_light._capabilities = mock_product_info(has_extended_multizone=False)
        mock_state = packets.MultiZone.StateMultiZone(
            count=8,
            index=0,
            colors=[
                LightHsbk(hue=0, saturation=65535, brightness=65535, kelvin=0)
                for _ in range(8)
            ],
        )
        multizone_light.connection.request_stream = async_generator_mock([mock_state])

        result = await multizone_light.get_color_zones()

        assert len(result) == 8
        assert all(zone.kelvin == KELVIN_SATURATED for zone in result)
        assert result[0].replace(brightness=0.5).to_protocol().kelvin == (
            KELVIN_SATURATED
        )

    async def test_get_extended_color_zones_accepts_saturated_kelvin(
        self, multizone_light: MultiZoneLight, mock_product_info
    ) -> None:
        """A StateExtendedColorZones carrying kelvin 0 parses instead of raising."""
        multizone_light._capabilities = mock_product_info(has_extended_multizone=True)
        mock_state = packets.MultiZone.StateExtendedColorZones(
            count=16,
            index=0,
            colors_count=16,
            colors=[
                LightHsbk(hue=0, saturation=65535, brightness=65535, kelvin=0)
                for _ in range(16)
            ],
        )
        multizone_light.connection.request_stream = async_generator_mock([mock_state])

        result = await multizone_light.get_color_zones()

        assert len(result) == 16
        assert all(zone.kelvin == KELVIN_SATURATED for zone in result)

    async def test_zone_debug_payload_is_lazy_when_debug_disabled(
        self, multizone_light: MultiZoneLight, mock_product_info
    ) -> None:
        """Per-zone debug fields must not be read unless DEBUG is enabled."""
        multizone_light._capabilities = mock_product_info(has_extended_multizone=False)
        protocol_color = HSBK(
            hue=0, saturation=0.5, brightness=0.75, kelvin=3500
        ).to_protocol()
        mock_state = packets.MultiZone.StateMultiZone(
            count=1, index=0, colors=[protocol_color]
        )
        multizone_light.connection.request_stream = async_generator_mock([mock_state])

        class LazyColor:
            @property
            def hue(self) -> float:
                raise AssertionError("debug payload was built eagerly")

        with (
            patch.object(HSBK, "from_protocol", return_value=LazyColor()),
            patch("lifx.devices.multizone._LOGGER.isEnabledFor", return_value=False),
        ):
            result = await multizone_light.get_color_zones()

        assert len(result) == 1

    async def test_zone_debug_payload_is_emitted_when_debug_enabled(
        self, multizone_light: MultiZoneLight, mock_product_info
    ) -> None:
        """DEBUG logging includes the fetched per-zone colour values."""
        multizone_light._capabilities = mock_product_info(has_extended_multizone=False)
        multizone_light._state = MagicMock()
        protocol_color = HSBK(
            hue=180, saturation=0.5, brightness=0.75, kelvin=3500
        ).to_protocol()
        mock_state = packets.MultiZone.StateMultiZone(
            count=2, index=1, colors=[protocol_color]
        )
        multizone_light.connection.request_stream = async_generator_mock([mock_state])

        with (
            patch("lifx.devices.multizone._LOGGER.isEnabledFor", return_value=True),
            patch("lifx.devices.multizone._LOGGER.debug") as debug_mock,
        ):
            result = await multizone_light.get_color_zones(1, 1)

        assert len(result) == 1
        debug_payload = debug_mock.call_args.args[0]
        assert debug_payload["reply"]["colors"] == [
            {
                "hue": result[0].hue,
                "saturation": result[0].saturation,
                "brightness": result[0].brightness,
                "kelvin": result[0].kelvin,
            }
        ]

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

    async def test_get_color_zones_caps_response_to_learned_count(
        self, multizone_light: MultiZoneLight, mock_product_info
    ) -> None:
        """A partial final chunk excludes padded protocol colour slots."""
        multizone_light._capabilities = mock_product_info(has_extended_multizone=False)
        real_colors = [
            HSBK(hue=180, saturation=0.5, brightness=0.75, kelvin=3500),
            HSBK(hue=225, saturation=0.5, brightness=0.75, kelvin=3500),
        ]
        padded_colors = [
            HSBK(hue=0, saturation=0, brightness=0, kelvin=3500) for _ in range(6)
        ]
        mock_state = packets.MultiZone.StateMultiZone(
            count=10,
            index=8,
            colors=[color.to_protocol() for color in real_colors + padded_colors],
        )
        multizone_light.connection.request_stream = async_generator_mock([mock_state])

        result = await multizone_light.get_color_zones(start=8)

        assert result == real_colors
        assert multizone_light.zone_count == 10

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
        multizone_light.connection.request_stream = MagicMock(
            side_effect=async_generator_mock([mock_state])
        )

        result_colors = await multizone_light.get_extended_color_zones(0, 9)

        assert len(result_colors) == 10
        assert all(isinstance(color, HSBK) for color in result_colors)
        assert result_colors[0].hue == pytest.approx(0, abs=1)
        assert result_colors[1].hue == pytest.approx(36, abs=1)
        assert result_colors[9].hue == pytest.approx(324, abs=1)
        assert result_colors[0].saturation == pytest.approx(0.8, abs=0.01)
        request_call = multizone_light.connection.request_stream.call_args
        assert isinstance(request_call.args[0], packets.MultiZone.GetExtendedColorZones)
        assert request_call.kwargs == {}

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
        # Mock request_stream to yield the state once
        multizone_light.connection.request_stream = async_generator_mock([mock_state])

        # Call without parameters - should get all zones
        result_colors = await multizone_light.get_extended_color_zones()

        assert len(result_colors) == 16
        assert all(isinstance(color, HSBK) for color in result_colors)

    async def test_get_extended_color_zones_handles_empty_stream(
        self, multizone_light: MultiZoneLight
    ) -> None:
        """An empty response stream preserves the request timeout contract."""
        multizone_light.connection.request_stream = async_generator_mock([])

        with pytest.raises(LifxTimeoutError, match="No extended color-zone response"):
            await multizone_light.get_extended_color_zones(start=4)

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
        multizone_light.connection.request_stream = MagicMock(
            side_effect=async_generator_mock([mock_state])
        )

        # First call should hit the device and store the result
        result1 = await multizone_light.get_extended_color_zones(0, 4)
        call_count_after_first = multizone_light.connection.request_stream.call_count

        # Each call hits the device (no automatic caching for range queries)
        result2 = await multizone_light.get_extended_color_zones(0, 4)
        call_count_after_second = multizone_light.connection.request_stream.call_count

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
        multizone_light.connection.request_stream = async_generator_mock([mock_state])

        result_colors = await multizone_light.get_extended_color_zones(0, 99)

        # Should return colors up to the actual zone count
        assert len(result_colors) == 16
        assert multizone_light.zone_count == 16

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

    async def test_set_extended_zone_debug_payload_is_lazy_when_debug_disabled(
        self, multizone_light: MultiZoneLight
    ) -> None:
        """Debug-only colour fields must not be read unless DEBUG is enabled."""
        multizone_light.connection.request.return_value = True

        class ProtocolOnlyColor:
            def to_protocol(self):
                return HSBK(0, 0.5, 0.75, 3500).to_protocol()

            @property
            def hue(self) -> float:
                raise AssertionError("debug payload was built eagerly")

        colors = [cast(HSBK, ProtocolOnlyColor())]
        with patch("lifx.devices.multizone._LOGGER.isEnabledFor", return_value=False):
            await multizone_light.set_extended_color_zones(0, colors)

        multizone_light.connection.request.assert_awaited_once()

    async def test_set_extended_zone_debug_payload_is_emitted_when_enabled(
        self, multizone_light: MultiZoneLight
    ) -> None:
        """DEBUG logging includes the outgoing per-zone colour values."""
        multizone_light.connection.request.return_value = True
        colors = [HSBK(180, 0.5, 0.75, 3500)]

        with (
            patch("lifx.devices.multizone._LOGGER.isEnabledFor", return_value=True),
            patch("lifx.devices.multizone._LOGGER.debug") as debug_mock,
        ):
            await multizone_light.set_extended_color_zones(0, colors)

        debug_payload = debug_mock.call_args.args[0]
        assert debug_payload["values"]["colors"] == [
            {
                "hue": colors[0].hue,
                "saturation": colors[0].saturation,
                "brightness": colors[0].brightness,
                "kelvin": colors[0].kelvin,
            }
        ]

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


class TestMultiZoneStateUpdates:
    """Tests for state updates during get_color_zones and get_extended_color_zones."""

    async def test_get_color_zones_updates_state(
        self, multizone_light: MultiZoneLight, mock_product_info
    ) -> None:
        """Test get_color_zones() updates _state.zones when fetching all zones (T-C2).

        State should be updated exactly once when start=0 and result covers
        all zones. This verifies the state caching path in get_color_zones().
        """
        multizone_light._capabilities = mock_product_info(has_extended_multizone=False)

        # Initialize _state with a MultiZoneLightState so the update path is exercised
        initial_zones = [
            HSBK(hue=0, saturation=0, brightness=0, kelvin=3500) for _ in range(8)
        ]
        multizone_light._state = MultiZoneLightState(
            model="Test",
            label="Test",
            serial="d073d5010203",
            mac_address="D0:73:D5:01:02:03",
            power=True,
            capabilities=mock_product_info(has_extended_multizone=False),
            host_firmware=None,
            wifi_firmware=None,
            wifi_info=WifiInfo(signal=None, host_firmware=None),
            location=None,
            group=None,
            color=HSBK(hue=0, saturation=0, brightness=0, kelvin=3500),
            ambient_light=None,
            zones=initial_zones,
            zone_count=8,
            effect=FirmwareEffect.OFF,
            last_updated=0.0,
        )

        # Mock response: 8 zones with distinct colors
        expected_colors = [
            HSBK(hue=i * 45, saturation=0.5, brightness=0.75, kelvin=3500).to_protocol()
            for i in range(8)
        ]
        mock_state = packets.MultiZone.StateMultiZone(
            count=8, index=0, colors=expected_colors
        )
        multizone_light.connection.request.return_value = mock_state
        multizone_light.connection.request_stream = async_generator_mock([mock_state])

        result = await multizone_light.get_color_zones(0, 7)

        assert len(result) == 8
        # State should have been updated with the fetched zones
        assert multizone_light._state.zones == result
        assert multizone_light._state.last_updated > 0.0

    async def test_get_extended_color_zones_updates_state(
        self, multizone_light: MultiZoneLight, mock_product_info
    ) -> None:
        """Test get_extended_color_zones() updates _state.zones when fetching all zones.

        Same pattern as get_color_zones but for the extended protocol path.
        """
        multizone_light._capabilities = mock_product_info(has_extended_multizone=True)

        zone_count = 10
        initial_zones = [
            HSBK(hue=0, saturation=0, brightness=0, kelvin=3500)
            for _ in range(zone_count)
        ]
        multizone_light._state = MultiZoneLightState(
            model="Test",
            label="Test",
            serial="d073d5010203",
            mac_address="D0:73:D5:01:02:03",
            power=True,
            capabilities=mock_product_info(has_extended_multizone=True),
            host_firmware=None,
            wifi_firmware=None,
            wifi_info=WifiInfo(signal=None, host_firmware=None),
            location=None,
            group=None,
            color=HSBK(hue=0, saturation=0, brightness=0, kelvin=3500),
            ambient_light=None,
            zones=initial_zones,
            zone_count=zone_count,
            effect=FirmwareEffect.OFF,
            last_updated=0.0,
        )

        # Mock response: 10 zones with distinct colors, padded to 82
        colors = [
            HSBK(hue=i * 36, saturation=0.8, brightness=0.9, kelvin=3500).to_protocol()
            for i in range(zone_count)
        ]
        colors.extend(
            [
                HSBK(hue=0, saturation=0, brightness=0, kelvin=3500).to_protocol()
                for _ in range(72)
            ]
        )

        mock_state = packets.MultiZone.StateExtendedColorZones(
            count=zone_count, index=0, colors_count=zone_count, colors=colors
        )
        multizone_light.connection.request.return_value = mock_state
        multizone_light.connection.request_stream = async_generator_mock([mock_state])

        result = await multizone_light.get_extended_color_zones(0, zone_count - 1)

        assert len(result) == zone_count
        # State should have been updated with the fetched zones
        assert multizone_light._state.zones == result
        assert multizone_light._state.last_updated > 0.0


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

    def test_direction_setter_produces_exactly_8_parameters(self) -> None:
        """Test direction setter preserves 8-element parameter list (T-C1).

        The LIFX protocol expects exactly 8 uint32 parameters for multizone
        effects. The direction setter must not produce 9.
        """
        effect = MultiZoneEffect(
            effect_type=FirmwareEffect.MOVE,
            speed=5000,
        )
        assert len(effect.parameters) == 8  # default is correct
        effect.direction = Direction.FORWARD
        assert len(effect.parameters) == 8  # must stay 8 after setter
        effect.direction = Direction.REVERSED
        assert len(effect.parameters) == 8  # must stay 8 after setter

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


class TestSetAllColorZones:
    """set_all_color_zones writes a window of a full-length color list."""

    RED = HSBK(hue=0, saturation=1.0, brightness=1.0, kelvin=3500)
    BLUE = HSBK(hue=240, saturation=1.0, brightness=1.0, kelvin=3500)

    @staticmethod
    def _light(*, extended: bool, zone_count: int | None = None) -> MultiZoneLight:
        """Return a light with mocked setters and a fixed capability."""
        light = MultiZoneLight(serial="d073d5010203", ip="192.168.1.100")
        light._capabilities = MagicMock()
        light._capabilities.has_extended_multizone = extended
        light._zone_count = zone_count
        light.set_color_zones = AsyncMock()
        light.set_extended_color_zones = AsyncMock()
        return light

    @classmethod
    def _colors(cls, count: int, *, gradient: bool) -> list[HSBK]:
        """Return count colors, either all identical or all distinct."""
        return [
            HSBK(
                hue=(i * 360 / count) if gradient else 0,
                saturation=1.0,
                brightness=1.0,
                kelvin=3500,
            )
            for i in range(count)
        ]

    # -- run-length encoding --------------------------------------------

    def test_encode_zone_runs_collapses_identical_colors(self) -> None:
        """Test a flat color list becomes a single run."""
        colors = self._colors(60, gradient=False)

        assert MultiZoneLight._encode_zone_runs(colors) == [(0, 59, colors[0])]

    def test_encode_zone_runs_splits_on_change(self) -> None:
        """Test runs break wherever the color changes."""
        runs = MultiZoneLight._encode_zone_runs(
            [self.RED, self.RED, self.BLUE, self.RED]
        )

        assert runs == [(0, 1, self.RED), (2, 2, self.BLUE), (3, 3, self.RED)]

    def test_encode_zone_runs_applies_offset(self) -> None:
        """Test the offset shifts runs into device zone numbering."""
        runs = MultiZoneLight._encode_zone_runs([self.RED, self.BLUE], offset=10)

        assert runs == [(10, 10, self.RED), (11, 11, self.BLUE)]

    def test_encode_zone_runs_gradient_yields_one_run_per_zone(self) -> None:
        """Test a gradient cannot be collapsed; this is the packet-count cliff."""
        colors = self._colors(60, gradient=True)

        assert len(MultiZoneLight._encode_zone_runs(colors)) == 60

    # -- extended path ---------------------------------------------------

    async def test_extended_writes_whole_list_by_default(self) -> None:
        """Test omitting end writes every color in the list."""
        light = self._light(extended=True)
        colors = self._colors(16, gradient=True)

        await light.set_all_color_zones(colors, duration=1.0)

        light.set_extended_color_zones.assert_awaited_once_with(
            0, colors, duration=1.0, apply=MultiZoneApplicationRequest.APPLY
        )
        light.set_color_zones.assert_not_awaited()

    async def test_extended_chunks_past_82_zones(self) -> None:
        """Test more than 82 zones is split, with only the last chunk applying."""
        light = self._light(extended=True)
        colors = self._colors(200, gradient=True)

        await light.set_all_color_zones(colors)

        calls = light.set_extended_color_zones.await_args_list
        assert [call.args[0] for call in calls] == [0, 82, 164]
        assert [len(call.args[1]) for call in calls] == [82, 82, 36]
        assert [call.kwargs["apply"] for call in calls] == [
            ExtendedAppReq.NO_APPLY,
            ExtendedAppReq.NO_APPLY,
            MultiZoneApplicationRequest.APPLY,
        ]

    async def test_extended_window_writes_only_the_window(self) -> None:
        """Test a window sends just its slice, at its own start index."""
        light = self._light(extended=True)
        colors = self._colors(64, gradient=True)

        await light.set_all_color_zones(colors, start=10, end=19)

        light.set_extended_color_zones.assert_awaited_once_with(
            10,
            colors[10:20],
            duration=0.0,
            apply=MultiZoneApplicationRequest.APPLY,
        )

    async def test_extended_window_chunks_offset_from_start(self) -> None:
        """Test chunk indices are offset by start, not from zero."""
        light = self._light(extended=True)
        colors = self._colors(300, gradient=True)

        await light.set_all_color_zones(colors, start=100, end=280)

        calls = light.set_extended_color_zones.await_args_list
        assert [call.args[0] for call in calls] == [100, 182, 264]
        assert [len(call.args[1]) for call in calls] == [82, 82, 17]

    async def test_read_modify_write_round_trip(self) -> None:
        """Test changing one zone addresses only that zone."""
        light = self._light(extended=True)
        colors = self._colors(64, gradient=False)
        colors[5] = self.BLUE

        await light.set_all_color_zones(colors, start=5, end=5)

        light.set_extended_color_zones.assert_awaited_once_with(
            5, [self.BLUE], duration=0.0, apply=MultiZoneApplicationRequest.APPLY
        )

    # -- legacy path -----------------------------------------------------

    async def test_legacy_flat_color_is_one_packet(self) -> None:
        """Test legacy firmware sends a single range for a flat color."""
        light = self._light(extended=False)
        colors = self._colors(60, gradient=False)

        await light.set_all_color_zones(colors, duration=2.0)

        light.set_color_zones.assert_awaited_once_with(
            0,
            59,
            colors[0],
            duration=2.0,
            apply=MultiZoneApplicationRequest.APPLY,
        )
        light.set_extended_color_zones.assert_not_awaited()

    async def test_legacy_gradient_is_one_packet_per_zone(self) -> None:
        """Test a legacy gradient costs one packet per zone, applying last."""
        light = self._light(extended=False)
        colors = self._colors(60, gradient=True)

        await light.set_all_color_zones(colors)

        calls = light.set_color_zones.await_args_list
        assert len(calls) == 60
        assert [call.kwargs["apply"] for call in calls[:-1]] == [
            MultiZoneApplicationRequest.NO_APPLY
        ] * 59
        assert calls[-1].kwargs["apply"] == MultiZoneApplicationRequest.APPLY

    async def test_legacy_window_offsets_run_indices(self) -> None:
        """Test legacy runs are numbered from start, not from zero."""
        light = self._light(extended=False)
        colors = self._colors(64, gradient=False)

        await light.set_all_color_zones(colors, start=10, end=19)

        light.set_color_zones.assert_awaited_once_with(
            10,
            19,
            colors[10],
            duration=0.0,
            apply=MultiZoneApplicationRequest.APPLY,
        )

    async def test_legacy_rle_does_not_merge_across_window_boundary(self) -> None:
        """Test identical colors outside the window do not extend a run.

        Merging across the boundary would spill the write onto zones the
        caller asked to leave alone.
        """
        light = self._light(extended=False)
        colors = [self.RED] * 64

        await light.set_all_color_zones(colors, start=10, end=19)

        light.set_color_zones.assert_awaited_once_with(
            10, 19, self.RED, duration=0.0, apply=MultiZoneApplicationRequest.APPLY
        )

    async def test_legacy_rejects_window_past_zone_255(self) -> None:
        """Test the uint8 index limit is reported rather than silently wrapping."""
        light = self._light(extended=False)

        with pytest.raises(ValueError, match="limit is 255"):
            await light.set_all_color_zones(self._colors(300, gradient=True))

    async def test_legacy_accepts_long_list_with_low_window(self) -> None:
        """Test the uint8 bound applies to the window, not the list length."""
        light = self._light(extended=False)
        colors = self._colors(300, gradient=False)

        await light.set_all_color_zones(colors, start=0, end=50)

        light.set_color_zones.assert_awaited_once_with(
            0, 50, colors[0], duration=0.0, apply=MultiZoneApplicationRequest.APPLY
        )

    # -- apply composition -----------------------------------------------

    async def test_apply_no_apply_buffers_every_packet(self) -> None:
        """Test NO_APPLY means no packet applies, so writes can compose."""
        light = self._light(extended=True)
        colors = self._colors(200, gradient=True)

        await light.set_all_color_zones(
            colors, apply=MultiZoneApplicationRequest.NO_APPLY
        )

        calls = light.set_extended_color_zones.await_args_list
        assert [call.kwargs["apply"] for call in calls] == [ExtendedAppReq.NO_APPLY] * 3

    # -- validation ------------------------------------------------------

    async def test_rejects_empty_colors(self) -> None:
        """Test an empty color list is rejected."""
        light = self._light(extended=True)

        with pytest.raises(ValueError, match="cannot be empty"):
            await light.set_all_color_zones([])

    @pytest.mark.parametrize(("start", "end"), [(-1, 5), (5, 4)])
    async def test_rejects_invalid_window(self, start: int, end: int) -> None:
        """Test a negative start or an end below start is rejected."""
        light = self._light(extended=True)

        with pytest.raises(ValueError, match="Invalid zone range"):
            await light.set_all_color_zones(
                self._colors(16, gradient=True), start=start, end=end
            )

    async def test_rejects_apply_only(self) -> None:
        """Test APPLY_ONLY is rejected before any packet is sent.

        APPLY_ONLY tells the device to ignore the colors carried by the
        message and flush only what is already buffered, so on a split write
        it would silently drop a chunk.
        """
        light = self._light(extended=True, zone_count=200)

        with pytest.raises(ValueError, match="APPLY_ONLY"):
            await light.set_all_color_zones(
                self._colors(200, gradient=True),
                apply=MultiZoneApplicationRequest.APPLY_ONLY,
            )

        light.set_extended_color_zones.assert_not_awaited()
        light.set_color_zones.assert_not_awaited()

    async def test_rejects_window_past_end_of_list(self) -> None:
        """Test the window must lie inside the color list."""
        light = self._light(extended=True)

        with pytest.raises(ValueError, match="extends past"):
            await light.set_all_color_zones(
                self._colors(16, gradient=True), start=0, end=20
            )

    async def test_rejects_window_past_cached_zone_count(self) -> None:
        """Test a cached zone count is enforced rather than clamped."""
        light = self._light(extended=True, zone_count=8)

        with pytest.raises(ValueError, match="exceeds the device's 8 zones"):
            await light.set_all_color_zones(self._colors(16, gradient=True))

        light.set_extended_color_zones.assert_not_awaited()

    async def test_uncached_zone_count_sends_no_extra_request(self) -> None:
        """Test an unknown zone count skips the check without a round trip."""
        light = self._light(extended=True, zone_count=None)
        light.get_zone_count = AsyncMock()

        await light.set_all_color_zones(self._colors(16, gradient=True))

        light.get_zone_count.assert_not_awaited()
        light.set_extended_color_zones.assert_awaited_once()
