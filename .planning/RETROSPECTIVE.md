# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v1.0 — Ceiling Save-on-Exit

**Shipped:** 2026-06-12
**Phases:** 1 | **Plans:** 1 | **Sessions:** ~4 (map → plan → execute → review/audit)

### What Was Built
- `CeilingLight.__aexit__` override that persists in-memory state to `state_file` before `close()`, with a belt-and-braces guard so save failures never raise and never mask a body exception
- Three emulator-backed TDD tests (`TestCeilingLightSaveOnExit`): happy-path write, `state_file=None` no-op, and exception-propagation-with-save-failure
- Review-driven hardening: atomic state-file writes (temp file + `os.replace`), per-serial entry merge instead of whole-file replace, exit-save moved off the event loop via `asyncio.to_thread`

### What Worked
- RED→GREEN TDD with atomic commits made the 6-minute execution clean — failing tests committed first, implementation second, quality gate third
- The embedded lifx-emulator gave real protocol-level coverage without hardware
- Code review caught three genuine issues (blocking I/O on the event loop, non-atomic writes, whole-file clobbering) that the original plan had explicitly decided the other way

### What Was Inefficient
- D-01 ("call `_save_state_to_file()` synchronously, matching the 8 existing call sites") was reversed by review fix IN-02 — researching the blocking-I/O question up front would have avoided a decide-then-revise cycle
- Planning artifacts (~25 docs commits) heavily outweighed the code change (2 files, +156/−8) for a single-phase milestone; a lighter-weight track may suit changes this small

### Patterns Established
- `CeilingLight` async context-manager lifecycle: `__aenter__` loads state, `__aexit__` saves state, both chain to `super()`
- Belt-and-braces `__aexit__` guards: outer try/except at the boundary, separate from the helper's own error handling, so the never-raise invariant survives future helper edits
- State-file writes are atomic (temp file + `os.replace`) and merge per-serial entries

### Key Lessons
1. "Match the existing call sites" is not always right — the exit path had different constraints (event-loop blocking matters more at lifecycle boundaries) than the per-operation save points.
2. Multiple devices sharing one `state_file` is a real usage pattern; any whole-file write must merge, not replace.
3. The outer exception guard in `__aexit__` is intentionally unreachable in production today (the helper catches I/O errors first) — documented as deliberate design, not dead code.

### Cost Observations
- Model mix: not tracked this milestone
- Sessions: ~4
- Notable: execution itself took 6 minutes; the bulk of effort went to planning, review and audit artifacts

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Sessions | Phases | Key Change |
|-----------|----------|--------|------------|
| v1.0 | ~4 | 1 | First GSD milestone on this repo; full pipeline (map → discuss → plan → execute → review → audit) exercised end-to-end |

### Cumulative Quality

| Milestone | Tests | Coverage | Zero-Dep Additions |
|-----------|-------|----------|-------------------|
| v1.0 | 2500 (suite green) | — | 0 (still zero runtime deps) |

### Top Lessons (Verified Across Milestones)

1. (Single milestone so far — lessons above pending cross-validation.)
