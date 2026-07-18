# Phase 3: Retry Schedule Reshape - Pattern Map

**Mapped:** 2026-07-16
**Files analyzed:** 2 (1 modified source, N test files to extend)
**Analogs found:** strong precedent in Phase 2 (discovery.py) for all 4 requirements

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|--------------------|------|-----------|-----------------|---------------|
| `src/lifx/const.py` (add `REQUEST_RETRANSMIT_GAPS`, floor const) | config | N/A | `src/lifx/const.py:36-39` (`DISCOVERY_REBROADCAST_GAPS`) | exact |
| `src/lifx/network/connection.py::_request_stream_impl` | service (request-response, retry loop) | request-response + streaming | `src/lifx/network/discovery.py::_discover_with_packet` (lines 158-336, esp. 246-336 due-send/deadline loop) | exact — same reshape shape (RETRY-01/02/03) |
| `src/lifx/network/connection.py::_request_ack_stream_impl` | service (request-response, retry loop) | request-response | same discovery loop, adapted for single-response/ACK | role-match (must unify with stream impl per CONTEXT.md constraint) |
| `src/lifx/network/connection.py::_calculate_retry_sleep_with_jitter` (to remove/replace) | utility | N/A | superseded by `IdleDeadline` + `accumulate(gaps)` pattern below | n/a — being replaced |
| `tests/test_network/test_concurrent_requests.py` (extend `TestRetryTimeoutBudget`) | test | request-response | `tests/test_network/test_discovery_rebroadcast.py` (whole file, esp. `TestRebroadcastSchedule`) | exact |
| `tests/test_network/test_connection.py` (retry/timeout classes) | test | request-response | same file, `TestDeviceConnectionRequestStream` (line 341) | role-match |

## Pattern Assignments

### `src/lifx/const.py` — new schedule constant

**Analog:** `src/lifx/const.py:36-39`

```python
# Photons-shaped gaps in seconds between successive discovery re-broadcasts
# after the first send (cumulative offsets 0.6, 1.8, 3.6, 5.6, 7.6), capped
# by DISCOVERY_TIMEOUT.
DISCOVERY_REBROADCAST_GAPS: Final[tuple[float, ...]] = (0.6, 1.2, 1.8, 2.0, 2.0)
```

Mirror this exactly for the request path. Per CONTEXT.md D3-01, gaps ≈ 0.2, 0.3, 0.4,
0.5, 0.7, 0.9, 1.0 (growing toward a cap), plus a floored first-window constant (~0.2 s,
analogous in spirit to `MAX_RESPONSE_TIME`/`DISCOVERY_TIMEOUT` living beside the gaps
tuple at `const.py:31,39`). Suggested naming to rhyme with existing conventions:
`REQUEST_RETRANSMIT_GAPS: Final[tuple[float, ...]]` and
`REQUEST_FIRST_WINDOW: Final[float] = 0.2`. Keep `DEFAULT_MAX_RETRIES` /
`DEFAULT_REQUEST_TIMEOUT` (lines 42+) as-is — `max_retries` becomes the retransmit cap
per D3-05, not a schedule length; document that the gaps tuple, not `max_retries`, drives
the actual retransmit cadence within the wall budget, with `max_retries` capping how many
entries of the schedule (or how many wraps of the cap) are consumed.

### `src/lifx/network/connection.py::_request_stream_impl` — reshape

**Analog:** `src/lifx/network/discovery.py:158-336`, especially:

**IdleDeadline construction and dual-deadline loop** (`discovery.py:246-247, 256-298`):
```python
idle_timeout = max_response_time * idle_timeout_multiplier
deadline = IdleDeadline(timeout, idle_timeout)

# Escalating re-broadcast schedule (DISC-01, D2-01): cumulative
# offsets from request_time at which the same message is re-sent.
# Read the module constant at runtime (not as a def-time default)
# so tests can patch it for fast schedule-exhaustion coverage.
tx_offsets = accumulate(DISCOVERY_REBROADCAST_GAPS)
next_tx: float | None = next(tx_offsets, None)

while True:
    if deadline.idle_expired:
        break
    if deadline.overall_expired:
        break

    now = time.monotonic()
    while next_tx is not None and now - request_time >= next_tx:
        await transport.send(message, (broadcast_address, port))
        next_tx = next(tx_offsets, None)
        now = time.monotonic()

    remaining = deadline.remaining()
    if remaining <= 0:
        break
    if next_tx is not None:
        remaining = min(remaining, request_time + next_tx - now)

    try:
        data, addr = await transport.receive(timeout=remaining)
    except LifxTimeoutError:
        continue
```

**Direct translation for `connection.py`:**
- Replace `total_weight`/`base_timeout` exponential-window math (`connection.py:485-508`,
  `686-698`) with a single `IdleDeadline(timeout, idle_timeout)` built once per logical
  request (matches D3-03: wall-time budget, no sleep-exclusion bookkeeping needed because
  nothing sleeps blind anymore).
- Replace the `_calculate_retry_sleep_with_jitter` + blind `asyncio.sleep()` on timeout
  (`connection.py:626-638`, `759-770`) with the discovery pattern: read
  `REQUEST_RETRANSMIT_GAPS` at runtime via `accumulate(...)`, resend the same request
  (fresh sequence, same `request_source`, satisfies D3-04) whenever `now - attempt_start
  >= next_tx`, and **never call `asyncio.sleep()` for backoff** — instead keep awaiting
  `response_queue.get()` with `timeout=deadline.remaining()` capped to the next due-send
  offset, exactly as `discovery.py:293-304` caps `remaining` to `next_tx`. This satisfies
  D3-02 (listen during backoff): the shared queue consumer never stops polling while
  "waiting to retransmit."
- Each retransmit still needs its own correlation key (`connection.py:514-523`) since
  sequence increments per attempt — keep the existing `correlation_keys` list and
  `_pending_requests` registration/cleanup (`connection.py:520-523, 640-643`) unchanged;
  only the *timing* of when a retransmit fires changes, not the correlation contract.
- `deadline.mark_response()` should be called whenever a response is yielded, matching
  `discovery.py`'s reset-idle-only-on-yield behaviour (see docstring at
  `discovery.py:189-193` and `IdleDeadline.mark_response` at `network/utils.py:70-77`).
  Do NOT call `mark_response()` on send (see `test_send_does_not_reset_idle_window` in
  `tests/test_network/test_discovery_rebroadcast.py:176-206`).

**Unify with `_request_ack_stream_impl`:** per CONTEXT.md constraint, factor the shared
deadline/due-send loop into one helper (e.g. `_send_with_retransmit_schedule`) used by
both `_request_stream_impl` (multi-response) and `_request_ack_stream_impl`
(single-response ACK), rather than duplicating the reshaped loop twice. The two impls
still differ in what they do with a received response (unpack GET/stream vs. validate
ACK/StateUnhandled) — only the "when to send/wait" scaffolding should be shared, same
level of sharing that `discovery.py` achieves by keeping `IdleDeadline` as a standalone
reusable class (`network/utils.py:19-93`) rather than inlining it per call-site.

### Constants/idioms already available (no new pattern needed)

- **`IdleDeadline`** (`src/lifx/network/utils.py:19-93`) — already generic; reuse directly
  for the request path with `timeout=wall_budget`. If a "no per-response idle timeout"
  concept is not desired for `_request_ack_stream_impl` (single ACK expected), pass
  `idle_timeout=timeout` so the idle deadline never fires before the overall one, or add a
  lighter single-deadline helper — but prefer reusing `IdleDeadline` over inventing a new
  class, consistent with `discovery.py`'s reuse.
- **`accumulate` from `itertools`** — already imported in `discovery.py` for turning a
  gaps tuple into cumulative offsets; reuse the same import idiom in `connection.py`.
- **Runtime constant read** — `discovery.py:253`'s comment ("Read the module constant at
  runtime (not as a def-time default) so tests can patch it") is directly reusable
  guidance: reference `REQUEST_RETRANSMIT_GAPS` via the module attribute inside the
  function body (not as a default argument value) so `monkeypatch`/`patch` on the
  `lifx.network.connection` module works in tests, exactly as
  `patch("lifx.network.discovery.DISCOVERY_REBROADCAST_GAPS", (...))` does in
  `tests/test_network/test_discovery_rebroadcast.py:108, 131, 161, 187, 229, 254, 295`.

## Shared Patterns

### Monotonic time / deadline conventions
**Source:** `src/lifx/network/utils.py:19-93` (`IdleDeadline`), used throughout
`discovery.py` via `time.monotonic()` (never wall-clock).
**Apply to:** both `_request_stream_impl` and `_request_ack_stream_impl` — replace
`time.monotonic() - overall_start - total_sleep_time` bookkeeping
(`connection.py:497-498, 504-509, 691-698`) with `IdleDeadline.remaining()` /
`.overall_expired` / `.idle_expired`.

### `asyncio.wait_for` / `TIMEOUT_ERRORS` idiom
**Source:** `src/lifx/const.py:129-134` (`TIMEOUT_ERRORS` tuple), used at
`connection.py:576-579, 722-725` and `discovery.py:300-304`.
**Apply to:** keep using `TIMEOUT_ERRORS` for catching both `asyncio.TimeoutError` and
plain `TimeoutError` consistently across Python versions — no change needed here, just
preserve the existing catch pattern when restructuring the wait loop.

### Structured `_LOGGER` conventions
**Source:** `src/lifx/network/connection.py:190-198, 240-247, 394-403, 406-416, 422-433`
(dict-shaped debug/warning/error logs with `class`/`method`/`action` keys), mirrored in
`discovery.py:233-243, 258-264, 268-275, 279-288`.
**Apply to:** any new log statements in the reshaped retry loop (e.g. `retransmit_sent`,
`idle_timeout`, `overall_timeout` actions) — follow the exact dict-log shape, do not
introduce f-string log messages.

### Correlation-key registration/cleanup
**Source:** `src/lifx/network/connection.py:520-523` (register), `640-643` (cleanup in
`finally`), `708-773` (ack variant, register at 708, cleanup at 772-773).
**Apply to:** preserve unchanged — RETRY-04 requires the same one-key-per-attempt,
shared-queue, cleanup-all-at-end contract. Do not fold correlation cleanup into the new
deadline helper; keep it at the call-site level as today.

## Test Patterns

### Primary analog: `tests/test_network/test_discovery_rebroadcast.py` (entire file)

This is the closest possible precedent — it tests the exact same reshape (escalating
schedule + `IdleDeadline` + due-send loop) that Phase 3 applies to `connection.py`. Mirror
its structure directly:

- **Fake transport with recording send + controllable receive**
  (`test_discovery_rebroadcast.py:24-55`, `_make_quiet_receive`,
  `_make_recording_send`, `_build_mock_transport`): for `connection.py`, the
  equivalent seam is `DeviceConnection._transport` (a `UdpTransport`) — patch
  `lifx.network.connection.UdpTransport` the same way discovery patches
  `lifx.network.discovery.UdpTransport`, or (simpler, since `DeviceConnection` already
  supports emulator-backed tests) use `emulator_server_with_scenarios` with
  `drop_packets` scenarios as `tests/test_network/test_concurrent_requests.py:40-70,
  260-330` already does, patching the new schedule constant via `monkeypatch.setattr` for
  fast, deterministic timing (as `test_retry_sleep_excluded_from_timeout_budget` does at
  `test_concurrent_requests.py:254-258` for the old jitter function — replace that
  monkeypatch target with the new gaps constant).
- **Schedule timing assertions** (`test_discovery_rebroadcast.py:61-79` "two sends at
  first gap within window", `81-96` "window caps schedule to single send",
  `98-119` "schedule exhaustion falls back to remaining"): write direct analogs for
  `connection.py`'s request retransmit schedule — e.g. `test_two_retransmits_at_first_gap`,
  `test_short_timeout_caps_to_single_send`, `test_schedule_exhaustion_falls_back_to_remaining`.
- **Idle-vs-overall exit distinction** (`test_discovery_rebroadcast.py:121-150` idle exit,
  `152-173` overall exit, `175-206` send-does-not-reset-idle): if `_request_stream_impl`
  keeps a per-response idle timeout (it already has one at `connection.py:493`,
  `idle_timeout = 2.0`), write equivalent tests confirming a retransmit does NOT reset the
  idle clock — only a genuine response does.
- **Runtime constant patching** (`test_discovery_rebroadcast.py:108, 131, 161, 187, 229,
  254, 295` — all use `patch("lifx.network.discovery.DISCOVERY_REBROADCAST_GAPS", (...))`):
  use the identical idiom against `lifx.network.connection.REQUEST_RETRANSMIT_GAPS` (or
  wherever the new impl imports/references it from) to get fast deterministic schedule
  tests without real multi-second sleeps.
- **Emulator integration test** (`test_discovery_rebroadcast.py:313-336`,
  `@pytest.mark.emulator`, `@pytest.mark.flaky` on Windows): mirror for a
  `connection.py` end-to-end retransmit test against a real (embedded) emulator with
  `drop_packets` loss injection, confirming first-reply-wins and correct wall-time bound.

### Existing `connection.py` retry tests to extend/replace

`tests/test_network/test_concurrent_requests.py`:
- `TestConcurrentRequests.test_timeout_behavior` (lines 20-33) — no server, `max_retries=0`
  — keep, should still pass unchanged (real timeout, no retries).
- `TestErrorHandling` (lines 37-123) — `drop_packets` scenario pattern via
  `emulator_server_with_scenarios` — directly reusable seam for new schedule tests.
- `TestRetryTimeoutBudget` (lines 219-434) — **must be substantially rewritten**: this
  class's docstring and assertions (lines 220-329) test the *old* "sleep excluded from
  budget" behaviour that RETRY-03 explicitly replaces (D3-03: wall-time budget must never
  be exceeded — the old test asserts the opposite, that `elapsed > timeout + sleep_time`).
  Replace with tests asserting `elapsed <= timeout` (plus small scheduling tolerance) for
  fully-lost-packet scenarios, i.e. invert the assertions at lines 316-328.
  `test_retry_timeout_calculation_consistency` (lines 332-390) and
  `test_retry_all_attempts_get_fair_timeout` (lines 392-434) remain conceptually valid
  (GET/SET consistency, all-attempts message) but need updated expected-attempt-count
  math once the schedule is gap-driven rather than exponential-window-driven.

`tests/test_network/test_connection.py`:
- `TestDeviceConnectionRequestStream` (line 341) and `TestAsyncGeneratorStreaming`
  (line 280) — general request_stream behaviour, largely orthogonal to the retry reshape;
  skim for any tests asserting the old per-attempt exponential timeout math and update
  those specifically.

## No Analog Found

None — Phase 2's discovery reshape is a near-total precedent for every RETRY-0x
requirement (schedule shape, listen-during-backoff, wall-time budget). The only genuinely
new piece is unifying the schedule loop across `_request_stream_impl` and
`_request_ack_stream_impl` (no existing dual-consumer analog in discovery.py, since
discovery only has one flavour of loop) — treat this as a straightforward extraction, not
a novel pattern.

## Metadata

**Analog search scope:** `src/lifx/network/`, `src/lifx/const.py`, `tests/test_network/`
**Files scanned:** `connection.py`, `discovery.py`, `utils.py`, `const.py`,
`test_concurrent_requests.py`, `test_connection.py`, `test_discovery_rebroadcast.py`
**Pattern extraction date:** 2026-07-16
</content>
