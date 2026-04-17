# Coding Conventions

**Analysis Date:** 2026-04-16

## Naming Patterns

**Files:**
- Use `snake_case.py` for all Python source files
- Module files match their primary class/purpose: `light.py` for `Light`, `connection.py` for `DeviceConnection`
- Test files use `test_` prefix: `test_light.py`, `test_connection.py`
- State management tests use `test_state_` prefix: `test_state_light.py`, `test_state_ceiling.py`
- Auto-generated files: `packets.py`, `protocol_types.py`, `registry.py` — never edit manually

**Functions:**
- Use `snake_case` for all functions and methods
- Async methods: `async def get_color()`, `async def set_color()`
- Private methods: prefix with `_` (e.g., `_initialize_state()`, `_raise_if_unhandled()`)
- Factory methods: `from_ip()`, `from_string()`, `from_protocol()`, `from_rgb()`
- Getter/setter pairs: `get_color()` / `set_color()`, `get_power()` / `set_power()`
- Conversion methods: `to_protocol()`, `to_string()`, `to_rgb()`

**Variables:**
- Use `snake_case` for all variables
- Module-level constants: `UPPER_SNAKE_CASE` with `Final` type annotation
- Private module-level constants: `_UPPER_SNAKE_CASE` (e.g., `_LOGGER`, `_RETRY_SLEEP_BASE`)
- Logger: always `_LOGGER = logging.getLogger(__name__)`

**Types/Classes:**
- Use `PascalCase` for classes: `Light`, `DeviceConnection`, `UdpTransport`
- Dataclasses: `PascalCase` (e.g., `DeviceVersion`, `FirmwareInfo`, `CollectionInfo`)
- State dataclasses: `{Device}State` pattern (e.g., `LightState`, `HevLightState`, `CeilingLightState`)
- Exception classes: `Lifx{Category}Error` pattern (e.g., `LifxTimeoutError`, `LifxConnectionError`)
- TypeVars: single uppercase letter `T` or descriptive `TypeVar("T")`

**Constants:**
- Defined in `src/lifx/const.py` with `Final` type annotations
- Grouped by category with section headers using `# ====` comment blocks
- Named constants for all magic numbers: `LIFX_UDP_PORT`, `MAX_PACKET_SIZE`, `DEFAULT_REQUEST_TIMEOUT`
- Kelvin presets: `KELVIN_CANDLELIGHT`, `KELVIN_NEUTRAL`, `KELVIN_DAYLIGHT`, etc.

## Code Style

**Formatting:**
- Tool: Ruff formatter
- Line length: 88 characters
- Indent: 4 spaces
- Quote style: double quotes
- Docstring code format: enabled
- Config: `[tool.ruff.format]` section in `pyproject.toml`

**Linting:**
- Tool: Ruff linter
- Selected rules: `E` (pycodestyle errors), `F` (Pyflakes), `I` (isort), `N` (naming), `W` (warnings), `UP` (pyupgrade)
- Per-file ignores for auto-generated code: E501 allowed in `packets.py`, `registry.py`, generators, benchmarks
- Config: `[tool.ruff.lint]` section in `pyproject.toml`

**Type Checking:**
- Tool: Pyright in `standard` mode
- Target: Python 3.10
- Scope: `src/` directory only (excludes generators and auto-generated registry)
- Library ships `py.typed` marker (`src/lifx/py.typed`)
- Full type hints on all public APIs including return types

## Import Organisation

**Order (enforced by Ruff isort):**
1. `from __future__ import annotations` — **first non-docstring statement** in every module (71+ files); a module-level docstring may precede it
2. Standard library imports (`asyncio`, `logging`, `time`, `dataclasses`, etc.)
3. Third-party imports (only in tests: `pytest`, `lifx_emulator`)
4. Local imports using package-relative paths (`from lifx.color import HSBK`)

**Path Aliases:**
- No path aliases configured — all imports use full package paths
- Always import from the public package: `from lifx.devices.light import Light`
- Use `TYPE_CHECKING` guard for imports only needed for type annotations:
```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing_extensions import Self
    from lifx.devices import Light
```

**Pattern:**
```python
"""Module docstring."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from lifx.const import DEFAULT_REQUEST_TIMEOUT
from lifx.exceptions import LifxTimeoutError

if TYPE_CHECKING:
    from typing_extensions import Self

_LOGGER = logging.getLogger(__name__)
```

## Error Handling

**Exception hierarchy** (`src/lifx/exceptions.py`):
- All exceptions inherit from `LifxError`
- Use specific exception types: `LifxTimeoutError`, `LifxConnectionError`, `LifxProtocolError`, `LifxNetworkError`, `LifxDeviceNotFoundError`, `LifxUnsupportedCommandError`, `LifxUnsupportedDeviceError`
- Validate inputs with `ValueError` and descriptive `match` messages:
```python
if not 0.0 <= brightness <= 1.0:
    raise ValueError("Brightness must be between 0.0 and 1.0")
```

**Error raising patterns:**
- Use `_raise_if_unhandled(state)` to check for `StateUnhandled` responses from devices
- Timeout handling wraps `asyncio.wait_for()` with `LifxTimeoutError`
- Connection errors raise `LifxConnectionError` when operations attempted on closed connections

**Context managers:**
- All devices and connections implement `async with` for automatic cleanup
- Pattern: `async with await Light.from_ip("192.168.1.100") as light:`

## Logging

**Framework:** Python standard library `logging`

**Pattern:**
- Module-level logger: `_LOGGER = logging.getLogger(__name__)` (19+ modules)
- Structured debug logging with dicts:
```python
_LOGGER.debug(
    {
        "class": "Device",
        "method": "get_color",
        "action": "query",
        "reply": {
            "hue": state.color.hue,
            "saturation": state.color.saturation,
        },
    }
)
```

**When to log:**
- `debug`: All device request/response pairs, connection state changes
- `warning`: Dropped packets, unexpected responses
- Do not log at `info` or higher in library code (leave for application developers)

## Comments

**When to Comment:**
- Section headers in `const.py` use `# ====` block separators
- Inline comments for non-obvious protocol behaviour or workarounds
- Never comment obvious code

**Docstrings:**
- Google-style docstrings on all public classes, methods, and functions
- Include `Args:`, `Returns:`, `Raises:`, `Example:` sections as applicable
- Docstring code examples use fenced Python blocks
- Module-level docstrings describe the module's purpose

**Pattern:**
```python
async def set_color(
    self,
    color: HSBK,
    duration: float = 0.0,
) -> None:
    """Set light color.

    Args:
        color: HSBK color to set
        duration: Transition duration in seconds (default 0.0)

    Raises:
        LifxDeviceNotFoundError: If device is not connected
        LifxTimeoutError: If device does not respond

    Example:
        ```python
        await light.set_color(HSBK.from_rgb(1.0, 0.0, 0.0))
        ```
    """
```

## Function Design

**Size:** Functions tend to be focused and single-purpose. Device methods typically: build packet, send request, parse response, update cache, log.

**Parameters:**
- Use keyword arguments with defaults for optional params: `duration: float = 0.0`
- Duration parameters accept seconds (float), convert to milliseconds for protocol internally
- Use `HSBK` for user-facing colour, `LightHsbk` for protocol-level colour

**Return Values:**
- Getters return tuples for multi-value responses: `get_color() -> tuple[HSBK, int, str]`
- Setters return `None`
- Factory methods return `Self` or the constructed type
- Properties expose cached state without network calls

## Module Design

**Exports:**
- Each package has an `__init__.py` with explicit `__all__` list
- Main `src/lifx/__init__.py` re-exports all public API symbols (170 items)
- Use `__all__` to control public interface

**Barrel Files:**
- `src/lifx/__init__.py` acts as the main barrel file for the entire library
- Sub-packages (`devices`, `effects`, `products`, `theme`) have their own `__init__.py` with re-exports

**Dataclass Usage:**
- Prefer `@dataclass` for value objects and state containers
- Use `@dataclass(frozen=True)` for immutable value types (e.g., `Serial`, `EffectInfo`)
- Include `as_dict` property for serialisation where needed
- Use `field(init=False)` for computed fields (e.g., `WifiInfo.rssi`)

**Generics:**
- `Device` class uses `Generic[TypeVar]` for state type: `Device[LightState]`, `Device[HevLightState]`

**Future Annotations:**
- Every module uses `from __future__ import annotations` as its first non-docstring statement (after any module-level docstring) for PEP 604 union syntax (`X | Y`) and forward references

---

*Convention analysis: 2026-04-16*
