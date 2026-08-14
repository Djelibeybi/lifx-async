# Phase 6: Generated Theme Library — Specification

**Created:** 2026-08-14
**Ambiguity score:** 0.125 (gate: ≤ 0.20)
**Requirements:** 9 locked

## Goal

`lifx.theme.library` stops being a 57-key hand-written table transcribed from photons and
becomes a generated module carrying the LIFX app's 138 non-sport theme slugs at
uint16-exact app palettes, with app display names and categories attached, while every
theme name that resolved before v1.2 still resolves.

## Background

**What exists today** (verified against the working tree, 2026-08-14):

- `ThemeLibrary._THEMES` is a hand-written dict of **57** keys in
  `src/lifx/theme/library.py` (560 lines). Its palettes were transcribed from photons
  years ago and never resynced.
- `ThemeLibrary` exposes `get()`, `get_available_themes()` and `get_by_category()`.
  `get()` lowercases the name and raises `KeyError` listing **every** available theme.
  `get_by_category()` carries a hand-made taxonomy (`seasonal`, `hygge`, `tranquil`,
  `sports`, …) unrelated to the app's; `sports` is both a category name and a theme key.
- `Theme` (`src/lifx/theme/theme.py`) holds **only** `colors: list[HSBK]`. It has no name,
  no identity, no category. META-01/META-02 have nowhere to live today.
- **Live bug, verified:** `ThemeLibrary.get()` returns `Theme(cls._THEMES[name])`, sharing
  the library's own list. `get("evening")` → `add_color(...)` → re-`get("evening")`
  returns 4 colours where the library defines 3. The library is corrupted for the rest of
  the process.
- Two generated-module precedents exist in-repo: `protocol/generator.py` → `packets.py`,
  and `products/generator.py` → `registry.py`. Neither is gate-checked for regeneration
  drift.

**The capture** (`.claude/theme-capture/`, 2026-08-14): 179 themes across 11 categories,
read back from a LIFX Tile (product 55) after applying each theme as MORPH from the app.
Dropping 🏆 AUSSIE RULES (19), 🏉 LEAGUE (17) and 🏉 UNION (4) leaves **139 records**,
which yield **138 distinct slugs** — `christmas` appears twice with identical palettes.

**The delta**, from a live run of `analyse_themes.py`: 27 slugs shared with the library
(2 identical, 25 differing — 6 by a uniform ×1.1087 brightness scale, 19 genuinely
redefined), 146 app themes absent from the library, 30 library keys with no app
counterpart (including `evening` and `autumn`, both used in docstrings across the
codebase).

**What does not exist yet:** the generator, the committed themes data file, the legacy
manifest, theme identity on `Theme`, and every one of the 146 new palettes.

## Requirements

1. **App themes by slug** (THEME-01): Every non-sport app theme resolves from
   `ThemeLibrary` by a deterministic ASCII slug.
   - Current: 57 hand-written keys; none of the 146 new app themes resolve
   - Target: 138 slugs from the 139 non-sport records, derived by NFKD-normalising the
     app display name, stripping non-ASCII, lowercasing and underscore-joining. Every
     slug is a valid Python identifier, unique across the whole library, and stable
     across regenerations
   - Acceptance: `ThemeLibrary.get(slug)` returns a `Theme` for all 138 slugs;
     `str.isidentifier()` is true for every key in `get_available_themes()`; a fixture
     display name that strips to an empty slug, and one that duplicates an existing slug,
     each abort generation with an error naming the offending display name

2. **Palettes match the app** (THEME-02): A shipped palette equals the captured palette as
   an unordered multiset, compared at protocol precision.
   - Current: shared palettes differ from the app; the capture carries uint16
     quantisation artefacts (`0.8699931334401465`, `338.0`)
   - Target: the generator normalises every captured value through the protocol's uint16
     encoding, and emits that normalised value. Duplicate colours within a palette are
     preserved exactly — 'Independence 🇺🇸' keeps all 4 of its identical
     `(0, 0, 1.0, 6500)` entries out of 16
   - Acceptance: for all 138 slugs, `sorted(shipped_palette) == sorted(uint16_normalised
     (captured_palette))` including repeats; no test compares palette order

3. **Shared slugs resynced** (THEME-03): The 25 differing shared slugs return app values.
   - Current: all 27 shared slugs return pre-v1.2 palettes
   - Target: the 25 differing slugs return the app palette, the 6 brightness-scaled among
     them included; `soothing` returns kelvin 8000, not 3500. The 2 already-identical
     slugs are unchanged
   - Acceptance: each of the 25 differing slugs matches its captured palette per THEME-02
     and does **not** equal its pre-v1.2 palette; `soothing`'s kelvin is 8000

4. **Generated, not transcribed** (THEME-04): `library.py`'s theme data is emitted by a
   generator from committed inputs.
   - Current: 500+ lines of hand-written `HSBK(...)` literals; no theme generator exists
   - Target: a generator reads a committed themes data file (repo data directory, outside
     the package — the package ships no data file) plus a committed legacy manifest, and
     emits `library.py`'s theme data. It writes atomically: emit to a temp file, rename
     over the target, so an interrupted or concurrent run never leaves a half-written
     `library.py`. Palette order in the emitted file is deterministic and documented as
     carrying no meaning
   - Acceptance: re-running the generator over unchanged inputs leaves `git status`
     clean. **Verified once by hand during this phase — not gate-checked**, matching how
     `packets.py` and `registry.py` are already handled. Consequence accepted: nothing
     detects later drift between the data file and `library.py`

5. **No key disappears** (COMPAT-01): Every pre-v1.2 theme name still resolves.
   - Current: 57 keys resolve, 30 of which have no app counterpart
   - Target: all 57 still resolve after the resync, in every intermediate state of the
     phase — the 30 orphans are carried by the legacy manifest
   - Acceptance: a test parameterised over the full pre-v1.2 key list (captured as a
     literal fixture, not read from the new library) resolves every one without raising

6. **Legacy palettes survive** (COMPAT-02): Each genuinely redefined theme keeps its old
   palette reachable.
   - Current: no aliases exist; overwriting would lose the old values to git history
   - Target: the 19 genuinely redefined themes each gain a `<slug>_legacy` key holding
     the pre-v1.2 palette. The 6 brightness-scaled themes get **no** legacy alias — the
     ×1.1087 factor is 1/0.902 = 255/230, so they are the same palette at a different
     level, not a changed theme
   - Acceptance: all 19 `*_legacy` keys resolve and each equals its pre-v1.2 palette
     exactly; no `*_legacy` key exists for any of the 6 brightness-scaled slugs; the
     ×1.1087 relationship holds for all 6 within uint16 precision

7. **Renames resolve both ways** (COMPAT-03): Renamed themes answer to both names.
   - Current: `aurora_borealis` and `forest` exist; the app spells them 'Aurora 🌌' and
     'Forrest 🌳'
   - Target: `aurora_borealis` and `aurora` return the same palette; `forest` and
     `forrest` return the same palette. Verified today: neither old key exists
     independently in the app set, so no conflict arises
   - Acceptance: for each rename pair, both keys resolve and their palettes are equal as
     multisets

8. **Display name on the theme** (META-01): A library theme knows its app name.
   - Current: `Theme` has no name attribute of any kind
   - Target: `Theme` gains theme identity; a theme from the library exposes its app
     display name with emoji intact ('Forrest 🌳'), distinct from its slug (`forrest`).
     The addition is additive — `Theme([...])` constructed by a caller with no name keeps
     working unchanged
   - Acceptance: `ThemeLibrary.get("forrest")` exposes display name 'Forrest 🌳';
     constructing `Theme([HSBK(...)])` directly succeeds and its existing behaviour
     (iteration, indexing, `add_color`) is unchanged

9. **Category on the theme** (META-02): A library theme knows its app category.
   - Current: no category data exists on `Theme`; `get_by_category()`'s taxonomy is
     hand-made and unrelated to the app's
   - Target: a theme from the library exposes the app category it came from. `christmas`
     resolves to the 🎉 HOLIDAYS record; the byte-identical 🗄️ ARCHIVES twin is dropped
   - Acceptance: `ThemeLibrary.get("christmas")` exposes category 🎉 HOLIDAYS; every one
     of the 138 slugs exposes a category drawn from the app's 8 in-scope categories

## Boundaries

**In scope:**

- A theme generator reading a committed themes data file plus a committed legacy manifest
- The themes data file, moved out of `.claude/theme-capture/` into a repo data directory
  outside the package
- The legacy manifest: the 30 orphaned palettes, the 19 `*_legacy` snapshots, and the
  rename map
- Regenerated `library.py` carrying 138 app slugs + 30 orphans + 19 legacy aliases
- Theme identity on `Theme` — display name and category, additive and optional
- Fixing the shared-list mutation leak: `get()` returns a `Theme` over a fresh list
- Shortening `get()`'s `KeyError` to the name plus a pointer to `get_available_themes()`

**Out of scope:**

- `get_by_category()`'s taxonomy — Phase 7 owns META-04; in Phase 6 it is left untouched
  and working, returning its current groupings over resynced palettes
- Dispositions for the 30 orphaned keys (COMPAT-04) — Phase 7; Phase 6 only guarantees
  they keep resolving
- Sport themes (40 records) — milestone-level exclusion
- Hardware validation of the shipped palettes — Phase 8 (FIDELITY-01..03)
- Shipping the capture tooling and the resync documentation — Phase 9 (TOOL-01..03)
- The theme *application* path (`apply_theme`, generators, canvas) — v1.2 changes palette
  data and its metadata, not how palettes reach a device
- Making `Theme` immutable — considered and rejected as a larger blast radius than the
  leak fix requires

## Constraints

- Zero new runtime dependencies; Python 3.10–3.14
- `uv run pyright` (strict) clean, `uv run ruff check`/`format` clean, `uv run pytest`
  green; CI requires **100% branch** patch coverage
- Theme names are public API: a key may gain values or an alias, never silently vanish —
  this binds every intermediate state, not just the phase's end state
- The package ships no data file; `library.py` is the shipped artefact
- Palette comparison is always unordered — the app shuffles order on every application
- 16 is the protocol palette ceiling; 25 in-scope themes sit exactly at it and may be
  clipped. Phase 6 ships what was captured and does not attempt recovery (Phase 8 owns
  the determination)
- Australian English in prose and comments

## Acceptance Criteria

- [ ] All 138 non-sport app slugs resolve via `ThemeLibrary.get()`
- [ ] Every key in `get_available_themes()` satisfies `str.isidentifier()`
- [ ] Every shipped app palette equals its captured palette as a uint16-normalised
      multiset, duplicates included
- [ ] `soothing` returns kelvin 8000; the other 24 differing shared slugs match the app
      and differ from their pre-v1.2 values
- [ ] All 57 pre-v1.2 keys still resolve, checked against a literal fixture list
- [ ] All 19 `*_legacy` keys resolve and equal their pre-v1.2 palettes exactly
- [ ] No `*_legacy` key exists for any of the 6 brightness-scaled slugs
- [ ] `aurora_borealis`/`aurora` and `forest`/`forrest` each return equal palettes
- [ ] `ThemeLibrary.get("forrest")` exposes display name 'Forrest 🌳'
- [ ] `ThemeLibrary.get("christmas")` exposes category 🎉 HOLIDAYS
- [ ] `Theme([HSBK(...)])` with no name still constructs and behaves as before
- [ ] `get()` returns a fresh list: mutating a returned `Theme` does not change what the
      next `get()` of the same slug returns
- [ ] A display name that strips to an empty slug aborts generation, naming it
- [ ] A duplicate slug aborts generation, naming both display names
- [ ] The generator writes atomically — an interrupted run leaves `library.py` unchanged
- [ ] Re-running the generator over unchanged inputs leaves `git status` clean (manual,
      once)
- [ ] `get_by_category()` still returns themes for its existing category names
- [ ] MUST NOT ship a palette value that no capture record supports
- [ ] MUST NOT reference the undocumented LIFX theme endpoints from shipped code, and
      regeneration MUST NOT require a network or a device
- [ ] MUST NOT claim fidelity beyond what was measured — one product, order lost, 16-colour
      ceiling

## Edge Coverage

**Coverage:** 22/22 applicable edges resolved · 0 unresolved

| Category | Requirement | Status | Resolution / Reason |
|----------|-------------|--------|---------------------|
| encoding | THEME-01 | ✅ covered | NFKD → strip non-ASCII → lowercase → underscore. Empty-after-strip aborts generation naming the display name |
| adjacency | THEME-01 | ✅ covered | Duplicate slug aborts generation naming both display names. Verified: only `christmas` collides today, and it collapses to the 🎉 HOLIDAYS record |
| empty | THEME-01 | ✅ covered | Unknown slug raises `KeyError` with the name and a pointer to `get_available_themes()` — the full 188-name list is dropped |
| ordering | THEME-01 | ✅ covered | `get_available_themes()` stays sorted by slug |
| adjacency | THEME-02 | ✅ covered | Duplicate colours preserved exactly as a multiset |
| empty | THEME-02 | ✅ covered | No captured palette is empty (minimum observed: 2 colours); a zero-colour record aborts generation |
| ordering | THEME-02 | ✅ covered | Emitted palette order is deterministic and documented as meaningless; never compared |
| unclassified | THEME-03 | ✅ covered | Reviewed manually: the 2 already-identical shared slugs get no legacy alias and no diff — only the 25 differing slugs change |
| concurrency | THEME-04 | ✅ covered | Atomic write (temp + rename); an interrupted or concurrent run leaves the committed file untouched |
| adjacency | COMPAT-01 | ✅ covered | An app slug colliding with a carried-forward orphan: app wins, orphan dropped **loudly**. Verified zero live instances |
| empty | COMPAT-01 | ✅ covered | Pre-v1.2 key list captured as a literal fixture so an empty/incorrect derivation cannot vacuously pass |
| encoding | COMPAT-01 | ✅ covered | Pre-v1.2 keys are already ASCII lowercase; `get()` keeps lowercasing its input |
| ordering | COMPAT-01 | ✅ covered | Resolution is by key, order-independent |
| adjacency | COMPAT-02 | ✅ covered | A `*_legacy` slug colliding with a real app slug: app wins, legacy dropped loudly. Verified zero live instances |
| empty | COMPAT-02 | ✅ covered | Exactly 19 legacy keys expected; count asserted, so a silently empty legacy layer fails |
| encoding | COMPAT-02 | ✅ covered | `_legacy` suffix on an already-ASCII slug; no normalisation involved |
| ordering | COMPAT-02 | ✅ covered | Legacy palettes compared as multisets like every other palette |
| empty | COMPAT-03 | ✅ covered | Rename map has 2 entries; both asserted. A missing entry fails COMPAT-01 as well |
| encoding | COMPAT-03 | ✅ covered | Verified: neither `aurora_borealis` nor `forest` exists independently in the app set, so no conflict |
| empty | META-01 | ✅ covered | `Theme` with no name is the caller-constructed case and must keep working |
| encoding | META-01 | ✅ covered | Display names stored as Python `str` with emoji intact; only the slug is ASCII-folded |
| unclassified | META-02 | ✅ covered | Reviewed manually: `christmas` keeps the 🎉 HOLIDAYS record; the identical 🗄️ ARCHIVES twin is dropped, recorded in phase docs only |

## Prohibitions (must-NOT)

**Coverage:** 3/3 applicable prohibitions resolved · 0 unresolved

| Prohibition (must-NOT statement) | Requirement | Status | Verification / Reason |
|----------------------------------|-------------|--------|------------------------|
| MUST NOT present palette values no capture record supports — no invented themes, no interpolated colours, no "tidied" palettes | THEME-02, THEME-04 | resolved | verification: judgment |
| MUST NOT reference the undocumented LIFX theme endpoints (`api.lifx.com/themes/v2`, `themes/v1/palette`) from shipped code; regeneration MUST NOT require a network or a device | THEME-04 | resolved | verification: judgment |
| MUST NOT claim more fidelity than was measured — a single product (Tile, 55), palette order lost to shuffling, palettes capped at the protocol's 16 colours | META-01, META-02 | resolved | verification: judgment |

## Ambiguity Report

| Dimension          | Score | Min  | Status | Notes                                                        |
|--------------------|-------|------|--------|--------------------------------------------------------------|
| Goal Clarity       | 0.90  | 0.75 | ✓      | Data home, precision rule and metadata home all locked        |
| Boundary Clarity   | 0.88  | 0.70 | ✓      | Phase 6/7 seam settled: `get_by_category()` untouched here    |
| Constraint Clarity | 0.85  | 0.65 | ✓      | uint16-exact comparison is the load-bearing constraint        |
| Acceptance Criteria| 0.85  | 0.70 | ✓      | THEME-04's check is manual and one-off by explicit choice     |
| **Ambiguity**      | 0.125 | ≤0.20| ✓      | Gate passed after round 3                                     |

Status: ✓ = met minimum, ⚠ = below minimum (planner treats as assumption)

## Interview Log

| Round | Perspective | Question summary | Decision locked |
|-------|-------------|------------------|-----------------|
| 1 | Researcher | Where does `themes.jsonl` live once shipped? | Repo data directory outside the package; the wheel ships no data file |
| 1 | Researcher | What does "palette matches the app" mean numerically? | Normalise through the protocol's uint16 encoding; compare exactly on those values |
| 1 | Researcher | Where does theme identity live — `Theme` has no name? | On the `Theme` object, additively |
| 2 | Researcher | Does COMPAT-02 cover all 25 differing themes or only the 19 redefined? | Only the 19 redefined; the 6 brightness-scaled are the same palette at a different level |
| 2 | Simplifier | How is "regeneration reproduces the file" enforced? | Convention only — matches `packets.py`/`registry.py`. Verified once by hand; drift goes undetected |
| 2 | Simplifier | Where do the orphans and legacy snapshots come from? | A committed legacy manifest as a second generator input |
| 3 | Boundary Keeper | `christmas` appears twice with identical palettes | Keep the 🎉 HOLIDAYS record; drop the 🗄️ ARCHIVES twin |
| 3 | Boundary Keeper | What does Phase 6 do with `get_by_category()`? | Leave it untouched and working; Phase 7 owns META-04 |
| 3 | Boundary Keeper | What must a slug guarantee? | Unique, stable, valid Python identifier; collisions fail the generator loudly |
| Edge | Failure Analyst | Empty or colliding slug derivation | Abort generation, naming the offending display name(s) |
| Edge | Failure Analyst | Duplicate colours within a palette | Preserve exactly — multiset, not set |
| Edge | Failure Analyst | Legacy vs app slug collision | App wins, legacy dropped. Verified zero live instances; drop must be loud |
| Edge | Failure Analyst | Shared-list mutation leak in `get()` | Fix it — return a `Theme` over a fresh list |
| Edge | Failure Analyst | `KeyError` listing ~188 themes | Name only plus a pointer to `get_available_themes()` |
| Edge | Failure Analyst | Ordering guarantees | Deterministic emitted order, documented as meaningless; listing stays sorted |
| Edge | Failure Analyst | Generator interrupted mid-write | Atomic write: temp file plus rename |
| Edge | Failure Analyst | Where is the dropped `christmas` twin recorded? | Phase docs only |
| Prohibition | Boundary Keeper | Three must-NOTs surfaced (invention, endpoint callout, overclaiming) | All kept at judgment tier |

---

*Phase: 06-generated-theme-library*
*Spec created: 2026-08-14*
*Next step: /gsd-discuss-phase 6 — implementation decisions (how to build what's specified above)*
