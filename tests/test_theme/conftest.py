"""Shared fixtures for theme tests."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from generate_theme_data import DATA_FILE

from lifx.color import HSBK
from lifx.devices.base import DeviceVersion
from lifx.devices.ceiling import CeilingLight
from lifx.devices.light import Light
from lifx.devices.matrix import MatrixLight, TileInfo
from lifx.devices.multizone import MultiZoneLight
from lifx.effects import EffectColorloop
from lifx.products import get_product
from lifx.protocol.protocol_types import LightWaveform
from lifx.theme import Theme
from lifx.theme.schema import load_theme_records

# The committed source records. The library is regenerated from this file
# whenever LIFX change the app's themes, so tests that need a theme count,
# category or palette read it from here rather than pinning a literal.
SOURCE_RECORDS: list[dict[str, Any]] = [
    record for _, record in load_theme_records(DATA_FILE)
]

# (alias, target) for every rename alias the source data declares.
SOURCE_ALIASES: list[tuple[str, str]] = sorted(
    (alias, record["slug"])
    for record in SOURCE_RECORDS
    for alias in record.get("aliases", ())
)

STRIP_SERIAL = "d073d5000005"
TILE_SERIAL = "d073d5000007"

RED = HSBK(hue=0, saturation=1.0, brightness=0.8, kelvin=3500)
GREEN = HSBK(hue=120, saturation=1.0, brightness=0.8, kelvin=3500)
BLUE = HSBK(hue=240, saturation=1.0, brightness=0.8, kelvin=3500)
# Values that no uint16 holds exactly, so every write is rounded.
AWKWARD = HSBK(hue=33.3333, saturation=0.33333, brightness=0.77777, kelvin=3500)


def make_theme(
    slug: str | None = "unit_test_a",
    *colors: HSBK,
    static_mode: str = "solid_static",
) -> Theme:
    """A caller-built theme carrying a slug, never a library theme."""
    return Theme(
        list(colors) or [RED, GREEN, AWKWARD], slug=slug, static_mode=static_mode
    )


def morphing(slug: str | None = "unit_test_m", *colors: HSBK) -> Theme:
    """A caller-built slugged theme whose mood runs firmware Morph."""
    return make_theme(slug, *(colors or (RED, GREEN, BLUE)), static_mode="blended")


async def _set_color(light: Light) -> None:
    await light.set_color(RED)


async def _set_brightness(light: Light) -> None:
    await light.set_brightness(0.5)


async def _set_waveform(light: Light) -> None:
    await light.set_waveform(RED, 1.0, 1, LightWaveform.SINE)


async def _pulse(light: Light) -> None:
    await light.pulse(RED, period=0.1, cycles=1)


async def _breathe(light: Light) -> None:
    await light.breathe(RED, period=0.1, cycles=1)


async def _start_effect(light: Light) -> None:
    try:
        await light.start_effect(EffectColorloop())
    finally:
        await light.stop_effect()


#: The writes that end a paint record on every kind of light.
COMMON_CLEARING_WRITES: dict[str, Callable[[Light], Awaitable[None]]] = {
    "set_color": _set_color,
    "set_brightness": _set_brightness,
    "set_waveform": _set_waveform,
    "pulse": _pulse,
    "breathe": _breathe,
    "start_effect": _start_effect,
}


async def assert_write_clears(
    light: Light,
    theme: Theme,
    kind: str,
    write: Callable[[Any], Awaitable[None]],
) -> None:
    """Paint ``theme`` as a theme or a mood, then check ``write`` ends the record."""
    if kind == "theme":
        await light.apply_theme(theme)
    else:
        await light.apply_mood(theme)
    assert (light.current_theme or light.current_mood) == theme.slug  # type: ignore[attr-defined]

    await write(light)

    assert light.current_theme is None  # type: ignore[attr-defined]
    assert light.current_mood is None  # type: ignore[attr-defined]


async def assert_power_keeps(light: Light, theme: Theme, on: bool) -> None:
    """Paint ``theme``, then check turning the light on or off keeps the record."""
    await light.apply_theme(theme)
    await light.set_power(on)
    assert light.current_theme == theme.slug  # type: ignore[attr-defined]
    await light.set_power(not on, duration=0.0)
    assert light.current_theme == theme.slug  # type: ignore[attr-defined]


@pytest.fixture
async def strip(emulator_server) -> AsyncIterator[MultiZoneLight]:
    """A connected strip, powered on; any effect is stopped afterwards."""
    port, _, _ = emulator_server
    async with MultiZoneLight(
        serial=STRIP_SERIAL, ip="127.0.0.1", port=port, timeout=2.0, max_retries=2
    ) as light:
        await light.set_power(True)
        yield light
        await light.stop_effect()


@pytest.fixture
async def matrix(emulator_server) -> AsyncIterator[MatrixLight]:
    """A connected matrix light, powered on; any effect is stopped afterwards."""
    port, _, _ = emulator_server
    async with MatrixLight(
        serial=TILE_SERIAL, ip="127.0.0.1", port=port, timeout=2.0, max_retries=2
    ) as light:
        await light.set_power(True)
        yield light
        await light.stop_effect()


@pytest.fixture
async def app(emulator_server) -> AsyncIterator[MatrixLight]:
    """Another client of the same light: what the LIFX app does."""
    port, _, _ = emulator_server
    async with MatrixLight(
        serial=TILE_SERIAL, ip="127.0.0.1", port=port, timeout=2.0, max_retries=2
    ) as light:
        yield light


def make_tile(
    tile_index: int = 0,
    *,
    user_x: float = 0.0,
    user_y: float = 0.0,
    width: int = 8,
    height: int = 8,
    accel: tuple[int, int, int] = (0, 0, 0),
) -> TileInfo:
    """Build a TileInfo with the geometry fields that matter for theming.

    Args:
        tile_index: Index of the tile in the chain
        user_x: Reported horizontal position, in tile-position units
        user_y: Reported vertical position, in tile-position units
        width: Tile width in pixels
        height: Tile height in pixels
        accel: Accelerometer reading (x, y, z), which decides
            ``nearest_orientation``. The default reads as Upright;
            ``(1, 0, 0)`` reads as RotatedRight.
    """
    return TileInfo(
        tile_index=tile_index,
        accel_meas_x=accel[0],
        accel_meas_y=accel[1],
        accel_meas_z=accel[2],
        user_x=user_x,
        user_y=user_y,
        width=width,
        height=height,
        supported_frame_buffers=2,
        device_version_vendor=1,
        device_version_product=27,
        device_version_version=0,
        firmware_build=1234567890,
        firmware_version_minor=50,
        firmware_version_major=3,
    )


@pytest.fixture
def mock_device_factory():
    """Factory for creating devices with mocked connections.

    This is imported from test_devices but redefined here to avoid
    pytest_plugins duplication issues.
    """

    def _create_device(
        device_class: type,
        serial: str = "d073d5010203",
        ip: str = "192.168.1.100",
        port: int = 56700,
        product: int = 27,
    ):
        device = device_class(serial=serial, ip=ip, port=port)
        # Replace device's connection with mock
        mock_conn = MagicMock()
        mock_conn.thread_connection = None
        mock_conn.request = AsyncMock()
        mock_conn.request_ack = AsyncMock()
        device.connection = mock_conn
        device._version = DeviceVersion(vendor=1, product=product)
        # A connected device populates this from the registry during setup;
        # set it directly so capability checks do not hit the mocked connection.
        device._capabilities = get_product(product)
        return device

    return _create_device


@pytest.fixture
def light(mock_device_factory) -> Light:
    """Create a test light with mocked theme methods."""
    light = mock_device_factory(Light)
    light.set_color = AsyncMock()
    light.set_power = AsyncMock()
    light.get_power = AsyncMock(return_value=False)
    return light


@pytest.fixture
def multizone_light(mock_device_factory) -> MultiZoneLight:
    """Create a test multizone light with mocked theme methods.

    Product 32 is a LIFX Z with extended multizone, so apply_theme takes the
    SetExtendedColorZones path.
    """
    light = mock_device_factory(MultiZoneLight, product=32)
    light.set_color = AsyncMock()
    light.set_extended_color_zones = AsyncMock()
    light.set_power = AsyncMock()
    light.get_power = AsyncMock(return_value=False)
    light.get_zone_count = AsyncMock(return_value=8)
    return light


@pytest.fixture
def matrix_light(mock_device_factory) -> MatrixLight:
    """Create a test matrix light with mocked theme methods."""
    device = mock_device_factory(MatrixLight)
    device.set_color = AsyncMock()
    device.set_matrix_colors = AsyncMock()
    device.set_power = AsyncMock()
    device.get_power = AsyncMock(return_value=False)
    device.get_device_chain = AsyncMock(return_value=[])
    return device


@pytest.fixture
def tile_light(mock_device_factory) -> MatrixLight:
    """Create a test LIFX Tile with mocked theme methods.

    Product 55 is the only chain-capable product and the only one with an
    accelerometer, so it is the only device whose reported orientation is real.
    """
    device = mock_device_factory(MatrixLight, product=55)
    device.set_color = AsyncMock()
    device.set_matrix_colors = AsyncMock()
    device.set_power = AsyncMock()
    device.get_power = AsyncMock(return_value=False)
    device.get_device_chain = AsyncMock(return_value=[])
    return device


@pytest.fixture
def ceiling_light(mock_device_factory) -> CeilingLight:
    """Create a test ceiling light with mocked theme methods.

    Product 201 is a LIFX Ceiling, which reports a single 16x8 tile covering
    both the downlight pixels and the uplight zone.
    """
    device = mock_device_factory(CeilingLight, product=201)
    device.set_color = AsyncMock()
    device.set_matrix_colors = AsyncMock()
    device.set_power = AsyncMock()
    device.get_power = AsyncMock(return_value=False)
    device.get_device_chain = AsyncMock(return_value=[])
    return device


def _matrix_with_theme_mocks(mock_device_factory, product: int) -> MatrixLight:
    device = mock_device_factory(MatrixLight, product=product)
    device.set_color = AsyncMock()
    device.set_matrix_colors = AsyncMock()
    device.set_power = AsyncMock()
    device.get_power = AsyncMock(return_value=False)
    device.get_device_chain = AsyncMock(return_value=[])
    return device


@pytest.fixture
def luna_light(mock_device_factory) -> MatrixLight:
    """Create a test LIFX Luna (product 219) with mocked theme methods."""
    return _matrix_with_theme_mocks(mock_device_factory, 219)


@pytest.fixture
def candle_light(mock_device_factory) -> MatrixLight:
    """Create a test LIFX Candle (product 57), a matrix product in no orientation
    group."""
    return _matrix_with_theme_mocks(mock_device_factory, 57)
