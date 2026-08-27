---
phase: 09-theme-data-contract-docs
verified: 2026-08-27T04:30:54Z
status: passed
score: 4/4 success criteria verified
behavior_unverified: 0
overrides_applied: 0
retroactive: true
retroactive_note: "Both plans and both summaries in this phase are reconstructions written after the work shipped. This verification is therefore the phase's first and only goal-backward check, performed against the shipped tree rather than against a plan that preceded execution."
---

# Phase 09: Theme Data Contract & Docs Verification Report

**Phase Goal:** The generated catalogue is produced from a validated, importable data contract, and the theme docs reflect the shipped library.
**Verified:** 2026-08-27T04:30:54Z
**Status:** passed
**Re-verification:** No — initial verification.

## Scope and honesty statement

Phase 9 was executed outside the GSD plan → execute → verify loop, as two
commits on two branches: `291e7e6` (2026-08-19, on `split/library-changes`,
merged to `main`) and `874f073` (2026-08-27, on
`chore/v1.2-closeout-v1.3-setup`). No PLAN.md preceded either. The plans and
summaries in this directory were reconstructed from those commits on 2026-08-27
and are labelled `reconstructed: true` in their frontmatter.

This verification does not treat those reconstructions as evidence of anything.
Every criterion below was checked directly against the shipped tree by executing
the command shown, at the timestamp above. Where a figure appears, it was
measured, not read out of a summary.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | The record contract lives in the library as `lifx.theme.schema` — importable and independently tested — rather than being private to the generator. | ✓ VERIFIED | `import lifx.theme.schema` succeeds and exposes all four contract functions (`canonical_palette`, `load_theme_records`, `validate_key`, `validate_records`). It ships in the wheel and is absent from `lifx.theme.__all__`, matching the `Canvas` precedent. `tests/test_theme/test_schema.py` — 6 passed — imports it directly rather than through the generator. `scripts/generate_theme_data.py:30` imports the contract rather than owning it. |
| 2 | Palettes are stored as the app reports them, as user-facing HSBK floats converted to wire values at runtime, and are not truncated to the 16-colour firmware effect limit. | ✓ VERIFIED | A stored colour is a float `HSBK` (`evening[0].hue == 34.002685546875`) that converts at runtime to `LightHsbk(hue=6190, saturation=49151, brightness=59113, kelvin=3500)` via `HSBK.to_protocol()`. `data/themes.jsonl` stores JSON numbers, not uint16. Measured over `THEMES`: 25 palettes exceed 16 colours, the longest being `independence` at 68. |
| 3 | Slug derivation is one documented rule with a single implementation, applied identically by the library and the generator. | ✓ VERIFIED | Exactly one `def derive_slug` exists across `src/lifx/` and `scripts/`. It lives in `src/lifx/theme/slug.py`, a leaf module whose only import is `re`. Both consumers reach that one definition: `src/lifx/theme/library.py:31` and `src/lifx/theme/schema.py:28`, the latter being the path the generator imports through. `tests/test_theme/test_slug.py` — 40 passed. |
| 4 | Theme documentation lists the available themes and categories, and states that the pre-v1.2 palettes of redefined themes were not carried forward. | ✓ VERIFIED | `docs/getting-started/built-in-themes.md` carries the nine categories with counts and the sentence "The redefined pre-6.4.0 palettes were not carried forward". `tests/test_theme/test_docs_catalogue.py` — 6 passed — binds the table to `ThemeLibrary` and derives every prose total from `THEMES`. The test was mutation-checked: perturbing the `Holidays` count from 15 to 14 failed two of its tests. |

**Score:** 4/4 roadmap success criteria verified.

## Requirements

| Requirement | Status | Evidence |
| --- | --- | --- |
| TOOL-04 — the importable record contract | ✓ Complete | Truth 1. |
| DOCS-03 — theme documentation lists themes and categories, and records the retirement | ✓ Complete | Truth 4. |
| TOOL-01, TOOL-02, TOOL-03 | Withdrawn 2026-08-19 | Out of scope for v1.2: the capture and analysis tooling is maintained in the separate private `lifx-theme-resync` repository. Recorded in `.planning/REQUIREMENTS.md` and the ROADMAP phase entry. |

## Whole-suite gates

| Gate | Result |
| --- | --- |
| `uv run --frozen pytest` | 3469 passed, 12 deselected |
| `uv run --frozen ruff format --check .` | 251 files already formatted |
| `uv run --frozen ruff check .` | All checks passed |
| `uv run --frozen pyright` | 0 errors, 0 warnings |
| `uv run --frozen zensical build` | No issues found |
| Generator idempotency | Regenerating `src/lifx/theme/data.py` from `data/themes.jsonl` produced a byte-identical file |

## Process deviations

**The phase was executed without plans.** This is the phase's principal
deviation and is not remediable after the fact — the record was reconstructed,
not recovered. Two consequences are recorded rather than smoothed over:

1. **No timings or token actuals exist.** Both summaries report `duration:
   unrecorded` and zero token actuals rather than estimates.
2. **There was no plan-checker, peer review, or UAT pass.** Phases 6, 7 and 8
   each went through those gates; Phase 9 did not. The compensating control is
   that every criterion above is bound to an executing test rather than to a
   reviewer's judgement, so a regression fails the suite.

**A prior Phase 9 existed under different requirements.** A complete phase named
`09-resync-tooling-docs` was executed and verified on 2026-08-17 against
TOOL-01/02/03 on the `codex/api-theme-generation` branches. Those requirements
were withdrawn on 2026-08-19 and that history was deliberately removed. It is
noted here only so the phase-number reuse is not mistaken for a lost record.

## Known open items (not blocking)

- **#198** — no changelog entry yet names every key whose palette changed in the
  resync. Deliberately left open by `291e7e6`.
- **#199** — `validate_key()` requires `str.isidentifier()`, so a digit-leading
  display name is unrepresentable. No shipped theme hits this today.
- **Phases 06–08 prose** still cites the removed `.claude/theme-capture/` paths.
  Recorded in the theme-resync split design as an accepted trade: editing it
  would falsify the record of why the shipped colours are what they are.

## Verdict

**PASSED.** All four roadmap success criteria are true of the shipped tree, each
bound to an executing test. The phase's process record is weaker than its
predecessors and this report says so plainly rather than presenting a
reconstruction as a plan.
