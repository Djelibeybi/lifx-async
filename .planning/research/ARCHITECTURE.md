# Architecture Research

**Domain:** Thread/IPv6 integration into an existing layered async LIFX library (v2.0 milestone)
**Researched:** 2026-08-27
**Confidence:** HIGH (derived from direct reading of `main`, the `feat/ipv6-thread-support` branch at `b49400b`/`b88cdb9`/`2f884f5`, and the test suite; no external sources needed)

## Scope

This is subsequent-milestone research: the layers already exist and are mapped in
`.planning/codebase/`. Everything here is about where the NEW capability plugs in. The six
questions from the research brief are answered in order, then rolled up into a
new-vs-modified inventory and a build order.

## System Overview: what changes and where

```
┌──────────────────────────────────────────────────────────────────────────┐
│ High-Level API  src/lifx/api.py                              [MODIFIED]  │
│   discover()        → gains merged broadcast + mDNS legs                 │
│   find_by_serial()  → gains dual-leg race, first hit wins                │
│   find_by_ip()      → gains IPv6 literal path                            │
│   find_by_label()   → UNCHANGED (user decision 2026-08-27)               │
│   discover_mdns()   → UNCHANGED public surface (leg improves underneath) │
├──────────────────────────────────────────────────────────────────────────┤
│ Device Layer  src/lifx/devices/                    [lands with branch]   │
│   base.py: IPv4-only guard removed, link-local-without-scope warning     │
│   Everything else UNTOUCHED (Light, MultiZone, Matrix, Ceiling, ...)     │
├──────────────────────────────────────────────────────────────────────────┤
│ Network Layer  src/lifx/network/                                         │
│   transport.py    [branch] family follows local bind address             │
│   connection.py   [branch] binds "::" when peer IP is IPv6               │
│   discovery.py    [NEW WORK] _discover_with_packet gains family-aware    │
│                   bind derived from broadcast_address (IPv4-only today)  │
│   utils.py        [NEW WORK] single is_ipv6()/family helper              │
│   mdns/transport.py [branch] ephemeral-port legacy-unicast bind          │
│   mdns/dns.py       [branch] build_address_query(); AAAA parse on main   │
│   mdns/discovery.py [branch] _LifxRecordCache cross-packet accumulation, │
│                     PTR retransmit, follow-up A/AAAA                     │
│                     [NEW WORK] parse TXT `tm` into LifxServiceRecord     │
│   mdns/types.py     [NEW WORK] LifxServiceRecord.transport_method        │
├──────────────────────────────────────────────────────────────────────────┤
│ Animation Layer  src/lifx/animation/animator.py    [lands with branch]   │
│   frame socket family follows self._addr; nothing else changes           │
├──────────────────────────────────────────────────────────────────────────┤
│ Protocol / Effects / Theme layers                          [UNTOUCHED]   │
│   The binary codec is address-family agnostic end to end                 │
└──────────────────────────────────────────────────────────────────────────┘
```

## Q1. Where does the address family belong? (and is the branch right?)

**Verdict: the branch puts the decision in the right place.** Address family is a property
of the *peer address*, not configuration, and the branch derives it at each socket-creation
site from the address that socket will talk to (or bind to). There is no family parameter
threaded through constructors, no mode flag on `Device`, and no public API change. That is
the cleanest possible seam for a zero-dependency library whose compatibility constraint is
"additive only".

The three decision sites on the branch:

| Site | Rule | File:line (branch) |
|------|------|--------------------|
| `UdpTransport.open()` | `AF_INET6 if ":" in self._ip_address else AF_INET`, keyed off the **local bind address** | `src/lifx/network/transport.py` (~L296) |
| `DeviceConnection.open()` | `local_ip = "::" if ":" in self.ip else DEFAULT_IP_ADDRESS`, keyed off the **peer IP**, passed to `UdpTransport(ip_address=...)` | `src/lifx/network/connection.py` (~L232) |
| `Animator._send_frame` lazy socket | `AF_INET6 if ":" in self._addr[0] else AF_INET` | `src/lifx/animation/animator.py` (~L396, commit `2f884f5`) |

`Device.__init__` (`src/lifx/devices/base.py`) correctly does NOT decide anything: it only
stops rejecting `addr.version == 6` and warns on a link-local literal without a
`scope_id`. `Device.from_ip()` therefore already connects to IPv6 literals with zero
device-layer changes, which is what makes Q4 cheap.

**What the branch gets wrong or leaves ragged (fix while landing or immediately after):**

1. **The `":" in ip` heuristic is written out three times.** Extract one helper into
   `src/lifx/network/utils.py`:

   ```python
   def is_ipv6(address: str) -> bool:
       """True when *address* is an IPv6 literal (colon is illegal in IPv4)."""
       return ":" in address
   ```

   (or return `socket.AddressFamily` directly). This is not cosmetic: Q4 adds a fourth
   site in `_discover_with_packet`, and four copies of a string heuristic is how one of
   them drifts. `utils.py` is already the shared leaf for `IdleDeadline` and
   `allocate_source`, so no new module is needed.

2. **`_discover_with_packet` still binds `DEFAULT_IP_ADDRESS` ("0.0.0.0") unconditionally**
   (`src/lifx/network/discovery.py`, `UdpTransport(port=0, broadcast=True)`). This is the
   known "discover() broadcast is IPv4-only" gap and it is also exactly what blocks
   `find_by_ip()` over IPv6 (see Q4). The fix belongs here, not in `find_by_ip`.

3. **`MdnsTransport.open()` leaks the raw socket on a mid-open failure.**
   `self._socket = sock` is assigned *before* `create_datagram_endpoint(sock=sock)`; if
   endpoint creation raises `OSError`, the `except` re-raises as `LifxNetworkError` without
   closing `sock`, and `close()` early-returns because `self._transport is None`. Wrap the
   endpoint creation so the socket is closed on failure. Small, but it is a real socket
   leak on the exact error path (no multicast route) that motivates Q2's failure handling.

4. **`retransmit_delays = [1.0, 3.0]` is a local literal** in `discover_lifx_services`.
   Hoist it to a module constant read at runtime, matching the established
   `DISCOVERY_REBROADCAST_GAPS` convention in `network/discovery.py` ("read the module
   constant at runtime so tests can patch it for fast schedule-exhaustion coverage").
   Without this, the retransmit branches cost wall-clock seconds per test and the
   100% branch-coverage gate gets expensive.

5. **Landing note, not a defect:** the mDNS query stays IPv4 multicast (`224.0.0.251`,
   `AF_INET` socket in `mdns/transport.py`). This is correct: Thread devices are
   advertised by the border router, which answers IPv4 legacy-unicast queries with AAAA
   records. It does mean an IPv6-*only* host cannot discover anything; record that as a
   documented limitation, not a code path.

## Q2. Merging two discovery legs in `discover()`

### The shape: queue fan-in, not generator interleaving, and **not `asyncio.TaskGroup`**

**`asyncio.TaskGroup` is unavailable: it is Python 3.11+, and this library supports 3.10**
(`requires-python = ">=3.10"`, held for LedFx compatibility; note the CLAUDE.md line about
TaskGroup describes multi-device parallelism aspirationally, and the codebase actually uses
`asyncio.gather`/`create_task` throughout). Even on 3.11+ TaskGroup's semantics would be
wrong here: one child failing cancels its sibling, and a dead mDNS leg must never kill the
broadcast leg. Use two `asyncio.create_task` pumps feeding one `asyncio.Queue`, with
`try/finally` cancellation. This is the standard async-iterator-merge shape and needs
nothing beyond stdlib.

Merge at the **record level, not the device level**: consume
`network.discovery.discover_devices()` (yields `DiscoveredDevice`) and
`network.mdns.discovery.discover_lifx_services()` (yields `LifxServiceRecord`), and only
construct a `Device` after cross-leg dedup. Wrapping the device-level generators
(`discover_devices_mdns`, or `discover()` itself) would pay `create_device()`'s network
round trips for a serial the other leg already claimed.

Sketch (lives in `src/lifx/api.py` as a private helper; `discover()` becomes a thin loop
over it):

```python
_LegItem = tuple[str, object]  # ("bcast", DiscoveredDevice) | ("mdns", LifxServiceRecord)
_LEG_DONE = ("done", None)

async def _merged_discovery(...) -> AsyncGenerator[Device, None]:
    queue: asyncio.Queue[_LegItem] = asyncio.Queue()

    async def _pump(tag: str, agen) -> None:
        try:
            async for item in agen:
                await queue.put((tag, item))
        except LifxError as e:
            _LOGGER.warning({..., "action": "discovery_leg_failed", "leg": tag, ...})
        finally:
            await queue.put(_LEG_DONE)

    tasks = [
        asyncio.create_task(_pump("bcast", discover_devices(timeout=timeout, ...))),
        asyncio.create_task(_pump("mdns", discover_lifx_services(timeout=timeout, ...))),
    ]
    seen: set[str] = set()
    pending_legs = len(tasks)
    try:
        while pending_legs:
            tag, item = await queue.get()
            if tag == "done":
                pending_legs -= 1
                continue
            serial = item.serial          # both legs: 12-hex lowercase, same format
            if serial in seen:            # cross-leg first-wins dedup
                continue
            seen.add(serial)
            if tag == "mdns":
                device = create_device_from_record(item, ...)   # sync, registry lookup
            else:
                device = await item.create_device()             # network round trips
            if device is not None:
                yield device
    finally:
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
```

### How the contract maps onto this shape

| Existing contract element | Where it lives in the merged design |
|---------------------------|-------------------------------------|
| Overall timeout | Passed identically to both legs, which start together; network activity is bounded by `timeout` because each leg's own `IdleDeadline` enforces it. The merge layer adds no third clock. |
| Idle timeout resets on consumer resume | **Per leg, and strengthened.** The pumps consume each leg with zero delay, so consumer time can never expire a leg's idle window at all; the invariant "time we spend, not time the network spends, never counts against the idle window" holds trivially. The `mark_response()` double-reset in `_discover_with_packet` keeps working unchanged for direct callers. |
| First-wins per-serial dedup | Three tiers, all first-wins: inside `_discover_with_packet` (existing), inside `discover_lifx_services` (existing), and the cross-leg `seen` set above. Serial formats already agree (both 12-digit lowercase hex; mDNS lowercases `txt.pairs["id"]`, broadcast uses `Serial.to_string()`). |
| DoS source/serial validation | Stays inside the legs where it already is (hoisted serial/source validation in `_discover_with_packet`; TXT `id`/`p` validation plus `_MAX_ENTRIES`/AAAA/queried-target caps in `_LifxRecordCache`). The merge layer validates nothing and must not: it only sees already-validated records. |

### Timeout interaction and early termination

- **The legs' clocks do not interact.** Each leg carries its own `IdleDeadline(timeout,
  idle)`. A quiet mDNS leg going idle ends only the mDNS pump; the broadcast leg keeps its
  full window, and vice versa. The merged generator ends when *both* pumps have posted
  their `done` sentinel and the queue is drained. Worst-case wall time is `max` of the two
  legs, which is `timeout` since they share it.
- **One leg finishing early:** its pump posts `done`; `pending_legs` drops to 1; the loop
  keeps draining the survivor. No special case.
- **One leg failing outright:** the realistic failure is `MdnsTransport.open()` raising
  `LifxNetworkError` on a multicast-blocked network. The pump's `except LifxError` catches
  it, logs, posts `done`, and `discover()` degrades to exactly today's broadcast-only
  behaviour. Unexpected exceptions deliberately propagate out of `asyncio.gather` in the
  `finally` only if the caller inspects; keep the pump catch narrow (`LifxError`) so
  programming errors still surface in tests.
- **Consumer abandons the generator** (`break` inside `async for`): `GeneratorExit` lands
  in the merge generator, the `finally` cancels both pumps, cancellation propagates into
  each leg's suspended `await`, and each leg's `async with UdpTransport/MdnsTransport`
  closes its socket. This is the same cleanup path the existing generators rely on.

### One honest behaviour delta to document

Because the pumps decouple the legs from the consumer, records found near the end of the
window sit in the queue, and a slow consumer will still be handed them *after* the network
window has closed. Today's `discover()` instead silently truncates: the overall deadline
fires while the consumer works, and unread responses are lost. The new behaviour is
strictly better (devices found are devices yielded) but it is a timing-observable change
on top of the already-accepted "discover()'s timing changes for every caller" cost from
the 2026-08-27 decision. Say so in the docstring.

## Q3. `find_by_serial()` dual-path race

### Shape

Two coroutine legs, each scanning its generator for the serial and returning the raw
record (not a constructed `Device`), raced with `asyncio.wait(FIRST_COMPLETED)` in a loop.
The loop matters: a leg can complete with `None` (exhausted its window without a hit) and
the race must then keep waiting on the survivor rather than returning `None` early.

```python
async def find_by_serial(serial, ...) -> Device | None:
    serial_str = serial.replace(":", "").replace("-", "").lower()

    async def _bcast_leg() -> DiscoveredDevice | None:
        async for disc in discover_devices(timeout=timeout, ...):
            if disc.serial.lower() == serial_str:
                return disc
        return None

    async def _mdns_leg() -> LifxServiceRecord | None:
        async for record in discover_lifx_services(timeout=timeout, ...):
            if record.serial == serial_str:
                return record
        return None

    tasks: set[asyncio.Task] = {
        asyncio.create_task(_bcast_leg()),
        asyncio.create_task(_mdns_leg()),
    }
    winner: DiscoveredDevice | LifxServiceRecord | None = None
    try:
        while tasks and winner is None:
            done, tasks = await asyncio.wait(
                tasks, return_when=asyncio.FIRST_COMPLETED
            )
            for task in done:
                if task.cancelled():
                    continue
                exc = task.exception()
                if exc is not None:
                    if isinstance(exc, LifxError):
                        continue        # leg failed; the other may still win
                    raise exc
                if task.result() is not None:
                    winner = task.result()
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    if winner is None:
        return None
    if isinstance(winner, LifxServiceRecord):
        return create_device_from_record(winner, ...)
    return await winner.create_device()
```

Construct the device **after** the `finally` has cancelled and reaped the loser, so the
loser's socket is closed before `create_device()`'s round trips begin, and so a
cancellation arriving mid-construction cannot orphan the loser.

### What could leak a socket or a task, specifically

1. **Cancelling without awaiting.** `task.cancel()` alone leaves the leg suspended; the
   `CancelledError` is only delivered when the task next runs. Skip the
   `await asyncio.gather(..., return_exceptions=True)` and you get "Task was destroyed but
   it is pending" plus a `UdpTransport`/`MdnsTransport` whose `__aexit__` never ran until
   GC. The gather is the cleanup, not politeness.
2. **Unretrieved exceptions on the loser.** A loser that fails *after* the winner returns
   would log "exception was never retrieved" at GC time; `return_exceptions=True` in the
   reaping gather retrieves them.
3. **Returning a constructed `Device` from inside the leg.** If the leg itself called
   `create_device()` and was then cancelled mid-way, the temp connection inside
   `DiscoveredDevice.create_device()` is closed by its own `finally`
   (`await temp_device.connection.close()`), but the race would also sometimes construct
   two devices and drop one. Returning raw records sidesteps both.
4. **`asyncio.wait` on nothing.** When both legs finish with `None`, `tasks` empties and
   the loop exits; never call `asyncio.wait(set())`, it raises `ValueError`.
5. **Both legs answering for the same device.** Not a leak, but note the race is benign:
   whichever leg's scan hits first wins; the loser is cancelled while still inside its
   generator, whose `async with` transport closes cleanly.

Neither leg alone is sufficient (decision 2026-08-27): broadcast covers WiFi firmware that
does not advertise mDNS; mDNS covers Thread devices with no IPv4 address. Both legs get
the caller's single `timeout`; a not-found result costs the full window, same as today.

## Q4. `find_by_ip()` over IPv6

The current mechanism is a *unicast* send of a broadcast-addressed `GetService`
("targeted broadcast": `broadcast_address=ip` in `api.find_by_ip` →
`_discover_with_packet`). That trick is address-family agnostic at the protocol level; the
only reason it fails for an IPv6 literal is that `_discover_with_packet` opens
`UdpTransport(port=0, broadcast=True)` with the default `0.0.0.0` bind, producing an
`AF_INET` socket that cannot `sendto` an IPv6 destination.

**The IPv6 equivalent is the same trick over an IPv6 socket.** One change, in
`src/lifx/network/discovery.py`:

```python
local_ip = "::" if is_ipv6(broadcast_address) else DEFAULT_IP_ADDRESS
async with UdpTransport(ip_address=local_ip, port=0, broadcast=True) as transport:
```

`UdpTransport.open()` (post-branch) already selects the family from the bind address, and
`SO_BROADCAST` on an `AF_INET6` socket is a legal no-op on Linux and macOS, so
`broadcast=True` needs no conditional. Everything downstream already works:
`DiscoveryResponse.ip` carries `addr[0]` verbatim (IPv6 literal included),
`DiscoveredDevice.create_device()` builds a `Device` whose validation now accepts IPv6
(branch), and `DeviceConnection.open()` binds `::` for the v6 peer (branch).
`Device.from_ip()` connecting to an IPv6 literal was proven on hardware by
`scripts/ipv6_thread_probe.py` stage 3, so `find_by_ip()` is purely the targeted-lookup
leg, not new transport work.

Do **not** implement `find_by_ip` as a separate `from_ip()`-based code path for IPv6: that
would fork the semantics (serial learned via connection instead of via the discovery
response, different timeout behaviour, no `StateService` port confirmation) for no gain.
Fixing the bind in `_discover_with_packet` keeps one code path for both families, and it
also future-proofs targeted discovery generally (any caller passing an IPv6
`broadcast_address` to `_discover_with_packet` gets the right socket).

Two footnotes: a link-local literal with a zone (`fe80::1%en0`) passes through
`sendto` untouched and works; `find_by_label()` deliberately gains nothing (decision
2026-08-27), because it keeps the broadcast `GetLabel` trick and reaches Thread devices
through `discover()`'s new mDNS leg.

## Q5. New versus modified components

### Lands with the branch (phase "land `feat/ipv6-thread-support`")

| File | Status | Content |
|------|--------|---------|
| `src/lifx/network/transport.py` | modified | family from local bind address in `open()` |
| `src/lifx/network/connection.py` | modified | bind `::` for IPv6 peers in `open()` |
| `src/lifx/devices/base.py` | modified | accept IPv6; warn link-local without `scope_id` |
| `src/lifx/network/mdns/transport.py` | modified | ephemeral-port bind, multicast join removed |
| `src/lifx/network/mdns/dns.py` | modified | `_encode_name()`, `build_address_query()` (AAAA parsing already on `main`) |
| `src/lifx/network/mdns/discovery.py` | modified | `_LifxRecordCache`, `_pick_address()`, PTR retransmit, follow-up A/AAAA, loop rewrite |
| `src/lifx/animation/animator.py` | modified | frame-socket family follows `self._addr` |
| `scripts/ipv6_thread_probe.py` | new | three-stage hardware probe (records/ports/connect) |
| `tests/test_network/test_mdns/test_discovery.py`, `test_transport.py`, `tests/test_animation/test_animator.py` | modified | branch's own coverage |

Landing tasks beyond the rebase: fix the `MdnsTransport.open()` socket leak (Q1 item 3),
hoist `retransmit_delays` to a patchable module constant (Q1 item 4), and top up branch
coverage to the 100% branch-patch gate (the branch predates that scrutiny of these paths;
check branch partials, not just line coverage, per the codecov memory).

### New work this milestone (all additive)

| File | Change | For |
|------|--------|-----|
| `src/lifx/network/utils.py` | new function `is_ipv6()` (or `udp_family()`) | Q1 dedup of the `":" in ip` heuristic |
| `src/lifx/network/discovery.py` | modified: `_discover_with_packet` derives bind IP/family from `broadcast_address` | Q4, and closes the "broadcast leg is IPv4-only" gap |
| `src/lifx/network/mdns/types.py` | modified: `LifxServiceRecord.transport_method: int \| None = None` (keyword default keeps construction additive; frozen dataclass unaffected) | `tm` requirement (1 WiFi, 2 Thread) |
| `src/lifx/network/mdns/discovery.py` | modified: `_LifxRecordCache.resolve()` parses `txt_data.pairs.get("tm")` into the record | `tm` requirement |
| `src/lifx/api.py` | modified: `_merged_discovery()` helper + `discover()` rewired onto it; `find_by_serial()` race; `find_by_ip()` needs **no body change** once `_discover_with_packet` is family-aware. Import `discover_lifx_services`/`create_device_from_record` at module top for patchability | Q2, Q3, Q4 |
| `tests/conftest.py` | modified: emulator fixture variant bound to `::1` | Q6 |
| `tests/test_network/test_discovery.py`, `tests/test_api/*` | modified/new: family-aware bind, merged discover, race, IPv6 find_by_ip | Q6 |
| `tests/test_network/test_mdns/*` | new tests: ephemeral-port regression (its own requirement), `tm` parsing, synthetic multi-packet accumulation, follow-up A/AAAA loop path | Q6 |
| `docs/` | consumer guidance for broadcast-first integrations | DOCS requirement |

### Untouched

`src/lifx/protocol/` (codec is family-agnostic), all of `src/lifx/devices/` except
`base.py`, `src/lifx/effects/`, `src/lifx/theme/`, `src/lifx/animation/` except the
animator socket line, `src/lifx/network/message.py`, `find_by_label()` and the whole
`DeviceGroup`/grouping surface in `api.py`.

### Build order

```
Phase 1  Land the branch (rebase onto main, leak fix, constant hoist,
         coverage top-up). Everything else depends on this.
              │
      ┌───────┴────────────────────┐
Phase 2a (parallel)          Phase 2b (parallel)
mDNS leg polish:             IPv4/IPv6 plumbing:
- tm field + parsing         - utils.is_ipv6() helper, adopt at the
- ephemeral-port               three branch sites
  regression test            - _discover_with_packet family-aware bind
- synthetic multi-packet     - find_by_ip IPv6 (test-only after the
  + follow-up A/AAAA           bind change)
  loop tests                 - conftest emulator-on-::1 fixture
              │                          │
              └───────┬──────────────────┘
Phase 3  Merged discover() + find_by_serial() race in api.py
         (needs both legs' shapes final; touches one file, so keep
          the two functions in one phase)
              │
Phase 4  Docs (broadcast-first consumer guidance) +
         THREAD-01/SEED-001 hardware revalidation per device class
         (hardware-gated; closes per class or as named gap)
```

2a and 2b share no files and can run as parallel plans. Phase 3 must be serial after both
because the merge consumes the record-level generators whose signatures 2a/2b finalise
(`tm` field, family-aware `_discover_with_packet`). Phase 4's hardware leg cannot block CI
work and sits last by design (decision 2026-08-27: synthetic first, hardware later).

## Q6. Testability seams under a no-hardware, no-multicast CI

The 100% branch-patch gate means every IPv6 and multi-packet branch must be reachable
without Thread hardware and without real multicast. The seams, all of which either exist
or fall out of the recommended design:

1. **mDNS discovery loop: patched transport with a scripted receive.** The branch already
   established this: `patch("lifx.network.mdns.discovery.MdnsTransport")` plus a
   `_receive_script(*packets)` helper that yields crafted `(bytes, addr)` tuples then
   raises `LifxTimeoutError` (see branch `tests/test_network/test_mdns/test_discovery.py`).
   This reaches: multi-packet accumulation across `receive()` calls, the retransmit
   branches (after the constant hoist), the `LifxNetworkError` break, parse-error
   continue, dedup, and idle/overall expiry. The follow-up A/AAAA path is asserted by
   checking `transport.send` was called with `build_address_query("host.local")` bytes and
   then scripting the AAAA answer as the next received packet, confirming the instance
   resolves on the *second* pass.
2. **`_LifxRecordCache` directly, no transport at all.** It is a pure accumulator:
   crafted `DnsResourceRecord` lists exercise every cap branch (`_MAX_ENTRIES` 1024, the
   16-AAAA per-host cap, `pending_targets()` gating, the 64-`queried_targets` cap at loop
   level), address preference (A over AAAA, routable over link-local), the
   single-instance source-IP fallback, and misattribution protection. The branch already
   tests most of these; `tm` parsing joins this tier.
3. **IPv6 request/response end-to-end: the in-process emulator bound to `::1`.**
   `EmulatedLifxServer` passes `bind_address` straight into
   `create_datagram_endpoint(local_addr=(bind_address, port))` with no family argument
   (verified in `lifx_emulator/server.py:519`), so `bind_address="::1"` yields an IPv6
   endpoint with no emulator changes. Loopback IPv6 exists on every CI runner even when
   routed IPv6 and multicast do not. A `conftest.py` fixture variant (or a parametrised
   bind) covers: `UdpTransport` v6 family branch, `DeviceConnection` binding `::`,
   `Device.from_ip("::1", port)`, `find_by_ip("::1")` after the Q4 change, and the
   animator's v6 frame socket against a real receiving socket.
4. **Merged `discover()` and the `find_by_serial()` race: patch the legs, not the
   sockets.** Import `discover_devices` and `discover_lifx_services` at the top of
   `api.py` so tests patch `lifx.api.discover_devices` / `lifx.api.discover_lifx_services`
   with scripted async generators. That makes every merge branch cheap and deterministic:
   leg finishes early, leg raises `LifxError` at open, leg raises non-Lifx error
   (propagates), cross-leg duplicate serial (first-wins, either order),
   `create_device()` returning `None`, consumer `break` (assert both pumps cancelled via
   `try/finally` flags inside the fake generators), and the race's None-then-win loop.
   A fake generator with a `finally` that records closure is the leak detector for Q3's
   cleanup contract.
5. **Ephemeral-port regression test (its own requirement).** No multicast needed: open
   `MdnsTransport`, assert `sock.getsockname()[1] != 5353` and that no
   `IP_ADD_MEMBERSHIP` setsockopt occurred (the probe script's stage 2 measured the
   defect on hardware, 25 vs 9 devices; the unit test pins the fix).
6. **Family-selection unit tests without connecting anywhere:** open
   `UdpTransport(ip_address="::")` and assert `get_extra_info("socket").family ==
   AF_INET6`; same for the animator by inspecting `self._socket.family` after a
   `send_frame` to a scripted address.

What CI cannot cover, by design: real border-router advertising, per-AP multicast
delivery, and Thread RF behaviour. Those are Phase 4 hardware runs (two `MatrixLight`
devices on `fd00:2::/64` now, joined by a `CeilingLight`, a `MultiZoneLight`
and two single-zone `Light`s as the migrations landed), recorded per
device class with named gaps, per the FIDELITY pattern.

## Anti-Patterns for this milestone

### Anti-Pattern 1: merging at the device level

**What:** implementing `discover()` as a merge of `discover()` and `discover_mdns()`.
**Why wrong:** dedup happens after `create_device()` has already spent network round trips
on the duplicate serial, and the mDNS leg's sync construction advantage is lost.
**Instead:** merge `DiscoveredDevice`/`LifxServiceRecord` records; construct after dedup.

### Anti-Pattern 2: `asyncio.TaskGroup`

**What:** structuring the legs with `TaskGroup`.
**Why wrong:** it does not exist on Python 3.10, which this library ships for (LedFx), and
its cancel-siblings-on-failure semantics are the opposite of "one leg failing must not end
the other".
**Instead:** `create_task` pumps + `try/finally` cancel + `gather(return_exceptions=True)`.

### Anti-Pattern 3: threading a family/mode parameter through public constructors

**What:** adding `family=` or `ipv6=True` to `Device`, `DeviceConnection`, or `discover()`.
**Why wrong:** the family is fully determined by the peer address; a parameter is a second
source of truth that can contradict the first, and it breaks the additive-only constraint.
**Instead:** keep the branch's derive-at-socket-creation seam, with the one shared helper.

### Anti-Pattern 4: cancelling the race loser without reaping it

**What:** `task.cancel()` and return.
**Why wrong:** the loser's transports stay open until GC, and its exceptions are logged as
never-retrieved.
**Instead:** always `await asyncio.gather(*losers, return_exceptions=True)` in `finally`.

## Sources

- `git diff main...feat/ipv6-thread-support` and `git show b49400b b88cdb9 2f884f5` (HIGH)
- `src/lifx/network/{transport,connection,discovery,utils}.py`, `src/lifx/network/mdns/*`,
  `src/lifx/api.py`, `src/lifx/animation/animator.py`, `src/lifx/devices/base.py` on
  `main` (HIGH)
- `tests/conftest.py` and `.venv/.../lifx_emulator/server.py` for the `::1` seam (HIGH)
- `.planning/PROJECT.md` v2.0 milestone decisions of 2026-08-27 (HIGH)
- CPython docs/source: `asyncio.TaskGroup` added in 3.11; `SO_BROADCAST` legality on
  `AF_INET6` sockets verified against platform behaviour on Darwin/Linux (MEDIUM, the only
  claims not re-verified inside this repo)

---
*Architecture research for: lifx-async v2.0 Thread/IPv6 Support*
*Researched: 2026-08-27*
