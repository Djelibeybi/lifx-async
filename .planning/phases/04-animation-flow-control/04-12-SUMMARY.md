---
phase: 04-animation-flow-control
plan: 12
subsystem: testing
tags: [hardware-uat, statistics, fisher-exact, matrix-light, ceiling-light, ack-gating]

# Dependency graph
requires:
  - phase: 04-animation-flow-control (04-11)
    provides: the paired-relative per-device gate (04-CRITERION-DESIGN.md), reused UNCHANGED here
provides:
  - Cross-device paired-sweep certification design (04-SWEEP-DESIGN.md) + reproducible exact-binomial aggregation runner (sweep_design.py)
  - Operator-approved ROADMAP/REQUIREMENTS wording for the cross-device sweep (criteria 3+4, ANIM-03/ANIM-04)
  - Sweep-generalised uat_ack_stream.py (ROSTER, --sweep-device, --sweep-verdict, serial-authoritative resolution, profile auto-selection, chain-dims-derived expected_packets_per_frame(), as-found capture/restore)
  - Honest 8-device sweep evidence (04-UAT-SWEEP-<serial>.json x8 + 04-UAT-SWEEP.json) -- aggregate outcome FAIL
affects: [04-animation-flow-control gap-closure planning, phase-5-reliability-documentation]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Cross-device aggregation: sweep PASS iff N_valid >= quorum AND per-device PASSes >= N_valid - allowed_fails, with INCONCLUSIVE/ENV-ERROR excluded from N_valid but always reported, and a reference-only device role that never enters the count"
    - "Serial-authoritative device resolution: roster IP as a fast path whose reported serial must match, broadcast discovery by serial as the fallback -- a single moved/unreachable device becomes its own ENV-ERROR row, never a whole-sweep abort"
    - "Chain-dims-derived packet-shape assertion (expected_packets_per_frame) replacing a hard-coded per-product constant -- an independent derivation from reported hardware state, not a read-back of the generator's own arithmetic"

key-files:
  created:
    - .planning/phases/04-animation-flow-control/04-SWEEP-DESIGN.md
    - .planning/phases/04-animation-flow-control/sweep_design.py
    - .planning/phases/04-animation-flow-control/04-UAT-SWEEP-d073d5893c04.json
    - .planning/phases/04-animation-flow-control/04-UAT-SWEEP-d073d55956e8.json
    - .planning/phases/04-animation-flow-control/04-UAT-SWEEP-d073d582bff4.json
    - .planning/phases/04-animation-flow-control/04-UAT-SWEEP-d073d5866777.json
    - .planning/phases/04-animation-flow-control/04-UAT-SWEEP-d073d5a132d9.json
    - .planning/phases/04-animation-flow-control/04-UAT-SWEEP-d073d5a132b8.json
    - .planning/phases/04-animation-flow-control/04-UAT-SWEEP-d073d587daab.json
    - .planning/phases/04-animation-flow-control/04-UAT-SWEEP-d073d53e11be.json
    - .planning/phases/04-animation-flow-control/04-UAT-SWEEP.json
  modified:
    - .planning/ROADMAP.md
    - .planning/REQUIREMENTS.md
    - .planning/phases/04-animation-flow-control/04-06-PLAN.md
    - .planning/phases/04-animation-flow-control/04-07-PLAN.md
    - .planning/phases/04-animation-flow-control/uat_ack_stream.py
    - .planning/STATE.md

key-decisions:
  - "Operator approved the complete cross-device sweep wording as presented (verbatim '1') -- no amendments"
  - "K=N_valid-1 (allowed_fails=1), quorum Q=5, chosen because it is the strictest K meeting the pre-declared P(sweep PASS | historical rate) >= 0.85 bar; the all-must-pass power (0.4813) was surfaced and rejected"
  - "Sweep aggregate outcome is FAIL: 5 of 5 valid gate sessions FAILed (0 PASS), exceeding the 1-allowed-fail bar; thresholds/roster/rule were not touched after seeing results"
  - "My Office Ceiling Capsule reported chain 16x8, not the roster's assumed 13x26 -- the chain-dims-derived expected_packets_per_frame() correctly computed 3 packets/frame from the REPORTED dims and every gated frame matched it; the discrepancy is a roster documentation error, not a harness defect"

requirements-completed: []

coverage:
  - id: D1
    description: "Cross-device sweep criterion design brief + reproducible exact-binomial aggregation runner, with the operator's Tiles ruling recorded verbatim and every new parameter evidence-derived"
    verification:
      - kind: other
        ref: "uv run python .planning/phases/04-animation-flow-control/sweep_design.py"
        status: pass
    human_judgment: false
  - id: D2
    description: "Operator approval of the complete final wording at a single blocking checkpoint, applied verbatim to ROADMAP/REQUIREMENTS and the 04-06/04-07 supersession notices"
    verification:
      - kind: other
        ref: "git show ec87a76 -- .planning/ROADMAP.md .planning/REQUIREMENTS.md"
        status: pass
    human_judgment: false
  - id: D3
    description: "Sweep-generalised uat_ack_stream.py: ROSTER, --sweep-device/--sweep-verdict modes, serial-authoritative resolution, profile auto-selection, expected_packets_per_frame(), as-found capture/restore"
    verification:
      - kind: unit
        ref: "expected_packets_per_frame(1,13,26)==8; (1,16,8)==3; (5,8,8)==5"
        status: pass
      - kind: other
        ref: "uv run ruff format --check / ruff check / pyright uat_ack_stream.py"
        status: pass
    human_judgment: false
  - id: D4
    description: "8-device cross-device sweep evidence collected honestly, one attempt per device, aggregated by the frozen rule"
    verification:
      - kind: other
        ref: ".planning/phases/04-animation-flow-control/04-UAT-SWEEP.json (outcome field)"
        status: pass
    human_judgment: false
  - id: D5
    description: "ANIM-03/ANIM-04 certified complete via the consolidated visual checkpoint"
    verification: []
    human_judgment: true
    rationale: "Task 5 was SKIPPED per its own routing -- the aggregate sweep outcome was FAIL, not PASS, so the consolidated visual checkpoint never executed and ANIM-03/ANIM-04 remain unchecked pending fresh operator routing"

duration: 50min
completed: 2026-07-17
status: complete
---

# Phase 04 Plan 12: Cross-Device ANIM-03/ANIM-04 Sweep Retarget Summary

**Operator-approved cross-device paired sweep (7 healthy-radio matrix devices + Tiles II reference) ran once per device; aggregate outcome FAIL (5/5 valid gate sessions FAILed) under unusually high ambient network loss -- ANIM-03/ANIM-04 remain unchecked pending fresh operator routing.**

## Performance

- **Duration:** ~50 min (this session, Tasks 3-4; Tasks 1-2 completed in a prior session)
- **Started:** 2026-07-17T06:59:45+10:00 (Task 3 resume)
- **Completed:** 2026-07-17T07:49:11+10:00
- **Tasks:** 5 total (Task 1 + Task 2 checkpoint completed in the prior session; Task 3, Task 4 completed this session; Task 5 skipped per its own routing)
- **Files modified:** 15 (6 governing/harness files modified, 10 new evidence files, 1 design brief + runner from Task 1)

## Task 2: Operator Checkpoint (completed prior session, recorded here for the complete record)

The Task 2 blocking checkpoint presented the complete final wording from
`04-SWEEP-DESIGN.md` section 8 (both ROADMAP criteria, both REQUIREMENTS entries,
the harness sweep contract, the 04-06/04-07 supersession text, the Tiles ruling
verbatim, the aggregation power table, the attempt-budget derivation, and the
wall-time estimate) with three options: (1) approve as presented, (2) approve
with amendments, (3) reject.

**Operator's verbatim reply: "1"** -- approve as presented, unamended. No
amendments were requested; the wording in `04-SWEEP-DESIGN.md` section 8 was
applied exactly as written.

## Accomplishments

- Applied the operator-approved cross-device sweep wording verbatim to ROADMAP
  Phase 4 criteria 3 and 4 and REQUIREMENTS ANIM-03/ANIM-04 (checkboxes stay
  unchecked; Traceability rows stay Pending), and appended exactly one new
  supersession notice each to 04-06-PLAN.md and 04-07-PLAN.md (visual ownership
  consolidates onto this plan's Task 5)
- Generalised `uat_ack_stream.py` to sweep mode: a module-level `ROSTER` (7 gate
  devices + System Test Tiles II as reference), `--sweep-device SERIAL` and
  `--sweep-verdict` CLI modes, serial-authoritative device resolution
  (roster-IP fast path + `find_by_serial` broadcast fallback), profile
  auto-selection (`CeilingLight` instance -> ceiling, else tiles),
  `expected_packets_per_frame()` (chain-dims-derived, replacing the hard-coded
  ceiling constant), and as-found power+colour capture/restore shared by both
  the single-device and sweep-device CLI modes -- all per-device paired-gate
  constants and `_evaluate` semantics unchanged
- Ran the sweep: one attempt per device, sequentially, over all 8 roster
  entries, then `--sweep-verdict` to deterministically aggregate the on-disk
  per-device JSONs
- Recorded the honest aggregate outcome (FAIL) in STATE.md's UAT sequencing
  gate bullet with full per-device routing, and committed all evidence

## Per-Device Sweep Results

| Device | Role | Outcome | Gated pooled | Blind pooled | Fisher p | Ratio | Validity | Restoration |
|---|---|---|---|---|---|---|---|---|
| Playroom Luna | gate | FAIL | 24/81 = 29.63% | 29/69 = 42.03% | 0.0790 | 1.42 | valid | succeeded |
| Dining Room Table Candle | gate | INCONCLUSIVE | 2/155 = 1.29% | 5/140 = 3.57% | 0.1841 | 2.77 | **ambient n=90 < 100 (V2)** | succeeded |
| Makerspace Candle | gate | FAIL | 27/77 = 35.06% | 30/67 = 44.78% | 0.1544 | 1.28 | valid | succeeded |
| Makerspace Tube | gate | FAIL | 24/86 = 27.91% | 28/73 = 38.36% | 0.1094 | 1.37 | valid | succeeded |
| Makerspace Ceiling | gate | FAIL | 24/79 = 30.38% | 28/68 = 41.18% | 0.1166 | 1.36 | valid | succeeded |
| Playroom Ceiling | gate | FAIL | 28/72 = 38.89% | 32/54 = 59.26% | 0.0184 | 1.52 | valid | succeeded |
| My Office Ceiling Capsule | gate | INCONCLUSIVE | 23/82 = 28.05% | 36/38 = 94.74% | 1.0e-12 | 3.38 | **2 gated rounds delivered_ratio < 0.50 (V3)** | succeeded |
| System Test Tiles II | **reference** | FAIL | 14/102 = 13.73% | 22/85 = 25.88% | 0.0280 | 1.89 | valid | succeeded |

Every measured device showed markedly higher query loss than any prior session
in this phase (gated 13.7-38.9%, blind 25.9-94.7%) -- consistent with the
operator's own "noisy environment" note (2026-07-17: "there is also a lot of
other stuff happening on my PC at the moment and the network"). The gated arm
was directionally better than blind in every single measured session (ratios
1.28-3.38x) but the relative rule's significance+ratio bar, and the clean-escape
floor, were both designed for a much less lossy ambient environment than this
session actually encountered.

### ANIM-04 framebuffer-path evidence (3 ceiling-class devices)

| Device | Chain dims | Expected packets/frame | packet_shape_ok (all rounds) | Ack RTT median | Ack RTT samples/round | A1/A2 disposition |
|---|---|---|---|---|---|---|
| Makerspace Ceiling | 8x8 | 1 (<=64 px, one Set64, no CopyFB) | true | 50.2 ms | 442-475 | **confirmed** |
| Playroom Ceiling | 8x8 | 1 | true | 50.1-50.2 ms | 466-507 | **confirmed** |
| My Office Ceiling Capsule | **16x8** (not the roster's assumed 13x26) | 3 (64//16=4 rows/packet, ceil(8/4)=2 Set64, +1 CopyFB) | true | 150.0-150.2 ms | 230-297 | **confirmed** |

The Capsule's reported chain (16x8 = 128 pixels) differs from the roster
documentation's assumed 13x26 (338 pixels) -- this is a **roster documentation
discrepancy, not a harness defect**: `expected_packets_per_frame()` is derived
independently from the REPORTED chain dimensions on every session (never a
hard-coded per-product constant), so it correctly computed 3 packets/frame for
the actual 16x8 geometry and every sent gated frame matched it across all 3
rounds. The CopyFrameBuffer ack-probe attachment (D4-04) is confirmed on all
three ceiling-class devices: every gated round recorded >= 1 ack RTT sample,
with medians of 50 ms (8x8 devices, 1 packet/frame) and 150 ms (Capsule,
3 packets/frame) -- both well under the 1 s expiry tuning.

## Aggregate Verdict

```
N_valid = PASS + FAIL among gate devices = 0 + 5 = 5   (quorum = 5, MET)
K       = N_valid - allowed_fails = 5 - 1 = 4           (min PASSes required)
FAIL count among valid gate sessions = 5                (> allowed_fails = 1)
=> aggregate outcome = FAIL
```

Dining Room Table Candle and My Office Ceiling Capsule were INCONCLUSIVE
(excluded from N_valid but reported); System Test Tiles II FAILed but was never
counted (reference-only, per the operator's Tiles ruling). Full arithmetic and
per-device rows are in `04-UAT-SWEEP.json`.

## Task 5: Consolidated Visual Checkpoint

**Skipped -- aggregate not PASS.** Per the plan's own routing, Task 5 (the
consolidated smoothness + geometry verdict on My Office Ceiling Capsule)
executes ONLY on Task 4 aggregate PASS. Since the aggregate outcome was FAIL,
Task 5 was not presented to the operator; ANIM-03 and ANIM-04 stay unchecked.

## Task Commits

Each task was committed atomically:

1. **Task 1: Cross-device sweep criterion design brief + reproducible aggregation runner** - `800b3b5` (docs) -- completed in the prior session
2. **Task 2: Blocking operator approval** - checkpoint only, no commit (decision recorded above) -- completed in the prior session
3. **Task 3a: Apply approved wording to governing documents** - `ec87a76` (docs)
4. **Task 3b: Generalise the harness to sweep mode** - `4e7640b` (feat)
5. **Task 4: Run the sweep, honest per-device + aggregate evidence** - `15e2cc0` (test)

**Plan metadata:** commit pending (this SUMMARY.md + STATE.md + ROADMAP.md/REQUIREMENTS.md close-out)

## Files Created/Modified

- `.planning/phases/04-animation-flow-control/04-SWEEP-DESIGN.md` - cross-device criterion design brief (Task 1, prior session)
- `.planning/phases/04-animation-flow-control/sweep_design.py` - reproducible exact-binomial aggregation runner (Task 1, prior session)
- `.planning/ROADMAP.md` - Phase 4 criteria 3+4 replaced with the approved cross-device sweep wording
- `.planning/REQUIREMENTS.md` - ANIM-03/ANIM-04 replaced with the approved wording (checkboxes unchecked)
- `.planning/phases/04-animation-flow-control/04-06-PLAN.md` - one new supersession notice appended (Task 2 superseded)
- `.planning/phases/04-animation-flow-control/04-07-PLAN.md` - one new supersession notice appended (superseded in full)
- `.planning/phases/04-animation-flow-control/uat_ack_stream.py` - ROSTER, sweep CLI modes, serial-authoritative resolution, profile auto-selection, `expected_packets_per_frame()`, as-found capture/restore
- `.planning/phases/04-animation-flow-control/04-UAT-SWEEP-<serial>.json` x8 - per-device sweep evidence
- `.planning/phases/04-animation-flow-control/04-UAT-SWEEP.json` - sweep-level aggregate verdict
- `.planning/STATE.md` - UAT sequencing gate bullet updated with the sweep outcome and routing

## Decisions Made

- Operator approved the complete cross-device sweep wording as presented
  (verbatim "1") -- no amendments to K, quorum, attempt budget, roster
  membership, or the visual device
- K=4 required PASSes of N_valid=5..7 (allowed_fails=1), quorum Q=5: the
  strictest K meeting the pre-declared P(sweep PASS | historical rate) >= 0.85
  bar (power 0.8523); the all-must-pass power (0.4813, a coin-flip sweep) was
  surfaced explicitly and rejected
- One attempt per device (no per-device re-runs): cross-device replication
  (7 independent sessions) absorbs a transient hit on one device via the
  aggregation rule instead of a re-run, removing any retry-until-pass surface
- Thresholds, roster membership, and the aggregation rule were NOT adjusted
  after seeing results -- the FAIL is recorded honestly, exactly as the
  operator's own approved rule computed it

## Deviations from Plan

None - plan executed exactly as written. The Capsule's chain dimensions
(16x8, not the roster's assumed 13x26) is a pre-existing documentation
discrepancy in the design brief's roster table (Task 1, prior session,
predating this session's work), not a deviation in this session's
execution -- the harness's chain-dims-derived assertion handled it correctly
without any code change, and the discrepancy is called out here for the
transparency it deserves rather than silently absorbed.

## Issues Encountered

The measured network conditions during this sweep were substantially lossier
than any prior session in Phase 4 (gated losses 13.7-38.9% vs the ~0-9% range
seen in 04-06 through 04-11; blind-fire losses up to 94.7%). This matches the
operator's own contemporaneous observation of a noisy PC/network environment
at measurement time. It produced 5 genuine per-device FAILs (the gated arm
still won directionally in every case, 1.28-3.38x, but the significance+ratio
bar and the 2.5% clean escape were both calibrated for calmer conditions) and
2 INCONCLUSIVE sessions (one from insufficient ambient sample size, one from
gated delivered_ratio dropping below the 0.50 sanity floor under load). No
threshold was touched in response -- this is exactly the honest-reporting
discipline the plan mandates.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- ANIM-03 and ANIM-04 remain unchecked; the aggregate sweep FAIL means fresh
  operator routing is required before either requirement can close
- **Recommended next step:** `/gsd-plan-phase 4 --gaps` with
  `04-UAT-SWEEP.json`, the 8 per-device JSONs, and this summary as the new
  evidence. Given the measured network conditions were anomalously lossy
  (consistent with the operator's own real-time observation of a noisy
  environment), the operator may want to consider: (a) re-running the sweep
  under calmer network conditions before deciding anything about the
  criterion itself, since every device's gated arm still won directionally;
  (b) revisiting the aggregation/attempt-budget rule given the one-attempt
  budget could not absorb an environment-wide degradation affecting all
  8 devices simultaneously (a condition the design brief's power analysis did
  not model); or (c) some combination -- this is the operator's call, not an
  executor decision
- The generalised harness (`uat_ack_stream.py --sweep-device` /
  `--sweep-verdict`) is reusable as-is for any re-run: no threshold, roster,
  or code change occurred in response to this outcome
- Phase 5 (Reliability Documentation) depends on Phase 4 completion and
  remains blocked on ANIM-03/ANIM-04

---
*Phase: 04-animation-flow-control*
*Completed: 2026-07-17*

## Self-Check: PASSED

All 15 claimed files verified present on disk; all 4 claimed commit hashes
(800b3b5, ec87a76, 4e7640b, 15e2cc0) verified present in git history.
