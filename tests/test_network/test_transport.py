"""Tests for UDP transport layer."""

import pytest

from lifx.exceptions import LifxNetworkError as NetworkError
from lifx.exceptions import LifxTimeoutError as TimeoutError
from lifx.network.transport import UdpTransport


class TestUdpTransport:
    """Test UDP transport."""

    async def test_transport_context_manager(self) -> None:
        """Test transport context manager."""
        async with UdpTransport() as transport:
            assert transport.is_open

        assert not transport.is_open

    async def test_transport_open_close(self) -> None:
        """Test manual open/close."""
        transport = UdpTransport()
        assert not transport.is_open

        await transport.open()
        assert transport.is_open

        await transport.close()
        assert not transport.is_open

    async def test_transport_double_open(self) -> None:
        """Test opening transport twice is safe."""
        transport = UdpTransport()
        await transport.open()
        await transport.open()  # Should not raise
        assert transport.is_open
        await transport.close()

    async def test_send_without_open(self) -> None:
        """Test sending without opening raises error."""
        transport = UdpTransport()
        with pytest.raises(NetworkError):
            await transport.send(b"test", ("127.0.0.1", 56700))

    async def test_receive_without_open(self) -> None:
        """Test receiving without opening raises error."""
        transport = UdpTransport()
        with pytest.raises(NetworkError):
            await transport.receive(timeout=1.0)

    async def test_receive_timeout(self) -> None:
        """Test receive timeout."""
        async with UdpTransport() as transport:
            with pytest.raises(TimeoutError):
                await transport.receive(timeout=0.1)

    async def test_receive_many_timeout(self) -> None:
        """Test receive_many returns empty list on timeout."""
        async with UdpTransport() as transport:
            packets = await transport.receive_many(timeout=0.1)
            assert packets == []

    async def test_broadcast_mode(self) -> None:
        """Test transport with broadcast mode."""
        async with UdpTransport(broadcast=True) as transport:
            assert transport.is_open
            # Just verify it opens successfully with broadcast enabled
