"""Tests for base device class."""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import fields
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
from lifx.devices.matrix import MatrixLight
from lifx.network.connection import DeviceConnection
from lifx.network.discovery import DiscoveredDevice
from lifx.protocol import packets
from lifx.protocol.protocol_types import DeviceService


class TestDevice:
    """Tests for Device class."""

    def test_fetch_flags_are_keyword_only(self) -> None:
        """The fetch flags cannot be passed positionally.

        Keeping them keyword-only stops a future parameter insertion from
        silently rebinding an existing positional argument, which is exactly
        how CeilingLight once swallowed its state_file path as a bool.
        """
        with pytest.raises(TypeError):
            Device("d073d5010203", "192.168.1.100", 56700, 5.0, 3, True)  # type: ignore[misc]

        device = Device(
            "d073d5010203",
            "192.168.1.100",
            56700,
            5.0,
            3,
            fetch_wifi_info=True,
            fetch_ambient_light=True,
        )
        assert device.fetch_wifi_info is True
        assert device.fetch_ambient_light is True

    def test_fetch_flags_default_to_disabled(self) -> None:
        """Both readings are opt-in, so a plain device collects neither."""
        device = Device(serial="d073d5010203", ip="192.168.1.100")

        assert device.fetch_wifi_info is False
        assert device.fetch_ambient_light is False

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

    def test_direct_loopback_construction_retains_caller_warning(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Wire suppression cannot disable advisories for public construction."""
        with caplog.at_level(logging.WARNING):
            Device(serial="d073d5010203", ip="127.0.0.1", port=12345)

        actions = {
            record.msg["action"]
            for record in caplog.records
            if isinstance(record.msg, dict)
        }
        assert actions == {"is_loopback", "non_standard_port"}

    def test_connectivity_defaults_to_wifi(self) -> None:
        """Direct construction defaults to WiFi connectivity."""
        device = Device(serial="d073d5010203", ip="192.0.2.10")

        assert device.connectivity == "wifi"

    @pytest.mark.parametrize("connectivity", ["wifi", "thread"])
    def test_set_connectivity_accepts_public_literals(self, connectivity: str) -> None:
        """The private discovery hand-off accepts both public literals."""
        device = Device(serial="d073d5010203", ip="192.0.2.10")

        device._set_connectivity(connectivity)  # type: ignore[arg-type]

        assert device.connectivity == connectivity

    @pytest.mark.parametrize("connectivity", ["", "Thread", "ethernet", None, 2])
    def test_set_connectivity_rejects_invalid_values_without_mutation(
        self, connectivity: object
    ) -> None:
        """Invalid private hand-off values do not change connectivity."""
        device = Device(serial="d073d5010203", ip="192.0.2.10")
        device._set_connectivity("thread")

        with pytest.raises(ValueError, match="Invalid connectivity value"):
            device._set_connectivity(connectivity)  # type: ignore[arg-type]

        assert device.connectivity == "thread"

    def test_adopt_cached_metadata_copies_connectivity(self) -> None:
        """Metadata adoption preserves the donor's discovery connectivity."""
        donor = Device(serial="d073d5010203", ip="192.0.2.10")
        recipient = Device(serial="d073d5010203", ip="192.0.2.10")
        donor._set_connectivity("thread")

        recipient.adopt_cached_metadata(donor)

        assert recipient.connectivity == "thread"

    def test_adopt_cached_metadata_preserves_default_wifi(self) -> None:
        """Adopting from a default device leaves WiFi connectivity intact."""
        donor = Device(serial="d073d5010203", ip="192.0.2.10")
        recipient = Device(serial="d073d5010203", ip="192.0.2.10")

        recipient.adopt_cached_metadata(donor)

        assert recipient.connectivity == "wifi"

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

    async def test_set_reboot(self, device: Device) -> None:
        """Test rebooting device."""

        # Mock SET operation returns True
        device.connection.request.return_value = True

        await device.set_reboot()

        # Verify request was called with SetReboot packet
        device.connection.request.assert_called_once()
        call_args = device.connection.request.call_args
        packet = call_args[0][0]
        assert isinstance(packet, packets.Device.SetReboot)

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
        device._host_firmware = FirmwareInfo(
            build=1234567890, version_major=3, version_minor=90
        )

        wifi_info = await device.get_wifi_info()

        assert isinstance(wifi_info, WifiInfo)
        assert wifi_info.rssi == -51
        assert wifi_info.rssi_unit == "dBm"

    async def test_get_wifi_info_fetches_firmware_for_rssi_unit(
        self, device: Device
    ) -> None:
        """An uncached firmware version is fetched to classify the RSSI unit."""
        wifi_state = packets.Device.StateWifiInfo(signal=7.943283890199382e-06)
        firmware_state = packets.Device.StateHostFirmware(
            build=1234567890, version_minor=77, version_major=2
        )

        async def request(packet):
            if isinstance(packet, packets.Device.GetWifiInfo):
                return wifi_state
            return firmware_state

        device.connection.request.side_effect = request

        wifi_info = await device.get_wifi_info()

        assert wifi_info.rssi == -51
        assert wifi_info.rssi_unit == "dB"
        assert device.host_firmware == FirmwareInfo(
            build=1234567890, version_major=2, version_minor=77
        )
        assert device.connection.request.await_count == 2

    @pytest.mark.parametrize("signal", [-1.0, -0.001, 0.0])
    async def test_get_wifi_info_returns_minimum_rssi_for_non_positive_signal(
        self, device: Device, signal: float
    ) -> None:
        """Test that WifiInfo returns -100 RSSI when signal is zero or negative."""
        mock_state = MagicMock()
        mock_state.signal = signal
        device.connection.request.return_value = mock_state
        device._host_firmware = FirmwareInfo(
            build=1234567890, version_major=3, version_minor=90
        )

        wifi_info = await device.get_wifi_info()

        assert isinstance(wifi_info, WifiInfo)
        assert wifi_info.rssi == -100

    @pytest.mark.parametrize(
        ("version_major", "version_minor", "expected_unit"),
        [
            (2, 76, "dB"),
            (2, 77, "dB"),
            (2, 78, "dBm"),
            (3, 1, "dBm"),
        ],
    )
    def test_wifi_info_rssi_unit_follows_firmware_boundary(
        self, version_major: int, version_minor: int, expected_unit: str
    ) -> None:
        wifi_info = WifiInfo(
            signal=7.943283890199382e-06,
            host_firmware=FirmwareInfo(
                build=1234567890,
                version_major=version_major,
                version_minor=version_minor,
            ),
        )

        assert wifi_info.rssi_unit == expected_unit

    def test_wifi_info_rssi_unit_unknown_without_firmware(self) -> None:
        """RSSI units remain unknown until host firmware is available."""
        wifi_info = WifiInfo(signal=7.943283890199382e-06, host_firmware=None)

        assert wifi_info.rssi_unit is None

    def test_wifi_info_without_signal_has_no_rssi(self) -> None:
        """An unfetched signal yields no RSSI but still classifies the unit."""
        wifi_info = WifiInfo(
            signal=None,
            host_firmware=FirmwareInfo(
                build=1234567890, version_major=3, version_minor=90
            ),
        )

        assert wifi_info.signal is None
        assert wifi_info.rssi is None
        assert wifi_info.rssi_unit == "dBm"

    def test_wifi_info_does_not_retain_host_firmware(self) -> None:
        """host_firmware is init-only: DeviceState owns the firmware version."""
        wifi_info = WifiInfo(
            signal=None,
            host_firmware=FirmwareInfo(
                build=1234567890, version_major=3, version_minor=90
            ),
        )

        assert "host_firmware" not in vars(wifi_info)
        assert "host_firmware" not in {f.name for f in fields(wifi_info)}

    def test_wifi_info_as_dict(self) -> None:
        """as_dict exposes signal, RSSI and unit only."""
        wifi_info = WifiInfo(
            signal=7.943283890199382e-06,
            host_firmware=FirmwareInfo(build=1, version_major=2, version_minor=77),
        )

        assert wifi_info.as_dict == {
            "signal": 7.943283890199382e-06,
            "rssi": -51,
            "rssi_unit": "dB",
        }

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
        label = "Test Lights"

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
        label = "Test Lights"
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
        label = "Test Lights"
        existing_uuid = uuid.uuid4().bytes  # Some existing UUID

        # Replace device's connection with mock

        # Mock discovered devices
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

    @pytest.mark.parametrize(
        ("collection", "label", "namespace"),
        [
            ("location", "Query Failure Location", LIFX_LOCATION_NAMESPACE),
            ("group", "Query Failure Group", LIFX_GROUP_NAMESPACE),
        ],
    )
    async def test_set_collection_falls_back_when_device_query_fails(
        self,
        device: Device,
        collection: str,
        label: str,
        namespace: uuid.UUID,
    ) -> None:
        """One unreachable discovery result does not prevent the update."""
        discovered = DiscoveredDevice(
            serial="d073d5aabbcc",
            ip="192.168.1.50",
        )

        async def mock_discover_gen(timeout: float = 5.0, **kwargs):
            yield discovered

        mock_discovered_conn = MagicMock(spec=DeviceConnection)
        mock_discovered_conn.request = AsyncMock(
            side_effect=RuntimeError("synthetic query failure")
        )
        mock_discovered_conn.close = AsyncMock()

        with (
            patch(
                "lifx.network.discovery.discover_devices",
                side_effect=mock_discover_gen,
            ),
            patch(
                "lifx.devices.base.DeviceConnection",
                return_value=mock_discovered_conn,
            ),
        ):
            await getattr(device, f"set_{collection}")(label)

        mock_discovered_conn.close.assert_awaited_once_with()
        packet = device.connection.request.call_args.args[0]
        assert getattr(packet, collection) == uuid.uuid5(namespace, label).bytes

    @pytest.mark.parametrize(
        ("collection", "label", "namespace"),
        [
            ("location", "Discovery Failure Location", LIFX_LOCATION_NAMESPACE),
            ("group", "Discovery Failure Group", LIFX_GROUP_NAMESPACE),
        ],
    )
    async def test_set_collection_falls_back_when_discovery_fails(
        self,
        device: Device,
        collection: str,
        label: str,
        namespace: uuid.UUID,
    ) -> None:
        """A failed discovery sweep still uses the deterministic UUID."""

        async def failed_discovery(timeout: float = 5.0, **kwargs):
            raise RuntimeError("synthetic discovery failure")
            yield

        with patch(
            "lifx.network.discovery.discover_devices",
            side_effect=failed_discovery,
        ):
            await getattr(device, f"set_{collection}")(label)

        packet = device.connection.request.call_args.args[0]
        assert getattr(packet, collection) == uuid.uuid5(namespace, label).bytes

    async def test_set_location_updates_initialised_state(self, device: Device) -> None:
        """A successful location update is mirrored into cached device state."""
        label = "Cached Location"
        expected_uuid = uuid.uuid5(LIFX_LOCATION_NAMESPACE, label)

        async def empty_discovery(timeout: float = 5.0, **kwargs):
            return
            yield

        device._state = MagicMock()
        device.connection.request.return_value = MagicMock()

        with (
            patch(
                "lifx.network.discovery.discover_devices",
                side_effect=empty_discovery,
            ),
            patch.object(
                device,
                "_schedule_refresh",
                new_callable=AsyncMock,
            ) as schedule_refresh,
        ):
            await device.set_location(label)

        assert device._state.location.uuid == expected_uuid.hex
        assert device._state.location.label == label
        assert device._state.location.updated_at > 0
        schedule_refresh.assert_awaited_once_with()


class TestAddressEntryPointGate:
    """The address gate at `Device.__init__`, `from_ip()` and `connect()`.

    All three delegate to :func:`lifx.network.address.validate_address`, so
    what is asserted here is that each one calls it, and calls it *before*
    building anything. A zone-less IPv6 link-local address is the case that
    motivated the gate (IPV6-02): the branch logged a warning and carried
    on, so the caller paid a full silent request timeout for a permanent
    configuration error.

    The elapsed-time assertions are deliberately loose. They are not
    performance tests: they distinguish "rejected before a socket existed"
    from "rejected after the request timeout", which are three orders of
    magnitude apart.
    """

    SERIAL = "d073d5001234"
    ZONE_LESS = "fe80::1"
    ZONED = "fe80::1%en0"

    def test_init_rejects_zone_less_link_local(self) -> None:
        """Construction raises, naming the missing zone identifier."""
        started = time.perf_counter()
        with pytest.raises(ValueError, match="zone identifier"):
            Device(serial=self.SERIAL, ip=self.ZONE_LESS)
        assert time.perf_counter() - started < 0.1

    def test_init_accepts_zoned_link_local(self) -> None:
        """The zoned form is reachable, so it must construct."""
        device = Device(serial=self.SERIAL, ip=self.ZONED)
        assert device.ip == self.ZONED

    async def test_from_ip_rejects_zone_less_link_local(self) -> None:
        """`from_ip()` raises before any connection object is built."""
        with patch("lifx.devices.base.DeviceConnection") as mock_conn_class:
            started = time.perf_counter()
            with pytest.raises(ValueError, match="zone identifier"):
                await Device.from_ip(ip=self.ZONE_LESS)
            assert time.perf_counter() - started < 0.1

        mock_conn_class.assert_not_called()

    async def test_from_ip_accepts_zoned_link_local(self) -> None:
        """The acceptance side, asserted rather than assumed."""
        device = await Device.from_ip(ip=self.ZONED, serial=self.SERIAL)
        assert isinstance(device, Device)
        assert device.ip == self.ZONED

    async def test_from_ip_emits_each_caller_advisory_once(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Factory validation cannot duplicate constructor advisories."""
        with caplog.at_level(logging.WARNING):
            await Device.from_ip(ip="127.0.0.1", port=12345, serial=self.SERIAL)

        actions = [
            record.msg.get("action")
            for record in caplog.records
            if isinstance(record.msg, dict)
        ]
        assert actions.count("is_loopback") == 1
        assert actions.count("non_standard_port") == 1
        port_record = next(
            record.msg
            for record in caplog.records
            if isinstance(record.msg, dict)
            and record.msg.get("action") == "non_standard_port"
        )
        assert port_record["class"] == "Device"
        assert port_record["method"] == "from_ip"

    async def test_subclass_factory_advisory_names_the_subclass(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Inherited factories attribute endpoint warnings to their real class."""
        with caplog.at_level(logging.WARNING):
            await MatrixLight.from_ip(
                ip="127.0.0.1",
                port=12345,
                serial=self.SERIAL,
            )

        port_record = next(
            record.msg
            for record in caplog.records
            if isinstance(record.msg, dict)
            and record.msg.get("action") == "non_standard_port"
        )
        assert port_record["class"] == "MatrixLight"
        assert port_record["method"] == "from_ip"

    async def test_from_ip_without_serial_suppresses_constructor_advisories(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Serial discovery does not repeat the public factory warnings."""
        connection = MagicMock()
        connection.serial = self.SERIAL
        connection.request = AsyncMock(
            return_value=packets.Device.StateService(
                service=DeviceService.UDP,
                port=12345,
            )
        )
        connection.close = AsyncMock()

        with (
            caplog.at_level(logging.WARNING),
            patch("lifx.devices.base.DeviceConnection", return_value=connection),
        ):
            device = await Device.from_ip(ip="127.0.0.1", port=12345)

        actions = [
            record.msg.get("action")
            for record in caplog.records
            if isinstance(record.msg, dict)
        ]
        assert isinstance(device, Device)
        assert actions.count("is_loopback") == 1
        assert actions.count("non_standard_port") == 1

    async def test_connect_rejects_zone_less_link_local(self) -> None:
        """`connect()` raises with no DeviceConnection constructed.

        The serial-less leg builds a ``DeviceConnection`` directly instead of
        going through ``__init__``, so without its own gate this entry point
        reproduced the exact timeout the other three now avoid.
        """
        with patch("lifx.devices.base.DeviceConnection") as mock_conn_class:
            started = time.perf_counter()
            with pytest.raises(ValueError, match="zone identifier"):
                await Device.connect(ip=self.ZONE_LESS)
            assert time.perf_counter() - started < 0.1

        mock_conn_class.assert_not_called()

    async def test_connect_accepts_zoned_link_local(self) -> None:
        """A zoned address reaches the existing product-lookup path."""
        with patch.object(
            Device,
            "get_version",
            AsyncMock(return_value=DeviceVersion(vendor=1, product=27)),
        ):
            device = await Device.connect(ip=self.ZONED, serial=self.SERIAL)

        assert device.ip == self.ZONED

    async def test_connect_emits_each_caller_advisory_once(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Temporary and concrete devices do not repeat factory advisories."""
        with (
            caplog.at_level(logging.WARNING),
            patch.object(
                Device,
                "get_version",
                AsyncMock(return_value=DeviceVersion(vendor=1, product=27)),
            ),
        ):
            await Device.connect(ip="127.0.0.1", port=12345, serial=self.SERIAL)

        actions = [
            record.msg.get("action")
            for record in caplog.records
            if isinstance(record.msg, dict)
        ]
        assert actions.count("is_loopback") == 1
        assert actions.count("non_standard_port") == 1
        port_record = next(
            record.msg
            for record in caplog.records
            if isinstance(record.msg, dict)
            and record.msg.get("action") == "non_standard_port"
        )
        assert port_record["method"] == "connect"

    @pytest.mark.parametrize(
        ("ip", "message"),
        [
            ("::ffff:192.0.2.1", "IPv4-mapped"),
            ("fe80::1%", "Invalid IP address format"),
            ("FE80::1", "zone identifier"),
            ("fe80:0:0:0:0:0:0:1", "zone identifier"),
            ("0.0.0.0", "Unspecified IP address"),
            ("", "No IP address"),
        ],
    )
    def test_init_delegates_the_whole_rule_set(self, ip: str, message: str) -> None:
        """Every helper rejection is reachable through construction.

        `Device.__init__` keeps no address logic of its own, so these all
        arrive from the one shared implementation.
        """
        with pytest.raises(ValueError, match=message):
            Device(serial=self.SERIAL, ip=ip)

    def test_serial_and_port_checks_are_untouched(self) -> None:
        """The non-address checks stay exactly where they were (D-05)."""
        with pytest.raises(ValueError, match="all zeros"):
            Device(serial="000000000000", ip="192.168.1.10")

        with pytest.raises(ValueError, match="Broadcast serial number"):
            Device(serial="ffffffffffff", ip="192.168.1.10")

        with pytest.raises(ValueError, match="Port must be between 1024 and 65535"):
            Device(serial=self.SERIAL, ip="192.168.1.10", port=1023)
