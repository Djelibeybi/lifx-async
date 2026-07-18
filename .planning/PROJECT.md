# lifx-async — Wire Reliability

## Current State (post-v1.0)

**v1.1 Wire Reliability: all four phases complete (2026-07-18) — ready to close.**
Phases 2–5 delivered and verified; all 13 requirements (DISC-01..03, RETRY-01..04,
ANIM-01..04, DOCS-01..02) trace to Complete. Measured outcomes: discovery re-broadcast
took a single call from a median 48/73 devices to 73/73; the retry reshape cut
packets-per-request from 1.37 to 1.017 and latency from 62 ms to 12.6 ms; ack-gated
animation pacing won directionally on every device ever measured (1.28×–5.25×), accepted
by operator ruling over a recorded statistical FAIL rather than a statistical pass
(`04-RULING.md`). Milestone close carries known verification debt — see STATE.md
Blockers.

**Shipped:** v1.0 Ceiling Save-on-Exit (2026-06-12) — see `.planning/MILESTONES.md`.
**Also shipped post-v1.0:** Phase 1 discovery unification (verified 2026-06-13) — rebuilt
`discover_devices()` on `_discover_with_packet()` with hoisted DoS serial validation and
first-wins per-serial dedup.

**Spike series completed 2026-07-16** (`.planning/spikes/`, packaged as the
`spike-findings-lifx-async` skill): five real-hardware experiments that disproved the
"switch to threading" hypothesis and located the actual reliability levers.

## Current Milestone: v1.1 Wire Reliability

**Goal:** Close the empirically-measured reliability gap between lifx-async and the
reference clients (Glowup, Photons) using the spike-validated blueprints, without changing
the asyncio core or public API.

**Target features:**

- **Discovery re-broadcast** — re-send `GetService` on an escalating schedule inside the
  discovery window. Spike 005: single broadcast finds median 48/73 devices on a multi-AP
  network; re-broadcast schedules find 73/73.
- **Animation flow control** — the Animation layer owns delivery strategy internally
  (Photons-style ack-gated pacing); **decided by the animation library, not downstream
  consumers**. Spike 003: eliminates the 14.6% concurrent-query loss during streaming and
  produced the best visual smoothness.
- **Retry schedule reshape** — floor the 31 ms first-attempt window (~200 ms), keep
  listening during backoff instead of sleeping blind, count sleeps against the caller's
  timeout. Spike 002: kills duplicate-firing on healthy networks and 29 s wall-time
  overruns of the 16 s budget.
- **Docs** — gen4 power-save wake-tail footnote; guidance for streaming consumers (LedFx).

## What This Is

`lifx-async` is a mature, zero-dependency, type-safe async Python library for controlling
LIFX smart devices over the local network (published on PyPI as `lifx-async`). This
milestone makes its wire behaviour — discovery coverage, request retries, and animation
frame delivery — measurably as reliable as the best reference clients, keeping the async
API untouched.

## Core Value

Commands stick, devices are found, and streaming never starves control traffic — the
library is reliable enough that "bulb didn't respond" stops being a lifx-async problem.

## Requirements

### Validated

<!-- Inferred from existing code — already shipped and relied upon. -->

- ✓ v1.0 Ceiling save-on-exit lifecycle (see MILESTONES.md) — shipped
- ✓ Unified discovery generator with serial validation and first-wins dedup
  (`_discover_with_packet()`, post-v1.0 Phase 1) — shipped
- ✓ Request/response correlation on (source, sequence, serial) with shared response queue
  across retry attempts (`connection.py`) — existing; retry reshape must preserve it
- ✓ Zero-allocation prebaked packet templates for animation (`animation/packets.py`) —
  existing; flow control must preserve this send path
- ✓ Discovery re-broadcast on an escalating schedule (DISC-01..03) — Phase 2
- ✓ Retry schedule reshape (RETRY-01..04) — Phase 3
- ✓ Animation-layer-owned ack-gated flow control (ANIM-01..04) — Phase 4
- ✓ Reliability documentation (DOCS-01..02) — Phase 5

### Active

<!-- This milestone's scope — REQ-IDs defined in REQUIREMENTS.md. -->

None — every v1.1 requirement is validated. Next scope is set at the v1.1 close.

### Out of Scope

- **Switching from asyncio to threading** — disproven by Spike 004: wire-equivalent at
  idle, threading collapses under CPU load
- **Keepalive daemon** — disproven by Spike 001: zero idle-related loss on healthy
  networks; gen4-only sub-250 ms wake tail warrants a docs footnote, not a feature
- **Glowup-style query retries (3× fresh 2 s deadlines)** — disproven by Spike 002:
  40% failure at 50% loss
- **Downstream-facing flow-control toggles** — delivery strategy is the animation
  library's decision (user decision, 2026-07-16)
- Generalising `state_file` persistence into a reusable mixin (PERS-01) — still deferred;
  unrelated to this milestone
- mDNS discovery changes — Spike 005's finding applies to UDP broadcast discovery

## Context

- Brownfield: full codebase map in `.planning/codebase/` (refreshed 2026-06-11).
- Implementation blueprints with working reference code live in
  `./.claude/skills/spike-findings-lifx-async/` (references/ + sources/); raw spike data
  in `.planning/spikes/*/results-*.jsonl`.
- Reference clients studied: Glowup (threaded,
  `/Volumes/External/Developer/pkivolowitz/glowup/`) and Photons (asyncio,
  insider-authored, `/Volumes/External/Developer/Djelibeybi/photons`). Techniques port;
  dependencies don't.
- Real-hardware validation available: 7 quiesced test devices across gen2/3/4 plus a
  73-device production fleet (see auto-memory `project_test_fleet`). Repeated rounds are
  mandatory for discovery/loss claims — single rounds mislead.
- lifx-async is the LIFX provider for LedFx — the streaming + concurrent-control pattern
  Spike 003 measured is LedFx's exact workload.

## Constraints

- **Tech stack**: Python 3.10–3.14, `asyncio`, zero runtime dependencies — no new deps.
- **Compatibility**: Public async API unchanged. Additive/internal changes only; existing
  callers of `discover_devices()`, `DeviceConnection.request()`, and the Animation layer
  must work unmodified.
- **Emulator limits**: the emulator cannot model per-AP broadcast delivery, WiFi loss, or
  power-save — hardware validation runs complement, not replace, the test suite.
- **Quality gates**: `uv run pyright` (strict) clean, `uv run ruff check`/`format` clean,
  `uv run pytest` green across supported versions; CI requires 100% branch patch coverage.
- **Spelling**: Australian English in all prose/comments.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| v1.0 decisions | See MILESTONES.md and git history | ✓ Shipped |
| Investigate wire behaviour instead of porting to threading | Bulbs can only observe packets/timing, not the concurrency model | ✓ Validated (Spikes 001–005) |
| Adopt Photons-shaped schedules (discovery + retries) | Best measured balance: full coverage / 1-in-180 failure at moderate packet cost | ✓ Validated — Phases 2–3. Discovery: median 48/73 → 73/73 on one call. Retries: 1.37 → 1.017 packets/request, 62 ms → 12.6 ms, no 29 s overruns of the 16 s budget |
| Animation flow control owned by the library, not downstream | Consumers (LedFx) shouldn't need to choose delivery strategy; the layer that sends frames decides | ✓ Shipped — Phase 4. No consumer-facing toggle. Gated arm won directionally in every measured session (1.28×–5.25×); certified by operator ruling over a recorded FAIL, never a statistical pass (`04-RULING.md`) |
| Publish behaviour, not tuning constants (D5-09 as written) | Rendered docstrings state the behavioural contract; thresholds/expiries stay in `flow.py` and comments where they can change without a docs lie | ✓ Applied — Phase 5. **The rule itself is disputed by the operator and remains an OPEN decision** in `05-CONTEXT.md`, with spike candidate 006 (cap-impact measurement) linked. Phase 5 complied with it as written; its future is unsettled |
| Drop the 8-warning docs baseline instead of pinning it | The "pre-existing" warnings were a defect set (5 annotations parsed as link refs; 3 anchors to never-rendered mDNS symbols), not a constant | ✓ Shipped — Phase 5 (D5-23). Zero warnings under `--strict`, gated in CI so the class cannot drift back |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-07-18 after Phase 5 (v1.1 final phase — milestone ready to close)*
