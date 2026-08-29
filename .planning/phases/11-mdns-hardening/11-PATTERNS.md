# Phase 11: mDNS Hardening - Pattern Map

**Mapped:** 2026-08-28
**Files analysed:** 25 new/modified files
**Analogs found:** 25 / 25 file assignments, using 5 primary analog families

> **Authority amendment — 2026-08-28:** D-15 supersedes the earlier unlimited-address
> interpretation: exact-deduplicated A/AAAA admission is capped at 256 identities per owner
> and 1,024 per sweep, and permanent per-call overflow fails closed for selection,
> resolution, and follow-up. D-16 supersedes the preserved-public-factory interpretation:
> `_LifxServiceRecord`, `_discover_lifx_services`, and `_create_device_from_record` are
> private together with no compatibility aliases.

## Scope Guardrails

- Preserve Phase 10's `MdnsTransport` design: IPv4 multicast queries leave an OS-selected
  ephemeral port and replies return by legacy unicast. Phase 11 proves and documents that
  transport; it does not bind `5353`, join multicast membership, add another receive socket,
  or add IPv6 multicast queries.
- Keep `_LifxRecordCache`, its expiry state, follow-up ledgers, serial deduplication, and
  rejection counters per `_discover_lifx_services()` call. Do not create a process-wide or
  reusable DNS cache.
- Enforce D-15 at the same per-call boundary: exact duplicates refresh without consuming
  capacity; admit at most 256 A/AAAA identities per owner and 1,024 per sweep; reject and
  count unseen excess identities without eviction; permanently mark owner/sweep overflow;
  and refuse selection, resolution, or follow-up from incomplete state.
- Do not merge the mDNS leg into `discover()`/`find_by_serial()` (Phase 13), add family-aware
  `find_by_ip()` (Phase 12), or use connectivity to change retries, routing, bandwidth, or
  animation behaviour (Phase 14).
- Public output is `Device.connectivity: Literal["wifi", "thread"]` plus supported
  device-level discovery. D-16 keeps the raw record, low-level generator,
  record-to-device converter, retained alternative addresses, private TXT key, and any
  transport enum private in their defining modules.
- Use synthetic serials and documentation-range addresses in new tests/docs. Aggregate
  rejection diagnostics may contain only reason, record type, and count; never copy the
  existing serial/IP/hostname/value/error logging fields into that event.
- `src/lifx/network/mdns/dns.py` is an input pattern, not a planned semantic change: it
  already preserves the RR identity fields needed by the cache.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `src/lifx/network/mdns/discovery.py` | service | streaming, event-driven, request-response | same file: `_LifxRecordCache` and generator loop | exact |
| `src/lifx/network/mdns/types.py` | model | transform | same file: frozen serial-keyed record | exact |
| `src/lifx/network/mdns/transport.py` | service | streaming, file-I/O (UDP socket) | same file: lifecycle-safe ephemeral transport | exact |
| `src/lifx/network/mdns/__init__.py` | config | transform | same file: explicit imports and `__all__` | exact |
| `src/lifx/__init__.py` | config | transform | same file: top-level explicit exports | exact |
| `src/lifx/devices/base.py` | model/service | request-response | same file: keyword-only flags and getter-only properties | exact |
| `src/lifx/devices/infrared.py` | model/service | request-response | `InfraredLight.__init__` | exact |
| `src/lifx/devices/hev.py` | model/service | request-response | `InfraredLight.__init__` | exact role/flow |
| `src/lifx/devices/multizone.py` | model/service | request-response | `InfraredLight.__init__` | exact role/flow |
| `src/lifx/devices/matrix.py` | model/service | request-response | `InfraredLight.__init__` | exact role/flow |
| `src/lifx/devices/ceiling.py` | model/service | request-response | same file: positional `state_file` plus keyword-only options | exact |
| `scripts/ipv6_thread_probe.py` | utility | batch, streaming | same file: internal mDNS imports and `_collect()` | exact |
| `tests/test_network/test_mdns/test_discovery.py` | test | streaming, event-driven | same file: cache and scripted transport tests | exact |
| `tests/test_network/test_mdns/test_transport.py` | test | streaming, file-I/O | same file: real-socket lifecycle fixtures | role-match; delivery assertion is new |
| `tests/test_devices/test_base.py` | test | request-response | same file: default and keyword-only property tests | exact |
| `tests/test_api/test_api_discovery.py` | test | streaming, request-response | same file: mocked mDNS generator through public API | exact |
| `tests/test_scripts/test_ipv6_thread_probe.py` | test | batch, transform | same file: synthetic private record fixture | exact |
| `docs/api/devices.md` | config/documentation | transform | same file: `Device` API and property sections | exact |
| `docs/api/network.md` | config/documentation | transform | same file: explicit low-level API directives | exact removal target |
| `docs/api/index.md` | config/documentation | transform | same file: architecture tree and quick reference | exact removal target |
| `docs/user-guide/advanced-usage.md` | config/documentation | transform | same file: mDNS and device-property sections | exact |
| `examples/discovery_mdns.py` | utility/example | streaming, request-response | same file: supported high-level discovery example | exact |
| `AGENTS.md` | config/documentation | transform | same file: architecture inventory | exact |
| `CLAUDE.md` | config/documentation | transform | same file: architecture inventory | exact |
| `tests/test_network/test_mdns/test_discovery.py` (public-removal assertions) | test | transform | explicit export tables in both `__init__.py` files | role-match; no dedicated export-test file exists |

## Pattern Assignments

### Cache, Record Model, and Discovery Loop

**Apply to:**

- `src/lifx/network/mdns/discovery.py`
- `src/lifx/network/mdns/types.py`
- `tests/test_network/test_mdns/test_discovery.py`

**Primary analog:** `src/lifx/network/mdns/discovery.py`

**Imports and local ownership pattern** (`src/lifx/network/mdns/discovery.py:21-57`):

```python
from __future__ import annotations

import ipaddress
import logging
import time
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING

from lifx.network.mdns.transport import MdnsTransport
from lifx.network.utils import IdleDeadline

_LOGGER = logging.getLogger(__name__)
```

Keep new standard-library imports (`Counter`, dataclass helpers, typing) at module top. Keep
the cache and every ledger local to one generator invocation, as the existing generator does
(`src/lifx/network/mdns/discovery.py:353-357`):

```python
seen_serials: set[str] = set()
record_cache = _LifxRecordCache()
queried_targets: set[str] = set()
query_attempts: dict[str, int] = {}
start_time = time.monotonic()
```

**Bounded collection pattern** (`src/lifx/network/mdns/discovery.py`):

```python
_MAX_ADDRESS_RRS_PER_OWNER = 256
_MAX_ADDRESS_RRS_PER_SWEEP = 1024

# Exact duplicate identities refresh existing state. An unseen identity beyond either
# ceiling is counted without eviction and permanently marks the call incomplete.
```

Use bounded multi-value entries keyed by complete RR identity. TXT and SRV retain their
independent 16-identity ceilings. D-15 replaces the historical per-host address guidance
with the exact 256-per-owner and 1,024-per-sweep A/AAAA ceilings. Exact duplicates refresh;
unseen excess identities do not evict admitted state, set permanent per-call overflow, and
block selection, resolution, and follow-up. Keep the independent 64-target/two-attempt
follow-up ceilings and the caller deadline unchanged.

**RR identity inputs already exposed by the parser**
(`src/lifx/network/mdns/dns.py:111-139`):

```python
@dataclass
class DnsResourceRecord:
    name: str
    rtype: int
    rclass: int
    ttl: int
    rdata: bytes
    parsed_data: Any = None

    @property
    def cache_flush(self) -> bool:
        return bool(self.rclass & 0x8000)
```

Construct cache identity from lower-cased owner name, type, class with the high flush bit
masked, and raw `rdata`. A positive identical record inserts/rescues; `ttl == 0` schedules
that exact identity for expiry at `monotonic() + 1.0`. An unexpected flush bit increments
`unexpected_cache_flush` but neither replaces nor rejects the record.

**TXT conflict input** (`src/lifx/network/mdns/dns.py:219-245`):

```python
txt_data = TxtData()
# ...
txt_data.strings.append(txt_str)
if "=" in txt_str:
    key, _, value = txt_str.partition("=")
    txt_data.pairs[key] = value
```

`pairs` is last-wins. Inspect every live TXT RR's `strings` when deriving `id` candidates;
do not validate only `pairs["id"]`. Accept exactly twelve hexadecimal characters, reject
zero/all-ones/group identities, normalise the one valid unambiguous value to lowercase,
and derive connectivity with exact string comparison only:

```python
connectivity: Literal["wifi", "thread"] = (
    "thread" if txt_data.pairs.get("tm") == "2" else "wifi"
)
```

The fallback is valid behaviour, not a rejection diagnostic.

**Cross-packet accumulation and exact-once pattern**
(`src/lifx/network/mdns/discovery.py:121-173`, `175-235`):

```python
def add_packet(self, records: list, source_ip: str) -> bool:
    for record in records:
        name = record.name.lower()
        # Merge by record type into per-sweep tables.
    # Keep single-instance packet-source fallback in its own map.
    return has_lifx

def resolve(self) -> list[LifxServiceRecord]:
    for instance, txt_data in self._txt_by_instance.items():
        if instance in self._resolved_instances:
            continue
        # derive only from current live records
        # ...
        self._resolved_instances.add(instance)
        results.append(...)
```

Keep packet-source fallback separate from advertised `addresses`. Expiring/rescuing records
must not clear `_resolved_instances` or `seen_serials`; yielded async-generator values cannot
be retracted, and replay/goodbye cannot cause re-emission.

**Address retention versus selection**
(`src/lifx/network/address.py:94-110`):

```python
addr = ipaddress.ip_address(ip)
if isinstance(addr, ipaddress.IPv6Address):
    if addr.ipv4_mapped is not None:
        raise ValueError(...)
    if addr.is_link_local and addr.scope_id is None:
        raise ValueError(...)
```

Use `ipaddress.ip_address()` for syntactic admission, but do not call the public
`validate_address()` gate while accumulating: the SPEC requires an unscoped link-local
address to remain in the private address set while being ineligible for selection. Classify
selection separately: IPv4, explicit `fc00::/7` ULA, `is_global` GUA, then scoped link-local.
Apply that ordering only when D-15 state is complete; owner overflow or sweep exhaustion
must make `selected_address_for()`, resolution, and follow-up return no usable result.

**Private immutable record pattern** (`src/lifx/network/mdns/types.py:9-35`):

```python
@dataclass(frozen=True)
class LifxServiceRecord:
    serial: str
    ip: str
    port: int
    product_id: int
    firmware: str

    def __hash__(self) -> int:
        return hash(self.serial)
```

Rename to `_LifxServiceRecord` with no alias. Add unordered `addresses` (research recommends
`frozenset[str]`) and private connectivity hand-off data while retaining selected `ip` and
serial-keyed equality/deduplication. Tests compare address membership, never set iteration
order or byte ordering.

**Deadline and scheduled-wakeup pattern** (`src/lifx/network/mdns/discovery.py:409-437`):

```python
remaining = deadline.remaining()
if remaining <= 0:
    break

elapsed = time.monotonic() - start_time
if retransmit_delays:
    remaining = min(remaining, retransmit_delays[0] - elapsed)

try:
    data, addr = await transport.receive(timeout=max(remaining, 0.01))
except LifxTimeoutError:
    if retransmit_delays:
        continue
    break
```

Add the nearest goodbye expiry as another `min()` wake-up source. On timeout, distinguish
expiry work from retransmission and caller deadline expiry. Expiry processing must not call
`deadline.mark_response()` and must never extend overall/idle time.

**Follow-up query bounds** (`src/lifx/network/mdns/discovery.py:505-545`):

```python
for target in record_cache.pending_targets():
    if target in queried_targets:
        continue
    attempts = query_attempts.get(target)
    if attempts is None:
        if len(query_attempts) >= 64:
            continue
        attempts = 0
    if attempts >= 2:
        continue
    query_attempts[target] = attempts + 1
    try:
        await transport.send(build_address_query(target))
    except LifxNetworkError:
        continue
    queried_targets.add(target)
```

Copy these exact two-attempt/64-target/success-dedup semantics. The cache redesign must not
weaken them.

### Discovery Tests

**Primary analog:** `tests/test_network/test_mdns/test_discovery.py`

**Synthetic record helper and non-exhausting receive script** (lines 30-51):

```python
def _txt(serial: str = "d073d5123456", product: str = "27") -> TxtData:
    pairs = {"id": serial, "p": product, "fw": "4.112"}
    return TxtData(
        strings=[f"{k}={v}" for k, v in pairs.items() if v],
        pairs={k: v for k, v in pairs.items() if v},
    )

def _receive_script(*packets: tuple[bytes, tuple[str, int]]):
    queue = list(packets)
    async def receive(timeout: float = 5.0):
        if queue:
            return queue.pop(0)
        raise LifxTimeoutError("timeout")
    return receive
```

Extend `_txt` so tests can preserve repeated raw `id=` strings and exact `tm` spellings;
do not derive `strings` only from a dictionary for conflict tests.

**Cross-packet and exact-once assertions** (lines 274-312):

```python
cache = _LifxRecordCache()
cache.add_packet(packet1, "192.0.2.1")
assert cache.resolve() == []

assert cache.add_packet(packet2, "192.0.2.1") is False
results = cache.resolve()
assert len(results) == 1
assert cache.resolve() == []
```

Parameterise packet permutations, duplicates, empty/incomplete packets, A/AAAA sets, and
address-class choice. Use synthetic names such as `host0.local` and documentation prefixes;
do not copy live probe values.

**Deterministic clock/transport seam** (lines 1391-1408, 1420-1446):

```python
deadline = MagicMock()
deadline.idle_expired = False
deadline.overall_expired = False
deadline.remaining.return_value = 5.0

transport = AsyncMock()
transport.__aenter__ = AsyncMock(return_value=transport)
transport.__aexit__ = AsyncMock(return_value=False)
transport.send = AsyncMock()
```

Patch `time.monotonic`, `IdleDeadline`, and `MdnsTransport` to prove one-second grace,
expiry wake-up, rescue, unchanged caller deadlines, and concurrent-call isolation without
real sleeps.

**Privacy-safe aggregate logging test shape** (adapt from lines 1591-1608):

```python
with caplog.at_level("DEBUG", logger="lifx.network.mdns.discovery"):
    found = [record async for record in _discover_lifx_services(timeout=0.1)]

messages = [record.msg for record in caplog.records if isinstance(record.msg, dict)]
```

Assert exactly one aggregate summary and the locked `unexpected_cache_flush` reason. Assert
the full event key set contains only stable schema fields (action/reason/type/count or a
bounded list of those), and explicitly assert serials, addresses, hostnames, TXT values,
raw packets, hashes, and exception text are absent.

## Device Connectivity Plumbing

**Apply to:**

- `src/lifx/devices/base.py`
- `src/lifx/devices/{infrared,hev,multizone,matrix,ceiling}.py`
- `tests/test_devices/test_base.py`
- `tests/test_network/test_mdns/test_discovery.py`
- `tests/test_api/test_api_discovery.py`

**Base constructor pattern** (`src/lifx/devices/base.py:435-515`):

```python
def __init__(
    self,
    serial: str,
    ip: str,
    port: int = LIFX_UDP_PORT,
    timeout: float = DEFAULT_REQUEST_TIMEOUT,
    max_retries: int = DEFAULT_MAX_RETRIES,
    *,
    fetch_wifi_info: bool = False,
    fetch_ambient_light: bool = False,
) -> None:
    # validation...
    self.serial = serial_obj.to_string()
    self.ip = ip
    self.port = port
```

`Literal` is already imported at `src/lifx/devices/base.py:12`. Add connectivity after the
`*`, default it to `"wifi"`, store it privately, and expose a getter-only property. Follow
the existing read-only property shape (`src/lifx/devices/base.py:2220-2229`):

```python
@property
def version(self) -> DeviceVersion | None:
    """Get cached version if available."""
    return self._version
```

Do not infer connectivity from address family. `_create_device_from_record()` passes the
private record value; all non-mDNS constructors keep the default.

**Explicit subclass forwarding pattern** (`src/lifx/devices/infrared.py:88-113`):

```python
def __init__(
    self,
    serial: str,
    ip: str,
    port: int = LIFX_UDP_PORT,
    timeout: float = DEFAULT_REQUEST_TIMEOUT,
    max_retries: int = DEFAULT_MAX_RETRIES,
    *,
    fetch_wifi_info: bool = False,
    fetch_ambient_light: bool = False,
) -> None:
    super().__init__(
        serial,
        ip,
        port,
        timeout,
        max_retries,
        fetch_wifi_info=fetch_wifi_info,
        fetch_ambient_light=fetch_ambient_light,
    )
```

Apply the same typed keyword and forwarding to HEV, infrared, multizone, and matrix. Do not
replace explicit signatures with `**kwargs`.

**Ceiling positional-compatibility pattern** (`src/lifx/devices/ceiling.py:356-396`):

```python
def __init__(
    self,
    serial: str,
    ip: str,
    port: int = LIFX_UDP_PORT,
    timeout: float = DEFAULT_REQUEST_TIMEOUT,
    max_retries: int = DEFAULT_MAX_RETRIES,
    state_file: str | None = None,
    *,
    fetch_wifi_info: bool = False,
    fetch_ambient_light: bool = False,
):
    super().__init__(..., fetch_wifi_info=fetch_wifi_info,
                     fetch_ambient_light=fetch_ambient_light)
```

Keep `state_file` in its current positional slot and place connectivity after `*`.

**Default/keyword-only test pattern** (`tests/test_devices/test_base.py:29-57`):

```python
with pytest.raises(TypeError):
    Device("d073d5010203", "192.0.2.1", 56700, 5.0, 3, True)

device = Device(serial="d073d5010203", ip="192.0.2.1")
assert device.fetch_wifi_info is False
```

Add direct default and explicit literal tests. In factory tests, parameterise all product
paths already represented at `tests/test_network/test_mdns/test_discovery.py:315-423` and
assert each resulting specialised device retains record connectivity.

**Public API propagation test pattern** (`tests/test_api/test_api_discovery.py:415-441`):

```python
async def mock_discover_services(*args, **kwargs):
    yield mock_record

with patch(
    "lifx.network.mdns.discovery.discover_lifx_services",
    side_effect=mock_discover_services,
):
    devices = [device async for device in discover_mdns(timeout=0.1)]
```

Rename patch targets to the private generator and assert public `discover_mdns()` yields a
device with the expected connectivity. Keep `discover()` unchanged and WiFi-defaulted.

## Legacy-Unicast Transport Proof

**Apply to:**

- `src/lifx/network/mdns/transport.py` (docstrings only)
- `tests/test_network/test_mdns/test_transport.py`

**Transport behaviour to preserve** (`src/lifx/network/mdns/transport.py:94-130`):

```python
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind(("", 0))
sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
sock.setblocking(False)
datagram_transport, _ = await loop.create_datagram_endpoint(
    lambda: protocol,
    sock=sock,
)
```

The current mocked bind assertion (`tests/test_network/test_mdns/test_transport.py:168-196`)
remains useful but does not satisfy MDNS-01. Add a separate real loopback test that keeps
the actual `MdnsTransport` open, reads `transport._socket.getsockname()[1]`, asserts the
range and `!= 5353`, sends one synthetic datagram from a second IPv4 UDP socket to
`("127.0.0.1", port)`, and awaits `transport.receive()`. Assert payload and sender address;
never probe/free/rebind a port and never join multicast membership.

Use the existing async-context-manager cleanup shape
(`tests/test_network/test_mdns/test_transport.py:224-258`) so the endpoint is released even
when an assertion fails. Keep platform skips limited to inability to create/bind IPv4
loopback; do not fall back to a daemon, live network, or hardware.

Update internal docstrings from the already-correct module overview
(`src/lifx/network/mdns/transport.py:1-14`) and state all limits: IPv4 multicast query,
ephemeral source, legacy-unicast reply, no membership, no unsolicited announcements,
cache-flush inapplicable on this path, and cache state scoped to one discovery call.

## Private API, Exports, and Internal Consumers

**Apply to:**

- `src/lifx/network/mdns/discovery.py`
- `src/lifx/network/mdns/types.py`
- `src/lifx/network/mdns/__init__.py`
- `src/lifx/__init__.py`
- `scripts/ipv6_thread_probe.py`
- `tests/test_scripts/test_ipv6_thread_probe.py`
- mDNS/API tests

**Explicit private-surface pattern** (`src/lifx/network/mdns/__init__.py` and defining
modules):

```python
from lifx.network.mdns.discovery import discover_devices_mdns

__all__ = [
    "discover_devices_mdns",
    # ... DNS and transport primitives
]

# Internal consumers import private names directly from their defining modules.
from lifx.network.mdns.discovery import (
    _create_device_from_record,
    _discover_lifx_services,
)
from lifx.network.mdns.types import _LifxServiceRecord
```

Remove the low-level record/generator/converter imports and `__all__` entries from both
package levels. D-16 permits no aliases. Internal implementation, scripts, and tests import
`_LifxServiceRecord`, `_discover_lifx_services`, and `_create_device_from_record` directly
from their defining modules; supported callers use device-level discovery.

**Internal script migration pattern** (`scripts/ipv6_thread_probe.py:75-90`, `463-468`):

```python
from lifx.network.mdns.discovery import (
    _LifxRecordCache,
    _create_device_from_record,
    _discover_lifx_services,
    _pick_address,
)
from lifx.network.mdns.types import _LifxServiceRecord

async def _collect(timeout: float) -> list[_LifxServiceRecord]:
    records: list[_LifxServiceRecord] = []
    async for record in _discover_lifx_services(timeout=timeout):
        records.append(record)
    return records
```

This is an internal consumer, so a direct private import is intentional. Rename types,
annotations, patch targets, and the script test's `make_record()` fixture mechanically;
do not turn the record public again for script convenience. Preserve the probe's privacy
warning and never run it as Phase 11 validation.

Add public-removal assertions alongside mDNS discovery tests: old names absent from
`lifx.__all__`, absent as `lifx` attributes, and absent from `lifx.network.mdns.__all__`.
Also assert the underscored replacements are not exported. No dedicated export-test analog
exists, so follow the project's direct import/assert style rather than creating compatibility
shims.

## Documentation and Example Migration

**Apply to:**

- `docs/api/devices.md`
- `docs/api/network.md`
- `docs/api/index.md`
- `docs/user-guide/advanced-usage.md`
- `examples/discovery_mdns.py`
- `AGENTS.md`
- `CLAUDE.md`

**Public device documentation pattern** (`docs/api/devices.md:129-140`, `343-364`):

```markdown
## Base Device

The `Device` class provides common operations available on all LIFX devices.

::: lifx.devices.base.Device
    options:
      filters:
        - "!^_"

## Device Properties
```

Document `Device.connectivity` in the device-property section and in the mDNS high-level
guide. State only that devices positively reported as Thread are `"thread"` and all other
construction/discovery outcomes are `"wifi"`; do not expose or expand the private wire-key
abbreviation.

**Removal targets:**

- Delete the low-level block in `docs/api/network.md:21-31`.
- Remove the raw-record architecture/quick-reference entries in
  `docs/api/index.md:32-36` and `90-97`.
- Remove `docs/user-guide/advanced-usage.md:61-74` and the raw-data row at line 125; retain
  and update the supported `discover_mdns()` example at lines 40-59.
- Delete `discover_raw_records()` and its invocation from
  `examples/discovery_mdns.py:53-72`; show `device.connectivity` in the high-level example.
- Update the mDNS architecture bullets in `AGENTS.md:157-162` and
  `CLAUDE.md:138-143` to private terminology and accurate legacy-unicast wording.

Do not edit `docs/changelog.md`; it is generated release history. Do not rewrite historical
`.planning` references.

## Shared Patterns

### Error Handling

**Source:** `src/lifx/network/mdns/discovery.py:429-456`

- `LifxTimeoutError` is normal receive-loop control flow.
- `LifxNetworkError` terminates the sweep cleanly.
- Unexpected transport exceptions are logged and re-raised.
- Semantic record rejection does not abort the sweep; it increments a bounded aggregate
  counter and continues.

Do not catch constructor defects as invalid input. Existing tests explicitly require an
unexpected `ValueError` from `_create_device_from_record()` to propagate
(`tests/test_network/test_mdns/test_discovery.py:1049-1071`).

### Logging and Privacy

**Source shape:** module-level `_LOGGER` plus dictionary messages in
`src/lifx/network/mdns/discovery.py:363-371`.

Use one final `DEBUG` aggregate per sweep. Sort reason/type entries for stable tests, but do
not make address-set ordering a contract. The only locked reason name is
`unexpected_cache_flush`; the planner must choose and freeze any additional vocabulary.
Existing per-device `device_found` and parse-error logs include identifiers
(`src/lifx/network/mdns/discovery.py:491-500`, `547-555`) and therefore are not templates
for the new rejection summary.

### Validation Layering

1. DNS parser: preserve wire facts (`ttl`, `rclass`, `rdata`, parsed value).
2. Per-sweep cache: bounded syntactic address admission, exact TXT identity validation,
   conflict, expiry/rescue, D-15 overflow state, complete-state class selection, and
   rejection counts.
3. Device boundary: retain `validate_address(record.ip)` as the final selected-address gate.

This layering is required to retain-but-not-select unscoped link-local addresses.

### Test Evidence

- Use direct cache unit tests for RR identity, validation, address membership, goodbye, and
  rescue.
- Pin D-15 with
  `TestLifxRecordCacheBounds::test_address_owner_overflow_fails_closed_without_selecting_a_subset`
  and `TestLifxRecordCacheBounds::test_sweep_address_budget_cannot_be_bypassed_across_owners`.
- Pin D-16 with
  `TestPhase11SurfaceContract::test_record_to_device_factory_is_internal_with_its_record_type`;
  it is the structured package-surface analogue and must keep the converter private.
- Use scripted generator tests for packet permutations, timeout wake-ups, follow-up sends,
  concurrent call isolation, aggregate diagnostics, and exact-once emission.
- Use one real loopback datagram test only for the OS-selected transport port.
- Do not use live hardware, mDNS daemons, multicast membership, or probe output in Phase 11.

## No Exact Analog Found

| Behaviour | Planned File | Reason / Planner Guidance |
|---|---|---|
| Timed multi-value RR cache with exact goodbye/rescue | `src/lifx/network/mdns/discovery.py` | Current cache is bounded but last-wins and untimed. Build on its per-sweep ownership and bounds plus `DnsResourceRecord` identity fields; use `11-RESEARCH.md` expiry scheduling. |
| Real ephemeral-port legacy-unicast receipt test | `tests/test_network/test_mdns/test_transport.py` | Existing test only mocks `bind(("", 0))`. Use the already-open real socket and a second loopback sender; do not use the free-port fixture because that introduces a probe/free/rebind race. |
| Dedicated public-export removal test | `tests/test_network/test_mdns/test_discovery.py` | No existing `__all__` test module was found. Add direct negative assertions near mDNS tests, without aliases. |

## Metadata

**Primary analog families:** mDNS cache/generator; DNS RR parser; device constructor lattice;
scripted discovery tests; lifecycle-safe UDP transport tests.

**Analog search scope:** `src/lifx/network/mdns`, `src/lifx/network/address.py`,
`src/lifx/devices`, `tests/test_network/test_mdns`, `tests/test_devices`, `tests/test_api`,
`tests/test_scripts`, `scripts`, `docs`, `examples`, `AGENTS.md`, and `CLAUDE.md`.

**Pattern extraction date:** 2026-08-28

**Pattern decisions preserved:** Phase 10/11 boundary; D-16 one-way private record,
generator, and converter removal; exact connectivity literals; unordered admitted address
membership; D-15 exact 256-per-owner and 1,024-per-sweep ceilings with permanent per-call
overflow and fail-closed selection/resolution/follow-up; IPv4/ULA/GUA/scoped-link-local
selection classes for complete state; strict serial validation; one-second goodbye
grace/rescue; ignored legacy-unicast cache-flush semantics with
`unexpected_cache_flush`; two-attempt/64-target follow-up bounds; aggregate privacy-safe
diagnostics.
