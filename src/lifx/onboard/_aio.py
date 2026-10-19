"""Cancellation-safe bounded awaits for the onboarding sequence.

``asyncio.wait_for`` on Python 3.10 and 3.11 drops a cancellation that
arrives in the same loop iteration the awaited coroutine completes in, so a
cancelled run could carry on as if nothing had happened. ``bounded()`` waits
through ``asyncio.wait``, which never swallows the caller's cancellation,
and cancels the inner task itself on a timeout or a cancellation.
"""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import Any, TypeVar

_T = TypeVar("_T")


async def bounded(coro: Coroutine[Any, Any, _T], timeout: float) -> _T:
    """Await ``coro`` for at most ``timeout`` seconds.

    Raises:
        asyncio.TimeoutError: If ``coro`` has not finished in time. The inner
            task is cancelled and reaped first, and an exception it raised
            meanwhile is marked retrieved so asyncio never logs it (a backend
            error may carry the password).
    """
    task = asyncio.ensure_future(coro)
    cancellation: asyncio.CancelledError | None = None
    finished = False
    try:
        done, _ = await asyncio.wait({task}, timeout=max(timeout, 0.0))
        finished = bool(done)
    except asyncio.CancelledError as error:
        cancellation = error
    if cancellation is None and finished:
        return task.result()
    task.cancel()
    await asyncio.wait({task})
    if not task.cancelled():
        task.exception()
    if cancellation is not None:
        raise cancellation
    raise asyncio.TimeoutError
