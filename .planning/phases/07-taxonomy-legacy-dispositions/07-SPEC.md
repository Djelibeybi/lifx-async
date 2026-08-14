# Phase 7: Taxonomy & Legacy Dispositions — Specification

**Created:** 2026-08-15
**Ambiguity score:** 0.08 (gate: ≤ 0.20)
**Requirements:** 7 locked

## Goal

`ThemeLibrary` navigates by the LIFX app's category taxonomy instead of a hand-made one, every
pre-v1.2 category name either returns themes or raises naming its replacement, and each of the
28 `Library` orphan keys carries a machine-readable keep-or-deprecate disposition.

## Background

Phase 6 replaced the hand-written palette table with a generated one, but left
`get_by_category()` untouched. Measured against the shipped code and data:

- The generated data carries **8 app categories** — Archives 60, Art Series 10, Holidays 15,
  Moods 13, Music 14, Nature 8, Play 7, Space 11 — plus the **synthetic `Library` 28** that
  Phase 6 invented for the pre-v1.2 orphans. META-04's "11 app categories" counts the 3 sport
  categories Phase 6 dropped (AUSSIE RULES, LEAGUE, UNION).
- `get_by_category()` still holds a **hand-made 6-name taxonomy** (`seasonal`, `holiday`,
  `mood`, `ambient`, `functional`, `atmosphere`) over hardcoded theme-name lists.
- **`get_by_category(theme.category)` raises for every theme in the library** — the method wants
  `"holiday"`, the data says `"Holidays"`. Recorded as WR-02 in `06-REVIEW.md`.
- **3 names in those lists are dead**: `winter`, `romantic` and `dramatic` resolve to nothing
  and are silently filtered out of the result.
- The docstring advertises a **`time` category that has never existed**.
- No legacy name maps 1:1 to an app category. Measured spread:

  | Legacy name | Themes today | App categories they now belong to |
  |---|---|---|
  | `holiday` | 12 | Holidays 7 + Library 5 |
  | `mood` | 18 | Moods 10 + Library 5 + Play 1 |
  | `ambient` | 6 | Play 5 + Moods 1 |
  | `seasonal` | 2 (3rd dead) | Library 2 |
  | `functional` | 3 | Library 3 |
  | `atmosphere` | 3 | Library 2 + Moods 1 |

- COMPAT-04's "30 orphans" = the **28 `Library` keys** plus the 2 rename aliases
  (`aurora_borealis`→`aurora`, `forest`→`forrest`) that Phase 6 already wired. Only the 28 need
  a disposition.

## Requirements

1. **Category listing**: `ThemeLibrary.get_categories()` returns every category present in the
   generated data.
   - Current: No method exists. A caller cannot discover what categories the library has.
   - Target: `get_categories()` returns a `list[str]` of the 9 category names, sorted ascending
     by plain codepoint order.
   - Acceptance: Returns exactly `["Archives", "Art Series", "Holidays", "Library", "Moods",
     "Music", "Nature", "Play", "Space"]`.

2. **Category lookup**: `get_by_category()` reads the app taxonomy from the generated records.
   - Current: Reads a hardcoded 6-key dict of theme-name lists; `get_by_category(theme.category)`
     raises for every theme in the library; 3 listed names silently resolve to nothing.
   - Target: Returns `dict[str, Theme]` for every record whose `category` matches, keyed by slug,
     sorted by slug. Name matching normalises both sides by lowercasing and collapsing each run of
     non-alphanumeric characters to a single underscore (the D-09 slug rule), so `"Art Series"`,
     `"art series"` and `"art_series"` all resolve and `"artseries"` does not. The hardcoded lists
     are deleted.
   - Acceptance: `get_by_category(t.category)` succeeds and contains `t` for all 168 names;
     `len(get_by_category("Holidays")) == 15`; `get_by_category("art_series")` equals
     `get_by_category("Art Series")`; `get_by_category("artseries")` raises `ValueError`.

3. **Legacy category names**: every pre-v1.2 category name resolves or raises naming its
   replacement.
   - Current: All 6 legacy names return themes from hardcoded lists. No name raises.
   - Target: `holiday` → `Holidays` and `mood` → `Moods` return the app category's themes.
     `seasonal`, `ambient`, `functional` and `atmosphere` raise `ValueError` naming the closest
     app category — `Nature`, `Play`, `Library` and `Moods` respectively. Lookup order is app
     taxonomy first, legacy map second.
   - Acceptance: `get_by_category("holiday")` returns the 15 Holidays themes;
     `get_by_category("mood")` returns the 13 Moods themes; each of the other 4 raises
     `ValueError` whose message contains its named replacement; `get_by_category("HOLIDAY")`
     behaves identically to `get_by_category("holiday")`.

4. **Orphan dispositions**: each of the 28 `Library` orphans carries a recorded fate in the data.
   - Current: `data/themes.jsonl` records carry slug, name, category and colours. No disposition
     field exists in the schema, the generator, or `ThemeRecord`.
   - Target: Every record carries `disposition ∈ {"lifx-app", "library-only", "deprecated"}`. A
     `deprecated` record also carries `replaced_by` naming a key that resolves in `THEMES`. The
     140 app records are `lifx-app`. The 28 orphans split **9 deprecated / 19 library-only**:

     | Deprecated key | replaced_by | Palette distance | Basis |
     |---|---|---|---|
     | `focusing` | `gentle` | 0.00 | identical palette |
     | `intense` | `fantasy` | 0.00 | identical palette |
     | `shamrock` | `st_patrick_s_day` | 0.08 | palette + semantic |
     | `love` | `romance` | 0.09 | palette + semantic |
     | `holly` | `christmas` | 0.09 | Christmas iconography; `kwanzaa` at 0.08 is within noise |
     | `fire` | `warm_ember` | 0.11 | palette + semantic |
     | `proud` | `pride` | 0.13 | palette + semantic |
     | `pumpkin` | `pumpkin_spice` | 0.13 | palette + semantic |
     | `santa` | `candy_cane` | 0.14 | Christmas-adjacent of a tied pair with `canada_day` |

     **library-only (19):** `arctic`, `autumn`, `bias_lighting`, `cherry_blossom`, `cyberpunk`,
     `deep_sea`, `desert`, `epic`, `evening`, `galaxy`, `hygge`, `neon`, `relaxing`, `serene`,
     `spring`, `sports`, `tropical`, `vaporwave`, `water`.

     The governing rule, applied to produce the split: deprecate only where a named app theme is
     both palette-close **and** semantically the same idea. Palette proximity alone is not
     succession — `galaxy` sits 0.13 from `party` and stays library-only.
   - Acceptance: All 168 records carry a `disposition` in the allowed set; exactly 9 are
     `deprecated` with the replacements above; exactly 19 are `library-only`; every `replaced_by`
     resolves in `THEMES`; the generator aborts on a `deprecated` record with no `replaced_by`.

5. **Disposition on the public object**: a retrieved `Theme` exposes its disposition.
   - Current: `Theme` carries `slug`, `name` and `category` from Phase 6. No disposition.
   - Target: `Theme.disposition` and `Theme.replaced_by` are readable on the object `get()`
     returns. `replaced_by` is `None` unless `disposition == "deprecated"`. `Theme.__eq__` remains
     palette-only and ignores both new fields, exactly as it ignores the Phase 6 identity fields
     (D-19 unchanged); `Theme` remains unhashable (D-20 unchanged).
   - Acceptance: `get("fire").disposition == "deprecated"` and `.replaced_by == "warm_ember"`;
     `get("hygge").disposition == "library-only"` and `.replaced_by is None`;
     `get("christmas").disposition == "lifx-app"`; two Themes with equal palettes and different
     dispositions compare equal; `Theme.__hash__ is None`.

6. **Taxonomy documentation**: the taxonomy and the v1.2 migration are documented.
   - Current: No docs describe the categories. The `get_by_category()` docstring lists a
     nonexistent `time` category and names only 4 of the 6 legacy keys.
   - Target: A documentation page lists the 9 categories with their theme counts, records for all
     6 legacy names whether they map or raise and to what, and tables the 9 deprecated keys with
     their replacements. The stale docstring is corrected.
   - Acceptance: The page names all 9 categories, all 6 legacy names, and all 9 deprecated keys;
     no docstring or doc page mentions a `time` category.

7. **No key stops resolving**: the Phase 6 compatibility guarantee holds unchanged.
   - Current: 168 names resolve (166 slugs + 2 rename aliases). All 57 pre-v1.2 keys among them.
   - Target: Unchanged. Deprecation records a fate; it never removes or renames. Alias identity
     binding (`THEMES[alias] is THEMES[target]`) is preserved.
   - Acceptance: All 168 names still resolve; the `PRE_V12_KEYS` 57-key fixture from Phase 6
     still passes; both rename aliases still share their target's record object.

## Boundaries

**In scope:**
- `get_categories()` and the rewrite of `get_by_category()` over the app taxonomy
- The legacy-name map and its raising branch, with replacement-naming messages
- The `disposition` / `replaced_by` schema addition: data file, generator validation, generated
  module, `ThemeRecord`, and `Theme`
- The 28 orphan disposition values, as locked in requirement 4
- A taxonomy documentation page and the corrected `get_by_category()` docstring

**Out of scope:**
- Removing or renaming any orphan key — deprecation records a fate, it never deletes; removal
  would be a v2.0 decision
- Restoring the 3 sport categories — they stay dropped; `sports` is a library-only orphan key and
  `atmosphere` (which listed it) raises, neither being a route back to the 40 sport themes
- Reviving `winter`, `romantic` or `dramatic` — they never resolved to real themes; they simply
  stop being silently filtered
- Any palette or colour change — Phase 7 touches taxonomy and metadata only; Phase 8 owns fidelity
- Runtime deprecation signalling — no `DeprecationWarning`, no log line; disposition is queryable
  data, never emitted
- Broader theme documentation — Phase 9 owns DOCS-03; this phase documents only the taxonomy and
  the v1.2 migration

## Constraints

- Zero runtime dependencies — unchanged project constraint
- Australian English throughout; `uv` for all tooling
- CI requires 100% **branch** patch coverage
- `data/themes.jsonl` remains the single source of truth; `src/lifx/theme/data.py` stays generated
  and is never hand-edited. Adding two fields is a generator schema change, so regeneration
  idempotence (THEME-04) must be re-established after it
- The `disposition` addition must be additive — no existing `ThemeRecord` or `Theme` field changes
  type or meaning
- `replaced_by` need only resolve in `THEMES`; the schema permits a chain to another deprecated
  key. No chain exists today — all 9 replacements are `lifx-app` records

## Acceptance Criteria

- [ ] `get_categories()` returns exactly the 9 category names, codepoint-sorted
- [ ] `get_by_category(t.category)` succeeds and contains `t` for all 168 names
- [ ] `get_by_category("art_series") == get_by_category("Art Series")`; `"artseries"` raises `ValueError`
- [ ] `get_by_category("holiday")` returns 15 themes; `get_by_category("mood")` returns 13
- [ ] `seasonal`, `ambient`, `functional`, `atmosphere` each raise `ValueError` naming `Nature`, `Play`, `Library`, `Moods` respectively
- [ ] An unknown or empty-string category raises `ValueError` listing the available categories
- [ ] All 168 records carry `disposition` in `{"lifx-app", "library-only", "deprecated"}`
- [ ] Exactly 9 records are `deprecated` with the replacements in requirement 4; exactly 19 are `library-only`; every `replaced_by` resolves in `THEMES`
- [ ] The generator aborts with a controlled error on a `deprecated` record with no `replaced_by`
- [ ] `Theme.disposition` and `Theme.replaced_by` are readable; `replaced_by is None` unless deprecated
- [ ] Two Themes with equal palettes and differing dispositions compare equal; `Theme.__hash__ is None`
- [ ] Regenerating from the data file reproduces `data.py` byte-identically after the schema change
- [ ] All 168 names still resolve; the 57-key `PRE_V12_KEYS` fixture passes; both rename aliases still share their target's record object
- [ ] The docs page names all 9 categories, all 6 legacy names and all 9 deprecated keys
- [ ] No docstring or doc page mentions a `time` category
- [ ] **MUST NOT** present `Library` as a category the LIFX app defines
- [ ] **MUST NOT** assign or withhold a disposition based on what a theme depicts
- [ ] **MUST NOT** fetch taxonomy or disposition data from any network source, LIFX API or device

## Edge Coverage

**Coverage:** 17/23 applicable edges resolved · 6 dismissed · 0 unresolved

| Category | Requirement | Status | Resolution / Reason |
|----------|-------------|--------|---------------------|
| adjacency | R1 | ✅ covered | Names derive from the validated record set; no two of the 9 differ only by case or whitespace |
| empty | R1 | ✅ covered | A zero-record category cannot exist since names derive from records; an empty library returns `[]` |
| encoding | R1 | ✅ covered | All category names are pure ASCII (META-02); comparison is ASCII-only |
| ordering | R1 | ✅ covered | Plain codepoint `sorted()`; `"Archives"` precedes `"Art Series"` |
| adjacency | R2 | ✅ covered | Lookup order fixed: app taxonomy first, legacy map second. No current name collides |
| empty | R2 | ✅ covered | Unknown or empty-string category raises `ValueError` listing available categories |
| encoding | R2 | ✅ covered | Both sides normalised by lower + non-alphanumeric-run→`_` (D-09); `"artseries"` raises |
| ordering | R2 | ✅ covered | Returned dict is sorted by slug |
| empty | R3 | ✅ covered | `""` raises the generic unknown-category error, not a legacy-replacement message |
| encoding | R3 | ✅ covered | Legacy names pass through the same normalisation, so `"HOLIDAY"` resolves |
| adjacency | R4 | ✅ covered | `replaced_by` must resolve in `THEMES`; chains permitted by schema, zero exist today |
| empty | R4 | ✅ covered | `replaced_by` is `None` unless deprecated; generator aborts on deprecated-without-replacement |
| encoding | R4 | ✅ covered | `disposition` and `replaced_by` are ASCII, enforced by the existing canonical-key check |
| ordering | R4 | ⛔ dismissed | `disposition` is a per-record scalar; there is no collection whose order could vary |
| unclassified | R5 | ✅ covered | `disposition` is present on every record including the 140 app themes (`"lifx-app"`); `__eq__` ignores both new fields |
| adjacency | R6 | ✅ covered | The docs table must list all 6 legacy names, including the 4 that raise |
| empty | R6 | ✅ covered | One row per legacy name and per deprecated key; no empty sections |
| encoding | R6 | ⛔ dismissed | Markdown documentation; no encoding contract beyond the repo's UTF-8 convention |
| ordering | R6 | ⛔ dismissed | The presentation order of a docs table carries no behavioural contract |
| adjacency | R7 | ✅ covered | The 168 count includes the 2 rename alias keys; alias identity binding is preserved |
| empty | R7 | ⛔ dismissed | "No key is removed" has no empty-input form |
| encoding | R7 | ⛔ dismissed | Keys are unchanged from Phase 6, whose ASCII guarantee already holds |
| ordering | R7 | ⛔ dismissed | Resolution is by key and order-independent |

## Prohibitions (must-NOT)

**Coverage:** 3/4 applicable prohibitions resolved · 1 dismissed · 0 unresolved

| Prohibition (must-NOT statement) | Requirement | Status | Verification / Reason |
|----------------------------------|-------------|--------|------------------------|
| MUST NOT present the synthetic `Library` category as one the LIFX app defines, in docs, docstrings or error messages | R1, R6 | resolved | verification: judgment — `Library` is listable by operator decision, so the wording is the only thing keeping the attribution honest |
| MUST NOT assign or withhold a disposition based on what a theme depicts or represents, rather than palette and semantic evidence | R4 | resolved | verification: judgment — every one of the 9 calls must trace to the measured distance and a name correspondence |
| MUST NOT fetch taxonomy or disposition data from any network source, LIFX API or device — categories come from the committed data file alone | R1, R4 | resolved | verification: test — no network imports in `src/lifx/theme/`, the Phase 6 T-06-03/T-06-06 check. Descriptor not captured: the schema's `check_kind` values (`node-test`, `lint-rule`) do not fit a pytest assertion; the check is named here in prose for plan-phase to wire |
| MUST NOT record a `replaced_by` that is not evidenced by the palette-distance + semantic rule | R4 | dismissed | Not selected by the operator. All 9 replacements are individually locked in requirement 4 with their measured distances, so no successor judgement remains open during execution for this prohibition to guard |

## Ambiguity Report

| Dimension          | Score | Min  | Status | Notes                                                        |
|--------------------|-------|------|--------|--------------------------------------------------------------|
| Goal Clarity       | 0.95  | 0.75 | ✓      | API shape, semantics and disposition mechanism all concrete   |
| Boundary Clarity   | 0.92  | 0.70 | ✓      | 6-item out-of-scope list, each with reasoning                 |
| Constraint Clarity | 0.85  | 0.65 | ✓      | Public surface, deprecation behaviour and equality all pinned |
| Acceptance Criteria| 0.92  | 0.70 | ✓      | 18 pass/fail criteria; all 28 dispositions locked             |
| **Ambiguity**      | 0.08  | ≤0.20| ✓      |                                                              |

Status: ✓ = met minimum, ⚠ = below minimum (planner treats as assumption)

## Interview Log

| Round | Perspective | Question summary | Decision locked |
|-------|-------------|------------------|-----------------|
| 1 | Researcher | API shape for category navigation? | Rewrite `get_by_category()` over app categories; add `get_categories()`; delete the hardcoded lists |
| 1 | Researcher | What do the 6 legacy names do? | Map where sane, raise naming the replacement elsewhere |
| 1 | Researcher | Is synthetic `Library` public? | Yes — a real, listable category |
| 2 | Researcher | Measured: no legacy name maps 1:1. What should a mapped name return? | The app category's set, accepting that a pre-v1.2 caller gets a different set; only `holiday` and `mood` map |
| 2 | Researcher | Where does the COMPAT-04 disposition live? | In the JSONL record, generated into `data.py` |
| 2 | Simplifier | Irreducible core? | All four: navigation API, legacy handling, 28 dispositions, and the docs page |
| 3 | Boundary Keeper | Is disposition on the public `Theme`? | Yes — `Theme.disposition` and `Theme.replaced_by` |
| 3 | Boundary Keeper | Runtime behaviour on a deprecated key? | Nothing — resolves silently; disposition is data, never emitted |
| 3 | Boundary Keeper | What is out of scope? | All four proposed exclusions accepted |
| 4 | Seed Closer | The 28 per-key dispositions? | Decided in session against measured palette distance: 9 deprecated, 19 library-only |
| 4 | Seed Closer | Deprecation rule? | Palette proximity **and** semantic succession — proximity alone is not succession |
| 4 | Seed Closer | Contested `santa` and `holly`? | `santa`→`candy_cane`; `holly`→`christmas` |
| 5.5 | Edge probe | Category name matching form? | Lower + non-alphanumeric-run→`_`, the D-09 slug rule |
| 5.5 | Edge probe | `replaced_by` constraint? | Must resolve in `THEMES`; chains permitted |
| 5.5 | Edge probe | Disposition of the 140 app themes? | `"lifx-app"` — a third explicit value, no `None` |
| 5.5 | Edge probe | Lookup order across namespaces? | App category first, then legacy |
| 5.6 | Prohibition probe | Which must-NOTs to carry? | 3 kept (Library attribution, no subject-matter judgement, no network); 1 dismissed |

---

*Phase: 07-taxonomy-legacy-dispositions*
*Spec created: 2026-08-15*
*Next step: /gsd-discuss-phase 7 — implementation decisions (how to build what's specified above)*
