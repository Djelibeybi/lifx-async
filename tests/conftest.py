"""Shared fixtures for all tests."""

from __future__ import annotations

import os
import shutil
import socket
import time
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import ClassVar

import pytest
import requests
from xprocess import ProcessStarter

from lifx.api import DeviceGroup
from lifx.devices import HevLight, InfraredLight, Light, MultiZoneLight
from lifx.devices.base import Device
from lifx.devices.matrix import MatrixLight


def get_free_port() -> int:
    """Get a free UDP port."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def find_lifx_emulator() -> Path | None:
    """Find the lifx-emulator executable.

    Returns:
        Path to lifx-emulator executable, or None if not found
    """
    # Check system PATH
    system_path = shutil.which("lifx-emulator")
    if system_path:
        return Path(system_path)

    return None


@pytest.fixture(scope="session")
def emulator_available() -> bool:
    """Check if lifx-emulator is available."""
    return find_lifx_emulator() is not None


@pytest.fixture(scope="session")
def emulator_server(emulator_available: bool, xprocess) -> Generator[int]:
    """Start lifx-emulator as a subprocess for the entire test session.

    The emulator starts once at the beginning and stops when all tests complete.
    This significantly reduces test overhead compared to per-test startup.

    Only starts if lifx-emulator is available. Tests that require the emulator
    should check emulator_available or will be skipped automatically.

    Uses pytest-xprocess for robust process management and cleanup.

    External emulator mode:
        Set LIFX_EMULATOR_EXTERNAL=1 to skip starting the emulator subprocess.
        Use LIFX_EMULATOR_PORT to specify the port (default: 56700).
        This is useful for testing against actual hardware or a manually managed
        emulator instance with custom configuration.

    Yields:
        UDP port number where the emulator is listening
    """
    # Check if using external emulator
    use_external = os.environ.get("LIFX_EMULATOR_EXTERNAL", "").lower() in (
        "1",
        "true",
        "yes",
    )

    if use_external:
        # Use external emulator - don't start subprocess
        port = int(os.environ.get("LIFX_EMULATOR_PORT", "56700"))
        yield port
        # No cleanup needed for external emulator
        return

    # Standard mode: use xprocess to start emulator subprocess
    if not emulator_available:
        pytest.skip("lifx-emulator not available")

    emulator_path = find_lifx_emulator()
    if not emulator_path:
        pytest.skip("Failed to find lifx-emulator")

    port = get_free_port()

    class EmulatorServer(ProcessStarter):
        """Process starter for use with pytest-xprocess."""

        pattern = "Starting LIFX Emulator"
        args: ClassVar[list[str]] = [
            str(emulator_path),
            "--bind",
            "127.0.0.1",  # bind emulator to localhost
            "--port",
            str(port),
            "--api",  # Enable HTTP API on port 8080
            "--color",
            "1",  # 1 color light
            "--multizone",
            "2",  # 2 multizone devices
            "--tile",
            "1",  # 1 tile device
            "--tile-count",
            "1",  # 1 tile on the chain
            "--hev",
            "1",  # 1 HEV light
            "--infrared",
            "1",  # 1 infrared light
            "--color-temperature",
            "1",  # 1 color temperature light
        ]

        # # Terminate the process on interrupt
        # terminate_on_interrupt = True

    # Use xprocess to manage the emulator subprocess
    _ = xprocess.ensure("lifx_emulator", EmulatorServer)

    yield port

    xprocess.getinfo("lifx_emulator").terminate()


@pytest.fixture(scope="session")
def emulator_devices(emulator_server: int) -> DeviceGroup:
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
    devices: list[Device] = []

    devices.extend(
        [
            Light(
                serial="d073d5000001",
                ip="127.0.0.1",
                port=emulator_server,
            ),
            Light(
                serial="d073d5000002",
                ip="127.0.0.1",
                port=emulator_server,
            ),
            InfraredLight(
                serial="d073d5000003",
                ip="127.0.0.1",
                port=emulator_server,
            ),
            HevLight(
                serial="d073d5000004",
                ip="127.0.0.1",
                port=emulator_server,
            ),
            MultiZoneLight(
                serial="d073d5000005",
                ip="127.0.0.1",
                port=emulator_server,
            ),
            MultiZoneLight(
                serial="d073d5000006",
                ip="127.0.0.1",
                port=emulator_server,
            ),
            MatrixLight(
                serial="d073d5000007",
                ip="127.0.0.1",
                port=emulator_server,
            ),
        ]
    )
    return DeviceGroup(devices)


@pytest.fixture(autouse=True)
async def cleanup_device_connections(emulator_devices):
    """Clean up device connections after each test.

    This ensures test isolation by closing all device connections
    after each test completes. Since each test has its own event loop,
    connections must be closed so they can reopen with the new loop.
    """
    yield
    # Close all device connections after test completes
    for device in emulator_devices:
        await device.connection.close()


@pytest.fixture(scope="session")
def emulator_api_url() -> str:
    """Return the base URL for the emulator's HTTP API.

    The API is enabled with the --api flag and runs on port 8080.

    Returns:
        Base URL like "http://127.0.0.1:8080/api"
    """
    return "http://127.0.0.1:8080/api"


@pytest.fixture(scope="session")
def ceiling_device(emulator_server: int, emulator_api_url: str):
    """Create a LIFX Ceiling device (product 201) for SKY effect testing.

    The Ceiling device supports SKY effects and has >128 zones (16x8 tile).
    This fixture uses the emulator's HTTP API to create the device.

    Returns:
        MatrixLight instance for the Ceiling device
    """

    # Wait for API to be ready (emulator might not have HTTP API ready immediately)
    max_retries = 10
    for i in range(max_retries):
        try:
            response = requests.get(f"{emulator_api_url}/docs", timeout=1.0)
            if response.status_code == 200:
                break
        except requests.exceptions.ConnectionError:
            if i < max_retries - 1:
                time.sleep(0.5)
            else:
                raise

    # Create Ceiling device via API (product 201 = LIFX Ceiling with >128 zones)
    response = requests.post(
        f"{emulator_api_url}/devices",
        json={
            "product_id": 201,  # LIFX Ceiling (16x8 = 128 zones)
            # Use serial that doesn't conflict with existing devices
            "serial": "d073d5000100",
        },
        timeout=5.0,
    )
    response.raise_for_status()  # 201 Created is expected

    try:
        ceiling = MatrixLight(
            serial="d073d5000100",
            ip="127.0.0.1",
            port=emulator_server,
        )
        yield ceiling
    finally:
        # Clean up: delete the device
        try:
            requests.delete(
                f"{emulator_api_url}/devices/d073d5000100",
                timeout=5.0,
            )
        except Exception:
            pass  # Best effort cleanup


@pytest.fixture
def scenario_manager(emulator_api_url: str):
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

    active_scenarios = []

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
        url = f"{emulator_api_url}/scenarios/{scope}"
        if identifier:
            url = f"{url}/{identifier}"

        # Wait for API to be ready (emulator might not have HTTP API ready immediately)
        max_retries = 10
        for i in range(max_retries):
            try:
                response = requests.get(f"{emulator_api_url}/docs", timeout=1.0)
                if response.status_code == 200:
                    break
            except requests.exceptions.ConnectionError:
                if i < max_retries - 1:
                    time.sleep(0.5)
                else:
                    raise

        # Add the scenario
        response = requests.put(url, json=config, timeout=5.0)
        response.raise_for_status()
        active_scenarios.append(url)

        try:
            yield
        finally:
            # Clean up this scenario
            try:
                requests.delete(url, timeout=5.0)
                active_scenarios.remove(url)
            except Exception:
                pass  # Best effort cleanup

    yield manage_scenario

    # Clean up any remaining scenarios
    for url in active_scenarios:
        try:
            requests.delete(url, timeout=5.0)
        except Exception:
            pass


@pytest.fixture
async def emulator_server_with_scenarios(emulator_server: int, emulator_api_url: str):
    """Create devices with specific scenario configurations.

    This fixture provides a callable that applies scenarios to devices
    and returns server/device info for testing.

    Usage:
        async def test_example(emulator_server_with_scenarios):
            server, device = await emulator_server_with_scenarios(
                device_type="color",
                serial="d073d5000001",
                scenarios={"drop_packets": {"20": 1.0}}
            )
            # Test code using server.port and device info
    """

    applied_scenarios = []

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
        # Wait for API to be ready (emulator might not have HTTP API ready immediately)
        max_retries = 10
        for i in range(max_retries):
            try:
                response = requests.get(f"{emulator_api_url}/docs", timeout=1.0)
                if response.status_code == 200:
                    break
            except requests.exceptions.ConnectionError:
                if i < max_retries - 1:
                    time.sleep(0.5)
                else:
                    raise

        # Apply scenario to the specified device
        url = f"{emulator_api_url}/scenarios/devices/{serial}"
        response = requests.put(url, json=scenarios, timeout=5.0)
        response.raise_for_status()
        applied_scenarios.append(url)

        # Create namespace objects for server and device info
        server_info = SimpleNamespace(port=emulator_server)
        device_info = SimpleNamespace(serial=serial, type=device_type)

        return server_info, device_info

    yield create_device_with_scenario

    # Clean up all scenarios after test
    for url in applied_scenarios:
        try:
            requests.delete(url, timeout=5.0)
        except Exception:
            pass  # Best effort cleanup
