# Theme tags and effect modes design

Date: 2026-10-09
Status: draft, awaiting review
Scope: `data/themes.jsonl`, `src/lifx/theme/` (`schema.py`, `theme.py`,
`library.py`, `__init__.py`, generated `data.py`), `scripts/generate_theme_data.py`,
and the contract any tooling that writes `data/themes.jsonl` must meet

## Problem

A later App Mode in ThemePainter, with matching effects, is meant to let Home
Assistant apply a mood that looks and feels like the LIFX app. The app renders
each mood according to two effect modes the catalogue throws away today:

- `static_mode` decides the still image a tap paints, and whether `colors` is
  a palette or an ordered layout (a serpentine 8x8 grid for `grid_static`, a
  row of stripes for `solid_static`).
- `dynamic_mode` decides what the Dynamic toggle starts. Its absence is
  meaningful: the app then starts MORPH for `blended` and MOVE otherwise.

The app also attaches search `tags` to every mood. Neither the modes nor the
tags reach `data/themes.jsonl`, `Theme` or `ThemeLibrary`.

How the app paints and animates each mode was verified on a Ceiling and a Beam
in October 2026. This design only has to carry what that rendering model needs.
Rendering itself is a later project.

### Colour order is data, and the catalogue discards it

`schema.canonical_palette()` (D-24) sorts every palette. The generator applies
it at emit time and the catalogue resync tooling applies it before writing the
file, so all 166 committed records are sorted today. That was sound while a theme was
modelled as an unordered palette. It is not sound for the modes:

- For `grid_static`, the list is a serpentine raster: order is the image.
- For `solid_static` and `solid_loop`, order is the stripe sequence (a flag).
- The run-weighted stretch the app uses to fit any list to a light, including
  MORPH's sixteen-colour selection, groups *consecutive* equal colours, so
  order changes its result for every mode.

A sorted 64-cell Van Gogh cannot be repainted. Storing the full colour list,
already settled, therefore also means storing it in source order.

## Settled decisions

Made with the maintainer on 2026-10-08 and 2026-10-09:

1. Store both effect modes. An absent `dynamic_mode` is meaningful.
2. Store all tags, colour tags included.
3. Keep the app's `aliases` out of catalogue aliases. Catalogue aliases are
   unique compatibility slugs; the app's are shared search keywords.
4. Store the full colour list, in source order. D-24 is dropped.
5. Mode value sets are learned from the data by the generator, never
   hard-coded. A well-formed unknown value is accepted, not rejected. App Mode
   renders any `static_mode` it has no recipe for as `blended`, as the app does.
6. Records with no app source carry `static_mode: "blended"`, no
   `dynamic_mode` and no tags.
7. Discovery mirrors the category API and adds one combined filter.
8. Rendering (App Mode and its effects) is a later project.

## Design

### 1. Data contract

`data/themes.jsonl` records gain three fields beside the existing ones. Records
stay flat, whatever shape the app's own catalogue uses.

| Field | Presence | Value |
|---|---|---|
| `static_mode` | required on every record | canonical identifier |
| `dynamic_mode` | optional; absence is meaningful | canonical identifier |
| `tags` | optional; omitted when empty | list of display strings |

"Canonical identifier" is the existing `validate_key()` predicate: a non-empty,
ASCII, lowercase Python identifier that is not a keyword. No value set is
enforced, so any well-formed mode passes (decision 5).

Validation in `validate_records()`, each failure a controlled `RuntimeError`
naming the record and JSONL line, as every existing check does:

- `static_mode` missing, or failing `validate_key()`.
- `dynamic_mode` present but failing `validate_key()`. An explicit JSON `null`
  is rejected: there is exactly one way to say "absent".
- `tags` not a list; a tag that is not a non-empty ASCII `str`; a tag whose
  `derive_slug()` is empty; two tags in one record whose `derive_slug()` values
  collide. The last two keep normalised matching unambiguous.
- Tags are display text, not keys. They never join the slug and alias
  collision pass, and the same tag appears on many records.

`static_mode`, `dynamic_mode` and `tags` join `_REQUIRED_FIELDS` and
`_OPTIONAL_FIELDS` accordingly.

**Colour order.** `canonical_palette()` is removed from `schema.py`, along with
D-24. The generator emits colours in file order, and the generated module's
docstring states that order is source data. `schema.py` is documented as
internal (absent from `__all__` and the API docs), so removal needs no major
version. Existing records keep their current, sorted order until a resync
rewrites the app records in the app's order (section 4).

**Records without an app source.** The 19 `library-only` records, the 9 `deprecated` records
and the `lifx-app` records absent from the current catalogue are authored with
`static_mode: "blended"`, no `dynamic_mode` and no tags. Every one of them holds
a palette whose order carries no meaning (MORPH readbacks or hand-built
tuples), and `blended` is the only app mode that reads a list that way.

### 2. Generator (`scripts/generate_theme_data.py`)

- `ThemeRecord` gains `static_mode: StaticMode`,
  `dynamic_mode: DynamicMode | None = None` and `tags: tuple[str, ...] = ()`.
  `static_mode` has no default, so it is declared before the defaulted fields.
- The generator collects every `static_mode` and every `dynamic_mode` value
  present in the data and emits, sorted, into `data.py`:

  ```python
  StaticMode = Literal["blended", ...]
  DynamicMode = Literal["morph", ...]
  ```

  A new app value therefore flows through a resync with no hand edit.
  `StaticMode` always includes `"blended"`, the fallback rendering mode, which
  also keeps it non-empty for an empty record set.
  `DynamicMode` always includes `"morph"` and `"move"`, whether or not any
  record names them, because `resolved_dynamic_mode` can return either. This
  also keeps the `Literal` non-empty while every record still omits
  `dynamic_mode` (7.9.0's state).
- Tags are emitted sorted case-insensitively (ties broken by the exact string).
  The app's tag order is accidental, and a stable order keeps regeneration diffs
  quiet.
- Fields equal to their default (`dynamic_mode=None`, `tags=()`) are not
  emitted, matching the existing treatment of `replaced_by`.
- Rename-alias records copy their target's `static_mode`, `dynamic_mode` and
  `tags`, as they already share the target's `colors` object
  (`tags=THEMES[target].tags`, and so on).
- Emit-time defence-in-depth backstops, beside the existing ones: each mode
  passes `validate_key()`, and each tag is a non-empty ASCII `str`, before it is
  interpolated into source.

### 3. Public API

**`Theme`** (`theme.py`)

- New keyword-only constructor arguments and attributes:
  `static_mode: StaticMode | None = None`,
  `dynamic_mode: DynamicMode | None = None`,
  `tags: Iterable[str] = ()` stored as `tuple[str, ...]`.
- A library theme always carries a `static_mode`. A caller-built theme
  defaults to `None`, as `slug` and `name` do; App Mode will treat `None` as
  `blended`.
- A caller-supplied mode that fails `validate_key()` raises `ValueError`. A
  `tags` argument that is a bare `str` raises `TypeError` (it would otherwise be
  stored letter by letter).
- `theme.py` imports `StaticMode` and `DynamicMode` from `lifx.theme.data`
  under `TYPE_CHECKING` only. `data.py` already imports `Disposition` from
  `theme.py`, so a runtime import would be circular; `from __future__ import
  annotations` is already in effect.
- New read-only property `resolved_dynamic_mode -> DynamicMode`: returns
  `dynamic_mode` when set, otherwise `"morph"` when `static_mode` is
  `"blended"` or `None`, and `"move"` for any other `static_mode`. This is the
  catalogue half of the app's rule. Substituting MORPH on a light that cannot
  run MOVE depends on the device and belongs to App Mode.
- `shuffled()` keeps returning an identity-less theme, so it drops modes and
  tags too. That is correct: shuffling a grid destroys the image. The class
  docstring's note on `shuffled()` names the new fields.
- `palette_equals()` stays an unordered multiset comparison. It compares
  palettes, not layouts; an ordered comparison is `a.colors == b.colors`.

**`ThemeLibrary`** (`library.py`). Every new method excludes rename-alias
records, as `get_by_category()` does, and returns themes built by `get()`.

- `get(name)` passes `static_mode`, `dynamic_mode` and `tags` to `Theme`.
- `get_tags() -> list[str]`: every distinct tag across the library, sorted as
  the generator sorts tags.
- `get_by_tag(tag: str) -> dict[str, Theme]`: themes carrying the tag, keyed
  and sorted by slug. Matching applies `derive_slug()` to both sides, so
  `"Date night"`, `"date night"` and `"date_night"` all resolve. A non-string
  raises `ValueError`, and so does a tag that matches nothing; both messages
  list the available tags, mirroring `get_by_category()`.
- `find(*, tags: Iterable[str] = (), match: Literal["all", "any"] = "all",
  category: str | None = None, static_mode: str | None = None)
  -> dict[str, Theme]`:
  - Criteria combine with AND. `match` applies only within `tags`.
  - `tags` and `category` match by `derive_slug()`, as above. `static_mode`
    matches exactly.
  - A bare `str` for `tags` raises `TypeError`. An unknown tag, unknown
    category or unknown `static_mode` raises `ValueError` listing the valid
    values, which catches typos. An invalid `match` raises `ValueError`.
  - A valid combination that selects nothing returns `{}`.
  - No criteria returns every non-alias theme.
- The distinct-value normalisation follows `_slugs_for_category()`: the slug
  rule runs once per distinct tag or category, never once per record.

**Exports.** `StaticMode` and `DynamicMode` are re-exported from `lifx.theme`
and added to `__all__`, so Home Assistant can annotate with them. A resync that
learns a new value widens them, which is additive.

### 4. Contract for tooling that writes the catalogue

`data/themes.jsonl` is written by maintainer tooling that lives outside this
repository. This section is the contract that tooling must meet; how it meets
it is its own project.

- **One rule.** `lifx.theme.schema` stays the single implementation of the
  record contract. Tooling validates what it writes with
  `validate_records()` rather than re-implementing the checks.
- **Version.** Tooling that targets the new fields requires
  `lifx-async>=7.9.0`. Tooling that called `canonical_palette()` must stop
  before it can take 7.9.0, because the function is removed.
- **Fields from the LIFX app.** For each app record: `static_mode` and
  `dynamic_mode` as the app's catalogue gives them (the latter only when
  present), and `tags` as the app's display strings, reduced to ASCII with
  decoration stripped in the same way as display names. The app's own aliases
  are not written to `aliases`.
- **Colour order.** Colours are written in the app's order, never sorted.
- **Records the app does not supply.** Non-app records, and app records absent
  from the current app catalogue, carry through unchanged. From 7.9.0 they
  already hold `static_mode: "blended"`.
- **Review.** `static_mode`, `dynamic_mode`, `tags` and colour order are facts a
  resync compares and reports; an order-only change is a real change. Rename
  detection can keep comparing unordered colour multisets, so a reordered
  palette still identifies its predecessor.

**Out of scope, flagged for the next resync review:**

- 61 `lifx-app` records (60 in Archives, one in Moods) are absent from the
  current app catalogue. Whether they become `deprecated` is a separate
  disposition review.
- Whether the app's Worldly category enters the catalogue is a separate
  decision.

### 5. Compatibility and release

Releases are cut by semantic-release on merge to `main`, so this lands as two
releases, each consistent on its own:

1. **7.9.0** (`feat(themes)`): sections 1 to 3, plus a one-off data migration
   setting `static_mode: "blended"` on all 166 records. While every palette is
   still sorted, `blended` is the only correct mode for every record, so the
   release is truthful rather than provisional.
2. **A following data release**: the first resync on 7.9.0 rewrites the app
   records present in the app catalogue in the app's order, with their real modes and
   tags.

For callers:

- Additive. `get()`, `get_by_category()`, `get_available_themes()`,
  `get_categories()`, `get_theme()` and every `apply_theme()` keep their
  signatures and behaviour.
- A library theme's `colors` order changes in the second release. Order is
  documented as meaningless today, and `palette_equals()` is unaffected.
- Rendering does not change. The theme generators and `apply_theme()` already
  shuffle. `effects/rule_trio.py` takes distinct colours in palette order; its
  comment citing the D-24 sort is updated, and its behaviour needs no change
  because it already de-duplicates.
- Home Assistant reads the new fields after pinning `lifx-async>=7.9.0`.
  Nothing it does today breaks.
- `canonical_palette()` is removed without deprecation: `schema.py` is
  documented as internal, and its only external caller is maintainer tooling
  covered by section 4.

## Testing

CI requires 100% branch patch coverage.

- **Schema**: `static_mode` required; `dynamic_mode` optional; explicit `null`
  rejected; malformed identifiers rejected for both; tag container, type and
  ASCII checks; empty-slug and within-record slug-collision rejections; a tag
  shared across records does not trip the key-collision pass; an unknown but
  well-formed mode is accepted.
- **Generator**: `StaticMode` and `DynamicMode` learned from the data, including
  a value no fixture had before; `morph` and `move` always present in
  `DynamicMode`; colour file order preserved; tags sorted; default fields
  omitted; rename aliases copy their target's modes and tags; the new
  emit-time backstops.
- **`Theme`**: new constructor fields, mode validation, bare-`str` `tags`
  rejection, `resolved_dynamic_mode` on every branch, `shuffled()` dropping
  modes and tags.
- **`ThemeLibrary`**: `get()` passes the fields through; `get_tags()`;
  `get_by_tag()` with normalised matching, unknown tag and non-string; `find()`
  on each criterion, `all` versus `any`, bare `str`, unknown values, invalid
  `match`, empty result, no criteria, and alias exclusion.
- **Removed or replaced**: the `canonical_palette` tests in
  `tests/test_theme/test_schema.py` and `test_theme_generator.py`, and
  `test_canonical_palette_order` in `test_library.py`, replaced by a test that
  file order survives generation.
- **Docs**: the theme guide and API reference gain tags, modes, `find()` and
  `resolved_dynamic_mode`. `docs/changelog.md` is auto-generated and untouched.
