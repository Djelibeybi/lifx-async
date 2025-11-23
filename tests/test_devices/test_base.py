"""Tests for base device class."""

from __future__ import annotations

import time
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lifx.devices.base import (
    LIFX_GROUP_NAMESPACE,
    LIFX_LOCATION_NAMESPACE,
    CollectionInfo,
    Device,
    DeviceInfo,
    DeviceVersion,
    FirmwareInfo,
    WifiInfo,
)
from lifx.network.connection import DeviceConnection
from lifx.protocol import packets


class TestDevice:
    """Tests for Device class."""

    def test_create_device(self) -> None:
        """Test creating a device."""
        device = Device(
            serial="d073d5010203",
            ip="192.168.1.100",
            port=56700,
        )
        assert device.serial == "d073d5010203"
        assert device.ip == "192.168.1.100"
        assert device.port == 56700
        assert device.connection is not None

    def test_serial_property(self, device: Device) -> None:
        """Test serial property."""
        assert device.serial == "d073d5010203"

    def test_create_device_invalid_serial(self) -> None:
        """Test creating device with invalid serial number."""
        with pytest.raises(ValueError, match="Serial number must be 12 hex characters"):
            Device(serial="d073d5", ip="192.168.1.100")

    @pytest.mark.asyncio
    async def test_create_device_from_ip(self, emulator_port: int) -> None:
        """Test creating a device from an IP address."""
        async with await Device.from_ip(ip="127.0.0.1", port=emulator_port) as device:
            assert isinstance(device, Device)

    async def test_get_label(self, device: Device) -> None:
        """Test getting device label."""

        # Mock response with decoded label (connection already decoded it)
        mock_state = packets.Device.StateLabel(label="Living Room Light")
        device.connection.request.return_value = mock_state

        label = await device.get_label()

        assert label == "Living Room Light"
        # Verify it was stored in cache
        stored = device.label
        assert stored is not None
        assert stored == "Living Room Light"

    async def test_label_property_cached(self, device: Device) -> None:
        """Test label property returns cached value."""
        # Set stored label
        device._label = "Stored Label"

        # Access property
        stored = device.label
        assert stored is not None
        assert stored == "Stored Label"

    async def test_set_label(self, device: Device) -> None:
        """Test setting device label."""

        # Mock SET operation returns True
        device.connection.request.return_value = True

        await device.set_label("New Label")

        # Verify request was called
        device.connection.request.assert_called_once()
        call_args = device.connection.request.call_args
        packet = call_args[0][0]
        assert packet.label.startswith(b"New Label")

        # Verify store was updated in cache
        stored = device.label
        assert stored is not None
        assert stored == "New Label"

    async def test_set_label_too_long(self, device: Device) -> None:
        """Test setting label that's too long."""
        with pytest.raises(ValueError, match="Label too long"):
            await device.set_label("x" * 50)

    async def test_get_power(self, device: Device) -> None:
        """Test getting power state."""

        # Mock response with power on (65535)
        mock_state = packets.Device.StatePower(level=65535)
        device.connection.request.return_value = mock_state

        power = await device.get_power()

        assert power == 65535

    async def test_get_power_off(self, device: Device) -> None:
        """Test getting power state when off."""

        # Mock response with power off (0)
        mock_state = packets.Device.StatePower(level=0)
        device.connection.request.return_value = mock_state

        power = await device.get_power()

        assert power == 0

    async def test_set_power_on(self, device: Device) -> None:
        """Test turning device on."""

        # Mock SET operation returns True
        device.connection.request.return_value = True

        await device.set_power(True)

        # Verify request was called
        device.connection.request.assert_called_once()
        call_args = device.connection.request.call_args
        packet = call_args[0][0]
        assert packet.level == 65535

    async def test_set_power_off(self, device: Device) -> None:
        """Test turning device off."""

        # Mock SET operation returns True
        device.connection.request.return_value = True

        await device.set_power(False)

        # Verify request was called
        device.connection.request.assert_called_once()
        call_args = device.connection.request.call_args
        packet = call_args[0][0]
        assert packet.level == 0

    async def test_get_version(self, device: Device) -> None:
        """Test getting device version."""

        # Mock response with version data
        mock_state = packets.Device.StateVersion(vendor=1, product=27)
        device.connection.request.return_value = mock_state

        version = await device.get_version()

        assert isinstance(version, DeviceVersion)
        assert version.vendor == 1
        assert version.product == 27

    async def test_get_info(self, device: Device) -> None:
        """Test getting device info."""

        # Mock response with info data
        mock_state = packets.Device.StateInfo(
            time=1234567890, uptime=9876543210, downtime=1111111111
        )
        device.connection.request.return_value = mock_state

        info = await device.get_info()

        assert isinstance(info, DeviceInfo)
        assert info.time == 1234567890
        assert info.uptime == 9876543210
        assert info.downtime == 1111111111

    async def test_get_wifi_info(self, device: Device) -> None:
        """Test getting WiFi info."""

        # Mock response with WiFi info data
        mock_state = MagicMock()
        mock_state.signal = 7.943283890199382e-06
        device.connection.request.return_value = mock_state

        wifi_info = await device.get_wifi_info()

        assert isinstance(wifi_info, WifiInfo)
        assert wifi_info.rssi == -51

    async def test_get_host_firmware(self, device: Device) -> None:
        """Test getting host firmware info."""

        # Mock response with WiFi firmware data
        mock_state = packets.Device.StateWifiFirmware(
            build=1234567890, version_minor=5, version_major=3
        )
        device.connection.request.return_value = mock_state

        firmware = await device.get_host_firmware()

        assert isinstance(firmware, FirmwareInfo)
        assert firmware.build == 1234567890
        assert firmware.version_major == 3
        assert firmware.version_minor == 5

    def test_label_property_none_when_not_fetched(self, device: Device) -> None:
        """Test that label property is None when not yet fetched."""
        assert device.label is None

    def test_version_property_none_when_not_fetched(self, device: Device) -> None:
        """Test that version property is None when not yet fetched."""
        assert device.version is None

    def test_repr(self, device: Device) -> None:
        """Test string representation."""
        repr_str = repr(device)
        assert "Device" in repr_str
        assert "192.168.1.100" in repr_str
        assert "d073d5010203" in repr_str


class TestLocationAndGroupManagement:
    """Tests for location and group management."""

    def test_location_uuid_deterministic(self) -> None:
        """Test that same location labels generate the same UUID."""
        label = "Living Room"

        # Generate UUID twice with the same label
        uuid1 = uuid.uuid5(LIFX_LOCATION_NAMESPACE, label)
        uuid2 = uuid.uuid5(LIFX_LOCATION_NAMESPACE, label)

        # Should be identical
        assert uuid1 == uuid2
        assert uuid1.bytes == uuid2.bytes

    def test_location_uuid_different_labels(self) -> None:
        """Test that different location labels generate different UUIDs."""
        label1 = "Living Room"
        label2 = "Kitchen"

        uuid1 = uuid.uuid5(LIFX_LOCATION_NAMESPACE, label1)
        uuid2 = uuid.uuid5(LIFX_LOCATION_NAMESPACE, label2)

        # Should be different
        assert uuid1 != uuid2
        assert uuid1.bytes != uuid2.bytes

    def test_group_uuid_deterministic(self) -> None:
        """Test that same group labels generate the same UUID."""
        label = "Bedroom Lights"

        # Generate UUID twice with the same label
        uuid1 = uuid.uuid5(LIFX_GROUP_NAMESPACE, label)
        uuid2 = uuid.uuid5(LIFX_GROUP_NAMESPACE, label)

        # Should be identical
        assert uuid1 == uuid2
        assert uuid1.bytes == uuid2.bytes

    def test_group_uuid_different_labels(self) -> None:
        """Test that different group labels generate different UUIDs."""
        label1 = "Upstairs"
        label2 = "Downstairs"

        uuid1 = uuid.uuid5(LIFX_GROUP_NAMESPACE, label1)
        uuid2 = uuid.uuid5(LIFX_GROUP_NAMESPACE, label2)

        # Should be different
        assert uuid1 != uuid2
        assert uuid1.bytes != uuid2.bytes

    def test_location_and_group_namespaces_separate(self) -> None:
        """Test that location and group UUIDs are different even with same label."""
        label = "Test Label"

        location_uuid = uuid.uuid5(LIFX_LOCATION_NAMESPACE, label)
        group_uuid = uuid.uuid5(LIFX_GROUP_NAMESPACE, label)

        # Should be different due to different namespaces
        assert location_uuid != group_uuid
        assert location_uuid.bytes != group_uuid.bytes

    async def test_set_location_generates_uuid(self, device: Device) -> None:
        """Test that set_location generates deterministic UUID from label."""
        label = "Living Room"
        expected_uuid = uuid.uuid5(LIFX_LOCATION_NAMESPACE, label)

        # Replace device's connection with mock

        # Mock discovery to return no devices (so new UUID is generated)
        # Use a proper async generator mock since discover_devices is an async generator
        async def empty_async_gen(*args, **kwargs):
            return
            yield  # Makes this an async generator

        with patch("lifx.network.discovery.discover_devices", empty_async_gen):
            await device.set_location(label)

        # Verify request was called with new connection API
        device.connection.request.assert_called_once()

        # Get the packet that was sent
        call_args = device.connection.request.call_args
        packet = call_args[0][0]

        # Verify the UUID matches expected
        assert packet.location == expected_uuid.bytes
        assert packet.label == label.encode("utf-8")[:32].ljust(32, b"\x00")

        # Verify store was updated (location property returns location name as string)
        stored_location = device.location
        assert stored_location is not None
        assert stored_location == label

    async def test_set_group_generates_uuid(self, device: Device) -> None:
        """Test that set_group generates deterministic UUID from label."""
        label = "Bedroom Lights"
        expected_uuid = uuid.uuid5(LIFX_GROUP_NAMESPACE, label)

        # Replace device's connection with mock

        # Mock discovery to return no devices (so new UUID is generated)
        # Use a proper async generator mock since discover_devices is an async generator
        async def empty_async_gen(*args, **kwargs):
            return
            yield  # Makes this an async generator

        with patch("lifx.network.discovery.discover_devices", empty_async_gen):
            await device.set_group(label)

        # Verify request was called with new connection API
        device.connection.request.assert_called_once()

        # Get the packet that was sent
        call_args = device.connection.request.call_args
        packet = call_args[0][0]

        # Verify the UUID matches expected
        assert packet.group == expected_uuid.bytes
        assert packet.label == label.encode("utf-8")[:32].ljust(32, b"\x00")

        # Verify store was updated (group property returns group name as string)
        stored_group = device.group
        assert stored_group is not None
        assert stored_group == label

    async def test_multiple_devices_same_location_label(self) -> None:
        """Test that multiple devices with same location label get same UUID."""
        label = "Kitchen"

        device1 = Device(serial="d073d5010203", ip="192.168.1.100")
        device2 = Device(serial="d073d5040506", ip="192.168.1.101")

        # Replace devices' connections with mock (these don't use fixture)
        mock_conn = MagicMock()
        mock_conn.request = AsyncMock()
        device1.connection = mock_conn
        device2.connection = mock_conn

        # Mock discovery to return no devices for both calls
        # Use a proper async generator mock since discover_devices is an async generator
        async def empty_async_gen(*args, **kwargs):
            return
            yield  # Makes this an async generator

        with patch("lifx.network.discovery.discover_devices", empty_async_gen):
            await device1.set_location(label)
            mock_conn.request.reset_mock()
            await device2.set_location(label)

        # Both devices should have the same location name
        assert device1.location is not None
        assert device2.location is not None
        assert device1.location == device2.location == label

    async def test_multiple_devices_same_group_label(self) -> None:
        """Test that multiple devices with same group label get same UUID."""
        label = "Upstairs"

        device1 = Device(serial="d073d5010203", ip="192.168.1.100")
        device2 = Device(serial="d073d5040506", ip="192.168.1.101")

        # Replace devices' connections with mock (these don't use fixture)
        mock_conn = MagicMock()
        mock_conn.request = AsyncMock()
        device1.connection = mock_conn
        device2.connection = mock_conn

        # Mock discovery to return no devices for both calls
        # Use a proper async generator mock since discover_devices is an async generator
        async def empty_async_gen(*args, **kwargs):
            return
            yield  # Makes this an async generator

        with patch("lifx.network.discovery.discover_devices", empty_async_gen):
            await device1.set_group(label)
            mock_conn.request.reset_mock()
            await device2.set_group(label)

        # Both devices should have the same group name
        assert device1.group is not None
        assert device2.group is not None
        assert device1.group == device2.group == label

    async def test_set_location_empty_label_fails(self, device: Device) -> None:
        """Test that empty location label raises ValueError."""
        with pytest.raises(ValueError, match="Label cannot be empty"):
            with patch(
                "lifx.devices.base.DeviceConnection", return_value=device.connection
            ):
                await device.set_location("")

    async def test_set_location_long_label_fails(self, device: Device) -> None:
        """Test that location label over 32 characters raises ValueError."""
        long_label = "A" * 33
        with pytest.raises(ValueError, match="Label must be max 32 characters"):
            with patch(
                "lifx.devices.base.DeviceConnection", return_value=device.connection
            ):
                await device.set_location(long_label)

    async def test_set_group_empty_label_fails(self, device: Device) -> None:
        """Test that empty group label raises ValueError."""
        with pytest.raises(ValueError, match="Label cannot be empty"):
            with patch(
                "lifx.devices.base.DeviceConnection", return_value=device.connection
            ):
                await device.set_group("")

    async def test_set_group_long_label_fails(self, device: Device) -> None:
        """Test that group label over 32 characters raises ValueError."""
        long_label = "B" * 33
        with pytest.raises(ValueError, match="Label must be max 32 characters"):
            with patch(
                "lifx.devices.base.DeviceConnection", return_value=device.connection
            ):
                await device.set_group(long_label)

    def test_location_info_with_newer_updated_at(self) -> None:
        """Test label selection from most recent updated_at for same UUID.

        This test documents the LIFX protocol behavior: when multiple devices share
        the same location/group UUID, clients should display the label from the device
        with the most recent updated_at timestamp.

        Note: This is a protocol-level behavior that clients must implement, not
        enforced by the set_location/set_group methods themselves.
        """
        import time

        # Simulate two devices with the same location UUID but different timestamps
        location_uuid = uuid.uuid5(LIFX_LOCATION_NAMESPACE, "Kitchen").bytes
        older_timestamp = int(time.time() * 1e9) - 1000000000  # 1 second ago
        newer_timestamp = int(time.time() * 1e9)

        device1_location = CollectionInfo(
            uuid=location_uuid.hex(), label="Kitchen (old)", updated_at=older_timestamp
        )

        device2_location = CollectionInfo(
            uuid=location_uuid.hex(), label="Kitchen (new)", updated_at=newer_timestamp
        )

        # When displaying the location, clients should use the newer label
        # (this would be implemented in a client application, not in this library)
        locations = [device1_location, device2_location]
        most_recent = max(locations, key=lambda loc: loc.updated_at)

        assert most_recent.label == "Kitchen (new)"
        assert most_recent.updated_at == newer_timestamp

    def test_group_info_with_newer_updated_at(self) -> None:
        """Test label selection from most recent updated_at for same UUID.

        This test documents the LIFX protocol behavior: when multiple devices share
        the same location/group UUID, clients should display the label from the device
        with the most recent updated_at timestamp.

        Note: This is a protocol-level behavior that clients must implement, not
        enforced by the set_location/set_group methods themselves.
        """
        import time

        # Simulate two devices with the same group UUID but different timestamps
        group_uuid = uuid.uuid5(LIFX_GROUP_NAMESPACE, "Bedroom").bytes
        older_timestamp = int(time.time() * 1e9) - 1000000000  # 1 second ago
        newer_timestamp = int(time.time() * 1e9)

        device1_group = CollectionInfo(
            uuid=group_uuid.hex(), label="Bedroom (old)", updated_at=older_timestamp
        )

        device2_group = CollectionInfo(
            uuid=group_uuid.hex(), label="Bedroom (new)", updated_at=newer_timestamp
        )

        # When displaying the group, clients should use the newer label
        # (this would be implemented in a client application, not in this library)
        groups = [device1_group, device2_group]
        most_recent = max(groups, key=lambda grp: grp.updated_at)

        assert most_recent.label == "Bedroom (new)"
        assert most_recent.updated_at == newer_timestamp

    async def test_set_location_reuses_existing_uuid(self, device: Device) -> None:
        """Test that set_location reuses UUID when label already exists on network."""
        label = "Living Room"
        existing_uuid = uuid.uuid4().bytes  # Some existing UUID

        # Replace device's connection with mock

        # Mock discovered devices
        from lifx.network.discovery import DiscoveredDevice

        discovered_devices = [
            DiscoveredDevice(serial="d073d5aabbcc", ip="192.168.1.50")
        ]

        # Create mock response for the discovered device
        mock_state_location = MagicMock()
        mock_state_location.location = existing_uuid
        mock_state_location.label = label  # Already decoded by request()
        mock_state_location.updated_at = int(time.time() * 1e9)

        # Mock the discovery and connection for discovered device
        mock_discovered_conn = MagicMock(spec=DeviceConnection)
        mock_discovered_conn.request = AsyncMock(return_value=mock_state_location)

        # Create async generator mock for discover_devices
        async def mock_discover_gen(timeout: float = 5.0, **kwargs):
            for disc in discovered_devices:
                yield disc

        with (
            patch(
                "lifx.network.discovery.discover_devices", side_effect=mock_discover_gen
            ),
            patch("lifx.devices.base.DeviceConnection") as mock_conn_class,
        ):
            # Only one DeviceConnection created for discovered device
            mock_conn_class.return_value = mock_discovered_conn
            # Add async close method to mock
            mock_discovered_conn.close = AsyncMock()

            await device.set_location(label)

        # Verify the device used the existing UUID, not generated a new one
        device.connection.request.assert_called_once()
        call_args = device.connection.request.call_args
        packet = call_args[0][0]

        assert packet.location == existing_uuid
        assert packet.label == label.encode("utf-8")[:32].ljust(32, b"\x00")

        # Verify store was updated with location name
        stored_location = device.location
        assert stored_location is not None
        assert stored_location == label

    async def test_set_location_creates_new_uuid_when_not_found(
        self, device: Device
    ) -> None:
        """Test new UUID creation for new location label."""
        label = "New Location"

        # Replace device's connection with mock

        # Mock discovered devices with different label
        from lifx.network.discovery import DiscoveredDevice

        discovered_devices = [
            DiscoveredDevice(serial="d073d5aabbcc", ip="192.168.1.50")
        ]

        # Create mock response with different label
        mock_state_location = MagicMock()
        mock_state_location.location = uuid.uuid4().bytes
        mock_state_location.label = "Different Location"  # Already decoded by request()
        mock_state_location.updated_at = int(time.time() * 1e9)

        # Mock the discovery and connection for discovered device
        mock_discovered_conn = MagicMock(spec=DeviceConnection)
        mock_discovered_conn.request = AsyncMock(return_value=mock_state_location)

        # Create async generator mock for discover_devices
        async def mock_discover_gen(timeout: float = 5.0, **kwargs):
            for disc in discovered_devices:
                yield disc

        with (
            patch(
                "lifx.network.discovery.discover_devices", side_effect=mock_discover_gen
            ),
            patch("lifx.devices.base.DeviceConnection") as mock_conn_class,
        ):
            # Only one DeviceConnection created for discovered device
            mock_conn_class.return_value = mock_discovered_conn
            # Add async close method to mock
            mock_discovered_conn.close = AsyncMock()

            await device.set_location(label)

        # Verify the device generated a new UUID based on the label
        expected_uuid = uuid.uuid5(LIFX_LOCATION_NAMESPACE, label)
        device.connection.request.assert_called_once()
        call_args = device.connection.request.call_args
        packet = call_args[0][0]

        assert packet.location == expected_uuid.bytes
        assert packet.label == label.encode("utf-8")[:32].ljust(32, b"\x00")

    async def test_set_group_reuses_existing_uuid(self, device: Device) -> None:
        """Test that set_group reuses UUID when label already exists on network."""
        label = "Bedroom Lights"
        existing_uuid = uuid.uuid4().bytes  # Some existing UUID

        # Replace device's connection with mock

        # Mock discovered devices
        from lifx.network.discovery import DiscoveredDevice

        discovered_devices = [
            DiscoveredDevice(serial="d073d5aabbcc", ip="192.168.1.50")
        ]

        # Create mock response for the discovered device
        mock_state_group = MagicMock()
        mock_state_group.group = existing_uuid
        mock_state_group.label = label  # Already decoded by request()
        mock_state_group.updated_at = int(time.time() * 1e9)

        # Mock the discovery and connection for discovered device
        mock_discovered_conn = MagicMock(spec=DeviceConnection)
        mock_discovered_conn.request = AsyncMock(return_value=mock_state_group)

        # Create async generator mock for discover_devices
        async def mock_discover_gen(timeout: float = 5.0, **kwargs):
            for disc in discovered_devices:
                yield disc

        with (
            patch(
                "lifx.network.discovery.discover_devices", side_effect=mock_discover_gen
            ),
            patch("lifx.devices.base.DeviceConnection") as mock_conn_class,
        ):
            # Only one DeviceConnection created for discovered device
            mock_conn_class.return_value = mock_discovered_conn
            # Add async close method to mock
            mock_discovered_conn.close = AsyncMock()

            await device.set_group(label)

        # Verify the device used the existing UUID, not generated a new one
        device.connection.request.assert_called_once()
        call_args = device.connection.request.call_args
        packet = call_args[0][0]

        assert packet.group == existing_uuid
        assert packet.label == label.encode("utf-8")[:32].ljust(32, b"\x00")

        # Verify store was updated with group name
        stored_group = device.group
        assert stored_group is not None
        assert stored_group == label

    async def test_set_group_creates_new_uuid_when_not_found(
        self, device: Device
    ) -> None:
        """Test that set_group creates new UUID when label doesn't exist on network."""
        label = "New Group"

        # Replace device's connection with mock

        # Mock discovered devices with different label
        from lifx.network.discovery import DiscoveredDevice

        discovered_devices = [
            DiscoveredDevice(serial="d073d5aabbcc", ip="192.168.1.50")
        ]

        # Create mock response with different label
        mock_state_group = MagicMock()
        mock_state_group.group = uuid.uuid4().bytes
        mock_state_group.label = "Different Group"  # Already decoded by request()
        mock_state_group.updated_at = int(time.time() * 1e9)

        # Mock the discovery and connection for discovered device
        mock_discovered_conn = MagicMock(spec=DeviceConnection)
        mock_discovered_conn.request = AsyncMock(return_value=mock_state_group)

        # Create async generator mock for discover_devices
        async def mock_discover_gen(timeout: float = 5.0, **kwargs):
            for disc in discovered_devices:
                yield disc

        with (
            patch(
                "lifx.network.discovery.discover_devices", side_effect=mock_discover_gen
            ),
            patch("lifx.devices.base.DeviceConnection") as mock_conn_class,
        ):
            # Only one DeviceConnection created for discovered device
            mock_conn_class.return_value = mock_discovered_conn
            # Add async close method to mock
            mock_discovered_conn.close = AsyncMock()

            await device.set_group(label)

        # Verify the device generated a new UUID based on the label
        expected_uuid = uuid.uuid5(LIFX_GROUP_NAMESPACE, label)
        device.connection.request.assert_called_once()
        call_args = device.connection.request.call_args
        packet = call_args[0][0]

        assert packet.group == expected_uuid.bytes
        assert packet.label == label.encode("utf-8")[:32].ljust(32, b"\x00")
