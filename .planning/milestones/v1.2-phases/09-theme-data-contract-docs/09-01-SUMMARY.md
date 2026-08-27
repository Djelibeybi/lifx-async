---
phase: 09-theme-data-contract-docs
plan: 01
subsystem: theme-data
tags: [theme-library, schema, slug, HSBK, generator, api-resync]
reconstructed: true
reconstructed_from: 291e7e6f0331f59e3fa1250f1e52896c2a13abf9
reconstructed_at: 2026-08-27
requires: []
provides:
  - An importable, independently tested record contract at lifx.theme.schema
  - Float-stored palettes converted to wire values at runtime
  - Untruncated palettes, up to 68 colours
  - A single slug rule shared by the library and the generator
affects: [09-02, TOOL-04, DOCS-03]
actuals:
  tokens: 0
  tasks: 3
  commits: 1
tech-stack:
  added: []
  patterns:
    - The record contract ships in the wheel but stays out of __all__ and the published docs (the Canvas precedent).
    - Colours are stored in the user-facing float form and converted at the wire boundary, never pre-rounded.
    - The slug rule lives in a leaf module so both the library and the generator apply it identically.
key-files:
  created:
    - src/lifx/theme/schema.py
    - tests/test_theme/test_schema.py
  modified:
    - src/lifx/theme/slug.py
    - src/lifx/theme/data.py
    - data/themes.jsonl
    - scripts/generate_theme_data.py
    - tests/test_theme/test_slug.py
    - tests/test_theme/test_theme_generator.py
key-decisions:
  - "The contract lives in the library as lifx.theme.schema, importable but absent from __all__ and the published API docs, so its signatures can change without a major version."
  - "Palettes are stored as user-facing HSBK floats; nothing replicates the app's lossy Java Float arithmetic any more."
  - "A palette longer than the 16 MORPH wire slots is accepted rather than truncated; the ceiling is a wire-packet limit, not a data limit."
  - "The catalogue is resynced from the LIFX Cloud API, not a device readback, so the readback ceiling stops bounding the shipped data."
  - "Apostrophes are dropped by the slug rule rather than collapsed to an underscore, so Spider's Lair ships intact as spiders_lair (closes #197)."
  - "TOOL-01, TOOL-02 and TOOL-03 are withdrawn from v1.2 in favour of TOOL-04; the capture and analysis tooling is maintained outside this repository."
requirements-completed: [TOOL-04]
coverage:
  - id: D1
    description: The record contract is importable as lifx.theme.schema and independently tested.
    requirement: TOOL-04
    verification:
      - kind: unit
        ref: tests/test_theme/test_schema.py
        status: pass
    human_judgment: false
  - id: D2
    description: Palettes are stored as floats, converted at runtime, and are not truncated to 16 colours.
    requirement: TOOL-04
    verification:
      - kind: unit
        ref: tests/test_theme/test_theme_generator.py
        status: pass
    human_judgment: false
  - id: D3
    description: Slug derivation is one rule with a single implementation, used by both the library and the generator.
    requirement: TOOL-04
    verification:
      - kind: unit
        ref: tests/test_theme/test_slug.py
        status: pass
    human_judgment: false
duration: unrecorded
completed: 2026-08-19
status: complete
---

# Phase 09 Plan 01: Theme Data Contract & Catalogue Resync Summary

**The theme record contract became an importable, independently tested library module, palettes became untruncated user-facing floats resynced from the LIFX Cloud API, and slug derivation collapsed to one rule with one implementation.**

> **Reconstructed record.** Written 2026-08-27 from commit `291e7e6` (2026-08-19),
> which was executed on the `split/library-changes` branch outside the GSD loop.
> Timings and token actuals were never recorded and are reported as unrecorded
> rather than estimated.

## Performance

- **Duration:** unrecorded
- **Completed:** 2026-08-19
- **Tasks:** 3/3
- **Files modified:** 16 (10 outside `.planning/`)

## Accomplishments

- Extracted `canonical_palette`, `load_theme_records`, `validate_key` and `validate_records` into `src/lifx/theme/schema.py`: importable, in the wheel, absent from `lifx.theme.__all__`, and independently tested by `tests/test_theme/test_schema.py`.
- Stored colours as user-facing HSBK floats converted at runtime by `HSBK.to_protocol()`. `_validate_colors` accepts a JSON number for hue, saturation and brightness, rejecting bool and non-finite values; kelvin stays a strict integer.
- Accepted palettes longer than 16 slots. 25 themes that a device readback had silently truncated regained their full palettes, up to 68 colours.
- Resynced the catalogue from the LIFX Cloud API: 166 records over the app's nine categories — 138 `lifx-app`, 19 `library-only`, 9 `deprecated` — plus 3 rename aliases, for 169 resolvable keys.
- Moved slug derivation into `src/lifx/theme/slug.py`, a leaf module whose only import is `re`, shared by `ThemeLibrary` and the generator via `schema.py`.

## Task Commits

1. **Tasks 1–3** — `291e7e6` (fix). The work shipped as one commit; the three tasks above are a reconstruction of its content, not three separate commits.

## Files Created/Modified

- `src/lifx/theme/schema.py` — the record contract, newly importable.
- `src/lifx/theme/slug.py` — the single slug rule.
- `data/themes.jsonl` — resynced from the API, colours stored as floats.
- `src/lifx/theme/data.py` — regenerated; byte-idempotent.
- `scripts/generate_theme_data.py` — now imports the contract rather than owning it.
- `tests/test_theme/test_schema.py` — the contract's independent tests.
- `tests/test_theme/test_slug.py`, `tests/test_theme/test_theme_generator.py` — updated for the new home and the float storage.

## Decisions Made

See `key-decisions` in the frontmatter. The scope reduction is the load-bearing
one: TOOL-01, TOOL-02 and TOOL-03 required the capture and analysis tooling to
ship in this repository, and it is now maintained in the separate private
`lifx-theme-resync` repository, so they were withdrawn from v1.2 in favour of
TOOL-04.

## Verification

Re-verified against the shipped tree on 2026-08-27 (see `09-VERIFICATION.md`):
`lifx.theme.schema` imports and exposes the four contract functions; a stored
colour is a float `HSBK` that converts to a `LightHsbk` at runtime; 25 palettes
exceed 16 colours with `independence` longest at 68; `derive_slug` has one
definition and two importers; regenerating `data.py` produces an identical file.

## Deviations from Plan

Not applicable — the plan is reconstructed from the commit, so there is no
prior plan to have deviated from. This is itself the phase's principal process
deviation and is recorded as such in `09-VERIFICATION.md`.

## Issues Encountered

Issues #198 and #199 were explicitly left open by this work: no changelog entry
yet names every key whose palette changed, and `validate_key()` still requires
`str.isidentifier()`, so a digit-leading display name remains unrepresentable.
No shipped theme hits the second today.

## User Setup Required

None.
