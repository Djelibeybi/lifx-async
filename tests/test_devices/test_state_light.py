"""Tests for Light state management."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock

import pytest

from lifx.color import HSBK
from lifx.devices.light import LightState
from lifx.protocol import packets
from lifx.protocol.protocol_types import LightHsbk


class TestLightStateManagement:
    """Tests for Light state management."""

    @pytest.mark.asyncio
    async def test_light_state_property_before_init_raises(self, light):
        """Test accessing state property before initialization raises RuntimeError."""
        # Light fixture has no state initialized
        with pytest.raises(RuntimeError, match="State not found."):
            _ = light.state

    @pytest.mark.asyncio
    async def test_initialize_state_creates_light_state(self, light, mock_product_info):
        """Test _initialize_state() creates LightState instance."""
        product_info = mock_product_info(has_color=True)
        light._capabilities = product_info

        # Mock responses
        mock_color = packets.Light.StateColor(
            color=LightHsbk(hue=21845, saturation=65535, brightness=32768, kelvin=3500),
            power=65535,
            label="Test Light",
        )

        async def mock_request(packet):
            if isinstance(packet, packets.Light.GetColor):
                return mock_color
            elif isinstance(packet, packets.Device.GetHostFirmware):
                return packets.Device.StateHostFirmware(
                    build=0, version_major=2, version_minor=80
                )
            elif isinstance(packet, packets.Device.GetWifiFirmware):
                return packets.Device.StateWifiFirmware(
                    build=0, version_major=2, version_minor=80
                )
            elif isinstance(packet, packets.Device.GetLocation):
                return packets.Device.StateLocation(
                    location=b"\x00" * 16,
                    label="Home",
                    updated_at=int(time.time() * 1e9),
                )
            elif isinstance(packet, packets.Device.GetGroup):
                return packets.Device.StateGroup(
                    group=b"\x00" * 16,
                    label="Living Room",
                    updated_at=int(time.time() * 1e9),
                )

        light.connection.request.side_effect = mock_request

        # Initialize
        await light._initialize_state()

        # Verify state is LightState
        assert light._state is not None
        assert isinstance(light._state, LightState)
        assert light._state.label == "Test Light"
        assert light._state.power == 65535
        assert light._state.color.hue == 120.0  # 21845/65535 * 360

    @pytest.mark.asyncio
    async def test_state_property_after_init_returns_light_state(
        self, light, mock_product_info
    ):
        """Test state property returns LightState after initialization."""
        product_info = mock_product_info(has_color=True)
        light._capabilities = product_info

        # Setup mocks
        mock_color = packets.Light.StateColor(
            color=LightHsbk(hue=0, saturation=0, brightness=65535, kelvin=3500),
            power=65535,
            label="Test",
        )

        async def mock_request(packet):
            if isinstance(packet, packets.Light.GetColor):
                return mock_color
            elif isinstance(packet, packets.Device.GetHostFirmware):
                return packets.Device.StateHostFirmware(
                    build=0, version_major=2, version_minor=80
                )
            elif isinstance(packet, packets.Device.GetWifiFirmware):
                return packets.Device.StateWifiFirmware(
                    build=0, version_major=2, version_minor=80
                )
            elif isinstance(packet, packets.Device.GetLocation):
                return packets.Device.StateLocation(
                    location=b"\x00" * 16, label="Loc", updated_at=0
                )
            elif isinstance(packet, packets.Device.GetGroup):
                return packets.Device.StateGroup(
                    group=b"\x00" * 16, label="Grp", updated_at=0
                )

        light.connection.request.side_effect = mock_request
        await light._initialize_state()

        # Access state property
        state = light.state
        assert isinstance(state, LightState)
        assert state.label == "Test"

    @pytest.mark.asyncio
    async def test_refresh_state_updates_color(self, light, mock_product_info):
        """Test refresh_state() updates color field."""
        product_info = mock_product_info(has_color=True)
        light._capabilities = product_info

        # Initialize first
        initial_color = packets.Light.StateColor(
            color=LightHsbk(hue=0, saturation=0, brightness=65535, kelvin=3500),
            power=0,
            label="Test",
        )

        async def init_mock(packet):
            if isinstance(packet, packets.Light.GetColor):
                return initial_color
            elif isinstance(packet, packets.Device.GetHostFirmware):
                return packets.Device.StateHostFirmware(
                    build=0, version_major=2, version_minor=80
                )
            elif isinstance(packet, packets.Device.GetWifiFirmware):
                return packets.Device.StateWifiFirmware(
                    build=0, version_major=2, version_minor=80
                )
            elif isinstance(packet, packets.Device.GetLocation):
                return packets.Device.StateLocation(
                    location=b"\x00" * 16, label="Loc", updated_at=0
                )
            elif isinstance(packet, packets.Device.GetGroup):
                return packets.Device.StateGroup(
                    group=b"\x00" * 16, label="Grp", updated_at=0
                )

        light.connection.request.side_effect = init_mock
        await light._initialize_state()

        # Now update color
        updated_color = packets.Light.StateColor(
            color=LightHsbk(hue=21845, saturation=65535, brightness=32768, kelvin=4000),
            power=65535,
            label="Test",
        )

        async def refresh_mock(packet):
            if isinstance(packet, packets.Light.GetColor):
                return updated_color

        light.connection.request.side_effect = refresh_mock

        # Refresh
        await light.refresh_state()

        # Check updated
        assert light._state.color.kelvin == 4000
        assert light._state.power == 65535

    @pytest.mark.asyncio
    async def test_set_color_optimistic_update(self, light, mock_product_info):
        """Test set_color() updates state optimistically."""
        product_info = mock_product_info(has_color=True)
        light._capabilities = product_info

        # Initialize
        mock_color = packets.Light.StateColor(
            color=LightHsbk(hue=0, saturation=0, brightness=65535, kelvin=3500),
            power=65535,
            label="Test",
        )

        async def init_mock(packet):
            if isinstance(packet, packets.Light.GetColor):
                return mock_color
            elif isinstance(packet, packets.Device.GetHostFirmware):
                return packets.Device.StateHostFirmware(
                    build=0, version_major=2, version_minor=80
                )
            elif isinstance(packet, packets.Device.GetWifiFirmware):
                return packets.Device.StateWifiFirmware(
                    build=0, version_major=2, version_minor=80
                )
            elif isinstance(packet, packets.Device.GetLocation):
                return packets.Device.StateLocation(
                    location=b"\x00" * 16, label="Loc", updated_at=0
                )
            elif isinstance(packet, packets.Device.GetGroup):
                return packets.Device.StateGroup(
                    group=b"\x00" * 16, label="Grp", updated_at=0
                )

        light.connection.request.side_effect = init_mock
        await light._initialize_state()

        # Mock set_color
        async def set_mock(packet):
            return True

        light.connection.request.side_effect = set_mock

        # Set new color
        new_color = HSBK(hue=240, saturation=1.0, brightness=0.5, kelvin=4000)
        await light.set_color(new_color)

        # State should be updated immediately
        assert light._state.color.hue == 240
        assert light._state.color.saturation == 1.0
        assert light._state.color.brightness == 0.5
        assert light._state.color.kelvin == 4000

    @pytest.mark.asyncio
    async def test_get_color_updates_state(self, light, mock_product_info):
        """Test get_color() updates state when it exists."""
        product_info = mock_product_info(has_color=True)
        light._capabilities = product_info

        # Initialize
        mock_color = packets.Light.StateColor(
            color=LightHsbk(hue=0, saturation=0, brightness=65535, kelvin=3500),
            power=0,
            label="Initial",
        )

        async def init_mock(packet):
            if isinstance(packet, packets.Light.GetColor):
                return mock_color
            elif isinstance(packet, packets.Device.GetHostFirmware):
                return packets.Device.StateHostFirmware(
                    build=0, version_major=2, version_minor=80
                )
            elif isinstance(packet, packets.Device.GetWifiFirmware):
                return packets.Device.StateWifiFirmware(
                    build=0, version_major=2, version_minor=80
                )
            elif isinstance(packet, packets.Device.GetLocation):
                return packets.Device.StateLocation(
                    location=b"\x00" * 16, label="Loc", updated_at=0
                )
            elif isinstance(packet, packets.Device.GetGroup):
                return packets.Device.StateGroup(
                    group=b"\x00" * 16, label="Grp", updated_at=0
                )

        light.connection.request.side_effect = init_mock
        await light._initialize_state()

        # Update via get_color
        updated_mock = packets.Light.StateColor(
            color=LightHsbk(hue=21845, saturation=65535, brightness=32768, kelvin=4000),
            power=65535,
            label="Updated",
        )

        async def get_mock(packet):
            if isinstance(packet, packets.Light.GetColor):
                return updated_mock

        light.connection.request.side_effect = get_mock

        # Get color
        color, power, label = await light.get_color()

        # State should be updated
        assert light._state.color.kelvin == 4000
        assert light._state.power == 65535
        assert light._state.label == "Updated"

    @pytest.mark.asyncio
    async def test_close_cancels_refresh_task(self, light, mock_product_info):
        """Test close() cancels pending refresh task."""
        product_info = mock_product_info(has_color=True)
        light._capabilities = product_info

        # Initialize
        mock_color = packets.Light.StateColor(
            color=LightHsbk(hue=0, saturation=0, brightness=65535, kelvin=3500),
            power=65535,
            label="Test",
        )

        async def mock_request(packet):
            if isinstance(packet, packets.Light.GetColor):
                return mock_color
            elif isinstance(packet, packets.Device.GetHostFirmware):
                return packets.Device.StateHostFirmware(
                    build=0, version_major=2, version_minor=80
                )
            elif isinstance(packet, packets.Device.GetWifiFirmware):
                return packets.Device.StateWifiFirmware(
                    build=0, version_major=2, version_minor=80
                )
            elif isinstance(packet, packets.Device.GetLocation):
                return packets.Device.StateLocation(
                    location=b"\x00" * 16, label="Loc", updated_at=0
                )
            elif isinstance(packet, packets.Device.GetGroup):
                return packets.Device.StateGroup(
                    group=b"\x00" * 16, label="Grp", updated_at=0
                )
            elif isinstance(packet, packets.Light.SetColor):
                return True

        light.connection.request = AsyncMock(side_effect=mock_request)
        light.connection.close = AsyncMock()  # Mock close() method
        await light._initialize_state()

        # Schedule a refresh
        await light.set_color(HSBK(120, 1.0, 1.0, 3500))

        # Task should be scheduled
        assert light._refresh_task is not None

        # Close
        await light.close()

        # Task should be cancelled
        assert light._refresh_task is None or light._refresh_task.cancelled()

    @pytest.mark.asyncio
    async def test_set_brightness_optimistic_update(
        self, light, mock_product_info
    ) -> None:
        """Test set_brightness() updates state optimistically."""
        product_info = mock_product_info(has_color=True)
        light._capabilities = product_info

        # Initialize
        mock_color = packets.Light.StateColor(
            color=LightHsbk(hue=0, saturation=0, brightness=65535, kelvin=3500),
            power=65535,
            label="Test",
        )

        async def init_mock(packet):
            if isinstance(packet, packets.Light.GetColor):
                return mock_color
            elif isinstance(packet, packets.Device.GetHostFirmware):
                return packets.Device.StateHostFirmware(
                    build=0, version_major=2, version_minor=80
                )
            elif isinstance(packet, packets.Device.GetWifiFirmware):
                return packets.Device.StateWifiFirmware(
                    build=0, version_major=2, version_minor=80
                )
            elif isinstance(packet, packets.Device.GetLocation):
                return packets.Device.StateLocation(
                    location=b"\\x00" * 16, label="Loc", updated_at=0
                )
            elif isinstance(packet, packets.Device.GetGroup):
                return packets.Device.StateGroup(
                    group=b"\\x00" * 16, label="Grp", updated_at=0
                )

        light.connection.request.side_effect = init_mock
        await light._initialize_state()

        # Mock set_brightness
        async def set_mock(packet):
            return True

        light.connection.request.side_effect = set_mock

        # Set brightness
        await light.set_brightness(0.5)

        # State should be updated immediately
        assert light._state.color.brightness == 0.5

    @pytest.mark.asyncio
    async def test_set_kelvin_optimistic_update(self, light, mock_product_info) -> None:
        """Test set_kelvin() updates state optimistically."""
        product_info = mock_product_info(has_color=True)
        light._capabilities = product_info

        # Initialize
        mock_color = packets.Light.StateColor(
            color=LightHsbk(hue=0, saturation=0, brightness=65535, kelvin=3500),
            power=65535,
            label="Test",
        )

        async def init_mock(packet):
            if isinstance(packet, packets.Light.GetColor):
                return mock_color
            elif isinstance(packet, packets.Device.GetHostFirmware):
                return packets.Device.StateHostFirmware(
                    build=0, version_major=2, version_minor=80
                )
            elif isinstance(packet, packets.Device.GetWifiFirmware):
                return packets.Device.StateWifiFirmware(
                    build=0, version_major=2, version_minor=80
                )
            elif isinstance(packet, packets.Device.GetLocation):
                return packets.Device.StateLocation(
                    location=b"\\x00" * 16, label="Loc", updated_at=0
                )
            elif isinstance(packet, packets.Device.GetGroup):
                return packets.Device.StateGroup(
                    group=b"\\x00" * 16, label="Grp", updated_at=0
                )

        light.connection.request.side_effect = init_mock
        await light._initialize_state()

        # Mock set_kelvin
        async def set_mock(packet):
            return True

        light.connection.request.side_effect = set_mock

        # Set kelvin
        await light.set_kelvin(4000)

        # State should be updated immediately
        assert light._state.color.kelvin == 4000

    @pytest.mark.asyncio
    async def test_set_hue_optimistic_update(self, light, mock_product_info) -> None:
        """Test set_hue() updates state optimistically."""
        product_info = mock_product_info(has_color=True)
        light._capabilities = product_info

        # Initialize
        mock_color = packets.Light.StateColor(
            color=LightHsbk(hue=0, saturation=0, brightness=65535, kelvin=3500),
            power=65535,
            label="Test",
        )

        async def init_mock(packet):
            if isinstance(packet, packets.Light.GetColor):
                return mock_color
            elif isinstance(packet, packets.Device.GetHostFirmware):
                return packets.Device.StateHostFirmware(
                    build=0, version_major=2, version_minor=80
                )
            elif isinstance(packet, packets.Device.GetWifiFirmware):
                return packets.Device.StateWifiFirmware(
                    build=0, version_major=2, version_minor=80
                )
            elif isinstance(packet, packets.Device.GetLocation):
                return packets.Device.StateLocation(
                    location=b"\\x00" * 16, label="Loc", updated_at=0
                )
            elif isinstance(packet, packets.Device.GetGroup):
                return packets.Device.StateGroup(
                    group=b"\\x00" * 16, label="Grp", updated_at=0
                )

        light.connection.request.side_effect = init_mock
        await light._initialize_state()

        # Mock set_hue
        async def set_mock(packet):
            return True

        light.connection.request.side_effect = set_mock

        # Set hue
        await light.set_hue(180)

        # State should be updated immediately
        assert light._state.color.hue == 180

    @pytest.mark.asyncio
    async def test_set_saturation_optimistic_update(
        self, light, mock_product_info
    ) -> None:
        """Test set_saturation() updates state optimistically."""
        product_info = mock_product_info(has_color=True)
        light._capabilities = product_info

        # Initialize
        mock_color = packets.Light.StateColor(
            color=LightHsbk(hue=0, saturation=0, brightness=65535, kelvin=3500),
            power=65535,
            label="Test",
        )

        async def init_mock(packet):
            if isinstance(packet, packets.Light.GetColor):
                return mock_color
            elif isinstance(packet, packets.Device.GetHostFirmware):
                return packets.Device.StateHostFirmware(
                    build=0, version_major=2, version_minor=80
                )
            elif isinstance(packet, packets.Device.GetWifiFirmware):
                return packets.Device.StateWifiFirmware(
                    build=0, version_major=2, version_minor=80
                )
            elif isinstance(packet, packets.Device.GetLocation):
                return packets.Device.StateLocation(
                    location=b"\\x00" * 16, label="Loc", updated_at=0
                )
            elif isinstance(packet, packets.Device.GetGroup):
                return packets.Device.StateGroup(
                    group=b"\\x00" * 16, label="Grp", updated_at=0
                )

        light.connection.request.side_effect = init_mock
        await light._initialize_state()

        # Mock set_saturation
        async def set_mock(packet):
            return True

        light.connection.request.side_effect = set_mock

        # Set saturation
        await light.set_saturation(0.75)

        # State should be updated immediately
        assert light._state.color.saturation == 0.75
