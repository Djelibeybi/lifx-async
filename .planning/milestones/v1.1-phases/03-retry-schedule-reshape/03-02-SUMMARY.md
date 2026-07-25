---
phase: 03-retry-schedule-reshape
plan: 02
subsystem: network
tags: [asyncio, connection, retry, retransmit, photons-schedule]

requires:
  - phase: 03-retry-schedule-reshape
    provides: Wave-0 RED branch-matrix suite (test_connection_retry.py) and rewritten TestRetryTimeoutBudget defining GREEN
provides:
  - REQUEST_RETRANSMIT_GAPS Photons-shaped schedule constant in const.py
  - Shared _transmit_and_listen() wall-deadline retransmit-while-listening engine in connection.py
  - Thin _request_stream_impl/_request_ack_stream_impl wrappers (unchanged mock-seam names/signatures)
  - ACK path on the same shared-queue correlation contract as GET (late-ACK acceptance)
affects: [03-03-retry-schedule-reshape, phase-4-animation-flow-control, phase-5-reliability-documentation]

tech-stack:
  added: []
  patterns:
    - "Runtime-read module-attribute patching (REQUEST_RETRANSMIT_GAPS, _STREAM_IDLE_TIMEOUT) — same idiom as Phase 2's DISCOVERY_REBROADCAST_GAPS, lets tests patch schedule/idle constants for deterministic fast timing"
    - "Single shared async-generator engine with two thin wrapper generators preserving distinct GET/ACK semantics (mock-seam names/signatures locked)"
    - "# pragma: no branch on a loop whose body always exits via return/raise, documented rather than distorting control flow to force an uncoverable branch"

key-files:
  created: []
  modified:
    - src/lifx/const.py
    - src/lifx/network/connection.py
    - tests/test_network/test_connection_retry.py

key-decisions:
  - "Unified both request paths into one _transmit_and_listen() engine (source allocation, shared queue, schedule, wall deadline, correlation-key lifecycle, response validation); GET/ACK wrappers keep only their distinct semantics (multi-response idle streaming vs single-ACK + StateUnhandled)"
  - "ACK path moved onto the shared-queue correlation contract used by GET — late ACKs to earlier retransmits now satisfy the request instead of being discarded (RETRY-04 mandated behaviour change)"
  - "Patched _STREAM_IDLE_TIMEOUT down in test_discovery_connection_accepts_any_target (03-01 RED test) to match its three sibling _drive()-based tests — it passed coincidentally under the old exponential per-attempt windowing (~0.29s) but genuinely needs the real 2.0s idle window under the correct engine; verified empirically against both implementations before touching it"
  - "Marked the ACK wrapper's async-for loop `# pragma: no branch` — its body always exits via return or a raised exception, so the loop's natural-exhaustion arc is structurally unreachable; confirmed the identical pattern already exists, unaddressed, in the untouched request_stream() SET/EchoRequest branches (out of this phase's scope per D3-06)"

patterns-established:
  - "Wall-deadline + retransmit-while-listening loop (deadline/idle/retransmit-due checks folded into one asyncio.wait_for call, no blind sleeps) — reusable shape for any future request-path scheduling work"

requirements-completed: [RETRY-01, RETRY-02, RETRY-03, RETRY-04]

coverage:
  - id: D1
    description: "REQUEST_RETRANSMIT_GAPS Photons-shaped schedule constant added to const.py, floors the first-attempt window at 0.2s"
    requirement: "RETRY-01"
    verification:
      - kind: unit
        ref: "tests/test_network/test_connection_retry.py::TestRetransmitSchedule (6 tests)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Shared _transmit_and_listen() engine: retransmit-while-listening, no blind sleeps between attempts"
    requirement: "RETRY-02"
    verification:
      - kind: unit
        ref: "tests/test_network/test_connection_retry.py::TestListenDuringBackoff (4 tests)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Single monotonic wall deadline honoured on both GET and ACK paths — failing requests complete at timeout, not timeout+overrun"
    requirement: "RETRY-03"
    verification:
      - kind: integration
        ref: "tests/test_network/test_concurrent_requests.py::TestRetryTimeoutBudget (3 tests, emulator drop-scenarios)"
        status: pass
    human_judgment: false
  - id: D4
    description: "Shared-queue correlation across all issued sequences on both GET and ACK paths — late replies accepted, duplicates silently discarded"
    requirement: "RETRY-04"
    verification:
      - kind: unit
        ref: "tests/test_network/test_connection_retry.py::TestCorrelationContract (8 tests)"
        status: pass
    human_judgment: false
  - id: D5
    description: "Existing callers (12+ mock-seam tests in test_connection.py, all StateUnhandled emulator tests) pass unmodified against the reshaped engine"
    verification:
      - kind: unit
        ref: "tests/test_network/test_connection.py (34 tests)"
        status: pass
    human_judgment: false
  - id: D6
    description: "100% branch-patch coverage on the new/changed connection.py ranges; full suite green with no regressions"
    verification:
      - kind: unit
        ref: "uv run pytest tests/test_network/ --cov-report=term-missing (connection.py: all missing lines/branches fall outside Task 1 edit ranges)"
        status: pass
      - kind: integration
        ref: "uv run --frozen pytest (2563 passed, 12 deselected)"
        status: pass
    human_judgment: false

duration: ~40min
completed: 2026-07-17
status: complete
---

# Phase 3 Plan 02: Retry Reshape GREEN Summary

**Reshaped both `DeviceConnection` request paths onto a single shared `_transmit_and_listen()` engine — one monotonic wall deadline, Photons-shaped escalating retransmits, retransmit-while-listening, and shared-queue correlation on both GET and ACK — turning all 20 Wave-0 tests green and closing RETRY-01 through RETRY-04.**

## Performance

- **Duration:** ~40 min
- **Started:** 2026-07-16T23:42:19+10:00 (prior commit)
- **Completed:** 2026-07-17T00:07:06+10:00
- **Tasks:** 2
- **Files modified:** 3 (2 source, 1 test)

## Accomplishments

- Added `REQUEST_RETRANSMIT_GAPS: Final[tuple[float, ...]] = (0.2, 0.3, 0.4, 0.5, 0.7, 0.9, 1.0, 2.0, 3.0, 4.0, 5.0)` to `src/lifx/const.py` — the exact Photons-shaped expansion raced in spike 002 (1/180 failures across all loss rates).
- Implemented `_transmit_and_listen()` in `src/lifx/network/connection.py`: a private async-generator engine owning source allocation, the shared response queue, the retransmit schedule (read from the module attribute at runtime so tests can patch it), the single wall deadline, correlation-key lifecycle, and the three response validations (serial/source/sequence-range) moved verbatim from the old GET path.
- Reduced `_request_stream_impl` and `_request_ack_stream_impl` to thin wrappers with unchanged names and signatures — the mock seam patched by 12+ tests in `test_connection.py` — delegating to the shared engine with `ack_required`/`res_required`/`timeout_noun` parameters. ACK-specific StateUnhandled handling stays in its wrapper (D3-06).
- Deleted `_calculate_retry_sleep_with_jitter`, `_RETRY_SLEEP_BASE`, the dead `_DEFAULT_IDLE_TIMEOUT` constant, `total_sleep_time` budget-exclusion bookkeeping, and the now-unused `import random`. Added `_STREAM_IDLE_TIMEOUT: float = 2.0` as a runtime-read module attribute replacing the old hardcoded local.
- Fixed two in-scope docstring defects: the class docstring's "exponential backoff and jitter" claim (now describes the wall-time budget with escalating retransmits), and `__init__`'s `timeout` default (was wrongly documented as 8.0; `DEFAULT_REQUEST_TIMEOUT` is 16.0) — both also gained precise documentation of the `max_retries` interaction rule (retransmit cap vs wall-time budget, whichever binds first).
- Moved the ACK path onto the same shared-queue correlation contract as GET: a late acknowledgement answering an earlier retransmit now satisfies the request instead of being silently discarded by the old per-attempt queue (RETRY-04's mandated ACK-path behaviour change).
- All 20 Wave-0 tests (17 in `test_connection_retry.py` + 3 rewritten `TestRetryTimeoutBudget` tests) pass, plus the entire 34-test mock-seam file (`test_connection.py`) unmodified.
- Branch-patch coverage audited clean: every missing line/branch in `connection.py`'s coverage report falls outside this plan's edited ranges (pre-existing gaps in `close()`, `send_packet()`, `_background_receiver()`, and the untouched `request_stream()` SET/EchoRequest branches).
- Full suite: 2563 passed, 12 deselected, ~112s — comparable to the Phase 2 baseline (~109s), no regressions, and failing-path tests now complete faster (at the wall deadline rather than overshooting it).

## Task Commits

1. **Task 1: Implement the shared transmit-and-listen engine (GREEN)** - `d2e299b` (feat)
2. **Task 2: Branch-coverage audit and full-suite regression** - `15148be` (test)

**Plan metadata:** committed alongside this summary.

## Files Created/Modified

- `src/lifx/const.py` - Added `REQUEST_RETRANSMIT_GAPS` Photons-shaped schedule constant.
- `src/lifx/network/connection.py` - New `_transmit_and_listen()` shared engine; `_request_stream_impl`/`_request_ack_stream_impl` reduced to thin wrappers; deleted jitter-sleep machinery, dead constants, and budget-exclusion bookkeeping; fixed two docstring defects; added `# pragma: no branch` on the ACK wrapper's structurally-unreachable loop-exhaustion arc.
- `tests/test_network/test_connection_retry.py` - Patched `_STREAM_IDLE_TIMEOUT` in `test_discovery_connection_accepts_any_target` to match its sibling tests (see Deviations); added `test_ack_wrapper_direct_call_completes_naturally` to close a branch-patch coverage gap on the ACK wrapper's own `return` statement.

## Decisions Made

- Single shared `_transmit_and_listen()` engine rather than duplicating the reshaped loop in both impls — resolves the cross-impl duplication CONTEXT flagged as a cleanup candidate in the same pass as the reshape (per CONTEXT's explicit "unify rather than duplicating the new schedule twice").
- `timeout_noun` parameter (`"response"` | `"acknowledgement"`) gives the engine one raise site for the final `LifxTimeoutError`, avoiding a wrapper-level catch-and-re-raise for no benefit (research Open Question 1, planner's-discretion branch taken as recommended).
- Sequence numbering stays `sequence = transmission count` (0, 1, 2, …), identical to today's `sequence = attempt`, so `len(correlation_keys)` remains the valid upper bound for the sequence-range check — no new wraparound handling needed at default schedule/timeout values.
- Kept the `# pragma: no cover` markers on the open-guard and `timeout is None` default lines exactly as they existed in both old impls (now consolidated to one occurrence in the shared engine).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Test defect discovered during execution] Patched `_STREAM_IDLE_TIMEOUT` in `test_discovery_connection_accepts_any_target`**
- **Found during:** Task 1 (initial GREEN run of the Wave-0 suite)
- **Issue:** This 03-01 RED test drives `_request_stream_impl` directly via a full, non-early-return consuming loop (`_drive()`), exactly like its three sibling tests in the same file (`test_no_retransmit_after_first_response`, `test_second_response_before_idle_extends_stream`, `test_deadline_return_after_yield_no_raise`) — but unlike those three, it did not patch `_STREAM_IDLE_TIMEOUT` down. Under the OLD exponential per-attempt windowing, the per-attempt timeout (~0.29s for `timeout=2.0, max_retries=2`) happened to truncate the stream well before the real 2.0s idle window ever mattered, so the test passed coincidentally in ~0.29s (documented in 03-01-SUMMARY.md as a coincidental pass). Under the correctly-implemented engine, idle streaming genuinely waits the real 2.0s window after the only response, which exceeds the test's own `asyncio.wait_for(task, timeout=1.0)` bound.
- **Fix:** Verified the root cause empirically by running the exact test scenario against both the pre-Task-1 code (measured ~0.29s) and the new engine (measured ~2.0s) via standalone scratch scripts before touching anything. Added `patch("lifx.network.connection._STREAM_IDLE_TIMEOUT", 0.3)` around the `_drive()` call, matching the exact idiom its three sibling tests already use. The test's assertion (`len(yields) == 1`, discovery-serial-skip behaviour) is unchanged — only the timing setup was adjusted for consistency with the file's own established pattern.
- **Files modified:** tests/test_network/test_connection_retry.py
- **Verification:** Full Wave-0 suite green (59/59 across the three targeted test files); this specific test passes in ~0.3s.
- **Committed in:** d2e299b (Task 1 commit)

**2. [Rule 3 - Blocking, branch-patch coverage] Added a narrow test + `# pragma: no branch` for the ACK wrapper's unreachable loop-exhaustion arc**
- **Found during:** Task 2 (branch-coverage audit)
- **Issue:** `--cov-branch` flagged `730->exit` and line `743` (the bare `return` immediately after `yield True`) as missing in `_request_ack_stream_impl`. Investigation showed: (a) the `return` line is only reached when a consumer resumes the generator a second time after the first yield — `conn.request()`'s own early-return pattern never does this, so a narrow test driving the wrapper directly with a full consuming loop was needed and added; (b) even with that test, the wrapper's `async for` loop can never reach its "natural exhaustion" arc (`->exit`) because the loop body always exits via an explicit `return` or a raised exception by design — this is structurally unreachable, not a real behavioural gap, and the identical pattern already exists unaddressed in the untouched `request_stream()` SET/EchoRequest branches (confirmed by comparing against the pre-Task-1 baseline, which had the same gap at its own equivalent line).
- **Fix:** Added `test_ack_wrapper_direct_call_completes_naturally` (drives `_request_ack_stream_impl` directly with a full non-early-return loop) to cover the `return` line. Marked the loop's `async for` statement `# pragma: no branch` with a comment explaining the unreachable arc, rather than distorting the control flow (e.g. adding a dead `else` branch) to force coverage of something that cannot occur — consistent with the research's explicit anti-pattern guidance against defensive clamps that trade a covered branch for an uncoverable one.
- **Files modified:** tests/test_network/test_connection_retry.py, src/lifx/network/connection.py
- **Verification:** `uv run pytest tests/test_network/ --cov-report=term-missing` shows connection.py's only remaining gaps are outside this plan's edited ranges.
- **Committed in:** 15148be (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (1 test-timing fix for consistency with an established in-file pattern, 1 coverage-gap closure with a documented pragma)
**Impact on plan:** Both fixes were narrowly scoped, verified empirically before being applied, and left every assertion's meaning intact. No scope creep — no production behaviour changed as a result of either fix.

## Issues Encountered

None beyond the two deviations above. `uv run ruff format .`, `uv run ruff check . --fix`, and `uv run pyright` were clean after every task commit.

## Branch Coverage Matrix Audit (B1-B16)

Audited `uv run pytest tests/test_network/ --cov-report=term-missing` against 03-RESEARCH.md's matrix:

| Rows | Outcome |
|------|---------|
| B1 (`timeout is None` pragma), B2 (`max_retries is None` both arms) | Covered — B2's False arm via `test_direct_impl_call_explicit_max_retries_zero` |
| B3 (initial `max_retries > 0` schedule-armed, both arms) | Covered — `test_timeout_behavior` (max_retries=0) and any retransmit test |
| B4 (wall-deadline compound: return-if-yielded / raise-if-not / false) | Covered — `test_deadline_return_after_yield_no_raise`, drop-all wall-time tests, all happy paths |
| B5 (idle-elapsed compound, all arms) | Covered — `test_no_retransmit_after_first_response`, `test_second_response_before_idle_extends_stream` |
| B6/B6a/B6b (retransmit-due compound, all arms) | Covered — `test_escalating_gaps_drive_retransmits`, `test_retransmit_cap_then_keeps_listening`, `test_response_between_retransmits_completes_immediately` |
| B7 (post-send cap, both arms) | Covered — `test_gap_exhaustion_repeats_final_gap` (repeat), `test_retransmit_cap_then_keeps_listening` (cap) |
| B8/B9 (wait-cap conditions) | Covered — mirrors B6/B5 tests |
| B10 (`TIMEOUT_ERRORS` continue, both arms) | Covered — quiet-slice tests and injected-response tests |
| B11 (discovery-serial compound, all arms) | Covered — `test_serial_mismatch_raises_protocol_error`, `test_discovery_connection_accepts_any_target`, emulator happy path |
| B12 (source mismatch) | Covered — `test_wrong_source_raises_protocol_error` |
| B13 (sequence-range, both arms) | Covered — `test_out_of_range_sequence_raises_protocol_error`, `test_late_reply_to_earlier_sequence_accepted` |
| B14 (StateUnhandled, both arms) | Covered — existing emulator switch tests (unchanged) |
| B15 (final raise reached / not-reached) | Covered — same tests as B4 |
| B16 (gap-iterator exhaustion) | Covered — `test_gap_exhaustion_repeats_final_gap` |

No partials remain within Task 1's edited ranges. The one additional gap found (ACK wrapper's structurally-unreachable loop-exhaustion arc, not in the B1-B16 matrix since the matrix predates this specific coverage-tooling artifact) is documented above under Deviations and resolved via `# pragma: no branch`.

## Phase 5 Handoff Notes (docs-rot, out of this phase's scope per D3-06)

- `docs/api/network.md:132` still reads "Retry logic with exponential backoff and jitter" — needs updating to describe the wall-time budget with Photons-shaped escalating retransmits.
- `docs/architecture/overview.md:136` still reads "**Retry Logic**: Automatic retry with exponential backoff" — same update needed.
- Project `CLAUDE.md:244` still says "Requests on a single connection are serialized via `_request_lock` (asyncio.Lock)" — no such lock exists in `connection.py` (pre-existing housekeeping item, unrelated to this phase's changes, flagged for a future documentation pass).

## Full-Suite Regression Check

`uv run --frozen pytest`: **2563 passed, 12 deselected, ~112s** (vs the ~109s Phase 2 baseline — comparable, no regression). `git status --porcelain` shows only this plan's `files_modified` touched (`src/lifx/const.py`, `src/lifx/network/connection.py`, `tests/test_network/test_connection_retry.py`); the scope guard (`src/lifx/network/discovery.py`, `src/lifx/network/mdns/`, `src/lifx/animation/`) is clean.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- RETRY-01 through RETRY-04 are closed. Phase 3's remaining plan (03-03) is the optional zero-loss packets/trial hardware measurement against the gen4 downlight (192.168.18.95) — not a CI gate, can run independently or be deferred.
- The shared `_transmit_and_listen()` engine and `REQUEST_RETRANSMIT_GAPS`/`_STREAM_IDLE_TIMEOUT` module attributes are stable, tested seams ready for 03-03's harness reuse (the `_send_spy`/`_header`/`_wait_for_keys` helpers from 03-01 remain available).
- Phase 4 (Animation Flow Control) and Phase 5 (Reliability Documentation, which must pick up the two docs-rot items noted above plus this phase's own retry-schedule behaviour) are unblocked to proceed independently.
- No blockers.

---
*Phase: 03-retry-schedule-reshape*
*Completed: 2026-07-17*

## Self-Check: PASSED

- FOUND: src/lifx/const.py (REQUEST_RETRANSMIT_GAPS present)
- FOUND: src/lifx/network/connection.py (_transmit_and_listen present)
- FOUND: tests/test_network/test_connection_retry.py
- FOUND: commit d2e299b (Task 1)
- FOUND: commit 15148be (Task 2)
