# Roadmap: lifx-async

## Milestones

- ✅ **v1.0 Ceiling Save-on-Exit**: Phase 1, shipped 2026-06-12 ([archive](milestones/v1.0-ROADMAP.md))
- ✅ **Post-v1.0 Discovery unification**: Phase 1, verified 2026-06-13, archived in `milestones/v1.1-phases/01-unify-duplicated-discovery-loops/`
- ✅ **v1.1 Wire Reliability**: Phases 2–5, shipped 2026-07-26 ([archive](milestones/v1.1-ROADMAP.md))
- ✅ **v1.2 Theme Library Update**: Phases 6–9, shipped 2026-08-27 ([archive](milestones/v1.2-ROADMAP.md))
- 🚧 **v2.0 Thread/IPv6 Support**: Phases 10–14, in progress

## Phases

<details>
<summary>✅ v1.0 Ceiling Save-on-Exit (Phase 1), SHIPPED 2026-06-12</summary>

- [x] Phase 1: Ceiling Save-on-Exit (1/1 plans), completed 2026-06-12

Full details: [milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md)

</details>

<details>
<summary>✅ Post-v1.0 Phase 1: Unify duplicated discovery loops (verified 2026-06-13)</summary>

Standalone phase from the /simplify review (2026-06-13). Rebuilt `discover_devices()`
on `_discover_with_packet()` with hoisted DoS serial validation and first-wins per-serial
dedup; retired `_parse_device_state_service()`. Review-fix 6/6, security 11/11 closed,
UAT 4/4 including real-hardware validation (regression 0d83deb found and fixed).
5/5 plans complete. Phase directory archived in
`milestones/v1.1-phases/01-unify-duplicated-discovery-loops/`.

</details>

<details>
<summary>✅ v1.1 Wire Reliability (Phases 2–5), SHIPPED 2026-07-26</summary>

Closed the measured reliability gap against the reference clients (Glowup, Photons) using
the spike-validated blueprints, without changing the asyncio core or the public API.

- [x] Phase 2: Discovery Re-broadcast (2/2 plans), completed 2026-07-16
- [x] Phase 3: Retry Schedule Reshape (3/3 plans), completed 2026-07-17
- [x] Phase 4: Animation Flow Control (13/13 plans), completed 2026-07-17
- [x] Phase 5: Reliability Documentation (6/6 plans), completed 2026-07-18

13/13 requirements satisfied, 25/25 must-have truths verified, 7/7 cross-phase
connections wired, all four phases Nyquist-compliant.

Full details: [milestones/v1.1-ROADMAP.md](milestones/v1.1-ROADMAP.md) ·
audit: [milestones/v1.1-MILESTONE-AUDIT.md](milestones/v1.1-MILESTONE-AUDIT.md)

</details>

<details>
<summary>✅ v1.2 Theme Library Update (Phases 6–9), SHIPPED 2026-08-27</summary>

Resynced `lifx.theme.library` with the LIFX app's live theme set without silently changing
colours existing callers depend on. The hand-written palette table is gone: 166 committed
JSONL records drive a validating generator into `src/lifx/theme/data.py`, and 169 names
resolve with app-accurate palettes, names, categories and dispositions.

- [x] Phase 6: Generated Theme Library (2/2 plans), completed 2026-08-15
- [x] Phase 7: Taxonomy & Legacy Dispositions (3/3 plans), completed 2026-08-15
- [x] Phase 8: Hardware Fidelity Validation (4/4 plans), completed 2026-08-16
- [x] Phase 9: Theme Data Contract & Docs (2/2 plans), completed 2026-08-27

16/16 live requirements satisfied, 8 cross-phase seams checked, 3520 tests at 97%
coverage. COMPAT-02 retired 2026-08-14; TOOL-01..03 withdrawn 2026-08-19 to the private
`lifx-theme-resync` repository.

Two locked decisions reversed in flight: the `*_legacy` aliases, and the "device readback
only" capture rule. The latter is what answered the milestone's central question, since
Phase 9's resync from an internal LIFX HTTP API endpoint supplied the true palette lengths
that no device could.

Closed at `tech_debt` with both audit findings remediated before archiving, and one
finding withdrawn as mistaken. Phase 8 retains its operator-approved exception: the
source-Tile restoration is unverified, `08-UAT-RESULTS.json` is deliberately absent, and a
synthetic two-role merge is prohibited.

Full details: [milestones/v1.2-ROADMAP.md](milestones/v1.2-ROADMAP.md) ·
audit: [milestones/v1.2-MILESTONE-AUDIT.md](milestones/v1.2-MILESTONE-AUDIT.md)

</details>

### 🚧 v2.0 Thread/IPv6 Support (Phases 10–14, In Progress)

**Milestone Goal:** A Thread device becomes a first-class device in this library: found,
addressed, controlled and animated without the caller needing to know it is on Thread. The
v1.1 wire-reliability findings are then revalidated over Thread, because every one of them
was measured on WiFi/IPv4.

- [ ] **Phase 10: Land the IPv6/Thread Branch** - Reconcile `feat/ipv6-thread-support` from `main` on its phase branch, so IPv6-only devices can be controlled and animated; merge only in the post-phase shipment workflow
- [ ] **Phase 11: mDNS Hardening** - Bring the mDNS leg to broadcast-grade quality: ephemeral-port bind regression test, `tm` transport field, synthetic mesh-scale tests, deterministic address selection, validation and honest docs
- [ ] **Phase 12: IPv6 Discovery Plumbing** - Family-aware `_discover_with_packet` bind, `find_by_ip()` for IPv6 literals, and an emulator-on-`::1` CI fixture
- [ ] **Phase 13: Merged Discovery** - `discover()` runs broadcast and mDNS legs merged by serial and `find_by_serial()` races both legs, with the existing contract proven intact by entry-gate invariant tests and a before-and-after measurement
- [ ] **Phase 14: Thread Revalidation and Docs** - SEED-001 measurements over Thread hardware, per-device-class evidence records or named gaps, and the consumer guidance and corrections docs

**Execution notes:**

- **Phase 10 is the critical path.** Nothing else in the milestone is testable on Thread
  hardware until the branch merges.

- **Phases 11 and 12 are file-disjoint and can run in parallel** once Phase 10 lands.
  Phase 11 lives in `network/mdns/`; Phase 12 lives in `network/discovery.py`, `api.py`'s
  `find_by_ip()` and the test fixtures.

- **Phase 13 is serial after both 11 and 12**: both merged functions live in `api.py` and
  consume the record-level generator shapes those phases finalise.

- **Phase 14 is hardware-gated** (Thread devices; CI has none) and must not block CI or
  any other phase. THREAD-05 closes incrementally: a device class closes when evidenced or
  as a named gap, never by waiting for hardware that does not exist yet.

- **No WiFi-measured constant may be retuned before Phase 14 measures it over Thread.**
  This is the project's spike-first discipline; it binds Phases 10 to 13.

## Phase Details

### Phase 10: Land the IPv6/Thread Branch

**Goal**: The reconciled IPv6/Thread series is complete and ready to ship from its phase branch, so a caller can control a device that has only an IPv6 address; merging the accepted tree to `main` happens only after the phase ships
**Depends on**: Nothing (first phase of v2.0; v1.2 shipped)
**Requirements**: IPV6-01, IPV6-02, IPV6-03, IPV6-04
**Success Criteria** (what must be TRUE):

  1. A caller can connect to, control and stream animation frames to a device that has only an IPv6 address, and every socket-creation site, including the animator's direct-UDP frame socket, derives its family from the target address
  2. Supplying a link-local address without a zone identifier raises an immediate `ValueError` naming the problem, instead of the silent 16 second timeout the branch's warning downgrade produced
  3. Address-family selection has exactly one implementation, a shared helper used by every socket-creation site, replacing the three duplicated `":" in ip` checks
  4. An `MdnsTransport.open()` that fails partway through endpoint creation leaves no socket behind
  5. The exact phase branch is functionally green, signed and ready for the post-phase shipment merge; patch coverage is advisory and operator-overridable, and the branch remains off `main` until shipment

**Plans**: 9/9 plans executed

Plans:
**Wave 1**

- [x] 10-01-PLAN.md — Rebase the three branch commits onto main as a pure replay, with an IPv6 end-to-end tracer proof against an emulator on `::1`, then measure the branch's patch-coverage debt into `10-COVERAGE-GAPS.md`

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 10-02-PLAN.md — Create `lifx.network.address` (validate_address/family_for/wildcard_for), adopt it at the three socket-creation sites (B9), gate the public IP entry points (B2), close the assigned coverage gaps

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 10-03-PLAN.md — B1 send-time family assertion, IPV6-04 `MdnsTransport.open()` leak and phantom-open-state fix with the R4 concurrency backstop, B4 honest mDNS docstrings, mDNS rewrite coverage top-up

**Wave 4** *(blocked on Wave 3 completion)*

- [x] 10-04-PLAN.md — `::1` emulator fixture (socket configured before bind), IPv6 end-to-end tests with per-test family assertions and proven frame delivery, `LIFX_REQUIRE_IPV6` must-not-skip CI cell
- [x] 10-05-PLAN.md — Extend `scripts/ipv6_thread_probe.py` into the Thread hardware UAT harness (`--serial` control stage, full matrix-state capture and restore, optional streaming stage, `--uat-output`) with its own test module

**Wave 5** *(blocked on Wave 4 completion)*

- [x] 10-06-PLAN.md — PR, CI green at 100% branch patch coverage verified against the gap list, recorded Thread hardware UAT gate with enforcing validators, fast-forward merge to main

**Wave 6** *(gap closure; blocked on completed Wave 5)*

- [x] 10-07-PLAN.md — Keep mDNS discovery productive when one record has a bare link-local address or an unrelated follow-up query send fails

**Wave 7** *(gap closure; blocked on Wave 6 completion)*

- [x] 10-08-PLAN.md — Make mDNS and general UDP endpoint creation cancellation-safe, descriptor-clean and reusable

**Wave 8** *(operator-directed gap closure; blocked on Wave 7 completion)*

- [x] 10-09-PLAN.md — Correct the shipment/coverage/UAT specification and make transport lifecycle transitions atomic under open/open and open/close races

### Phase 11: mDNS Hardening

**Goal**: The mDNS leg reaches broadcast-grade quality before it is promoted into the default discovery path: correct at mesh scale (proven synthetically), validated like the broadcast path, and documented honestly
**Depends on**: Phase 10 (parallel with Phase 12; file-disjoint)
**Requirements**: MDNS-01, MDNS-02, MDNS-03, MDNS-04, MDNS-05, MDNS-06, MDNS-07, MDNS-08
**Success Criteria** (what must be TRUE):

  1. mDNS queries bind an ephemeral port, and a regression test proves legacy-unicast replies are received without the test itself binding 5353, because CI runners run Avahi and the test would otherwise measure the runner rather than the fix
  2. A caller can read how a device was reached from the `tm` field on `LifxServiceRecord`; an absent, unparsable or unrecognised value reports as unknown and never raises, and no expansion of the undocumented `tm` key is asserted anywhere
  3. Synthetic multi-packet tests prove that records for one service instance accumulate across response packets and that an SRV target whose address records did not fit a reply triggers a follow-up A/AAAA query
  4. Address selection is deterministic and documented (ULA, then GUA, then scoped link-local) with every discovered address retained on the record; a TXT `id` failing the broadcast serial validation is rejected; TTL 0 goodbye packets and cache-flush bits are honoured
  5. The module's docstrings match its actual behaviour, with the deleted multicast membership no longer claimed and the unicast-only trade recorded as a known limitation

**Plans**: TBD

### Phase 12: IPv6 Discovery Plumbing

**Goal**: The targeted-lookup leg works over IPv6: `_discover_with_packet` binds by family, `find_by_ip()` accepts an IPv6 literal, and real IPv6 end-to-end tests run on every CI runner
**Depends on**: Phase 10 (parallel with Phase 11; file-disjoint)
**Requirements**: FIND-06
**Success Criteria** (what must be TRUE):

  1. `find_by_ip()` returns the device for an IPv6 literal instead of returning `None`
  2. `_discover_with_packet` derives its bind address and socket family from the target address rather than unconditionally binding `0.0.0.0`
  3. An emulator bound to `::1` is available as a test fixture, giving real IPv6 end-to-end coverage on every CI runner without hardware

**Plans**: TBD

### Phase 13: Merged Discovery

**Goal**: Thread devices are found by default: `discover()` runs broadcast and mDNS legs concurrently merged by serial, `find_by_serial()` races both legs, and the existing discovery contract survives measurably intact
**Depends on**: Phase 11 and Phase 12 (both merged functions live in `api.py` and consume the record-level generator shapes those phases finalise)
**Requirements**: FIND-01, FIND-02, FIND-03, FIND-04, FIND-05, FIND-07, FIND-08
**Success Criteria** (what must be TRUE):

  1. ENTRY GATE, satisfied before any merge code lands: the invariant test suite (overall timeout, idle timeout resetting on consumer resume, first-wins per-serial dedup, DoS source and serial validation) and the before-and-after measurement harness both exist and pass against the pre-merge `discover()`
  2. `discover()` yields Thread devices with no caller opt-in, streaming as found with serial-keyed first-wins merge, and degrades to today's broadcast-only behaviour when the mDNS leg fails or is unavailable, without `asyncio.TaskGroup`, which the Python 3.10 floor rules out
  3. An mDNS-sourced device is unicast-verified before it is yielded, so `discover()` never yields a device that is not answering right now, closing both the SRP stale-lease liveness hole and the mDNS spoofing exposure
  4. `find_by_serial()` races a broadcast leg and an mDNS leg, first hit wins, and the losing leg is cancelled and reaped with no leaked task or socket
  5. The timing change imposed on existing callers is a measured before-and-after number against the fleet including emulator CI wall time, and the TXT `id` versus broadcast serial check for firmware 3.70 to 3.99 WiFi devices is recorded as the low-priority, non-gating verification it is

**Plans**: TBD

### Phase 14: Thread Revalidation and Docs

**Goal**: The v1.1 wire-reliability findings are revalidated over Thread with measurements from this fleet (SEED-001), evidenced per device class, and the consumer guidance and documentation corrections ship. Hardware-gated: must not block CI or any other phase
**Depends on**: Phase 13 (needs the whole transport stack)
**Requirements**: THREAD-01, THREAD-02, THREAD-03, THREAD-04, THREAD-05, DOCS-04, DOCS-05, DOCS-06
**Success Criteria** (what must be TRUE):

  1. Discovery coverage over Thread is measured across repeated rounds, never a single round, which is the Spike 005 lesson this project already paid for
  2. The retry schedule's WiFi-tuned constants are measured against Thread ack RTT, and the achievable animation frame rate over Thread is measured; the measured ceiling is the deliverable, and no constant changes without this evidence
  3. Border router advertisement staleness is measured directly, by unplugging a Thread device and timing when it stops being advertised
  4. Every device class carries either a Thread evidence record or a named gap: `MatrixLight` closes now on two devices, `CeilingLight`, `MultiZoneLight` and single-zone `Light` close as migrations land, and `InfraredLight` and `HevLight` close as named gaps; the phase closes when every class has one or the other, not when every class is evidenced
  5. A broadcast-first consumer can read what changes for them and how to reach Thread devices, the known limitations are documented (IPv4-multicast query leg, unicast-only reception, no unsolicited announcements, mesh scale proven synthetically), and the false `asyncio.TaskGroup` claim in `CLAUDE.md` is corrected

**Plans**: TBD

## Progress

**Execution Order:** 10 → (11 ∥ 12) → 13 → 14

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Ceiling Save-on-Exit | v1.0 | 1/1 | Complete | 2026-06-12 |
| 1. Unify duplicated discovery loops | post-v1.0 | 5/5 | Complete | 2026-06-13 |
| 2. Discovery Re-broadcast | v1.1 | 2/2 | Complete | 2026-07-16 |
| 3. Retry Schedule Reshape | v1.1 | 3/3 | Complete | 2026-07-17 |
| 4. Animation Flow Control | v1.1 | 13/13 | Complete | 2026-07-17 |
| 5. Reliability Documentation | v1.1 | 6/6 | Complete | 2026-07-18 |
| 6. Generated Theme Library | v1.2 | 2/2 | Complete | 2026-08-15 |
| 7. Taxonomy & Legacy Dispositions | v1.2 | 3/3 | Complete | 2026-08-15 |
| 8. Hardware Fidelity Validation | v1.2 | 4/4 | Complete | 2026-08-16 |
| 9. Theme Data Contract & Docs | v1.2 | 2/2 | Complete | 2026-08-27 |
| 10. Land the IPv6/Thread Branch | v2.0 | 9/9 | Ready to ship | 2026-08-28 |
| 11. mDNS Hardening | v2.0 | 0/TBD | Not started | - |
| 12. IPv6 Discovery Plumbing | v2.0 | 0/TBD | Not started | - |
| 13. Merged Discovery | v2.0 | 0/TBD | Not started | - |
| 14. Thread Revalidation and Docs | v2.0 | 0/TBD | Not started | - |
