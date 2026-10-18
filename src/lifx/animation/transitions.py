"""Transition clipping: keep a write's fade inside the gap to the next write.

A fade that outlives the gap to the next write on the same target is cut off by
that write, and a write that gets less than a few milliseconds does nothing
visible. :func:`clip_transitions` is the pure rule for both: it does no I/O and
knows nothing about devices. The animated mood's scroll uses it to schedule its
steps. The Conductor's frame-paced transition (1.5 frames at the effect's fps)
does not use it.
"""

from __future__ import annotations

from collections.abc import Hashable, Sequence
from typing import NamedTuple

# Writes that would get less than this are removed.
MIN_TRANSITION_SECONDS = 0.020

_EPSILON = 1e-9


class TransitionWrite(NamedTuple):
    """One scheduled write.

    Attributes:
        time: When the write is sent, in seconds on any shared clock
        target: What it writes to; only writes to the same target clip each other
        duration: The fade in seconds; 0 is an instant write
    """

    time: float
    target: Hashable
    duration: float


def clip_transitions(writes: Sequence[TransitionWrite]) -> list[TransitionWrite]:
    """Clip each fade to the gap before the next write on the same target.

    A write whose fade is longer than the gap gets the gap as its duration. A
    write with a fade whose gap is under 20 ms is removed. Instant writes
    (duration 0) and the last write on each target are kept as they are. The
    gap is measured to the next write as given, whether or not that write is
    itself removed.

    Args:
        writes: Scheduled writes, in any order

    Returns:
        The surviving writes, in the order they were given
    """
    order = sorted(range(len(writes)), key=lambda i: writes[i].time)
    next_time: dict[int, float] = {}
    last_seen: dict[Hashable, int] = {}
    for index in reversed(order):
        target = writes[index].target
        if target in last_seen:
            next_time[index] = writes[last_seen[target]].time
        last_seen[target] = index

    out: list[TransitionWrite] = []
    for index, write in enumerate(writes):
        if write.duration <= 0 or index not in next_time:
            out.append(write)
            continue
        gap = next_time[index] - write.time
        if gap >= write.duration:
            out.append(write)
        elif gap >= MIN_TRANSITION_SECONDS - _EPSILON:
            out.append(write._replace(duration=gap))
    return out
