# Phase 1: Ceiling Save-on-Exit — Research

**Researched:** 2026-06-12
**Domain:** Python async context manager override; in-process codebase change only
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Call `_save_state_to_file()` directly (synchronous, inline) in `__aexit__`, exactly like the 8 existing call sites (e.g. `ceiling.py:499`, `:561`). No `asyncio.to_thread`.
- **D-02:** Guard the call with `if self._state_file:` at the call site, mirroring the established pattern — even though the helper also early-returns when `state_file` is `None`. Makes CEIL-02 obvious at the call site.
- **D-03:** Belt-and-braces: wrap the save call in `try/except Exception` with a log line in `__aexit__` itself, in addition to `_save_state_to_file()`'s internal error handling. The CEIL-03 invariant lives at the boundary and survives future helper edits.
- **D-04:** `super().__aexit__(...)` (which calls `close()`) must run unconditionally even if the save attempt raises unexpectedly — connection cleanup can never be skipped (CEIL-04).
- **D-05:** Tests follow the existing pattern: `@pytest.mark.asyncio` emulator tests using real `async with CeilingLight(...)` blocks with a `tmp_path` `state_file`. No mock-only unit tests.
- **D-06:** TEST-03's I/O failure is induced by monkeypatching `_save_state_to_file` to raise inside the emulator test — deterministic, exercises the `__aexit__` guard directly, and `caplog` asserts the log line. Do NOT use an unwritable path.

### Claude's Discretion

- Exact log message wording and log level for the `__aexit__` guard (existing helper uses `_LOGGER.warning` — match house style).
- Test file placement (`test_ceiling.py` vs `test_state_ceiling.py`) — pick whichever class/section fits best.

### Deferred Ideas (OUT OF SCOPE)

- **PERS-01**: Extract `state_file` save/load into a reusable mixin once a second device type needs persistence.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CEIL-01 | When `state_file` is set, exiting `async with` persists current in-memory state before connection closes | `_save_state_to_file()` already handles JSON write; `__aexit__` just needs to call it before `super().__aexit__()` |
| CEIL-02 | When `state_file` is `None`, exiting performs no write (no file, no error) | Guard `if self._state_file:` at the call site makes the no-op explicit |
| CEIL-03 | Save-on-exit I/O failure is logged and swallowed — never raises, never suppresses body exception | `try/except Exception` in `__aexit__` + `_LOGGER.warning`; `__aexit__` returns `None` so body exception re-raises automatically |
| CEIL-04 | Existing `__aenter__` (validation, load-from-file) and `close()` cleanup run unchanged | Place save before `super().__aexit__()` call; do not touch `__aenter__` |
| TEST-01 | Test proves state written to `state_file` on context exit when `state_file` is set | Emulator test: exit `async with`, assert file exists and contains expected JSON keys |
| TEST-02 | Test proves no write occurs on context exit when `state_file` is `None` | Emulator test: exit `async with` with no `state_file`, assert no file created |
| TEST-03 | Test proves original exception propagates and save errors are swallowed + logged | Monkeypatch `_save_state_to_file` to raise, raise from body, assert body exception propagates, assert `caplog` contains warning |
</phase_requirements>

---

## Summary

This phase adds a single method override — `CeilingLight.__aexit__` — to `src/lifx/devices/ceiling.py`. The override saves the device's current in-memory state to `state_file` before delegating to the inherited `close()` via `super().__aexit__()`. No new packages, no schema changes, no mixin extraction. All implementation materials are already in the codebase.

The `_save_state_to_file()` helper already handles graceful I/O errors (it wraps file ops in `try/except Exception` and logs with `_LOGGER.warning`). The `__aexit__` override adds a second guard layer ("belt-and-braces", D-03), ensuring CEIL-03's invariant survives any future edits to the helper. The `super().__aexit__()` call is placed unconditionally after the save attempt (D-04), so the connection is always cleaned up.

Three emulator-backed tests cover the requirements: happy-path write, `state_file=None` no-op, and exception-propagation-with-save-error. All three follow the existing `@pytest.mark.asyncio` + `ceiling_device` fixture pattern used throughout `test_state_ceiling.py`.

**Primary recommendation:** Implement `__aexit__` in one targeted edit, add three tests to `test_state_ceiling.py` in a new `TestCeilingLightSaveOnExit` class, then run the full suite to confirm nothing regresses.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| State persistence on context exit | Device Layer (`ceiling.py`) | — | `_save_state_to_file()` and `_state_file` already live in `CeilingLight`; the context manager override is the correct hook point |
| Connection cleanup | Device Layer (`base.py`) | — | `Device.__aexit__` calls `close()`; `CeilingLight.__aexit__` chains to it via `super()` |
| JSON serialisation | Device Layer (`ceiling.py`) | — | Existing `_save_state_to_file()` owns serialisation; not duplicated |
| Test emulation | Test infrastructure (`conftest.py`) | `tests/test_devices/` | `ceiling_device` + `emulator_server` fixtures are session-scoped; test file adds function-scoped `tmp_path` |

---

## Standard Stack

No new packages. This phase is purely additive within the existing zero-dependency library.

### Package Legitimacy Audit

No packages installed this phase.

**Packages removed due to SLOP verdict:** none
**Packages flagged as suspicious (SUS):** none

---

## Architecture Patterns

### System Architecture Diagram

```
CeilingLight.__aexit__(exc_type, exc_val, exc_tb)
       |
       |─── if self._state_file:
       |         try:
       |             _save_state_to_file()   ──► JSON write to disk
       |         except Exception as e:
       |             _LOGGER.warning(...)    ──► swallows I/O failure (D-03)
       |
       └─── await super().__aexit__(...)     ──► Device.close() always runs (D-04)
                  |
                  └─── connection.close()   ──► UDP socket teardown
```

Body exception, if any, propagates automatically because `__aexit__` returns `None` (falsy), which instructs Python to re-raise the suppressed exception.

### Pattern: `__aexit__` Override Chaining to `super()`

**What:** Override `__aexit__` in a subclass, do pre-close work, then unconditionally delegate to `super().__aexit__()`.

**When to use:** When a subclass needs cleanup steps that must run before the parent's cleanup, but parent cleanup must always run regardless.

**Existing in-file template:** `CeilingLight.__aenter__` (line 191) — overrides parent, does extra validation, then calls `super().__aenter__()`.

**Example:** [VERIFIED: codebase — `src/lifx/devices/ceiling.py:191-205`]
```python
async def __aenter__(self) -> CeilingLight:
    """Async context manager entry."""
    await super().__aenter__()

    # Validate product ID after version is fetched
    if self.version and not is_ceiling_product(self.version.product):
        raise LifxError(
            f"Product ID {self.version.product} is not a supported Ceiling light."
        )

    # Load state from disk if state_file is provided
    if self._state_file:
        self._load_state_from_file()

    return self
```

### Pattern: Guarded `_save_state_to_file()` Call Sites

**What:** Every mutating method guards the save call with `if self._state_file:`. The helper also early-returns on `None`, but the guard at the call site makes the no-op explicit (D-02).

**Existing call sites:** lines 498–499, 560–561, 635–636, 700–701, 789–790, 889–890, 942–943, 1020–1021.

**Example:** [VERIFIED: codebase — `src/lifx/devices/ceiling.py:498-499`]
```python
if self._state_file:
    self._save_state_to_file()
```

### Pattern: Belt-and-Braces Exception Guard

**What:** `_save_state_to_file()` already has `try/except Exception` internally (lines 1271–1316). The `__aexit__` override adds an outer guard to ensure the CEIL-03 invariant is enforced at the boundary even if the helper changes.

**Log level:** `_LOGGER.warning` — matches house style (`_save_state_to_file` uses `_LOGGER.warning` at line 1316). [VERIFIED: codebase — `src/lifx/devices/ceiling.py:1316`]

### Recommended Implementation

```python
async def __aexit__(
    self,
    exc_type: type[BaseException] | None,
    exc_val: BaseException | None,
    exc_tb: object,
) -> None:
    """Exit async context manager, saving state to file before close."""
    if self._state_file:
        try:
            self._save_state_to_file()
        except Exception as e:  # pragma: no cover — belt-and-braces; helper also catches
            _LOGGER.warning("Failed to save state on exit for %s: %s", self.serial, e)
    await super().__aexit__(exc_type, exc_val, exc_tb)
```

**Why no `finally`:** The `except Exception` guard means any exception from `_save_state_to_file` is swallowed before `super().__aexit__()` is reached. A `finally` around `super().__aexit__()` is not needed because there is no code path that can raise between the `except` block and the `await super()` call.

**Return value:** `None` (implicit). Python re-raises the body exception when `__aexit__` returns a falsy value, satisfying CEIL-03 without any extra code.

### Anti-Patterns to Avoid

- **Returning `True` from `__aexit__`:** Suppresses body exceptions. `__aexit__` must return `None`. [ASSUMED — documented Python async context manager protocol]
- **Calling `close()` directly instead of `super().__aexit__()`:** Bypasses any future overrides in the MRO and diverges from the established chaining pattern.
- **Using `asyncio.to_thread` for `_save_state_to_file()`:** Rejected by D-01. Existing call sites are all synchronous; the file write is small and infrequent.
- **Using an unwritable path to induce TEST-03 failure:** Rejected by D-06. The helper's internal guard swallows it before reaching the `__aexit__` boundary guard.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JSON serialisation of HSBK state | Custom serialiser | Existing `_save_state_to_file()` | Already handles directory creation, file merging, error logging — 8 tested call sites |
| File I/O error handling | New guard logic | Reuse existing `try/except` in `_save_state_to_file()` + belt-and-braces in `__aexit__` | Double-guarded pattern covers all realistic failure modes |
| Device cleanup | Custom close logic | `super().__aexit__()` → `Device.close()` | Cancels refresh tasks, drains the connection — must not be bypassed |

---

## Common Pitfalls

### Pitfall 1: Placing Save After `super().__aexit__()`

**What goes wrong:** The connection is closed before the save runs. The `_save_state_to_file()` method reads `self.state`, which may still be accessible, but the ordering violates the documented intent ("persists state before the connection is closed").

**Why it happens:** Copying the `__aenter__` pattern blindly — in `__aenter__`, `super()` is called first because the parent initialises the connection.

**How to avoid:** In `__aexit__`, save first, then delegate to `super()`. The save does not require an open connection (it reads in-memory state, not network state).

**Warning signs:** Tests that check file content after exit would still pass, but the semantic contract is violated.

### Pitfall 2: Test Uses Mock-Only Setup (Not Emulator)

**What goes wrong:** A mock-only test does not exercise `__aenter__` (product-ID validation, state initialisation). The emulator is required to validate the full context manager lifecycle (D-05).

**Why it happens:** The `ceiling_176` fixture in `TestCeilingLightStatePersistence` (line 708) uses a mocked connection — it was designed for unit-testing the helper methods, not the context manager protocol.

**How to avoid:** New tests belong in `test_state_ceiling.py` using `ceiling_device` + `CeilingLight(serial=..., ip=..., port=..., state_file=...)`. The `ceiling_device` fixture provides a running emulator target.

### Pitfall 3: TEST-03 Uses Unwritable Path Instead of Monkeypatch

**What goes wrong:** An unwritable path triggers the I/O guard inside `_save_state_to_file()`, which logs and returns. The outer `__aexit__` guard is never exercised, so TEST-03 does not actually test what D-03 requires.

**Why it happens:** Unwritable paths are an intuitive way to simulate I/O failures.

**How to avoid:** Per D-06, monkeypatch `_save_state_to_file` on the device instance to raise unconditionally. This forces the exception past the helper's guard and into the `__aexit__` guard.

### Pitfall 4: Pyright Mode Discrepancy

**What goes wrong:** The ROADMAP mentions "strict Pyright" but `pyproject.toml` sets `typeCheckingMode = "standard"`. Running `pyright --strict` on the implementation may surface failures that don't represent real quality regressions.

**Why it happens:** The ROADMAP was written with aspirational language; the project config reflects the actual enforced mode.

**How to avoid:** Run `uv run pyright` (which respects `pyproject.toml`'s `standard` mode) as the quality gate. [VERIFIED: codebase — `pyproject.toml:82-90`]

---

## Code Examples

### Existing `_save_state_to_file()` — the helper being reused

[VERIFIED: codebase — `src/lifx/devices/ceiling.py:1263-1317`]
```python
def _save_state_to_file(self) -> None:
    """Save state to JSON file.

    Handles file I/O errors gracefully.
    """
    if not self._state_file:
        return

    try:
        state_path = Path(self._state_file).expanduser()
        # ... reads existing file, merges, writes updated JSON ...
        _LOGGER.debug("Saved state to %s for device %s", state_path, self.serial)

    except Exception as e:
        _LOGGER.warning("Failed to save state to %s: %s", self._state_file, e)
```

### Existing `Device.__aexit__` — the parent being overridden

[VERIFIED: codebase — `src/lifx/devices/base.py:644-651`]
```python
async def __aexit__(
    self,
    exc_type: type[BaseException] | None,
    exc_val: BaseException | None,
    exc_tb: object,
) -> None:
    """Exit async context manager and close connection."""
    await self.close()
```

### TEST-01: Happy-path state written on exit

```python
@pytest.mark.asyncio
async def test_save_on_exit_writes_state_file(
    ceiling_device, tmp_path
) -> None:
    """CEIL-01 / TEST-01: state is written to state_file on __aexit__."""
    state_file = tmp_path / "ceiling_state.json"

    async with CeilingLight(
        serial=ceiling_device.serial,
        ip=ceiling_device.ip,
        port=ceiling_device.port,
        state_file=str(state_file),
    ):
        pass  # exit normally

    assert state_file.exists()
    data = json.loads(state_file.read_text())
    assert ceiling_device.serial in data
```

### TEST-02: No write when `state_file` is `None`

```python
@pytest.mark.asyncio
async def test_save_on_exit_no_op_without_state_file(
    ceiling_device, tmp_path
) -> None:
    """CEIL-02 / TEST-02: no file is created when state_file is None."""
    async with CeilingLight(
        serial=ceiling_device.serial,
        ip=ceiling_device.ip,
        port=ceiling_device.port,
    ):
        pass

    assert not any(tmp_path.iterdir())
```

### TEST-03: Body exception propagates; save failure is logged and swallowed

```python
@pytest.mark.asyncio
async def test_save_on_exit_body_exception_propagates(
    ceiling_device, tmp_path, caplog, monkeypatch
) -> None:
    """CEIL-03 / TEST-03: body exception propagates; save error is logged and swallowed."""
    state_file = tmp_path / "ceiling_state.json"

    with pytest.raises(RuntimeError, match="body error"):
        ceiling = CeilingLight(
            serial=ceiling_device.serial,
            ip=ceiling_device.ip,
            port=ceiling_device.port,
            state_file=str(state_file),
        )
        async with ceiling:
            monkeypatch.setattr(
                ceiling, "_save_state_to_file", lambda: (_ for _ in ()).throw(OSError("disk full"))
            )
            raise RuntimeError("body error")

    assert any("disk full" in r.message or "Failed to save" in r.message
               for r in caplog.records
               if r.levelname == "WARNING")
```

**Note on monkeypatch scope:** `monkeypatch.setattr` is called on the device instance inside the `async with` body so the instance exists. `ceiling_device` serial is reused across tests (session scope) — the instance `ceiling` is new per test.

---

## Runtime State Inventory

Not applicable. This is a greenfield addition (new method) to an existing class, not a rename or migration. No stored data, service config, OS registrations, secrets, or build artefacts reference the changed surface.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| No `__aexit__` in `CeilingLight` — state lost silently on context exit | `__aexit__` saves state before `close()` | Phase 1 (this change) | State is reliably persisted whenever a `CeilingLight` is used as an async context manager with `state_file` set |

**Deprecated/outdated:** Nothing deprecated by this phase.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `ceiling_device.serial` and `ceiling_device.ip`/`ceiling_device.port` are accessible as attributes on the fixture-yielded `CeilingLight` instance | Code Examples (test patterns) | LOW — `ceiling_device` is a `CeilingLight`, `serial` and `ip` are defined in `Device.__init__`; trivially verifiable |

**All other claims** in this research were verified by reading codebase source files directly.

---

## Open Questions (RESOLVED)

1. **Log message wording for `__aexit__` guard**
   - What we know: Claude's Discretion; house style uses `_LOGGER.warning("Failed to save state to %s: %s", self._state_file, e)` in the helper
   - What's unclear: Whether to differentiate "on exit" from "mid-operation" in the message
   - Recommendation: Use `_LOGGER.warning("Failed to save state on __aexit__ for %s: %s", self.serial, e)` — distinguishes the boundary guard from the helper's internal warning when reading logs

2. **Test file placement**
   - What we know: `test_ceiling.py` has `TestCeilingLightStatePersistence` (mock-based); `test_state_ceiling.py` has `TestCeilingLightEmulatorStateManagement` (emulator-based)
   - Recommendation: Add a new `TestCeilingLightSaveOnExit` class to `test_state_ceiling.py` — emulator tests belong alongside other emulator tests; the mock-based class in `test_ceiling.py` is for the helper methods, not the context manager

---

## Environment Availability

Step 2.6: SKIPPED — no external dependencies. All runtime needs (Python 3.10+, `asyncio`, `json`, `pathlib`) are stdlib. The emulator (`lifx-emulator-core`) is a dev dependency installed via `uv sync`.
<br>

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `lifx-emulator-core` | TEST-01, TEST-02, TEST-03 | ✓ (dev dep) | installed via `uv sync` | Tests auto-skip if unavailable |

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (asyncio_mode = "auto") |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `uv run --frozen pytest tests/test_devices/test_state_ceiling.py -v -k "SaveOnExit"` |
| Full suite command | `uv run --frozen pytest` |

### Phase Requirements → Test Map

| Req ID | Behaviour | Test Type | Automated Command | File Exists? |
|--------|-----------|-----------|-------------------|--------------|
| CEIL-01 | State file written on exit when `state_file` is set | integration (emulator) | `uv run pytest tests/test_devices/test_state_ceiling.py::TestCeilingLightSaveOnExit::test_save_on_exit_writes_state_file` | ❌ Wave 0 |
| CEIL-02 | No file created when `state_file` is `None` | integration (emulator) | `uv run pytest tests/test_devices/test_state_ceiling.py::TestCeilingLightSaveOnExit::test_save_on_exit_no_op_without_state_file` | ❌ Wave 0 |
| CEIL-03 | Body exception propagates; save error swallowed + logged | integration (emulator) | `uv run pytest tests/test_devices/test_state_ceiling.py::TestCeilingLightSaveOnExit::test_save_on_exit_body_exception_propagates` | ❌ Wave 0 |
| CEIL-04 | `__aenter__` and `close()` run unchanged | regression (full suite) | `uv run --frozen pytest` | ✅ (existing suite) |
| TEST-01 | See CEIL-01 above | — | — | — |
| TEST-02 | See CEIL-02 above | — | — | — |
| TEST-03 | See CEIL-03 above | — | — | — |

### Sampling Rate

- **Per task commit:** `uv run --frozen pytest tests/test_devices/test_state_ceiling.py -v`
- **Per wave merge:** `uv run --frozen pytest`
- **Phase gate:** Full suite green + `uv run pyright` clean + `uv run ruff check .` clean before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `TestCeilingLightSaveOnExit` class in `tests/test_devices/test_state_ceiling.py` — covers CEIL-01, CEIL-02, CEIL-03 / TEST-01, TEST-02, TEST-03

*(No framework install needed — pytest infrastructure already in place.)*

---

## Security Domain

No security-relevant surface is touched by this phase. The change writes JSON to a user-specified local file path. The file write path, `_save_state_to_file()`, already existed and is unchanged. ASVS categories V2/V3/V4/V6 do not apply. V5 (input validation) is addressed by the existing `_save_state_to_file()` implementation, which is unmodified.

---

## Project Constraints (from CLAUDE.md)

| Directive | Applies to this phase |
|-----------|----------------------|
| Use Australian English spelling | Yes — docstrings and log messages |
| `uv run pyright` strict type checking | Yes — new `__aexit__` must be fully typed; `pyproject.toml` enforces `typeCheckingMode = "standard"` (ROADMAP says "strict" but config says "standard" — run `uv run pyright`) |
| `uv run ruff format . && uv run ruff check . --fix` | Yes — must be clean before commit |
| `uv run --frozen pytest` must stay green | Yes — full suite gate |
| `uv add --dev` for dev deps | N/A — no new deps |
| Never edit generated files (`packets.py`, `registry.py`, `protocol_types.py`) | N/A — no generated files touched |
| User-visible fields must never be `bytes` | N/A — no protocol layer touched |
| `git commit -s` with GPG signing | Yes — all commits |

---

## Sources

### Primary (HIGH confidence)

- `src/lifx/devices/ceiling.py` — `__aenter__` template (line 191), `_save_state_to_file()` (line 1263), `_LOGGER` declaration (line 34), all 8 guarded call sites
- `src/lifx/devices/base.py` — `Device.__aexit__` (line 644)
- `tests/test_devices/test_state_ceiling.py` — emulator test style, `CeilingLight.connect()` usage (line 281)
- `tests/test_devices/test_ceiling.py` — `ceiling_176` fixture (line 708), monkeypatching pattern (line 183)
- `tests/conftest.py` — `ceiling_device` fixture (line 352), `cleanup_device_connections` (line 327)
- `pyproject.toml` — `[tool.pyright]` (line 82), `[tool.pytest.ini_options]` (line 95)

### Secondary (MEDIUM confidence)

- `.planning/phases/01-ceiling-save-on-exit/01-CONTEXT.md` — all 6 locked decisions
- `.planning/REQUIREMENTS.md` — CEIL-01..04, TEST-01..03
- `.planning/ROADMAP.md` — success criteria

---

## Metadata

**Confidence breakdown:**

- Implementation pattern: HIGH — verified from 8 identical call sites in the codebase
- Test approach: HIGH — verified from existing emulator test class structure
- Type signature: HIGH — verified from `Device.__aexit__` in `base.py`
- Pyright mode discrepancy: HIGH — directly read from `pyproject.toml`

**Research date:** 2026-06-12
**Valid until:** Indefinite — codebase-internal research does not become stale
