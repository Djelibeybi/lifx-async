---
phase: 17-fleet-diagnostics-and-the-staleness-control
plan: 05
subsystem: diagnostics
tags: [evidence, docs, discovery, staleness, mdns, wifi, thread]

requires:
  - phase: 17-fleet-diagnostics-and-the-staleness-control (plan 04)
    provides: "17-EVIDENCE/14-MANIFEST.json and 17-EVIDENCE/14-STALENESS.jsonl: one committed WiFi staleness trial (seed-002) with a mandatory accuracy caveat this plan carries forward"
  - phase: v2.0 Phase 14 (14-06)
    provides: "The Thread-arm staleness evidence (seed-001) this plan's verdict compares against, read-only"
provides:
  - "17-EVIDENCE/17-STALENESS-CONTROL.md: the staleness control verdict with all four figures, their measurement resolutions, the pre-stated opposite-observation clause, the operator's precision caveat carried forward, and the 69.4s/4140-4200s conflation correction"
  - "ROADMAP.md and REQUIREMENTS.md corrected: 69s no longer appears as a disappearance-to-expiry figure anywhere in either file"
  - "docs/user-guide/discovery.md: a caller-facing liveness statement quantifying the existing Phase 16 claim with measured durations on both sides, attributed to the functions that actually behave that way (discover_mdns() vs discover()/find_by_serial()), per SPEC amendment A3"
  - "docs/user-guide/troubleshooting.md: a cross-referenced entry pointing at the new Limitations content"
  - "Three new approved-phrase fragments locking the liveness claim in tests/test_network/test_mdns/test_phase_contract.py"
affects: []

actuals:
  tokens: 4611
  tasks: 2
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Bound, not point value, carried through to prose: the WiFi disappearance figure is written as 'at most 80.8548 s' (the measured completion time of the confirming poll), never as an interval starting at 0, in both the finding table and the docs sentence"
    - "Comparison arm, not matched control: every mention of the WiFi/Thread pair explicitly names the four SPEC amendment A8 tool departures and the confounder asymmetry rather than presenting them as a matched pair"

key-files:
  created:
    - .planning/phases/17-fleet-diagnostics-and-the-staleness-control/17-EVIDENCE/17-STALENESS-CONTROL.md
  modified:
    - .planning/ROADMAP.md
    - .planning/REQUIREMENTS.md
    - .planning/phases/17-fleet-diagnostics-and-the-staleness-control/17-05-PLAN.md
    - docs/user-guide/discovery.md
    - docs/user-guide/troubleshooting.md
    - tests/test_network/test_mdns/test_phase_contract.py

key-decisions:
  - "Fixed a bug in this plan's own two verify gates (Rule 1): both computed the WiFi disappearance bound from the nominal s * STALENESS_POLL_INTERVAL_S constant (giving 'at most 60 s'), the exact defect commit 21fd669 had already fixed in 17-04-PLAN.md's analogous gate under SPEC amendment A8 point 2. 17-05-PLAN.md was never updated to match. Both gates now read the row's own measured elapsed_s, matching 17-04-SUMMARY.md's reported 0-80.85s bound and A8's explicit statement that the nominal figure 'would have understated the expiry bound by roughly 1.5x'"
  - "Published the WiFi disappearance figure as 'at most 80.8548 s' throughout (finding table and docs prose), not 'at most 60 s', because that is what the committed row's measured elapsed_s actually records and what the operator's mandatory caveat requires"
  - "Placed the mandatory operator precision caveat as its own subsection inside the finding's ## The verdict, naming all four precision-limiting reasons, the supported/not-supported split, and the planned third (1Hz targeted-unicast) round, per the caveat recorded at the top of 17-04-SUMMARY.md"

patterns-established:
  - "A plan's own inline verify-script bug, found mid-execution and inconsistent with a sibling plan's already-authorised fix for the same defect class, is corrected in a dedicated commit before the task it blocks, documented as a Rule 1 deviation"

requirements-completed: [DISC-04]

coverage:
  - id: D1
    description: "17-EVIDENCE/17-STALENESS-CONTROL.md: the staleness control verdict, all four figures with resolutions, the pre-stated opposite-observation clause, and the ROADMAP/REQUIREMENTS 69s correction"
    requirement: "DISC-04"
    verification:
      - kind: other
        ref: "Task 1 FINDING-SHAPE-OK gate (all four required headings and literal clauses present)"
        status: pass
      - kind: other
        ref: "Task 1 four-figures table gate (exact headings, four rows, two Thread/two WiFi arms, each figure's derived value inside its own Value cell, WiFi gap bound derived from measured elapsed_s: 80.8548 s)"
        status: pass
      - kind: other
        ref: "Task 1 AC-19-SATISFIED gate (grep -nE '\\b69s\\b' .planning/ROADMAP.md .planning/REQUIREMENTS.md returns nothing)"
        status: pass
      - kind: other
        ref: "Task 1 scoped ROADMAP/REQUIREMENTS section gate (both sections carry 4140, 4200, and a line with both 'restoration duration' and '69.4')"
        status: pass
      - kind: other
        ref: "Task 1 em-dash and V2.0-EVIDENCE-UNTOUCHED gates"
        status: pass
    human_judgment: false
  - id: D2
    description: "docs/user-guide/discovery.md and docs/user-guide/troubleshooting.md: the caller-facing liveness statement with both directions, both figure sets and the trial count, attributed to the correct functions per SPEC amendment A3, locked by three approved-phrase fragments"
    requirement: "DISC-04"
    verification:
      - kind: other
        ref: "Task 2 Limitations-passage gate (all required elements inside the extraction between the Phase 16 paragraph and the disclaimer; each WiFi figure inside a WiFi-labelled sentence; poll-1 gap sentence carries 'at most')"
        status: pass
      - kind: other
        ref: "Task 2 attribution gate (stale-advertisement sentence names discover_mdns() and not discover(), within a 160-char window)"
        status: pass
      - kind: other
        ref: "Task 2 verification-window gate (discover(), find_by_serial(), correlated request, point-in-time all present around the 'not a continuing reachability guarantee' claim)"
        status: pass
      - kind: other
        ref: "Task 2 merge-base gate (Phase 16 paragraph verbatim-intact; private approved-phrase test body byte-identical to merge base)"
        status: pass
      - kind: unit
        ref: "tests/test_network/test_mdns/test_phase_contract.py (24 passed)"
        status: pass
      - kind: unit
        ref: "tests/test_docs_language.py (4 passed)"
        status: pass
      - kind: other
        ref: "uv run zensical build --clean --strict (zero warnings)"
        status: pass
      - kind: unit
        ref: "uv run --frozen pytest -q (4272 passed, 674 deselected)"
        status: pass
    human_judgment: true
    rationale: "The plan's own <human-check> requires reading the new prose end to end to confirm the three directions read as one claim, the discover_mdns()/discover() distinction reads as a coherent extension of the existing paragraph rather than a correction, no figure reads as a promise, and a caller knows what to do next. Performed during execution (see Decisions Made); recorded here as human_judgment for the verifier's own confirmation pass."

duration: 24min
completed: 2026-09-08
status: complete
---

# Phase 17 Plan 5: Staleness Control Verdict and Caller-Facing Liveness Statement Summary

**Published the DISC-04 staleness control verdict (Thread 4140-4200s vs WiFi at most 80.8548s, roughly two orders of magnitude apart, supporting Thread-specificity), corrected the conflated "69s" figure at every site, and extended the discovery guide's Limitations section with the measured liveness durations attributed to the correct functions per SPEC amendment A3.**

## Performance

- **Duration:** 24 min
- **Started:** 2026-09-08T10:01:40Z
- **Completed:** 2026-09-08T10:25:11Z
- **Tasks:** 2
- **Files modified:** 7 (1 created, 6 modified, including the plan's own two verify-script gates)

## Accomplishments

- Wrote `17-EVIDENCE/17-STALENESS-CONTROL.md`: the four-figure table (Thread 4140-4200s/69.4s, WiFi at most 80.8548s/14.6s), the Thread-specificity verdict with its pre-stated opposite-observation clause, the mechanism explanation (no Thread Border Router rebroadcasts a WiFi advertisement), and the operator's mandatory precision caveat carried forward in full
- Corrected "69s" wherever it was conflated with the disappearance-to-expiry interval: `.planning/ROADMAP.md`'s Phase 17 summary line, goal, and success criteria 3-4, and `.planning/REQUIREMENTS.md`'s DISC-04 entry — every site a word-boundary grep can find, verified by re-running that grep until it reported nothing
- Extended (not edited) the Phase 16 Limitations paragraph in `docs/user-guide/discovery.md` with three new sentences: the stale-advertisement direction attributed to `discover_mdns()` alone, the point-in-time verification direction attributed to `discover()` and `find_by_serial()`, and the restoration direction attributed to every method, each carrying both the Thread and WiFi figures
- Added a two-sentence cross-referenced entry to `docs/user-guide/troubleshooting.md` pointing at the new Limitations content, restating no figure
- Locked the claim with three new fragments in the `approved_phrases` tuple `test_public_guidance_uses_the_approved_limitation_phrases` reads
- Fixed a bug in this plan's own inline verify scripts (see Deviations) so the published WiFi bound reflects the row's actual measured data rather than a stale nominal-cadence calculation

## Task Commits

1. **Deviation fix (Rule 1): correct 17-05's stale WiFi-bound verify gates** - `23aa862` (fix)
2. **Task 1: Write the staleness control finding and correct the conflated 69 second figure** - `ded44b5` (docs)
3. **Task 2: Publish the caller-facing liveness statement and lock it with three approved phrases** - `c0f2aaf` (docs)

**Plan metadata:** committed below (docs: complete plan)

## Files Created/Modified

- `.planning/phases/17-fleet-diagnostics-and-the-staleness-control/17-EVIDENCE/17-STALENESS-CONTROL.md` - the staleness control finding (created)
- `.planning/ROADMAP.md` - Phase 17 summary line, goal, and success criteria 3-4 corrected
- `.planning/REQUIREMENTS.md` - DISC-04 entry corrected
- `.planning/phases/17-fleet-diagnostics-and-the-staleness-control/17-05-PLAN.md` - two verify-script gates fixed to derive the WiFi bound from measured `elapsed_s` (Rule 1 deviation)
- `docs/user-guide/discovery.md` - Limitations section extended with the liveness statement
- `docs/user-guide/troubleshooting.md` - cross-referenced entry added
- `tests/test_network/test_mdns/test_phase_contract.py` - three fragments added to the public-guidance approved-phrase tuple

## Decisions Made

See `key-decisions` in frontmatter. The load-bearing one: this plan's Task 1 and Task 2 verify scripts computed the WiFi disappearance bound from the nominal `STALENESS_POLL_INTERVAL_S` constant (`s * 60`, giving `at most 60 s` for this row's poll-1 confirming run), which is the identical defect commit `21fd669` already fixed in `17-04-PLAN.md`'s own analogous gate, under SPEC amendment A8 point 2: each poll now records measured wall-clock `elapsed_s`, not `poll_index * interval_s`, because a fully-absent poll can overrun the nominal 60s interval by running both discovery legs sequentially at a 45s timeout. `17-04-PLAN.md`'s fix commit explicitly names this as "the one line 17-05 consumes as its headline figure", and `17-04-SUMMARY.md` itself reports the bound as 0-80.85s, not 0-60s. `17-05-PLAN.md` was simply never updated to match. Both gates were corrected to read `r['polls'][s - 1]['elapsed_s']` (and `s - 2` for the lower bound) in place of the nominal multiplication, matching `21fd669`'s derivation exactly, and the published figures throughout this plan's deliverables use the corrected value (80.8548s, not 60s).

Read the new discovery.md prose end to end against the human-check criteria before committing: the three directions (stale-advertisement, verification, restoration) read as one connected claim; the `discover_mdns()`/`discover()` distinction reads as an extension of the existing Phase 16 paragraph rather than a correction of it (it does not contradict the paragraph above, which already draws the qualitative distinction); no figure is presented as a promise (the closing sentence explicitly disclaims guarantee/lease/limit/timeout-sizing status, and the pre-existing universal-benchmark disclaimer sits immediately below); and a caller finishing the passage is told to confirm reachability with a request, not to size a timeout from a number (reinforced by the pre-existing "Do not size timeouts or retry policy" sentence that follows).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed 17-05-PLAN.md's stale WiFi-disappearance-bound verify gates**
- **Found during:** Task 1 (before writing the finding), while computing what the plan's own Python verify one-liner would require in the `## The four figures` table's WiFi gap `Value` cell
- **Issue:** Both Task 1's and Task 2's `<automated>` verify scripts computed the WiFi disappearance bound as `s * tr.STALENESS_POLL_INTERVAL_S` (the nominal 60s cadence constant), giving `at most 60 s` for this row's poll-1 confirming run (`confirmed_expiry_poll: 3`, `STALENESS_CONFIRM_ABSENT_POLLS: 3`, so `s == 1`). This is the identical defect commit `21fd669` had already fixed in `17-04-PLAN.md`'s own `DISAPPEARANCE-BOUND` gate, under SPEC amendment A8 point 2 (each poll now records measured wall-clock `elapsed_s`, not `poll_index * interval_s`, because a fully-absent poll can overrun the nominal 60s interval running both discovery legs sequentially at a 45s timeout). `21fd669`'s commit message explicitly names the WiFi row's `elapsed_s` of 80.85s as "the one line 17-05 consumes as its headline figure," and `17-04-SUMMARY.md` reports the bound as 0-80.85s, not 0-60s. `17-05-PLAN.md` was simply never updated to match its sibling plan's fix, so executing it literally would have published a figure (60s) the committed evidence directly contradicts (the row's actual `elapsed_s` for poll 1 is 80.8548s).
- **Fix:** Edited both `<automated>` verify one-liners in `17-05-PLAN.md` to read `r['polls'][s - 1]['elapsed_s']` (and `r['polls'][s - 2]['elapsed_s']` for the lower bound when `s > 1`) in place of `s * tr.STALENESS_POLL_INTERVAL_S` / `(s - 1) * tr.STALENESS_POLL_INTERVAL_S`, matching `21fd669`'s derivation exactly. The `'at most'` wording requirement for the `s == 1` case was preserved unchanged.
- **Files modified:** `.planning/phases/17-fleet-diagnostics-and-the-staleness-control/17-05-PLAN.md`
- **Verification:** Ran both corrected gates directly, confirming `required-in-the-wifi-gap-cell=['80.8548', 'at most']` and `required-in-the-wifi-gap-sentence=['80.8548']`, matching `17-04-SUMMARY.md`'s reported bound
- **Committed in:** `23aa862`

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Necessary for correctness — without this fix the plan's own gates would have required and validated a scientifically incorrect figure (60s instead of the measured 80.8548s) directly contradicting the committed evidence, `17-04-SUMMARY.md`'s reported bound, and the operator's mandatory accuracy caveat. No scope creep: the fix touches only the two specific gate expressions the defect affects, mirroring an already-authorised fix to a sibling plan under the same SPEC amendment.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- DISC-04 is fully closed: the WiFi control trial evidence (17-04), the published verdict and figure correction (this plan's Task 1), and the caller-facing consequence (this plan's Task 2) are all committed
- Phase 17 (Fleet Diagnostics and the Staleness Control) is now 5/5 plans executed; MDNS-10 and DISC-04 both closed
- The planned third round (1Hz targeted-unicast disappearance measurement) is out of scope for this phase and recorded in the finding as future work superseding only the WiFi disappearance figure
- No blockers

## Self-Check: PASSED

- `.planning/phases/17-fleet-diagnostics-and-the-staleness-control/17-EVIDENCE/17-STALENESS-CONTROL.md` — FOUND
- `docs/user-guide/discovery.md` (modified) — FOUND
- `docs/user-guide/troubleshooting.md` (modified) — FOUND
- `tests/test_network/test_mdns/test_phase_contract.py` (modified) — FOUND
- Commit `23aa862` — FOUND
- Commit `ded44b5` — FOUND
- Commit `c0f2aaf` — FOUND
- All plan-level `<verification>` items re-run and passing (four-figures table, AC-19 grep, ROADMAP/REQUIREMENTS scoped check, Limitations passage, attribution and verification-window gates, merge-base comparisons, phrase-lock, em-dash scan, `zensical build --strict`, `pytest -q` at 4272 passed)

---
*Phase: 17-fleet-diagnostics-and-the-staleness-control*
*Completed: 2026-09-08*
