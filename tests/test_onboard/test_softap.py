"""Tests for the SoftAP TLS client against an in-process fake access point.

Assertions are made on the raw bytes the fake access point receives, never by
unpacking a ``Wifi.SetAccessPoint``: the client itself never unpacks anything,
and the no-leak test below must observe exactly what the client logs.
"""

from __future__ import annotations

import asyncio
import logging
import ssl

import pytest

import lifx.onboard
from lifx.onboard import (
    HomeNetwork,
    LegacyTlsUnavailableError,
    OnboardPhase,
    SoftApDialError,
    SoftApSendError,
    SoftApUnreachableError,
    WifiSecurity,
    softap,
)
from lifx.onboard.softap import (
    SOFTAP_ADDRESS,
    SOFTAP_PORT,
    SoftApConnection,
    build_access_point_message,
)
from lifx.protocol.models import Serial
from tests.conftest import HANG_GUARD_TIMEOUT
from tests.test_onboard.conftest import FakeAccessPoint

PASSWORD = "secret"
SERIAL = Serial.from_string("d073d5e0a1b2")
NETWORK = HomeNetwork("home", PASSWORD, WifiSecurity.WPA2_AES_PSK)
# The golden payload pinned by tests/test_protocol/test_generated.py.
GOLDEN_PAYLOAD = (
    b"\x02" + b"home".ljust(32, b"\0") + b"secret".ljust(64, b"\0") + b"\x05"
)


def assert_access_point_message(data: bytes, source: int | None = None) -> None:
    """Check the 36-byte header and 98-byte payload of a credential message."""
    assert len(data) == 134
    assert data[0:2] == b"\x86\x00"  # size 134
    assert data[2:4] == b"\x00\x14"  # addressable, protocol 1024, tagged unset
    found_source = int.from_bytes(data[4:8], "little")
    assert found_source >= 2
    if source is not None:
        assert found_source == source
    assert data[8:16] == SERIAL.to_protocol()  # target, padded to 8 bytes
    assert data[16:22] == b"\x00" * 6  # reserved
    assert data[22] == 0  # no ack, no response
    assert data[23] == 0  # sequence
    assert data[24:32] == b"\x00" * 8  # reserved
    assert data[32:34] == b"\x31\x01"  # type 305
    assert data[34:36] == b"\x00\x00"  # reserved
    assert data[36:] == GOLDEN_PAYLOAD


class TestConstants:
    def test_softap_address_and_port(self) -> None:
        assert SOFTAP_ADDRESS == "172.16.0.1"
        assert SOFTAP_PORT == 56700


class TestBuildAccessPointMessage:
    def test_golden_bytes_with_allocated_source(self) -> None:
        data = build_access_point_message(SERIAL, NETWORK)

        assert_access_point_message(data)

    def test_explicit_source_is_used(self) -> None:
        data = build_access_point_message(SERIAL, NETWORK, source=0x12345678)

        assert_access_point_message(data, source=0x12345678)

    def test_open_network_has_empty_password(self) -> None:
        data = build_access_point_message(SERIAL, HomeNetwork("cafe"))

        assert data[36] == 2
        assert data[37:69] == b"cafe".ljust(32, b"\0")
        assert data[69:133] == b"\0" * 64
        assert data[133] == WifiSecurity.OPEN


class TestProbe:
    async def test_succeeds_against_a_listener(
        self, fake_access_point: FakeAccessPoint
    ) -> None:
        connection = SoftApConnection(
            address=fake_access_point.address, port=fake_access_point.port
        )

        await connection.probe(timeout=1.0)

        assert fake_access_point.messages == []

    async def test_raises_unreachable_against_a_closed_port(
        self, closed_port: int
    ) -> None:
        connection = SoftApConnection(address="127.0.0.1", port=closed_port)

        with pytest.raises(SoftApUnreachableError) as excinfo:
            await connection.probe(timeout=1.0)

        assert excinfo.value.__cause__ is not None
        assert str(closed_port) in str(excinfo.value)

    async def test_raises_unreachable_on_timeout(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def never_connects(*args: object, **kwargs: object) -> object:
            await asyncio.sleep(HANG_GUARD_TIMEOUT)
            raise AssertionError("unreachable")

        monkeypatch.setattr(softap.asyncio, "open_connection", never_connects)
        connection = SoftApConnection(address="127.0.0.1", port=1)

        with pytest.raises(SoftApUnreachableError):
            await connection.probe(timeout=0.01)


async def wait_for_messages(access_point: FakeAccessPoint, count: int) -> None:
    """Give the fake access point's handler a chance to record its reads."""
    deadline = asyncio.get_running_loop().time() + HANG_GUARD_TIMEOUT
    while len(access_point.messages) < count:
        assert asyncio.get_running_loop().time() < deadline, "fake AP got nothing"
        await asyncio.sleep(0.005)


class TestSendAccessPoint:
    async def test_delivers_the_message_over_tls(
        self, fake_access_point: FakeAccessPoint
    ) -> None:
        async with SoftApConnection(
            address=fake_access_point.address, port=fake_access_point.port
        ) as connection:
            await connection.send_access_point(SERIAL, NETWORK)

        await wait_for_messages(fake_access_point, 1)
        assert_access_point_message(fake_access_point.messages[0])
        assert fake_access_point.tls_versions[0] in {"TLSv1.2", "TLSv1.3"}

    async def test_explicit_open_send_close(
        self, fake_access_point: FakeAccessPoint
    ) -> None:
        connection = SoftApConnection(
            address=fake_access_point.address, port=fake_access_point.port
        )
        await connection.open()
        await connection.send_access_point(SERIAL, NETWORK)
        await connection.close()
        await connection.close()  # idempotent

        await wait_for_messages(fake_access_point, 1)
        assert_access_point_message(fake_access_point.messages[0])

    async def test_send_before_open_raises(self) -> None:
        connection = SoftApConnection(address="127.0.0.1", port=1)

        with pytest.raises(SoftApSendError) as excinfo:
            await connection.send_access_point(SERIAL, NETWORK)

        assert excinfo.value.phase is OnboardPhase.CONFIGURE

    async def test_write_failure_raises_send_error(
        self, fake_access_point: FakeAccessPoint, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A reset during the write surfaces as SoftApSendError.

        asyncio reports a lost connection from ``drain()``, and only once it
        has processed the far end's close, so the failure is injected at the
        stream boundary rather than raced against the fake access point.
        """
        real_open_connection = asyncio.open_connection

        async def open_connection(*args: object, **kwargs: object) -> object:
            reader, writer = await real_open_connection(*args, **kwargs)  # type: ignore[arg-type]

            async def drain() -> None:
                raise ConnectionResetError("Connection lost")

            monkeypatch.setattr(writer, "drain", drain)
            return reader, writer

        monkeypatch.setattr(softap.asyncio, "open_connection", open_connection)
        connection = SoftApConnection(
            address=fake_access_point.address, port=fake_access_point.port
        )
        await connection.open()

        with pytest.raises(SoftApSendError) as excinfo:
            await connection.send_access_point(SERIAL, NETWORK)

        assert isinstance(excinfo.value.__cause__, ConnectionResetError)
        await connection.close()


class TestClose:
    async def test_reset_while_closing_is_swallowed(
        self,
        fake_access_point: FakeAccessPoint,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """A device that resets the socket as we close must not raise."""
        caplog.set_level(logging.DEBUG)
        real_open_connection = asyncio.open_connection

        async def open_connection(*args: object, **kwargs: object) -> object:
            reader, writer = await real_open_connection(*args, **kwargs)  # type: ignore[arg-type]

            async def wait_closed() -> None:
                raise ConnectionResetError("Connection reset by peer")

            monkeypatch.setattr(writer, "wait_closed", wait_closed)
            return reader, writer

        monkeypatch.setattr(softap.asyncio, "open_connection", open_connection)

        async with SoftApConnection(
            address=fake_access_point.address, port=fake_access_point.port
        ):
            pass

        assert "closed the connection first" in caplog.text


class TestOpen:
    async def test_closed_port_raises_dial_error(self, closed_port: int) -> None:
        connection = SoftApConnection(address="127.0.0.1", port=closed_port)

        with pytest.raises(SoftApDialError) as excinfo:
            await connection.open()

        assert excinfo.value.phase is OnboardPhase.DIAL
        assert isinstance(excinfo.value.__cause__, OSError)

    async def test_silent_server_raises_dial_error_within_dial_timeout(
        self,
    ) -> None:
        accepted = asyncio.Event()

        async def accept_and_say_nothing(
            reader: asyncio.StreamReader, writer: asyncio.StreamWriter
        ) -> None:
            accepted.set()
            await reader.read(1)
            writer.close()

        server = await asyncio.start_server(accept_and_say_nothing, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        connection = SoftApConnection(address="127.0.0.1", port=port, dial_timeout=0.05)
        try:
            started = asyncio.get_running_loop().time()
            with pytest.raises(SoftApDialError) as excinfo:
                await connection.open()
            elapsed = asyncio.get_running_loop().time() - started
        finally:
            server.close()
            await server.wait_closed()

        assert accepted.is_set()
        assert elapsed < HANG_GUARD_TIMEOUT
        assert "0.05" in str(excinfo.value)

    async def test_handshake_rejection_raises_dial_error(self) -> None:
        async def talk_garbage(
            reader: asyncio.StreamReader, writer: asyncio.StreamWriter
        ) -> None:
            writer.write(b"not a tls server record" * 4)
            await writer.drain()
            writer.close()

        server = await asyncio.start_server(talk_garbage, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        connection = SoftApConnection(address="127.0.0.1", port=port)
        try:
            with pytest.raises(SoftApDialError) as excinfo:
                await connection.open()
        finally:
            server.close()
            await server.wait_closed()

        assert isinstance(excinfo.value.__cause__, ssl.SSLError)

    async def test_context_manager_closes_without_sending(
        self, fake_access_point: FakeAccessPoint
    ) -> None:
        async with SoftApConnection(
            address=fake_access_point.address, port=fake_access_point.port
        ) as connection:
            assert connection.address == fake_access_point.address
            assert connection.port == fake_access_point.port

        await wait_for_messages(fake_access_point, 1)
        assert fake_access_point.messages == [b""]


class TestTlsContexts:
    def test_default_context(self) -> None:
        context = softap._build_ssl_context(False)

        assert context.protocol is ssl.PROTOCOL_TLS_CLIENT
        assert context.check_hostname is False
        assert context.verify_mode is ssl.CERT_NONE
        assert context.minimum_version is ssl.TLSVersion.TLSv1_2
        assert context.maximum_version is ssl.TLSVersion.MAXIMUM_SUPPORTED

    def test_legacy_context(self) -> None:
        try:
            context = softap._build_ssl_context(True)
        except LegacyTlsUnavailableError as error:
            pytest.skip(
                f"OpenSSL {ssl.OPENSSL_VERSION} refuses TLS 1.0 at SECLEVEL 0: {error}"
            )

        assert context.check_hostname is False
        assert context.verify_mode is ssl.CERT_NONE
        assert context.minimum_version is ssl.TLSVersion.TLSv1
        assert context.maximum_version is ssl.TLSVersion.TLSv1
        assert "AES256-SHA" in {cipher["name"] for cipher in context.get_ciphers()}

    def test_legacy_context_is_unavailable_when_openssl_refuses(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def refuse(self: ssl.SSLContext, ciphers: str) -> None:
            raise ssl.SSLError(1, "no cipher match")

        monkeypatch.setattr(ssl.SSLContext, "set_ciphers", refuse)

        with pytest.raises(LegacyTlsUnavailableError) as excinfo:
            SoftApConnection(legacy_tls=True)

        assert excinfo.value.phase is None
        assert ssl.OPENSSL_VERSION in str(excinfo.value)
        assert isinstance(excinfo.value.__cause__, ssl.SSLError)

    def test_legacy_context_is_unavailable_when_version_is_refused(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def refuse(self: ssl.SSLContext, version: ssl.TLSVersion) -> None:
            raise ValueError("Unsupported protocol version 0x301")

        monkeypatch.setattr(
            ssl.SSLContext,
            "minimum_version",
            property(ssl.SSLContext.minimum_version.fget, refuse),
        )

        with pytest.raises(LegacyTlsUnavailableError) as excinfo:
            softap._build_ssl_context(True)

        assert isinstance(excinfo.value.__cause__, ValueError)

    def test_default_context_does_not_touch_legacy_settings(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def refuse(self: ssl.SSLContext, ciphers: str) -> None:
            raise AssertionError("set_ciphers must not be called")

        monkeypatch.setattr(ssl.SSLContext, "set_ciphers", refuse)

        SoftApConnection()


class TestLegacyHandshake:
    async def test_tls_1_0_handshake_against_the_fake_access_point(
        self, legacy_fake_access_point: FakeAccessPoint
    ) -> None:
        try:
            connection = SoftApConnection(
                address=legacy_fake_access_point.address,
                port=legacy_fake_access_point.port,
                legacy_tls=True,
            )
        except LegacyTlsUnavailableError as error:
            pytest.skip(
                f"OpenSSL {ssl.OPENSSL_VERSION} refuses TLS 1.0 at SECLEVEL 0: {error}"
            )

        try:
            async with connection:
                await connection.send_access_point(SERIAL, NETWORK)
        except SoftApDialError as error:
            if isinstance(error.__cause__, ssl.SSLError):
                pytest.skip(
                    f"OpenSSL {ssl.OPENSSL_VERSION} refuses TLS 1.0 at SECLEVEL 0: "
                    f"{error.__cause__}"
                )
            raise

        await wait_for_messages(legacy_fake_access_point, 1)
        assert legacy_fake_access_point.tls_versions == ["TLSv1"]
        assert_access_point_message(legacy_fake_access_point.messages[0])


class TestNoSecretLeaks:
    async def test_password_never_reaches_logs_errors_or_reprs(
        self,
        fake_access_point: FakeAccessPoint,
        closed_port: int,
        caplog: pytest.LogCaptureFixture,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        caplog.set_level(logging.DEBUG)
        password = "Tr0ub4dor&3-synthetic"
        network = HomeNetwork("home", password)
        raised: list[BaseException] = []

        connection = SoftApConnection(
            address=fake_access_point.address, port=fake_access_point.port
        )
        async with connection:
            await connection.send_access_point(SERIAL, network)
        await wait_for_messages(fake_access_point, 1)

        unreachable = SoftApConnection(address="127.0.0.1", port=closed_port)
        with pytest.raises(SoftApUnreachableError) as excinfo:
            await unreachable.probe(timeout=1.0)
        raised.append(excinfo.value)
        with pytest.raises(SoftApDialError) as excinfo:
            await unreachable.open()
        raised.append(excinfo.value)
        with pytest.raises(SoftApSendError) as excinfo:
            await unreachable.send_access_point(SERIAL, network)
        raised.append(excinfo.value)

        def refuse(self: ssl.SSLContext, ciphers: str) -> None:
            raise ssl.SSLError(1, f"no cipher match for {password}")

        monkeypatch.setattr(ssl.SSLContext, "set_ciphers", refuse)
        with pytest.raises(LegacyTlsUnavailableError) as excinfo:
            SoftApConnection(legacy_tls=True)
        # The host's own error text is passed through; only our side is checked.
        assert "no cipher match" in str(excinfo.value)

        assert password.encode() in fake_access_point.messages[0]
        assert caplog.records, "the client logged nothing at DEBUG"
        assert password not in caplog.text
        for error in raised:
            assert password not in str(error)
            assert password not in repr(error)
        assert password not in repr(connection)
        assert password not in repr(unreachable)
        assert repr(connection) == (
            f"SoftApConnection(address='127.0.0.1', port={fake_access_point.port}, "
            "dial_timeout=10.0, legacy_tls=False)"
        )


def test_softap_names_are_exported_from_the_package() -> None:
    for name in (
        "SOFTAP_ADDRESS",
        "SOFTAP_PORT",
        "SoftApClient",
        "SoftApConnection",
        "build_access_point_message",
    ):
        assert name in lifx.onboard.__all__
        assert getattr(lifx.onboard, name) is getattr(softap, name)
