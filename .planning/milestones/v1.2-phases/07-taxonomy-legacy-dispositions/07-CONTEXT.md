# Phase 7: Taxonomy & Legacy Dispositions - Context

**Gathered:** 2026-08-15
**Status:** Ready for planning

<domain>
## Phase Boundary

Rewrite `ThemeLibrary`'s category navigation over the app's own 9-category taxonomy, give
each of the 6 pre-v1.2 category names a working fate (2 resolve, 4 raise naming their
replacement), and add a `disposition` / `replaced_by` field pair to every one of the 166
theme records — carried from `data/themes.jsonl` through the generator to the public
`Theme`. No key stops resolving; no palette changes.

</domain>

<spec_lock>
## Requirements (locked via SPEC.md)

**7 requirements are locked.** See `07-SPEC.md` for full requirements, boundaries, edge
coverage, prohibitions and acceptance criteria.

Downstream agents MUST read `07-SPEC.md` before planning or implementing. Requirements are
not duplicated here.

**In scope (from SPEC.md):**

- `get_categories()` and the rewrite of `get_by_category()` over the app taxonomy
- The legacy-name map and its raising branch, with replacement-naming messages
- The `disposition` / `replaced_by` schema addition: data file, generator validation,
  generated module, `ThemeRecord`, and `Theme`
- The 28 orphan disposition values, as locked in requirement 4
- A taxonomy documentation page and the corrected `get_by_category()` docstring

**Out of scope (from SPEC.md):**

- Removing or renaming any orphan key — deprecation records a fate, it never deletes
- Restoring the 3 sport categories
- Reviving `winter`, `romantic` or `dramatic` — they never resolved to real themes
- Any palette or colour change — Phase 8 owns fidelity
- Runtime deprecation signalling — no `DeprecationWarning`, no log line
- Broader theme documentation — Phase 9 owns DOCS-03

</spec_lock>

<decisions>
## Implementation Decisions

### Legacy category map

- **D-01:** The 6 pre-v1.2 category names and their fates live as a **module-level constant
  in the hand-written `library.py`**, not in `data/themes.jsonl` and not derived at runtime.
  It is API migration behaviour, not theme data: the JSONL holds per-theme records and has
  no place to hang a category-level mapping, and D-04 (Phase 6) already ruled out a second
  generator input. Phase 9's resync tooling therefore never touches it. — **Reversibility:**
  reversible — a private constant in one module; moving it into the data file later is a
  generator change with no public-API effect.
- **D-02:** The constant is **one dict with tagged values** —
  `_LEGACY_CATEGORIES: dict[str, tuple[str, bool]]` mapping legacy name →
  (app category, resolves). One lookup, all 6 fates readable in one place, and the raising
  branch still holds a real category name so R3's "message names its replacement" writes
  itself. Rejected: two dicts (fates split across two places), and `str | None` where `None`
  means raise (leaves the raising branch with no replacement to name).
- **D-03:** The map is **private** — `_LEGACY_CATEGORIES`, underscore-prefixed, absent from
  `lifx.theme.__all__`, with no public accessor. SPEC R1 pins `get_categories()` to exactly
  the 9 real category names; the legacy names are a migration shim, not taxonomy. The new
  migration docs page carries the table for humans.
- **D-04:** Category-name normalisation **reuses the generator's `derive_slug` rule (D-09)
  rather than reimplementing it**. Since `scripts/generate_theme_data.py` lives outside the
  wheel, the shared implementation must sit inside the package and the generator import it —
  one rule, stated once, as D-09 intended. Both the app-taxonomy lookup and the legacy
  lookup pass through it, which is what makes `"Art Series"` / `"art series"` /
  `"art_series"` agree and `"artseries"` raise.

### Disposition schema

- **D-05:** `disposition` is **required on all 166 records** — it joins `_REQUIRED_FIELDS` in
  the generator rather than defaulting to `"lifx-app"` when absent. Every line states its
  fate, and a record cannot be added without a deliberate decision. Accepted cost: a one-off
  rewrite of all 166 JSONL lines, and Phase 9's capture→JSONL converter must emit the field.
  Rejected: optional-with-default (a forgotten orphan silently becomes an app theme — the
  same silent-drift class D-23 already accepted once) and category-conditional requirement
  (adds cross-field validation the otherwise-flat schema avoids). — **Reversibility:** costly
  — the field becomes part of the format Phase 9's tooling reads and writes.
- **D-06:** `replaced_by` is **`str | None`, `None` when not deprecated** — never an empty
  string. Matches D-17 (identity fields are `None`, never `""`) and SPEC R5's acceptance
  criterion verbatim (`get("hygge").replaced_by is None`). On `ThemeRecord`:
  `disposition: str` (a record always has a fate) and `replaced_by: str | None = None`.
- **D-07:** On `Theme`, both fields are **keyword-only optionals defaulting to `None`** —
  `Theme(colors, *, slug=None, name=None, category=None, disposition=None, replaced_by=None)`,
  the exact D-16/D-17 pattern Phase 6 established. So `Theme.disposition` is `str | None`
  while `ThemeRecord.disposition` is `str`: a record always has a fate, a caller-constructed
  theme has none. Keeps the addition additive — `Theme([...])` still works, satisfying the
  SPEC constraint that no existing field changes type or meaning.
- **D-08:** The three new generator validations — disposition in the allowed set, `deprecated`
  requires `replaced_by`, `replaced_by` resolves in `THEMES` — get **one failing-record test
  each**, in the existing generator test file, asserting the controlled abort. This matches
  how the Phase 6 validations (bad slug, bad kelvin, oversized palette) are already tested,
  and SPEC pins the deprecated-without-replacement abort as an acceptance criterion.
  Explicitly **not** adding a whole-file invariant test pinning 9 / 19 / 138 counts — D-23
  declined count pinning for Phase 6 data and that stands.

### Documentation

- **D-09:** The taxonomy and migration content ships as a **new page under the existing
  `Migration:` nav section** — `docs/migration/theme-taxonomy-v1.2.md`, alongside
  `migration/effect-api-changes.md`. The 6 legacy names and 9 deprecated keys are migration
  content by nature; keeping them out of `user-guide/themes.md` (a 400-line cookbook) leaves
  Phase 9's DOCS-03 reference listing a clean, non-colliding home.
- **D-10:** The page is an explicit **point-in-time record, stamped "As of migration"** —
  the category theme counts are historical claims, not live ones, and the page is
  deliberately **not** resynced when the library changes. No CI check pins the counts and no
  build-time generation produces them. This is what makes hand-written tables honest here,
  where Phase 6's hand-listed inventory (retired in `47e2864`) was not: that page claimed to
  be current.
- **D-11:** The correction reaches **all 4 stale sites**, not just the one SPEC names:
  `library.py:120` (the nonexistent `time` category), `library.py:46` (the class-docstring
  example `get_by_category("seasonal")`, which will *raise* after this phase), the
  now-false known-gap note at `docs/api/themes.md:67`, and `docs/getting-started/themes.md:30-31`
  (`"holiday"` / `"mood"` still resolve, but the examples are re-pointed at the app names).
  Nothing shipped teaches a name that raises.

### Scope

- **D-12:** **Issue #201** (`get_available_themes()` cannot distinguish the 2 rename aliases
  from the 166 primaries) is **deferred to Phase 9**, despite STATE.md assigning it to
  Phase 7. The locked SPEC does not carry it — R7 guarantees only that aliases keep
  resolving — and Phase 9's resync tooling needs primary enumeration anyway. No new public
  API is added for it here. The GitHub issue is left untouched; this decision is the record,
  and #201 should be retargeted when Phase 9 is planned.
- **D-13:** **Issue #200** is closed by this phase's R2/R3 — it is the same defect as WR-02
  in `06-REVIEW.md`. Close it at ship, not before.

### Claude's Discretion

None — every question in this discussion was answered directly.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Locked requirements

- `.planning/phases/07-taxonomy-legacy-dispositions/07-SPEC.md` — Locked requirements,
  boundaries, edge coverage, prohibitions and acceptance criteria. **MUST read before
  planning.** Requirement 4 holds the full 9-deprecated / 19-library-only disposition table
  with the measured palette distances that justify each call.

### Prior-phase decisions this phase is bound by

- `.planning/phases/06-generated-theme-library/06-CONTEXT.md` — D-01 (module split),
  D-04 (one generator input), D-07 (Title Case categories, case-insensitive lookup),
  D-09 (the slug rule D-04 above reuses), D-13 (flat dict, no alias indirection),
  D-16/D-17 (keyword-only optional identity, `None` never `""`), D-19a/D-20a
  (`palette_equals`, identity `__eq__`, `Theme` stays hashable), D-21/D-22 (coverage
  omissions), D-23 (nothing pinned), D-24 (canonical palette ordering).
- `.planning/phases/06-generated-theme-library/06-REVIEW.md` — WR-02 is this phase's R2/R3.

### Existing code this phase changes

- `src/lifx/theme/library.py` — `get_by_category()` at :116 (the hardcoded 6-key dict at
  :130-188 is deleted), the stale docstring at :120, the class-docstring example at :46, and
  the `_THEMES` class attribute at :57 that every lookup already reads through.
- `src/lifx/theme/theme.py` — `Theme` gains `disposition` / `replaced_by`.
- `src/lifx/theme/data.py` — generated; `ThemeRecord` gains two fields. Never hand-edited.
- `scripts/generate_theme_data.py` — `_REQUIRED_FIELDS` (:48), `_OPTIONAL_FIELDS` (:51),
  `validate_records()` (:248), `emit_data_module()` (:380), `derive_slug()` (:110).
- `data/themes.jsonl` — 166 records; every line gains `disposition`.
- `docs/migration/theme-taxonomy-v1.2.md` — new page; `mkdocs.yml` nav `Migration:` section.
- `docs/api/themes.md` :67-69, `docs/getting-started/themes.md` :30-31 — corrections.

### Project constraints

- `CLAUDE.md` — theme-layer overview, the generator's `scripts/` placement and why, the
  regeneration command, and the rule that user-visible fields are never bytes.
- `.planning/codebase/CONVENTIONS.md` — naming, module design, type annotations.
- `.planning/codebase/TESTING.md` — fixtures, markers, coverage expectations.
- GitHub issues #200 (closed by this phase) and #201 (deferred per D-12).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- `scripts/generate_theme_data.py::derive_slug()` (:110) — the D-09 rule. D-04 makes it
  shared rather than duplicated; note the generator lives outside the wheel, so the shared
  copy must move *into* the package and the generator import it, not the reverse.
- `scripts/generate_theme_data.py::_fail()` (:161) and `validate_records()` (:248) — the
  existing controlled-abort pattern the three new validations extend.
- `ThemeLibrary._THEMES` (:57) — already the subclass-safe indirection every lookup reads,
  with a comment explicitly reserving the taxonomy rewrite for Phase 7.
- `tests/test_theme/conftest.py` — existing theme fixtures.
- The Phase 6 `PRE_V12_KEYS` 57-key fixture — R7's regression guard, already in the suite.

### Established Patterns

- Generated modules carry a DO-NOT-EDIT header naming source and generator; the generator is
  omitted from coverage but still has a test file (D-21).
- Case-insensitive lookup is house style — `get()` lowercases its input, and D-07 (Phase 6)
  extended that to categories.
- Keyword-only optional fields with defaults are how identity and the v1.1 device-state
  fields were added without breaking existing constructors.
- Rename aliases are emitted *after* the dict literal and bind the target's own record
  object, so alias identity (R7's `THEMES[alias] is THEMES[target]`) is already mechanised —
  the disposition addition must not disturb that emission order.

### Integration Points

- `get_by_category()` — the method being rewritten; today it filters through
  `if name in cls._THEMES`, which is what silently swallows `winter` / `romantic` / `dramatic`.
- `get()` — unchanged in behaviour, but constructs the `Theme` and so gains the two new
  keyword arguments.
- `lifx.theme.__all__` — `get_categories()` is a new public name and needs a deliberate
  decision about joining the exported surface; `_LEGACY_CATEGORIES` explicitly does not (D-03).
- CI regenerates and diffs `src/lifx/theme/data.py` on every change to `data/**` — the
  schema change must leave regeneration idempotent (THEME-04) or that job fails.

### Measured facts confirmed during this discussion

- `data/themes.jsonl` is 166 lines; `THEMES` resolves 168 keys (166 records + 2 alias keys).
- Generator fields today: required `slug`, `name`, `category`, `colors`; optional `aliases`.
- Exactly one source of the phantom `time` category: `library.py:120`.
- `library.py:46` ships a `get_by_category("seasonal")` example that this phase makes raise.
- `mkdocs.yml` already has a `Migration:` nav section with one page in it.

</code_context>

<specifics>
## Specific Ideas

- "Just add 'As of migration' as an indication the values may change over time but the
  migration docs will not be updated to reflect current status" — the operator's resolution
  of the docs-staleness question (D-10). It reframes the page: not a live reference that
  needs a CI check, but a dated migration record whose claims are scoped to the moment of
  migration. That is a different contract from the Phase 6 inventory page that went stale.
- The legacy map is deliberately framed as a *shim*, not as taxonomy — which is why it is
  private (D-03) and why `get_categories()` never lists its names.

</specifics>

<deferred>
## Deferred Ideas

- **Issue #201 — alias-vs-primary listing** (`get_available_themes(include_aliases=False)`,
  or another way to enumerate the 166 primaries). Deferred to Phase 9 per D-12; the resync
  tooling needs primary enumeration anyway. Note `get("forest").slug == "forrest"` already
  holds via the Phase 6 alias binding, so the round-trip half of the issue is satisfied — it
  is the *listing* that cannot distinguish them.
- **A public accessor for the legacy category map** (`get_legacy_categories()`) — offered and
  declined (D-03). Worth revisiting only if callers ask for programmatic migration support.
- **A whole-file invariant test pinning the 9 / 19 / 138 disposition counts** — offered and
  declined (D-08), consistent with D-23. If a future resync ships with a wrong disposition
  split, this is the mechanism that would have caught it.
- **Generating the docs tables at build time** — offered and declined (D-10). Would become
  relevant if the taxonomy page were ever re-scoped from migration record to live reference.
- **How the `disposition` field is added to all 166 JSONL lines** (scripted rewrite vs
  hand edit) and **how THEME-04 regeneration idempotence is re-established** after the
  schema change — raised but not discussed; both are planner/executor mechanics rather than
  operator decisions.

</deferred>

---

*Phase: 7-Taxonomy & Legacy Dispositions*
*Context gathered: 2026-08-15*
