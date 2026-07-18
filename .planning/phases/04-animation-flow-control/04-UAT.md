---
status: complete
phase: 04-animation-flow-control
source: [04-01-SUMMARY.md, 04-02-SUMMARY.md, 04-03-SUMMARY.md, 04-04-SUMMARY.md, 04-05-SUMMARY.md, 04-12-SUMMARY.md, 04-13-SUMMARY.md]
started: 2026-07-17T15:27:12Z
updated: 2026-07-17T15:28:10Z
---

## Current Test

[testing complete]

## Tests

### 1. ANIM-03/ANIM-04 Resolution — Operator Ruling Over Honest FAIL
expected: The cross-device sweep honestly FAILed (5/5 valid sessions, 04-UAT-SWEEP.json unmodified); resolution is your ruling "2" (04-RULING.md) accepting the directional dossier over the FAILed bar — never presented as a statistical pass. Confirm the ruling still stands.
result: pass
coverage_id: D5 (04-12) / ruling

### 2. Capsule Visual Streaming Verdict (ANIM-03 smoothness + ANIM-04 geometry)
expected: Single Capsule visual streaming round (My Office Ceiling Capsule, 16×8 zones / 3 packets per frame, --profile ceiling --rounds 1 --duration 60). Your recorded dual verdict — "Geometry was fine. It was as smooth as the tiles. No multi-second freezes but it stuttered throughout." — reads as geometry PASS and smoothness accepted, with the stutter being documented latest-frame-wins degradation under 20 FPS saturation (~10 FPS sustainable at this chain shape), carried forward as a Phase 5 doc recommendation. Confirm this verdict still stands.
result: pass
coverage_id: D4 (04-13)

### 3. Ack-gate flow control facility (ANIM-01)
expected: AckGate in flow.py (gate at 2 outstanding, ~1s expiry, latest-frame-wins), gate check before framebuffer work, no consumer-facing toggle. 16 test_flow.py + gating suite in test_animator.py, all green.
result: pass
source: automated
coverage_id: D1/D2 (04-01)

### 4. Zero-allocation prebaked send path preserved (ANIM-02)
expected: Prebaked templates at construction; ack flag baked once into probe template; hot path is colour update + sequence byte + one dict write + non-blocking recvfrom_into sweep; no reaching into transport/connection privates.
result: pass
source: automated
coverage_id: 04-02 D1-D4

### 5. Packet-shape + probe-index seam (ANIM-02)
expected: FLAGS_OFFSET/ACK_REQUIRED_FLAG constants, probe_template_index seam (large-tile → final CopyFrameBuffer), row-aligned large-tile chunking. 100% coverage on packets.py.
result: pass
source: automated
coverage_id: 04-03 D1/D2

### 6. Animator gating integration + additive stats
expected: Ack-gated send_frame with additive AnimatorStats.gated/acks_outstanding (backwards compatible defaults); gated frames drop, consume no sequence numbers; close() resets gate.
result: pass
source: automated
coverage_id: 04-04 D1-D5

### 7. Cross-device sweep design + reproducible aggregation runner
expected: 04-SWEEP-DESIGN.md criterion brief + exact-binomial aggregation runner (sweep_design.py runs clean); frozen rule (quorum 5, allowed_fails 1) declared before results.
result: pass
source: automated
coverage_id: 04-12 D1

### 8. Operator-approved sweep wording applied verbatim
expected: Operator approval (verbatim "1") of cross-device sweep wording applied verbatim to ROADMAP/REQUIREMENTS and 04-06/04-07 supersession notices (git ec87a76).
result: pass
source: automated
coverage_id: 04-12 D2

### 9. Sweep-generalised harness (uat_ack_stream.py)
expected: ROSTER, --sweep-device/--sweep-verdict modes, serial-authoritative resolution, profile auto-selection, expected_packets_per_frame() derived from reported chain dims, as-found capture/restore. ruff/pyright clean.
result: pass
source: automated
coverage_id: 04-12 D3

### 10. 8-device sweep evidence collected honestly
expected: 8 per-device sweep JSONs + aggregate 04-UAT-SWEEP.json, one attempt per device, aggregated by the frozen rule; outcome FAIL recorded honestly, thresholds untouched after results.
result: pass
source: automated
coverage_id: 04-12 D4

### 11. Ruling record complete and honest (04-RULING.md)
expected: 04-RULING.md records routing options + verbatim reply "2", supporting context, cited directional dossier, dims correction, and full proposed wording — committed before the wording checkpoint; contains "never a statistical pass".
result: pass
source: automated
coverage_id: 04-13 D1

### 12. Final wording approved and applied verbatim
expected: Operator approval (verbatim "1") applied verbatim to ROADMAP criteria 3+4, REQUIREMENTS ANIM-03/04, and 04-06/04-07 final supersession notices (git fd7207c).
result: pass
source: automated
coverage_id: 04-13 D2

### 13. Capsule dims correction applied everywhere governing
expected: 16×8 zones / 128 zones / 26in×13in applied to ROADMAP, REQUIREMENTS, harness comments; expected_packets_per_frame(1,16,8)==3, (1,13,26)==8, (5,8,8)==5; historical records left as-is. ruff/pyright clean.
result: pass
source: automated
coverage_id: 04-13 D3

### 14. Close-out gates cleared, no stale residue
expected: ANIM-03/ANIM-04 marked complete in REQUIREMENTS.md; STATE.md/ROADMAP/04-06/04-07 gates cleared; no residual "visual pending"/"routing required"/"04-12 Task 5" strings.
result: pass
source: automated
coverage_id: 04-13 D5

## Summary

total: 14
passed: 14
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

[none yet]
