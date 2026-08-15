# Requirements: lifx-async — v1.2 Theme Library Update

**Defined:** 2026-08-14
**Core Value:** Commands stick, devices are found, streaming never starves control
traffic — and a theme by name looks like the theme of that name in the LIFX app.

## v1.2 Requirements

Source data: `.claude/theme-capture/themes.jsonl` — 179 themes captured from a LIFX Tile
(product 55) on 2026-08-14, of which 139 are non-sport and in scope. Method and caveats:
`.claude/theme-capture/README.md`.

### Theme Import

- [x] **THEME-01**: Caller can get any of the 139 non-sport app themes from `ThemeLibrary`
      by ASCII slug

- [x] **THEME-02**: A returned palette matches the captured app palette as an unordered
      set of HSBK values, brightness and kelvin intact — the app shuffles palette order on
      every application, so order is never compared

- [x] **THEME-03**: The 27 slugs shared between the app and the pre-v1.2 library return
      the app's palette (6 differ only by a uniform ×1.1087 brightness scale, 19 are
      genuinely redefined — `soothing` among them changes kelvin 3500 → 8000)

- [x] **THEME-04**: The theme data in `library.py` is generated from `themes.jsonl` rather
      than hand-transcribed, and regenerating reproduces the committed file exactly

### Compatibility

- [x] **COMPAT-01**: Every theme name that resolved before v1.2 still resolves after it —
      no shipped key disappears

- [x] ~~**COMPAT-02**: Each overwritten palette stays retrievable under a `*_legacy` name~~
      — **RETIRED 2026-08-14** during Phase 6 discussion. Measuring the 19 redefined
      themes showed 10 of them shift by one or two colours; only 9 change wholesale. The
      operator ruled that the app is the source of truth and the pre-v1.2 palettes stay in
      git history. No `*_legacy` keys, no Legacy category. Supersedes the milestone-kickoff
      decision "Overwrite + keep legacy aliases". COMPAT-01 is unaffected: all 57 pre-v1.2
      names still resolve

- [x] **COMPAT-03**: Renamed themes resolve under both the old library key and the new app
      slug (`aurora_borealis` / `aurora`, `forest` / `forrest`)

- [x] **COMPAT-04**: Each of the 30 orphaned library keys carries a recorded disposition —
      kept as library-only, or deprecated naming its replacement.
      **Amended 2026-08-15 post-ship** (`582f74b`, code review of PR #202): a fourth
      disposition, `renamed`, was added. The original three-value set had no way to express
      a rename, so the 2 alias keys (`forest`, `aurora_borealis`) inherited their target's
      `lifx-app` fate and the requirement shipped 28 recorded fates for 30 orphans

### Metadata

- [x] **META-01**: A theme exposes its app display name, distinct from its ASCII slug.
      **Amended 2026-08-14** (Phase 6 discussion): emoji are stripped from display names
      and categories — the app supports them, downstream consumers likely do not. 'Forrest
      🌳' ships as `Forrest`

- [x] **META-02**: A theme exposes its app category
- [x] **META-03**: Caller can list the categories, and list the themes within one
- [x] **META-04**: `ThemeLibrary.get_by_category()`'s existing hand-made taxonomy
      (`seasonal`, `hygge`, `tranquil`, `sports`, …) is reconciled with the app's 11
      categories — the old names either keep working or fail with a message naming their
      replacement.
      **Amended 2026-08-15 post-ship** (`582f74b`, code review of PR #202): all six old
      names fail with a message listing the nine real categories and naming **no**
      replacement. No old name mapped onto a single category, so every candidate
      replacement was either a minority holder or, for `seasonal`, held none of what the
      name returned. Naming one would have been a false promise about the old result set

### Fidelity

- [ ] **FIDELITY-01**: The 26 themes that returned exactly 16 colours — the protocol
      palette ceiling for both `SetTileEffect` and `SetMultiZoneEffect`, and all 10 of
      🎨 ART SERIES among them — carry a recorded determination: their true length, or a
      documented finding that no device-based method can supply it

- [ ] **FIDELITY-02**: A sampled theme applied through the library renders on hardware the
      same as that theme applied from the LIFX app

- [ ] **FIDELITY-03**: Product-invariance is spot-checked — a palette read back from a
      matrix product other than the Tile matches the Tile capture

### Tooling

- [ ] **TOOL-01**: The capture tooling ships in the repo and runs from a documented command
- [ ] **TOOL-02**: The analysis tool reports the diff between a fresh capture and the
      shipped library

- [ ] **TOOL-03**: Docs describe the resync procedure for a future app update

### Docs

- [ ] **DOCS-03**: Theme documentation lists the available themes and categories, and
      states that the pre-v1.2 palettes of redefined themes were not carried forward
      (continues v1.1's DOCS-01..02). **Amended 2026-08-14** with COMPAT-02's retirement

## Future Requirements

Tracked, not in this milestone.

- **PERS-01**: Generalise `state_file` persistence into a reusable mixin (deferred since
  2026-06-11)

- **THREAD-01 / SEED-001**: Revalidate wire behaviour over Thread/IPv6 when LIFX Thread
  firmware lands (dormant)

- **Spike 006**: Measure the impact of publishing tuning constants vs behaviour only — the
  D5-09 rule is disputed and remains an OPEN decision

## Out of Scope

| Feature | Reason |
|---------|--------|
| Sport themes — 🏆 AUSSIE RULES (19), 🏉 LEAGUE (17), 🏉 UNION (4) | Club-branded palettes with colliding slugs and no general appeal; dropping them removes 5 of the 6 slug collisions outright (user decision, 2026-08-14) |
| Calling `api.lifx.com/themes/v2` or `themes/v1/palette` | Undocumented internal endpoints, unauthenticated to us, deliberately untouched — the device stays the source of truth |
| MirrorLight (PR #194) | Complete and open; lands on its own schedule (user decision, 2026-08-14) |
| Preserving app names verbatim as keys | Emoji are poor Python identifiers and CLI arguments; display names are carried as metadata instead (META-01) |
| Changing the theme *application* path (`apply_theme`, generators, canvas) | v1.2 changes the palette data and its metadata, not how palettes reach a device |

## Traceability

Which phases cover which requirements. Mapped at roadmap creation (2026-08-14) —
see `.planning/ROADMAP.md` Phase Details. 18/18 live requirements mapped, no orphans;
COMPAT-02 retired during Phase 6 discussion (2026-08-14).

| Requirement | Phase | Status |
|-------------|-------|--------|
| THEME-01 | Phase 6 | Complete |
| THEME-02 | Phase 6 | Complete |
| THEME-03 | Phase 6 | Complete |
| THEME-04 | Phase 6 | Complete |
| COMPAT-01 | Phase 6 | Complete |
| COMPAT-02 | — | Retired 2026-08-14 |
| COMPAT-03 | Phase 6 | Complete |
| COMPAT-04 | Phase 7 | Complete |
| META-01 | Phase 6 | Complete |
| META-02 | Phase 6 | Complete |
| META-03 | Phase 7 | Complete |
| META-04 | Phase 7 | Complete |
| FIDELITY-01 | Phase 8 | Pending |
| FIDELITY-02 | Phase 8 | Pending |
| FIDELITY-03 | Phase 8 | Pending |
| TOOL-01 | Phase 9 | Pending |
| TOOL-02 | Phase 9 | Pending |
| TOOL-03 | Phase 9 | Pending |
| DOCS-03 | Phase 9 | Pending |
