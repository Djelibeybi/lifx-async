---
phase: 03-retry-schedule-reshape
plan: 01
subsystem: testing
tags: [asyncio, pytest, retry, connection, network]

requires:
  - phase: 02-discovery-rebroadcast
    provides: proven runtime-constant-patching test idiom and escalating-gap schedule pattern reused here
provides:
  - Wave-0 RED test suite for the retry reshape (RETRY-01/02/04 branch matrix)
  - Rewritten TestRetryTimeoutBudget encoding the RETRY-03 wall-time contract
  - Reusable send-spy / header-factory / bounded-key-wait test helpers for plan 03-02/03-03
affects: [03-02-retry-schedule-reshape, 03-03-retry-schedule-reshape]

tech-stack:
  added: []
  patterns:
    - "Runtime-read module-attribute patching (REQUEST_RETRANSMIT_GAPS, _STREAM_IDLE_TIMEOUT) mirrors Phase 2's DISCOVERY_REBROADCAST_GAPS idiom for fast deterministic schedule tests"
    - "Deterministic response injection via put_nowait() on the real queue grabbed from conn._pending_requests, never mocking wait_for"
    - "Bounded poll helper (_wait_for_keys) instead of unbounded spin when waiting for correlation keys to register"

key-files:
  created:
    - tests/test_network/test_connection_retry.py
  modified:
    - tests/test_network/test_concurrent_requests.py

key-decisions:
  - "max_retries=5 (not the research sketch's 3) in the rewritten wall-time test, so the old code's 'after 6 attempts' message is a deterministic RED independent of jitter timing"
  - "test_retry_timeout_calculation_consistency's new upper bounds are acknowledged probabilistic (jitter sum can land under 0.3s) per 03-RESEARCH.md; observed as a coincidental pass in this environment, documented rather than forced"

patterns-established:
  - "Send-spy factory wraps the real bound send_packet and records monotonic() timestamps before delegating -- reused pattern for plan 03-02/03-03 harness reporting"

requirements-completed: [RETRY-01, RETRY-02, RETRY-03, RETRY-04]

duration: ~10min
completed: 2026-07-16
status: complete
---

# Phase 3 Plan 01: Retry Reshape RED Suite Summary

**17-test branch-matrix RED suite in test_connection_retry.py plus a rewritten TestRetryTimeoutBudget, both confirmed RED against the current exponential/jitter retry implementation with the exact fail/pass breakdown 03-RESEARCH.md predicted.**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-07-16T23:27:59+10:00 (prior commit)
- **Completed:** 2026-07-16T23:37:35+10:00
- **Tasks:** 2
- **Files modified:** 2 (1 created, 1 modified)

## Accomplishments

- New `tests/test_network/test_connection_retry.py` (661 lines) with 17 tests across `TestRetransmitSchedule` (6), `TestListenDuringBackoff` (4), and `TestCorrelationContract` (7), covering branch-matrix rows B2-B13, B15-B16 from 03-RESEARCH.md.
- Three reusable module-level test helpers (`_send_spy`, `_header`, `_wait_for_keys`) that plan 03-02/03-03 can reuse for GREEN verification and harness reporting.
- `TestRetryTimeoutBudget` in `test_concurrent_requests.py` rewritten to assert the RETRY-03 wall-time contract (elapsed within `[timeout, timeout + 0.3)`), replacing the old sleep-exclusion assertions that encoded the exact defect D3-03 removes.
- Confirmed RED at this commit: 11/20 total tests across both files fail (10 in the new file + 1 in the rewrite), all failing for the reasons 03-RESEARCH.md anticipated (module attributes not yet existing, or old exponential-scheme timing/message mismatches) -- no assertion weakened, nothing marked `xfail`.
- Full suite (`uv run --frozen pytest`) run once at the end: 2551 passed, 11 failed (exactly the new/rewritten RED tests), 12 deselected -- zero regressions elsewhere.

## Task Commits

1. **Task 1: Write the RED retry branch-matrix tests (test_connection_retry.py)** - `25aa1f2` (test)
2. **Task 2: Rewrite TestRetryTimeoutBudget to the wall-time contract (RED)** - `b1628e7` (test)

**Plan metadata:** committed alongside this summary.

## Files Created/Modified

- `tests/test_network/test_connection_retry.py` - New 17-test branch-matrix suite (RETRY-01/02/04) plus module-level `_send_spy`/`_header`/`_wait_for_keys` helpers.
- `tests/test_network/test_concurrent_requests.py` - `TestRetryTimeoutBudget` class rewritten (docstring + 3 tests); every other class in the file untouched (confirmed via `git diff --stat`, 35 insertions / 76 deletions, all within the one class).

## Per-Test RED / Coincidental-Pass Breakdown

### `tests/test_network/test_connection_retry.py` (17 tests, 10 fail / 7 pass)

| Test | Class | Result | Reason |
|------|-------|--------|--------|
| `test_healthy_network_single_transmission` | TestRetransmitSchedule | **PASS (coincidental)** | Emulator answers well inside the old ~31ms first window; 1 send either way |
| `test_no_retransmit_before_first_gap_floor` | TestRetransmitSchedule | **FAIL (behavioural)** | Old exponential/jitter scheme fires 3 sends within 0.15s (`assert 3 == 1`) instead of 1 |
| `test_escalating_gaps_drive_retransmits` | TestRetransmitSchedule | **FAIL (AttributeError)** | `REQUEST_RETRANSMIT_GAPS` does not exist on `lifx.network.connection` yet |
| `test_retransmit_cap_then_keeps_listening` | TestRetransmitSchedule | **FAIL (AttributeError)** | Same -- patches `REQUEST_RETRANSMIT_GAPS` |
| `test_gap_exhaustion_repeats_final_gap` | TestRetransmitSchedule | **FAIL (AttributeError)** | Same -- patches `REQUEST_RETRANSMIT_GAPS` |
| `test_direct_impl_call_explicit_max_retries_zero` | TestRetransmitSchedule | **PASS (coincidental)** | `max_retries=0` single-shot semantics already correct in old code |
| `test_response_between_retransmits_completes_immediately` | TestListenDuringBackoff | **FAIL (AttributeError)** | Patches `REQUEST_RETRANSMIT_GAPS` |
| `test_no_retransmit_after_first_response` | TestListenDuringBackoff | **FAIL (AttributeError)** | Patches `REQUEST_RETRANSMIT_GAPS` and `_STREAM_IDLE_TIMEOUT` (neither exists) |
| `test_second_response_before_idle_extends_stream` | TestListenDuringBackoff | **FAIL (AttributeError)** | Patches `_STREAM_IDLE_TIMEOUT` (does not exist -- old code has a local `idle_timeout = 2.0`, not a module attribute) |
| `test_deadline_return_after_yield_no_raise` | TestListenDuringBackoff | **FAIL (AttributeError)** | Patches `_STREAM_IDLE_TIMEOUT` |
| `test_late_reply_to_earlier_sequence_accepted` | TestCorrelationContract | **FAIL (AttributeError)** | Patches `REQUEST_RETRANSMIT_GAPS` |
| `test_late_ack_to_earlier_sequence_accepted` | TestCorrelationContract | **FAIL (AttributeError)** | Patches `REQUEST_RETRANSMIT_GAPS`; also exercises the ACK-path per-attempt-queue defect (today's per-attempt cleanup means 2 keys are never simultaneously registered on the ACK path -- would time out in `_wait_for_keys` even without the AttributeError) |
| `test_wrong_source_raises_protocol_error` | TestCorrelationContract | **PASS (coincidental)** | Source-mismatch validation already exists and is unchanged by the reshape |
| `test_out_of_range_sequence_raises_protocol_error` | TestCorrelationContract | **PASS (coincidental)** | Sequence-range validation already exists |
| `test_serial_mismatch_raises_protocol_error` | TestCorrelationContract | **PASS (coincidental)** | Serial validation already exists |
| `test_discovery_connection_accepts_any_target` | TestCorrelationContract | **PASS (coincidental)** | Discovery-connection serial-skip already exists |
| `test_duplicate_response_discarded_silently` | TestCorrelationContract | **PASS (coincidental)** | First-wins consumption + full key cleanup on generator close already exists |

**Totals:** 7 pass (coincidental), 10 fail (9 AttributeError on not-yet-existing module attributes, 1 deterministic behavioural failure on send count).

### `tests/test_network/test_concurrent_requests.py::TestRetryTimeoutBudget` (3 tests, 1 fail / 2 pass)

| Test | Result | Reason |
|------|--------|--------|
| `test_wall_time_budget_honoured_under_total_loss` | **FAIL (deterministic-ish)** | Old code overruns the wall budget via budget-excluded jitter sleeps; observed elapsed ~2.55s against the asserted `< 2.3s` upper bound, confirmed failing across 3 repeated runs. The message assertion (`"after 5 attempts"`) would also fail independently (old code reports `"after 6 attempts"` = `max_retries + 1`), but the elapsed assertion is evaluated first in this test and is what surfaces |
| `test_retry_timeout_calculation_consistency` | **PASS (probabilistic, documented)** | 03-RESEARCH.md explicitly flags this test's new upper bounds (`elapsed < timeout + 0.3`) as probabilistic -- the max possible jitter sum (0.1 + 0.2 = 0.3s) sits exactly at the boundary and a continuous random draw essentially never hits it. Observed passing across 3 repeated runs in this environment; this is the documented, acceptable outcome, not a test defect |
| `test_retry_all_attempts_get_fair_timeout` | **PASS (expected)** | Message arithmetic (`"after 3 attempts"`) is unchanged between the old exponential scheme and the new schedule for `timeout=2.0, max_retries=2` -- this test was expected to keep passing per 03-RESEARCH.md |

**Totals:** 2 pass (1 expected-unchanged, 1 probabilistic-but-documented), 1 fail (deterministic overrun of the wall-time upper bound).

## Full-Suite Regression Check

`uv run --frozen pytest` (no `-k`/`-x` filtering): **2551 passed, 11 failed, 12 deselected**. The 11 failures are exactly the 10 new-file RED tests plus the 1 rewritten wall-time test enumerated above -- no other test in the 2500+ test suite regressed. `git status --porcelain tests/` shows only the two files in this plan's `files_modified` touched.

## Decisions Made

- Used `max_retries=5` in the rewritten wall-time test rather than the research sketch's `max_retries=3`, per the plan's explicit instruction, so the message assertion is a deterministic RED (`"after 5 attempts"` vs. old code's `"after 6 attempts"`) independent of jitter randomness.
- Left `test_retry_timeout_calculation_consistency`'s upper-bound assertions in place even though they pass coincidentally at this commit -- 03-RESEARCH.md documents this as an accepted probabilistic outcome (jitter can, in principle, sum under 0.3s), and the plan's Task 2 action explicitly mandates adding these bounds regardless of RED/pass status at this commit.
- Grabbed the lowest-sequence key (`min(conn._pending_requests, key=lambda k: k[1])`) rather than assuming dict insertion order for the two late-reply tests, since dict key order is an implementation detail not part of the correlation contract being tested.

## Deviations from Plan

None - plan executed exactly as written. All 17 branch-matrix tests and the 3 rewritten `TestRetryTimeoutBudget` tests match the plan's `<behavior>` specification precisely, and the observed RED/pass breakdown matches the plan's `<action>` predictions test-for-test.

## Issues Encountered

None. `uv run ruff format`, `uv run ruff check --fix`, and `uv run pyright` were clean on both files at every commit (pyright's configured `include = ["src"]` means tests aren't part of the enforced pyright surface, but both files were written to the same strict-typing standard as existing test files and reported 0 errors when checked explicitly).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 03-02 has a fully-specified GREEN target: implement `REQUEST_RETRANSMIT_GAPS` and `_STREAM_IDLE_TIMEOUT` as runtime-read module attributes of `lifx.network.connection`, plus the shared `_transmit_and_listen()`-style engine, and all 20 tests across both files should flip to green without weakening any assertion here.
- The `_send_spy`, `_header`, and `_wait_for_keys` helpers in `test_connection_retry.py` are ready for reuse by plan 03-03's harness/reporting work.
- No blockers. The ACK-path late-reply test (`test_late_ack_to_earlier_sequence_accepted`) surfaces a real behavioural gap in the current per-attempt-queue implementation (keys are never simultaneously registered), which 03-02's shared-queue engine is specifically designed to close.

---
*Phase: 03-retry-schedule-reshape*
*Completed: 2026-07-16*

## Self-Check: PASSED

- FOUND: tests/test_network/test_connection_retry.py
- FOUND: tests/test_network/test_concurrent_requests.py
- FOUND: commit 25aa1f2 (Task 1)
- FOUND: commit b1628e7 (Task 2)
