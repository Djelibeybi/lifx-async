# Requirements: lifx-async — v1.2 Theme Library Update

**Defined:** 2026-08-14
**Core Value:** Commands stick, devices are found, streaming never starves control
traffic — and a theme by name looks like the theme of that name in the LIFX app.

## v1.2 Requirements

Source data: `.claude/theme-capture/themes.jsonl` — 179 themes captured from a LIFX Tile
(product 55) on 2026-08-14, of which 139 are non-sport and in scope. Method and caveats:
`.claude/theme-capture/README.md`.

### Theme Import

- [ ] **THEME-01**: Caller can get any of the 139 non-sport app themes from `ThemeLibrary`
      by ASCII slug
- [ ] **THEME-02**: A returned palette matches the captured app palette as an unordered
      set of HSBK values, brightness and kelvin intact — the app shuffles palette order on
      every application, so order is never compared
- [ ] **THEME-03**: The 27 slugs shared between the app and the pre-v1.2 library return
      the app's palette (6 differ only by a uniform ×1.1087 brightness scale, 19 are
      genuinely redefined — `soothing` among them changes kelvin 3500 → 8000)
- [ ] **THEME-04**: The theme data in `library.py` is generated from `themes.jsonl` rather
      than hand-transcribed, and regenerating reproduces the committed file exactly

### Compatibility

- [ ] **COMPAT-01**: Every theme name that resolved before v1.2 still resolves after it —
      no shipped key disappears
- [ ] **COMPAT-02**: Each overwritten palette stays retrievable under a `*_legacy` name
- [ ] **COMPAT-03**: Renamed themes resolve under both the old library key and the new app
      slug (`aurora_borealis` / `aurora`, `forest` / `forrest`)
- [ ] **COMPAT-04**: Each of the 30 orphaned library keys carries a recorded disposition —
      kept as library-only, or deprecated naming its replacement

### Metadata

- [ ] **META-01**: A theme exposes its app display name with emoji intact, distinct from
      its ASCII slug
- [ ] **META-02**: A theme exposes its app category
- [ ] **META-03**: Caller can list the categories, and list the themes within one
- [ ] **META-04**: `ThemeLibrary.get_by_category()`'s existing hand-made taxonomy
      (`seasonal`, `hygge`, `tranquil`, `sports`, …) is reconciled with the app's 11
      categories — the old names either keep working or fail with a message naming their
      replacement

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

- [ ] **DOCS-03**: Theme documentation lists the available themes and categories and
      explains the `*_legacy` aliases (continues v1.1's DOCS-01..02)

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
see `.planning/ROADMAP.md` Phase Details. 19/19 requirements mapped, no orphans.

| Requirement | Phase | Status |
|-------------|-------|--------|
| THEME-01 | Phase 6 | Pending |
| THEME-02 | Phase 6 | Pending |
| THEME-03 | Phase 6 | Pending |
| THEME-04 | Phase 6 | Pending |
| COMPAT-01 | Phase 6 | Pending |
| COMPAT-02 | Phase 6 | Pending |
| COMPAT-03 | Phase 6 | Pending |
| COMPAT-04 | Phase 7 | Pending |
| META-01 | Phase 6 | Pending |
| META-02 | Phase 6 | Pending |
| META-03 | Phase 7 | Pending |
| META-04 | Phase 7 | Pending |
| FIDELITY-01 | Phase 8 | Pending |
| FIDELITY-02 | Phase 8 | Pending |
| FIDELITY-03 | Phase 8 | Pending |
| TOOL-01 | Phase 9 | Pending |
| TOOL-02 | Phase 9 | Pending |
| TOOL-03 | Phase 9 | Pending |
| DOCS-03 | Phase 9 | Pending |
