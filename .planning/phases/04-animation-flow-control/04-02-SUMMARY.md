---
phase: 04-animation-flow-control
plan: 02
subsystem: testing
tags: [pytest, animator, ack-gating, flow-control, emulator, pyright]

# Dependency graph
requires:
  - phase: 04-animation-flow-control
    provides: "Plan 04-01's RED row-aligned chunking / probe_template_index / header-flag-constant suite in test_packets.py (sibling wave-0 plan, same phase)"
provides:
  - RED branch-matrix suite pinning the AckGate facility contract (constants, track/sweep/reset/gated/outstanding_count, untrusted-datagram validation, expiry) in a new test_flow.py
  - RED suite pinning the animator's gate-before-framebuffer, probe-baking, additive-stats, and no-toggle contract in test_animator.py
  - Shared mock_udp_socket fixture + make_ack_datagram helper unblocking all future sweep-aware socket tests
  - Deterministic emulator gating tests (drop_packets scenarios + a genuine 13x26 large-tile device fixture)
affects: [04-03-fix-packets-geometry, 04-04-implement-ackgate-and-animator-gating]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "mock_udp_socket fixture: patches socket.socket with a deque-backed recvfrom_into side_effect (BlockingIOError when empty), replacing bare MagicMock in every animator socket test"
    - "make_ack_datagram(source, sequence, pkt_type=45, size=36) helper crafts wire-accurate (or deliberately runt/wrong-type/wrong-source) 36-byte Acknowledgement datagrams for AckGate sweep tests"
    - "getattr(obj, 'name', sentinel) for RED tests targeting not-yet-existing attributes (AnimatorStats.gated/acks_outstanding, PacketGenerator.probe_template_index) — reused from 04-01's deviation, keeps pyright clean while pytest still fails on the assertion"
    - "Emulator tile-geometry override: lifx_emulator.factories.create_device(tile_width=, tile_height=) does not honour explicit dims for products with fixed spec geometry; patch the per-tile tile_devices dict records directly after construction instead (drives StateDeviceChain/Set64/CopyFrameBuffer correctly)"

key-files:
  created:
    - tests/test_animation/test_flow.py
  modified:
    - tests/test_animation/conftest.py
    - tests/test_animation/test_animator.py

key-decisions:
  - "Worked around a lifx-emulator-core 3.6.3 limitation: create_device(product_id=201, tile_width=13, tile_height=26) silently ignores the tile_width/tile_height kwargs because DeviceBuilder._apply_product_defaults() unconditionally overwrites them from the product's spec registry (get_tile_dimensions(201) == (16, 8)). Added a _force_tile_dimensions() helper in conftest.py that rewrites the per-tile tile_devices[i] dict records (width/height/colors) after construction — StateDeviceChain, Tile.Set64, and Tile.CopyFrameBuffer are all driven from those records, so the emulated device behaves as a genuine 13x26 large-tile device with no protocol-level shortcut."
  - "Test 18 (13x26 framebuffer path) and the large-tile probe-baking test assert the future 8-template/probe-index-7 contract literally (not just 'final template'), matching the geometry plan 04-03 must produce, and so is doubly RED today (7 templates, no baking) rather than coincidentally passing."

patterns-established:
  - "Sweep-compatible mocked-socket pattern: any future test needing a mocked UDP socket for the animator should consume mock_udp_socket rather than patching socket.socket inline, so recvfrom_into behaves correctly once AckGate.sweep exists."

requirements-completed: [ANIM-01, ANIM-02]

coverage:
  - id: D1
    description: "RED branch-matrix suite pins the complete AckGate contract: spike-measured constants (ACK_PKT_TYPE=45, ACK_INFLIGHT_LIMIT=2, ACK_EXPIRY_SECONDS=1.0), track/gated/outstanding_count/reset state transitions, wrap-collision overwrite, the untrusted-datagram sweep validation matrix (empty/matching/multiple/untracked/runt/wrong-type/wrong-source/OSError), and explicit-now expiry pruning"
    requirement: "ANIM-01"
    verification:
      - kind: unit
        ref: "tests/test_animation/test_flow.py (16 tests, all RED via collection ImportError — lifx.animation.flow does not exist yet)"
        status: pass
    human_judgment: false
  - id: D2
    description: "RED suite pins the animator's gate-before-framebuffer ordering, latest-frame-wins drop (no packets sent, no sequence consumed), ack-sweep reopening (correct source only), expiry reopening, close()-resets-gate, and additive AnimatorStats.gated/acks_outstanding observability"
    requirement: "ANIM-01"
    verification:
      - kind: unit
        ref: "tests/test_animation/test_animator.py::TestAnimatorGating + TestAnimatorStatsFlowFields (11 tests, 9 RED / 2 invariance-pass: length-check precedence, no-toggle guard)"
        status: pass
    human_judgment: false
  - id: D3
    description: "RED suite pins the ack-required probe flag baked ONCE at Animator construction on the correct template (first packet for standard/multizone/light; final CopyFrameBuffer, index 7, for 13x26 large-tile mode), and that the internal AckGate facility is never exported (D4-02 no-toggle invariant)"
    requirement: "ANIM-02"
    verification:
      - kind: unit
        ref: "tests/test_animation/test_animator.py::TestAnimatorProbeBaking (3 tests, RED)"
        status: pass
    human_judgment: false
  - id: D4
    description: "Deterministic end-to-end gating pinned against the emulator: drop_packets{45:1.0} scenario reaches the gate limit deterministically, a single 1.05s sleep reopens the gate past ACK_EXPIRY_SECONDS, a healthy emulator collects acks every frame, and a genuine 13x26 large-tile emulated device (product 201, dims patched post-construction) exercises the row-aligned + CopyFB probe path end-to-end"
    requirement: "ANIM-01"
    verification:
      - kind: integration
        ref: "tests/test_animation/test_animator.py::TestAnimatorFlowControlIntegration (4 tests, RED, @pytest.mark.emulator) + 3 updated existing loop/integration tests (RED on the new gated assertion)"
        status: pass
    human_judgment: false

# Metrics
duration: 13min
completed: 2026-07-17
status: complete
---

# Phase 4 Plan 02: RED Suite for Animator Flow Control Summary

**RED test suite pinning the AckGate facility contract (test_flow.py) and the animator's gate-before-frame/probe-baking/additive-stats contract (test_animator.py), including deterministic emulator gating against a genuine 13x26 large-tile device, that plan 04-04 must turn GREEN.**

## Performance

- **Duration:** ~13 min
- **Started:** 2026-07-17T01:26:00+10:00 (approx)
- **Completed:** 2026-07-17T01:39:20+10:00
- **Tasks:** 3 completed
- **Files modified:** 3 (`tests/test_animation/conftest.py`, `tests/test_animation/test_animator.py`, new `tests/test_animation/test_flow.py`)

## Accomplishments
- Added a shared `mock_udp_socket` fixture (deque-backed `recvfrom_into` side_effect defaulting to `BlockingIOError`) and `make_ack_datagram()` helper to `conftest.py`, then migrated the six existing bare-`MagicMock`-patched animator socket tests onto it — behaviour-neutral, whole suite stayed green.
- Added a session-scoped `large_tile_matrix_device` fixture (emulated LIFX Ceiling 13x26, product 201) — required a workaround for a `lifx-emulator-core` limitation where explicit `tile_width`/`tile_height` kwargs are silently ignored for products with fixed spec geometry.
- Created `tests/test_animation/test_flow.py`: a 16-test RED branch matrix pinning the complete `AckGate` API (constants, state transitions, untrusted-datagram sweep validation, expiry) — fails at collection since `lifx.animation.flow` doesn't exist yet.
- Extended `tests/test_animation/test_animator.py` with 18 new tests across `TestAnimatorStatsFlowFields`, `TestAnimatorProbeBaking`, `TestAnimatorGating`, and `TestAnimatorFlowControlIntegration`, and updated 3 existing emulator loop/integration tests to assert `stats.gated is False` — pinning gate-before-framebuffer ordering, probe baking, sequence-consumption-on-drop, ack reopening, expiry, `close()` reset, and deterministic end-to-end gating via `drop_packets` scenarios.

## Task Commits

Each task was committed atomically:

1. **Task 1: Shared fixtures — mock UDP socket + 13x26 emulated device (stays green)** - `e04e57f` (test)
2. **Task 2: RED — AckGate unit branch matrix (test_flow.py)** - `4d3e45f` (test)
3. **Task 3: RED — animator gating, probe baking, additive stats + deterministic emulator gating** - `dd8f0de` (test)

**Plan metadata:** committed alongside this SUMMARY.

## Files Created/Modified
- `tests/test_animation/conftest.py` - Added `make_ack_datagram()`, `MockUdpSocket` + `mock_udp_socket` fixture, `_force_tile_dimensions()` helper, and `large_tile_matrix_device` fixture (emulated 13x26 Ceiling).
- `tests/test_animation/test_animator.py` - Migrated 6 tests off inline `patch.object(socket, "socket")` onto `mock_udp_socket`; added `TestAnimatorStatsFlowFields`, `TestAnimatorProbeBaking`, `TestAnimatorGating`, `TestAnimatorFlowControlIntegration`; updated 3 existing emulator loop/integration tests to assert `gated is False`.
- `tests/test_animation/test_flow.py` - New file: `TestAckGateConstants`, `TestAckGateState`, `TestAckGateSweep`, `TestAckGateExpiry` (16 tests total).

## RED Evidence Table

| File | Class | Tests | Status today | Reason |
|---|---|---|---|---|
| test_flow.py | (whole file) | 16 | RED (collection error) | `lifx.animation.flow` module doesn't exist |
| test_animator.py | TestAnimatorStatsFlowFields | 1 | RED | `AnimatorStats` has no `gated`/`acks_outstanding` fields |
| test_animator.py | TestAnimatorProbeBaking | 3 | RED | Nothing bakes the ack-required flag at construction yet; `probe_template_index` doesn't exist |
| test_animator.py | TestAnimatorGating | 8 | RED | No `AckGate`, no gating in `send_frame` |
| test_animator.py | TestAnimatorGating::test_wrong_length_raises_even_when_gated | 1 | PASS (invariance) | `framebuffer.apply` already raises before any gate exists; must keep passing once 04-04 reorders |
| test_animator.py | TestAnimatorGating::test_send_frame_has_no_flow_control_toggle | 1 | PASS (invariance) | D4-02 no-toggle guard already holds (no gate param, no `AckGate` export) |
| test_animator.py | TestAnimatorForMatrixIntegration::test_send_frame_sends_packets | 1 | RED | `stats.gated` missing |
| test_animator.py | TestAnimatorForMatrixIntegration::test_animation_loop_simulation | 1 | RED | `stats.gated` missing |
| test_animator.py | TestAnimatorForMultizoneIntegration::test_animation_loop_simulation | 1 | RED | `stats.gated` missing |
| test_animator.py | TestAnimatorFlowControlIntegration | 4 | RED | No gating, no 8-template 13x26 chunking, no `acks_outstanding` |

**Totals:** 37 new/modified tests across both files — 35 RED, 2 invariance-pass (length-check precedence, no-toggle guard).

## Verification Run

```
uv run pytest tests/test_animation/test_flow.py -q
  -> ModuleNotFoundError: No module named 'lifx.animation.flow' — EXIT 2 (collection error, isolated to this file)

uv run pytest tests/test_animation/test_packets.py tests/test_animation/test_framebuffer.py tests/test_animation/test_orientation.py -q -k "not RowAlignedChunking and not ProbeTemplateIndex and not HeaderFlagConstants"
  -> 103 passed, 21 deselected — EXIT 0 (test_flow.py's RED does not disturb other files)

uv run pytest tests/test_animation/test_animator.py -q -k "FlowFields or ProbeBaking or Gating"
  -> 13 failed, 2 passed, 30 deselected — EXIT 1 (assertion failures, not collection errors)

uv run pytest tests/test_animation/test_animator.py -q -m emulator -k "FlowControlIntegration or loop_simulation"
  -> 6 failed, 39 deselected — EXIT 1 (all fail on the new gated-field assertions)

uv run pytest tests/test_animation/test_animator.py -q
  -> 19 failed, 26 passed — EXIT 1 (whole-file totals: 27 pre-existing + 18 new = 45)

uv run pytest tests/test_animation/ -q --ignore=tests/test_animation/test_flow.py
  -> 36 failed, 133 passed — EXIT 1 (17 pre-existing RED from 04-01's test_packets.py + 19 from test_animator.py)

uv run ruff format tests/test_animation/ --check  -> 7 files already formatted
uv run ruff check tests/test_animation/           -> All checks passed!
uv run pyright tests/test_animation/conftest.py tests/test_animation/test_animator.py
  -> 0 errors, 0 warnings
```

## Decisions Made
- **Emulator tile-geometry workaround:** `lifx_emulator.factories.create_device(product_id=201, tile_width=13, tile_height=26, ...)` was specified in the plan, but the installed `lifx-emulator-core` 3.6.3 ignores those kwargs for any product whose spec registry already defines fixed tile dims — `DeviceBuilder._apply_product_defaults()` unconditionally overwrites `tile_width`/`tile_height` from `get_tile_dimensions(201)`, which returns `(16, 8)`. Verified by direct inspection of the installed package (`factories/builder.py:275-292`) and confirmed empirically (the fixture as originally written produced a 128-pixel device, not 338). Added `_force_tile_dimensions()` in `conftest.py`, which rewrites the per-tile `tile_devices[i]` dict records (`width`, `height`, `colors`) after construction — `StateDeviceChain`, `Tile.Set64`, and `Tile.CopyFrameBuffer` handlers all read tile geometry from those records (verified via `handlers/tile_handlers.py`), so the emulated device now genuinely reports and behaves as 13x26 (338 pixels) with no protocol-level shortcut. Re-verified: `animator.pixel_count == 338` now passes; only the packet-count assertion (`packets_sent == 8`, pending 04-03's chunking fix) remains RED.
- Pinned the large-tile probe-baking and 13x26-framebuffer-path tests to the literal future geometry (8 templates, `probe_template_index == 7`) rather than a relative "final template" check alone, so the suite doubly fails today (wrong template count AND no baking) and precisely matches what 04-03 + 04-04 must jointly produce.
- Reused the `getattr(obj, "attr", sentinel)` RED pattern from 04-01's deviation for every not-yet-existing attribute access (`AnimatorStats.gated`/`acks_outstanding`, `PacketGenerator.probe_template_index`), keeping `uv run pyright` clean while pytest still fails on the assertion.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Patched emulated device tile geometry post-construction instead of via `create_device` kwargs**
- **Found during:** Task 1 (large_tile_matrix_device fixture), confirmed during Task 3 verification
- **Issue:** The plan specified `create_device(product_id=201, tile_width=13, tile_height=26, scenario_manager=scenario_manager)`. Running the resulting fixture showed `animator.pixel_count == 128`, not the expected 338 — the installed `lifx-emulator-core` silently discards the `tile_width`/`tile_height` kwargs for products with fixed spec-registry geometry.
- **Fix:** Added `_force_tile_dimensions(device, width, height)` in `tests/test_animation/conftest.py`, which rewrites `device.state.tile_width`/`tile_height` and each `tile_devices[i]` dict's `width`/`height`/`colors` after `create_device()` returns, before `server.add_device()`. Verified against `handlers/tile_handlers.py` that `StateDeviceChain`, `Set64`, and `CopyFrameBuffer` all read geometry from these per-tile records, so the patched device is protocol-faithful.
- **Files modified:** `tests/test_animation/conftest.py`
- **Verification:** `animator.pixel_count == 338` now passes for the fixture-backed animator; the emulator produces a genuine 13x26 (338-pixel) device.
- **Committed in:** `e04e57f` (Task 1 commit) and `dd8f0de` (Task 3, verification confirmed)

---

**Total deviations:** 1 auto-fixed (1 blocking — environment/tooling limitation in a third-party dev dependency)
**Impact on plan:** Purely a test-infrastructure workaround; no change to what contract is pinned or which tests are RED vs. invariance. No scope creep. Plan 04-03/04-04 authors should be aware `create_device`'s tile-dimension kwargs cannot be trusted for fixed-spec products going forward.

## Issues Encountered
None beyond the emulator-geometry deviation above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Plan 04-03 has an exact GREEN target from 04-01 (row-aligned 13x26 chunking + `probe_template_index` + `FLAGS_OFFSET`/`ACK_REQUIRED_FLAG` constants in `packets.py`).
- Plan 04-04 has an exact GREEN target from this plan: create `src/lifx/animation/flow.py` (`AckGate` + constants) to satisfy `test_flow.py`, then wire gating/probe-baking/additive-stats into `animator.py` to satisfy `test_animator.py`'s new and updated tests — without editing any test in either file.
- The `large_tile_matrix_device` fixture and its `_force_tile_dimensions()` workaround are available to 04-03/04-04 for any further 13x26-specific test needs.
- No blockers for 04-03 or 04-04.

---
*Phase: 04-animation-flow-control*
*Completed: 2026-07-17*

## Self-Check: PASSED
