# Phase 7: Taxonomy & Legacy Dispositions - Pattern Map

**Mapped:** 2026-08-15
**Files analysed:** 10 new/modified files
**Analogs found:** 10 / 10 (all changes are extensions of existing files or siblings of existing pages — every file has a direct analog, usually itself)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/lifx/theme/library.py` | service (lookup API) | request-response | itself — `ThemeLibrary.get()` at :59-95 | exact (self-analog) |
| `src/lifx/theme/theme.py` | model | in-memory | itself — Phase 6 identity fields at :64-101 | exact (self-analog) |
| `src/lifx/theme/data.py` | generated model | batch (generated) | itself — regenerated, never hand-edited | exact |
| `scripts/generate_theme_data.py` | generator/utility | file-I/O + validation | itself — `validate_records()` :248, `_fail()` :161 | exact (self-analog) |
| package-side slug helper (new home for `derive_slug`, per D-04) | utility | transform | `src/lifx/geometry.py` (single-rule shared helper module) + `derive_slug()` at `scripts/generate_theme_data.py:110-125` | role-match |
| `data/themes.jsonl` | data file | file-I/O | itself — existing 166-line record shape | exact |
| `tests/test_theme/test_theme_generator.py` | test | batch | itself — `TestValidateRecords` failing-record tests :278-305 | exact |
| `tests/test_theme/test_library.py` | test | request-response | itself — `PRE_V12_KEYS` at :15, parametrised at :373 | exact |
| `docs/migration/theme-taxonomy-v1.2.md` | docs (new page) | n/a | `docs/migration/effect-api-changes.md` | exact |
| `mkdocs.yml` + `docs/api/themes.md` :55-71 + `docs/getting-started/themes.md` :20-32 | config/docs | n/a | existing `Migration:` nav entries at mkdocs.yml:149-150 and :223-224 | exact |

## Pattern Assignments

### `src/lifx/theme/library.py` (service, request-response)

**Analog:** itself — copy the shape of `get()` and the existing error message style.

**Lookup + controlled error pattern** (`library.py:80-95`):
```python
normalized_name = name.lower()
if normalized_name not in cls._THEMES:
    raise KeyError(
        f"Theme '{name}' not found. Use "
        f"ThemeLibrary.get_available_themes() to list the "
        f"available themes."
    )
record = cls._THEMES[normalized_name]
# Theme.__init__ copies the palette, so mutating a returned Theme can
# never corrupt the library's own record.
return Theme(
    list(record.colors),
    slug=record.slug,
    name=record.name,
    category=record.category,
)
```
`get()` is where the two new keyword args (`disposition=record.disposition, replaced_by=record.replaced_by`) are threaded (SPEC R5).

**Unknown-category error style** (`library.py:190-195` — keep this message shape for the rewritten raising branch, listing available categories per SPEC edge coverage):
```python
if category_lower not in categories:
    available = ", ".join(sorted(categories.keys()))
    raise ValueError(
        f"Category '{category}' not recognized. "
        f"Available categories: {available}"
    )
```
Note: existing text uses "recognized"; user rules mandate Australian English — new/changed messages should use "recognised" (flag in plan; the old string is being deleted anyway).

**Subclass-safe indirection** (`library.py:53-57`) — all new lookups (`get_categories()`, rewritten `get_by_category()`, legacy map branch) must read `cls._THEMES`, never module-global `THEMES`:
```python
# The generated theme registry. Every lookup classmethod reads this class
# attribute rather than the module-global `THEMES`, ...
_THEMES: dict[str, ThemeRecord] = THEMES
```

**Delete:** the hardcoded 6-key dict at :130-188, the stale docstring at :120 (`time` category), the `get_by_category("seasonal")` example at :46.

**Module-level private constant pattern (D-01/D-02):** `_LEGACY_CATEGORIES: dict[str, tuple[str, bool]]` — analog for a documented module-level private constant with a `#:` docstring is `scripts/generate_theme_data.py:44-54`:
```python
#: Fields every record must carry.
_REQUIRED_FIELDS = frozenset({"slug", "name", "category", "colors"})
```

---

### `src/lifx/theme/theme.py` (model, in-memory)

**Analog:** itself — the D-16/D-17 keyword-only optional identity pattern (`theme.py:64-101`):
```python
def __init__(
    self,
    colors: list[HSBK] | None = None,
    *,
    slug: str | None = None,
    name: str | None = None,
    category: str | None = None,
) -> None:
    ...
    self.slug = slug
    self.name = name
    self.category = category
```
Append `disposition: str | None = None, replaced_by: str | None = None` in the same keyword-only block; assign the same way. Extend the class docstring `Attributes:` block (:22-29) with the same "(None for a caller-constructed theme)" phrasing.

**Do not touch:** `palette_equals()` (:223-260 — `Counter(self.colors) == Counter(other.colors)`, ignores identity fields already) and identity `__eq__`/hashability — SPEC R5 pins both unchanged.

---

### `scripts/generate_theme_data.py` (generator, file-I/O + validation)

**Analog:** itself.

**Schema field sets** (:47-51) — add `"disposition"` to required, `"replaced_by"` to optional:
```python
_REQUIRED_FIELDS = frozenset({"slug", "name", "category", "colors"})
_OPTIONAL_FIELDS = frozenset({"aliases"})
```
Add an allowed-set constant in the same style, e.g. `_DISPOSITIONS = frozenset({"lifx-app", "library-only", "deprecated"})`.

**Controlled-abort pattern** (:161-165) — the three new validations (disposition in set; deprecated requires `replaced_by`; `replaced_by` resolves) each raise via `_fail`:
```python
def _fail(line_number: int, record: Any, message: str) -> RuntimeError:
    """Build the controlled validation error naming record and JSONL line."""
    return RuntimeError(
        f"themes.jsonl line {line_number}: record '{_record_label(record)}': {message}"
    )
```
Existing per-field validation to copy (`validate_records()` :285-300, the name/category string checks):
```python
for field in ("name", "category"):
    value = record[field]
    if type(value) is not str:
        raise _fail(line_number, record, f"field '{field}' is not a string: {value!r}")
    if not value:
        raise _fail(line_number, record, f"field '{field}' is empty")
```
Note `replaced_by`-resolves-in-`THEMES` is a cross-record check: the analog is the `seen_keys` collision pass at :262, :329-335 — collect keys (slug + aliases) in a first pass or after the loop, then verify every `replaced_by` against the collected key set (aliases count, since SPEC says "resolves in `THEMES`").

**Emit pattern** (`emit_data_module()` :432-466) — add the two `ThemeRecord` field lines and the two per-record kwarg lines in the same style, with the same emit-time backstop shape (:451-457):
```python
lines.append(f"    {slug!r}: ThemeRecord(")
lines.append(f"        slug={slug!r},")
lines.append(f"        name={name!r},")
lines.append(f"        category={category!r},")
```
Emit `replaced_by={value!r}` so `None` prints as `None`. **Do not disturb the alias emission at :469-482** — aliases are assigned *after* the dict literal, binding the target's record (R7's identity guarantee).

**D-04 shared-slug move:** `derive_slug()` (:110-125) moves *into the package* and the generator imports it (generator already imports from `lifx`: see :31-33 `from lifx.color import HSBK` etc.). Rule to relocate verbatim:
```python
return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
```
Package-side home analog: `src/lifx/geometry.py` is the precedent for "one rule, one small module, stated once" (per CLAUDE.md). A private helper inside `lifx/theme/` (e.g. next to `library.py`, imported by both library and generator) also fits; planner decides placement, but the implementation must be the single shared function.

---

### `src/lifx/theme/data.py` (generated)

**Analog:** itself. Never hand-edited — regenerate with `uv run scripts/generate_theme_data.py`. `ThemeRecord` gains:
```python
disposition: str
replaced_by: str | None = None
```
(D-06: default `None`, dataclass stays frozen. `disposition` non-optional on the record.) Docstring header lines are emitted by the generator (:407-423) — extend there, not in data.py. THEME-04: regeneration must be byte-idempotent after the change; CI diffs data.py on any `data/**` change.

---

### `data/themes.jsonl` (data file)

**Analog:** existing line shape (line 1):
```json
{"slug": "arctic", "name": "Arctic", "category": "Library", "colors": [...]}
```
Every one of the 166 lines gains `"disposition"`; the 9 deprecated records also gain `"replaced_by"`. 140 records with app categories → `"lifx-app"`; the 28 `Library` records split 9 deprecated / 19 library-only per SPEC R4's locked table. Mechanics (scripted rewrite recommended — deferred to planner per CONTEXT). Keep JSON key order consistent per line so future diffs stay clean; a one-off script in scratchpad or `scripts/` can do the rewrite.

---

### `tests/test_theme/test_theme_generator.py` (test)

**Analog:** itself — `TestValidateRecords` failing-record pattern (:278-286):
```python
def test_missing_required_field_aborts(self) -> None:
    """A record missing a required field aborts naming record and line."""
    record = _record()
    del record["category"]

    with pytest.raises(
        RuntimeError, match=r"line 1.*Test Theme.*missing required field.*category"
    ):
        validate_records(_pairs(record))
```
Helpers to reuse: `_record(**overrides)` (:68-77 — will need `"disposition": "lifx-app"` added to stay minimal-valid), `_pairs()` (:80-82), `_exec_module()` (:85-89). D-08 pins exactly three new failing-record tests (bad disposition value; deprecated without `replaced_by`; `replaced_by` not resolving) in this file. No count-pinning invariant test (declined per D-08/D-23).

---

### `tests/test_theme/test_library.py` (test)

**Analog:** itself — `PRE_V12_KEYS` tuple at :15 with parametrised resolution at :373:
```python
@pytest.mark.parametrize("key", PRE_V12_KEYS)
```
New tests follow the existing class-per-method structure in this file: `get_categories()` exact-list assertion, `get_by_category()` for all 9 + normalised forms + unknown/empty raises, legacy 2-resolve/4-raise (message contains replacement), and `Theme.disposition`/`replaced_by` surfacing via `get()`. Remember CI requires 100% **branch** patch coverage — every raise branch and both legacy fates need tests.

---

### `docs/migration/theme-taxonomy-v1.2.md` (new docs page)

**Analog:** `docs/migration/effect-api-changes.md` — heading style, Overview section, numbered change list, Before/After fenced code blocks:
```markdown
# Effect API Changes (v4.3.0)

This document describes changes to the effect handling API introduced in version 4.3.0.

## Overview
...
**Before:**
```python
...
```
**After:**
```
Per D-10 the page is stamped "As of migration" (point-in-time record; counts are historical claims, no CI pinning). Must table: 9 categories with counts, all 6 legacy names with map/raise fate, 9 deprecated keys with replacements. Prohibition: never present `Library` as an app-defined category.

**Nav:** `mkdocs.yml` has the `Migration:` section in **two places** — :149-150 (llms/full_output nav) and :223-224 (main nav). Add the page to both, alongside `migration/effect-api-changes.md`.

---

### Doc corrections (D-11, 4 stale sites)

1. `library.py:120` — docstring `(seasonal, mood, holiday, time, etc.)` → the 9 real names.
2. `library.py:46` — class example `get_by_category("seasonal")` → an app category.
3. `docs/api/themes.md:67-71` — the `!!! note "get_by_category() still uses the older grouping"` admonition is now false; remove/replace. (Existing table at :55-65 already lists the 9 categories with counts — reusable as the migration page's count source.)
4. `docs/getting-started/themes.md:30-31` — `get_by_category("holiday")` / `("mood")` still resolve but re-point at `"Holidays"` / `"Moods"`.

## Shared Patterns

### Case-insensitive + slug normalisation (house style)
**Source:** `library.py:80` (`name.lower()`) + `scripts/generate_theme_data.py:125` (D-09 rule)
**Apply to:** app-taxonomy lookup, legacy lookup, `get_by_category()` input — both sides pass through the shared slug rule so `"Art Series"` / `"art_series"` / `"HOLIDAY"` agree and `"artseries"` raises.

### Keyword-only optional additive fields
**Source:** `theme.py:64-71`
**Apply to:** `Theme` (both new fields) — keeps `Theme([...])` working (SPEC additive constraint).

### Controlled generator abort naming record + line
**Source:** `scripts/generate_theme_data.py:161-165` (`_fail`)
**Apply to:** all three new validations.

### Export decision
**Source:** `src/lifx/theme/__init__.py:47-54` (`__all__` list; note the deliberate-omission comment pattern for `Canvas` at :43-46)
**Apply to:** `get_categories()` is a `ThemeLibrary` classmethod so `__all__` likely needs no change, but confirm nothing new module-level is exported; `_LEGACY_CATEGORIES` stays out (D-03).

### No-network prohibition check
Existing Phase 6 tests T-06-03/T-06-06 assert no network imports in `src/lifx/theme/` — the new code must keep passing them; SPEC names this as the verification for the no-network prohibition.

## No Analog Found

None — every file has a direct analog.

## Metadata

**Analog search scope:** `src/lifx/theme/`, `scripts/`, `tests/test_theme/`, `docs/`, `mkdocs.yml`
**Files scanned:** 12 read/excerpted
**Pattern extraction date:** 2026-08-15
