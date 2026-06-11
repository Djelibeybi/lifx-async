# Testing Patterns

**Analysis Date:** 2026-06-11

## Test Framework

**Runner:**
- pytest 8.4.2+
- Config: `pyproject.toml` `[tool.pytest.ini_options]`

**Async Support:**
- pytest-asyncio 0.24.0+
- Mode: `asyncio_mode = "auto"` (automatically detects async fixtures)
- Scope: `asyncio_default_fixture_loop_scope = "function"` (fresh loop per test)

**Assertion Library:**
- Built-in pytest assertions
- pytest.approx() for floating-point comparisons

**Run Commands:**
```bash
# All tests
uv run pytest

# Watch mode (not configured)
# Use: uv run pytest --co (list tests) or manually re-run

# Coverage report
uv run pytest --cov=lifx --cov-report=html

# Specific test file
uv run pytest tests/test_devices/test_light.py -v

# Specific test
uv run pytest tests/test_color.py::TestHSBK::test_create_hsbk -v

# Exclude emulator tests (on Windows or without emulator)
uv run pytest -m "not emulator"

# Only emulator tests
uv run pytest -m emulator
```

## Test File Organization

**Location:**
- Tests mirror source structure: `tests/test_devices/test_light.py` tests `src/lifx/devices/light.py`

**Naming:**
- Test files: `test_*.py`
- Test classes: `Test*` (e.g., `TestLight`, `TestHSBK`)
- Test functions: `test_*` (e.g., `test_create_hsbk()`)

**Structure:**
```
tests/
├── test_protocol/          # Protocol header, serializer, packets, generator
├── test_network/           # Transport, discovery, connection, message, concurrent requests
│   └── test_mdns/          # mDNS DNS parser, transport, discovery
├── test_devices/           # Base, light, ceiling, hev, infrared, multizone, matrix
│   ├── conftest.py         # Device fixtures (mock_device_factory, mock_product_info)
│   └── test_state_*.py     # State management tests per device type
├── test_api/               # Discovery, batch operations, errors, organization, themes
├── test_effects/           # Individual effect tests + registry, integration
├── test_theme/             # Theme, canvas, generators, library
├── test_animation/         # Animator, framebuffer, packets, orientation
├── test_color.py           # Color utilities and RGB roundtrip
├── test_products/          # Product registry
├── test_utils.py           # General utilities
├── conftest.py             # Shared session-level fixtures (emulator, devices)
└── benchmarks/             # Performance benchmarks with pytest-benchmark
    └── test_*.py           # Benchmarks marked with @pytest.mark.benchmark
```

## Test Structure

**Suite Organization:**
```python
class TestLight:
    """Tests for Light class."""

    def test_create_light(self) -> None:
        """Test creating a light."""
        light = Light(...)
        assert light.serial == "..."

    async def test_get_color(self, light: Light) -> None:
        """Test getting light color."""
        await light.get_color()
        assert ...
```

**Patterns:**
- Class-based organization (one Test* class per unit under test)
- Descriptive test names that explain what is tested
- One assertion focus per test (or related group with comments)
- Async tests: `async def test_*` methods (no need for `@pytest.mark.asyncio`)

**Setup/Teardown:**
- Fixtures for setup (avoid setUp/tearDown methods)
- Autouse fixtures for test isolation (e.g., `cleanup_device_connections`)
- Session-level fixtures: `scope="session"` (emulator runs once)
- Function-level fixtures: `scope="function"` (default, fresh per test)

Example:
```python
@pytest.fixture(scope="session")
def emulator_port(emulator_server):
    """Return emulator port for all tests."""
    return emulator_server[0]

@pytest.fixture(autouse=True)
async def cleanup_device_connections(request, emulator_available):
    """Clean up connections after each test."""
    yield
    if emulator_available and "emulator_devices" in request.fixturenames:
        emulator_devices = request.getfixturevalue("emulator_devices")
        for device in emulator_devices:
            await device.connection.close()
```

## Mocking

**Framework:** `unittest.mock` (built-in)

**Patterns:**
```python
from unittest.mock import AsyncMock, MagicMock

# Mock async function
mock_conn = MagicMock()
mock_conn.request = AsyncMock()
device.connection = mock_conn

# Use mock
mock_conn.request.return_value = packets.Light.StateColor(...)
await device.get_color()

# Verify calls
mock_conn.request.assert_called_once()
call_args = mock_conn.request.call_args
packet = call_args[0][0]  # First positional arg
```

**What to Mock:**
- Network connections (`DeviceConnection`)
- External dependencies (emulator when not testing real protocol)
- Side effects (file I/O, timing)
- Device responses (fixtures return mock packet data)

**What NOT to Mock:**
- Protocol serialization (test real serialization behavior)
- Core business logic (test actual implementations)
- Exceptions (raise real exceptions, not mocks)
- Time-sensitive operations (use mock clocks or fixtures)

**Fixture Factories:**
```python
@pytest.fixture
def mock_device_factory():
    """Factory for creating devices with mocked connections."""
    def _create_device(device_class, serial="d073d5010203", ip="192.168.1.100"):
        device = device_class(serial=serial, ip=ip, port=56700)
        mock_conn = MagicMock()
        mock_conn.request = AsyncMock()
        device.connection = mock_conn
        return device
    return _create_device

# Usage
def test_something(mock_device_factory):
    light = mock_device_factory(Light)
    # light has mocked connection ready
```

## Fixtures and Factories

**Test Data:**

Device fixture factory pattern (`tests/test_devices/conftest.py`):
```python
@pytest.fixture
def light(mock_device_factory) -> Light:
    """Create a test light with mocked connection."""
    return mock_device_factory(Light)

@pytest.fixture
def mock_product_info():
    """Factory for creating mock ProductInfo objects."""
    def _create_product_info(
        pid: int = 32,
        has_color: bool = True,
        has_multizone: bool = True,
    ) -> ProductInfo:
        capabilities = 0
        if has_color:
            capabilities |= ProductCapability.COLOR
        # ... build capabilities
        return ProductInfo(pid=pid, capabilities=capabilities, ...)
    return _create_product_info

# Usage
def test_something(mock_product_info):
    info = mock_product_info(has_multizone=True)
```

Emulator device fixtures (`tests/conftest.py`):
```python
@pytest.fixture(scope="session")
def emulator_devices(emulator_server) -> DeviceGroup:
    """Return a DeviceGroup with 7 hardcoded emulated devices."""
    port, _, _ = emulator_server
    devices = [
        Light(serial="d073d5000001", ip="127.0.0.1", port=port, ...),
        # ... 6 more devices
    ]
    return DeviceGroup(devices)

# Usage
async def test_batch_operation(emulator_devices):
    await emulator_devices.set_power(True)
```

**Location:**
- Shared fixtures: `tests/conftest.py` (session-level, emulator)
- Device fixtures: `tests/test_devices/conftest.py` (mock factories)
- Module-specific: In test file itself (if used by one module only)

## Coverage

**Requirements:** No minimum enforced; high coverage encouraged

**Measurement:**
- Tool: pytest-cov
- Branch coverage enabled: `--cov-branch`
- Report: XML (for CI), terminal with missing line numbers

**View Coverage:**
```bash
# Generate HTML report
uv run pytest --cov=lifx --cov-report=html

# View in browser
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

**Omitted from Coverage:**
- `src/lifx/protocol/generator.py` (generates code, not executed)
- `src/lifx/protocol/protocol_types.py` (auto-generated)
- `src/lifx/products/generator.py` (generates registry)

**Exclude Lines:**
- `pragma: no cover` (skip this line)
- `@overload` (type hint only)
- `if TYPE_CHECKING:` (type hints only)
- `raise NotImplementedError` (abstract methods)
- `if __name__ == "__main__":` (CLI only)

## Test Types

**Unit Tests:**
- Scope: Individual functions/methods
- Mocking: Mock external dependencies
- Examples: `test_color.py` (color conversion), `test_protocol/` (serialization)
- Location: Majority of tests

**Integration Tests:**
- Scope: Multiple layers together
- Mocking: Mock network only
- Examples: Device + Connection, Device + Protocol
- Pattern: Use fixture devices

**E2E/Emulator Tests:**
- Framework: lifx-emulator-core (embedded in-process)
- Marker: `@pytest.mark.emulator`
- Scope: Full request/response cycle against emulator
- Fixtures: `emulator_port`, `emulator_devices`, `scenario_manager`
- Timeout: 120s (longer than normal 30s due to I/O variability)
- Skip conditions: Windows (UDP timing sensitive), external emulator mode

Example:
```python
@pytest.mark.emulator
async def test_get_color(emulator_devices):
    """Test getting color from emulated device."""
    light = emulator_devices[0]
    color, power, label = await light.get_color()
    assert isinstance(color, HSBK)
    assert power == 65535 or power == 0
```

## Common Patterns

**Async Testing:**

Simple async test:
```python
async def test_connection_opens(self) -> None:
    """Test connection opens lazily on first request."""
    conn = DeviceConnection(serial="d073d5001234", ip="192.168.1.100")
    assert not conn.is_open
    await conn._ensure_open()
    assert conn.is_open
    await conn.close()
```

With asyncio.gather for concurrent tests:
```python
async def test_concurrent_requests(self) -> None:
    """Test concurrent requests execute in parallel."""
    await asyncio.gather(
        mock_request(1),
        mock_request(2),
        mock_request(3),
    )
    # Verify all completed
```

**Error Testing:**

```python
async def test_set_brightness_invalid(self, light: Light) -> None:
    """Test setting invalid brightness raises ValueError."""
    with pytest.raises(ValueError, match="Brightness must be between"):
        await light.set_brightness(1.5)
```

With context manager setup:
```python
async def test_send_without_open(self) -> None:
    """Test sending without opening raises ConnectionError."""
    conn = DeviceConnection(serial="...", ip="...")
    packet = Device.GetLabel()
    with pytest.raises(ConnectionError):
        await conn.send_packet(packet, source=12345, sequence=0)
```

**Mocking Responses:**

```python
async def test_get_color(self, light: Light) -> None:
    """Test getting light color."""
    # Setup mock response
    mock_state = packets.Light.StateColor(
        color=HSBK(hue=180, saturation=0.5, brightness=0.75, kelvin=3500).to_protocol(),
        power=65535,
        label="Test Light",
    )
    light.connection.request.return_value = mock_state

    # Call method
    color, power, label = await light.get_color()

    # Verify results
    assert isinstance(color, HSBK)
    assert color.hue == pytest.approx(180, abs=1)
    assert power == 65535
    assert label == "Test Light"
```

**Timing Tests:**

```python
async def test_concurrent_timing(self) -> None:
    """Test concurrent requests complete faster than sequential."""
    start_time = time.monotonic()
    await asyncio.gather(
        mock_request(conn1, "conn1"),
        mock_request(conn2, "conn2"),
    )
    total_time = time.monotonic() - start_time

    # If serial, would take ~0.2s (two 0.1s sleeps)
    # If concurrent, should take ~0.1s (one sleep duration)
    # Tolerance for CI variability
    assert total_time < 0.19
```

## Scenario Management

**Emulator Scenarios:**

Use scenario_manager fixture to inject test conditions:

```python
async def test_packet_drop_retry(scenario_manager):
    """Test retry on dropped packets."""
    with scenario_manager("devices", "d073d5000001", {"drop_packets": {20: 0.5}}):
        # 50% drop rate for packet type 20
        light = Light(serial="d073d5000001", ip="127.0.0.1", port=port)
        # Test should retry and succeed despite drops
        color, power, label = await light.get_color()
        assert color is not None
```

Scenario types:
- `"global"`: Affects all devices
- `"devices"`: Specific device by serial
- `"types"`: All devices of a type
- `"locations"`: All devices in location
- `"groups"`: All devices in group

Configuration:
```python
{
    "drop_packets": {pkt_type: rate},      # 0.0-1.0 drop probability
    "response_delays": {pkt_type: seconds}, # Add latency
    "malformed_packets": [pkt_types],       # Corrupt responses
}
```

## Test Markers

**Defined Markers:**
- `@pytest.mark.emulator` - Requires lifx-emulator-core
- `@pytest.mark.benchmark` - Performance benchmark

**Usage:**
```python
@pytest.mark.emulator
async def test_real_protocol(emulator_devices):
    """Test against emulated device."""
    ...

@pytest.mark.benchmark
def test_color_conversion_perf(benchmark):
    """Benchmark RGB conversion speed."""
    result = benchmark(HSBK.from_rgb, 1.0, 0.5, 0.2)
```

**Running:**
```bash
# Exclude emulator tests (CI without emulator)
uv run pytest -m "not emulator"

# Only emulator tests
uv run pytest -m emulator

# Skip benchmarks (default)
uv run pytest -m "not benchmark"

# Only benchmarks
uv run pytest -m benchmark
```

## Test Isolation and Cleanup

**Autouse Fixtures:**

```python
@pytest.fixture(autouse=True)
async def cleanup_device_connections(request, emulator_available):
    """Clean up device connections after each test.

    Automatically runs after every test function.
    Yields first (test runs), then cleanup happens.
    """
    yield  # Test runs here

    # Cleanup happens here
    if emulator_available and "emulator_devices" in request.fixturenames:
        emulator_devices = request.getfixturevalue("emulator_devices")
        for device in emulator_devices:
            await device.connection.close()
```

**Scenario Cleanup:**

```python
@pytest.fixture
def scenario_manager(emulator_server):
    """Context manager that auto-cleans scenarios."""
    _, server, sm = emulator_server

    active_scenarios = []

    @contextmanager
    def manage_scenario(scope, identifier, config):
        # Setup
        sm.set_device_scenario(identifier, ScenarioConfig(**config))
        active_scenarios.append((scope, identifier))
        server.invalidate_all_scenario_caches()

        try:
            yield  # Test runs
        finally:
            # Cleanup
            sm.delete_device_scenario(identifier)
            active_scenarios.remove((scope, identifier))
            server.invalidate_all_scenario_caches()

    yield manage_scenario

    # Final cleanup for any remaining scenarios
    for scope, identifier in active_scenarios:
        sm.delete_device_scenario(identifier)
```

## Timeout Configuration

**Defaults:**
- Normal tests: 30 seconds (`timeout = 30`)
- Emulator tests: 120 seconds (auto-applied to tests using emulator fixtures)
- Method: thread-based timeout

**Per-test override:**
```python
@pytest.mark.timeout(60)
async def test_slow_operation(self):
    """This test gets 60 seconds instead of default."""
    ...
```

## CI Integration

**Command:**
```bash
uv run pytest
```

**Output:**
- Verbose: `-v` flag
- JUnit XML: junit.xml (for GitHub Actions)
- Coverage XML: coverage.xml (for codecov)
- Terminal: Formatted output with sugar plugin

**Retry on Transient Failures:**
- pytest-retry: Auto-retries on `LifxTimeoutError` and `LifxConnectionError`
- Configured in `conftest.py`: `pytest_set_filtered_exceptions()`
- Useful for network-sensitive tests

---

*Testing analysis: 2026-06-11*
