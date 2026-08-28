---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: Thread/IPv6 Support
current_phase: 10
current_phase_name: Land the IPv6/Thread Branch
status: verified
stopped_at: "Phase 10 verified on its phase branch; ready for shipment"
last_updated: "2026-08-28T09:31:00+10:00"
last_activity: 2026-08-28
last_activity_desc: Phase 10 plan 09 closed the lifecycle blocker and re-verification passed
state_head: e31185c07476807768043343f3af7c70bfd16710
progress:
  total_phases: 5
  completed_phases: 0
  total_plans: 9
  completed_plans: 9
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-08-27 after opening the v2.0 milestone)

**Core value:** Commands stick, devices are found, streaming never starves control traffic, and a theme by name looks like the theme of that name in the LIFX app.
**Current focus:** Phase 10 — Land the IPv6/Thread Branch

## Current Position

Phase: 10 (Land the IPv6/Thread Branch) — VERIFIED, READY TO SHIP
Plan: 9 of 9
Total Plans in Phase: 9
Status: All 9 plans executed and re-verification passed on the phase branch. D-26 requires this
tree to remain off `main` until the post-phase shipment workflow. Patch coverage remains recorded
as advisory evidence; UAT restoration remains best-effort.
Last activity: 2026-08-28 — Plan 10-09 closed the transport lifecycle blocker; 3,731 tests passed

Progress: [░░░░░░░░░░] 0%

Execution order: 10 → (11 ∥ 12, file-disjoint) → 13 → 14. Phase 14 is hardware-gated
and must not block CI or any other phase.

## Performance Metrics

**Velocity (project to date):** 41 plans across v1.0 (1), post-v1.0 Phase 1 (5),
v1.1 (24, of which 2 are superseded closure records; read SUMMARY frontmatter, not
counts) and v1.2 (11 plans, 28 tasks, 87 commits over 13 days).

Per-plan metrics for shipped milestones live with their archives under
`.planning/milestones/`.

*Updated after each plan completion*
**Per-Plan Metrics:**

| Plan | Duration | Tasks | Files |
|------|----------|-------|-------|
| Phase 10 P01 | 25 min | 2 tasks | 12 files |
| Phase 10 P02 | 35 min | 3 tasks | 12 files |
| Phase 10 P03 | 36 min | 4 tasks | 8 files |
| Phase 10 P04 | 30 min | 3 tasks | 4 files |
| Phase 10 P05 | 23 min | 3 tasks | 3 files |
| Phase 10 P07 | 18 min | 3 tasks | 5 files |
| Phase 10 P08 | 10 min | 2 tasks | 4 files |
| Phase 10 P09 | 25 min | 2 tasks | 11 files |

## Accumulated Context

### Roadmap Evolution

- v1.1 roadmap created 2026-07-16 (Phases 2 to 5, from the spike series blueprints); shipped 2026-07-26
- v1.2 roadmap created 2026-08-14 (Phases 6 to 9, from the hardware theme capture); shipped 2026-08-27
- v2.0 roadmap created 2026-08-27 (Phases 10 to 14, from the four-document research pass in `.planning/research/`): Land the IPv6/Thread Branch, mDNS Hardening, IPv6 Discovery Plumbing, Merged Discovery, Thread Revalidation and Docs

### Decisions

Decisions are logged in the PROJECT.md Key Decisions table. Recent decisions shaping
this milestone (all 2026-08-27 unless noted):

- `discover()` gains an mDNS leg merged by serial rather than staying broadcast-only; accepted cost is a timing change for every caller, which FIND-07 measures rather than assumes
- `find_by_serial()` races both legs, first hit wins; neither leg alone covers the fleet
- `find_by_ip()` accepts IPv6 literals; `find_by_label()` deliberately does not change
- Fleet-scale mDNS paths (cross-packet accumulation, follow-up A/AAAA) are proven synthetically first, on hardware later
- The mDNS ephemeral-port bind is a requirement in its own right (MDNS-01): an IPv4 defect, not a Thread feature
- `LifxServiceRecord` keeps the wire name `tm`; no expansion of the undocumented key may be asserted anywhere
- No WiFi-measured constant is retuned before Phase 14 measures it over Thread (spike-first discipline, 2026-07-16 lineage)
- [Phase 10]: Phase 10 topology: replay the 23 planning commits on top of the three rebased IPv6 code commits; feat/ipv6-thread-support and gsd/phase-10-land-the-ipv6-thread-branch resolve to the same SHA — Rebasing the feature branch in isolation would have dropped 29 tracked planning files from the working tree, leaving downstream plans unable to read their own instructions
- [Phase 10]: scripts/ipv6_thread_probe.py is unmeasured by --cov rather than uncovered; plan 10-05 owns the treatment and must not widen --cov inside a 100% patch target — Widening --cov would drop 521 unmeasured lines into the 100% patch gate in the same PR, which is the false-green pressure threat T-10-19 exists to prevent
- [Phase 10]: lifx.network.address is the single home of address-family selection and address validation, consumed by all three socket-creation sites and all four public entry points — IPV6-03 audit finding B9: the same colon-membership heuristic was written out by hand at three sites and Device.__init__ held a fourth, independent opinion
- [Phase 10]: A zone-less IPv6 link-local address raises ValueError at Device.__init__, Device.from_ip(), Device.connect() and find_by_ip() instead of logging a warning and proceeding — IPV6-02 audit finding B2: the warning cost a silent 16 second timeout for a permanent configuration error. connect() was the fourth entry point the cross-AI review found unguarded
- [Phase 10]: The three coverage-exemption markers on the moved address checks were removed rather than carried into the new module, and every branch got a unit test — D-04: the markers existed because the branches were awkward to reach through a Device constructor, not because they were unreachable. Carrying them into a new file would be the weakening SPEC prohibition 3 forbids
- [Phase 10]: The B1 send-time family assertion is a pre-send guard placed after the transport-liveness check, so a dead endpoint still reports Socket not open — SPEC AC 11 and threat T-10-09: error_received, _FATAL_SOCKET_ERRNOS and _endpoint_lost are untouched, pinned by a parameterised EHOSTUNREACH/EHOSTDOWN/ENETUNREACH regression test, because converting peer-unreachable storms into raises would tear down healthy request flows
- [Phase 10]: A failed MdnsTransport.open() clears _socket, _protocol and _transport together as well as closing the descriptor — Cross-AI review finding 7: closing alone leaves is_open reporting True and the already-open early return refusing to rebuild, producing a transport that is descriptor-clean and permanently unusable
- [Phase 10]: No _is_opening guard was added to MdnsTransport.open(); the R4 concurrency backstop is kept purely as a regression pin — The backstop was written first and passed against the unfixed code: no await sits between the already-open check and the _protocol assignment, so the early return is atomic in practice. The plan asked for a minimal fix, not a restructure
- [Phase 10]: 10-COVERAGE-GAPS.md was corrected for the B1 misattribution but deliberately not annotated as closed — It is the independent checklist plan 10-06 verifies against before the PR opens; marking it done inside the plan that closed it would invite a rubber-stamp, so the closure evidence lives in 10-03-SUMMARY.md instead
- [Phase 10]: The ::1 emulator hosts a matrix-capable Tile rather than a plain colour light, while the library-side object under test stays a plain Light — The emulator's Set64Handler returns early when the device has no matrix capability, so against a plain colour light the animation test could only ever prove a datagram was sent, never that a frame arrived and was applied
- [Phase 10]: IPV6_V6ONLY is set by a test-only EmulatedLifxServer subclass that owns socket creation, and only read back in the fixture — Setting the option after a bind raises EINVAL on macOS and the stock start() binds internally via local_addr, so owning socket creation is the only way to set it explicitly; getsockopt stays legal on a bound socket
- [Phase 10]: The must-not-skip CI gate is a conditional env var on the existing pytest step, not a new job — LIFX_REQUIRE_IPV6=1 on the ubuntu/Python 3.10 cell flips the ipv6_available probe from skip to fail; that cell is present in every matrix configuration including the reduced ubuntu-only path, so no artefact plumbing or junit parsing is needed
- [Phase 10]: scripts/ipv6_thread_probe.py stays OUT of the global --cov and codecov.yml is untouched; the probe helpers are covered by a scoped local assertion instead — The probe is unmeasured, not uncovered. Widening --cov would drop 521 lines of a hardware script whose three original stages need real Thread devices into a PR carrying a 100 percent branch patch target, creating pressure to lower the target or add pragma markers (threat T-10-19). The six new helpers are factored out and asserted to have zero missing lines and zero partial branches. Plan 10-06 verifies this treatment rather than reopening it.
- [Phase 10]: The UAT harness refuses --uat-output without --serial — An honest not_run is always a valid stage value, but a record naming no device cannot satisfy SPEC AC 19 and would be a repudiation surface (T-10-14) rather than evidence.
- [Phase 10]: Mutation testing replaced the unreachable TDD RED gate in plan 10-05 Task 3 — The plan assigns implementation to Tasks 1 and 2 and tests to Task 3, so a red commit was impossible. Five mutations of the probe were applied and reverted; the one that survived exposed that the outer restore finally had no test that could fail, which is why a KeyboardInterrupt test now exists.
- [Phase 10]: Bare link-local mDNS records are skipped only inside the public discovery sweep; direct construction and all four user-input entry points remain strict — Improves availability for mixed-quality advertisements without weakening IPV6-02 or duplicating the shared IPV6-03 validator
- [Phase 10]: Resolved mDNS records are yielded before auxiliary sends, with separate successful-send and attempt ledgers — Preserves exact-once delivery while allowing one retry and bounding all traffic-bearing targets to 64
- [Phase 10]: Patch coverage is measured from immutable base b4e9b365f4f388ad4dd6800be8e7f9144f027bd6 using branch-aware coverage.py JSON — Provides one deterministic fail-closed authority for plans 10-07 and 10-08 without a dependency or coverage-configuration change
- [Phase 10]: MdnsTransport serialises open() calls with an asyncio.Lock so a concurrent opener waits for cancellation cleanup and then establishes the replacement endpoint
- [Phase 10]: MdnsTransport.close() remains outside the open lock so a close-racing-cancelled-open schedule cannot deadlock
- [Phase 10]: Both UDP transports wrap only OSError after cleanup; cancellation and other BaseException failures retain their original identity
- [Phase 10]: The phase branch MUST remain off main until Phase 10 ships; merging to main is the post-phase shipment action, so branch-only delivery is not a verification gap
- [Phase 10]: Patch coverage remains recorded but is advisory and operator-overridable because it does not affect runtime functionality
- [Phase 10]: Transport lifecycle races and DeviceConnection opener-waiter failures are blocking defects and require deterministic regression fixes
- [Phase 10]: UAT state restoration is best-effort operator hygiene and does not gate the control result or phase completion

### v2.0 Working Notes

- Branch to land: `feat/ipv6-thread-support` (`b49400b`, `b88cdb9`, `2f884f5`); pre-rebase state preserved on `backup/ipv6-thread-pre-rebase`
- Thread hardware today (measured 2026-08-28): six IPv6-only devices on OMR prefix `fd00:2::/64`, covering two `MatrixLight`s (Test Candle `d073d5e00001`, Test Tube `d073d5e00002`), `CeilingLight` `d073d5e00003`, `MultiZoneLight` `d073d5e00004` and two `Light`s (`d073d5e00005`, `d073d5e00006`); the planned migrations have landed. `InfraredLight` and `HevLight` close as named gaps under THREAD-05. The OMR prefix re-derives whenever the border router re-forms the mesh, so match on serial and never on prefix; full inventory in PROJECT.md
- `asyncio.TaskGroup` is unavailable (3.11 or later; the library ships 3.10 for LedFx) and its cancel-siblings semantics would be wrong for the merge anyway
- FIND-02 invariant tests and the FIND-07 measurement harness are ENTRY GATES for Phase 13, not follow-up work
- Deeper phase detail: `.planning/research/ARCHITECTURE.md` (build order, test seams) and `.planning/research/PITFALLS.md` (12 pitfalls, branch audit B1 to B9)

### Pending Todos

- Adopt the `**D-NN**` decision-ID grammar in v2.0 CONTEXT.md files so `check.decision-coverage-plan` can parse decisions; v1.1's `D5-NN` parsed as zero and the gate passed vacuously (open-gsd/gsd-core#2347)

### Blockers/Concerns

- **Hardware validation cannot run in CI.** CI has no Thread hardware; THREAD-01..04 are UAT-style measurement runs against the two Thread MatrixLights and the fleet. Automated emulator and synthetic tests remain the functional evidence; patch coverage is recorded separately and is advisory under D-27. Repeated rounds remain mandatory for any coverage or loss claim (Spike 005 lesson).
- **Verification staleness heuristic (open-gsd/gsd-core#2348).** `readVerificationStatus` overrides a declared `passed` with `stale` whenever any SUMMARY is newer than the VERIFICATION file. Write or refresh each phase VERIFICATION file after the last summary. Do not fix by touching mtimes.
- **Decision-coverage gate has never fired here (open-gsd/gsd-core#2347).** Mitigation is the `**D-NN**` grammar todo above; until adopted, decision coverage is only verified by the plan-checker reading CONTEXT.md by hand.
- **`plan-scan.cjs` inflates `completed_plans` for superseded plans (open-gsd/gsd-core#2349).** Read SUMMARY frontmatter (`status: superseded`), not counts.
- **Do not run `state sync` unchecked.** `cmdStateSync` lacks the ratchet `cmdStateJson` applies, so the write path can regress protected values. When citing the archived predecessor repo, always qualify refs; both repos number issues from 1.

## Deferred Items

Items acknowledged and carried forward from previous milestone closes:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| Persistence | PERS-01: extract `state_file` save/load into reusable mixin | Deferred | 2026-06-11 |
| Thread/IPv6 | THREAD-01 (SEED-001): revalidate wire behaviour over Thread/IPv6 | Activated in v2.0 as THREAD-01..05 (Phase 14) | 2026-07-16 |
| Seed | SEED-001-thread-ipv6-revalidation, dormant at the v1.1 and v1.2 closes | Fired 2026-08-27; live in v2.0 | 2026-07-26 |
| Docs | 02-01-SUMMARY.md carries no `requirements-completed` frontmatter; DISC-01/02 evidenced only in 02-VERIFICATION.md (cross-checked manually at the v1.1 audit) | Acknowledged, deferred | 2026-07-26 |
| Decision | D5-09 "publish behaviour, not tuning constants" is disputed by the operator and remains OPEN; spike candidate 006 would measure the cap impact | Open decision | 2026-07-26 |
| Verification | v1.1 `override_closeout` overrides (3): Phase 2 and Phase 4 resolver-stale false negatives (open-gsd/gsd-core#2348) and Phase 3's `human_needed` manual UAT | Recorded at close | 2026-07-26 |
| Style | No-em-dash house style: roughly 200 em dashes across `docs/`, deferred by the user during v1.2 Phase 7 UAT. Recast each sentence rather than swapping the character | Open, repo-wide | 2026-08-27 |
| Verification | v1.2 `override_closeout` overrides (1): SEED-001 acknowledged at close. Phase 8 retains its operator-approved exception (Tile restoration unverified, `08-UAT-RESULTS.json` deliberately absent, synthetic merge prohibited) | Recorded at close | 2026-08-27 |

## Session Continuity

Last session: 2026-08-28T09:31:00+10:00
Stopped at: Phase 10 verified on its phase branch; ready for shipment
Resume file: None

## Operator Next Steps

- Ship the verified phase with `/gsd-ship 10`; that post-phase workflow owns the merge to `main`
