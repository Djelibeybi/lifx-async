# Requirements: lifx-async v2.0 Thread/IPv6 Support

**Defined:** 2026-08-27
**Core Value:** Commands stick, devices are found, streaming never starves control traffic, and a theme by name looks like the theme of that name in the LIFX app.

**Milestone goal:** A Thread device becomes a first-class device in this library: found,
addressed, controlled and animated without the caller needing to know it is on Thread. The
v1.1 wire-reliability findings are then revalidated over Thread, because every one of them
was measured on WiFi/IPv4.

**Research:** `.planning/research/SUMMARY.md` (2026-08-27), backed by STACK, FEATURES,
ARCHITECTURE and PITFALLS in the same directory.

## v2.0 Requirements

### IPv6 Transport

Landing `feat/ipv6-thread-support` (`b49400b`, `b88cdb9`, `2f884f5`) onto `main`. Research
verdict: the branch's stdlib primitives and address-family seam are correct, so this is a
rebase plus a reconciled fix list, not a rewrite.

- [ ] **IPV6-01**: A caller can connect to, control and send animation frames to a device
      that has only an IPv6 address. The socket family follows the target address at every
      socket-creation site, including the animation layer's separate direct-UDP frame
      socket
- [ ] **IPV6-02**: A caller who supplies a link-local address with no zone identifier gets
      an immediate `ValueError` naming the problem, rather than a silent timeout. The
      branch downgraded this check to a warning on a transport that routes every send-time
      `OSError` to `error_received` and never raises, which turns a permanent
      configuration error into a 16 second wait (PITFALLS B2)
- [ ] **IPV6-03**: Address-family selection has one implementation, shared by every
      socket-creation site, so the transports cannot drift apart. The branch repeats the
      `":" in ip` heuristic three times (PITFALLS B9)
- [ ] **IPV6-04**: An mDNS transport whose endpoint creation fails partway through
      `open()` leaves no socket behind

### mDNS Discovery

Hardening the mDNS leg to broadcast-grade quality before it is promoted into the default
discovery path.

- [ ] **MDNS-01**: mDNS queries bind an ephemeral port, so a system mDNS daemon sharing
      5353 cannot steal RFC 6762 section 6.7 legacy-unicast replies. Measured impact: 25
      devices found bound ephemeral against 9 bound on 5353 with `SO_REUSEPORT`. The
      regression test must not itself bind 5353, because CI runners run Avahi and the test
      would measure the runner rather than the fix
- [ ] **MDNS-02**: A caller can read how a device was reached, from a `tm` field on
      `LifxServiceRecord` carrying the mDNS TXT `tm` key's value. The field keeps the wire
      name deliberately (user decision, 2026-08-27): the protocol layer normally renames
      wire fields for readability, but a readable name here would have to assert an
      expansion nobody has confirmed, so the cryptic-but-honest name wins. What LIFX has
      confirmed is
      the value semantics only: `1` is WiFi and `2` is Thread. What `tm` abbreviates is
      **not** confirmed, and the key is absent from the public LIFX LAN documentation
      entirely, so no expansion of it may be asserted in the public API name, the
      docstrings or the docs. Parsing is defensive: an absent, unparsable or unrecognised
      value reports as unknown and never raises, because a third value could appear in any
      future firmware
- [ ] **MDNS-03**: Records for one service instance accumulate across multiple response
      packets, proven by synthetic multi-packet tests. A Thread border router acts as an
      advertising proxy for the whole mesh, and RFC 6762 legacy-unicast replies cannot
      span packets, so records are omitted rather than continued
- [ ] **MDNS-04**: An SRV target whose address records did not fit in a reply triggers a
      follow-up A/AAAA query, proven by synthetic tests
- [ ] **MDNS-05**: Address selection is deterministic and documented, preferring ULA, then
      GUA, then scoped link-local, and every discovered address is retained on the record
      rather than discarded at selection time (PITFALLS B3)
- [ ] **MDNS-06**: A TXT `id` that fails the same validation the broadcast path applies to
      a serial is rejected rather than trusted (PITFALLS B6)
- [ ] **MDNS-07**: TTL 0 goodbye packets and cache-flush bits are honoured (PITFALLS B5)
- [ ] **MDNS-08**: The mDNS module's documented behaviour matches its actual behaviour.
      The branch deleted `IP_ADD_MEMBERSHIP` while leaving docstrings that still claim the
      multicast group is joined. The docstrings are corrected and the unicast-only trade
      is recorded as a known limitation. No group rejoin and no responder-population
      probe: the ephemeral-port fix came from LIFX, so LIFX devices answering unicast per
      RFC 6762 section 6.7 is vendor-stated, not inferred

### Discovery and Lookup

- [ ] **FIND-01**: `discover()` finds Thread devices without the caller opting in, running
      a broadcast leg and an mDNS leg concurrently and merging by serial, first wins.
      Measured today: `discover()` returns 25 devices and neither Thread serial, while
      `discover_mdns()` returns both
- [ ] **FIND-02**: `discover()`'s existing contract survives the merge, specifically its
      overall timeout, its idle timeout resetting on consumer resume, first-wins
      per-serial dedup, and DoS source and serial validation. The invariant tests are
      written before the merge, as its entry gate, not after it
- [ ] **FIND-03**: An mDNS leg that fails or is unavailable degrades `discover()` to
      today's broadcast-only behaviour rather than ending discovery. `asyncio.TaskGroup`
      is unavailable regardless (Python 3.11 or later; this library ships 3.10 for LedFx),
      and its cancel-siblings semantics would be wrong here anyway
- [ ] **FIND-04**: An mDNS-sourced device is unicast-verified before it is yielded, so
      `discover()` never yields a device that is not answering. A border router's SRP
      registration can outlive the device by up to a 2 hour default lease, and `discover()`
      has never broken that liveness contract. Verification also closes the mDNS leg's
      spoofing exposure, since it carries none of the broadcast leg's validation
- [ ] **FIND-05**: `find_by_serial()` races a broadcast leg and an mDNS leg, first hit
      wins, and the losing leg is cancelled and reaped so no task or socket leaks. Both
      legs are required: broadcast covers WiFi devices whose firmware does not advertise
      over mDNS, mDNS covers Thread devices with no IPv4 address to broadcast to
- [ ] **FIND-06**: `find_by_ip()` resolves a device from an IPv6 literal instead of
      returning `None`
- [ ] **FIND-07**: The timing change merged discovery imposes on existing callers is a
      measured before-and-after number against the fleet, not an assumption. Emulator CI
      wall time is part of that measurement
- [ ] **FIND-08**: The mDNS TXT `id` is confirmed to match the broadcast serial for
      firmware 3.70 to 3.99 WiFi devices, the only population where the two could diverge.
      Low priority and not a gate: Thread requires firmware 4 or later, and
      `Device.get_mac_address()` fires only on `version_major == 3 and version_minor >= 70`,
      so a Thread device structurally cannot exhibit the off-by-one quirk

### Thread Revalidation

SEED-001, planted 2026-07-16 and dormant through the v1.1 and v1.2 closes. Its trigger
condition, LIFX Thread firmware shipping, was met during the v1.2 close-out. Every v1.1
reliability finding was measured on WiFi/IPv4 and none of them transfers unexamined.

- [ ] **THREAD-01**: Discovery coverage over Thread is measured across repeated rounds.
      Single rounds mislead, which is the Spike 005 lesson this project already paid for
- [ ] **THREAD-02**: The retry schedule's WiFi-tuned constants are measured against Thread
      ack RTT. The 200 ms "an acked bulb has answered by now" floor exists because of WiFi
      timing; no constant changes without evidence
- [ ] **THREAD-03**: The achievable animation frame rate over Thread is measured, and the
      measured ceiling is the deliverable. Published arithmetic suggests 20 FPS full-frame
      matrix streaming is infeasible sustained (roughly 89 kbps for `Set64` at 20 FPS, and
      roughly 179 kbps for a Ceiling's two `Set64` per frame, against a 250 kbps gross
      802.15.4 PHY and a measured single-hop ceiling near 100 kbps), and the ack gate's
      designed degradation floor is exactly 2 FPS. Those are other people's networks;
      this requirement replaces them with a number from this fleet
- [ ] **THREAD-04**: Border router advertisement staleness is measured directly, by
      unplugging a Thread device and timing when it stops being advertised. This settles
      LIFX's actual SRP lease, which is unverified; OpenThread's default is 2 hours
- [ ] **THREAD-05**: Every device class has either a Thread evidence record or a named
      gap, following the v1.2 FIDELITY pattern so that an unavailable class closes rather
      than staying open indefinitely. `MatrixLight` closes now on two devices;
      `CeilingLight`, `MultiZoneLight` and single-zone `Light` close as migrations land;
      `InfraredLight` and `HevLight` close as named gaps, since the fleet's hardware in
      both classes predates Thread

### Documentation

- [ ] **DOCS-04**: A broadcast-first consumer can read what changes for them, what Thread
      support does and does not give them, and how to reach Thread devices
- [ ] **DOCS-05**: Known limitations are documented rather than discovered: the mDNS query
      leg is IPv4 multicast by design, there are no unsolicited announcements, reception
      is unicast-only, and fleet-scale mesh behaviour is proven synthetically rather than
      on hardware
- [ ] **DOCS-06**: The repository's own architecture documentation is corrected where it
      is factually wrong. `CLAUDE.md` states that operations on multiple devices execute
      in parallel via `asyncio.TaskGroup`; `grep` finds no `TaskGroup` anywhere in `src/`,
      and it would not run on the Python 3.10 floor this library supports. Left standing,
      it would mislead a future planner into writing code that fails on 3.10

## Future Requirements

Deferred beyond v2.0. Tracked, not in this roadmap.

### Thread at Fleet Scale

- **FLEET-01**: Cross-packet accumulation and follow-up A/AAAA queries confirmed on real
  hardware, once enough of the fleet is migrated for a border router to overflow a single
  legacy-unicast reply packet
- **FLEET-02**: Multi-address and multi-border-router topologies revalidated, once a
  second border router or a GUA prefix exists on the network

### Carried Forward

- **PERS-01**: Generalise `state_file` persistence into a reusable mixin (deferred since
  2026-06-11)
- **SPIKE-006**: Measure the impact of publishing tuning constants against publishing
  behaviour only. The D5-09 rule is disputed by the operator and remains an OPEN decision
- **STYLE-01**: No-em-dash house style across `docs/`, roughly 200 instances. Preference
  is to recast each sentence rather than swap the character

## Out of Scope

| Feature | Reason |
|---------|--------|
| An mDNS path of `find_by_label()`'s own | It keeps the broadcast `GetLabel` trick and gains Thread devices through `discover()`'s new mDNS leg, so a second addressing scheme buys nothing (user decision, 2026-08-27) |
| Home Assistant integration code | This milestone ships the library capability and the guidance a broadcast-first consumer needs; downstream changes land in their own repositories (user decision, 2026-08-27) |
| Thread coverage for `HevLight` and `InfraredLight` | No Thread-capable hardware of either class exists in the fleet. Closed as named gaps under THREAD-05 rather than excluded permanently, since newer models may gain Thread |
| Fleet-scale Thread hardware validation | Deferred until enough of the fleet is migrated. Covered synthetically under MDNS-03 and MDNS-04 in the meantime, and recorded as a named gap (user decision, 2026-08-27) |
| Rejoining the mDNS multicast group | The ephemeral-port fix came from LIFX, so LIFX devices honouring RFC 6762 section 6.7 unicast replies is vendor-stated. Rejoining would reintroduce the shared-socket exposure the fix was made to escape, with nothing needing it (user decision, 2026-08-27) |
| An IPv6 multicast mDNS query leg | The query leg is IPv4 multicast by design and the unicast-reply path carries Thread devices fine. Would require per-interface `IPV6_MULTICAST_IF` iteration, which macOS demands and CPython gives no `getifaddrs` for. Documented limitation under DOCS-05, revisit on demand |
| Transport-specific entry points, `transport=` parameters, or routing control traffic by `tm` | No comparable library does this. Transport is read-only diagnostics; a caller choosing a transport is the anti-feature the merged `discover()` exists to remove |
| Consumer-facing Thread tuning knobs | Contradicts the locked decision of 2026-07-16 that the animation library owns delivery strategy, not downstream consumers |
| Thread commissioning or border-router management | Out of a device-control library's remit entirely |
| Retuning any WiFi-measured constant before SEED-001 measures it | The project's own spike-first discipline. Constants change on evidence, in the Revalidate phase, never in Land or Merge |

## Traceability

Populated at roadmap creation, 2026-08-27.

| Requirement | Phase | Status |
|-------------|-------|--------|
| IPV6-01 | Phase 10 | Pending |
| IPV6-02 | Phase 10 | Pending |
| IPV6-03 | Phase 10 | Pending |
| IPV6-04 | Phase 10 | Pending |
| MDNS-01 | Phase 11 | Pending |
| MDNS-02 | Phase 11 | Pending |
| MDNS-03 | Phase 11 | Pending |
| MDNS-04 | Phase 11 | Pending |
| MDNS-05 | Phase 11 | Pending |
| MDNS-06 | Phase 11 | Pending |
| MDNS-07 | Phase 11 | Pending |
| MDNS-08 | Phase 11 | Pending |
| FIND-01 | Phase 13 | Pending |
| FIND-02 | Phase 13 | Pending |
| FIND-03 | Phase 13 | Pending |
| FIND-04 | Phase 13 | Pending |
| FIND-05 | Phase 13 | Pending |
| FIND-06 | Phase 12 | Pending |
| FIND-07 | Phase 13 | Pending |
| FIND-08 | Phase 13 | Pending |
| THREAD-01 | Phase 14 | Pending |
| THREAD-02 | Phase 14 | Pending |
| THREAD-03 | Phase 14 | Pending |
| THREAD-04 | Phase 14 | Pending |
| THREAD-05 | Phase 14 | Pending |
| DOCS-04 | Phase 14 | Pending |
| DOCS-05 | Phase 14 | Pending |
| DOCS-06 | Phase 14 | Pending |

**Coverage:**
- v2.0 requirements: 28 total
- Mapped to phases: 28
- Unmapped: 0

---
*Requirements defined: 2026-08-27*
*Last updated: 2026-08-27 after roadmap creation (Phases 10 to 14 mapped)*
