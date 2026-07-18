# Phase 2: Discovery Re-broadcast - Pattern Map

**Mapped:** 2026-07-16
**Files analyzed:** 1 source file (modified) + 1-2 test files (new/modified)
**Analogs found:** 4 / 4 (all in-repo; no "no analog" files)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|--------------------|------|-----------|-----------------|----------------|
| `src/lifx/network/discovery.py::_discover_with_packet` | service (receive loop w/ timed re-send) | event-driven / streaming | itself (same function, modified in place) — schedule/deadline shape borrowed from `src/lifx/network/utils.py::IdleDeadline` and `src/lifx/network/connection.py::_calculate_retry_sleep_with_jitter` | role-match |
| `src/lifx/const.py` (new schedule constant(s)) | config | n/a | existing `DISCOVERY_TIMEOUT` / `MAX_RESPONSE_TIME` / `IDLE_TIMEOUT_MULTIPLIER` block, `src/lifx/const.py:28-34` | exact |
| `tests/test_network/test_discovery_errors.py` (new test class for re-broadcast schedule + dedup) | test | request-response / event-driven | `TestDiscoverWithPacketSerialValidation` and `TestRemainingNonPositiveGuard` in the same file | exact |

## Pattern Assignments

### `src/lifx/network/discovery.py::_discover_with_packet` (service, event-driven)

**Analog for the *shape* of a re-broadcast schedule:** the spike harness's `schedule_photons()`,
`.claude/skills/spike-findings-lifx-async/sources/005-discovery-regimes/sweep.py:69-79`:

```python
def schedule_photons(window: float) -> list[float]:
    # Expansion of [(0.6,1.8),(1,2),(2,6),(4,10),(5,20)]: gaps 0.6, 1.2, 1.8,
    # then 2, then 2..6 by 2, then 4..10 by 4, then 5..20 by 5, then 20 forever.
    gaps = [0.6, 1.2, 1.8, 2.0, 2.0, 4.0, 6.0, 4.0, 8.0, 10.0, 5.0]
    times, t = [0.0], 0.0
    for g in gaps:
        t += g
        if t >= window:
            break
        times.append(round(t, 2))
    return times
```

Per CONTEXT.md D2-01, only the first five gaps are in scope for the escalating
schedule inside the discovery window (0.6, 1.2, 1.8, 2.0, 2.0 s from first send).
Implement as a small local helper (e.g. `_rebroadcast_offsets()` or an inline
`next(...)` gap list) rather than porting the full spike harness — the harness
computes absolute times up front; the production loop needs to compare
`time.monotonic() - start_time` against the next scheduled offset each
iteration and fire a resend when crossed. Structure it as a simple index into
a tuple of cumulative offsets, checked once per loop iteration, mirroring how
`deadline.idle_expired` / `deadline.overall_expired` are checked as properties
each pass (`src/lifx/network/discovery.py:239-257`).

**Existing receive-loop skeleton to extend (do not restructure)** —
`src/lifx/network/discovery.py:236-267`:

```python
idle_timeout = max_response_time * idle_timeout_multiplier
deadline = IdleDeadline(timeout, idle_timeout)

while True:
    if deadline.idle_expired:
        ...
        break

    if deadline.overall_expired:
        ...
        break

    remaining = deadline.remaining()
    if remaining <= 0:
        break

    try:
        data, addr = await transport.receive(timeout=remaining)
        response_timestamp = time.monotonic()
    except LifxTimeoutError:
        break
    except LifxProtocolError as e:
        ...
        continue
```

**Where the re-broadcast send belongs**: the existing single send happens
once, before the loop, at `src/lifx/network/discovery.py:221-233`
(`request_time = time.monotonic()` then `await transport.send(message,
(broadcast_address, port))`). The re-broadcast schedule must reuse the *same*
`message` bytes (same `discovery_source`, same sequence
`_DEFAULT_SEQUENCE_START` — do not re-`create_message` with a new source, or
the source-validation guard at line 287 will reject the retried device's
responses to earlier broadcasts as mismatched... actually the guard compares
against a single `discovery_source` so re-sending the identical `message` is
correct and the only safe choice). The natural insertion point is inside the
`while True:` loop, checked immediately after the `remaining <= 0` guard and
before `transport.receive(...)`, since `transport.receive(timeout=remaining)`
can block up to the full idle/overall remaining window and a resend must not
be delayed behind a pending long receive. Consider using
`min(remaining, next_rebroadcast_due)` as the receive timeout so the loop
wakes up promptly at each scheduled resend boundary (analogous to how
`IdleDeadline.remaining()` already takes the min of two deadlines,
`src/lifx/network/utils.py:55-68`).

**Idle-deadline interaction (D2-02, preserve unchanged)**: `deadline.mark_response()`
is called on every valid protocol response before the dedup check,
`src/lifx/network/discovery.py:385-393` — this must continue to apply
regardless of which broadcast round produced the response, so no changes are
needed there. A resend action itself does not call `mark_response()` (it is a
send, not a receive) and should not reset the idle window artificially.

**Structured logging for the resend event** — follow the exact dict-based
`_LOGGER.debug({...})` convention already used for the initial broadcast,
`src/lifx/network/discovery.py:222-233`:

```python
_LOGGER.debug(
    {
        "class": "_discover_with_packet",
        "method": "discover",
        "action": "broadcast_sent",
        "broadcast_address": broadcast_address,
        "port": port,
        "packet_type": type(packet).__name__,
        "expected_response": expected_response_type,
    }
)
await transport.send(message, (broadcast_address, port))
```

A resend log entry should add an `"action": "rebroadcast_sent"` (or similar)
with an `"elapsed"` or `"round"` field, matching the style of the idle/overall
timeout debug logs at lines 240-257.

**Exponential/staged-timing analog (for review, not copy)**:
`src/lifx/network/connection.py:330-348`
(`_calculate_retry_sleep_with_jitter`) is the codebase's only other "timed
resend schedule" precedent, but it is jittered exponential backoff for
per-request retries — not a fit for the fixed Photons-shaped gap list
required here. Use it only as evidence for where in the file class/module
timing constants and computed-offset helpers conventionally live (as a
`@staticmethod` near the loop that uses it), not for its jitter logic.

---

### `src/lifx/const.py` (config)

**Analog** — the existing discovery timing constant block,
`src/lifx/const.py:26-34`:

```python
DISCOVERY_TIMEOUT: Final[float] = 15.0

MAX_RESPONSE_TIME: Final[float] = 1.0  # 1 second

# Idle timeout multiplier - wait this many times MAX_RESPONSE_TIME after last response
IDLE_TIMEOUT_MULTIPLIER: Final[float] = 4.0  # 4 seconds (1.0 x 4.0)
```

If the planner decides to expose the re-broadcast gap schedule as a named
constant (per CONTEXT D2-03, "module-level constants in `const.py` are the
pattern, not new kwargs"), follow this exact convention: `Final[...]`
annotation, a one-line inline comment explaining the value in seconds, grouped
immediately below the existing discovery constants (after line 34, before the
`DEFAULT_REQUEST_TIMEOUT` block at line 37). E.g.:

```python
# Escalating GetService re-broadcast schedule (Photons-shaped), seconds from
# first send: 0.6, 1.2, 1.8, 2.0, 2.0 — capped by DISCOVERY_TIMEOUT.
DISCOVERY_REBROADCAST_GAPS: Final[tuple[float, ...]] = (0.6, 1.2, 1.8, 2.0, 2.0)
```

---

### `tests/test_network/test_discovery_errors.py` (test, request-response / event-driven)

**Analog for mocked-transport send counting** —
`TestDiscoverWithPacketSerialValidation.test_broadcast_bit_serial_rejected_at_generator`,
`tests/test_network/test_discovery_errors.py:430-472`, and
`TestRemainingNonPositiveGuard.test_remaining_nonpositive_breaks_before_receive`,
`tests/test_network/test_discovery_errors.py:749-775`. Both patch
`lifx.network.discovery.UdpTransport` and `lifx.network.discovery.allocate_source`,
build an `AsyncMock` transport with `__aenter__`/`__aexit__`/`send`/`receive`
stubbed, and drive `_discover_with_packet(...)` directly (not the
`discover_devices()` wrapper) to assert internal generator behaviour. This is
the closest existing pattern for a new test asserting **re-broadcast send
count and timing**:

```python
mock_transport = AsyncMock()
mock_transport.__aenter__ = AsyncMock(return_value=mock_transport)
mock_transport.__aexit__ = AsyncMock(return_value=False)
mock_transport.send = AsyncMock()
mock_transport.receive = mock_receive
mock_transport_cls.return_value = mock_transport
```

For asserting the **schedule** specifically: after the test drains the
generator, use `mock_transport.send.call_count` and/or
`mock_transport.send.call_args_list` (currently unused by existing tests,
since they only ever expect exactly one send) — this is a new assertion
pattern the planner should add, not something to copy verbatim. Because
`mock_transport.receive` in existing tests is a plain async function
(`mock_receive`) rather than something that advances a virtual clock, the
schedule test will need to control `time.monotonic()` — no existing test in
this repo mocks `time.monotonic()` for discovery; `pytest-mock`'s
`monkeypatch` or `unittest.mock.patch("lifx.network.discovery.time.monotonic",
side_effect=[...])` (a stepped sequence of monotonic values, one per
loop-iteration check) is the natural mechanism, following the same
`patch("lifx.network.discovery.X", ...)` targeting convention used throughout
this file for `UdpTransport` and `allocate_source`.

**Analog for dedup-across-resends test** —
`TestDiscoverWithPacketSerialValidation.test_first_wins_dedup_at_generator`,
`tests/test_network/test_discovery_errors.py:560-603`, sends the identical
`_build_state_service_packet(...)` twice via `packet_iter` and asserts
`len(responses) == 1`. Extend this exact pattern for
"duplicate StateService responses across two separate re-broadcast rounds
still dedup to one yield" (DISC-02) — reuse `_build_state_service_packet`
(module-level helper, `tests/test_network/test_discovery_errors.py:96-125`)
unchanged.

**Marker convention**: emulator-backed integration tests use
`@pytest.mark.emulator` plus
`@pytest.mark.flaky(retries=2, delay=1, condition=sys.platform.startswith("win32"))`
at the class level (e.g. `tests/test_network/test_discovery_devices.py:24-25`,
`tests/test_network/test_discovery_errors.py:17-18`). Any new emulator-backed
schedule/coverage test (verifying more devices are found across rounds, per
DISC-01/03 "automated tests cover schedule mechanics") should use the same
`emulator_port` fixture and marker stack; unit-level schedule/dedup tests
that mock `UdpTransport` directly (per the constraint "emulator cannot model
per-AP broadcast loss") should live unmarked in the same style as
`TestDiscoverWithPacketSerialValidation`.

**Branch-coverage-sensitive test structuring** — see
`TestRemainingNonPositiveGuard`, `tests/test_network/test_discovery_errors.py:741-775`,
which exists solely to hit a defensive `remaining() <= 0` branch by mocking
`IdleDeadline` itself with a `MagicMock` reporting a contradictory state. New
re-broadcast branches (e.g. "resend fires exactly at boundary", "resend does
not fire after `DISCOVERY_TIMEOUT` truncates the schedule") will likely need
similarly narrow, purpose-built unit tests rather than relying on broader
emulator integration tests to exercise every branch — CI requires 100%
branch patch coverage (CONTEXT.md constraints).

---

## Shared Patterns

### Structured logging
**Source:** `src/lifx/network/discovery.py:222-233`, `240-257`, `430-437`
**Apply to:** the new re-broadcast log statement inside `_discover_with_packet`
```python
_LOGGER.debug(
    {
        "class": "_discover_with_packet",
        "action": "<new action name>",
        ...
    }
)
```
All fields are plain dict literals passed directly as the log message (not
f-strings) — preserve this exactly for the new rebroadcast log line.

### Monotonic-time deadline math
**Source:** `src/lifx/network/utils.py:19-93` (`IdleDeadline`)
**Apply to:** any new schedule-offset tracking inside `_discover_with_packet`
```python
self._start: float = time.monotonic()
...
remaining_overall = self._overall - (now - self._start)
```
Reuse `time.monotonic()` exclusively (never wall-clock) for computing "has
the next rebroadcast offset elapsed since `start_time`", matching the
existing `start_time = time.monotonic()` already captured at
`src/lifx/network/discovery.py:206`.

### Constants block conventions
**Source:** `src/lifx/const.py:26-34`
**Apply to:** any new `const.py` addition
`Final[...]` typed, grouped with related discovery constants, one-line
trailing or leading comment stating the unit and rationale.

## No Analog Found

None — this phase only modifies one existing function and its existing test
file; every piece of new work has a directly reusable in-repo precedent.

## Metadata

**Analog search scope:** `src/lifx/network/`, `src/lifx/const.py`,
`tests/test_network/`, `.claude/skills/spike-findings-lifx-async/sources/005-discovery-regimes/`
**Files scanned:** `discovery.py`, `utils.py`, `connection.py`, `const.py`,
`test_discovery_errors.py`, `test_discovery_devices.py`, `sweep.py`
**Pattern extraction date:** 2026-07-16
</content>
