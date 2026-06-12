# Phase 1: Ceiling Save-on-Exit - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-12
**Phase:** 1-Ceiling Save-on-Exit
**Areas discussed:** Blocking I/O on exit, Exception guard depth, Test approach

---

## Blocking I/O on exit

| Option | Description | Selected |
|--------|-------------|----------|
| Direct call | Call inline, like the 8 existing call sites inside async methods | ✓ |
| asyncio.to_thread | Offload to a thread so the event loop never blocks | |
| You decide | Leave to planner/executor | |

**User's choice:** Direct call (recommended)

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, mirror pattern | Guard with `if self._state_file:` like every other call site | ✓ |
| Unguarded call | Rely on the helper's internal early-return | |

**User's choice:** Yes, mirror pattern (recommended)

---

## Exception guard depth

| Option | Description | Selected |
|--------|-------------|----------|
| Belt-and-braces | try/except Exception + log line in `__aexit__` itself, in addition to helper's handling | ✓ |
| Rely on helper only | Helper already catches and logs; no extra wrapper | |

**User's choice:** Belt-and-braces (recommended)

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — save then always close | `super().__aexit__()` runs unconditionally even if save raises | ✓ |
| Sequential, no finally | Plain sequential statements | |

**User's choice:** Yes — save then always close (recommended)

---

## Test approach

| Option | Description | Selected |
|--------|-------------|----------|
| Emulator + tmp state_file | `@pytest.mark.emulator` with real `async with` blocks and tmp-path state_file | ✓ |
| Unit tests with mocks | Mock connection, call `__aexit__` directly | |
| Both | Emulator integration plus direct-call unit tests | |

**User's choice:** Emulator + tmp state_file (recommended)

| Option | Description | Selected |
|--------|-------------|----------|
| monkeypatch save helper | Patch `_save_state_to_file`/open to raise; caplog asserts log line | ✓ |
| Unwritable path | Real I/O failure but helper swallows it internally | |
| You decide | Leave mechanism to planner | |

**User's choice:** monkeypatch save helper (recommended)

## Claude's Discretion

- Log message wording/level for the `__aexit__` guard (match house style, `_LOGGER.warning`)
- Test file placement (`test_ceiling.py` vs `test_state_ceiling.py`)

## Deferred Ideas

- PERS-01 (mixin generalisation) — already tracked in REQUIREMENTS.md v2
