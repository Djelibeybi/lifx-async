"""Tests for MatrixLight device class."""

from __future__ import annotations

import pytest

from lifx.color import HSBK, Colors
from lifx.devices.matrix import MatrixEffect, MatrixLight, TileInfo
from lifx.protocol.protocol_types import FirmwareEffect, TileEffectSkyType


class TestMatrixLight:
    """Tests for MatrixLight class."""

    def test_create_matrix_light(self) -> None:
        """Test creating a matrix light device."""
        matrix = MatrixLight(
            serial="d073d5010203",
            ip="192.168.1.100",
            port=56700,
        )
        assert matrix.serial == "d073d5010203"
        assert matrix.ip == "192.168.1.100"
        assert matrix.port == 56700

    async def test_get_device_chain(self, emulator_devices) -> None:
        """Test getting device chain from emulator."""
        matrix = emulator_devices[6]  # TileDevice/MatrixLight at index 6
        async with matrix:
            chain = await matrix.get_device_chain()
            assert isinstance(chain, list)
            assert len(chain) > 0
            assert all(isinstance(tile, TileInfo) for tile in chain)

            # Check first tile has valid dimensions
            assert chain[0].width > 0
            assert chain[0].height > 0
            assert chain[0].total_zones == chain[0].width * chain[0].height

    async def test_get_device_chain_single_tile(self, emulator_devices) -> None:
        """Test common single-tile case."""
        matrix = emulator_devices[6]
        async with matrix:
            chain = await matrix.get_device_chain()
            # Most MatrixLight devices have a single tile
            assert len(chain) >= 1

            # Verify tile_index matches position in chain
            for i, tile in enumerate(chain):
                assert tile.tile_index == i

    async def test_device_chain_cached_property(self, emulator_devices) -> None:
        """Test device_chain property caching."""
        matrix = emulator_devices[6]

        async with matrix:
            # After setup (which calls get_device_chain), should be cached
            assert matrix.device_chain is not None
            assert isinstance(matrix.device_chain, list)
            # Verify it returns the same instance on subsequent accesses
            cached_chain = matrix.device_chain
            assert matrix.device_chain is cached_chain

    async def test_tile_count_property(self, emulator_devices) -> None:
        """Test tile_count property."""
        matrix = emulator_devices[6]

        async with matrix:
            # After setup (which calls get_device_chain), tile_count should be available
            assert matrix.tile_count is not None
            assert matrix.tile_count > 0
            assert matrix.tile_count == len(matrix.device_chain)
            # Verify count is consistent
            assert matrix.tile_count == len(await matrix.get_device_chain())

    async def test_get64_single_tile(self, emulator_devices) -> None:
        """Test getting colors from 8x8 tile (64 zones) with default parameters."""
        matrix = emulator_devices[6]
        async with matrix:
            chain = await matrix.get_device_chain()
            tile = chain[0]

            # Verify tile dimensions
            assert tile.width == 8
            assert tile.height == 8
            assert tile.total_zones == 64

            # Get colors using default parameters (no args needed)
            colors = await matrix.get64()

            assert isinstance(colors, list)
            assert len(colors) == 64  # Returns actual number of zones
            assert all(isinstance(color, HSBK) for color in colors)

    async def test_set64_single_tile(self, emulator_devices) -> None:
        """Test setting colors on 8x8 tile (64 zones)."""
        matrix = emulator_devices[6]
        async with matrix:
            chain = await matrix.get_device_chain()
            tile = chain[0]

            # Set all zones to red
            zone_count = tile.width * tile.height
            red_colors = [Colors.RED] * min(zone_count, 64)

            await matrix.set64(
                tile_index=0,
                length=1,
                x=0,
                y=0,
                width=tile.width,
                duration=0,
                colors=red_colors,
            )

            # Verify colors were set (read back)
            colors = await matrix.get64()

            # First color should be red (allow protocol conversion tolerance)
            assert colors[0].hue < 10 or colors[0].hue > 350  # Red ~0 deg
            assert colors[0].saturation > 0.9  # High saturation

    async def test_set_matrix_colors_convenience(self, emulator_devices) -> None:
        """Test convenience method for setting all tile colors."""
        matrix = emulator_devices[6]
        async with matrix:
            chain = await matrix.get_device_chain()
            tile = chain[0]

            # Create gradient colors
            zone_count = tile.total_zones
            gradient = [
                HSBK(i * 360 / zone_count, 1.0, 1.0, 3500) for i in range(zone_count)
            ]

            # Set all colors at once
            await matrix.set_matrix_colors(tile_index=0, colors=gradient, duration=0)

            # Verify first few colors (partial verification to avoid test complexity)
            colors = await matrix.get64()
            assert len(colors) > 0

    async def test_set_matrix_colors_solid_color(self, emulator_devices) -> None:
        """Test setting all zones to same color uses SetColor packet.

        When all zones are set to the same color, set_matrix_colors should
        use the SetColor packet instead of set64, which is much more efficient.

        Requires emulator 2.3.1+ which supports SetColor for matrix devices.
        """
        matrix = emulator_devices[6]
        async with matrix:
            chain = await matrix.get_device_chain()
            tile = chain[0]

            # Create solid red across all zones
            red_colors = [Colors.RED] * tile.total_zones

            # Set all zones to red (should use SetColor packet)
            await matrix.set_matrix_colors(tile_index=0, colors=red_colors, duration=0)

            # Verify the color was set by reading back
            colors = await matrix.get64()

            # Verify first zone is red
            assert colors[0].hue == 0
            assert colors[0].saturation == 1.0
            assert colors[0].brightness == 1.0

    async def test_get_effect(self, emulator_devices) -> None:
        """Test getting current tile effect."""
        matrix = emulator_devices[6]
        async with matrix:
            effect = await matrix.get_effect()

            assert isinstance(effect, MatrixEffect)
            assert isinstance(effect.effect_type, FirmwareEffect)
            assert effect.speed >= 0
            assert effect.duration >= 0
            # Palette can be None if palette_count is 0
            if effect.palette is not None:
                assert len(effect.palette) > 0

    async def test_tile_effect_cached_property(self, emulator_devices) -> None:
        """Test tile_effect property caching."""
        matrix = emulator_devices[6]
        async with matrix:
            # Fetch tile effect
            effect = await matrix.get_effect()

            # Should be cached in property
            assert matrix.tile_effect is not None
            assert isinstance(matrix.tile_effect, MatrixEffect)
            assert matrix.tile_effect == effect

    async def test_set_effect_morph(self, emulator_devices) -> None:
        """Test setting MORPH effect."""
        matrix = emulator_devices[6]
        async with matrix:
            # Create rainbow palette
            rainbow = [
                Colors.RED,  # Red
                Colors.YELLOW,  # Yellow
                Colors.GREEN,  # Green
                Colors.BLUE,  # Blue
            ]

            await matrix.set_effect(
                effect_type=FirmwareEffect.MORPH,
                speed=5000,
                palette=rainbow,
            )

            # Verify effect was set
            effect = await matrix.get_effect()
            assert effect.effect_type == FirmwareEffect.MORPH
            assert len(effect.palette) == 4

    async def test_set_effect_flame(self, emulator_devices) -> None:
        """Test setting FLAME effect."""
        matrix = emulator_devices[6]
        async with matrix:
            # Flame effect with fire colors
            fire_palette = [
                Colors.RED,  # Red
                HSBK(hue=16, saturation=1.0, brightness=1.0, kelvin=3500),
                Colors.ORANGE,  # Orange
                HSBK(hue=51, saturation=1.0, brightness=1.0, kelvin=3500),
            ]

            await matrix.set_effect(
                effect_type=FirmwareEffect.FLAME,
                speed=3000,
                palette=fire_palette,
            )

            # Verify effect was set
            effect = await matrix.get_effect()
            assert effect.effect_type == FirmwareEffect.FLAME

    async def test_set_effect_sky_sunrise(self, ceiling_device) -> None:
        """Test setting SKY effect with SUNRISE.

        SKY effects are only supported on LIFX Ceiling devices
        (product IDs 176, 177, 201, 202) with firmware 4.4+.
        This test uses a Ceiling device created via the emulator API.
        """
        matrix = ceiling_device
        async with matrix:
            await matrix.set_effect(
                effect_type=FirmwareEffect.SKY,
                speed=2000,
                sky_type=TileEffectSkyType.SUNRISE,
            )

            # Verify effect was set
            effect = await matrix.get_effect()
            assert effect.effect_type == FirmwareEffect.SKY
            assert effect.sky_type == TileEffectSkyType.SUNRISE

    async def test_set_effect_sky_sunset(self, ceiling_device) -> None:
        """Test setting SKY effect with SUNSET.

        SKY effects are only supported on LIFX Ceiling devices
        (product IDs 176, 177, 201, 202) with firmware 4.4+.
        This test uses a Ceiling device created via the emulator API.
        """
        matrix = ceiling_device
        async with matrix:
            await matrix.set_effect(
                effect_type=FirmwareEffect.SKY,
                speed=2000,
                sky_type=TileEffectSkyType.SUNSET,
            )

            # Verify effect was set
            effect = await matrix.get_effect()
            assert effect.effect_type == FirmwareEffect.SKY
            assert effect.sky_type == TileEffectSkyType.SUNSET

    async def test_set_effect_sky_clouds(self, ceiling_device) -> None:
        """Test setting SKY effect with CLOUDS and saturation parameters.

        SKY effects are only supported on LIFX Ceiling devices
        (product IDs 176, 177, 201, 202) with firmware 4.4+.
        This test uses a Ceiling device created via the emulator API.
        """
        matrix = ceiling_device
        async with matrix:
            await matrix.set_effect(
                effect_type=FirmwareEffect.SKY,
                speed=4000,
                sky_type=TileEffectSkyType.CLOUDS,
                cloud_saturation_min=50,
                cloud_saturation_max=200,
            )

            # Verify effect was set
            effect = await matrix.get_effect()
            assert effect.effect_type == FirmwareEffect.SKY
            assert effect.sky_type == TileEffectSkyType.CLOUDS
            assert effect.cloud_saturation_min == 50
            assert effect.cloud_saturation_max == 200

    async def test_set_effect_off(self, emulator_devices) -> None:
        """Test turning off tile effect."""
        matrix = emulator_devices[6]
        async with matrix:
            # First set an effect
            await matrix.set_effect(
                effect_type=FirmwareEffect.MORPH,
                speed=3000,
            )

            # Then turn it off
            await matrix.set_effect(
                effect_type=FirmwareEffect.OFF,
                speed=0,
            )

            # Verify effect was turned off
            effect = await matrix.get_effect()
            assert effect.effect_type == FirmwareEffect.OFF

    async def test_copy_frame_buffer(self, emulator_devices) -> None:
        """Test copy_frame_buffer() copies frame buffer between tiles."""
        matrix = emulator_devices[6]
        async with matrix:
            chain = await matrix.get_device_chain()
            tile = chain[0]

            # Set initial state on display buffer (fb_index=0) - all white
            white_colors = [HSBK(0, 0, 1.0, 3500)] * 64
            await matrix.set64(
                tile_index=0,
                length=1,
                x=0,
                y=0,
                width=tile.width,
                duration=0,
                colors=white_colors,
                fb_index=0,  # Display buffer
            )

            # Verify initial state is white
            initial_colors = await matrix.get64()
            assert initial_colors[0].saturation == 0.0  # White has no saturation
            assert initial_colors[0].brightness == 1.0

            # Set different pattern on temp buffer (fb_index=1) - all red
            red_colors = [Colors.RED] * 64
            await matrix.set64(
                tile_index=0,
                length=1,
                x=0,
                y=0,
                width=tile.width,
                duration=0,
                colors=red_colors,
                fb_index=1,  # Temp buffer
            )

            # Display buffer should still be white (not affected by fb_index=1)
            display_colors = await matrix.get64()
            assert display_colors[0].saturation == 0.0  # Still white

            # Copy temp buffer (fb_index=1) to display buffer (fb_index=0)
            await matrix.copy_frame_buffer(tile_index=0, source_fb=1, target_fb=0)

            # Now display buffer should be red (copied from fb_index=1)
            copied_colors = await matrix.get64()
            assert copied_colors[0].hue == 0  # Red
            assert copied_colors[0].saturation == 1.0
            assert copied_colors[0].brightness == 1.0

    async def test_copy_frame_buffer_with_length(self, emulator_devices) -> None:
        """Test copy_frame_buffer() with explicit length parameter."""
        matrix = emulator_devices[6]
        async with matrix:
            chain = await matrix.get_device_chain()
            tile = chain[0]

            # Set pattern on temp buffer (fb_index=1)
            blue_colors = [Colors.BLUE] * 64
            await matrix.set64(
                tile_index=0,
                length=1,
                x=0,
                y=0,
                width=tile.width,
                duration=0,
                colors=blue_colors,
                fb_index=1,
            )

            # Copy with explicit length=1 (same as default behavior)
            await matrix.copy_frame_buffer(
                tile_index=0, source_fb=1, target_fb=0, length=1
            )

            # Verify the copy worked
            copied_colors = await matrix.get64()
            assert copied_colors[0].hue == 240  # Blue
            assert copied_colors[0].saturation == 1.0
            assert copied_colors[0].brightness == 1.0

    async def test_set_effect_without_palette(self, emulator_devices) -> None:
        """Test setting effect without a palette (palette_count=0)."""
        matrix = emulator_devices[6]
        async with matrix:
            # Set effect without palette - should send palette_count=0
            await matrix.set_effect(
                effect_type=FirmwareEffect.MORPH,
                speed=3000,
            )

            # Verify effect was set
            effect = await matrix.get_effect()
            assert effect.effect_type == FirmwareEffect.MORPH
            assert effect.palette is None

    async def test_get64_large_tile(self, ceiling_device) -> None:
        """Test getting colors from 16x8 tile (128 zones) with default parameters.

        Ceiling devices have 16x8 tiles with 128 zones. The get64() method returns
        up to 64 colors due to protocol limitations, so we have to send two get64
        requests.
        """
        matrix = ceiling_device
        async with matrix:
            chain = await matrix.get_device_chain()
            tile = chain[0]

            # Verify this is a 128-zone tile
            assert tile.width == 16
            assert tile.height == 8
            assert tile.total_zones == 128

            # Get zones using two get64 requests, 64 zones per request.
            colors: list[HSBK] = []
            colors.extend(await matrix.get64())
            colors.extend(await matrix.get64(y=4))

            assert isinstance(colors, list)
            assert len(colors) == 128
            assert all(isinstance(color, HSBK) for color in colors)

    async def test_set64_large_tile(self, ceiling_device) -> None:
        """Test setting colors on 16x8 tile (128 zones) using frame buffer.

        For tiles with >64 zones, set64 writes to a temporary frame buffer (fb_index=1),
        then copy_frame_buffer() copies it to the display buffer (fb_index=0).
        """
        matrix = ceiling_device
        async with matrix:
            chain = await matrix.get_device_chain()
            tile = chain[0]

            # Verify this is a 128-zone tile
            assert tile.total_zones == 128

            # Create 64 blue colors for first 64 zones
            blue_colors = [Colors.BLUE] * 64

            # Create 64 red colors for the second 64 zones
            red_colors = [Colors.RED] * 64

            # Set first 64 zones to blue (on frame buffer 1)
            await matrix.set64(
                tile_index=0,
                length=1,
                x=0,
                y=0,
                width=tile.width,
                duration=0,
                colors=blue_colors,
                fb_index=1,  # Write to temp buffer
            )

            # Set the second 64 zones to red (on frame buffer 1)
            await matrix.set64(
                tile_index=0,
                length=1,
                x=0,
                y=4,
                width=tile.width,
                duration=0,
                colors=red_colors,
                fb_index=1,  # Write to temp buffer
            )

            # Copy frame buffer 1 to frame buffer 0 (display)
            await matrix.copy_frame_buffer(tile_index=0, source_fb=1, target_fb=0)

            # Get the updated colors
            colors: list[HSBK] = []
            colors.extend(await matrix.get64())
            colors.extend(await matrix.get64(y=4))

            # Verify the colors were set correctly
            assert len(colors) == 128
            # Blue is hue ~240
            assert 230 < colors[0].hue < 250
            assert colors[0].saturation > 0.9  # High saturation
            assert colors[0].brightness > 0.9  # Full brightness
            # Red is hue ~0
            assert colors[64].hue == 0
            assert colors[64].saturation == 1.0
            assert colors[64].brightness == 1.0

    async def test_set_matrix_colors_large_tile(self, ceiling_device) -> None:
        """Test setting all colors on 16x8 tile (128 zones) set_matrix_colors()

        This tests the automatic frame buffer strategy for tiles with >64 zones.
        The method should automatically batch the colors and use the frame buffer.
        Uses a gradient to ensure set64 path is taken (not SetColor).
        """
        matrix = ceiling_device
        async with matrix:
            chain = await matrix.get_device_chain()
            tile = chain[0]

            # Verify this is a 128-zone tile
            assert tile.total_zones == 128

            # Create a gradient (different colors, so uses set64 not SetColor)
            colors = [HSBK(round(i * 360.0 / 128), 1.0, 1.0, 3500) for i in range(128)]

            # Set all 128 zones at once (should use frame buffer strategy)
            # This requires:
            # 1. Batching into two set64 calls (first 64, then next 64)
            # 2. Writing to frame buffer 1
            # 3. Copying frame buffer 1 to frame buffer 0
            await matrix.set_matrix_colors(tile_index=0, colors=colors, duration=0)

            # Verify first 64 zones
            first_half = await matrix.get64()

            assert len(first_half) == 64
            # First zone should be hue 0 (red)
            assert first_half[0].hue < 10 or first_half[0].hue > 350
            assert first_half[0].saturation > 0.9  # High saturation
            assert first_half[0].brightness > 0.9  # Full brightness

            # Verify second 64 zones
            second_half = await matrix.get64(y=4)  # Start at row 4

            assert len(second_half) == 64
            # Zone 64 should be hue ~180 (cyan)
            assert 170 < second_half[0].hue < 190
            assert second_half[0].saturation > 0.9  # High saturation
            assert (
                second_half[0].brightness > 0.9
            )  # Full brightness  # Full brightness  # Full brightness

    async def test_manual_frame_buffer_workflow_large_tile(
        self, ceiling_device
    ) -> None:
        """Test manual frame buffer workflow for 16x8 tile (128 zones).

        This tests the complete manual workflow:
        1. Set initial state (all white) to verify we can change colors
        2. Send two set64() messages to fb_index=1 (non-visible buffer)
        3. Send copy_frame_buffer() to copy fb_index=1 -> fb_index=0
        4. Send two get64() messages to retrieve all 128 zones from fb_index=0
        5. Verify the colors match what we set (blue top half, green bottom half)
        """
        matrix = ceiling_device
        async with matrix:
            chain = await matrix.get_device_chain()
            tile = chain[0]

            # Verify this is a 128-zone tile
            assert tile.width == 16
            assert tile.height == 8
            assert tile.total_zones == 128

            # Step 0: Set initial state to white to ensure we can detect changes
            white_colors = [HSBK(0, 0, 1.0, 3500)] * 128
            await matrix.set_matrix_colors(
                tile_index=0, colors=white_colors, duration=0
            )

            # Create colors: first 64 zones blue, second 64 zones green
            blue_colors = [Colors.BLUE] * 64
            green_colors = [Colors.GREEN] * 64

            # Step 1: Set first 64 zones (rows 0-3) to blue in frame buffer 1
            await matrix.set64(
                tile_index=0,
                length=1,
                x=0,
                y=0,
                width=tile.width,
                duration=0,
                colors=blue_colors,
                fb_index=1,  # Write to non-visible buffer
            )

            # Step 2: Set second 64 zones (rows 4-7) to green in frame buffer 1
            await matrix.set64(
                tile_index=0,
                length=1,
                x=0,
                y=4,  # Start at row 4 (after first 64 zones)
                width=tile.width,
                duration=0,
                colors=green_colors,
                fb_index=1,  # Write to non-visible buffer
            )

            # Step 3: Copy frame buffer 1 to frame buffer 0 (display)
            # This should copy all 128 zones using the tile's width and height
            await matrix.copy_frame_buffer(tile_index=0, source_fb=1, target_fb=0)

            # Step 4: Read back first 64 zones
            first_64_colors = await matrix.get64()

            # Step 5: Read back second 64 zones
            second_64_colors = await matrix.get64(y=4)

            # Verify all 128 zones were retrieved
            assert len(first_64_colors) == 64
            assert len(second_64_colors) == 64

            # Verify first 64 zones are blue (hue ~240)
            assert 230 < first_64_colors[0].hue < 250
            assert first_64_colors[0].saturation > 0.9
            assert first_64_colors[0].brightness > 0.9

            # Verify second 64 zones are green (hue ~120)
            assert 110 < second_64_colors[0].hue < 130
            assert second_64_colors[0].saturation > 0.9
            assert second_64_colors[0].brightness > 0.9


class TestMatrixEffect:
    """Tests for MatrixEffect class."""

    def test_create_valid_effect(self) -> None:
        """Test creating a valid matrix effect."""
        effect = MatrixEffect(
            effect_type=FirmwareEffect.MORPH,
            speed=3000,
            duration=0,
            palette=[HSBK(0, 1.0, 1.0, 3500)],
        )
        assert effect.effect_type == FirmwareEffect.MORPH
        assert effect.speed == 3000
        assert effect.duration == 0
        assert effect.palette is not None
        assert len(effect.palette) == 1

    def test_effect_none_palette(self) -> None:
        """Test that palette can be None (no palette specified)."""
        effect = MatrixEffect(
            effect_type=FirmwareEffect.MORPH,
            speed=3000,
        )
        assert effect.palette is None

    def test_effect_validation_negative_speed(self) -> None:
        """Test that negative speed raises error."""
        with pytest.raises(ValueError, match="speed must be non-negative"):
            MatrixEffect(
                effect_type=FirmwareEffect.OFF,
                speed=-1,
            )

    def test_effect_validation_zero_speed_for_active_effect(self) -> None:
        """Test that zero speed raises error for active effects."""
        with pytest.raises(
            ValueError, match="speed must be positive for active effects"
        ):
            MatrixEffect(
                effect_type=FirmwareEffect.MORPH,
                speed=0,
            )

    def test_effect_validation_zero_speed_for_off(self) -> None:
        """Test that zero speed is valid when effect is OFF."""
        effect = MatrixEffect(
            effect_type=FirmwareEffect.OFF,
            speed=0,
        )
        assert effect.speed == 0
        assert effect.effect_type == FirmwareEffect.OFF

    def test_effect_validation_negative_duration(self) -> None:
        """Test that negative duration raises error."""
        with pytest.raises(ValueError, match="duration must be non-negative"):
            MatrixEffect(
                effect_type=FirmwareEffect.MORPH,
                speed=3000,
                duration=-1,
            )

    def test_effect_validation_empty_palette(self) -> None:
        """Test that empty palette raises error."""
        with pytest.raises(ValueError, match="palette must contain at least one color"):
            MatrixEffect(
                effect_type=FirmwareEffect.MORPH,
                speed=3000,
                palette=[],
            )

    def test_effect_validation_too_many_palette_colors(self) -> None:
        """Test that palette with >16 colors raises error."""
        palette = [HSBK(0, 1.0, 1.0, 3500)] * 17
        with pytest.raises(ValueError, match="at most 16 colors"):
            MatrixEffect(
                effect_type=FirmwareEffect.MORPH,
                speed=3000,
                palette=palette,
            )

    def test_effect_validation_saturation_out_of_range(self) -> None:
        """Test that saturation values out of range raise error."""
        with pytest.raises(ValueError, match="cloud_saturation_min must be in range"):
            MatrixEffect(
                effect_type=FirmwareEffect.SKY,
                speed=3000,
                cloud_saturation_min=256,
            )

        with pytest.raises(ValueError, match="cloud_saturation_max must be in range"):
            MatrixEffect(
                effect_type=FirmwareEffect.SKY,
                speed=3000,
                cloud_saturation_max=-1,
            )


class TestTileInfo:
    """Tests for TileInfo class."""

    def test_tile_info_total_zones(self) -> None:
        """Test total_zones property calculation."""
        from lifx.protocol.protocol_types import (
            DeviceStateHostFirmware,
            DeviceStateVersion,
            TileAccelMeas,
        )
        from lifx.protocol.protocol_types import (
            TileStateDevice as LifxProtocolTileDevice,
        )

        protocol_tile = LifxProtocolTileDevice(
            accel_meas=TileAccelMeas(x=0, y=0, z=0),
            user_x=0.0,
            user_y=0.0,
            width=8,
            height=8,
            supported_frame_buffers=2,
            device_version=DeviceStateVersion(vendor=1, product=27),
            firmware=DeviceStateHostFirmware(
                build=1234567890, version_minor=3, version_major=2
            ),
        )

        tile_info = TileInfo.from_protocol(0, protocol_tile)
        assert tile_info.total_zones == 64

    def test_tile_info_requires_frame_buffer_false(self) -> None:
        """Test requires_frame_buffer for tile with ≤64 zones."""
        from lifx.protocol.protocol_types import (
            DeviceStateHostFirmware,
            DeviceStateVersion,
            TileAccelMeas,
        )
        from lifx.protocol.protocol_types import (
            TileStateDevice as LifxProtocolTileDevice,
        )

        protocol_tile = LifxProtocolTileDevice(
            accel_meas=TileAccelMeas(x=0, y=0, z=0),
            user_x=0.0,
            user_y=0.0,
            width=8,
            height=8,
            supported_frame_buffers=2,
            device_version=DeviceStateVersion(vendor=1, product=27),
            firmware=DeviceStateHostFirmware(
                build=1234567890, version_minor=3, version_major=2
            ),
        )

        tile_info = TileInfo.from_protocol(0, protocol_tile)
        assert not tile_info.requires_frame_buffer

    def test_tile_info_requires_frame_buffer_true(self) -> None:
        """Test requires_frame_buffer for tile with >64 zones."""
        from lifx.protocol.protocol_types import (
            DeviceStateHostFirmware,
            DeviceStateVersion,
            TileAccelMeas,
        )
        from lifx.protocol.protocol_types import (
            TileStateDevice as LifxProtocolTileDevice,
        )

        # 16x8 tile = 128 zones
        protocol_tile = LifxProtocolTileDevice(
            accel_meas=TileAccelMeas(x=0, y=0, z=0),
            user_x=0.0,
            user_y=0.0,
            width=16,
            height=8,
            supported_frame_buffers=2,
            device_version=DeviceStateVersion(vendor=1, product=27),
            firmware=DeviceStateHostFirmware(
                build=1234567890, version_minor=3, version_major=2
            ),
        )

        tile_info = TileInfo.from_protocol(0, protocol_tile)
        assert tile_info.requires_frame_buffer
        assert tile_info.total_zones == 128
