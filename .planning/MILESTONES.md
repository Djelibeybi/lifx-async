# Milestones

## v1.0 Ceiling Save-on-Exit (Shipped: 2026-06-12)

**Phases completed:** 1 phases, 1 plans, 3 tasks

**Key accomplishments:**

- `CeilingLight.__aexit__` override that persists in-memory state to `state_file` before `close()`, proven by three emulator-backed TDD tests covering happy-path write, no-op without state_file, and exception-propagation-with-save-failure.

---
