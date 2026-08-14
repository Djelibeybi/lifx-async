# Roadmap: lifx-async

## Milestones

- ✅ **v1.0 Ceiling Save-on-Exit** — Phase 1 (shipped 2026-06-12) — [archive](milestones/v1.0-ROADMAP.md)
- ✅ **Post-v1.0: Discovery unification** — Phase 1 (verified 2026-06-13) — archived in `milestones/v1.1-phases/01-unify-duplicated-discovery-loops/`
- ✅ **v1.1 Wire Reliability** — Phases 2–5 (shipped 2026-07-26) — [archive](milestones/v1.1-ROADMAP.md)
- 🚧 **v1.2 Theme Library Update** — Phases 6–9 (in progress, started 2026-08-14)

## Phases

<details>
<summary>✅ v1.0 Ceiling Save-on-Exit (Phase 1) — SHIPPED 2026-06-12</summary>

- [x] Phase 1: Ceiling Save-on-Exit (1/1 plans) — completed 2026-06-12

Full details: [milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md)

</details>

<details>
<summary>✅ Post-v1.0: Phase 1 — Unify duplicated discovery loops (verified 2026-06-13)</summary>

Standalone phase from the /simplify review (2026-06-13). Rebuilt `discover_devices()`
on `_discover_with_packet()` with hoisted DoS serial validation and first-wins per-serial
dedup; retired `_parse_device_state_service()`. Review-fix 6/6, security 11/11 closed,
UAT 4/4 including real-hardware validation (regression 0d83deb found and fixed).
5/5 plans complete. Phase directory archived in
`milestones/v1.1-phases/01-unify-duplicated-discovery-loops/`.

</details>

<details>
<summary>✅ v1.1 Wire Reliability (Phases 2–5) — SHIPPED 2026-07-26</summary>

Closed the measured reliability gap against the reference clients (Glowup, Photons) using
the spike-validated blueprints, without changing the asyncio core or the public API.

- [x] Phase 2: Discovery Re-broadcast (2/2 plans) — completed 2026-07-16
- [x] Phase 3: Retry Schedule Reshape (3/3 plans) — completed 2026-07-17
- [x] Phase 4: Animation Flow Control (13/13 plans) — completed 2026-07-17
- [x] Phase 5: Reliability Documentation (6/6 plans) — completed 2026-07-18

13/13 requirements satisfied · 25/25 must-have truths verified · 7/7 cross-phase
connections wired · all four phases Nyquist-compliant.

Full details: [milestones/v1.1-ROADMAP.md](milestones/v1.1-ROADMAP.md) ·
audit: [milestones/v1.1-MILESTONE-AUDIT.md](milestones/v1.1-MILESTONE-AUDIT.md)

</details>

### 🚧 v1.2 Theme Library Update (Phases 6–9) — IN PROGRESS

Resync `lifx.theme.library` with the LIFX app's live theme set — 139 non-sport themes
captured from hardware on 2026-08-14 (`.claude/theme-capture/`) — without silently
changing colours existing callers depend on. Every phase is bound by the project-wide
gates: zero runtime dependencies, Python 3.10–3.14, pyright strict clean, ruff clean,
pytest green, 100% branch patch coverage in CI, Australian English in prose and comments.
Theme names are public API — a key may gain values or an alias; it may never silently
vanish, in any intermediate state.

- [x] **Phase 6: Generated Theme Library** - The 138 non-sport app theme slugs land with app-accurate palettes and emoji-stripped metadata, generated from a committed data file, with every pre-v1.2 name still resolving (completed 2026-08-15)
- [ ] **Phase 7: Taxonomy & Legacy Dispositions** - Callers navigate the library by the app's category taxonomy; every legacy category name and orphaned key has a recorded, working fate
- [ ] **Phase 8: Hardware Fidelity Validation** - Shipped palettes render as the app renders them, on more than the capture product, and the 16-colour question carries an evidenced determination either way
- [ ] **Phase 9: Resync Tooling & Docs** - A future app update is resynced by documented procedure; theme docs reflect the new library

## Phase Details

### Phase 6: Generated Theme Library

**Goal**: Every non-sport app theme resolves by ASCII slug with app-accurate colours and app metadata, generated from the capture, and no name that resolved before v1.2 breaks
**Depends on**: Nothing within v1.2 (first phase; builds on the shipped v1.1 library)
**Requirements**: THEME-01, THEME-02, THEME-03, THEME-04, COMPAT-01, COMPAT-03, META-01, META-02
(COMPAT-02 retired 2026-08-14 — see below)
**Success Criteria** (what must be TRUE):

  1. Any of the 138 non-sport app theme slugs is retrievable from `ThemeLibrary`, and its palette matches the captured app palette as an unordered multiset of HSBK values with brightness and kelvin intact
  2. The 25 differing shared slugs return the app's palette (the 6 brightness-scaled and 19 genuinely redefined among them, `soothing`'s kelvin 3500 → 8000 included)
  3. Every theme name that resolved before v1.2 still resolves, and the renamed themes resolve under both the old key and the new app slug (`aurora_borealis`/`aurora`, `forest`/`forrest`)
  4. A retrieved theme exposes its display name and category — both emoji-stripped, both distinct from its ASCII slug
  5. Regenerating the theme data module from the committed data file reproduces it exactly (verified by hand, convention only)

**Plans:** 2/2 plans complete

Plans:
**Wave 1**

- [x] 06-01-PLAN.md — Tracer: seed data file → generator → generated data module → `ThemeLibrary.get()` with identity, plus `Theme` equality and generator tests

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 06-02-PLAN.md — Full 166-record data file, library cutover to the generated dict, and the compatibility/metadata acceptance tests

One phase by necessity, not appetite: the generator's first real output *is* the import,
and "no key silently vanishes" binds every intermediate state, so splitting the import
from the compatibility guarantees would mandate a broken midpoint. Plan ordering inside
the phase runs data model → generator → generated output, satisfying THEME-04's
foundational position. Palette comparison is always unordered-multiset — the app shuffles
palette order on every application. `christmas` appears twice with identical palettes and
collapses to the HOLIDAYS record.

**Amended 2026-08-14 (Phase 6 discussion, `06-CONTEXT.md`):** COMPAT-02 is retired — no
`*_legacy` keys and no Legacy category. Measurement showed 10 of the 19 redefined themes
shift by only one or two colours; the operator ruled the app is the source of truth and
the pre-v1.2 palettes stay in git history. Emoji are stripped from display names and
categories. The generator takes **one** committed input (a normalised JSONL of 168
records: 138 app themes plus the 30 pre-v1.2 keys, 2 of which are rename aliases), not a
data file plus a separate legacy manifest.

### Phase 7: Taxonomy & Legacy Dispositions

**Goal**: Callers can navigate the library by the app's category taxonomy, and every legacy category name and orphaned key has a recorded, working fate
**Depends on**: Phase 6
**Requirements**: META-03, META-04, COMPAT-04
**Success Criteria** (what must be TRUE):

  1. Caller can list the app's categories and list the themes within any one of them
  2. Every category name `get_by_category()` accepted before v1.2 (`seasonal`, `hygge`, `tranquil`, `sports`, …) either still returns themes or fails with a message naming its replacement
  3. Each of the 30 orphaned library keys carries a recorded disposition — kept as library-only, or deprecated naming its replacement — and a deprecated key still resolves

**Plans**: TBD

COMPAT-04 is a per-key judgement over a small fixed set, not a code change: the renames
were already wired in Phase 6, so this phase records keep-or-deprecate decisions for the
remainder and encodes only the messaging those decisions require. Sport categories are out
of scope, so the old `sports` taxonomy name resolves to a message, not to themes.

### Phase 8: Hardware Fidelity Validation

**Goal**: The shipped palettes are demonstrated to render as the app renders them, on more than the capture product, and the 16-colour question has an evidenced answer either way
**Depends on**: Phase 6 (validates the shipped palette data; independent of Phase 7)
**Requirements**: FIDELITY-01, FIDELITY-02, FIDELITY-03
**Success Criteria** (what must be TRUE):

  1. A sampled theme applied through the library renders on hardware the same as the identical theme applied from the LIFX app
  2. A palette read back from a matrix product other than the Tile matches the Tile capture as an unordered HSBK set
  3. Each of the 26 exactly-16-colour themes carries a committed determination: a true length established from a non-device source, or an evidenced finding that it cannot be established from a device

**Plans**: TBD

Hardware phase — runs against the 73-device production fleet and the quiesced gen2/3/4
test devices; a LIFX Tile is product 55, so FIDELITY-03 needs a different matrix product
(e.g. Candle or Ceiling). These checks cannot run in CI: they are UAT-style evidence,
while emulator-backed tests must independently reach 100% branch patch coverage.
FIDELITY-01 is an investigation, not a recovery job: 16 is the protocol palette ceiling
for both `SetTileEffect` and `SetMultiZoneEffect`, so no device readback can ever return
more — a recorded, evidenced "cannot be determined from a device" is a complete,
successful outcome.

### Phase 9: Resync Tooling & Docs

**Goal**: A future app update can be resynced by documented procedure rather than re-derived, and the theme docs reflect the new library
**Depends on**: Phase 7 (documents the taxonomy) and Phase 8 (the FIDELITY-01 determination reaches the docs)
**Requirements**: TOOL-01, TOOL-02, TOOL-03, DOCS-03
**Success Criteria** (what must be TRUE):

  1. The capture tooling (`enumerate_themes.py`, `sweep_themes.py`, `analyse_themes.py`) ships in the repo and each tool runs from a documented command
  2. The analysis tool, run against a fresh capture, reports the diff against the shipped library — new, changed and orphaned themes
  3. Docs describe the end-to-end resync procedure for a future app update: capture, analyse, regenerate, review
  4. Theme documentation lists the available themes and categories, and states that the pre-v1.2 palettes of redefined themes were not carried forward (amended 2026-08-14 with COMPAT-02's retirement)

**Plans**: TBD

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Ceiling Save-on-Exit | v1.0 | 1/1 | Complete | 2026-06-12 |
| 1. Unify duplicated discovery loops | post-v1.0 | 5/5 | Complete | 2026-06-13 |
| 2. Discovery Re-broadcast | v1.1 | 2/2 | Complete | 2026-07-16 |
| 3. Retry Schedule Reshape | v1.1 | 3/3 | Complete | 2026-07-17 |
| 4. Animation Flow Control | v1.1 | 13/13 | Complete | 2026-07-17 |
| 5. Reliability Documentation | v1.1 | 6/6 | Complete | 2026-07-18 |
| 6. Generated Theme Library | v1.2 | 2/2 | Complete    | 2026-08-15 |
| 7. Taxonomy & Legacy Dispositions | v1.2 | 0/TBD | Not started | - |
| 8. Hardware Fidelity Validation | v1.2 | 0/TBD | Not started | - |
| 9. Resync Tooling & Docs | v1.2 | 0/TBD | Not started | - |
