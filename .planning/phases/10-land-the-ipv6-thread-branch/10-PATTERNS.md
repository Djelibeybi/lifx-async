# Phase 10: Land the IPv6/Thread Branch - Pattern Map

**Mapped:** 2026-08-27
**Files analyzed:** 16 new/modified files (plus 3 rebased-whole files)
**Analogs found:** 15 / 16

> File list derived from 10-SPEC.md + 10-CONTEXT.md D-01..D-23 and the three branch
> commits (`b49400b`, `b88cdb9`, `2f884f5`, 11 files, +1131/-330). Line numbers marked
> *(branch)* refer to the file content at `2f884f5`; unmarked lines refer to `main`.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/lifx/network/address.py` (NEW) | utility (leaf rule module) | transform (pure) | `src/lifx/theme/slug.py` | exact — cited by SPEC R3 itself |
| `tests/test_network/test_address.py` (NEW) | test | transform | `tests/test_theme/test_slug.py`, `tests/test_utils.py` | exact |
| `src/lifx/network/transport.py` | network transport | request-response UDP | itself (branch `2f884f5` version) | exact |
| `src/lifx/network/connection.py` | network connection | request-response UDP | itself (branch version) | exact |
| `src/lifx/animation/animator.py` | animation hot path | streaming UDP | itself (branch version) | exact |
| `src/lifx/devices/base.py` | device model | request-response | itself (branch version) | exact |
| `src/lifx/api.py` (`find_by_ip`) | high-level API | request-response | `find_by_serial()` in same file | exact |
| `src/lifx/network/mdns/transport.py` | network transport | request-response multicast | `UdpTransport.open()` error path, `transport.py:339` | role-match |
| `tests/conftest.py` (`emulator_server_ipv6`, `ipv6_available`, `get_free_port6`) | test fixture | config | `tile_chain_server` (:241), `emulator_available` (:130), `get_free_port()` (:83) | exact — CONTEXT names these as templates |
| `tests/test_api/test_ipv6_e2e.py` (or similar, NEW) | test (emulator e2e) | request-response | `tests/test_devices/conftest.py` + `tile_chain_light` fixture pattern | role-match |
| `tests/test_network/test_transport.py` | test | request-response | itself (endpoint-death class, lines 474-560) | exact |
| `tests/test_network/test_mdns/test_transport.py` | test | request-response | itself (rebased branch version) | exact |
| `tests/test_devices/test_base.py` | test | request-response | itself | exact |
| `.github/workflows/ci.yml` | config (CI) | batch | itself (test matrix, lines 150-205) | exact |
| `scripts/ipv6_thread_probe.py` | script (UAT harness) | request-response | itself (lands whole in `b88cdb9`, then extended per D-21) | exact |
| `10-UAT-RESULTS.json` / `10-EXCEPTION-OVERRIDE.json` | artefact | — | v1.2 Phase 8 exception schema (per SPEC R9) | no code analog |

Rebased whole, no new-pattern work needed: `src/lifx/network/mdns/discovery.py`,
`src/lifx/network/mdns/dns.py`, `tests/test_network/test_mdns/test_discovery.py`.

## Pattern Assignments

### `src/lifx/network/address.py` (NEW — utility, pure transform)

**Analog:** `src/lifx/theme/slug.py` — the project's canonical "leaf module owning exactly
one rule" pattern, explicitly cited by SPEC R3 and CONTEXT D-01. `src/lifx/geometry.py` is
the second instance of the same pattern.

**Module-docstring pattern** (`src/lifx/theme/slug.py:1-31`): a long docstring stating (a)
this is the *one home* of the rule, (b) which call sites share it so they "cannot drift
apart", (c) the rule itself with rationale for each deliberate choice, (d) leaf-module
status ("its only import is `re`, never anything from `lifx`"). For `address.py` the only
stdlib imports should be `socket` and `ipaddress` (plus `lifx.const` for
`DEFAULT_IP_ADDRESS`, needed by `wildcard_for()` — note that makes it a near-leaf, not a
pure leaf; call it out in the docstring the way slug.py calls out its constraints).

**Import/constant pattern** (`slug.py:33-52`):
```python
from __future__ import annotations

import re

#: Rationale comment on every module-level constant, explaining why it is
#: shaped the way it is, not just what it is.
_DROPPED = re.compile(r"['‘’ʼ`\"“”]+")
```
Every source file in the package opens with `from __future__ import annotations`.

**Surface (per D-02):** three functions, each owning one rule —
`validate_address(ip) -> None` (raises `ValueError`), `family_for(ip) -> socket.AddressFamily`,
`wildcard_for(ip) -> str` (returns `"::"` or `DEFAULT_IP_ADDRESS`).

**Validation-rule source material** — the block being moved out of `Device.__init__`
(branch `src/lifx/devices/base.py`, roughly lines 485-535 *(branch)*):
```python
# Validate IP address
try:
    addr = ipaddress.ip_address(ip)
except ValueError as e:  # pragma: no cover
    raise ValueError(f"Invalid IP address format: {e}")

# Check for localhost
if addr.is_loopback:
    _LOGGER.warning({"class": "Device", "method": "__init__",
                     "action": "is_loopback", "ip": ip})

# Check for unspecified (0.0.0.0)
if addr.is_unspecified:
    raise ValueError("Unspecified IP address (0.0.0.0) not allowed")  # pragma: no cover

# Warn for non-private IPs (LIFX should be on local network)
if not addr.is_private:
    _LOGGER.warning({"class": "Device", "method": "__init__",
                     "action": "non_private_ip", "ip": ip})

# IPv6 link-local addresses need a zone/scope ID to be reachable.
if (addr.version == 6 and addr.is_link_local
        and getattr(addr, "scope_id", None) is None):
    _LOGGER.warning({...})   # B2: MUST become raise ValueError naming the missing zone
```
Rules for the move (D-03..D-06): ALL address rules move (loopback warn, unspecified raise,
non-private warn, plus new zone-less link-local raise, IPv4-mapped raise, empty/`None`
raise). All `# pragma: no cover` markers come OFF and every branch gets a unit test (D-04).
Serial checks (all-zeros/broadcast, base.py lines above the address block) do NOT move
(D-05). Moved warnings log as `{"module": "lifx.network.address", "function":
"validate_address", "action": ..., "ip": ip}` — dropping the `class`/`method` keys (D-06).
Note `ipaddress.ip_address()` rejects zoned literals like `fe80::1%en0` on some parses —
use `ipaddress.IPv6Address` which accepts `%zone` on Python 3.9+; `scope_id` is the probe
already used on the branch. IPv4-mapped detection: `addr.ipv4_mapped is not None`.

**Grep obligation (AC 8):** after this file lands, `grep '":" in ' src/lifx/` must return
no family-selection use.

---

### `src/lifx/network/transport.py` (B9 call site + B1 send assertion + R5 contract)

**Analog:** the branch version of itself; error-path conventions from `main`.

**Branch code to replace** (`UdpTransport.open()`, ~line 295 *(branch)*):
```python
# The socket family follows the local bind address: "::" selects IPv6 ...
family = socket.AF_INET6 if ":" in self._ip_address else socket.AF_INET
self._transport, _ = await loop.create_datagram_endpoint(
    lambda: protocol,
    local_addr=(self._ip_address, self._port),
    reuse_port=bool(hasattr(socket, "SO_REUSEPORT")),
    family=family,
)
```
Becomes `family = family_for(self._ip_address)` — family derived from the **bind** address.

**B1 send-time assertion goes in `send()`** (`main` transport.py:389-415):
```python
async def send(self, data: bytes, address: tuple[str, int]) -> None:
    if self._transport is None or self._protocol is None:
        raise LifxNetworkError("Socket not open")
    try:
        self._transport.sendto(data, address)
    ...
        raise LifxNetworkError(f"Failed to send data: {e}") from e
```
Pattern to copy: raise `LifxNetworkError` with a plain message (matching "Socket not
open"). The family check compares `family_for(address[0])` against the open socket's
family (`self._transport.get_extra_info("socket").family` or a family stored at open
time). Placement before/after the `is_open` check is Claude's discretion per CONTEXT, but
the `error_received` contract must survive: `_FATAL_SOCKET_ERRNOS` (transport.py:34),
`_UdpProtocol.error_received` (:164-189) — peer errors (`EHOSTUNREACH`/`EHOSTDOWN`/
`ENETUNREACH`) route to `error_received` and never tear down the endpoint; only
`EBADF`/`ENOTSOCK` signal endpoint death via `_endpoint_lost` (:341).

---

### `src/lifx/network/connection.py` (B9 call site)

**Analog:** branch version of itself, `DeviceConnection._open()` ~line 234 *(branch)*:
```python
# Open transport, binding to the address family that matches the device
local_ip = "::" if ":" in self.ip else DEFAULT_IP_ADDRESS
self._transport = UdpTransport(ip_address=local_ip, port=0, broadcast=False, peer=self._peer)
```
Becomes `local_ip = wildcard_for(self.ip)` — per D-02, `_open()` contains no family test
at all. Everything else in the method (receiver task, `_is_opening` guard, debug dict log)
stays as the branch wrote it.

---

### `src/lifx/animation/animator.py` (B9 call site + AC 2 family assertion)

**Analog:** branch version of itself, `send_frame` ~line 399 *(branch)*:
```python
# Ensure socket exists. The socket family follows the device address ...
if self._socket is None:
    family = socket.AF_INET6 if ":" in self._addr[0] else socket.AF_INET
    self._socket = socket.socket(family, socket.SOCK_DGRAM)
    self._socket.setblocking(False)
```
Becomes `family = family_for(self._addr[0])` — family from the **target**. Keep the
cache-on-first-frame shape exactly; NO per-frame check (D-08, the Phase 4 hot path).
`_addr` is assigned once at animator.py:147 and never reassigned; the family assertion for
AC 2 is a construction-time/test-level assertion, not runtime code.

---

### `src/lifx/devices/base.py` (`Device.__init__`, `Device.from_ip()`)

**Analog:** branch version of itself.

`Device.__init__`: the whole inline address block (~485-535 *(branch)*, excerpted above
under address.py) is replaced by a single `validate_address(ip)` call. The serial checks
above it and the port checks below it (`if not (1024 <= port <= 65535): ... # pragma: no
cover`, non-standard-port warning) stay untouched with their pragmas.

`Device.from_ip()` (branch base.py:~596): a classmethod whose signature is
`(cls, ip, port=LIFX_UDP_PORT, serial=None, timeout=DEFAULT_REQUEST_TIMEOUT,
max_retries=DEFAULT_MAX_RETRIES, *, ...)`. Add `validate_address(ip)` before it constructs
anything, so `fe80::1` raises in <100 ms with no socket (AC 3). (Construction already
routes through `Device.__init__`, but SPEC lists `from_ip()` as its own entry point — the
call must precede any network work.)

---

### `src/lifx/api.py` (`find_by_ip`, line ~906)

**Analog:** the function itself; validation-first pattern per D-07.
```python
async def find_by_ip(
    ip: str,
    timeout: float = DISCOVERY_TIMEOUT,
    ...
) -> Device | None:
    """Find a LIFX device by IP address. ..."""
```
Add `validate_address(ip)` as the **first statement** of the body, before any socket. A
syntactically valid IPv6 literal then falls through to today's IPv4 targeted-broadcast
behaviour and returns `None` (Phase 12's gap — no interim docstring note, no
`LifxUnsupportedCommandError`).

---

### `src/lifx/network/mdns/transport.py` (IPV6-04 leak fix + B4 docstrings)

**Analog:** its own branch `open()` (excerpted below) plus `UdpTransport.open()`'s error
wrap (`main` transport.py:339: `raise LifxNetworkError(f"Failed to open UDP socket: {e}")
from e`).

**Leak site** (branch mdns/transport.py, `open()`):
```python
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind(("", 0))                                    # can raise -> leak
sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)  # can raise -> leak
sock.setblocking(False)
self._socket = sock
...
self._transport, _ = await loop.create_datagram_endpoint(  # can raise -> leak
    lambda: protocol, sock=sock,
)
...
except OSError as e:
    ...raises LifxNetworkError without closing sock
```
Fix (Claude's discretion on mechanism): `try/except OSError: sock.close(); raise` or
`contextlib.ExitStack` with `stack.pop_all()` on success. The existing
`except OSError as e:` block with its debug-dict log and `LifxNetworkError` re-raise stays
the outer shape.

**B4 docstrings** — current false text to replace:
- module docstring: `"...with multicast group joining and appropriate socket
  configuration."`
- class docstring: `"...with support for multicast group membership and appropriate
  socket options."`
Rewrite both around the RFC 6762 §6.7 rationale already in `open()`'s inline comment
("Bind to an ephemeral port: per RFC 6762 §6.7, queries sent from a port other than 5353
are 'legacy unicast' queries and responders reply directly to our port..."). AC: neither
docstring contains "multicast group", "membership" or "IP_ADD_MEMBERSHIP".

---

### `tests/conftest.py` (fixtures — R7)

**Analog 1 — `get_free_port6()` copies `get_free_port()`** (conftest.py:83):
```python
def get_free_port() -> int:
    """Get a free UDP port."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]
```
IPv6 sibling binds `socket.AF_INET6` on `("::1", 0)` (D-10).

**Analog 2 — `ipv6_available` copies `emulator_available`** (conftest.py:130):
```python
@pytest.fixture(scope="session")
def emulator_available(request: pytest.FixtureRequest) -> bool:
    """Check if lifx-emulator-core is available. ..."""
    disable_emulator = request.config.getoption("--disable-emulator", default=False)
    if disable_emulator:
        return False
    # Emulator tests are too flaky on Windows (timing-sensitive UDP)
    if sys.platform == "win32":
        return False
    try:
        from lifx_emulator import EmulatedLifxServer  # noqa: F401
        return True
    except ImportError:
        return False
```
`ipv6_available` is the same shape: session-scoped bool, probes
`socket.socket(AF_INET6).bind(("::1", 0))` once (D-12). Twist per D-15/D-17: when
`os.environ.get("LIFX_REQUIRE_IPV6") == "1"` and the bind fails, it must **raise/fail**
(e.g. `pytest.fail(...)`) instead of returning False, with a message naming the cause.
The env var guards the IPv6 probe only, never `emulator_available`.

**Analog 3 — `emulator_server_ipv6` copies `tile_chain_server`** (conftest.py:241):
```python
@pytest.fixture(scope="session")
def tile_chain_server(emulator_available: bool) -> Generator[int]:
    """Start an emulator hosting a single 5-tile LIFX Tile chain. ..."""
    if not emulator_available:
        pytest.skip("lifx-emulator-core not available")

    scenario_manager = HierarchicalScenarioManager()
    devices = [create_tile_device(serial="d073d5000101", tile_count=5,
                                  scenario_manager=scenario_manager)]
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
```
The IPv6 variant: depends on `emulator_available` AND `ipv6_available` (skip through the
`ipv6_available` gate, D-12), uses `get_free_port6()`, `bind_address="::1"`, one `Light`
class device (D-14), and asserts/sets `IPV6_V6ONLY` explicitly on the emulator socket per
amended AC 16 (SPEC notes lifx-emulator-core 3.7.0 infers AF_INET6 from `"::1"` with no
emulator change). The existing `emulator_server` and its seven devices are untouched
(D-11). The docstring pattern to copy from `tile_chain_server`: state why a *second*
server exists and what it deliberately does not change.

**Analog 4 — device fixture copies `tile_chain_light`** (conftest.py, directly below
`tile_chain_server`): a function-scoped fixture returning an unconnected device pointed at
the fixture's port; e.g. `Light(serial=..., ip="::1", port=emulator_server_ipv6,
timeout=2.0, max_retries=2)`.

---

### IPv6 end-to-end tests (NEW test module)

**Analog:** any emulator-backed device test using the `tile_chain_light` shape (e.g.
`tests/test_devices/test_matrix.py` chain tests) — `async with light:` then exercise
methods. Scope is exactly SPEC R1 on one `Light`: connect, `get_color()`, `set_color()`,
`set_power()`, plus an `Animator` frame-delivery run (analog:
`tests/test_animation/test_animator.py`). Every test asserts the socket family it used is
`AF_INET6` (amended AC 16) — for the connection, via
`device.connection._transport` internals or `get_extra_info("socket").family`; for the
Animator, `animator._socket.family == socket.AF_INET6` after a frame. Note: the loopback
warning will fire on every `::1` test; leave it alone (D-13).

---

### `tests/test_network/test_address.py` (NEW)

**Analog:** `tests/test_theme/test_slug.py` (unit tests for the sibling leaf-rule module)
and the plain-class style of `tests/test_network/test_transport.py:153-190`
(`test_protocol_error_received` — instantiate, call, assert on the structured log dict
via `caplog`). Must cover every branch (D-04, 100% branch patch coverage): IPv4, IPv6,
`"::"`/`"0:0:0:0:0:0:0:0"` same family, `fe80::1` raise, `fe80::1%en0` accept, `fe80::1%`
raise, `FE80::1`/expanded-form raise identically, `::ffff:192.0.2.1` raise, `""`/`None`
raise, loopback warning fires, non-private warning fires, unspecified raise. Warning
assertions check the new dict shape (`module`/`function` keys, D-06).

---

### `tests/test_network/test_transport.py` (B1 + R5 tests)

**Analog:** its own endpoint-death test class (lines 474-560), which already
parameterises over `[errno.EHOSTDOWN, errno.EHOSTUNREACH, errno.ENETUNREACH,
errno.ECONNREFUSED]` (line 542) and asserts peer errors do NOT tear the endpoint down.
Copy that parameterised shape for the R5 "family assertion must not convert peer errors
into raises" test (AC 11). New B1 test: open an `AF_INET` transport, `send()` to an IPv6
destination, assert `LifxNetworkError` in <100 ms.

### `tests/test_network/test_mdns/test_transport.py` (IPV6-04 tests)

**Analog:** the rebased branch version of itself. New tests force `OSError` at each of
`bind()`, `setsockopt()`, `create_datagram_endpoint()` (monkeypatch each) and assert the
socket is closed and no `ResourceWarning` (use
`pytest.warns`-suppression / `warnings.catch_warnings(record=True)` with
`simplefilter("error", ResourceWarning)` and `gc.collect()`). Plus the R4 backstop:
concurrent `open()` calls and `close()` racing a failing `open()` leak no descriptor —
carry into plan `must_haves` per SPEC edge table.

### `tests/test_devices/test_base.py` + `tests/test_api/` (entry-point tests)

**Analog:** existing `ValueError`-on-construction tests in `test_base.py` (the serial and
port validation tests). Per D-19, B2's WARNING→raise flip carries its test updates in the
same commit that changes behaviour; the branch's own rebased tests land untouched in the
rebase commits.

---

### `.github/workflows/ci.yml` (R7 CI gate)

**Analog:** the existing test job (lines 150-205):
```yaml
test:
  name: Test (Python ${{ matrix.python-version }} on ${{ matrix.os }})
  runs-on: ${{ matrix.os }}
  strategy:
    matrix:
      python-version: ['3.10', '3.11', '3.12', '3.13', '3.14']
```
Per D-15/D-16 the gate is NOT a new job: add a conditional env var so the ubuntu +
Python 3.10 cell runs with `LIFX_REQUIRE_IPV6=1`, e.g.
`LIFX_REQUIRE_IPV6: ${{ (matrix.os == 'ubuntu-latest' && matrix.python-version == '3.10') && '1' || '' }}`
on the pytest step's `env:`. That cell exists in every matrix configuration including the
ubuntu-only reduced path (lines 150-155 comment). No artefact plumbing, no gate job.
Optionally document `LIFX_REQUIRE_IPV6` in CLAUDE.md alongside `LIFX_EMULATOR_EXTERNAL`
(Claude's discretion).

---

### `scripts/ipv6_thread_probe.py` (D-21 UAT extension)

**Analog:** itself as landed by `b88cdb9` (521 lines, three stages: records / ports /
connect, driving the library's own primitives). Extend with a control stage
(`set_color`/`set_power`) and an optional streaming stage, emitting `10-UAT-RESULTS.json`
with device serial + timestamp. Follow its existing stage structure and the CLAUDE.md
script conventions (`scripts/serial_mac_audit.py` is the other hardware-facing script).

## Shared Patterns

### Structured dict logging
**Source:** everywhere, e.g. `src/lifx/network/transport.py` `open()`:
```python
_LOGGER.debug({"class": "UdpTransport", "method": "open",
               "action": "opening_socket", "ip_address": self._ip_address, ...})
```
**Apply to:** all touched modules. Module-level functions in `address.py` use
`module`/`function` keys instead of `class`/`method` (D-06); classes keep `class`/`method`.
Every file defines `_LOGGER = logging.getLogger(__name__)`.

### Typed exception raising
**Source:** `src/lifx/exceptions.py` hierarchy; `transport.py:339, 400, 415`.
**Apply to:** B1 assertion and IPV6-04 re-raise use `LifxNetworkError` with
`raise ... from e` where an underlying `OSError` exists. Address validation uses plain
`ValueError` (construction-time input errors, matching `Device.__init__` precedent).

### Peer-error vs endpoint-death contract (must not break)
**Source:** `transport.py:34` `_FATAL_SOCKET_ERRNOS = frozenset({errno.EBADF,
errno.ENOTSOCK})`, `_UdpProtocol.error_received` (:164-189), `_endpoint_lost` (:341).
**Apply to:** the B1 send assertion — it must be a pre-send check, never a change to
`error_received` routing.

### Coverage discipline
`codecov.yml` `patch.default.target: 100%` branch coverage on the merged report. No new
`# pragma: no cover` on IPv6 code (prohibition 3); D-04 removes the pragmas from the moved
branches and tests each one. Every emulator test skips through fixture-level
`pytest.skip()` gates, never module-level skips.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `10-UAT-RESULTS.json` / `10-EXCEPTION-OVERRIDE.json` | phase artefact | — | Schema comes from the v1.2 Phase 8 exception schema referenced in SPEC R9, not from code; check `.planning/` history for the Phase 8 artefact when writing it |

## Metadata

**Analog search scope:** `src/lifx/` (network, animation, devices, theme, api),
`tests/` (conftest, test_network, test_animation, test_devices), `.github/workflows/`,
branch commits `b49400b`/`b88cdb9`/`2f884f5` via `git show`
**Files scanned:** 14 read in detail, 11-file branch diff surveyed
**Pattern extraction date:** 2026-08-27
