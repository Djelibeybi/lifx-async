"""Fixtures for the onboarding tests: an in-process fake LIFX SoftAP."""

from __future__ import annotations

import asyncio
import socket
import ssl
import warnings
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
FAKE_AP_CERT = FIXTURES / "lifx-fake-ap.crt"
FAKE_AP_KEY = FIXTURES / "lifx-fake-ap.key"
LEGACY_CIPHERS = "AES256-SHA:@SECLEVEL=0"


def configure_legacy_tls(context: ssl.SSLContext) -> None:
    """Pin ``context`` to TLS 1.0 with the SoftAP's only cipher suite.

    Raises:
        ssl.SSLError: If OpenSSL refuses the cipher string at security level 0.
        ValueError: If OpenSSL refuses TLS 1.0 as a version bound.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        context.minimum_version = ssl.TLSVersion.TLSv1
        context.maximum_version = ssl.TLSVersion.TLSv1
    context.set_ciphers(LEGACY_CIPHERS)


@dataclass
class FakeAccessPoint:
    """A loopback TLS listener that records the first message of each client.

    Attributes:
        address: The address the listener is bound to.
        port: The ephemeral port the listener is bound to.
        messages: The first chunk of bytes each TLS client wrote, in order.
        tls_versions: The negotiated TLS version of each completed handshake.
    """

    address: str
    port: int
    messages: list[bytes] = field(default_factory=list)
    tls_versions: list[str] = field(default_factory=list)

    async def _handle(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        ssl_object = writer.get_extra_info("ssl_object")
        self.tls_versions.append(ssl_object.version())
        self.messages.append(await reader.read(4096))
        writer.close()


async def _serve_fake_access_point(legacy: bool) -> AsyncIterator[FakeAccessPoint]:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(FAKE_AP_CERT, FAKE_AP_KEY)
    if legacy:
        configure_legacy_tls(context)
    access_point = FakeAccessPoint(address="127.0.0.1", port=0)
    server = await asyncio.start_server(
        access_point._handle, access_point.address, 0, ssl=context
    )
    access_point.port = server.sockets[0].getsockname()[1]
    try:
        yield access_point
    finally:
        server.close()
        await server.wait_closed()


@pytest.fixture
async def fake_access_point() -> AsyncIterator[FakeAccessPoint]:
    """A fake SoftAP speaking the default (TLS 1.2 or later) configuration."""
    async for access_point in _serve_fake_access_point(legacy=False):
        yield access_point


@pytest.fixture
async def legacy_fake_access_point() -> AsyncIterator[FakeAccessPoint]:
    """A fake SoftAP pinned to TLS 1.0 with ``AES256-SHA`` at security level 0.

    Skips the test when this host's OpenSSL refuses that configuration.
    """
    try:
        async for access_point in _serve_fake_access_point(legacy=True):
            yield access_point
    except (ssl.SSLError, ValueError) as error:
        pytest.skip(
            f"OpenSSL {ssl.OPENSSL_VERSION} refuses TLS 1.0 at SECLEVEL 0: {error}"
        )


@pytest.fixture
def closed_port() -> int:
    """A loopback port with nothing listening on it."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]
