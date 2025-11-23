"""Tests for MultiZoneLight state management using LIFX Emulator."""

from __future__ import annotations

import pytest

from lifx.color import HSBK
from lifx.devices.multizone import MultiZoneLight, MultiZoneLightState


class TestMultiZoneLightStateManagement:
    """Tests for MultiZoneLight state management using emulator."""

    @pytest.mark.asyncio
    async def test_multizone_state_property_before_init_raises(
        self, emulator_devices
    ) -> None:
        """Test accessing state property before initialization raises RuntimeError."""
        multizone_light: MultiZoneLight = emulator_devices[4]  # d073d5000005

        # State is None before using Device.connect()
        with pytest.raises(RuntimeError, match="State not found."):
            _ = multizone_light.state

    @pytest.mark.asyncio
    async def test_initialize_state_creates_multizone_state(
        self, emulator_devices
    ) -> None:
        """Test Device.connect() creates MultiZoneLightState instance."""
        template: MultiZoneLight = emulator_devices[4]  # d073d5000005

        # Use Device.connect() to get a properly initialized device
        async with await MultiZoneLight.connect(
            serial=template.serial, ip=template.ip, port=template.port
        ) as multizone_light:
            # Verify state is MultiZoneLightState
            assert multizone_light._state is not None
            assert isinstance(multizone_light._state, MultiZoneLightState)
            assert isinstance(multizone_light._state.label, str)
            assert isinstance(multizone_light._state.power, int)
            assert hasattr(multizone_light._state, "zones")
            assert hasattr(multizone_light._state, "zone_count")

    @pytest.mark.asyncio
    async def test_state_property_after_init_returns_multizone_state(
        self, emulator_devices
    ) -> None:
        """Test state property returns MultiZoneLightState after initialization."""
        template: MultiZoneLight = emulator_devices[4]  # d073d5000005

        async with await MultiZoneLight.connect(
            serial=template.serial, ip=template.ip, port=template.port
        ) as multizone_light:
            # Access state property
            state = multizone_light.state
            assert isinstance(state, MultiZoneLightState)
            assert isinstance(state.label, str)
            assert hasattr(state, "zones")
            assert hasattr(state, "zone_count")

    @pytest.mark.asyncio
    async def test_refresh_state_updates_zones(self, emulator_devices) -> None:
        """Test refresh_state() updates zone colors."""
        template: MultiZoneLight = emulator_devices[4]  # d073d5000005

        async with await MultiZoneLight.connect(
            serial=template.serial, ip=template.ip, port=template.port
        ) as multizone_light:
            assert isinstance(multizone_light, MultiZoneLight)

            # Set zones to a specific color
            zone_count = await multizone_light.get_zone_count()
            await multizone_light.set_color_zones(
                0,
                zone_count - 1,
                HSBK(hue=120, saturation=1.0, brightness=0.5, kelvin=3500),
            )

            # Refresh state
            await multizone_light.refresh_state()

            # Zones should be updated
            assert multizone_light.state.zones is not None
            assert len(multizone_light.state.zones) > 0

    @pytest.mark.asyncio
    async def test_get_zone_count_updates_state(self, emulator_devices) -> None:
        """Test get_zone_count() updates state when it exists."""
        template: MultiZoneLight = emulator_devices[4]  # d073d5000005

        async with await MultiZoneLight.connect(
            serial=template.serial, ip=template.ip, port=template.port
        ) as multizone_light:
            assert isinstance(multizone_light, MultiZoneLight)

            # Get zone count
            zone_count = await multizone_light.get_zone_count()

            # State should be updated
            assert multizone_light.state.zone_count == zone_count
            assert zone_count > 0

    @pytest.mark.asyncio
    async def test_get_color_zones_updates_state(self, emulator_devices) -> None:
        """Test get_color_zones() updates state when it exists."""
        template: MultiZoneLight = emulator_devices[4]  # d073d5000005

        async with await MultiZoneLight.connect(
            serial=template.serial, ip=template.ip, port=template.port
        ) as multizone_light:
            assert isinstance(multizone_light, MultiZoneLight)

            # Get zone colors
            zone_count = await multizone_light.get_zone_count()
            zones = await multizone_light.get_color_zones(0, zone_count - 1)

            # State should be updated
            assert multizone_light.state.zones is not None
            assert len(multizone_light.state.zones) == len(zones)

    @pytest.mark.asyncio
    async def test_get_all_color_zones_updates_state(self, emulator_devices) -> None:
        """Test get_all_color_zones() updates state."""
        template: MultiZoneLight = emulator_devices[4]  # d073d5000005

        async with await MultiZoneLight.connect(
            serial=template.serial, ip=template.ip, port=template.port
        ) as multizone_light:
            assert isinstance(multizone_light, MultiZoneLight)

            # Get all zone colors
            zones = await multizone_light.get_all_color_zones()

            # State should be updated
            assert multizone_light.state.zones is not None
            assert len(multizone_light.state.zones) == len(zones)
            assert len(zones) == multizone_light.state.zone_count

    @pytest.mark.asyncio
    async def test_set_color_zones_updates_state(self, emulator_devices) -> None:
        """Test set_color_zones() updates state optimistically."""
        template: MultiZoneLight = emulator_devices[4]  # d073d5000005

        async with await MultiZoneLight.connect(
            serial=template.serial, ip=template.ip, port=template.port
        ) as multizone_light:
            assert isinstance(multizone_light, MultiZoneLight)

            # Set zones
            zone_count = await multizone_light.get_zone_count()
            new_color = HSBK(hue=240, saturation=1.0, brightness=0.5, kelvin=4000)
            await multizone_light.set_color_zones(0, zone_count - 1, new_color)

            # State zones should be updated (may take a moment for refresh)
            assert multizone_light.state.zones is not None

    @pytest.mark.asyncio
    async def test_get_effect_updates_state(self, emulator_devices) -> None:
        """Test get_effect() updates state when it exists."""
        template: MultiZoneLight = emulator_devices[4]  # d073d5000005

        async with await MultiZoneLight.connect(
            serial=template.serial, ip=template.ip, port=template.port
        ) as multizone_light:
            assert isinstance(multizone_light, MultiZoneLight)

            # Get effect
            effect = await multizone_light.get_effect()

            # State should be updated
            assert multizone_light.state.effect is not None
            assert multizone_light.state.effect == effect.effect_type

    @pytest.mark.asyncio
    async def test_state_dataclass_properties(self, emulator_devices) -> None:
        """Test MultiZoneLightState dataclass computed properties."""
        template: MultiZoneLight = emulator_devices[4]  # d073d5000005

        async with await MultiZoneLight.connect(
            serial=template.serial, ip=template.ip, port=template.port
        ) as multizone_light:
            state = multizone_light.state

            # Test is_on property
            await multizone_light.set_power(True)
            await multizone_light.refresh_state()
            assert state.is_on is True

            await multizone_light.set_power(False)
            await multizone_light.refresh_state()
            assert state.is_on is False

            # Test age property (should be very recent)
            age = state.age
            assert age >= 0
            assert age < 5  # Should be less than 5 seconds old

            # Test is_fresh property (should be fresh)
            assert state.is_fresh(max_age=10) is True
