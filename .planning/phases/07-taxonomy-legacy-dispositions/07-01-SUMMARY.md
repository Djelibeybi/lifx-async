---
phase: 07-taxonomy-legacy-dispositions
plan: 01
subsystem: theme
tags: [themes, jsonl, code-generation, compat, disposition]

# Dependency graph
requires:
  - phase: 06-generated-theme-library
    provides: data/themes.jsonl schema, generate_theme_data.py validation/emit pipeline, ThemeRecord/THEMES, Theme identity fields (D-16/D-17), alias binding (D-13/D-14)
provides:
  - disposition field on all 166 data/themes.jsonl records (138 lifx-app / 19 library-only / 9 deprecated per locked SPEC R4 table)
  - replaced_by field on the 9 deprecated records, each resolving in THEMES
  - generator _DISPOSITIONS constant, disposition in _REQUIRED_FIELDS, replaced_by in _OPTIONAL_FIELDS, three D-08 validations, emit-time backstops
  - ThemeRecord.disposition (str) and ThemeRecord.replaced_by (str | None = None) in regenerated data.py
  - Theme.disposition / Theme.replaced_by keyword-only optionals; ThemeLibrary.get() threads both
  - D-08 failing-record tests, F1 branch matrix, TestDispositionSurfacing shape sweeps
affects: [07-02 taxonomy rewrite, 07-03 docs, phase-9 resync tooling]

# Actuals (#2632) — pairs with the plan's `estimate` to calibrate future estimates.
actuals:
  tokens: 74000
  tasks: 3
  commits: 4

# Tech tracking
tech-stack:
  added: []
  patterns: [required-field-with-closed-value-set in JSONL schema, cross-record validation pass after seen_keys is complete, library-side shape sweep as sole enforcement of a data invariant (R2-05)]

key-files:
  created: []
  modified:
    - data/themes.jsonl
    - scripts/generate_theme_data.py
    - src/lifx/theme/data.py
    - src/lifx/theme/theme.py
    - src/lifx/theme/library.py
    - tests/test_theme/test_theme_generator.py
    - tests/test_theme/test_theme.py
    - tests/test_theme/test_library.py

key-decisions:
  - "R2-05 deferral held: the generator does NOT reject replaced_by on a non-deprecated record; enforcement is the library-side shape sweep alone (test time / CI)"
  - "Emit-time asymmetry accepted (F3): the emit backstop checks replaced_by is canonical but not that it resolves — resolution needs whole-set knowledge the per-record backstops deliberately do not rebuild"
  - "Disposition type-and-membership check is a single compound condition; both branch sides are coverage-tested (123 and 'retired')"

patterns-established:
  - "Cross-record validation pass: iterate records a second time after the main loop so seen_keys holds every slug AND alias before resolution checks"
  - "Shape sweep, never count pin: TestDispositionSurfacing asserts invariants over THEMES without pinning 9/19/138 (D-08/D-23)"

requirements-completed: [COMPAT-04]

# Coverage metadata (#1602)
coverage:
  - id: D1
    description: "All 166 JSONL records carry disposition; 9 deprecated records carry replaced_by per the locked SPEC R4 table"
    requirement: COMPAT-04
    verification:
      - kind: other
        ref: "uv run python -c \"...Counter(r['disposition'])...\" (Task 1 acceptance: prints 'jsonl ok')"
        status: pass
      - kind: unit
        ref: "tests/test_theme/test_library.py#TestDispositionSurfacing"
        status: pass
    human_judgment: false
  - id: D2
    description: "Generator validates disposition set membership, deprecated-requires-replaced_by (canonical key), and cross-record resolution; aborts via controlled _fail()"
    requirement: COMPAT-04
    verification:
      - kind: unit
        ref: "tests/test_theme/test_theme_generator.py#TestValidateRecordsDispositions"
        status: pass
    human_judgment: false
  - id: D3
    description: "Theme.disposition / Theme.replaced_by readable on get() results; additive defaults; palette_equals/hash/== unchanged"
    requirement: COMPAT-04
    verification:
      - kind: unit
        ref: "tests/test_theme/test_theme.py#TestThemeDisposition"
        status: pass
      - kind: unit
        ref: "tests/test_theme/test_library.py#TestDispositionSurfacing"
        status: pass
    human_judgment: false
  - id: D4
    description: "Regeneration byte-idempotent after the schema change (THEME-04); 168 keys resolve; alias identity intact (R7)"
    requirement: COMPAT-04
    verification:
      - kind: other
        ref: "T=$(mktemp) && uv run scripts/generate_theme_data.py && cat src/lifx/theme/data.py > \"$T\" && uv run scripts/generate_theme_data.py && cmp \"$T\" src/lifx/theme/data.py"
        status: pass
      - kind: unit
        ref: "tests/test_theme/test_library.py#TestPreV12Compatibility + TestRenamePairs"
        status: pass
    human_judgment: false

# Metrics
duration: 10min
completed: 2026-08-15
status: complete
---

!!! warning "Partly superseded by the post-ship amendment (2026-08-15, `582f74b`)"

    This is the execution record as delivered and is not rewritten. A `max`-effort code
    review of PR #202 changed behaviour afterwards: the legacy-category shim was **deleted**
    (all six pre-6.4.0 names now raise the generic unrecognised-category error), and each
    rename alias became its own `disposition="renamed"` record instead of binding its
    target's. See the Post-Ship Amendment section of `07-SPEC.md` and the addendum in
    `07-VERIFICATION.md`.

# Phase 7 Plan 01: Disposition Schema Summary

**COMPAT-04 disposition schema wired end-to-end: all 166 JSONL records carry a machine-readable fate (138 lifx-app / 19 library-only / 9 deprecated with replaced_by), validated by three D-08 generator aborts and surfaced on the public Theme via get()**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-08-15T02:58:00Z
- **Completed:** 2026-08-15T03:08:00Z
- **Tasks:** 3
- **Files modified:** 8

## Accomplishments

- Every one of the 166 `data/themes.jsonl` records now states its fate: `disposition` is a required field with the locked 138/19/9 split, and the 9 deprecated records carry `replaced_by` values that each resolve in `THEMES` (aliases counting as targets)
- Generator gained `_DISPOSITIONS`, three controlled validations (allowed set; deprecated requires a non-empty canonical `replaced_by`; cross-record resolution after `seen_keys` is complete) and emit-time backstops for both fields; `data.py` regenerated byte-idempotently
- `Theme` gained keyword-only `disposition`/`replaced_by` defaulting to `None` (D-07 additive), threaded through `ThemeLibrary.get()`; `palette_equals()`, identity `==` and hashability unchanged (R5, D-19a/D-20a)
- Full branch coverage held: generator, theme.py and library.py at 0 missing lines / 0 partial branches under the theme suite; full project suite green (3377 passed), pyright and ruff clean

## Task Commits

Each task was committed atomically:

1. **Task 1: Tracer — disposition wired JSONL → generator → THEMES** - `c430532` (feat)
2. **Task 2: Surface disposition on the public Theme via get()** - `748b6cd` (test, RED) + `185ec7a` (feat, GREEN)
3. **Task 3: D-08 validation tests plus surfacing and shape sweeps** - `aee48a3` (test)

## Files Created/Modified

- `data/themes.jsonl` - all 166 lines rewritten with `disposition` (9 also with `replaced_by`)
- `scripts/generate_theme_data.py` - schema constants, three validations, extended emit + backstops
- `src/lifx/theme/data.py` - regenerated; `ThemeRecord` gains `disposition: str` and `replaced_by: str | None = None`
- `src/lifx/theme/theme.py` - keyword-only `disposition`/`replaced_by`; docstrings updated including the F7 copy-semantics note
- `src/lifx/theme/library.py` - `get()` threads both new fields
- `tests/test_theme/test_theme_generator.py` - `_record()` gains disposition; `TestValidateRecordsDispositions`; two new emit-backstop matrix rows; emit round-trip test
- `tests/test_theme/test_theme.py` - `TestThemeDisposition` (4 behaviour tests, written RED-first)
- `tests/test_theme/test_library.py` - `TestDispositionSurfacing` (R5 triples, shape sweeps, alias identity)

## JSONL Rewrite Script Logic (review F14 — reproducibility record)

The one-off rewrite ran from a throwaway scratchpad script (not committed). Its full logic, so the rewrite stays reproducible (the locked SPEC R4 table in `07-SPEC.md` remains the authoritative fallback):

- **Read** `data/themes.jsonl` line by line, `json.loads` each non-blank line
- **Disposition rule:** `category != "Library"` → `"lifx-app"` (138 records). The 28 `category == "Library"` records use the locked SPEC R4 table verbatim — deprecated (9, each with `replaced_by`): focusing→gentle, intense→fantasy, shamrock→st_patrick_s_day, love→romance, holly→christmas, fire→warm_ember, proud→pride, pumpkin→pumpkin_spice, santa→candy_cane; library-only (19, no `replaced_by`): arctic, autumn, bias_lighting, cherry_blossom, cyberpunk, deep_sea, desert, epic, evening, galaxy, hygge, neon, relaxing, serene, spring, sports, tropical, vaporwave, water. No palette or semantic judgement was exercised — values copied from the locked table
- **Key insertion order:** `slug`, `name`, `category`, `disposition`, `replaced_by` (only when present), `aliases` (only when present), `colors`
- **Serialisation:** `json.dumps(obj, separators=(", ", ": "), ensure_ascii=False)` + trailing newline (`ensure_ascii=False` per review F9 — a surviving non-ASCII character must not drift into a `\uXXXX` escape)
- **Safety checks:** per line, re-serialising the rebuilt object *minus* the two new keys had to reproduce the original line byte-for-byte (proving separators/ordering exact); final split had to equal `{lifx-app: 138, library-only: 19, deprecated: 9}`. Both held on the live file

## Decisions Made

- **R2-05 deferral held (user decision, recorded per Task 1):** the generator does NOT enforce SPEC R5's invariant that `replaced_by` is `None` unless `disposition == "deprecated"`. A non-deprecated record carrying a canonical `replaced_by` passes all three validations and is emitted. Enforcement rests entirely on `TestDispositionSurfacing::test_replaced_by_only_on_deprecated_records`, which runs at test time (and in CI before any ship). Residual risk accepted: a bad data edit is caught by the suite, not at generation. Reversible: a one-line generator addition plus one failing-record test closes the gap later with no data or API change
- **Emit-time asymmetry accepted (review F3, recorded per Task 1):** the emit-time backstop checks `replaced_by` is `None`-or-canonical but NOT that it resolves. Resolution needs whole-set knowledge (`seen_keys`) that the per-record emit backstops deliberately do not rebuild; `emit_data_module()` without `validate_records()` is a test-harness path, not a production path
- Disposition type-and-membership implemented as one compound condition (`type(...) is not str or ... not in _DISPOSITIONS`) with both branch sides coverage-tested, matching the existing house validation style

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None. The pre-existing `.planning/STATE.md` working-tree modification (the orchestrator's D-21 record correction, flagged in the plan) was left unstaged per the plan's "do NOT edit STATE.md" instruction.

## Known Stubs

None — no placeholder values, no unwired data paths. All disposition data is real and flows JSONL → generator → data.py → Theme.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 07-02 (taxonomy rewrite) can proceed: `ThemeRecord.disposition`/`replaced_by` are available; `get()` construction site is where 07-02's changes land; alias emission order undisturbed
- The AST no-network assertion's `>= 7` file-count guard passes now and is designed to keep passing when 07-02 adds `slug.py` as an eighth theme-layer file

---
*Phase: 07-taxonomy-legacy-dispositions*
*Completed: 2026-08-15*

## Self-Check: PASSED

All 8 modified files exist; all 4 task commits (c430532, 748b6cd, 185ec7a, aee48a3) present in git log.
