"""Where a Mirror ring's effects start: the ring origin."""

from __future__ import annotations

import asyncio
import socket
import struct
from collections.abc import Iterator
from unittest.mock import MagicMock, patch

import pytest

from lifx.color import HSBK
from lifx.devices import MirrorLight
from lifx.effects.conductor import Conductor
from lifx.effects.frame_effect import FrameContext, FrameEffect
from lifx.products import get_product
from lifx.protocol import packets
from tests.test_devices import test_component_transitions as transitions

# Set64 colours start after the 36-byte header and the 10-byte payload prefix
# (tile index, length, rect and duration).
_SET64_COLOURS = 36 + 10
RING = 25


@pytest.fixture
def udp() -> Iterator[MagicMock]:
    """Capture the Animator's UDP datagrams; no acks ever arrive."""
    with patch.object(socket, "socket") as socket_class:
        sock = MagicMock()
        sock.recvfrom_into.side_effect = BlockingIOError
        socket_class.return_value = sock
        yield sock


@pytest.fixture
def rig(monkeypatch: pytest.MonkeyPatch) -> transitions.Rig:
    # The rig freezes time.monotonic, so settle delays must not use the timer.
    for module in ("state_manager", "base"):
        for name in (
            "COLOR_UPDATE_SETTLE_DELAY",
            "ZONE_UPDATE_SETTLE_DELAY",
            "POWER_ON_SETTLE_DELAY",
        ):
            monkeypatch.setattr(f"lifx.effects.{module}.{name}", 0, raising=False)
    rig = transitions.build_rig(267, monkeypatch)
    rig.light._capabilities = get_product(267)
    return rig


class _Pixels(FrameEffect):
    """Draws hue ``10 * p`` on frame pixel ``p``."""

    def __init__(self) -> None:
        super().__init__(power_on=False, fps=50.0)
        self.drawn = asyncio.Event()

    @property
    def name(self) -> str:
        return "pixels"

    def generate_frame(self, ctx: FrameContext) -> list[HSBK]:
        self.drawn.set()
        return [HSBK(i * 10, 1, 0.5, 3500) for i in range(ctx.pixel_count)]

    async def from_poweroff_hsbk(self, _light) -> HSBK:
        return HSBK(0, 0, 0, 3500)


def _last_tile(udp: MagicMock) -> list[tuple[int, ...]]:
    tiles = []
    for call in udp.sendto.call_args_list:
        data = bytes(call.args[0])
        if struct.unpack_from("<H", data, 32)[0] != packets.Tile.Set64.PKT_TYPE:
            continue
        flat = struct.unpack_from("<256H", data, _SET64_COLOURS)
        tiles.append([tuple(flat[i : i + 4]) for i in range(0, 256, 4)])
    return tiles[-1]


async def _pixels_shown(
    rig: transitions.Rig, udp: MagicMock
) -> tuple[list[int], list[int]]:
    """Run an effect for one frame and return the frame pixel on each zone.

    The result is the pixel on each front zone, then on each back ring index
    (zone order), so ``front[9]`` is the pixel at top centre on the front.
    """
    udp.sendto.reset_mock()
    conductor = Conductor()
    effect = _Pixels()
    await conductor.start(effect, [rig.light])
    await asyncio.wait_for(effect.drawn.wait(), 1)
    await conductor.stop([rig.light])
    sent = _last_tile(udp)
    by_hue = {HSBK(i * 10, 1, 0.5, 3500).as_tuple(): i for i in range(RING)}
    front, back = rig.positions
    return [by_hue[sent[p]] for p in front], [by_hue[sent[p]] for p in back]


async def test_the_default_origin_is_top_centre(rig: transitions.Rig, udp: MagicMock):
    assert rig.light.ring_origin == "top"

    front, back = await _pixels_shown(rig, udp)

    assert front[9] == 0
    # Back zone 40 is index 15 of the back ring and sits at top centre.
    assert back[40 - 25] == 0


@pytest.mark.parametrize(
    ("origin", "front_zone"),
    [("top", 9), ("bottom", 22), ("left", 3), ("right", 15), (0, 0), (24, 24), (6, 6)],
)
async def test_pixel_0_lands_on_the_origin_of_both_rings(
    rig: transitions.Rig, udp: MagicMock, origin, front_zone
):
    rig.light.ring_origin = origin

    front, back = await _pixels_shown(rig, udp)

    assert front[front_zone] == 0
    assert back[24 - front_zone] == 0
    # Pixels still run clockwise on the front: the next zone shows pixel 1.
    assert front[(front_zone + 1) % RING] == 1


@pytest.mark.parametrize("origin", ["top", "bottom", "left", "right", 0, 7, 24])
async def test_the_two_rings_show_the_same_pixel_at_the_same_spot(
    rig: transitions.Rig, udp: MagicMock, origin
):
    rig.light.ring_origin = origin

    front, back = await _pixels_shown(rig, udp)

    assert all(front[k] == back[24 - k] for k in range(RING))
    # Both rings turn clockwise: the front's next zone and the back's
    # previous index hold the next pixel.
    assert all(front[(k + 1) % RING] == (front[k] + 1) % RING for k in range(RING))
    assert all(back[(j - 1) % RING] == (back[j] + 1) % RING for j in range(RING))


async def test_changing_the_origin_applies_from_the_next_effect_start(
    rig: transitions.Rig, udp: MagicMock
):
    front, _ = await _pixels_shown(rig, udp)
    assert front[9] == 0

    rig.light.ring_origin = "bottom"
    assert rig.light.ring_origin == "bottom"
    front, _ = await _pixels_shown(rig, udp)
    assert front[22] == 0


def test_the_origin_can_be_set_when_constructing_a_mirror():
    mirror = MirrorLight("d073d5e00001", "192.0.2.1", ring_origin="left")

    assert mirror.ring_origin == "left"
    assert MirrorLight("d073d5e00001", "192.0.2.1").ring_origin == "top"
    assert MirrorLight("d073d5e00001", "192.0.2.1", ring_origin=12).ring_origin == 12


@pytest.mark.parametrize("bad", [25, -1, "centre", "TOP", 1.5, True, None])
def test_an_invalid_origin_is_refused(bad):
    mirror = MirrorLight("d073d5e00001", "192.0.2.1")

    with pytest.raises(ValueError, match="ring_origin"):
        mirror.ring_origin = bad
    with pytest.raises(ValueError, match="ring_origin"):
        MirrorLight("d073d5e00001", "192.0.2.1", ring_origin=bad)
    assert mirror.ring_origin == "top"
