"""Comprehensive tests for device state management system."""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import lifx
from lifx.color import HSBK
from lifx.const import INVALID_AMBIENT_LIGHT_RESPONSE
from lifx.devices.base import (
    CollectionInfo,
    Connectivity,
    Device,
    DeviceCapabilities,
    DeviceState,
    DeviceVersion,
    FirmwareInfo,
    ThreadInfo,
    WifiInfo,
)
from lifx.devices.light import Light, LightState
from lifx.exceptions import (
    LifxTimeoutError,
    LifxUnsupportedCommandError,
    LifxUnsupportedDeviceError,
)
from lifx.products.registry import (
    ProductCapability,
    ProductInfo,
    TemperatureRange,
)
from lifx.protocol import packets
from lifx.protocol.protocol_types import (
    LightHsbk,
    ThreadLinkHealth,
    ThreadRoutingRole,
)
from tests.conftest import PROGRESS_TIMEOUT


def _thread_state_info() -> packets.Thread.StateInfo:
    """A ThreadStateInfo reply from a router with a healthy next-hop link."""
    return packets.Thread.StateInfo(
        rloc16=0x2C00,
        network_name=b"OpenThread-c9d1\x00",
        role=ThreadRoutingRole.ROUTER,
        link_health=ThreadLinkHealth(
            rloc16=0x2800, link_quality_in=3, link_quality_out=2, link_margin_db=55
        ),
    )


def _state_request_handler(
    signal: float = 7.943283890199382e-06, lux: float = 12.5, power: int = 65535
):
    """Return a request side effect covering every _initialize_state() query.

    ``power`` also decides whether an ambient light reading is usable: readings
    taken while the light is on are stored as INVALID_AMBIENT_LIGHT_RESPONSE.
    """

    async def mock_request(packet):
        if isinstance(packet, packets.Thread.GetInfo):
            return _thread_state_info()
        if isinstance(packet, packets.Sensor.GetAmbientLight):
            return packets.Sensor.StateAmbientLight(lux=lux)
        if isinstance(packet, packets.Light.GetColor):
            state = MagicMock()
            state.color = LightHsbk(hue=0, saturation=0, brightness=65535, kelvin=3500)
            state.power = power
            state.label = "Test"
            return state
        if isinstance(packet, packets.Device.GetLabel):
            return packets.Device.StateLabel(label=b"Test")
        if isinstance(packet, packets.Device.GetPower):
            return packets.Device.StatePower(level=power)
        if isinstance(packet, packets.Device.GetHostFirmware):
            return packets.Device.StateHostFirmware(
                build=0, version_major=2, version_minor=80
            )
        if isinstance(packet, packets.Device.GetWifiFirmware):
            return packets.Device.StateWifiFirmware(
                build=0, version_major=2, version_minor=80
            )
        if isinstance(packet, packets.Device.GetWifiInfo):
            return packets.Device.StateWifiInfo(signal=signal)
        if isinstance(packet, packets.Device.GetLocation):
            return packets.Device.StateLocation(
                location=b"\x00" * 16, label=b"Location", updated_at=0
            )
        if isinstance(packet, packets.Device.GetGroup):
            return packets.Device.StateGroup(
                group=b"\x00" * 16, label=b"Group", updated_at=0
            )
        raise AssertionError(f"Unexpected packet: {packet!r}")

    return mock_request


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
                    mock_conn.thread_connection = None
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
                    mock_conn.thread_connection = None
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

    @pytest.mark.asyncio
    async def test_connect_returns_light_for_cct_device(self, mock_product_info):
        """Test connect() returns Light for CCT products."""
        product_info = mock_product_info(
            pid=125,
            name="LIFX White to Warm US",
            has_color=False,
            has_multizone=False,
        )

        with (
            patch("lifx.devices.base.get_product", return_value=product_info),
            patch(
                "lifx.devices.base.Device.get_version",
                new_callable=AsyncMock,
                return_value=DeviceVersion(vendor=1, product=125),
            ),
            patch("lifx.devices.detection.is_ceiling_product", return_value=False),
        ):
            device = await Device.connect(ip="192.168.1.100", serial="d073d5010203")
            assert isinstance(device, Light)

    @pytest.mark.asyncio
    async def test_connect_raises_for_relay_device(self, mock_product_info):
        """Test Device.connect() raises LifxDeviceNotFoundError for relay devices."""
        product_info = mock_product_info(
            pid=70,
            name="LIFX Switch",
            has_color=False,
            has_multizone=False,
            has_relays=True,
        )

        with (
            patch("lifx.devices.base.get_product", return_value=product_info),
            patch(
                "lifx.devices.base.Device.get_version",
                new_callable=AsyncMock,
                return_value=DeviceVersion(vendor=1, product=70),
            ),
            patch("lifx.devices.detection.is_ceiling_product", return_value=False),
        ):
            with pytest.raises(
                LifxUnsupportedDeviceError, match="Relay/button-only device"
            ):
                await Device.connect(ip="192.168.1.100", serial="d073d5010203")

    @pytest.mark.asyncio
    async def test_connect_raises_for_button_only_device(self, mock_product_info):
        """Test connect() raises for button-only devices."""
        product_info = mock_product_info(
            pid=71,
            name="LIFX Button",
            has_color=False,
            has_multizone=False,
            has_buttons=True,
        )

        with (
            patch("lifx.devices.base.get_product", return_value=product_info),
            patch(
                "lifx.devices.base.Device.get_version",
                new_callable=AsyncMock,
                return_value=DeviceVersion(vendor=1, product=71),
            ),
            patch("lifx.devices.detection.is_ceiling_product", return_value=False),
        ):
            with pytest.raises(
                LifxUnsupportedDeviceError, match="Relay/button-only device"
            ):
                await Device.connect(ip="192.168.1.100", serial="d073d5010203")


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
        mock_color.label = "Test Light"

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
        assert light._state.label == "Test Light"
        assert light._state.power == 65535
        assert light._state.color.hue == pytest.approx(120.0, abs=0.01)
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

    @pytest.mark.asyncio
    async def test_initialize_state_skips_wifi_info_by_default(
        self, light, mock_product_info
    ):
        """Signal and RSSI stay None, but the RSSI unit follows the firmware."""
        light._capabilities = mock_product_info(has_color=True)
        light.connection.request.side_effect = _state_request_handler()

        await light._initialize_state()

        assert light._state is not None
        assert light._state.wifi_info.signal is None
        assert light._state.wifi_info.rssi is None
        assert light._state.wifi_info.rssi_unit == "dBm"
        assert not any(
            isinstance(call.args[0], packets.Device.GetWifiInfo)
            for call in light.connection.request.await_args_list
        )

    @pytest.mark.asyncio
    async def test_initialize_state_fetches_wifi_info_when_enabled(
        self, mock_device_factory, mock_product_info
    ):
        """fetch_wifi_info=True populates signal and RSSI from the device."""
        light = mock_device_factory(Light, fetch_wifi_info=True)
        light._capabilities = mock_product_info(has_color=True)
        light.connection.request.side_effect = _state_request_handler(
            signal=7.943283890199382e-06
        )

        await light._initialize_state()

        assert light._state is not None
        assert light._state.wifi_info.signal == pytest.approx(7.943283890199382e-06)
        assert light._state.wifi_info.rssi == -51
        assert light._state.wifi_info.rssi_unit == "dBm"

    @pytest.mark.asyncio
    async def test_initialize_state_skips_ambient_light_by_default(
        self, light, mock_product_info
    ):
        """The ambient light sensor is not queried unless it is enabled."""
        light._capabilities = mock_product_info(has_color=True)
        light.connection.request.side_effect = _state_request_handler()

        await light._initialize_state()

        assert light._state is not None
        assert light._state.ambient_light is None
        assert not any(
            isinstance(call.args[0], packets.Sensor.GetAmbientLight)
            for call in light.connection.request.await_args_list
        )

    @pytest.mark.asyncio
    async def test_initialize_state_fetches_ambient_light_when_enabled(
        self, mock_device_factory, mock_product_info
    ):
        """fetch_ambient_light=True populates the lux reading from the device."""
        light = mock_device_factory(Light, fetch_ambient_light=True)
        light._capabilities = mock_product_info(has_color=True)
        light.connection.request.side_effect = _state_request_handler(lux=42.0, power=0)

        await light._initialize_state()

        assert light._state is not None
        assert light._state.ambient_light == pytest.approx(42.0)


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
        assert light._state.color.brightness == pytest.approx(0.5, abs=0.001)

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
        # last_updated is stamped from time.time(), whose Windows resolution is
        # ~15.6 ms before Python 3.13. A 10 ms sleep can leave both stamps on
        # the same tick and turn the strict comparison below into a flake.
        await asyncio.sleep(PROGRESS_TIMEOUT)

        # Refresh
        await light.refresh_state()

        assert light._state.last_updated > old_timestamp

    @pytest.mark.asyncio
    async def test_refresh_state_skips_wifi_info_by_default(
        self, light, mock_product_info
    ):
        """A refresh leaves wifi_info alone when fetching is disabled."""
        light._capabilities = mock_product_info(has_color=True)
        light.connection.request.side_effect = _state_request_handler()
        await light._initialize_state()

        await light.refresh_state()

        assert light._state.wifi_info.signal is None
        assert not any(
            isinstance(call.args[0], packets.Device.GetWifiInfo)
            for call in light.connection.request.await_args_list
        )

    @pytest.mark.asyncio
    async def test_refresh_state_fetches_wifi_info_once_property_is_set(
        self, light, mock_product_info
    ):
        """Setting fetch_wifi_info makes the next refresh collect a reading."""
        light._capabilities = mock_product_info(has_color=True)
        light.connection.request.side_effect = _state_request_handler()
        await light._initialize_state()

        light.fetch_wifi_info = True
        await light.refresh_state()

        assert light._state.wifi_info.rssi == -51
        assert light._state.wifi_info.rssi_unit == "dBm"

    @pytest.mark.asyncio
    async def test_fetch_wifi_info_property_applies_to_initialization(
        self, light, mock_product_info
    ):
        """The property also covers the uninitialized-state path."""
        light._capabilities = mock_product_info(has_color=True)
        light.connection.request.side_effect = _state_request_handler()

        light.fetch_wifi_info = True
        await light.refresh_state()

        assert light._state is not None
        assert light._state.wifi_info.rssi == -51

    @pytest.mark.asyncio
    async def test_clearing_fetch_wifi_info_stops_the_query(
        self, mock_device_factory, mock_product_info
    ):
        """Clearing the property stops collecting readings from the next refresh."""
        light = mock_device_factory(Light, fetch_wifi_info=True)
        light._capabilities = mock_product_info(has_color=True)
        light.connection.request.side_effect = _state_request_handler()
        await light._initialize_state()
        light.connection.request.reset_mock()

        light.fetch_wifi_info = False
        await light.refresh_state()

        assert not any(
            isinstance(call.args[0], packets.Device.GetWifiInfo)
            for call in light.connection.request.await_args_list
        )

    @pytest.mark.asyncio
    async def test_fetch_wifi_info_property_reflects_constructor_argument(
        self, mock_device_factory, mock_product_info
    ):
        """The constructor argument is readable and refreshes keep following it."""
        light = mock_device_factory(Light, fetch_wifi_info=True)
        assert light.fetch_wifi_info is True
        light._capabilities = mock_product_info(has_color=True)
        light.connection.request.side_effect = _state_request_handler()
        await light._initialize_state()
        light.connection.request.reset_mock()

        await light.refresh_state()

        assert any(
            isinstance(call.args[0], packets.Device.GetWifiInfo)
            for call in light.connection.request.await_args_list
        )

    @pytest.mark.asyncio
    async def test_refresh_state_skips_ambient_light_by_default(
        self, light, mock_product_info
    ):
        """A refresh leaves ambient_light alone when fetching is disabled."""
        light._capabilities = mock_product_info(has_color=True)
        light.connection.request.side_effect = _state_request_handler()
        await light._initialize_state()

        await light.refresh_state()

        assert light._state.ambient_light is None
        assert not any(
            isinstance(call.args[0], packets.Sensor.GetAmbientLight)
            for call in light.connection.request.await_args_list
        )

    @pytest.mark.asyncio
    async def test_refresh_state_fetches_ambient_light_once_property_is_set(
        self, light, mock_product_info
    ):
        """Setting fetch_ambient_light makes the next refresh read the sensor."""
        light._capabilities = mock_product_info(has_color=True)
        light.connection.request.side_effect = _state_request_handler(lux=42.0, power=0)
        await light._initialize_state()

        light.fetch_ambient_light = True
        await light.refresh_state()

        assert light._state.ambient_light == pytest.approx(42.0)

    @pytest.mark.asyncio
    async def test_clearing_fetch_ambient_light_stops_the_query(
        self, mock_device_factory, mock_product_info
    ):
        """Clearing the property stops reading the sensor from the next refresh."""
        light = mock_device_factory(Light, fetch_ambient_light=True)
        light._capabilities = mock_product_info(has_color=True)
        light.connection.request.side_effect = _state_request_handler()
        await light._initialize_state()
        light.connection.request.reset_mock()

        light.fetch_ambient_light = False
        await light.refresh_state()

        assert not any(
            isinstance(call.args[0], packets.Sensor.GetAmbientLight)
            for call in light.connection.request.await_args_list
        )

    @pytest.mark.asyncio
    async def test_fetch_ambient_light_property_applies_to_initialization(
        self, light, mock_product_info
    ):
        """The ambient property also covers the uninitialized-state path."""
        light._capabilities = mock_product_info(has_color=True)
        light.connection.request.side_effect = _state_request_handler(lux=42.0, power=0)

        light.fetch_ambient_light = True
        await light.refresh_state()

        assert light._state is not None
        assert light._state.ambient_light == pytest.approx(42.0)

    @pytest.mark.asyncio
    async def test_base_device_refresh_state_honours_property(
        self, device, mock_product_info
    ):
        """Device.refresh_state() applies the property on both state paths."""
        device._capabilities = mock_product_info(has_color=False)
        device.connection.request.side_effect = _state_request_handler()

        # Uninitialized: the property drives the query during initialization
        device.fetch_wifi_info = True
        await device.refresh_state()
        assert device._state is not None
        assert device._state.wifi_info.rssi == -51

        # Initialized: the property still applies on the already-initialized path
        device._state.wifi_info = WifiInfo(signal=None, host_firmware=None)
        await device.refresh_state()
        assert device._state.wifi_info.rssi == -51

        # Cleared: a refresh leaves wifi_info alone again
        device.fetch_wifi_info = False
        device._state.wifi_info = WifiInfo(signal=None, host_firmware=None)
        await device.refresh_state()
        assert device._state.wifi_info.signal is None

    @pytest.mark.asyncio
    async def test_base_device_refresh_state_updates_timestamp(
        self, device, mock_product_info
    ):
        """Device.refresh_state() stamps last_updated so state reads as fresh."""
        device._capabilities = mock_product_info(has_color=False)
        device.connection.request.side_effect = _state_request_handler()
        await device._initialize_state()

        device._state.last_updated = 0.0
        await device.refresh_state()

        assert device._state.last_updated > 0.0
        assert device._state.is_fresh()

    @pytest.mark.asyncio
    async def test_clearing_fetch_wifi_info_clears_the_reading(
        self, mock_device_factory, mock_product_info
    ):
        """A refresh with the query off reports None instead of a stale reading."""
        light = mock_device_factory(Light, fetch_wifi_info=True)
        light._capabilities = mock_product_info(has_color=True)
        light.connection.request.side_effect = _state_request_handler()
        await light._initialize_state()
        assert light._state.wifi_info.rssi == -51

        light.fetch_wifi_info = False
        await light.refresh_state()

        assert light._state.wifi_info.signal is None
        assert light._state.wifi_info.rssi is None

    @pytest.mark.asyncio
    async def test_clearing_fetch_ambient_light_clears_the_reading(
        self, mock_device_factory, mock_product_info
    ):
        """A refresh with the sensor off reports None instead of a stale reading."""
        light = mock_device_factory(Light, fetch_ambient_light=True)
        light._capabilities = mock_product_info(has_color=True)
        light.connection.request.side_effect = _state_request_handler(lux=42.0, power=0)
        await light._initialize_state()
        assert light._state.ambient_light == pytest.approx(42.0)

        light.fetch_ambient_light = False
        await light.refresh_state()

        assert light._state.ambient_light is None

    @pytest.mark.asyncio
    async def test_ambient_light_read_while_light_is_on_is_marked_invalid(
        self, mock_device_factory, mock_product_info
    ):
        """A reading taken with the light on measures the light, not the room."""
        light = mock_device_factory(Light, fetch_ambient_light=True)
        light._capabilities = mock_product_info(has_color=True)
        light.connection.request.side_effect = _state_request_handler(
            lux=42.0, power=65535
        )

        await light._initialize_state()
        assert light._state.ambient_light == INVALID_AMBIENT_LIGHT_RESPONSE

        light.connection.request.side_effect = _state_request_handler(lux=42.0, power=0)
        await light.refresh_state()
        assert light._state.ambient_light == pytest.approx(42.0)

        light.connection.request.side_effect = _state_request_handler(
            lux=42.0, power=65535
        )
        await light.refresh_state()
        assert light._state.ambient_light == INVALID_AMBIENT_LIGHT_RESPONSE

    @pytest.mark.asyncio
    async def test_unsupported_ambient_sensor_does_not_fail_initialization(
        self, mock_device_factory, mock_product_info
    ):
        """A device that refuses the sensor query still initializes."""
        light = mock_device_factory(Light, fetch_ambient_light=True)
        light._capabilities = mock_product_info(has_color=True)
        handler = _state_request_handler()

        async def mock_request(packet):
            if isinstance(packet, packets.Sensor.GetAmbientLight):
                raise LifxUnsupportedCommandError("Device does not support packet 401")
            return await handler(packet)

        light.connection.request.side_effect = mock_request

        await light._initialize_state()

        assert light._state is not None
        assert light._state.ambient_light is None

    @pytest.mark.asyncio
    async def test_failed_optional_query_keeps_the_colour_reading(
        self, mock_device_factory, mock_product_info
    ):
        """A refused opt-in query does not discard the colour/power/label reading."""
        light = mock_device_factory(Light, fetch_wifi_info=True)
        light._capabilities = mock_product_info(has_color=True)
        light.connection.request.side_effect = _state_request_handler()
        await light._initialize_state()
        light._state.label = "Stale"
        handler = _state_request_handler()

        async def mock_request(packet):
            if isinstance(packet, packets.Device.GetWifiInfo):
                raise LifxTimeoutError("Timed out")
            return await handler(packet)

        light.connection.request.side_effect = mock_request

        await light.refresh_state()

        assert light._state.label == "Test"
        assert light._state.wifi_info.signal is None

    @pytest.mark.asyncio
    async def test_light_refresh_state_cancels_in_flight_requests(
        self, mock_device_factory, mock_product_info
    ):
        """A failed refresh cancels the requests still in flight beside it."""
        light = mock_device_factory(Light, fetch_ambient_light=True)
        light._capabilities = mock_product_info(has_color=True)
        light.connection.request.side_effect = _state_request_handler()
        await light._initialize_state()

        cancelled = asyncio.Event()

        async def mock_request(packet):
            if isinstance(packet, packets.Light.GetColor):
                raise LifxTimeoutError("Timed out")
            try:
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                cancelled.set()
                raise

        light.connection.request.side_effect = mock_request

        with pytest.raises(LifxTimeoutError):
            await light.refresh_state()

        assert cancelled.is_set()

    @pytest.mark.asyncio
    async def test_base_device_refresh_state_rereads_label_and_power(
        self, device, mock_product_info
    ):
        """Device.refresh_state() re-queries what it stamps as fresh."""
        device._capabilities = mock_product_info(has_color=False)
        device.connection.request.side_effect = _state_request_handler()
        await device._initialize_state()

        device._state.label = "Stale"
        device._state.power = 0
        device.connection.request.reset_mock()

        await device.refresh_state()

        requested = [call.args[0] for call in device.connection.request.await_args_list]
        assert any(isinstance(packet, packets.Device.GetLabel) for packet in requested)
        assert any(isinstance(packet, packets.Device.GetPower) for packet in requested)
        assert device._state.label != "Stale"
        assert device._state.power == 65535
        assert device._state.is_fresh()

    @pytest.mark.asyncio
    async def test_base_device_refresh_state_cancels_in_flight_requests(
        self, device, mock_product_info
    ):
        """A failed base refresh cancels the requests still in flight beside it."""
        device._capabilities = mock_product_info(has_color=False)
        device.connection.request.side_effect = _state_request_handler()
        await device._initialize_state()

        cancelled = asyncio.Event()

        async def mock_request(packet):
            if isinstance(packet, packets.Device.GetLabel):
                raise LifxTimeoutError("Timed out")
            try:
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                cancelled.set()
                raise

        device.connection.request.side_effect = mock_request

        with pytest.raises(LifxTimeoutError):
            await device.refresh_state()

        assert cancelled.is_set()

    @pytest.mark.asyncio
    async def test_set_group_updates_group_not_location(
        self, device, mock_product_info
    ):
        """set_group() writes the new group into state.group, leaving location."""
        device._capabilities = mock_product_info(has_color=False)
        device.connection.request.side_effect = _state_request_handler()
        await device._initialize_state()
        device._state.location = CollectionInfo(
            uuid="0" * 32, label="Home", updated_at=0
        )
        device._state.group = CollectionInfo(uuid="1" * 32, label="Old", updated_at=0)

        async def empty_async_gen(*args, **kwargs):
            return
            yield

        device.connection.request.side_effect = None
        device.connection.request.return_value = packets.Device.StateGroup(
            group=b"\x00" * 16, label=b"Kitchen", updated_at=0
        )

        with patch("lifx.network.discovery.discover_devices", empty_async_gen):
            with patch.object(Device, "_schedule_refresh", new_callable=AsyncMock):
                await device.set_group("Kitchen")

        assert device._state.group.label == "Kitchen"
        assert device._state.location.label == "Home"
        assert device._state.location.uuid == "0" * 32

    @pytest.mark.asyncio
    async def test_base_device_refresh_state_initializes_without_override(
        self, device, mock_product_info
    ):
        """Without an override, initialization applies the instance default."""
        device._capabilities = mock_product_info(has_color=False)
        device.connection.request.side_effect = _state_request_handler()

        await device.refresh_state()

        assert device._state is not None
        assert device._state.wifi_info.signal is None
        assert not any(
            isinstance(call.args[0], packets.Device.GetWifiInfo)
            for call in device.connection.request.await_args_list
        )


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
        before = time.time()
        label = await light.get_label()
        after = time.time()

        # State should be updated
        assert label == b"New Label"
        assert light.state.label == b"New Label"
        assert before <= light.state.last_updated <= after

    @pytest.mark.asyncio
    async def test_get_power_updates_state_timestamp(self, light, mock_product_info):
        """Test Device.get_power() updates state.last_updated when state exists."""
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

        # Mock get_power response for Device.get_power (base class)
        async def get_power_mock(packet):
            if isinstance(packet, packets.Device.GetPower):
                return packets.Device.StatePower(level=65535)

        light.connection.request.side_effect = get_power_mock

        # Call base Device.get_power() directly (Light overrides it)
        before = time.time()
        power = await Device.get_power(light)
        after = time.time()

        # State should be updated with timestamp
        assert power == 65535
        assert light.state.power == 65535
        assert before <= light.state.last_updated <= after


class TestStateDataclasses:
    """Tests for state dataclass properties and functionality."""

    def test_opt_in_fields_are_optional_keyword_arguments(self):
        """State can be built without the opt-in fields, as before they existed."""
        capabilities = DeviceCapabilities(
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
        firmware = FirmwareInfo(build=0, version_major=2, version_minor=80)

        state = LightState(
            model="Test",
            label="Test",
            serial="000000000000",
            mac_address="00:00:00:00:00:00",
            capabilities=capabilities,
            power=0,
            host_firmware=firmware,
            wifi_firmware=firmware,
            location=CollectionInfo("0000000000000000", "Location", 0),
            group=CollectionInfo("0000000000000000", "Group", 0),
            last_updated=time.time(),
            color=HSBK(hue=0.0, saturation=0.0, brightness=1.0, kelvin=3500),
        )

        assert state.ambient_light is None
        assert state.wifi_info.signal is None
        assert state.wifi_info.rssi is None

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
            wifi_info=WifiInfo(
                signal=None,
                host_firmware=FirmwareInfo(build=0, version_major=2, version_minor=80),
            ),
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
            wifi_info=WifiInfo(
                signal=None,
                host_firmware=FirmwareInfo(build=0, version_major=2, version_minor=80),
            ),
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
            wifi_info=WifiInfo(
                signal=None,
                host_firmware=FirmwareInfo(build=0, version_major=2, version_minor=80),
            ),
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
        device = Device(serial="d073d5010203", ip="192.168.1.100")
        product_info = mock_product_info(has_color=True)

        version = DeviceVersion(vendor=1, product=32)
        firmware = FirmwareInfo(build=0, version_major=2, version_minor=80)

        with patch("lifx.devices.base.get_product", return_value=product_info):
            device._process_capabilities(version, firmware)

        assert device._capabilities is product_info

    def test_process_capabilities_noop_when_already_set(self, mock_product_info):
        """Test _process_capabilities() is a no-op when capabilities already set."""
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


class TestStateBatchOnThreadDevice:
    """The shared state batch keeps working once a device is evidenced as Thread."""

    async def test_initialize_state_does_not_apply_the_wifi_firmware_guard(
        self, mock_product_info, mock_firmware_info
    ):
        """The batch sends GetWifiFirmware to a Thread device as it always has.

        The public ``get_wifi_firmware()`` refuses a Thread device, but state
        initialisation and refresh predate that guard and a refresh on an
        observed Thread device must not start failing because of it.
        """
        product_info = mock_product_info(has_color=True)
        firmware = mock_firmware_info()

        device = Device(serial="d073d5010203", ip="192.168.1.100")
        mock_conn = MagicMock()
        mock_conn.thread_connection = True
        device.connection = mock_conn
        device._capabilities = product_info

        requested_packets: list[type] = []

        async def mock_request(packet):
            requested_packets.append(type(packet))
            if isinstance(packet, packets.Device.GetLabel):
                return packets.Device.StateLabel(label=b"Test")
            elif isinstance(packet, packets.Device.GetPower):
                return packets.Device.StatePower(level=0)
            elif isinstance(
                packet,
                (packets.Device.GetHostFirmware, packets.Device.GetWifiFirmware),
            ):
                state_class = (
                    packets.Device.StateHostFirmware
                    if isinstance(packet, packets.Device.GetHostFirmware)
                    else packets.Device.StateWifiFirmware
                )
                return state_class(
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
            raise AssertionError(f"unexpected packet {packet!r}")

        mock_conn.request = AsyncMock(side_effect=mock_request)

        state = await device._initialize_state()

        assert packets.Device.GetWifiFirmware in requested_packets
        assert state.wifi_firmware.version_major == firmware.version_major


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
        mock_conn.thread_connection = None
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
        mock_conn.thread_connection = None
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
        device = Device(serial="d073d5010203", ip="192.168.1.100")
        mock_conn = MagicMock()
        mock_conn.thread_connection = None
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

    @pytest.mark.asyncio
    async def test_device_initialize_state_cancels_in_flight_requests(
        self, device, mock_product_info
    ):
        """Requests still in flight are cancelled when one of them fails.

        Every state request is scheduled up front, so a failure part-way
        through awaiting them leaves the rest pending. Without the cancel they
        would surface later as "exception was never retrieved".
        """
        device._capabilities = mock_product_info(has_color=False)
        cancelled = asyncio.Event()
        handler = _state_request_handler()

        async def mock_request(packet):
            if isinstance(packet, packets.Device.GetLabel):
                raise LifxTimeoutError("Timed out")
            if isinstance(packet, packets.Device.GetGroup):
                try:
                    await asyncio.sleep(10)
                except asyncio.CancelledError:
                    cancelled.set()
                    raise
            return await handler(packet)

        device.connection.request.side_effect = mock_request

        with pytest.raises(LifxTimeoutError):
            await device._initialize_state()

        assert cancelled.is_set()
        assert device._state is None


class TestThreadInfoInState:
    """state.thread_info follows fetch_thread_info as wifi_info follows its flag."""

    def test_device_state_thread_info_defaults_to_none(self) -> None:
        """thread_info is keyword-only with a None default, so it stays additive."""
        state = DeviceState(
            model="Test",
            label="Test",
            serial="d073d5010203",
            mac_address="d0:73:d5:01:02:03",
            capabilities=DeviceCapabilities(
                has_color=True,
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
            location=CollectionInfo(uuid="", label="", updated_at=0),
            group=CollectionInfo(uuid="", label="", updated_at=0),
            last_updated=0.0,
        )

        assert state.thread_info is None
        assert state.as_dict["thread_info"] is None

    async def test_initialize_state_skips_thread_info_by_default(
        self, light, mock_product_info
    ):
        """No ThreadGetInfo is sent unless a consumer asks for it."""
        light._capabilities = mock_product_info(has_color=True)
        light.connection.request.side_effect = _state_request_handler()

        await light._initialize_state()

        assert light._state.thread_info is None
        assert not any(
            isinstance(call.args[0], packets.Thread.GetInfo)
            for call in light.connection.request.await_args_list
        )

    async def test_initialize_state_fetches_thread_info_when_enabled(
        self, mock_device_factory, mock_product_info
    ):
        """fetch_thread_info=True populates state.thread_info from the device."""
        light = mock_device_factory(Light, fetch_thread_info=True)
        light._capabilities = mock_product_info(has_color=True)
        light.connection.request.side_effect = _state_request_handler()

        await light._initialize_state()

        assert light._state.thread_info == ThreadInfo(
            rloc=0x2C00,
            network_name="OpenThread-c9d1",
            role=ThreadRoutingRole.ROUTER,
            next_hop=0x2800,
            link_quality_in=3,
            link_quality_out=2,
            link_margin_db=55,
        )
        assert light._state.as_dict["thread_info"]["rssi"] == -45

    async def test_refresh_state_fetches_thread_info_once_property_is_set(
        self, light, mock_product_info
    ):
        """Setting fetch_thread_info makes the next refresh collect a reading."""
        light._capabilities = mock_product_info(has_color=True)
        light.connection.request.side_effect = _state_request_handler()
        await light._initialize_state()
        assert light._state.thread_info is None

        light.fetch_thread_info = True
        await light.refresh_state()

        assert light._state.thread_info is not None
        assert light._state.thread_info.role is ThreadRoutingRole.ROUTER

    async def test_clearing_fetch_thread_info_clears_the_reading(
        self, mock_device_factory, mock_product_info
    ):
        """A refresh with the flag cleared stores None, not a stale reading."""
        light = mock_device_factory(Light, fetch_thread_info=True)
        light._capabilities = mock_product_info(has_color=True)
        light.connection.request.side_effect = _state_request_handler()
        await light._initialize_state()
        light.connection.request.reset_mock()

        light.fetch_thread_info = False
        await light.refresh_state()

        assert light._state.thread_info is None
        assert not any(
            isinstance(call.args[0], packets.Thread.GetInfo)
            for call in light.connection.request.await_args_list
        )

    async def test_base_device_refresh_also_collects_thread_info(
        self, mock_device_factory, mock_product_info
    ):
        """The base Device refresh path stores the reading, not only Light's."""
        device = mock_device_factory(Device, fetch_thread_info=True)
        device._capabilities = mock_product_info(has_color=False)
        device.connection.request.side_effect = _state_request_handler()
        await device._initialize_state()
        device._state.thread_info = None

        await device.refresh_state()

        assert device._state.thread_info is not None

    async def test_thread_query_failure_leaves_none_and_keeps_the_batch(
        self, mock_device_factory, mock_product_info
    ):
        """A device that does not answer ThreadGetInfo still initialises."""
        light = mock_device_factory(Light, fetch_thread_info=True)
        light._capabilities = mock_product_info(has_color=True)
        handler = _state_request_handler()

        async def failing(packet):
            if isinstance(packet, packets.Thread.GetInfo):
                raise LifxTimeoutError("no reply")
            return await handler(packet)

        light.connection.request.side_effect = failing

        await light._initialize_state()

        assert light._state is not None
        assert light._state.thread_info is None

    async def test_thread_query_is_not_sent_to_an_evidenced_wifi_device(
        self, mock_device_factory, mock_product_info
    ):
        """The flag on a WiFi device costs no packet: the guard refuses first."""
        light = mock_device_factory(Light, fetch_thread_info=True)
        light._capabilities = mock_product_info(has_color=True)
        light.connection.thread_connection = False
        light.connection.request.side_effect = _state_request_handler()

        await light._initialize_state()

        assert light._state.thread_info is None
        assert not any(
            isinstance(call.args[0], packets.Thread.GetInfo)
            for call in light.connection.request.await_args_list
        )

    async def test_fetch_thread_info_property_reflects_constructor_argument(
        self, mock_device_factory
    ):
        """The constructor argument is readable through the property."""
        light = mock_device_factory(Light, fetch_thread_info=True)

        assert light.fetch_thread_info is True

    @pytest.mark.parametrize(
        "device_class",
        ["HevLight", "InfraredLight", "MultiZoneLight", "MatrixLight", "CeilingLight"],
    )
    def test_subclasses_accept_the_new_flags(self, device_class: str) -> None:
        """Every device class spells out fetch_thread_info and fetch_radio_info."""
        cls = getattr(lifx, device_class)
        device = cls(
            serial="d073d5010203",
            ip="192.0.2.10",
            fetch_thread_info=True,
            fetch_radio_info=True,
        )

        assert device.fetch_thread_info is True
        assert device.fetch_radio_info is True


class TestFetchRadioInfo:
    """fetch_radio_info sends the query matching the evidenced connectivity."""

    async def test_evidenced_thread_device_gets_thread_info_only(
        self, mock_device_factory, mock_product_info
    ):
        """A Thread device fetches thread_info and leaves the WiFi signal alone."""
        light = mock_device_factory(Light, fetch_radio_info=True)
        light._capabilities = mock_product_info(has_color=True)
        light._set_connectivity(Connectivity.THREAD)
        light.connection.request.side_effect = _state_request_handler()

        await light._initialize_state()

        assert light._state.thread_info is not None
        assert light._state.wifi_info.signal is None
        assert not any(
            isinstance(call.args[0], packets.Device.GetWifiInfo)
            for call in light.connection.request.await_args_list
        )

    async def test_evidenced_wifi_device_gets_wifi_info_only(
        self, mock_device_factory, mock_product_info
    ):
        """A WiFi device fetches the WiFi signal and sends no ThreadGetInfo."""
        light = mock_device_factory(Light, fetch_radio_info=True)
        light._capabilities = mock_product_info(has_color=True)
        light.connection.thread_connection = False
        light.connection.request.side_effect = _state_request_handler()

        await light._initialize_state()

        assert light._state.wifi_info.rssi == -51
        assert light._state.thread_info is None
        assert not any(
            isinstance(call.args[0], packets.Thread.GetInfo)
            for call in light.connection.request.await_args_list
        )

    async def test_mdns_wifi_record_is_evidence_for_the_wifi_query(
        self, mock_device_factory, mock_product_info
    ):
        """A TXT record saying WiFi is as much evidence as one saying Thread."""
        light = mock_device_factory(Light, fetch_radio_info=True)
        light._capabilities = mock_product_info(has_color=True)
        light._set_connectivity("wifi")
        light.connection.request.side_effect = _state_request_handler()

        await light._initialize_state()

        assert light._state.wifi_info.rssi == -51
        assert light._state.thread_info is None
        assert not any(
            isinstance(call.args[0], packets.Thread.GetInfo)
            for call in light.connection.request.await_args_list
        )

    async def test_unknown_connectivity_sends_neither_radio_query(
        self, mock_device_factory, mock_product_info
    ):
        """Without evidence no radio packet is sent, so nothing is wasted."""
        light = mock_device_factory(Light, fetch_radio_info=True)
        light._capabilities = mock_product_info(has_color=True)
        light.connection.request.side_effect = _state_request_handler()

        await light._initialize_state()

        assert light._state.wifi_info.signal is None
        assert light._state.thread_info is None
        assert not any(
            isinstance(call.args[0], packets.Device.GetWifiInfo)
            for call in light.connection.request.await_args_list
        )
        assert not any(
            isinstance(call.args[0], packets.Thread.GetInfo)
            for call in light.connection.request.await_args_list
        )

    async def test_radio_info_is_reevaluated_on_each_refresh(
        self, mock_device_factory, mock_product_info
    ):
        """Evidence arriving after initialisation is honoured by the next refresh."""
        light = mock_device_factory(Light, fetch_radio_info=True)
        light._capabilities = mock_product_info(has_color=True)
        light.connection.request.side_effect = _state_request_handler()
        await light._initialize_state()
        assert light._state.thread_info is None

        light.connection.thread_connection = True
        await light.refresh_state()

        assert light._state.thread_info is not None

    async def test_explicit_flag_still_wins_over_radio_choice(
        self, mock_device_factory, mock_product_info
    ):
        """fetch_wifi_info=True keeps querying WiFi regardless of the radio flag."""
        light = mock_device_factory(Light, fetch_wifi_info=True, fetch_radio_info=True)
        light._capabilities = mock_product_info(has_color=True)
        light.connection.request.side_effect = _state_request_handler()

        await light._initialize_state()

        assert light._state.wifi_info.rssi == -51

    def test_fetch_radio_info_property_is_settable(self, light) -> None:
        """The property toggles like the other opt-in readings."""
        assert light.fetch_radio_info is False
        light.fetch_radio_info = True
        assert light.fetch_radio_info is True
