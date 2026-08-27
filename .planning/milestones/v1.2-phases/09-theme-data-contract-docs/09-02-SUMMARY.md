---
phase: 09-theme-data-contract-docs
plan: 02
subsystem: documentation
tags: [theme-library, documentation, mkdocs, publication-contract]
reconstructed: true
reconstructed_from: 874f073
reconstructed_at: 2026-08-27
requires:
  - phase: 09-01
    provides: The resynced catalogue whose categories, counts and palette lengths the page documents
provides:
  - A live public catalogue page owning categories, counts and the compatibility boundary
  - A publication contract test binding that page to the shipped library
  - One home for the inventory, with the API reference and quick start pointing at it
affects: [DOCS-03, milestone-v1.2-close]
actuals:
  tokens: 0
  tasks: 3
  commits: 1
tech-stack:
  added: []
  patterns:
    - A documentation page that states counts is bound to the data by a test, so it fails the suite rather than rotting.
    - Prose contracts compare against whitespace-normalised text, so reflowing a paragraph is not a test failure.
    - Documented totals are derived from the records in the test, never restated as literals on both sides.
key-files:
  created:
    - docs/getting-started/built-in-themes.md
    - tests/test_theme/test_docs_catalogue.py
  modified:
    - docs/api/themes.md
    - docs/getting-started/themes.md
    - mkdocs.yml
    - CLAUDE.md
key-decisions:
  - "The catalogue page is the single owner of category membership, counts and the compatibility boundary; the API reference and the quick start link to it rather than carrying copies."
  - "The source page's fidelity section was rewritten rather than ported: the Phase 8 device-readback boundary it described was superseded by 09-01's API resync."
  - "The runbook link was dropped; that document now lives in the private lifx-theme-resync repository."
  - "The publication contract test was written here rather than assumed: the test the page claimed belonged to the tooling and left with it."
  - "The contract test was mutation-checked — perturbing a documented count fails two tests — rather than merely observed to pass as authored."
requirements-completed: [DOCS-03]
coverage:
  - id: D1
    description: One page lists the available themes and categories, with counts bound to the live library.
    requirement: DOCS-03
    verification:
      - kind: unit
        ref: tests/test_theme/test_docs_catalogue.py#test_table_matches_live_categories
        status: pass
      - kind: unit
        ref: tests/test_theme/test_docs_catalogue.py#test_table_matches_live_counts
        status: pass
    human_judgment: false
  - id: D2
    description: The page states that the pre-v1.2 palettes of redefined themes were not carried forward.
    requirement: DOCS-03
    verification:
      - kind: unit
        ref: tests/test_theme/test_docs_catalogue.py#test_retirement_statement_present
        status: pass
    human_judgment: false
  - id: D3
    description: The documented totals and palette-length figures are derived from the records, not restated.
    requirement: DOCS-03
    verification:
      - kind: unit
        ref: tests/test_theme/test_docs_catalogue.py#test_documented_totals_hold
        status: pass
      - kind: unit
        ref: tests/test_theme/test_docs_catalogue.py#test_long_palette_claims_hold
        status: pass
    human_judgment: false
duration: unrecorded
completed: 2026-08-27
status: complete
---

# Phase 09 Plan 02: Built-in Theme Catalogue Documentation Summary

**The shipped library gained a live catalogue page listing its nine categories with counts and recording that the redefined pre-6.4.0 palettes were not carried forward, bound to the library by a test that fails when the two disagree.**

> **Reconstructed record.** Written 2026-08-27 alongside commit `874f073` rather
> than before it. Token actuals were not tracked and are reported as zero rather
> than estimated.

## Performance

- **Duration:** unrecorded
- **Completed:** 2026-08-27
- **Tasks:** 3/3
- **Files modified:** 6

## Accomplishments

- Added `docs/getting-started/built-in-themes.md`: the nine categories with counts, three executable enumeration examples, and the compatibility and fidelity boundary. Nav entries added to both the site nav and the llmstxt section list.
- Corrected the fidelity section for what actually shipped. Palettes are no longer truncated to the 16 slots a firmware effect packet carries; 25 themes exceed 16 colours, `independence` longest at 68. That length is available to `apply_theme()`, which renders the whole palette, but not to `MatrixEffect`, which rejects a palette above `MAX_PALETTE_COLORS` — verified by execution, not assumed.
- Added `tests/test_theme/test_docs_catalogue.py` (6 tests), deriving every prose total from `THEMES` and measuring the palette-length figures rather than restating them.
- Corrected the resolvable-key count from 168 to 169 in the API reference, the themes quick start and `CLAUDE.md` — the resync added a third rename alias when LIFX renamed Energizing to Energising.
- Removed the duplicate inventories from `docs/api/themes.md` and `docs/getting-started/themes.md`; both now point at the catalogue.
- Corrected `mkdocs.yml`, which described the library as supporting "TileDevice" — not a class here — and omitted `MatrixLight` and `CeilingLight`.

## Task Commits

1. **Tasks 1–3** — `874f073` (docs). The work shipped as one commit.

## Files Created/Modified

- `docs/getting-started/built-in-themes.md` — the live public catalogue.
- `tests/test_theme/test_docs_catalogue.py` — the publication contract.
- `docs/api/themes.md`, `docs/getting-started/themes.md` — duplicate inventories replaced by pointers; counts corrected.
- `mkdocs.yml` — nav and llmstxt entries; device-type line corrected.
- `CLAUDE.md` — resolvable-key count corrected.

## Decisions Made

See `key-decisions` in the frontmatter.

## Verification

- Full suite: 3469 passed.
- `ruff format --check` and `ruff check`: clean. `pyright`: 0 errors.
- `zensical build`: "No issues found".
- Mutation check: perturbing the `Holidays` count from 15 to 14 failed `test_table_matches_live_counts` and `test_documented_totals_hold`; restored and re-verified green.
- No `theme-resync`, `theme_resync` or `theme-capture` reference survives in `docs/`, `src/` or `mkdocs.yml`.

## Deviations from Plan

Not applicable — the plan is reconstructed from the commit. Recorded as a
process deviation in `09-VERIFICATION.md`.

## Issues Encountered

Two stale untracked directories left by the theme-resync split, `tests/test_theme_resync/`
and `tests/test_tools/`, held nothing but `__pycache__` and so were invisible to
`git status`. Both were removed.

## User Setup Required

None.
