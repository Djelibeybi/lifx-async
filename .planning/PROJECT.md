# lifx-async — Ceiling save-on-exit

## Current State (post-v1.0)

**Shipped:** v1.0 Ceiling Save-on-Exit (2026-06-12) — see `.planning/MILESTONES.md`.

`CeilingLight.__aexit__` now persists in-memory state to `state_file` (when set) before the
inherited `close()` runs. The save is executed via `asyncio.to_thread`, writes atomically
(temp file + `os.replace`), merges the on-disk per-serial entry rather than replacing the
whole file, never raises out of `__aexit__`, and never masks an exception propagating from
the `async with` body. Proven by three emulator-backed tests (`TestCeilingLightSaveOnExit`).

## Next Milestone Goals

Not yet defined — run `/gsd-new-milestone`. Candidate carried forward:

- **PERS-01** (deferred from v1.0): extract `state_file` save/load into a reusable mixin so
  other device types (Matrix, MultiZone) can opt into persistence + save-on-exit

## What This Is

`lifx-async` is a mature, zero-dependency, type-safe async Python library for controlling
LIFX smart devices over the local network (published on PyPI as `lifx-async`). This milestone
adds a **save-on-exit guarantee** to `CeilingLight`'s async context-manager lifecycle so that
exiting an `async with` block always persists the device's latest in-memory state to its
`state_file`.

## Core Value

Exiting a `CeilingLight` `async with` block reliably persists current state to disk — no
uplight/downlight state is silently lost on context exit.

## Requirements

### Validated

<!-- Inferred from existing code — already shipped and relied upon. -->

- ✓ Base `Device.__aenter__`/`__aexit__` async context managers (`devices/base.py:639`) inherited by all device subclasses via `Generic[StateT]` with `Self` return — existing
- ✓ `CeilingLight.__aenter__` override (`devices/ceiling.py:191`): product-ID validation + load persisted state from `state_file` on entry — existing
- ✓ `CeilingLight` state persistence: `_save_state_to_file()` / `_load_state_from_file()` writing per-serial uplight/downlight colours to JSON (`devices/ceiling.py:1196`, `:1263`) — existing
- ✓ State saved after each mutating operation (set colour, power-off, etc.) when `state_file` is set — existing
- ✓ Async context managers on `DeviceGroup`, `UdpTransport`, `MdnsTransport`, `DeviceConnection` — existing
- ✓ `CeilingLight.__aexit__` override saves state to `state_file` (when set) before the inherited `close()`, with belt-and-braces error swallowing — Validated in Phase 1: Ceiling Save-on-Exit (`devices/ceiling.py:207`)
- ✓ Save-on-exit never raises: I/O failures logged and swallowed; body exceptions propagate unchanged — Validated in Phase 1 (TEST-03)
- ✓ Emulator tests cover save-on-exit with `state_file`, no-op when `None`, and exit-during-exception (`TestCeilingLightSaveOnExit`) — Validated in Phase 1

### Active

<!-- This milestone's scope. -->

_None — all milestone requirements validated in Phase 1._

### Out of Scope

- Generalising `state_file` persistence into a reusable mixin for other device types (Matrix, MultiZone, etc.) — only `CeilingLight` persists state today; deferred until a second class actually needs it
- New async-context-manager support on non-device classes (`Animator`, effect `StateManager`, running-effect handles) — separate concern, not requested
- Changing the load/save JSON schema or the per-operation save points — exit save reuses the existing mechanism unchanged
- Renaming `CeilingLight` to `LIFXCeiling` — no such class exists; `CeilingLight` is the established name

## Context

- Brownfield: full codebase map exists in `.planning/codebase/` (refreshed 2026-06-11).
- `CeilingLight` extends `MatrixLight` and is the only device class with disk-backed state
  persistence (`state_file` parameter). `state_file` stores per-serial stored uplight colour and
  stored downlight colours so a Ceiling can restore its "remembered" colours across restarts.
- Today, state is written after each mutating call, but the `async with` exit path inherits the
  base `__aexit__` (which only calls `close()`), so there is no explicit final save tied to the
  context-manager lifecycle. Any code path that mutates `state` without an intervening save would
  lose that change on exit.
- Library convention: device subclasses that need extra entry/exit behaviour override
  `__aenter__`/`__aexit__` and chain to `super()` (see `CeilingLight.__aenter__`).

## Constraints

- **Tech stack**: Python 3.10–3.14, `asyncio`, zero runtime dependencies — no new deps.
- **Compatibility**: Must not change the public API surface or `state_file` JSON schema; purely
  additive exit behaviour.
- **Error handling**: Save-on-exit must never raise — I/O errors are logged (existing
  `_save_state_to_file` behaviour) and must not suppress or replace an exception propagating
  out of the `async with` body.
- **Quality gates**: `uv run pyright` (strict) clean, `uv run ruff check`/`format` clean,
  `uv run pytest` green across all supported Python versions.
- **Spelling**: Australian English in all prose/comments.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Save-on-exit persists current state before `close()` | Guarantees the `async with` lifecycle never drops in-memory state, even via paths that didn't already save | ✓ Shipped (Phase 1) |
| Always save on exit (not only clean exit) | User chose "Final save then close"; per-operation saves already write valid state, so a final save is a safe superset | ✓ Shipped (Phase 1) |
| Ceiling-only scope (no mixin generalisation) | `CeilingLight` is the only class persisting state; premature abstraction adds risk with no consumer | ✓ Held (PERS-01 deferred to v2) |
| Reuse existing `_save_state_to_file()` unchanged | Keeps JSON schema and graceful error handling intact; minimises blast radius | ✓ Shipped (Phase 1) |
| D-01 revised: exit-save runs via `asyncio.to_thread` | Code review (IN-02) flagged blocking file I/O on the event loop; original "synchronous like the other 8 call sites" decision reversed for the exit path | ✓ Shipped (review fix) |
| Atomic state-file writes (temp file + `os.replace`) | Code review (WR-03) — a crash mid-write must not corrupt the state file | ✓ Shipped (review fix) |
| Merge on-disk device entry instead of replacing file | Code review (WR-01) — multiple devices sharing one `state_file` must not clobber each other's entries | ✓ Shipped (review fix) |

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
*Last updated: 2026-06-12 after v1.0 milestone*
