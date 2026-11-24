"""Static pins for the request() response types (issue #356).

Pyright checks this file (it is in ``[tool.pyright] include``) but pytest never
collects it, because the file name does not start with ``test_``. Every
``assert_type`` here fails ``uv run pyright`` if the resolved type drifts.
The ignore comment at the end fails it too if ``_raise_if_unhandled()`` ever
accepts a Set's result again.
"""

# pyright: reportUnnecessaryTypeIgnoreComment=true

from __future__ import annotations

from typing import Literal, assert_type

from lifx.devices.base import Device
from lifx.network.connection import DeviceConnection
from lifx.protocol import packets
from lifx.protocol.protocol_types import LightHsbk


async def request_types(conn: DeviceConnection) -> None:
    """request() resolves each packet kind to its response type."""
    assert_type(
        await conn.request(packets.Device.GetVersion()),
        packets.Device.StateVersion,
    )
    assert_type(
        await conn.request(packets.Light.GetColor()),
        packets.Light.StateColor | packets.Device.StateUnhandled,
    )
    assert_type(
        await conn.request(packets.Light.GetInfrared()),
        packets.Light.StateInfrared | packets.Device.StateUnhandled,
    )
    assert_type(
        await conn.request(packets.MultiZone.GetColorZones(start_index=0, end_index=0)),
        packets.MultiZone.StateMultiZone
        | packets.MultiZone.StateZone
        | packets.Device.StateUnhandled,
    )
    assert_type(
        await conn.request(
            packets.Light.SetColor(
                color=LightHsbk(hue=0, saturation=0, brightness=0, kelvin=3500),
                duration=0,
            )
        ),
        Literal[True],
    )
    assert_type(
        await conn.request(
            packets.Tile.CopyFrameBuffer(
                tile_index=0,
                length=1,
                src_fb_index=0,
                dst_fb_index=0,
                src_x=0,
                src_y=0,
                dst_x=0,
                dst_y=0,
                width=8,
                height=8,
                duration=0,
            )
        ),
        Literal[True],
    )
    assert_type(
        await conn.request(packets.Device.EchoRequest(payload=b"")),
        packets.Device.EchoResponse,
    )


async def request_stream_types(conn: DeviceConnection) -> None:
    """request_stream() yields the same types request() returns."""
    async for state in conn.request_stream(packets.Device.GetLabel()):
        assert_type(state, packets.Device.StateLabel)
    async for zones in conn.request_stream(packets.MultiZone.GetExtendedColorZones()):
        assert_type(
            zones,
            packets.MultiZone.StateExtendedColorZones | packets.Device.StateUnhandled,
        )
    async for ack in conn.request_stream(packets.Device.SetLabel(label=b"")):
        assert_type(ack, Literal[True])
    async for echo in conn.request_stream(packets.Device.EchoRequest(payload=b"")):
        assert_type(echo, packets.Device.EchoResponse)


async def raise_if_unhandled_types(conn: DeviceConnection) -> None:
    """_raise_if_unhandled() narrows a capability Get result, rejects a Set's."""
    state = Device._raise_if_unhandled(await conn.request(packets.Light.GetInfrared()))
    assert_type(state, packets.Light.StateInfrared)
    # A Set raises from request() itself, so its result has nothing to check.
    Device._raise_if_unhandled(
        await conn.request(packets.Device.SetPower(level=0))  # pyright: ignore[reportArgumentType]
    )
