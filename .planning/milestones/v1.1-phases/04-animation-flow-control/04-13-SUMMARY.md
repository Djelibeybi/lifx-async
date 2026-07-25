---
phase: 04-animation-flow-control
plan: 13
subsystem: testing
tags: [hardware-uat, operator-ruling, matrix-light, ceiling-light, ack-gating]

# Dependency graph
requires:
  - phase: 04-animation-flow-control (04-12)
    provides: the honestly-FAILed cross-device sweep aggregate (04-UAT-SWEEP.json) and its 8 per-device evidence files, which this plan's ruling accepts over rather than modifies
provides:
  - "04-RULING.md — the ruling record: routing options + verbatim operator reply, supporting operator context verbatim, the full directional-evidence dossier with file citations, the dims correction verbatim, and the complete approved final wording"
  - ANIM-03/ANIM-04 resolved and marked complete in REQUIREMENTS.md (operator ruling + approved dual visual verdict)
  - Corrected Capsule dims (16×8 zones, 128 zones, 26 in × 13 in physical) applied everywhere they govern (ROADMAP, REQUIREMENTS, uat_ack_stream.py comments)
  - Phase 4 (Animation Flow Control) plans complete (11/13 executed; 04-06/04-07 permanently superseded, never executed) — ready for phase-level verification
affects: [phase-5-reliability-documentation, phase-level verification of Phase 4]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Operator ruling over a recorded FAIL: an explicit, dated, verbatim-quoted acceptance decision layered on top of an honest statistical FAIL record — never presented as, or allowed to be mistaken for, a statistical pass; the FAIL evidence stays on disk unmodified and is cited read-only"
    - "Governing-document dims correction scoped to live/governing text only (ROADMAP, REQUIREMENTS, live plan bullets, harness comments); historical records (design briefs, prior SUMMARYs, evidence JSONs) keep their original text as records of what was believed/measured at the time"

key-files:
  created:
    - .planning/phases/04-animation-flow-control/04-RULING.md
    - .planning/phases/04-animation-flow-control/04-UAT-VISUAL-CAPSULE.json
  modified:
    - .planning/ROADMAP.md
    - .planning/REQUIREMENTS.md
    - .planning/STATE.md
    - .planning/phases/04-animation-flow-control/04-06-PLAN.md
    - .planning/phases/04-animation-flow-control/04-07-PLAN.md
    - .planning/phases/04-animation-flow-control/uat_ack_stream.py

key-decisions:
  - "Operator ruled (verbatim '2', 2026-07-17): accept the eight-device directional dossier over the honestly-FAILed 04-12 sweep bar as satisfying ANIM-03/ANIM-04's intent — an acceptance over a recorded FAIL, never a statistical pass"
  - "Operator approved the complete final wording as presented (verbatim '1') — no amendments to ROADMAP criteria 3+4, REQUIREMENTS ANIM-03/04, the 04-06/04-07 supersession notices, the STATE gate texts, or the harness comment corrections"
  - "Operator's dims correction (verbatim, 2026-07-17): the Capsule is 16×8 zones (128 zones, 8 rows of 16), 26 in × 13 in physical — the prior '13×26 Capsule' wording carried an early-planning units mix-up (physical inches swapped for a zone count); corrected in every governing reference, historical records left as-is"
  - "Operator approved the Capsule visual round with the observation recorded (verbatim '1' of 3 presented options): geometry PASS; the reported stutter is the documented latest-frame-wins degradation under device saturation at 20 FPS (not a freeze/crawl failure mode) — the Capsule's sustainable rate is ~10 FPS at its 16×8/3-packets-per-frame chain shape, carried forward as a Phase 5 documentation recommendation"

requirements-completed: [ANIM-03, ANIM-04]

coverage:
  - id: D1
    description: "Ruling record (04-RULING.md) recording the routing options + verbatim operator reply '2', supporting context verbatim, the cited directional-evidence dossier, the dims correction verbatim, and the complete proposed final wording — committed before the wording checkpoint"
    verification:
      - kind: other
        ref: "test -f .planning/phases/04-animation-flow-control/04-RULING.md; grep for 'accept the eight-device directional dossier', 'notoriously flaky', '04-UAT-SWEEP.json', '128 zones', 'never a statistical pass'"
        status: pass
    human_judgment: false
  - id: D2
    description: "Operator approval of the complete final wording at a single blocking checkpoint (verbatim '1' = approve as presented), applied verbatim to ROADMAP criteria 3+4, REQUIREMENTS ANIM-03/04, and the 04-06/04-07 final supersession notices"
    verification:
      - kind: other
        ref: "git show fd7207c -- .planning/ROADMAP.md .planning/REQUIREMENTS.md .planning/phases/04-animation-flow-control/04-06-PLAN.md .planning/phases/04-animation-flow-control/04-07-PLAN.md"
        status: pass
    human_judgment: false
  - id: D3
    description: "Capsule dims correction (16×8 zones, 128 zones, 26 in × 13 in physical) applied to every governing reference; harness comment-only corrections leave behaviour unchanged"
    verification:
      - kind: unit
        ref: "expected_packets_per_frame(1,13,26)==8; (1,16,8)==3; (5,8,8)==5; EXPECTED_CEILING_PACKETS_PER_FRAME==8"
        status: pass
      - kind: other
        ref: "uv run ruff format --check / ruff check / pyright uat_ack_stream.py"
        status: pass
    human_judgment: false
  - id: D4
    description: "Single Capsule visual streaming round (My Office Ceiling Capsule, serial-verified, --profile ceiling --rounds 1 --duration 60) with power-on + as-found restore, dual operator verdict on smoothness (ANIM-03) and geometry (ANIM-04)"
    verification: []
    human_judgment: true
    rationale: "Numbers count packets; only eyes judge rendered smoothness and geometry on the physical panel — this is the plan's designated human-only criterion"
  - id: D5
    description: "ANIM-03/ANIM-04 marked complete in REQUIREMENTS.md (Traceability Complete) and every gate cleared (STATE.md, ROADMAP.md, 04-06/04-07 notices) with no residual reference to the skipped 04-12 Task 5 or pending routing"
    verification:
      - kind: other
        ref: "close-out consistency check (Task 5 automated verify) — pass; grep sweep for 'visual pending'/'routing required'/'04-12 Task 5' stale residue — clean"
        status: pass
    human_judgment: false

duration: ~1h50min
completed: 2026-07-17
status: complete
---

# Phase 04 Plan 13: ANIM-03/ANIM-04 Resolution by Operator Ruling Summary

**ANIM-03/ANIM-04 resolved by operator ruling (verbatim "2") over the 04-12 sweep's honest statistical FAIL — an acceptance of the eight-device directional dossier, never a statistical pass — with the Capsule dims corrected (16×8 zones, 128 zones, 26 in × 13 in physical) and closed out by an approved dual visual verdict (geometry PASS, smoothness = documented 20 FPS latest-frame-wins stutter, not freeze/crawl); Phase 4 plans complete.**

## Performance

- **Duration:** ~1h 50min (08:22 ruling draft → 10:12 close-out commit; includes two blocking checkpoints)
- **Started:** 2026-07-17T08:22:31+10:00
- **Completed:** 2026-07-17T10:12:11+10:00
- **Tasks:** 5 total (all executed — 2 blocking checkpoints, both approved)
- **Files modified:** 8 (2 created: 04-RULING.md, 04-UAT-VISUAL-CAPSULE.json; 6 modified: ROADMAP.md, REQUIREMENTS.md, STATE.md, 04-06-PLAN.md, 04-07-PLAN.md, uat_ack_stream.py)

## Task 2: Operator Checkpoint — Wording Approval

The blocking checkpoint presented the complete final wording from `04-RULING.md`
section 5 inline: both ROADMAP criteria replacements, both REQUIREMENTS entries
(checkboxes unchecked), the 04-06/04-07 final supersession notes, both STATE
gate texts (visual-pending and cleared), and the harness comment-only dims
corrections — with three framing statements (operator acceptance over a
recorded FAIL, checkbox flips deferred to the visual verdict, dims correction
scoped to governing text only).

**Operator's verbatim reply: "1"** — approve the wording exactly as presented,
unamended. Task 3 applied it verbatim.

## Task 4: Capsule Visual Round — Dual Verdict

Serial-verified My Office Ceiling Capsule (`d073d587daab`) at its roster IP
(`192.168.19.231`) — no re-resolution needed. Ran
`uat_ack_stream.py --ip 192.168.19.231 --profile ceiling --rounds 1 --duration 60
--json-out 04-UAT-VISUAL-CAPSULE.json` while the operator watched from their desk.

**Headless outcome (non-gating context, per the ruling):** FAIL, exit code 1.
Gated pooled query loss 51.28% vs the 9.0% ceiling (delivered_ratio 0.5233,
ambient clean at 0/111), blind pooled 96.0%, Fisher p = 9.13e-05, improvement
ratio 1.87x. Chain confirmed 16×8 (128 zones), `expected_packets_per_frame: 3`,
`packet_shape_ok: true`, ack RTT median 150.3 ms (D4-04 consistent with the
04-12 sweep session on the same device). Restoration succeeded (as-found power
and colour). Exit code was 1, not 2 (ENV-ERROR) — the round was valid context,
not invalidated.

**Operator's verbatim dual verdict:** "Geometry was fine. It was as smooth as
the tiles. No multi-second freezes but it stuttered throughout."

Presented with the round's telemetry (ambient clean, delivered_ratio 0.5233,
ack RTT 150.3 ms, gated loss 51.28% vs blind 96%, Fisher p) and three routing
options, the **operator's verbatim reply: "1"** — approved with the
observation recorded: geometry PASS; the reported stutter is classified as the
documented latest-frame-wins degradation under device saturation at 20 FPS
(a `queries_lost`/`ack_expiries`-consistent pacing symptom, not the
multi-second-freeze/persistent-crawl failure mode the plan's smoothness
criterion excludes) — the Capsule's sustainable streaming rate is estimated at
~10 FPS given its 16×8/3-packets-per-frame chain shape, carried forward as a
Phase 5 documentation recommendation (choose streaming FPS per device class),
not a code change to this plan.

## Accomplishments

- Recorded the operator's ruling verbatim (`04-RULING.md`): routing option 2
  text, the operator's verbatim reply "2" (2026-07-17), supporting operator
  context verbatim (the Tiles/noisy-environment quote), the full
  directional-evidence dossier with file citations (04-08 five-arm, 04-11
  paired runs 1+2, 04-12 sweep — ratios 1.28x–5.25x across ~10 sessions, 8
  devices, 2 radio generations), and the Capsule dims correction verbatim
  (16×8 zones, 128 zones, 26 in × 13 in physical)
- Got the complete final wording approved at a single blocking checkpoint
  (verbatim "1" = approve as presented) and applied it verbatim in one docs
  commit: ROADMAP Phase 4 criteria 3+4, REQUIREMENTS ANIM-03/04 (checkboxes
  unchecked pending the visual verdict), one final supersession note each on
  04-06-PLAN.md and 04-07-PLAN.md, STATE.md's visual-pending gate text, and
  three comment-only dims corrections in `uat_ack_stream.py` (module
  docstring, `EXPECTED_CEILING_PACKETS_PER_FRAME` comment block,
  `expected_packets_per_frame()` worked-example docstring) — zero behaviour
  change, verified by the unchanged unit assertions and clean ruff/pyright
- Ran the single Capsule visual streaming round (serial-verified,
  `--profile ceiling --rounds 1 --duration 60`, power-on + as-found restore)
  and obtained the operator's explicit dual verdict, approved with the
  stutter observation recorded rather than smoothed over
- Closed out: flipped ANIM-03/ANIM-04 to complete in REQUIREMENTS.md
  (Traceability rows Complete), replaced STATE.md's gate bullet with the
  cleared close-out text quoting the operator's verbatim verdict, reconciled
  ROADMAP.md (11/13 plans executed, Progress table row, 04-13 bullet ticked
  with outcome, and the 04-06/04-07 plan-list bullets corrected so visual
  ownership no longer appears to sit with the skipped 04-12 Task 5)

## Task Commits

Each task was committed atomically:

1. **Task 1: Draft the ruling record and proposed final wording** - `a6ece8e` (docs)
2. **Task 2: Blocking operator approval of the wording** - checkpoint only, no commit (verbatim reply "1" recorded above)
3. **Task 3: Apply the approved wording verbatim** - `fd7207c` (docs)
4. **Task 4: Capsule visual round + dual verdict** - checkpoint (evidence JSON committed separately below)
5. **Task 5a: Record the visual round evidence** - `a96d021` (test)
6. **Task 5b: Close out ANIM-03/ANIM-04** - `6bd627c` (docs)

## Files Created/Modified

- `.planning/phases/04-animation-flow-control/04-RULING.md` - ruling record + proposed/approved final wording, six required sections
- `.planning/ROADMAP.md` - Phase 4 criteria 3+4 replaced with the ruling-based wording; 04-06/04-07/04-12/04-13 plan-list bullets reconciled; Progress table Phase 4 row updated
- `.planning/REQUIREMENTS.md` - ANIM-03/04 replaced with the ruling-based wording, flipped `[x]`, Traceability rows Complete
- `.planning/STATE.md` - UAT sequencing gate replaced with the cleared close-out text (verbatim verdict quoted); Current Position, Performance Metrics, Decisions, Session Continuity, Operator Next Steps updated
- `.planning/phases/04-animation-flow-control/04-06-PLAN.md` - final supersession notice appended (visual ownership passed to 04-13 Task 4, approved)
- `.planning/phases/04-animation-flow-control/04-07-PLAN.md` - final supersession notice appended (visual ownership passed to 04-13 Task 4, approved)
- `.planning/phases/04-animation-flow-control/uat_ack_stream.py` - three comment/docstring-only dims corrections; zero behaviour change
- `.planning/phases/04-animation-flow-control/04-UAT-VISUAL-CAPSULE.json` - the visual round's session context (non-gating; new filename, sweep evidence untouched)

## Decisions Made

- Operator ruled (verbatim "2", 2026-07-17): accept the eight-device
  directional dossier over the honestly-FAILed 04-12 sweep bar as satisfying
  ANIM-03/ANIM-04's intent — an acceptance over a recorded FAIL, never a
  statistical pass
- Operator approved the complete final wording as presented (verbatim "1")
  — no amendments
- Operator's dims correction (verbatim, 2026-07-17): the Capsule is 16×8
  zones (128 zones, 8 rows of 16), 26 in × 13 in physical — corrected in
  every governing reference; historical records left as-is
- Operator approved the Capsule visual round with the observation recorded
  (verbatim "1" of 3 presented options): geometry PASS; the stutter is the
  documented latest-frame-wins degradation under 20 FPS saturation (not
  freeze/crawl); ~10 FPS estimated sustainable rate carried forward as a
  Phase 5 documentation recommendation

## Deviations from Plan

None - plan executed exactly as written. The visual round's headless outcome
(FAIL, exit 1) and the operator's stutter observation were both recorded
honestly as directed by the plan rather than smoothed over; neither triggered
a deviation since the plan's own routing (non-gating headless context;
operator's classification authority over the dual verdict) anticipated
exactly this outcome.

## Issues Encountered

None. The visual round streamed for its full 60 s duration, restored the
Capsule successfully, and produced a valid (non-ENV-ERROR) session — the
headless FAIL and the reported stutter are expected characteristics of
streaming a 3-packets-per-frame device at 20 FPS under the same anomalously
lossy network conditions noted in 04-12, not defects introduced by this plan.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- ANIM-03 and ANIM-04 are complete; Phase 4 (Animation Flow Control) plans
  are done — 11/13 executed, 04-06 and 04-07 permanently superseded and
  never executed
- **Recommended next step:** `/gsd-verify-work` for phase-level verification
  of Phase 4, then proceed to Phase 5 (Reliability Documentation), which
  depends on Phase 4
- Phase 5 planning may want to fold in the Capsule FPS observation: the
  operator's approved verdict noted throughout-stutter at 20 FPS with an
  estimated ~10 FPS sustainable rate for the Capsule's 16×8/3-packets-per-frame
  chain shape — a candidate line for DOCS-02 streaming-consumer guidance
  (choose FPS per device class)
- The FAIL evidence files this plan's ruling accepted over
  (`04-UAT-SWEEP.json`, the 8 per-device `04-UAT-SWEEP-<serial>.json` files,
  `04-UAT-TILES*.json`, `04-GAP-*.json*`) remain byte-identical throughout —
  verified via `git diff` showing no evidence-file or src/tests/ modification
  in any 04-13 commit

---
*Phase: 04-animation-flow-control*
*Completed: 2026-07-17*

## Self-Check: PASSED

All 9 claimed files verified present on disk; all 4 claimed commit hashes
(a6ece8e, fd7207c, a96d021, 6bd627c) verified present in git history.
