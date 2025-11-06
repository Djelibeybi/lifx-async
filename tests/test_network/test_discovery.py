"""Tests for device discovery."""

from lifx.network.discovery import DiscoveredDevice, discover_devices


class TestDiscoveredDevice:
    """Test DiscoveredDevice class."""

    def test_device_creation(self) -> None:
        """Test creating a discovered device."""
        serial = "d073d5001234"
        device = DiscoveredDevice(
            serial=serial, ip="192.168.1.100", port=56700, service=1
        )

        assert device.serial == serial
        assert device.ip == "192.168.1.100"
        assert device.port == 56700
        assert device.service == 1

    def test_device_equality(self) -> None:
        """Test device equality based on serial."""
        serial = "d073d5001234"
        device1 = DiscoveredDevice(
            serial=serial, ip="192.168.1.100", port=56700, service=1
        )
        device2 = DiscoveredDevice(
            serial=serial, ip="192.168.1.101", port=56700, service=1
        )

        assert device1 == device2  # Same serial

    def test_device_inequality(self) -> None:
        """Test device inequality with different serial."""
        serial1 = "d073d5001234"
        serial2 = "d073d5005678"
        device1 = DiscoveredDevice(
            serial=serial1, ip="192.168.1.100", port=56700, service=1
        )
        device2 = DiscoveredDevice(
            serial=serial2, ip="192.168.1.100", port=56700, service=1
        )

        assert device1 != device2

    def test_device_hash(self) -> None:
        """Test device hashing for deduplication."""
        serial = "d073d5001234"
        device1 = DiscoveredDevice(
            serial=serial, ip="192.168.1.100", port=56700, service=1
        )
        device2 = DiscoveredDevice(
            serial=serial, ip="192.168.1.101", port=56700, service=1
        )

        # Can be added to set and deduplicated
        devices = {device1, device2}
        assert len(devices) == 1


class TestDiscoverDevices:
    """Test device discovery function."""

    async def test_discover_devices_timeout(self, emulator_server: int) -> None:
        """Test discovery with short timeout using mock server."""
        devices = await discover_devices(
            timeout=0.5,
            broadcast_address="127.0.0.1",
            port=emulator_server,
        )
        assert isinstance(devices, list)
        # Should discover the 7 mock devices
        assert len(devices) == 7

    async def test_discover_devices_default(self, emulator_server: int) -> None:
        """Test discovery with mock server."""
        devices = await discover_devices(
            broadcast_address="127.0.0.1",
            port=emulator_server,
        )
        assert isinstance(devices, list)
        # Should discover the 7 mock devices
        assert len(devices) == 7
