"""Tests for listeners notified after the debounced post-write refresh."""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lifx.devices.base import Device


@pytest.fixture
def refreshing_device(device: Device) -> Device:
    """Return a device whose refresh succeeds without a network round trip."""
    device._state = MagicMock()
    device.refresh_state = AsyncMock()
    return device


async def _write_and_settle(device: Device) -> None:
    """Run the refresh a write schedules, without waiting out the debounce."""
    with patch("lifx.const.STATE_REFRESH_DEBOUNCE_MS", 0):
        await device._schedule_refresh()
        assert device._refresh_task is not None
        await device._refresh_task


async def test_listener_receives_state_after_post_write_refresh(
    refreshing_device: Device,
) -> None:
    """A listener is called with the refreshed state once the refresh completes."""
    listener = MagicMock()
    refreshing_device.add_state_listener(listener)

    await _write_and_settle(refreshing_device)

    refreshing_device.refresh_state.assert_awaited_once_with()
    listener.assert_called_once_with(refreshing_device._state)


async def test_removed_listener_is_not_called(refreshing_device: Device) -> None:
    """Calling the returned function removes the listener."""
    listener = MagicMock()
    remove = refreshing_device.add_state_listener(listener)

    remove()
    await _write_and_settle(refreshing_device)

    listener.assert_not_called()


async def test_direct_refresh_does_not_notify(refreshing_device: Device) -> None:
    """Only the post-write refresh notifies; a caller's own refresh does not."""
    listener = MagicMock()
    refreshing_device.add_state_listener(listener)

    await refreshing_device.refresh_state()

    listener.assert_not_called()


async def test_failed_refresh_does_not_notify(refreshing_device: Device) -> None:
    """A refresh that fails leaves the listener uncalled."""
    refreshing_device.refresh_state.side_effect = TimeoutError("no reply")
    listener = MagicMock()
    refreshing_device.add_state_listener(listener)

    await _write_and_settle(refreshing_device)

    listener.assert_not_called()


async def test_failing_listener_does_not_stop_the_others(
    refreshing_device: Device, caplog: pytest.LogCaptureFixture
) -> None:
    """A listener that raises is logged, and later listeners are still called."""
    failing = MagicMock(side_effect=RuntimeError("listener broke"))
    working = MagicMock()
    refreshing_device.add_state_listener(failing)
    refreshing_device.add_state_listener(working)

    with caplog.at_level(logging.ERROR):
        await _write_and_settle(refreshing_device)

    working.assert_called_once_with(refreshing_device._state)
    assert "listener broke" in caplog.text
