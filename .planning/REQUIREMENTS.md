# Requirements: lifx-async — Ceiling save-on-exit

**Defined:** 2026-06-11
**Core Value:** Exiting a `CeilingLight` `async with` block reliably persists current state to disk — no uplight/downlight state is silently lost on context exit.

## v1 Requirements

Requirements for this milestone. Each maps to a roadmap phase.

### Ceiling Save-on-Exit

- [x] **CEIL-01**: When a `CeilingLight` is used as an async context manager and `state_file` is set, exiting the `async with` block persists the device's current in-memory state to disk before the connection is closed
- [x] **CEIL-02**: When `state_file` is `None`, exiting the `async with` block performs no state-file write (no file created, no error)
- [x] **CEIL-03**: A save-on-exit I/O failure is logged and swallowed — it never raises out of `__aexit__` and never suppresses or replaces an exception propagating from the `async with` body
- [x] **CEIL-04**: The existing `__aenter__` behaviour (product-ID validation, load-state-from-file) and `close()` cleanup continue to run unchanged when entering/exiting the context

### Verification

- [x] **TEST-01**: Test proves state is written to `state_file` on context exit when `state_file` is set
- [x] **TEST-02**: Test proves no write occurs on context exit when `state_file` is `None`
- [x] **TEST-03**: Test proves that when the `async with` body raises, the original exception still propagates and save-on-exit behaviour is correct (save attempted, errors swallowed)

## v2 Requirements

Deferred to future work. Tracked but not in this roadmap.

### Persistence Generalisation

- **PERS-01**: Extract `state_file` save/load into a reusable mixin so other device types (Matrix, MultiZone) can opt into persistence + save-on-exit

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| State-persistence mixin for other device types | Only `CeilingLight` persists state today; premature abstraction with no second consumer (see PERS-01, deferred) |
| Async-context-manager support on `Animator` / effect `StateManager` / running-effect handles | Separate concern, not requested |
| Changes to the `state_file` JSON schema or per-operation save points | Exit save reuses the existing mechanism unchanged |
| Skipping save when exiting via exception | User chose "Final save then close" — always save on exit |
| Renaming `CeilingLight` → `LIFXCeiling` | No such class exists; `CeilingLight` is the established public name |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| CEIL-01 | Phase 1 | Complete |
| CEIL-02 | Phase 1 | Complete |
| CEIL-03 | Phase 1 | Complete |
| CEIL-04 | Phase 1 | Complete |
| TEST-01 | Phase 1 | Complete |
| TEST-02 | Phase 1 | Complete |
| TEST-03 | Phase 1 | Complete |

**Coverage:**

- v1 requirements: 7 total
- Mapped to phases: 7
- Unmapped: 0 ✓

---
*Requirements defined: 2026-06-11*
*Last updated: 2026-06-12 after roadmap creation (traceability mapped)*
