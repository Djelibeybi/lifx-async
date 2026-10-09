"""EffectScroll: move a painted matrix image along its rows.

The LIFX app's MOVE on a matrix light: every 1.25 seconds each row moves one
cell toward higher column numbers, wrapping round, and the light fades to the
new frame. A chain scrolls as one canvas in chain order. With ``vertical``,
whole rows move down the light instead.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence

from lifx.color import HSBK
from lifx.const import MOOD_SCROLL_MAX_FADE_SECONDS, MOOD_SCROLL_STEP_SECONDS
from lifx.devices.light import Light
from lifx.devices.matrix import MatrixLight
from lifx.devices.mirror import MirrorLight
from lifx.effects.base import LIFXEffect


def scrolled(
    frames: Sequence[Sequence[HSBK]],
    widths: Sequence[int],
    height: int,
    step: int,
    *,
    vertical: bool = False,
) -> list[list[HSBK]]:
    """Move a chain canvas ``step`` cells along its rows, or rows down it.

    Args:
        frames: Per tile, row-major colours, in chain order
        widths: Each tile's width
        height: Rows per tile
        step: Cells (or rows) to move
        vertical: Move whole rows toward higher row numbers, wrapping to the
            top. Single tile only.

    Returns:
        The scrolled frames, per tile
    """
    if vertical:
        width = widths[0]
        rows = [list(frames[0][r * width : (r + 1) * width]) for r in range(height)]
        return [[color for r in range(height) for color in rows[(r - step) % height]]]

    rows = [
        [
            color
            for frame, width in zip(frames, widths)
            for color in frame[row * width : (row + 1) * width]
        ]
        for row in range(height)
    ]
    shift = step % len(rows[0]) if rows and rows[0] else 0
    moved = [row[len(row) - shift :] + row[: len(row) - shift] for row in rows]
    out: list[list[HSBK]] = []
    start = 0
    for width in widths:
        out.append([color for row in moved for color in row[start : start + width]])
        start += width
    return out


class EffectScroll(LIFXEffect):
    """Scroll a painted matrix image one column at a time.

    ``animate_mood()`` starts it after painting a mood, passing the frame it
    painted. Without ``frame``, it reads the tiles once when it starts; a
    read straight after a fade can catch colours mid-fade, so pass the frame
    when you have it. It streams no frames, so it runs on Thread lights.

    ``vertical`` moves whole rows down the light instead of shifting each row
    sideways, as the LIFX app does for stripe moods on every Candle and the
    Tube.

    Example:
        ```python
        await light.start_effect(EffectScroll())
        ```
    """

    def __init__(
        self,
        frame: Sequence[Sequence[HSBK]] | None = None,
        power_on: bool = True,
        *,
        vertical: bool = False,
    ) -> None:
        """Create the effect.

        Args:
            frame: Per tile, row-major colours to scroll, in chain order
            power_on: Turn lights on if they are off
            vertical: Move whole rows down instead of shifting rows sideways
        """
        super().__init__(power_on=power_on)
        self.frame = [list(tile) for tile in frame] if frame is not None else None
        self.vertical = vertical

    @property
    def name(self) -> str:
        """Return the name of the effect."""
        return "scroll"

    async def is_light_compatible(self, light: Light) -> bool:
        """Matrix lights only; a Mirror's buffer is two rings, not rows."""
        return isinstance(light, MatrixLight) and not isinstance(light, MirrorLight)

    async def async_play(self) -> None:
        """Scroll every participant until stopped.

        Raises:
            ValueError: If ``frame`` does not match a light's tiles
        """
        plans = []
        for light in self.participants:
            if not isinstance(light, MatrixLight):
                continue
            matrix = light
            tiles = await matrix.get_device_chain()
            frames = (
                self.frame
                if self.frame is not None
                else await matrix.get_all_tile_colors()
            )
            if len(frames) != len(tiles) or any(
                len(colors) != tile.width * tile.height
                for colors, tile in zip(frames, tiles)
            ):
                raise ValueError(
                    f"frame does not match {matrix.label or matrix.serial}'s tiles"
                )
            await matrix.ensure_capabilities()
            has_chain = bool(matrix.capabilities and matrix.capabilities.has_chain)
            plans.append((matrix, tiles, frames, has_chain))

        fade = min(MOOD_SCROLL_STEP_SECONDS, MOOD_SCROLL_MAX_FADE_SECONDS)
        step = 0
        while True:
            step += 1
            await asyncio.gather(
                *(
                    matrix._write_mood_frames(
                        tiles,
                        scrolled(
                            frames,
                            [t.width for t in tiles],
                            tiles[0].height,
                            step,
                            vertical=self.vertical,
                        ),
                        fade,
                        has_chain=has_chain,
                    )
                    for matrix, tiles, frames, has_chain in plans
                )
            )
            await asyncio.sleep(MOOD_SCROLL_STEP_SECONDS)
