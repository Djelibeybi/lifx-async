"""Shared fixtures for all tests."""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import time
from pathlib import Path
from typing import Any

import pytest

# Import DeviceConnection for cleanup
from lifx.network.connection import DeviceConnection


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


class EmulatorServer:
    """Manages lifx-emulator subprocess for testing."""

    def __init__(self, port: int = 56700, verbose: bool = False):
        """Initialize emulator server manager.

        Args:
            port: UDP port for emulator to listen on
            verbose: Enable verbose logging from emulator
        """
        self.port = port
        self.verbose = verbose
        self.process: subprocess.Popen[bytes] | None = None
        self.emulator_path: Path | None = None

    def start(self) -> bool:
        """Start the emulator process.

        Returns:
            True if emulator started successfully, False otherwise
        """
        # Find emulator
        self.emulator_path = find_lifx_emulator()
        if not self.emulator_path:
            return False

        # Build command - bind to 127.0.0.1 for security
        # Enables API for runtime reconfiguration
        # Creates 7 devices to match test expectations:
        # - 1 color light
        # - 1 infrared light
        # - 1 HEV light
        # - 2 multizone lights
        # - 1 tile device
        # - 1 color temperature (white-only) light
        cmd = [
            str(self.emulator_path),
            "--bind",
            "127.0.0.1",  # bind emulator to localhost
            "--port",
            str(self.port),
            "--api",  # start the API
            "--api-host",
            "127.0.0.1",  # bind API to localhost
            "--color",
            "1",  # 1 color light
            "--multizone",
            "2",  # 2 multizone devices
            "--tile",
            "1",  # 1 tile device
            "--hev",
            "1",  # 1 HEV light
            "--infrared",
            "1",  # 1 infrared light
            "--color-temperature",
            "1",  # 1 color temperature (white-only) light
        ]

        if self.verbose:
            cmd.append("--verbose")

        # Start process
        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE if not self.verbose else None,
            stderr=subprocess.PIPE if not self.verbose else None,
            stdin=subprocess.DEVNULL,
        )

        # Wait for emulator to be ready (check if port is bound)
        self._wait_for_ready(timeout=5.0)
        return True

    def _wait_for_ready(self, timeout: float = 5.0) -> None:
        """Wait for emulator to be ready to accept connections.

        Args:
            timeout: Maximum time to wait in seconds
        """
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.process and self.process.poll() is not None:
                # Process terminated
                code = self.process.returncode
                raise RuntimeError(f"Emulator process terminated (exit code: {code})")

            # Try to connect to check if server is ready
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.settimeout(0.1)
                sock.sendto(b"", ("127.0.0.1", self.port))
                sock.close()
                # If we can send, assume emulator is ready
                time.sleep(1.0)  # Give it more time to fully initialize all devices
                return
            except (ConnectionRefusedError, OSError):
                time.sleep(0.1)

        raise TimeoutError(f"Emulator did not become ready within {timeout}s")

    def stop(self) -> None:
        """Stop the emulator process."""
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
            self.process = None

    def is_running(self) -> bool:
        """Check if emulator process is running."""
        return self.process is not None and self.process.poll() is None


@pytest.fixture(scope="session")
def emulator_available() -> bool:
    """Check if lifx-emulator is available."""
    return find_lifx_emulator() is not None


@pytest.fixture(scope="session")
def emulator_server(emulator_available: bool) -> Any:
    """Start lifx-emulator as a subprocess for the entire test session.

    The emulator starts once at the beginning and stops when all tests complete.
    This significantly reduces test overhead compared to per-test startup.

    Only starts if lifx-emulator is available. Tests that require the emulator
    should check emulator_available or will be skipped automatically.

    External emulator mode:
        Set LIFX_EMULATOR_EXTERNAL=1 to skip starting the emulator subprocess.
        Use LIFX_EMULATOR_PORT to specify the port (default: 56700).
        This is useful for testing against actual hardware or a manually managed
        emulator instance with custom configuration.

    Yields:
        EmulatorServer instance with .port attribute
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
        emulator = EmulatorServer(port=port, verbose=False)
        # Don't start the subprocess, just provide the port
        yield emulator
        # No cleanup needed for external emulator
        return

    # Standard mode: start emulator subprocess
    if not emulator_available:
        pytest.skip(
            "lifx-emulator not available - install from ../lifx-emulator or system PATH"
        )

    port = get_free_port()
    emulator = EmulatorServer(port=port, verbose=False)

    started = emulator.start()
    if not started:
        pytest.skip("Failed to start lifx-emulator")

    yield emulator

    emulator.stop()


@pytest.fixture(autouse=True)
def allow_localhost_for_tests(monkeypatch):
    """Allow localhost IPs for testing with emulator.

    The Device class normally rejects localhost IPs, but for testing with
    the emulator running on 127.0.0.1, we need to bypass this validation.
    """
    import ipaddress

    from lifx.devices.base import Device

    original_init = Device.__init__

    def patched_init(self, *args, **kwargs):
        # Temporarily replace is_loopback check
        original_is_loopback = ipaddress.IPv4Address.is_loopback.fget

        def fake_is_loopback(addr_self):
            # Allow loopback addresses in tests
            return False

        # Monkeypatch the property
        monkeypatch.setattr(
            ipaddress.IPv4Address, "is_loopback", property(fake_is_loopback)
        )

        try:
            original_init(self, *args, **kwargs)
        finally:
            # Restore original
            monkeypatch.setattr(
                ipaddress.IPv4Address, "is_loopback", property(original_is_loopback)
            )

    monkeypatch.setattr(Device, "__init__", patched_init)


@pytest.fixture(autouse=True)
async def cleanup_connection_pool():
    """Clean up the connection pool after each test.

    This ensures test isolation by closing all pooled connections
    after each test completes. Without this, stale connections to
    old mock server ports persist across tests.
    """
    yield
    # Close all connections in the pool after test completes
    await DeviceConnection.close_all_connections()
