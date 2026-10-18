"""The paint record remembers when its fade lands, and readers wait for it.

A paint written with a duration is still fading when the write returns, and
firmware reports the in-flight colors until the fade ends. These tests pin
the deadline the record carries and the wait before a verifying read.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from lifx.color import HSBK
from lifx.devices.multizone import MultiZoneLight
from lifx.devices.paint_record import PaintRecord, PaintTracking
from lifx.theme.theme import Theme

RED = HSBK(hue=0, saturation=1.0, brightness=1.0, kelvin=3500)


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin ``time.monotonic()`` at 100.0 where the record and the wait read it."""
    monkeypatch.setattr("lifx.devices.paint_record.time.monotonic", lambda: 100.0)
    monkeypatch.setattr("lifx.devices.light.time.monotonic", lambda: 100.0)


@pytest.fixture
def sleep(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    """Capture the wait instead of sleeping."""
    mock = AsyncMock()
    monkeypatch.setattr("lifx.devices.light.asyncio.sleep", mock)
    return mock


class TestSettlesAt:
    def test_no_fade_lands_at_once(self, clock: None) -> None:
        assert PaintTracking._settles_at(0.0) == 0.0

    def test_a_fade_lands_when_its_duration_is_up(self, clock: None) -> None:
        assert PaintTracking._settles_at(0.3) == pytest.approx(100.3)

    def test_zone_paint_carries_its_fade(
        self, multizone_light: MultiZoneLight, clock: None
    ) -> None:
        multizone_light._record_paint("mood", Theme([RED], slug="x"), [RED], 0.3)
        record = multizone_light._paint_record
        assert record is not None
        assert record.settles_at == pytest.approx(100.3)

    def test_zone_paint_defaults_to_no_fade(
        self, multizone_light: MultiZoneLight, clock: None
    ) -> None:
        multizone_light._record_paint("theme", Theme([RED], slug="x"), [RED])
        record = multizone_light._paint_record
        assert record is not None
        assert record.settles_at == 0.0


class TestAwaitPaintSettled:
    async def test_nothing_recorded_does_not_wait(
        self, multizone_light: MultiZoneLight, clock: None, sleep: AsyncMock
    ) -> None:
        multizone_light._paint_record = None
        await multizone_light._await_paint_settled()
        sleep.assert_not_awaited()

    async def test_a_landed_paint_does_not_wait(
        self, multizone_light: MultiZoneLight, clock: None, sleep: AsyncMock
    ) -> None:
        multizone_light._paint_record = PaintRecord("mood", "x", settles_at=99.9)
        await multizone_light._await_paint_settled()
        sleep.assert_not_awaited()

    async def test_a_fading_paint_waits_out_the_rest_of_its_fade(
        self,
        multizone_light: MultiZoneLight,
        monkeypatch: pytest.MonkeyPatch,
        sleep: AsyncMock,
    ) -> None:
        # Read before the wait and again after it; the event loop shares the
        # clock, so it keeps answering once the ticks run out.
        ticks = iter([100.0, 100.25])
        monkeypatch.setattr(
            "lifx.devices.light.time.monotonic", lambda: next(ticks, 100.25)
        )
        multizone_light._paint_record = PaintRecord("mood", "x", settles_at=100.25)
        await multizone_light._await_paint_settled()
        sleep.assert_awaited_once()
        assert sleep.await_args.args[0] == pytest.approx(0.25)

    async def test_a_paint_made_during_the_wait_is_waited_for_too(
        self,
        multizone_light: MultiZoneLight,
        monkeypatch: pytest.MonkeyPatch,
        sleep: AsyncMock,
    ) -> None:
        """The record is re-read after every sleep, so a newer fade is honoured."""
        ticks = iter([100.0, 100.0, 100.5])
        monkeypatch.setattr(
            "lifx.devices.light.time.monotonic", lambda: next(ticks, 100.5)
        )
        multizone_light._paint_record = PaintRecord("mood", "a", settles_at=100.25)
        newer = PaintRecord("mood", "b", settles_at=100.5)

        async def repaint(_remaining: float) -> None:
            multizone_light._paint_record = newer

        sleep.side_effect = repaint
        await multizone_light._await_paint_settled()

        assert [call.args[0] for call in sleep.await_args_list] == [
            pytest.approx(0.25),
            pytest.approx(0.5),
        ]
        assert multizone_light._paint_record is newer
