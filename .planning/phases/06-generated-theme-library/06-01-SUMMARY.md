---
phase: 06-generated-theme-library
plan: 01
subsystem: theme
tags: [jsonl, code-generation, hsbk, uint16, multiset-equality, atomic-write]

# Dependency graph
requires:
  - phase: 05 (theme capture tooling)
    provides: .claude/theme-capture/themes.jsonl raw capture and the D-09 slug() derivation in analyse_themes.py
provides:
  - data/themes.jsonl — committed normalised theme data file (4 seed records covering all three record shapes)
  - src/lifx/theme/generator.py — validating, atomically-writing theme data module generator (uv run python -m lifx.theme.generator)
  - src/lifx/theme/data.py — generated ThemeRecord dataclass + THEMES flat dict with alias keys bound to target records
  - Theme identity kwargs (slug/name/category, keyword-only, default None) on lifx.theme.theme.Theme
  - Theme.__eq__ palette-only unordered-multiset equality at uint16 precision; Theme unhashable
  - Transitional ThemeLibrary.get() — generated-first lookup with pre-v1.2 hand-written fallback, fresh-list mutation fix on both paths
  - tests/test_theme/test_theme_generator.py — 69 generator hardening tests over fixture data
  - Coverage omissions for generator + generated module in pyproject.toml and codecov.yml
affects: [06-02 full theme import and fallback removal, phase-9 capture/regeneration tooling]

# Actuals (#2632) — pairs with the plan's `estimate` to calibrate future estimates.
actuals:
  tokens: 15388
  tasks: 3
  commits: 4

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Generated data module from committed JSONL via validating generator (products/protocol generator precedent, minus the download step)"
    - "Atomic formatted write: mkstemp in target dir → ruff format → Path.replace, finally-unlink cleanup (D-05)"
    - "Canonical palette sort by uint16 (hue, saturation, brightness, kelvin) tuple, duplicates preserved (D-24)"
    - "One canonical-key predicate for primary slugs AND aliases (non-empty, ASCII, lowercase, isidentifier)"
    - "Palette-only multiset equality via Counter over uint16-hashable HSBK (D-19); __eq__ without __hash__ for deliberate unhashability (D-20)"

key-files:
  created:
    - data/themes.jsonl
    - src/lifx/theme/generator.py
    - src/lifx/theme/data.py
    - tests/test_theme/test_theme_generator.py
  modified:
    - src/lifx/theme/theme.py
    - src/lifx/theme/library.py
    - tests/test_theme/test_theme.py
    - pyproject.toml
    - codecov.yml

key-decisions:
  - "Generated module named src/lifx/theme/data.py (D-01, planner discretion now fixed)"
  - "Seed records derived mechanically from the committed capture — no palette value retyped by hand (phase prohibition)"
  - "Theme equality is Counter-based multiset at uint16 precision, identity ignored; unhashable via __eq__-without-__hash__ (D-19, D-20)"
  - "Coverage omission extended to theme generator + generated module in BOTH pyproject omit and codecov ignore, matching the products/protocol precedent (D-21, D-22)"

patterns-established:
  - "Trusted-but-validated data boundary: every JSONL field type-checked (type(v) is int rejects bools; type(v) is str for metadata) with controlled RuntimeError naming record and line — emit-time asserts are backstops, never the boundary"
  - "Generator tests run only against fixture data in tmp_path, never the committed data file (D-23)"

requirements-completed: [THEME-04, COMPAT-01, META-01, META-02, COMPAT-03]

coverage:
  - id: D1
    description: "End-to-end generated theme pipeline: JSONL seed → generator → data.py → ThemeLibrary.get() with app-accurate palette, display name and category; all 57 pre-v1.2 names keep resolving via fallback"
    requirement: THEME-04
    verification:
      - kind: integration
        ref: "tracer verify script (generator double-run shasum + ThemeLibrary assertions) — run in Task 1 and re-run at plan end"
        status: pass
      - kind: unit
        ref: "tests/test_theme/ (249 tests)"
        status: pass
      - kind: manual_procedural
        ref: "tracer feedback gate — approved by user"
        status: pass
    human_judgment: false
  - id: D2
    description: "Theme carries optional identity (slug/name/category) and palette-only multiset equality at uint16 precision; Theme is unhashable"
    requirement: META-01
    verification:
      - kind: unit
        ref: "tests/test_theme/test_theme.py#TestThemeEquality + TestThemeIdentity"
        status: pass
    human_judgment: false
  - id: D3
    description: "Generator validation aborts (schema, canonical keys, metadata, collisions, ranges), canonical palette order, alias expansion, uint16 round-trip, determinism and atomic write pinned by tests; coverage omissions configured"
    requirement: THEME-04
    verification:
      - kind: unit
        ref: "tests/test_theme/test_theme_generator.py (69 tests)"
        status: pass
      - kind: other
        ref: "grep -c checks: both paths exactly once in pyproject.toml omit and codecov.yml ignore"
        status: pass
    human_judgment: false

# Metrics
duration: 12min (continuation, Tasks 2-3; Task 1 by previous executor)
completed: 2026-08-14
status: complete
---

# Phase 6 Plan 01: Generated Theme Library Tracer Summary

**Four-record JSONL seed travels data file → validating generator → generated data.py → ThemeLibrary.get() with app-accurate palettes and identity, plus palette-only multiset Theme equality and 69 generator hardening tests**

## Performance

- **Duration:** ~12 min continuation (Tasks 2–3); Task 1 executed and gate-approved in the prior session
- **Started:** 2026-08-14T13:15:24Z (continuation)
- **Completed:** 2026-08-14T13:25:00Z
- **Tasks:** 3/3
- **Files modified:** 9

## Accomplishments

- **Tracer (Task 1, prior session):** `data/themes.jsonl` seed (cheerful, evening, forrest+forest alias, mondrian), `lifx.theme.generator` with canonical-key/schema/metadata validation and atomic mkstemp write, generated `data.py`, identity-carrying `Theme`, transitional generated-first `ThemeLibrary.get()` with the pre-v1.2 fallback intact and the shared-list mutation leak fixed on both paths. Gate approved by user.
- **Theme equality (Task 2, TDD):** `Theme.__eq__` compares palettes as unordered multisets via `Counter` over uint16-hashable HSBK — order and identity excluded; `Theme` is deliberately unhashable (`__hash__` is None). RED commit proved five failing behaviours before the GREEN implementation.
- **Generator hardening (Task 3):** 69 tests over tmp_path fixtures pin every validation abort (empty/non-identifier/Unicode slugs, invalid aliases, derivation mismatch, missing/extra fields, bool and string-numeric colour values, six name/category metadata cases, collisions naming both display names, zero colours, ranges with kelvin-0 accepted), canonical D-24 ordering with duplicates, alias record-sharing, uint16 round-trip at boundaries, deterministic emission, and the unique-temp atomic write surviving an interrupted run. Coverage omissions added to both pyproject.toml and codecov.yml.

## Task Commits

Each task was committed atomically:

1. **Task 1: One theme end to end (tracer)** - `3ab50ee` (feat) — prior session, gate approved
2. **Task 2: Theme equality (TDD RED)** - `586e769` (test)
3. **Task 2: Theme equality (TDD GREEN)** - `a0e0209` (feat)
4. **Task 3: Generator hardening tests + coverage config** - `bda5da2` (test)

## Files Created/Modified

- `data/themes.jsonl` - Committed normalised theme data (4 seed records, pure ASCII, canonically sorted palettes)
- `src/lifx/theme/generator.py` - Theme data module generator: load/validate/emit/format/atomic-write
- `src/lifx/theme/data.py` - Generated: ThemeRecord dataclass + THEMES dict with alias bindings
- `src/lifx/theme/theme.py` - Identity kwargs (Task 1) + palette-only multiset `__eq__`, unhashable (Task 2)
- `src/lifx/theme/library.py` - Transitional generated-first `get()` with fallback, fresh-list fix
- `tests/test_theme/test_theme.py` - TestThemeIdentity + TestThemeEquality classes (14 new tests)
- `tests/test_theme/test_theme_generator.py` - 69 generator hardening tests over fixtures
- `pyproject.toml` - Coverage omit: theme generator + generated module; stray blank line removed
- `codecov.yml` - Ignore: theme generator + generated module (matches existing precedent)

## Decisions Made

None beyond the plan — all locked decisions (D-01 through D-24) implemented as specified.

## Deviations from Plan

None - plan executed exactly as written. Task 3 exposed no generator defects, so `src/lifx/theme/generator.py` needed no changes in that task.

## Issues Encountered

None. One test-authoring iteration during Task 3 (regex fragment for the non-ASCII metadata message adjusted to match the generator's actual wording) — normal test development, not a defect.

## Verification Evidence (plan-level)

- Generator run twice → byte-identical `data.py` (shasum equal); committed `data.py` unchanged after regeneration
- All 57 pre-v1.2 theme names resolve (fallback intact, COMPAT-01 intermediate guarantee holds at every commit)
- `Theme.__hash__` prints `None`; `theme.py` contains `def __eq__` and no `def __hash__`
- `uv run pytest tests/test_theme/ -q` → 249 passed; `uv run pytest tests/ -q -x --ignore=tests/test_effects` → 1929 passed
- `uv run ruff check .` clean; `uv run pyright` 0 errors at every task boundary
- pyproject omit and codecov ignore each list both theme paths exactly once (grep -c = 1)

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Pipeline proven end to end; Plan 06-02 expands the record count to the full 166-record import, removes the hand-written fallback, switches `get_available_themes()` to the generated dict (D-15) and lands the shortened KeyError message
- Known deferred gap (documented in the Theme docstring): `shuffled()`/`random()` return identity-less copies — D-18 round-trip limitation, visible not silent

## Self-Check: PASSED

All created files verified on disk; all four task commits (3ab50ee, 586e769, a0e0209, bda5da2) verified in git history.

---
*Phase: 06-generated-theme-library*
*Completed: 2026-08-14*
