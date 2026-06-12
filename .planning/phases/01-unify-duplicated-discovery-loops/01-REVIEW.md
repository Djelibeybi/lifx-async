---
phase: 01-unify-duplicated-discovery-loops
reviewed: 2026-06-12T16:09:53Z
depth: standard
files_reviewed: 8
files_reviewed_list:
  - src/lifx/network/discovery.py
  - src/lifx/network/mdns/discovery.py
  - src/lifx/network/transport.py
  - src/lifx/network/utils.py
  - tests/test_network/test_discovery_errors.py
  - tests/test_network/test_mdns/test_discovery.py
  - tests/test_network/test_transport.py
  - tests/test_network/test_utils.py
findings:
  critical: 1
  warning: 5
  info: 7
  total: 13
status: issues_found
---

# Phase 01: Code Review Report

**Reviewed:** 2026-06-12T16:09:53Z
**Depth:** standard
**Files Reviewed:** 8
**Status:** issues_found

## Summary

Reviewed the unified discovery loop (`_discover_with_packet` with hoisted serial
validation and first-wins dedup), the `discover_devices` thin wrapper, the new
`IdleDeadline` helper, the typed exception routing in mDNS discovery, and the
`receive_many` deprecation, plus the four accompanying test files. Verification
performed: all 79 in-scope tests pass, `ruff check` clean, `pyright` clean
(note: `pyproject.toml` sets `typeCheckingMode = "standard"`, not strict).
Cross-references checked: `Packet.as_dict` key casing (snake_case — line 435's
`response_payload["port"]` is correct), `STATE_TYPE` class vars on generated
Get packets, label decoding via `_decode_labels_inplace`, all callers of
`_discover_with_packet` in `api.py`, and `MdnsTransport.receive` exception
surface.

The hoisted validation and dedup are correctly implemented and well-tested at
the generator level. However, the consolidated loop has one Critical defect: a
single size-invalid UDP datagram aborts every discovery API with an uncaught
`LifxProtocolError`, directly contradicting the documented DoS-protection
contract. The two "unified" loops also retain divergent idle-reset semantics,
and the serial guard still admits the all-zeros broadcast target.

## Critical Issues

### CR-01: Uncaught LifxProtocolError from transport.receive() aborts all discovery — DoS vector

**File:** `src/lifx/network/discovery.py:258-262` (interacting with `src/lifx/network/transport.py:253-279`)
**Issue:** `UdpTransport.receive()` raises `LifxProtocolError` when a received
datagram is larger than `MAX_PACKET_SIZE` (1024) or smaller than
`MIN_PACKET_SIZE` (36). In `_discover_with_packet`, the receive call is guarded
only by `except LifxTimeoutError: break`:

```python
try:
    data, addr = await transport.receive(timeout=remaining)
    response_timestamp = time.monotonic()
except LifxTimeoutError:
    break
```

The `except LifxProtocolError` handler at line 351 covers only the
parse/unpack block — not the receive call. The exception therefore propagates
out of the generator, and no caller catches it: `discover_devices`,
`api.discover()` (api.py:782), `find_by_serial` (api.py:887), `find_by_ip`
(api.py:940), and `find_by_label` (api.py:1002) all iterate without handling
`LifxProtocolError`.

Attack/failure scenario: the GetService broadcast reveals the discovery
socket's ephemeral source port to every host on the LAN segment. Any host (or
any misbehaving device) that sends a single UDP datagram under 36 bytes to that
port during the discovery window terminates discovery with an exception and
loses all not-yet-yielded devices. This contradicts the CLAUDE.md "Discovery
DoS Protection" contract, and the test docstring in
`tests/test_network/test_discovery_errors.py:23` ("discovery continues when
receiving malformed packets") asserts behaviour the code does not exhibit for
size-invalid packets. The flaw predates this phase, but the phase made this
loop the single discovery path for the whole library, so it must be fixed here.

**Fix:**
```python
try:
    data, addr = await transport.receive(timeout=remaining)
    response_timestamp = time.monotonic()
except LifxTimeoutError:
    break
except LifxProtocolError as e:
    # Size-invalid datagram from a hostile or broken sender — skip it,
    # never abort discovery (DoS protection contract).
    _LOGGER.warning(
        {
            "class": "_discover_with_packet",
            "action": "invalid_packet_size",
            "reason": str(e),
        }
    )
    continue
```
Add a regression test that injects an undersized (<36 byte) datagram followed
by a valid StateService response and asserts the valid device is still yielded.

## Warnings

### WR-01: Serial guard accepts the all-zeros broadcast target

**File:** `src/lifx/network/discovery.py:284`
**Issue:** The hoisted guard rejects multicast serials (`header.target[0] & 0x01`)
and all-0xFF targets, but accepts `b"\x00" * 8` — the LIFX broadcast/all-devices
target, which is exactly what the discovery request itself uses (line 211) and
is never a valid device serial. A spoofed response echoing a zero target is
accepted and yields a phantom `DiscoveredDevice` with serial `"000000000000"`,
which callers may then instantiate as a `Device`. The CLAUDE.md contract says
discovery "rejects invalid/broadcast serial numbers"; the protocol's own
broadcast representation slips through. (Behaviour is inherited from the old
loop, but this phase hoisted the guard specifically to be the single
enforcement point.) Note also that the `header.target == b"\xff" * 8` clause is
unreachable as a distinct condition — `0xff & 0x01` already trips the first
clause — so the current guard effectively checks only the multicast bit.
**Fix:**
```python
if (
    header.target[0] & 0x01  # multicast bit (covers all-0xff)
    or header.target == b"\x00" * 8  # broadcast/zero target
):
    ...
    continue
```

### WR-02: Idle-reset semantics still diverge between the two "unified" loops

**File:** `src/lifx/network/discovery.py:329-339` and `src/lifx/network/mdns/discovery.py:316-337`
**Issue:** The phase rationale (Pitfall 1 / D-04) states a duplicate flood must
not cause premature idle expiry, and `_discover_with_packet` accordingly calls
`deadline.mark_response()` on every valid response *before* the dedup check.
The mDNS loop does the opposite: `mark_response()` is called only *after* a
successful `yield` of a *new* serial (line 337), so:

1. Duplicate mDNS re-announcements (normal mDNS behaviour — devices answer
   multiple times, and responses to other hosts' queries are also received on
   the multicast group) never extend the idle window. With one device
   repeatedly announcing while a slower device has not yet answered, the idle
   deadline can expire prematurely — the exact failure mode D-04 fixes in the
   broadcast loop.
2. Because `mark_response()` runs after the `yield` resumes, consumer
   processing time is excluded from the idle window in the mDNS loop but
   *included* in the broadcast loop (where the mark happens pre-yield). A slow
   consumer of `discover_devices`/`find_by_label` (e.g. `find_by_label` awaits
   `disc.create_device()` — network round trips with retries — inside the
   loop) can burn through the 4-second default idle window, after which the
   loop breaks at the `idle_expired` check *without draining valid responses
   already sitting in the receive queue*.

These are observable behavioural differences between the two loops this phase
set out to unify, and each loop has the failure mode the other one guards
against.
**Fix:** In `discover_lifx_services`, hoist `deadline.mark_response()` to run
on every valid LIFX response before the `seen_serials` dedup check (mirroring
discovery.py line 332), and add a comment matching the D-04 rationale. For the
slow-consumer hazard in `_discover_with_packet`, either drain the queue with a
zero-timeout receive before honouring `idle_expired`, or document that consumer
processing time counts against the idle window.

### WR-03: `_discover_with_packet` docstring describes a different function

**File:** `src/lifx/network/discovery.py:175-192`
**Issue:** Three inaccuracies in the docstring of the now-central shared
generator:
1. "Returns: List of DiscoveryResponse objects" — it is an `AsyncGenerator`,
   nothing is returned as a list.
2. The example uses `responses = await _discover_with_packet(...)` followed by
   a synchronous `for` loop — awaiting an async generator raises `TypeError`.
3. The example reads `resp.response_payload["Label"]` — `Packet.as_dict` uses
   dataclass `asdict()`, so keys are snake_case Python names (`label`,
   `port`), as `find_by_label` (api.py:1010) correctly uses.

Any future caller copying this example writes code that crashes. Since this
function is now the documented replacement for `receive_many` (transport.py
deprecation message), the docstring is load-bearing.
**Fix:** Change "Returns" to "Yields: DiscoveryResponse objects ...", rewrite
the example to `async for resp in _discover_with_packet(...)`, and use the
snake_case key `resp.response_payload["label"]`.

### WR-04: `DiscoveryResponse.port` documented as "Device UDP port" but holds the broadcast parameter

**File:** `src/lifx/network/discovery.py:137,144,324`
**Issue:** The dataclass docstring says `port: Device UDP port`, but
`_discover_with_packet` sets `port=port` — the broadcast destination
parameter, not anything the device reported. The wrapper `discover_devices`
explicitly works around this (lines 433-435, "Pitfall 2"), but `find_by_label`
(api.py:1027) passes `resp.port` straight into `DiscoveredDevice(port=...)`,
trusting the misleading field. For non-GetService responses the device's actual
responding port is available as `addr[1]` and is not captured anywhere.
**Fix:** Either set `port=addr[1]` (the device's actual source port) when
constructing `DiscoveryResponse` at line 324, or correct the attribute
docstring to "Port the discovery request was sent to (not necessarily the
device's service port)" so consumers cannot mistake it for device-reported
data. The first option also makes `find_by_label`'s usage correct for devices
on non-default ports.

### WR-05: Deprecation guidance points users at a private API; `deprecated` directive missing version

**File:** `src/lifx/network/transport.py:298-309`
**Issue:** Both the docstring and the `DeprecationWarning` message tell users
to migrate to `_discover_with_packet()` — an underscore-private internal
function that is not part of the public API surface and may change without
notice. External consumers of `receive_many` cannot legitimately follow this
guidance. Additionally, the Sphinx directive `.. deprecated::` requires a
version argument (`.. deprecated:: 1.x`); without it the directive renders
incorrectly.
**Fix:** Recommend the public alternatives only ("Use `receive()` in a loop,
or the public discovery API in `lifx.api`") in both the docstring and the
warning message, and supply the version in which deprecation occurred, e.g.
`.. deprecated:: 1.2`.

## Info

### IN-01: Logging code reaches into IdleDeadline private attributes

**File:** `src/lifx/network/discovery.py:239,249`; `src/lifx/network/mdns/discovery.py:236,248`
**Issue:** Debug logging computes elapsed times via `deadline._last_response`
and `deadline._start`, coupling two modules to `IdleDeadline` internals. This
passes Pyright at `standard` mode but would fail `reportPrivateUsage` under the
strict mode the project documentation claims to use.
**Fix:** Add public read-only properties to `IdleDeadline` (e.g.
`idle_elapsed`, `elapsed`) and use those in the log payloads.

### IN-02: Redundant triple expiry check at loop top; third break skips diagnostics

**File:** `src/lifx/network/discovery.py:233-256`; `src/lifx/network/mdns/discovery.py:229-256`
**Issue:** Each iteration reads `time.monotonic()` up to three times via
`idle_expired`, `overall_expired`, and `remaining()`. The `remaining <= 0`
break is reachable only when time advances between the property reads and the
`remaining()` call, and when it fires it bypasses both debug log messages, so
the exit reason is silently lost.
**Fix:** Compute `remaining = deadline.remaining()` once; if `<= 0`, branch on
`deadline.idle_expired` to choose which debug message to emit, then break.

### IN-03: Hardcoded mDNS fallback port 56700

**File:** `src/lifx/network/mdns/discovery.py:102`
**Issue:** `port = srv_data.port if srv_data else 56700` uses a magic number;
`LIFX_UDP_PORT` already exists in `lifx.const` and is imported elsewhere in the
package.
**Fix:** `port = srv_data.port if srv_data else LIFX_UDP_PORT` (add to the
existing `lifx.const` import block).

### IN-04: Untyped `list` parameter on `_extract_lifx_info`

**File:** `src/lifx/network/mdns/discovery.py:58`
**Issue:** `records: list` lacks a type argument; the docstring says it is a
list of `DnsResourceRecord`. Under standard Pyright this silently degrades to
`list[Unknown]`, losing attribute checking on `record.rtype`/`record.parsed_data`.
**Fix:** `records: list[DnsResourceRecord]` (import is already available from
`lifx.network.mdns.dns`).

### IN-05: `test_discover_idle_timeout` never exercises the idle-expiry branch

**File:** `tests/test_network/test_mdns/test_discovery.py:398-429`
**Issue:** `slow_receive` sleeps past the idle window and then raises
`LifxTimeoutError`, which is caught at mdns/discovery.py:260 and breaks the
loop immediately — the loop never returns to the top where `idle_expired`
(lines 230-240) is evaluated. The test passes regardless of whether the idle
branch exists, so the branch it is named for has no real coverage.
**Fix:** Have the mock return a valid (or ignorable) datagram after sleeping
past the idle window instead of raising, so the loop iterates again and exits
via `deadline.idle_expired`; assert on the exit (e.g. record count plus a log
capture of `"action": "idle_timeout"`).

### IN-06: `test_discovery_with_malformed_header` does not inject malformed packets

**File:** `tests/test_network/test_discovery_errors.py:22-40`
**Issue:** The test class is named `TestDiscoveryMalformedPackets` and the
docstring claims "discovery continues when receiving malformed packets", but
the test only runs a normal emulator discovery — no malformed datagram is ever
sent. It provides false confidence about exactly the behaviour CR-01 shows to
be broken for size-invalid packets.
**Fix:** Once CR-01 is fixed, send an undersized datagram to the discovery
socket mid-discovery (or mock `transport.receive` to raise
`LifxProtocolError` once) and assert that a subsequent valid response is still
yielded. Otherwise rename the test to reflect what it actually verifies.

### IN-07: receive_many tests emit seven unsuppressed DeprecationWarnings

**File:** `tests/test_network/test_transport.py:59-63,71-75,96-101,256-318,392-426`
**Issue:** Every `receive_many` test except the dedicated
`test_receive_many_emits_deprecation_warning` now triggers the new
`DeprecationWarning`, producing 7 warnings per run. If the suite ever adopts
`filterwarnings = error` (a common hardening step), all of these tests break at
once.
**Fix:** Decorate the legacy-behaviour tests with
`@pytest.mark.filterwarnings("ignore::DeprecationWarning")` (or wrap calls in
`pytest.warns(DeprecationWarning)`), keeping the single dedicated test as the
explicit assertion of the warning.

---

_Reviewed: 2026-06-12T16:09:53Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
