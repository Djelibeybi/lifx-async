# Phase 1: Unify Duplicated Discovery Loops — Research

**Researched:** 2026-06-13
**Domain:** Python asyncio async-generator refactoring; LIFX UDP discovery protocol
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Serial validation (broadcast/multicast bit set, or all-`0xff` serial → reject) moves
  into `_discover_with_packet` — **unconditional**, no opt-out parameter.
- **D-02:** Rejected responses → **DEBUG log only** (no WARNING-level per-packet logging).
- **D-03:** Hoisting hardens `find_by_label` and label/colour enrichment paths — deliberate
  behaviour change; previously invalid serials flowed through, now dropped.
- **D-04:** Per-serial dedup lives in the **shared generator**: first response per serial wins.
  Retires the vestigial write-only `responses` dict at `discovery.py:322`.
- **D-05:** `discover_devices()` becomes a thin wrapper over
  `_discover_with_packet(DevicePackets.GetService(), ...)`.
  `_parse_device_state_service()` is **deleted**; `StateService.unpack()` is the single source
  of truth.
- **D-06:** Extract `class IdleDeadline` in `src/lifx/network/utils.py`:
  `__init__(timeout, idle_timeout)`, `remaining() -> float`, `mark_response()`.
  Monotonic-clock based.
- **D-07:** Both the unified LIFX loop AND `mdns/discovery.py`'s `discover_lifx_services` adopt
  `IdleDeadline` this phase.
- **D-08:** mDNS loop's bare `except Exception` around `receive()` is tightened: catch
  `LifxTimeoutError` to stop; `LifxNetworkError`/unexpected errors are logged distinctly or
  propagate.
- **D-09:** `UdpTransport.receive_many` deprecated this phase (`warnings.warn` + `.. deprecated::`
  docstring), removed in v2.0. Method body otherwise untouched.
- **D-10:** Tests pinned to retired internals may be rewritten or deleted freely, as long as
  every proved behaviour stays covered via the shared path.
- **D-11:** New tests for the shared generator proving serial validation and first-wins dedup at
  the `_discover_with_packet` level. Emulator-first where possible.
- **D-12:** One test asserting `receive_many` emits `DeprecationWarning`.

### Claude's Discretion

- Exact DEBUG log message wording/format for rejected serials.
- Exact deprecation message text (must name `v2.0`, point to `receive()` / discovery loops).
- `IdleDeadline` internals (attribute names, caching of `monotonic()` calls).
- Test placement and naming within `tests/test_network/`.

### Deferred Ideas (OUT OF SCOPE)

- Retry-budget unification in `connection.py`.
- `receive_many` actual removal (v2.0 only).
- Transport base-class extraction.

</user_constraints>

---

## Summary

This phase is a pure internal refactor of `src/lifx/network/discovery.py`. The two discovery
loops (`_discover_with_packet` and `discover_devices`) implement the same timeout arithmetic,
transport lifecycle, and packet-receive loop with ~150 lines of near-identical code that have
already drifted: serial DoS validation exists only in `discover_devices`, `time.time()` was used
in the mDNS loop until recently, and a `responses` dict is written but never read in
`_discover_with_packet`.

The unification strategy is mechanical: hoist validation and dedup into `_discover_with_packet`,
extract the triple-copied timeout arithmetic into `IdleDeadline`, then thin `discover_devices`
down to a wrapper that calls `_discover_with_packet(DevicePackets.GetService(), ...)` and
converts each `DiscoveryResponse` into a `DiscoveredDevice`. The hand-rolled
`_parse_device_state_service()` (which duplicates `StateService.unpack()`) is deleted. The mDNS
`discover_lifx_services` loop adopts `IdleDeadline` and gets its bare `except Exception`
tightened to distinguish timeouts from genuine network errors.

No public API surface changes: `discover_devices()`, `find_by_serial()`, `find_by_ip()`, and
`find_by_label()` all preserve their signatures and yield contracts. The only observable
behaviour changes are the two deliberate hardening side effects agreed in CONTEXT.md (D-03: invalid
serials now rejected on all paths; D-04: duplicate serials no longer double-yield from
`find_by_label`).

**Primary recommendation:** Implement in two sub-tasks — (1) hoist validation + dedup into
`_discover_with_packet` and extract `IdleDeadline`; (2) thin `discover_devices` down to a
wrapper and delete `_parse_device_state_service`. Tests and deprecation warning are a
third sub-task.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Serial DoS validation | Network Layer (`discovery.py`) | — | All discovery paths flow through `_discover_with_packet`; validation belongs at the generator boundary |
| Deduplication | Network Layer (`discovery.py`) | — | Dedup is a transport-level concern, not a caller concern |
| Port extraction from StateService | Network Layer (`discovery.py` thin wrapper) | Protocol Layer (`packets.py`) | Callers need `DiscoveredDevice.port`; extraction logic delegates to `StateService.unpack()` |
| Timeout arithmetic | Utility (`utils.py` `IdleDeadline`) | Network Layer (both loops) | Identical logic used in 3 places; belongs in a shared helper |
| Deprecation signal | Network Layer (`transport.py`) | — | `receive_many` is a transport method; warning emitted at call site |
| mDNS exception routing | Network Layer (`mdns/discovery.py`) | — | Tightening is local to that loop's `receive()` call |

---

## Standard Stack

No new external dependencies. This phase is stdlib + project-internal only, consistent with the
zero-runtime-dependency policy.

### Relevant Stdlib
| Module | Use |
|--------|-----|
| `time.monotonic()` | All timeout arithmetic — already used in both loops |
| `warnings.warn(..., DeprecationWarning, stacklevel=2)` | `receive_many` deprecation |
| `struct` | Currently used only by `_parse_device_state_service` — removed after D-05 |

**Package Legitimacy Audit:** Not applicable — this phase installs no packages.

---

## Architecture Patterns

### System Architecture Diagram

```
External network
      │  UDP responses
      ▼
_discover_with_packet(packet, ...)          ← GENERIC BROADCAST GENERATOR
  ├─ allocate_source()                       (utils.py — unchanged)
  ├─ UdpTransport(broadcast=True)            (transport.py — unchanged)
  ├─ IdleDeadline(timeout, idle_timeout)     (utils.py — NEW)
  ├─ serial validation [NEW]                 (D-01/D-02)
  │    broadcast/multicast bit or 0xff → DEBUG log + skip
  ├─ per-serial dedup [NEW]                  (D-04)
  │    first response wins; duplicate serial → skip
  └─ yield DiscoveryResponse(serial, ip, port, response_time, response_payload)
            │
            ├─── discover_devices() [THIN WRAPPER]  ← D-05
            │     extracts port via StateService.unpack()
            │     yields DiscoveredDevice(serial, ip, port, ...)
            │              │
            │              └─── api.py: discover(), find_by_serial(), find_by_ip()
            │              └─── devices/base.py: set_location(), set_group()
            │
            └─── api.py: find_by_label()   ← already calls _discover_with_packet directly
                  (gains validation + dedup via hoist — D-03)

mdns/discovery.py: discover_lifx_services()
  ├─ MdnsTransport()
  ├─ IdleDeadline(timeout, idle_timeout)     (utils.py — NEW, D-07)
  ├─ except LifxTimeoutError → break         (tightened — D-08)
  ├─ except LifxNetworkError → log + propagate or break
  └─ yield LifxServiceRecord
```

### Recommended Project Structure
```
src/lifx/network/
├── utils.py           # allocate_source() + NEW: IdleDeadline class
├── discovery.py       # _discover_with_packet (with validation+dedup), discover_devices (thin)
│                      # _parse_device_state_service DELETED
├── transport.py       # receive_many deprecated (warnings.warn + docstring)
└── mdns/
    └── discovery.py   # discover_lifx_services adopts IdleDeadline, tightened except

tests/test_network/
├── test_discovery_errors.py   # REWRITE: retire _parse_device_state_service tests;
│                              #  add shared-generator serial validation + dedup tests
├── test_transport.py          # ADD: D-12 DeprecationWarning test; rest stays
└── (new?) test_utils.py       # IdleDeadline unit tests (already exists as test_utils.py
                               #  at tests/ root — consider tests/test_network/test_utils.py)
```

---

## Detailed Behavioural Difference Table

This is the critical planning artefact: every behavioural difference between the two loops
that the unification must resolve.

| Behaviour | `_discover_with_packet` (current) | `discover_devices` (current) | Resolution |
|-----------|-----------------------------------|------------------------------|------------|
| Serial validation (broadcast bit / 0xff) | **ABSENT** | Lines 558–566: `WARNING` log, `continue` | Move to `_discover_with_packet`; change to `DEBUG` (D-01, D-02) |
| Per-serial dedup | **ABSENT** — duplicate serials yield multiple times | Lines 578–579: `seen_serials` set | Move to `_discover_with_packet` (D-04) |
| Vestigial `responses` dict | Line 201: allocated; line 322: written; **never read** | N/A | **Delete** when hoisting dedup (D-04) |
| Payload parsing | Uses `get_packet_class(header.pkt_type).unpack(payload)` then `as_dict` | Uses `_parse_device_state_service(payload)` (hand-rolled `struct.unpack`) | `discover_devices` adopts protocol layer; delete `_parse_device_state_service` (D-05) |
| Packet-type filtering | Checks `header.pkt_type != expected_response_type` | Checks `header.pkt_type != DevicePackets.StateService.PKT_TYPE` | Same logic; no change needed |
| Source-ID validation | Line 271: `header.source != discovery_source → continue` (no log) | Lines 528–541: same check + DEBUG log with `expected_source`/`received_source` | Both have it; log format is discretionary (Claude's) |
| `packet_count` counter | **ABSENT** | Lines 522–523: incremented before inner try | **Drop** when thinning (not in `DiscoveredDevice` contract) |
| `start_time` tracking | Line 202 (used only in final log) | Line 433 (used only in final log) | Both; `IdleDeadline` tracks its own start; expose or keep separate |
| Final completion log fields | `devices_found: len(responses)`, `elapsed` | `devices_found: len(seen_serials)`, `packets_processed`, `elapsed` | After hoisting dedup, `_discover_with_packet` has seen_serials count; `packets_processed` is dropped (not material) |
| `LifxTimeoutError` on receive | `break` (silent) | `break` + DEBUG log `"no_responses"` | After thin-wrapper, `_discover_with_packet` break is authoritative; extra `discover_devices` log disappears (acceptable) |
| `LifxProtocolError` handling | WARNING log without `exc_info`, `continue` | WARNING log with `exc_info=True` + `packet_size` field, `continue` | Align to `exc_info=True`; `packet_size` is available in wrapper if desired |
| Unexpected errors | ERROR log with `exc_info=True` | ERROR log with `exc_info=True` | Already matching |
| Transport ownership | Owns its own `UdpTransport` context | Owns its own `UdpTransport` context | No change — `discover_devices` becomes a thin caller on top; transport stays inside `_discover_with_packet` |
| `device_timeout` / `max_retries` params | **ABSENT** — not in signature | Present — passed through to `DiscoveredDevice` | Thin wrapper receives them and uses them when constructing `DiscoveredDevice`; not needed in `_discover_with_packet` |
| `idle_timeout` reset point | After yielding `DiscoveryResponse` (line 323) | After `seen_serials.add` (duplicates also reset timer, line 606) | After hoisting dedup, timer resets only for first-seen serials — semantics preserved for deduped case because duplicates now never pass the dedup check |
| `as_dict` field names for StateService | Would use `response_payload["service"]`, `response_payload["port"]` (Packet.as_dict uses Python attribute names) | N/A (parses `service` and `port` from struct) | Confirmed: `StateService` fields are `service: DeviceService` and `port: int`; `as_dict` returns `{"service": ..., "port": ...}` — wrapper uses `resp.response_payload["port"]` |

---

## `DiscoveryResponse` Contract (what `discover_devices` wrapper needs)

`DiscoveryResponse` fields:
- `serial: str` — 12-digit hex (e.g., `"d073d5123456"`)
- `ip: str` — device IP address
- `port: int` — currently **always set to the broadcast port** (default `LIFX_UDP_PORT`), NOT the
  device-specific UDP port from the `StateService` payload
- `response_time: float`
- `response_payload: dict[str, Any]` — result of `response_packet_class.unpack(payload).as_dict`

**Critical note on `port`:** The `DiscoveryResponse.port` field is set to the broadcast port
(line 317: `port=port` where `port` is the parameter, defaulting to `LIFX_UDP_PORT`), not the
device's actual service port from the `StateService` payload. The device-specific port must be
extracted from `response_payload["port"]` when constructing `DiscoveredDevice` in the thin
wrapper. This is exactly what `_parse_device_state_service` currently does — the thin wrapper
replaces it with `resp.response_payload["port"]`.

**`StateService.as_dict` field names:**
```python
# StateService fields: service: DeviceService, port: int
# as_dict returns:
{"service": <DeviceService enum value>, "port": <int>}
```
Confirmed by reading `packets.py:430–445` and `base.py:64–66` (`as_dict` returns `asdict(self)`
which uses Python attribute names, not protocol names).

---

## `IdleDeadline` Design

### What it replaces (identical in all three loops)

```python
# Current pattern — appears in _discover_with_packet, discover_devices,
# and discover_lifx_services with identical logic
idle_timeout = max_response_time * idle_timeout_multiplier
last_response_time = request_time

while True:
    elapsed_since_last = time.monotonic() - last_response_time

    if elapsed_since_last >= idle_timeout:
        break                           # idle timeout

    if time.monotonic() - request_time >= timeout:
        break                           # overall timeout

    remaining_idle = idle_timeout - elapsed_since_last
    remaining_overall = timeout - (time.monotonic() - request_time)
    remaining = min(remaining_idle, remaining_overall)

    try:
        data, addr = await transport.receive(timeout=remaining)
        response_timestamp = time.monotonic()
    except LifxTimeoutError:
        break
    ...
    last_response_time = response_timestamp   # mark_response()
```

### Proposed `IdleDeadline` interface [ASSUMED for exact internals; Claude's discretion]

```python
# src/lifx/network/utils.py
import time

class IdleDeadline:
    """Manages dual timeout: overall deadline and idle (inter-response) deadline."""

    def __init__(self, timeout: float, idle_timeout: float) -> None:
        self._start = time.monotonic()
        self._overall = timeout
        self._idle = idle_timeout
        self._last_response = self._start

    def remaining(self) -> float:
        """Return seconds until next deadline (min of idle and overall).
        Returns <= 0 when either deadline is exceeded."""
        now = time.monotonic()
        remaining_overall = self._overall - (now - self._start)
        remaining_idle = self._idle - (now - self._last_response)
        return min(remaining_overall, remaining_idle)

    @property
    def expired(self) -> bool:
        """True when either timeout has been exceeded."""
        return self.remaining() <= 0

    def mark_response(self) -> None:
        """Reset the idle timer (call when a valid response is received)."""
        self._last_response = time.monotonic()
```

The loop body simplifies to:
```python
deadline = IdleDeadline(timeout, idle_timeout)
while not deadline.expired:
    remaining = deadline.remaining()
    if remaining <= 0:
        break
    try:
        data, addr = await transport.receive(timeout=remaining)
    except LifxTimeoutError:
        break
    ...
    deadline.mark_response()
```

**Note:** The existing loops check idle and overall conditions separately before computing
`remaining`, so they can emit different log messages per timeout type. The planner should decide
whether to preserve two separate log messages or merge into a single `deadline.expired` check.
The existing per-type log messages aid diagnosis and should be preserved — achieved by checking
`deadline.idle_expired` and `deadline.overall_expired` as separate properties, or by logging
after the loop using the known remaining values.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| StateService payload parsing | Custom `struct.unpack("<BI", ...)` | `Device.StateService.unpack(payload)` | Protocol layer already does this; the hand-rolled version in `_parse_device_state_service` is ~10 lines to delete, not extend |
| Serial → string conversion | Manual `bytes.hex()` or custom logic | `Serial.from_protocol(header.target).to_string()` | Already used in `_discover_with_packet`; `discover_devices` does it too (line 575); both must use the same conversion |
| Timeout arithmetic | Inline `time.monotonic()` scattered through the loop | `IdleDeadline` | Prevents the third drift incident (mDNS used `time.time()` until recently) |

**Key insight:** The only reason `_parse_device_state_service` exists is that `discover_devices`
was written before `_discover_with_packet` was generalised; it is now dead weight.

---

## Common Pitfalls

### Pitfall 1: Idle-timer reset semantics after dedup hoist

**What goes wrong:** When dedup moves into `_discover_with_packet`, a duplicate serial that
previously reset `last_response_time` in `discover_devices` now never reaches the reset line.
This could cause premature idle timeout if a device floods duplicate responses.

**Why it happens:** Currently `discover_devices` resets the timer unconditionally at line 606
(after `seen_serials.add`, so duplicates reset the timer). After the hoist, the dedup `continue`
fires before the `deadline.mark_response()` call.

**How to avoid:** Reset the timer on **every valid protocol response** (valid source, valid
pkt_type, valid serial), regardless of whether it is a duplicate. The dedup check then fires
after the timer reset. This matches the spirit of "idle" — the network is not idle if a device
is sending.

**Warning signs:** Tests show discovery stopping early when a device replies more than once.

### Pitfall 2: `DiscoveryResponse.port` is the broadcast port, not the device port

**What goes wrong:** After the hoist, the thin `discover_devices` wrapper receives
`DiscoveryResponse` objects where `resp.port` is `LIFX_UDP_PORT` (the broadcast port parameter),
not the device's actual UDP service port from the `StateService` payload.

**Why it happens:** `_discover_with_packet` sets `port=port` in the `DiscoveryResponse`
constructor, where `port` is the function parameter (default 56700). It has no reason to
special-case `StateService`.

**How to avoid:** The thin wrapper must extract the device port from
`resp.response_payload["port"]`, NOT `resp.port`. The `DiscoveredDevice` constructor call is:
```python
DiscoveredDevice(
    serial=resp.serial,
    ip=resp.ip,
    port=resp.response_payload["port"],   # ← from StateService, not resp.port
    response_time=resp.response_time,
    timeout=device_timeout,
    max_retries=max_retries,
)
```

**Warning signs:** All discovered devices connect on port 56700 regardless of what the device
reports (usually identical, but not guaranteed on non-standard setups).

### Pitfall 3: Async-generator cleanup — `aclose()` / `GeneratorExit` on early break

**What goes wrong:** `find_by_serial` in `api.py:887` breaks early from `discover_devices`
after the first match (no explicit loop — it returns inside the `async for`). This triggers
`aclose()` on the `discover_devices` generator, which propagates `GeneratorExit` into
`_discover_with_packet`'s inner generator. If `_discover_with_packet` has a `try/finally` around
the `UdpTransport` context, the transport closes cleanly. If the generator is abandoned without
`aclose()`, Python's GC eventually cleans it up, but the socket may linger.

**Why it happens:** Python async generators require explicit `aclose()` for deterministic
cleanup. The `async with` pattern for `UdpTransport` inside `_discover_with_packet` already
handles this correctly — `GeneratorExit` thrown into a generator inside an `async with` will
run the `__aexit__` finaliser. This is safe.

**How to avoid:** No action needed for the `UdpTransport` case — the `async with` inside
`_discover_with_packet` provides the teardown hook. The risk is if the thin `discover_devices`
wrapper has any cleanup that must run. Keep the wrapper as a trivial `async for ... yield`
pattern with no state to clean up.

**Warning signs:** `ResourceWarning: Unclosed socket` in test output.

### Pitfall 4: `StateService.unpack()` field name case

**What goes wrong:** `as_dict` returns keys derived from Python attribute names, not protocol
field names. `StateService` defines `service` and `port` (lowercase), so `as_dict` returns
`{"service": ..., "port": ...}`. Access with `resp.response_payload["port"]` (lowercase) — not
`"Port"` (protocol-style uppercase).

**Why it happens:** `Packet.as_dict` uses `dataclasses.asdict(self)` which uses Python
attribute names. The `_fields` metadata uses protocol names (`"Port"`, `"Service"`) but
`asdict` ignores those.

**How to avoid:** Use `resp.response_payload["port"]` (lowercase). Verified by reading
`packets.py:444–445`: the dataclass fields are `service: DeviceService` and `port: int`.

### Pitfall 5: mDNS bare `except Exception` — masking `LifxNetworkError`

**What goes wrong:** `discover_lifx_services` (lines 264–277) catches all exceptions on
`transport.receive()` and logs DEBUG then breaks. A genuine socket error (`LifxNetworkError`)
silently terminates discovery and looks like "no devices found". The caller (e.g.
`discover_mdns` in `api.py`) cannot distinguish a clean timeout from a network failure.

**Why it happens:** The original code was written before `MdnsTransport.receive()` was refined
to raise typed exceptions (`LifxTimeoutError` vs `LifxNetworkError`).

**How to avoid (D-08):** Split into:
```python
except LifxTimeoutError:
    break                      # clean: no more responses in idle window
except LifxNetworkError as e:
    _LOGGER.warning({...})     # or re-raise — TBD per Claude's discretion
    break
except Exception as e:
    _LOGGER.error({...}, exc_info=True)
    raise                      # unexpected — propagate
```

### Pitfall 6: `struct` import becomes unused after D-05

**What goes wrong:** After deleting `_parse_device_state_service`, the top-level `import struct`
in `discovery.py` is unused. `ruff` or `pyright` will flag this.

**How to avoid:** Remove the `import struct` line as part of the same commit that deletes
`_parse_device_state_service`.

---

## Code Examples

All examples are from direct source inspection [VERIFIED: codebase].

### StateService.unpack() usage replacing _parse_device_state_service

```python
# Source: src/lifx/protocol/packets.py:430-445, src/lifx/protocol/base.py:97
# StateService has: service: DeviceService, port: int
# _discover_with_packet already calls get_packet_class(pkt_type).unpack(payload)
# The thin wrapper extracts port from the response_payload dict:

state_service = Device.StateService.unpack(payload)  # direct form (not used in wrapper)

# In the thin wrapper context:
device_port: int = resp.response_payload["port"]      # from StateService.as_dict
```

### Thin wrapper pattern for discover_devices

```python
# Source: analysis of src/lifx/network/discovery.py
async def discover_devices(
    timeout: float = DISCOVERY_TIMEOUT,
    broadcast_address: str = "255.255.255.255",
    port: int = LIFX_UDP_PORT,
    max_response_time: float = MAX_RESPONSE_TIME,
    idle_timeout_multiplier: float = IDLE_TIMEOUT_MULTIPLIER,
    device_timeout: float = DEFAULT_REQUEST_TIMEOUT,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> AsyncGenerator[DiscoveredDevice, None]:
    async for resp in _discover_with_packet(
        DevicePackets.GetService(),
        timeout=timeout,
        broadcast_address=broadcast_address,
        port=port,
        max_response_time=max_response_time,
        idle_timeout_multiplier=idle_timeout_multiplier,
    ):
        device_port: int = resp.response_payload["port"]   # device's actual UDP port
        yield DiscoveredDevice(
            serial=resp.serial,
            ip=resp.ip,
            port=device_port,
            response_time=resp.response_time,
            timeout=device_timeout,
            max_retries=max_retries,
        )
```

### Serial validation logic (to hoist into _discover_with_packet)

```python
# Source: src/lifx/network/discovery.py:558-566
# Current location in discover_devices; moves to _discover_with_packet after serial extraction

if header.target[0] & 0x01 or header.target == b"\xff" * 8:
    _LOGGER.debug(                     # changed from WARNING to DEBUG per D-02
        {
            "class": "_discover_with_packet",
            "action": "invalid_serial",
            "serial": header.target.hex(),
            "source_ip": addr[0],
        }
    )
    continue
```

### DeprecationWarning for receive_many

```python
# Source: src/lifx/network/transport.py:282-333
# D-09: add at start of receive_many body

import warnings

async def receive_many(self, ...) -> list[...]:
    """...existing docstring...

    .. deprecated:: current
        :class:`receive_many` is deprecated and will be removed in v2.0.
        Use :meth:`receive` in a loop or :func:`~lifx.network.discovery._discover_with_packet`
        for multi-response collection.
    """
    warnings.warn(
        "UdpTransport.receive_many is deprecated and will be removed in v2.0. "
        "Use receive() in a loop or _discover_with_packet() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    # ... rest of body unchanged
```

### pytest.warns test for D-12

```python
# Source: analysis of tests/test_network/test_transport.py structure
async def test_receive_many_emits_deprecation_warning(self) -> None:
    """receive_many must emit DeprecationWarning (D-12)."""
    async with UdpTransport() as transport:
        with pytest.warns(DeprecationWarning, match="v2.0"):
            await transport.receive_many(timeout=0.1)
```

---

## Tests: What Changes and What New Coverage Is Required

### Tests targeting retired internals (D-10)

**`tests/test_network/test_discovery_errors.py`**

Current tests that must change:

| Test class | What it tests | Action |
|------------|--------------|--------|
| `TestParseDeviceStateServiceErrors` (4 tests) | `_parse_device_state_service` directly — short payload, empty payload, valid payload, extra data | **Delete** entire class — function is deleted. The payload-too-short scenario is now handled by `StateService.unpack()` raising `LifxProtocolError`; prove via the `LifxProtocolError` handling path in `_discover_with_packet` |
| `TestDiscoverySourceValidation` (3 tests) | source-ID rejection, 0xff serial rejection, multicast serial rejection | **Keep and update** — these prove DoS protection. After hoisting, they should test `_discover_with_packet` directly (currently they test `discover_devices`; either is fine since both share the path post-unification). The serial validation tests can be updated to patch `_discover_with_packet`'s transport instead of `discover_devices`. |
| `TestDiscoveryDeduplication` (1 emulator test) | dedup via `discover_devices` with emulator | **Keep** — behaviour preserved; test still valid after unification |

**`tests/test_network/test_transport.py`**

- All `receive_many` tests (9 references per grep): **keep** until actual removal in v2.0.
- Add one test: `test_receive_many_emits_deprecation_warning` (D-12).

### New tests required (D-11)

These prove the hoisted validation at the `_discover_with_packet` level:

| Test | Type | Approach |
|------|------|----------|
| Broadcast-bit serial rejected by `_discover_with_packet` | unit (mock) | Craft a `StateService` packet with multicast serial; patch `UdpTransport`; assert nothing yielded |
| 0xff serial rejected by `_discover_with_packet` | unit (mock) | Same pattern with all-0xff target |
| First-wins dedup in `_discover_with_packet` | unit (mock) | Feed two packets with same serial; assert only one `DiscoveryResponse` yielded |
| Dedup integrates with `discover_devices` wrapper | emulator | `discover_devices` against emulator; assert no duplicate `DiscoveredDevice` serials (D-11, emulator-first) |

**New `IdleDeadline` tests** (suggested location: `tests/test_network/test_utils.py` — new file):

| Test | Behaviour |
|------|-----------|
| `test_idle_deadline_overall_expires` | `remaining()` returns ≤ 0 after `timeout` seconds |
| `test_idle_deadline_idle_expires` | `remaining()` returns ≤ 0 after `idle_timeout` with no `mark_response()` |
| `test_idle_deadline_mark_response_resets_idle` | `mark_response()` extends `remaining()` beyond the idle window |
| `test_idle_deadline_overall_caps_idle` | `remaining()` never exceeds `timeout - elapsed` even after `mark_response()` |

---

## State of the Art

| Old Approach | Current Approach | Status |
|--------------|------------------|--------|
| `time.time()` in mDNS loop | `time.monotonic()` (commit `2f6404a`) | Already fixed; `IdleDeadline` must use `monotonic()` |
| Hand-rolled `struct.unpack("<BI", ...)` for StateService | `Device.StateService.unpack()` | Exists in protocol layer; `_parse_device_state_service` is the stale form |
| Separate loops with duplicated timeout arithmetic | Shared `IdleDeadline` helper | This phase |
| DoS validation only in `discover_devices` | Validation in shared generator | This phase |
| `receive_many` as a production API | Deprecated; all multi-response flows use `connection.request_stream()` | This phase (deprecation) |

**Deprecated/outdated:**
- `_parse_device_state_service`: hand-rolled struct parser superseded by `StateService.unpack()`.
  Will be deleted in this phase.
- `UdpTransport.receive_many`: confirmed zero production callers; all multizone/multi-response
  flows go through `connection.request_stream()`. Will be deprecated this phase, removed in v2.0.
- `responses` dict in `_discover_with_packet` (line 201/322): allocated and written but never
  read — write-only accumulator left over from an earlier design. Will be deleted when dedup is
  hoisted (D-04).

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `IdleDeadline.remaining()` should cache `monotonic()` to avoid double-call skew within one iteration | IdleDeadline Design | Minor: two extra syscalls per loop iteration; negligible in practice |
| A2 | `LifxNetworkError` from `MdnsTransport.receive()` should break (not propagate) with a WARNING log | Pitfall 5 | If re-raise is correct: mDNS discovery will surface errors to callers rather than silently stopping; callers must handle `LifxNetworkError` |
| A3 | `packet_size` field in `discover_devices` malformed-packet log is not worth preserving in `_discover_with_packet` | Difference table | Low: debugging value only; `addr[0]` and `reason` are more useful |

---

## Environment Availability

Step 2.6: SKIPPED (no external tools or services required — stdlib-only, zero runtime deps).

---

## Validation Architecture

`workflow.nyquist_validation` is `true` in `.planning/config.json`. Section included.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.4.2+ with pytest-asyncio 0.24.0+ |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/test_network/ -v` |
| Full suite command | `uv run --frozen pytest` |

### Phase Requirements → Test Map

| Behaviour | Test Type | Automated Command | Notes |
|-----------|-----------|-------------------|-------|
| Serial validation in `_discover_with_packet` (broadcast bit) | unit (mock) | `uv run pytest tests/test_network/test_discovery_errors.py -v -k "broadcast"` | New test per D-11 |
| Serial validation in `_discover_with_packet` (0xff) | unit (mock) | `uv run pytest tests/test_network/test_discovery_errors.py -v -k "all_ff"` | New test per D-11 |
| First-wins dedup in `_discover_with_packet` | unit (mock) | `uv run pytest tests/test_network/test_discovery_errors.py -v -k "dedup"` | New test per D-11 |
| `discover_devices` wrapper yields `DiscoveredDevice` with correct port | emulator | `uv run pytest tests/test_network/ -m emulator -v` | Existing tests prove this |
| `IdleDeadline` overall timeout | unit | `uv run pytest tests/test_network/test_utils.py -v` | New file per Wave 0 gap |
| `IdleDeadline` idle timeout | unit | `uv run pytest tests/test_network/test_utils.py -v` | New file per Wave 0 gap |
| `receive_many` DeprecationWarning | unit | `uv run pytest tests/test_network/test_transport.py -v -k "deprecation"` | New test per D-12 |
| mDNS `except LifxTimeoutError` tightening | unit (mock) | `uv run pytest tests/test_network/test_mdns/ -v` | Existing + possible new |
| No regressions across full network layer | integration (emulator) | `uv run pytest tests/test_network/ -m emulator` | All existing emulator tests |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/test_network/ -v`
- **Per wave merge:** `uv run --frozen pytest`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_network/test_utils.py` — `IdleDeadline` unit tests (covers all D-06 behaviour)
- [ ] New test methods in `tests/test_network/test_discovery_errors.py` for `_discover_with_packet`-level serial validation and dedup (D-11)
- [ ] New test method in `tests/test_network/test_transport.py` for `receive_many` `DeprecationWarning` (D-12)

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | no | — |
| V5 Input Validation | yes | Serial validation (broadcast/multicast bit check, 0xff rejection) — DoS protection for UDP broadcast responses |
| V6 Cryptography | no | — |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Spoofed UDP responses with broadcast serial | Spoofing / DoS | Reject `header.target[0] & 0x01` or `header.target == b"\xff" * 8` (D-01) |
| Source-ID mismatch (off-session responses) | Spoofing | `header.source != discovery_source → skip` (already in both loops) |
| Hostile network flooding WARNING logs | Denial of Service | Log at DEBUG only (D-02) |

**This phase strengthens the DoS protection surface** by moving serial validation from
`discover_devices` only into the shared generator, covering all callers including `find_by_label`
and the label/colour enrichment paths.

---

## Project Constraints (from CLAUDE.md)

| Directive | Impact on This Phase |
|-----------|---------------------|
| Zero runtime dependencies | `IdleDeadline` must use stdlib `time.monotonic()` only — no third-party timing libraries |
| Strict Pyright (`uv run pyright` at 0 errors) | `IdleDeadline` needs full type annotations; `discover_devices` thin wrapper return type must match existing `AsyncGenerator[DiscoveredDevice, None]`; `import struct` must be removed when `_parse_device_state_service` is deleted |
| Australian English spelling | Log message wording, docstrings, comments |
| `uv run pytest` for tests | All test commands use `uv run` |
| Structured dict-style log entries | `{"class": ..., "method": ..., "action": ...}` — DEBUG log for rejected serials must follow this pattern |
| `time.monotonic()` for all interval arithmetic | `IdleDeadline.__init__` uses `time.monotonic()`; not `time.time()` |
| Never edit generated files manually | `src/lifx/protocol/packets.py` and `src/lifx/protocol/protocol_types.py` are auto-generated — reference only, do not edit |
| If user-visible fields, never bytes | Not directly applicable to this refactor; `Serial.from_protocol(...).to_string()` already handles conversion |
| `git commit -s` with GPG signing | All commits must include sign-off and GPG signature |

---

## Open Questions

1. **`IdleDeadline.expired` property vs inline `remaining() <= 0` check in the loop**
   - What we know: the existing loops check idle and overall separately to emit distinct log
     messages; a single `expired` property merges them.
   - What's unclear: whether the planner wants to preserve two separate timeout log messages
     (easier with two properties: `idle_expired` and `overall_expired`) or simplify to one.
   - Recommendation: Expose `idle_expired` and `overall_expired` properties as well as
     `expired`; costs two extra comparisons, gains diagnostic clarity.

2. **mDNS `LifxNetworkError` handling — break or propagate?**
   - What we know: D-08 says "log distinctly or propagate"; both are acceptable.
   - What's unclear: whether callers of `discover_lifx_services` currently handle or expect
     `LifxNetworkError`.
   - Recommendation: Break with `WARNING` log. Propagating would require all callers to handle
     `LifxNetworkError`, which they do not currently do.

---

## Sources

### Primary (HIGH confidence — direct codebase inspection)
- `src/lifx/network/discovery.py` — full text read; all line numbers verified [VERIFIED: codebase]
- `src/lifx/network/utils.py` — full text read [VERIFIED: codebase]
- `src/lifx/network/transport.py` — full text read [VERIFIED: codebase]
- `src/lifx/network/mdns/discovery.py` — full text read [VERIFIED: codebase]
- `src/lifx/network/mdns/transport.py` — exception type grep [VERIFIED: codebase]
- `src/lifx/protocol/packets.py` — `StateService` class, `PACKET_REGISTRY`, `get_packet_class` [VERIFIED: codebase]
- `src/lifx/protocol/base.py` — `as_dict`, `unpack` signatures [VERIFIED: codebase]
- `src/lifx/api.py` — all `discover_devices` and `_discover_with_packet` call sites [VERIFIED: codebase]
- `src/lifx/devices/base.py` — `discover_devices` call sites at lines 1264, 1458 [VERIFIED: codebase]
- `tests/test_network/test_discovery_errors.py` — full test inventory [VERIFIED: codebase]
- `tests/test_network/test_discovery_devices.py` — emulator test patterns [VERIFIED: codebase]
- `tests/test_network/test_transport.py` — `receive_many` test line references [VERIFIED: codebase]
- `tests/conftest.py` — `emulator_port` fixture [VERIFIED: codebase]
- `.planning/codebase/ARCHITECTURE.md` — network layer structure [VERIFIED: codebase]
- `.planning/codebase/TESTING.md` — test framework and patterns [VERIFIED: codebase]

### Tertiary (LOW confidence — design proposals)
- `IdleDeadline` interface design [ASSUMED] — inferred from existing loop patterns; exact attribute names are Claude's discretion per CONTEXT.md

---

## Metadata

**Confidence breakdown:**
- Difference table (what each loop does): HIGH — verified by reading both loops line by line
- `DiscoveryResponse.port` vs device port: HIGH — verified by tracing `DiscoveryResponse` constructor call at line 317
- `StateService.as_dict` field names: HIGH — verified by reading `packets.py:444–445` and `base.py:64–66`
- `IdleDeadline` design: MEDIUM — interface is clear from the three existing patterns; exact implementation is Claude's discretion
- Test inventory: HIGH — read all relevant test files

**Research date:** 2026-06-13
**Valid until:** Indefinite (all findings from internal codebase; no external dependencies)
