"""Tests for EffectScroll."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from lifx.color import HSBK
from lifx.devices.light import Light
from lifx.devices.matrix import MatrixLight
from lifx.devices.mirror import MirrorLight
from lifx.devices.multizone import MultiZoneLight
from lifx.effects import EffectScroll
from lifx.effects.registry import get_effect_registry
from lifx.effects.scroll import scrolled
from tests.test_theme.conftest import make_tile, mock_device_factory  # noqa: F401


def hues(*values: int) -> list[HSBK]:
    return [HSBK(hue=v, saturation=1.0, brightness=1.0, kelvin=3500) for v in values]


async def run_briefly(effect: EffectScroll) -> None:
    task = asyncio.create_task(effect.async_play())
    await asyncio.sleep(0.05)
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)


class TestScrolled:
    def test_moves_toward_higher_columns(self) -> None:
        out = scrolled([hues(0, 10, 20, 30)], [4], 1, 1)
        assert [c.hue for c in out[0]] == [30, 0, 10, 20]

    def test_wraps_across_a_chain(self) -> None:
        out = scrolled([hues(0, 10), hues(20, 30)], [2, 2], 1, 1)
        assert [[c.hue for c in t] for t in out] == [[30, 0], [10, 20]]

    def test_every_row_moves(self) -> None:
        out = scrolled([hues(0, 10, 20, 30)], [2], 2, 1)
        assert [c.hue for c in out[0]] == [10, 0, 30, 20]

    def test_full_cycle_returns_home(self) -> None:
        frame = [hues(0, 10, 20)]
        assert scrolled(frame, [3], 1, 3) == frame

    def test_vertical_moves_rows_down(self) -> None:
        frame = [hues(0, 0, 10, 10, 20, 20)]  # 2 wide, 3 rows
        out = scrolled(frame, [2], 3, 1, vertical=True)
        assert [c.hue for c in out[0]] == [20, 20, 0, 0, 10, 10]

    def test_vertical_full_cycle_returns_home(self) -> None:
        frame = [hues(0, 0, 10, 10, 20, 20)]
        assert scrolled(frame, [2], 3, 3, vertical=True) == frame

    def test_vertical_scrolls_each_tile_of_a_chain_on_its_own(self) -> None:
        frames = [hues(0, 10, 20), hues(30, 40, 50)]  # two 1x3 tiles
        out = scrolled(frames, [1, 1], 3, 1, vertical=True)
        assert [[c.hue for c in t] for t in out] == [[20, 0, 10], [50, 30, 40]]


class TestEffectScroll:
    def test_name_and_registry(self) -> None:
        assert EffectScroll().name == "scroll"
        info = get_effect_registry().get_effect("scroll")
        assert info is not None
        assert info.effect_class is EffectScroll

    async def test_compatible_with_matrix_only(self, mock_device_factory) -> None:  # noqa: F811
        effect = EffectScroll()
        assert await effect.is_light_compatible(mock_device_factory(MatrixLight))
        assert not await effect.is_light_compatible(mock_device_factory(Light))
        assert not await effect.is_light_compatible(mock_device_factory(MultiZoneLight))
        assert not await effect.is_light_compatible(
            mock_device_factory(MirrorLight, product=267)
        )

    async def test_writes_the_given_frame_scrolled(self, mock_device_factory) -> None:  # noqa: F811
        light = mock_device_factory(MatrixLight)
        light.get_device_chain = AsyncMock(
            return_value=[make_tile(0, width=2, height=1)]
        )
        light.get_all_tile_colors = AsyncMock()
        light._write_mood_frames = AsyncMock()
        effect = EffectScroll(frame=[hues(0, 10)])
        effect.participants = [light]
        await run_briefly(effect)
        light.get_all_tile_colors.assert_not_awaited()
        frames, duration = light._write_mood_frames.await_args.args[1:3]
        assert [c.hue for c in frames[0]] == [10, 0]
        assert duration == 1.25

    async def test_reads_the_tiles_without_a_frame(self, mock_device_factory) -> None:  # noqa: F811
        light = mock_device_factory(MatrixLight)
        light.get_device_chain = AsyncMock(
            return_value=[make_tile(0, width=2, height=1)]
        )
        light.get_all_tile_colors = AsyncMock(return_value=[hues(0, 10)])
        light._write_mood_frames = AsyncMock()
        effect = EffectScroll()
        effect.participants = [light]
        await run_briefly(effect)
        light.get_all_tile_colors.assert_awaited_once()

    async def test_frame_must_match_the_chain(self, mock_device_factory) -> None:  # noqa: F811
        light = mock_device_factory(MatrixLight)
        light.get_device_chain = AsyncMock(
            return_value=[
                make_tile(0, width=2, height=1),
                make_tile(1, width=2, height=1),
            ]
        )
        effect = EffectScroll(frame=[hues(0, 10)])
        effect.participants = [light]
        with pytest.raises(ValueError, match="frame"):
            await effect.async_play()

    async def test_vertical_moves_rows_down(self, mock_device_factory) -> None:  # noqa: F811
        light = mock_device_factory(MatrixLight)
        light.get_device_chain = AsyncMock(
            return_value=[make_tile(0, width=1, height=3)]
        )
        light._write_mood_frames = AsyncMock()
        effect = EffectScroll(frame=[hues(0, 10, 20)], vertical=True)
        assert effect.vertical is True
        effect.participants = [light]
        await run_briefly(effect)
        frames = light._write_mood_frames.await_args.args[1]
        assert [c.hue for c in frames[0]] == [20, 0, 10]

    async def test_vertical_runs_on_a_chain(
        self, tile_chain_light: MatrixLight
    ) -> None:
        async with tile_chain_light:
            tiles = await tile_chain_light.get_device_chain()
            frame = [
                hues(*([index * 10] * (tile.width * tile.height)))
                for index, tile in enumerate(tiles)
            ]
            effect = EffectScroll(frame=frame, vertical=True)
            effect.participants = [tile_chain_light]
            written: list[list[list[HSBK]]] = []
            write = tile_chain_light._write_mood_frames

            async def record(tiles_, frames, *args, **kwargs) -> None:
                written.append(frames)
                await write(tiles_, frames, *args, **kwargs)

            tile_chain_light._write_mood_frames = record  # type: ignore[method-assign]
            await run_briefly(effect)
        assert len(written[0]) == len(tiles)
        assert written[0] == frame  # one colour per tile scrolls onto itself

    async def test_vertical_defaults_off(self, mock_device_factory) -> None:  # noqa: F811
        tube = mock_device_factory(MatrixLight, product=217)
        tube.get_device_chain = AsyncMock(
            return_value=[make_tile(0, width=3, height=1)]
        )
        tube._write_mood_frames = AsyncMock()
        effect = EffectScroll(frame=[hues(0, 10, 20)])
        assert effect.vertical is False
        effect.participants = [tube]
        await run_briefly(effect)
        frames = tube._write_mood_frames.await_args.args[1]
        assert [c.hue for c in frames[0]] == [20, 0, 10]

    async def test_skips_non_matrix_participants(self, mock_device_factory) -> None:  # noqa: F811
        bulb = mock_device_factory(Light)
        matrix = mock_device_factory(MatrixLight)
        matrix.get_device_chain = AsyncMock(
            return_value=[make_tile(0, width=2, height=1)]
        )
        matrix._write_mood_frames = AsyncMock()
        effect = EffectScroll(frame=[hues(0, 10)])
        effect.participants = [bulb, matrix]
        await run_briefly(effect)
        matrix._write_mood_frames.assert_awaited()


class TestReadbackOrientation:
    """A frame read back from a rotated Tile is physical; it scrolls as logical."""

    @pytest.mark.parametrize("accel", [(0, 0, 0), (1, 0, 0), (-1, 0, 0), (0, 1, 0)])
    async def test_readback_scrolls_like_the_logical_frame(
        self,
        mock_device_factory,  # noqa: F811
        accel: tuple[int, int, int],
    ) -> None:
        tile = make_tile(0, width=2, height=2, accel=accel)
        logical = hues(0, 10, 20, 30)
        physical = MatrixLight._orient_tile_colors(tile, logical)
        # A rotated tile really moves cells; an upright one leaves them.
        assert (physical == logical) == (accel == (0, 0, 0))

        written: dict[str, list[int]] = {}
        for label, effect, readback in (
            ("given", EffectScroll(frame=[logical]), None),
            ("read", EffectScroll(), [physical]),
        ):
            light = mock_device_factory(MatrixLight, product=55)
            light.get_device_chain = AsyncMock(return_value=[tile])
            light.get_all_tile_colors = AsyncMock(return_value=readback)
            light.set_matrix_colors = AsyncMock()
            effect.participants = [light]
            await run_briefly(effect)
            written[label] = [
                c.hue for c in light.set_matrix_colors.await_args_list[0].args[1]
            ]
        assert written["read"] == written["given"]

    async def test_readback_ignores_buffer_padding(
        self,
        mock_device_factory,  # noqa: F811
    ) -> None:
        light = mock_device_factory(MatrixLight)
        light.get_device_chain = AsyncMock(
            return_value=[make_tile(0, width=2, height=1)]
        )
        light.get_all_tile_colors = AsyncMock(return_value=[hues(0, 10, 99, 99)])
        light._write_mood_frames = AsyncMock()
        effect = EffectScroll()
        effect.participants = [light]
        await run_briefly(effect)
        frames = light._write_mood_frames.await_args.args[1]
        assert [c.hue for c in frames[0]] == [10, 0]
