---
phase: 04-animation-flow-control
plan: 08
subsystem: animation
tags: [gap-closure, hardware-uat, evidence, ack-gating, anim-03]
requires:
  - "04-05: uat_ack_stream.py harness mechanics (prober, observer, reachability guard)"
  - "04-06: the reproducible ANIM-03 FAIL evidence (04-UAT-TILES*.json, commit 5de88f6)"
  - "spike 003: stream.py photons-arm mechanics and raw results JSONL"
provides:
  - "04-GAP-SPIKE-FORENSICS.md: spike 003 sample-size audit with binomial bounds (H2 calibration half settled)"
  - "uat_loss_investigation.py: threshold-free five-arm investigation instrument"
  - "04-GAP-INVESTIGATION.json: per-arm aggregate hardware evidence from both Tiles"
  - "04-GAP-INVESTIGATION-EVENTS.jsonl: 1009 per-query + 7500 per-frame timestamped events"
affects:
  - "04-09: analysis and operator routing decision consumes all four artefacts"
  - "04-06 Task 2 / 04-07: remain gated on the 04-09 routing decision"
tech-stack:
  added: []
  patterns:
    - "Threshold-free measurement instrument: exit codes only 0 (measured) / 2 (primary ENV-ERROR); no verdict fields"
    - "Per-event JSONL capture (kind=query/frame with monotonic t) for loss-clustering analysis"
    - "Instrument committed before hardware run so the protocol is provably fixed pre-run"
key-files:
  created:
    - .planning/phases/04-animation-flow-control/04-GAP-SPIKE-FORENSICS.md
    - .planning/phases/04-animation-flow-control/uat_loss_investigation.py
    - .planning/phases/04-animation-flow-control/04-GAP-INVESTIGATION.json
    - .planning/phases/04-animation-flow-control/04-GAP-INVESTIGATION-EVENTS.jsonl
  modified:
    - .pre-commit-config.yaml
decisions:
  - "Spike 003's 0% threshold was calibrated beyond its evidence's resolution: one 50-query photons round (>=6% rule-of-three upper bound; 18% chance of 0/50 even at the UAT's 3.37% rate)"
  - "ANIM-03 deliberately NOT marked complete: this plan gathers evidence only; 04-09 interprets and routes (04-05 precedent)"
  - "Large-file hook: scoped exclude for .planning/phases/*-EVENTS.jsonl evidence logs rather than raising the 1000 KB cap or compressing committed evidence"
metrics:
  duration: ~28min
  tasks: 3
  files: 5
  completed: 2026-07-17
status: complete
---

# Phase 04 Plan 08: ANIM-03 Gap Investigation (Evidence Gathering) Summary

Spike 003's 0% loss threshold came from a single underpowered 50-query round; a
committed-before-run five-arm instrument then measured control/shipped/replica/sweep
arms on both Tiles devices with per-event timestamps, producing verbatim evidence for
04-09's routing decision.

## Task Commits

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Spike 003 raw-data forensics | 0f453e8 (`docs(04-08)`) | 04-GAP-SPIKE-FORENSICS.md |
| 2 | Threshold-free investigation instrument | f7c0854 (`feat(04-08)`) | uat_loss_investigation.py |
| — | Hook-cap exemption (deviation, Rule 3) | 1c2ddc1 (`chore(04-08)`) | .pre-commit-config.yaml |
| 3 | Hardware run + evidence commit | dd6a15e (`test(04-08)`) | 04-GAP-INVESTIGATION.json, 04-GAP-INVESTIGATION-EVENTS.jsonl |

The instrument commit (f7c0854) lands strictly before the evidence commit (dd6a15e) —
the protocol is provably fixed pre-run in git history.

## Forensics Verdict (Task 1 — H2 calibration half, settled)

Computed from the raw files, formulas shown in 04-GAP-SPIKE-FORENSICS.md:

- Spike 003's photons arm was **exactly one round of 50 queries with 0 losses**; the
  no-stream baseline was n=20 (plus another n=20 in the aborted first run).
- Pooled 04-06 UAT rate from the two UAT JSONs: **9/267 = 3.37%** (run 1: 4/135 = 2.96%;
  run 2: 5/132 = 3.79%).
- 0/50 carries a 6.0% rule-of-three (7.11% exact one-sided 97.5%) upper bound, and had
  an **18% probability of occurring even if the true rate is 3.37%**. The baseline's
  0/20 bounds the ambient floor only at <=15%.
- **Verdict: the 0% threshold was calibrated beyond the spike's resolution.** This
  settles the calibration question only — whether ~3.4% is fixable or a floor was
  deferred to the hardware arms.
- Mechanical spike-vs-shipped differences enumerated for the hardware arms: per-packet
  awaited sends vs synchronous sendto burst; raw-socket 1.0 s prober vs DeviceConnection
  2.0 s prober (more generous — timeout width cannot explain the UAT losing more); probe
  attachment and D4-01 gate tuning identical.

## Hardware Evidence (Task 3 — numbers only, no H1/H2 verdict here)

Run 2026-07-17T03:28:57 local, exit 0, no re-runs, both devices reachable. Per-arm
pooled queries alongside the references:

| Arm | Device | Load | Queries ok | Lost | Loss % |
|-----|--------|------|-----------|------|--------|
| control (120 s, no stream) | Tiles I | — | 227 | 0 | 0.00 |
| shipped (4 × 30 s) | Tiles I | 20 FPS | 187 | 2 | 1.06 |
| replica (spike-faithful, 4 × 30 s) | Tiles I | 20 FPS | 176 | 9 | 4.86 |
| sweep (2 × 30 s each) | Tiles I | 10 + 15 FPS | 209 | 1 | 0.48 |
| fallback (60 s control + 2 × 30 s shipped) | Tiles II | 20 FPS | 194 | 4 | 2.02 |
| *reference: spike 003 photons* | Tiles I | 20 FPS | *50* | *0* | *0.0* |
| *reference: 04-06 UAT pooled* | Tiles I | 20 FPS | *258* | *9* | *3.37* |

Sweep detail: 10 FPS rounds lost 0/108; 15 FPS rounds lost 1/102. Fallback loss was
entirely in its streaming rounds (control 0/114; shipped rounds 4/84). Events JSONL
holds 1009 query events and 7500 frame events (gated flag + outstanding count per
frame) for 04-09's loss-clustering analysis.

Interpretation of these numbers against the pre-declared rules is 04-09 Task 1's job —
kept separate so measurement and interpretation cannot contaminate each other.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Large-file pre-commit hook rejected the events evidence**
- **Found during:** Task 3 (evidence commit)
- **Issue:** `check-added-large-files` (--maxkb=1000) rejected
  04-GAP-INVESTIGATION-EVENTS.jsonl (1078 KB). Bypassing hooks (--no-verify) and
  rewriting measured evidence bytes were both off the table.
- **Fix:** Scoped `exclude: ^\.planning/phases/.*-EVENTS\.jsonl$` on that hook only —
  the 1000 KB policy stays intact for source files; evidence bytes untouched.
- **Files modified:** .pre-commit-config.yaml
- **Commit:** 1c2ddc1

No instrument mechanism fixes were needed (no 5f1d80b-style crash): the battery ran
start-to-finish on the first attempt, exit 0.

### Deliberate non-action

- **ANIM-03 not marked complete in REQUIREMENTS.md** despite appearing in this plan's
  frontmatter `requirements`. This plan gathers evidence for the still-open ANIM-03 gap;
  marking it complete would contradict the recorded 04-05 decision and the STATE
  sequencing blocker. 04-09's routing decision owns the requirement's resolution.

## Pinned-Artefact Verification

`git diff HEAD` against `uat_ack_stream.py`, `04-UAT-TILES.json`,
`04-UAT-TILES-run1-FAIL.json` and everything under `src/` is empty across all plan
commits — the 04-06 UAT artefacts, its thresholds, and the shipped gate are
byte-identical to their pre-plan state. No packages were installed.

## Known Stubs

None — all artefacts carry real measured data; the instrument has no placeholder paths.

## Threat Flags

None. The only new surface is the pre-declared outbound streaming/query load against
the two quiesced test devices (T-04-15, mitigated by fixed arm durations, 10 s
inter-arm rests, and reachability guards, all as planned).

## Self-Check: PASSED

All four artefacts and this summary exist on disk; commits 0f453e8, f7c0854, 1c2ddc1
and dd6a15e are present in history with the instrument strictly before the evidence.
