# Implementation Plan: Docs IA Restructure

**Track ID:** docs-ia-restructure_20260319
**Spec:** [spec.md](./spec.md)
**Created:** 2026-03-19
**Status:** [~] In Progress

## Overview

Restructure docs in four phases: consolidate Effects (the largest duplication), deduplicate Themes and Animation, relocate misplaced content, then fix cross-links and navigation. Each phase ends with `uv run mkdocs build` to catch broken links immediately.

---

## Phase 1: Effects Consolidation

The biggest IA win: Effects content is scattered across 6+ files. Establish `user-guide/effects.md` as the canonical guide.

### Tasks

- [x] Task 1.1: Move `getting-started/effects.md` (906 lines) to `user-guide/effects.md` — this becomes the canonical effects guide; update internal links within the moved file to reflect its new directory (`../api/` → `../api/`, `../` → `../` relative paths will change)
- [x] Task 1.2: Create new `getting-started/effects.md` (~100 lines) — brief intro with "Your First Effect" example (pulse), link to `user-guide/effects.md` for full guide, link to `getting-started/effects-gallery.md` for visual overview
- [x] Task 1.3: Move `getting-started/effects-gallery.md` to `user-guide/effects-gallery.md` — its effect descriptions duplicate `effects.md`; move any unique gallery assets (GIF references) into the new `user-guide/effects.md` as an appendix section or keep the gallery but move it to user-guide
- [x] Task 1.4: Update `api/effects.md` (720 lines) — add "See also" link to `user-guide/effects.md` at the top; remove any duplicated explanatory prose that exists in both; keep all method/parameter reference content
- [x] Task 1.5: Link `migration/effect-api-changes.md` from `api/effects.md` and `user-guide/effects.md` — add a "Migration" or "Breaking Changes" note at the top of each
- [x] Task 1.6: Verify Phase 1 — run `uv run mkdocs build` and check for broken links or warnings

### Verification

- [x] `uv run mkdocs build` completes with no errors
- [x] `getting-started/effects.md` is under 150 lines
- [x] `user-guide/effects.md` exists and contains the full effects guide

---

## Phase 2: Themes & Animation Deduplication

Fix the remaining content duplication in Themes and Animation sections.

### Tasks

- [x] Task 2.1: Trim `getting-started/themes.md` — keep only "Apply a Theme" (code example) and "Next Steps" links (~40 lines total); remove the full categories list and "Create a Custom Theme" section (these are already in `user-guide/themes.md`)
- [x] Task 2.2: Add "See also" links to `user-guide/themes.md` — ensure it links to `getting-started/themes.md` (intro), `api/themes.md` (reference), and `api/colors.md` (HSBK details)
- [x] Task 2.3: Trim `api/animation.md` — remove duplicated prose guide (which is identical to `user-guide/animation.md`); replace with a brief overview paragraph, a "See [Animation Guide](../user-guide/animation.md) for usage" link, and keep only the Performance Characteristics table and any API-specific reference content
- [x] Task 2.4: Add "See also" links to `user-guide/animation.md` — link to `api/animation.md` for API reference at the bottom
- [x] Task 2.5: Verify Phase 2 — run `uv run mkdocs build` and check for broken links

### Verification

- [x] `uv run mkdocs build` completes with no errors
- [x] `getting-started/themes.md` is under 50 lines (38 lines)
- [x] `api/animation.md` is significantly shorter than `user-guide/animation.md` (156 vs 373)

---

## Phase 3: Content Relocation

Move misplaced content to correct sections and fix troubleshooting cross-links.

### Tasks

- [ ] Task 3.1: Move `user-guide/protocol-deep-dive.md` → `architecture/protocol-deep-dive.md` — update all internal links within the file; add cross-link from `api/protocol.md` to the deep dive
- [ ] Task 3.2: Add cross-link from `user-guide/troubleshooting.md` to `user-guide/effects-troubleshooting.md` — add an "Effects Troubleshooting" entry in the troubleshooting guide's table or "See Also" section
- [ ] Task 3.3: Add cross-links to orphaned API pages — add links to `api/network.md` from `user-guide/advanced-usage.md` and `api/index.md`; add links to `api/high-level.md` from `getting-started/quickstart.md`; add links to `api/colors.md` from `getting-started/quickstart.md` and `user-guide/themes.md`
- [ ] Task 3.4: Verify Phase 3 — run `uv run mkdocs build` and check for broken links

### Verification

- [ ] `uv run mkdocs build` completes with no errors
- [ ] `architecture/protocol-deep-dive.md` exists
- [ ] `user-guide/protocol-deep-dive.md` is deleted

---

## Phase 4: Navigation & Progressive Disclosure

Update mkdocs.yml nav and add "Learn more" links connecting the tiers.

### Tasks

- [ ] Task 4.1: Update `mkdocs.yml` nav — restructure to: Getting Started (Installation, Quick Start), User Guide (Effects, Effects Gallery, Custom Effects, Themes, Animation, Ceiling Lights, Advanced Usage, Troubleshooting, Effects Troubleshooting), Architecture (Overview, Effects System, Protocol Deep Dive), API Reference (unchanged), Migration, FAQ, Changelog
- [ ] Task 4.2: Add progressive disclosure links — at the bottom of each Getting Started page, add "Next: [User Guide topic]" links; at the bottom of each User Guide page, add "API Reference: [relevant API page]" links where missing
- [ ] Task 4.3: Update `docs/index.md` — ensure the landing page links reflect the new nav structure (e.g., remove "Effects Gallery" from Getting Started if moved)
- [ ] Task 4.4: Run benchmarks and save as `docs-ia-restructure_20260319-final`: `uv run pytest tests/benchmarks/ -m benchmark --no-cov --benchmark-save=docs-ia-restructure_20260319-final`
- [ ] Task 4.5: Final verification — run `uv run mkdocs build`, `uv run --frozen pytest`, spot-check key pages in `uv run mkdocs serve`

### Verification

- [ ] `uv run mkdocs build` completes with no errors or broken link warnings
- [ ] `uv run --frozen pytest` — full test suite passes (docs changes should not affect tests)
- [ ] Nav structure in browser matches the intended hierarchy
- [ ] All Getting Started pages are under 200 lines

---

## Final Verification

- [ ] All acceptance criteria in spec.md met
- [ ] `uv run mkdocs build` — clean build, no warnings
- [ ] `uv run --frozen pytest` — all tests pass
- [ ] No orphaned pages (every docs page has at least one inbound link)
- [ ] Progressive disclosure: Getting Started → User Guide → API Reference pathway exists for Effects, Themes, Animation
- [ ] Ready for review

---

_Generated by Conductor. Tasks will be marked [~] in progress and [x] complete._
