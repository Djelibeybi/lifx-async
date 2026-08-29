# Phase 12: IPv6 Discovery Plumbing - Pattern Map

**Mapped:** 2026-08-29
**Files analysed:** 6 modified files (no production file creation required)
**Analogues found:** 6 / 6 file assignments; one test helper is a composite pattern

## File Classification

| New/Modified File | Role | Data Flow | Closest Analogue | Match Quality |
|-------------------|------|-----------|------------------|---------------|
| `src/lifx/network/discovery.py` | service | streaming request-response | `src/lifx/network/connection.py` | exact family/bind analogue |
| `src/lifx/network/transport.py` | service | request-response | existing comments and lifecycle in the same file | exact, comment-only |
| `tests/test_api/test_ipv6_e2e.py` | test | real UDP request-response, event-driven lifecycle | `tests/test_api/test_ipv6_e2e.py` plus `tests/test_network/test_transport.py` | exact + composite |
| `tests/test_api/test_api_discovery.py` | test | public request-response and validation | existing `TestFindByIp` / `TestFindByIpAddressGate` in the same file | exact |
| `tests/conftest.py` | provider/test config | event-driven fixture lifecycle | existing IPv6 probe and emulator fixtures in the same file | exact |
| `.github/workflows/ci.yml` | config | batch | existing test matrix and IPv6 must-not-skip environment | exact |

The recommended placement uses the existing API test modules rather than creating a parallel emulator or a new production abstraction. If the planner prefers a dedicated `tests/test_network/test_discovery_ipv6.py`, copy the transport-boundary patterns assigned below; do not move the real public `find_by_ip()` proof out of `tests/test_api/test_ipv6_e2e.py`.

## Pattern Assignments

### `src/lifx/network/discovery.py` (service, streaming request-response)

**Analogue:** `src/lifx/network/connection.py`

**Imports pattern** (`src/lifx/network/connection.py`, lines 28-30):

```python
from lifx.network.address import wildcard_for
from lifx.network.message import create_message, parse_message
from lifx.network.transport import PeerInfo, UdpTransport
```

Follow the same top-of-file import convention. Phase 12 also needs stdlib `socket` and the shared `family_for()` helper; do not add a colon heuristic or a second `ipaddress` parser.

**Family-aware local bind pattern** (`src/lifx/network/connection.py`, lines 237-245):

```python
# Open transport, binding the wildcard that matches the device
# address family: IPv6 for Thread devices, IPv4 otherwise. The
# shared rule owns the choice, so this method makes no family
# test of its own.
local_ip = wildcard_for(self.ip)
self._transport = UdpTransport(
    ip_address=local_ip, port=0, broadcast=False, peer=self._peer
)
await self._transport.open()
```

**Phase 12 adaptation at the existing seam** (`src/lifx/network/discovery.py`, current lines 237-266):

```python
destination_family = family_for(broadcast_address)
async with UdpTransport(
    ip_address=wildcard_for(broadcast_address),
    port=0,
    broadcast=destination_family == socket.AF_INET,
) as transport:
    # Existing source allocation, message creation, logging, and send stay here.
    await transport.send(message, (broadcast_address, port))
```

This is the only production behaviour change required. Derive the wildcard and the IPv4-only broadcast flag together. `UdpTransport.open()` already derives the endpoint family from its local bind (`src/lifx/network/transport.py`, lines 302-349), while `send()` already rejects a destination-family mismatch before `sendto()` (`src/lifx/network/transport.py`, lines 420-484).

**Cleanup pattern** (`src/lifx/network/transport.py`, lines 254-261):

```python
async def __aenter__(self) -> UdpTransport:
    await self.open()
    return self

async def __aexit__(self, *args: object) -> None:
    await self.close()
```

Keep `_discover_with_packet()`'s `async with` ownership. Cancellation, errors, early generator closure, and ordinary completion must all continue to close the endpoint through this path.

**Invariant boundary:** leave `src/lifx/network/discovery.py` lines 268-520 structurally unchanged. Those lines own the overall/idle deadlines, escalating retransmission schedule, protocol-size handling, source and packet-type checks, serial validation, UDP-service filtering, first-wins deduplication, consumer-time exclusion, and cleanup completion log.

---

### `src/lifx/network/transport.py` (service, request-response)

**Analogue:** existing structured lifecycle comments and logging in the same file.

No functional transport change is planned. The caller supplies the correct bind and broadcast capability. One comment becomes false once discovery may bind `::`.

**Comment to update** (current lines 392-400):

```python
# The local bind values are deliberately left out: both callers bind
# 0.0.0.0 on an ephemeral port, so they are constants that name no
# device. The peer is what identifies whose socket just died.
_LOGGER.warning(
    self._log(
        method="_endpoint_lost",
        action="endpoint_lost",
        reason=str(exc) if exc is not None else "closed",
    )
)
```

Preserve the value-suppressed log record, but describe that callers bind a family-appropriate wildcard on an ephemeral port. Do not add the bind literal to logs merely to make the comment easier to write.

**Close-state pattern** (lines 546-577):

```python
async def close(self) -> None:
    self._state_generation += 1
    transport, self._transport = self._transport, None
    self._protocol = None
    self._family = None

    if transport is not None:
        transport.close()

@property
def is_open(self) -> bool:
    return (
        self._protocol is not None
        and self._transport is not None
        and self._family is not None
    )
```

Tests may retain the real underlying asyncio endpoint before close and assert `endpoint.is_closing()` (or an equivalent closed state), but production diagnostics should not be expanded.

---

### `tests/test_api/test_ipv6_e2e.py` (test, real UDP request-response and lifecycle)

**Analogues:** existing real IPv6 tests in this file and cancellation tests in `tests/test_network/test_transport.py`.

**Imports pattern** (lines 19-33):

```python
from __future__ import annotations

import asyncio
import socket

import pytest
from lifx_emulator import EmulatedLifxServer

from lifx.animation.animator import Animator
from lifx.devices.light import Light
from tests.conftest import IPV6_DEVICE_SERIAL, ipv6_probe_outcome
```

Keep all new imports at the top. Add `unittest.mock.patch`, public `find_by_ip`, `UdpTransport`, and the correctly typed device class required by the fixture; do not use local imports in new tests.

Update the module scope description at lines 3-7 when adding targeted discovery: it currently says the file covers exactly direct control and animation on one `Light`, which would become false.

**Actual socket observation pattern** (lines 46-63):

```python
udp_transport = light.connection._transport
assert udp_transport is not None, "the device connection has no transport"

endpoint = udp_transport._transport
assert endpoint is not None, "the transport has no asyncio endpoint"

sock = endpoint.get_extra_info("socket")
assert sock is not None, "the asyncio endpoint exposes no socket"

return sock.family
```

The discovery spy must likewise record the real endpoint after `await super().open()`. Assert both `sock.family == socket.AF_INET6` and `sock.getsockname()[0] == "::"`; constructor arguments or `_family` alone are not endpoint evidence.

**Real emulator path** (lines 163-187):

```python
port, server = emulator_server_ipv6

emulated = server.get_device(IPV6_DEVICE_SERIAL)
assert emulated is not None, "the ::1 emulator is not hosting its device"

animator = Animator(
    ip="::1",
    serial=Serial.from_string(IPV6_DEVICE_SERIAL),
    framebuffer=FrameBuffer(pixel_count=_PIXEL_COUNT),
    packet_generator=MatrixPacketGenerator(
        tile_count=1, tile_width=_TILE_WIDTH, tile_height=_TILE_HEIGHT
    ),
    port=port,
)
```

For the new proof, call `find_by_ip("::1", port=port, ...)`; do not directly construct a `Light`, stub `discover_devices()`, or synthesise a discovery response. Patch only `lifx.network.discovery.UdpTransport` with an observation-only subclass so discovery traffic remains real and the later device-connection transport is not counted as a discovery endpoint.

**Deterministic event/cancellation pattern** (`tests/test_network/test_transport.py`, lines 318-352):

```python
transport = UdpTransport()
entered = asyncio.Event()
blocked = asyncio.Event()

async def _blocked_endpoint(*args: Any, **kwargs: Any) -> None:
    entered.set()
    await blocked.wait()

opening = asyncio.create_task(transport.open())
await entered.wait()
opening.cancel()

with pytest.raises(asyncio.CancelledError):
    await opening

assert transport._protocol is None
assert transport._transport is None
assert transport._family is None
assert transport.is_open is False
```

Adapt this shape so the recording discovery transport exposes `opened`, `receive_blocked`, and `closed` events. Cancel only after the real endpoint is open and `receive()` is blocked. Await cancellation and close, assert the saved endpoint is closing/closed, then perform a fresh real `::1` lookup successfully. Do not use a fixed sleep or pre-start cancellation.

**Concurrent independence:** run two real public lookups as separate tasks, then assert the spy recorded two distinct discovery transport instances and two distinct underlying endpoints. Keep this test separate from cancellation recovery.

**Existing Windows retry policy** (`tests/test_network/test_discovery_errors.py`, lines 17-18):

```python
@pytest.mark.emulator
@pytest.mark.flaky(retries=2, delay=1, condition=sys.platform.startswith("win32"))
```

Apply the same retry marker to the focused real emulator-backed targeted-discovery test, with `sys` imported at the top. Do not add shell retries.

---

### `tests/test_api/test_api_discovery.py` (test, public validation and transport selection)

**Analogue:** existing `TestFindByIp` and `TestFindByIpAddressGate`.

**IPv4 regression pattern** (lines 175-203):

```python
@pytest.mark.emulator
class TestFindByIp:
    async def test_find_by_ip_found(self, emulator_port: int):
        device = await find_by_ip(
            "127.0.0.1",
            timeout=1.0,
            port=emulator_port,
            idle_timeout_multiplier=0.5,
        )

        assert device is not None
        assert device.serial.startswith("d073d5")
```

Keep this real IPv4 path green. Add a transport-boundary assertion that IPv4 uses `ip_address="0.0.0.0"`, `broadcast=True`, and sends to the supplied IPv4 literal.

**Public validation-first pattern** (`src/lifx/api.py`, lines 955-973):

```python
validate_address(ip)

async for discovered in discover_devices(
    timeout=timeout,
    broadcast_address=ip,
    port=port,
    max_response_time=max_response_time,
    idle_timeout_multiplier=idle_timeout_multiplier,
    device_timeout=device_timeout,
    max_retries=max_retries,
):
    return await discovered.create_device()

return None
```

Replace the weaker delegate assertion at current lines 520-528 with a fail-on-construction sentinel patched at `lifx.network.discovery.UdpTransport`. Parameterise `""`, a malformed literal, and bare `fe80::1`. The sentinel constructor must raise `AssertionError`; the expected public result is the validator's `ValueError`, proving transport construction was never reached.

**Patch-the-consumed-name pattern** (`tests/test_network/test_discovery_errors.py`, lines 156-165):

```python
with (
    patch("lifx.network.discovery.UdpTransport") as mock_transport_cls,
    patch("lifx.network.discovery.allocate_source", return_value=known_source),
):
    mock_transport = AsyncMock()
    mock_transport.__aenter__ = AsyncMock(return_value=mock_transport)
    mock_transport.__aexit__ = AsyncMock(return_value=False)
    mock_transport.send = AsyncMock()
    mock_transport.receive = mock_receive
    mock_transport_cls.return_value = mock_transport
```

Use this seam for non-routable representation tests. Record constructor kwargs and send destinations, then end with `LifxTimeoutError`; do not fake a device. Drive public `find_by_ip()` with compressed and expanded IPv6, ULA, documentation-range global-form, loopback, and zoned link-local strings. Assert each selects `ip_address="::"`, `broadcast=False`, and sends to the exact accepted representation.

Current `test_routable_ipv6_literal_falls_through` (lines 540-553) records the pre-Phase-12 gap and must be replaced or rewritten; retaining its `None` expectation without transport assertions would preserve obsolete evidence.

Use only loopback, ULA, documentation-range, and synthetic fixture identifiers. Do not introduce a live interface name obtained from the host; a literal such as `fe80::1%test0` is representation-only because delivery is instrumented.

---

### `tests/conftest.py` (provider/test config, event-driven fixture lifecycle)

**Analogue:** existing availability decisions and `emulator_server_ipv6` fixture.

**Preserve the blanket Windows policy** (lines 185-211):

```python
@pytest.fixture(scope="session")
def emulator_available(request: pytest.FixtureRequest) -> bool:
    disable_emulator = request.config.getoption("--disable-emulator", default=False)

    if disable_emulator:
        return False

    if sys.platform == "win32":
        return False

    try:
        from lifx_emulator import EmulatedLifxServer  # noqa: F401
        return True
    except ImportError:
        return False
```

Do not remove the normal Windows skip. Add a separate narrowly named session fixture for the IPv6 emulator that honours `--disable-emulator`, permits Windows only when the focused CI environment variable is exactly `"1"`, and otherwise follows the existing import check. Make `emulator_server_ipv6` depend on that dedicated decision rather than broadening `emulator_available` for the complete suite.

**Must-not-skip decision pattern** (lines 214-265):

```python
if require_ipv6 == "1":
    return (
        f"LIFX_REQUIRE_IPV6=1 set but ::1 cannot be bound: {error}. "
        "This is the designated must-not-skip IPv6 job, so the IPv6 "
        "end-to-end tests failing to run is a build failure, not a skip."
    )
return False
```

Keep the existing full-suite `LIFX_REQUIRE_IPV6` selection unchanged. Set `LIFX_REQUIRE_IPV6=1` in the focused Windows step as well, so a missing Windows loopback fails the required attempt instead of reporting a passing skip. The new Windows opt-in controls emulator eligibility; neither variable broadens the subsequent ordinary Windows suite.

**IPv6 fixture lifecycle** (lines 462-487):

```python
port = get_free_port6()
server = _Ipv6EmulatedLifxServer(
    devices=devices,
    device_manager=DeviceManager(DeviceRepository()),
    bind_address="::1",
    port=port,
    scenario_manager=scenario_manager,
)

runner = EmulatorRunner(server)
runner.start()

serving_socket = (
    server.transport.get_extra_info("socket")
    if server.transport is not None
    else None
)
assert serving_socket is not None
assert serving_socket.family == socket.AF_INET6
assert serving_socket.getsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY) == 1

yield port, server

runner.stop()
```

Retain the ephemeral IPv6 port, V6ONLY readback, synthetic `IPV6_DEVICE_SERIAL`, and teardown. If Windows exposes a setup defect inside this direct fixture path, fix it here without enabling unrelated emulator fixtures.

---

### `.github/workflows/ci.yml` (config, batch)

**Analogue:** existing matrix and unit-test step at lines 150-192.

**Matrix selection pattern** (lines 150-163):

```yaml
# Testing matrix scope:
# - PRs with source/test changes: full 3-OS matrix
# - PRs with CI-only changes: Ubuntu-only (smoke test)
# - Push to main: Ubuntu-only (PR already validated all OSes)
test:
  needs: changes
  name: Test (Python ${{ matrix.python-version }} on ${{ matrix.os }})
  runs-on: ${{ matrix.os }}
  strategy:
    fail-fast: false
    matrix:
      os: ${{ needs.changes.outputs.source == 'true' && github.event_name == 'pull_request' && fromJSON('["ubuntu-latest","macos-latest","windows-latest"]') || fromJSON('["ubuntu-latest"]') }}
      python-version: ['3.10', '3.11', '3.12', '3.13', '3.14']
```

Add the focused step inside this job, after dependency installation and immediately before `Run unit tests`. Do not create a job or expand the attempt to other Windows/Python cells.

**Focused-step shape:**

```yaml
- name: Run targeted IPv6 discovery on Windows
  if: ${{ matrix.os == 'windows-latest' && matrix.python-version == '3.10' }}
  run: uv run --frozen pytest tests/test_api/test_ipv6_e2e.py::<focused-test-node-id>
  env:
    <FOCUSED_IPV6_EMULATOR_ENV>: '1'
    LIFX_REQUIRE_IPV6: '1'
  timeout-minutes: 10

- name: Run unit tests
  run: uv run --frozen pytest
  env:
    LIFX_REQUIRE_IPV6: ${{ (matrix.os == 'ubuntu-latest' && matrix.python-version == '3.10') && '1' || '' }}
  timeout-minutes: 10
```

Use the final chosen test node ID and environment name literally. Do not add `continue-on-error`, a JUnit evidence artefact, or a shell retry. The following full-suite step and its existing environment remain unchanged, so the ordinary Windows run retains the blanket emulator skip.

## Shared Patterns

### Single address-family rule

**Source:** `src/lifx/network/address.py`, lines 136-175
**Apply to:** `src/lifx/network/discovery.py` and all transport-boundary tests

```python
def family_for(ip: str) -> socket.AddressFamily:
    addr = ipaddress.ip_address(ip)
    return socket.AF_INET6 if addr.version == 6 else socket.AF_INET

def wildcard_for(ip: str) -> str:
    return _IPV6_WILDCARD if family_for(ip) == socket.AF_INET6 else DEFAULT_IP_ADDRESS
```

No production or test helper may decide IPv6 by string shape.

### Validation before networking

**Source:** `src/lifx/network/address.py`, lines 76-113 and `src/lifx/api.py`, lines 955-961
**Apply to:** every invalid-input public test

```python
if not ip:
    raise ValueError("No IP address provided")

try:
    addr = ipaddress.ip_address(ip)
except ValueError as e:
    raise ValueError(f"Invalid IP address format: {e}") from e

if isinstance(addr, ipaddress.IPv6Address):
    if addr.is_link_local and addr.scope_id is None:
        raise ValueError(
            f"IPv6 link-local address requires a zone identifier: {ip}. "
            f"Append the interface, for example {ip}%en0"
        )
```

Assert this boundary with a fail-on-construction transport, not elapsed-time thresholds or a mocked API delegate.

### Discovery invariants are regression inputs, not code to refactor

**Source:** `src/lifx/network/discovery.py`, lines 268-520
**Apply to:** production implementation and regression selection

Preserve unchanged:

- overall and idle deadline semantics;
- cumulative re-broadcast offsets and the rule that sends do not reset idle time;
- source ID and expected packet-type validation;
- serial multicast/all-zero/padding checks;
- UDP-service filtering before first-wins deduplication;
- response-time calculation and consumer-work exclusion;
- `LifxProtocolError` continuation and async-context cleanup.

Run the existing discovery rebroadcast and error suites unchanged; new assertions supplement rather than weaken them. The project-local spike findings specifically prohibit retuning the discovery schedule in this phase.

### Real delivery, instrumented observation

**Source:** `tests/test_api/test_ipv6_e2e.py`, lines 46-63; `tests/test_network/test_discovery_errors.py`, lines 156-165
**Apply to:** real `::1`, concurrency, and cancellation tests

Patch the symbol consumed by `lifx.network.discovery`, call `super()` for real open/send/receive/close behaviour, and record only lifecycle state. Patching the transport class globally would also observe the separate device-capability connection and make endpoint counts ambiguous.

### Deterministic lifecycle coordination

**Source:** `tests/test_network/test_transport.py`, lines 318-352 and 370-409
**Apply to:** cancellation and concurrent-independence tests

Use `asyncio.Event` handshakes and task completion. Fixed sleeps are not accepted as proof that the endpoint was open or receive was blocked.

### Privacy-safe fixtures

**Source:** `AGENTS.md`, privacy rules; `tests/conftest.py`, lines 409-503
**Apply to:** every Phase 12 test, log assertion, and planning example

Use the existing synthetic serial, `::1`/`127.0.0.1`, ULA, and documentation-range literals. Never capture or commit a live interface, hostname, serial, MAC address, raw discovery response, or local network address. Keep log assertions value-suppressed where identity is not part of the contract.

### Imports, dependencies, and tooling

All Python imports remain at the top of their files. Add no dependency: use stdlib `socket`, `asyncio`, and `unittest.mock`; execute through `uv`. Do not modify `pyproject.toml`, `uv.lock`, generated protocol/product files, or `docs/changelog.md`.

## No Analogue Found

No file lacks a close repository analogue. The observation-only `RecordingDiscoveryTransport` helper has no single exact predecessor; compose it from:

| Helper | Role | Data Flow | Sources to combine |
|--------|------|-----------|--------------------|
| embedded recording discovery transport | test utility | real UDP + event-driven lifecycle | actual-socket inspection in `tests/test_api/test_ipv6_e2e.py:46-63`; `asyncio.Event` cancellation in `tests/test_network/test_transport.py:318-352`; patch boundary in `tests/test_network/test_discovery_errors.py:156-165` |

It belongs inside the test module unless reuse clearly emerges. It must call the real transport methods and change observation only.

## Metadata

**Analogue search scope:** `src/lifx/network/`, `src/lifx/api.py`, `tests/test_api/`, `tests/test_network/`, `tests/conftest.py`, `.github/workflows/`
**Files scanned:** 207 source, test, and workflow paths; five primary analogue families selected
**Pattern extraction date:** 2026-08-29
**Repository state:** clean `gsd/phase-12-ipv6-discovery-plumbing` branch when mapping began
