# Phase 6: Generated Theme Library - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-14
**Phase:** 6-generated-theme-library
**Areas discussed:** Generated module layout, Alias mechanics, Theme identity API, Test strategy

---

## Generated module layout

| Option | Description | Selected |
|--------|-------------|----------|
| Generated data module + hand-written API | Generated DO-NOT-EDIT data module; `library.py` keeps `ThemeLibrary` hand-written | ✓ |
| One fully-generated library.py | Matches `registry.py`, which generates the class too | |
| Generated data + generated API, split files | Both files generated | |

| Option | Description | Selected |
|--------|-------------|----------|
| JSONL as captured, `data/themes.jsonl` | Move the capture verbatim | |
| Normalised JSON, `data/themes.json` | Pre-normalised single document | |
| JSONL, normalised at rest | Line-per-theme diffs, slugs and uint16 pre-resolved | ✓ |

| Option | Description | Selected |
|--------|-------------|----------|
| One manifest, three sections | `orphans`, `legacy`, `renames` in one file | |
| Three separate files | Each concern versioned independently | |
| Two: palettes file + rename map | Frozen palettes share a shape; renames differ | |
| **(free text)** | "Orphans and Legacy should just become categories in the main theme library" | ✓ |

| Option | Description | Selected |
|--------|-------------|----------|
| Format the temp, then rename | Target only ever replaced by finished, formatted output | ✓ |
| Rename, then format in place | Matches `products/generator.py` today | |

**Follow-ups:** category names `Library` / `Legacy` (plain, no emoji); renames as an
`aliases` field on the target record; pure JSONL with all data on records, no header.

**Then, free text:** *"We need to strip the emojis from the theme categories and names.
The app is designed to support them but our downstream consumers are not likely to be."*

| Option | Description | Selected |
|--------|-------------|----------|
| Title Case values, case-insensitive lookup | `Holidays`, `Art Series` | ✓ |
| Keep SHOUTING | `HOLIDAYS`, `ART SERIES` | |
| lowercase values | `holidays`, `art series` | |

| Option | Description | Selected |
|--------|-------------|----------|
| Kept in the data file, not exposed | Raw string retained for traceability | |
| Stripped at capture, gone | Shipped data holds stripped text only | ✓ |
| Kept and exposed as an extra field | Callers can request app presentation | |

| Option | Description | Selected |
|--------|-------------|----------|
| Derive slugs from the stripped name | One pipeline: strip → NFKD → ASCII → slug | ✓ |
| Derive slugs from the raw name | Independent ASCII fold | |

**Notes:** Verified before locking — 8 non-sport categories strip cleanly (`NATURE`,
`HOLIDAYS`, `ART SERIES`, `MUSIC`, `PLAY`, `SPACE`, `ARCHIVES`, `MOODS`), no name strips to
empty, and `Christmas` is the only duplicate display name.

---

## Alias mechanics

| Option | Description | Selected |
|--------|-------------|----------|
| Every key is a real entry | Flat dict, no indirection in `get()` | ✓ (after clarification) |
| Alias map resolved by `get()` | Saves 2 duplicated palettes, adds a branch | |
| Aliases as references in the data | Data expresses intent, runtime stays flat | |

| Option | Description | Selected |
|--------|-------------|----------|
| Everything resolvable | All resolvable names listed | ✓ |
| Current themes only | Hide aliases | |
| Everything, with a flag to filter | New parameter on a shipped method | |

| Option | Description | Selected |
|--------|-------------|----------|
| The target's identity | `get("forest")` reports `Forrest` / `Nature` | ✓ |
| Its own identity | Reports `Forest` / `Library` | |

| Option | Description | Selected |
|--------|-------------|----------|
| Category only, no warning | Category is the whole signal | ✓ |
| DeprecationWarning on access | Visible in test suites | |
| You decide | Planner chooses | |

**User's clarifying questions, answered mid-area:**

1. *"How many actual duplicate names?"* → **2** palettes stored twice (the rename
   aliases); separately **19** names wanted by two different palettes (the redefined
   themes). Two different counts; the first was answered before the second was asked, which
   the user rightly flagged as confusing.
2. *"How different are the 19 themes between the app and the existing entry?"* → ten shift
   by one or two colours; nine change wholesale.

**Outcome:** *"There is no `*_legacy`. There are just themes in a Legacy category."* — which
exposed that 19 legacy records would collide with 19 app records. Presented with the
severity split, the user chose **"Nothing — drop legacy entirely"**, retiring COMPAT-02.

| Option | Description | Selected |
|--------|-------------|----------|
| Propagate everywhere now | REQUIREMENTS, ROADMAP, PROJECT, SPEC all amended | ✓ |
| SPEC.md + REQUIREMENTS.md only | Fix what planner and verifier read | |
| CONTEXT.md records it, docs follow later | Fastest, leaves four documents wrong | |

| Option | Description | Selected |
|--------|-------------|----------|
| Keep all 30 orphans, unchanged | No collision; COMPAT-01 still requires them | ✓ |
| Drop them too | Breaks COMPAT-01 and every `evening` docstring | |

---

## Theme identity API

| Option | Description | Selected |
|--------|-------------|----------|
| Optional keyword args | `Theme(colors, *, slug=, name=, category=)` | ✓ |
| A ThemeInfo record on the Theme | Identity grouped in one object | |
| Read-only properties from the library | Library subclasses/wraps `Theme` | |

| Option | Description | Selected |
|--------|-------------|----------|
| `None` for both | Honest; callers handle None | ✓ |
| Empty strings | Always a str | |
| Name required, category optional | Breaking change | |

| Option | Description | Selected |
|--------|-------------|----------|
| Slug and name both | Round-trip a theme back to its key | ✓ |
| Name only | One field to keep consistent | |

| Option | Description | Selected |
|--------|-------------|----------|
| Leave equality alone | No `__eq__` today | |
| Palette equality only | `love == romance` becomes true | ✓ |
| Palette and identity | Most precise, largest new surface | |

| Option | Description | Selected |
|--------|-------------|----------|
| Unhashable, deliberately | Correct for a mutable object | ✓ |
| Hash the palette anyway | `add_color()` would change a live hash | |
| Hash it and freeze the palette | Retires `add_color()` | |

**Notes:** The hashing question was raised because defining `__eq__` sets `__hash__` to
`None` — a consequence worth deciding rather than discovering.

---

## Test strategy

**First answers:** *"We don't test the generated protocol or products, so we don't need to
test the generated themes either"*; exclude generated data from coverage; ignore coverage
for the generator; no drift check.

**Checked against the repo before accepting.** The premise held in one part and not in two:
generators *are* in `[tool.coverage.run] omit`, but `test_protocol_generator.py` and
`test_product_generator.py` exist, `test_generated.py` pins protocol facts, and only
`protocol_types.py` (not `packets.py` or `registry.py`) is coverage-omitted.

| Option | Description | Selected |
|--------|-------------|----------|
| Follow the precedent exactly | Generator omitted from coverage but still tested; API fully covered | ✓ |
| API only | No generator or data tests at all | |
| Everything | Per-theme parameterised cases over all 168 | |

| Option | Description | Selected |
|--------|-------------|----------|
| Cover generated data like any module | Data lines execute at import | |
| Exclude generated data from coverage | Alongside `protocol_types.py` | ✓ |

| Option | Description | Selected |
|--------|-------------|----------|
| Pin counts and the tricky ones | 168 names, renames, `soothing` 8000K | |
| Pin the full slug list | Any change fails until updated | |
| Nothing pinned | Data file is the only record | ✓ |

| Option | Description | Selected |
|--------|-------------|----------|
| Test asserts module matches data | Catches drift every run | |
| No drift check | Matches "convention only" exactly | ✓ |

**Correction accepted:** the `COLOR_SWEEP` framing was wrong — it was newly added upstream
in protocol.yml 0.10 and the hand-listed quirk enum silently failed to pick it up. It was
never dropped from anything.

---

## Claude's Discretion

None — every question was answered directly.

## Deferred Ideas

- Freezing theme palettes / making `Theme` immutable — rejected as too large for this phase
- A drift check between the data file and the generated module — offered, declined
- How Phase 7 signals a deprecated orphan key (COMPAT-04)
- `get_available_themes()` filtering — listing changes belong to Phase 7
