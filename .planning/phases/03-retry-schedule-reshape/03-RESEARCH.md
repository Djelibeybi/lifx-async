# Phase 3: Retry Schedule Reshape - Research

**Researched:** 2026-07-16
**Domain:** asyncio UDP request retry scheduling inside `DeviceConnection` (internal codebase change; no external dependencies)
**Confidence:** HIGH

## Summary

Phase 3 replaces the retry machinery in `src/lifx/network/connection.py`'s two request
paths. Today `_request_stream_impl` (L435-649) and `_request_ack_stream_impl` (L651-778)
each distribute the caller's timeout as exponential per-attempt windows
(`timeout/(2^(n+1)-1) · 2^attempt` → ~31 ms first window at defaults) with full-jitter
sleeps between attempts that are deliberately *excluded* from the budget
(`total_sleep_time` bookkeeping). Spike 002 measured the consequences: 1.37 packets/trial
at zero loss (all pure duplicates), median latency doubled on gen4 (responses sat unread
through the jitter sleep), and 23.4–29.0 s wall time against a 16 s budget
`[VERIFIED: spike 002, 540 trials]`.

The fix is the Photons shape, proven in `race.py::regime_photons()`: one wall deadline
(`start + timeout`), retransmits fired by a timer folded into the queue-get timeout
(`wait = min(deadline, next_tx_at, idle_deadline) − now`), fresh sequence per retransmit
registered against the *same* shared response queue, first reply wins, retransmits stop
once a response arrives. This is structurally the same interleave Phase 2 shipped in
`_discover_with_packet()` (send timer capped receive slices, `except LifxTimeoutError:
continue`), so the proven pattern, the constant shape (`DISCOVERY_REBROADCAST_GAPS`
analogue), and the test techniques all carry over. Because both impls need the identical
transmit/wait engine, the flagged duplication is resolved by extracting one shared
private async-generator helper that owns source allocation, the shared queue, the
schedule, the wall deadline, correlation-key lifecycle, and response validation; the two
impls become thin wrappers preserving their distinct semantics (multi-response idle
streaming vs single-ACK + StateUnhandled → `LifxUnsupportedCommandError`).

**Primary recommendation:** Add `REQUEST_RETRANSMIT_GAPS = (0.2, 0.3, 0.4, 0.5, 0.7,
0.9, 1.0, 2.0, 3.0, 4.0, 5.0)` to `const.py` (runtime-read for patchability), implement a
shared `_transmit_and_listen()` helper generator with a single monotonic wall deadline
and retransmit-while-listening, delete `_calculate_retry_sleep_with_jitter` /
`_RETRY_SLEEP_BASE` / `total_sleep_time` entirely, and keep the
`_request_stream_impl`/`_request_ack_stream_impl` names and signatures intact (the
existing mock-seam tests depend on them).

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D3-01**: Replace the exponential window distribution (`timeout/(2^(n+1)-1) · 2^attempt`
  → 31 ms first window) with a Photons-shaped schedule: floored first window (~200 ms),
  escalating retransmit gaps thereafter. Reference expansion in the spike:
  gaps ≈ 0.2, 0.3, 0.4, 0.5, 0.7, 0.9, 1.0, then growing toward a cap.
- **D3-02**: Listen during backoff — never sleep blind. Replace the jittered
  inter-attempt `asyncio.sleep()` with retransmit-while-listening: the shared response
  queue is consumed continuously; a timer decides when to retransmit. A response arriving
  at any moment is accepted immediately.
- **D3-03**: The caller's `timeout` is WALL time. All waiting counts against the budget;
  a 16 s budget can never take 29 s (spike observed 23.4–29.0 s overruns from
  budget-excluded sleeps).
- **D3-04**: Preserve the correlation contract: one source per logical request, fresh
  sequence per retransmit, shared queue accepts responses from ALL issued sequences,
  first reply wins, late/duplicate replies silently discarded (DEBUG at most).
- **D3-05**: Public API unchanged — `request()`/`request_stream()` signatures, `timeout`
  and `max_retries` parameters keep working. `max_retries` reinterpreted naturally as the
  retransmit cap within the wall budget (document precisely). Constants in `const.py`.
- **D3-06**: Scope is `connection.py` request paths only. No discovery changes (Phase 2,
  shipped), no animation changes (Phase 4), no ack semantics changes.

### Claude's Discretion

(No explicit discretion section in CONTEXT.md — implementation details within the locked
decisions are at the planner's discretion: helper naming, constant naming, unification
shape, test structure.)

### Deferred Ideas (OUT OF SCOPE)

- Discovery re-broadcast (Phase 2, shipped).
- Animation flow control (Phase 4).
- User-facing documentation pages (Phase 5) — in-file docstrings in `connection.py` ARE
  in scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| RETRY-01 | First-attempt window floored (~200 ms) with escalating retransmit gaps replacing the 31 ms-doubling shape — no duplicate packets on healthy networks | Schedule constant design in "Q4"; first gap of `REQUEST_RETRANSMIT_GAPS` (0.2 s) *is* the floor; zero-duplicate test via send-spy in "Code Examples" |
| RETRY-02 | Responses arriving between attempts are consumed immediately (listen during backoff — no blind sleeps) | Loop design in "Q2" — `wait_for(queue.get(), min(deadline, next_tx, idle))`; jitter sleep + `total_sleep_time` deletion mapped in "Q1"; immediacy test via queue injection |
| RETRY-03 | The caller's `timeout` is honoured as wall time — a 16 s budget can never take 29 s | Single monotonic wall deadline enforced at every await ("Q2"); wall-time test replaces `test_retry_sleep_excluded_from_timeout_budget` ("Existing Test Impact") |
| RETRY-04 | Shared-queue correlation across all issued sequences preserved: late replies accepted, duplicates silently discarded | GET path already has this (keep verbatim, L474-483/L517-523/L640-643); ACK path gains it (per-attempt queue → shared queue, strict-sequence check relaxed — see "Q3"); duplicate discard is the existing `_background_receiver` unmatched path (L404-416) |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- Zero runtime dependencies — this phase adds none (stdlib only).
- All imports at top of file.
- `uv` exclusively; `uv run --frozen pytest`; `uv run ruff format/check`; `uv run pyright`
  (strict per repo config).
- Commits: `git commit -s`, GPG-signed (planner note: research not committed per
  orchestrator instruction).
- CI requires 100% **branch** patch coverage (project memory: check branch partials, not
  just diff-cover lines) — avoid defensive clamps that create unreachable branches.
- "Don't ignore a problem: if you see it, fix it" — two in-scope docstring defects found
  (see Pitfall 6).
- Australian English spelling in comments/docstrings.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Retransmit scheduling + wall deadline | Network layer (`network/connection.py`, new shared helper) | — | D3-06 locks scope to connection.py request paths; both impls delegate to one engine |
| Schedule constant | `const.py` (`REQUEST_RETRANSMIT_GAPS`) | — | D3-05: constants in const.py; mirrors `DISCOVERY_REBROADCAST_GAPS` pattern (runtime-read, test-patchable) |
| Response routing / correlation | `_background_receiver` (unchanged) | — | Routing by `(source, sequence, serial)` key and unmatched-discard already implement the D3-04 contract at the receiver |
| Late/duplicate reply discard | `_background_receiver` unmatched path (unchanged) | — | After key cleanup, late replies log at DEBUG and drop (L404-416) — exactly "silently discarded" |
| GET vs ACK semantics | Thin impl wrappers (`_request_stream_impl`, `_request_ack_stream_impl`) | — | Names/signatures are a test seam (mocked in 12+ tests); semantics differences stay in the wrappers |

## Standard Stack

### Core

No new libraries. Stdlib-only work inside an existing zero-dependency module
`[VERIFIED: codebase — pyproject.toml has no runtime deps]`.

| Component | Version | Purpose | Why Standard |
|-----------|---------|---------|--------------|
| `time.monotonic()` | stdlib | Wall deadline + retransmit timer | Codebase convention (connection.py already uses it throughout; `IdleDeadline` documents "monotonic exclusively"). Do NOT use `perf_counter()` even though race.py did |
| `asyncio.wait_for(queue.get(), timeout=...)` | stdlib | Bounded listen slices | Already the receive mechanism in both impls (L576, L722); the reshape only changes what bounds the timeout |
| `TIMEOUT_ERRORS` from `const.py` | stdlib shim | Py3.10 asyncio.TimeoutError compat | Existing pattern; keep for every `wait_for` |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Timer folded into queue-get timeout (recommended) | Separate retransmit `asyncio.Task` | Background task needs cancellation on every generator exit path (GeneratorExit, protocol errors, deadline) and races the consumer on `tx_count`/key registration; the fold-in is single-coroutine, matches both `regime_photons()` and Phase 2's shipped interleave, and is trivially branch-coverable |
| Shared helper async generator | Duplicating the new loop in both impls | CONTEXT explicitly flags the duplication as a cleanup candidate: "if the reshape touches both paths, unify rather than duplicating the new schedule twice" |
| `next(gaps_iter, last_gap)` repeat-last-cap | Explicit `itertools.cycle`/index arithmetic | `next(it, default)` is the exact shape race.py used (L282) and Phase 2 used (`next(tx_offsets, None)`); no extra branch to cover |
| Reusing `IdleDeadline` for the stream idle window | Hand-rolled `last_response` timestamp (recommended) | `IdleDeadline` anchors its idle clock at construction; the stream contract is "no idle exit until the FIRST response" — shoehorning it in needs a sentinel and adds branches. Two timestamps + one comparison is simpler and matches the existing code |

**Installation:** none.

## Package Legitimacy Audit

No external packages are installed by this phase. **Packages removed:** none.
**Packages flagged:** none.

## Architecture Patterns

### System Architecture Diagram

```
request() / request_stream(packet, timeout)
        │
        ├─ GET/Echo ─▶ _request_stream_impl ──┐   (thin wrappers; names kept —
        └─ SET ──────▶ _request_ack_stream_impl┤    they are the mock seam)
                                               ▼
              _transmit_and_listen(request, timeout, max_retries,
                                   ack_required, res_required, noun)
                                               │
   ┌───────────────────────────────────────────┴───────────────────────────────┐
   │ setup: source = allocate_source(); shared Queue(100); keys=[];            │
   │        deadline = monotonic() + timeout                                   │
   │ tx #0: register (source, 0, serial) → queue; send_packet(seq=0)           │
   │        next_tx_at = now + gaps[0] (0.2 s)  [None if max_retries == 0]     │
   │ ┌── while True ──────────────────────────────────────────────────────────┐│
   │ │ 1. now ≥ deadline?  → yielded ? return : break (raise LifxTimeoutError)││
   │ │ 2. yielded and idle ≥ _STREAM_IDLE_TIMEOUT? → return                   ││
   │ │ 3. retransmit due (next_tx_at ≤ now, not yielded)?                     ││
   │ │      register (source, tx_count, serial) → SAME queue; send;           ││
   │ │      tx_count += 1; next gap or None if tx_count > max_retries;        ││
   │ │      continue                                                          ││
   │ │ 4. wait = deadline − now, capped by next_tx_at and idle remainder      ││
   │ │ 5. wait_for(queue.get(), wait) — TIMEOUT_ERRORS → continue     ◀ D3-02 ││
   │ │ 6. validate serial / source / sequence-in-issued-range                 ││
   │ │ 7. yield (header, payload); mark yielded; reset idle clock             ││
   │ └────────────────────────────────────────────────────────────────────────┘│
   │ finally: pop ALL correlation keys                                  ◀ D3-04 │
   └───────────────────────────────────────────────────────────────────────────┘
   Late replies after cleanup → _background_receiver unmatched path → DEBUG log,
   discarded (unchanged, L404-416)
```

### Q1: Current control flow and concrete edit points

All line numbers verified against `src/lifx/network/connection.py` this session
`[VERIFIED: codebase]`.

**Module level:**

| Location | Current | Edit |
|----------|---------|------|
| L7 `import random` | jitter only | DELETE (sole user is the jitter helper) |
| L15-20 const import | — | ADD `REQUEST_RETRANSMIT_GAPS` (becomes a patchable module attribute of `lifx.network.connection`) |
| L40 `_RETRY_SLEEP_BASE` | jitter base | DELETE |
| L42 `_DEFAULT_IDLE_TIMEOUT = 0.1` | **dead constant** (defined, never referenced) | DELETE; ADD `_STREAM_IDLE_TIMEOUT: float = 2.0` (hoists the L493 magic number; runtime-read so tests can patch it) |
| L56-62 class docstring | "Retry logic with exponential backoff and jitter" | UPDATE to describe wall-time budget + escalating retransmits |
| L101-102 `__init__` docstring | "timeout ... (default: 8.0)" — wrong, `DEFAULT_REQUEST_TIMEOUT` is 16.0 | FIX while here (Pitfall 6); document `max_retries` as "maximum retransmits within the timeout budget" |
| L330-348 `_calculate_retry_sleep_with_jitter` | jitter maths | DELETE (one test monkeypatches it — see Existing Test Impact) |

**`_request_stream_impl` (L435-649):**

| Lines | Current | Fate |
|-------|---------|------|
| L464-471 | open guard + `timeout`/`max_retries` defaults (pragmas) | KEEP (move into helper; keep pragma comments) |
| L474 | one `allocate_source()` per logical request | KEEP (D3-04) — moves to helper |
| L477-483 | ONE shared `Queue(maxsize=100)` + `correlation_keys` list | KEEP verbatim — moves to helper |
| L485-489 | `total_weight = 2^(n+1)−1; base_timeout = timeout/total_weight` | DELETE (D3-01) |
| L493 | `idle_timeout = 2.0` local | REPLACE with module `_STREAM_IDLE_TIMEOUT` |
| L495-498 | `last_error`, `has_yielded`, `overall_start`, `total_sleep_time` | `total_sleep_time` DELETE (D3-03); `overall_start` becomes `deadline = monotonic() + timeout`; `has_yielded` KEEP |
| L501-511 | per-attempt window computation + `current_timeout <= 0` break | REPLACE with wall-deadline check |
| L515 | `sequence = attempt` | Same numbering (0, 1, 2, …) but driven by transmit count, not loop index |
| L517-523 | register key with shared queue BEFORE send | KEEP shape — repeated per retransmit inside the loop |
| L526-533 | `send_packet(..., ack_required=False, res_required=True)` | KEEP flags — parameterised in helper |
| L535-550 | attempt deadline + per-attempt `TimeoutError` raise / `return` if yielded | REPLACE: single wall deadline; on expiry `return` if yielded else raise `LifxTimeoutError` once |
| L552-571 | idle timeout after first response (check + wait cap) | KEEP semantics; folds into steps 2 and 4 of the new loop |
| L573-587 | `wait_for(response_queue.get(), remaining)` + timeout → retry/return | KEEP core await; timeout now means `continue` (slice ended — deadline checks and retransmit timer own control flow) |
| L589-609 | serial validation (skip for discovery) + source validation | KEEP verbatim — moves to helper |
| L611-617 | sequence-in-range check (`header.sequence >= len(correlation_keys)`) | KEEP — `len(correlation_keys)` still equals transmissions issued |
| L619-622 | `has_yielded = True; last_response_time = ...; yield` | KEEP |
| L626-638 | `except TIMEOUT_ERRORS:` jitter sleep + `total_sleep_time` + continue/break | DELETE ENTIRELY (D3-02/D3-03 — this is where arrived responses sat unread) |
| L640-643 | `finally:` pop ALL keys | KEEP verbatim — moves to helper |
| L645-649 | raise `No response from {ip} after {max_retries + 1} attempts` | KEEP message shape, but report **transmissions actually sent** (`after {tx_count} attempts`) |

**`_request_ack_stream_impl` (L651-778):**

| Lines | Current | Fate |
|-------|---------|------|
| L674-681 | guards + defaults | KEEP (delegated to helper) |
| L684-688 | own source + duplicate window arithmetic | DELETE — helper owns it (the flagged duplication) |
| L699-708 | **per-attempt** key + **per-attempt** `Queue(maxsize=10)` | REPLACE with helper's shared queue + all-keys-registered. Behaviour change mandated by D3-04: a late ACK from an earlier retransmit now satisfies the request (today it's discarded as unmatched because the earlier key was popped in the per-attempt `finally` L772-773) |
| L711-718 | `send_packet(..., ack_required=True, res_required=False)` | KEEP flags via helper parameter |
| L720-729 | single `wait_for` + per-attempt TimeoutError | REPLACE via helper |
| L731-747 | strict correlation: `header.sequence != sequence` → protocol error | RELAX to helper's sequence-in-issued-range check (D3-04). Source/serial checks unify with the GET path |
| L749-753 | StateUnhandled → `LifxUnsupportedCommandError` | KEEP in the wrapper (ack-only semantic, D3-06) |
| L755-757 | `yield True; return` | KEEP in the wrapper |
| L759-770 | jitter sleep retry | DELETE |
| L772-773 | per-attempt `finally` pop | Superseded by helper's all-keys `finally` |
| L775-778 | raise `No acknowledgement from {ip} after {n} attempts` | KEEP message (helper takes a noun parameter, or wrapper catches and re-raises) |

### Q2: The reshaped loop, concretely

Reference implementation shape (adapted from `race.py::regime_photons()` L248-283 and
Phase 2's shipped interleave in `discovery.py` L249-304):

```python
# Source: race.py regime_photons (spike 002) + discovery.py Phase 2 interleave,
# adapted to the shared-queue architecture. Illustrative — names at planner's discretion.
async def _transmit_and_listen(
    self,
    request: Any,
    timeout: float,
    max_retries: int,
    *,
    ack_required: bool,
    res_required: bool,
    timeout_noun: str,          # "response" | "acknowledgement"
) -> AsyncGenerator[tuple[LifxHeader, bytes], None]:
    request_source = allocate_source()
    response_queue: asyncio.Queue[tuple[LifxHeader, bytes]] = asyncio.Queue(maxsize=100)
    correlation_keys: list[tuple[int, int, str]] = []

    # Runtime read of the module attribute → tests patch
    # lifx.network.connection.REQUEST_RETRANSMIT_GAPS for fast schedules.
    gaps = iter(REQUEST_RETRANSMIT_GAPS)
    last_gap = REQUEST_RETRANSMIT_GAPS[-1]

    start = time.monotonic()
    deadline = start + timeout
    has_yielded = False
    last_response_time = start
    tx_count = 0

    try:
        # Transmission #0 (sequence 0), key registered BEFORE send
        key = (request_source, 0, self.serial)
        self._pending_requests[key] = response_queue
        correlation_keys.append(key)
        await self.send_packet(request, source=request_source, sequence=0,
                               ack_required=ack_required, res_required=res_required)
        tx_count = 1
        next_tx_at = (time.monotonic() + next(gaps, last_gap)
                      if max_retries > 0 else None)

        while True:
            now = time.monotonic()
            if now >= deadline:                      # RETRY-03: wall budget
                if has_yielded:
                    return                           # stream complete
                break                                # → raise after finally

            if has_yielded:
                idle_elapsed = now - last_response_time
                if idle_elapsed >= _STREAM_IDLE_TIMEOUT:
                    return                           # idle streaming exit (unchanged)

            if next_tx_at is not None and not has_yielded and now >= next_tx_at:
                seq = tx_count                       # fresh sequence per retransmit
                key = (request_source, seq, self.serial)
                self._pending_requests[key] = response_queue   # SAME queue (D3-04)
                correlation_keys.append(key)
                await self.send_packet(request, source=request_source, sequence=seq,
                                       ack_required=ack_required,
                                       res_required=res_required)
                tx_count += 1
                next_tx_at = (time.monotonic() + next(gaps, last_gap)
                              if tx_count <= max_retries else None)
                continue                             # re-check deadlines with fresh now

            # Fold every bound into ONE queue-get timeout (RETRY-02)
            wait = deadline - now
            if next_tx_at is not None and not has_yielded:
                wait = min(wait, next_tx_at - now)
            if has_yielded:
                wait = min(wait, _STREAM_IDLE_TIMEOUT - (now - last_response_time))

            try:
                header, payload = await asyncio.wait_for(
                    response_queue.get(), timeout=wait
                )
            except TIMEOUT_ERRORS:
                continue                             # slice ended — loop decides why

            # Validations: keep the GET path's three checks verbatim (L589-617)
            ...                                      # serial / source / sequence-range

            has_yielded = True
            last_response_time = time.monotonic()
            yield header, payload
    finally:
        for key in correlation_keys:
            self._pending_requests.pop(key, None)

    raise LifxTimeoutError(
        f"No {timeout_noun} from {self.ip} after {tx_count} attempts"
    )
```

Key properties the planner must preserve:

- **Wall deadline enforced at every await.** The only awaits are `send_packet` (UDP,
  effectively instant) and `wait_for(queue.get(), wait)` where `wait ≤ deadline − now`.
  Elapsed can exceed `timeout` only by scheduler jitter (ε, not seconds).
- **All `wait` operands are strictly positive** at the point of use: `deadline − now > 0`
  (checked in step 1), `next_tx_at − now > 0` (else step 3 fired and `continue`d),
  idle remainder `> 0` (checked in step 2). **No `max(wait, 0.001)` clamp** — it would
  create an uncoverable branch and fail the 100% branch patch gate (same proof Phase 2
  used, discovery.py L293-298).
- **Retransmits stop after the first accepted response** (`not has_yielded` gate).
  For single-response requests the consumer breaks anyway; for multi-response streams a
  retransmit after responses began would provoke a duplicate response *set*. Photons
  behaves the same way (first reply wins ends the send loop) `[VERIFIED: race.py L270-277]`.
- **Register key BEFORE each send** (existing pattern, L517-523) so a response cannot
  arrive before its key exists.
- **`continue` after a retransmit** re-reads `now` before computing `wait` — otherwise
  the send's own latency silently eats into the next slice.

### Q3: Unification shape and preserved behavioural differences

**Shape:** one private helper (async generator yielding raw `(header, payload)`),
two thin wrappers. The wrappers MUST keep their current names and signatures —
`_request_stream_impl(self, request, timeout=None, max_retries=None)` and
`_request_ack_stream_impl(self, request, timeout=None, max_retries=None)` — because
12+ tests in `test_connection.py` patch exactly these attributes as their mock seam
`[VERIFIED: tests/test_network/test_connection.py L373, L440, L483, ...]`.

```python
async def _request_stream_impl(self, request, timeout=None, max_retries=None):
    async for header, payload in self._transmit_and_listen(
        request, timeout, max_retries,
        ack_required=False, res_required=True, timeout_noun="response",
    ):
        yield header, payload

async def _request_ack_stream_impl(self, request, timeout=None, max_retries=None):
    async for header, _payload in self._transmit_and_listen(
        request, timeout, max_retries,
        ack_required=True, res_required=False, timeout_noun="acknowledgement",
    ):
        if header.pkt_type == _STATE_UNHANDLED_PKT_TYPE:
            raise LifxUnsupportedCommandError("Device does not support this command")
        yield True
        return          # closes helper → finally pops all keys
```

(Default resolution — `timeout=None → self.timeout`, `max_retries=None →
self.max_retries` — and the open guard can live in the helper or the wrappers; keeping
them in the helper avoids triplication. Preserve the existing `# pragma: no cover`
markers on the guard/default lines that carry them today.)

**Differences that MUST be preserved (the wrapper layer):**

| Aspect | GET (`_request_stream_impl`) | ACK (`_request_ack_stream_impl`) |
|--------|------------------------------|----------------------------------|
| Header flags | `res_required=True, ack_required=False` (L531-532) | `ack_required=True, res_required=False` (L716-717) |
| Response count | Multi-response: stream until idle (2.0 s after first) or wall deadline | Single: yield `True` once, return |
| StateUnhandled (223) | Normal response — unpacked and yielded by `request_stream` (switch test asserts this) | Raise `LifxUnsupportedCommandError` (L749-753) |
| Yield type | `(LifxHeader, bytes)` | `bool` |
| Timeout message | `"No response from {ip} after {n} attempts"` | `"No acknowledgement from {ip} after {n} attempts"` |

**Difference that intentionally CHANGES (mandated by D3-04, not an ack-semantics
change):** the ACK path's per-attempt queue (`maxsize=10`, L705-707) and strict
`header.sequence != sequence` check (L738) become the shared queue + sequence-in-issued-
range check. Consequence: a late ACK answering retransmit #0 that arrives after
retransmit #1 was sent now completes the request (today it is discarded and the request
waits for an ACK to the newest sequence). Queue maxsize unifies to 100 (harmless).

**Duplicate discard (RETRY-04):** needs no new code. During the request, the consumer
takes the first queued reply; extra queued replies are dropped when the generator exits
(queue garbage-collected). After key cleanup, late replies fail the
`_pending_requests` lookup in `_background_receiver` and are logged at DEBUG and
discarded (L404-416). Never a protocol error — the `LifxProtocolError` validations fire
only on responses that routed through a *registered* key with inconsistent contents,
which the routing key makes impossible in production (defence-in-depth only, reachable
in tests via direct queue injection).

### Q4: `max_retries` reinterpretation and the schedule constant

**Constant (in `const.py`, mirroring `DISCOVERY_REBROADCAST_GAPS`):**

```python
# Photons-shaped gaps in seconds between successive request transmissions.
# The first gap is the floored first-attempt window (~200 ms — an acked bulb
# answers within 200 ms); after exhaustion the final gap repeats. Retransmits
# are capped by max_retries and by the caller's wall-time budget, whichever
# binds first.
REQUEST_RETRANSMIT_GAPS: Final[tuple[float, ...]] = (
    0.2, 0.3, 0.4, 0.5, 0.7, 0.9, 1.0, 2.0, 3.0, 4.0, 5.0
)
```

`[CITED: race.py PHOTONS_GAPS L61 — the exact expansion raced in spike 002 (1/180
failures across all loss rates)]`. Import into `connection.py` and **read the module
attribute at runtime** inside the helper so tests can
`patch("lifx.network.connection.REQUEST_RETRANSMIT_GAPS", (0.02, 0.03))` (Phase 2's
proven pattern, discovery.py L249-253).

**Natural schedule maths** (cumulative retransmit offsets: 0.2, 0.5, 0.9, 1.4, 2.1,
3.0, 4.0, 6.0, 9.0, 13.0, 18.0 s):

| Configuration | Transmissions | Last tx at | Then |
|---------------|--------------|------------|------|
| Defaults (`timeout=16.0`, `max_retries=8`) | 9 (= today's 9 attempts) | 6.0 s | listens ~10 s more, hard-stops at 16.0 s |
| `timeout=16.0`, uncapped | 11 | 13.0 s | schedule itself nearly fills the budget |
| `timeout=2.0`, `max_retries=3` | 4 | 0.9 s | listens to 2.0 s (matches existing test's "after 4 attempts") |
| `timeout=2.0`, `max_retries=2` | 3 | 0.5 s | matches existing test's "after 3 attempts" |
| any timeout, `max_retries=0` | 1 | 0 | pure single-shot with full-budget listen (same as today) |

**Interaction rule (document in the `max_retries` docstring):** `max_retries` caps the
number of *retransmits* after the initial send (total transmissions ≤ `max_retries + 1`,
same arithmetic as today's "attempts"); the wall deadline caps *time*. Whichever binds
first wins. After the retransmit cap, the request keeps listening until the wall
deadline — it does not fail early. The timeout error message reports transmissions
actually sent, which keeps the existing `"after N attempts"` assertions truthful.

**Sequence numbering:** sequence = transmission index (0, 1, 2, …) — identical to
today's `sequence = attempt`, so `len(correlation_keys)` remains the valid upper bound
for the sequence-range check. Sequence is uint8; the wall budget bounds transmissions to
~12 at defaults so wraparound is unreachable in practice. A caller passing an absurd
`timeout`+`max_retries` combination could exceed 255 — that failure mode exists in the
current code too (not a regression); if the planner wants belt-and-braces,
`sequence = tx_count & 0xFF` is branch-free (no coverage cost), and a duplicate dict key
merely re-registers the same shared queue (harmless, pop is idempotent).

### Anti-Patterns to Avoid

- **Blind sleeps of any kind** between transmissions — the entire point of D3-02. There
  is no `asyncio.sleep()` anywhere in the new loop.
- **Budget-excluded time**: no `total_sleep_time`-style bookkeeping survives. One
  deadline, computed once.
- **Per-attempt queues** (current ACK path): breaks late-reply acceptance (D3-04).
- **New source per retransmit**: responses to earlier transmissions would fail source
  validation. One source per logical request (L474 today — keep).
- **Retransmitting after the first response**: duplicates entire multi-response sets and
  wastes the packet budget RETRY-01 exists to fix.
- **Defensive `max(wait, ε)` clamps**: provably-positive operands; a clamp is an
  uncoverable branch → Codecov branch-patch failure (Phase 2 Pitfall 4, verified again
  here).
- **Renaming or re-signaturing `_request_stream_impl`/`_request_ack_stream_impl`**:
  they are the mock seam for 12+ existing tests.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Response routing/correlation | Any new matching logic | Existing `_background_receiver` + `(source, sequence, serial)` keyed `_pending_requests` (L350-433) | Already implements shared-queue fan-in, unmatched discard at DEBUG, and QueueFull protection |
| Late/duplicate reply discard | Explicit dedup in the request loop | The unmatched-response path (L404-416) after key cleanup | "Silently discarded, DEBUG at most" is exactly its current behaviour |
| Py3.10 timeout compat | `try/except asyncio.TimeoutError` branches | `TIMEOUT_ERRORS` tuple from `const.py` | Existing convention; avoids version-conditional branches in new code |
| Schedule expansion | Recomputing cumulative offsets | `next(gaps_iter, last_gap)` per-gap iteration | race.py's exact shape; per-gap (not cumulative) because each retransmit re-anchors at `time.monotonic()` after the send |
| Test response crafting | New builders | `LifxHeader(...)` construction pattern from `test_connection.py::TestRequestStreamDebugLogging._header` | Already builds valid headers with arbitrary source/sequence/target/pkt_type |

**Key insight:** the receiver architecture (background task, shared-queue correlation,
key lifecycle) already satisfies RETRY-04 for the GET path. This phase rewrites *when
packets are sent and how long the consumer waits* — not how responses are routed.

## Common Pitfalls

### Pitfall 1: Applying the retransmit timer after the first response

**What goes wrong:** multi-response streams (GetColorZones) receive a retransmit
mid-stream → device sends the whole zone set again → consumer yields duplicates.
**Why it happens:** forgetting the `not has_yielded` gate on step 3.
**How to avoid:** gate retransmits and the `next_tx_at` wait-cap on `not has_yielded`.
**Warning signs:** emulator multizone tests yield more responses than zones.

### Pitfall 2: Computing `wait` from a stale `now` after a send

**What goes wrong:** `send_packet` awaits; using the pre-send `now` for the queue-get
timeout overshoots the deadline or the next retransmit slot by the send latency.
**How to avoid:** `continue` after every send so the loop top re-reads `time.monotonic()`
(the illustrative loop does this; race.py re-reads via `time.perf_counter()` at L278).
**Warning signs:** wall-time test measures `timeout + n·ε` drift with many retransmits.

### Pitfall 3: Emulator drop-scenario tests now finish at ≈ `timeout` exactly

**What goes wrong (perceived):** timing assertions written for the old behaviour
(`elapsed > timeout + sleeps`) fail — correctly.
**Why:** D3-03 inverts the contract: failing requests complete in `timeout` wall time,
*faster* than before (a `timeout=2.0, max_retries=3` failure drops from ~2.7 s to
~2.0 s).
**How to avoid:** rewrite `test_retry_sleep_excluded_from_timeout_budget` as the
wall-time test (see Existing Test Impact); assert `timeout ≤ elapsed ≤ timeout + 0.3`.
**Warning signs:** the old test monkeypatches `_calculate_retry_sleep_with_jitter`,
which no longer exists — it fails at collection/setup, not silently.

### Pitfall 4: Sequence-range validation vs `len(correlation_keys)`

**What goes wrong:** if the helper appends keys anywhere other than immediately before
each send, `header.sequence >= len(correlation_keys)` (L611-617 semantics) rejects valid
in-flight responses or accepts never-issued sequences.
**How to avoid:** keep the register-then-send pairing atomic per transmission (no awaits
between append and the check being meaningful — the append happens before `send_packet`).
**Warning signs:** late-reply acceptance test (D3-04) raises `LifxProtocolError`.

### Pitfall 5: Hot loop with immediately-raising mocked queues

**What goes wrong:** a test that makes `wait_for` raise instantly (or injects
`wait <= 0`) spins the loop hot until the deadline.
**Why it happens:** `except TIMEOUT_ERRORS: continue` (correct in production where
`wait > 0` always) plus a mock that doesn't honour the requested timeout.
**How to avoid:** in tests, inject responses via `queue.put_nowait()` on the *real*
queue (grab it from `conn._pending_requests`) rather than mocking `wait_for`; keep
timeouts tiny so even a hot spin is bounded by pytest's 30 s timeout. (Same lesson as
Phase 2's quiet-receive note, 02-RESEARCH.md Code Examples.)

### Pitfall 6: In-scope docstring/comment rot

Found while reading `[VERIFIED: codebase]` — fix in this phase since the lines are being
touched anyway:
- `connection.py` L59: class docstring advertises "exponential backoff and jitter".
- `connection.py` L102: says `timeout` default is 8.0; `DEFAULT_REQUEST_TIMEOUT` is 16.0.
- `docs/api/network.md:132` and `docs/architecture/overview.md:136` repeat the
  "exponential backoff" claim — **docs pages are Phase 5 scope**; record in the phase
  summary as a handoff note rather than editing here (D3-06).
- Project `CLAUDE.md` mentions a `_request_lock` that no longer exists — out of scope,
  note for a housekeeping pass.

### Pitfall 7: Forgetting that `request_stream` never passes `max_retries`

**What goes wrong:** the `max_retries is None → self.max_retries` branch is the ONLY
path exercised by the public API (`request_stream` calls impls with `timeout` only,
L859-861/L905-907). If the helper re-implements the default resolution, the
`is not None` arm needs a direct-call unit test or it fails branch patch coverage.
**How to avoid:** the branch matrix below includes both arms explicitly (B2).

## Code Examples

Verified patterns for the test file (proposed: `tests/test_network/test_connection_retry.py`,
mirroring Phase 2's `test_discovery_rebroadcast.py`).

### Counting transmissions with a send spy (RETRY-01)

```python
# Pattern: wrap the real send_packet with a counting spy; unroutable TEST-NET IP
# means no responses ever arrive (or use the emulator for the healthy-path case).
send_count = 0
real_send = conn.send_packet

async def counting_send(*args: Any, **kwargs: Any) -> None:
    nonlocal send_count
    send_count += 1
    await real_send(*args, **kwargs)

with (
    patch.object(conn, "send_packet", side_effect=counting_send),
    patch("lifx.network.connection.REQUEST_RETRANSMIT_GAPS", (0.05, 0.05)),
):
    with pytest.raises(LifxTimeoutError, match="after 3 attempts"):
        await conn.request(Device.GetPower(), timeout=0.5)  # max_retries=2 on conn
assert send_count == 3   # tx at ~0, 0.05, 0.10; then listens to 0.5 s
```

Healthy-path zero-duplicate variant (emulator): same spy, real gaps, assert
`send_count == 1` — the emulator answers in ms, well inside the 0.2 s floor.

### Deterministic response injection (RETRY-02, RETRY-04, validation branches)

```python
# Start the request as a task, wait for the correlation key to register, then
# put a crafted response straight into the shared queue.
task = asyncio.create_task(conn.request(Device.GetPower(), timeout=2.0))
while not conn._pending_requests:
    await asyncio.sleep(0.001)
(key,) = conn._pending_requests.keys()          # (source, 0, serial)
source, seq, _ = key
header = LifxHeader(
    size=36 + 2, protocol=1024, source=source,
    target=bytes.fromhex("d073d5001234") + b"\x00\x00",
    tagged=False, ack_required=False, res_required=False,
    sequence=seq, pkt_type=22,                   # StatePower
)
conn._pending_requests[key].put_nowait((header, b"\x00\x00"))
response = await asyncio.wait_for(task, timeout=1.0)   # completes immediately
```

Late-reply variant (RETRY-04): patch gaps tiny so ≥2 transmissions happen, then inject
with `sequence=0` and assert acceptance. Mismatch variants: inject wrong `source` /
out-of-range `sequence` / wrong `target` and assert `LifxProtocolError` (these
defence-in-depth branches are only reachable via injection — that is expected).

### Wall-time budget assertion (RETRY-03)

```python
# Emulator drop-all scenario (existing fixture emulator_server_with_scenarios,
# "drop_packets": {"20": 1.0}); timeout=1.0, max_retries=8.
start = time.monotonic()
with pytest.raises(LifxTimeoutError):
    await conn.request(Device.GetPower(), timeout=1.0)
elapsed = time.monotonic() - start
assert 1.0 <= elapsed < 1.3    # wall budget honoured; generous CI tolerance
```

### Fast idle-exit test (stream semantics preserved)

```python
# _STREAM_IDLE_TIMEOUT must be a module attribute read at runtime:
with patch("lifx.network.connection._STREAM_IDLE_TIMEOUT", 0.05):
    # inject one response, then nothing → generator returns ~0.05 s later,
    # well before the wall deadline; assert exactly one yield, no raise.
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Exponential windows `(timeout/511)·2^n`, 31 ms first window | Escalating gaps, 200 ms floored first window | This phase (D3-01) | 1.37 → 1.0 packets/trial at zero loss `[VERIFIED: spike 002]` |
| Jittered blind sleeps between attempts (budget-excluded) | Retransmit-while-listening; no sleeps | This phase (D3-02/03) | Gen4 median 62 ms → ≈ RTT; 16 s budget never takes 29 s |
| ACK path: per-attempt queue, strict sequence match | Shared queue, any-issued-sequence accepted | This phase (D3-04) | Late ACKs complete the request instead of forcing another retransmit round |
| Duplicated retry arithmetic in two impls | One `_transmit_and_listen` helper | This phase (CONTEXT cleanup mandate) | Single engine to test; wrappers keep the mock seam |

**Deprecated/removed by this phase:** `_calculate_retry_sleep_with_jitter`,
`_RETRY_SLEEP_BASE`, `_DEFAULT_IDLE_TIMEOUT` (dead), `total_sleep_time` bookkeeping,
`import random`.

## Existing Test Impact (Question 5)

### Tests that assert the OLD behaviour — must change

All in `tests/test_network/test_concurrent_requests.py::TestRetryTimeoutBudget`
`[VERIFIED: read this session]`:

| Test | Why it breaks | Action |
|------|---------------|--------|
| `test_retry_sleep_excluded_from_timeout_budget` (L228-330) | Monkeypatches `_calculate_retry_sleep_with_jitter` (deleted); core assertions (`elapsed > timeout + sleeps`) assert the exact contract D3-03 inverts | **Replace** with the RETRY-03 wall-time test: drop-all scenario, `timeout=2.0, max_retries=3`, assert `2.0 ≤ elapsed < 2.3` and `"after 4 attempts"` (4 tx fit: 0, 0.2, 0.5, 0.9 s) |
| `test_retry_timeout_calculation_consistency` (L332-390) | Docstring/comments describe the exponential formula; `elapsed >= timeout` still holds but the test's *meaning* changes | **Update**: keep GET-vs-SET consistency assertion, add upper bounds (`elapsed_get/set ≤ timeout + 0.3`), reword docstring to "both paths honour the wall budget" |
| `test_retry_all_attempts_get_fair_timeout` (L392-434) | Asserts `"after 3 attempts"`; holds under the new schedule (timeout=2.0, max_retries=2 → 3 tx at 0, 0.2, 0.5 s) **only if** the error message reports transmissions sent | **Keep**, reword docstring; the class docstring (L220-226, describes the sleep-exclusion fix) must be rewritten |

### Tests that assert surviving contracts — pass unmodified

| File / test | Contract |
|-------------|----------|
| `test_concurrent_requests.py::TestConcurrentRequests::test_timeout_behavior` | `timeout=0.1, max_retries=0` → single tx, LifxTimeoutError ≈ 0.1 s |
| `test_concurrent_requests.py::TestErrorHandling::*` (drop scenarios, timeout isolation) | Timeout raised; concurrent request isolation |
| `test_concurrent_requests.py::TestAsyncGeneratorRequests::*` | Single-response streaming, `request()` wrapper, early-exit no-leak |
| `test_connection.py` — **entire file** | Mocks `_request_stream_impl`/`_request_ack_stream_impl` at the seam; unaffected iff names/signatures survive (locked above). Includes StateUnhandled emulator tests (GET yields packet, SET raises) — ack semantics preserved per D3-06 |
| `tests/conftest.py` fixtures (`timeout=2.0, max_retries=2`) | Healthy emulator answers inside the 0.2 s floor → 1 tx, marginally faster than today |
| `tests/test_api/test_api_batch_errors.py` (`max_retries=0`) | Single-shot semantics unchanged |
| `tests/test_devices/test_ceiling.py`, mdns `max_retries=5` passthrough | Constructor params only |

**Suite-wide timing effect:** failing-path tests get *faster* (wall ≈ timeout instead of
timeout + sleeps); healthy-path tests are unchanged or marginally faster. Nothing new
approaches pytest's 30 s timeout.

## Branch Coverage Matrix (Question 6)

Every new/changed branch in `connection.py`, with the test that hits each arm. Compound
conditions listed per-arm (Codecov counts branch partials). Tests marked (E) use the
emulator; (U) are offline unit tests in the new `test_connection_retry.py`.

| # | Branch (helper unless noted) | Arm | Test |
|---|------------------------------|-----|------|
| B1 | `timeout is None` default | pragma: no cover (kept, as today L467-468) | — |
| B2 | `max_retries is None` default | True: any public-API test (E); False: direct impl call with `max_retries=1` (U) | both |
| B3 | initial `max_retries > 0` → schedule armed | True: any retransmit test (U); False: `max_retries=0` single-tx (existing `test_timeout_behavior`) | both |
| B4 | `now >= deadline` | True + `has_yielded` → return: inject 1 response then quiet, tiny timeout, assert 1 yield no raise (U); True + not yielded → raise: drop-all wall-time test (E); False: every happy path | all three |
| B5 | `has_yielded and idle ≥ _STREAM_IDLE_TIMEOUT` | True → return: patched `_STREAM_IDLE_TIMEOUT=0.05`, 1 injected response (U); False-short-circuit (`has_yielded` False): any pre-response path; False (idle not elapsed): second injected response before idle (U) | all |
| B6 | retransmit-due compound: `next_tx_at is not None` | True: quiet + patched gaps → sends (U); False (post-cap): `max_retries=1`, quiet past cap, assert exactly 2 sends then listen (U); False (max_retries=0): B3 | all |
| B6a | … `and not has_yielded` | True: B6 sends; False: response injected while retransmits pending → no further sends (send spy, U) | both |
| B6b | … `and now >= next_tx_at` | True: B6; False: normal wait path (any test) | both |
| B7 | post-send cap `tx_count <= max_retries` | True: multi-retransmit test (≥2 gaps used, U); False: last allowed retransmit → `next_tx_at=None` (B6 cap test) | both |
| B8 | wait-cap `if next_tx_at is not None and not has_yielded` | mirrors B6/B6a arms — covered by the same tests | both |
| B9 | wait-cap `if has_yielded` (idle bound) | True: B5's second-response test; False: pre-response waits | both |
| B10 | `except TIMEOUT_ERRORS: continue` | Raised: any quiet slice (B6 tests); not raised: any injected/emulator response | both |
| B11 | `if not self._is_discovery` (serial validation) | True + target match: happy path (E); True + mismatch → `LifxProtocolError`: injected wrong-target header (U); False: discovery-serial conn (`"000000000000"`) accepts any target (U) | all |
| B12 | source mismatch → `LifxProtocolError` | Mismatch: injected wrong-source header (U); match: every accepted response | both |
| B13 | `header.sequence >= len(correlation_keys)` → `LifxProtocolError` | Out-of-range: injected `sequence=99` (U); in-range: happy path + late-reply test (`sequence=0` after 2 tx — the RETRY-04 acceptance case) (U) | both |
| B14 | ack wrapper: `pkt_type == _STATE_UNHANDLED_PKT_TYPE` | True: existing `test_set_color_raises_for_switch` (E); False: existing SET-ack emulator tests (E) | both |
| B15 | final raise (loop broke un-yielded) | Reached: B4 raise arm; not reached (return paths): B4/B5 return arms | both |
| B16 | gap-iterator exhaustion (`next(gaps, last_gap)` default) | Not a branch statement (default-arg expression) — exercise anyway: patched gaps `(0.01,)`, `max_retries=3` → 4 sends at ~0.01 spacing (U) | n/a |

Wrapper `_request_stream_impl`'s `async for … yield` and `_request_ack_stream_impl`'s
yield-True-return are straight-line except B14; the existing seam tests plus emulator
tests cover them.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The `"after N attempts"` message with N = transmissions-sent keeps the two surviving message assertions passing (3 tx and 4 tx computed from the schedule) | Q4, Test Impact | Low — arithmetic shown; if implementation registers sends differently the two tests fail loudly and the string is trivially adjusted |
| A2 | No consumer depends on failing requests taking *longer* than `timeout` (the old overrun) as a de-facto grace period | Q2 | Low — the overrun was undocumented and is the defect RETRY-03 targets |
| A3 | Photons' repeat-final-gap cap ("then every 5 s") matches upstream Photons | Q4 | Low — `[CITED: race.py L61/L282 spike replication]`; not re-read from Photons source this session; only matters for `max_retries > 10`, above the default |

All other claims are `[VERIFIED: codebase]` (connection.py, const.py, discovery.py,
utils.py, tests read line-by-line this session) or `[VERIFIED: spike 002 measured data]`.

## Open Questions

1. **Helper timeout signalling: raise inside the helper vs sentinel.**
   - What we know: the helper must produce different nouns for GET/ACK messages.
   - Recommendation: pass `timeout_noun` (shown above) — one raise site, no re-wrapping.
     Alternative (wrapper catches a generic `LifxTimeoutError` and re-raises with its
     message) adds a try/except and a branch for no benefit. Planner's call; both satisfy
     the requirements.
2. **Should `request_stream`'s hardcoded `timeout` resolution move too?** No — out of
   the request-path reshape's blast radius; `request_stream` L851-852 already resolves
   `timeout` before calling the impls, which is why the impls' `timeout is None` arms are
   pragma'd. Keep as-is.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `uv` + Python ≥3.10 | build/test | ✓ (repo standard) | per `uv.lock` | — |
| `lifx-emulator-core` (dev dep, embedded, drop-packet scenarios) | wall-time + retry emulator tests | ✓ via `uv sync` (`emulator_server_with_scenarios` fixture exists and is used by the current retry tests) | dev dependency | tests auto-skip if absent |
| Quiesced gen4 downlight 192.168.18.95 | optional hardware UAT (packets/trial at zero loss) | ✓ (user's network; spike 002 ran on it) | — | none — optional, human-executed |

**Missing dependencies with no fallback:** none for automated work. The optional
hardware validation (CONTEXT constraint) needs the user's network; model it as an
optional human-verify step, not a gate — CONTEXT marks it "optional", unlike Phase 2's
mandatory DISC-03.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (asyncio_mode=auto, pytest-cov `--cov-branch`, pytest-timeout 30 s) `[VERIFIED: pyproject.toml]` |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/test_network/test_connection.py tests/test_network/test_concurrent_requests.py -x` |
| Full suite command | `uv run --frozen pytest` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| RETRY-01 | Healthy network: exactly 1 transmission (send spy + emulator) | integration (emulator) | `uv run pytest tests/test_network/test_connection_retry.py -x` | ❌ Wave 0 |
| RETRY-01 | Escalating gaps: ≥3 sends at patched-gap spacing within window; first gap honoured (no send before 0.2 s on quiet net with real gaps) | unit | same file | ❌ Wave 0 |
| RETRY-02 | Injected response between retransmits completes immediately (elapsed ≪ timeout); no further sends after response | unit | same file | ❌ Wave 0 |
| RETRY-03 | Drop-all: `timeout ≤ elapsed < timeout + 0.3` for GET and SET | integration (emulator) | rewritten `TestRetryTimeoutBudget` in `test_concurrent_requests.py` | ✅ (rewrite) |
| RETRY-04 | Late reply to sequence 0 accepted after retransmit 1 issued (GET and ACK paths); mismatch injections raise `LifxProtocolError`; post-cleanup late reply logged at DEBUG + discarded (caplog on `_background_receiver` unmatched path) | unit | `test_connection_retry.py` | ❌ Wave 0 |
| RETRY-01..04 regression | Existing seam/emulator/device tests pass unmodified | all | `uv run --frozen pytest` | ✅ (existing) |
| Optional hardware | Zero-loss packets/trial = 1.0 on gen4 downlight | manual-only (hardware, optional per CONTEXT) | small harness: N `request(GetColor())` calls with the send spy against 192.168.18.95 | ❌ optional |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/test_network/ -x` plus
  `uv run ruff format . && uv run ruff check . --fix && uv run pyright`
- **Per wave merge:** `uv run --frozen pytest`
- **Phase gate:** full suite green + Codecov **branch** patch = 100% before
  `/gsd-verify-work` (check branch partials on the compound conditions B6/B8/B11)

### Wave 0 Gaps

- [ ] `tests/test_network/test_connection_retry.py` — covers RETRY-01/02/04 + branch
  matrix rows B2-B13, B15-B16 (send-spy, queue-injection, patched
  `REQUEST_RETRANSMIT_GAPS` / `_STREAM_IDLE_TIMEOUT` patterns from Code Examples)
- [ ] Rewrite of `TestRetryTimeoutBudget` (3 tests + class docstring) in
  `tests/test_network/test_concurrent_requests.py` — RETRY-03

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | LIFX LAN protocol is unauthenticated by design |
| V4 Access Control | no | — |
| V5 Input Validation | yes | Existing (kept verbatim): serial/source/sequence-range validation on every accepted response; packet-size limits in transport; unmatched responses discarded |
| V6 Cryptography | no | — |

### Known Threat Patterns for this change

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Response flood into the shared queue | DoS | Bounded queue (maxsize=100) with QueueFull warning in `_background_receiver` (unchanged); wall deadline hard-caps request lifetime |
| Spoofed responses to retransmit sequences | Spoofing | Same three-way validation for every issued sequence; routing key requires knowing (source, sequence, serial) — source is per-request random (`secrets.randbelow`) |
| Self-inflicted retransmit load | DoS (outbound) | Escalating gaps + `max_retries` cap + stop-on-first-response: worst case 9 packets/request at defaults vs today's 9 — and 1 vs 1.37 on healthy networks `[VERIFIED: spike 002]` |

## Sources

### Primary (HIGH confidence)

- Codebase, read line-by-line this session: `src/lifx/network/connection.py` (full),
  `src/lifx/const.py`, `src/lifx/network/discovery.py` (Phase 2 interleave, L249-304),
  `src/lifx/network/utils.py` (IdleDeadline, allocate_source),
  `tests/test_network/test_connection.py`, `tests/test_network/test_concurrent_requests.py`,
  `tests/conftest.py`, `pyproject.toml`
- Spike 002 measured data + working reference: `.claude/skills/spike-findings-lifx-async/sources/002-retry-storm-vs-fresh-deadline/race.py`
  (`regime_photons()` L248-283; `PHOTONS_GAPS` L61), 540-trial results in
  `references/retry-schedule.md`
- Spike blueprint: `.claude/skills/spike-findings-lifx-async/references/retry-schedule.md`
- Phase 2 shipped pattern + research: `.planning/phases/02-discovery-rebroadcast/02-RESEARCH.md`,
  `DISCOVERY_REBROADCAST_GAPS` in `const.py` L36-39

### Secondary (MEDIUM confidence)

- Photons upstream retry gaps ("0.2, 0.3, … then every 5 s") — cited via the spike's
  source reading of `photons_transport/targets/__init__.py`, not re-fetched this session
  `[CITED: race.py docstring L13-15]`

### Tertiary (LOW confidence)

- None.

## Metadata

**Confidence breakdown:**

- Edit points / current control flow: HIGH — both impls read line-by-line this session
- Reshaped loop design: HIGH — direct adaptation of `regime_photons()` (raced on real
  hardware, 1/180 failures) and Phase 2's shipped, tested interleave
- Unification shape: HIGH — mock-seam constraint verified against every patching test;
  behavioural-difference table drawn from the code, not memory
- Test impact / branch matrix: HIGH — every affected test read; matrix maps each arm to
  a concrete technique already proven in this repo (Phase 2 or existing tests)

**Research date:** 2026-07-16
**Valid until:** stable (internal codebase; re-verify connection.py line numbers if it
changes before planning)
