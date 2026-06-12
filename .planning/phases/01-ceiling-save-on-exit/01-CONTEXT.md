# Phase 1: Ceiling Save-on-Exit - Context

**Gathered:** 2026-06-12
**Status:** Ready for planning

<domain>
## Phase Boundary

`CeilingLight` gains an `__aexit__` override that persists the device's current in-memory
state to `state_file` before the inherited `close()` runs, plus tests proving save-on-exit,
no-op when `state_file` is `None`, and correct behaviour when the `async with` body raises.
No public API changes, no JSON schema changes, no persistence mixin.

</domain>

<decisions>
## Implementation Decisions

### Blocking I/O on exit
- **D-01:** Call `_save_state_to_file()` directly (synchronous, inline) in `__aexit__`, exactly like the 8 existing call sites that call it from async methods (e.g. `src/lifx/devices/ceiling.py:499`, `:561`). No `asyncio.to_thread`.
- **D-02:** Guard the call with `if self._state_file:` at the call site, mirroring the established pattern — even though the helper also early-returns when `state_file` is `None`. Makes CEIL-02 obvious at the call site.

### Exception guard depth
- **D-03:** Belt-and-braces: wrap the save call in `try/except Exception` with a log line in `__aexit__` itself, in addition to `_save_state_to_file()`'s internal error handling. The CEIL-03 invariant lives at the boundary and survives future helper edits.
- **D-04:** `super().__aexit__(...)` (which calls `close()`) must run unconditionally even if the save attempt raises unexpectedly — connection cleanup can never be skipped (CEIL-04).

### Test approach
- **D-05:** Tests follow the existing pattern: `@pytest.mark.emulator` tests using real `async with CeilingLight.connect(...)` blocks with a tmp-path `state_file` (see `tests/test_devices/test_ceiling.py:712` and `tests/test_devices/test_state_ceiling.py`). No mock-only unit tests.
- **D-06:** TEST-03's I/O failure is induced by monkeypatching `_save_state_to_file` (or the underlying open) to raise inside the emulator test — deterministic, exercises the `__aexit__` guard directly, and `caplog` asserts the log line. Do NOT use an unwritable path (the helper would swallow it internally and the boundary guard would go unexercised).

### Claude's Discretion
- Exact log message wording and log level for the `__aexit__` guard (existing helper uses `_LOGGER.warning` — match house style).
- Test file placement (`test_ceiling.py` vs `test_state_ceiling.py`) — pick whichever class/section fits best.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & scope
- `.planning/REQUIREMENTS.md` — CEIL-01..04, TEST-01..03, out-of-scope table (no mixin, no schema change, always-save-on-exit decision)
- `.planning/ROADMAP.md` — Phase 1 success criteria (includes pyright strict + ruff clean, full suite green)

### Implementation surface
- `src/lifx/devices/ceiling.py` — `__aenter__` override (`:191`), `_save_state_to_file()` (`:1263` area), `_load_state_from_file()` (`:1196`), existing guarded call sites
- `src/lifx/devices/base.py:644` — inherited `__aexit__` (calls `close()` only)

### Tests
- `tests/test_devices/test_ceiling.py:712` — existing tmp state_file fixture pattern (`ceiling_176`)
- `tests/test_devices/test_state_ceiling.py` — emulator-based `async with CeilingLight.connect(...)` test style

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `_save_state_to_file()`: already handles file I/O errors gracefully (logs warning, never raises) — exit save reuses it unchanged.
- `ceiling_176` fixture + tempdir `state_file` pattern in `test_ceiling.py` — directly reusable for the new tests.

### Established Patterns
- Subclasses needing extra entry/exit behaviour override `__aenter__`/`__aexit__` and chain to `super()` — `CeilingLight.__aenter__` is the in-file template.
- Every mutating method uses `if self._state_file: self._save_state_to_file()` — the exit save uses the identical idiom.

### Integration Points
- New `__aexit__` sits in `CeilingLight` (`src/lifx/devices/ceiling.py`), signature matching `Device.__aexit__` (`exc_type`, `exc_val`, `exc_tb`), returning `None` (never suppresses exceptions).

</code_context>

<specifics>
## Specific Ideas

No specific requirements beyond the decisions above — open to standard approaches.

</specifics>

<deferred>
## Deferred Ideas

- **PERS-01** (already tracked in REQUIREMENTS.md v2): extract `state_file` save/load into a reusable mixin once a second device type needs persistence.

</deferred>

---

*Phase: 1-Ceiling Save-on-Exit*
*Context gathered: 2026-06-12*
