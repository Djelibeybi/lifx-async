"""Comprehensive tests for device state management system."""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lifx.color import HSBK
from lifx.devices.base import (
    CollectionInfo,
    Device,
    DeviceCapabilities,
    DeviceState,
    FirmwareInfo,
)
from lifx.devices.light import Light, LightState
from lifx.protocol import packets
from lifx.protocol.protocol_types import LightHsbk


class TestDeviceConnectFactory:
    """Tests for Device.connect() factory method."""

    @pytest.mark.asyncio
    async def test_connect_returns_light_for_color_device(
        self, mock_product_info, mock_firmware_info
    ):
        """Test Light._initialize_state() creates LightState for color device."""
        # Mock product registry to return Light-capable product
        product_info = mock_product_info(
            has_color=True, has_multizone=False, has_matrix=False
        )

        with patch("lifx.devices.base.get_product", return_value=product_info):
            with patch.object(Light, "_ensure_capabilities", new_callable=AsyncMock):
                with patch.object(Light, "get_version") as mock_get_version:
                    mock_get_version.return_value = (1, 27)

                    # Create Light device and mock all required state fetching
                    device = Light(serial="d073d5010203", ip="192.168.1.100")
                    mock_conn = MagicMock()
                    mock_conn.request = AsyncMock()
                    device.connection = mock_conn

                    # Mock all state responses
                    mock_color_response = MagicMock()
                    mock_color_response.color = LightHsbk(
                        hue=0, saturation=0, brightness=65535, kelvin=3500
                    )
                    mock_color_response.power = 65535
                    mock_color_response.label = "Test Light"

                    firmware = mock_firmware_info()

                    # Setup request mock to return appropriate responses
                    async def mock_request(packet):
                        if isinstance(packet, packets.Light.GetColor):
                            return mock_color_response
                        elif isinstance(packet, packets.Device.GetHostFirmware):
                            return packets.Device.StateHostFirmware(
                                build=firmware.build,
                                version_major=firmware.version_major,
                                version_minor=firmware.version_minor,
                            )
                        elif isinstance(packet, packets.Device.GetWifiFirmware):
                            return packets.Device.StateWifiFirmware(
                                build=firmware.build,
                                version_major=firmware.version_major,
                                version_minor=firmware.version_minor,
                            )
                        elif isinstance(packet, packets.Device.GetLocation):
                            return packets.Device.StateLocation(
                                location=b"\x00" * 16,
                                label=b"Test Location",
                                updated_at=int(time.time() * 1e9),
                            )
                        elif isinstance(packet, packets.Device.GetGroup):
                            return packets.Device.StateGroup(
                                group=b"\x00" * 16,
                                label=b"Test Group",
                                updated_at=int(time.time() * 1e9),
                            )
                        elif isinstance(packet, packets.Device.GetLabel):
                            return packets.Device.StateLabel(label=b"Test Light")
                        elif isinstance(packet, packets.Device.GetPower):
                            return packets.Device.StatePower(level=65535)

                    mock_conn.request.side_effect = mock_request

                    # Initialize state on Light instance
                    device._capabilities = product_info
                    await device._initialize_state()

                    # Verify device is Light type
                    assert isinstance(device, Light)
                    # Verify state is initialized with LightState
                    assert device._state is not None
                    assert isinstance(device._state, LightState)
                    assert device._state.power == 65535
                    assert device._state.label == "Test Light"
                    assert isinstance(device._state.color, HSBK)

    @pytest.mark.asyncio
    async def test_connect_state_is_non_none(
        self, mock_product_info, mock_firmware_info
    ):
        """Test Device.connect() guarantees state is not None."""
        product_info = mock_product_info(has_color=True)

        with patch("lifx.devices.base.get_product", return_value=product_info):
            with patch.object(Device, "_ensure_capabilities", new_callable=AsyncMock):
                with patch.object(Device, "get_version") as mock_get_version:
                    mock_get_version.return_value = (1, 27)

                    device = Device(serial="d073d5010203", ip="192.168.1.100")
                    mock_conn = MagicMock()
                    mock_conn.request = AsyncMock()
                    device.connection = mock_conn

                    # Mock minimal responses
                    mock_color_response = MagicMock()
                    mock_color_response.color = LightHsbk(
                        hue=0, saturation=0, brightness=65535, kelvin=3500
                    )
                    mock_color_response.power = 65535
                    mock_color_response.label = "Test"

                    firmware = mock_firmware_info()

                    async def mock_request(packet):
                        if isinstance(packet, packets.Light.GetColor):
                            return mock_color_response
                        elif isinstance(packet, packets.Device.GetHostFirmware):
                            return packets.Device.StateHostFirmware(
                                build=firmware.build,
                                version_major=firmware.version_major,
                                version_minor=firmware.version_minor,
                            )
                        elif isinstance(packet, packets.Device.GetWifiFirmware):
                            return packets.Device.StateWifiFirmware(
                                build=firmware.build,
                                version_major=firmware.version_major,
                                version_minor=firmware.version_minor,
                            )
                        elif isinstance(packet, packets.Device.GetLocation):
                            return packets.Device.StateLocation(
                                location=b"\x00" * 16,
                                label=b"Location",
                                updated_at=int(time.time() * 1e9),
                            )
                        elif isinstance(packet, packets.Device.GetGroup):
                            return packets.Device.StateGroup(
                                group=b"\x00" * 16,
                                label=b"Group",
                                updated_at=int(time.time() * 1e9),
                            )
                        elif isinstance(packet, packets.Device.GetLabel):
                            return packets.Device.StateLabel(label=b"Test")
                        elif isinstance(packet, packets.Device.GetPower):
                            return packets.Device.StatePower(level=65535)

                    mock_conn.request.side_effect = mock_request
                    device._capabilities = product_info

                    # Initialize state
                    await device._initialize_state()

                    # State should never be None after connect
                    assert device._state is not None


class TestStateInitialization:
    """Tests for _initialize_state() method."""

    @pytest.mark.asyncio
    async def test_initialize_state_populates_all_fields(
        self, light, mock_product_info, mock_firmware_info
    ):
        """Test _initialize_state() populates all state fields."""
        product_info = mock_product_info(has_color=True)
        light._capabilities = product_info

        # Mock all responses
        mock_color = MagicMock()
        mock_color.color = LightHsbk(
            hue=21845, saturation=65535, brightness=32768, kelvin=3500
        )
        mock_color.power = 65535
        mock_color.label = "Kitchen Light"

        firmware = mock_firmware_info(version_major=2, version_minor=80)

        async def mock_request(packet):
            if isinstance(packet, packets.Light.GetColor):
                return mock_color
            elif isinstance(packet, packets.Device.GetHostFirmware):
                return packets.Device.StateHostFirmware(
                    build=firmware.build,
                    version_major=firmware.version_major,
                    version_minor=firmware.version_minor,
                )
            elif isinstance(packet, packets.Device.GetWifiFirmware):
                return packets.Device.StateWifiFirmware(
                    build=firmware.build,
                    version_major=firmware.version_major,
                    version_minor=firmware.version_minor,
                )
            elif isinstance(packet, packets.Device.GetLocation):
                return packets.Device.StateLocation(
                    location=b"\x01" * 16,
                    label=b"Home",
                    updated_at=int(time.time() * 1e9),
                )
            elif isinstance(packet, packets.Device.GetGroup):
                return packets.Device.StateGroup(
                    group=b"\x02" * 16,
                    label=b"Kitchen",
                    updated_at=int(time.time() * 1e9),
                )

        light.connection.request.side_effect = mock_request

        # Initialize state
        await light._initialize_state()

        # Verify all fields populated
        assert light._state is not None
        assert isinstance(light._state, LightState)
        assert light._state.label == "Kitchen Light"
        assert light._state.power == 65535
        assert light._state.color.hue == 120.0  # 21845/65535 * 360
        assert light._state.host_firmware.version_major == 2
        assert light._state.wifi_firmware.version_minor == 80
        assert light._state.location.label == b"Home"
        assert light._state.group.label == b"Kitchen"

    @pytest.mark.asyncio
    async def test_initialize_state_sets_timestamp(self, light, mock_product_info):
        """Test _initialize_state() sets last_updated timestamp."""
        product_info = mock_product_info(has_color=True)
        light._capabilities = product_info

        # Setup minimal mocks
        mock_color = MagicMock()
        mock_color.color = LightHsbk(hue=0, saturation=0, brightness=65535, kelvin=3500)
        mock_color.power = 65535
        mock_color.label = "Test"

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
                    location=b"\x00" * 16, label=b"Location", updated_at=0
                )
            elif isinstance(packet, packets.Device.GetGroup):
                return packets.Device.StateGroup(
                    group=b"\x00" * 16, label=b"Group", updated_at=0
                )

        light.connection.request.side_effect = mock_request

        before = time.time()
        await light._initialize_state()
        after = time.time()

        assert light._state is not None
        assert before <= light._state.last_updated <= after


class TestRefreshState:
    """Tests for refresh_state() method."""

    @pytest.mark.asyncio
    async def test_refresh_state_updates_volatile_fields(
        self, light, mock_product_info
    ):
        """Test refresh_state() updates volatile fields (power, color)."""
        # Initialize state first
        product_info = mock_product_info(has_color=True)
        light._capabilities = product_info

        # Initial state setup
        initial_color = MagicMock()
        initial_color.color = LightHsbk(
            hue=0, saturation=0, brightness=65535, kelvin=3500
        )
        initial_color.power = 0
        initial_color.label = "Test Light"

        async def initial_mock(packet):
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
                    location=b"\x00" * 16, label=b"Location", updated_at=0
                )
            elif isinstance(packet, packets.Device.GetGroup):
                return packets.Device.StateGroup(
                    group=b"\x00" * 16, label=b"Group", updated_at=0
                )

        light.connection.request.side_effect = initial_mock
        await light._initialize_state()

        # Now mock updated values
        updated_color = MagicMock()
        updated_color.color = LightHsbk(
            hue=21845, saturation=65535, brightness=32768, kelvin=4000
        )
        updated_color.power = 65535
        updated_color.label = "Test Light"

        async def updated_mock(packet):
            if isinstance(packet, packets.Light.GetColor):
                return updated_color

        light.connection.request.side_effect = updated_mock

        # Refresh state
        await light.refresh_state()

        # Verify volatile fields updated
        assert light._state.power == 65535
        assert light._state.color.kelvin == 4000
        assert light._state.color.brightness == 0.5  # 32768/65535

    @pytest.mark.asyncio
    async def test_refresh_state_updates_timestamp(self, light, mock_product_info):
        """Test refresh_state() updates last_updated timestamp."""
        product_info = mock_product_info(has_color=True)
        light._capabilities = product_info

        # Initial setup
        mock_color = MagicMock()
        mock_color.color = LightHsbk(hue=0, saturation=0, brightness=65535, kelvin=3500)
        mock_color.power = 65535
        mock_color.label = "Test"

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
                    location=b"\x00" * 16, label=b"Location", updated_at=0
                )
            elif isinstance(packet, packets.Device.GetGroup):
                return packets.Device.StateGroup(
                    group=b"\x00" * 16, label=b"Group", updated_at=0
                )

        light.connection.request.side_effect = mock_request
        await light._initialize_state()

        old_timestamp = light._state.last_updated
        await asyncio.sleep(0.01)  # Small delay to ensure timestamp difference

        # Refresh
        await light.refresh_state()

        assert light._state.last_updated > old_timestamp


class TestOptimisticUpdates:
    """Tests for optimistic updates in set_* methods."""

    @pytest.mark.asyncio
    async def test_set_power_updates_state_optimistically(
        self, light, mock_product_info
    ):
        """Test set_power() updates state immediately (optimistically)."""
        # Initialize state
        product_info = mock_product_info(has_color=True)
        light._capabilities = product_info

        mock_color = MagicMock()
        mock_color.color = LightHsbk(hue=0, saturation=0, brightness=65535, kelvin=3500)
        mock_color.power = 0
        mock_color.label = "Test"

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
                    location=b"\x00" * 16, label=b"Location", updated_at=0
                )
            elif isinstance(packet, packets.Device.GetGroup):
                return packets.Device.StateGroup(
                    group=b"\x00" * 16, label=b"Group", updated_at=0
                )

        light.connection.request.side_effect = init_mock
        await light._initialize_state()

        # Mock set_power response
        async def set_power_mock(packet):
            if isinstance(packet, packets.Light.SetPower):
                return True  # Acknowledgement
            return True  # Default to True for other packets

        light.connection.request.side_effect = set_power_mock

        # Set power
        await light.set_power(True)

        # State should be updated immediately
        assert light._state.power == 65535

    @pytest.mark.asyncio
    async def test_set_color_schedules_debounced_refresh(
        self, light, mock_product_info
    ):
        """Test set_color() schedules debounced refresh."""
        # Initialize state
        product_info = mock_product_info(has_color=True)
        light._capabilities = product_info

        mock_color = MagicMock()
        mock_color.color = LightHsbk(hue=0, saturation=0, brightness=65535, kelvin=3500)
        mock_color.power = 65535
        mock_color.label = "Test"

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
                    location=b"\x00" * 16, label=b"Location", updated_at=0
                )
            elif isinstance(packet, packets.Device.GetGroup):
                return packets.Device.StateGroup(
                    group=b"\x00" * 16, label=b"Group", updated_at=0
                )

        light.connection.request.side_effect = init_mock
        await light._initialize_state()

        # Mock set_color response
        async def set_color_mock(packet):
            return True

        light.connection.request.side_effect = set_color_mock

        # Set color
        new_color = HSBK(hue=120, saturation=1.0, brightness=0.5, kelvin=4000)
        await light.set_color(new_color)

        # Refresh task should be scheduled
        assert light._refresh_task is not None


class TestAcknowledgementBasedStateUpdates:
    """Tests that state is only updated when acknowledgements are received."""

    @pytest.mark.asyncio
    async def test_set_label_updates_state_on_ack(self, light, mock_product_info):
        """Test set_label() updates both cache and state when ack received."""
        # Initialize state
        product_info = mock_product_info(has_color=True)
        light._capabilities = product_info

        mock_color = MagicMock()
        mock_color.color = LightHsbk(hue=0, saturation=0, brightness=65535, kelvin=3500)
        mock_color.power = 0
        mock_color.label = "Original"

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
                    location=b"\x00" * 16, label=b"Location", updated_at=0
                )
            elif isinstance(packet, packets.Device.GetGroup):
                return packets.Device.StateGroup(
                    group=b"\x00" * 16, label=b"Group", updated_at=0
                )

        light.connection.request.side_effect = init_mock
        await light._initialize_state()

        # Verify initial state
        assert light._label == "Original"
        assert light._state.label == "Original"

        # Mock set_label response with ack
        async def set_label_ack_mock(packet):
            if isinstance(packet, packets.Device.SetLabel):
                return True  # Acknowledgement
            return None

        light.connection.request.side_effect = set_label_ack_mock

        # Set label
        await light.set_label("New Label")

        # Both cache and state should be updated
        assert light._label == "New Label"
        assert light._state.label == "New Label"

    @pytest.mark.asyncio
    async def test_set_label_no_update_without_ack(self, light, mock_product_info):
        """Test set_label() does NOT update state when ack not received."""
        # Initialize state
        product_info = mock_product_info(has_color=True)
        light._capabilities = product_info

        mock_color = MagicMock()
        mock_color.color = LightHsbk(hue=0, saturation=0, brightness=65535, kelvin=3500)
        mock_color.power = 0
        mock_color.label = "Original"

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
                    location=b"\x00" * 16, label=b"Location", updated_at=0
                )
            elif isinstance(packet, packets.Device.GetGroup):
                return packets.Device.StateGroup(
                    group=b"\x00" * 16, label=b"Group", updated_at=0
                )

        light.connection.request.side_effect = init_mock
        await light._initialize_state()

        # Mock set_label response without ack
        async def set_label_no_ack_mock(packet):
            if isinstance(packet, packets.Device.SetLabel):
                return False  # No acknowledgement
            return None

        light.connection.request.side_effect = set_label_no_ack_mock

        # Set label
        await light.set_label("New Label")

        # State should NOT be updated
        assert light._label == "Original"
        assert light._state.label == "Original"

    @pytest.mark.asyncio
    async def test_set_power_updates_state_on_ack(self, light, mock_product_info):
        """Test set_power() updates state when ack received."""
        # Initialize state
        product_info = mock_product_info(has_color=True)
        light._capabilities = product_info

        mock_color = MagicMock()
        mock_color.color = LightHsbk(hue=0, saturation=0, brightness=65535, kelvin=3500)
        mock_color.power = 0
        mock_color.label = "Test"

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
                    location=b"\x00" * 16, label=b"Location", updated_at=0
                )
            elif isinstance(packet, packets.Device.GetGroup):
                return packets.Device.StateGroup(
                    group=b"\x00" * 16, label=b"Group", updated_at=0
                )

        light.connection.request.side_effect = init_mock
        await light._initialize_state()

        # Verify initial state
        assert light._state.power == 0

        # Mock set_power response with ack
        async def set_power_ack_mock(packet):
            if isinstance(packet, packets.Light.SetPower):
                return True  # Acknowledgement
            return None

        light.connection.request.side_effect = set_power_ack_mock

        # Set power
        await light.set_power(True)

        # State should be updated
        assert light._state.power == 65535

    @pytest.mark.asyncio
    async def test_set_power_no_update_without_ack(self, light, mock_product_info):
        """Test set_power() does NOT update state when ack not received."""
        # Initialize state
        product_info = mock_product_info(has_color=True)
        light._capabilities = product_info

        mock_color = MagicMock()
        mock_color.color = LightHsbk(hue=0, saturation=0, brightness=65535, kelvin=3500)
        mock_color.power = 0
        mock_color.label = "Test"

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
                    location=b"\x00" * 16, label=b"Location", updated_at=0
                )
            elif isinstance(packet, packets.Device.GetGroup):
                return packets.Device.StateGroup(
                    group=b"\x00" * 16, label=b"Group", updated_at=0
                )

        light.connection.request.side_effect = init_mock
        await light._initialize_state()

        # Mock set_power response without ack
        async def set_power_no_ack_mock(packet):
            if isinstance(packet, packets.Light.SetPower):
                return False  # No acknowledgement
            return None

        light.connection.request.side_effect = set_power_no_ack_mock

        # Set power
        await light.set_power(True)

        # State should NOT be updated
        assert light._state.power == 0

    @pytest.mark.asyncio
    async def test_set_color_updates_state_on_ack(self, light, mock_product_info):
        """Test set_color() updates state when ack received."""
        # Initialize state
        product_info = mock_product_info(has_color=True)
        light._capabilities = product_info

        mock_color = MagicMock()
        mock_color.color = LightHsbk(hue=0, saturation=0, brightness=65535, kelvin=3500)
        mock_color.power = 65535
        mock_color.label = "Test"

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
                    location=b"\x00" * 16, label=b"Location", updated_at=0
                )
            elif isinstance(packet, packets.Device.GetGroup):
                return packets.Device.StateGroup(
                    group=b"\x00" * 16, label=b"Group", updated_at=0
                )

        light.connection.request.side_effect = init_mock
        await light._initialize_state()

        # Verify initial color
        assert light._state.color.hue == 0
        assert light._state.color.saturation == 0.0

        # Mock set_color response with ack
        async def set_color_ack_mock(packet):
            if isinstance(packet, packets.Light.SetColor):
                return True  # Acknowledgement
            return None

        light.connection.request.side_effect = set_color_ack_mock

        # Set color
        new_color = HSBK(hue=120, saturation=1.0, brightness=0.5, kelvin=4000)
        await light.set_color(new_color)

        # State should be updated
        assert light._state.color.hue == 120
        assert light._state.color.saturation == 1.0
        assert light._state.color.brightness == 0.5
        assert light._state.color.kelvin == 4000

    @pytest.mark.asyncio
    async def test_set_color_no_update_without_ack(self, light, mock_product_info):
        """Test set_color() does NOT update state when ack not received."""
        # Initialize state
        product_info = mock_product_info(has_color=True)
        light._capabilities = product_info

        mock_color = MagicMock()
        mock_color.color = LightHsbk(hue=0, saturation=0, brightness=65535, kelvin=3500)
        mock_color.power = 65535
        mock_color.label = "Test"

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
                    location=b"\x00" * 16, label=b"Location", updated_at=0
                )
            elif isinstance(packet, packets.Device.GetGroup):
                return packets.Device.StateGroup(
                    group=b"\x00" * 16, label=b"Group", updated_at=0
                )

        light.connection.request.side_effect = init_mock
        await light._initialize_state()

        # Mock set_color response without ack
        async def set_color_no_ack_mock(packet):
            if isinstance(packet, packets.Light.SetColor):
                return False  # No acknowledgement
            return None

        light.connection.request.side_effect = set_color_no_ack_mock

        # Set color
        new_color = HSBK(hue=120, saturation=1.0, brightness=0.5, kelvin=4000)
        await light.set_color(new_color)

        # State should NOT be updated
        assert light._state.color.hue == 0
        assert light._state.color.saturation == 0.0


class TestGetMethodsStateUpdates:
    """Tests for get_*() methods updating state."""

    @pytest.mark.asyncio
    async def test_get_power_updates_state(self, emulator_devices):
        """Test get_power() updates state when it exists."""
        # Use first light device from emulator
        light = emulator_devices[0]

        async with light:
            # Initialize state
            await light._initialize_state()

            # Change power via get_power()
            power = await light.get_power()

            # State should be updated with the fetched value
            assert light._state.power == power

    @pytest.mark.asyncio
    async def test_get_color_updates_state(self, light, mock_product_info):
        """Test get_color() updates state when it exists."""
        # Initialize state
        product_info = mock_product_info(has_color=True)
        light._capabilities = product_info

        mock_color = MagicMock()
        mock_color.color = LightHsbk(hue=0, saturation=0, brightness=65535, kelvin=3500)
        mock_color.power = 0
        mock_color.label = "Test"

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
                    location=b"\x00" * 16, label=b"Location", updated_at=0
                )
            elif isinstance(packet, packets.Device.GetGroup):
                return packets.Device.StateGroup(
                    group=b"\x00" * 16, label=b"Group", updated_at=0
                )

        light.connection.request.side_effect = init_mock
        await light._initialize_state()

        # Mock get_color response with different value
        updated_mock = MagicMock()
        updated_mock.color = LightHsbk(
            hue=21845, saturation=65535, brightness=32768, kelvin=4000
        )
        updated_mock.power = 65535
        updated_mock.label = "Test"

        async def get_color_mock(packet):
            if isinstance(packet, packets.Light.GetColor):
                return updated_mock

        light.connection.request.side_effect = get_color_mock

        # Get color
        color, power, label = await light.get_color()

        # State should be updated
        assert light._state.color.hue == color.hue
        assert light._state.color.kelvin == 4000
        assert light._state.power == 65535

    @pytest.mark.asyncio
    async def test_get_label_updates_state(self, light, mock_product_info):
        """Test get_label() updates state when it exists."""
        # Initialize state
        product_info = mock_product_info(has_color=True)
        light._capabilities = product_info

        mock_color = MagicMock()
        mock_color.color = LightHsbk(hue=0, saturation=0, brightness=65535, kelvin=3500)
        mock_color.power = 0
        mock_color.label = "Old Label"

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
                    location=b"\x00" * 16, label=b"Location", updated_at=0
                )
            elif isinstance(packet, packets.Device.GetGroup):
                return packets.Device.StateGroup(
                    group=b"\x00" * 16, label=b"Group", updated_at=0
                )

        light.connection.request.side_effect = init_mock
        await light._initialize_state()

        # Mock get_label response
        async def get_label_mock(packet):
            if isinstance(packet, packets.Device.GetLabel):
                return packets.Device.StateLabel(label=b"New Label")

        light.connection.request.side_effect = get_label_mock

        # Get label
        label = await light.get_label()

        # State should be updated
        assert label == b"New Label"
        assert light.state.label == b"New Label"


class TestStateDataclasses:
    """Tests for state dataclass properties and functionality."""

    def test_device_state_is_on_property(self):
        """Test DeviceState.is_on property."""
        # Create minimal state
        state = DeviceState(
            model="Test",
            label="Test",
            serial="000000000000",
            mac_address="00:00:00:00:00:00",
            capabilities=DeviceCapabilities(
                has_color=False,
                has_multizone=False,
                has_chain=False,
                has_matrix=False,
                has_infrared=False,
                has_hev=False,
                has_extended_multizone=False,
                kelvin_min=None,
                kelvin_max=None,
            ),
            power=0,
            host_firmware=FirmwareInfo(build=0, version_major=2, version_minor=80),
            wifi_firmware=FirmwareInfo(build=0, version_major=2, version_minor=80),
            location=CollectionInfo("0000000000000000", "Location", 0),
            group=CollectionInfo("0000000000000000", "Group", 0),
            last_updated=time.time(),
        )

        assert state.is_on is False

        state.power = 65535
        assert state.is_on is True

    def test_device_state_age_property(self):
        """Test DeviceState.age property."""
        state = DeviceState(
            model="Test",
            label="Test",
            serial="000000000000",
            mac_address="00:00:00:00:00:00",
            capabilities=DeviceCapabilities(
                has_color=False,
                has_multizone=False,
                has_chain=False,
                has_matrix=False,
                has_infrared=False,
                has_hev=False,
                has_extended_multizone=False,
                kelvin_min=None,
                kelvin_max=None,
            ),
            power=0,
            host_firmware=FirmwareInfo(build=0, version_major=2, version_minor=80),
            wifi_firmware=FirmwareInfo(build=0, version_major=2, version_minor=80),
            location=CollectionInfo("0000000000000000", "Location", 0),
            group=CollectionInfo("0000000000000000", "Group", 0),
            last_updated=time.time() - 5.0,
        )

        age = state.age
        assert 4.9 <= age <= 5.1  # Allow small timing variance

    def test_device_state_is_fresh_property(self):
        """Test DeviceState.is_fresh() method."""
        # Recent state
        state = DeviceState(
            model="Test",
            label="Test",
            serial="000000000000",
            mac_address="00:00:00:00:00:00",
            capabilities=DeviceCapabilities(
                has_color=False,
                has_multizone=False,
                has_chain=False,
                has_matrix=False,
                has_infrared=False,
                has_hev=False,
                has_extended_multizone=False,
                kelvin_min=None,
                kelvin_max=None,
            ),
            power=0,
            host_firmware=FirmwareInfo(build=0, version_major=2, version_minor=80),
            wifi_firmware=FirmwareInfo(build=0, version_major=2, version_minor=80),
            location=CollectionInfo("0000000000000000", "Location", 0),
            group=CollectionInfo("0000000000000000", "Group", 0),
            last_updated=time.time(),
        )

        assert state.is_fresh(max_age=5.0) is True

        # Old state
        state.last_updated = time.time() - 10.0
        assert state.is_fresh(max_age=5.0) is False

    def test_device_capabilities_has_variable_color_temp(self):
        """Test DeviceCapabilities.has_variable_color_temp property."""
        # Device with fixed temperature
        caps = DeviceCapabilities(
            has_color=True,
            has_multizone=False,
            has_chain=False,
            has_matrix=False,
            has_infrared=False,
            has_hev=False,
            has_extended_multizone=False,
            kelvin_min=3500,
            kelvin_max=3500,
        )
        assert caps.has_variable_color_temp is False

        # Device with variable temperature
        caps = DeviceCapabilities(
            has_color=True,
            has_multizone=False,
            has_chain=False,
            has_matrix=False,
            has_infrared=False,
            has_hev=False,
            has_extended_multizone=False,
            kelvin_min=1500,
            kelvin_max=9000,
        )
        assert caps.has_variable_color_temp is True


class TestProcessCapabilities:
    """Tests for _process_capabilities() synchronous helper."""

    def test_process_capabilities_sets_capabilities(self, mock_product_info):
        """Test _process_capabilities() sets device capabilities from version."""
        from lifx.devices.base import DeviceVersion, FirmwareInfo

        device = Device(serial="d073d5010203", ip="192.168.1.100")
        product_info = mock_product_info(has_color=True)

        version = DeviceVersion(vendor=1, product=32)
        firmware = FirmwareInfo(build=0, version_major=2, version_minor=80)

        with patch("lifx.devices.base.get_product", return_value=product_info):
            device._process_capabilities(version, firmware)

        assert device._capabilities is product_info

    def test_process_capabilities_noop_when_already_set(self, mock_product_info):
        """Test _process_capabilities() is a no-op when capabilities already set."""
        from lifx.devices.base import DeviceVersion, FirmwareInfo

        device = Device(serial="d073d5010203", ip="192.168.1.100")
        existing_info = mock_product_info(has_color=True, name="Existing")
        device._capabilities = existing_info

        version = DeviceVersion(vendor=1, product=99)
        firmware = FirmwareInfo(build=0, version_major=2, version_minor=80)

        # Should NOT call get_product since capabilities already set
        with patch("lifx.devices.base.get_product") as mock_get:
            device._process_capabilities(version, firmware)
            mock_get.assert_not_called()

        assert device._capabilities is existing_info

    def test_process_capabilities_strips_extended_multizone_for_old_firmware(self):
        """Test _process_capabilities() strips extended_multizone for old firmware."""
        from lifx.devices.base import DeviceVersion, FirmwareInfo
        from lifx.products.registry import (
            ProductCapability,
            ProductInfo,
            TemperatureRange,
        )

        device = Device(serial="d073d5010203", ip="192.168.1.100")

        # Create product with extended_multizone and a minimum firmware requirement
        product_info = ProductInfo(
            pid=32,
            name="Test Strip",
            vendor=1,
            capabilities=ProductCapability.COLOR
            | ProductCapability.MULTIZONE
            | ProductCapability.EXTENDED_MULTIZONE,
            temperature_range=TemperatureRange(min=1500, max=9000),
            min_ext_mz_firmware=(2 << 16) | 77,  # Requires firmware 2.77+
        )

        version = DeviceVersion(vendor=1, product=32)
        # Firmware 2.50 is below the 2.77 requirement
        firmware = FirmwareInfo(build=0, version_major=2, version_minor=50)

        with patch("lifx.devices.base.get_product", return_value=product_info):
            device._process_capabilities(version, firmware)

        assert device._capabilities is not None
        assert not device._capabilities.has_extended_multizone


class TestDeviceInitializeStateParallel:
    """Tests for _initialize_state() parallel get_version() optimization."""

    @pytest.mark.asyncio
    async def test_device_initialize_state_without_capabilities_includes_get_version(
        self, mock_product_info, mock_firmware_info
    ):
        """Test _initialize_state() includes get_version()
        when capabilities not loaded."""
        product_info = mock_product_info(has_color=True)
        firmware = mock_firmware_info()

        device = Device(serial="d073d5010203", ip="192.168.1.100")
        mock_conn = MagicMock()
        mock_conn.request = AsyncMock()
        device.connection = mock_conn

        # Track which packet types were requested
        requested_packets: list[type] = []

        async def mock_request(packet):
            requested_packets.append(type(packet))
            if isinstance(packet, packets.Device.GetVersion):
                return packets.Device.StateVersion(vendor=1, product=32)
            elif isinstance(packet, packets.Device.GetLabel):
                return packets.Device.StateLabel(label=b"Test")
            elif isinstance(packet, packets.Device.GetPower):
                return packets.Device.StatePower(level=65535)
            elif isinstance(packet, packets.Device.GetHostFirmware):
                return packets.Device.StateHostFirmware(
                    build=firmware.build,
                    version_major=firmware.version_major,
                    version_minor=firmware.version_minor,
                )
            elif isinstance(packet, packets.Device.GetWifiFirmware):
                return packets.Device.StateWifiFirmware(
                    build=firmware.build,
                    version_major=firmware.version_major,
                    version_minor=firmware.version_minor,
                )
            elif isinstance(packet, packets.Device.GetLocation):
                return packets.Device.StateLocation(
                    location=b"\x00" * 16,
                    label=b"Location",
                    updated_at=int(time.time() * 1e9),
                )
            elif isinstance(packet, packets.Device.GetGroup):
                return packets.Device.StateGroup(
                    group=b"\x00" * 16,
                    label=b"Group",
                    updated_at=int(time.time() * 1e9),
                )

        mock_conn.request.side_effect = mock_request

        # Capabilities NOT set - should include get_version()
        assert device._capabilities is None

        with patch("lifx.devices.base.get_product", return_value=product_info):
            await device._initialize_state()

        # Verify GetVersion was dispatched
        assert packets.Device.GetVersion in requested_packets

        # Verify state is populated
        assert device._state is not None
        assert device._state.label == b"Test"
        assert device._state.power == 65535

        # Verify capabilities were set
        assert device._capabilities is product_info

    @pytest.mark.asyncio
    async def test_device_initialize_state_with_capabilities_skips_get_version(
        self, mock_product_info, mock_firmware_info
    ):
        """Test _initialize_state() skips get_version() when capabilities pre-loaded."""
        product_info = mock_product_info(has_color=True)
        firmware = mock_firmware_info()

        device = Device(serial="d073d5010203", ip="192.168.1.100")
        mock_conn = MagicMock()
        mock_conn.request = AsyncMock()
        device.connection = mock_conn

        # Track which packet types were requested
        requested_packets: list[type] = []

        async def mock_request(packet):
            requested_packets.append(type(packet))
            if isinstance(packet, packets.Device.GetLabel):
                return packets.Device.StateLabel(label=b"Test")
            elif isinstance(packet, packets.Device.GetPower):
                return packets.Device.StatePower(level=0)
            elif isinstance(packet, packets.Device.GetHostFirmware):
                return packets.Device.StateHostFirmware(
                    build=firmware.build,
                    version_major=firmware.version_major,
                    version_minor=firmware.version_minor,
                )
            elif isinstance(packet, packets.Device.GetWifiFirmware):
                return packets.Device.StateWifiFirmware(
                    build=firmware.build,
                    version_major=firmware.version_major,
                    version_minor=firmware.version_minor,
                )
            elif isinstance(packet, packets.Device.GetLocation):
                return packets.Device.StateLocation(
                    location=b"\x00" * 16,
                    label=b"Location",
                    updated_at=int(time.time() * 1e9),
                )
            elif isinstance(packet, packets.Device.GetGroup):
                return packets.Device.StateGroup(
                    group=b"\x00" * 16,
                    label=b"Group",
                    updated_at=int(time.time() * 1e9),
                )

        mock_conn.request.side_effect = mock_request

        # Pre-load capabilities
        device._capabilities = product_info

        await device._initialize_state()

        # Verify GetVersion was NOT dispatched
        assert packets.Device.GetVersion not in requested_packets

        # Verify state is still populated correctly
        assert device._state is not None
        assert device._state.power == 0

    @pytest.mark.asyncio
    async def test_device_initialize_state_cancels_version_task_on_error(
        self,
    ):
        """Test _initialize_state() cancels version_task if gather
        raises."""
        from lifx.exceptions import LifxTimeoutError

        device = Device(serial="d073d5010203", ip="192.168.1.100")
        mock_conn = MagicMock()
        mock_conn.request = AsyncMock()
        device.connection = mock_conn

        call_count = 0

        async def mock_request(packet):
            nonlocal call_count
            call_count += 1
            if isinstance(packet, packets.Device.GetVersion):
                return packets.Device.StateVersion(vendor=1, product=32)
            elif isinstance(packet, packets.Device.GetLabel):
                raise LifxTimeoutError("Timed out")
            return MagicMock()

        mock_conn.request.side_effect = mock_request

        assert device._capabilities is None

        with pytest.raises(LifxTimeoutError):
            await device._initialize_state()
