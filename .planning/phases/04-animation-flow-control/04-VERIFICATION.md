---
phase: 04-animation-flow-control
verified: 2026-07-17T15:28:30Z
status: passed
score: 4/4 must-haves verified
behavior_unverified: 0
overrides_applied: 0
---

# Phase 4: Animation Flow Control Verification Report

**Phase Goal:** Streaming animations pace themselves via ack-gated flow control decided inside the animation layer, so frame delivery never starves other traffic to the device — invisible to downstream consumers
**Verified:** 2026-07-17T15:28:30Z
**Status:** passed
**Re-verification:** Yes — refreshed after UAT (see Re-verification Note below)

## Re-verification Note (2026-07-17)

Refreshed during `/gsd-verify-work 04`. Both human-judgement items — the ANIM-03/
ANIM-04 acceptance-over-FAIL ruling (04-RULING.md, "2") and the Capsule dual
visual verdict (geometry PASS, smooth-as-tiles with documented latest-frame-wins
stutter) — were re-confirmed PASS by the operator in UAT (`04-UAT.md` tests 1–2).
All 14 UAT checks passed (12 automated coverage entries + 2 human verdicts),
0 issues.

Since initial verification (2026-07-17T02:20Z), `src/lifx/animation/` was edited
by phase-05 commit `docs(05-06)` (docstring de-jargoning). Behaviour was
re-confirmed against the current code: `uv run pytest tests/test_animation/` →
**185 passed**; git tree clean. The FAIL evidence JSONs remain unmodified (the
statistical FAIL for criteria 3–4 is still the recorded state, resolved by the
operator ruling layered on top — never a statistical pass).

**Verification mode note:** Criteria 3–4 were resolved by operator ruling
(`04-RULING.md`, verbatim reply "2", 2026-07-17) plus the operator's dual
visual verdict (04-13 Task 4). Per the amended ROADMAP wording, this
verification checks that the RECORDS are complete, honest, and coherent —
not that the sweep statistics passed (they honestly did not; that is the
recorded state, preserved unmodified).

## Goal Achievement

### Observable Truths (ROADMAP Phase 4 Success Criteria)

| # | Truth | Status | Evidence |
| --- | ----- | ------ | -------- |
| 1 | Animator gates frame delivery on outstanding ack probes (ack flag on first packet of each frame, gate at 2 outstanding, ~1 s expiry, latest-frame-wins) as internal behaviour with no consumer-facing toggle (ANIM-01) | ✓ VERIFIED | `src/lifx/animation/flow.py`: `ACK_INFLIGHT_LIMIT = 2`, `ACK_EXPIRY_SECONDS = 1.0`, `AckGate.gated`/`track()`/`sweep()`; `animator.py:398-406` gate check before any framebuffer work — gated frames drop, never queue. `send_frame()` signature unchanged; `AckGate`/`flow` never exported from `lifx.animation.__init__` (asserted by `test_animator.py` "AckGate not in `__all__`" test). Behavioural tests: `test_flow.py` (16 tests: gate-at-limit, expiry prune, wrap-collision overwrite, runt/wrong-type/wrong-source rejection, OSError exit) + `test_animator.py` gating suite (gate-at-2, gated frame skips `framebuffer.apply`, consumes no sequence numbers, expiry reopens gate without acks, `close()` resets gate, validation still raises when gated) — all ran green in the full suite. |
| 2 | Zero-allocation prebaked-template send path preserved; ack collection is a proper animator facility with no private-reaching (ANIM-02) | ✓ VERIFIED | Templates prebaked at construction (`animator.py:159-170`); `ack_required` flag baked ONCE into the probe template (`probe_template_index` seam, `packets.py`; large-tile mode → final CopyFrameBuffer per D4-04, default → index 0). Hot path per frame: colour update + sequence byte + one dict write + non-blocking `recvfrom_into` sweep into a preallocated 64-byte buffer (`flow.py:85`, `__slots__`, fixed-offset peeks, no `parse_message`, no per-datagram allocation). Animation layer imports only public seams: `lifx.const.LIFX_UDP_PORT`, `lifx.network.utils.allocate_source`, `lifx.protocol.models.Serial` — grep confirms zero reaching into transport/connection privates; acks are read from the animator's OWN socket. |
| 3 | ANIM-03 record: cross-device paired sweep honestly FAILed its statistical bar; resolution by operator ruling accepting the directional dossier; visual smoothness verdict recorded (ANIM-03) | ✓ VERIFIED | `04-RULING.md` records the ruling verbatim ("2", 2026-07-17) with the option text quoted, the 8-device dossier table with per-session Fisher p and evidence-file citations, and an explicit "acceptance over a recorded FAIL, never a statistical pass" framing. `04-UAT-SWEEP.json` still records `outcome: FAIL`, aggregation `{PASS: 0, FAIL: 5, INCONCLUSIVE: 2}` — git log shows the file committed exactly once (`15e2cc0`) and never touched since; same single-commit history for `04-UAT-TILES.json` (`bfeae3e`) and `04-GAP-INVESTIGATION.json` (`dd6a15e`). The operator's verbatim dual verdict ("Geometry was fine. It was as smooth as the tiles. No multi-second freezes but it stuttered throughout.") and the "1" approval are recorded in `04-13-SUMMARY.md` and STATE.md; the visual round's headless FAIL (`04-UAT-VISUAL-CAPSULE.json`, `outcome: FAIL`) is preserved and recorded as non-gating context per the ruling. |
| 4 | ANIM-04 record: framebuffer-path evidence stands (packet shape + CopyFB ack RTTs on the three ceiling-class devices); dims correction applied; visual geometry verdict recorded (ANIM-04) | ✓ VERIFIED | Independent re-read of all 8 per-device sweep JSONs confirms the ROADMAP claims exactly: `packet_shape_ok: true` on every gated round of every device; every gated round has hundreds of ack RTT samples (≥ 1 required); Capsule (`d073d587daab`) `expected_packets_per_frame: 3` with RTT medians 150.0–150.2 ms; the two 8×8 ceilings RTT medians 50.1–50.2 ms — all matching criterion 4 verbatim. Dims correction (16×8 zones, 128 zones, 26 in × 13 in physical) applied in ROADMAP, REQUIREMENTS, and the three comment-only `uat_ack_stream.py` locations; remaining "13×26" strings in governing docs are either the deliberate chain-geometry worked example (per ruling §5(vii)) or carry the inline `[corrected 2026-07-17 ...]` annotation (ROADMAP 04-07 bullet). Historical records (04-SWEEP-DESIGN.md, prior SUMMARYs, evidence JSONs) left unrewritten per the ruling's scope rule. Geometry PASS verdict recorded (04-13 Task 4). |

**Score:** 4/4 truths verified (0 present-but-behaviour-unverified)

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `src/lifx/animation/flow.py` | `AckGate` facility (gate 2, ~1 s expiry, non-blocking sweep) | ✓ VERIFIED | 165 lines, substantive; wired into `Animator.__init__`/`send_frame`/`close`; 100% coverage (in the "skipped due to complete coverage" set) |
| `src/lifx/animation/animator.py` | Ack-gated `send_frame` with additive `AnimatorStats.gated`/`acks_outstanding` | ✓ VERIFIED | Gate check before framebuffer work; additive dataclass fields with defaults (backwards compatible); 100% coverage |
| `src/lifx/animation/packets.py` | `FLAGS_OFFSET`/`ACK_REQUIRED_FLAG`, `probe_template_index` seam, row-aligned large-tile chunking | ✓ VERIFIED | `FLAGS_OFFSET = 22`, `ACK_REQUIRED_FLAG = 0x02`; large-tile probe on final CopyFrameBuffer (D4-04) with one-line fallback seam; `rows_per_packet` row-aligned chunking; 100% coverage |
| `tests/test_animation/test_flow.py` | AckGate branch matrix | ✓ VERIFIED | 16 behavioural tests incl. mock-socket ack injection |
| `tests/test_animation/test_animator.py` | Gating behaviour + no-export guard | ✓ VERIFIED | 45 tests incl. gate-at-2, latest-frame-wins, expiry, close-resets, `AckGate not in __all__` |
| `.planning/phases/.../uat_ack_stream.py` | UAT harness (ANIM-03/ANIM-04) | ✓ VERIFIED | Present with the three comment-only dims corrections applied per ruling §5(vii); measurement semantics byte-identical to 04-12 per ruling §6 |
| `04-RULING.md` + evidence JSONs | Complete, honest, unmodified record | ✓ VERIFIED | All 4 named evidence JSONs parse; each committed once, never amended |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | --- | --- | ------ | ------- |
| `Animator.send_frame()` | `AckGate.sweep()/gated/track()` | direct calls on own socket | ✓ WIRED | `animator.py:398-418`; probe tracked only on `probe_template_index` packet |
| `Animator.__init__` | probe flag bake | `_templates[probe_index].data[FLAGS_OFFSET] \|= ACK_REQUIRED_FLAG` | ✓ WIRED | Flag set once; hot loop never touches flags byte |
| `MatrixPacketGenerator.probe_template_index` | final CopyFrameBuffer (large-tile) | D4-04 override | ✓ WIRED | `tile_count * (packets_per_tile + 1) - 1` |
| `lifx.animation.__init__` | NO `AckGate`/flow export | D4-02 no-toggle | ✓ VERIFIED | Absent from imports and `__all__`; guarded by test |
| ROADMAP c3/c4 ↔ 04-RULING.md §5 | verbatim application | 04-13 Task 3 | ✓ COHERENT | Applied wording matches proposed wording; REQUIREMENTS/STATE/supersession notices consistent |

### Behavioural Spot-Checks

| Behaviour | Command | Result | Status |
| --------- | ------- | ------ | ------ |
| Full suite green (includes all flow/animator behavioural tests) | `uv run --frozen pytest -q` | 2618 passed, 12 deselected, 110 s | ✓ PASS |
| Evidence JSONs parse and match cited claims | python json re-read of SWEEP/TILES/GAP/VISUAL + 8 per-device files | `outcome: FAIL` (5/5 valid FAIL, 2 INCONCLUSIVE); `packet_shape_ok: true` all gated rounds; Capsule epf=3, RTT 150.0–150.2 ms; ceilings 50.1–50.2 ms | ✓ PASS |
| FAIL evidence never modified | `git log --follow` per evidence file | Single creating commit each (`15e2cc0`, `bfeae3e`, `d154ccf`, `dd6a15e`, `5de88f6`); no later commits | ✓ PASS |

### Requirements Coverage

| Requirement | Description | Status | Evidence |
| ----------- | ----------- | ------ | -------- |
| ANIM-01 | Ack-gated pacing, latest-frame-wins, no toggle | ✓ SATISFIED | Truth 1 |
| ANIM-02 | Zero-allocation path preserved, proper facility | ✓ SATISFIED | Truth 2 |
| ANIM-03 | Hardware validation resolved by operator ruling + visual smoothness verdict | ✓ SATISFIED (record) | Truth 3; REQUIREMENTS.md wording matches ruling §5(iii) with checkbox flipped post-verdict per the gate text |
| ANIM-04 | Framebuffer path covered, hardware-validated, geometry verdict | ✓ SATISFIED (record) | Truth 4 |

No orphaned requirements: REQUIREMENTS.md maps exactly ANIM-01..04 to Phase 4, all claimed by the phase plans.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| — | — | none | — | No TBD/FIXME/XXX/TODO/HACK/placeholder markers in any phase-modified source or test file |

### Human Verification Required

None outstanding. The two human-judgement items this phase required (ANIM-03
smoothness, ANIM-04 geometry) were completed by the operator at 04-13 Task 4
with verbatim verdicts recorded in `04-13-SUMMARY.md` and STATE.md, and the
governing ruling is recorded in `04-RULING.md`. The stutter observation was
recorded honestly (documented latest-frame-wins degradation under 20 FPS
saturation, ~10 FPS sustainable on the Capsule) and carried forward as a
Phase 5 DOCS-02 recommendation.

### Coherence Sweep (04-10 → 04-13 amendments)

- STATE.md carries the cleared close-out gate text (matches ruling §5(vi) cleared branch, extended with the verbatim verdict) — no stale "visual pending" text remains.
- 04-06-PLAN.md and 04-07-PLAN.md both carry FINAL SUPERSESSION NOTICES ending "do not execute any task from it"; ROADMAP marks them `[ ]` with matching "superseded — never execute" annotations. Plan count 11/13 executed is consistent.
- ROADMAP criteria 3–4 and REQUIREMENTS ANIM-03/04 use the operator-approved wording verbatim; nowhere is the outcome described as a statistical pass.
- Phase 4 top-level ROADMAP checkbox remains `[ ]` — correctly deferred to post-verification orchestration.

### Gaps Summary

None. The shipped code delivers criteria 1–2 with 100% coverage on all three
animation-layer modules and behavioural tests for every gate semantic; the
records for criteria 3–4 are complete, internally consistent, and honest —
the statistical FAIL is preserved unmodified everywhere it is cited, with the
operator ruling layered transparently on top.

---

_Verified: 2026-07-17_
_Verifier: Claude (gsd-verifier)_
