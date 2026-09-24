---
gsd_state_version: "1.0"
milestone: v2.1
milestone_name: Spring Cleaning
current_phase: 19
current_phase_name: Theme Library API and Data
status: "Phase 18 shipped — PR #236"
stopped_at: Phase 18 complete, ready to plan Phase 19
last_updated: "2026-09-24T00:45:27.915Z"
last_activity: 2026-09-24
state_head: cad679c7497c55d2d99feec6e1b38a9cb4de7893
progress:
  total_phases: 7
  completed_phases: 4
  total_plans: 20
  completed_plans: 20
  percent: 57
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-09-24 after Phase 18)

**Core value:** Commands stick, devices are found — over WiFi or Thread, transparently — streaming never starves control traffic, and a theme by name looks like the theme of that name in the LIFX app.
**Current focus:** Phase 19 — Theme Library API and Data

## Current Position

Phase: 19 — Theme Library API and Data
Plan: Not started
Status: Phase 18 shipped — PR #236
Total Plans in Phase: 0 (not yet planned)
Last activity: 2026-09-24 — Phase 18 shipped as PR #236; Phase 19 ready to plan

**v2.1 phase order:** 15 → (16 → 17) ∥ 18 ∥ 19 → 20 → 21

| Phase | Name | Requirements |
|-------|------|--------------|
| 15 | Coverage Gate and Test-Suite Health | CI-01, CI-02, TEST-02 |
| 16 | mDNS Correctness, Docs and Test Hygiene | MDNS-09, DOCS-07, DOCS-08, TEST-01 |
| 17 | Fleet Diagnostics and the Staleness Control | MDNS-10, DISC-04 |
| 18 | Typed Move and Morph Palette Effects | EFFECT-01, EFFECT-02 |
| 19 | Theme Library API and Data | THEME-05, THEME-06, THEME-07 |
| 20 | Animator Thread Guard | ANIM-05 |
| 21 | Documentation Prose Sweep | DOCS-09 |

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
| Phase 16 P01 | 12 min | 2 tasks | 2 files |
| Phase 16 P02 | 18min | 2 tasks | 4 files |
| Phase 16 P03 | 12 min | 2 tasks | 4 files |
| Phase 16 P04 | 24min | 2 tasks | 28 files |
| Phase 17 P01 | 15 min | 3 tasks | 2 files |
| Phase 17 P02 | 20 min | 2 tasks | 2 files |
| Phase 17 P03 | 12min | 3 tasks | 1 files |
| Phase 17 P04 | 6min | 5 tasks | 2 files |
| Phase 17 P05 | 24min | 2 tasks | 7 files |
| Phase 18 P03 | 16 min | 2 tasks | 2 files |
| Phase 18 P04 | 25min | 2 tasks | 4 files |
| Phase 18 P06 | 26min | 3 tasks | 2 files |
| Phase 18 P07 | 25min | 3 tasks | 6 files |
| Phase 18 P08 | 20min | 2 tasks | 3 files |
| Phase 18 P09 | 35min | 3 tasks | 6 files |

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
- [Phase 17]: 17-01: Module-level string constants hold each new fixed message tail on one physical source line, so grep-checkable phrases stay contiguous under ruff's 88-character limit
- [Phase 17]: 17-01: Kept dead-code removal (Task 3) separate from the typed-view migration (Task 1) and the normalisation/summary changes (Task 2), so each commit's tests exercise only what that commit changed
- [Phase 17]: [Phase 17]: 17-02: --alias-map redaction uses a single combined regex alternation (IPv6 branch first, dotted-quad before hex tail) so an IPv4-mapped IPv6 literal is consumed as one token rather than corrupted across two sequential passes
- [Phase 17]: [Phase 17]: 17-02: Address redaction reserves a distinct documentation sub-range per classify_address() class (192.0.2.x for IPv4, 2001:db8:{1,2,3,4}::x for GUA/IPv6-other/ULA/link-local) rather than a class round trip, since no documentation-safe IPv6 range classifies as GUA/ULA/link-local; no pseudonym is drawn from operational fd00:: or fe80:: space
- [Phase 17]: [Phase 17]: 17-02: The redacting stream is installed via contextlib.redirect_stdout() inside an ExitStack rather than a direct sys.stdout assignment, so it is always restored, including when the run raises, and cannot contaminate a later in-process test invocation
- [Phase 17]: 17-03: Operator adjudicated the identity backstop's full local-tokens-for-operator list (46 entries) as exactly two classes with no residue: 10 firmware-assigned bare-hex SRV labels accepted per SPEC amendment A7, and 36 operator-chosen LIFX-<Type>-<n> aliases accepted as deliberately chosen and non-sensitive
- [Phase 17]: 17-03: The Task 3 adjudication is recorded in the plan SUMMARY rather than by editing the committed transcript, since Task 2 forbids any edit to the staged transcript after staging
- [Phase 17]: [Phase 17]: 17-04: WiFi staleness trial (seed-002) closes DISC-04/R5 with disappearance-to-expiry bounded at 0-80.85s (confirmed_expiry, first_absence_poll 1) against the Thread arm's 4140-4200s, restoration 14.557s (mDNS)/15.530s (broadcast); operator mandated a prominent accuracy caveat (coarse cadence, coarse absence detection, four confounders, unmatched arms) that must carry into 17-05's published verdict
- [Phase 17]: [Phase 17]: 17-04: a third, 1Hz targeted-unicast disappearance measurement is planned to supersede this arm's disappearance figure; it does not supersede the restoration figures
- [Phase 17]: Fixed 17-05-PLAN.md's stale WiFi-disappearance-bound verify gates to use measured elapsed_s (Rule 1), matching 17-04's already-authorised fix under SPEC amendment A8 — The plan's own gates computed the WiFi bound from the nominal 60s cadence constant, giving 'at most 60 s' when the committed row's measured elapsed_s is 80.8548 s; 17-04-PLAN.md's commit 21fd669 already fixed the identical defect and named this figure as 17-05's headline
- [Phase 18]: D-09 implemented: _coerce_direction() is the single parsing rule for the direction field, shared by move() and the widened setter; a bare int now deliberately raises ValueError
- [Phase 18]: 18-04: derive_effect_palette()/validate_effect_palette() shared helper in component_state.py implements the full R10 Morph default-palette rule; MatrixEffect._validate_palette delegates to it, ready for plan 06's Move palette rule
- [Phase 18]: set_move_effect() implements the full D-10 palette flow in Task 1 (tracer), leaving Task 2's tdd="true" gate with zero RED failures — 56 edge-case tests passed on first run, documented as regression coverage per the 18-04 precedent — Task 1's own plan action mandated the complete production method (not a throwaway slice), so no implementation gap remained for Task 2's GREEN commit
- [Phase 18]: 18-07: every keyword-first pre-4.3.0 set_move_effect() call in the migration guide became prose rather than a code sample, since the method name is reused today with a different signature and a literal call would misleadingly read as valid current code
- [Phase 18]: 18-07: the phase-wide added-lines prose gate scans the whole phase diff from merge-base, not just the current plan's additions, so an earlier plan's stray em dash (component_state.py, plan 04) blocked this plan's own Task 3 verify and was fixed here
- [Phase 18]: [Phase 18]: 18-08: closed the Phase 16 D-05 PLC0415 handoff for both owned test paths by merging every function-local test import into each file's existing module-scope import block, proven import-only by an ast/difflib diff gate and exact before/after node-ID set equality
- [Phase 18]: [Phase 18] 18-09: sample_effect_palette() samples on the ORIGINAL pixel count (n = len(colors)), not the pre-deduplicated distinct count, matching D-25's literal i * n // 16 formula -- confirmed against the maintainer's 40-pixel worked example
- [Phase 18]: D-26 (2026-09-24): palette-less Morph raises when the colour read fails, reversing the WR-01 fallback for Morph only; Move keeps its fallback
- [Phase 18]: [Phase 18] 18-09: GREEN commit for the read-failure raise uses a fix(devices) scope, not feat(devices) -- removing the over-wide except from commit 5a9d254 is a bug fix per D-26

### v2.1 Working Notes

- **Phase 15 runs first because it changes what "verified" means.** CI-01 is reversed: the
  probe is operator tooling, so it leaves the measured tree entirely and relocates to
  `.planning/scripts/ipv6_thread_probe.py`, where Phase 17 edits it.
- **Phase 17 is serial after Phase 16.** The probe drives the library's own mDNS
  primitives including `selected_address_for()` (`.planning/scripts/ipv6_thread_probe.py`),
  so MDNS-09's owner-name normalisation settles before MDNS-10 changes what the probe reports.
- **Phases 16, 18 and 19 are file-disjoint** and can run in parallel:
  `src/lifx/network/discovery/mdns/` plus `tests/test_network/`;
  `src/lifx/devices/multizone.py`, `matrix.py` and `component_state.py`; `src/lifx/theme/` plus
  `data/themes.jsonl`.
- **Phase 20 is verified without the emulator.** CI uses synthetic Thread connectivity;
  integration evidence comes from an operator-run check on real Thread devices,
  pseudonymised. The superseded 18-01, 18-02 and 18-05 plans assumed per-device emulator
  replies and are reference only.
- **Phase 21 is last on purpose.** A ~200-occurrence prose pass across `docs/` conflicts
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

### Roadmap Evolution

- Phase 17.1 inserted after Phase 17: Modify the Move and Morph effect handling when no palette is provided (URGENT)
- Phase 17.1 removed: Folded into Phase 18 as SPEC R9/R10 and CONTEXT D-13 to D-23
- Phase 18 split (2026-09-23): ANIM-05 moved to new Phase 20 Animator Thread Guard, verified with synthetic CI tests plus a real Thread hardware check (emulator integration deferred); Phase 18 keeps EFFECT-01/02 and needs replanning without the `thread_emulator` fixture; Documentation Prose Sweep renumbered 20 to 21

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
| Style | No-em-dash house style: roughly 200 em dashes across `docs/`, deferred by the user during v1.2 Phase 7 UAT. Recast each sentence rather than swapping the character | Scheduled as v2.1 DOCS-09 (Phase 21) | 2026-08-27 |
| Verification | v1.2 `override_closeout` overrides (1): SEED-001 acknowledged at close. Phase 8 retains its operator-approved exception (Tile restoration unverified, `08-UAT-RESULTS.json` deliberately absent, synthetic merge prohibited) | Recorded at close | 2026-08-27 |
| Seed | SEED-002-wifi-advertisement-staleness-control: run the staleness experiment against WiFi bulbs as a control | Fired 2026-09-05; live as v2.1 DISC-04 (Phase 17) | 2026-09-05 |
| Testing | ANIM-05 emulator integration tests: add once lifx-emulator ships standards-based Thread replies (packed into as few packets as possible, not per-device). Phase 20 ships on synthetic CI tests plus a real-hardware check | Deferred | 2026-09-23 |
| Seed | SEED-003-lock-animation-to-wifi: lock `Animator` to WiFi devices | Fired 2026-09-05; live as v2.1 ANIM-05 (Phase 20) | 2026-09-05 |
| Verification | Phase 13 deferred item: coordinator teardown test left a blocked executor worker in `test_discovery_coordinator.py` (`test_non_last_detach_preserves_producer_and_last_detach_reaps_it`); confirmed load-bearing under v2.1 TEST-02 (Phase 15). The real fix is `39bad58`, not the `fc61b98` the v2.0 close assumed. Reintroducing the pre-fix form in a scratch worktree reproduces the hang; the fixed form exits cleanly. See `15-TEST-02-EVIDENCE.md` and `deferred-items.md`, which now state the same outcome | Resolved and confirmed load-bearing (Phase 15) | 2026-09-05 |

## Session Continuity

Last session: 2026-09-24T00:13:01.086Z
Stopped at: Phase 18 complete, ready to plan Phase 19
Resume file: None

## Operator Next Steps

- Phase 18 shipped as PR #236 from `gsd/phase-18-typed-move-and-morph-palette-effects` (renamed from the pre-split branch name), squashed to one commit
- Next: `/gsd-discuss-phase 19` (Theme Library API and Data)
