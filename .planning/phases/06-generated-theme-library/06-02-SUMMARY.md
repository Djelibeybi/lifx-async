---
phase: 06-generated-theme-library
plan: 02
subsystem: theme
tags: [jsonl, code-generation, hsbk, uint16, multiset-equality, compat, canonical-order]

# Dependency graph
requires:
  - phase: 06-01 (tracer)
    provides: generator pipeline (load/validate/emit/atomic-write), 4-record seed schema, Theme identity + multiset equality, transitional ThemeLibrary
  - phase: 05 (theme capture tooling)
    provides: .claude/theme-capture/themes.jsonl raw capture and the D-09 slug() derivation in analyse_themes.py
provides:
  - data/themes.jsonl — full committed data file: 166 records (138 app + 28 Library orphans), aliases on aurora and forrest, uint16-normalised, canonically sorted (D-24), pure ASCII, sorted by slug
  - src/lifx/theme/data.py — regenerated generated module carrying all 168 resolvable keys
  - src/lifx/theme/library.py — hand-written ThemeLibrary over the generated dict alone: fresh-list get() with identity, shortened KeyError, 168-name listing; hand-written _THEMES literal deleted
  - tests/test_theme/test_library.py — PRE_V12_KEYS literal 57-key COMPAT-01 fixture, rename-pair, soothing-kelvin, mutation-leak, KeyError-message, identifier/ASCII/category/canonical-order sweeps
  - tests/test_effects/test_rule_trio.py — literal uint16 pin of exciting's canonical leading trio (0, 7282, 10923), the committed D-24 regression gate
affects: [phase-7 taxonomy and orphan dispositions, phase-8 hardware fidelity, phase-9 resync tooling]

# Actuals (#2632) — pairs with the plan's `estimate` to calibrate future estimates.
actuals:
  tokens: 83735
  tasks: 3
  commits: 3

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Throwaway scratchpad conversion script deriving committed data mechanically from capture + legacy table, with embedded multiset verification (never committed; Phase 9 owns resync tooling)"
    - "Behavioural test assertions over runtime library data instead of count/palette pins (D-23); the single sanctioned literal palette pin binds D-24 to its positional consumer"

key-files:
  created: []
  modified:
    - data/themes.jsonl
    - src/lifx/theme/data.py
    - src/lifx/theme/library.py
    - tests/test_theme/test_library.py
    - tests/test_theme/test_theme.py
    - tests/test_effects/test_rule_trio.py
    - tests/test_api/test_api_apply_theme.py
    - .pre-commit-config.yaml

key-decisions:
  - "codespell ignore-words gained 'whats': the D-06 strip drops the curly apostrophe from 'What's the craic?', so the stored name 'Whats the craic?' is mechanical data, not a typo (Rule 3 blocking fix)"
  - "Theme equality example test moved from love/romance (no longer identical after the resync) to the app's genuinely identical memorial_day/independence/old_glory trio"
  - "exciting's 1-ulp uint16 drift vs pre-v1.2 shipped as captured — THEME-02 binds shipped == captured and the app is the source of truth; no value invented to match the old table"

patterns-established:
  - "Shared-slug delta classification is precision-dependent: analyse_themes.py classifies at 0.1 degree rounding; strict uint16 comparison can differ by 1 ulp where the app truncates and the old transcription rounded"

requirements-completed: [THEME-01, THEME-02, THEME-03, THEME-04, COMPAT-01, COMPAT-03, META-01, META-02]

coverage:
  - id: D1
    description: "Full data file: 166 records, 168 resolvable names, every app palette multiset-equal to its capture record and every orphan multiset-equal to _THEMES at uint16; canonical D-24 order; pure ASCII"
    requirement: THEME-01
    verification:
      - kind: integration
        ref: "conversion script embedded verification + plan Task 1 verify script (both passed, first run)"
        status: pass
    human_judgment: false
  - id: D2
    description: "ThemeLibrary serves all 168 names from the generated module alone; palettes multiset-exact end to end through the public API; soothing carries kelvin 8000; exciting leads uint16 hues 0/7282/10923"
    requirement: THEME-02
    verification:
      - kind: integration
        ref: "Task 2 cutover verify script (all 166 records resolved and compared through ThemeLibrary.get())"
        status: pass
      - kind: unit
        ref: "tests/test_theme/ (320 tests), tests/test_effects/test_rule_trio.py + test_spin.py (90 tests)"
        status: pass
    human_judgment: false
  - id: D3
    description: "All 57 pre-v1.2 keys resolve against a literal fixture; rename pairs resolve both ways with target identity; KeyError shortened; mutation leak fixed; META sweeps (ASCII, categories, identifiers, canonical order)"
    requirement: COMPAT-01
    verification:
      - kind: unit
        ref: "tests/test_theme/test_library.py::TestPreV12Compatibility + TestRenamePairs + TestResyncedPalettes + TestMutationIsolation + TestKeyErrorMessage + TestLibrarySweeps + TestNewSlugBehaviour"
        status: pass
    human_judgment: false
  - id: D4
    description: "Regeneration idempotence: double-run byte-identical; post-commit regeneration leaves git status clean (manual, once, per SPEC)"
    requirement: THEME-04
    verification:
      - kind: manual_procedural
        ref: "shasum double-run equal (0c037fdf...) and `git status --porcelain src/lifx/theme/data.py` empty after the Task 2 commit"
        status: pass
    human_judgment: false

# Metrics
duration: 17min
completed: 2026-08-14
status: complete
---

# Phase 6 Plan 02: Full Theme Import and Cutover Summary

**166-record data file built mechanically from the hardware capture plus the pre-v1.2 orphans, ThemeLibrary cut over to the generated dict alone (hand-written table deleted), and every compatibility/metadata guarantee pinned — 168 names resolve with app-accurate uint16 palettes**

## Performance

- **Duration:** ~17 min
- **Started:** 2026-08-14T13:28:43Z
- **Completed:** 2026-08-14T13:45:27Z
- **Tasks:** 3/3
- **Files modified:** 8

## Accomplishments

- **Task 1 — data file:** throwaway scratchpad conversion script (see "Conversion script logic" below) rebuilt `data/themes.jsonl` in full: 40 sport records dropped, the christmas ARCHIVES twin (capture index 133) proven palette-identical to the HOLIDAYS record (index 78) and dropped, emoji stripped per D-06/D-08, slugs derived via `analyse_themes.py::slug()` with a per-record assertion that `generator.derive_slug(stored_name)` reproduces the same key (all 138 agreed, including the eight punctuated names), every palette uint16-normalised through `HSBK.as_tuple()` and canonically sorted (D-24). The 28 orphans carried unchanged from `_THEMES` with category `Library`; aliases attached to `aurora` and `forrest`. Embedded verification passed on the first run: 166 records, categories {Moods 13, Art Series 10, Music 14, Nature 8, Space 11, Play 7, Holidays 15, Archives 60, Library 28}, 168 unique identifier keys, all app multisets == capture, all orphan multisets == `_THEMES`, no empty palettes, collision guard clean (zero live instances).
- **Task 2 — cutover:** regenerated `data.py` (168 keys), deleted the 366-line hand-written `_THEMES` literal and the transitional fallback; `get()` is a single lookup in the generated flat dict (D-13) over a fresh list, with the shortened KeyError; `get_available_themes()` returns `sorted(THEMES)` (D-15); `get_by_category()` left textually untouched over `_THEMES: dict[str, ThemeRecord] = THEMES`. Module docstring rewritten (generated provenance, 168 names, order-is-meaningless note; "60+ curated" and the aiolifx-themes reference dropped). All inventory test fixes applied; full suite green.
- **Task 3 — pins:** `PRE_V12_KEYS` literal 57-key fixture with parametrised COMPAT-01 resolution, rename-pair palette+identity tests, soothing kelvin-8000 pin, mutation-leak proof, KeyError name+pointer/no-listing tests, runtime sweeps (isidentifier, listing-resolves, ASCII identity distinct from slug, 9-category membership, canonical D-24 order, no `_legacy` key), MONDRIAN case-insensitivity, palette-only equality integration. Branch coverage on `library.py` and `theme.py`: 100% (branch-measured).

## Task Commits

1. **Task 1: Build the full committed data file** - `cbd451a` (feat)
2. **Task 2: Regenerate and cut ThemeLibrary over** - `bf3bcd8` (feat)
3. **Task 3: Pin the compatibility and metadata guarantees** - `f9f5da4` (test)

## Conversion script logic (Task 1, scratchpad — not committed)

Load 179 capture records (assert all `suspect_unchanged` false) → drop the 40 sport records (category contains AUSSIE RULES/LEAGUE/UNION) → collapse christmas (keep HOLIDAYS index 78, drop ARCHIVES index 133 after uint16-multiset identity proof) → per record: name = NFKD → drop non-ASCII → collapse whitespace → trim; category = same strip then Title Case; slug = `analyse_themes.slug()` (imported, not re-implemented) cross-asserted against `generator.derive_slug(stored_name)`; colours = `HSBK(**floats).as_tuple()` stored as ints, `canonical_palette()`-sorted → aliases on aurora/forrest → 28 orphans from `ThemeLibrary._THEMES` via `as_tuple()`, names Title-Cased from keys, collision guard (app wins, loud failure; zero instances) → embedded verification (all multisets, counts, keys, D-24 order) → write sorted-by-slug ASCII JSONL with fixed key order.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] codespell pre-commit hook rejected the data file**
- **Found during:** Task 1 commit
- **Issue:** the D-06 strip drops the non-ASCII curly apostrophe from the app's "What's the craic?" theme, and codespell flags the resulting stored name "Whats the craic?" as a typo. The generated `data.py` carries the same string, so skipping only the JSONL would not have sufficed.
- **Fix:** added `whats` to the codespell `--ignore-words-list` in `.pre-commit-config.yaml`; verified no other data-file word trips codespell.
- **Files modified:** .pre-commit-config.yaml
- **Commit:** cbd451a

**2. [Rule 1 - Bug] Test outside the plan's file list broken by the resync**
- **Found during:** Task 2 full-suite run (the plan instructs: run the full suite and fix remaining breakage with behavioural assertions)
- **Issue:** `tests/test_theme/test_theme.py::test_love_equals_romance` relied on love and romance sharing a palette — true pre-v1.2, false after romance resynced to its app palette while love stayed a Library orphan.
- **Fix:** replaced with `test_distinct_themes_with_identical_palettes_compare_equal` using the app's measured genuinely identical trio (memorial_day / independence / old_glory) — same D-19 behaviour, no palette pin.
- **Files modified:** tests/test_theme/test_theme.py
- **Commit:** bf3bcd8

### Findings (no code change)

**3. `exciting` is not uint16-identical to pre-v1.2 — the "2 identical shared slugs" classification is precision-dependent.**
The plan (and SPEC) state the 2 already-identical shared slugs (exciting, kwanzaa) are carried without diff at uint16 multiset precision. Measured during the one-off verification: at strict uint16 only **kwanzaa** is identical; **exciting** drifts by exactly 1 uint16 unit on its three trailing hues (pre-v1.2 stored integer degrees 239/271/294 which *round* to 43509/49334/53521, while the app itself sends 43508/49333/53520 — truncation). The "2 identical" classification came from `analyse_themes.py::palette_key`, which rounds hue to 0.1 degree; at that precision the measurement reproduces exactly (2 identical, 25 differing). No action taken: THEME-02 binds shipped == captured and prohibits inventing values, and the wire-visible positional behaviour is untouched — exciting's leading trio is 0/7282/10923 as pinned, and `test_rule_trio` passes. Recorded here so Phase 8's fidelity work knows the delta exists.

**4. Task 3 `tdd="true"` RED gate inapplicable.**
Every behaviour Task 3 pins was delivered by Task 2 within this same plan (the task is by design a pinning/characterisation task), so a failing-first RED run was impossible without deleting Task 2's work. Written as characterisation tests, verified passing, committed once as `test(...)`.

## Issues Encountered

None beyond the deviations above.

## Verification Evidence (plan-level)

- Task 1 verify script: 166 records, 168 resolvable names, pure ASCII bytes, sorted by slug, canonical D-24 order, alias map exact — passed
- Generator double-run byte-identical (shasum `0c037fdf274eb32e210c4f1fe5e66683e729b880`); post-Task-2-commit regeneration leaves `git status --porcelain src/lifx/theme/data.py` empty (THEME-04 convention check, performed once)
- Task 2 cutover verify: all 166 records resolved through `ThemeLibrary.get()` with multiset-exact palettes, matching identity triples and canonical order; `exciting` leads uint16 hues 0/7282/10923; soothing carries kelvin 8000; christmas → Holidays; forrest → 'Forrest'
- One-off THEME-03 shared-slug delta (scratchpad, vs `git show` of the pre-cutover library): at the classification precision (0.1 degree) 2 identical (exciting, kwanzaa) / 25 differing; at strict uint16 1 identical (kwanzaa) — see Finding 3
- `rg -n '_THEMES\[' tests/ src/` — zero hits after the cutover (the only pre-existing hit was the `library.py` read this plan rewrote); no `MappingProxyType` needed
- `grep -c 'HSBK(' src/lifx/theme/library.py` → 0
- `uv run pytest tests/ -q` → 3326 passed; `uv run ruff check .` clean; `uv run pyright` 0 errors
- Branch coverage: `src/lifx/theme/library.py` 100%, `src/lifx/theme/theme.py` 100% (with `--cov-branch`)

## Known Stubs

None — no placeholder values, no TODO/FIXME, no unwired data paths introduced.

## Threat Flags

None — no new network endpoints, auth paths or trust-boundary changes; regeneration reads only the committed local data file (T-06-06 honoured), and every shipped palette value traces to a capture record or `_THEMES` (T-06-05 honoured).

## User Setup Required

None.

## Next Phase Readiness

- Phase 7 (taxonomy, META-04, COMPAT-04) can replace `get_by_category()`'s hand-made taxonomy: the generated records already carry app categories, and `_THEMES` on the class now aliases the generated dict
- Phase 8 fidelity work should note Finding 3: strict-uint16 comparison against pre-v1.2 values is 1-ulp-sensitive where the old table stored rounded integer degrees
- Phase 9 owns committing resync tooling; the conversion logic to reproduce is recorded above

## Self-Check: PASSED

All modified files verified on disk; all three task commits (cbd451a, bf3bcd8, f9f5da4) verified in git history.

---
*Phase: 06-generated-theme-library*
*Completed: 2026-08-14*
