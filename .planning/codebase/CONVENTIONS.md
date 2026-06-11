# Coding Conventions

**Analysis Date:** 2026-06-11

## Naming Patterns

**Files:**
- Snake case with `.py` extension
- Module names describe contents: `protocol_types.py`, `connection.py`, `discovery.py`
- Test files: `test_*.py` (pytest convention)
- Conftest files: `conftest.py` for shared fixtures

**Functions:**
- Snake case: `get_color()`, `set_brightness()`, `allocate_source()`
- Async functions: `async def` with `async_` prefix only if explicitly differentiating sync variant
- Private functions: Leading underscore `_private_function()`
- Factories/helpers: Descriptive names like `create_device()`, `pack_value()`, `unpack_value()`

**Variables:**
- Snake case throughout: `mock_state`, `execution_order`, `response_time`
- Private module-level: `_LOGGER`, `_STRUCT_CACHE`, `_EMULATOR_FIXTURES`, `_EMULATOR_TIMEOUT`
- Constants: UPPER_SNAKE_CASE: `LIFX_UDP_PORT`, `DEFAULT_REQUEST_TIMEOUT`, `MAX_BRIGHTNESS`
- Loop/temporary variables: Short but descriptive: `conn`, `device`, `i`, `item`

**Types:**
- PascalCase: `HSBK`, `Device`, `Light`, `DeviceConnection`, `DiscoveredDevice`
- Dataclass names: `DeviceVersion`, `DeviceInfo`, `FirmwareInfo`, `WifiInfo`, `CollectionInfo`
- Exception classes: `LifxError`, `LifxTimeoutError`, `LifxProtocolError`, `LifxConnectionError`, `LifxUnsupportedCommandError`

## Code Style

**Formatting:**
- Tool: `ruff format`
- Line length: 88 characters
- Indentation: 4 spaces
- Quote style: Double quotes (`"string"`, not `'string'`)
- Docstring code: Formatted with double quotes

**Linting:**
- Tool: `ruff check` with auto-fix
- Selected rules: E (errors), F (Pyflakes), I (isort imports), N (pep8 naming), W (warnings), UP (pyupgrade)
- Generator files exempt: `src/lifx/{protocol,products}/generator.py` and `src/lifx/protocol/packets.py` allow long lines (E501)
- Auto-generated files exempt: `src/lifx/products/registry.py` allows long lines

**Type checking:**
- Tool: `pyright` in standard mode
- Python version: 3.10 (minimum supported)
- Strict on `src/` only
- Excludes: `generator.py` (untyped YAML/JSON handling), `registry.py` (auto-generated)

## Import Organization

**Order:**
1. `from __future__ import annotations` (always first if used)
2. Standard library imports (grouped alphabetically): `import asyncio`, `import logging`, `from dataclasses import dataclass`
3. Third-party imports (grouped alphabetically): `import pytest`, `from lifx_emulator import EmulatedLifxServer`
4. Local imports: `from lifx.color import HSBK`, `from lifx.devices import Light`

**Path Aliases:**
- No aliases configured; imports use full paths
- TYPE_CHECKING block for forward references to avoid circular imports:
  ```python
  if TYPE_CHECKING:
      from lifx.devices import Light, HevLight
  ```

**Barrel Files:**
- `src/lifx/__init__.py` and module `__init__.py` files export public APIs
- Device subpackage: `src/lifx/devices/__init__.py` exports `Device`, `Light`, `HevLight`, etc.
- Products subpackage: `src/lifx/products/__init__.py` exports `get_product()`

## Error Handling

**Patterns:**
- All exceptions inherit from `LifxError` base class
- Specific exception types for different failure modes:
  - `LifxDeviceNotFoundError`: Device unreachable or unknown product ID
  - `LifxTimeoutError`: Operation timeout
  - `LifxProtocolError`: Packet parsing/validation failure
  - `LifxConnectionError`: Connection not open
  - `LifxNetworkError`: UDP/mDNS socket errors
  - `LifxUnsupportedCommandError`: Device returns StateUnhandled
  - `LifxUnsupportedDeviceError`: Device is relay-only or button-only
- Raised with descriptive messages including context where helpful
- Custom exception docstrings document when/why they're raised

**Best practices:**
- Use `try/except` to catch specific exceptions
- Let exceptions propagate unless explicitly handled
- Finally blocks for cleanup (e.g., closing connections)
- Log before raising exceptions for context

## Logging

**Framework:** Built-in `logging` module

**Pattern:**
```python
_LOGGER = logging.getLogger(__name__)
```
- Module-level logger created once per file
- Consistent logger name = module name for filtering

**Levels used:**
- `_LOGGER.debug()`: Detailed protocol/connection events ("Connected to 192.168.1.100")
- `_LOGGER.warning()`: Non-fatal issues ("Response timeout, retrying...")
- `_LOGGER.error()`: Failures that don't crash but prevent operation ("Failed to open UDP socket")

**When to log:**
- Connection lifecycle events (open, close, error)
- Retry attempts with context
- Packet send/receive boundaries
- Network errors and timeouts
- Do NOT log inside loops (performance impact)

## Comments

**When to Comment:**
- **Explain why, not what** - Code should be self-documenting
- Constants and magic numbers: Explain significance
- Non-obvious algorithms: Document approach
- Workarounds: Explain the constraint being worked around
- Section headers: Use comment lines with `-` characters:
  ```python
  # ---------------------------------------------------------------------------
  # sRGB gamma (IEC 61966-2-1)
  # ---------------------------------------------------------------------------
  ```

**Docstrings:**

Google-style format with full type annotations in code (not repeated in docstring):

```python
def pack_value(value: Any, type_name: str) -> bytes:
    """Pack a single value into bytes.

    Args:
        value: Value to pack
        type_name: Type name (e.g., 'uint16', 'float32')

    Returns:
        Packed bytes

    Raises:
        ValueError: If type is unknown
        struct.error: If value doesn't match type
    """
```

- **Modules:** Docstring at top describes purpose and structure
- **Classes:** Describe what the class represents
- **Functions:** One-line summary, then Args/Returns/Raises sections
- **Async functions:** Mark with "async" or indicate `async with` usage
- **Properties:** One-line docstring for simple properties
- **Type hints:** Include in signature, not repeated in docstring

Example docstring with code:
```python
async def create_device(self) -> Device | None:
    """Create appropriate device instance based on product capabilities.

    Example:
        ```python
        devices = await discover_devices()
        for discovered in devices:
            device = await discovered.create_device()
        ```
    """
```

## Function Design

**Size:** Functions should be under 50 lines (aim for <30)

**Parameters:**
- Use keyword arguments for clarity on public APIs
- Single positional argument acceptable (e.g., `get_device_class_for_product(product_id, capabilities)`)
- Multiple parameters prefer explicit type hints:
  ```python
  async def request(self, packet: Packet, source: int, sequence: int) -> Packet | None
  ```

**Return Values:**
- Explicit return type hints always
- Use tuples for multiple returns: `return (color, power, label)`
- None for side-effect-only functions
- Union types for conditional returns: `Device | None`

**Async patterns:**
- Mark async with `async def`
- Use `async with` for context managers
- Use `async for` for async generators
- Use `await` on coroutines (linter enforces)

## Module Design

**Exports:**
- `__all__` lists public API (used by `from module import *`)
- Private items prefixed with `_`
- Public items documented in module docstring

**Module-level code:**
- Logger creation: `_LOGGER = logging.getLogger(__name__)`
- Constants only (no side effects)
- No network calls or I/O in module scope

**Dataclasses:**
- Use `@dataclass` decorator for value objects
- Include type hints on all fields
- Define docstring describing purpose
- Provide field docstrings for complex attributes
- Use `field(default_factory=...)` for mutable defaults
- Use `field(init=False)` for computed fields with `__post_init__`

Example:
```python
@dataclass
class DeviceVersion:
    """Device version information.

    Attributes:
        vendor: Vendor ID (typically 1 for LIFX)
        product: Product ID (identifies specific device model)
    """
    vendor: int
    product: int
```

## Type Annotations

**Pattern:**
- Annotate all function parameters and return types
- Use `from typing import TYPE_CHECKING` for forward references
- Use `from typing_extensions import Self` for self-references (Python 3.10 compat)
- Union types: `X | Y` (Python 3.10+)
- Optional: `X | None` instead of `Optional[X]`
- Collections: `list[X]`, `dict[str, Y]`, `set[int]`
- Callables: `Callable[[int, str], bool]`

**Future annotations:**
- Import `from __future__ import annotations` at file top
- Allows forward references without string quotes
- Used throughout the codebase

## String Formatting

**Style:**
- f-strings preferred: `f"Device {serial} at {ip}"`
- String literals use double quotes: `"string"` not `'string'`
- Multiline strings use triple double quotes: `"""docstring"""`

## Async Context Managers

**Pattern:**
```python
async with connection as conn:
    await conn.send_packet(packet)
```

- Use `async with` for resource management
- Connection/device classes implement `__aenter__` and `__aexit__`
- Lazy opening: Connections may not open until first use
- Explicit close: Can call `await device.connection.close()` to reset

## Common Patterns

**State caching:**
- Store in private attribute: `self._color = (hsbk_value, timestamp)`
- Cache TTL configurable, no automatic expiration
- Always provide `get_*()` methods for volatile state

**Packet building:**
- Use protocol packet classes: `packets.Light.SetColor()`
- Build with keyword arguments
- Send via connection: `await device.connection.request(packet)`

**Discovery:**
- Return `AsyncGenerator` for lazy streaming
- Yields `DiscoveredDevice` namedtuples
- Caller can break early to short-circuit

**Error recovery:**
- Timeout: Retry with exponential backoff
- Network error: Log, propagate, let caller retry
- Device not found: Raise `LifxDeviceNotFoundError`

---

*Convention analysis: 2026-06-11*
