---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: Thread/IPv6 Support
current_phase: 10
current_phase_name: Land the IPv6/Thread Branch
status: ready_to_ship
stopped_at: Phase 12 complete; Phase 10 remains ready to ship
last_updated: "2026-08-29T13:34:05.481Z"
last_activity: 2026-08-29
last_activity_desc: Phase 12 complete; Phase 10 remains ready to ship
state_head: 0b5e57cb908d6904768a08de282d731fd91e14bb
progress:
  total_phases: 5
  completed_phases: 3
  total_plans: 28
  completed_plans: 28
  percent: 60
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-08-27 after opening the v2.0 milestone)

**Core value:** Commands stick, devices are found, streaming never starves control traffic, and a theme by name looks like the theme of that name in the LIFX app.
**Current focus:** Phase 10 — Land the IPv6/Thread Branch

## Current Position

Phase: 10 — Land the IPv6/Thread Branch
Plan: 9 of 9
Status: Ready to ship
Last activity: 2026-08-30 - Completed quick task 260830-ea6: Adjust the pytest retry configuration as described above
Progress: [██████░░░░] 60%

Execution order: 10 → (11 ∥ 12, file-disjoint) → 13 → 14. Phase 14 is hardware-gated
and must not block CI or any other phase.

## Performance Metrics

**Velocity:** 41 plans shipped before v2.0; archived milestone metrics live under `.planning/milestones/`.
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
| Phase 11 P01 | 18 min | 3 tasks | 9 files |
| Phase 11 P02 | 22 min | 2 tasks | 5 files |
| Phase 11 P03 | 23 min | 3 tasks | 2 files |
| Phase 11 P04 | 10 min | 2 tasks | 10 files |
| Phase 11 P05 | 15 min | 2 tasks | 8 files |
| Phase 11 P06 | 27 min | 2 tasks | 4 files |
| Phase 11 P07 | 8 min | 3 tasks | 6 files |
| Phase 11 P08 | 14 min | 2 tasks | 4 files |
| Phase 11 P09 | 9 min | 3 tasks | 4 files |
| Phase 11 P10 | 47 min | 2 tasks | 5 files |
| Phase 11 P11 | 22 min | 2 tasks | 2 files |
| Phase 11 P12 | 38 min | 2 tasks | 2 files |
| Phase 12 P01 | 17 min | 2 tasks | 5 files |
| Phase 12 P02 | 7 min | 2 tasks | 2 files |
| Phase 12 P03 | 4 min | 2 tasks | 1 files |
| Phase 12 P04 | 15 min | 3 tasks | 5 files |
| Phase 12 P05 | 32 min | 3 tasks | 2 files |

## Accumulated Context

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
- [Phase 11]: Connectivity is adopted with registry-derived metadata — Future serial de-duplication must preserve Thread classification without changing address, routing, retry, or tuning behaviour
- [Phase 11, superseded 2026-08-28 by D-15]: The earlier decision treated admitted addresses as lossless within the 1,024-owner cache. D-15 now exact-deduplicates A/AAAA identities, admits at most 256 per owner and 1,024 per sweep, rejects and privacy-safely counts unseen excess identities without eviction, makes owner overflow or sweep exhaustion permanent for the call, and refuses selection, resolution, or follow-up from incomplete state while leaving caller deadlines unchanged.
- [Phase 11, supersession recorded 2026-08-28 as D-16]: The earlier D-03 integration interpretation preserved a public factory. D-16 keeps `_LifxServiceRecord`, `_discover_lifx_services`, and `_create_device_from_record` private together with no public or compatibility alias; supported callers use `discover_devices_mdns()` or `lifx.api.discover_mdns()`.
- [Phase 11]: mDNS TXT construction metadata and SRV endpoints resolve only through full live-set consensus; record ordering never selects a trusted winner.
- [Phase 11]: Goodbye scheduling indexes only complete RR identities under TTL-zero grace; ordinary retained addresses stay outside timer traversal.
- [Phase 11]: Recoverable mDNS parsing is limited to ValueError, IndexError, and struct.error, followed by one privacy-safe rejection summary per sweep.
- [Phase 11]: Packet-source fallback is validated and deferred until sweep completion so later advertised endpoints win without arrival-order bias.
- [Phase 11]: Deletion-only source files remain anti-weakening and public-surface inputs but are excluded from changed-executable coverage.
- [Phase 11]: IPv4 UDP loopback availability is mandatory evidence for the MDNS-01 legacy-unicast transport proof.
- [Phase 11]: Preserve the completed D-15 and D-16 authority commits without replay or amendment. — Current-file and draft recovery is distinct from historical authority work.
- [Phase 11]: Keep branch-history disposition in Plan 11-08 and fresh full gates in Plan 11-09. — Plan 11-07 is limited to current-file sanitisation, draft guidance, and structural closeout.
- [Phase 11]: Preserve history under the Plan 11-08 `no-rewrite` disposition. — The operator confirmed the historical candidate is an approved stable pseudonym; Plan 11-09 owns fresh privacy and full gates.
- [Phase 11]: Only exact canonical LIFX service-instance ownership creates mDNS construction provenance.
- [Phase 11]: A and AAAA records remain bounded candidates until linked by a live exact-service SRV record.
- [Phase 11]: TXT construction metadata uses one-pass effective-value consensus with immediate conflict rejection.
- [Phase 11]: Charge only exact retained variable payload and release the stored cost only when expiry removes the cached identity.
- [Phase 11]: Filter unusable mDNS addresses before the IPv4, ULA, GUA, scoped-link-local ranking and use lexical same-class order.
- [Phase 12]: Select the wildcard and IPv4-only broadcast capability from the validated target family, close both generator ownership layers with `aclosing`, and prove behaviour from the actual endpoint without replacing emulator traffic.
- [Phase 12]: Targeted find_by_ip preserves the already validated caller literal through device construction.
- [Phase 12]: Representation tests exercise the public API and real discovery parser while replacing only transport delivery.
- [Phase 12]: Invalid-target regressions use a fail-on-construction transport sentinel to prove validation precedes network setup.
- [Phase 12]: Retain concrete discovery transports and endpoints in per-test observations so lifecycle assertions use actual OS-managed objects.
- [Phase 12]: Synchronise cancellation on real endpoint-open, receive-started, and close-completed events without sleeps or polling.
- [Phase 12]: Keep concurrent independence and cancellation/reuse in separate public-API tests.
- [Phase 12]: Keep Windows IPv6 emulator eligibility behind exact opt-in and exact CI node selection.
- [Phase 12]: Require exact current-revision CI job logs, not aggregate green status, for D-10.
- [Phase 12]: Normalise AF_INET6 datagram destinations to canonical four-field socket addresses at send time.
- [Phase 12]: Resolve numeric and named IPv6 zones at the UDP send boundary and pass scope in the native sockaddr field.
- [Phase 12]: Report invalid IPv6 zone resolution as an immediate LifxNetworkError while keeping the endpoint reusable.

### v2.0 Working Notes

- Branch to land: `feat/ipv6-thread-support` (`b49400b`, `b88cdb9`, `2f884f5`); pre-rebase state preserved on `backup/ipv6-thread-pre-rebase`

Thread hardware endpoint values remain operator-controlled evidence outside the repository and must be re-derived before Phase 14 validation; this planning state intentionally records no serial, address, hostname, or mapping value.

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
- PR #219 DCO is blocked by three earlier unsigned Phase 12 documentation commits; history rewrite or repository-owner override requires explicit authorisation.

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 260830-ea6 | Adjust the pytest retry configuration as described above | 2026-08-30 | e1ba123 | [260830-ea6-adjust-the-pytest-retry-configuration-as](./quick/260830-ea6-adjust-the-pytest-retry-configuration-as/) |

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

Last session: 2026-08-29T12:50:45.012Z
Stopped at: Phase 12 complete; Phase 10 remains ready to ship
Resume file: None

## Operator Next Steps

- Resolve PR #219's pre-existing DCO history failure, then ship the verified Phase 12 branch.
- Ship the already verified Phase 10 branch separately when ready.
