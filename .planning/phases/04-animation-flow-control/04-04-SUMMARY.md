---
phase: 04-animation-flow-control
plan: 04
subsystem: animation
tags: [animator, ack-gating, flow-control, udp, emulator, pyright]

# Dependency graph
requires:
  - phase: 04-animation-flow-control
    provides: "04-02's RED branch-matrix suite (test_flow.py) and animator gating/probe-baking/additive-stats suite (test_animator.py) — the exact GREEN target this plan closes"
  - phase: 04-animation-flow-control
    provides: "04-03's row-aligned large-tile chunking, FLAGS_OFFSET/ACK_REQUIRED_FLAG constants, and probe_template_index seam in packets.py"
provides:
  - "AckGate flow-control facility (src/lifx/animation/flow.py): ACK_INFLIGHT_LIMIT=2, ACK_EXPIRY_SECONDS=1.0, ACK_PKT_TYPE=45, non-blocking sweep on the animator's own socket, zero per-datagram allocation"
  - "Ack-gated Animator.send_frame: probe flag baked once at construction, sweep-then-gate ordering before framebuffer work, latest-frame-wins drop, additive AnimatorStats.gated/acks_outstanding observability"
  - "Fix: Animator factories now pass the device's actual port to the raw animation socket (previously always defaulted to 56700, silently misdirecting all animation traffic for non-standard-port devices)"
affects: [04-05-tiles-hardware-uat, 04-06-ceiling-hardware-uat, 04-07-anim04-uat, 05-reliability-documentation]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "AckGate: dict[int, float] outstanding-probe map + one preallocated bytearray(64) receive buffer; sweep() drains recvfrom_into until BlockingIOError/OSError, peeking pkt_type/source/sequence via fixed offsets (no parse_message, no allocation)"
    - "Runtime-read constants: ACK_INFLIGHT_LIMIT/ACK_EXPIRY_SECONDS/ACK_PKT_TYPE are Final module attributes read directly inside methods (never bound as method defaults), matching the project's monkeypatch-friendly idiom used elsewhere for retry gaps"
    - "Probe baking once at __init__: self._templates[packet_generator.probe_template_index].data[FLAGS_OFFSET] |= ACK_REQUIRED_FLAG — the hot send loop never touches the flags byte again"
    - "send_frame ordering: explicit length check -> lazy socket -> AckGate.sweep -> gate check (drop before any framebuffer work) -> apply/update_colors/send loop (tracking the probe's stamped sequence before advancing the counter)"

key-files:
  created:
    - src/lifx/animation/flow.py
  modified:
    - src/lifx/animation/animator.py

key-decisions:
  - "Constants placement follows the research plan exactly: ACK_INFLIGHT_LIMIT/ACK_EXPIRY_SECONDS/ACK_PKT_TYPE live in flow.py (animation-layer tuning, D4-05 scope), not const.py."
  - "AckGate is never exported from lifx.animation.__init__ — confirmed by the existing (already-passing) D4-02 no-toggle guard test; no change needed to __init__.py."
  - "[Rule 1 - Bug] Fixed a pre-existing latent bug surfaced by wiring the real ack-receive path: Animator.for_matrix/for_multizone/for_light never passed the connected device's actual port to the Animator constructor, always defaulting to LIFX_UDP_PORT (56700). On any device running on a non-standard port (every emulator-backed integration test, and any real device behind port-forwarding/NAT), the raw animation socket silently sent every frame to the wrong port. This was invisible before this phase because send_frame never verified delivery; it surfaced immediately as a 100%-reproducible 'acks never arrive' failure once the sweep path existed. Fixed by passing port=device.port in all three factory methods."

requirements-completed: [ANIM-01, ANIM-02]

coverage:
  - id: D1
    description: "AckGate facility (flow.py) satisfies the complete 16-test branch matrix from test_flow.py: constants, track/gated/outstanding_count/reset transitions, wrap-collision overwrite, the untrusted-datagram sweep validation matrix (empty/matching/multiple/untracked/runt/wrong-type/wrong-source/OSError), and explicit-now expiry pruning"
    requirement: "ANIM-01"
    verification:
      - kind: unit
        ref: "tests/test_animation/test_flow.py (16/16 pass)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Animator.send_frame gates before any framebuffer work, drops gated frames with packets_sent=0/no sequence consumed (latest-frame-wins), reopens on a matching ack from the correct source, ignores foreign-source acks, reopens via explicit-now expiry, and close() resets the gate"
    requirement: "ANIM-01"
    verification:
      - kind: unit
        ref: "tests/test_animation/test_animator.py::TestAnimatorGating (11/11 pass)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Ack-required probe flag baked exactly once at construction on the correct template (standard/multizone/light index 0; 13x26 large-tile final CopyFrameBuffer index 7); AnimatorStats gains additive gated/acks_outstanding fields with defaults; AckGate is never exported (D4-02)"
    requirement: "ANIM-02"
    verification:
      - kind: unit
        ref: "tests/test_animation/test_animator.py::TestAnimatorProbeBaking + TestAnimatorStatsFlowFields (4/4 pass)"
        status: pass
    human_judgment: false
  - id: D4
    description: "Deterministic end-to-end gating against the real embedded emulator: ack-drop scenario reaches the gate limit and reopens past ACK_EXPIRY_SECONDS, a healthy emulator collects acks every frame (acks_outstanding==1 from frame 2 onward), and the genuine 13x26 large-tile device exercises the row-aligned + CopyFB probe path end-to-end with correct port routing"
    requirement: "ANIM-01"
    verification:
      - kind: integration
        ref: "tests/test_animation/test_animator.py::TestAnimatorFlowControlIntegration (4/4 pass) + TestAnimatorForMatrixIntegration/TestAnimatorForMultizoneIntegration loop tests (2/2 pass)"
        status: pass
    human_judgment: false
  - id: D5
    description: "100% branch patch coverage across flow.py, animator.py, and packets.py (this phase's entire edited surface); full 2618-test suite green; pyright strict and ruff clean project-wide"
    verification:
      - kind: other
        ref: "uv run pytest tests/test_animation/ --cov=lifx.animation --cov-report=term-missing (100% on all 5 animation files) + uv run --frozen pytest (2618 passed) + uv run pyright + uv run ruff check ."
        status: pass
    human_judgment: false

# Metrics
duration: ~35min
completed: 2026-07-17
status: complete
---

# Phase 4 Plan 04: AckGate Implementation and Animator Wiring Summary

**Implemented the internal `AckGate` flow-control facility and wired sweep-then-gate ordering into `Animator.send_frame`, turning the full 04-02 RED suite green while fixing a pre-existing port-routing bug that the new ack-receive path exposed.**

## Performance

- **Duration:** ~35 min
- **Started:** 2026-07-17 (approx)
- **Completed:** 2026-07-17
- **Tasks:** 3 completed
- **Files modified:** 2 (`src/lifx/animation/flow.py` created, `src/lifx/animation/animator.py` modified)

## Accomplishments

- Created `src/lifx/animation/flow.py`: the `AckGate` facility with spike-003-measured constants (`ACK_PKT_TYPE=45`, `ACK_INFLIGHT_LIMIT=2`, `ACK_EXPIRY_SECONDS=1.0`), a preallocated 64-byte receive buffer, and a `sweep()` drain loop that peeks `pkt_type`/`source`/`sequence` via fixed-offset reads with zero per-datagram allocation. Turns `tests/test_animation/test_flow.py`'s 16-test branch matrix green with zero test edits.
- Wired `AckGate` into `Animator`: baked the `ack_required` flag once at construction onto the template named by `PacketGenerator.probe_template_index`; reordered `send_frame` to explicit length check → lazy socket → `AckGate.sweep` → gate check (drop before any framebuffer work, `packets_sent=0`, no sequence consumed) → the existing apply/update_colors/send loop, tracking the probe's stamped sequence immediately before advancing the counter. `close()` now also resets the gate. `AnimatorStats` gained additive `gated: bool = False` and `acks_outstanding: int = 0` fields. Turns the full 04-02 RED `test_animator.py` suite green with zero test edits.
- Found and fixed a pre-existing latent bug (Rule 1): none of the three `Animator` factory methods (`for_matrix`, `for_multizone`, `for_light`) ever passed the connected device's actual port to the constructor — the raw animation UDP socket always defaulted to `LIFX_UDP_PORT` (56700). This was invisible before this phase (send_frame never verified delivery), but became a 100%-reproducible integration-test failure once the ack sweep needed replies to actually arrive: every emulator-backed test runs on a random free port. Fixed by passing `port=device.port` in all three factories.
- Ran the full-phase branch-coverage audit (Task 3): `--cov-branch` shows 100% line and branch coverage across all five `src/lifx/animation/*.py` files with zero missing arcs — no coverage gaps to close, no pragmas needed. Full suite (2618 tests) green in ~111s (comparable to the Phase 3 ~112s baseline); `uv run pyright` and `uv run ruff check .` both clean project-wide.

## Task Commits

Each task was committed atomically:

1. **Task 1: AckGate facility (src/lifx/animation/flow.py)** - `c3f18a8` (feat)
2. **Task 2: Wire ack-gated flow control into Animator** - `24357e7` (feat)
3. **Task 3: Branch-coverage audit + full-suite regression** - no code changes required (100% coverage confirmed, no gaps found); verification evidence recorded below

**Plan metadata:** committed alongside this SUMMARY.

## Files Created/Modified

- `src/lifx/animation/flow.py` - New: `AckGate` class + `ACK_PKT_TYPE`/`ACK_INFLIGHT_LIMIT`/`ACK_EXPIRY_SECONDS` constants. `gated`/`outstanding_count` properties, `track()`/`sweep()`/`reset()` methods.
- `src/lifx/animation/animator.py` - `AnimatorStats` gains `gated`/`acks_outstanding`; `__init__` creates `self._ack_gate` and bakes the probe flag once; `send_frame` reordered for sweep-then-gate with latest-frame-wins drop; `close()` resets the gate; module/class/method docstrings updated to describe the internal ack-gated pacing; `for_matrix`/`for_multizone`/`for_light` now pass `port=device.port`.

## Verification Evidence

```
uv run pytest tests/test_animation/test_flow.py -q
  -> 16 passed

uv run pytest tests/test_animation/ -q
  -> 185 passed (whole test_animation/ directory, including all emulator-marked tests)

uv run pytest tests/test_animation/ --cov=lifx.animation --cov-report=term-missing -q
  -> src/lifx/animation/__init__.py     100%
     src/lifx/animation/animator.py     100% (101 stmts, 20 branches, 0 missing)
     src/lifx/animation/flow.py         100% (42 stmts, 8 branches, 0 missing)
     src/lifx/animation/framebuffer.py  100%
     src/lifx/animation/orientation.py  100%
     src/lifx/animation/packets.py      100%

uv run --frozen pytest -q
  -> 2618 passed, 12 deselected, 7 warnings in 111.31s

uv run pyright
  -> 0 errors, 0 warnings, 0 notices

uv run ruff check .
  -> All checks passed!

git status --porcelain src/lifx/network/ src/lifx/devices/ src/lifx/effects/ src/lifx/const.py tests/
  -> (empty — scope guard satisfied, D4-05)

! grep -v '^\s*#' src/lifx/animation/animator.py | grep -qi 'no waiting'
  -> exit 0 (stale fire-and-forget docstring language fully removed)
```

## Decisions Made

- Constants (`ACK_INFLIGHT_LIMIT`, `ACK_EXPIRY_SECONDS`, `ACK_PKT_TYPE`) placed in `flow.py`, not `const.py`, per the research's D4-05 scoping rationale (animation-layer tuning values, not shared network configuration).
- Read constants via direct module-attribute lookup inside `AckGate` methods rather than binding them as method-parameter defaults, matching the project's runtime-read idiom (a test patches `time.monotonic` the same way elsewhere in this suite).
- `AckGate` confirmed never exported from `lifx.animation.__init__` — the existing `test_send_frame_has_no_flow_control_toggle` guard (already passing pre-plan) required no additional work.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Animator factories never passed the device's real port to the raw animation socket**
- **Found during:** Task 2, discovered while investigating a 100%-reproducible failure in `TestAnimatorFlowControlIntegration::test_acks_collected_on_healthy_emulator` and the two `test_animation_loop_simulation` integration tests
- **Issue:** `Animator.for_matrix`, `for_multizone`, and `for_light` all called `cls(ip, serial, framebuffer, packet_generator)` without a `port` argument, so the constructor's `port: int = LIFX_UDP_PORT` default (56700) was always used for the raw UDP socket — regardless of the actual port the connected `device` used. Debugged by adding a temporary manual poll script against the embedded emulator: after sending a Set64 with the ack flag correctly baked (confirmed via `TestAnimatorProbeBaking`), zero ack datagrams arrived even after 0.4s of polling. Traced to the emulator's session-scoped fixtures always binding to a random free port (never 56700), meaning every animation packet the raw socket sent was silently misdirected to an unrelated (or unbound) port — invisible before this phase because `send_frame` never checked for a reply.
- **Fix:** Added `port=device.port` to the `cls(...)` call in all three factory methods. `Device.port` (set in `devices/base.py.__init__`) already carries the correct connected port for every device type.
- **Files modified:** `src/lifx/animation/animator.py`
- **Verification:** All four previously-failing integration tests pass; full `tests/test_animation/` suite (185 tests) green; manual poll script (removed before commit) confirmed acks now arrive within a few ms of sending.
- **Committed in:** `24357e7` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** The port-routing bug pre-dates this phase entirely and was invisible under blind-fire behaviour (no verification that packets landed anywhere). It would also have silently broken production animation against any real device running on a non-standard port (e.g. behind NAT/port-forwarding) — Rule 1 auto-fix, no scope creep, and arguably a correctness fix this phase was uniquely positioned to surface.

## Issues Encountered

None beyond the port-routing deviation above, which was root-caused and fixed within Task 2's scope.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- ANIM-01 and ANIM-02 are closed for automated verification (deterministic emulator gating, 100% branch patch coverage, full suite green). ANIM-03 (Tiles hardware UAT) and ANIM-04 (Ceiling Capsule hardware UAT, probe-attachment validation) remain manual gates per plans 04-05/04-06/04-07 — CONTEXT.md already documents these as mandatory hardware-only steps the emulator cannot substitute for.
- The `probe_template_index` fallback seam (standard/multizone/light → index 0; large-tile → final CopyFrameBuffer) is ready for the ANIM-04 hardware UAT to confirm or flip via a one-line change.
- No blockers for plans 04-05/04-06/04-07.

---
*Phase: 04-animation-flow-control*
*Completed: 2026-07-17*

## Self-Check: PASSED

- FOUND: src/lifx/animation/flow.py
- FOUND: src/lifx/animation/animator.py
- FOUND: c3f18a8 (Task 1 commit)
- FOUND: 24357e7 (Task 2 commit)
