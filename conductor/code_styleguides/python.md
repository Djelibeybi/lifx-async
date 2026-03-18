# Python Style Guide: lifx-async

## Formatting (ruff format)

- Line length: 88
- Indent: 4 spaces
- Quotes: double
- Docstring code format: enabled

## Linting (ruff check)

Enabled rule sets: `E`, `F`, `I`, `N`, `W`, `UP`

Per-file ignores:
- `src/lifx/{protocol,products}/generator.py` — E501
- `src/lifx/protocol/packets.py` — E501
- `src/lifx/products/registry.py` — E501
- `benchmarks/*.py` — E501

## Type Checking (pyright)

- Mode: standard
- Target: Python 3.10
- Scope: `src/` directory
- Excluded: `__pycache__`, `generator.py`, `registry.py`

## Conventions

- All imports at the top of the file
- Use `from __future__ import annotations` for forward references
- Type hints required on all public APIs
- `TYPE_CHECKING` guard for import-only type dependencies
- Underscore prefix for private methods/attributes
- Async context managers for resource lifecycle
- No mutable default arguments

## Naming

- Classes: `PascalCase`
- Functions/methods: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- Private: `_leading_underscore`
- Module-level constants: `_LEADING_UNDERSCORE_UPPER`

## Testing

- Test files mirror source: `tests/test_<module>/test_<file>.py`
- Test classes: `Test<Feature>`
- Test functions: `test_<behavior>`
- Use `pytest.mark.parametrize` for data-driven tests
- Async tests: `async def test_*` (auto mode via pytest-asyncio)
