"""Shared fixtures for animation module tests."""

from __future__ import annotations

import socket
import struct
from collections import deque
from collections.abc import Generator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from lifx_emulator.factories import create_device
from lifx_emulator.protocol.protocol_types import LightHsbk

from lifx.devices.ceiling import CeilingLight

if TYPE_CHECKING:
    from lifx_emulator import EmulatedLifxServer
    from lifx_emulator.scenarios import HierarchicalScenarioManager


def make_ack_datagram(
    source: int, sequence: int, *, pkt_type: int = 45, size: int = 36
) -> bytes:
    """Build a wire-accurate Acknowledgement datagram for AckGate sweep tests.

    Parameters allow tests to craft wrong-type, wrong-source, or runt
    (undersized) datagrams for the untrusted-datagram validation branch
    matrix. Fields are only packed if `size` is large enough to hold them,
    so runt datagrams (e.g. `size=20`) come back truncated rather than
    raising.

    Args:
        source: uint32 protocol source ID to embed at header offset 4.
        sequence: uint8 sequence number to embed at header offset 23.
        pkt_type: uint16 packet type to embed at header offset 32
            (default 45 = Device.Acknowledgement).
        size: total datagram length in bytes (default 36 = a real ack).

    Returns:
        The crafted datagram as immutable bytes.
    """
    buf = bytearray(size)
    if size >= 2:
        struct.pack_into("<H", buf, 0, min(size, 0xFFFF))
    if size >= 8:
        struct.pack_into("<I", buf, 4, source)
    if size > 23:
        buf[23] = sequence
    if size >= 34:
        struct.pack_into("<H", buf, 32, pkt_type)
    return bytes(buf)


@dataclass
class MockUdpSocket:
    """Typed handle for the shared sweep-compatible mocked UDP socket.

    Attributes:
        sock: The mocked socket instance (`socket.socket(...)` return value).
        socket_class: The patched `socket.socket` class mock, for
            call-count assertions (e.g. "socket only created once").
    """

    sock: MagicMock
    socket_class: MagicMock
    _queue: deque[bytes] = field(default_factory=deque)

    def queue_datagram(self, data: bytes) -> None:
        """Queue a raw datagram to be returned by the next `recvfrom_into` call."""
        self._queue.append(data)


@pytest.fixture
def mock_udp_socket() -> Generator[MockUdpSocket, None, None]:
    """Patch `socket.socket` with a sweep-compatible mocked UDP socket.

    `recvfrom_into` defaults to raising `BlockingIOError` (empty queue),
    matching the contract `AckGate.sweep` depends on for its normal "no more
    datagrams" exit. Use `.queue_datagram()` to inject crafted ack datagrams
    (see `make_ack_datagram`) that get copied into the caller's buffer via
    slice assignment, mirroring the real `recvfrom_into` contract.
    """
    queue: deque[bytes] = deque()

    def _recvfrom_into(
        buffer: bytearray, *_args: object, **_kwargs: object
    ) -> tuple[int, tuple[str, int]]:
        if not queue:
            raise BlockingIOError()
        datagram = queue.popleft()
        buffer[: len(datagram)] = datagram
        return len(datagram), ("127.0.0.1", 56700)

    with patch.object(socket, "socket") as socket_class:
        sock = MagicMock()
        sock.recvfrom_into.side_effect = _recvfrom_into
        socket_class.return_value = sock
        yield MockUdpSocket(sock=sock, socket_class=socket_class, _queue=queue)


@dataclass
class MockTileInfo:
    """Mock TileInfo for testing without device dependency."""

    tile_index: int
    width: int
    height: int
    accel_meas_x: int = 0
    accel_meas_y: int = -100  # Default: right-side up
    accel_meas_z: int = 0
    user_x: float = 0.0
    user_y: float = 0.0
    supported_frame_buffers: int = 2
    device_version_vendor: int = 1
    device_version_product: int = 55
    device_version_version: int = 0
    firmware_build: int = 0
    firmware_version_minor: int = 0
    firmware_version_major: int = 3

    @property
    def total_zones(self) -> int:
        """Get total number of zones on this tile."""
        return self.width * self.height

    @property
    def requires_frame_buffer(self) -> bool:
        """Check if tile has more than 64 zones."""
        return self.total_zones > 64

    @property
    def nearest_orientation(self) -> str:
        """Determine the orientation of the tile from accelerometer data."""
        abs_x = abs(self.accel_meas_x)
        abs_y = abs(self.accel_meas_y)
        abs_z = abs(self.accel_meas_z)

        if (
            self.accel_meas_x == -1
            and self.accel_meas_y == -1
            and self.accel_meas_z == -1
        ):
            return "Upright"

        elif abs_x > abs_y and abs_x > abs_z:
            if self.accel_meas_x > 0:
                return "RotatedRight"
            else:
                return "RotatedLeft"

        elif abs_z > abs_x and abs_z > abs_y:
            if self.accel_meas_z > 0:
                return "FaceDown"
            else:
                return "FaceUp"

        else:
            if self.accel_meas_y > 0:
                return "UpsideDown"
            else:
                return "Upright"


@pytest.fixture
def mock_tile_upright() -> MockTileInfo:
    """Create a mock 8x8 tile in upright orientation."""
    return MockTileInfo(
        tile_index=0,
        width=8,
        height=8,
        accel_meas_x=0,
        accel_meas_y=-100,
        accel_meas_z=0,
    )


@pytest.fixture
def mock_tile_rotated_90() -> MockTileInfo:
    """Create a mock 8x8 tile rotated 90 degrees (RotatedRight)."""
    return MockTileInfo(
        tile_index=0,
        width=8,
        height=8,
        accel_meas_x=100,  # Positive X = RotatedRight
        accel_meas_y=0,
        accel_meas_z=0,
    )


@pytest.fixture
def mock_tile_rotated_180() -> MockTileInfo:
    """Create a mock 8x8 tile rotated 180 degrees (UpsideDown)."""
    return MockTileInfo(
        tile_index=0,
        width=8,
        height=8,
        accel_meas_x=0,
        accel_meas_y=100,  # Positive Y = UpsideDown
        accel_meas_z=0,
    )


@pytest.fixture
def mock_tile_rotated_270() -> MockTileInfo:
    """Create a mock 8x8 tile rotated 270 degrees (RotatedLeft)."""
    return MockTileInfo(
        tile_index=0,
        width=8,
        height=8,
        accel_meas_x=-100,  # Negative X = RotatedLeft
        accel_meas_y=0,
        accel_meas_z=0,
    )


@pytest.fixture
def mock_tile_chain() -> list[MockTileInfo]:
    """Create a mock chain of 3 tiles with different orientations."""
    return [
        MockTileInfo(
            tile_index=0,
            width=8,
            height=8,
            accel_meas_x=0,
            accel_meas_y=-100,  # Upright
            accel_meas_z=0,
        ),
        MockTileInfo(
            tile_index=1,
            width=8,
            height=8,
            accel_meas_x=100,  # RotatedRight
            accel_meas_y=0,
            accel_meas_z=0,
        ),
        MockTileInfo(
            tile_index=2,
            width=8,
            height=8,
            accel_meas_x=0,
            accel_meas_y=100,  # UpsideDown
            accel_meas_z=0,
        ),
    ]


@pytest.fixture
def mock_multizone_device() -> MagicMock:
    """Create a mock MultiZoneLight device."""
    device = MagicMock()
    device.capabilities = MagicMock()
    device.capabilities.has_extended_multizone = True
    device._zone_count = 82
    return device


@pytest.fixture
def mock_matrix_device() -> MagicMock:
    """Create a mock MatrixLight device."""
    device = MagicMock()
    device._device_chain = [
        MockTileInfo(tile_index=0, width=8, height=8),
    ]
    return device


def _force_tile_dimensions(device: object, width: int, height: int) -> None:
    """Override an emulated device's tile geometry after construction.

    `lifx_emulator.factories.create_device(product_id=..., tile_width=...,
    tile_height=...)` does NOT honour explicit tile dimensions for products
    whose spec registry already defines fixed dims (e.g. product 201 always
    builds as 16x8 regardless of the `tile_width`/`tile_height` kwargs --
    `DeviceBuilder._apply_product_defaults` unconditionally overwrites them
    from `lifx_emulator.products.specs.get_tile_dimensions`). `StateDeviceChain`,
    `Set64`, and `CopyFrameBuffer` are all driven purely from the per-tile
    `tile_devices[i]` dict records (`"width"`/`"height"`/`"colors"`), so
    rewriting those records after construction is sufficient to make the
    emulator behave as a genuine `width` x `height` large-tile device --
    no protocol-level difference from a real device shipping those dims.
    """
    state = device.state  # type: ignore[attr-defined]
    state.tile_width = width
    state.tile_height = height

    zones = width * height
    for tile in state.tile_devices:
        tile["width"] = width
        tile["height"] = height
        tile["colors"] = [
            LightHsbk(hue=0, saturation=0, brightness=32768, kelvin=3500)
            for _ in range(zones)
        ]


@pytest.fixture(scope="session")
def large_tile_matrix_device(
    emulator_server: tuple[int, EmulatedLifxServer, HierarchicalScenarioManager],
) -> Generator[CeilingLight, None, None]:
    """Create an emulated LIFX Ceiling 13x26 large-tile device (product 201).

    Mirrors the `ceiling_device` fixture pattern (`tests/conftest.py`), but
    with a non-64-divisible tile width (13) to exercise the row-aligned
    large-tile chunking path (ANIM-04) end-to-end against a real emulated
    device: 7 Set64 packets (6x52 + 1x26 colours) + 1 CopyFrameBuffer per
    frame. See `_force_tile_dimensions` for why the dims are patched after
    construction rather than passed to `create_device`.

    Yields:
        A `CeilingLight` connected to the emulated device.
    """
    port, server, scenario_manager = emulator_server

    if server is None:
        pytest.skip("Cannot create large-tile device with external emulator")

    device = create_device(
        product_id=201,
        serial="d073d5000201",
        scenario_manager=scenario_manager,
    )
    _force_tile_dimensions(device, width=13, height=26)
    server.add_device(device)

    yield CeilingLight(
        serial="d073d5000201",
        ip="127.0.0.1",
        port=port,
        timeout=2.0,
        max_retries=2,
    )

    server.remove_device("d073d5000201")
