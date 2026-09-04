---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: Thread/IPv6 Support
current_phase: 14
status: completed
stopped_at: Phase 14 complete — all phases complete
last_updated: "2026-09-04T12:00:03.566Z"
last_activity: 2026-09-04
last_activity_desc: Phase 14 complete
state_head: ed6a04d8197527a7291d17cfe0168440bc0a0ba4
progress:
  total_phases: 5
  completed_phases: 5
  total_plans: 41
  completed_plans: 41
  percent: 100
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-08-31 after Phase 13 completion)

**Core value:** Commands stick, devices are found, streaming never starves control traffic, and a theme by name looks like the theme of that name in the LIFX app.
**Current focus:** Phase 14 — Thread Revalidation and Docs

## Current Position

Phase: 14
Plan: Not started
Status: All phases complete
Last activity: 2026-09-04 — Phase 14 complete
Progress: [████████░░] 80%

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
| Phase 13 P01 | 29 min | 3 tasks | 10 files |
| Phase 13 P02 | 23 min | 2 tasks | 5 files |
| Phase 13 P03 | 29 min | 2 tasks | 6 files |
| Phase 13 P04 | 20 min | 2 tasks | 6 files |
| Phase 13 P05 | 15 min | 2 tasks | 2 files |
| Phase 14 P01 | 34 min | 2 tasks | 6 files |
| Phase 14 P05 | 25 min | 3 tasks | 10 files |
| Phase 14 P02 | 40 min | 2 tasks | 4 files |
| Phase 14 P03 | 49min | 3 tasks | 10 files |
| Phase 14 P04 | 45min | 3 tasks | 2 files |

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
- [Phase 13]: Keep discover() UDP-only at the entry gate while exposing the identical path as discover_udp().
- [Phase 13]: Pass caller-selected discovery observation sinks explicitly to producers instead of relying on ContextVar propagation.
- [Phase 13]: Keep the canonical measurement baseline on direct discover_devices() so coordinator overhead remains measurable.
- [Phase 13]: Keep emulator mDNS injection private, context-local, and generator-owned to exclude ambient multicast I/O.
- [Phase 13]: Store and replay only accepted raw DiscoveryResponse records; construct caller-specific devices after fan-out.
- [Phase 13]: Keep compatible UDP sharing process-wide and active-only across caller event loops.
- [Phase 13]: Carry observation sinks and caller deadlines explicitly on subscriptions.
- [Phase 13]: Share discover and discover_udp while preserving direct find_by_ip and discover_devices paths.
- [Phase 13]: Use GetColor for every current supported classifier outcome; unsupported products drop locally and exact Echo remains synthetic future-proofing.
- [Phase 13]: Treat sixteen concurrent probes as a reasoned D-07 safety bound, not a measured optimum.
- [Phase 13]: Start one caller deadline before consuming mDNS records so queue wait, retries, and cleanup cannot receive fresh windows.
- [Phase 13]: Preserve standalone mDNS propagation and detail logging while merged typed failures retain only bounded fields.
- [Phase 13]: Merged discovery uses one caller-origin deadline across shared UDP and verified mDNS.
- [Phase 13]: First-valid canonical serial wins; later source occurrences emit duplicate observations.
- [Phase 13]: Typed mDNS failure events suppress the defensive outer fallback to preserve exactly-once diagnostics.
- [Phase 13]: Repeated cancellation is re-raised only after shielded cleanup finalises both source generators.
- [Phase 13]: Canonicalise serial lookup input once before creating either discovery source.
- [Phase 13]: Race shared UDP records and verified mDNS devices under one caller-origin wall deadline.
- [Phase 13]: Construct UDP winners only after both source legs have been cancelled and reaped.
- [Phase 13]: Suspend winner pumps at the yield boundary until aggregate cleanup owns finalisation.
- [Phase 14]: THREAD-02 request-observer seam: private task-attribute selector on DeviceConnection, propagated explicitly into _transmit_and_listen(), never read from ambient state — Mirrors the existing discovery-observer pattern; accepted_ns sampled at dequeue (before validation) so it excludes validation work but includes receiver queueing/wake latency
- [Phase 14]: Removed CLAUDE.md from test_phase_contract.py's _REQUIRED_QUERY_MODEL_PATHS rather than scoping the new no-duplication test around it — The two requirements on the same file were mutually exclusive once D-24 made CLAUDE.md import-only; AGENTS.md alone now carries the shared mDNS query-model prose the contract checks
- [Phase 14]: CLAUDE.md is reduced to a literal @AGENTS.md import plus one Claude-specific note about Skill() invocation — No other genuinely Claude-only guidance was found in the original file after removing ~460 lines of drifted architecture duplication
- [Phase 14]: [Phase 14] Staleness absence is defined as BOTH discover() and discover_mdns() missing the target on one poll, never either leg alone — discover() reflects unicast-verified liveness and can go absent within one poll of disconnect, while discover_mdns() reflects border-router advertisement and can keep reporting the device far longer; an either-leg predicate would confirm expiry at unicast-liveness speed and publish that as the SRP lease, a materially different and smaller number than THREAD-04 actually asks for
- [Phase 14]: Animation evidence names only the four AnimatorStats fields that exist (packets_sent, total_time_ms, gated, acks_outstanding); acks_outstanding is never narrated as ACK-received/expiry evidence — AckGate.sweep() prunes expired probes silently, so a falling acks_outstanding is ambiguous between "the device acknowledged" and "the probe expired unacknowledged"; the closed animation-rate schema has no field that could hold such a narration, proven by a dedicated negative test
- [Phase 14]: Plan 14-02 built the manifest, five journals, schedules, statistics and deterministic products as one coherent unit rather than splitting Task 1/Task 2 into separate RED-then-GREEN commits — The manifest (Task 1) must freeze the exact generated D-02/D-06 jitter schedules (Task 2), so the two tasks are load-bearing on each other; most new tests define a schema contract rather than catch a pre-existing defect, so a traditional RED-first bug-catching phase does not cleanly apply
- [Phase 14]: restore_and_verify_device_state() requires exact post-command readback (protocol-normalised equality), never acknowledgement alone -- fixes ipv6_thread_probe.py's prior silent-success-on-command-only restoration bug; a captured power outside {0, 65535} refuses mutation before any command as a distinct power_out_of_range outcome (D-05/D-16)
- [Phase 14]: check_patch_coverage.py's changed-excluded-line rule cannot pass for a brand-new script's own if __name__ == "__main__": guard (a pre-existing, static exclude_lines pattern applied regardless of execution) -- documented rather than gamed by restructuring the guard's literal text to dodge the regex
- [Phase 14]: Removed thread_revalidation.py's only if TYPE_CHECKING: block for ordinary top-level Light/AnimatorStats imports — Avoided colliding with pyproject.toml's pre-existing 'if TYPE_CHECKING' coverage exclude_lines pattern on two brand-new lines, the same false-positive class already documented for the module's if __name__ guard
- [Phase 14]: derive_class_ledger_from_roster() is the Task 3 authoritative six-class ledger, derived from the frozen roster and journals only — An evidence_backed class requires every expected alias's physical discovery, all 100 physical request trials and one physical animation attempt -- never a caller-supplied closure claim or the subset of devices one sweep observed
- [Phase 14]: New generate CLI subcommand is additive and distinct from the unchanged validate — Keeps the 14-02/14-03 validate contract and its tests intact while generate requires roster completeness and writes products atomically only after validation passes

### v2.0 Working Notes

- Phase 10 shipped through PR #210 as `7f54ad7`; its feature, phase and backup branches
  have been cleaned up. The source commits (`b49400b`, `b88cdb9`, `2f884f5`) and Phase 10
  artefacts retain the reconciliation history.

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

Last session: 2026-09-04T05:59:29.447Z
Stopped at: Phase 14 complete — all phases complete
Resume file: None

## Operator Next Steps

- Discuss and plan Phase 14, Thread Revalidation and Docs.
