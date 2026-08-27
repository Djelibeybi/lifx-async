# Pitfalls Research

**Domain:** Adding Thread/IPv6 transport and merged mDNS discovery to a mature IPv4-only async LIFX library
**Researched:** 2026-08-27
**Confidence:** HIGH for codebase-specific findings (read from source and the `feat/ipv6-thread-support` diff); HIGH for RFC 6762 claims; MEDIUM for Thread-mesh behaviour not yet measured on this fleet

This document is organised around the six failure areas the milestone must survive, followed by
an audit of pitfalls the existing `feat/ipv6-thread-support` branch has already fallen into or
already fixed. Phase names refer to the natural v2.0 phase shapes: **Land** (land the branch),
**Harden** (mDNS validation + synthetic tests + ephemeral-port regression), **Merge** (merged
`discover()` / `find_by_serial()` / `find_by_ip()`), **Revalidate** (SEED-001 per-class hardware
work), **Compat** (before/after measurement + consumer docs).

## Critical Pitfalls

### Pitfall 1: IPv6 send failures are silent by design, so a bad address costs 16 s instead of raising

**What goes wrong:**
On an unconnected datagram socket, asyncio routes *every* `OSError` from `sendto` to
`error_received`, and `error_received` deliberately never tears the endpoint down
(`_FATAL_SOCKET_ERRNOS` in `network/transport.py` is only `EBADF`/`ENOTSOCK`; the module
docstring documents this contract). That design is correct for peer-unreachable storms, but it
means an *address-shaped* error behaves identically to a dead device:

- Sending to a link-local IPv6 literal without a scope ID (`fe80::...` with no `%en0`) fails
  `EINVAL`/`ENETUNREACH` inside `sock.sendto` → swallowed → the request retries on the full
  `REQUEST_RETRANSMIT_GAPS` schedule and surfaces as `LifxTimeoutError` after 16 s.
- Sending an IPv6 literal from an `AF_INET` socket raises `socket.gaierror`, which is an
  `OSError` subclass, so asyncio's `sendto` path swallows it the same way. This is exactly why
  `find_by_ip("fdc6:...")` today returns `None` after a full silent 15 s sweep rather than
  raising "wrong address family".

**Why it happens:**
The v1.1 work correctly hardened the transport so destination errors never kill the socket.
Nobody revisited that rule for the new class of *local configuration* errors IPv6 introduces,
which are permanent, not transient, and deserve a fast loud failure.

**How to avoid:**
Validate addresses at construction time, before they reach a socket. `Device.__init__` already
parses with `ipaddress.ip_address()`; the branch downgraded the IPv6 rejection to a `WARNING`
log for bare link-local (see Branch Audit finding B2), which recreates the silent-timeout path.
Make bare link-local without `scope_id` a `ValueError` (Python ≥3.9 parses `%zone` into
`IPv6Address.scope_id`), and make `find_by_ip` raise or route by family instead of feeding an
IPv6 literal to an `AF_INET` broadcast socket. Add a test that asserts the failure is immediate
and typed, not a timeout.

**Warning signs:**
A "device not found" report where the log shows `error_received` with `errno EINVAL` or a
`gaierror` string; any 16 s wall time on an operation whose address was wrong from the start.

**Phase to address:** Land (fix B2), Merge (family-aware `find_by_ip`).

---

### Pitfall 2: The socket family follows the *local bind*, but callers think in terms of the *target*

**What goes wrong:**
The branch's `UdpTransport` chooses `AF_INET6` when the **local bind address** contains a colon
(`transport.py`: `family = socket.AF_INET6 if ":" in self._ip_address else socket.AF_INET`).
`DeviceConnection._open` knows the contract and maps the peer IP to a local bind of `"::"` or
`"0.0.0.0"`. But `_discover_with_packet` still opens `UdpTransport(port=0, broadcast=True)` with
the default IPv4 bind, so any future call site that passes an IPv6 *target* without also passing
an IPv6 *local* address gets the Pitfall-1 silent gaierror. The contract lives in the caller's
head, not the type system.

**Why it happens:**
Family-follows-bind is the minimal diff onto an API whose only address parameter used to be
implicit. Each new call site must independently remember the mapping.

**How to avoid:**
Centralise the mapping once: either derive family from the *destination* at `send()`/open time
(a `UdpTransport.for_peer(ip)` constructor), or assert at `send()` that the destination family
matches the socket family and raise `LifxNetworkError` immediately. One assertion converts every
future mismatch from a 16 s timeout into a unit-test failure. Note also there is no IPv6
equivalent of `255.255.255.255`: the "broadcast leg" is structurally IPv4-only, which is fine,
but means `find_by_ip` with a v6 literal must take the unicast-GetService path over an
`AF_INET6` socket, not the broadcast path.

**Warning signs:**
Any new `UdpTransport(...)` call site constructed from a target IP without touching
`ip_address=`; `find_by_ip` returning `None` for an address `ping6` can reach.

**Phase to address:** Land (add the send-time family assertion), Merge (`find_by_ip` IPv6 leg).

---

### Pitfall 3: "One device, one address" is false on Thread; ordering-dependent address selection is untested

**What goes wrong:**
A Thread device registers multiple AAAA records via SRP: typically one address per on-link
prefix the border router advertises (OMR ULA, possibly a GUA if the LAN has global IPv6, and
with multiple border routers potentially one OMR address per BR). The branch's `_pick_address`
prefers "routable over link-local" but then returns `routable[0]`, i.e. **packet arrival
order**. Which of several `fd..`/`2xxx:` addresses is actually reachable from the host is not a
property the code checks. This fleet already demonstrates two coexisting ULA prefixes
(`fd00:2::` Thread OMR vs `fd00:3::` WiFi), so "any fd00::/7 address is
equally reachable" is already false on this network. The Thread OMR prefix is also not
stable: it is auto-generated and re-derived whenever the border router re-forms the mesh,
and this fleet moved from `fd00:1::` to `fd00:2::` between 2026-08-27 and
2026-08-28. Any cache, allow-list or heuristic keyed on the prefix rather than the serial
silently stops matching the moment that happens. GUA preference is also a trap: residential
GUA prefixes rotate with the ISP, ULAs are stable, so for local control ULA-over-GUA is the
right order and generic "prefer global" logic is wrong here.

**Why it happens:**
Two Thread devices behind one border router each currently advertise exactly one usable
address, so `routable[0]` happens to work, which is precisely the v1.2 product-invariance
failure mode: proven on the hardware at hand, assumed for the topology to come.

**How to avoid:**
Make the preference order explicit and tested: ULA (fc00::/7) > GUA > link-local-with-scope,
deterministic within a class (e.g. lexicographic) so runs are reproducible. Keep *all* learned
addresses on `LifxServiceRecord` (a `addresses: tuple[str, ...]` field) so a connect failure
can fall back rather than dead-ending on one choice. The probe's stage 3 (`connect`) already
separates "wrong address chosen" from "device didn't answer"; run it whenever a second border
router or a GUA prefix appears on the network.

**Warning signs:**
`ipv6_thread_probe.py --stage connect` reporting FAIL on an address while another AAAA for the
same host works; discovery results whose chosen address changes between runs.

**Phase to address:** Harden (explicit ordering + multi-address record, synthetic tests),
Revalidate (re-run stage 3 when topology grows).

---

### Pitfall 4: Sharing 5353 with the system mDNS daemon steals replies; but the ephemeral-port fix silently gave up multicast reception

**What goes wrong:**
Two coupled failure modes, one measured and fixed, one introduced by the fix:

1. **The measured defect.** Binding 5353 with `SO_REUSEPORT` alongside mDNSResponder/Avahi
   means legacy-unicast replies are delivered to *one* of the sharing sockets, usually the
   daemon's: measured 9 devices found on 5353 vs 25 on an ephemeral port. Per RFC 6762 §6.7 a
   query from a port other than 5353 is a legacy unicast query and responders MUST reply
   unicast to the querier's source port, which is why the ephemeral bind works.
2. **The regression risk.** The branch's `MdnsTransport.open()` now binds ephemeral and
   **never joins the multicast group at all** (`IP_ADD_MEMBERSHIP` deleted). A responder that
   ignores §6.7 and answers only to 224.0.0.251:5353 is now invisible to the library. The
   25-device measurement proves the fleet's mDNS-capable WiFi devices answer unicast; it does
   not prove all future firmware or all border routers do.

**Why it happens:**
The unicast-stealing bug and multicast reception pull in opposite directions on one socket; the
branch resolved the tension by dropping one side without recording the trade.

**How to avoid:**
Ship the ephemeral bind (it is what the evidence supports) but (a) regression-test it in its
own right, as PROJECT.md already requires: a test that asserts the query socket's local port is
not 5353 and that a synthetic unicast reply to that port is received; (b) add a probe stage
comparing "ephemeral only" vs "ephemeral + a second receive-only socket joined to the group"
on the production fleet, so the multicast-only-responder population is measured, not assumed to
be zero; (c) fix the stale docstrings in `mdns/transport.py` that still claim the socket "joins
the mDNS multicast group" (Branch Audit B4).

**Warning signs:**
`dns-sd -B _lifx._udp` (which uses mDNSResponder's cache and multicast) listing a device the
library never yields; device counts that drop when a host firewall starts blocking inbound
unicast UDP to ephemeral ports.

**Phase to address:** Harden (regression test + probe measurement + doc fix).

---

### Pitfall 5: mDNS record accumulation without TTL, cache-flush, or goodbye handling

**What goes wrong:**
`_LifxRecordCache` accumulates records for the whole discovery window and ignores
`DnsResourceRecord.ttl` and the `cache_flush` property entirely (`dns.py` parses the bit;
nothing reads it). Three consequences:

- A goodbye packet (RFC 6762 §10.1, TTL=0) is treated as a live record, and a TTL=0 AAAA is
  appended to `_aaaa_by_host` like any other.
- A cache-flush AAAA (§10.2), which means "replace all previous records of this name/type",
  is *appended* alongside the stale address it was meant to flush; combined with Pitfall 3's
  `routable[0]`, the stale address stays first and keeps winning.
- Legacy unicast responses carry TTL ≤ 10 s (§6.7); records held for a 15 s window can be
  expired the moment they are used.

Inside one 15 s sweep this is mostly harmless. It stops being harmless the moment the merged
`discover()` runs periodically (LedFx re-scans) against a Thread device that re-attached and
changed address mid-window, or when this cache is ever promoted to a longer-lived structure.

**Why it happens:**
The cache was built to solve cross-packet assembly (which it does); mDNS cache semantics were
out of scope and nothing marks that boundary.

**How to avoid:**
Minimum viable correctness for a per-sweep cache: honour cache-flush for A/AAAA (replace, not
append) and drop TTL=0 records. Add both to the synthetic multi-packet test suite, which the
milestone already commits to. Explicitly document that the cache's lifetime is one discovery
call and must never be reused across calls.

**Warning signs:**
A device that answers after re-attach at a new address but the library keeps connecting to the
old one within the same sweep; synthetic goodbye-packet test yielding a record.

**Phase to address:** Harden.

---

### Pitfall 6: A Thread border router is an advertising proxy, not a device, and it advertises the dead

**What goes wrong:**
Every mDNS answer for a Thread device comes from the border router's SRP advertising-proxy
cache, not from the device. Differences from a plain responder that bite this design:

- **No liveness.** An SRP registration outlives the device: OpenThread's default requested
  lease is 2 hours (`OPENTHREAD_CONFIG_SRP_CLIENT_DEFAULT_LEASE` = 7200 s; key lease 14 days).
  A powered-off Thread bulb keeps being "discovered" for up to 2 hours. Broadcast discovery
  structurally cannot have this failure (a reply proves the device is up); the mDNS leg
  imports it. `discover()` has never yielded a device that wasn't answering *right now*; after
  the merge it can.
- **Many instances per packet, and overflow.** One BR answers for the whole mesh in as few
  packets as fit; at fleet scale the TXT/SRV records fit but the AAAA additional records do not,
  which is exactly why the branch built `pending_targets()` + `build_address_query()`. Two
  devices cannot trigger this path; only synthetic tests can until the fleet migrates
  (PROJECT.md already records this as a named decision).
- **Multiple border routers.** An Apple-ecosystem network commonly runs several BRs (Apple
  TV, HomePod). Expect duplicate answers from different source IPs for the same serial, and
  potentially different OMR addresses per BR. Serial dedup handles the duplication; address
  selection (Pitfall 3) handles the rest, and both need tests with two-source synthetic input.

**Why it happens:**
mDNS reads as "like broadcast but over multicast". It is a *cache* protocol; broadcast is a
*liveness* protocol. The merge makes a cache and a liveness source feed one generator.

**How to avoid:**
Decide and document the liveness contract of merged `discover()`. Options: (a) mDNS-sourced
devices are verified with a cheap unicast `GetService`/`GetVersion` before being yielded
(restores the old invariant, costs one RTT); (b) yield unverified and document that callers
must tolerate dead entries (breaks the implicit contract every existing caller was written
under). Given LedFx constructs and uses devices immediately, (a) is the safer default; it also
kills the mDNS-spoofing problem in Pitfall 9. Measure the added latency on the probe first.

**Warning signs:**
A merged `discover()` yields a device whose first request eats the full 16 s
`DEFAULT_REQUEST_TIMEOUT`; device count from the mDNS leg exceeding the count of devices that
answer stage-3 connect.

**Phase to address:** Merge (contract decision), Revalidate (staleness measured by unplugging a
Thread device and timing its disappearance).

---

### Pitfall 7: Merged-discovery dedup key: serial vs MAC vs mDNS `id` are not proven identical

**What goes wrong:**
The merge dedups by serial. The broadcast leg's serial comes from the validated packet header
(`header.target`, with the D-01/D-02 multicast/padding checks). The mDNS leg's "serial" is
whatever string the TXT record's `id` key contains, and its SRV hostname is a third
identifier. This library documents (CLAUDE.md, `devices/base.py`) that firmware 3.x ≥ 3.70
reports a MAC that is the serial with the last octet incremented. If any firmware populates
mDNS records from the MAC rather than the serial, the same physical device appears under two
keys and the merged generator yields it twice, with two different addresses. Nothing measured
so far rules this out: the 25-device ephemeral-port sweep was never diffed against a broadcast
sweep serial-for-serial.

**Why it happens:**
Both fields are 12 hex digits and match for most devices, so a spot check passes. The
serial≠MAC quirk is exactly the kind of one-firmware-family exception this project has been
bitten by before.

**How to avoid:**
One fleet measurement before the merge lands: run broadcast discovery and mDNS discovery
back-to-back, join on serial, and list the symmetric difference with TXT `id`, SRV target, and
ARP MAC side by side (extend `scripts/serial_mac_audit.py` or add a probe stage). If any
device's mDNS `id` is MAC-shaped, add a normalisation rule next to
`mac_candidates_for_serial()` where the offset logic already lives. Also run the TXT `id`
through the same validation the broadcast leg applies (Pitfall 9).

**Warning signs:**
Merged discovery count = broadcast count + Thread count + *n* extra; two entries whose serials
differ only in the final octet by one.

**Phase to address:** Merge (measurement is a phase-entry gate), verified again in Revalidate
as fw≥3.70 Thread devices appear.

---

### Pitfall 8: The merge changes `discover()`'s timing contract that v1.1 carefully pinned

**What goes wrong:**
`_discover_with_packet` carries three load-bearing timing behaviours: an overall timeout, an
idle window that measures *network silence only* (reset both before yield and on consumer
resume; v1.1 close-out 260726-824), and re-broadcast offsets that compress rather than defer
when the consumer stalls. A naive merge breaks each:

- **Legs as background tasks feeding a queue** decouples receive from the consumer, so the
  "consumer time never counts against the idle window" invariant is trivially satisfied, but a
  *bounded* queue re-introduces the exact bug 260726-824 fixed (a slow consumer back-pressures
  the leg, which then idles out), while an *unbounded* queue is a memory hole on a hostile
  network, defeating the `_MAX_QUEUE_SIZE`-style bounds the transport layer maintains.
- **Completion semantics**: if merged completion waits for *both* legs' idle windows
  sequentially, every `discover()` gains ~4 s (`MAX_RESPONSE_TIME × IDLE_TIMEOUT_MULTIPLIER`).
  Legs must run concurrently and the generator must end when both are done, bounded by the one
  overall timeout.
- **Early exit**: every documented usage pattern includes `break` mid-iteration
  (`find_by_serial` literally returns on first match). Both legs must be `aclose()`d on
  `GeneratorExit`/cancellation; otherwise the losing leg's task dies at event-loop teardown
  with "Task was destroyed but it is pending", and its `MdnsTransport`/`UdpTransport` context
  managers never run. `asyncio.TaskGroup` plus explicit `finally: await leg.aclose()` is the
  shape; a bare `asyncio.ensure_future` merge is the trap.
- **One leg's failure must not kill the other**: `discover_lifx_services` raises
  `LifxNetworkError` out of `MdnsTransport.open()` (multicast blocked, sandboxed CI, container
  without a route) and `transport.send(query)` sits outside its try block. In the merged
  generator, an mDNS open/send failure must degrade to broadcast-only with a log, not
  propagate, or every containerised consumer's discovery breaks on day one.

**Why it happens:**
Merging two async generators looks like ten lines of `asyncio.wait`. The existing generator's
timing semantics took two milestones and a close-out quick task to get right, and none of them
are enforced by types.

**How to avoid:**
Write the invariant tests *before* the merge: (1) consumer sleeping longer than the idle
window inside the loop still receives late re-broadcast responders (port of
`test_multiple_sends_due_in_one_loop_pass` and the resume-reset tests to the merged path);
(2) `break` after the first yield leaves zero pending tasks and both sockets closed;
(3) mDNS `open()` raising yields exactly the broadcast-only result set; (4) wall-time of
merged `discover()` on a quiet network is within measurement noise of the current
broadcast-only wall time.

**Warning signs:**
Test-suite wall time jumping after the merge; `PYTHONASYNCIODEBUG=1` warnings about pending
tasks; emulator-based tests (which have no mDNS responder) timing out or slowing by ~4 s each.

**Phase to address:** Merge. The invariant tests are the phase's entry criteria, not its
follow-up.

---

### Pitfall 9: The mDNS leg has none of the broadcast leg's DoS/spoof protections, and the merge lets it shadow real devices

**What goes wrong:**
The broadcast leg validates source ID, rejects multicast/broadcast serials, and rejects
non-zero padding bytes precisely so a spoofed response cannot win the first-wins dedup against
a real device (comments in `_discover_with_packet` document this as D-01/D-02). The mDNS leg
has no equivalent: mDNS has no source correlation (transaction ID 0), and
`_LifxRecordCache.resolve()` accepts any non-empty TXT `id` and any parseable `p`. A single
spoofed multicast packet can claim a real serial with an attacker-controlled IP; in the merged
generator, first-wins dedup then *suppresses the genuine device* for that serial for the whole
sweep. The record cache is bounded (`_MAX_ENTRIES = 1024`, 16 AAAA/host, 64 follow-up
queries), so memory is defended; identity is not.

**Why it happens:**
The broadcast leg's protections were designed against its own threat model; the mDNS leg was
written as a discovery convenience before it was promoted into the default path.

**How to avoid:**
(a) Validate TXT `id` with the same rules as broadcast serials: 12 lowercase hex digits,
multicast bit clear, not all-zeros. (b) Prefer verified over unverified at the merge point: if
Pitfall 6's option (a) is taken (unicast verification of mDNS-sourced devices before yield),
spoofed entries fail verification and cost only one probe RTT, closing the hole entirely.
(c) Keep the existing bounds; add a synthetic flood test at the merge level, mirroring the
existing D-02 discovery tests.

**Warning signs:**
A serial yielded with an IP outside every local prefix; merged discovery yielding a serial the
broadcast leg saw at a different address.

**Phase to address:** Harden (TXT validation), Merge (verification ordering).

---

### Pitfall 10: WiFi-tuned reliability constants carried onto Thread unchanged

**What goes wrong:**
Every v1.1 constant encodes a WiFi measurement, and each fails differently on Thread:

- **`REQUEST_RETRANSMIT_GAPS[0] = 0.2`** ("an acked bulb answers within 200 ms", measured
  spike 002 on WiFi). Thread adds mesh hops and 802.15.4 airtime; a healthy multi-hop RTT can
  routinely exceed 200 ms. Failure signature: the packets/request metric (1.017 on WiFi after
  v1.1) climbs back toward the pre-v1.1 1.37+, every request double-fires, and duplicated
  *non-idempotent* sends become user-visible: a duplicated `SetWaveform`/effect trigger
  restarts the waveform (visible stutter), duplicated relative operations misapply.
- **`AckGate`: `ACK_INFLIGHT_LIMIT = 2`, `ACK_EXPIRY_SECONDS = 1.0`** (tuned to ~98 ms median
  / ~150 ms p95 ack RTT, spike 003). If Thread ack RTT under streaming load approaches
  500 ms+, the gate is closed most of the time and throughput approaches the documented
  degradation floor of `2/1.0` = **2 frames/s**. The failure is silent and looks like a broken
  animation on exactly one transport: no errors, no logs, ~2 FPS. Raw bandwidth compounds it:
  a Set64 frame is 557 bytes on the wire (521 payload + 36 header); 802.15.4 offers ~250 kbps
  gross, so 20 FPS × 2 packets (Ceiling) ≈ 179 kbps before 6LoWPAN/mesh overhead: 20 FPS
  streaming may be physically infeasible, which SEED-001 anticipates.
- **`DISCOVERY_REBROADCAST_GAPS`** exists because per-AP broadcast delivery at DTIM drops
  broadcasts (spike 005: 48/73 → 73/73). Thread has no DTIM and no broadcast; the mDNS leg's
  loss model is "did the multicast query reach the BR over WiFi", answered from cache. Porting
  the 5-gap broadcast schedule onto the mDNS leg would make every retransmit re-solicit the
  BR's *entire mesh worth* of records (the branch also sends no RFC 6762 §7.1 known-answer
  suppression, so re-answers are complete). The branch's lighter `[1.0, 3.0]` schedule
  satisfies §5.2 (≥1 s initial interval, growing) and is the right *shape*, but it is a guess,
  not a measurement.

**Why it happens:**
The constants live in `const.py` and `flow.py` and are quietly transport-agnostic in code even
though every one of them is a WiFi measurement (D5-09 deliberately keeps them out of the docs).

**How to avoid:**
This is SEED-001's whole purpose: re-run the spike-002/003/005-shaped measurements over Thread
before touching any constant, then decide per constant whether it needs a per-transport value.
The measurement, not the retune, is the deliverable; it is entirely possible Thread routers
(mains-powered LIFX bulbs will be full Thread devices, not sleepy end devices) answer inside
200 ms and nothing changes. Instrument first: log ack RTT distribution per device in the probe,
count retransmits per request per transport.

**Warning signs:**
packets/request > ~1.1 against Thread devices; animation FPS pinned near 2 on Thread only;
waveform effects visibly restarting.

**Phase to address:** Revalidate. Do not retune constants in Land or Merge; land behaviour,
then measure.

---

### Pitfall 11: Per-device-class breakage on Thread, and two MatrixLights prove only MatrixLight

**What goes wrong:**
The v1.2 lesson restated: everything measured so far ran on two `MatrixLight` devices, and the
classes to come stress the transport differently:

- **`CeilingLight` (16×8 = 128 px):** two `Set64` packets per frame instead of one, doubling
  streaming bandwidth vs the Candle (5×6); plus the v1.0 save-on-exit lifecycle performs extra
  writes at context exit over the slowest link, and uplight/downlight component control adds
  packets per logical operation. Streaming feasibility (Pitfall 10) hits this class first.
- **`MultiZoneLight`:** `SetExtendedColorZones` is the largest datagram in the protocol
  (~664-byte payload + 36 header = ~700 bytes). 802.15.4 frames carry ~127 bytes, so one
  extended-multizone datagram fragments into ~7+ 6LoWPAN fragments, and losing *any* fragment
  loses the datagram. Effective loss for this class's core operation is amplified relative to
  every packet the Matrix devices ever sent. Failure signature: label/power/colour work,
  full-strip zone writes are flaky or slow, retry counts spike only on zone operations.
- **Single-zone `Light`:** the baseline; validates raw RTT and waveform timing. Least likely
  to break, most useful as the control measurement.
- **Multi-tile chains cannot be Thread-validated at all:** chain is product 55 only (gen2
  Tile, no Thread firmware), so `has_chain` animation paths over Thread stay synthetic
  forever; record it as a permanent named gap, not a TODO.
- **`HevLight` / `InfraredLight`:** no Thread-capable hardware exists in the fleet; already
  scoped out as named gaps. Do not let the class matrix quietly imply coverage.

**What is provable synthetically vs what needs hardware:** parsing, cross-packet accumulation,
follow-up A/AAAA, dedup/merge semantics, family selection, scope-ID rejection, spoof handling:
all synthetic. Ack RTT distributions, fragmentation loss rates, BR lease staleness, address
reachability, per-class streaming ceilings: hardware only, per class, repeated rounds (the
project's own rule: single rounds mislead).

**How to avoid:**
Follow the v1.2 FIDELITY pattern PROJECT.md already prescribes: one evidence record per device
class, closed when evidenced or closed as a named gap. Add the class-specific probes: a
fragmentation test (send `SetExtendedColorZones` vs equivalent split `SetColorZones` writes N
times, compare delivery) belongs in the MultiZone class record.

**Warning signs:**
Any claim of the form "Thread works" without a class name attached to it.

**Phase to address:** Revalidate (per-class records); Harden (the synthetic half).

---

### Pitfall 12: `discover()` growing an mDNS leg changes behaviour for every existing caller, including this repo's own test suite

**What goes wrong:**
The decision is made and right (broadcast-only silently under-reports a Thread fleet), but the
accepted cost lands on parties who never opted in:

- **Emulator-based tests** (this repo's and downstream's): the emulator answers broadcast but
  runs no mDNS responder. Depending on merged completion semantics, every `discover()` in the
  suite either waits out an extra idle window (+~4 s × hundreds of tests) or, in sandboxed CI
  where multicast is blocked, hits `LifxNetworkError` from `MdnsTransport.open()`. Pitfall 8's
  degrade-cleanly requirement is also a CI-survival requirement.
- **Device-object provenance changes.** Today every `discover()` device went through
  `DiscoveredDevice.create_device()`: live `GetVersion`, capabilities cached via
  `adopt_cached_metadata()`, class chosen by `get_device_class_for_product`, port from
  `StateService`. The mDNS path (`create_device_from_record`) contacts nothing, chooses class
  from TXT `p` via a *duplicated* priority list, and takes port from SRV. For a WiFi device
  that advertises both ways, which leg wins the first-wins dedup is a race, so the same fleet
  yields subtly different objects run to run: sometimes with cached capabilities, sometimes
  without; sometimes at an IPv4 address, sometimes (for dual-advertised records) another.
  Downstream code that assumes discovery-returned devices have warm metadata gets a cold one
  intermittently, which is the worst kind of bug report.
- **LedFx**, the flagship consumer, re-scans periodically; scan duration, socket count and
  yielded-device liveness (Pitfall 6) all shift under it.

**Why it happens:**
"Additive" at the API-signature level is not additive at the behaviour level, and this
library's compatibility constraint is explicitly behavioural ("existing callers must work
unmodified").

**How to avoid:**
Measure before and after, and gate the merge on the diff: (1) time-to-first-device and
time-to-completion on the real fleet and against the emulator; (2) yielded device count per
leg and combined; (3) for every dual-advertised serial, assert both legs agree on class, port
and metadata or make one leg canonical (recommended: broadcast-leg object shape wins for
dual-advertised devices, so existing WiFi callers see byte-for-byte the old behaviour, and
mDNS only *adds* devices broadcast could not see); (4) unify class detection into one source of
truth instead of the two diverging priority lists; (5) run the full existing test suite against
the merged `discover()` before adding any new tests: its wall time is itself the measurement.
Publish the behaviour delta in the consumer guidance doc the milestone already includes; v2.0's
major version bump is the honest signal.

**Warning signs:**
CI wall time regression; flaky test that passes with `-k "not mdns"`; a bug report saying
"device.capabilities is sometimes None after discover()".

**Phase to address:** Compat (measurement harness first, run in Merge as its gate).

---

## Branch Audit: `feat/ipv6-thread-support` (b49400b, b88cdb9, 2f884f5)

Pitfalls the unmerged branch has already avoided, and ones it currently exhibits. Line
references are to the branch versions.

**Already got right:**

- **A1.** Ephemeral-port bind with the RFC 6762 §6.7 rationale written into the code
  (`mdns/transport.py`), matching the 25-vs-9 measurement.
- **A2.** RFC 6762 §5.2 retransmit (`[1.0, 3.0]`, ≥1 s initial, growing interval) with
  dedup-by-serial making re-answers harmless.
- **A3.** Cross-packet accumulation with bounded tables (`_MAX_ENTRIES = 1024`, ≤16
  AAAA/host, ≤64 follow-up targets): the multicast-flood memory DoS is defended.
- **A4.** Follow-up A/AAAA queries for SRV targets whose address records overflowed the reply
  (`build_address_query`), the exact fleet-scale path two devices cannot exercise.
- **A5.** The "pending, don't guess" rule: an instance with an SRV but no address records is
  held rather than misattributed to the packet's source IP, which would blame the border
  router's address for its whole mesh.
- **A6.** The probe (`scripts/ipv6_thread_probe.py`) measures rather than assumes: records,
  ports A/B against a verbatim reproduction of the pre-fix transport, and connect-stage
  separation of "wrong address" from "no answer".
- **A7.** Frame-socket family follows the device address (`animator.py`), so animation over
  IPv6 does not gaierror.

**Currently exhibits (fix in Land unless noted):**

- **B1 (= Pitfall 2).** `_discover_with_packet` still opens an IPv4-bound `UdpTransport`;
  the family-follows-local-bind contract has exactly one caller that knows it
  (`connection.py`). No send-time family assertion exists.
- **B2 (= Pitfall 1).** `devices/base.py` downgraded "IPv6 link-local without scope" from
  `ValueError` to a `WARNING` log. Combined with the swallow-all `error_received` contract,
  an unreachable-by-construction address now costs a silent 16 s instead of raising.
- **B3 (= Pitfall 3).** `_pick_address` returns `routable[0]`: arrival-order dependent, no
  ULA/GUA ordering, single address retained, no fallback on connect failure.
- **B4 (= Pitfall 4).** Multicast group membership deleted with no measurement of
  multicast-only responders, and `mdns/transport.py`'s module/class docstrings still describe
  joining the group. Fix docs in Land; measure in Harden.
- **B5 (= Pitfall 5).** `_LifxRecordCache` ignores TTL and the cache-flush bit; goodbye
  records are cached as live.
- **B6 (= Pitfall 9).** TXT `id` is accepted with no serial validation (any non-empty
  string).
- **B7 (= Pitfall 12).** `create_device_from_record` duplicates the class-priority ladder of
  `DiscoveredDevice.create_device()`/`get_device_class_for_product`; the two will drift.
- **B8.** mDNS transport is IPv4-only (`224.0.0.251`); there is no `ff02::fb` IPv6 mDNS leg.
  Works on this network because the BR answers over IPv4 mDNS (measured), but an IPv6-only
  host network gets nothing. Acceptable as a documented limitation; record it as one.
- **B9.** The `":" in ip` family heuristic appears in three places (`transport.py`,
  `connection.py`, `animator.py`) rather than one helper; same drift risk the theme layer
  solved with `slug.py`.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| `":" in ip` family sniffing in 3 places (B9) | Minimal diff | Divergent family logic; `%zone`/mapped-address edge cases handled 0 or 3 times | Only if collapsed to one helper in Land |
| Duplicated device-class ladder (B7) | mDNS path needs no network round trip | Class-detection drift between legs; already differ in relay/button handling | Never past Merge; unify |
| Single retained address per record (B3) | Simple `LifxServiceRecord` | No fallback when the chosen AAAA is unreachable; re-discovery required | Until a second BR or GUA prefix exists; fix in Harden |
| Per-sweep record cache with no TTL semantics (B5) | Avoids implementing mDNS caching | Wrong the moment the cache lifetime grows or sweeps repeat rapidly | Acceptable *only* with cache-flush + goodbye handled and lifetime documented |
| No IPv6 mDNS transport (B8) | Halves transport surface | IPv6-only host networks blind | Acceptable for v2.0 as a named gap |
| No §7.1 known-answer suppression in retransmits | Simpler query builder | Each retransmit re-solicits the BR's full mesh answer set | Acceptable at current scale; revisit at fleet migration |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| mDNSResponder / Avahi | Sharing 5353 via `SO_REUSEPORT`; daemon steals legacy-unicast replies (measured 9 vs 25) | Ephemeral-port legacy unicast query (RFC 6762 §6.7); regression-test the bind |
| Thread border router | Treating its answers as device liveness | It is an SRP cache (2 h default lease); verify before yield or document staleness |
| Multiple border routers | Assuming one answer source per device | Dedup by serial; deterministic address preference; synthetic two-source tests |
| Multi-homed hosts | One socket, default-route interface only; BR on another interface never hears the query | Measure with `dns-sd` comparison; per-interface sockets if the gap is real; document otherwise |
| asyncio datagram transport | Expecting `sendto` to raise on bad addresses | All `OSError`s (incl. `gaierror`, `EINVAL`) go to `error_received`; validate addresses before the socket |
| lifx-emulator-core | Assuming merged discovery behaves in CI as on a LAN | Emulator has no mDNS responder; mDNS leg must degrade cleanly and add ~0 s |
| Windows | `SO_REUSEPORT` absent; `IPV6_V6ONLY` defaults on | Existing `hasattr` guard covers the former; per-family sockets (never dual-stack tricks) cover the latter |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| 200 ms first retransmit gap on Thread | packets/request climbs from 1.017; duplicate waveform restarts | Measure Thread RTT distribution first (probe); per-transport gap only if evidenced | Multi-hop mesh or busy RF |
| AckGate 2-outstanding/1 s expiry on Thread | Animation pinned near 2 FPS on Thread only, no errors | Log ack RTT per device; retune from measurement (SEED-001) | Ack RTT ≳ 500 ms under load |
| Streaming bandwidth vs 802.15.4 | Ceiling (2×Set64/frame ≈ 179 kbps at 20 FPS) stutters | Measure per-class FPS ceiling; document realistic rates | Ceiling first, Candle later |
| ~700 B extended-multizone datagrams over 6LoWPAN | Zone writes flaky while small ops fine | Fragmentation A/B probe in the MultiZone class record | Any lossy mesh link (~7+ fragments, one loss kills all) |
| Merged discovery waiting both idle windows serially | Every discover() +~4 s; CI wall time jump | Concurrent legs, single overall deadline; wall-time regression test | Immediately, everywhere |
| Retransmit re-answers at fleet scale | BR resends whole mesh per retransmit | Keep mDNS schedule short; consider known-answer lists later | ~dozens of Thread devices |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Accepting unvalidated TXT `id` as a serial (B6) | Spoofed multicast packet claims a real serial; first-wins dedup shadows the genuine device for the sweep | Apply D-01/D-02 serial rules to TXT `id`; prefer broadcast-verified identity at the merge point |
| Yielding unverified mDNS devices | Attacker-controlled IP bound to a real serial; commands sent to attacker host | Unicast verification probe before yield (also fixes staleness, Pitfall 6) |
| Unbounded record accumulation | Multicast flood exhausts memory during sweep | Already bounded (A3); keep the bounds under any refactor, add a flood test |
| Follow-up query amplification | Hostile packets induce unbounded A/AAAA queries | Already capped at 64 targets; keep the cap |

## "Looks Done But Isn't" Checklist

- [ ] **IPv6 connect path:** works for the two ULA devices — verify a *link-local-only* record
      fails fast and typed, not via 16 s timeout (B2)
- [ ] **Ephemeral-port fix:** discovery finds 25 devices — verify a regression test pins the
      non-5353 bind and unicast reply delivery, per the standalone requirement in PROJECT.md
- [ ] **Cross-packet accumulation:** code exists — verify synthetic tests cover multi-packet,
      multi-source, cache-flush, goodbye, and overflowed-AAAA follow-up (two devices can
      trigger none of these)
- [ ] **Merged discover():** yields both fleets — verify early `break` leaves no pending tasks,
      mDNS failure degrades to broadcast-only, and emulator CI wall time is unchanged
- [ ] **find_by_serial both-legs:** first hit wins — verify the losing leg is cancelled and
      closed, and that a Thread-only serial and a WiFi-only serial both resolve
- [ ] **Dedup by serial:** works on 27 devices — verify broadcast-vs-mDNS serial sets were
      diffed fleet-wide (serial≠MAC quirk, Pitfall 7) before trusting the key
- [ ] **Thread revalidation:** MatrixLight evidenced — verify each remaining class has an
      evidence record or a named gap; "Thread works" claims carry a class name

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Silent 16 s address failures (1) | LOW | Add construction-time validation + send-time family assert; ship patch |
| Wrong address chosen (3) | LOW-MEDIUM | Retain all addresses on the record; add fallback-on-connect; re-run probe stage 3 |
| Merged discovery leaks tasks / breaks CI (8, 12) | MEDIUM | Feature-flag the mDNS leg internally, revert to broadcast-only default while fixing; the leg stays reachable via `discover_mdns()` |
| Dedup key wrong (7) | MEDIUM | Normalisation shim next to `mac_candidates_for_serial()`; one release, no API change |
| Constants wrong on Thread (10) | MEDIUM | Constants are internal by design (D5-09): retune from measurement without a docs lie or API change |
| Stale BR advertisements yield dead devices (6) | LOW if caught pre-merge | Insert verification probe before yield; document staleness window |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| 1. Silent IPv6 send failures | Land | Test: bad address raises typed error in <100 ms, never times out |
| 2. Family-follows-bind contract | Land / Merge | Send-time family assertion + unit test; `find_by_ip` IPv6 test |
| 3. Address selection ordering | Harden | Synthetic multi-AAAA ordering tests; probe stage 3 on hardware |
| 4. 5353 stealing / lost multicast reception | Harden | Ephemeral-bind regression test; probe A/B incl. group-joined receiver |
| 5. TTL / cache-flush / goodbye | Harden | Synthetic goodbye + cache-flush packets in the multi-packet suite |
| 6. BR staleness / liveness contract | Merge, measured in Revalidate | Unplug-and-time test; verified-before-yield decision recorded |
| 7. Dedup key (serial vs MAC vs TXT id) | Merge entry gate | Fleet-wide two-leg serial diff artefact committed |
| 8. Merged timing/teardown semantics | Merge | Invariant tests written before merge; wall-time regression check |
| 9. mDNS spoof shadows real devices | Harden + Merge | TXT id validation tests; spoof-injection test at merge level |
| 10. WiFi constants on Thread | Revalidate | Spike-shaped measurements re-run over Thread, per constant |
| 11. Per-class Thread validation | Revalidate | One evidence record or named gap per class, v1.2 FIDELITY pattern |
| 12. `discover()` behaviour change downstream | Compat (harness), gates Merge | Before/after metrics; emulator CI wall time; dual-advertised object-shape assertion |

## Sources

- Project source read directly: `src/lifx/network/transport.py`, `network/discovery.py`,
  `network/mdns/{discovery,transport,dns,types}.py`, `network/connection.py`,
  `network/utils.py`, `devices/base.py`, `animation/flow.py`, `animation/animator.py`,
  `api.py`, `const.py` (all on `main`, 2026-08-27)
- Branch audit: `git diff main...feat/ipv6-thread-support` (b49400b, b88cdb9, 2f884f5) and
  `feat/ipv6-thread-support:scripts/ipv6_thread_probe.py`
- Project measured evidence: PROJECT.md v2.0 milestone notes (25-vs-9 ephemeral-port
  measurement; `discover()` finding 25 devices and neither Thread serial; two Thread devices
  on ULA prefix `fd00:1::`, a prefix since superseded by `fd00:2::`);
  v1.1 spike series (spike 002 retry timings, spike 003 ack
  RTT ~98 ms median and gate tuning, spike 005 48/73 single-broadcast coverage);
  SEED-001-thread-ipv6-revalidation.md
- RFC 6762 (Multicast DNS): §5.2 (query retransmission, ≥1 s, doubling), §6.7 (legacy unicast
  responses, TTL ≤10), §7.1 (known-answer suppression), §10.1 (goodbye packets), §10.2
  (cache-flush bit)
- OpenThread SRP client defaults (lease 7200 s, key lease 14 days):
  [openthread.io SRP client config](https://openthread.io/reference/config/group/config-srp-client)
- CPython asyncio `_SelectorDatagramTransport.sendto` error routing (OSError →
  `error_received`), corroborated by this project's own verified transport docstrings
- Packet-size arithmetic from `src/lifx/protocol/packets.py` field definitions (Set64 payload
  521 B; SetExtendedColorZones payload 664 B; header 36 B)

---
*Pitfalls research for: lifx-async v2.0 Thread/IPv6 Support*
*Researched: 2026-08-27*
