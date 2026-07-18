---
phase: 02-discovery-rebroadcast
plan: 01
subsystem: network/discovery
tags: [discovery, udp-broadcast, tdd, reliability]
dependency-graph:
  requires: []
  provides:
    - DISCOVERY_REBROADCAST_GAPS (const.py)
    - re-broadcast interleave in _discover_with_packet
  affects:
    - discover_devices
    - find_by_serial
    - find_by_label
    - find_by_ip
tech-stack:
  added: []
  patterns:
    - "itertools.accumulate for cumulative-offset schedule, read at generator runtime (not def-time default)"
    - "receive-slice capping via min(remaining, next_send_offset) so the loop wakes at send boundaries"
    - "except LifxTimeoutError: continue -- deadline checks are the sole loop-exit authority"
key-files:
  created:
    - tests/test_network/test_discovery_rebroadcast.py
  modified:
    - src/lifx/const.py
    - src/lifx/network/discovery.py
decisions:
  - "Kept response_time anchored at the first broadcast (unchanged semantics); documented the anchor in both DiscoveredDevice.response_time and DiscoveryResponse.response_time docstrings (Open Question 1 resolution)"
  - "No mark_response() call added to the send path -- sends never reset the idle deadline, preserving quiet-network exit timing"
metrics:
  duration: "~7 minutes"
  completed: 2026-07-16
status: complete
---

# Phase 2 Plan 01: Photons-Shaped GetService Re-broadcast Summary

Implemented an escalating Photons-shaped `GetService` re-broadcast schedule
(0.6, 1.2, 1.8, 2.0, 2.0 s gaps) inside `_discover_with_packet()`'s receive
loop, tests-first, so a single `discover_devices()` call finds devices behind
lossy per-AP broadcast delivery on multi-AP networks -- while leaving serial
validation, first-wins dedup, and IdleDeadline semantics byte-for-byte
unchanged.

## Task-by-Task Outcomes

### Task 1: RED branch-matrix tests (`ec35187`)

Created `tests/test_network/test_discovery_rebroadcast.py` with 10 tests
across three classes (`TestRebroadcastSchedule` x8, `TestRebroadcastDedup` x1,
`TestRebroadcastEmulator` x1), covering the full behavioural branch matrix
from 02-VALIDATION.md: schedule timing at real gaps, window capping, patched-
gap schedule exhaustion, quiet-slice continue via both idle and overall
exits, no-`mark_response()`-on-send, multi-send loop passes, message/source
reuse across re-sends, and dedup across broadcasts (unit + one emulator
integration test).

RED result: 8 of 10 tests failed against the current single-broadcast
implementation --
`test_schedule_exhaustion_falls_back_to_remaining`,
`test_quiet_slice_rebroadcast_then_idle_exit`,
`test_quiet_slice_rebroadcast_then_overall_exit`,
`test_send_does_not_reset_idle_window`,
`test_multiple_sends_due_in_one_loop_pass`, and
`test_rebroadcast_reuses_identical_message` failed with
`AttributeError: ... does not have the attribute 'DISCOVERY_REBROADCAST_GAPS'`
(the patched-gap tests could not find the constant); `test_two_sends_at_first_gap_within_window`
and `test_same_serial_across_broadcasts_yields_once` failed on wrong send
counts (`assert 1 == 2`). Two tests passed as expected per plan:
`test_window_caps_schedule_single_send` (coincidentally true today, since a
0.3 s window is smaller than the first real offset regardless of
re-broadcast support) and the emulator dedup test (first-wins dedup already
existed pre-phase).

`tests/test_network/test_discovery_errors.py` was imported from, never
modified (`git status --porcelain` confirmed clean).

### Task 2: GREEN implementation (`c3e4591`)

- `src/lifx/const.py`: added `DISCOVERY_REBROADCAST_GAPS: Final[tuple[float, ...]] = (0.6, 1.2, 1.8, 2.0, 2.0)` after the `IDLE_TIMEOUT_MULTIPLIER` block, with a leading comment stating the cumulative offsets and the `DISCOVERY_TIMEOUT` cap.
- `src/lifx/network/discovery.py`:
  - Added `from itertools import accumulate` to stdlib imports and `DISCOVERY_REBROADCAST_GAPS` to the `lifx.const` import block.
  - After `deadline = IdleDeadline(...)` (now ~L246-247): build `tx_offsets = accumulate(DISCOVERY_REBROADCAST_GAPS)` and `next_tx: float | None = next(tx_offsets, None)` at generator runtime -- reads the module attribute fresh every call, so `patch("lifx.network.discovery.DISCOVERY_REBROADCAST_GAPS", ...)` works in tests.
  - At the top of `while True`, after the `idle_expired`/`overall_expired` checks and before `remaining = deadline.remaining()` (now ~L277-291): inserted the due-send loop -- while `next_tx is not None and now - request_time >= next_tx`, emit a `rebroadcast_sent` debug dict log, `await transport.send(message, (broadcast_address, port))` reusing the identical `message` object (same source, same sequence), then advance `next_tx = next(tx_offsets, None)` and refresh `now`.
  - Between the `remaining <= 0` guard and `transport.receive` (now ~L293-298): capped the receive slice with `if next_tx is not None: remaining = min(remaining, request_time + next_tx - now)` -- no clamp added, since both operands are provably positive at that point (proven by the guards above).
  - Changed `except LifxTimeoutError: break` to `except LifxTimeoutError: continue` (now ~L303-304) -- the single most important edit: a receive-slice timeout now re-enters the loop instead of ending discovery; the top-of-loop idle/overall expiry checks remain the sole exit authority.
  - Updated docstrings: `_discover_with_packet` and `discover_devices` now describe the escalating re-broadcast schedule and the ~11.6 s typical completion time on a populated network (still under the 15 s `DISCOVERY_TIMEOUT`); `DiscoveredDevice.response_time` and `DiscoveryResponse.response_time` now document the first-broadcast anchor.
  - Preserved unchanged: serial validation guards, first-wins `seen_serials` dedup, every `deadline.mark_response()` call site, the `remaining <= 0` defensive break, the `request_time` anchor, and the entire `src/lifx/network/mdns/` module.

GREEN result: all 10 Task 1 tests pass; all 27 existing tests in
`test_discovery_errors.py` and `test_discovery_devices.py` pass unmodified
(37 total, 18.98 s). `git status --porcelain` confirmed both existing test
files and `src/lifx/network/mdns/` were untouched. `grep -c
DISCOVERY_REBROADCAST_GAPS` returned 1 in `const.py` and 3 in
`discovery.py` (import + two runtime reads). `ruff format`, `ruff check
--fix`, and `pyright` all passed clean.

### Task 3: Branch-coverage audit and full-suite regression

Ran `uv run pytest tests/test_network/ --cov-report=term-missing`. The
`src/lifx/network/discovery.py` coverage row showed 88% line / branch
coverage with missing entries at lines 105->120, 115-116, 122, 126,
130-132, 211, 329-337, 371-378, 445-454 -- all of these are pre-existing,
out-of-scope code paths untouched by Task 2 (`DiscoveredDevice.create_device()`
error handling, `__hash__`/`__eq__`, the `ValueError` STATE_TYPE guard, the
`unexpected_packet_type` and `unknown_packet_type` debug/warning branches,
and the `LifxProtocolError` malformed-response handler). None of the new
Task 2 edit ranges (the due-send loop, the offsets iterator, the slice cap,
or the `continue` path) appear in the Missing column -- 100% branch patch
coverage confirmed for the new code with no additional tests required.

Ran the full suite: `uv run --frozen pytest` -- **2545 passed, 12 deselected
(benchmark marker), 0 failed**, in 109.22 s, 96% overall coverage. Confirmed
no test anywhere (new or existing) asserts raw send/response counts against
the emulator -- the new emulator test (`test_emulator_dedup_across_rebroadcast_window`)
only asserts `found_any` and no-duplicate-serial, matching Pitfall 6
guidance. `ruff check .` and `pyright` remained clean; no coverage-driven
test additions were needed, so no additional commit was made for Task 3.

## Deviations from Plan

None -- plan executed exactly as written. All eight prescribed edits in
Task 2 landed as specified in the research edit table, and Task 3 required
no additional narrow branch tests since the new code already met the 100%
branch patch coverage gate.

## Known Stubs

None.

## Threat Flags

None -- the threat model's three registered threats (T-02-01 spoofing,
T-02-02 inbound DoS, T-02-03 outbound self-inflicted DoS) are all mitigated
exactly as planned: re-sends reuse the identical source/message
(`test_rebroadcast_reuses_identical_message`), the overall deadline and
first-wins dedup bound response volume regardless of re-broadcast count,
and the Photons schedule caps outbound load to at most 6 sends per
discovery. No new network surface, auth path, or schema change was
introduced.

## Self-Check: PASSED

- FOUND: tests/test_network/test_discovery_rebroadcast.py
- FOUND: src/lifx/const.py (DISCOVERY_REBROADCAST_GAPS present)
- FOUND: src/lifx/network/discovery.py (rebroadcast_sent debug log present)
- FOUND commit ec35187 (test(02-01): add failing re-broadcast schedule tests)
- FOUND commit c3e4591 (feat(02-01): implement Photons-shaped re-broadcast interleave)

## Notes for Verification

- Full behavioural branch matrix lives in `tests/test_network/test_discovery_rebroadcast.py`; run with `uv run pytest tests/test_network/test_discovery_rebroadcast.py -v`.
- Regression gate: `uv run pytest tests/test_network/ -x` (existing discovery/transport/mDNS tests unmodified).
- Coverage gate: `uv run pytest tests/test_network/ --cov-report=term-missing` -- no missing lines/branches within `src/lifx/network/discovery.py` lines 249-304 (the Task 2 edit range).
- DISC-03 (hardware UAT, plan 02-02) is a separate plan and out of scope here; this plan closes DISC-01 and DISC-02 only.
