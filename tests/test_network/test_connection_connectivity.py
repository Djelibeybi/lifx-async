"""Tests for the connection's observed Thread transport reporting.

``LifxHeader.thread_connection`` (frame address byte 22, bit 3) is the
device's own report that a reply travelled over a Thread connection.
``DeviceConnection`` records it from correlated responses only, so
untrusted or mismatched traffic can never relabel a device's transport.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any
from unittest.mock import patch

import pytest

from lifx.network.connection import DeviceConnection
from lifx.protocol import packets
from lifx.protocol.header import LifxHeader

_OFFLINE_IP = "192.0.2.55"
_OFFLINE_SERIAL = "d073d5010203"
_STATE_POWER_PKT_TYPE = 22
_STATE_POWER_PAYLOAD = b"\xff\xff"


def _header(
    *,
    source: int,
    sequence: int,
    target: bytes,
    thread_connection: bool,
) -> LifxHeader:
    """Build a correlated StatePower header with an explicit Thread flag."""
    return LifxHeader(
        size=36 + len(_STATE_POWER_PAYLOAD),
        protocol=1024,
        source=source,
        target=target,
        tagged=False,
        ack_required=False,
        res_required=False,
        sequence=sequence,
        pkt_type=_STATE_POWER_PKT_TYPE,
        thread_connection=thread_connection,
    )


async def _wait_for_keys(conn: DeviceConnection, count: int) -> None:
    """Bounded wait until the request registers its correlation keys."""
    start = time.monotonic()
    while len(conn._pending_requests) < count:
        if time.monotonic() - start > 2.0:
            raise AssertionError("Timed out waiting for pending request keys")
        await asyncio.sleep(0.001)


async def _drive_one_response(
    conn: DeviceConnection, *, thread_connection: bool, target: bytes | None = None
) -> None:
    """Run one request to completion against an injected correlated response."""
    task: asyncio.Task[Any] | None = None
    try:
        await conn.open()
        with patch("lifx.network.connection.REQUEST_RETRANSMIT_GAPS", (0.5,)):
            task = asyncio.create_task(
                conn.request(packets.Device.GetPower(), timeout=5.0)
            )
            await _wait_for_keys(conn, 1)
            (key,) = conn._pending_requests.keys()
            source, sequence, _serial = key
            header = _header(
                source=source,
                sequence=sequence,
                target=target
                if target is not None
                else bytes.fromhex(conn.serial) + b"\x00\x00",
                thread_connection=thread_connection,
            )
            conn._pending_requests[key].put_nowait((header, _STATE_POWER_PAYLOAD))
            await asyncio.wait_for(task, timeout=1.0)
            task = None
    finally:
        if task is not None and not task.done():
            task.cancel()
        await conn.close()


class TestObservedThreadConnection:
    """DeviceConnection.thread_connection reflects correlated responses only."""

    async def test_unobserved_before_any_response(self) -> None:
        """A connection that has seen no response reports no observation."""
        conn = DeviceConnection(serial=_OFFLINE_SERIAL, ip=_OFFLINE_IP)

        assert conn.thread_connection is None

    async def test_records_thread_flagged_response(self) -> None:
        """A correlated reply with bit 3 set reports a Thread transport."""
        conn = DeviceConnection(
            serial=_OFFLINE_SERIAL, ip=_OFFLINE_IP, timeout=5.0, max_retries=8
        )

        await _drive_one_response(conn, thread_connection=True)

        assert conn.thread_connection is True

    async def test_records_unflagged_response(self) -> None:
        """A correlated reply without bit 3 reports a non-Thread transport."""
        conn = DeviceConnection(
            serial=_OFFLINE_SERIAL, ip=_OFFLINE_IP, timeout=5.0, max_retries=8
        )

        await _drive_one_response(conn, thread_connection=False)

        assert conn.thread_connection is False

    async def test_latest_correlated_response_wins(self) -> None:
        """The most recent correlated observation replaces the previous one."""
        conn = DeviceConnection(
            serial=_OFFLINE_SERIAL, ip=_OFFLINE_IP, timeout=5.0, max_retries=8
        )

        await _drive_one_response(conn, thread_connection=True)
        assert conn.thread_connection is True

        await _drive_one_response(conn, thread_connection=False)
        assert conn.thread_connection is False

    async def test_uncorrelated_response_does_not_record(self) -> None:
        """A reply failing serial validation never relabels the transport.

        The observation is taken after source/sequence/serial validation, so
        stray traffic on the shared socket cannot assert a transport for a
        device it does not belong to.
        """
        conn = DeviceConnection(
            serial=_OFFLINE_SERIAL, ip=_OFFLINE_IP, timeout=1.0, max_retries=0
        )

        with pytest.raises(Exception):
            await _drive_one_response(
                conn,
                thread_connection=True,
                target=bytes.fromhex("d073d5aabbcc") + b"\x00\x00",
            )

        assert conn.thread_connection is None
