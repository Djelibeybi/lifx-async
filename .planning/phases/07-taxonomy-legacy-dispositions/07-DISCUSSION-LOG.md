# Phase 7: Taxonomy & Legacy Dispositions - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-15
**Phase:** 07-taxonomy-legacy-dispositions
**Areas discussed:** Legacy map location, Disposition schema, Docs page shape, Issue #201 scope

---

## Legacy map location

### Q1 — Where should the 6 pre-v1.2 category names and their fates be recorded?

| Option | Description | Selected |
|--------|-------------|----------|
| Constant in `library.py` | Module-level frozen dict in the hand-written API module; the JSONL is per-theme and has no place for a category-level map; Phase 9 tooling never touches it | ✓ |
| Generated from a second data file | A new `data/legacy-categories.jsonl` the generator reads — but D-04 already rejected a second generator input | |
| Derived at runtime from `THEMES` | Match legacy names to app categories at import — cannot express the 4 raising names | |

**User's choice:** Constant in `library.py`

### Q2 — How should that constant encode the two fates (2 resolve, 4 raise)?

| Option | Description | Selected |
|--------|-------------|----------|
| One dict, tagged values | `dict[str, tuple[str, bool]]` — name → (app category, resolves); one lookup, all 6 fates in one place, raising branch still names a real category | ✓ |
| Two separate dicts | `_LEGACY_ALIASES` + `_LEGACY_RETIRED` — plain at the definition site, but two membership checks and fates in two places | |
| One dict, `None` means raise | `dict[str, str \| None]` — compact, but the raising branch then has no replacement to name, which R3 requires | |

**User's choice:** One dict, tagged values

### Q3 — Should the legacy map be reachable by callers?

| Option | Description | Selected |
|--------|-------------|----------|
| Private, underscore-prefixed | `_LEGACY_CATEGORIES`, out of `lifx.theme.__all__`; R1 pins `get_categories()` to the 9 real names; docs carry the table for humans | ✓ |
| Private constant, public accessor | `ThemeLibrary.get_legacy_categories()` — new public surface the SPEC does not require | |
| Public module constant | Export `LEGACY_CATEGORIES` — locks the internal tuple shape into the public API | |

**User's choice:** Private, underscore-prefixed

### Q4 — Where should the category-name normalisation live?

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse the generator's `derive_slug` | One shared D-09 implementation; since the generator sits outside the wheel, the shared copy moves into the package and the generator imports it | ✓ |
| Private helper in `library.py` | A local `_normalise_category()` — no cross-package import, but two implementations of D-09 that must not drift | |
| Precompute a lookup index at import | Build `{normalised: Title Case}` from `THEMES` — still needs a normalisation function; orthogonal | |

**User's choice:** Reuse the generator's `derive_slug`

---

## Disposition schema

### Q1 — How should `disposition` appear in `data/themes.jsonl`?

| Option | Description | Selected |
|--------|-------------|----------|
| Explicit on all 166 | Joins `_REQUIRED_FIELDS`; every line states its fate; costs a one-off rewrite and makes the field non-optional for Phase 9's converter | ✓ |
| Optional, generator defaults to `lifx-app` | Only the 28 orphans carry it — smallest diff, but a forgotten new orphan silently becomes an app theme | |
| Required for `Library` records only | Conditional requirement — precise, but adds cross-field validation the flat schema avoids | |

**User's choice:** Explicit on all 166

### Q2 — How should `replaced_by` be carried when a record is not deprecated?

| Option | Description | Selected |
|--------|-------------|----------|
| `str \| None`, `None` when not deprecated | Matches D-17 and SPEC R5's acceptance criterion verbatim | ✓ |
| Empty string when not deprecated | Avoids `None` checks, but contradicts D-17 and makes "unset" indistinguishable from a data error | |
| A single nullable pair field | One optional `(disposition, replaced_by)` — needs unpacking properties anyway since the SPEC names both accessors | |

**User's choice:** `str | None`, `None` when not deprecated

### Q3 — What is `Theme.disposition` for a caller-constructed `Theme([...])`?

| Option | Description | Selected |
|--------|-------------|----------|
| `None`, keyword-only optional | The exact D-16/D-17 pattern; `str \| None` on `Theme`, `str` on `ThemeRecord` | ✓ |
| Default to `"library-only"` | Asserts a fate nobody recorded; breaks the "`None` means no identity" invariant | |
| Required argument on `Theme` | Breaks `Theme([...])` — forbidden by the SPEC's additive constraint | |

**User's choice:** `None`, keyword-only optional

### Q4 — How far should the three new generator validations be tested?

| Option | Description | Selected |
|--------|-------------|----------|
| One failing-record test per rule | Three targeted tests asserting the controlled abort, matching how the Phase 6 validations are already tested | ✓ |
| Plus a whole-file invariant test | Also pin 9 / 19 / 138 against the real data file — count pinning D-23 declined | |
| Rely on the CI regeneration diff | Cheapest, but a bad record aborts rather than producing a diff, so the failure mode is untested | |

**User's choice:** One failing-record test per rule

---

## Docs page shape

### Q1 — Where should the taxonomy + v1.2 migration content live?

| Option | Description | Selected |
|--------|-------------|----------|
| New `migration/theme-taxonomy-v1.2.md` | Follows the existing `Migration:` nav section holding `effect-api-changes.md`; leaves Phase 9's DOCS-03 a clean home | ✓ |
| New `user-guide/theme-taxonomy.md` | Alongside the 400-line cookbook; risks overlapping Phase 9 | |
| Section inside `api/themes.md` | Smallest change, but that is a mkdocstrings reference page | |

**User's choice:** New `migration/theme-taxonomy-v1.2.md`

### Q2 — How should the category counts and tables be produced?

| Option | Description | Selected |
|--------|-------------|----------|
| Hand-written, CI-checked | Markdown tables plus a test asserting the counts match the runtime API | |
| Hand-written, no check | Just write it — Phase 6 proved this page class goes stale | |
| Generated at build time | Never stale, but adds a docs build dependency and a second generator | |
| **Other (user-authored)** | **Hand-written, no check, but stamped "As of migration" — the values may change over time and the migration docs will deliberately not be updated to reflect current status** | ✓ |

**User's choice:** Free text — "Just add 'As of migration' as a indication the values may
change over time but the migration docs will not be updated to reflect current status"

**Notes:** This is a third position rather than a variant of the offered three. It resolves
the staleness objection by narrowing the page's claim: a dated migration record, not a live
reference. The Phase 6 inventory that was retired in `47e2864` failed because it claimed to
be current; this page will not.

### Q3 — How far should the docstring/doc correction reach?

| Option | Description | Selected |
|--------|-------------|----------|
| All 4 sites, examples switched to app names | `library.py:120` (`time`), `library.py:46` (`"seasonal"` example that will now raise), the false known-gap note at `api/themes.md:67`, and `getting-started/themes.md:30-31` | ✓ |
| Only the docstring, per SPEC literal | Minimal diff — leaves a shipped example that raises and a stale known-gap note | |
| All 4 sites, keep legacy names in examples | Documents the shim as a feature rather than a migration path | |

**User's choice:** All 4 sites, examples switched to app names

---

## Issue #201 scope

### Q1 — Where does issue #201 land?

| Option | Description | Selected |
|--------|-------------|----------|
| Defer to Phase 9 | SPEC.md is the locked contract and does not carry it; Phase 9's resync tooling needs primary enumeration anyway | ✓ |
| Fold into Phase 7 now | Add `get_available_themes(include_aliases=False)` — public API the SPEC never specified or scored | |
| Partially fold in — note only | Document the 2 alias keys on the migration page, ship no API | |

**User's choice:** Defer to Phase 9

### Q2 — Re-label the GitHub issue now, or record the decision here only?

| Option | Description | Selected |
|--------|-------------|----------|
| Record in CONTEXT.md only | The issue body says "Owner: Phase 7"; updating it is an outward-facing edit, left to the operator | ✓ |
| Update the issue now | Post a comment reassigning ownership so the tracker does not contradict the plan | |

**User's choice:** Record in CONTEXT.md only

---

## Claude's Discretion

None — every question was answered directly.

## Deferred Ideas

- Issue #201 — alias-vs-primary listing → Phase 9
- A public accessor for the legacy category map (`get_legacy_categories()`) — declined
- A whole-file invariant test pinning the 9 / 19 / 138 disposition counts — declined
- Generating the docs tables at build time — declined
- Mechanics of adding `disposition` to all 166 JSONL lines, and re-establishing THEME-04
  regeneration idempotence after the schema change — raised, left to the planner
