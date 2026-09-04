# Phase 13: Merged Discovery - Pattern Map

> **Path amendment (Plan 13-07):** Source paths in this pre-implementation
> pattern snapshot remain historical. See
> [`13-PATH-AMENDMENT.md`](13-PATH-AMENDMENT.md) for current canonical paths.

**Mapped:** 2026-08-30
**Files analysed:** 14 new/modified files and artefacts
**Analogues found:** 13 / 14

## File Classification

| New/Modified File | Role | Data Flow | Closest Analogue | Match Quality |
|---|---|---|---|---|
| `src/lifx/api.py` | service | streaming + request-response | `src/lifx/api.py:754-966` | exact, existing seam |
| `src/lifx/__init__.py` | config | transform | `src/lifx/__init__.py:10-18,89-183` | exact |
| `src/lifx/network/discovery.py` | service | streaming + request-response | `src/lifx/network/discovery.py:217-711` | exact, existing producer |
| `src/lifx/network/discovery_coordinator.py` | provider | event-driven + pub-sub + streaming | `tests/conftest.py:142-180` plus `src/lifx/network/discovery.py:217-711` | partial; no production coordinator exists |
| `src/lifx/network/mdns/discovery.py` | service | streaming + request-response | `src/lifx/network/mdns/discovery.py:772-1188` | exact, existing raw-record seam |
| `src/lifx/devices/light.py` | model | request-response + transform | `src/lifx/devices/light.py:121-186,1041-1088` | exact, existing state decoder |
| `tests/test_api/test_api_discovery.py` | test | streaming + request-response | `tests/test_api/test_api_discovery.py:416-735` | exact |
| `tests/test_network/test_discovery_coordinator.py` | test | event-driven + pub-sub | `tests/test_network/test_discovery_rebroadcast.py:278-510` plus `tests/conftest.py:142-180` | role-match |
| `tests/test_network/test_mdns/test_liveness.py` | test | request-response + streaming | `tests/test_network/test_connection.py:861-905` plus `tests/test_network/test_mdns/test_discovery.py:2060-2215` | role-match |
| `tests/test_devices/test_state_light.py` | test | request-response + transform | `tests/test_devices/test_state_light.py:16-118` | exact |
| `scripts/measure_merged_discovery.py` | utility | batch + file-I/O + streaming | `scripts/ipv6_thread_probe.py:818-991,1271-1408` | role-match |
| `tests/test_scripts/test_measure_merged_discovery.py` | test | batch + file-I/O | `tests/test_theme/test_schema.py:19-65` and privacy cases in `tests/test_scripts/test_ipv6_thread_probe.py` | role-match |
| `.planning/phases/13-merged-discovery/13-MEASUREMENTS.jsonl` | config | file-I/O + batch | `data/themes.jsonl` through `src/lifx/theme/schema.py:64-86,268-430` | data-format match |
| `.planning/phases/13-merged-discovery/13-MEASUREMENT-SUMMARY.md` | config | transform + file-I/O | None in the live codebase | no close analogue |

The last four names are planner-selected concrete placements inferred from D-13 through D-16. The upstream documents lock one mode-driven script, append-only JSONL source data, and a regenerated human-readable summary, but leave filenames to the planner.

## Pattern Assignments

### `src/lifx/api.py` (service, streaming + request-response)

**Analogue:** the existing `discover()`, `discover_mdns()`, and `find_by_serial()` implementations in the same file.

**Imports and ownership pattern** (`src/lifx/api.py:10-19`):

```python
from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from collections.abc import AsyncGenerator, Iterator, Sequence
from contextlib import aclosing
from dataclasses import dataclass
from types import TracebackType
from typing import Literal
```

Keep all imports at the top except the existing deliberate layer-breaking local mDNS import. New merged orchestration needs `asyncio.Task`, a caller-loop event queue, and explicit task ownership; it must remain Python 3.10 compatible and must not use `TaskGroup`.

**Public streaming delegate and synchronous close** (`src/lifx/api.py:822-835`):

```python
devices = discover_devices(
    timeout=timeout,
    broadcast_address=broadcast_address,
    port=port,
    max_response_time=max_response_time,
    idle_timeout_multiplier=idle_timeout_multiplier,
    device_timeout=device_timeout,
    max_retries=max_retries,
)
async with aclosing(devices):
    async for discovered in devices:
        device = await _create_discovered_device(discovered, method="discover")
        if device is not None:
            yield device
```

Copy the `aclosing()` ownership shape for every UDP and mDNS pump. For merged discovery, create both pump tasks, consume typed events, serial-deduplicate only after a source result is fully valid, and in `finally` cancel, await, and close every owned task/generator. An empty leg is a `leg_done` event, not completion of the whole merge.

**mDNS-only API remains a direct source delegate** (`src/lifx/api.py:889-900`):

```python
from lifx.network.mdns.discovery import discover_devices_mdns

devices = discover_devices_mdns(
    timeout=timeout,
    max_response_time=max_response_time,
    idle_timeout_multiplier=idle_timeout_multiplier,
    device_timeout=device_timeout,
    max_retries=max_retries,
)
async with aclosing(devices):
    async for device in devices:
        yield device
```

Keep this unverified advertisement-level enumeration as the explicit mDNS-only API. The new liveness gate belongs in the merged/default and serial-race paths, not in `discover_mdns()`.

**Serial normalisation seam** (`src/lifx/network/connection.py:128-138`):

```python
serial_obj = Serial.from_string(serial)
self._serial = serial_obj.to_string()
```

Replace the API's hand-written separator/case normalisation at `src/lifx/api.py:948-950` with the existing `Serial` value object so both source legs compare the same validated 12-hex representation.

**Construction error boundary** (`src/lifx/api.py:754-772`):

```python
try:
    return await discovered.create_device()
except (AttributeError, TypeError) as error:
    _LOGGER.error(
        {
            "module": "lifx.api",
            "method": method,
            "action": "device_construction_failed",
            "error_type": type(error).__name__,
        },
        exc_info=True,
    )
    return None
```

Do not reuse this narrow construction-isolation rule as the mDNS availability rule. D-01 has its own explicit sweep-level and candidate-level allowlists; unexpected merge/coordinator errors must fail fast after cleanup.

**Required deviation for `find_by_serial()`:** the current early return at `src/lifx/api.py:951-966` owns one generator. The new implementation must race two pumps and complete loser cancellation/reaping before device construction or return. A no-match completion from either leg must leave the other leg running.

---

### `src/lifx/__init__.py` (config, transform)

**Analogue:** current public API import and `__all__` lists.

**Import/export pattern** (`src/lifx/__init__.py:10-18,153-162`):

```python
from lifx.api import (
    DeviceGroup,
    discover,
    discover_mdns,
    find_by_ip,
    find_by_label,
    find_by_serial,
)

# High-level API
"DeviceGroup",
"discover",
"discover_mdns",
"find_by_serial",
"find_by_label",
"find_by_ip",
```

Add `discover_udp` in both places, adjacent to the other discovery enumerators. Mirror the addition in `lifx.api.__all__` (`src/lifx/api.py:1141-1150`). Do not add a `transport=` selector and do not change `find_by_ip()` or `find_by_label()` exports/signatures.

---

### `src/lifx/network/discovery.py` (service, streaming + request-response)

**Analogue:** `_discover_with_packet()` is the authoritative wire producer and `discover_devices()` is the subscriber-specific wrapper.

**Validated raw producer boundary** (`src/lifx/network/discovery.py:288-337`):

```python
if not hasattr(packet, "STATE_TYPE"):
    raise ValueError(
        f"Packet {type(packet).__name__} must have STATE_TYPE attribute"
    )

expected_response_type: int = getattr(packet, "STATE_TYPE")
seen_serials: set[str] = set()
start_time = time.monotonic()

validate_address(broadcast_address, emit_warnings=not _address_is_prevalidated)
local_bind = wildcard_for(broadcast_address)
...
async with UdpTransport(...) as transport:
    discovery_source = allocate_source()
    ...
    await transport.send(message, send_address)
    deadline = IdleDeadline(timeout, idle_timeout)
```

The coordinator must consume this generator once per compatible key. It must not recreate sending, rebroadcast timing, endpoint management, source allocation, or deadline logic.

**Validate before first-wins dedup** (`src/lifx/network/discovery.py:413-555`):

```python
if header.source != discovery_source:
    continue
if header.pkt_type != expected_response_type:
    continue
...
device_serial = Serial.from_protocol(header.target).to_string()
...
if device_serial in seen_serials:
    continue
seen_serials.add(device_serial)

yield discovery_resp
```

Share only the already accepted `DiscoveryResponse` stream. The append-only active log therefore inherits source, packet, serial, address, service-port, and first-wins validation. Append before scheduling to subscribers; register a late subscriber by scheduling the current prefix from the coordinator loop before admitting it for suffix delivery.

**Subscriber-specific construction** (`src/lifx/network/discovery.py:689-711`):

```python
responses = _discover_with_packet(...)
async with aclosing(responses):
    async for resp in responses:
        device_port: int = resp.response_payload["port"]
        yield DiscoveredDevice(
            serial=resp.serial,
            ip=resp.ip,
            port=device_port,
            response_time=resp.response_time,
            timeout=device_timeout,
            max_retries=max_retries,
        )
```

Preserve this conversion after fan-out. Never share a `DiscoveredDevice`, because `device_timeout` and `max_retries` are intentionally absent from the sweep compatibility key.

**Do not copy:** the packet-loop blanket `except Exception` at `src/lifx/network/discovery.py:602-612` is legacy low-level isolation, not an analogue for merged-leg supervision. Phase 13 D-03 requires unexpected orchestration/invariant errors to cancel all work and propagate.

---

### `src/lifx/network/discovery_coordinator.py` (provider, event-driven + pub-sub + streaming)

**Closest partial analogue:** `EmulatorRunner` demonstrates the repository's thread/event-loop shape, but there is no production active-sweep coordinator to copy verbatim.

**Thread-owned loop pattern** (`tests/conftest.py:142-180`):

```python
class EmulatorRunner:
    def __init__(self, server: EmulatedLifxServer):
        self.server = server
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._started = threading.Event()

    def _run_loop(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self.server.start())
        self._started.set()
        self._loop.run_forever()
        self._loop.run_until_complete(self.server.stop())
        self._loop.close()

    def stop(self) -> None:
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread is not None:
            self._thread.join(timeout=5.0)
```

Adapt, do not copy blindly:

- Lazily create one internal thread and loop under a short `threading.Lock`/`Event` lifecycle boundary.
- Submit registration/detach coroutines with `asyncio.run_coroutine_threadsafe()` and await them in the caller loop with `asyncio.wrap_future()`.
- Schedule each record onto its caller-loop-owned unbounded queue using `caller_loop.call_soon_threadsafe(queue.put_nowait, event)`; never touch an asyncio queue directly from the coordinator thread.
- Allocate a subscription token before submission; registration and detach must be idempotent so cancellation between submit and acknowledgement cannot create a ghost subscriber.
- On the last detach, cancel and await the producer, and acknowledge detachment only after `_discover_with_packet()` has closed its endpoint.
- On loop shutdown, run `loop.shutdown_asyncgens()` before `loop.close()`; the test fixture does not currently need this because it owns a server rather than arbitrary async generators.

**Compatibility key:** exactly `(broadcast_address, port, timeout, max_response_time, idle_timeout_multiplier)`. Exclude `device_timeout` and `max_retries`.

**Active-only state:** registry entry, append-only accepted-response log, and terminal/error state are discarded at producer completion. Current subscribers may drain already scheduled events, but a later caller must start a new sweep.

---

### `src/lifx/network/mdns/discovery.py` (service, streaming + request-response)

**Analogue:** the private raw service stream and existing construction split.

**Invocation-local stream ownership** (`src/lifx/network/mdns/discovery.py:1102-1131`):

```python
record_cache = _LifxRecordCache()
sweep = _discover_lifx_services_sweep(
    record_cache,
    timeout=timeout,
    max_response_time=max_response_time,
    idle_timeout_multiplier=idle_timeout_multiplier,
)
try:
    async with aclosing(sweep):
        async for record in sweep:
            yield record
finally:
    _LOGGER.debug(
        {
            "class": "_discover_lifx_services",
            "action": "rejection_summary",
            "rejections": [...],
        }
    )
```

Expose/reuse `_discover_lifx_services()` internally. Do not move its `_LifxRecordCache` out of the call and do not put mDNS behind the UDP coordinator.

For hermetic emulator measurement, add private `_override_mdns_service_source()` backed by a `ContextVar`. When active, `_discover_lifx_services()` owns the injected async record generator with `aclosing()` and does not construct `MdnsTransport`; when absent, the normal invocation-local sweep above is unchanged. The script enters the scope only around the exact emulator-mode `discover()` iteration using a synthetic `_LifxServiceRecord` that matches its owned loopback device. This is not a public transport selector: normal and source-specific APIs keep their signatures, and verified merged discovery still performs the real correlated GetColor liveness request against the loopback emulator.

**Explicit expected/unexpected failure split** (`src/lifx/network/mdns/discovery.py:976-1006`):

```python
try:
    data, addr = await transport.receive(timeout=max(remaining, 0.01))
except LifxTimeoutError:
    ...
    break
except LifxNetworkError as e:
    ...
    break
except Exception as e:
    ...
    raise
```

The receive-time `LifxNetworkError` is already absorbed at this live catch, so an outer generator pump cannot reconstruct it. Add private `_MdnsSweepFailure(stage, reason, error_type)` delivery at the actual transport-open/send/receive/address-follow-up catches and thread one optional sink through `_discover_lifx_services()` and `_discover_verified_devices_mdns()`. `MdnsTransport` itself logs exception text and send destinations before raising, so give it a private keyword-only detail-logging flag whose default preserves current behaviour; disable it only when the merged sink is present. Then suppress the sweep catch's legacy raw dictionary and let the merger emit exactly one D-02 DEBUG record. With no sink, preserve existing standalone `discover_mdns()` logging/propagation compatibility. Ordinary receive timeout that drives retransmission/expiry/deadline completion is not a failure event. Absorb only expected sweep/candidate exception classes, re-raise `CancelledError`, and propagate all unexpected errors after deterministic cleanup. Tests must drive the real `MdnsTransport` seams before open, on send/receive before any result, during receive after a partial record, and on address follow-up.

**Record-to-device construction fields** (`src/lifx/network/mdns/discovery.py:772-831`):

```python
product = get_product(record.product_id)
kwargs = {
    "serial": record.serial,
    "ip": record.ip,
    "port": record.port,
    "timeout": timeout,
    "max_retries": max_retries,
    "_emit_input_warnings": False,
}
...
if device is not None:
    device._set_connectivity(record.connectivity)
```

For the merged path, verify the `_LifxServiceRecord` first, then construct through the shared classifier `get_device_class_for_product()` (`src/lifx/devices/detection.py:21-64`) rather than duplicating the lattice above. Preserve the validated record's connectivity and subscriber request settings.

**Deadline/cap pattern:** create one caller-owned monotonic deadline before reading/queueing candidates. A bounded worker computes remaining time at probe start and uses `min(device_timeout, remaining)`; if no time remains, drop the candidate without starting I/O. The cap is one private named constant (research recommends 16 pending fleet confirmation), patchable in tests.

---

### `src/lifx/devices/light.py` (model, request-response + transform)

**Analogue:** `get_color()` owns all `StateColor` decoding and state mutation.

**StateColor adoption pattern** (`src/lifx/devices/light.py:147-186`):

```python
state = await self.connection.request(packets.Light.GetColor())
self._raise_if_unhandled(state)

color = HSBK.from_protocol(state.color)
power = state.power
label = state.label
self._label = label

if self._state is not None:
    self._state.power = power
    self._state.label = label
    if hasattr(self._state, "color"):
        self._state.color = color
    self._state.last_updated = time.time()

return color, power, label
```

Extract the decoding/adoption portion into one private helper that accepts a verified `StateColor` and is used by both `get_color()` and merged discovery. A newly constructed Light has `_state is None`, so add a private immutable discovery snapshot/adoption seam for label/colour/power and seed `_label`. Do not make `get_color()` or `get_power()` consult that snapshot; both methods explicitly promise fresh network I/O (`src/lifx/devices/light.py:121-125,418-455`).

**Full-state construction remains separate** (`src/lifx/devices/light.py:1065-1088`):

```python
color, power, label = color_task.result()
self._state = LightState(
    ...,
    label=label,
    power=power,
    color=color,
    last_updated=time.time(),
)
```

Do not fabricate a partial `LightState`: it requires firmware, capability, collection, and WiFi fields. The discovery snapshot must not masquerade as fully initialised state.

---

### `tests/test_api/test_api_discovery.py` (test, streaming + request-response)

**Analogue:** existing delegate-lifecycle and mDNS source tests.

**Deterministic early-close fixture** (`tests/test_api/test_api_discovery.py:473-501`):

```python
finalised = False

async def _discover_devices(*args, **kwargs):
    nonlocal finalised
    try:
        yield discovered
    finally:
        finalised = True
...
generator = discover()
assert await anext(generator) is device
await generator.aclose()
assert finalised is True
```

Copy this generator-finalisation pattern for both merged legs and `find_by_serial()` losers. Add entry-gate tests before changing `discover()` behaviour: signatures/defaults, empty sweep, stream-before-completion, public first-wins dedup, overall timeout, consumer-body exclusion, inherited source/serial validation, fresh post-completion state, and early close.

**Source-specific mDNS seam** (`tests/test_api/test_api_discovery.py:661-689`): patch `_discover_lifx_services`, yield a synthetic `_LifxServiceRecord`, and assert class, normalised serial, and connectivity. Extend the same approach for explicit `discover_udp()` source participation and merged UDP-first/mDNS-first/no-priority cases.

Required merged cases: UDP-only, mDNS-only, both empty, overlap with reversed completion order, one leg finishing empty, expected mDNS failure before/during/after a result, unexpected error fail-fast, caller cancellation, and repeated calls starting fresh mDNS work.

---

### `tests/test_network/test_discovery_coordinator.py` (test, event-driven + pub-sub)

**Analogues:** deterministic raw discovery tests and the background-loop fixture.

**Wire schedule/dedup assertion shape** (`tests/test_network/test_discovery_rebroadcast.py:281-318`):

```python
send_times: list[float] = []
...
with (
    patch("lifx.network.discovery.UdpTransport") as mock_transport_cls,
    patch("lifx.network.discovery.DISCOVERY_REBROADCAST_GAPS", (0.15,)),
    patch("lifx.network.discovery.allocate_source", return_value=known_source),
):
    ...
    responses = [
        r async for r in _discover_with_packet(
            DevicePackets.GetService(), timeout=0.8
        )
    ]

assert len(responses) == 1
assert len(send_times) == 2
```

Keep the wire producer fake below the coordinator and assert destinations, packet bytes, send count, and schedule are identical for one and N compatible subscribers. Use `threading.Event`/`Barrier` and fake producer gates, not arbitrary sleeps, for cross-loop lifecycle tests.

Required coordinator cases: compatible overlap shares; incompatible key does not; differing device settings still share but construct distinct `DiscoveredDevice` settings; late join receives prefix then suffix; slow subscriber does not block producer; non-last close returns while producer remains; last close waits cancellation and endpoint close; positive/empty/error completion is not retained; registration cancellation creates no ghost; closed caller loop detaches safely; two real OS threads running separate `asyncio.run()` loops share one sweep; coordinator thread terminates when idle.

---

### `tests/test_network/test_mdns/test_liveness.py` (test, request-response + streaming)

**Echo request analogue** (`tests/test_network/test_connection.py:861-905`):

```python
echo_request = DevicePackets.EchoRequest(
    payload=b"\x01\x02\x03\x04" + (b"\x00" * 60)
)
responses = []
async for response in conn.request_stream(echo_request):
    responses.append(response)
assert len(responses) == 1
assert isinstance(responses[0], DevicePackets.EchoResponse)
```

For non-light candidates require an exact 64-byte Echo payload match in addition to the connection's source/sequence/serial correlation.

**Recoverable vs programming-error diagnostic tests** (`tests/test_network/test_mdns/test_discovery.py:2093-2215`):

```python
assert self._summaries(caplog)[0]["rejections"] == [
    {"reason": "malformed_packet", "type": "PACKET", "count": 1}
]
assert str(error) not in repr(self._summaries(caplog)[0])
...
generator = _discover_lifx_services(timeout=0.1)
await anext(generator)
await generator.aclose()
assert len(self._summaries(caplog)) == 1
```

Copy the privacy assertion: absorbed diagnostics expose stable categories and exception type only. Add real-sweep tests whose fake `MdnsTransport` fails before open, on initial/retransmit send, on receive before a record, on receive after yielding a valid record, and on address follow-up; the injected sink receives one typed event per absorbed failure, lower transport/sweep logs expose no raw exception/target/destination text, and the post-partial case retains its accepted record. Prove normal receive timeout emits no failure. Add no-sink tests for standalone compatibility and tests that an injected `RuntimeError` propagates promptly after all probe tasks/connections close.

Required liveness cases: every supported light subclass uses GetColor; relay/button-only/non-light uses Echo only; valid StateColor seeds snapshot; `StateUnhandled` rejects an advertised light without Echo fallback; wrong Echo payload, malformed response, silence, wrong identity, queue deadline expiry, and expected connection/protocol/timeout failures drop only the candidate; concurrency never exceeds the cap; every temporary connection closes; later volatile getters still send.

---

### `tests/test_devices/test_state_light.py` (test, request-response + transform)

**Analogue:** initial-state packet fixtures at `tests/test_devices/test_state_light.py:27-75`.

```python
mock_color = packets.Light.StateColor(
    color=LightHsbk(hue=21845, saturation=65535, brightness=32768, kelvin=3500),
    power=65535,
    label="Test Light",
)
...
await light._initialize_state()
assert light._state.label == "Test Light"
assert light._state.power == 65535
```

Add focused tests for the new private adoption helper: label/colour/power decode exactly once, existing full state updates when present, a pre-state snapshot does not make `state` appear initialised, subclass state is preserved, and subsequent `get_color()`/`get_power()` calls invoke `connection.request`. Retain the existing `StateUnhandled` coverage in `tests/test_devices/test_light.py:527-557`.

---

### `scripts/measure_merged_discovery.py` (utility, batch + file-I/O + streaming)

**Analogue:** the Phase 11 operator probe's schema/CLI/privacy separation.

**Build, validate, then write** (`scripts/ipv6_thread_probe.py:818-885`):

```python
def _build_uat_record(...) -> dict[str, object]:
    return {
        "schema_version": UAT_SCHEMA_VERSION,
        ...
        "device_alias": device_alias,
        ...
    }

def _write_uat_record(record, path, *, raw_serial):
    _validate_uat_record(record, raw_serial=raw_serial)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
```

Adapt the last step to append exactly one compact JSON object plus newline per arm/round (`path.open("a", encoding="utf-8")`), never rewrite existing raw rows. Validate the complete row—including privacy—before opening for append.

**Privacy gate** (`scripts/ipv6_thread_probe.py:888-991`): recursively reject forbidden identifier keys and raw serial material, require a controlled alias grammar, and keep the private alias mapping external. Phase 13 rows may contain only stable aliases and source categories, never live address/serial/hostname/raw packet fields.

**Mode-driven CLI** (`scripts/ipv6_thread_probe.py:1320-1404`): use `argparse` closed choices and `asyncio.run(main_async(args))`. Phase 13 modes are exactly `baseline-only`, `merged-only`, and `paired`; paired execution is sequential baseline then merged in one invocation. Emulator merged mode must also enter `_override_mdns_service_source()` around the exact `discover()` call so UDP uses the owned loopback/dynamic port, mDNS consumes the matching synthetic record without opening `MdnsTransport`, and the liveness request reaches the same server.

Each raw row must retain: schema/kind/version, scenario ID, pair ID, round, exact arm, exact environment, exact quiescence, categorical confounds, `elapsed_ns`, nullable first-result nanoseconds, integer unique count, per-alias contributing sources, and revision/context fields. Use `time.monotonic_ns()` for raw elapsed values. Do not invent a regression ceiling or round away raw values.

The same script should expose a validation/summary operation or reusable functions so a validator regenerates `13-MEASUREMENT-SUMMARY.md` solely from JSONL. It must reject missing arms and incomparable scenario metadata, label `not_quiesced`/`unknown` pairs as confounded, require at least six fleet pairs for the fleet claim, and require current-revision emulator evidence independently.

For FIND-08, accept only integer `(major == 3 and 70 <= minor <= 99)` WiFi observations; compare normalised identities transiently and record only alias plus match/gap disposition. An empty eligible population is an explicit non-gating record.

---

### `tests/test_scripts/test_measure_merged_discovery.py` (test, batch + file-I/O)

**Analogues:** line-oriented JSONL schema tests and Phase 11 privacy tests.

**Line-number-preserving JSONL load** (`src/lifx/theme/schema.py:74-86`):

```python
records: list[tuple[int, dict[str, Any]]] = []
with path.open(encoding="utf-8") as handle:
    for line_number, line in enumerate(handle, start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"{path.name} line {line_number}: not valid JSON: {exc}"
            ) from exc
        records.append((line_number, record))
```

Keep line numbers in validator errors so an immutable bad row is actionable. Copy the strict required/extra-field pattern from `src/lifx/theme/schema.py:274-293`.

Required tests: append preserves earlier bytes/rows; one invocation emits baseline then merged; single modes emit only their arm; nanoseconds/counts remain integers; first-result may be null only for empty results; pair/scenario/environment metadata matches; missing/duplicate arms reject; row order does not matter; quiescence/confounds label correctly; alias/source overlap reconstructs; forbidden identifiers and identifiers hidden in strings reject before write; firmware boundaries 3.69/3.70/3.99/4.0; separator/case identity normalisation; duplicate identity observations collapse; empty eligible population remains non-gating; regenerated summary is deterministic.

---

### `.planning/phases/13-merged-discovery/13-MEASUREMENTS.jsonl` (config, file-I/O + batch)

**Analogue:** line-oriented `data/themes.jsonl` loading and strict validation (`src/lifx/theme/schema.py:64-86,268-430`).

Store one immutable object per arm/round. Do not store an aggregate as a raw row, update an earlier row, or make row order semantic. Pair by stable scenario/pair identifiers. All hardware values must be synthetic or operator-controlled aliases; this tracked file is never a destination for raw probe output.

---

### `.planning/phases/13-merged-discovery/13-MEASUREMENT-SUMMARY.md` (config, transform + file-I/O)

**No close live analogue.** Generate this file deterministically from `13-MEASUREMENTS.jsonl`; never treat it as source data. Include pair completeness, observed raw/count deltas, source contribution/overlap, quiescence/confound qualification, fleet round count, emulator revision evidence, and FIND-08 disposition. A generated summary cannot upgrade a missing fleet run or empty eligible firmware population into confirmation.

## Shared Patterns

### Python 3.10 task cancellation and reaping

**Source:** `src/lifx/devices/base.py:1912-1948`

```python
task = asyncio.ensure_future(coro)
pending.append(task)
...
for task in pending:
    if not task.done():
        task.cancel()
await asyncio.gather(*pending, return_exceptions=True)
```

**Apply to:** merged source pumps, bounded liveness workers, `find_by_serial()` legs, coordinator producer teardown. Never cancel without awaiting. Never let a fast failure remain hidden behind another leg's normal discovery deadline.

### Cancellation-resistant endpoint cleanup

**Source:** `src/lifx/network/connection.py:350-394`

```python
cleanup_task = asyncio.create_task(_finish_cleanup())
try:
    while not cleanup_task.done():
        try:
            await asyncio.shield(cleanup_task)
        except asyncio.CancelledError as error:
            if cancelled is None:
                cancelled = error
    cleanup_task.result()
finally:
    ...
if cancelled is not None:
    raise cancelled
```

**Apply to:** last-subscriber detach and temporary mDNS connection closure where caller cancellation must not interrupt resource teardown. Preserve the original cancellation and re-raise it after cleanup; never classify it as mDNS unavailability.

### Async-generator ownership

**Sources:** `src/lifx/api.py:831-835`, `src/lifx/network/mdns/discovery.py:1115-1119`, `tests/test_api/test_api_discovery.py:473-501`.

Every function that creates a source generator owns an `aclosing()` scope. Tests must observe the delegate's `finally` before the outer generator's `aclose()` or lookup return completes.

### Product-directed liveness

**Sources:** `src/lifx/devices/detection.py:21-64`, `src/lifx/devices/light.py:147-186`, `src/lifx/network/connection.py:1213-1243`.

- Classify TXT `p` with `get_product()` plus `get_device_class_for_product()`.
- Every supported Light subclass: GetColor and require StateColor; `StateUnhandled` rejects with no Echo fallback.
- Non-light: one 64-byte Echo request; require correlated EchoResponse and identical payload.
- Always close the temporary `DeviceConnection` in `finally`.

### Privacy-safe diagnostics

**Sources:** `src/lifx/network/mdns/discovery.py:1119-1131` and `tests/test_network/test_mdns/test_discovery.py:2093-2114`.

Absorbed merged-discovery DEBUG records contain stable stage, stable reason, and exception class name only. No exception text, serial, address, hostname, service instance, TXT value, packet, or raw payload. Tests should assert the injected exception message is absent from `repr()` of the structured diagnostic.

### Serial identity

**Source:** `src/lifx/protocol/models.py:49-136`.

Use `Serial.from_string(value).to_string()` once at input/merge boundaries. Do not create separate lower/case/separator algorithms for UDP, mDNS, measurement, and firmware evidence.

### Test synchronisation and portability

**Source:** `tests/conftest.py:142-180`.

Use events/barriers and bounded thread joins. Run cross-loop sharing tests in actual OS threads with separate event loops. Do not hard-code macOS interface names or rely on fixed sleeps. The Phase 12 boundary remains intact: `discover_devices()` stays UDP-only; merged broadcast+mDNS behaviour belongs in high-level `discover()`.

## No Close Analogue Found

| File | Role | Data Flow | Reason / Planner Fallback |
|---|---|---|---|
| `src/lifx/network/discovery_coordinator.py` | provider | event-driven + pub-sub + streaming | No production thread-owned asyncio coordinator exists. Combine `_discover_with_packet()` ownership with the partial background-loop fixture and the Python 3.10 bridge rules in `13-RESEARCH.md`; independently test every registration/detach/terminal race. |
| `.planning/phases/13-merged-discovery/13-MEASUREMENT-SUMMARY.md` | config | transform + file-I/O | Existing generators emit Python rather than a paired measurement report. Treat JSONL as sole source, make generation deterministic, and test the rendered summary as derived output. |

## Anti-Patterns to Reject in Plans

- Sharing `DiscoveredDevice` rather than validated `DiscoveryResponse` records.
- A registry of asyncio objects shared directly between caller loops.
- A per-loop coordinator that multiplies wire sweeps across threads.
- Bounded/backpressured subscriber queues that let a slow consumer stall the producer.
- Retaining a positive, empty, or failed sweep after producer completion.
- Extending a queued liveness candidate with a fresh full timeout.
- Using `has_color` instead of the shared device-class classifier.
- Accepting Echo by packet type without checking the exact payload.
- Constructing/returning a serial winner before loser teardown completes.
- Blanket `except Exception` degradation or swallowing `CancelledError`.
- Reconstructing a receive failure in the outer pump after `_discover_lifx_services_sweep()` already absorbed it, or logging both at the catch and merger.
- Passing only UDP loopback parameters in emulator mode while leaving the merged mDNS leg on the ambient multicast destination.
- Concurrent baseline and merged measurement arms.
- Raw identifiers, addresses, exception messages, or private mappings in tests/logs/evidence.
- Any Phase 13 retuning of discovery/retry/bandwidth/animation constants.

## Metadata

**Analogue search scope:** `src/lifx/`, `tests/`, `scripts/`, Phase 11/12 inherited planning context, and the project discovery spike skill.

**Principal files read:** `src/lifx/api.py`, `src/lifx/__init__.py`, `src/lifx/network/discovery.py`, `src/lifx/network/mdns/discovery.py`, `src/lifx/network/connection.py`, `src/lifx/devices/light.py`, `src/lifx/devices/detection.py`, `src/lifx/protocol/models.py`, `tests/conftest.py`, `tests/test_api/test_api_discovery.py`, `tests/test_network/test_discovery_rebroadcast.py`, relevant targeted ranges of the large mDNS test module, `scripts/ipv6_thread_probe.py`, and `src/lifx/theme/schema.py`.

**Pattern extraction date:** 2026-08-30

**Live-tree note:** the worktree was clean when mapping began. This file is the only workspace artefact written by the pattern-mapping task.
