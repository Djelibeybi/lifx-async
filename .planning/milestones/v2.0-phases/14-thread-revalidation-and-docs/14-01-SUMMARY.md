---
phase: 14-thread-revalidation-and-docs
plan: 01
subsystem: network
tags: [asyncio, request-observability, jsonl, privacy-safe-telemetry, thread]

# Dependency graph
requires:
  - phase: 13-merged-discovery
    provides: privacy-safe append-only measurement patterns (scripts/measure_merged_discovery.py precedent, value-suppressed observation dataclasses)
provides:
  - A private request-observer seam on DeviceConnection._transmit_and_listen(), selected once per thin wrapper and propagated explicitly (never read from ambient state inside the retry loop)
  - Seven bounded, identity-free observation categories (logical_start, sent, accepted, timeout, send_error, cancelled, cleanup) on a metadata-only time.monotonic_ns() clock that never feeds scheduling
  - scripts/measurement_support.py owning the _RequestObservation/_RequestObservationSink/_capture_request_observations() primitives, independent of the tests/ tree
  - scripts/thread_revalidation.py owning validate/append/reload/derive primitives for a closed-schema, privacy-safe request-event JSONL journal, plus trace_request() driving one real production request end to end
  - 14-COVERAGE-BASE.txt freezing the pre-implementation HEAD for later changed-line/branch coverage gates
affects: [14-02-PLAN, 14-03-PLAN, 14-04-PLAN]

# Actuals (#2632)
actuals:
  tokens: 16076
  tasks: 2
  commits: 3

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Private observer seam: a task-attribute selector (_current_request_observer()) is read ONCE by each thin request wrapper and passed explicitly into the shared retry engine as a keyword-only parameter, mirroring the existing discovery-observer pattern in network/discovery/udp.py"
    - "Observer-only time.monotonic_ns() metadata clock kept fully separate from the existing time.monotonic() float scheduling clock"
    - "accepted_ns is the queue-dequeue timestamp itself, sampled before validation, so it deliberately includes receiver-queueing/wake latency but excludes validation work"
    - "Closed-schema JSONL validation (exact key-set match, not a forbidden-value denylist) for privacy-safe append-only journals"

key-files:
  created:
    - scripts/measurement_support.py
    - scripts/thread_revalidation.py
    - tests/test_scripts/test_thread_revalidation.py
    - .planning/phases/14-thread-revalidation-and-docs/14-COVERAGE-BASE.txt
  modified:
    - src/lifx/network/connection.py
    - tests/test_network/test_connection_retry.py

key-decisions:
  - "accepted_ns is sampled once, immediately after response_queue.get() returns, and reused unchanged as the accepted timestamp if validation later passes -- never resampled after validation, so the recorded latency excludes validation work by construction rather than by later subtraction"
  - "The 'timeout' observation fires at the break point inside the retry loop (before the try/finally's cleanup emission), not after the finally block, so the emitted order is logical_start -> sent -> timeout -> cleanup rather than ...-> cleanup -> timeout"
  - "scripts/measurement_support.py is an independent implementation, not a dynamic loader of tests/test_discovery_observation.py -- unlike the existing scripts/measure_merged_discovery.py precedent, per D-19's 'no script imports a helper from tests' requirement"
  - "The retransmitted-ACK proof (Task 1's acceptance criterion) uses direct queue injection against the DeviceConnection retry engine (the same pattern the rest of test_connection_retry.py already uses for offline-IP determinism), not the emulator's probabilistic drop_packets scenario, because drop_packets is a per-packet probability with no exactly-once-then-succeed mode and cannot deterministically force exactly one retransmit"

patterns-established:
  - "Request-engine measurement observer: connection.py exposes _RequestObserver/_current_request_observer as the single owned seam; any future Phase 14 measurement work (14-02+) attaches via scripts.measurement_support._capture_request_observations() rather than adding new hooks"

requirements-completed: [THREAD-02]

coverage:
  - id: D1
    description: "Private request-observer seam on DeviceConnection: selected once per thin wrapper, propagated explicitly, no public API/behavioural change when absent"
    requirement: THREAD-02
    verification:
      - kind: unit
        ref: "tests/test_network/test_connection_retry.py::TestRequestObservation::test_no_observer_outside_capture_context"
        status: pass
      - kind: unit
        ref: "tests/test_network/test_connection_retry.py::TestRequestObservation::test_observer_insertion_leaves_public_surface_unchanged"
        status: pass
    human_judgment: false
  - id: D2
    description: "Seven bounded observation categories emitted at the correct points, including a retransmitted acknowledgement resolving distinct logical_latency_ns and ack_rtt_ns"
    requirement: THREAD-02
    verification:
      - kind: unit
        ref: "tests/test_network/test_connection_retry.py::TestRequestObservation::test_retransmission_yields_distinct_logical_and_ack_rtt"
        status: pass
      - kind: unit
        ref: "tests/test_network/test_connection_retry.py::TestRequestObservation::test_late_ack_to_earlier_sequence_uses_matching_sent"
        status: pass
      - kind: unit
        ref: "tests/test_network/test_connection_retry.py::TestRequestObservation::test_timeout_observes_timeout_and_no_accepted"
        status: pass
      - kind: unit
        ref: "tests/test_network/test_connection_retry.py::TestRequestObservation::test_send_error_observes_send_error_not_sent"
        status: pass
      - kind: unit
        ref: "tests/test_network/test_connection_retry.py::TestRequestObservation::test_retransmit_send_error_observes_send_error"
        status: pass
      - kind: unit
        ref: "tests/test_network/test_connection_retry.py::TestRequestObservation::test_cancellation_observes_cancelled_then_cleanup"
        status: pass
      - kind: unit
        ref: "tests/test_network/test_connection_retry.py::TestRequestObservation::test_observes_thread_flagged_accepted_response"
        status: pass
    human_judgment: false
  - id: D3
    description: "scripts/thread_revalidation.py's closed-schema validate/append/reload/derive primitives, proven end to end against a real retransmitted DeviceConnection SetPower acknowledgement"
    requirement: THREAD-02
    verification:
      - kind: unit
        ref: "tests/test_scripts/test_thread_revalidation.py::TestTraceRequestEndToEnd::test_retransmitted_ack_journals_and_derives_distinct_values"
        status: pass
      - kind: unit
        ref: "tests/test_scripts/test_thread_revalidation.py::TestTraceRequestEndToEnd::test_timeout_still_journals_partial_evidence_and_reraises"
        status: pass
      - kind: unit
        ref: "tests/test_scripts/test_thread_revalidation.py::TestValidateRequestEvent"
        status: pass
      - kind: unit
        ref: "tests/test_scripts/test_thread_revalidation.py::TestAppendAndReload"
        status: pass
      - kind: unit
        ref: "tests/test_scripts/test_thread_revalidation.py::TestDeriveRequestResult"
        status: pass
    human_judgment: false
  - id: D4
    description: "14-COVERAGE-BASE.txt frozen at the pre-implementation HEAD and 100% changed-line/changed-branch patch coverage confirmed against it"
    verification:
      - kind: other
        ref: "uv run python scripts/check_patch_coverage.py --base 7e563b3cf0616a37227cad83a09bde6f3ebf2aac --coverage coverage.json --source src/lifx/network/connection.py"
        status: pass
    human_judgment: false

duration: 34min
completed: 2026-09-04
status: complete
---

# Phase 14 Plan 01: Trace a retransmitted acknowledgement from production send to validated JSONL Summary

**A private, opt-in request observer on `DeviceConnection`'s retry engine emits identity-free logical-start/sent/accepted/timeout/send_error/cancelled/cleanup events on a `time.monotonic_ns()` metadata clock, proven end to end by tracing a retransmitted fake `SetPower` acknowledgement through `scripts/thread_revalidation.py` into a validated, append-only, privacy-safe JSONL journal that round-trips losslessly.**

## Performance

- **Duration:** 34 min
- **Started:** 2026-09-04T02:39:00Z (approx, from prior session state)
- **Completed:** 2026-09-04T03:13:23Z
- **Tasks:** 2 completed
- **Files modified:** 6 (4 created, 2 modified)

## Accomplishments

- `DeviceConnection._transmit_and_listen()` gained a private `_RequestObserver` callback seam (`_current_request_observer()`, selected once per thin request wrapper, propagated explicitly as a keyword-only parameter) that emits seven bounded, value-only categories without touching any public signature, the retransmit schedule, or the float-based `time.monotonic()` scheduling clock.
- `accepted_ns` is sampled immediately after the response queue's `get()` returns and reused unchanged if validation later passes, so it deliberately includes background-receiver queueing and event-loop wake latency while excluding validation work — proven with a genuinely retransmitted acknowledgement where `logical_latency_ns` and `ack_rtt_ns` resolve to different values from the same event set.
- `scripts/measurement_support.py` owns the `_RequestObservation`/`_RequestObservationSink`/`_capture_request_observations()` primitives as an independent implementation (not a dynamic loader of the tests tree, unlike the existing discovery-measurement precedent).
- `scripts/thread_revalidation.py` owns closed-schema validate/append/reload/derive functions for a privacy-safe request-event JSONL journal, plus `trace_request()`, which drives one real `DeviceConnection.request()` call end to end — proven against a genuinely retransmitted `SetPower` acknowledgement (accepted on the second transmission) and against a genuine timeout (partial evidence still journaled before the exception propagates, per D-03).
- `14-COVERAGE-BASE.txt` freezes `7e563b3cf0616a37227cad83a09bde6f3ebf2aac` as the pre-implementation HEAD; `scripts/check_patch_coverage.py` confirms 100% of the 42 changed executable lines and 18 changed branches in `connection.py` are covered, with no added coverage exemptions or weakening.

## Task Commits

Each task was committed as a RED/GREEN pair (plus a follow-up regression-coverage commit for Task 2's expanded gates):

1. **Task 1 RED: failing tests for the request-observer seam** — `ad34129` (test)
2. **Task 1 GREEN: the observer seam, measurement primitives, and end-to-end tracer** — `30cf4fe` (feat)
3. **Task 2: close observer regression gates and freeze coverage base** — `c21dae0` (test)

_TDD note: Tasks 1 and 2 both carry `tdd="true"`. Task 1 followed the full RED→GREEN cycle (RED confirmed by temporarily reverting the implementation and observing both new test modules fail to import; GREEN confirmed by restoring it). Task 2 added no new production code — it only expanded the observer test suite to close branch-coverage gaps left by Task 1 — so it is committed as a single `test(...)` commit rather than a further RED/GREEN pair, since there was no new behaviour to make RED first._

**Plan metadata:** commit will follow this SUMMARY (docs commit).

## Files Created/Modified

- `src/lifx/network/connection.py` — Added the private `_RequestObserver` type, `_current_request_observer()` task-attribute selector, and observer propagation through `_transmit_and_listen()` and its two thin wrappers (`_request_stream_impl`, `_request_ack_stream_impl`); no public signature, retry schedule, or scheduling-clock change.
- `scripts/measurement_support.py` — New. Owns `_RequestObservation`, `_RequestObservationSink`, `_capture_request_observations()`.
- `scripts/thread_revalidation.py` — New. Owns `_validate_request_event`, `build_request_event`, `append_request_event`, `reload_request_events`, `derive_request_result`, `trace_request()`.
- `tests/test_network/test_connection_retry.py` — Added `TestRequestObservation` (17 tests) covering every observation category, both observer-present and observer-absent branches, and a source-level regression gate on public signatures and `REQUEST_RETRANSMIT_GAPS`.
- `tests/test_scripts/test_thread_revalidation.py` — New. 27 tests covering schema validation, append/reload round-trips, derivation, and two end-to-end `trace_request()` scenarios (retransmitted success, timeout).
- `.planning/phases/14-thread-revalidation-and-docs/14-COVERAGE-BASE.txt` — New. One resolvable full SHA (`7e563b3cf0616a37227cad83a09bde6f3ebf2aac`).

## Decisions Made

- **accepted_ns capture point:** sampled once immediately after the queue `get()` returns, reused unchanged as the accepted timestamp — never resampled after validation — so the recorded latency mechanically excludes validation work rather than relying on a later subtraction that could drift.
- **timeout-before-cleanup ordering:** the "timeout" observation was moved to the exact `break` point inside the retry loop (before the `try/finally`'s cleanup runs), giving the causally sensible `logical_start → sent → timeout → cleanup` order rather than `cleanup → timeout`. Caught by the RED test asserting the exact category sequence.
- **Independent measurement_support.py:** built as a standalone module rather than dynamically loading `tests/test_discovery_observation.py` (the pattern `scripts/measure_merged_discovery.py` currently uses), per D-19's explicit "no script imports a helper from tests" requirement.
- **Retransmission proof via direct queue injection, not the emulator:** the emulator's `drop_packets` scenario is a per-packet probability with no "fail once then succeed" mode, so it cannot deterministically force exactly one retransmit. Used the same direct-queue-injection pattern the rest of `test_connection_retry.py` already relies on for offline-IP determinism — still driving the real production `DeviceConnection` retry/correlation engine, just with the wire delivery simulated at the queue boundary (the established convention in this file).

## Deviations from Plan

None — plan executed as written. Task 1's `<files>` list omitted `tests/test_network/test_connection_retry.py`, but the plan's overall frontmatter `files_modified` list and Task 1's own `<verify>` command both name it, and its `<behavior>` block explicitly requires branch-level scenarios (initial/retransmitted sends, late ACK to an earlier sequence, timeout, send error, cancellation/cleanup, no-observer, repr/privacy) that most naturally live in that file — read as the intended, not a deviation.

## Issues Encountered

- **Async-generator abandonment timing for the SET/ACK success path.** `conn.request()`'s early `return` after the first ACK abandons the underlying `_transmit_and_listen()` generator without calling `aclose()`, so its `finally` block (the "cleanup" observation) can run on a GC-scheduled `call_soon` rather than synchronously. Resolved by testing the "cleanup" category deterministically via the GET/streaming path's own natural idle-timeout `return` (which executes `finally` synchronously in the same frame) instead of via `conn.request()`'s abandonment path, and by scoping the ACK-path tests that use `conn.request()` to only assert on the always-synchronous `logical_start`/`sent`/`accepted` events.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- `scripts/measurement_support.py` and `scripts/thread_revalidation.py` are ready for Plan 14-02 to extend with the complete session manifest, discovery/animation journals, and orchestrator CLI (D-17/D-18/D-20).
- The request-observer seam on `DeviceConnection` is stable and covered; no further changes to `connection.py` are anticipated for THREAD-02's remaining schema/hardware work.
- No blockers.

---
*Phase: 14-thread-revalidation-and-docs*
*Completed: 2026-09-04*

## Self-Check: PASSED

- All 7 key files (4 created, 2 modified, this SUMMARY) verified present on disk.
- All 3 task commits (`ad34129`, `30cf4fe`, `c21dae0`) verified present in git history.
- Focused plan-level verification (`uv run --frozen pytest -o addopts='' tests/test_network/test_connection_retry.py tests/test_scripts/test_thread_revalidation.py -q`) re-run and passing: 64 passed.
- Full project suite re-run and passing: 4477 passed, 12 deselected.
- `uv run ruff check .` / `uv run ruff format --check .` / `uv run pyright` clean on every file this plan touched (pre-existing unrelated findings in the untracked, user-owned `.claude/hooks/post-tool-call.py` are out of scope and untouched).
- `scripts/check_patch_coverage.py` confirms 100% changed-line/changed-branch coverage on `connection.py` against the frozen `14-COVERAGE-BASE.txt`, with no weakening.
