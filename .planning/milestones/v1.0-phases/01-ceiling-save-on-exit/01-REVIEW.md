---
phase: 01-ceiling-save-on-exit
reviewed: 2026-06-12T07:02:32Z
depth: standard
files_reviewed: 2
files_reviewed_list:
  - src/lifx/devices/ceiling.py
  - tests/test_devices/test_state_ceiling.py
findings:
  critical: 0
  warning: 3
  info: 3
  total: 6
status: issues_found
---

# Phase 1: Code Review Report

**Reviewed:** 2026-06-12T07:02:32Z
**Depth:** standard
**Files Reviewed:** 2
**Status:** issues_found

## Summary

Reviewed the `CeilingLight.__aexit__` save-on-exit override and the new `TestCeilingLightSaveOnExit` emulator test class (diff f7e6015..HEAD), with the full files read for context. The core change is structurally sound: the override signature matches the parent (`Device.__aexit__` at `src/lifx/devices/base.py:644` returns `None`, so there is no exception-suppression contract to preserve), the save runs before `super().__aexit__()` closes the connection, the body exception is never replaced, and `_save_state_to_file()` itself catches all exceptions so the connection cleanup is unconditional. Ruff lint and format both pass on the reviewed files.

However, the new exit-save changes the persistence contract in a way that can destroy previously stored on-disk state (WR-01), the primary positive test asserts only that an entry key exists — it passes when the persisted payload is an empty dict (WR-02), and the now-on-every-exit write path is non-atomic, putting other devices' entries in a shared state file at risk on a crash mid-write (WR-03).

## Warnings

### WR-01: Exit-save overwrites the on-disk device entry wholesale, destroying stored state that failed to load

**File:** `src/lifx/devices/ceiling.py:222-231` (interacting with `:1268-1282` and `:1330`)
**Issue:** `__aexit__` now calls `_save_state_to_file()` on every context exit. That helper rebuilds `device_state` purely from in-memory `stored_uplight_color` / `stored_downlight_colors` and assigns `data[self.serial] = device_state`, replacing the entire on-disk entry. Before this phase, a read-only session never rewrote the file; now it always does. Any stored state that `_load_state_from_file()` rejected or failed to load in `__aenter__` is therefore permanently destroyed on exit:

- Zone-count mismatch (line 1277): the on-disk `downlight` entry is ignored in memory, then wiped from disk at exit.
- Partial load failure (e.g. `KeyError` on a malformed `uplight_data["hue"]` at line 1251 aborts the whole load via the outer `except` at line 1286): whatever did not survive into memory is wiped at exit.
- A do-nothing session against a fresh device writes `data[serial] = {}`, accumulating empty entries.

The data at risk is exactly the data this feature exists to preserve.
**Fix:** Merge instead of replace in `_save_state_to_file()`, so absent in-memory values do not clobber on-disk ones:
```python
device_state = data.get(self.serial, {})
if state.stored_uplight_color is not None:
    device_state["uplight"] = {...}
if state.stored_downlight_colors:
    device_state["downlight"] = [...]
data[self.serial] = device_state
```
Alternatively (or additionally), skip the exit-save when nothing was stored and nothing changed during the session (dirty flag), so a read-only session never rewrites the file.

### WR-02: TEST-01 passes when the persisted payload is empty — it does not verify state actually round-trips

**File:** `tests/test_devices/test_state_ceiling.py:444-462`
**Issue:** On a fresh emulated device, `stored_uplight_color` and `stored_downlight_colors` are `None`, so the exit-save writes `{"d073d5000100": {}}`. The test's only content assertion is `ceiling_device.serial in data`, which passes for that empty dict. The test therefore verifies that the save mechanism fired, but would also pass if `_save_state_to_file()` persisted no usable state at all. It also cannot distinguish the `__aexit__` save from the per-operation saves already wired into every mutating method.
**Fix:** Mutate component state in the body, then delete the file inside the body so only the `__aexit__` save can recreate it, and assert on payload content:
```python
async with CeilingLight(..., state_file=str(state_file)) as ceiling:
    await ceiling.turn_uplight_off()  # populates stored_uplight_color (and saves)
    state_file.unlink()               # only __aexit__ can recreate it now

data = json.loads(state_file.read_text())
entry = data[ceiling_device.serial]
assert "uplight" in entry
assert entry["uplight"]["brightness"] > 0
```

### WR-03: State-file write is non-atomic; exit-save increases exposure to corruption of other devices' entries

**File:** `src/lifx/devices/ceiling.py:1336-1337`
**Issue:** `_save_state_to_file()` opens the target file with `"w"` and `json.dump()`s directly into it. A crash, SIGKILL, or power loss mid-write leaves a truncated/corrupt JSON file — and because the file is keyed by serial and shared across devices, every device's stored state is lost, not just this one's. This is pre-existing code, but the new `__aexit__` hook executes it on every context exit (including process-shutdown paths where interruption is most likely), materially increasing the exposure window. Note that recovery is also lossy: a corrupt file makes the next session's load fail, leaving stored state `None`, after which WR-01 finishes the job.
**Fix:** Write to a temp file in the same directory, then atomically replace (stdlib-only, preserving the zero-dependency constraint):
```python
import os, tempfile

fd, tmp = tempfile.mkstemp(dir=state_path.parent, suffix=".tmp")
try:
    with os.fdopen(fd, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, state_path)
except BaseException:
    os.unlink(tmp)
    raise
```

## Info

### IN-01: `# pragma: no cover` excludes a branch that TEST-03 deliberately exercises

**File:** `src/lifx/devices/ceiling.py:225-227`
**Issue:** The pragma on line 227 is part of the multi-line `except (Exception) as e:` statement; coverage.py maps excluded raw lines to the statement's first line and excludes the whole clause. So the exact path that `test_save_on_exit_body_exception_propagates` monkeypatches `_save_state_to_file` to reach is marked "uncoverable" — the test's coverage contribution is silently discarded, and a future regression that makes the warning log unreachable would not show up as a coverage drop. The comment's claim ("helper also catches") is true for production paths but contradicted by the test.
**Fix:** Remove the pragma (the path is covered) and collapse the awkward `except (\n    Exception\n) as e:` wrapping back to `except Exception as e:`.

### IN-02: Blocking synchronous file I/O inside async `__aexit__`

**File:** `src/lifx/devices/ceiling.py:224`
**Issue:** `_save_state_to_file()` performs synchronous `open`/`json.dump`/`mkdir` on the event loop. The file is small so the stall is minor, and this matches the pre-existing per-operation save pattern under the zero-dependency constraint — noting it only because `__aexit__` now runs it on every context exit. If it ever becomes a problem, `await asyncio.to_thread(self._save_state_to_file)` is a stdlib-only mitigation.
**Fix:** Optional: `asyncio.to_thread`; otherwise accept as a documented trade-off.

### IN-03: Pre-existing — `from_ip` drops `port`, `timeout`, and `max_retries` on the wrapper instance

**File:** `src/lifx/devices/ceiling.py:332`
**Issue:** Outside the diff but in the reviewed file: `CeilingLight(device.serial, device.ip)` constructs the returned instance with default port/timeout/max_retries, ignoring the caller's arguments. The reused `device.connection` masks this in practice, but the instance's own attributes misreport the configuration and any future code reading `self.timeout`/`self.max_retries` on the wrapper gets defaults.
**Fix:** `CeilingLight(device.serial, device.ip, port, timeout, max_retries, state_file=state_file)` (which also removes the post-construction `ceiling._state_file = state_file` assignment).

---

_Reviewed: 2026-06-12T07:02:32Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
