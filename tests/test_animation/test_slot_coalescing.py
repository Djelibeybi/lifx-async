"""Concurrent light component effects share one tile behind one ack gate."""

from __future__ import annotations

import pytest

from lifx.animation.flow import ACK_INFLIGHT_LIMIT
from lifx.color import HSBK
from lifx.devices.component.effect_support import component_writer
from lifx.effects.frame_effect import FrameContext, FrameEffect
from tests.test_animation.conftest import MockUdpSocket, make_ack_datagram
from tests.test_animation.test_component_slots import (
    CYAN,
    RED,
    UPLIGHT,
    _ceiling,
    _frame,
    _tiles,
)
from tests.test_animation.test_component_slots import (
    sent as sent,  # noqa: F401 - fixture
)

ORANGE = HSBK(30, 1, 1, 3500)
VIOLET = HSBK(270, 1, 1, 3500)


class _OneFrame(FrameEffect):
    """Paints each participant one colour, by device index, for one frame."""

    def __init__(self, colours: list[HSBK]) -> None:
        super().__init__(power_on=False, fps=20.0)
        self.colours = colours
        self.contexts: list[FrameContext] = []

    @property
    def name(self) -> str:
        return "one-frame"

    def generate_frame(self, ctx: FrameContext) -> list[HSBK]:
        self.contexts.append(ctx)
        self.stop()
        return [self.colours[ctx.device_index]] * ctx.pixel_count


class TestSlotCoalescing:
    async def test_both_components_of_one_effect_send_one_tile_per_frame(
        self, sent: list[bytes]
    ) -> None:
        ceiling = _ceiling()
        effect = _OneFrame([ORANGE, VIOLET])
        effect.participants = [ceiling, ceiling]
        effect._animators = [
            await component_writer(ceiling, "uplight", 0),
            await component_writer(ceiling, "downlight", 0),
        ]

        await effect.async_play()

        (tile,) = _tiles(sent)
        assert tile[UPLIGHT] == ORANGE.as_tuple()
        assert tile[:UPLIGHT] == [VIOLET.as_tuple()] * UPLIGHT
        assert [ctx.elapsed_s for ctx in effect.contexts] == [
            effect.contexts[0].elapsed_s
        ] * 2

    async def test_a_gated_frame_rides_on_the_next_tile_any_slot_sends(
        self, sent: list[bytes], mock_udp_socket: MockUdpSocket
    ) -> None:
        ceiling = _ceiling()
        uplight = await component_writer(ceiling, "uplight", 0)
        downlight = await component_writer(ceiling, "downlight", 0)
        frame = _frame(64)
        for _ in range(ACK_INFLIGHT_LIMIT):
            downlight.send_frame(frame)

        gated = uplight.send_frame([RED])
        mock_udp_socket.queue_datagram(make_ack_datagram(ceiling.animator._source, 0))
        downlight.send_frame(frame)

        assert gated.gated
        assert _tiles(sent)[-1] == frame[:UPLIGHT] + [RED]

    async def test_two_component_effects_never_exceed_one_lights_traffic(
        self, sent: list[bytes]
    ) -> None:
        ceiling = _ceiling()
        uplight = await component_writer(ceiling, "uplight", 0)
        downlight = await component_writer(ceiling, "downlight", 0)
        frame = _frame(64)

        stats = []
        for _ in range(10):
            stats.append(uplight.send_frame([CYAN]))
            stats.append(downlight.send_frame(frame))

        assert len(sent) == ACK_INFLIGHT_LIMIT
        assert all(s.acks_outstanding <= ACK_INFLIGHT_LIMIT for s in stats)
        assert sum(not s.gated for s in stats) == ACK_INFLIGHT_LIMIT


@pytest.mark.parametrize("order", ["uplight-first", "downlight-first"])
async def test_one_tile_per_frame_whatever_the_participant_order(
    sent: list[bytes], order: str
) -> None:
    ceiling = _ceiling()
    components = [ceiling.uplight, ceiling.downlight]
    if order == "downlight-first":
        components.reverse()
    effect = _OneFrame([ORANGE, VIOLET])
    effect.participants = [ceiling, ceiling]
    effect._animators = [
        await component_writer(component.light, component.name, 0)
        for component in components
    ]

    await effect.async_play()

    assert len(_tiles(sent)) == 1
