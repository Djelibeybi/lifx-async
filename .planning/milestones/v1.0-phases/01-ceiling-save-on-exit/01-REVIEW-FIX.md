---
phase: 01-ceiling-save-on-exit
fixed_at: 2026-06-12T08:55:00Z
review_path: .planning/phases/01-ceiling-save-on-exit/01-REVIEW.md
iteration: 2
findings_in_scope: 6
fixed: 6
skipped: 0
status: all_fixed
---

# Phase 1: Code Review Fix Report

**Fixed at:** 2026-06-12T08:30:00Z
**Source review:** .planning/phases/01-ceiling-save-on-exit/01-REVIEW.md
**Iteration:** 2

**Summary:**
- Findings in scope: 6 (fix_scope: all — 0 Critical, 3 Warning, 3 Info)
- Fixed: 6 (WR-01, WR-02, WR-03 in iteration 1; IN-01, IN-03 in iteration 2; IN-02 after the user revised locked decision D-01)
- Skipped: 0

## Fixed Issues

### WR-01: Exit-save overwrites the on-disk device entry wholesale, destroying stored state that failed to load

**Files modified:** `src/lifx/devices/ceiling.py`
**Commit:** 4c81917 _(iteration 1)_
**Applied fix:** `_save_state_to_file()` now seeds `device_state` from the existing on-disk entry (`data.get(self.serial, {})`) instead of an empty dict, so in-memory values that are absent (e.g. state rejected by a zone-count mismatch or a partial load failure in `__aenter__`) no longer clobber previously persisted state on exit. Stored values still overwrite their on-disk counterparts when present in memory.

### WR-02: TEST-01 passes when the persisted payload is empty — it does not verify state actually round-trips

**Files modified:** `tests/test_devices/test_state_ceiling.py`
**Commit:** f82fda6 _(iteration 1)_
**Applied fix:** `test_save_on_exit_writes_state_file` now mutates component state in the body via `turn_uplight_off(color=HSBK(hue=120.0, saturation=1.0, brightness=0.8, kelvin=3500))` (explicit colour, because the session-scoped `ceiling_device` fixture is shared across tests and the device's current brightness is not deterministic), deletes the state file inside the body so only the `__aexit__` save can recreate it, and asserts on payload content (`"uplight" in entry`, brightness ≈ 0.8, hue ≈ 120.0). An empty persisted entry now fails the test.

### WR-03: State-file write is non-atomic; exit-save increases exposure to corruption of other devices' entries

**Files modified:** `src/lifx/devices/ceiling.py`
**Commit:** 1ed3e61 _(iteration 1)_
**Applied fix:** `_save_state_to_file()` now dumps JSON to a `tempfile.mkstemp` temp file in the same directory and atomically swaps it in with `os.replace`, unlinking the temp file on any failure. A crash mid-write can no longer truncate the shared state file and lose other devices' entries. Stdlib-only (`os`, `tempfile`), preserving the zero-dependency constraint.

### IN-01: `# pragma: no cover` excludes a branch that TEST-03 deliberately exercises

**Files modified:** `src/lifx/devices/ceiling.py`
**Commit:** 0bb84b3
**Applied fix:** Removed the `# pragma: no cover` comment that excluded the entire `except` clause in `__aexit__` (the clause `test_save_on_exit_body_exception_propagates` deliberately exercises, so its coverage contribution was being silently discarded) and collapsed the awkward multi-line `except (\n    Exception\n) as e:` wrapping back to a single-line `except Exception as e:`.

### IN-03: `from_ip` drops `port`, `timeout`, and `max_retries` on the wrapper instance

**Files modified:** `src/lifx/devices/ceiling.py`
**Commit:** 61d122a
**Applied fix:** `CeilingLight.from_ip` now constructs the returned wrapper as `CeilingLight(device.serial, device.ip, port, timeout, max_retries, state_file=state_file)`, matching the `Device.from_ip` pattern of passing the caller's configuration through to the constructor. The post-construction `ceiling._state_file = state_file` private-attribute assignment was removed. The instance's own attributes now correctly report the caller's port/timeout/max_retries configuration.

### IN-02: Blocking synchronous file I/O inside async `__aexit__`

**Files modified:** `src/lifx/devices/ceiling.py`
**Commit:** 71142ff _(applied after the user revised locked decision D-01)_
**Applied fix:** The `__aexit__` save now runs as `await asyncio.to_thread(self._save_state_to_file)`, moving the file I/O off the event loop. Initially skipped because the remedy conflicted with locked decision D-01 ("synchronous, inline ... No `asyncio.to_thread`"); the user explicitly revisited and relaxed D-01 after review, and the revision is recorded in `01-CONTEXT.md`. The 8 per-operation save call sites remain synchronous inline — only the context-exit path changed.

## Skipped Issues

None.

## Verification

After IN-02 (final state):
- `uv run pytest tests/test_devices/test_state_ceiling.py -k SaveOnExit` — 3 passed
- `uv run ruff format` / `uv run ruff check` — clean
- `uv run pyright` — 0 errors, 0 warnings
- `uv run --frozen pytest` — 2500 passed, 12 deselected (full suite, with the `to_thread` change applied)

Iteration 2 (after IN-01 and IN-03):
- `uv run pytest tests/test_devices/test_state_ceiling.py -k SaveOnExit -v` — 3 passed (after IN-01)
- `uv run pytest tests/test_devices/test_state_ceiling.py` — 16 passed; `tests/test_devices/test_ceiling.py -k from_ip` — 2 passed (after IN-03)
- `uv run ruff format .` — 204 files left unchanged
- `uv run ruff check .` — all checks passed
- `uv run pyright` — 0 errors, 0 warnings
- `uv run --frozen pytest` — 2500 passed, 12 deselected
- Both iteration-2 fix commits passed the project pre-commit hooks (ruff, bandit, codespell) and are GPG-signed with sign-off.

---

_Fixed: 2026-06-12T08:30:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 2_
