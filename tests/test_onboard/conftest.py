"""Fixtures for the onboarding tests.

An in-process fake LIFX SoftAP exercises the real TLS client; scripted fakes
for the ``Scanner``, ``Joiner`` and ``SoftApClient`` protocols drive the state
machine without a socket.
"""

from __future__ import annotations

import asyncio
import socket
import ssl
import warnings
from collections import deque
from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, cast

import pytest
from lifx_emulator import EmulatedLifxServer
from lifx_emulator.devices import DeviceManager
from lifx_emulator.factories import create_color_light
from lifx_emulator.repositories import DeviceRepository
from lifx_emulator.scenarios import HierarchicalScenarioManager

from lifx import DeviceEvent, DeviceEventType, DeviceWatcher
from lifx.network.discovery.mdns.discovery import _override_mdns_service_source
from lifx.onboard import (
    SOFTAP_ADDRESS,
    SOFTAP_PORT,
    HomeNetwork,
    SoftApNetwork,
    SoftApUnreachableError,
)
from lifx.protocol.models import Serial
from tests.conftest import HANG_GUARD_TIMEOUT, EmulatorRunner, get_free_port

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


# ---- fakes for the state machine -----------------------------------------

#: A clearly synthetic SoftAP name and the serial it encodes.
SOFTAP_SSID = "LIFX Candle Color 0a0b0c"
SOFTAP_SERIAL = Serial.from_string("d073d50a0b0c")
#: A second device in setup mode, for target selection tests.
OTHER_SOFTAP_SSID = "LIFX Beam 0d0e0f"
HOME_SSID = "Home-Network"
HOME_PASSWORD = "correct-horse-battery-staple"
ORIGINAL_SSID = "Office-Network"


def softap_network(ssid: str = SOFTAP_SSID, rssi: float = -40.0) -> SoftApNetwork:
    """A LIFX SoftAP as a scanner would report it."""
    return SoftApNetwork.from_ssid(ssid, rssi=rssi)


@pytest.fixture
def home_network() -> HomeNetwork:
    return HomeNetwork(HOME_SSID, HOME_PASSWORD)


class FakeScanner:
    """A scripted ``Scanner``.

    Each ``scan()`` consumes the next entry of ``results``: a list of networks
    to return or an exception to raise. The last entry repeats forever, and no
    entries at all means every scan is empty.
    """

    interface = "fake0"

    def __init__(self, *results: list[SoftApNetwork] | BaseException) -> None:
        self.results = list(results)
        self.calls: list[dict[str, Any]] = []

    async def scan(
        self, *, min_rssi: float = 0.0, include_non_lifx: bool = False
    ) -> list[SoftApNetwork]:
        self.calls.append({"min_rssi": min_rssi, "include_non_lifx": include_non_lifx})
        if not self.results:
            return []
        item = self.results.pop(0) if len(self.results) > 1 else self.results[0]
        if isinstance(item, BaseException):
            raise item
        return list(item)


class FakeJoiner:
    """A recording ``Joiner`` whose optional capabilities are mixed in.

    ``calls`` records every method call in order so tests can assert on the
    sequence. ``current`` is the network the fake believes the host is on;
    ``join()``, ``rejoin()`` and ``disassociate()`` update it, and each
    ``current_ssid()`` poll first pops the next entry of ``ssid_sequence``
    into it, which is how a test scripts what the OS reports over time; an
    exception in the sequence is raised by that poll instead, the way a
    reporter backend fails. The ``after_join`` and ``after_disassociate``
    lists are appended to ``ssid_sequence`` when those calls succeed.

    The host has one WiFi interface, so a ``join()`` while a previous
    ``join()`` has not been followed by a ``rejoin()`` is a test failure:
    bulk onboarding must never overlap two devices.
    """

    def __init__(
        self,
        *,
        current: str | None = None,
        join_failures: int = 0,
        rejoin_failures: int = 0,
        rejoin_failures_for: str | None = None,
        rejoin_error_lands_anyway: bool = False,
        rejoin_hangs: bool = False,
        join_hangs: bool = False,
        forget_hangs: bool = False,
        disassociate_hangs: bool = False,
        rejoin_fail_takes: float = 0.0,
        report_takes: float = 0.0,
        forget_error: BaseException | None = None,
        disassociate_error: BaseException | None = None,
        rejoin_error_echoes_password: bool = False,
    ) -> None:
        self.rejoin_error_echoes_password = rejoin_error_echoes_password
        self.forget_error = forget_error
        self.disassociate_error = disassociate_error
        self.current = current
        self.join_failures = join_failures
        self.rejoin_failures = rejoin_failures
        self.rejoin_failures_for = rejoin_failures_for
        self.rejoin_error_lands_anyway = rejoin_error_lands_anyway
        self.rejoin_hangs = rejoin_hangs
        self.join_hangs = join_hangs
        self.forget_hangs = forget_hangs
        self.disassociate_hangs = disassociate_hangs
        self.rejoin_fail_takes = rejoin_fail_takes
        self.report_takes = report_takes
        self.calls: list[str] = []
        self.joins: list[SoftApNetwork] = []
        self.rejoins: list[tuple[str, str]] = []
        self.forgotten: list[str] = []
        self.ssid_sequence: deque[str | None | BaseException] = deque()
        self.after_join: list[str | None | BaseException] = []
        self.after_disassociate: list[str | None | BaseException] = []
        self.on_softap: SoftApNetwork | None = None

    async def join(self, network: SoftApNetwork) -> None:
        self.calls.append("join")
        if self.on_softap is not None:
            raise AssertionError(
                f"join({network.ssid!r}) while still on {self.on_softap.ssid!r}"
            )
        if self.join_failures > 0:
            self.join_failures -= 1
            raise OSError("could not find network")
        self.joins.append(network)
        self.on_softap = network
        self.current = network.ssid
        self.ssid_sequence.extend(self.after_join)
        if self.join_hangs:
            # The association has changed but the backend has not returned
            # yet: it is still waiting on DHCP or a subprocess.
            await asyncio.sleep(HANG_GUARD_TIMEOUT)

    async def rejoin(self, ssid: str, password: str = "") -> None:
        self.calls.append("rejoin")
        self.rejoins.append((ssid, password))
        self.on_softap = None
        if self.rejoin_hangs:
            await asyncio.sleep(HANG_GUARD_TIMEOUT)
        applies = self.rejoin_failures_for is None or self.rejoin_failures_for == ssid
        if applies and self.rejoin_failures > 0:
            self.rejoin_failures -= 1
            if self.rejoin_fail_takes:
                # A backend that fails slowly, the way a stuck OS command does.
                await asyncio.sleep(self.rejoin_fail_takes)
            if self.rejoin_error_lands_anyway:
                self.current = ssid
                self.ssid_sequence.clear()
            if self.rejoin_error_echoes_password:
                # A subprocess backend echoing its argv would do this.
                raise RuntimeError(f"nmcli dev wifi connect {ssid} password {password}")
            raise OSError("join failed")
        self.current = ssid


class _Reports:
    async def current_ssid(self: Any) -> str | None:
        self.calls.append("current_ssid")
        if self.report_takes:
            await asyncio.sleep(self.report_takes)
        if self.ssid_sequence:
            item = self.ssid_sequence.popleft()
            if isinstance(item, BaseException):
                raise item
            self.current = item
        return self.current


class _Forgets:
    async def forget(self: Any, ssid: str) -> None:
        self.calls.append("forget")
        if self.forget_hangs:
            await asyncio.sleep(HANG_GUARD_TIMEOUT)
        if self.forget_error is not None:
            raise self.forget_error
        self.forgotten.append(ssid)


class _Disassociates:
    async def disassociate(self: Any) -> None:
        self.calls.append("disassociate")
        if self.disassociate_hangs:
            await asyncio.sleep(HANG_GUARD_TIMEOUT)
        if self.disassociate_error is not None:
            raise self.disassociate_error
        self.current = None
        self.ssid_sequence.extend(self.after_disassociate)


def make_joiner(
    *,
    reporter: bool = False,
    forgetter: bool = False,
    disassociator: bool = False,
    **kwargs: Any,
) -> FakeJoiner:
    """Build a ``FakeJoiner`` with exactly the capabilities asked for."""
    bases: list[type] = []
    if reporter:
        bases.append(_Reports)
    if forgetter:
        bases.append(_Forgets)
    if disassociator:
        bases.append(_Disassociates)
    bases.append(FakeJoiner)
    return type("ScriptedJoiner", tuple(bases), {})(**kwargs)


def make_scanner(
    *results: Any, reporter: list[str | None] | None = None
) -> FakeScanner:
    """Build a ``FakeScanner``.

    With ``reporter`` the scanner also implements ``CurrentNetworkReporter``,
    answering each poll with the next entry; the last entry repeats.
    """
    if reporter is None:
        return FakeScanner(*results)
    answers = deque(reporter)

    class ReportingScanner(FakeScanner):
        async def current_ssid(self) -> str | None:
            answer = answers.popleft() if len(answers) > 1 else answers[0]
            self.calls.append({"current_ssid": answer})
            return answer

    return ReportingScanner(*results)


class FakeSoftApClient:
    """A recording ``SoftApClient`` that never touches a socket."""

    def __init__(
        self,
        *,
        probe_failures: int = 0,
        probe_takes: float = 0.0,
        open_takes: float = 0.0,
        open_error: BaseException | None = None,
        send_error: BaseException | None = None,
        address: str = SOFTAP_ADDRESS,
        port: int = SOFTAP_PORT,
    ) -> None:
        self.probe_failures = probe_failures
        self.probe_takes = probe_takes
        self.open_takes = open_takes
        self.open_error = open_error
        self.send_error = send_error
        self._address = address
        self._port = port
        self.probes: list[float | None] = []
        self.opened = 0
        self.sent: list[tuple[Serial, HomeNetwork]] = []
        self.closed = 0

    @property
    def address(self) -> str:
        return self._address

    @property
    def port(self) -> int:
        return self._port

    async def probe(self, *, timeout: float | None = None) -> None:
        self.probes.append(timeout)
        if self.probe_failures > 0:
            self.probe_failures -= 1
            await asyncio.sleep(self.probe_takes)
            raise SoftApUnreachableError(f"nothing at {self._address}:{self._port}")

    async def open(self) -> None:
        self.opened += 1
        await asyncio.sleep(self.open_takes)
        if self.open_error is not None:
            raise self.open_error

    async def send_access_point(self, target: Serial, network: HomeNetwork) -> None:
        if self.send_error is not None:
            raise self.send_error
        self.sent.append((target, network))

    async def close(self) -> None:
        self.closed += 1


# ---- LAN verification: the emulator and a scriptable watcher ---------------

LOOPBACK = "127.0.0.1"


@pytest.fixture(autouse=True)
def _no_ambient_mdns() -> Iterator[None]:
    """Keep a real mDNS responder on the host out of every watcher sweep."""

    async def empty_source():
        return
        yield  # noqa: B901

    with _override_mdns_service_source(empty_source):
        yield


@contextmanager
def emulator(serials: tuple[str, ...], port: int | None = None) -> Iterator[int]:
    """Run the embedded emulator on the loopback with one color light per serial."""
    scenario_manager = HierarchicalScenarioManager()
    port = port or get_free_port()
    server = EmulatedLifxServer(
        devices=[
            create_color_light(serial=s, scenario_manager=scenario_manager)
            for s in serials
        ],
        device_manager=DeviceManager(DeviceRepository()),
        bind_address=LOOPBACK,
        port=port,
        scenario_manager=scenario_manager,
    )
    runner = EmulatorRunner(server)
    runner.start()
    try:
        yield port
    finally:
        runner.stop()


@contextmanager
def growing_emulator(
    port: int | None = None,
) -> Iterator[tuple[EmulatedLifxServer, int]]:
    """Run the embedded emulator on the loopback with no devices yet.

    ``add_color_light(server, serial)`` adds one while it runs, which is how a
    test makes a device appear on the LAN at a chosen moment.
    """
    scenario_manager = HierarchicalScenarioManager()
    port = port or get_free_port()
    server = EmulatedLifxServer(
        devices=[],
        device_manager=DeviceManager(DeviceRepository()),
        bind_address=LOOPBACK,
        port=port,
        scenario_manager=scenario_manager,
    )
    runner = EmulatorRunner(server)
    runner.start()
    try:
        yield server, port
    finally:
        runner.stop()


def add_color_light(server: EmulatedLifxServer, serial: str) -> None:
    """Add a color light to a running emulator so the next sweep finds it."""
    assert server.add_device(create_color_light(serial=serial)), serial


def loopback_watcher(port: int, **kwargs: Any) -> DeviceWatcher:
    """A ``DeviceWatcher`` that sweeps only the loopback, quickly."""
    kwargs.setdefault("sweep_interval", 3600.0)
    kwargs.setdefault("discovery_timeout", 0.5)
    kwargs.setdefault("idle_timeout_multiplier", 0.5)
    kwargs.setdefault("device_timeout", 2.0)
    return DeviceWatcher(broadcast_address=LOOPBACK, port=port, **kwargs)


@dataclass(frozen=True)
class FakeSighting:
    """Stands in for the device object a ``DeviceEvent`` carries."""

    serial: str
    ip: str
    port: int


class FakeWatcher:
    """The listener surface of a ``DeviceWatcher``, driven by the test.

    ``emit()`` delivers a ``DeviceEvent`` to every registered listener, so a
    test can stage sightings the emulator cannot produce, such as a device
    first seen at the SoftAP address.
    """

    def __init__(self, *, enter_takes: float = 0.0) -> None:
        self.enter_takes = enter_takes
        self._listeners: list[Any] = []
        self.entered = 0
        self.exited = 0
        self.running = False

    @property
    def listener_count(self) -> int:
        return len(self._listeners)

    def add_listener(self, listener: Any) -> Any:
        self._listeners.append(listener)

        def remove() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return remove

    async def __aenter__(self) -> FakeWatcher:
        self.entered += 1
        await asyncio.sleep(self.enter_takes)
        self.running = True
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        self.exited += 1
        self.running = False

    def emit(
        self,
        event_type: DeviceEventType,
        serial: str,
        ip: str,
        port: int = 56700,
        changes: dict[str, tuple[object, object]] | None = None,
    ) -> DeviceEvent:
        event = DeviceEvent(
            type=event_type,
            serial=serial,
            device=cast(Any, FakeSighting(serial, ip, port)),
            changes=MappingProxyType(dict(changes or {})),
        )
        for listener in tuple(self._listeners):
            listener(event)
        return event
