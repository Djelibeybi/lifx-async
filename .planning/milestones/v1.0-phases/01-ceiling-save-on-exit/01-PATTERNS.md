# Phase 1: Ceiling Save-on-Exit — Pattern Map

**Mapped:** 2026-06-12
**Files analysed:** 2 (1 modified source + 1 modified test)
**Analogs found:** 2 / 2

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/lifx/devices/ceiling.py` (add `__aexit__`) | device / context-manager | request-response + file-I/O | `src/lifx/devices/ceiling.py:191` (`__aenter__`) | exact — same class, symmetric hook |
| `tests/test_devices/test_state_ceiling.py` (add class) | test | event-driven (async context manager lifecycle) | `tests/test_devices/test_state_ceiling.py:277` existing emulator tests | exact |

---

## Pattern Assignments

### `src/lifx/devices/ceiling.py` — add `CeilingLight.__aexit__`

**Analog:** `src/lifx/devices/ceiling.py:191-205` (`__aenter__` override)

**Imports pattern** — already present, nothing new needed (lines 19-34):
```python
from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, cast

from lifx.color import HSBK
from lifx.const import DEFAULT_MAX_RETRIES, DEFAULT_REQUEST_TIMEOUT, LIFX_UDP_PORT
from lifx.devices.matrix import MatrixLight, MatrixLightState
from lifx.exceptions import LifxError
from lifx.products import get_ceiling_layout, is_ceiling_product

_LOGGER = logging.getLogger(__name__)
```

**Context manager entry pattern — template to mirror** (lines 191-205):
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

**Parent `__aexit__` signature to match** (`src/lifx/devices/base.py:644-652`):
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

**Guarded save call-site pattern — used at 8 existing sites** (lines 498-499):
```python
if self._state_file:
    self._save_state_to_file()
```

**`_save_state_to_file()` internal error handling — what the belt-and-braces guard wraps** (lines 1263-1316):
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

**Target implementation** (insert after `__aenter__`, before `_initialize_state` at line 207):
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
            _LOGGER.warning("Failed to save state on __aexit__ for %s: %s", self.serial, e)
    await super().__aexit__(exc_type, exc_val, exc_tb)
```

Key points:
- Save runs **before** `super().__aexit__()` (opposite of `__aenter__` where `super()` is first)
- Returns `None` implicitly — never suppresses body exceptions
- `super().__aexit__()` is unconditional — connection cleanup always runs (D-04)
- Log message uses `self.serial` (not `self._state_file`) to distinguish from helper's warning

---

### `tests/test_devices/test_state_ceiling.py` — add `TestCeilingLightSaveOnExit`

**Analog:** `tests/test_devices/test_state_ceiling.py:277-338` (existing `@pytest.mark.asyncio` emulator tests using `CeilingLight.connect()`)

**File header pattern** (lines 1-9):
```python
"""Tests for CeilingLight state management using LIFX Emulator."""

from __future__ import annotations

import pytest

from lifx.color import HSBK
from lifx.devices.ceiling import CeilingLight, CeilingLightState
from lifx.devices.matrix import MatrixLightState
```

Additional imports needed for new class: `import json` (already used in `test_ceiling.py`).

**Emulator test pattern — `async with CeilingLight.connect(...)`** (lines 281-288):
```python
@pytest.mark.asyncio
async def test_initialize_state_creates_ceiling_state(self, ceiling_device) -> None:
    """Test Device.connect() creates CeilingLightState instance."""
    async with await CeilingLight.connect(
        serial=ceiling_device.serial,
        ip=ceiling_device.ip,
        port=ceiling_device.port,
    ) as ceiling_light:
        assert ceiling_light._state is not None
```

**Mock-based `_save_state_to_file` MagicMock pattern** (`tests/test_devices/test_ceiling.py:183`):
```python
ceiling._save_state_to_file = MagicMock()
```
For TEST-03, the monkeypatch target is the instance attribute using `monkeypatch.setattr`.

**New test class to add** (append to end of `test_state_ceiling.py`):
```python
class TestCeilingLightSaveOnExit:
    """Tests for CeilingLight.__aexit__ save-on-exit behaviour."""

    @pytest.mark.asyncio
    async def test_save_on_exit_writes_state_file(
        self, ceiling_device, tmp_path
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

    @pytest.mark.asyncio
    async def test_save_on_exit_no_op_without_state_file(
        self, ceiling_device, tmp_path
    ) -> None:
        """CEIL-02 / TEST-02: no file is created when state_file is None."""
        async with CeilingLight(
            serial=ceiling_device.serial,
            ip=ceiling_device.ip,
            port=ceiling_device.port,
        ):
            pass

        assert not any(tmp_path.iterdir())

    @pytest.mark.asyncio
    async def test_save_on_exit_body_exception_propagates(
        self, ceiling_device, tmp_path, caplog, monkeypatch
    ) -> None:
        """CEIL-03 / TEST-03: body exception propagates; save error logged and swallowed."""
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
                    ceiling,
                    "_save_state_to_file",
                    lambda: (_ for _ in ()).throw(OSError("disk full")),
                )
                raise RuntimeError("body error")

        assert any(
            "disk full" in r.message or "Failed to save" in r.message
            for r in caplog.records
            if r.levelname == "WARNING"
        )
```

Note on `CeilingLight(...)` vs `CeilingLight.connect(...)`: The new tests use the direct constructor form (not `connect()`) because `state_file` is a constructor parameter and `__aenter__` is the first async step. This matches the test examples in RESEARCH.md. The emulator fixture provides the target host; `__aenter__` opens the connection as usual.

---

## Shared Patterns

### Logger usage
**Source:** `src/lifx/devices/ceiling.py:34`
**Apply to:** `__aexit__` implementation
```python
_LOGGER = logging.getLogger(__name__)
```
Log level for the `__aexit__` guard: `_LOGGER.warning(...)` — matches `_save_state_to_file`'s own warning at line 1316.

### `super().__aexit__()` chaining
**Source:** `src/lifx/devices/base.py:644-652`
**Apply to:** `CeilingLight.__aexit__`
Always `await super().__aexit__(exc_type, exc_val, exc_tb)` — never call `close()` directly. This preserves MRO correctness and mirrors how `__aenter__` chains via `super().__aenter__()`.

### Emulator fixture availability
**Source:** `tests/conftest.py:352` (`ceiling_device` fixture)
**Apply to:** All three new test methods
The `ceiling_device` fixture is session-scoped and yields a live `CeilingLight` pointed at the in-process emulator. `tmp_path` is function-scoped (pytest built-in), providing a clean directory per test.

---

## No Analog Found

None — both files have close analogs in the existing codebase.

---

## Metadata

**Analog search scope:** `src/lifx/devices/`, `tests/test_devices/`
**Files scanned:** 4 (`ceiling.py`, `base.py`, `test_state_ceiling.py`, `test_ceiling.py`)
**Pattern extraction date:** 2026-06-12
