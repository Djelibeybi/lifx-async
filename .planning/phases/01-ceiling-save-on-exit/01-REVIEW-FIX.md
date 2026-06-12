---
phase: 01-ceiling-save-on-exit
fixed_at: 2026-06-12T07:45:00Z
review_path: .planning/phases/01-ceiling-save-on-exit/01-REVIEW.md
iteration: 1
findings_in_scope: 3
fixed: 3
skipped: 0
status: all_fixed
---

# Phase 1: Code Review Fix Report

**Fixed at:** 2026-06-12T07:45:00Z
**Source review:** .planning/phases/01-ceiling-save-on-exit/01-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 3 (fix_scope: critical_warning — 0 Critical, 3 Warning; 3 Info findings out of scope)
- Fixed: 3
- Skipped: 0

## Fixed Issues

### WR-01: Exit-save overwrites the on-disk device entry wholesale, destroying stored state that failed to load

**Files modified:** `src/lifx/devices/ceiling.py`
**Commit:** 4c81917
**Applied fix:** `_save_state_to_file()` now seeds `device_state` from the existing on-disk entry (`data.get(self.serial, {})`) instead of an empty dict, so in-memory values that are absent (e.g. state rejected by a zone-count mismatch or a partial load failure in `__aenter__`) no longer clobber previously persisted state on exit. Stored values still overwrite their on-disk counterparts when present in memory.

### WR-02: TEST-01 passes when the persisted payload is empty — it does not verify state actually round-trips

**Files modified:** `tests/test_devices/test_state_ceiling.py`
**Commit:** f82fda6
**Applied fix:** `test_save_on_exit_writes_state_file` now mutates component state in the body via `turn_uplight_off(color=HSBK(hue=120.0, saturation=1.0, brightness=0.8, kelvin=3500))` (explicit colour, because the session-scoped `ceiling_device` fixture is shared across tests and the device's current brightness is not deterministic), deletes the state file inside the body so only the `__aexit__` save can recreate it, and asserts on payload content (`"uplight" in entry`, brightness ≈ 0.8, hue ≈ 120.0). An empty persisted entry now fails the test.

### WR-03: State-file write is non-atomic; exit-save increases exposure to corruption of other devices' entries

**Files modified:** `src/lifx/devices/ceiling.py`
**Commit:** 1ed3e61
**Applied fix:** `_save_state_to_file()` now dumps JSON to a `tempfile.mkstemp` temp file in the same directory and atomically swaps it in with `os.replace`, unlinking the temp file on any failure. A crash mid-write can no longer truncate the shared state file and lose other devices' entries. Stdlib-only (`os`, `tempfile`), preserving the zero-dependency constraint.

## Verification

- `uv run ruff format --check .` — 204 files already formatted
- `uv run ruff check .` — all checks passed
- `uv run pyright` — 0 errors, 0 warnings
- `uv run --frozen pytest` — 2500 passed, 12 deselected
- All three fix commits passed the project pre-commit hooks (ruff, bandit, codespell) and are GPG-signed with sign-off.

---

_Fixed: 2026-06-12T07:45:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
