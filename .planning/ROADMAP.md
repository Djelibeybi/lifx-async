# Roadmap: lifx-async

## Milestones

- ✅ **v1.0 Ceiling Save-on-Exit**: Phase 1, shipped 2026-06-12 ([archive](milestones/v1.0-ROADMAP.md))
- ✅ **Post-v1.0 Discovery unification**: Phase 1, verified 2026-06-13, archived in `milestones/v1.1-phases/01-unify-duplicated-discovery-loops/`
- ✅ **v1.1 Wire Reliability**: Phases 2–5, shipped 2026-07-26 ([archive](milestones/v1.1-ROADMAP.md))
- ✅ **v1.2 Theme Library Update**: Phases 6–9, shipped 2026-08-27 ([archive](milestones/v1.2-ROADMAP.md))
- ✅ **v2.0 Thread/IPv6 Support**: Phases 10–14, shipped 2026-09-05 ([archive](milestones/v2.0-ROADMAP.md))

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

<details>
<summary>✅ v2.0 Thread/IPv6 Support (Phases 10–14), SHIPPED 2026-09-05</summary>

A Thread device became a first-class device: found by default (`discover()` merges a UDP
broadcast leg and a unicast-verified mDNS leg by serial), addressed by IPv6 literal
(`find_by_ip()`), raced concurrently in `find_by_serial()`, and self-identified via
`Device.connectivity`. The mDNS leg reached broadcast-grade quality (ephemeral-port bind,
RFC 6762-compliant goodbye/cache-flush handling, bounded fail-closed record admission).
Every v1.1 wire-reliability finding was then revalidated against a real 8-device Thread
fleet.

- [x] Phase 10: Land the IPv6/Thread Branch (9/9 plans), completed 2026-08-28 (PR #210)
- [x] Phase 11: mDNS Hardening (14/14 plans), completed 2026-08-29
- [x] Phase 12: IPv6 Discovery Plumbing (5/5 plans), completed 2026-08-29
- [x] Phase 13: Merged Discovery (7/7 plans), completed 2026-08-31
- [x] Phase 14: Thread Revalidation and Docs (6/6 plans), completed 2026-09-04

28/28 requirements satisfied, 41/41 plans complete. Closed at `override_closeout`: two
dormant seeds (SEED-002 WiFi-control staleness, SEED-003 lock `Animator` to WiFi) and one
Phase 13 deferred item (coordinator teardown test hang) acknowledged rather than blocking
close — see `.planning/STATE.md` Deferred Items.

Full details: [milestones/v2.0-ROADMAP.md](milestones/v2.0-ROADMAP.md)

</details>

## Progress

| Milestone | Phases | Status | Shipped |
|-----------|--------|--------|---------|
| v1.0 Ceiling Save-on-Exit | 1 | Complete | 2026-06-12 |
| Post-v1.0 Discovery unification | 1 | Complete | 2026-06-13 |
| v1.1 Wire Reliability | 2–5 | Complete | 2026-07-26 |
| v1.2 Theme Library Update | 6–9 | Complete | 2026-08-27 |
| v2.0 Thread/IPv6 Support | 10–14 | Complete | 2026-09-05 |
