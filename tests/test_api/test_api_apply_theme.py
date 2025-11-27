"""Tests for DeviceGroup.apply_theme() method.

This module tests high-level theme application on DeviceGroup:
- apply_theme() - Apply a theme to all devices in the group
- Theme distribution across different device types
- Power on and duration parameter propagation
"""

from __future__ import annotations

import asyncio

from lifx.api import DeviceGroup
from lifx.theme import ThemeLibrary


class TestDeviceGroupApplyTheme:
    """Test DeviceGroup.apply_theme() method."""

    async def test_apply_theme_basic(self, emulator_devices: DeviceGroup) -> None:
        """Test applying a theme to all devices."""
        group = emulator_devices

        async with group:
            theme = ThemeLibrary.get("evening")
            await group.apply_theme(theme)

            # Verify theme was applied (check one device)
            await asyncio.sleep(0.1)  # Give time for updates
            device = group.lights[0]
            color, _, _ = await device.get_color()
            # Evening theme colors are warm (hue 30-40)
            assert 25 <= color.hue <= 45, f"Hue {color.hue} not in evening theme range"

    async def test_apply_theme_with_power_on(
        self, emulator_devices: DeviceGroup
    ) -> None:
        """Test applying a theme with power_on=True."""
        group = emulator_devices

        async with group:
            theme = ThemeLibrary.get("christmas")
            await group.apply_theme(theme, power_on=True)

            # Verify power is on and theme was applied
            await asyncio.sleep(0.1)
            device = group.lights[0]
            power_level = await device.get_power()
            assert power_level == 65535

    async def test_apply_theme_with_duration(
        self, emulator_devices: DeviceGroup
    ) -> None:
        """Test applying a theme with transition duration."""
        group = emulator_devices

        async with group:
            theme = ThemeLibrary.get("halloween")
            # Should not raise
            await group.apply_theme(theme, duration=1.5)

            await asyncio.sleep(0.1)
            # Verify devices received the command
            device = group.lights[0]
            color, _, _ = await device.get_color()
            assert color is not None

    async def test_apply_theme_to_multizone(
        self, emulator_devices: DeviceGroup
    ) -> None:
        """Test that theme is applied to multizone lights."""
        group = emulator_devices

        if len(group.multizone_lights) == 0:
            # Skip if no multizone lights
            return

        async with group:
            theme = ThemeLibrary.get("christmas")
            await group.apply_theme(theme)

            await asyncio.sleep(0.1)
            # Verify multizone light was updated
            multizone = group.multizone_lights[0]
            # Get zone count to verify device is responsive
            zone_count = await multizone.get_zone_count()
            assert zone_count > 0
            await multizone.connection.close()

    async def test_apply_theme_to_tiles(self, emulator_devices: DeviceGroup) -> None:
        """Test that theme is applied to tile devices."""
        group = emulator_devices

        if len(group.matrix_lights) == 0:
            # Skip if no tile devices
            return

        async with group:
            theme = ThemeLibrary.get("dream")
            await group.apply_theme(theme)

            await asyncio.sleep(0.1)
            # Verify tile device was updated
            tile = group.matrix_lights[0]
            # Get tile chain to verify device is responsive
            tiles_info = await tile.get_device_chain()
            assert len(tiles_info) > 0
            await tile.connection.close()

    async def test_apply_different_themes(self, emulator_devices: DeviceGroup) -> None:
        """Test applying different themes to the group."""
        group = emulator_devices

        themes_to_test = ["evening", "christmas", "halloween", "relaxing", "dream"]

        async with group:
            for theme_name in themes_to_test:
                theme = ThemeLibrary.get(theme_name)
                await group.apply_theme(theme)
                await asyncio.sleep(0.05)  # Brief delay between theme changes

                # Verify at least one device is updated
                device = group.lights[0]
                color, _, _ = await device.get_color()
                assert color is not None

    async def test_apply_theme_empty_group(self) -> None:
        """Test apply_theme on empty device group."""
        group = DeviceGroup([])

        assert len(group) == 0

        # Should not raise on empty group
        async with group:
            theme = ThemeLibrary.get("evening")
            await group.apply_theme(theme)
            await group.apply_theme(theme, power_on=True)
            await group.apply_theme(theme, duration=1.0)

    async def test_apply_theme_mixed_devices(
        self, emulator_devices: DeviceGroup
    ) -> None:
        """Test apply_theme works correctly with heterogeneous device types."""
        group = emulator_devices

        # Should have mix of device types from emulator
        assert len(group.lights) > 0
        assert len(group.multizone_lights) > 0
        assert len(group.matrix_lights) > 0

        async with group:
            theme = ThemeLibrary.get("relaxing")
            await group.apply_theme(theme, power_on=True, duration=0.5)

            await asyncio.sleep(0.1)

            # Verify at least one light was updated
            light = group.lights[0]
            power_level = await light.get_power()
            assert power_level == 65535

            # Verify at least one multizone was updated
            multizone = group.multizone_lights[0]
            zone_count = await multizone.get_zone_count()
            assert zone_count > 0

    async def test_apply_theme_all_library_themes(
        self, emulator_devices: DeviceGroup
    ) -> None:
        """Test that all library themes can be applied without error."""
        group = emulator_devices

        async with group:
            theme_names = ThemeLibrary.list()

            # Test a subset to keep test time reasonable
            for theme_name in theme_names[:10]:
                theme = ThemeLibrary.get(theme_name)
                await group.apply_theme(theme)
                await asyncio.sleep(0.05)

    async def test_apply_theme_concurrent_groups(self) -> None:
        """Test applying themes to multiple groups concurrently."""
        # Create two empty groups (we can't easily create multiple hardware devices)
        group1 = DeviceGroup([])
        group2 = DeviceGroup([])

        async with group1, group2:
            theme1 = ThemeLibrary.get("evening")
            theme2 = ThemeLibrary.get("christmas")

            # Apply themes concurrently
            await asyncio.gather(
                group1.apply_theme(theme1),
                group2.apply_theme(theme2),
            )

    async def test_apply_theme_with_all_parameters(
        self, emulator_devices: DeviceGroup
    ) -> None:
        """Test apply_theme with all parameters specified."""
        group = emulator_devices

        async with group:
            theme = ThemeLibrary.get("spacey")
            await group.apply_theme(theme, power_on=True, duration=2.0)

            await asyncio.sleep(0.1)
            # Verify operation completed successfully
            device = group.lights[0]
            power_level = await device.get_power()
            assert power_level == 65535

    async def test_apply_theme_sequential_calls(
        self, emulator_devices: DeviceGroup
    ) -> None:
        """Test applying multiple themes sequentially."""
        group = emulator_devices

        async with group:
            themes = ["evening", "christmas", "halloween"]

            for theme_name in themes:
                theme = ThemeLibrary.get(theme_name)
                await group.apply_theme(theme)
                await asyncio.sleep(0.05)

            # Verify last theme was applied
            device = group.lights[0]
            color, _, _ = await device.get_color()
            # Halloween theme has orange colors (hue ~30-35)
            assert 25 <= color.hue <= 40

    async def test_apply_theme_only_lights(self) -> None:
        """Test apply_theme on group with only lights."""
        from lifx.devices.light import Light

        light1 = Light(serial="d073d5010001", ip="192.168.1.1", port=56700)
        light2 = Light(serial="d073d5010002", ip="192.168.1.2", port=56700)
        group = DeviceGroup([light1, light2])

        # Should only iterate lights, skip multizone/tiles
        assert len(group.lights) == 2
        assert len(group.multizone_lights) == 0
        assert len(group.matrix_lights) == 0

        # Theme application should handle this gracefully
        async with group:
            theme = ThemeLibrary.get("relaxing")
            # Should not raise even with no connections
            # (will fail at connection level, but our method works)
            try:
                await asyncio.wait_for(group.apply_theme(theme), timeout=0.1)
            except TimeoutError:
                # Expected - no real devices
                pass

    async def test_apply_theme_duration_zero(
        self, emulator_devices: DeviceGroup
    ) -> None:
        """Test apply_theme with zero duration (instant change)."""
        group = emulator_devices

        async with group:
            theme = ThemeLibrary.get("evening")
            await group.apply_theme(theme, duration=0.0)

            # Verify change was instant
            await asyncio.sleep(0.05)
            device = group.lights[0]
            color, _, _ = await device.get_color()
            assert color in theme.colors

    async def test_apply_theme_large_duration(
        self, emulator_devices: DeviceGroup
    ) -> None:
        """Test apply_theme with large duration (slow transition)."""
        group = emulator_devices

        async with group:
            theme = ThemeLibrary.get("peaceful")
            # Should accept large duration values
            await group.apply_theme(theme, duration=5.0)

            await asyncio.sleep(5.5)
            # Verify command was sent
            device = group.lights[0]
            color, _, _ = await device.get_color()
            assert color in theme
