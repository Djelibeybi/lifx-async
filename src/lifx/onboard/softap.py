"""The SoftAP control channel: a TLS connection to a device's own access point.

A LIFX device that has not joined a network runs a SoftAP at
``172.16.0.1`` and listens for one TLS connection on the LIFX port. The host
connects, writes a single 134-byte ``Wifi.SetAccessPoint`` message and
closes. Nothing is read back.

The device's certificate is self-signed and per device, so verification is
disabled. Firmware older than the TLS 1.2 generation only speaks TLS 1.0 with
``AES256-SHA``, which modern OpenSSL builds refuse by default; ``legacy_tls``
opts into that configuration where the host's OpenSSL still allows it.

The password is never logged, never put into an exception message and never
included in a ``repr``.
"""

from __future__ import annotations

import asyncio
import logging
import socket
import ssl
import warnings
from typing import Protocol

from lifx.network.message import create_message
from lifx.network.utils import allocate_source
from lifx.onboard.errors import (
    LegacyTlsUnavailableError,
    SoftApDialError,
    SoftApSendError,
    SoftApUnreachableError,
)
from lifx.onboard.models import HomeNetwork
from lifx.protocol.models import Serial
from lifx.protocol.packets import Wifi
from lifx.protocol.protocol_types import WifiInterface, WifiSecurity

__all__ = [
    "SOFTAP_ADDRESS",
    "SOFTAP_PORT",
    "SoftApClient",
    "SoftApConnection",
    "build_access_point_message",
]

_LOGGER = logging.getLogger(__name__)

#: The address every LIFX SoftAP assigns itself.
SOFTAP_ADDRESS = "172.16.0.1"
#: The TCP port the SoftAP accepts the credential message on.
SOFTAP_PORT = 56700
#: The only cipher suite legacy firmware offers, at the security level that
#: still admits it.
_LEGACY_CIPHERS = "AES256-SHA:@SECLEVEL=0"


class SoftApClient(Protocol):
    """The control channel the onboarding sequence drives.

    ``SoftApConnection`` is the real implementation; tests substitute fakes.
    """

    @property
    def address(self) -> str:
        """The SoftAP address this client talks to."""
        ...

    @property
    def port(self) -> int:
        """The SoftAP port this client talks to."""
        ...

    async def probe(self, *, timeout: float | None = None) -> None:
        """Make one plain TCP connection to the SoftAP and close it.

        Raises:
            SoftApUnreachableError: If the connection fails or ``timeout``
                elapses first.
        """
        ...

    async def open(self) -> None:
        """Connect and complete the TLS handshake.

        Raises:
            SoftApDialError: If the connection or handshake fails or the dial
                timeout elapses first.
        """
        ...

    async def send_access_point(self, target: Serial, network: HomeNetwork) -> None:
        """Write the credential message for ``target``.

        Raises:
            SoftApSendError: If the message cannot be written.
        """
        ...

    async def close(self) -> None:
        """Close the connection; safe to call when it is not open."""
        ...


def _build_ssl_context(legacy_tls: bool) -> ssl.SSLContext:
    """Build the client TLS context for a SoftAP.

    Every device presents its own self-signed certificate, so hostname
    checking and verification are off. The default context requires TLS 1.2
    or later; the legacy context pins TLS 1.0 with ``AES256-SHA`` at
    security level 0.

    Raises:
        LegacyTlsUnavailableError: If this host's OpenSSL refuses the legacy
            configuration.
    """
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    # The device's certificate is self-signed and per device; there is no
    # authority that could verify it, so verification is deliberately off.
    context.verify_mode = ssl.CERT_NONE
    if not legacy_tls:
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        return context
    try:
        with warnings.catch_warnings():
            # Legacy firmware only speaks TLS 1.0; the deprecation is the point.
            warnings.simplefilter("ignore", DeprecationWarning)
            context.minimum_version = ssl.TLSVersion.TLSv1
            context.maximum_version = ssl.TLSVersion.TLSv1
        context.set_ciphers(_LEGACY_CIPHERS)
    except (ssl.SSLError, ValueError) as error:
        raise LegacyTlsUnavailableError(
            f"{ssl.OPENSSL_VERSION} refuses TLS 1.0 with {_LEGACY_CIPHERS}: {error}"
        ) from error
    return context


class SoftApConnection:
    """A TLS connection to a device's SoftAP.

    Use as an async context manager, or call ``open()``, ``send_access_point()``
    and ``close()`` directly. Nothing is ever read from the device.

    Args:
        address: The SoftAP address.
        port: The SoftAP port.
        dial_timeout: Seconds allowed for the TCP connect plus TLS handshake.
        legacy_tls: Pin TLS 1.0 with ``AES256-SHA`` for firmware that speaks
            nothing newer.

    Raises:
        LegacyTlsUnavailableError: If ``legacy_tls`` is set and this host's
            OpenSSL refuses the configuration.
    """

    def __init__(
        self,
        address: str = SOFTAP_ADDRESS,
        port: int = SOFTAP_PORT,
        dial_timeout: float = 10.0,
        legacy_tls: bool = False,
    ) -> None:
        self._address = address
        self._port = port
        self._dial_timeout = dial_timeout
        self._legacy_tls = legacy_tls
        self._ssl_context = _build_ssl_context(legacy_tls)
        self._writer: asyncio.StreamWriter | None = None

    def __repr__(self) -> str:
        return (
            f"SoftApConnection(address={self._address!r}, port={self._port!r}, "
            f"dial_timeout={self._dial_timeout!r}, legacy_tls={self._legacy_tls!r})"
        )

    @property
    def address(self) -> str:
        """The SoftAP address this connection talks to."""
        return self._address

    @property
    def port(self) -> int:
        """The SoftAP port this connection talks to."""
        return self._port

    async def probe(self, *, timeout: float | None = None) -> None:
        """Make one plain TCP connection to the SoftAP and close it.

        Args:
            timeout: Seconds to wait for the connection; unbounded when
                ``None``.

        Raises:
            SoftApUnreachableError: If the connection fails or ``timeout``
                elapses first.
        """
        try:
            _reader, writer = await asyncio.wait_for(
                asyncio.open_connection(
                    self._address, self._port, family=socket.AF_INET
                ),
                timeout,
            )
        except (TimeoutError, OSError) as error:
            raise SoftApUnreachableError(
                f"No SoftAP reachable at {self._address}:{self._port}: "
                f"{type(error).__name__}"
            ) from error
        _LOGGER.debug("SoftAP at %s:%s accepted a TCP probe", self._address, self._port)
        writer.close()
        await _wait_closed_quietly(writer)

    async def open(self) -> None:
        """Connect to the SoftAP and complete the TLS handshake.

        Raises:
            SoftApDialError: If the connection or handshake fails or
                ``dial_timeout`` elapses first.
        """
        try:
            _reader, writer = await asyncio.wait_for(
                asyncio.open_connection(
                    self._address,
                    self._port,
                    ssl=self._ssl_context,
                    family=socket.AF_INET,
                ),
                self._dial_timeout,
            )
        except (TimeoutError, OSError) as error:
            raise SoftApDialError(
                f"Could not dial SoftAP at {self._address}:{self._port} within "
                f"{self._dial_timeout}s: {type(error).__name__}"
            ) from error
        self._writer = writer
        _LOGGER.debug(
            "Dialed SoftAP at %s:%s over %s",
            self._address,
            self._port,
            writer.get_extra_info("ssl_object").version(),
        )

    async def send_access_point(self, target: Serial, network: HomeNetwork) -> None:
        """Write the credential message for ``target`` and flush it.

        Raises:
            SoftApSendError: If the connection is not open or the write fails.
        """
        if self._writer is None:
            raise SoftApSendError(
                f"SoftAP connection to {self._address}:{self._port} is not open"
            )
        message = build_access_point_message(target, network)
        try:
            self._writer.write(message)
            await self._writer.drain()
        except OSError as error:
            raise SoftApSendError(
                f"Could not send credentials to SoftAP at "
                f"{self._address}:{self._port}: {type(error).__name__}"
            ) from error
        _LOGGER.debug(
            "Sent %d-byte credential message for %s (SSID %r) to SoftAP at %s:%s",
            len(message),
            target,
            network.ssid,
            self._address,
            self._port,
        )

    async def close(self) -> None:
        """Close the connection; a no-op when it is not open."""
        writer, self._writer = self._writer, None
        if writer is None:
            return
        writer.close()
        await _wait_closed_quietly(writer)

    async def __aenter__(self) -> SoftApConnection:
        await self.open()
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.close()


async def _wait_closed_quietly(writer: asyncio.StreamWriter) -> None:
    """Wait for ``writer`` to close, ignoring a reset from the far end."""
    try:
        await writer.wait_closed()
    except OSError:
        _LOGGER.debug("SoftAP closed the connection first", exc_info=True)


def build_access_point_message(
    target: Serial, network: HomeNetwork, *, source: int | None = None
) -> bytes:
    """Build the 134-byte message that hands a device its home network.

    The header is the standard LIFX frame: protocol 1024, addressable set,
    tagged unset, sequence 0, no acknowledgement or response requested, and
    the target set to the device's padded serial. The payload is packet 305.

    Args:
        target: The serial of the device being onboarded.
        network: The network the device should join.
        source: Frame source; a fresh one is allocated when omitted.

    Returns:
        The complete header plus payload, ready to write to the SoftAP.
    """
    packet = Wifi.SetAccessPoint(
        interface=WifiInterface.STATION,
        ssid=network.ssid.encode("utf-8"),
        password=network.password.encode("utf-8"),
        security=WifiSecurity(network.security),
    )
    return create_message(
        packet,
        source=allocate_source() if source is None else source,
        target=target.to_protocol(),
        sequence=0,
        ack_required=False,
        res_required=False,
    )
