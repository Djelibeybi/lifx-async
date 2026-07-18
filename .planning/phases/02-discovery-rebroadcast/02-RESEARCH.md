# Phase 2: Discovery Re-broadcast - Research

**Researched:** 2026-07-16
**Domain:** UDP broadcast discovery scheduling inside an existing asyncio receive loop (internal codebase change; no external dependencies)
**Confidence:** HIGH

## Summary

Phase 2 adds an escalating re-broadcast schedule to `_discover_with_packet()` in
`src/lifx/network/discovery.py`. Today the generator sends exactly one `GetService`
broadcast (line 233) then only listens; on the 73-device multi-AP production fleet this
yields a median of 48/73 devices per round (min 27) because broadcast delivery to WiFi
clients is per-AP best-effort `[VERIFIED: spike 005 summary-20260716-211339.json]`. The
fix is a send/receive interleave proven working in the spike harness
(`sweep.py::run_round()`): track the next scheduled send time, cap the receive timeout at
`min(deadline.remaining(), time-to-next-send)`, send when due, and — critically — change
the `except LifxTimeoutError: break` at discovery.py:266-267 to `continue` so a
receive-slice timeout re-enters the loop (the top-of-loop idle/overall expiry checks
still provide every exit) `[VERIFIED: codebase + sweep.py]`.

Everything else is preservation work: serial validation, first-wins dedup, and
IdleDeadline semantics stay byte-for-byte identical, and the dedup already absorbs the
~2× duplicate responses per broadcast (D2-02). The schedule lives as one new constant in
`const.py` (`DISCOVERY_REBROADCAST_GAPS`), referenced at generator runtime (not as a
def-time default) so tests can patch it for fast schedule-exhaustion coverage. Public
API is unchanged; all callers of the shared generator (`discover_devices`,
`find_by_label`, and transitively `find_by_serial`/`find_by_ip`) get re-broadcast
uniformly — early-exit callers close the generator on first yield, so targeted lookups
pay nothing on the happy path.

**Primary recommendation:** Implement the sweep.py `run_round()` interleave inside
`_discover_with_packet()` with a cumulative-offset iterator anchored at `request_time`,
change the receive-timeout `break` to `continue`, add `DISCOVERY_REBROADCAST_GAPS =
(0.6, 1.2, 1.8, 2.0, 2.0)` to `const.py`, and never call `mark_response()` on a send.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D2-01**: Re-broadcast `GetService` inside `_discover_with_packet()`'s receive loop on
  a Photons-shaped escalating schedule; gaps ≈ 0.6, 1.2, 1.8, 2.0, 2.0 s from first send,
  capped by the discovery window. Working interleave pattern:
  `spike-findings-lifx-async/sources/005-discovery-regimes/sweep.py` (`run_round()`).
- **D2-02**: Preserve everything from the Phase 1 rework unchanged: serial validation,
  first-wins per-serial dedup (D-04), IdleDeadline semantics, thin `discover_devices()`
  wrapper. The dedup already absorbs duplicate responses to later broadcasts.
- **D2-03**: Public API unchanged — no new parameters required for the default behaviour;
  existing callers benefit transparently. (If the planner finds a schedule constant worth
  exposing, module-level constants in `const.py` are the pattern, not new kwargs.)
- **D2-04**: Applies to UDP broadcast discovery only; mDNS path untouched (Out of Scope).

### Claude's Discretion

(No explicit discretion section in CONTEXT.md — implementation details within the locked
decisions above are at the planner's discretion, e.g. constant naming, test structure,
and whether targeted/unicast callers share the schedule.)

### Deferred Ideas (OUT OF SCOPE)

- mDNS discovery path (D2-04).
- Unicast request retries — Phase 3 (Retry Schedule Reshape, `connection.py`).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DISC-01 | `discover_devices()` re-broadcasts `GetService` on an escalating schedule (Photons-shaped gaps) within the discovery window, preserving serial validation and first-wins dedup | Concrete edit points mapped in "Architecture Patterns"; schedule constant design in "Standard Stack"; interleave pattern verified in `sweep.py::run_round()` |
| DISC-02 | Duplicate `StateService` responses (~2× per broadcast, multiplied by re-broadcasts) never cause duplicate device yields | Existing first-wins dedup at discovery.py:391-393 already enforces this at the shared generator; test strategy adds duplicate-across-broadcast cases (see "Validation Architecture") |
| DISC-03 | Hardware validation over repeated rounds: median per-round coverage of the production fleet equals full coverage (baseline 48/73) | UAT tooling section: 6-round harness invocation; recorded baseline at `.planning/spikes/005-discovery-regimes/summary-20260716-211339.json` |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- Zero runtime dependencies — this phase must add none (it doesn't need any).
- All imports at top of file (`Iterator` from `collections.abc` if needed for typing).
- `uv` exclusively; run tests via `uv run --frozen pytest`; `uv run ruff format/check`;
  `uv run pyright` (strict).
- Commits: `git commit -s`, GPG-signed.
- Never edit generated protocol files (this phase touches none).
- CI requires 100% **branch** patch coverage (project memory: check branch partials, not
  just diff-cover lines) — avoid defensive clamps that create unreachable branches.
- Australian English spelling in comments/docstrings.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Re-broadcast scheduling | Network layer (`network/discovery.py::_discover_with_packet`) | — | D2-01 locks the schedule inside the shared generator's receive loop; all callers benefit transparently |
| Schedule constants | `const.py` | — | D2-03: module-level constants, not kwargs; matches `DISCOVERY_TIMEOUT`/`IDLE_TIMEOUT_MULTIPLIER` pattern |
| Dedup / serial validation | Network layer (unchanged) | — | Already hoisted into `_discover_with_packet` in Phase 1 (D-04, D-11) — preserve, don't touch |
| Idle/overall deadline | `network/utils.py::IdleDeadline` (unchanged) | — | No changes needed; the loop composes the send timer with `remaining()` — IdleDeadline itself stays generic |
| Hardware UAT measurement | Tooling (phase-dir script / spike harness) | — | Emulator can't model per-AP loss; measurement runs against the production fleet |

## Standard Stack

### Core

No new libraries. This is stdlib-only work inside an existing zero-dependency module
`[VERIFIED: codebase — pyproject.toml has no runtime deps]`.

| Component | Version | Purpose | Why Standard |
|-----------|---------|---------|--------------|
| `time.monotonic()` | stdlib | Schedule anchor + deadline math | Codebase-wide convention; `IdleDeadline` documents "monotonic exclusively" (`utils.py:28-29`). Do NOT use `time.perf_counter()` even though sweep.py did — the production module uses `monotonic` throughout |
| `asyncio` via `UdpTransport.receive(timeout=...)` | stdlib | Bounded receive slices | Existing transport already provides per-call timeout (`transport.py:218`) — no new asyncio primitives needed |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Timer folded into receive-timeout computation (recommended) | Separate `asyncio.Task` sending on a schedule | A background task needs cancellation on every generator exit path (GeneratorExit, exceptions, deadline expiry) and introduces send/receive races on the shared transport; the fold-in approach is single-coroutine, matches sweep.py's proven pattern, and is trivially branch-coverable |
| Module constant read at runtime | Parameter on `_discover_with_packet` with constant default | Def-time default binding would make the constant unpatchable in tests and edges toward new kwargs (against D2-03 spirit). Runtime read of the module attribute keeps tests fast via `patch("lifx.network.discovery.DISCOVERY_REBROADCAST_GAPS", ...)` |

**Installation:** none.

## Package Legitimacy Audit

No external packages are installed by this phase. **Packages removed:** none.
**Packages flagged:** none.

## Architecture Patterns

### System Architecture Diagram

```
discover() / find_by_serial() ──▶ discover_devices() ──┐
find_by_ip() (unicast addr) ───▶ discover_devices() ──┤
find_by_label() ───────────────────────────────────────┤
                                                        ▼
                            _discover_with_packet(packet, timeout, ...)
                                                        │
                    ┌───────────────────────────────────┤
                    │  t=0: send #1 (existing L233)     │
                    ▼                                   ▼
        ┌─── receive loop (while True) ────────────────────────────────┐
        │ 1. idle_expired? ──▶ exit          2. overall_expired? ──▶ exit
        │ 3. while next_tx due: transport.send(message) ◀── NEW (DISC-01)
        │ 4. remaining = deadline.remaining(); <=0 ──▶ exit
        │ 5. slice = min(remaining, time_to_next_tx)   ◀── NEW
        │ 6. transport.receive(timeout=slice)
        │      timeout ──▶ continue (was break)        ◀── NEW (critical)
        │ 7. source check → pkt_type check → serial validation
        │ 8. mark_response() → first-wins dedup → yield ◀── UNCHANGED (DISC-02)
        └────────────────────────────────────────────────────────────────┘
```

Data flow: re-broadcasts re-enter at step 3; duplicate responses they provoke flow
through steps 7-8 where the existing `seen_serials` set suppresses re-yields.

### Concrete Edit Points (Question 1)

All in `src/lifx/network/discovery.py`, current line numbers `[VERIFIED: codebase]`:

| Location | Edit |
|----------|------|
| L11-18 (imports) | Add `DISCOVERY_REBROADCAST_GAPS` to the `from lifx.const import (...)` block. It becomes a module attribute of `lifx.network.discovery`, patchable in tests |
| L221 `request_time = time.monotonic()` | Keep — this is the schedule anchor (t=0) as well as the `response_time` anchor |
| L233 `await transport.send(...)` | Keep — first broadcast at t=0 |
| After L236 (deadline construction) | Build the cumulative-offset iterator **inside the generator body** (runtime read of the module constant): expand gaps `(0.6, 1.2, 1.8, 2.0, 2.0)` to offsets `0.6, 1.8, 3.6, 5.6, 7.6`; `next_tx: float \| None = <first offset>` |
| Top of `while True`, after the `idle_expired`/`overall_expired` checks (L238-257) and **before** L259 | Insert the due-send loop: `now = time.monotonic()`; `while next_tx is not None and now - request_time >= next_tx: await transport.send(message, (broadcast_address, port)); <debug log>; next_tx = next(tx_iter, None); now = time.monotonic()` |
| L259-261 (`remaining = deadline.remaining(); if remaining <= 0: break`) | Keep exactly as-is (a mocked-deadline test, `TestRemainingNonPositiveGuard`, asserts receive is never called when this fires) |
| Between L261 and L264 | Cap the receive slice: `if next_tx is not None: remaining = min(remaining, request_time + next_tx - now)`. Both operands are strictly positive here (deadline checked above; the due-send loop guarantees `request_time + next_tx > now`), so **no clamp is needed** — adding `max(x, 0.001)` would create an uncoverable branch and break the 100% branch patch gate |
| L266-267 `except LifxTimeoutError: break` | **Change `break` to `continue`.** This is the single most important edit: a receive timeout now means "slice ended — maybe time to re-broadcast", not "discovery over". The top-of-loop expiry checks still terminate the loop on idle/overall deadline. sweep.py uses exactly this shape (`sweep.py:135-136`) |
| L222-232 debug log | Optionally add a `rebroadcast_sent` debug log (with cumulative offset / attempt index) inside the due-send loop, mirroring the existing structured-dict logging style |
| L449-455 / L160-198 docstrings | Update `discover_devices` ("Sends a broadcast DeviceGetService packet…") and `_discover_with_packet` ("Broadcasts the specified packet…") to describe the escalating re-broadcast schedule |

**Reuse the existing `message` object for every re-send.** Same `source`, same
`sequence=0` — response correlation in discovery is source-based (L287), so allocating a
new source per re-send would cause the source-validation guard to reject responses to
earlier broadcasts. sweep.py confirms one message reused across all sends works against
the real fleet `[VERIFIED: sweep.py:112-127 + spike results]`.

### Pattern 1: Send/receive interleave (from sweep.py `run_round()`)

**What:** Fold the send schedule into the receive-timeout computation so one coroutine
does everything. **When to use:** exactly this phase.

```python
# Source: .claude/skills/spike-findings-lifx-async/sources/005-discovery-regimes/sweep.py
# (adapted: perf_counter → monotonic, window → IdleDeadline)
next_tx = iter(schedule)
pending_tx: float | None = next(next_tx)
while True:
    now = time.perf_counter() - start
    if now >= window:
        break
    while pending_tx is not None and now >= pending_tx:
        await transport.send(message, (BROADCAST, LIFX_PORT))
        pending_tx = next(next_tx, None)
        now = time.perf_counter() - start
    wait = min(
        pending_tx - now if pending_tx is not None else window - now,
        window - now,
    )
    try:
        data, addr = await transport.receive(timeout=max(wait, 0.001))
    except LifxTimeoutError:
        continue
```

Production adaptation differences: use `time.monotonic()`, keep the existing
`IdleDeadline` checks as the loop exits, keep the existing `remaining <= 0` defensive
break, and drop the `max(wait, 0.001)` clamp (provably positive operands — see edit
table).

### Pattern 2: IdleDeadline interaction (Question 2)

**Do not call `deadline.mark_response()` on send.** Only received valid protocol
responses reset the idle clock (current contract at L356 and L388). Rationale
`[VERIFIED: codebase analysis + spike doc]`:

- The spike blueprint states re-broadcasts "reset the effective idle window *naturally*
  since responses keep arriving" — via the responses, not the sends.
- Empty-network behaviour is preserved: with defaults (idle = 4.0 s), discovery on a
  silent network exits at ~4.0 s exactly as today — it just sends 4 packets (t=0, 0.6,
  1.8, 3.6) instead of 1 before giving up.
- Callers passing tiny timeouts keep their semantics: `timeout=0.1` sends only the t=0
  broadcast (first gap 0.6 > window); `idle_timeout_multiplier=0.0` exits immediately.
  Existing tests `test_discovery_timeout_scenario`, `test_discovery_idle_timeout_branch`,
  `test_discovery_overall_timeout_branch` should pass unmodified — treat them as the
  regression gate for this question.
- The overall deadline caps everything: the due-send loop sits *after* the expiry checks,
  so no send ever happens once either deadline has fired.

### Pattern 3: Uniform behaviour for all callers (Question 5)

Re-broadcast lives in `_discover_with_packet()` with **no branching by caller or
address**. Consequences, all acceptable or beneficial `[VERIFIED: codebase]`:

- `find_by_ip` (api.py:903, passes the target IP as `broadcast_address`): the unicast
  `GetService` now re-sends on the schedule too. If the device answers the first send,
  the caller `return`s on first yield → generator closed (GeneratorExit) → no further
  sends. If the first packet is lost, a re-send recovers it — a free reliability win.
- `find_by_serial` (api.py:850): iterates `discover_devices` until match; benefits
  directly from fleet-wide coverage.
- `find_by_label` (api.py:955): broadcasts `GetLabel` — re-sends apply identically; the
  StateLabel dedup path is the same code.
- Phase 3 (retry reshape) covers `DeviceConnection.request()` in `connection.py` — a
  disjoint code path. Nothing here overlaps with it; there is no "leave unicast to
  Phase 3" carve-out needed because targeted *discovery* never goes through
  `connection.py`.

### Anti-Patterns to Avoid

- **Background sender task:** cancellation/cleanup complexity on every generator exit
  path for zero benefit over the interleave (see Alternatives Considered).
- **`mark_response()` on send:** would defeat idle early-exit on quiet networks.
- **New source or incremented sequence per re-send:** breaks source validation for
  responses to earlier sends (source) or does nothing useful (sequence — discovery never
  checks it).
- **Gaps as a def-time default argument:** freezes the constant at import; tests can't
  patch it and slow to 7.6 s+ per schedule-exhaustion case.
- **Glowup-style 0.5 s hammer:** locked out by D2-01; provokes ~2,100 responses/round for
  the same coverage Photons gets at ~615 `[VERIFIED: spike 005 measurements]`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Dual idle/overall deadline math | New timer logic | Existing `IdleDeadline` (`network/utils.py:19`) unchanged | Already tested, monotonic-safe, and its `remaining()` is designed to be composed via `min()` with other bounds |
| Duplicate suppression | Any new tracking | Existing `seen_serials` first-wins set (discovery.py:391-393) | D2-02 locks it; already proven at generator level by `test_first_wins_dedup_at_generator` |
| Response crafting in tests | New packet builders | `_build_state_service_packet()` helper (test_discovery_errors.py:96) | Exact wire-format StateService bytes with controllable source/target/service/port |
| Transport mocking | New fixtures | `patch("lifx.network.discovery.UdpTransport")` AsyncMock pattern, or the `_PreloadedTransport` real-transport subclass (test_discovery_errors.py:332-358) | Both patterns are established in this exact test module |

**Key insight:** Phase 1 already hoisted every hard invariant (validation, dedup, idle
semantics) into the shared generator. This phase only threads a send timer through the
existing loop — the smaller the diff, the safer the invariants.

## Common Pitfalls

### Pitfall 1: Leaving `except LifxTimeoutError: break` as `break`

**What goes wrong:** The first quiet receive slice that ends at a re-broadcast boundary
terminates discovery — re-broadcasts after the first quiet gap never happen; on a quiet
start you get exactly today's single-broadcast behaviour.
**Why it happens:** Today a receive timeout can only mean a deadline fired (the slice
*is* `deadline.remaining()`), so `break` was correct. With capped slices it usually means
"time to send again".
**How to avoid:** `continue`; the top-of-loop expiry checks are the sole exit authority.
**Warning signs:** Tests asserting ≥2 sends on a quiet network fail; hardware UAT shows
no improvement over baseline.

### Pitfall 2: Discovery wall time grows on populated networks — by design

**What goes wrong (perceived):** Default `discover_devices()` today typically returns in
~5 s (responses within ~1 s + 4 s idle). With the full schedule (last send at t=7.6 s)
each re-broadcast provokes fresh duplicate responses that legitimately reset the idle
clock, so a populated network typically runs to ~11.6 s (7.6 + ~4 s idle), still under
`DISCOVERY_TIMEOUT` (15 s).
**Why it happens:** Using the whole window is precisely how coverage improves — devices
behind a lossy AP only answer a later broadcast.
**How to avoid:** Nothing to fix; document it in the `discover_devices` docstring so the
change in typical latency is expected. Streaming consumers (`async for`) see first
devices at the same latency as today — only generator *completion* moves later.
**Warning signs:** A reviewer flags "discovery got slower" — point at DISC-03 and this
note.

### Pitfall 3: Def-time binding of the schedule constant

**What goes wrong:** `def _discover_with_packet(..., gaps=DISCOVERY_REBROADCAST_GAPS)`
binds the tuple at import; `patch("lifx.network.discovery.DISCOVERY_REBROADCAST_GAPS", …)`
has no effect and schedule-exhaustion tests must really wait 7.6 s+ (pytest `--timeout=30`
pressure, slow CI).
**How to avoid:** Read the module-level name inside the generator body when building the
offsets iterator.
**Warning signs:** Patched-gap tests still take multiple seconds or assert wrong send
counts.

### Pitfall 4: Dead branches from defensive clamps

**What goes wrong:** `max(slice, 0.001)` or an extra `if slice <= 0` guard is
unreachable (both slice operands are provably positive at that point), and Codecov's
100% **branch** patch gate fails on the never-taken branch.
**How to avoid:** Rely on the proof: `remaining > 0` is checked at L260-261, and the
due-send loop exits only when `request_time + next_tx - now > 0`.
**Warning signs:** Codecov branch partials on the new lines
`[VERIFIED: project memory — check branch partials, not just diff-cover lines]`.

### Pitfall 5: `response_time` anchor ambiguity

**What goes wrong:** `response_time = response_timestamp - request_time` (L371) is
anchored at the *first* send. Devices answering a later broadcast report inflated
"response times" (e.g. 3.7 s for a device that answered the t=3.6 s broadcast in 100 ms).
**How to avoid (recommendation):** Keep the anchor unchanged — it's an informational
field meaning "time since discovery began", and re-anchoring per send would mis-attribute
responses that answer an *earlier* broadcast after a later send. Add one docstring
sentence to `DiscoveredDevice.response_time` / `DiscoveryResponse.response_time` noting
the anchor. Changing semantics here is a needless behaviour change for existing users.
**Warning signs:** A test asserting `response_time < 1.0`
(`test_discover_devices_response_time_accuracy`, timeout=1.0 window) — safe with a 1.0 s
window (only sends at 0 and 0.6 fit, and localhost emulator answers the t=0 send), but
don't tighten that assertion.

### Pitfall 6: Emulator tests now trigger multiple broadcasts

**What goes wrong:** Existing emulator tests use `timeout=1.0–2.0` windows against
127.0.0.1 — they will now send 2–3 `GetService` packets and receive 2–3× the responses.
The dedup absorbs them (each serial still yielded once), but any future test asserting
raw response counts would break.
**How to avoid:** No existing test asserts send or raw-response counts against the
emulator `[VERIFIED: grep of tests/test_network/ and tests/test_api/]`. Keep it that way:
assert send timing via mocked transports only.

## Code Examples

### Recording sends with timestamps in a mocked transport (Question 4)

```python
# Source: adapted from tests/test_network/test_discovery_errors.py existing pattern
send_times: list[float] = []

async def recording_send(data: bytes, address: tuple[str, int]) -> None:
    send_times.append(time.monotonic())

async def quiet_receive(timeout: float = 2.0):
    await asyncio.sleep(timeout)          # honour the requested slice
    raise LifxTimeoutError("timeout")

with (
    patch("lifx.network.discovery.UdpTransport") as mock_transport_cls,
    patch("lifx.network.discovery.allocate_source", return_value=42),
):
    mock_transport = AsyncMock()
    mock_transport.__aenter__ = AsyncMock(return_value=mock_transport)
    mock_transport.__aexit__ = AsyncMock(return_value=False)
    mock_transport.send = recording_send
    mock_transport.receive = quiet_receive
    mock_transport_cls.return_value = mock_transport

    _ = [d async for d in discover_devices(timeout=1.0)]

# Window 1.0 s ⇒ sends at t=0 and t≈0.6 only (next offset 1.8 > window).
assert len(send_times) == 2
assert 0.4 <= (send_times[1] - send_times[0]) <= 0.9   # ≈0.6 with CI tolerance
```

Note: the existing tests' `quiet` mocks raise `LifxTimeoutError` *immediately* without
sleeping — that was fine when timeout meant `break`, but with `continue` an
instantly-raising receive spins the loop hot until a deadline fires. For quiet-network
tests either sleep for the requested slice (above) or keep windows tiny. Existing tests
that raise immediately (`test_wrong_source_id_rejected` etc.) still terminate correctly
— the loop busy-polls only until idle/overall expiry, which their 0.5 s timeouts bound —
but the planner should sanity-check none of them exceed pytest's 30 s timeout. With
`timeout=0.5` and default idle 4.0 s, the overall deadline fires at 0.5 s: bounded, fine.

### Fast schedule-exhaustion test via patched gaps

```python
# Requires the implementation to read the constant at runtime (Pitfall 3).
with patch("lifx.network.discovery.DISCOVERY_REBROADCAST_GAPS", (0.02, 0.02)):
    # window 0.5 s >> total schedule 0.04 s ⇒ all 3 sends (t=0, .02, .04) happen,
    # iterator exhausts (next_tx is None branch), receive slice falls back to
    # deadline.remaining().
    ...
```

### Dedup across re-broadcasts (DISC-02 at generator level)

Extend the existing `test_first_wins_dedup_at_generator` pattern: a `mock_receive` that
returns the same-serial `_build_state_service_packet(...)` twice with an
`await asyncio.sleep(...)` spanning a patched send offset between them, then assert one
yield and ≥2 recorded sends. This proves dedup and re-broadcast interleave together.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single `GetService` broadcast, listen-only (discovery.py:233) | Escalating re-broadcast (0.6/1.2/1.8/2.0/2.0 gaps), capped by window | This phase | Median fleet coverage 48/73 → target 73/73 `[VERIFIED: spike 005]` |
| `except LifxTimeoutError: break` | `continue` (deadline checks own the exits) | This phase | Receive-slice timeouts no longer end discovery |
| Photons reference schedule `timeouts=[(0.6,1.8),(1,2),(2,6),(4,10),(5,20)]` | First five gaps only (0.6, 1.2, 1.8, 2.0, 2.0) — later gaps exceed the 15 s default window anyway | Locked in D2-01 | 6 sends max per discovery (t=0 + 5 offsets, last at 7.6 s) `[CITED: sweep.py:69-79 expansion of Photons session/network.py]` |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Typical populated-network completion moves from ~5 s to ~11.6 s (reasoned from schedule + idle window; not yet measured end-to-end) | Pitfall 2 | Low — only affects docstring wording; hardware UAT will produce the real number |
| A2 | No consumer depends on `discover_devices()` completing in under ~12 s with default arguments | Pitfall 2 | Low — callers wanting faster completion already pass smaller `timeout`; streaming consumers see first yields at unchanged latency |

All other claims are `[VERIFIED: codebase]` or `[VERIFIED: spike 005 measured data]`.

## Open Questions (RESOLVED)

1. **Should the `response_time` anchor change?**
   - What we know: anchored at first send (L371); re-broadcasts inflate it for
     late-answering devices.
   - What's unclear: whether any consumer treats it as per-packet RTT.
   - Recommendation: keep unchanged, document the anchor (Pitfall 5). Flag in the plan as
     a one-line docstring task, not a behaviour change.

2. **Emulator-visible send counting for the ROADMAP wording "observable in emulator
   tests as multiple broadcasts at the expected gaps".**
   - What we know: emulator tests use the real transport; there's no hook to count
     outbound datagrams without new plumbing. CONTEXT.md refines this to "automated tests
     cover schedule mechanics" — the mocked-transport timing tests satisfy the intent.
   - Recommendation: assert send times via mocked transports (unit tests); use emulator
     tests for dedup-under-rebroadcast (DISC-02) only. If a literal emulator observation
     is wanted, the `_PreloadedTransport`-style subclass with a recording `send()` is the
     cheapest bridge — still no production plumbing.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `uv` + Python ≥3.10 | build/test | ✓ (repo standard) | per `uv.lock` | — |
| `lifx-emulator-core` (dev dep, embedded) | `@pytest.mark.emulator` tests | ✓ via `uv sync` | dev dependency | tests auto-skip if absent |
| 73-device production fleet on multi-AP LAN | DISC-03 hardware UAT | ✓ (user's network; spike 005 ran on it 2026-07-16) | — | none — UAT is a human-executed checkpoint, not CI |

**Missing dependencies with no fallback:** none for automated work. DISC-03 requires the
user to run the UAT harness on the production network (plan should model this as a
human-verify checkpoint).

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (asyncio_mode=auto, pytest-cov with `--cov-branch`, pytest-timeout 30 s) `[VERIFIED: pyproject.toml:95-114]` |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/test_network/test_discovery_errors.py tests/test_network/test_discovery_devices.py -x` |
| Full suite command | `uv run --frozen pytest` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DISC-01 | ≥2 sends at ≈0.6 s gap within a 1.0 s window (real gaps, mocked transport) | unit | `uv run pytest tests/test_network/test_discovery_rebroadcast.py -x` | ❌ Wave 0 |
| DISC-01 | Schedule capped by window (timeout=0.3 ⇒ exactly 1 send) | unit | same file | ❌ Wave 0 |
| DISC-01 | Schedule exhaustion → receive slice falls back to `deadline.remaining()` (patched tiny gaps) | unit | same file | ❌ Wave 0 |
| DISC-01 | Receive timeout mid-window continues (re-broadcast after a quiet slice), then exits via idle AND via overall deadline (both exit branches) | unit | same file | ❌ Wave 0 |
| DISC-01 | Multiple sends due in one loop pass (mock receive sleeps past ≥2 patched offsets) | unit | same file | ❌ Wave 0 |
| DISC-01 | No `mark_response()` on send: quiet network exits at idle deadline (~wall-time assert) despite sends inside the window | unit | same file | ❌ Wave 0 |
| DISC-02 | Same-serial responses across two broadcasts yield once | unit | same file (extends `test_first_wins_dedup_at_generator` pattern) | ❌ Wave 0 |
| DISC-02 | Emulator: every serial yielded once with a ≥2-broadcast window | integration (emulator) | existing `test_devices_deduplicated_by_serial` (timeout=1.5 now spans 2 sends) + optionally one with timeout=2.0 | ✅ (existing) |
| DISC-01/02 regression | Existing timeout/idle/validation/dedup tests pass unmodified | unit | `uv run pytest tests/test_network/ -x` | ✅ (existing) |
| DISC-03 | 6-round median fleet coverage == full roster | manual-only (hardware) | UAT harness below — emulator cannot model per-AP broadcast loss `[VERIFIED: CONTEXT.md constraint]` | ❌ Wave 0 (harness script) |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/test_network/ -x` plus
  `uv run ruff format . && uv run ruff check . --fix && uv run pyright`
- **Per wave merge:** `uv run --frozen pytest`
- **Phase gate:** full suite green + Codecov branch patch = 100% before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_network/test_discovery_rebroadcast.py` — covers DISC-01, DISC-02
  (mocked-transport send-timing, patched-gap, dedup-across-broadcast tests; reuse
  `_build_state_service_packet` — either import from `test_discovery_errors` or lift into
  a shared helper)
- [ ] UAT harness for DISC-03 (see below) — a script, not a pytest test

### DISC-03 UAT Tooling (Question 6)

`sweep.py`'s regimes hand-roll schedules on a raw transport — its "lifx-async" arm models
the *old* single-broadcast behaviour and never calls `discover_devices()`, so it cannot
measure the implementation directly `[VERIFIED: sweep.py:56-58, 106-147]`.

**Baseline (already recorded — do not re-run):**
`.planning/spikes/005-discovery-regimes/summary-20260716-211339.json` — `lifx-async`
found min/med/max = 27/48/73 over 6 rounds; `photons` arm demonstrates the target
(~72–73/73 at ~615 responses/round).

**After-measurement (recommended):** a small phase-dir script that drives the real
implementation:

```python
# .planning/phases/02-discovery-rebroadcast/uat_rounds.py (run: uv run python <path>)
import asyncio, statistics
from lifx.network.discovery import discover_devices

async def main() -> None:
    rounds: list[set[str]] = []
    for i in range(6):
        found = {d.serial async for d in discover_devices(timeout=10.0)}
        print(f"round {i}: {len(found)}")
        rounds.append(found)
        await asyncio.sleep(3.0)          # matches sweep.py INTER_ROUND_GAP
    roster = set().union(*rounds)
    med = statistics.median(len(r) for r in rounds)
    print(f"roster={len(roster)} median={med} -> {'PASS' if med == len(roster) else 'FAIL'}")

asyncio.run(main())
```

Pass criterion (DISC-03): `median == roster size` (expected 73/73; per-round misses of
1 device occasionally are tolerable if the median holds — spike doc notes >99% per-round
is the physical ceiling). `timeout=10.0` matches the spike's 10 s windows for
apples-to-apples comparison against the recorded baseline.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | LIFX LAN protocol is unauthenticated by design |
| V4 Access Control | no | — |
| V5 Input Validation | yes | Existing (unchanged): source-ID validation, serial validation (multicast/broadcast/padding guards), packet-size limits in transport |
| V6 Cryptography | no | — |

### Known Threat Patterns for this change

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Response flood keeping discovery alive | DoS | Overall deadline (unchanged) hard-caps the window regardless of response volume; re-broadcasts add at most 5 outbound packets |
| Spoofed responses to re-broadcasts | Spoofing | Same source-ID + serial validation path handles every response identically — re-broadcast adds no new acceptance surface (same source reused across sends is what keeps validation sound) |
| Self-inflicted network load | DoS (outbound) | Photons schedule chosen over Glowup specifically to bound load: ~615 vs ~2,146 responses/round on a 73-device fleet `[VERIFIED: spike 005]` |

## Sources

### Primary (HIGH confidence)

- Codebase, read directly this session: `src/lifx/network/discovery.py`,
  `src/lifx/network/utils.py`, `src/lifx/network/transport.py` (receive semantics),
  `src/lifx/api.py` (all four discovery callers), `src/lifx/const.py`,
  `tests/test_network/test_discovery_errors.py`,
  `tests/test_network/test_discovery_devices.py`, `pyproject.toml`
- Spike 005 measured data: `.planning/spikes/005-discovery-regimes/summary-20260716-211339.json`
  (73-device roster, 6 rounds/regime, run 2026-07-16)
- Spike blueprint: `.claude/skills/spike-findings-lifx-async/references/discovery.md`
- Working interleave: `.claude/skills/spike-findings-lifx-async/sources/005-discovery-regimes/sweep.py`

### Secondary (MEDIUM confidence)

- Photons discovery schedule shape (`timeouts=[(0.6,1.8),(1,2),(2,6),(4,10),(5,20)]`,
  `session/network.py:93-98`) — cited via the spike's source reading, not re-fetched this
  session `[CITED: spike 005 README/sweep.py docstring]`

### Tertiary (LOW confidence)

- None.

## Metadata

**Confidence breakdown:**

- Edit points / loop mechanics: HIGH — code read line-by-line this session; interleave
  pattern already ran against the production fleet in spike 005
- IdleDeadline interaction: HIGH — semantics verified in `utils.py` and existing tests;
  empty-network invariance reasoned from constants
- Test strategy: HIGH — built entirely from patterns already present in
  `test_discovery_errors.py`; branch-coverage matrix mapped to each new branch
- UAT tooling: HIGH — baseline artefacts exist on disk; harness is a 20-line adaptation

**Research date:** 2026-07-16
**Valid until:** stable (internal codebase; re-verify line numbers if discovery.py
changes before planning)
