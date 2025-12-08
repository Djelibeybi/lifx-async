"""Shared fixtures for all tests."""

from __future__ import annotations

import asyncio
import os
import socket
import threading
from collections.abc import Generator
from contextlib import contextmanager

import pytest

# Import emulator library components
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
from lifx.network.connection import DeviceConnection


def get_free_port() -> int:
    """Get a free UDP port."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


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


@pytest.fixture(scope="session")
def emulator_available() -> bool:
    """Check if lifx-emulator-core is available.

    The library is always available as it's a direct dependency.
    This fixture exists for backwards compatibility with test markers.
    """
    import sys

    if sys.platform != "linux":
        return False

    try:
        from lifx_emulator import EmulatedLifxServer  # noqa: F401

        return True
    except ImportError:
        return False


@pytest.fixture(scope="session")
def emulator_server(
    emulator_available: bool,
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

    if not emulator_available:
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
async def cleanup_device_connections(request, emulator_available):
    """Clean up device connections after each test.

    This ensures test isolation by closing all device connections
    after each test completes. Since each test has its own event loop,
    connections must be closed so they can reopen with the new loop.

    Only runs for tests marked with @pytest.mark.emulator and when
    the emulator is available.
    """
    yield

    # Skip cleanup if emulator is not available or test doesn't use it
    if not emulator_available:
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
