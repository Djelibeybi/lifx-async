# Roadmap: lifx-async — Ceiling save-on-exit

## Overview

A single-phase brownfield milestone: override `CeilingLight.__aexit__` in
`src/lifx/devices/ceiling.py` so that exiting an `async with` block persists the device's
current in-memory state to its `state_file` (when set) before the inherited `close()` runs,
then prove the behaviour with tests covering the happy path, the `state_file=None` no-op, and
exit-during-exception semantics. The change is purely additive: the existing
`_save_state_to_file()` mechanism, JSON schema, `__aenter__` behaviour, and quality gates
(strict Pyright, ruff, full pytest suite) remain unchanged.

## Phases

**Phase Numbering:**

- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Ceiling Save-on-Exit** - `CeilingLight.__aexit__` persists state to `state_file` before close, with full test coverage (completed 2026-06-12)

## Phase Details

### Phase 1: Ceiling Save-on-Exit

**Goal**: Exiting a `CeilingLight` `async with` block reliably persists current state to disk — no uplight/downlight state is silently lost on context exit
**Depends on**: Nothing (first phase)
**Requirements**: CEIL-01, CEIL-02, CEIL-03, CEIL-04, TEST-01, TEST-02, TEST-03
**Success Criteria** (what must be TRUE):

  1. Exiting `async with CeilingLight(..., state_file=path)` writes the device's current in-memory state to `state_file` before the connection is closed, and a test (TEST-01) proves the write occurs on exit
  2. Exiting `async with CeilingLight(...)` with `state_file=None` performs no state-file write — no file is created and no error is raised — and a test (TEST-02) proves it
  3. When the `async with` body raises, the original exception still propagates unchanged; the exit save is attempted and any I/O failure is logged and swallowed (never raised, never masking the body's exception), and a test (TEST-03) proves it
  4. Existing `__aenter__` behaviour (product-ID validation, load-state-from-file) and `close()` cleanup continue to run unchanged — the full existing test suite stays green, with `pyright` (strict) and `ruff` clean**Plans**: 1 plan
- [x] 01-01-PLAN.md — Add `CeilingLight.__aexit__` save-on-exit override + three emulator tests (TEST-01/02/03), then run the full quality gate

## Progress

**Execution Order:**
Phases execute in numeric order: 1

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Ceiling Save-on-Exit | 1/1 | Complete    | 2026-06-12 |
