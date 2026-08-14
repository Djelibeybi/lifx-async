# Phase 6: Generated Theme Library - Pattern Map

**Mapped:** 2026-08-14
**Files analysed:** 8 new/modified files
**Analogs found:** 7 / 8 (the committed data file has no in-repo analog by design)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/lifx/theme/generator.py` (new) | code generator (script) | file I/O, transform | `src/lifx/products/generator.py` | exact |
| generated theme data module, e.g. `src/lifx/theme/data.py` (new; name at planner's discretion per D-01) | generated data module | static data | `src/lifx/products/registry.py` | exact |
| `data/themes.jsonl` (new; repo data directory outside `src/lifx` per D-03 — no `data/` dir exists yet) | committed data file | static data | `.claude/theme-capture/themes.jsonl` (source, not analog) | n/a |
| `src/lifx/theme/library.py` (rewrite: drop `_THEMES`, keep API) | library/service | request-response (lookup) | itself (lines 407-560) | exact |
| `src/lifx/theme/theme.py` (modify: identity kwargs, `__eq__`) | model | static data | v1.1 keyword-only state-field precedent (D-16) | role-match |
| `src/lifx/theme/__init__.py` (possibly modify exports) | config/barrel | n/a | itself | exact |
| `tests/test_theme/test_library.py`, `test_theme.py` (modify) | test | n/a | themselves | exact |
| `tests/test_theme/test_theme_generator.py` (new) | test | n/a | `tests/test_products/test_product_generator.py` | exact |
| `pyproject.toml` (modify: coverage omit) | config | n/a | existing `[tool.coverage.run] omit` block | exact |

## Which generator is the closer analog — and why

**`src/lifx/products/generator.py` is the closer analog**, decisively:

- It reads one input file, emits one Python module of data literals, then runs ruff over the output — exactly this phase's shape. `protocol/generator.py` is a multi-file, multi-pass template engine driven by a YAML schema with quirk layers; far more machinery than a JSONL→dict emitter needs.
- CONTEXT D-05 explicitly names `products/generator.py::format_generated_files()` as directly reusable, with one deliberate change: format the **temp file**, then atomically rename (products formats in place after writing — do not copy that ordering).
- Difference to note: `products/generator.py` downloads its input from GitHub (`urlopen`). The theme generator must **not** — regeneration must not require a network (SPEC prohibition). Read the committed JSONL from the repo data directory instead. Also drop `products/generator.py`'s in-place `open(output_path, "w")` in favour of temp + `Path.rename()`.

## Pattern Assignments

### `src/lifx/theme/generator.py` (generator, file I/O)

**Analog:** `src/lifx/products/generator.py`

**Ruff formatting pattern** (lines 20-55) — reuse near-verbatim, pointed at the temp file:
```python
def format_generated_files(*paths: Path) -> None:
    """Run `ruff format` and `ruff check --fix` over the generated files. ..."""
    print("Formatting generated code with ruff...")
    targets = [str(path) for path in paths]
    for command in (["format"], ["check", "--fix"]):
        result = subprocess.run(  # nosec B603
            [sys.executable, "-m", "ruff", *command, *targets],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            diagnostics = "\n".join(
                stream.strip()
                for stream in (result.stdout, result.stderr)
                if stream.strip()
            )
            raise RuntimeError(
                f"ruff {command[0]} failed on the generated files:\n{diagnostics}"
            )
```

**Imports pattern** (lines 7-17): `from __future__ import annotations`, then stdlib only (`json`, `subprocess  # nosec B404`, `sys`, `pathlib.Path`) — zero runtime deps holds for the generator too since it uses only dev tooling (ruff) via subprocess.

**Emission pattern** (lines 106-195): build `code_lines: list[str]`, append literal `dict` entries with `repr()` for strings, `"\n".join(code_lines)`. Rely on `format_generated_files` for style, not hand-formatting.

**Output-path + entry-point pattern** (lines 500-536): `main()` with `output_path = Path(__file__).parent / "registry.py"`, `if __name__ == "__main__": main()`, runnable as `uv run python -m lifx.theme.generator`. **Change for D-05:** write to a temp file in the same directory (`output_path.with_suffix(".py.tmp")` or `tempfile.NamedTemporaryFile(dir=output_path.parent)`), run `format_generated_files(temp_path)`, then `temp_path.rename(output_path)` — same-filesystem rename is atomic. Products' `open(output_path, "w")` then format-in-place is the pattern being deliberately superseded.

**Validation-abort pattern** (no analog — new): empty-slug, duplicate-slug and zero-colour records must abort with an error naming the offending display name(s). Follow `format_generated_files`'s style: `raise RuntimeError(f"...")` with the specifics in the message.

**Input data shape** — the raw capture at `.claude/theme-capture/themes.jsonl` (179 records, one JSON object per line):
```json
{"name": "Cheerful", "category": "🙂 MOODS", "index": 1,
 "colors": [{"hue": 265.9954833984375, "saturation": 0.8699931334401465,
             "brightness": 0.4699931334401465, "kelvin": 3500}, ...],
 "suspect_unchanged": false}
```
The new committed file (D-02) is derived from this: slugs pre-resolved, emoji stripped, uint16-normalised, sport dropped, christmas collapsed, `aliases` field on rename targets, `Library` category on orphans, no header record.

---

### Generated theme data module (generated data, static)

**Analog:** `src/lifx/products/registry.py`

**DO-NOT-EDIT header** (lines 1-10) — copy this format exactly, adapted:
```python
"""LIFX product definitions and capability detection.

DO NOT EDIT THIS FILE MANUALLY.
Generated from https://github.com/LIFX/products/blob/master/products.json
by products/generator.py

This module provides pre-generated product information for efficient runtime lookups.
"""

from __future__ import annotations
```
For themes: name the committed data file path and `theme/generator.py` as source/generator, and per SPEC document that palette order is deterministic but carries no meaning.

**Data-literal pattern:** `registry.py` holds `PRODUCTS: dict[int, ProductInfo] = { pid: ProductInfo(...), ... }`. The theme equivalent is a flat dict of 168 slug keys (D-13) mapping to palette + identity data — the emitted `HSBK(...)` literal style already exists in the current `library.py` `_THEMES` (lines 40-405), e.g. `HSBK(hue=31, saturation=1.0, brightness=0.5, kelvin=3500)`.

---

### `src/lifx/theme/library.py` (hand-written API, lookup)

**Analog:** itself — current lines 407-560 are the API to keep, minus `_THEMES`.

**Current `get()`** (lines 407-432) — carries both bugs this phase fixes:
```python
@classmethod
def get(cls, name: str) -> Theme:
    normalized_name = name.lower()
    if normalized_name not in cls._THEMES:
        available = ", ".join(sorted(cls._THEMES.keys()))
        raise KeyError(f"Theme '{name}' not found. Available themes: {available}")
    return Theme(cls._THEMES[normalized_name])
```
Keep: classmethod, `name.lower()` case-insensitivity, `KeyError`. Change: `KeyError` message becomes the name plus a pointer to `get_available_themes()` (drop the full list); return a `Theme` over a **fresh list** (`list(...)` copy) with slug/name/category attached (mutation-leak fix, D-14 for aliases).

**`get_available_themes()`** (lines 434-450): `return sorted(cls._THEMES.keys())` — same shape over the generated dict, 168 names (D-15).

**`get_by_category()`** (lines 452-538): hand-made taxonomy dict, `ValueError` on unknown category — **left untouched and working** against the new data source; Phase 7 owns it. Note its tolerant tail: `if name in cls._THEMES` filters silently, which is why it survives palette resync unchanged.

**Module-level convenience** (lines 541-560): `get_theme(name)` delegates to `ThemeLibrary.get(name)` — untouched, exported in `__all__`.

---

### `src/lifx/theme/theme.py` (model)

**Analog:** itself plus the v1.1 keyword-only-additive precedent (D-16).

**Current constructor** (lines 47-66) — the signature identity extends:
```python
def __init__(self, colors: list[HSBK] | None = None) -> None:
    if colors and len(colors) > 0:
        self.colors: list[HSBK] = colors
    else:
        self.colors = [Colors.WHITE_NEUTRAL]
```
Becomes `def __init__(self, colors=None, *, slug=None, name=None, category=None)` — keyword-only, all defaulting to `None` (D-16/D-17). `Theme([...])` and `Theme()` must behave identically to today.

**Equality pattern** — copy the *documentation style* of `HSBK.__eq__` (`src/lifx/color.py` lines 282-291), not its hash:
```python
def __eq__(self, other: object) -> bool:
    """Two colors are equal if they share the same wire representation. ..."""
    if not isinstance(other, HSBK):
        return NotImplemented
    return self.as_tuple() == other.as_tuple()
```
`Theme.__eq__` compares palette only, as an **unordered multiset** (SPEC: order is never compared). Since `HSBK` is hashable at uint16 granularity (`__hash__` = `hash(self.as_tuple())`, line 293-295), `collections.Counter(self.colors) == Counter(other.colors)` gives multiset equality at protocol precision with no new comparison code. Return `NotImplemented` for non-`Theme`. **Do not define `__hash__`** — defining `__eq__` sets it to `None`, which is the locked outcome (D-20).

**uint16 normalisation for the generator:** `HSBK.as_tuple()` (color.py line 677, returns `tuple[int, int, int, int]`) is the existing uint16 encoding — the generator's THEME-02 normalisation should round-trip captured floats through this rather than reimplementing quantisation.

---

### `src/lifx/theme/__init__.py` (exports)

**Analog:** itself (55 lines, read in full). Current `__all__`: `MatrixGenerator`, `MultiZoneGenerator`, `SingleZoneGenerator`, `Theme`, `ThemeLibrary`, `get_theme`. The `Canvas` comment (lines 43-46) is the house pattern for a deliberate non-export — if the generated data module's dict gets a public-looking name, decide explicitly whether it joins `__all__`, and if not, consider a comment in the same style. Adding no new names is the default.

---

### `tests/test_theme/test_theme_generator.py` (test, new)

**Analog:** `tests/test_products/test_product_generator.py`

**Structure** (lines 1-50): module docstring listing coverage areas; `from __future__ import annotations`; imports the generator's functions directly (`download_products, format_generated_files, generate_product_definitions, generate_registry_file, main`); `unittest.mock` (`Mock, mock_open, patch`) for I/O; plain `@pytest.fixture` functions returning literal dict test data (`minimal_products_data`, `full_featured_product_data`); section-divider comments (`# ====`). Follow the same shape: fixtures with minimal/full JSONL records, tests for slug derivation, empty-slug abort, duplicate-slug abort, zero-colour abort, uint16 normalisation, atomic write (interrupt → target unchanged, via `tmp_path`).

**Coverage config** — `pyproject.toml` lines 130-136, the block D-21/D-22 extend:
```toml
[tool.coverage.run]
omit = [
    "src/lifx/protocol/generator.py",
    "src/lifx/protocol/protocol_types.py",
    "src/lifx/products/generator.py",
]
```
Add `src/lifx/theme/generator.py` and the generated data module. The hand-written `library.py` / `theme.py` changes are NOT omitted — CI needs 100% branch patch coverage on them.

---

### `tests/test_theme/test_library.py`, `test_theme.py` (test, modify)

**Analog:** themselves. Style: plain test classes grouping by method (`TestThemeLibraryGet`, `TestThemeLibraryList`, `TestThemeCreation`, ...), no fixtures needed for library tests (classmethod API), `pytest.raises(KeyError) as exc_info` with message assertions. `tests/test_theme/conftest.py` fixtures (`light`, `matrix_light`, `tile_light`, etc. via `mock_device_factory`) are for device-facing tests — not needed for library/identity tests.

**Tests that will break and must change** (test_library.py):
- `test_get_nonexistent_theme` (lines 27-33) asserts `"Available themes"` in the KeyError — the shortened message changes this.
- `test_list_returns_sorted_list` (line 68) pins `len(themes) == 57` → becomes 168 (but D-23 says pin nothing; drop the count).
- `test_get_specific_themes` (lines 45-57) pins colour counts (`christmas` 4, `halloween` 6, ...) — resynced palettes change these; per D-23, do not pin counts against the new data.
- COMPAT-01 test pattern: parametrise over a **literal** 57-key fixture list (SPEC: not derived from the library) — `@pytest.mark.parametrize` over a module-level tuple.

## Shared Patterns

### DO-NOT-EDIT header
**Source:** `src/lifx/products/registry.py` lines 1-10 (excerpt above)
**Apply to:** the generated theme data module.

### Ruff-over-output formatting
**Source:** `src/lifx/products/generator.py::format_generated_files()` lines 20-55 (excerpt above)
**Apply to:** theme generator, run on the temp file before rename (D-05 ordering).

### Case-insensitive lookup
**Source:** `library.py::get()` line 428 (`name.lower()`)
**Apply to:** `get()` unchanged; D-07's category storage is Title Case with case-insensitive lookup following the same style.

### Keyword-only additive fields
**Source:** precedent named by D-16 — v1.1's `fetch_wifi_info` / `fetch_ambient_light` (see `src/lifx/devices/` state dataclasses; CLAUDE.md "Opt-in state fields")
**Apply to:** `Theme` identity kwargs.

### uint16-granularity comparison
**Source:** `src/lifx/color.py` `HSBK.__eq__`/`__hash__`/`as_tuple()` (lines 282-295, 677)
**Apply to:** `Theme.__eq__` multiset comparison and generator palette normalisation.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `data/themes.jsonl` (committed data file) | data | static | No repo data directory outside the package exists today; the format is defined by D-02, not by precedent. `.claude/theme-capture/themes.jsonl` is its *source*, and the JSONL record shape above is the starting shape. `pyproject.toml` `packages = ["src/lifx"]` (line 66) already excludes anything outside `src/lifx` from the wheel, satisfying D-03 with no packaging change. |

## Metadata

**Analog search scope:** `src/lifx/theme/`, `src/lifx/products/`, `src/lifx/protocol/` (generator comparison only), `src/lifx/color.py`, `tests/test_theme/`, `tests/test_products/`, `pyproject.toml`, `.claude/theme-capture/`
**Files scanned:** 12
**Pattern extraction date:** 2026-08-14
