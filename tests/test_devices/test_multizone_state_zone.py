"""StateZone (503) replies from the embedded emulator, end to end.

Firmware answers a GetColorZones or SetColorZones whose range covers exactly
one zone with StateZone, which carries a single color, rather than a padded
StateMultiZone (506). lifx-emulator-core 3.14.0 does the same, so these tests
drive the public API against it and check both the reply shape the emulator
sent and what the library read from it (issue #324).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest

from lifx.color import HSBK
from lifx.devices.multizone import MultiZoneLight
from lifx.protocol import packets

pytestmark = pytest.mark.emulator

STRIP_SERIAL = "d073d5000006"


@pytest.fixture
async def strip(emulator_server) -> AsyncIterator[MultiZoneLight]:
    """A connected emulated strip with at least nine zones."""
    port, _, _ = emulator_server
    async with MultiZoneLight(
        serial=STRIP_SERIAL, ip="127.0.0.1", port=port, timeout=2.0, max_retries=2
    ) as light:
        assert await light.get_zone_count() >= 9
        yield light


def spy_replies(light: MultiZoneLight, monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    """Every reply the light's connection yields from now on.

    ``request()`` is a wrapper over ``request_stream()``, so one spy sees both:
    a Get yields its unpacked state packet, a Set yields ``True`` for the
    acknowledgement it asks for instead of a state reply.
    """
    replies: list[Any] = []
    connection = light.connection
    request_stream = connection.request_stream

    def spy_stream(packet: Any, *args: Any, **kwargs: Any) -> Any:
        async def generator() -> AsyncIterator[Any]:
            async for reply in request_stream(packet, *args, **kwargs):
                replies.append(reply)
                yield reply

        return generator()

    monkeypatch.setattr(connection, "request_stream", spy_stream)
    return replies


def _ramp(count: int) -> list[HSBK]:
    """A different hue in every zone."""
    return [
        HSBK(hue=i * 20 % 360, saturation=1.0, brightness=0.5, kelvin=3500)
        for i in range(count)
    ]


class TestGetColorZones:
    async def test_one_zone_request_is_read_as_one_color(
        self, strip: MultiZoneLight, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        colors = _ramp(await strip.get_zone_count())
        await strip.set_all_color_zones(colors)
        replies = spy_replies(strip, monkeypatch)

        assert await strip.get_color_zones(3, 3) == [colors[3]]

        assert len(replies) == 1
        assert isinstance(replies[0], packets.MultiZone.StateZone)
        assert replies[0].index == 3

    async def test_chunked_request_ending_in_one_zone(
        self, strip: MultiZoneLight, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # 0..8 is nine zones: one full chunk of eight, then zone 8 alone.
        colors = _ramp(await strip.get_zone_count())
        await strip.set_all_color_zones(colors)
        replies = spy_replies(strip, monkeypatch)

        assert await strip.get_color_zones(0, 8) == colors[:9]

        assert [type(reply) for reply in replies] == [
            packets.MultiZone.StateMultiZone,
            packets.MultiZone.StateZone,
        ]
        assert replies[1].index == 8


class TestSetColorZones:
    async def test_one_zone_set_is_acknowledged_and_reads_back(
        self, strip: MultiZoneLight, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A one-zone set asks for an acknowledgement, never a StateZone.

        Firmware answers a one-zone SetColorZones that asks for a response with
        StateZone, as the emulator does; the library asks for an
        acknowledgement instead, so the reply shape cannot trip it. The zone it
        wrote then reads back through a StateZone.
        """
        colors = _ramp(await strip.get_zone_count())
        await strip.set_all_color_zones(colors)
        replies = spy_replies(strip, monkeypatch)
        color = HSBK(hue=300, saturation=1.0, brightness=0.25, kelvin=3500)

        await strip.set_color_zones(5, 5, color)

        assert replies == [True]
        assert await strip.get_color_zones(5, 5) == [color]
        assert isinstance(replies[1], packets.MultiZone.StateZone)
        zones = await strip.get_all_color_zones()
        assert zones[5] == color
        assert zones[:5] + zones[6:] == colors[:5] + colors[6:]
