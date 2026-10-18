"""Unknown products are probed instead of refused.

A product id the registry does not list connects as the device class its
answers to the matrix chain and extended zones queries imply.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import pytest

from lifx.api import DeviceGroup
from lifx.color import HSBK
from lifx.devices import Device, Light, MatrixLight, MultiZoneLight
from lifx.devices.probe import probe_unknown_product
from lifx.exceptions import LifxTimeoutError
from lifx.network.discovery import DiscoveredDevice
from lifx.products.registry import get_registry
from lifx.theme import get_theme

pytestmark = pytest.mark.emulator

#: Serials of the emulated plain, multizone and matrix devices.
PLAIN_SERIAL = "d073d5000001"
MULTIZONE_SERIAL = "d073d5000005"
MATRIX_SERIAL = "d073d5000007"


@pytest.fixture
def forget_product(
    emulator_devices: DeviceGroup, monkeypatch: pytest.MonkeyPatch
) -> Callable[[str], Awaitable[int]]:
    """Return a coroutine function that drops an emulated device's registry entry."""

    async def forget(serial: str) -> int:
        device = next(d for d in emulator_devices.devices if d.serial == serial)
        try:
            pid = (await device.get_version()).product
        finally:
            await device.connection.close()
        monkeypatch.delitem(get_registry()._products, pid)
        return pid

    return forget


def _address(emulator_devices: DeviceGroup, serial: str) -> tuple[str, int]:
    device = next(d for d in emulator_devices.devices if d.serial == serial)
    return device.ip, device.port


class TestConnectUnknownProduct:
    async def test_matrix_answer_makes_a_matrix_light(
        self, emulator_devices: DeviceGroup, forget_product
    ) -> None:
        pid = await forget_product(MATRIX_SERIAL)
        ip, port = _address(emulator_devices, MATRIX_SERIAL)

        device = await Device.connect(ip, serial=MATRIX_SERIAL, port=port, timeout=2.0)
        async with device:
            assert type(device) is MatrixLight
            assert device.is_unknown_product
            assert device.capabilities is not None
            assert device.capabilities.name == f"Unknown product {pid}"
            assert device.capabilities.has_matrix
            assert device.capabilities.has_color
            await device.apply_theme(_theme())

    async def test_zones_answer_makes_a_multizone_light(
        self, emulator_devices: DeviceGroup, forget_product
    ) -> None:
        pid = await forget_product(MULTIZONE_SERIAL)
        ip, port = _address(emulator_devices, MULTIZONE_SERIAL)

        device = await Device.connect(
            ip, serial=MULTIZONE_SERIAL, port=port, timeout=2.0
        )
        async with device:
            assert type(device) is MultiZoneLight
            assert device.is_unknown_product
            assert device.capabilities is not None
            assert device.capabilities.name == f"Unknown product {pid}"
            await device.set_color_zones(0, 1, HSBK(120, 1.0, 0.5, 3500))

    async def test_no_answer_makes_a_plain_light(
        self, emulator_devices: DeviceGroup, forget_product
    ) -> None:
        pid = await forget_product(PLAIN_SERIAL)
        ip, port = _address(emulator_devices, PLAIN_SERIAL)

        device = await Device.connect(ip, serial=PLAIN_SERIAL, port=port, timeout=2.0)
        async with device:
            assert type(device) is Light
            assert device.is_unknown_product
            assert device.capabilities is not None
            assert device.capabilities.name == f"Unknown product {pid}"
            assert not device.capabilities.has_matrix
            assert not device.capabilities.has_multizone
            await device.set_color(HSBK(200, 1.0, 0.5, 3500))

    async def test_known_product_is_not_unknown(
        self, emulator_devices: DeviceGroup
    ) -> None:
        ip, port = _address(emulator_devices, PLAIN_SERIAL)
        device = await Device.connect(ip, serial=PLAIN_SERIAL, port=port, timeout=2.0)
        async with device:
            assert not device.is_unknown_product

    async def test_unknown_product_gets_the_default_kelvin_range(
        self, emulator_devices: DeviceGroup, forget_product
    ) -> None:
        await forget_product(PLAIN_SERIAL)
        ip, port = _address(emulator_devices, PLAIN_SERIAL)
        device = await Device.connect(ip, serial=PLAIN_SERIAL, port=port, timeout=2.0)
        async with device:
            assert isinstance(device, Light)
            assert (device.min_kelvin, device.max_kelvin) == (2500, 9000)

    async def test_firmware_refresh_keeps_the_synthetic_entry(
        self, emulator_devices: DeviceGroup, forget_product
    ) -> None:
        pid = await forget_product(PLAIN_SERIAL)
        ip, port = _address(emulator_devices, PLAIN_SERIAL)
        device = await Device.connect(ip, serial=PLAIN_SERIAL, port=port, timeout=2.0)
        async with device:
            assert device.capabilities is not None
            before = device.capabilities
            device._capabilities_firmware = (0, 0)
            await device.get_host_firmware()
            assert device.capabilities.pid == pid
            assert device.capabilities.name == before.name
            assert device.is_unknown_product

    async def test_loaded_capabilities_are_not_probed_again(
        self, emulator_devices: DeviceGroup, forget_product
    ) -> None:
        await forget_product(PLAIN_SERIAL)
        ip, port = _address(emulator_devices, PLAIN_SERIAL)
        device = await Device.connect(ip, serial=PLAIN_SERIAL, port=port, timeout=2.0)
        async with device:
            loaded = device.capabilities
            version = await device.get_version()
            firmware = await device.get_host_firmware()

            await device._load_capabilities(version, firmware)

            assert device.capabilities is loaded


class TestDiscoveryUnknownProduct:
    async def test_discovery_construction_follows_the_same_path(
        self, emulator_devices: DeviceGroup, forget_product
    ) -> None:
        pid = await forget_product(MATRIX_SERIAL)
        ip, port = _address(emulator_devices, MATRIX_SERIAL)
        discovered = DiscoveredDevice(
            serial=MATRIX_SERIAL,
            ip=ip,
            port=port,
            timeout=2.0,
            max_retries=2,
        )

        device = await discovered.create_device()

        assert type(device) is MatrixLight
        assert device.is_unknown_product
        assert device.capabilities is not None
        assert device.capabilities.name == f"Unknown product {pid}"


class TestFirstUse:
    async def test_a_directly_built_light_probes_on_entry(
        self, emulator_devices: DeviceGroup, forget_product
    ) -> None:
        pid = await forget_product(MULTIZONE_SERIAL)
        ip, port = _address(emulator_devices, MULTIZONE_SERIAL)

        async with MultiZoneLight(
            serial=MULTIZONE_SERIAL, ip=ip, port=port, timeout=2.0, max_retries=2
        ) as device:
            assert device.is_unknown_product
            assert device.capabilities is not None
            assert device.capabilities.pid == pid
            assert device.capabilities.has_multizone


def _theme():
    return get_theme("autumn")


class _SilentConnection:
    """A connection whose device never answers anything."""

    async def request(self, packet: object, timeout: float | None = None) -> object:
        raise LifxTimeoutError("no answer")


class TestSilentDevice:
    async def test_silence_makes_a_plain_light(self) -> None:
        info = await probe_unknown_product(
            _SilentConnection(),  # type: ignore[arg-type]
            4321,
        )

        assert info.name == "Unknown product 4321"
        assert info.has_color
        assert not info.has_matrix
        assert not info.has_multizone
