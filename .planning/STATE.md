---
gsd_state_version: 1.0
milestone: v2.1
milestone_name: Spring Cleaning
current_phase: 16
current_phase_name: mDNS Correctness, Docs and Test Hygiene
status: planning
stopped_at: Phase 15 complete, ready to plan Phase 16
last_updated: "2026-09-07T00:10:13.393Z"
last_activity: 2026-09-07
state_head: e21ef649c6c4014b71d7582deb72bd13625d5e61
progress:
  total_phases: 6
  completed_phases: 1
  total_plans: 5
  completed_plans: 5
  percent: 17
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-09-05 after v2.0 milestone)

**Core value:** Commands stick, devices are found — over WiFi or Thread, transparently — streaming never starves control traffic, and a theme by name looks like the theme of that name in the LIFX app.
**Current focus:** Phase 15, Coverage Gate and Test-Suite Health

## Current Position

Phase: 16 of 20 (mDNS Correctness, Docs and Test Hygiene)
Plan: Not started
Status: Ready to plan (Phase 15 shipped as PR #227)
Total Plans in Phase: 5
Last activity: 2026-09-07

**v2.1 phase order:** 15 → (16 → 17) ∥ 18 ∥ 19 → 20

| Phase | Name | Requirements |
|-------|------|--------------|
| 15 | Coverage Gate and Test-Suite Health | CI-01, CI-02, TEST-02 |
| 16 | mDNS Correctness, Docs and Test Hygiene | MDNS-09, DOCS-07, DOCS-08, TEST-01 |
| 17 | Fleet Diagnostics and the Staleness Control | MDNS-10, DISC-04 |
| 18 | Animator Connectivity Guard and Typed Move Effect | ANIM-05, EFFECT-01 |
| 19 | Theme Library API and Data | THEME-05, THEME-06, THEME-07 |
| 20 | Documentation Prose Sweep | DOCS-09 |

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
| Phase 15 P01 | 27 min | 2 tasks | 7 files |
| Phase 15 P02 | 23 min | 4 tasks | 16 files |
| Phase 15 P03 | 33min | 3 tasks | 4 files |
| Phase 15 P04 | 24 min | 3 tasks | 7 files |
| Phase 15 P05 | ~20min (continuation) | 5 tasks | 12 files |

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
- [Phase 15]: D-09: deselection via opt-in flags through the existing collection hook, not a growing -m negation
- [Phase 15]: Extended bandit's pre-commit exclude to also cover .planning/scripts/tests/, since those test files were only ever exempted by their old tests/ path
- [Phase 15]: [Phase 15] Accepted a pre-commit-forced isort reorder in Task 1's pure-rename commit rather than fighting an unavoidable, mechanically-identical re-trigger caused by ruff no longer treating scripts.* as first-party from the new .planning/scripts/ location
- [Phase 15]: [Phase 15] Suppressed a reportPrivateImportUsage diagnostic surfaced by adding the locked [tool.pyright] extraPaths entry with a targeted type: ignore rather than exporting the private symbol from library code
- [Phase 15]: [Phase 15] Fixed a hardcoded parents[1] directory-depth bug in measure_merged_discovery.py's _load_alias_map(), one level too shallow after the script moved one directory deeper to .planning/scripts/
- [Phase 15]: The vacuous-gate guard derives its authoritative changed-measured denominator from coverage.py's own source analysis (analysis2), never from the coverage.xml report under judgement. A report-derived denominator let a report classifying nothing score a false pass; the source-derived denominator closes that while still passing docstring/comment/configured-exclusion-only changes
- [Phase 15]: TEST-02: coordinator teardown fix (39bad58) confirmed load-bearing by reproducing the pre-fix hang in a scratch worktree; deferred-items.md and STATE.md reconciled to the same outcome
- [Phase 15]: [Phase 15] Operator selected publish-both-close-209 at the Task 4 checkpoint: both drafted issue comments published verbatim, #214 closed on the CI-01 reversal reasoning, and #209 also closed even though 15-SPEC.md R5 expected it to stay open
- [Phase 15]: [Phase 15] 15-SPEC.md's locked amendment scope widened from one region to an allowlist of five, because the spec restates its commitments twice and four phase-global restatements contradicted the delivered mechanism

### v2.1 Working Notes

- **Phase 15 runs first because it changes what "verified" means.** CI-01 is reversed: the
  probe is operator tooling, so it leaves the measured tree entirely and relocates to
  `.planning/scripts/ipv6_thread_probe.py`, where Phase 17 edits it.
- **Phase 17 is serial after Phase 16.** The probe drives the library's own mDNS
  primitives including `selected_address_for()` (`.planning/scripts/ipv6_thread_probe.py`),
  so MDNS-09's owner-name normalisation settles before MDNS-10 changes what the probe reports.
- **Phases 16, 18 and 19 are file-disjoint** and can run in parallel:
  `src/lifx/network/discovery/mdns/` plus `tests/test_network/`;
  `src/lifx/animation/` plus `src/lifx/devices/multizone.py`; `src/lifx/theme/` plus
  `data/themes.jsonl`.
- **Phase 20 is last on purpose.** A ~200-occurrence prose pass across `docs/` conflicts
  textually with every other phase that touches documentation.
- **DISC-04 (Phase 17) is hardware-gated**, needing a real WiFi bulb and a physical unplug.
  The emulator cannot verify it. It must not block CI or any other phase.
- **TEST-02's outcome is settled.** `fc61b98` fixed
  `test_forked_child_lazily_starts_a_fresh_coordinator`, a different test, so the v2.0
  close assumption does not carry. The real fix is `39bad58`. Two bounded process-exit
  observations confirmed it is load-bearing: the fixed form exits cleanly (0.66s against a
  60s watchdog); the pre-fix form, reintroduced once in a scratch worktree and never
  committed, hangs and is only detected because the in-child watchdog forces a hard exit at
  60s, with a faulthandler dump naming the exact blocked executor worker
  `deferred-items.md` describes. See
  `.planning/phases/15-coverage-gate-and-test-suite-health/15-TEST-02-EVIDENCE.md`.
- **THEME-07 must not edit `docs/changelog.md`.** That file is generated by the release
  workflow; the enumeration reaches it through Conventional Commit messages and release
  notes.
- **MDNS-10 and DISC-04 produce hardware evidence.** Format-preserving pseudonyms from the
  operator's private mapping only. Inspect the staged diff before committing.

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
| Style | No-em-dash house style: roughly 200 em dashes across `docs/`, deferred by the user during v1.2 Phase 7 UAT. Recast each sentence rather than swapping the character | Scheduled as v2.1 DOCS-09 (Phase 20) | 2026-08-27 |
| Verification | v1.2 `override_closeout` overrides (1): SEED-001 acknowledged at close. Phase 8 retains its operator-approved exception (Tile restoration unverified, `08-UAT-RESULTS.json` deliberately absent, synthetic merge prohibited) | Recorded at close | 2026-08-27 |
| Seed | SEED-002-wifi-advertisement-staleness-control: run the staleness experiment against WiFi bulbs as a control | Fired 2026-09-05; live as v2.1 DISC-04 (Phase 17) | 2026-09-05 |
| Seed | SEED-003-lock-animation-to-wifi: lock `Animator` to WiFi devices | Fired 2026-09-05; live as v2.1 ANIM-05 (Phase 18) | 2026-09-05 |
| Verification | Phase 13 deferred item: coordinator teardown test left a blocked executor worker in `test_discovery_coordinator.py` (`test_non_last_detach_preserves_producer_and_last_detach_reaps_it`); confirmed load-bearing under v2.1 TEST-02 (Phase 15). The real fix is `39bad58`, not the `fc61b98` the v2.0 close assumed. Reintroducing the pre-fix form in a scratch worktree reproduces the hang; the fixed form exits cleanly. See `15-TEST-02-EVIDENCE.md` and `deferred-items.md`, which now state the same outcome | Resolved and confirmed load-bearing (Phase 15) | 2026-09-05 |

## Session Continuity

Last session: 2026-09-06T22:52:25.623Z
Stopped at: Phase 15 complete, ready to plan Phase 16
Resume file: None

## Operator Next Steps

- Review `.planning/ROADMAP.md` v2.1 section (Phases 15 to 20)
- Then discuss and plan the first phase with `/gsd-discuss-phase 15`
