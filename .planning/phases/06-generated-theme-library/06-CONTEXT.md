# Phase 6: Generated Theme Library - Context

**Gathered:** 2026-08-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace the hand-written 57-key `ThemeLibrary._THEMES` table with a generated data module
built from one committed data file, carrying 168 resolvable theme names — 138 LIFX app
slugs plus the 30 pre-v1.2 keys — with emoji-stripped display names and categories
attached to each `Theme`, while every name that resolved before v1.2 still resolves.

</domain>

<spec_lock>
## Requirements (locked via SPEC.md)

**8 requirements are locked** (9 written, COMPAT-02 retired during this discussion). See
`06-SPEC.md` for full requirements, boundaries and acceptance criteria, including the
amendment block at the top recording what this discussion changed.

Downstream agents MUST read `06-SPEC.md` before planning or implementing. Requirements are
not duplicated here.

**In scope (from SPEC.md):**

- A theme generator reading one committed themes data file
- The themes data file, moved out of `.claude/theme-capture/` into a repo data directory
  outside the package, holding 168 emoji-stripped records
- A generated theme data module, with the hand-written `ThemeLibrary` API kept separate
- Theme identity on `Theme` — slug, display name, category; additive and optional
- Fixing the shared-list mutation leak: `get()` returns a `Theme` over a fresh list
- Shortening `get()`'s `KeyError` to the name plus a pointer to `get_available_themes()`

**Out of scope (from SPEC.md):**

- `get_by_category()`'s taxonomy — Phase 7 owns META-04; left untouched and working here
- Dispositions for the 30 pre-v1.2 keys (COMPAT-04) — Phase 7
- Sport themes (40 records) — milestone-level exclusion
- Hardware validation — Phase 8 (FIDELITY-01..03)
- Capture tooling and resync documentation — Phase 9 (TOOL-01..03)
- The theme application path (`apply_theme`, generators, canvas)
- Making `Theme` immutable

</spec_lock>

<decisions>
## Implementation Decisions

### Module layout

- **D-01:** `library.py` splits into a **generated data module** (DO-NOT-EDIT header, as
  `registry.py` carries) holding palettes and metadata, and a **hand-written `library.py`**
  keeping `ThemeLibrary`. The generator never touches API code. — **Reversibility:**
  reversible — internal module split; the public import path `lifx.theme.ThemeLibrary` is
  unchanged either way.
- **D-02:** The committed source is **one pure-JSONL file, normalised at rest** — one JSON
  object per theme, slugs pre-resolved, values uint16-normalised, sport dropped, christmas
  collapsed, emoji stripped. No top-level metadata block and no header record; every field
  lives on a theme record. — **Reversibility:** costly — the format is what the Phase 9
  tooling reads and writes, so changing it later touches capture, analysis and generation
  together.
- **D-03:** It lives in a **repo data directory outside the package**. The wheel ships no
  data file; the generated module is the shipped artefact.
- **D-04:** **No separate legacy manifest.** Orphans and rename aliases are records in the
  same data file. Orphans carry the category `Library`; renames are expressed as an
  `aliases` field on the target record (the `aurora` record lists `aurora_borealis`).
  — **Reversibility:** reversible — a second input could be reintroduced without touching
  the public API.
- **D-05:** The generator **formats the temp file, then renames**: emit → `ruff format` /
  `ruff check --fix` on the temp → atomic rename over the target. `products/generator.py`
  formats after writing in place; this ordering is deliberately stricter so the committed
  file is only ever replaced by finished, formatted output, satisfying SPEC's "an
  interrupted run leaves the module unchanged".

### Naming and metadata

- **D-06:** **Emoji are stripped from theme names and categories.** The app is designed to
  display them; downstream consumers of a Python library are not. 'Forrest 🌳' ships as
  `Forrest`; '🎉 HOLIDAYS' as `Holidays`. — **Reversibility:** one-way — display names and
  categories are public API values; restoring emoji later changes what every caller's
  output, logs and docs render, and `get_by_category()` arguments alongside them.
- **D-07:** Categories are stored **Title Case** with **case-insensitive lookup** —
  `Holidays`, `Art Series`, `Library` — matching how `get()` already lowercases its input.
- **D-08:** The **raw app string is not retained** in the shipped data file. It remains
  available in the committed capture (`.claude/theme-capture/themes.jsonl`, commit
  `b9ff729`), so the stripping rule can be re-derived; it is simply not carried forward.
- **D-09:** **Slugs derive from the stripped name** — strip emoji → NFKD → ASCII →
  lowercase → underscore. One pipeline, stated once, rather than two rules that happen to
  agree.
- **D-10:** The 8 app categories ship as `Moods`, `Art Series`, `Music`, `Nature`, `Space`,
  `Play`, `Holidays`, `Archives`; the 30 pre-v1.2 keys with no app counterpart carry
  `Library`.

### Legacy and aliases

- **D-11:** **No `*_legacy` keys and no Legacy category — COMPAT-02 is retired.**
  Measurement drove this: of the 19 redefined themes, ten shift by one or two colours and
  nine change wholesale. Preserving all 19 would have cost 19 name collisions (app
  `soothing` vs pre-v1.2 `soothing`) and a second addressing scheme, for a benefit the
  operator judged absent. The pre-v1.2 palettes stay in git history. — **Reversibility:**
  one-way — once released, callers depend on `soothing` meaning the app palette;
  reintroducing the old values later needs a new naming scheme and a migration note.
- **D-12:** **All 30 pre-v1.2 orphan keys are kept unchanged**, including `evening` and
  `autumn` which appear in docstrings across the codebase. Phase 7 decides their long-term
  disposition (COMPAT-04).
- **D-13:** **Every key is a real entry in a flat dict** — 168 names, no alias indirection
  in `get()`. Only 2 palettes are stored twice (the rename aliases), and the pre-v1.2
  library already stores `love` and `romance` as identical palettes under two keys, so
  duplication is an existing norm rather than a new cost.
- **D-14:** **Rename aliases carry the target's identity.** `get("forest")` reports display
  name `Forrest` and category `Nature` — it *is* that theme, reached by its old name.
- **D-15:** `get_available_themes()` returns **everything resolvable** — all 168 sorted
  names. The list matches exactly what `get()` accepts.

### Theme identity API

- **D-16:** Identity attaches as **optional keyword-only arguments** on `Theme` —
  `Theme(colors, *, slug=None, name=None, category=None)`. Additive; positional callers
  untouched; `Theme([...])` still works. Mirrors how `fetch_wifi_info` /
  `fetch_ambient_light` were added to device state in v1.1.
- **D-17:** A caller-constructed `Theme` has **`None` for every identity field** — not
  empty strings. Callers reading identity must handle `None`.
- **D-18:** **Slug and display name are both reachable** on a Theme, so code can round-trip
  a theme back to its key without reversing the derivation.
- **D-19:** ~~`Theme.__eq__` compares **palette only** — identity is ignored, so `love` and
  `romance` (which genuinely share a palette) compare equal.~~ — **Reversibility:** costly —
  equality semantics are observable by every caller and by the test suite. **SUPERSEDED by
  D-19a** during PR #196 review, before the behaviour ever shipped.
- **D-20:** ~~`Theme` becomes **deliberately unhashable**: defining `__eq__` sets `__hash__`
  to `None`, and that is the correct outcome for a mutable object whose palette can change
  via `add_color()`.~~ **SUPERSEDED by D-20a.**
- **D-19a:** Palette comparison is the named method **`Theme.palette_equals(other)`**, not
  `__eq__`. Semantics are otherwise as D-19 described: unordered multiset over `HSBK` at
  uint16 granularity, duplicates counted, identity ignored. It takes a `Theme` and raises
  `TypeError` on anything else rather than returning `NotImplemented` — a named method has
  no reflected-operand protocol to feed.
- **D-20a:** `Theme` **stays hashable** — `__eq__` is left at identity, so `__hash__` is
  inherited from `object`. D-20 traded hashability for an `==` nobody had asked for: it
  would have made a previously usable object unhashable (breaking any caller putting Themes
  in a set or dict key), which is a breaking change to a mutable object mid-milestone, and
  it silently redefines `==` for every existing caller. Keeping identity `==` holds 6.3.0 to
  a feature release with no BREAKING CHANGE footer. Do **not** hand-write a `__hash__` over
  the colour tuple: the palette is mutable via `add_color()`, so a value hash would not be
  stable.

### Testing

- **D-21:** **Follow the protocol/products precedent exactly**, which the discussion
  verified against the repo rather than assuming: the generator goes in
  `[tool.coverage.run] omit` (as `protocol/generator.py` and `products/generator.py`
  already are) **but still gets a test file** (as `test_protocol_generator.py` and
  `test_product_generator.py` already are). The hand-written `ThemeLibrary` / `Theme`
  changes are fully covered — they carry real new branches (identity defaults, the copy
  fix, the shortened `KeyError`) and CI requires 100% branch patch coverage.
- **D-22:** The **generated data module is excluded from coverage**, alongside
  `protocol_types.py`.
- **D-23:** **Nothing is pinned** in tests — no literal slug list, no count assertions, no
  drift check between the data file and the generated module. The data file is the record
  of what should exist. Consequence accepted: a short or stale regeneration ships silently.

### Amendment — 2026-08-14 (plan review convergence)

Recorded during `/gsd-plan-phase --reviews` after cross-AI review surfaced that palette
order, treated as meaningless by the plans, is consumed positionally by `EffectRuleTrio`
(`rule_trio.py` takes `colors[:3]`) and `EffectSpin` (`spin.py` uses `colors[0]`).
Escalated to the operator, who chose canonical sorting.

- **D-24:** **Canonical palette ordering.** The generator sorts every palette by its
  normalised `(hue, saturation, brightness, kelvin)` tuple, preserving duplicates, before
  emitting it. Rationale: the app shuffles palette order on every application, so captured
  order is an accident, not data. THEME-02 compares palettes as an unordered multiset and
  sorting preserves the multiset exactly, so the requirement is unaffected. The decisive
  consequence: `exciting`'s captured order `271°, 294°, 239°, 0°, 60°, 40°, 122°` sorts to
  `0°, 40°, 60°, 122°, 239°, 271°, 294°` — identical to the current `library.py:107`
  order — so positional consumers keep working and future re-captures become order-stable
  instead of capture-accident-dependent. Accepted cost: stored order no longer mirrors the
  app's own display order for any theme. — **Reversibility:** costly — order is observable
  through the two positional effect sites once released; changing the sort key later
  changes their visible output.

### Claude's Discretion

None — every question in this discussion was answered directly.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Locked requirements

- `.planning/phases/06-generated-theme-library/06-SPEC.md` — Locked requirements, MUST
  read before planning. Note the amendment block at the top: COMPAT-02 retired, emoji
  stripped, one generator input.

### Source data and its caveats

- `.claude/theme-capture/README.md` — how the capture was taken and its four caveats:
  palette order is meaningless, 16 is the protocol ceiling, slug collisions, single
  product. Also the record of why the LIFX theme endpoints were not called.
- `.claude/theme-capture/themes.jsonl` — the 179-record raw capture, emoji intact. Source
  for the new data file and the only place the original app strings survive.
- `.claude/theme-capture/picker-order.txt` — picker contents in order, including the 11
  category headings.
- `.claude/theme-capture/tools/analyse_themes.py` — diffs a capture against the shipped
  library. Run it with `uv run --frozen python` — it imports `lifx`.

### Existing code this phase changes

- `src/lifx/theme/library.py` — the 560-line hand-written table and the `ThemeLibrary` API.
- `src/lifx/theme/theme.py` — the `Theme` class that gains identity.
- `src/lifx/theme/__init__.py` — the export surface; note the deliberate `Canvas` comment
  explaining what is and is not advertised.

### Generator precedent to follow

- `src/lifx/products/generator.py` — closest precedent: emits Python, then runs
  `ruff format` and `ruff check --fix` over the output. Its `format_generated_files()`
  docstring explains why an unformatted regeneration shows as a spurious diff.
- `src/lifx/products/registry.py` — the DO-NOT-EDIT header format for generated modules.
- `tests/test_products/test_product_generator.py`, `tests/test_protocol/test_generated.py`
  — what testing a generator and its output looks like in this repo.
- `pyproject.toml` `[tool.coverage.run] omit` — the existing generator exclusions D-21 and
  D-22 extend.

### Project constraints

- `CLAUDE.md` — HSBK dual formats (float user-facing vs uint16 protocol), the rule that
  user-visible fields are never bytes, and the theme-layer overview.
- `.planning/codebase/CONVENTIONS.md` — naming, module design, type annotations.
- `.planning/codebase/TESTING.md` — fixtures, markers, coverage expectations.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- `products/generator.py::format_generated_files()` — runs ruff over emitted files and
  raises on failure. Directly reusable; D-05 only changes *when* it runs (on the temp file,
  before the rename).
- `products/registry.py` header — the DO-NOT-EDIT / provenance comment block to copy.
- `HSBK` already defines `__eq__`/`__hash__` with uint16 semantics, so palette comparison
  at protocol precision needs no new comparison code.
- `tests/test_theme/conftest.py` (154 lines) — existing theme fixtures.

### Established Patterns

- Generated modules carry a DO-NOT-EDIT header naming their source and generator, and are
  regenerated by `uv run python -m lifx.<pkg>.generator`.
- Generators are omitted from coverage but still have test files.
- `ThemeLibrary.get()` lowercases its input; case-insensitive lookup is the house style and
  D-07's category lookup follows it.
- Keyword-only optional fields with defaults are how v1.1 added state fields without
  breaking existing constructors (`fetch_wifi_info`, `fetch_ambient_light`).

### Integration Points

- `ThemeLibrary.get()` / `get_theme()` — the resolution path all 168 names flow through.
  Carries the live mutation bug this phase fixes.
- `get_by_category()` — reads `_THEMES` today. It must keep working against the new data
  module unchanged; Phase 7 replaces it.
- `MatrixLight.apply_theme()` and the three generators consume `Theme.colors` — untouched,
  but they are why `Theme` must stay constructible and iterable exactly as it is.
- `lifx.theme.__all__` — the advertised surface. Any new public name needs a deliberate
  decision about whether it joins the list.

### Measured facts established during discussion

These were computed from the capture and the shipped library, not assumed:

- 138 distinct slugs from 139 non-sport records — `christmas` is the only duplicate.
- No display name strips to an empty slug; `Christmas` is the only duplicate display name.
- 8 non-sport categories: Moods 13, Art Series 10, Music 14, Nature 8, Space 11, Play 7,
  Holidays 15, Archives 61.
- 27 slugs shared with the pre-v1.2 library: 2 identical, 6 brightness-scaled by ×1.1087
  (= 255/230), 19 genuinely redefined.
- Of the 19: ten shift by one or two colours; nine change wholesale (`tranquil`, `zombie`
  share nothing with their old palettes; `hanukkah` 5→2, `spacey` 4→2, `earth` and
  `independence` 3→16, `coral_reef` 3500K→9000K, `halloween` loses 5 of 6, `stardust` 4).
- 25 in-scope themes sit at exactly 16 colours, including all 10 of Art Series.
- Three app themes share one identical palette: `Memorial Day`, `Independence`,
  `Old Glory`.
- The pre-v1.2 library already stores `love` and `romance` as identical palettes.
- Neither `aurora_borealis` nor `forest` exists independently in the app set.
- **Live bug:** `ThemeLibrary.get()` returns a `Theme` sharing the library's own list —
  `get("evening")` → `add_color()` → next `get("evening")` yields 4 colours where the
  library defines 3.

</code_context>

<specifics>
## Specific Ideas

- "The app is designed to support them but our downstream consumers are not likely to be"
  — the reasoning behind stripping emoji (D-06). It applies to categories as much as names.
- "There is no `*_legacy`. There are just themes in a Legacy category. They resolve like
  all other themes" — the intermediate position that exposed the 19-way name collision and
  led to retiring COMPAT-02 outright (D-11).
- "We don't test the generated protocol or products, so we don't need to test the generated
  themes either" — the intent behind D-21. Checked against the repo: the coverage omission
  is real, the absence of tests is not, so D-21 follows the precedent as it actually is.
- The `christmas` twin drop is recorded in phase docs only — nothing in the running code
  mentions it (SPEC edge row, META-02).

</specifics>

<deferred>
## Deferred Ideas

- **Freezing theme palettes / making `Theme` immutable** — considered while deciding
  equality and hashing (D-19, D-20). Rejected for this phase: it retires `add_color()` and
  reaches every consumer of `Theme`. Worth revisiting if `Theme` ever needs to be hashable.
- **A drift check between the data file and the generated module** — offered and declined
  (D-23). If a future resync ships short, this is the mechanism that would have caught it.
- **Deprecation warnings on superseded themes** — moot now that legacy is retired, but the
  question of how Phase 7 signals a deprecated orphan key (COMPAT-04) is still open.
- **`get_available_themes()` filtering** — a parameter to narrow the listing was offered
  and not taken; listing changes belong to Phase 7.

</deferred>

---

*Phase: 6-Generated Theme Library*
*Context gathered: 2026-08-14*
