---
gsd_state_version: 1.0
milestone: v1.2
milestone_name: Theme Library Update
current_phase: 7
current_phase_name: Taxonomy & Legacy Dispositions
status: planning
stopped_at: Phase 7 context gathered
last_updated: "2026-08-15T01:16:23.505Z"
last_activity: 2026-08-15
progress:
  total_phases: 4
  completed_phases: 1
  total_plans: 2
  completed_plans: 2
  percent: 25
last_activity_desc: "Phase 06 merged to main via PR #196; Phase 7 ready to plan"
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-08-14 at the start of v1.2)

**Core value:** Commands stick, devices are found, streaming never starves control traffic — and a theme by name looks like the theme of that name in the LIFX app.
**Current focus:** Phase 07 — taxonomy-legacy-dispositions

## Current Position

Phase: 7 — Taxonomy & Legacy Dispositions
Plan: Not started
Status: Ready to plan
Last activity: 2026-08-15

Phase 6 shipped: PR #196 merged to main 2026-08-15 (merge commit `cee51bf`), branch deleted.
Self-review raised 20 inline comments, all resolved before merge: 15 fixed on the branch, 5
split out as tracked issues. Every one was re-verified against the working tree rather than trusted
from notes — the docs-staleness comment had been recorded as fixed when it was not, and was
fixed in 732e512.

- **#197, #198, #199 — Phase 9 (resync tooling):** apostrophe corruption in display names,
  `earth`/`coral_reef` substitution with no changelog entry, digit-leading slugs
  unrepresentable. All three need the committed capture→JSONL converter that does not exist
  yet, so none is fixable by editing `data/themes.jsonl`.

- **#200, #201 — Phase 7:** `get_by_category()` still on the legacy six-group taxonomy while
  `Theme.category` returns the app's nine; no way to tell a rename alias from a primary slug
  in `get_available_themes()` (168 names, 166 themes).

Progress: [██▌       ] 25% (1/4 phases)

## Performance Metrics

**Velocity (project to date):**

- Plans completed before v1.2: 30 — v1.0: 1; post-v1.0 Phase 1: 5; v1.1: 24 (22 executed + 2 superseded closure records — read the frontmatter, not the count; see Blockers)
- v1.2: 0 plans (roadmap stage)

Per-plan metrics for shipped milestones live with their archives under
`.planning/milestones/` (v1.1's table was retired from this file at the v1.2 rollover).

*Updated after each plan completion*
**Per-Plan Metrics:**

| Plan | Duration | Tasks | Files |
|------|----------|-------|-------|
| Phase 06 P01 | 12min | 3 tasks | 9 files |
| Phase 06 P02 | 17min | 3 tasks | 8 files |

## Accumulated Context

### Roadmap Evolution

- v1.1 roadmap created (2026-07-16): Phases 2–5 — Discovery Re-broadcast, Retry Schedule Reshape, Animation Flow Control, Reliability Documentation. Derived from spike series 001–005 blueprints (`.claude/skills/spike-findings-lifx-async/`). Shipped 2026-07-26.
- v1.2 roadmap created (2026-08-14): Phases 6–9 — Generated Theme Library, Taxonomy & Legacy Dispositions, Hardware Fidelity Validation, Resync Tooling & Docs. Derived from the 2026-08-14 hardware capture (`.claude/theme-capture/`, 139 non-sport themes in scope). No research phase — user chose to skip. Import/resync/aliases deliberately kept in one phase: "no key silently vanishes" binds every intermediate state, so splitting them would mandate a broken midpoint.

### Decisions

Decisions are logged in PROJECT.md Key Decisions table. v1.1's per-plan decision log
moved to the milestone archives (`.planning/milestones/` and the archived phase
directories) at the v1.2 rollover.

Recent decisions affecting current work (all 2026-08-14, PROJECT.md Key Decisions):

- Overwrite redefined themes but keep `*_legacy` aliases — old values recoverable by name, not git archaeology
- ASCII slugs; sport categories dropped — removes 5 of the 6 slug collisions outright; `christmas` collapses cleanly (identical palettes)
- Device readback is the only capture source — internal LIFX theme endpoints deliberately untouched; accepted cost: 16-colour protocol ceiling and lost palette order
- [Phase 6]: Palette comparison is the named `Theme.palette_equals()` — Counter-based multiset at uint16 precision, identity ignored, `TypeError` on a non-Theme; `Theme.__eq__` stays identity so Theme stays hashable and 6.3.0 needs no BREAKING CHANGE footer (D-19a, D-20a; supersedes D-19, D-20 pre-ship during PR #196 review)
- [Phase ?]: Theme generator + generated data module excluded from coverage in both pyproject omit and codecov ignore, per products/protocol precedent (D-21, D-22)
- [Phase ?]: codespell ignore-words gained 'whats': the D-06 emoji/non-ASCII strip turns "What's the craic?" into 'Whats the craic?' — mechanical data, not a typo
- [Phase ?]: exciting shipped as captured despite a 1-ulp uint16 drift vs pre-v1.2 on 3 hues (app truncates, old table rounded) — THEME-02 binds shipped == captured; positional trio 0/7282/10923 unchanged and pinned

### v1.2 Working Notes

- **Palette order is meaningless** — the app shuffles on every application; all palette comparison is unordered-set over HSBK values
- **16 is the protocol palette ceiling** for `SetTileEffect`/`SetMultiZoneEffect` — FIDELITY-01's success is a recorded, evidenced determination either way ("cannot be determined from a device" is a complete outcome), never recovered longer palettes
- Capture came from a single product (Tile, product 55); product-invariance is expected but untested until FIDELITY-03 (needs a non-Tile matrix product — e.g. Candle or Ceiling)
- Theme names are public API: every pre-v1.2 key must keep resolving in every intermediate state — a key may gain values or an alias, never silently vanish
- Capture method and caveats: `.claude/theme-capture/README.md`; raw data `themes.jsonl` (179 records; 139 non-sport in scope)

### Pending Todos

- Adopt the `**D-NN**` decision-ID grammar in v1.2 CONTEXT.md files so `check.decision-coverage-plan` can actually parse decisions — v1.1 used `D5-NN`, which parsed as zero decisions and let the gate pass vacuously (see Blockers, open-gsd/gsd-core#2347)

### Blockers/Concerns

- **Hardware validation cannot run in CI (v1.2: FIDELITY-01..03).** Treat as UAT-style steps against the quiesced gen2/3/4 test devices / 73-device production fleet; automated emulator-backed tests must independently reach 100% branch patch coverage. Repeated rounds remain mandatory for any loss/coverage claim (Spike 005 lesson) — fidelity readbacks are less round-sensitive but still deserve more than one application per verdict, since the app shuffles palette order per application.
- **Verification staleness heuristic (open-gsd/gsd-core#2348).** `readVerificationStatus` silently overrides a file's declared `passed` with `stale` whenever any SUMMARY is newer than the VERIFICATION file. Bit Phases 2 and 4 at the v1.1 close. For v1.2 phase closes: write/refresh the phase VERIFICATION file *after* the last summary (Phase 5 was the worked example). Do not fix by touching mtimes; the heuristic cannot survive a fresh `git clone`.
- **Decision-coverage gate has never fired on this project (open-gsd/gsd-core#2347).** `parseDecisions` requires a literal `**D-` prefix; v1.1's `D5-NN` convention parsed as zero decisions, so the blocking gate passed vacuously on every phase. Mitigation for v1.2 is in Pending Todos (adopt `D-NN`). Until adopted, decision coverage is only ever verified by the plan-checker reading CONTEXT.md by hand.
- **`plan-scan.cjs` has no concept of a deliberately-unexecuted plan (open-gsd/gsd-core#2349).** Superseded plans need closure SUMMARYs to count a phase complete, and the tool then inflates `completed_plans` — read SUMMARY frontmatter (`status: superseded`), not counts. Relevant if any v1.2 plan is superseded mid-phase.
- **Do not run `state sync` unchecked.** `cmdStateSync` lacks the `shouldPreserveExistingProgress` ratchet that `cmdStateJson` applies, so the write path can regress values the read path protects. Verified safe 2026-07-17 but not self-guarding. When citing the archived predecessor repo, always qualify refs — both repos number issues from 1, and `open-gsd/gsd-core#3242` does not exist.
- **[RESOLVED 2026-07-26 — historical] v1.1 milestone-close verification status.** Closed via `override_closeout` with three known verification overrides recorded (see Deferred Items). Phase 5 resolved legitimately; Phases 2/4 were resolver-stale false negatives; Phase 3's UAT was a genuine `human_needed`. Retained because MILESTONES.md points here for the override record.

### Quick Tasks Completed

| # | Description | Date | Commit | Status | Directory |
|---|-------------|------|--------|--------|-----------|
| 260726-42c | Serial/MAC correlation audit script (`scripts/serial_mac_audit.py`) — enumerates serial, derived MAC, real ARP MAC, product and firmware to test the `get_mac_address()` off-by-one rule | 2026-07-26 | f625afd | Verified | [260726-42c-create-a-script-that-enumerates-mac-addr](./quick/260726-42c-create-a-script-that-enumerates-mac-addr/) |
| 260726-824 | Consumer time no longer expires the discovery idle window — `_discover_with_packet()` re-marks a response once the consumer resumes, so `api.discover()`'s per-device `create_device()` round trips cannot truncate a sweep (DISC-03, v1.1 audit follow-up); docs corrected and tests hardened in the `9afe8df` follow-up | 2026-07-26 | dca9e39 | Verified | [260726-824-fix-discover-idle-window-consumer-time](./quick/260726-824-fix-discover-idle-window-consumer-time/) |

**260726-42c outcome:** Fleet sweep run and signed off 2026-07-26. The audit found
`get_mac_address()` wrong for LIFX Tiles on firmware 3.50 — their real ARP MAC equals
their serial, while the `version_major == 3` rule predicted serial + 1. Rule narrowed to
`version_major == 3 and version_minor >= 70` in `f625afd` (parametrised boundary test;
2625 tests pass). Two rendering defects found by the run were fixed in `0f5b228`. Closed:
the 3.70 boundary is stated by LIFX, not inferred from the sweep — the replacement bound
is vendor-authoritative (GitHub issue #174 closed for the same reason).

## Deferred Items

Items acknowledged and carried forward from previous milestone closes:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| Persistence | PERS-01: extract `state_file` save/load into reusable mixin | Deferred to v2 | 2026-06-11 |
| Thread/IPv6 | THREAD-01 (SEED-001): revalidate wire behaviour over Thread/IPv6 when LIFX Thread firmware lands | Future requirement | 2026-07-16 |
| Seed | SEED-001-thread-ipv6-revalidation [dormant] — the same Thread/IPv6 revalidation, still unimplemented at the v1.1 close | Acknowledged, deferred | 2026-07-26 |
| Docs | 02-01-SUMMARY.md carries no `requirements-completed` frontmatter; DISC-01/DISC-02 are evidenced only in 02-VERIFICATION.md (cross-checked manually during the v1.1 audit) | Acknowledged, deferred | 2026-07-26 |
| Decision | D5-09 "publish behaviour, not tuning constants" is disputed by the operator and remains OPEN; spike candidate 006 would measure the cap impact | Open decision | 2026-07-26 |
| Verification | v1.1 `override_closeout` overrides (3): Phase 2 and Phase 4 resolver-stale false negatives (declared `passed`, resolver said `stale` — open-gsd/gsd-core#2348) and Phase 3's `human_needed` manual UAT | Recorded at close | 2026-07-26 |

## Session Continuity

Last session: 2026-08-15T01:16:23.494Z
Stopped at: Phase 7 context gathered
Resume file: .planning/phases/07-taxonomy-legacy-dispositions/07-CONTEXT.md

## Operator Next Steps

- Plan the first v1.2 phase with `/gsd-plan-phase 6`
