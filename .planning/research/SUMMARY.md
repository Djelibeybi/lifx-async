# Project Research Summary

**Project:** lifx-async v2.0 Thread/IPv6 Support
**Domain:** Thread/IPv6 device discovery and control in a zero-dependency async Python LIFX library
**Researched:** 2026-08-27
**Confidence:** HIGH for stdlib primitives, architecture seams and codebase-specific pitfalls; MEDIUM for ecosystem behaviour; MEDIUM-LOW for Thread performance numbers, which are published figures rather than fleet measurements and are gated on SEED-001

## Executive Summary

This milestone makes a Thread device a first-class citizen of the library: found by the default `discover()`, addressable by IPv6 literal, controlled and animated without the caller knowing the transport. The entire stack is the Python standard library. Stack research verified empirically (macOS and Linux, CPython 3.10 and 3.14) that the existing `feat/ipv6-thread-support` branch uses the correct stdlib primitives everywhere: per-family sockets whose family follows the target address, `ipaddress` at validation boundaries, and an ephemeral-port legacy-unicast mDNS querier that RFC 6762 §6.7 obliges responders to answer directly. The ephemeral bind also fixes a measured IPv4 defect in its own right (25 devices found versus 9 when sharing port 5353 with the system daemon), which is why it carries its own regression-test requirement.

The reconciled verdict on the branch: **the primitives and the address-family seam are right, but "land the branch" is not "rebase and merge".** The pitfalls audit found nine findings (B1 to B9) against seven things done right, and two look like regressions introduced by the branch itself: multicast group membership was deleted while the docstrings still claim the group is joined (B4), and the link-local-without-scope check in `Device.__init__` was downgraded from `ValueError` to a warning on a transport that swallows every send-time `OSError`, converting a permanent configuration error into a silent 16 second timeout (B2). The Land phase must therefore include: restore the `ValueError` for bare link-local (B2), fix the stale multicast docstrings and record the no-unsolicited-announcements trade (B4), fix the `MdnsTransport.open()` socket leak, hoist `retransmit_delays` to a patchable module constant, collapse the thrice-repeated `":" in ip` family heuristic into one `network/utils.py` helper (B9), and top the branch up to the 100% branch-patch coverage gate. The remaining findings (address-selection ordering B3, TTL/cache-flush semantics B5, TXT `id` validation B6, duplicated class ladder B7) belong to the Harden and Merge phases.

The main risks are behavioural, not primitive. Merging an mDNS leg into `discover()` mixes a liveness protocol (broadcast: a reply proves the device is up) with a cache protocol (a border router's SRP registration can outlive the device by up to its 2 hour default lease), and it changes timing that v1.1 spent two milestones pinning. Mitigation: unicast verification of mDNS-sourced devices before yield, invariant tests written before the merge, and a before/after measurement harness as the Merge phase's entry gate. Streaming feasibility over Thread is unknowable from published numbers alone: the arithmetic from both FEATURES and PITFALLS agrees in direction (20 FPS Set64 at roughly 89 kbps against a roughly 100 kbps zero-loss single-hop ceiling; Ceiling at two Set64 per frame roughly 179 kbps against roughly 250 kbps gross 802.15.4), so 20 FPS full-frame matrix streaming over Thread is probably infeasible sustained, the AckGate's designed degradation floor is exactly 2 FPS, and the honest deliverable is the measured number from the two Thread MatrixLights, not a recalibrated constant.

## Key Findings

### Recommended Stack

Stdlib only, no additions, and the branch already uses the right pieces. Full detail in STACK.md.

**Core APIs:**
- `create_datagram_endpoint(family=...)` with per-family sockets: dual-stack `"::"` sockets are a trap (mapped-address peer strings, no IPv4 broadcast, 4-tuple sockaddrs); family follows the target address
- `ipaddress.ip_address()` at validation boundaries: handles zone IDs on all platforms; `socket.inet_pton` diverges between Apple libc and glibc and must never sniff families
- Ephemeral-port bind for mDNS queries: RFC 6762 §6.7 guarantees unicast replies; never bind 5353 (system daemons steal replies on both macOS and Linux, by different mechanisms)
- `IPv6Address.is_link_local` and `fc00::/7` containment for classification: both stable across the CVE-2024-4032 realignment
- Never pass `reuse_address` (removed in 3.11); never use `IPV6_ADD_MEMBERSHIP` (not exposed by CPython on either platform; the constant is `IPV6_JOIN_GROUP`)
- Testing without hardware or multicast: pure codec tests, direct `datagram_received()` injection with zone-qualified 4-tuples, and real `::1` loopback endpoints (verified available on CI runners and inside Docker)

### Expected Features

Full detail in FEATURES.md. The ecosystem consensus (Home Assistant, python-kasa, python-matter-server) is that discovery merges sources invisibly, dedups on stable device identity (serial, never address), and exposes transport as read-only diagnostics only.

**Must have (table stakes):**
- Merged `discover()`: concurrent broadcast and mDNS legs, serial-keyed first-wins, stream-as-found (never gather-then-merge)
- IPv6 device connections and AAAA parsing with routable-over-link-local preference (on branch)
- Correct multi-instance mDNS at mesh scale: cross-packet accumulation, follow-up A/AAAA, §5.2 retransmit (on branch, provable only synthetically today)
- Ephemeral-port bind with its own regression test
- `find_by_serial()` racing both legs; `find_by_ip()` accepting an IPv6 literal
- Public API additive only; existing callers unmodified

**Should have (competitive):**
- `tm` transport method exposed on `LifxServiceRecord`, parsed defensively (the key is undocumented; absent means unknown); no other LIFX LAN library has any Thread awareness
- Thread-revalidated reliability constants (SEED-001), evidenced per device class
- Consumer guidance docs for broadcast-first integrations

**Anti-features (do not build):**
- Transport-specific entry points or `transport=` parameters; Thread tuning knobs for consumers; routing control traffic by `tm`; treating an mDNS advertisement as proof of reachability; Thread commissioning or border-router management

### Architecture Approach

Full detail in ARCHITECTURE.md. The address family is a property of the peer address, derived at each socket-creation site; no family parameter threads through public constructors. The merge lives in `api.py` as a queue fan-in: two `asyncio.create_task` pumps feeding one `asyncio.Queue`, merged at the record level (`DiscoveredDevice` / `LifxServiceRecord`) before device construction. **`asyncio.TaskGroup` is unavailable (3.11+, library ships 3.10) and its cancel-siblings semantics would be wrong anyway**: a dead mDNS leg must degrade to broadcast-only, never kill the other leg. `find_by_serial()` is an `asyncio.wait(FIRST_COMPLETED)` loop over raw-record legs with mandatory reaping (`gather(return_exceptions=True)` in `finally`) so the loser's sockets close. `find_by_ip()` over IPv6 needs one change: `_discover_with_packet` derives its bind address from `broadcast_address` instead of unconditionally binding `0.0.0.0`.

**Major components:**
1. `network/utils.py` `is_ipv6()` helper: single home for the family heuristic (new)
2. `network/discovery.py` family-aware `_discover_with_packet`: closes the IPv4-only gap and delivers `find_by_ip()` for free (new work)
3. `network/mdns/*`: branch changes plus `tm` parsing into `LifxServiceRecord.transport_method` (branch + new)
4. `api.py` `_merged_discovery()` and the `find_by_serial()` race (new work, one file, one phase)
5. Emulator on `::1` fixture: `EmulatedLifxServer` already accepts `bind_address="::1"` unchanged, giving real IPv6 end-to-end tests on every CI runner

### Critical Pitfalls

Top five of twelve; full detail in PITFALLS.md.

1. **Silent IPv6 send failures** (B2): asyncio routes all send-time `OSError`s including `gaierror` to `error_received`, so a wrong-family or unscoped link-local address costs a silent 16 seconds instead of raising. Restore construction-time `ValueError` and add a send-time family assertion.
2. **Discovery liveness broken by the SRP cache**: a border router advertises a powered-off Thread device for up to 2 hours. `discover()` has never yielded a device that was not answering right now. **Reconciled decision for the roadmap: unicast verification before yield is part of the Merge requirement**, restoring the old invariant at one RTT per mDNS-sourced device and closing the mDNS-spoofing hole (Pitfall 9) at the same time. Measure the added latency on the probe first.
3. **Dedup key: narrow, WiFi-only residual risk**: PITFALLS framed the serial-versus-MAC divergence as an unproven Merge gate; that is overstated. The off-by-one quirk is gated to firmware 3.70 to 3.99 (`Device.get_mac_address()` in `src/lifx/devices/base.py` fires only on `version_major == 3 and version_minor >= 70`), and LIFX Thread support requires firmware 4 or later, so no Thread device can exhibit it and the mDNS `id` and broadcast serial cannot diverge by this mechanism on Thread. The residual question is whether a dual-advertised WiFi device on 3.70 to 3.99 has a MAC-derived rather than serial-derived TXT `id`; confirm once against that subset of the fleet as a low-priority verification, not a Merge entry gate.
4. **Merge timing and teardown semantics**: idle-window invariants, early `break` cleanup, mDNS-failure degradation and emulator CI wall time are all breakable; the invariant tests are the Merge phase's entry criteria.
5. **WiFi constants carried onto Thread**: 200 ms retry floor, AckGate of 2 with 1 s expiry, and the 20 FPS assumption are all WiFi measurements. Do not retune in Land or Merge; measure in Revalidate (SEED-001), per constant, per device class.

## Implications for Roadmap

### Phase 1: Land the branch
**Rationale:** Everything else in the milestone depends on it; nothing is testable on Thread hardware until it merges.
**Delivers:** IPv6 connections, AAAA parsing, multi-packet mDNS accumulation, ephemeral bind, animator frame-socket family; rebased onto `main`.
**Beyond the rebase (the reconciled landing list):** restore link-local `ValueError` (B2), fix multicast docstrings and record the trade (B4), fix the `MdnsTransport.open()` socket leak, hoist `retransmit_delays` to a module constant, extract `is_ipv6()` and adopt it at the three branch sites (B9), coverage top-up to the 100% branch-patch gate (check branch partials).
**Avoids:** Pitfalls 1, 2 (partially), the drift risk of B9.

### Phase 2a: Harden the mDNS leg (parallel with 2b)
**Rationale:** The mesh-scale claims can only be proved synthetically today, and the mDNS leg needs broadcast-grade validation before it is promoted into the default path.
**Delivers:** `tm` field and parsing; ephemeral-bind regression test (its own requirement); synthetic multi-packet tests covering accumulation, follow-up A/AAAA, cache-flush, goodbye packets and two-source input; explicit address preference (ULA > GUA > link-local-with-scope, deterministic) with all addresses retained on the record (B3); TXT `id` validated with the broadcast serial rules (B6); TTL=0 and cache-flush honoured (B5); probe A/B measuring the multicast-only-responder population.
**Avoids:** Pitfalls 3, 4, 5, 9 (validation half).

### Phase 2b: IPv4/IPv6 plumbing (parallel with 2a)
**Rationale:** Shares no files with 2a; unblocks Phase 3.
**Delivers:** family-aware `_discover_with_packet` bind; `find_by_ip()` IPv6 (test-only after the bind change); emulator-on-`::1` conftest fixture.
**Avoids:** Pitfall 2 (the fourth call site lands already centralised).

### Phase 3: Merged `discover()` and `find_by_serial()` race
**Rationale:** Consumes the record-level generators whose signatures 2a/2b finalise; both functions live in `api.py`, so one phase.
**Delivers:** queue fan-in merge, serial-keyed first-wins, stream-as-found; `FIRST_COMPLETED` race with reaping; unicast verification of mDNS-sourced devices before yield; unified device-class ladder (B7).
**Entry gates, not follow-ups:** the invariant test suite plus before/after measurement harness (Pitfalls 8, 12: wall time, emulator CI, dual-advertised object shape with the broadcast-leg object canonical). The dedup-key question (Pitfall 7) is downgraded: Thread devices run firmware 4+, where the serial-versus-MAC quirk structurally cannot fire; a one-off TXT `id` check against the fw 3.70 to 3.99 WiFi subset suffices, at low priority.
**Avoids:** Pitfalls 6, 8, 9 (ordering half), 12; Pitfall 7 reduced to a low-priority WiFi-only verification.

### Phase 4: Revalidate (SEED-001) and docs
**Rationale:** Needs the whole transport stack; hardware-gated by design (decision 2026-08-27: synthetic first, hardware later); cannot block CI work.
**Delivers:** spike-shaped measurements over Thread on the two MatrixLights (retry floor, ack RTT distribution, achievable streaming FPS); one evidence record or named gap per device class (CeilingLight, MultiZoneLight and Light close as migrations land; HevLight, InfraredLight and multi-tile chains close as named gaps); staleness measured by unplugging a Thread device; consumer guidance docs including the broadcast-first warning and the documented limitations (IPv4-only mDNS query leg, no unsolicited announcements).
**Streaming statement for the roadmap:** expect the ack gate to degrade gracefully to whatever the mesh supports; 20 FPS matrix streaming is probably infeasible sustained, the designed floor is 2 FPS, and the deliverable is the measured ceiling, published as behaviour, not constants (D5-09 as written). No constant changes without SEED-001 evidence.

### Phase Ordering Rationale

- The branch is the critical path (every researcher agrees); 2a/2b are file-disjoint and parallelisable; the merge must be serial after both because it consumes their finalised shapes.
- Measurement gates (serial diff, invariant tests, wall-time harness) sit at the Merge boundary because the merge is where the behavioural compatibility constraint is most at risk.
- Constants are measured last and only changed on evidence, matching the project's own spike-first discipline.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 3 (Merge):** the liveness verification cost is an open measurement; plan with `--research-phase` if it surprises.
- **Phase 4 (Revalidate):** hardware measurement design (spike-shaped, repeated rounds mandatory); the achievable-FPS question has no literature answer for this stack.

Phases with standard patterns (skip research-phase):
- **Phase 1 (Land):** fully specified by the branch audit; the fixes are enumerated.
- **Phases 2a/2b:** established test seams (injection, `::1` loopback, patched transports) already proven on the branch and in ARCHITECTURE.md Q6.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Core claims verified empirically this session on macOS and Linux, both ends of the Python range, plus CPython source reading |
| Features | MEDIUM | Ecosystem claims verified in source; Thread performance figures are published measurements from other networks, MEDIUM-LOW, and anything resting on them needs SEED-001 measurement before it is treated as established |
| Architecture | HIGH | Derived from direct reading of `main`, the branch and the test suite; only the `SO_BROADCAST`-on-AF_INET6 legality claim is MEDIUM |
| Pitfalls | HIGH | Codebase-specific findings read from source and the branch diff; Thread-mesh behaviour not yet measured on this fleet is MEDIUM |

**Overall confidence:** HIGH for the code plan; MEDIUM for everything Thread-performance-shaped until SEED-001 runs.

### Gaps to Address

- **Thread RTT, ack RTT under load, and streaming FPS ceiling:** unknown for this fleet; SEED-001 on the two MatrixLights is the only resolution. Do not let published figures leak into constants.
- **mDNS `id` derivation on firmware 3.70 to 3.99 WiFi devices:** the only population where TXT `id` could be MAC-derived rather than serial-derived (Thread requires firmware 4+, outside the quirk's gate); confirm once, low priority, not a blocker.
- **Multicast-only mDNS responders:** the 25-device measurement proves the current fleet answers unicast, not that all future firmware or border routers do; the Harden phase's probe A/B (ephemeral versus ephemeral-plus-group-joined receiver) measures the population instead of assuming zero.
- **SRP lease behaviour of LIFX Thread firmware:** OpenThread default is 2 hours; LIFX's actual lease is unverified. The unplug-and-time test in Revalidate settles it.
- **Multi-address and multi-border-router topologies:** only one usable address per device exists today; re-run probe stage 3 when a second border router or GUA prefix appears.
- **IPv6-only host networks:** the mDNS query leg is IPv4 multicast by design (B8); documented limitation, revisit only on demand.

## Sources

### Primary (HIGH confidence)
- CPython 3.14.2 source and empirical verification on macOS Darwin 25 / CPython 3.14.2 and `python:3.10-slim` (glibc): asyncio datagram internals, socket constants, dual-stack behaviour, zone handling
- Project source on `main` and `git diff main...feat/ipv6-thread-support` (`b49400b`, `b88cdb9`, `2f884f5`)
- Project field measurements (PROJECT.md): 25-vs-9 ephemeral-bind sweep; `discover()` missing both Thread serials; ULA prefixes; v1.1 spike series (002, 003, 005)
- RFC 6762 (§5.1, §5.2, §6.7, §7.1, §10.1, §10.2, §11), RFC 4007, RFC 4193, RFC 4291

### Secondary (MEDIUM confidence)
- OpenThread border router and SRP documentation (advertising proxy, 7200 s default lease); Thread 1.3.0 white paper
- Library source surveys: python-matter-server, HA lifx/matter components, python-kasa, aioesphomeapi, aiolifx (verified in source)
- LIFX LAN docs (TXT keys `id`/`fw`/`p`; `tm` is undocumented, local-hardware observation only)

### Tertiary (LOW-MEDIUM confidence, needs SEED-001 validation)
- Silicon Labs Thread overview and MDPI 2023 Thread performance evaluation: 250 kbps PHY, tens-of-ms single-hop RTT, roughly 100 kbps zero-loss single-hop ceiling
- Press coverage of the LIFX Thread firmware beta (HomeKit News, Matter Alpha)

---
*Research completed: 2026-08-27*
*Ready for roadmap: yes*
