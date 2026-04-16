# Testing Patterns

**Analysis Date:** 2026-04-16

## Test Framework

**Runner:**
- pytest >= 8.4.2
- Config: `[tool.pytest.ini_options]` in `pyproject.toml`

**Key plugins:**
- `pytest-asyncio` >= 0.24.0 — async test support with `asyncio_mode = "auto"`
- `pytest-cov` >= 7.0.0 — coverage reporting
- `pytest-benchmark` >= 5.2.3 — performance benchmarks
- `pytest-retry` >= 1.7.0 — retries for flaky network tests (`LifxTimeoutError`, `LifxConnectionError`)
- `pytest-sugar` >= 1.1.1 — improved output formatting
- `pytest-timeout` >= 2.4.0 — 30s default timeout per test

**Assertion Library:**
- Built-in `assert` statements
- `pytest.approx()` for floating-point comparisons with tolerances
- `pytest.raises()` with `match=` for exception message validation

**Run Commands:**
```bash
uv run --frozen pytest              # Run all tests (excludes benchmarks by default)
uv run pytest -v                    # Verbose output
uv run pytest --cov=lifx --cov-report=html  # With HTML coverage report
uv run pytest tests/test_devices/test_light.py -v  # Specific file
uv run pytest -m benchmark          # Run benchmarks only
uv run pytest -m emulator           # Run only emulator integration tests
```

## Test File Organisation

**Location:** Separate `tests/` directory mirroring `src/lifx/` structure

**Naming:**
- Test files: `test_{module}.py`
- State management tests: `test_state_{device}.py`
- Test classes: `Test{Feature}` (e.g., `TestLight`, `TestDeviceConnection`)
- Test functions: `test_{behaviour}` (e.g., `test_create_light`, `test_get_color`)

**Structure:**
```
tests/
├── conftest.py                     # Root fixtures: emulator, cleanup, scenarios
├── test_color.py                   # Color utilities
├── test_utils.py                   # General utilities
├── test_protocol/                  # Protocol layer tests
│   ├── test_serializer.py
│   ├── test_header.py
│   └── test_packets.py
├── test_network/                   # Network layer tests
│   ├── test_connection.py
│   ├── test_transport.py
│   ├── test_discovery_devices.py
│   ├── test_discovery_errors.py
│   ├── test_concurrent_requests.py
│   ├── test_message.py
│   ├── test_message_advanced.py
│   └── test_mdns/                  # mDNS sub-module tests
│       └── conftest.py
├── test_devices/                   # Device layer tests
│   ├── conftest.py                 # Device-specific fixtures
│   ├── test_base.py
│   ├── test_light.py
│   ├── test_ceiling.py
│   ├── test_hev.py
│   ├── test_infrared.py
│   ├── test_matrix.py
│   ├── test_multizone.py
│   ├── test_mac_address.py
│   ├── test_state_light.py         # State management per device type
│   ├── test_state_ceiling.py
│   ├── test_state_hev.py
│   ├── test_state_infrared.py
│   ├── test_state_management.py
│   ├── test_state_matrix.py
│   └── test_state_multizone.py
├── test_api/                       # High-level API tests
│   ├── test_api_discovery.py
│   ├── test_api_batch_operations.py
│   ├── test_api_batch_errors.py
│   ├── test_api_organization.py
│   └── test_api_apply_theme.py
├── test_effects/                   # Effects (30+ individual effect test files)
│   ├── test_aurora.py
│   ├── test_flame.py
│   ├── test_rainbow.py
│   ├── test_registry.py
│   ├── test_integration.py
│   ├── test_capability_filtering.py
│   ├── test_state_manager.py
│   ├── test_conductor.py
│   └── ... (30+ effect test files)
├── test_theme/                     # Theme tests
├── test_animation/                 # Animation layer tests
│   ├── conftest.py                 # Mock tile/device fixtures
│   ├── test_animator.py
│   ├── test_framebuffer.py
│   ├── test_orientation.py
│   └── test_packets.py
├── test_products/                  # Product registry tests
└── benchmarks/                     # Performance benchmarks
    ├── conftest.py
    ├── test_packets_perf.py
    ├── test_framebuffer_perf.py
    └── test_effect_frame_perf.py
```

## Test Structure

**Suite Organisation:**
```python
"""Tests for light device class."""

from __future__ import annotations

import pytest

from lifx.color import HSBK
from lifx.devices.light import Light


class TestLight:
    """Tests for Light class."""

    def test_create_light(self) -> None:
        """Test creating a light."""
        light = Light(serial="d073d5010203", ip="192.168.1.100", port=56700)
        assert light.serial == "d073d5010203"

    async def test_get_color(self, light: Light) -> None:
        """Test getting light color."""
        mock_state = packets.Light.StateColor(...)
        light.connection.request.return_value = mock_state

        color, power, label = await light.get_color()
        assert isinstance(color, HSBK)
        assert color.hue == pytest.approx(180, abs=1)
```

**Key patterns:**
- Group related tests in `Test{Feature}` classes (e.g., `TestAuroraInheritance`, `TestAuroraGenerateFrame`)
- All test methods include `-> None` return type annotation
- Async tests: just use `async def` — `asyncio_mode = "auto"` handles the rest (no `@pytest.mark.asyncio` needed for most tests)
- Each test has a descriptive docstring explaining what it validates
- Tests follow Arrange-Act-Assert pattern

**Setup/Teardown:**
- Fixtures handle setup; `yield`-based fixtures handle teardown
- `autouse=True` fixture in root `conftest.py` cleans up device connections after each test
- Session-scoped emulator fixture starts once, shared across all tests

## Mocking

**Framework:** `unittest.mock` (stdlib)

**Primary pattern — Mock device factory** (`tests/test_devices/conftest.py`):
```python
@pytest.fixture
def mock_device_factory():
    """Factory for creating devices with mocked connections."""
    def _create_device(
        device_class: type[Device],
        serial: str = "d073d5010203",
        ip: str = "192.168.1.100",
        port: int = 56700,
    ) -> Device:
        device = device_class(serial=serial, ip=ip, port=port)
        mock_conn = MagicMock()
        mock_conn.request = AsyncMock()
        mock_conn.request_ack = AsyncMock()
        device.connection = mock_conn
        return device
    return _create_device
```

**Derived fixtures for each device type:**
```python
@pytest.fixture
def light(mock_device_factory) -> Light:
    """Create a test light with mocked connection."""
    return mock_device_factory(Light)

@pytest.fixture
def multizone_light(mock_device_factory) -> MultiZoneLight:
    return mock_device_factory(MultiZoneLight)
```

**Mocking protocol responses:**
```python
async def test_get_color(self, light: Light) -> None:
    mock_state = packets.Light.StateColor(
        color=HSBK(hue=180, saturation=0.5, brightness=0.75, kelvin=3500).to_protocol(),
        power=65535,
        label="Test Light",
    )
    light.connection.request.return_value = mock_state
    color, power, label = await light.get_color()
```

**Side-effect mocking for multi-packet conversations:**
```python
async def mock_request(packet):
    if isinstance(packet, packets.Light.GetColor):
        return mock_color
    elif isinstance(packet, packets.Device.GetHostFirmware):
        return packets.Device.StateHostFirmware(build=0, version_major=2, version_minor=80)
    elif isinstance(packet, packets.Device.GetLocation):
        return packets.Device.StateLocation(location=b"\x00" * 16, label="Home", ...)

light.connection.request.side_effect = mock_request
```

**What to mock:**
- Device connections (`MagicMock` with `AsyncMock` for `request`/`request_ack`)
- Network transport for unit tests
- Product info capabilities (`mock_product_info` fixture)
- Firmware info (`mock_firmware_info` fixture)
- Tile info for animation tests (`MockTileInfo` dataclass in `tests/test_animation/conftest.py`)

**What NOT to mock:**
- Protocol serialisation/deserialisation (test real binary encoding)
- HSBK colour conversion (test real maths)
- Product registry lookups (test real data)
- Emulator integration tests (test against real protocol implementation)

## Fixtures and Factories

**Root fixtures** (`tests/conftest.py`):
```python
# Session-scoped emulator management
@pytest.fixture(scope="session")
def emulator_server(emulator_available):
    """Start embedded lifx-emulator for entire session."""
    # Returns (port, server, scenario_manager)

@pytest.fixture(scope="session")
def emulator_port(emulator_server) -> int:
    """Return just the emulator port."""

@pytest.fixture(scope="session")
def emulator_devices(emulator_server) -> DeviceGroup:
    """Return DeviceGroup with 7 hardcoded emulated devices."""

@pytest.fixture(scope="session")
def ceiling_device(emulator_server):
    """Dynamically add ceiling device to running emulator."""

@pytest.fixture
def scenario_manager(emulator_server):
    """Context manager for scenario-based testing."""
```

**Device fixtures** (`tests/test_devices/conftest.py`):
- `mock_device_factory` — factory callable for any device type
- `device`, `light`, `multizone_light`, `matrix_light`, `hev_light`, `infrared_light` — pre-built mocked devices
- `mock_product_info` — factory for `ProductInfo` with configurable capabilities
- `mock_firmware_info` — factory for `FirmwareInfo` with configurable versions

**Animation fixtures** (`tests/test_animation/conftest.py`):
- `MockTileInfo` dataclass — lightweight tile mock without device dependency
- `mock_tile_upright`, `mock_tile_rotated_90`, etc. — orientation-specific tile fixtures
- `mock_tile_chain` — multi-tile chain fixture
- `mock_multizone_device`, `mock_matrix_device` — device mocks for animation

**Test data location:**
- No external fixture files — all test data inline or in conftest fixtures
- Protocol test data uses raw bytes literals for binary testing
- Serial numbers follow pattern `d073d5XXXXXX` matching LIFX vendor prefix

## Coverage

**Requirements:**
- Branch coverage enabled (`--cov-branch`)
- Coverage reported on `lifx` package only
- XML and terminal reports generated by default
- Coverage context per test (`--cov-context=test`)

**Exclusions** (`[tool.coverage.run]` and `[tool.coverage.report]`):
- Omitted: `src/lifx/protocol/generator.py`, `src/lifx/protocol/protocol_types.py`, `src/lifx/products/generator.py`
- Excluded lines: `pragma: no cover`, `@overload`, `if TYPE_CHECKING`, `raise NotImplementedError`, `if __name__ == "__main__":`

**View Coverage:**
```bash
uv run pytest --cov=lifx --cov-report=html    # HTML report in htmlcov/
uv run pytest --cov=lifx --cov-report=term     # Terminal summary
```

## Test Types

**Unit Tests (majority):**
- Test individual classes and methods in isolation
- Mock device connections, replace `request()` with `AsyncMock`
- Validate packet construction, response parsing, state updates
- Located throughout `tests/test_*` directories
- ~2400+ tests

**Integration Tests (emulator-based):**
- Marked with `@pytest.mark.emulator`
- Run against `lifx-emulator-core` embedded in-process
- Test real UDP protocol communication
- Session-scoped emulator with 7 default devices + dynamic device creation
- Scenario-based testing for error conditions (packet drops, delays, malformed responses)
- Located in `tests/test_api/test_api_discovery.py`, `tests/test_api/test_api_batch_operations.py`, `tests/test_animation/test_animator.py`
- Auto-skipped if emulator unavailable or on Windows (timing-sensitive)
- Extended timeout: 120s (vs 30s default)

**Benchmark Tests:**
- Marked with `@pytest.mark.benchmark`
- Excluded from default test runs (`-m "not benchmark"`)
- Use `pytest-benchmark` for statistical analysis
- Located in `tests/benchmarks/`
- Test animation packet generation, framebuffer operations, effect frame generation
- Support baseline saving and comparison:
```bash
uv run pytest tests/benchmarks/ -m benchmark --benchmark-save=phase1
uv run pytest tests/benchmarks/ -m benchmark --benchmark-compare=phase1
```

**E2E Tests:**
- Not a separate category — emulator integration tests serve this purpose
- External emulator mode supports testing against real hardware:
```bash
LIFX_EMULATOR_EXTERNAL=1 pytest  # Test against real LIFX hardware
```

## Common Patterns

**Async Testing:**
```python
# asyncio_mode = "auto" means no decorator needed in most cases
async def test_get_color(self, light: Light) -> None:
    """Test getting light color."""
    light.connection.request.return_value = mock_state
    color, power, label = await light.get_color()
    assert isinstance(color, HSBK)

# Explicit marker only needed when not using fixtures that imply async
@pytest.mark.asyncio
async def test_for_matrix_fetches_device_chain(self) -> None:
    animator = await Animator.for_matrix(device)
    assert animator.pixel_count == 64
```

**Error Testing:**
```python
def test_aurora_invalid_speed(self) -> None:
    """Test EffectAurora with invalid speed raises ValueError."""
    with pytest.raises(ValueError, match="Speed must be positive"):
        EffectAurora(speed=0)

async def test_send_without_open(self) -> None:
    """Test sending without opening raises error."""
    conn = DeviceConnection(serial="d073d5001234", ip="192.168.1.100")
    with pytest.raises(ConnectionError):
        await conn.send_packet(packet, source=12345, sequence=0)
```

**Parametrised Tests:**
```python
@pytest.mark.parametrize("pixel_count", [1, 8, 16, 82])
def test_multi_pixel_returns_correct_count(self, pixel_count: int) -> None:
    """Test correct number of colors for various pixel counts."""
    effect = EffectAurora()
    ctx = FrameContext(elapsed_s=1.0, device_index=0, pixel_count=pixel_count, ...)
    colors = effect.generate_frame(ctx)
    assert len(colors) == pixel_count
```

**Floating-point Comparison:**
```python
assert color.hue == pytest.approx(180, abs=1)
assert color.saturation == pytest.approx(0.5, abs=0.01)
```

**Scenario-based Integration Testing:**
```python
@pytest.mark.emulator
async def test_with_packet_drops(self, scenario_manager, emulator_devices):
    """Test behaviour when device drops packets."""
    with scenario_manager("devices", "d073d5000001", {"drop_packets": {20: 1.0}}):
        # Test code with scenario active
        pass
    # Scenario automatically cleaned up
```

**Connection Cleanup (autouse fixture):**
```python
@pytest.fixture(autouse=True)
async def cleanup_device_connections(request, emulator_available):
    """Close all device connections after each test for isolation."""
    yield
    if "emulator_devices" in request.fixturenames:
        for device in request.getfixturevalue("emulator_devices"):
            await device.connection.close()
```

## Test Markers

| Marker | Purpose | Default behaviour |
|--------|---------|-------------------|
| `@pytest.mark.emulator` | Requires lifx-emulator-core | Skipped if unavailable or on Windows |
| `@pytest.mark.benchmark` | Performance benchmark | Excluded from default runs (`-m "not benchmark"`) |
| `@pytest.mark.asyncio` | Explicit async test marker | Rarely needed (auto mode handles most cases) |
| `@pytest.mark.timeout(N)` | Custom timeout | Emulator tests auto-set to 120s |
| `@pytest.mark.parametrize(...)` | Parametrised test data | Standard pytest behaviour |

## Retry Behaviour

Configured via `pytest-retry` in `tests/conftest.py`:
```python
def pytest_set_filtered_exceptions() -> list[type[Exception]]:
    """Only retry on transient network exceptions."""
    return [LifxTimeoutError, LifxConnectionError]
```

---

*Testing analysis: 2026-04-16*
