---
phase: 07-taxonomy-legacy-dispositions
plan: 03
subsystem: docs
tags: [themes, taxonomy, migration, documentation]

# Dependency graph
requires:
  - phase: 07-taxonomy-legacy-dispositions
    plan: 01
    provides: Theme.disposition/replaced_by surfaced via get() — the After example's fate read
  - phase: 07-taxonomy-legacy-dispositions
    plan: 02
    provides: get_categories(), rewritten get_by_category() with legacy fates — the behaviour the page documents
provides:
  - docs/migration/theme-taxonomy-v1.2.md — dated point-in-time migration record (9 categories with counts, 6 legacy fates, 9 deprecated keys with replacements)
  - mkdocs.yml — page listed in BOTH Migration nav sections (llms nav and main nav)
  - docs/api/themes.md — stale 'older grouping' admonition replaced with current behaviour + migration link
  - docs/getting-started/themes.md — examples re-pointed at Holidays/Moods with a get_categories() discovery line
affects: [phase-9 DOCS-03]

# Actuals (#2632) — pairs with the plan's `estimate` to calibrate future estimates.
actuals:
  tokens: 3500
  tasks: 2
  commits: 3

# Tech tracking
tech-stack:
  added: []
  patterns: [dated point-in-time migration record instead of live reference (D-10 contract), doc claims verified by executing every After statement class against the shipped library]

key-files:
  created:
    - docs/migration/theme-taxonomy-v1.2.md
  modified:
    - mkdocs.yml
    - docs/api/themes.md
    - docs/getting-started/themes.md

key-decisions:
  - "Category table carries a third 'Defined by' column (LIFX app / This library) so the Library attribution is explicit in the table itself, not only in prose — the name and count cells stay adjacent, so the R2-03 per-row regex still matches"
  - "The point-in-time stamp is an admonition titled 'As of the v1.2 migration (2026-08-15)' — prominent, dated, and states the page is deliberately never resynced (D-10)"

patterns-established:
  - "Migration pages follow the effect-api-changes.md shape: H1 with version, intro sentence, Overview numbered list, sections with Before/After fenced blocks"

requirements-completed: [META-04, COMPAT-04]

# Coverage metadata (#1602)
coverage:
  - id: DOC1
    description: "Migration page names all 9 categories with exact counts as adjacent cells, all 6 legacy fates and all 9 deprecated→replacement pairs, each pair on one table row"
    requirement: META-04
    verification:
      - kind: other
        ref: "Task 1 verify script — per-row regex over all 9 category/count pairs (fixture-validated in both directions), row-level pair checks for all 15 fate rows; printed 'page ok'"
        status: pass
    human_judgment: false
  - id: DOC2
    description: "Every After-block statement class executes against the shipped library: get_categories(), get_by_category('Holidays') non-empty, get('fire').disposition == 'deprecated' / .replaced_by == 'warm_ember'"
    requirement: COMPAT-04
    verification:
      - kind: other
        ref: "Task 1 verify script behavioural assertions (mirror contract per review R2-03)"
        status: pass
    human_judgment: false
  - id: DOC3
    description: "Page reachable from both mkdocs nav trees; docs build clean"
    requirement: META-04
    verification:
      - kind: other
        ref: "grep -c theme-taxonomy-v1.2.md mkdocs.yml == 2; uv run zensical build exits 0"
        status: pass
    human_judgment: false
  - id: DOC4
    description: "No shipped doc teaches a category name that raises; no phantom 'time' category list anywhere in docs/ or src/lifx/"
    requirement: META-04
    verification:
      - kind: other
        ref: "Task 2 verify doc-wide get_by_category() scan (every argument outside the migration page resolves); grep for 'seasonal, mood, holiday, time' returns nothing"
        status: pass
    human_judgment: false
  - id: DOC5
    description: "Library category attributed to this library, never the LIFX app"
    requirement: META-04
    verification:
      - kind: other
        ref: "Page table 'Defined by' column + prose 'Library is defined by this library, not the app'"
        status: pass
    human_judgment: true

# Metrics
duration: 8min
completed: 2026-08-15
status: complete
---

# Phase 7 Plan 03: Taxonomy & Migration Docs Summary

**The v1.2 theme-taxonomy migration documented as a dated point-in-time record: a new page under both Migration nav sections carrying the 9 categories with counts, the 6 legacy-name fates and the 9 deprecated→replacement pairs — every After example executed against the shipped library — plus the last two stale doc sites corrected (D-11 sites 3-4)**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-08-15T03:20:58Z
- **Completed:** 2026-08-15T03:28:00Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- `docs/migration/theme-taxonomy-v1.2.md` created following the `effect-api-changes.md` shape, stamped **"As of the v1.2 migration (2026-08-15)"** as a deliberately-never-resynced record (D-10): the 9-category table with counts verified against the shipped data (Archives 60, Art Series 10, Holidays 15, Library 28, Moods 13, Music 14, Nature 8, Play 7, Space 11), one row per legacy name (holiday→Holidays, mood→Moods; seasonal/ambient/functional/atmosphere raise naming Nature/Play/Library/Moods), and one row per deprecated key with its exact replacement
- The Library attribution is explicit twice — a "Defined by" table column and prose — so the synthetic category is never presented as app-defined; the 3 dropped sport categories are noted as out of scope
- The deprecation contract uses the SPEC's locked wording (review F6): a deprecated key still resolves, deprecation records a fate and never deletes, removal would be a **v2.0 decision** — no duration-bound 1.x support promise
- The Before block is labelled historical and the prose states `get_by_category("holiday")`/`("mood")` still resolve — the result set changed, not the call's validity (review F8); every After statement class was executed against the shipped code in the verify step (review R2-03)
- Both mkdocs nav trees list the page (llms nav bare path + main nav "Theme Taxonomy Changes")
- `docs/api/themes.md`: the now-false "older grouping" admonition replaced with the current `get_by_category()`/`get_categories()` behaviour, the holiday/mood mapping, the raising legacy names, and a migration-page link plus one `Theme.disposition`/`Theme.replaced_by` sentence (D-11 site 3; no full attribute reference — Phase 9 owns DOCS-03)
- `docs/getting-started/themes.md`: examples re-pointed at `get_by_category("Holidays")`/`("Moods")` with a `get_categories()` discovery line above them (D-11 site 4)
- Doc-wide scan proves every `get_by_category()` example outside the migration page resolves without `ValueError` (review F11); `grep -rn "seasonal, mood, holiday, time" docs/ src/lifx/` returns nothing
- Full suite green (3390 passed), zensical build clean, ruff format/check clean, pyright 0 errors; `docs/changelog.md` untouched

## Task Commits

Each task was committed atomically:

1. **Task 1: The theme-taxonomy migration page and its nav entries** - `bc61ee3` (docs)
2. **Task 2: Correct the two stale doc sites outside library.py** - `b299464` (docs)

## Files Created/Modified

- `docs/migration/theme-taxonomy-v1.2.md` - new dated migration page: stamp admonition, Overview, three tables, Before/After examples
- `mkdocs.yml` - `migration/theme-taxonomy-v1.2.md` added to the llms nav Migration list and `Theme Taxonomy Changes: migration/theme-taxonomy-v1.2.md` to the main nav Migration section
- `docs/api/themes.md` - admonition deleted; replacement paragraph with migration link and disposition sentence
- `docs/getting-started/themes.md` - category examples re-pointed at app names; `get_categories()` line added

## Verification Evidence (every documented claim executed)

All page claims were verified against the delivered library before writing:

- `get_categories()` returned exactly the 9 documented names; per-category counts over the 166 primary records matched the table exactly
- All 6 legacy fates observed live: holiday→15 themes, mood→13; the other 4 raised `ValueError` with messages naming Nature/Play/Library/Moods
- All 9 deprecated pairs read from `get()`: each `.disposition == "deprecated"` with the exact documented `.replaced_by`; disposition split confirmed 138/19/9
- Normalisation confirmed: `Art Series`/`art series`/`art_series` agree (10 themes); `artseries` raises; `HOLIDAY` behaves as `holiday`
- The R2-03 pairing regex was validated against a fixture table in both directions: correct counts pass, a swapped Nature/Play count fails naming Nature

## Decisions Made

- **Category table gains a "Defined by" column** (LIFX app / This library) so the Library-attribution prohibition is satisfied inside the count table itself, not only in prose; the name and count cells remain adjacent so the verify regex is unaffected
- **The D-10 stamp is an admonition** titled with the operator's "As of" framing and the migration date, stating the page is deliberately not updated as the library changes

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## Known Stubs

None — a documentation-only plan; no placeholder values or unwired data paths.

## Threat Flags

None — no new security-relevant surface. T-07-07 mitigated (all counts/fates copied from the locked SPEC tables, page dated, After examples executed); T-07-08 mitigated (Library attributed to this library in table and prose); T-07-09 accepted as planned (zero packages installed).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 7 is complete: all three plans (schema, taxonomy rewrite, docs) delivered; SPEC R6 closed
- Phase 8 (palette fidelity) and Phase 9 (DOCS-03 broader theme docs, resync tooling, issue #201) can proceed; the migration page is a stable dated record they must not resync
- Issue #200 remains OPEN for closure at ship (D-13)

---
*Phase: 07-taxonomy-legacy-dispositions*
*Completed: 2026-08-15*

## Self-Check: PASSED

All 4 doc files plus this SUMMARY exist; both task commits (bc61ee3, b299464) present in git log.
