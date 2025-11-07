"""Tests for tile device class."""

from __future__ import annotations

import time

import pytest

from lifx.color import HSBK
from lifx.devices.tile import TileDevice, TileEffect, TileInfo, TileRect
from lifx.protocol import packets
from lifx.protocol.protocol_types import TileEffectSkyType, TileEffectType


class TestTileDevice:
    """Tests for TileDevice class."""

    def test_create_tile_device(self) -> None:
        """Test creating a tile device."""
        tile = TileDevice(
            serial="d073d5010203",
            ip="192.168.1.100",
            port=56700,
        )
        assert tile.serial == "d073d5010203"
        assert tile.ip == "192.168.1.100"
        assert tile.port == 56700

    async def test_get_tile_chain(self, tile_device: TileDevice) -> None:
        """Test getting tile chain."""
        # Mock TileStateDeviceChain response
        from lifx.protocol.protocol_types import (
            DeviceStateHostFirmware,
            DeviceStateVersion,
            TileAccelMeas,
            TileStateDevice,
        )

        tile_devices = []
        for i in range(3):
            tile_devices.append(
                TileStateDevice(
                    accel_meas=TileAccelMeas(x=0, y=0, z=0),
                    user_x=float(i),
                    user_y=float(i),
                    width=8,
                    height=8,
                    device_version=DeviceStateVersion(vendor=1, product=27),
                    firmware=DeviceStateHostFirmware(
                        build=1234567890, version_minor=3, version_major=2
                    ),
                )
            )

        # Pad to 16 tiles
        for _ in range(13):
            tile_devices.append(
                TileStateDevice(
                    accel_meas=TileAccelMeas(x=0, y=0, z=0),
                    user_x=0.0,
                    user_y=0.0,
                    width=0,
                    height=0,
                    device_version=DeviceStateVersion(vendor=0, product=0),
                    firmware=DeviceStateHostFirmware(
                        build=0, version_minor=0, version_major=0
                    ),
                )
            )

        mock_state = packets.Tile.StateDeviceChain(
            start_index=0, tile_devices=tile_devices, tile_devices_count=3
        )
        tile_device.connection.request.return_value = mock_state

        chain = await tile_device.get_tile_chain()

        assert len(chain) == 3
        assert all(isinstance(tile_info, TileInfo) for tile_info in chain)
        assert chain[0].width == 8
        assert chain[0].height == 8
        assert chain[0].user_x == 0.0
        assert chain[1].user_x == 1.0

    async def test_get_tile_count(self, tile_device: TileDevice) -> None:
        """Test getting tile count."""
        # Create minimal chain response with 2 tiles
        from lifx.protocol.protocol_types import (
            DeviceStateHostFirmware,
            DeviceStateVersion,
            TileAccelMeas,
            TileStateDevice,
        )

        tile_devices = []
        for _ in range(2):
            tile_devices.append(
                TileStateDevice(
                    accel_meas=TileAccelMeas(x=0, y=0, z=0),
                    user_x=0.0,
                    user_y=0.0,
                    width=8,
                    height=8,
                    device_version=DeviceStateVersion(vendor=1, product=27),
                    firmware=DeviceStateHostFirmware(
                        build=0, version_minor=3, version_major=2
                    ),
                )
            )

        # Pad to 16 tiles
        for _ in range(14):
            tile_devices.append(
                TileStateDevice(
                    accel_meas=TileAccelMeas(x=0, y=0, z=0),
                    user_x=0.0,
                    user_y=0.0,
                    width=0,
                    height=0,
                    device_version=DeviceStateVersion(vendor=0, product=0),
                    firmware=DeviceStateHostFirmware(
                        build=0, version_minor=0, version_major=0
                    ),
                )
            )

        mock_state = packets.Tile.StateDeviceChain(
            start_index=0, tile_devices=tile_devices, tile_devices_count=2
        )
        tile_device.connection.request.return_value = mock_state

        count = await tile_device.get_tile_count()
        assert count == 2

    async def test_get_tile_colors(self, tile_device: TileDevice) -> None:
        """Test getting tile colors."""
        # First, mock the tile chain query
        from lifx.protocol.protocol_types import (
            DeviceStateHostFirmware,
            DeviceStateVersion,
            TileAccelMeas,
            TileBufferRect,
            TileStateDevice,
        )

        tile_devices = [
            TileStateDevice(
                accel_meas=TileAccelMeas(x=0, y=0, z=0),
                user_x=0.0,
                user_y=0.0,
                width=8,
                height=8,
                device_version=DeviceStateVersion(vendor=1, product=27),
                firmware=DeviceStateHostFirmware(
                    build=0, version_minor=3, version_major=2
                ),
            )
        ]
        # Pad to 16 tiles
        for _ in range(15):
            tile_devices.append(
                TileStateDevice(
                    accel_meas=TileAccelMeas(x=0, y=0, z=0),
                    user_x=0.0,
                    user_y=0.0,
                    width=0,
                    height=0,
                    device_version=DeviceStateVersion(vendor=0, product=0),
                    firmware=DeviceStateHostFirmware(
                        build=0, version_minor=0, version_major=0
                    ),
                )
            )

        chain_state = packets.Tile.StateDeviceChain(
            start_index=0, tile_devices=tile_devices, tile_devices_count=1
        )

        # Then, mock the TileState64 response with 64 colors
        # Create colors with varying hues (i * 5.625° for each pixel)
        colors = [
            HSBK(
                hue=i * 5.625, saturation=0.5, brightness=0.75, kelvin=3500
            ).to_protocol()
            for i in range(64)
        ]

        state64 = packets.Tile.State64(
            tile_index=0,
            rect=TileBufferRect(fb_index=0, x=0, y=0, width=8),
            colors=colors,
        )

        # Setup mock to return different responses for different calls
        tile_device.connection.request.side_effect = [chain_state, state64]

        colors_result = await tile_device.get_tile_colors(0)

        assert len(colors_result) == 8  # 8 rows
        assert len(colors_result[0]) == 8  # 8 columns
        assert all(isinstance(color, HSBK) for row in colors_result for color in row)
        assert colors_result[0][0].kelvin == 3500

    async def test_get_tile_colors_wide_tile(self, tile_device: TileDevice) -> None:
        """Test getting tile colors from a wide tile (16x8)."""
        from lifx.protocol.protocol_types import (
            DeviceStateHostFirmware,
            DeviceStateVersion,
            TileAccelMeas,
            TileBufferRect,
            TileStateDevice,
        )

        # Mock a wide tile (16x8 pixels = 128 pixels total)
        tile_devices = [
            TileStateDevice(
                accel_meas=TileAccelMeas(x=0, y=0, z=0),
                user_x=0.0,
                user_y=0.0,
                width=16,
                height=8,
                device_version=DeviceStateVersion(vendor=1, product=27),
                firmware=DeviceStateHostFirmware(
                    build=0, version_minor=3, version_major=2
                ),
            )
        ]
        # Pad to 16 tiles
        for _ in range(15):
            tile_devices.append(
                TileStateDevice(
                    accel_meas=TileAccelMeas(x=0, y=0, z=0),
                    user_x=0.0,
                    user_y=0.0,
                    width=0,
                    height=0,
                    device_version=DeviceStateVersion(vendor=0, product=0),
                    firmware=DeviceStateHostFirmware(
                        build=0, version_minor=0, version_major=0
                    ),
                )
            )

        chain_state = packets.Tile.StateDeviceChain(
            start_index=0, tile_devices=tile_devices, tile_devices_count=1
        )

        # For wide tiles (16x8), two Get64 requests are sent sequentially:
        # - Request 1: y=0, height=4 (16x4 = 64 pixels, rows 0-3)
        # - Request 2: y=4, height=4 (16x4 = 64 pixels, rows 4-7)

        # Create first State64 (top half, rows 0-3)
        colors_top = [
            HSBK(
                hue=i * 2.8125, saturation=0.5, brightness=0.75, kelvin=3500
            ).to_protocol()
            for i in range(64)
        ]
        state64_top = packets.Tile.State64(
            tile_index=0,
            rect=TileBufferRect(fb_index=0, x=0, y=0, width=16),
            colors=colors_top,
        )

        # Create second State64 (bottom half, rows 4-7)
        colors_bottom = [
            HSBK(
                hue=180 + i * 2.8125, saturation=0.5, brightness=0.75, kelvin=3500
            ).to_protocol()
            for i in range(64)
        ]
        state64_bottom = packets.Tile.State64(
            tile_index=0,
            rect=TileBufferRect(fb_index=0, x=0, y=4, width=16),
            colors=colors_bottom,
        )

        # Setup mock to return chain state, then two State64 packets sequentially
        tile_device.connection.request.side_effect = [
            chain_state,
            state64_top,
            state64_bottom,
        ]

        colors_result = await tile_device.get_tile_colors(0)

        # Verify dimensions
        assert len(colors_result) == 8  # 8 rows
        assert len(colors_result[0]) == 16  # 16 columns (wide tile)

        # Verify all colors are HSBK
        assert all(isinstance(color, HSBK) for row in colors_result for color in row)

        # Verify top half has different hues than bottom half
        assert colors_result[0][0].hue < 180  # Top half starts at low hue
        assert colors_result[4][0].hue >= 180  # Bottom half starts at higher hue

        # Verify kelvin is preserved
        assert colors_result[0][0].kelvin == 3500
        assert colors_result[0][8].kelvin == 3500

    async def test_set_tile_colors(self, tile_device: TileDevice) -> None:
        """Test setting tile colors."""
        # Set up a simple 8x8 tile
        tile_info = TileInfo(
            accel_meas_x=0,
            accel_meas_y=0,
            accel_meas_z=0,
            user_x=0.0,
            user_y=0.0,
            width=8,
            height=8,
            device_version_vendor=1,
            device_version_product=27,
            device_version_version=0,
            firmware_build=0,
            firmware_version_minor=3,
            firmware_version_major=2,
        )
        tile_device._tile_chain = ([tile_info], time.time())

        # Mock power state (device is on)
        tile_device._power = (True, time.time())

        # Mock SET operation returns True
        tile_device.connection.request.return_value = True

        # Create 8x8 grid of colors
        red = HSBK.from_rgb(255, 0, 0)
        colors = [[red] * 8 for _ in range(8)]

        await tile_device.set_tile_colors(0, colors, duration=1.0)

        # Verify packet was sent
        tile_device.connection.request.assert_called_once()
        call_args = tile_device.connection.request.call_args
        packet = call_args[0][0]

        # Verify packet has correct values
        assert packet.tile_index == 0
        assert packet.rect.x == 0
        assert packet.rect.y == 0
        assert packet.rect.width == 8
        assert packet.duration == 1000  # 1 second in ms
        assert len(packet.colors) == 64

    async def test_set_tile_colors_partial(self, tile_device: TileDevice) -> None:
        """Test setting colors on partial tile area."""
        # Set up a simple 8x8 tile
        tile_info = TileInfo(
            accel_meas_x=0,
            accel_meas_y=0,
            accel_meas_z=0,
            user_x=0.0,
            user_y=0.0,
            width=8,
            height=8,
            device_version_vendor=1,
            device_version_product=27,
            device_version_version=0,
            firmware_build=0,
            firmware_version_minor=3,
            firmware_version_major=2,
        )
        tile_device._tile_chain = ([tile_info], time.time())

        # Mock power state (device is on)
        tile_device._power = (True, time.time())

        # Mock SET operation returns True
        tile_device.connection.request.return_value = True

        # Create 4x4 grid of colors
        blue = HSBK.from_rgb(0, 0, 255)
        colors = [[blue] * 4 for _ in range(4)]

        await tile_device.set_tile_colors(0, colors, x=2, y=2)

        # Verify packet was sent
        tile_device.connection.request.assert_called_once()
        call_args = tile_device.connection.request.call_args
        packet = call_args[0][0]

        # Verify packet has correct values
        assert packet.tile_index == 0
        assert packet.rect.x == 2
        assert packet.rect.y == 2
        assert packet.rect.width == 4

    async def test_set_tile_colors_wide_tile(self, tile_device: TileDevice) -> None:
        """Test setting colors on a wide tile (16x8) using frame buffer strategy."""
        from lifx.protocol.protocol_types import (
            DeviceStateHostFirmware,
            DeviceStateVersion,
            TileAccelMeas,
            TileStateDevice,
        )

        # Mock tile chain for a 16x8 wide tile
        tile_devices = [
            TileStateDevice(
                accel_meas=TileAccelMeas(x=0, y=0, z=0),
                user_x=0.0,
                user_y=0.0,
                width=16,
                height=8,
                device_version=DeviceStateVersion(vendor=1, product=27),
                firmware=DeviceStateHostFirmware(
                    build=0, version_minor=3, version_major=2
                ),
            )
        ]
        # Pad to 16 tiles
        for _ in range(15):
            tile_devices.append(
                TileStateDevice(
                    accel_meas=TileAccelMeas(x=0, y=0, z=0),
                    user_x=0.0,
                    user_y=0.0,
                    width=0,
                    height=0,
                    device_version=DeviceStateVersion(vendor=0, product=0),
                    firmware=DeviceStateHostFirmware(
                        build=0, version_minor=0, version_major=0
                    ),
                )
            )

        # _ = packets.Tile.StateDeviceChain(start_index=0, ...)

        # Store the chain state so copy_frame_buffer can access it
        tile_info_list = [
            TileInfo(
                accel_meas_x=0,
                accel_meas_y=0,
                accel_meas_z=0,
                user_x=0.0,
                user_y=0.0,
                width=16,
                height=8,
                device_version_vendor=1,
                device_version_product=27,
                device_version_version=0,
                firmware_build=0,
                firmware_version_minor=3,
                firmware_version_major=2,
            )
        ]
        # Set tile_chain with timestamp
        tile_device._tile_chain = (tile_info_list, time.time())

        # Mock power state (device is on)
        tile_device._power = (True, time.time())

        # Create StateDeviceChain response for get_tile_chain()
        # call in copy_frame_buffer
        tile_devices = [
            TileStateDevice(
                accel_meas=TileAccelMeas(x=0, y=0, z=0),
                user_x=0.0,
                user_y=0.0,
                width=16,
                height=8,
                device_version=DeviceStateVersion(vendor=1, product=27),
                firmware=DeviceStateHostFirmware(
                    build=0, version_minor=3, version_major=2
                ),
            )
        ]
        # Pad to 16 tiles
        while len(tile_devices) < 16:
            tile_devices.append(
                TileStateDevice(
                    accel_meas=TileAccelMeas(x=0, y=0, z=0),
                    user_x=0.0,
                    user_y=0.0,
                    width=0,
                    height=0,
                    device_version=DeviceStateVersion(vendor=0, product=0),
                    firmware=DeviceStateHostFirmware(
                        build=0, version_minor=0, version_major=0
                    ),
                )
            )

        chain_response = packets.Tile.StateDeviceChain(
            start_index=0, tile_devices=tile_devices, tile_devices_count=1
        )

        # Mock request responses:
        # - 2 Set64 packets return True
        # - 1 GetDeviceChain (in copy_frame_buffer) returns chain_response
        # - 1 CopyFrameBuffer packet returns True
        tile_device.connection.request.side_effect = [True, True, chain_response, True]

        # Create 16x8 grid of colors (128 pixels total, requires 2 Set64 packets)
        green = HSBK.from_rgb(0, 255, 0)
        colors = [[green] * 16 for _ in range(8)]

        await tile_device.set_tile_colors(0, colors, duration=1.0)

        # Verify multiple packets were sent:
        # - 2 Set64 packets to frame buffer 1 (top and bottom halves)
        # - 1 GetDeviceChain (for get_tile_chain in copy_frame_buffer)
        # - 1 CopyFrameBuffer packet to copy from fb 1 to fb 0
        assert tile_device.connection.request.call_count == 4

        # Check first Set64 call (top half to frame buffer 1)
        first_call = tile_device.connection.request.call_args_list[0]
        packet1 = first_call[0][0]
        assert packet1.tile_index == 0
        assert packet1.rect.fb_index == 1  # Write to invisible frame buffer
        assert packet1.rect.x == 0
        assert packet1.rect.y == 0
        assert packet1.rect.width == 16
        assert packet1.duration == 0  # No duration when writing to fb 1

        # Check second Set64 call (bottom half to frame buffer 1)
        second_call = tile_device.connection.request.call_args_list[1]
        packet2 = second_call[0][0]
        assert packet2.tile_index == 0
        assert packet2.rect.fb_index == 1
        assert packet2.rect.x == 0
        assert packet2.rect.y == 4  # Second chunk starts at row 4
        assert packet2.rect.width == 16

        # Check third call (GetDeviceChain - called by copy_frame_buffer)
        third_call = tile_device.connection.request.call_args_list[2]
        packet3 = third_call[0][0]
        assert isinstance(packet3, packets.Tile.GetDeviceChain)

        # Check fourth call (CopyFrameBuffer)
        fourth_call = tile_device.connection.request.call_args_list[3]
        packet4 = fourth_call[0][0]
        assert packet4.tile_index == 0
        assert packet4.src_fb_index == 1  # Copy from invisible frame buffer
        assert packet4.dst_fb_index == 0  # To visible frame buffer
        assert packet4.width == 16
        assert packet4.height == 8

    async def test_set_tile_colors_when_powered_off(
        self, tile_device: TileDevice
    ) -> None:
        """Test color setting when device is off with duration."""
        # Set up a simple 8x8 tile
        tile_info = TileInfo(
            accel_meas_x=0,
            accel_meas_y=0,
            accel_meas_z=0,
            user_x=0.0,
            user_y=0.0,
            width=8,
            height=8,
            device_version_vendor=1,
            device_version_product=27,
            device_version_version=0,
            firmware_build=0,
            firmware_version_minor=3,
            firmware_version_major=2,
        )
        tile_device._tile_chain = ([tile_info], time.time())

        # Mock power state (device is off)
        tile_device._power = (False, time.time())

        # Mock SET operation returns True
        tile_device.connection.request.return_value = True

        # Create 8x8 grid of colors
        red = HSBK.from_rgb(255, 0, 0)
        colors = [[red] * 8 for _ in range(8)]

        await tile_device.set_tile_colors(0, colors, duration=2.0)

        # Verify two calls were made: Set64 and set_power
        assert tile_device.connection.request.call_count == 2

        # First call: Set64 with duration=0 (instant color change)
        first_call = tile_device.connection.request.call_args_list[0]
        packet1 = first_call[0][0]
        assert packet1.tile_index == 0
        assert packet1.duration == 0  # Instant color change when off

        # Second call: SetPower with duration=2000ms (power on with transition)
        second_call = tile_device.connection.request.call_args_list[1]
        packet2 = second_call[0][0]
        assert hasattr(packet2, "level")  # SetPower packet
        assert packet2.level == 65535  # Full power
        assert packet2.duration == 2000  # 2 seconds in ms

    async def test_set_tile_colors_invalid_dimensions(
        self, tile_device: TileDevice
    ) -> None:
        """Test that inconsistent row widths raise error."""
        # Create array with inconsistent row widths
        colors = [[HSBK(0, 0, 1.0, 3500)] * 4, [HSBK(0, 0, 1.0, 3500)] * 5]

        with pytest.raises(ValueError, match="same width"):
            await tile_device.set_tile_colors(0, colors)

    async def test_get_tile_effect(self, tile_device: TileDevice) -> None:
        """Test getting tile effect."""
        # Mock Tile.StateEffect response
        from lifx.protocol.protocol_types import TileEffectParameter, TileEffectSettings

        # Create 3 HSBK colors for palette (0°, 120°, 240°)
        palette = []
        for i in range(3):
            palette.append(
                HSBK(
                    hue=i * 120, saturation=1.0, brightness=1.0, kelvin=3500
                ).to_protocol()
            )

        # Pad palette to 16 colors (use black with minimum kelvin)
        for _ in range(13):
            palette.append(
                HSBK(hue=0, saturation=0, brightness=0, kelvin=3500).to_protocol()
            )

        mock_state = packets.Tile.StateEffect(
            settings=TileEffectSettings(
                instanceid=12345,
                effect_type=TileEffectType.MORPH,
                speed=5000,
                duration=0,
                parameter=TileEffectParameter(
                    sky_type=TileEffectSkyType.SUNRISE,
                    cloud_saturation_min=0,
                    cloud_saturation_max=0,
                ),
                palette_count=3,
                palette=palette,
            )
        )
        tile_device.connection.request.return_value = mock_state

        effect = await tile_device.get_tile_effect()

        assert effect is not None
        assert effect.effect_type == TileEffectType.MORPH
        assert effect.speed == 5000
        assert effect.duration == 0
        assert len(effect.palette) == 3

    async def test_set_tile_effect(self, tile_device: TileDevice) -> None:
        """Test setting tile effect."""
        # Mock SET operation returns True
        tile_device.connection.request.return_value = True

        palette = [
            HSBK.from_rgb(255, 0, 0),
            HSBK.from_rgb(0, 255, 0),
            HSBK.from_rgb(0, 0, 255),
        ]
        effect = TileEffect(
            effect_type=TileEffectType.MORPH,
            speed=5000,
            duration=0,
            palette=palette,
        )
        await tile_device.set_tile_effect(effect)

        # Verify packet was sent
        tile_device.connection.request.assert_called_once()
        call_args = tile_device.connection.request.call_args
        packet = call_args[0][0]

        # Verify packet has correct values
        assert packet.settings.effect_type == TileEffectType.MORPH
        assert packet.settings.speed == 5000
        assert packet.settings.palette_count == 3
        assert len(packet.settings.palette) == 16  # Padded

    async def test_stop_effect(self, tile_device: TileDevice) -> None:
        """Test stopping effect."""
        # Mock SET operation returns True
        tile_device.connection.request.return_value = True

        await tile_device.stop_effect()

        # Verify packet was sent with OFF effect
        tile_device.connection.request.assert_called_once()
        call_args = tile_device.connection.request.call_args
        packet = call_args[0][0]
        assert packet.settings.effect_type == TileEffectType.OFF

    async def test_copy_frame_buffer(self, tile_device: TileDevice) -> None:
        """Test copying frame buffer."""
        # Mock tile chain response
        from lifx.protocol.protocol_types import (
            DeviceStateHostFirmware,
            DeviceStateVersion,
            TileAccelMeas,
            TileStateDevice,
        )

        tile_devices = [
            TileStateDevice(
                accel_meas=TileAccelMeas(x=0, y=0, z=0),
                user_x=0.0,
                user_y=0.0,
                width=8,
                height=8,
                device_version=DeviceStateVersion(vendor=1, product=27),
                firmware=DeviceStateHostFirmware(
                    build=0, version_minor=3, version_major=2
                ),
            )
        ]
        # Pad to 16
        for _ in range(15):
            tile_devices.append(
                TileStateDevice(
                    accel_meas=TileAccelMeas(x=0, y=0, z=0),
                    user_x=0.0,
                    user_y=0.0,
                    width=0,
                    height=0,
                    device_version=DeviceStateVersion(vendor=0, product=0),
                    firmware=DeviceStateHostFirmware(
                        build=0, version_minor=0, version_major=0
                    ),
                )
            )

        mock_chain = packets.Tile.StateDeviceChain(
            start_index=0, tile_devices=tile_devices, tile_devices_count=1
        )

        # First call returns chain, second call returns True (copy operation)
        tile_device.connection.request.side_effect = [mock_chain, True]

        # Copy entire tile from buffer 0 to buffer 1
        await tile_device.copy_frame_buffer(
            tile_index=0, src_fb_index=0, dst_fb_index=1
        )

        # Verify CopyFrameBuffer packet was sent
        assert tile_device.connection.request.call_count == 2
        copy_call = tile_device.connection.request.call_args_list[1]
        packet = copy_call[0][0]

        assert isinstance(packet, packets.Tile.CopyFrameBuffer)
        assert packet.tile_index == 0
        assert packet.length == 1
        assert packet.src_fb_index == 0
        assert packet.dst_fb_index == 1
        assert packet.src_x == 0
        assert packet.src_y == 0
        assert packet.dst_x == 0
        assert packet.dst_y == 0
        assert packet.width == 8
        assert packet.height == 8

    async def test_copy_frame_buffer_partial(self, tile_device: TileDevice) -> None:
        """Test copying partial frame buffer region."""
        # Mock tile chain response
        from lifx.protocol.protocol_types import (
            DeviceStateHostFirmware,
            DeviceStateVersion,
            TileAccelMeas,
            TileStateDevice,
        )

        tile_devices = [
            TileStateDevice(
                accel_meas=TileAccelMeas(x=0, y=0, z=0),
                user_x=0.0,
                user_y=0.0,
                width=8,
                height=8,
                device_version=DeviceStateVersion(vendor=1, product=27),
                firmware=DeviceStateHostFirmware(
                    build=0, version_minor=3, version_major=2
                ),
            )
        ]
        # Pad to 16
        for _ in range(15):
            tile_devices.append(
                TileStateDevice(
                    accel_meas=TileAccelMeas(x=0, y=0, z=0),
                    user_x=0.0,
                    user_y=0.0,
                    width=0,
                    height=0,
                    device_version=DeviceStateVersion(vendor=0, product=0),
                    firmware=DeviceStateHostFirmware(
                        build=0, version_minor=0, version_major=0
                    ),
                )
            )

        mock_chain = packets.Tile.StateDeviceChain(
            start_index=0, tile_devices=tile_devices, tile_devices_count=1
        )

        # First call returns chain, second call returns True
        tile_device.connection.request.side_effect = [mock_chain, True]

        # Copy 4x4 region from (0,0) to (2,2)
        await tile_device.copy_frame_buffer(
            tile_index=0, src_x=0, src_y=0, dst_x=2, dst_y=2, width=4, height=4
        )

        # Verify packet was sent with correct dimensions
        copy_call = tile_device.connection.request.call_args_list[1]
        packet = copy_call[0][0]

        assert packet.src_x == 0
        assert packet.src_y == 0
        assert packet.dst_x == 2
        assert packet.dst_y == 2
        assert packet.width == 4
        assert packet.height == 4

    async def test_copy_frame_buffer_invalid_tile_index(
        self, tile_device: TileDevice
    ) -> None:
        """Test copy_frame_buffer with invalid tile index."""
        with pytest.raises(ValueError, match="Invalid tile index"):
            await tile_device.copy_frame_buffer(tile_index=-1)

    async def test_copy_frame_buffer_invalid_fb_index(
        self, tile_device: TileDevice
    ) -> None:
        """Test copy_frame_buffer with invalid frame buffer index."""
        with pytest.raises(ValueError, match="Invalid frame buffer indices"):
            await tile_device.copy_frame_buffer(tile_index=0, src_fb_index=-1)

    async def test_copy_frame_buffer_invalid_coordinates(
        self, tile_device: TileDevice
    ) -> None:
        """Test copy_frame_buffer with invalid coordinates."""
        with pytest.raises(ValueError, match="Invalid coordinates"):
            await tile_device.copy_frame_buffer(tile_index=0, src_x=-1)

    async def test_copy_frame_buffer_invalid_dimensions(
        self, tile_device: TileDevice
    ) -> None:
        """Test copy_frame_buffer with invalid dimensions."""
        with pytest.raises(ValueError, match="Invalid dimensions"):
            await tile_device.copy_frame_buffer(tile_index=0, width=0)

    async def test_copy_frame_buffer_out_of_range_tile(
        self, tile_device: TileDevice
    ) -> None:
        """Test copy_frame_buffer with tile index out of range."""
        # Mock tile chain with single tile
        from lifx.protocol.protocol_types import (
            DeviceStateHostFirmware,
            DeviceStateVersion,
            TileAccelMeas,
            TileStateDevice,
        )

        tile_devices = [
            TileStateDevice(
                accel_meas=TileAccelMeas(x=0, y=0, z=0),
                user_x=0.0,
                user_y=0.0,
                width=8,
                height=8,
                device_version=DeviceStateVersion(vendor=1, product=27),
                firmware=DeviceStateHostFirmware(
                    build=0, version_minor=3, version_major=2
                ),
            )
        ]
        # Pad to 16
        for _ in range(15):
            tile_devices.append(
                TileStateDevice(
                    accel_meas=TileAccelMeas(x=0, y=0, z=0),
                    user_x=0.0,
                    user_y=0.0,
                    width=0,
                    height=0,
                    device_version=DeviceStateVersion(vendor=0, product=0),
                    firmware=DeviceStateHostFirmware(
                        build=0, version_minor=0, version_major=0
                    ),
                )
            )

        mock_chain = packets.Tile.StateDeviceChain(
            start_index=0, tile_devices=tile_devices, tile_devices_count=1
        )
        tile_device.connection.request.return_value = mock_chain

        with pytest.raises(ValueError, match="out of range"):
            await tile_device.copy_frame_buffer(tile_index=5)

    async def test_copy_frame_buffer_source_exceeds_dimensions(
        self, tile_device: TileDevice
    ) -> None:
        """Test copy_frame_buffer with source rectangle exceeding tile dimensions."""
        # Mock tile chain
        from lifx.protocol.protocol_types import (
            DeviceStateHostFirmware,
            DeviceStateVersion,
            TileAccelMeas,
            TileStateDevice,
        )

        tile_devices = [
            TileStateDevice(
                accel_meas=TileAccelMeas(x=0, y=0, z=0),
                user_x=0.0,
                user_y=0.0,
                width=8,
                height=8,
                device_version=DeviceStateVersion(vendor=1, product=27),
                firmware=DeviceStateHostFirmware(
                    build=0, version_minor=3, version_major=2
                ),
            )
        ]
        # Pad to 16
        for _ in range(15):
            tile_devices.append(
                TileStateDevice(
                    accel_meas=TileAccelMeas(x=0, y=0, z=0),
                    user_x=0.0,
                    user_y=0.0,
                    width=0,
                    height=0,
                    device_version=DeviceStateVersion(vendor=0, product=0),
                    firmware=DeviceStateHostFirmware(
                        build=0, version_minor=0, version_major=0
                    ),
                )
            )

        mock_chain = packets.Tile.StateDeviceChain(
            start_index=0, tile_devices=tile_devices, tile_devices_count=1
        )
        tile_device.connection.request.return_value = mock_chain

        with pytest.raises(
            ValueError, match="Source rectangle .* exceeds tile dimensions"
        ):
            await tile_device.copy_frame_buffer(
                tile_index=0, src_x=7, src_y=7, width=4, height=4
            )

    async def test_copy_frame_buffer_destination_exceeds_dimensions(
        self, tile_device: TileDevice
    ) -> None:
        """Test copy_frame_buffer with exceeding destination rectangle."""
        # Mock tile chain
        from lifx.protocol.protocol_types import (
            DeviceStateHostFirmware,
            DeviceStateVersion,
            TileAccelMeas,
            TileStateDevice,
        )

        tile_devices = [
            TileStateDevice(
                accel_meas=TileAccelMeas(x=0, y=0, z=0),
                user_x=0.0,
                user_y=0.0,
                width=8,
                height=8,
                device_version=DeviceStateVersion(vendor=1, product=27),
                firmware=DeviceStateHostFirmware(
                    build=0, version_minor=3, version_major=2
                ),
            )
        ]
        # Pad to 16
        for _ in range(15):
            tile_devices.append(
                TileStateDevice(
                    accel_meas=TileAccelMeas(x=0, y=0, z=0),
                    user_x=0.0,
                    user_y=0.0,
                    width=0,
                    height=0,
                    device_version=DeviceStateVersion(vendor=0, product=0),
                    firmware=DeviceStateHostFirmware(
                        build=0, version_minor=0, version_major=0
                    ),
                )
            )

        mock_chain = packets.Tile.StateDeviceChain(
            start_index=0, tile_devices=tile_devices, tile_devices_count=1
        )
        tile_device.connection.request.return_value = mock_chain

        with pytest.raises(
            ValueError, match="Destination rectangle .* exceeds tile dimensions"
        ):
            await tile_device.copy_frame_buffer(
                tile_index=0, dst_x=7, dst_y=7, width=4, height=4
            )

    async def test_set_morph_effect(self, tile_device: TileDevice) -> None:
        """Test setting morph effect."""
        # Mock SET operation returns True
        tile_device.connection.request.return_value = True

        palette = [
            HSBK.from_rgb(255, 0, 0),
            HSBK.from_rgb(0, 255, 0),
            HSBK.from_rgb(0, 0, 255),
        ]
        await tile_device.set_morph_effect(palette, speed=5.0, duration=60.0)

        # Verify packet was sent
        tile_device.connection.request.assert_called_once()
        call_args = tile_device.connection.request.call_args
        packet = call_args[0][0]

        # Verify packet has correct values
        assert packet.settings.effect_type == TileEffectType.MORPH
        assert packet.settings.speed == 5000
        assert packet.settings.duration == 60_000_000_000  # 60 seconds in nanoseconds

    async def test_set_morph_effect_invalid_palette(
        self, tile_device: TileDevice
    ) -> None:
        """Test that invalid palette raises error."""
        # Too few colors
        with pytest.raises(ValueError, match="at least 2 colors"):
            await tile_device.set_morph_effect([HSBK(0, 0, 1.0, 3500)])

        # Too many colors
        palette = [HSBK(0, 0, 1.0, 3500) for _ in range(17)]
        with pytest.raises(ValueError, match="too large"):
            await tile_device.set_morph_effect(palette)

    async def test_set_flame_effect(self, tile_device: TileDevice) -> None:
        """Test setting flame effect."""
        # Mock SET operation returns True
        tile_device.connection.request.return_value = True

        await tile_device.set_flame_effect(speed=3.0)

        # Verify packet was sent
        tile_device.connection.request.assert_called_once()
        call_args = tile_device.connection.request.call_args
        packet = call_args[0][0]

        # Verify packet has correct values
        assert packet.settings.effect_type == TileEffectType.FLAME
        assert packet.settings.speed == 3000

    async def test_set_flame_effect_custom_palette(
        self, tile_device: TileDevice
    ) -> None:
        """Test setting flame effect with custom palette."""
        # Mock SET operation returns True
        tile_device.connection.request.return_value = True

        custom_palette = [
            HSBK.from_rgb(255, 0, 0),
            HSBK.from_rgb(255, 128, 0),
        ]
        await tile_device.set_flame_effect(speed=5.0, palette=custom_palette)

        # Verify packet was sent
        tile_device.connection.request.assert_called_once()
        call_args = tile_device.connection.request.call_args
        packet = call_args[0][0]

        assert packet.settings.effect_type == TileEffectType.FLAME
        assert packet.settings.palette_count == 2

    async def test_set_sky_effect_with_parameters(
        self, tile_device: TileDevice
    ) -> None:
        """Test setting sky effect with TileEffectParameter (cloud saturation)."""
        # Mock SET operation returns True
        tile_device.connection.request.return_value = True

        palette = [
            HSBK.from_rgb(255, 0, 0),
            HSBK.from_rgb(0, 255, 0),
        ]

        # Create effect with custom parameters for SKY effect
        effect = TileEffect(
            effect_type=TileEffectType.SKY,
            speed=5000,
            duration=0,
            palette=palette,
            parameters=[
                int(TileEffectSkyType.SUNSET),  # sky_type
                100,  # cloud_saturation_min
                200,  # cloud_saturation_max
            ],
        )

        await tile_device.set_tile_effect(effect)

        # Verify packet was sent
        tile_device.connection.request.assert_called_once()
        call_args = tile_device.connection.request.call_args
        packet = call_args[0][0]

        # Verify packet has correct effect type and parameters
        assert packet.settings.effect_type == TileEffectType.SKY
        assert packet.settings.speed == 5000
        assert packet.settings.palette_count == 2

        # Verify TileEffectParameter is correctly set
        assert packet.settings.parameter.sky_type == TileEffectSkyType.SUNSET
        assert packet.settings.parameter.cloud_saturation_min == 100
        assert packet.settings.parameter.cloud_saturation_max == 200


class TestTileRect:
    """Tests for TileRect class."""

    def test_create_rect(self) -> None:
        """Test creating a tile rectangle."""
        rect = TileRect(x=2, y=3, width=4, height=5)
        assert rect.x == 2
        assert rect.y == 3
        assert rect.width == 4
        assert rect.height == 5

    def test_rect_pixel_count(self) -> None:
        """Test pixel count calculation."""
        rect = TileRect(x=0, y=0, width=8, height=8)
        assert rect.pixel_count == 64

    def test_rect_contains_point(self) -> None:
        """Test point containment check."""
        rect = TileRect(x=2, y=2, width=4, height=4)
        assert rect.contains_point(2, 2)  # Top-left corner
        assert rect.contains_point(5, 5)  # Bottom-right corner (inside)
        assert not rect.contains_point(6, 6)  # Outside
        assert not rect.contains_point(1, 2)  # Left of rect
        assert not rect.contains_point(2, 1)  # Above rect

    def test_rect_invalid_coordinates(self) -> None:
        """Test that negative coordinates raise error."""
        with pytest.raises(ValueError, match="non-negative"):
            TileRect(x=-1, y=0, width=4, height=4)

        with pytest.raises(ValueError, match="non-negative"):
            TileRect(x=0, y=-1, width=4, height=4)

    def test_rect_invalid_dimensions(self) -> None:
        """Test that invalid dimensions raise error."""
        with pytest.raises(ValueError, match="positive"):
            TileRect(x=0, y=0, width=0, height=4)

        with pytest.raises(ValueError, match="positive"):
            TileRect(x=0, y=0, width=4, height=0)


class TestTileEffect:
    """Tests for TileEffect class."""

    def test_create_effect(self) -> None:
        """Test creating a tile effect."""
        effect = TileEffect(
            effect_type=TileEffectType.MORPH,
            speed=5000,
            duration=0,
        )
        assert effect.effect_type == TileEffectType.MORPH
        assert effect.speed == 5000
        assert effect.duration == 0
        assert len(effect.palette) == 1  # Default palette
        assert len(effect.parameters) == 3  # Default parameters

    def test_create_effect_with_palette(self) -> None:
        """Test creating effect with custom palette."""
        palette = [HSBK(0, 1.0, 1.0, 3500), HSBK(120, 1.0, 1.0, 3500)]
        effect = TileEffect(
            effect_type=TileEffectType.MORPH,
            speed=5000,
            duration=0,
            palette=palette,
        )
        assert len(effect.palette) == 2
        assert effect.palette[0].hue == 0
        assert effect.palette[1].hue == 120


class TestTileInfo:
    """Tests for TileInfo class."""

    def test_create_tile_info(self) -> None:
        """Test creating tile info."""
        info = TileInfo(
            accel_meas_x=0,
            accel_meas_y=0,
            accel_meas_z=0,
            user_x=1.0,
            user_y=2.0,
            width=8,
            height=8,
            device_version_vendor=1,
            device_version_product=27,
            device_version_version=1,
            firmware_build=1234567890,
            firmware_version_minor=3,
            firmware_version_major=2,
        )
        assert info.width == 8
        assert info.height == 8
        assert info.user_x == 1.0
        assert info.user_y == 2.0
