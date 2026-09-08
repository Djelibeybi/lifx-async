---
phase: 17-fleet-diagnostics-and-the-staleness-control
plan: 04
subsystem: diagnostics
tags: [evidence, hardware, wifi, staleness, mdns, privacy, redaction]

requires:
  - phase: 17-fleet-diagnostics-and-the-staleness-control (plan 03)
    provides: "17-EVIDENCE/17-PROBE-TRANSCRIPT.md committed in the previous wave, fixing the alias each WiFi device carries here (AC-24)"
  - phase: v2.0 Phase 14 (14-06)
    provides: "The Thread-arm staleness evidence (seed-001) this plan's WiFi arm is a control against"
provides:
  - "17-EVIDENCE/14-MANIFEST.json and 17-EVIDENCE/14-STALENESS.jsonl: one WiFi staleness trial (session_id seed-002), run through thread_revalidation.py as modified under SPEC amendment A8, so the protocol is NOT identical to the one THREAD-04 ran on Thread"
  - "DISC-04 closed: disappearance-to-expiry bounded at 0 to 80.85 s (order-of-magnitude control against the Thread arm's 4140-4200 s), restoration measured at 14.557 s (mDNS leg) / 15.530 s (broadcast leg)"
  - "A mandatory accuracy caveat on the WiFi figures, carried forward for 17-05's published verdict"
affects: [17-05-fleet-diagnostics-and-the-staleness-control]

actuals:
  tokens: 14464
  tasks: 5
  commits: 8

tech-stack:
  added: []
  patterns:
    - "Comparable but not matched: the WiFi trial reuses run_staleness_experiment() with R5's frozen constants intact (60s cadence, 3 confirm polls, 10800s cap), but under four tool departures authorised by SPEC amendment A8, so it is a comparison arm rather than a matched control"
    - "Bound, not point value: a disappearance interval derived from the confirming run's start poll (confirmed_expiry_poll - STALENESS_CONFIRM_ABSENT_POLLS + 1), never from first_absence_poll alone, so an early transient absence cannot be mistaken for the true interval"

key-files:
  created:
    - .planning/phases/17-fleet-diagnostics-and-the-staleness-control/17-EVIDENCE/14-MANIFEST.json
    - .planning/phases/17-fleet-diagnostics-and-the-staleness-control/17-EVIDENCE/14-STALENESS.jsonl
  modified: []

key-decisions:
  - "Operator resumed Task 5 with \"commit\": AMBIGUOUS-NUMERIC-TOKENS reported none, so no numeric-artefact adjudication was required; the operator inspected the staged diff against the private mapping and confirmed AC-24 alias consistency with 17-03's probe transcript before approving"
  - "Operator mandated a prominent accuracy caveat on the WiFi figures (this document's next section) rather than a bare close: the disappearance bound is real and is the finding, but the specific figure is precision-limited by four stated constraints and is not a measurement of where inside the bound the true value fell"
  - "A third round is planned: a 1 Hz disappearance measurement using a targeted unicast probe against a known device, because a broadcast sweep's absence verdict costs a full ~90s discovery timeout per poll and cannot be driven at 1 Hz. That round supersedes this arm's disappearance figure; it does not supersede the restoration figures, which are already well-resolved"

patterns-established:
  - "Bound-not-point reporting: a coarse-cadence disappearance measurement is recorded as an interval derived from the tool's own confirming-run derivation, with the imprecision named explicitly rather than presented as a single number"

requirements-completed: [DISC-04]

coverage:
  - id: D1
    description: "One WiFi staleness trial (seed-002), validated by thread_revalidation.py's own load_manifest()/reload_staleness_events(), staged and committed as 17-EVIDENCE/14-MANIFEST.json and 17-EVIDENCE/14-STALENESS.jsonl, closing DISC-04/R5 as a bounded control against the Thread arm"
    requirement: "DISC-04"
    verification:
      - kind: other
        ref: "Task 4 STALENESS-EVIDENCE-VALIDATED-BY-THE-TOOL gate (reload_staleness_events() accepted the row; disposition confirmed_expiry; DISAPPEARANCE-BOUND: interval 0 to 80.8548 s from a confirming run starting at poll 1)"
        status: pass
      - kind: other
        ref: "Task 4 SAME-ALIAS-RERUN-VERIFIED gate (two recorded journal hashes equal each other and the journal now; run one's verdict carries restoration_duration_s, run two's does not; same alias and disposition both sides)"
        status: pass
      - kind: other
        ref: "Task 4 INDEX-WORKTREE-PARITY-OK, THREAD-REVALIDATION-AUTHORISED, TOOL-FILENAMES-INTACT and V2.0-EVIDENCE-UNTOUCHED gates"
        status: pass
      - kind: other
        ref: "Task 4 identity backstop (IDENTITY-SHAPED-TOKENS: none, AMBIGUOUS-NUMERIC-TOKENS: none)"
        status: pass
    human_judgment: true
    rationale: "Task 5 is a blocking operator checkpoint (SPEC prohibition P3, D-23) inspecting the staged diff against the private mapping and adjudicating any ambiguous numeric tokens by name; no automated check can perform that inspection, and the SPEC resolves it as judgment rather than test. The operator resumed with 'commit' and mandated the accuracy caveat this document carries."

duration: 6min
completed: 2026-09-08
status: complete
---

# Phase 17 Plan 4: WiFi staleness trial evidence for DISC-04 Summary

**One WiFi staleness trial (`seed-002`) run through `thread_revalidation.py` as modified under SPEC amendment A8, closing DISC-04 with disappearance-to-expiry bounded at 0-80.85s against the Thread arm's 4140-4200s, and restoration measured at 14.56s/15.53s — committed with a mandatory accuracy caveat on the WiFi figures.**

## ⚠️ MANDATORY CAVEAT: THE WIFI NUMBERS ARE IMPRECISE

**The operator committed this evidence on the explicit condition that this caveat travel with it into `17-05-PLAN.md`'s published verdict.** The order-of-magnitude finding is solid; the specific WiFi figures are not measurements of a precise value, for four stated reasons:

1. **The cadence is coarser than the phenomenon.** A 60s poll interval against a disappearance that completed inside 80.85s means the measurement has roughly the same resolution as the thing being measured. The device was already absent at the *first* poll (`first_absence_poll: 1`), so nothing about the interval's shape inside that first 80.85s window was observed.
2. **Absence detection is inherently coarse here.** Each poll runs both discovery legs sequentially at a 45s timeout, so an absent poll costs ~90s wall time and cannot resolve anything finer than that.
3. **Four confounders were present, none of which the Thread arm carried**: `background_pollers`, `busy_network`, `unquiesced_environment`, `wireless_interference` (see the `confounders` array in the committed JSONL row).
4. **The arms are neither protocol- nor condition-matched.** Four operator-authorised departures from the byte-identical tool (SPEC amendment A8, 2026-09-08: an explicit 45s discovery timeout passed at the call site, measured-vs-nominal `elapsed_s`, first-leg-present restoration close, and the `InfraredLight`/`HevLight` inventory acceptance) sit on top of the confounder asymmetry above.

**What the evidence supports:**
- Disappearance-to-expiry is **bounded** at 0 to 80.85s, against 4140-4200s on Thread. The order-of-magnitude difference (roughly two orders of magnitude) is real and **is the finding**.
- Restoration is **better resolved**: 14.557s (mDNS leg) and 15.530s (broadcast leg). Present-detection short-circuits on match, so those polls each took ~1s rather than the ~90s an absent poll costs — restoration is the better-resolved half of this arm, though still measured under all four confounders above.

**What the evidence does NOT support:**
- Any point value for disappearance. `first_absence_poll: 1` means the run never observed *where* inside 0-80.85s the disappearance actually happened.
- Any precise comparison of the two arms' magnitudes beyond "roughly two orders of magnitude apart".

**A third round is planned** to supersede the disappearance figure specifically: a 1Hz disappearance measurement using a targeted unicast probe against a known device, rather than a broadcast sweep. A sweep's absence verdict costs a full discovery timeout per poll and cannot be driven at 1Hz; a unicast probe against one known device can. That round does not supersede the restoration figures above, which are already well-resolved.

## Performance

- **Duration:** 6 min (this resumed session — Tasks 1-4 and the tool authorisation commits were completed by a prior session, which halted at Task 5's blocking checkpoint; this session received the operator's "commit" answer and the mandatory caveat, committed the staged evidence, and wrote this SUMMARY)
- **Started:** 2026-09-08T09:52:00Z
- **Completed:** 2026-09-08T09:58:37Z
- **Tasks:** 5 (Tasks 1-4 satisfied on entry; this session resumed at and completed Task 5)
- **Files modified:** 2 (evidence, committed unmodified from staged state)

## Accomplishments

- Committed `17-EVIDENCE/14-MANIFEST.json` and `17-EVIDENCE/14-STALENESS.jsonl` exactly as staged, without hand-editing either tool-generated file (commit `072159d`)
- DISC-04 and R5 both **closed**: `confirmed_expiry` disposition, `first_absence_poll: 1`, `confirmed_expiry_poll: 3`, giving a disappearance-to-expiry bound of 0 to 80.85483916700468 s, derived by the tool-consuming gate from the confirming run's start poll (`confirmed_expiry_poll - STALENESS_CONFIRM_ABSENT_POLLS + 1 = 1`), not from `first_absence_poll` alone
- Restoration measured at `restoration_duration_s: 14.557117625008686` (equal to `restoration_mdns_s`, the mDNS leg closing first) and `restoration_discover_s: 15.530575042008422` (the broadcast leg)
- Same-alias rerun proven mechanically (AC-15): both recorded journal hashes equal each other and the journal's current hash, run one's verdict carried `restoration_duration_s` and run two's did not, and both named the same alias and disposition
- Identity backstop over the staged diff reported `IDENTITY-SHAPED-TOKENS: none` and `AMBIGUOUS-NUMERIC-TOKENS: none` — no numeric-artefact adjudication was required at Task 5
- Operator inspected the staged diff against the private mapping, confirmed AC-24 alias consistency against `17-03-PLAN.md`'s committed probe transcript, and resumed with "commit" together with the mandatory accuracy caveat recorded above
- `.planning/scripts/thread_revalidation.py` confirmed unchanged from its authorised content (`THREAD-REVALIDATION-AUTHORISED`, blob `ad0fea79ba0d83b15e3f1990ecdf762213b8670a`) and no file under `.planning/milestones/v2.0-phases/` appears in the branch diff (`V2.0-EVIDENCE-UNTOUCHED`)

## Task Commits

Work on this plan spanned prior sessions (Tasks 1-4 and the four operator-authorised tool changes) and this session (Task 5's resolution and the evidence commit):

1. **Task 1: Confirm WiFi roster, private alias map and power scripts** — checkpoint answered by the operator in a prior session (no commit; roster and scripts supplied out of band)
2. **Pre-Task-2 deviation (Rule 4, operator-authorised): four targeted changes to `thread_revalidation.py`** — `3e812ab` (explicit 45s discovery timeout), `5f554a3` (measured wall-clock `elapsed_s`), `d27c294` (restoration closes on first leg present, per-leg bounded), `b53de94` (accept `InfraredLight`/`HevLight` in manifest inventory); documented and pinned by `9fbd3b0` and `52e3fe8`
3. **Task 2: Author the WiFi roster and write the session manifest** — manifest written by the tool's own `init` subcommand into `17-EVIDENCE/14-MANIFEST.json` (uncommitted evidence write, validated in Task 4)
4. **Task 3: Run the WiFi staleness trial and the same-alias rerun** — journal written by the tool's own `staleness` subcommand into `17-EVIDENCE/14-STALENESS.jsonl` (uncommitted evidence write, validated in Task 4); `21fd669` (fix: derive the disappearance bound from measured poll times) landed alongside this task's gate work
5. **Task 4: Validate, stage, and run the identity backstop** — both files validated through `load_manifest()`/`reload_staleness_events()`, staged by path, backstop run (no commit; staging only, prior session)
6. **Task 5: Operator inspection of the staged evidence** — `072159d` (docs(evidence): commit WiFi staleness trial evidence for DISC-04), this session, resumed from the operator's "commit" answer plus the mandatory accuracy caveat

**Plan metadata:** committed below (docs: complete plan)

## Files Created/Modified

- `.planning/phases/17-fleet-diagnostics-and-the-staleness-control/17-EVIDENCE/14-MANIFEST.json` - WiFi session manifest (`session_id: seed-002`, seed `4823901756`, 64-entry inventory covering `Light`, `MultiZoneLight`, `CeilingLight`, `HevLight`, `InfraredLight` and multiple `MatrixLight` aliases, three frozen staleness constants unchanged)
- `.planning/phases/17-fleet-diagnostics-and-the-staleness-control/17-EVIDENCE/14-STALENESS.jsonl` - exactly one WiFi staleness row: `confirmed_expiry` disposition, three polls, restoration figures for both discovery legs, and the four active confounders

## Decisions Made

- See `key-decisions` in frontmatter. The load-bearing one: the operator required the accuracy caveat above to be prominent and to travel forward into `17-05-PLAN.md`'s published verdict, not buried as a footnote.

## Deviations from Plan

None in this session beyond what the plan itself already authorised and documented (the four `thread_revalidation.py` changes under D-13 as amended, all committed by the prior session and re-verified by `THREAD-REVALIDATION-AUTHORISED` before this session's commit). This session performed exactly the action Task 5's resume-signal specifies: commit the staged evidence as-is, no hand-edits.

## Issues Encountered

None. The prior session's halt at Task 5 was the correct behaviour for a blocking operator checkpoint following a multi-hour hardware trial, not an error.

## User Setup Required

None - Task 1's hardware precondition (private alias map outside the repository, WiFi bulb powered and quiesced, power scripts ready) was satisfied by the operator before the prior session ran the trial.

## Next Phase Readiness

- **DISC-04 is CLOSED** and R5 is closed: `confirmed_expiry` disposition with a disappearance-to-expiry bound of 0-80.85s and restoration at 14.557s (mDNS) / 15.530s (broadcast), against the Thread arm's `first_absence_poll: 70`, interval 4140-4200s, restoration 69.4s (v2.0 `seed-001`, for scale)
- **`17-05-PLAN.md` cannot publish its verdict without carrying the accuracy caveat above forward, verbatim in substance if not in wording.** Specifically: state the disappearance figure as a bound, never a point value; name all four precision-limiting constraints; distinguish "supported" (order-of-magnitude bound, well-resolved restoration) from "not supported" (any point value inside the bound, any precise cross-arm magnitude comparison); and record the planned third (1Hz targeted-unicast) round as superseding the disappearance figure only, not the restoration figures
- `17-EVIDENCE/17-PROBE-TRANSCRIPT.md` (from `17-03-PLAN.md`) and `17-EVIDENCE/14-MANIFEST.json`/`14-STALENESS.jsonl` (this plan) now both sit committed under the same `17-EVIDENCE/` directory with no cross-contamination: each plan's staging, inspection and commit named only its own paths throughout
- No blockers

## Self-Check: PASSED

- `.planning/phases/17-fleet-diagnostics-and-the-staleness-control/17-EVIDENCE/14-MANIFEST.json` — FOUND
- `.planning/phases/17-fleet-diagnostics-and-the-staleness-control/17-EVIDENCE/14-STALENESS.jsonl` — FOUND
- Commit `072159d` — FOUND

---
*Phase: 17-fleet-diagnostics-and-the-staleness-control*
*Completed: 2026-09-08*
