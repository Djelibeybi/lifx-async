"""Shared fixtures for all tests."""

from __future__ import annotations

import asyncio
import os
import socket
import sys
import threading
from collections.abc import Generator
from contextlib import contextmanager

import pytest
from lifx_emulator import EmulatedLifxServer
from lifx_emulator.devices import DeviceManager
from lifx_emulator.factories import (
    create_color_light,
    create_color_temperature_light,
    create_device,
    create_hev_light,
    create_infrared_light,
    create_multizone_light,
    create_switch,
    create_tile_device,
)
from lifx_emulator.repositories import DeviceRepository
from lifx_emulator.scenarios import HierarchicalScenarioManager
from lifx_emulator.scenarios.models import ScenarioConfig

from lifx.api import DeviceGroup
from lifx.devices import HevLight, InfraredLight, Light, MultiZoneLight
from lifx.devices.base import Device
from lifx.devices.ceiling import CeilingLight
from lifx.devices.matrix import MatrixLight
from lifx.exceptions import LifxConnectionError, LifxTimeoutError
from lifx.network.connection import DeviceConnection


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add custom command-line options for pytest."""
    parser.addoption(
        "--disable-emulator",
        action="store_true",
        default=False,
        help="Disable lifx-emulator tests for this test run",
    )


# Give emulator tests more time on slow CI runners (especially Windows)
_EMULATOR_TIMEOUT = 120

_EMULATOR_FIXTURES = frozenset(
    {
        "emulator_port",
        "emulator_server",
        "emulator_devices",
        "ceiling_device",
        "switch_device",
    }
)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Apply a longer timeout to emulator tests."""
    for item in items:
        uses_emulator = item.get_closest_marker("emulator") is not None or (
            hasattr(item, "fixturenames")
            and _EMULATOR_FIXTURES & set(item.fixturenames)
        )
        if uses_emulator and item.get_closest_marker("timeout") is None:
            item.add_marker(pytest.mark.timeout(_EMULATOR_TIMEOUT))


def pytest_set_filtered_exceptions() -> list[type[Exception]]:
    """Configure pytest-retry to only retry on network-related exceptions.

    Tests that fail with LifxTimeoutError or LifxConnectionError will be
    retried automatically, as these are typically transient network issues.
    """
    return [LifxTimeoutError, LifxConnectionError]


def get_free_port() -> int:
    """Get a free UDP port."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def get_free_port6() -> int:
    """Get a free UDP port on the IPv6 loopback.

    ``get_free_port()`` binds ``AF_INET`` on ``127.0.0.1`` and cannot speak
    for an IPv6 port: a ``IPV6_V6ONLY`` socket has its own port space, so a
    port free for IPv4 says nothing about ``::1``.

    The port is asserted non-zero before it is returned, so a bind that
    somehow failed to assign one fails here rather than handing an unusable
    0 to the emulator.
    """
    with socket.socket(socket.AF_INET6, socket.SOCK_DGRAM) as s:
        s.bind(("::1", 0))
        port = s.getsockname()[1]
    assert port > 0, "binding ('::1', 0) returned port 0 instead of an ephemeral port"
    return port


class EmulatorRunner:
    """Manages the emulator server in a background thread with its own event loop."""

    def __init__(self, server: EmulatedLifxServer):
        self.server = server
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._started = threading.Event()

    def _run_loop(self) -> None:
        """Run the event loop in the background thread."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        # Start the server
        self._loop.run_until_complete(self.server.start())
        self._started.set()

        # Run until stopped
        self._loop.run_forever()

        # Cleanup
        self._loop.run_until_complete(self.server.stop())
        self._loop.close()

    def start(self) -> None:
        """Start the emulator in a background thread."""
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        # Wait for server to start
        self._started.wait(timeout=5.0)

    def stop(self) -> None:
        """Stop the emulator and its event loop."""
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread is not None:
            self._thread.join(timeout=5.0)


class _Ipv6EmulatedLifxServer(EmulatedLifxServer):
    """An emulator server that creates and configures its own ``::1`` socket.

    ``IPV6_V6ONLY`` can only be set on an unbound socket: setting it after a
    bind raises ``OSError: [Errno 22] Invalid argument`` on macOS, verified
    on this project's development machine. The stock
    ``EmulatedLifxServer.start()`` binds inside itself, by handing
    ``local_addr=`` to ``create_datagram_endpoint``, so there is no moment
    between socket creation and bind for a caller to reach.

    Owning socket creation here is therefore the only way to set the option
    explicitly rather than trusting the platform default, which is what this
    phase asked for as hygiene against a future wildcard bind. ``stop()`` is
    inherited unchanged: it closes the transport, and the transport owns the
    adopted socket.
    """

    async def start(self) -> None:
        """Bind a V6ONLY ``AF_INET6`` socket and hand it to asyncio."""
        loop = asyncio.get_running_loop()
        sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
        try:
            # Before the bind. The option is immutable once the socket is
            # bound, so this ordering is the whole point of the subclass.
            sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
            sock.bind((self.bind_address, self.port))
            sock.setblocking(False)
            self.transport, _ = await loop.create_datagram_endpoint(
                lambda: self.LifxProtocol(self), sock=sock
            )
        except Exception:
            # Nothing has taken ownership of the descriptor yet, so a
            # partway failure has to close it here or it leaks.
            sock.close()
            raise


@pytest.fixture(scope="session")
def emulator_enabled(request: pytest.FixtureRequest) -> bool:
    """Decide whether the normal embedded-emulator suite is enabled.

    The library is a required development dependency, so pytest collection
    fails if it is absent. Emulator tests are enabled off Windows by default;
    use ``--disable-emulator`` to disable them explicitly.

    Args:
        request: Pytest fixture request for accessing command-line options
    """
    # Check command-line flags
    disable_emulator = request.config.getoption("--disable-emulator", default=False)

    if disable_emulator:
        return False

    # Emulator tests are too flaky on Windows (timing-sensitive UDP)
    if sys.platform == "win32":
        return False

    return True


def targeted_ipv6_emulator_allowed(
    disable_emulator: bool,
    platform: str,
    windows_ci_opt_in: str | None,
) -> bool:
    """Decide whether the focused targeted-IPv6 emulator path may run."""
    if disable_emulator:
        return False
    if platform.startswith("win32"):
        return windows_ci_opt_in == "1"
    return True


@pytest.fixture(scope="session")
def targeted_ipv6_emulator_available(request: pytest.FixtureRequest) -> bool:
    """Check emulator availability for the focused targeted-IPv6 path."""
    disable_emulator = request.config.getoption("--disable-emulator", default=False)
    return targeted_ipv6_emulator_allowed(
        disable_emulator,
        sys.platform,
        os.environ.get("LIFX_WINDOWS_IPV6_DISCOVERY"),
    )


def ipv6_probe_outcome(error: OSError, require_ipv6: str | None) -> bool | str:
    """Decide what a failed ``::1`` bind means for this run.

    Split out of :func:`ipv6_available` so both non-happy arms are testable
    without arranging a real bind failure. Every host the suite runs on
    today can bind ``::1``, so the probe only ever takes its success branch
    and the skip and fail-instead-of-skip behaviour would otherwise be
    trusted purely on inspection.

    Args:
        error: The ``OSError`` raised by the probe bind.
        require_ipv6: The raw ``LIFX_REQUIRE_IPV6`` value, or ``None`` when
            the variable is unset. Anything other than ``"1"`` means the
            IPv6 tests may skip.

    Returns:
        ``False`` when the IPv6 tests should skip, or the message to fail
        the run with when IPv6 was declared mandatory for this job.
    """
    if require_ipv6 == "1":
        return (
            f"LIFX_REQUIRE_IPV6=1 set but ::1 cannot be bound: {error}. "
            "This is the designated must-not-skip IPv6 job, so the IPv6 "
            "end-to-end tests failing to run is a build failure, not a skip."
        )
    return False


@pytest.fixture(scope="session")
def ipv6_available() -> bool:
    """Check whether an IPv6 loopback socket can be bound.

    Mirrors :func:`emulator_enabled`: a session-scoped bool, probed once
    and cached. Every ``::1`` fixture gates on it, so all the dependent
    tests skip through a single decision rather than each inventing its own.

    ``LIFX_REQUIRE_IPV6=1`` turns a missing ``::1`` from a skip into a
    failure. CI sets it for the Ubuntu IPv6 suite and the focused Windows
    targeted-discovery check, so IPv6 cannot quietly skip everywhere. The
    variable guards this probe alone; emulator eligibility is handled by the
    normal and focused fixtures separately.
    """
    try:
        with socket.socket(socket.AF_INET6, socket.SOCK_DGRAM) as probe:
            probe.bind(("::1", 0))
    except OSError as error:
        outcome = ipv6_probe_outcome(error, os.environ.get("LIFX_REQUIRE_IPV6"))
        if isinstance(outcome, str):
            pytest.fail(outcome)
        return False
    return True


@pytest.fixture(scope="session")
def emulator_server(
    emulator_enabled: bool,
) -> Generator[tuple[int, EmulatedLifxServer, HierarchicalScenarioManager]]:
    """Start embedded lifx-emulator for the entire test session.

    The emulator runs in-process in a background thread, providing faster
    startup (~5-10ms vs 500ms+) and cross-platform support.

    External emulator mode:
        Set LIFX_EMULATOR_EXTERNAL=1 to skip starting the embedded emulator.
        Use LIFX_EMULATOR_PORT to specify the port (default: 56700).
        This is useful for testing against actual hardware or a manually managed
        emulator instance with custom configuration.

    Yields:
        Tuple of (port, server, scenario_manager) where:
        - port: UDP port number where the emulator is listening
        - server: EmulatedLifxServer instance for direct manipulation
        - scenario_manager: HierarchicalScenarioManager for scenario configuration
    """
    # Check if using external emulator
    use_external = os.environ.get("LIFX_EMULATOR_EXTERNAL", "").lower() in (
        "1",
        "true",
        "yes",
    )

    if use_external:
        # Use external emulator - don't start embedded server
        port = int(os.environ.get("LIFX_EMULATOR_PORT", "56700"))
        # Return None for server and scenario_manager since we don't control it
        yield port, None, None  # type: ignore[misc]
        return

    if not emulator_enabled:
        pytest.skip("lifx-emulator-core not available")

    # Create scenario manager for all devices to share
    scenario_manager = HierarchicalScenarioManager()

    # Create the 7 default devices matching the old CLI configuration:
    # --color 1 --multizone 2 --tile 1 --hev 1 --infrared 1 --color-temperature 1
    devices = [
        create_color_light(serial="d073d5000001", scenario_manager=scenario_manager),
        create_color_temperature_light(
            serial="d073d5000002", scenario_manager=scenario_manager
        ),
        create_infrared_light(serial="d073d5000003", scenario_manager=scenario_manager),
        create_hev_light(serial="d073d5000004", scenario_manager=scenario_manager),
        create_multizone_light(
            serial="d073d5000005", scenario_manager=scenario_manager
        ),
        create_multizone_light(
            serial="d073d5000006", scenario_manager=scenario_manager
        ),
        create_tile_device(
            serial="d073d5000007", tile_count=1, scenario_manager=scenario_manager
        ),
    ]

    port = get_free_port()
    device_manager = DeviceManager(DeviceRepository())

    server = EmulatedLifxServer(
        devices=devices,
        device_manager=device_manager,
        bind_address="127.0.0.1",
        port=port,
        scenario_manager=scenario_manager,
    )

    # Start the server in a background thread
    runner = EmulatorRunner(server)
    runner.start()

    yield port, server, scenario_manager

    # Stop the server
    runner.stop()


@pytest.fixture(scope="session")
def tile_chain_server(
    emulator_enabled: bool,
) -> Generator[int]:
    """Start an emulator hosting a single 5-tile LIFX Tile chain.

    The shared ``emulator_server`` fixture creates its Tile with
    ``tile_count=1``, so nothing there exercises chain behaviour. This runs a
    second emulator with the only chain-capable product (55, LIFX Tile) at its
    full 5-tile length, on its own server so the device lists that other tests
    iterate stay unchanged.

    Yields:
        UDP port the chain emulator is listening on
    """
    if not emulator_enabled:
        pytest.skip("lifx-emulator-core not available")

    scenario_manager = HierarchicalScenarioManager()
    devices = [
        create_tile_device(
            serial="d073d5000101",
            tile_count=5,
            scenario_manager=scenario_manager,
        )
    ]

    port = get_free_port()
    server = EmulatedLifxServer(
        devices=devices,
        device_manager=DeviceManager(DeviceRepository()),
        bind_address="127.0.0.1",
        port=port,
        scenario_manager=scenario_manager,
    )

    runner = EmulatorRunner(server)
    runner.start()

    yield port

    runner.stop()


@pytest.fixture
def tile_chain_light(tile_chain_server: int) -> MatrixLight:
    """Return a MatrixLight backed by the 5-tile chain emulator.

    The device is not connected; use it as an async context manager.
    """
    return MatrixLight(
        serial="d073d5000101",
        ip="127.0.0.1",
        port=tile_chain_server,
        timeout=2.0,
        max_retries=2,
    )


#: Serial of the single device hosted by the ``::1`` emulator. Exported so
#: the IPv6 end-to-end tests can address the emulated device directly.
IPV6_DEVICE_SERIAL = "d073d5000301"


@contextmanager
def _running_ipv6_emulator() -> Generator[tuple[int, EmulatedLifxServer]]:
    """Run one emulator bound to ``::1`` for an owning fixture.

    Every other emulator fixture binds ``127.0.0.1``, so nothing else in the
    suite exercises an ``AF_INET6`` socket. This runs its own server on the
    IPv6 loopback with its own port, which leaves ``emulator_server`` and the
    seven devices the rest of the suite iterates completely untouched.
    Parameterising the shared server over both families was rejected: it
    would roughly double the emulator suite's runtime on every CI job.

    The server is a :class:`_Ipv6EmulatedLifxServer` so ``IPV6_V6ONLY`` is
    set before the bind; the option is read back here afterwards. Reading the
    option is legal on a bound socket where setting it is not, which is why
    the set lives in the subclass and only the read-back lives here.

    Its single device is a matrix-capable Tile rather than a plain colour
    light. It answers the Light commands the control tests use exactly as a
    plain light would, and it additionally applies the ``Set64`` frames the
    Animator sends: the emulator's ``Set64Handler`` returns early for a
    device without matrix capability, so against a plain light the animation
    test could only ever prove a datagram was sent, never that a frame
    arrived and was applied.

    Yields:
        Tuple of (port, server) where:
        - port: UDP port the IPv6 emulator is listening on
        - server: the server itself, so a test can read emulated device
          state back and prove a frame actually landed
    """
    scenario_manager = HierarchicalScenarioManager()
    devices = [
        create_tile_device(
            serial=IPV6_DEVICE_SERIAL,
            tile_count=1,
            scenario_manager=scenario_manager,
        )
    ]

    port = get_free_port6()
    server = _Ipv6EmulatedLifxServer(
        devices=devices,
        device_manager=DeviceManager(DeviceRepository()),
        bind_address="::1",
        port=port,
        scenario_manager=scenario_manager,
    )

    runner = EmulatorRunner(server)
    try:
        runner.start()

        serving_socket = (
            server.transport.get_extra_info("socket")
            if server.transport is not None
            else None
        )
        assert serving_socket is not None, (
            "the ::1 emulator did not finish starting within the runner timeout"
        )
        assert serving_socket.family == socket.AF_INET6
        assert serving_socket.getsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY) == 1

        yield port, server
    finally:
        runner.stop()


@pytest.fixture(scope="session")
def _shared_ipv6_emulator_server(
    ipv6_available: bool,
) -> Generator[tuple[int, EmulatedLifxServer]]:
    """Start the one IPv6 emulator shared by every eligible test path."""
    if not ipv6_available:
        pytest.skip("IPv6 loopback (::1) is not available on this host")

    with _running_ipv6_emulator() as running_server:
        yield running_server


@pytest.fixture(scope="session")
def emulator_server_ipv6(
    emulator_enabled: bool,
    request: pytest.FixtureRequest,
) -> tuple[int, EmulatedLifxServer]:
    """Return the shared IPv6 emulator for the normal cross-platform suite."""
    if not emulator_enabled:
        pytest.skip("lifx-emulator-core tests are disabled on this platform")
    return request.getfixturevalue("_shared_ipv6_emulator_server")


@pytest.fixture(scope="session")
def targeted_emulator_server_ipv6(
    targeted_ipv6_emulator_available: bool,
    request: pytest.FixtureRequest,
) -> tuple[int, EmulatedLifxServer]:
    """Return the shared server for cross-platform targeted IPv6 discovery."""
    if not targeted_ipv6_emulator_available:
        if sys.platform == "win32" and os.environ.get("LIFX_REQUIRE_IPV6") == "1":
            pytest.fail(
                "the required Windows IPv6 check was not opted in; set "
                "LIFX_WINDOWS_IPV6_DISCOVERY=1"
            )
        pytest.skip("the targeted IPv6 emulator path is not enabled")
    return request.getfixturevalue("_shared_ipv6_emulator_server")


@pytest.fixture
def ipv6_light(emulator_server_ipv6: tuple[int, EmulatedLifxServer]) -> Light:
    """Return a Light backed by the ``::1`` emulator.

    The device is not connected; use it as an async context manager.
    """
    port, _ = emulator_server_ipv6
    return Light(
        serial=IPV6_DEVICE_SERIAL,
        ip="::1",
        port=port,
        timeout=2.0,
        max_retries=2,
    )


@pytest.fixture(scope="session")
def emulator_port(
    emulator_server: tuple[int, EmulatedLifxServer, HierarchicalScenarioManager],
) -> int:
    """Return just the emulator port for tests that don't need server access.

    This is a convenience fixture for backwards compatibility with tests
    that only need the port number.
    """
    port, _, _ = emulator_server
    return port


@pytest.fixture(scope="session")
def emulator_devices(
    emulator_server: tuple[int, EmulatedLifxServer, HierarchicalScenarioManager],
) -> DeviceGroup:
    """Return a DeviceGroup with the 7 hardcoded emulated devices.

    This fixture hard-codes the seven devices created by the emulator to avoid
    the overhead of running discovery for every test. All devices connect to
    127.0.0.1 on the emulator's port.

    Returns:
        DeviceGroup containing the 7 emulated devices:
        - 2 regular Light devices (d073d5000001, d073d5000002)
        - 1 InfraredLight (d073d5000003)
        - 1 HevLight (d073d5000004)
        - 2 MultiZoneLight devices (d073d5000005, d073d5000006)
        - 1 MatrixLight (d073d5000007)
    """
    port, _, _ = emulator_server
    devices: list[Device] = [
        Light(
            serial="d073d5000001",
            ip="127.0.0.1",
            port=port,
            timeout=2.0,
            max_retries=2,
        ),
        Light(
            serial="d073d5000002",
            ip="127.0.0.1",
            port=port,
            timeout=2.0,
            max_retries=2,
        ),
        InfraredLight(
            serial="d073d5000003",
            ip="127.0.0.1",
            port=port,
            timeout=2.0,
            max_retries=2,
        ),
        HevLight(
            serial="d073d5000004",
            ip="127.0.0.1",
            port=port,
            timeout=2.0,
            max_retries=2,
        ),
        MultiZoneLight(
            serial="d073d5000005",
            ip="127.0.0.1",
            port=port,
            timeout=2.0,
            max_retries=2,
        ),
        MultiZoneLight(
            serial="d073d5000006",
            ip="127.0.0.1",
            port=port,
            timeout=2.0,
            max_retries=2,
        ),
        MatrixLight(
            serial="d073d5000007",
            ip="127.0.0.1",
            port=port,
            timeout=2.0,
            max_retries=2,
        ),
    ]
    return DeviceGroup(devices)


@pytest.fixture(autouse=True)
async def cleanup_device_connections(request, emulator_enabled):
    """Clean up device connections after each test.

    This ensures test isolation by closing all device connections
    after each test completes. Since each test has its own event loop,
    connections must be closed so they can reopen with the new loop.

    Only runs for tests marked with @pytest.mark.emulator and when
    the emulator is available.
    """
    yield

    # Skip cleanup if emulator is not available or test doesn't use it
    if not emulator_enabled:
        return

    # Get the emulator_devices fixture if it was used
    if "emulator_devices" in request.fixturenames:
        emulator_devices = request.getfixturevalue("emulator_devices")
        # Close all device connections after test completes
        for device in emulator_devices:
            await device.connection.close()


@pytest.fixture(scope="session")
def ceiling_device(
    emulator_server: tuple[int, EmulatedLifxServer, HierarchicalScenarioManager],
):
    """Create a LIFX Ceiling device (product 201) for SKY effect and component testing.

    The Ceiling device supports SKY effects and has >128 zones (16x8 tile).
    This fixture dynamically adds the device to the running emulator.

    Returns:
        CeilingLight instance for the Ceiling device
    """
    port, server, scenario_manager = emulator_server

    if server is None:
        pytest.skip("Cannot create ceiling device with external emulator")

    # Create Ceiling device (product 201 = LIFX Ceiling with 16x8 = 128 zones)
    # Let the emulator use its internal product configuration
    ceiling = create_device(
        product_id=201,
        serial="d073d5000100",
        scenario_manager=scenario_manager,
    )
    server.add_device(ceiling)

    yield CeilingLight(
        serial="d073d5000100",
        ip="127.0.0.1",
        port=port,
        timeout=2.0,
        max_retries=2,
    )

    # Clean up: remove the device
    server.remove_device("d073d5000100")


@pytest.fixture(scope="session")
def switch_device(
    emulator_server: tuple[int, EmulatedLifxServer, HierarchicalScenarioManager],
):
    """Create a LIFX Switch device (product 70) for StateUnhandled testing.

    The Switch device does not support Light commands (GetColor, SetColor, etc.)
    and will return StateUnhandled responses. This is useful for testing that
    the library correctly handles unsupported command responses.

    Returns:
        DeviceConnection instance for the Switch device
    """
    port, server, scenario_manager = emulator_server

    if server is None:
        pytest.skip("Cannot create switch device with external emulator")

    # Create Switch device (product 70 = LIFX Switch)
    switch = create_switch(
        serial="d073d5000200",
        scenario_manager=scenario_manager,
    )
    server.add_device(switch)

    yield DeviceConnection(
        serial="d073d5000200",
        ip="127.0.0.1",
        port=port,
        timeout=2.0,
        max_retries=2,
    )

    # Clean up: remove the device
    server.remove_device("d073d5000200")


@pytest.fixture
def scenario_manager(
    emulator_server: tuple[int, EmulatedLifxServer, HierarchicalScenarioManager],
):
    """Provide a context manager for scenario management.

    Automatically cleans up scenarios after each test to prevent
    test contamination.

    Usage:
        def test_example(scenario_manager):
            with scenario_manager("devices", "d073d5000001", {...}):
                # Test code with scenario active
                pass
            # Scenario automatically cleaned up
    """
    _, server, sm = emulator_server

    if server is None:
        pytest.skip("Cannot manage scenarios with external emulator")
    active_scenarios: list[tuple[str, str]] = []

    @contextmanager
    def manage_scenario(scope: str, identifier: str, config: dict):
        """Add a scenario and ensure cleanup.

        Args:
            scope: "global", "devices", "types", "locations", or "groups"
            identifier: The scope identifier (serial, type name, etc.)
                       Use empty string for "global"
            config: Scenario configuration dict with keys like:
                   - drop_packets: {pkt_type: drop_rate}
                   - response_delays: {pkt_type: delay_seconds}
                   - malformed_packets: [pkt_types]
                   - etc.
        """
        scenario_config = ScenarioConfig(**config)

        # Set the scenario based on scope
        if scope == "global":
            sm.set_global_scenario(scenario_config)
        elif scope == "devices":
            sm.set_device_scenario(identifier, scenario_config)
        elif scope == "types":
            sm.set_type_scenario(identifier, scenario_config)
        elif scope == "locations":
            sm.set_location_scenario(identifier, scenario_config)
        elif scope == "groups":
            sm.set_group_scenario(identifier, scenario_config)
        else:
            raise ValueError(f"Unknown scope: {scope}")

        active_scenarios.append((scope, identifier))

        # Invalidate all scenario caches so devices pick up the new scenario
        server.invalidate_all_scenario_caches()

        try:
            yield
        finally:
            # Clean up this scenario
            if scope == "global":
                sm.clear_global_scenario()
            elif scope == "devices":
                sm.delete_device_scenario(identifier)
            elif scope == "types":
                sm.delete_type_scenario(identifier)
            elif scope == "locations":
                sm.delete_location_scenario(identifier)
            elif scope == "groups":
                sm.delete_group_scenario(identifier)

            try:
                active_scenarios.remove((scope, identifier))
            except ValueError:
                pass

            # Invalidate caches after cleanup
            server.invalidate_all_scenario_caches()

    yield manage_scenario

    # Clean up any remaining scenarios
    for scope, identifier in active_scenarios:
        try:
            if scope == "global":
                sm.clear_global_scenario()
            elif scope == "devices":
                sm.delete_device_scenario(identifier)
            elif scope == "types":
                sm.delete_type_scenario(identifier)
            elif scope == "locations":
                sm.delete_location_scenario(identifier)
            elif scope == "groups":
                sm.delete_group_scenario(identifier)
        except Exception:
            pass  # Best effort cleanup


@pytest.fixture
async def emulator_server_with_scenarios(
    emulator_server: tuple[int, EmulatedLifxServer, HierarchicalScenarioManager],
):
    """Create devices with specific scenario configurations.

    This fixture provides a callable that applies scenarios to devices
    and returns server/device info for testing.

    Usage:
        async def test_example(emulator_server_with_scenarios):
            server, device = await emulator_server_with_scenarios(
                device_type="color",
                serial="d073d5000001",
                scenarios={"drop_packets": {20: 1.0}}
            )
            # Test code using server.port and device info
    """
    from types import SimpleNamespace

    port, server, sm = emulator_server

    if server is None:
        pytest.skip("Cannot manage scenarios with external emulator")
    applied_scenarios: list[str] = []

    async def create_device_with_scenario(
        device_type: str, serial: str, scenarios: dict
    ):
        """Apply scenarios to a device.

        Args:
            device_type: Device type (color, multizone, tile, hev, infrared)
            serial: Device serial number
            scenarios: Scenario configuration dict

        Returns:
            Tuple of (server_info, device_info) where:
            - server_info has .port attribute
            - device_info has device details
        """
        scenario_config = ScenarioConfig(**scenarios)
        sm.set_device_scenario(serial, scenario_config)
        applied_scenarios.append(serial)

        # Invalidate caches so devices pick up the new scenario
        server.invalidate_all_scenario_caches()

        # Create namespace objects for server and device info
        server_info = SimpleNamespace(port=port)
        device_info = SimpleNamespace(serial=serial, type=device_type)

        return server_info, device_info

    yield create_device_with_scenario

    # Clean up all scenarios after test
    for serial in applied_scenarios:
        try:
            sm.delete_device_scenario(serial)
        except Exception:
            pass  # Best effort cleanup

    # Invalidate caches after cleanup
    server.invalidate_all_scenario_caches()
