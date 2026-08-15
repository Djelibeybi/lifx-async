---
phase: 07-taxonomy-legacy-dispositions
plan: 02
subsystem: theme
tags: [themes, taxonomy, categories, compat, migration]

# Dependency graph
requires:
  - phase: 07-taxonomy-legacy-dispositions
    plan: 01
    provides: ThemeRecord.disposition/replaced_by, Theme disposition threading via get(), disposition data on all 166 records
  - phase: 06-generated-theme-library
    provides: THEMES/_THEMES indirection, D-09 slug rule, Title Case categories, alias binding
provides:
  - src/lifx/theme/slug.py — single shared derive_slug() implementation (D-04), leaf module
  - ThemeLibrary.get_categories() — public classmethod listing the 9 categories from the generated records
  - ThemeLibrary.get_by_category() rewritten over the app taxonomy with D-09 normalisation on both sides
  - _LEGACY_CATEGORIES private migration shim — holiday/mood resolve; seasonal/ambient/functional/atmosphere raise naming Nature/Play/Library/Moods
  - corrected library.py docstrings (D-11 sites 1-2) — no 'time' category, no raising example
affects: [07-03 docs, phase-9 resync tooling]

# Actuals (#2632) — pairs with the plan's `estimate` to calibrate future estimates.
actuals:
  tokens: 5100
  tasks: 2
  commits: 3

# Tech tracking
tech-stack:
  added: []
  patterns: [leaf shared-rule module inside the package imported by an out-of-wheel generator (geometry.py precedent), private tagged-tuple migration shim probed with normalised input, shared private helper for both lookup namespaces]

key-files:
  created:
    - src/lifx/theme/slug.py
  modified:
    - scripts/generate_theme_data.py
    - src/lifx/theme/library.py
    - tests/test_theme/test_theme_generator.py
    - tests/test_theme/test_library.py

key-decisions:
  - "Review F2 (recorded per Task 1): derive_slug placement stays src/lifx/theme/slug.py — the regeneration bootstrap cycle PREDATES this phase (src/lifx/__init__.py eagerly imports lifx.theme, so the generator's lifx.color import already loads data.py); recovery for a broken data.py is git; slug.py is pinned as a leaf module (only import: re)"
  - "Review F13 (declined, recorded): no precompute or cache for the per-call record scan — 168 bounded regex passes per occasional classmethod call is negligible; the shared _slugs_for_category() helper serves both paths instead"
  - "Review F16 (declined, recorded): no isinstance guard on get_by_category()/derive_slug() input — get_by_category(None) raises AttributeError from .lower(), not the documented ValueError; the signature is typed str and enforced by pyright at the caller boundary"

# Metrics
duration: 8min
completed: 2026-08-15
status: complete

# Coverage metadata (#1602)
coverage:
  - id: T1
    description: "get_categories() returns exactly the 9 codepoint-sorted category names derived from the record set; empty library returns []"
    requirement: META-03
    verification:
      - kind: unit
        ref: "tests/test_theme/test_library.py#TestGetCategories"
        status: pass
    human_judgment: false
  - id: T2
    description: "get_by_category(record.category) succeeds with record.slug among its keys for all 168 resolvable names; result slug-keyed and slug-sorted; D-09 normalised forms agree; unknown and empty-string inputs raise listing available categories"
    requirement: META-03
    verification:
      - kind: unit
        ref: "tests/test_theme/test_library.py#TestThemeLibraryGetByCategory"
        status: pass
      - kind: other
        ref: "Task 2 verify block python assertions (SPEC R1/R2/R3 acceptance verbatim) — printed 'taxonomy ok'"
        status: pass
    human_judgment: false
  - id: T3
    description: "All 6 pre-v1.2 names have their locked fates: holiday→Holidays (15), mood→Moods (13); seasonal/ambient/functional/atmosphere raise ValueError naming Nature/Play/Library/Moods; every replacement in _LEGACY_CATEGORIES names a listable category (review F4 drift guard)"
    requirement: META-04
    verification:
      - kind: unit
        ref: "tests/test_theme/test_library.py#TestLegacyCategoryNames"
        status: pass
    human_judgment: false
  - id: T4
    description: "Exactly one derive_slug implementation, inside the package, shared by generator and library (identity assertion); regeneration byte-idempotent after the move"
    requirement: META-03
    verification:
      - kind: unit
        ref: "tests/test_theme/test_theme_generator.py#TestDeriveSlug::test_generator_shares_the_package_rule"
        status: pass
      - kind: other
        ref: "uv run scripts/generate_theme_data.py && git diff --exit-code src/lifx/theme/data.py"
        status: pass
    human_judgment: false

requirements-completed: [META-03, META-04]
---

!!! warning "Partly superseded by the post-ship amendment (2026-08-15, `582f74b`)"

    This is the execution record as delivered and is not rewritten. A `max`-effort code
    review of PR #202 changed behaviour afterwards: the legacy-category shim was **deleted**
    (all six pre-6.4.0 names now raise the generic unrecognised-category error), and each
    rename alias became its own `disposition="renamed"` record instead of binding its
    target's. See the Post-Ship Amendment section of `07-SPEC.md` and the addendum in
    `07-VERIFICATION.md`.

# Phase 7 Plan 02: Taxonomy Rewrite Summary

**Category navigation rewritten over the app's 9-category taxonomy read from the generated records: get_categories() lists them, get_by_category() matches with D-09 slug normalisation on both sides, the 6 pre-v1.2 legacy names get their locked fates via the private _LEGACY_CATEGORIES shim, and generator + library share one derive_slug in the new lifx.theme.slug leaf module — closing the WR-02 defect**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-08-15T03:10:11Z
- **Completed:** 2026-08-15T03:18:00Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- `derive_slug()` relocated verbatim into `src/lifx/theme/slug.py` (D-04): a leaf module whose only import is `re`; the generator imports it from the package, the identity test pins `generator_module.derive_slug is lifx.theme.slug.derive_slug`, and regeneration left `data.py` byte-identical
- `get_categories()` returns exactly `["Archives", "Art Series", "Holidays", "Library", "Moods", "Music", "Nature", "Play", "Space"]`, derived from `cls._THEMES` (subclass-safe; an empty library returns `[]`)
- `get_by_category()` rewritten (TDD, RED→GREEN): app taxonomy first via the shared `_slugs_for_category()` helper, legacy map second; result keyed and sorted by slug; hardcoded 6-key dict deleted — `get_by_category(t.category)` now succeeds for every theme in the library (WR-02 closed; issue #200 stays OPEN per D-13, closed at ship)
- All 6 legacy fates locked in `_LEGACY_CATEGORIES` (D-01/D-02/D-03, private, unexported): `holiday`→Holidays (15 themes), `mood`→Moods (13); `seasonal`/`ambient`/`functional`/`atmosphere` raise `ValueError` naming Nature/Play/Library/Moods with the pinned pre-v1.2 message; empty string falls through to the generic unknown-category error ("not recognised", Australian English)
- Both stale docstring sites corrected (D-11 sites 1-2): no `time` category, class example now uses `get_categories()` + `get_by_category("Holidays")`; the Library category is attributed to this library, never the LIFX app
- Full suite green (3390 passed), pyright 0 errors, ruff clean; `library.py` and `slug.py` at 100% branch coverage under the theme suite

## Task Commits

Each task was committed atomically:

1. **Task 1: Relocate derive_slug into the package (D-04)** - `f438817` (refactor)
2. **Task 2: get_categories(), the get_by_category() rewrite and the legacy map** - `d86d808` (test, RED) + `ae42f54` (feat, GREEN)

## Files Created/Modified

- `src/lifx/theme/slug.py` - new leaf module housing the single D-09 slug rule; generalised docstring covering both stored names and caller-supplied category names
- `scripts/generate_theme_data.py` - local `derive_slug` deleted; imports it from `lifx.theme.slug`; now-unused `import re` removed
- `src/lifx/theme/library.py` - `_LEGACY_CATEGORIES` constant, `get_categories()`, `_slugs_for_category()`, rewritten `get_by_category()` with corrected docstrings
- `tests/test_theme/test_theme_generator.py` - shared-rule identity test in `TestDeriveSlug`; `import lifx.theme.slug` in the top import block
- `tests/test_theme/test_library.py` - `TestGetCategories`, `TestLegacyCategoryNames`, rewritten `TestThemeLibraryGetByCategory`; three stale tests deleted (review F5)

## Decisions Made

- **Review F2 (recorded per Task 1):** `derive_slug`'s home stays `src/lifx/theme/slug.py` — the most direct reading of locked D-04. The regeneration bootstrap cycle the reviewers flagged PREDATES this phase: `src/lifx/__init__.py` eagerly imports `lifx.theme`, so the generator's existing `from lifx.color import HSBK` already executes the full package init and loads the generated `data.py`. The relocation adds a second import path to an existing dependency; it does not introduce the cycle. Recovery for a broken committed `data.py` is git (`git checkout -- src/lifx/theme/data.py`; CI regenerates and diffs it on every `data/**` change). `slug.py` is pinned as a LEAF module — its only import is `re`, verified by the `grep -cE "^(from|import) lifx"` acceptance check — so a future recovery-oriented init refactor frees the slug rule automatically
- **Review F13 (declined, recorded):** no precompute of per-record category slugs at generation time and no caching of the scan — 168 bounded regex passes per occasional classmethod call is negligible; revisit only if a hot-loop caller appears. Both lookup paths share the one `_slugs_for_category()` helper instead
- **Review F16 (declined, recorded):** no runtime `isinstance` guard on `get_by_category()`/`derive_slug()` input — `get_by_category(None)` raises `AttributeError` from `.lower()`, not the documented `ValueError`. The signature is typed `str` and enforced by pyright at the caller boundary; runtime type enforcement is out of scope for this phase

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Removed the generator's now-unused `import re`**
- **Found during:** Task 1
- **Issue:** `derive_slug` was the generator's only `re` user; after the relocation the bare `import re` fails ruff (F401)
- **Fix:** deleted the import alongside the function move
- **Files modified:** scripts/generate_theme_data.py
- **Commit:** f438817

**2. [Rule 3 - Blocking] Split the legacy-resolve dict comprehension across a local variable**
- **Found during:** Task 2
- **Issue:** the plan's inline `sorted(cls._slugs_for_category(derive_slug(replacement)))` comprehension exceeded the 88-column E501 limit
- **Fix:** bound `replacement_slugs` first; behaviour identical
- **Files modified:** src/lifx/theme/library.py
- **Commit:** ae42f54

## TDD Gate Compliance

Task 2 (`tdd="true"`) followed RED→GREEN: `d86d808` (test — collection fails on the missing `_LEGACY_CATEGORIES`/`get_categories`) precedes `ae42f54` (feat — 118 library tests pass). No refactor commit was needed.

## Issues Encountered

None beyond the two auto-fixes above.

## Known Stubs

None — no placeholder values, no unwired data paths. Category navigation reads real generated records end-to-end.

## Threat Flags

None — no new network endpoints, auth paths, file access patterns or schema changes. T-07-06 (taxonomy source) mitigation holds: categories derive solely from the committed generated record set, and adding `slug.py` introduces no network capability (its only import is `re`).

**Corrected 2026-08-15 during `/gsd-secure-phase 7`:** this section previously claimed "the Phase 6 no-network AST assertion still passes with `slug.py` as the eighth theme-layer file". No such automated assertion exists — Phase 6's no-network finding was a review-time inspection recorded at `06-SECURITY.md:71`, not a test. The control itself is real and was verified directly during the Phase 7 security audit (every import across the theme layer is stdlib or intra-`lifx`); only the described mechanism was wrong. The layer also contains seven `.py` files, not eight.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 07-03 (docs) can proceed: `get_categories()` and the rewritten `get_by_category()` are the behaviours the migration page documents; the pinned error-message texts are stable for doc examples
- Issue #200 remains OPEN for closure at ship (D-13); issue #201 untouched (deferred to Phase 9 per D-12)

---
*Phase: 07-taxonomy-legacy-dispositions*
*Completed: 2026-08-15*

## Self-Check: PASSED

All 5 code files plus this SUMMARY exist; all 3 task commits (f438817, d86d808, ae42f54) present in git log.
