---
phase: 7
reviewers: [codex, opencode, antigravity]
reviewed_at: 2026-08-15T01:54:59Z
plans_reviewed: [07-01-PLAN.md, 07-02-PLAN.md, 07-03-PLAN.md]
---

# Cross-AI Plan Review — Phase 7: Taxonomy & Legacy Dispositions

## Consensus Summary

All three reviewers independently confirmed the plans' core measurements against the
live repo (166 records / 138 app / 28 Library, the two aliases, both mkdocs nav sites,
the four stale doc sites) and all three rate the *design* sound. They diverge sharply on
execution risk: Codex says MEDIUM-HIGH on 07-01 and MEDIUM on 07-02; OpenCode and
Antigravity both say LOW overall.

Two of the divergences were adjudicated against source during synthesis and **resolve in
Codex's favour** — see "Divergent Views". Both are worth a targeted revision before
execution.

### Agreed Strengths

- **Counts are ground truth, SPEC's "140" is the typo.** Codex and OpenCode both
  independently re-counted `data/themes.jsonl` and confirmed 166/138/28 and the nine
  category totals. Both credit the plan for surfacing the discrepancy rather than
  hunting for two phantom records.
- **Alias emission order preserved → R7 identity holds.** All three reviewers flagged
  `scripts/generate_theme_data.py:469-482` as the load-bearing pass and credit the plan's
  explicit "do NOT touch" instruction.
- **Additive schema keeps backward compatibility and identity semantics.** All three note
  the keyword-only-optional pattern at `src/lifx/theme/theme.py:64-71` is the established
  one, `palette_equals()` reads only `colors`, and `Theme` stays hashable with identity `==`.
- **`derive_slug` centralisation removes real duplication** (OpenCode, Antigravity) — though
  Codex disputes the chosen location; see below.
- **Point-in-time migration-doc framing is the right contract** (Codex, OpenCode), avoiding
  the Phase 6 stale-inventory failure mode.
- **No count-pinning in committed tests**, honouring D-08/D-23 (OpenCode, Codex).

### Agreed Concerns

- **MEDIUM — The generator does not reject `replaced_by` on a non-deprecated record.**
  Raised by Codex (MEDIUM) and OpenCode (LOW). The defence is split: three generator
  validations plus a library-side shape sweep at test time. Per D-08 this was a deliberate
  scope lock, but both reviewers note the *schema* remains capable of emitting a
  `lifx-app` record carrying a replacement. Codex adds that the emit-time backstop is
  weaker still — it checks `replaced_by` is canonical but not that it resolves, and
  `emit_data_module()` is directly callable from tests.
- **MEDIUM — `_LEGACY_CATEGORIES` key-form is an undocumented constraint.** OpenCode: the
  lookup probes the dict with a `derive_slug`-normalised key, so a future non-slug-form
  key silently falls through to the unknown-category error. Antigravity independently
  suggests a test asserting every `resolves=True` replacement names a category that
  actually exists in the generated data. One comment line plus one test closes both.
- **LOW — Before/After framing in the migration page misleads.** Codex and OpenCode both
  note `holiday` and `mood` still resolve after v1.2, so a Before/After contrast implies
  removal that did not happen. What changed is the *result set*, not the call's validity.
- **LOW — `get_by_category()` rescans every record per call.** Codex frames it as duplicated
  comprehension logic across the current and legacy paths (wants a private helper);
  OpenCode frames it as 168 `derive_slug` regex subs per invocation (suggests precomputing
  a `_category_slug` or caching). Both call it non-blocking.

### Divergent Views

1. **Generator branch coverage — Codex HIGH vs OpenCode "gate respected". ADJUDICATED: Codex is right.**
   `pyproject.toml:112-113` runs `--cov=generate_theme_data --cov-branch`, and the
   `[tool.coverage.run] omit` list excludes only `src/lifx/theme/data.py`, with an explicit
   comment that the generator "is hand-written and stays measured, so the emit-time
   backstops keep their patch-coverage requirement." `07-01-PLAN.md:305` states the
   opposite — "(scripts/ is excluded from coverage per D-21)" — and its verify command
   measures `--cov=lifx.theme`, which never measures the generator at all. The upstream
   record is also stale: `STATE.md:90` records D-21 as excluding the generator, which
   current `pyproject.toml` contradicts.
   **Impact:** the new validation and emit-time branches are likely to miss the 100%
   branch-patch gate in CI. Codex names the specific untested paths: non-string
   `disposition`; empty and non-string `replaced_by`; present-but-non-canonical
   `replaced_by` (distinct from unresolved-but-canonical); invalid emit-time `disposition`;
   invalid emit-time `replaced_by`. It recommends extending the existing parametrised
   backstop matrix at `tests/test_theme/test_theme_generator.py:558-580` rather than
   starting a disconnected pattern.

2. **Where `derive_slug` should live — Codex MEDIUM vs OpenCode "consistent". ADJUDICATED: Codex's mechanism is real.**
   `src/lifx/theme/__init__.py:40` imports `ThemeLibrary`, and `library.py:27` imports the
   generated `lifx.theme.data`. So `from lifx.theme.slug import derive_slug` executes the
   package `__init__` and pulls in the generated module. The generator currently imports
   only `lifx.color`, `lifx.const` and `lifx.protocol.protocol_types` — none of which reach
   `lifx.theme` — so today it has no dependency on its own output. The relocation would
   introduce one: regenerating `data.py` would require importing `data.py`.
   OpenCode is correct that this passes in CI (a valid `data.py` is always committed) and
   that both import spellings resolve; the disagreement is about *recovery*, not steady
   state. Codex's options: put the helper outside the package init path (e.g.
   `lifx._theme_slug`), make `lifx.theme.__init__` lazy, or add a test proving regeneration
   works with `data.py` absent.

3. **Overall risk rating.** Codex MEDIUM-HIGH (07-01) / MEDIUM (07-02) / LOW-MEDIUM (07-03);
   OpenCode LOW with "confidence in the plans as written: high"; Antigravity LOW. The gap
   is almost entirely explained by the two adjudicated items above — OpenCode's LOW rests
   on the coverage gate being satisfied, which the source contradicts.

### Reviewer-specific findings not corroborated

- **Antigravity — `ensure_ascii` on the JSONL rewrite (LOW).** The throwaway migration
  script uses `json.dumps(obj, separators=(", ", ": "))`; without `ensure_ascii=False`,
  any surviving non-ASCII character becomes a `\uXXXX` escape and drifts the file. OpenCode
  separately verified the current separators reproduce existing lines byte-for-byte, so this
  is latent rather than active — cheap to pin regardless.
- **OpenCode — old test assertions must be explicitly deleted, not shadowed (MEDIUM).**
  `tests/test_theme/test_library.py:211` asserts the American `"not recognized"`;
  `test_category_case_insensitive` uses `"SEASONAL"`, which will now raise; and
  `test_all_categories_have_themes` (`:354-367`) asserts all six legacy names return themes,
  four of which will raise. The rewritten class must remove these, and the plan's behaviour
  block does not name them for deletion.
- **OpenCode — stale `shuffled()` docstring (MEDIUM).** `theme.py:31-34` says "slug, name and
  category do not propagate"; `disposition` and `replaced_by` will not propagate either.
- **Codex — the no-network grep is brittle (LOW).** It matches string patterns with several
  attribution exceptions rather than asserting on imports; an AST or import assertion would
  be clearer.
- **Codex — "always will within v1.x" is a new compatibility promise (MEDIUM).** The locked
  requirement says deprecated keys keep resolving and removal is a v2 decision; the docs task
  would turn that into an externally visible support guarantee. Should be tied to the
  versioning policy or reworded.
- **Codex — doc verification is substring-based (LOW).** Checking each name appears does not
  prove it sits in the right table with the right fate and replacement; a swapped successor
  would pass.

---

## Codex Review

# Cross-AI Plan Review

## Overall assessment

The phase is well decomposed and closely aligned with the locked specification. The repository confirms the principal measurements: `data/themes.jsonl` contains 166 records, comprising 138 non-`Library` records and 28 `Library` records, with the expected nine category totals and two rename aliases. The main weakness is Plan 07-01’s incomplete treatment of branch coverage: the generator is explicitly coverage-measured, but several proposed validation and emit-time branches lack tests. Plan 07-02 also introduces a regeneration bootstrapping dependency by placing `derive_slug()` beneath a package whose `__init__` imports the generated module.

Current measured category counts:

| Category | Records |
|---|---:|
| Archives | 60 |
| Art Series | 10 |
| Holidays | 15 |
| Library | 28 |
| Moods | 13 |
| Music | 14 |
| Nature | 8 |
| Play | 7 |
| Space | 11 |
| Total | 166 |

The aliases are `aurora_borealis → aurora` and `forest → forrest`, present on `data/themes.jsonl:3` and `data/themes.jsonl:50`.

---

## Plan 07-01 — Disposition schema end-to-end

### Summary

The data-to-public-object tracer is sound: the plan correctly changes the JSONL schema, validates it, regenerates rather than hand-edits `data.py`, extends `ThemeRecord` and `Theme`, and threads the metadata through `ThemeLibrary.get()`. Its locked 9/19/138 split agrees with the live data. However, its test instructions do not exercise every proposed generator branch, despite the generator being explicitly measured with branch coverage.

### Strengths

- The plan correctly recognises the specification’s `140 app records` statement as a typo. The live data has 166 records, of which 28 have category `Library`, leaving 138 app records. The current category distribution is also documented in `.planning/phases/07-taxonomy-legacy-dispositions/07-SPEC.md:18-21`.

- It preserves the generated-file boundary. The generator identifies `data/themes.jsonl` as its source and `src/lifx/theme/data.py` as its output at `scripts/generate_theme_data.py:35-42`; CI regenerates and diffs that file at `.github/workflows/ci.yml:129-146`.

- The proposed cross-record validation is placed correctly after the main loop. The existing `seen_keys` table contains both primary slugs and aliases because they are inserted together at `scripts/generate_theme_data.py:313-335`. Consequently, checking `replaced_by in seen_keys` genuinely permits alias targets as specified.

- The emission field order is valid for a dataclass: required `disposition` precedes `colors`, while defaulted `replaced_by` comes last. The current generated layout is assembled at `scripts/generate_theme_data.py:432-440`.

- Alias identity should remain intact if the plan leaves the final alias pass unchanged. The generator binds each alias directly to the primary record at `scripts/generate_theme_data.py:469-481`, and current aliases are limited to the two measured JSONL entries.

- Extending `Theme` with keyword-only defaults follows the existing additive identity pattern at `src/lifx/theme/theme.py:64-71`. `Theme.palette_equals()` only reads `colors` at `src/lifx/theme/theme.py:223-260`, so the new metadata naturally remains excluded.

- The plan correctly preserves identity equality and hashability. `Theme` has no custom `__eq__` or `__hash__`, while the existing documentation explicitly defines identity semantics at `src/lifx/theme/theme.py:36-39`.

### Concerns

- **HIGH — Proposed tests do not cover all new generator branches.** The generator is not excluded from coverage: pytest explicitly uses `--cov=generate_theme_data --cov-branch` at `pyproject.toml:113-120`, and the coverage configuration says its emit-time backstops remain measured at `pyproject.toml:135-143`. Plan 07-01 incorrectly says “scripts/ is excluded from coverage per D-21.”

  Missing or insufficiently specified paths include:

  - Non-string `disposition`, distinct from an unknown string.
  - Empty and non-string `replaced_by`, depending on how the compound condition is implemented.
  - A present but non-canonical `replaced_by`, which is a separate validation branch from unresolved-but-canonical.
  - Invalid emit-time `disposition`.
  - Invalid emit-time `replaced_by`.

  Existing emit-time branches are covered deliberately through a parametrised test at `tests/test_theme/test_theme_generator.py:558-580`; the new backstops should be added to that matrix.

- **MEDIUM — The generator permits `replaced_by` on non-deprecated records.** The locked target says `replaced_by is None unless disposition == "deprecated"` at `.planning/phases/07-taxonomy-legacy-dispositions/07-SPEC.md:108-118`. The plan deliberately omits a generator rejection and checks this only against shipped data in a runtime sweep. That satisfies the current dataset but leaves the schema capable of generating a `lifx-app` or `library-only` record with a replacement.

- **MEDIUM — Emit-time validation is weaker than normal validation.** The plan’s emit backstop validates only that `replaced_by` is canonical, while the normal path also checks that it resolves. Since `emit_data_module()` is directly callable—the existing tests explicitly treat it that way at `tests/test_theme/test_theme_generator.py:570-577`—an unvalidated record can emit an unresolved successor.

- **LOW — Validation and data decisions are split across tasks in a way that can temporarily leave the suite red.** Task 1 changes `_record()` and production code, while Task 3 adds several required tests. Execution needs to treat these as one atomic plan-level change rather than expecting Task 1’s full generator verification to represent final branch coverage.

- **LOW — The no-network grep is brittle.** It searches string patterns rather than actual imports/calls and carries several attribution exceptions. The current generator already documents its local-only nature at `scripts/generate_theme_data.py:3-17`, so a focused import or AST assertion would be clearer.

### Suggestions

- Add explicit generator tests for:

  - `disposition=None`
  - `disposition="retired"`
  - `replaced_by=""`
  - `replaced_by=123`
  - `replaced_by="bad-key"`
  - `replaced_by="valid_but_missing"`
  - emit-time invalid disposition
  - emit-time invalid replacement

- Either enforce `replaced_by` absence for non-deprecated records or explicitly document that this is only a shipped-data invariant, not a schema invariant. The current plan and specification use language suggesting the stronger contract.

- Extend the existing emit-time backstop parameter table at `tests/test_theme/test_theme_generator.py:558-580` rather than creating a disconnected testing pattern.

- Correct all statements claiming the generator is coverage-excluded.

### Risk assessment

**MEDIUM-HIGH.** The implementation mechanism is sound, but the current test plan is likely to miss the project’s branch-patch coverage gate. Once the missing validation and emit-backstop cases are specified, risk drops to low-medium.

---

## Plan 07-02 — Taxonomy rewrite and shared slug rule

### Summary

The taxonomy API design matches the locked requirements and the current generated data. Deriving categories from `cls._THEMES`, normalising both operands, deduplicating aliases by primary slug, and checking current taxonomy before the legacy shim are all appropriate. The main architectural concern is that moving `derive_slug()` under `lifx.theme` makes the generator import the package’s generated data before it can regenerate that data.

### Strengths

- `cls._THEMES` is the correct source. The class attribute exists specifically so all lookup methods remain subclass-safe at `src/lifx/theme/library.py:53-57`.

- The proposed `get_categories()` implementation correctly derives only populated categories and naturally returns `[]` for an empty subclass. This matches the measured nine categories and avoids a second taxonomy source.

- The proposed set comprehension correctly deduplicates alias entries. `THEMES` contains 168 keys but only 166 records because aliases share record identity; using `record.slug` produces one result per primary theme.

- App-taxonomy-first lookup directly matches the locked order in `.planning/phases/07-taxonomy-legacy-dispositions/07-SPEC.md:66-76`.

- The proposed normalisation reproduces the current D-09 implementation exactly. The live function lowercases and collapses non-`[a-z0-9]` runs at `scripts/generate_theme_data.py:110-125`, with existing tests for spaces and punctuation at `tests/test_theme/test_theme_generator.py:169-186`.

- The legacy map matches all six locked dispositions, and its tagged tuple structure makes the replacement available for both resolving and raising paths.

- The test plan covers the important runtime branches: current category, mapped legacy category, rejected legacy category, unknown category, empty library, empty input, normalised input, and sorted output.

- Correcting the existing American `recognized` message is appropriate. The current user-facing string is at `src/lifx/theme/library.py:190-195`.

### Concerns

- **MEDIUM — Generator bootstrapping becomes dependent on generated data.** Importing `from lifx.theme.slug import derive_slug` first executes `lifx.theme.__init__`. That module imports `ThemeLibrary` at `src/lifx/theme/__init__.py:34-41`; `library.py` then imports the generated `lifx.theme.data` module at `src/lifx/theme/library.py:27`. Therefore, the generator may be unable to regenerate `data.py` if that generated file is missing, syntactically broken, or temporarily incompatible.

  This weakens the generator’s recovery properties even though normal CI, where a valid committed `data.py` exists, will pass.

- **MEDIUM — “All 168 names contain `t`” needs precise test wording.** `Theme` equality remains identity-based, so constructing a fresh `Theme` and checking membership by value cannot work. The proposed implementation test using `record.slug in result` is correct, but the plan’s truth statement should avoid suggesting object equality.

- **LOW — The implementation rescans all records twice for mapped legacy categories.** With 168 keys this is negligible, but a small private helper such as `_get_by_normalised_category()` would reduce duplicated comprehension logic and make branch testing clearer.

- **LOW — Public-surface language is slightly confused.** `get_categories()` is a classmethod, not a module-level exported symbol. The acceptance assertion that `"get_categories" not in lifx.theme.__all__` is harmless but does not validate public accessibility; `ThemeLibrary` is already exported at `src/lifx/theme/__init__.py:47-54`.

- **LOW — `derive_slug()` has no type guard for public caller input.** `get_by_category(None)` would raise `AttributeError` from `.lower()`, not the documented `ValueError`. The signature is `str`, so this is not a locked requirement, but it is worth deciding explicitly because caller input is the trust boundary.

### Suggestions

- Avoid the regeneration bootstrapping cycle. Suitable options include:

  - Put the shared helper in a lightweight module outside the `lifx.theme` package initialisation path, such as `lifx._theme_slug`.
  - Make `lifx.theme.__init__` lazy enough that importing `lifx.theme.slug` does not import `library.py` or generated data.
  - Add an explicit test that regeneration still works when `src/lifx/theme/data.py` is temporarily unavailable, if recovery-from-source is intended.

- Add a private helper for category collection so both current and mapped legacy lookups use one implementation.

- Rephrase the 168-name test as: every key’s record slug appears in the result for that record’s category.

- Consider a controlled `ValueError` for non-string category input, or document that runtime type enforcement is not part of this phase.

### Risk assessment

**MEDIUM.** Runtime taxonomy behaviour is well planned and should satisfy META-03/META-04. The principal risk is the generator’s new dependency on importing the generated artefact it is responsible for rebuilding.

---

## Plan 07-03 — Migration documentation

### Summary

The documentation plan is appropriately sequenced after the code plans, targets the actual stale sites, and correctly updates both MkDocs navigation trees. Its content matches the measured category totals and disposition tables. The main concern is one additional compatibility promise—“always will within v1.x”—that is stronger than the locked phase requirements.

### Strengths

- Both required navigation locations exist exactly where the plan says: the LLM-output navigation at `mkdocs.yml:149-150` and the main site navigation at `mkdocs.yml:223-224`.

- The existing stale API admonition is correctly identified at `docs/api/themes.md:67-72`.

- The getting-started examples currently use the old names at `docs/getting-started/themes.md:29-31`, so replacing them with `Holidays` and `Moods` is source-grounded.

- The category counts proposed for the migration page exactly match the live JSONL.

- The plan explicitly distinguishes eight app categories from the synthetic `Library` category, matching the existing code’s attribution at `src/lifx/theme/library.py:14-22` and the specification at `.planning/phases/07-taxonomy-legacy-dispositions/07-SPEC.md:18-21`.

- The point-in-time framing is a good fit for a migration document and avoids reintroducing the stale-live-inventory problem.

- Running the “After” examples against the delivered API is a useful behavioural check rather than merely checking Markdown content.

- It respects the project prohibition against changing the generated changelog.

### Concerns

- **MEDIUM — “Always will within v1.x” creates a new compatibility guarantee.** The locked requirement says deprecated keys continue to resolve and removal would be a v2 decision, but the plan’s proposed prose is still an externally visible support promise. If that wording is intended, it should be copied directly from or explicitly approved against the project’s versioning policy, not introduced casually in a docs task.

- **LOW — Content verification is mostly substring-based.** Checking that each name occurs does not establish that it appears in the correct table, has the correct fate, or has the correct replacement. A swapped successor could pass the proposed script.

- **LOW — “No shipped doc teaches a name that raises” is broader than the verification.** The proposed grep only checks one exact phantom phrase. The current targeted search shows the relevant stale category instructions are confined to `library.py`, `docs/api/themes.md`, and `docs/getting-started/themes.md`, but the final check should search all `get_by_category(...)` examples and classify their arguments.

- **LOW — The “Before” example needs explicit historical labelling.** Since `get_by_category("holiday")` will continue to work after migration, it is not inherently wrong. The page should clarify that the semantic result changed from a hand-built mixed grouping to the complete `Holidays` category.

### Suggestions

- Replace the blanket v1.x promise with wording tied directly to the locked contract, such as: “Deprecated keys remain resolvable; disposition records migration guidance and emits no warning.”

- Add a verification mapping of every deprecated key to its exact replacement and every legacy category to its exact fate, rather than checking name presence independently.

- Extract or scan all fenced examples containing `get_by_category()` and verify that each is either executable or explicitly marked as a historical/raising example.

- Make the Before/After section explain the changed result set for `holiday` and `mood`, not merely the changed preferred spelling.

### Risk assessment

**LOW-MEDIUM.** The documentation scope and sequencing are good. Remaining risks concern claim precision rather than implementation correctness.

---

## Final recommendation

Approve the overall three-wave structure after two revisions:

1. Expand Plan 07-01’s generator tests to cover every new validation and emit-time branch, and remove the incorrect claim that the generator is excluded from coverage.
2. Reconsider where the shared slug helper lives so regeneration does not require importing the generated theme module.

With those changes, the plans should achieve the phase goals without palette changes, key removals, or taxonomy drift.

---

## OpenCode Review

All key claims verified against repo. Writing review now.

---

# Cross-AI Plan Review — Phase 7: Taxonomy & Legacy Dispositions

## Verification Status

**REVIEWED-WITH-REPO-ACCESS.** I read `data/themes.jsonl`, `scripts/generate_theme_data.py`, `src/lifx/theme/{library,theme,__init__}.py`, both test files, `mkdocs.yml`, `pyproject.toml`, both stale doc files, and `07-SPEC.md`. All counts, file:line citations, and mechanical claims checked against source.

**Verified facts:**
- `data/themes.jsonl` = 166 records; 138 non-Library, 28 Library (Counter matches plan exactly)
- The 9 deprecated replacements (gentle, fantasy, st_patrick_s_day, romance, christmas, warm_ember, pride, pumpkin_spice, candy_cane) all resolve as primary slugs in THEMES
- `json.dumps(obj, separators=(", ", ": "))` produces byte-identical lines to existing JSONL
- `mkdocs.yml` has two Migration nav sections at :149-150 (llms) and :223-224 (main)
- `docs/api/themes.md:67` carries the "older grouping" admonition; `docs/getting-started/themes.md:30-31` uses `get_by_category("holiday")`/`("mood")`
- `library.py:120` carries "seasonal, mood, holiday, time, etc"; `:46` carries the seasonal docstring example; `:193` uses American "recognized"
- SPEC R4 text says "140 app records" (should be 138) — plan correctly catches this; SPEC acceptance criterion 11 already carries a correction parenthetical
- `pyproject.toml:109` `pythonpath = ["src", "scripts"]` — generator import and test `from generate_theme_data import derive_slug` both survive the slug relocation
- `derive_slug` on all 9 category names produces the expected slugs; `sorted(cats)` matches plan's expected list; `"artseries"` → `"artseries"` (not in set, raises per SPEC R2)

---

## 1. Summary

Three tightly-scoped plans that deliver COMPAT-04 (disposition schema end-to-end), META-03/META-04 (taxonomy rewrite + legacy map), and the migration docs. The plans are unusually well-grounded: every file:line citation I checked is accurate, the disposition table is copied verbatim from the locked SPEC R4, the SPEC's internal "140 vs 138" inconsistency is surfaced and handled correctly, and the `Theme.__hash__ is None` typo (already corrected in SPEC) is explicitly declined. The wave ordering is sound (data → taxonomy → docs), the TDD discipline is real (tests written first, watched fail, then implemented), and the coverage gate is respected (all four `get_by_category` branches plus three generator abort branches get explicit tests). The main risks are cosmetic: a stale `shuffled()` note that should mention the new fields, an undocumented constraint that `_LEGACY_CATEGORIES` keys must be slug-form, and an American-spelling assertion in the existing test suite that the rewrite must explicitly delete rather than merely shadow.

## 2. Strengths

- **Disposition table copied, not re-derived.** Plan 07-01 Task 1 explicitly says "These 28 values are copied verbatim from the locked table — exercise no palette or semantic judgement of your own." I confirmed all 9 replacements resolve as primary slugs in `data/themes.jsonl`. This is the single highest-risk judgment area and the plan removes it entirely.
- **SPEC discrepancy surfaced, not papered.** The "140 vs 138" inconsistency in SPEC R4 (lines 83, 213, 264 say 140; the background table sums to 138; acceptance criterion says "exactly 19 library-only" implying 138) is caught and resolved with "Use 138. Do not hunt for 2 extra records." Correct call.
- **Additive constraint honoured.** Plan 07-01 Task 2 pins `Theme([...])` with no keywords still constructs and `.disposition is None` — the D-07 guarantee. The `Theme.__init__` at `theme.py:64-71` currently has `slug`/`name`/`category` as keyword-only optionals; adding `disposition`/`replaced_by` in the same block is the exact established pattern.
- **Alias emission order preserved.** Plan 07-01 Task 1 step 4: "Do NOT touch the alias emission pass." I verified `generate_theme_data.py:469-482` emits `THEMES[alias] = THEMES[target]` after the dict literal; the R7 identity guarantee (`THEMES["forest"] is THEMES["forrest"]`) depends on this ordering surviving the schema change.
- **One slug rule, stated once.** Plan 07-02 Task 1 relocates `derive_slug` to `src/lifx/theme/slug.py` and has the generator import it. I confirmed the generator (`scripts/generate_theme_data.py`) already imports from `lifx.*` (lines 31-33), so `from lifx.theme.slug import derive_slug` is consistent, and the test's `from generate_theme_data import derive_slug` keeps working because the name stays bound in the generator namespace. The identity test (`generator_module.derive_slug is lifx.theme.slug.derive_slug`) is the right enforcement.
- **No count-pinning, consistently.** D-08/D-23 decline is respected across all three plans: the shape-sweep in Task 3 checks "every record's disposition is one of the three allowed values" and "every non-None replaced_by resolves" — never `assert count == 9`. The phase-acceptance split check in 07-01's verification section is explicitly "run once, not committed as a test."
- **D-10 point-in-time framing is honest.** The migration page is stamped "As of migration" and deliberately not CI-pinned. This is the right contract for a page whose counts are historical claims, and it avoids the Phase 6 inventory page failure mode (a page that claimed to be current but went stale).
- **Empty-library edge covered.** Plan 07-02 Task 2 TestGetCategories includes "a subclass-with-empty-_THEMES case asserting `get_categories() == []` and `get_by_category('anything')` raises." This exercises the SPEC R1 adjacency + empty edges and the `cls._THEMES` subclass-safe indirection at `library.py:57`.
- **Throwaway script format verified.** I confirmed `json.dumps(obj, separators=(", ", ": "))` reproduces existing JSONL lines byte-for-byte. The rewrite won't introduce spurious whitespace diffs on the 138 app records beyond the inserted `disposition` field.

## 3. Concerns

- **MEDIUM — `_LEGACY_CATEGORIES` keys must be slug-form, undocumented.** Plan 07-02 Task 2 defines `_LEGACY_CATEGORIES` with keys `"holiday"`, `"mood"`, `"seasonal"`, `"ambient"`, `"functional"`, `"atmosphere"` — all already slug-form. The lookup does `if key in _LEGACY_CATEGORIES` where `key = derive_slug(category)`. If a future maintainer adds a legacy name that isn't pre-slugified (e.g. `"Pre-V12 Name"`), the lookup silently fails and the name falls through to the unknown-category error. The plan should add a one-line comment on the constant stating keys must be `derive_slug`-form, since the dict literal itself doesn't enforce it.

- **MEDIUM — Stale `shuffled()` note not updated.** `theme.py:31-34` carries: "``shuffled()`` and ``random()`` return identity-less copies: slug, name and category do not propagate." After plan 07-01 Task 2 adds `disposition`/`replaced_by`, this note is technically stale — the new fields also don't propagate (since `shuffled()` at `:145` calls `Theme(shuffled_colors)` with no keywords). The plan says "Do not touch ... any other method" for Task 2, which is correct for the code, but the docstring note should be extended to mention the new fields, or at least generalized to "identity fields." Low impact, but it's a shipped inaccuracy.

- **MEDIUM — American-spelling test assertion must be explicitly deleted.** `tests/test_theme/test_library.py:211` asserts `"not recognized" in str(exc_info.value)` (American). The rewrite changes the message to "not recognised" (Australian). Plan 07-02 Task 2 says "rewriting `TestThemeLibraryGetByCategory`" — but if the rewrite is done by adding new test classes and deleting the old one, the old `test_get_invalid_category` at `:205-211` must be fully removed, not just shadowed. The plan's behavior Test 7 asserts `"Available categories"` and `"Archives"` but does NOT assert the spelling of "recognised", so a leftover old test would fail with a confusing message. The plan should explicitly call out: delete `test_get_invalid_category` and `test_category_case_insensitive` (which uses `"SEASONAL"` — now raises) from the old class.

- **LOW — `test_all_categories_have_themes` at `test_library.py:354-367` lists the 6 legacy names and asserts each returns themes.** After the rewrite, 4 of them raise. The plan says this test is rewritten — confirmed in the must_haves. But the plan's behavior block doesn't explicitly list this test for deletion. The executor must know to delete it, not just add new tests alongside.

- **LOW — Non-deprecated records with `replaced_by` pass generator validation.** Plan 07-01 Task 1 explicitly declines to add a fourth validation rejecting `replaced_by` on non-deprecated records (D-08). The library-side sweep test in Task 3 catches this at test time. But a bad future data edit could slip a `replaced_by` onto a `lifx-app` record through the generator and into `data.py` before the sweep test runs. Acceptable per D-08's cost-benefit, but worth noting the generator is not self-defending here — the defence is split across generator (3 validations) + test suite (sweep).

- **LOW — `get_by_category` does 168 `derive_slug` calls per invocation.** `slugs = {record.slug for record in cls._THEMES.values() if derive_slug(record.category) == key}` — O(168) regex subs per call. Negligible at ~microseconds for a classmethod called occasionally, but if a caller hot-loops `get_by_category`, pre-computing `derive_slug(record.category)` once at import time would help. Not a blocker.

- **LOW — Throwaway JSONL rewrite script not persisted.** The script lives in the scratchpad and is discarded. Between Phase 7 and Phase 9, if the 28 dispositions need re-application, the script is gone. The SPEC R4 table is the fallback source. Acceptable per D-05 ("Phase 9's capture→JSONL converter must emit the field"), but the plan could note the script's logic in the SUMMARY for reproducibility.

## 4. Suggestions

- Add a comment on `_LEGACY_CATEGORIES` in `library.py`: `# Keys MUST be derive_slug-form; the lookup normalises caller input with derive_slug before probing this dict.` One line, prevents the silent-failure footgun.

- In plan 07-02 Task 2, add to the action: "Delete the existing `test_get_invalid_category` (asserts American 'not recognized') and `test_category_case_insensitive` (uses 'SEASONAL' which now raises) from `TestThemeLibraryGetByCategory` — the rewritten class replaces them." Make the deletion explicit so the executor doesn't leave stale assertions that fail post-rewrite.

- In plan 07-01 Task 2, extend the `Theme` class docstring note at `theme.py:31-34` from "slug, name and category do not propagate" to "slug, name, category, disposition and replaced_by do not propagate" — or generalize to "identity fields do not propagate." Keeps the shipped docstring honest.

- Consider pre-computing `derive_slug(record.category)` once during `emit_data_module` and storing it on `ThemeRecord` as a private `_category_slug` field, so `get_by_category` does a single `derive_slug(category)` on the caller input and a dict lookup instead of 168 regex subs. Not required for correctness, but it's a one-time cost at generation that pays off at every call. If the plan prefers to keep `ThemeRecord` lean (no extra field), at minimum cache the result in `get_by_category` via `functools.lru_cache` on a helper. Low priority — current perf is fine for the expected call frequency.

- In plan 07-03 Task 1, the migration page's "Before" example shows `get_by_category("holiday")` under the old grouping. Consider adding a one-line note that the old grouping is gone in v1.2 (not just shown as a contrast), so a reader landing on the page from a v1.1 codebase knows the call will still work (resolve to Holidays) rather than having been removed. The current Before/After framing implies the old call no longer works, which is false for `holiday`/`mood` (they still resolve).

## 5. Risk Assessment

**LOW risk overall.**

The plans are well-scoped, mechanically verified, and the highest-risk judgment (the 9/19 split) is copied from a locked table rather than re-derived. The schema change is additive (no existing field changes type or meaning), the alias emission order is explicitly preserved, and the SPEC's two internal inconsistencies (140 vs 138, `__hash__ is None`) are both surfaced and handled correctly. The wave ordering is sound — 07-02 depends on 07-01 (disposition must exist on `ThemeRecord` before `get()` threads it), and 07-03 depends on both (the page's After examples must run against shipped code).

The main residual risks are cosmetic: a stale docstring note, an American-spelling test that must be explicitly deleted, and an undocumented constraint on legacy-map key format. None of these can cause a runtime regression — the worst case is a confused test failure during execution that the executor will fix by updating the assertion. The no-key-stops-resolving guarantee (SPEC R7) is protected by the additive schema change, the preserved alias emission, and the existing `PRE_V12_KEYS` 57-key fixture which the plans explicitly leave untouched.

**Confidence in the plans as written: high.** The `confidence: low` self-assessment in the plan headers is overly modest — the plans are more thoroughly grounded than most.

---

## Antigravity Review

# Cross-AI Plan Review

### 1. Summary
The provided plans are extremely comprehensive, tightly scoped to the locked SPEC, and correctly map the migration requirements to concrete implementation steps. The approach to generating the taxonomy from `data/themes.jsonl` rather than hardcoding it is robust, and the transition strategy—handling legacy categories, updating schemas without breaking existing callers, and creating point-in-time migration docs—is executed carefully. The plans display a deep understanding of the repository's generator patterns, alias logic, and test coverage requirements.

### 2. Strengths
- **Backward Compatibility:** The backward compatibility of the `Theme` class is perfectly preserved by adding `disposition` and `replaced_by` as keyword-only arguments with `None` defaults (`src/lifx/theme/theme.py:__init__`), safely handling existing callers.
- **Generator Integrity:** The `scripts/generate_theme_data.py` generator modification safely wires the new schema fields and extends the defense-in-depth emission checks without disrupting the crucial alias assignment order (lines 469-482) that ensures aliases carry their target's identity.
- **Code Deduplication:** The choice to centralize `derive_slug()` into `src/lifx/theme/slug.py` cleanly removes code duplication between the library and the generator script, guaranteeing that the `get_by_category` taxonomy normalisation stays perfectly synced with the data generation process.
- **Documentation Accuracy:** The docstring and MkDocs changes (Plan 03) correctly reflect the point-in-time nature of the migration documentation, ensuring the `mkdocs.yml` is updated in both the `llmstxt` structure (lines 149-150) and the main `nav` tree (lines 223-224).
- **Data Migration Approach:** Relying on a throwaway script in the scratchpad directory to append the fields to `data/themes.jsonl` is a clean way to perform the one-off data migration without polluting the repository with single-use utility scripts.
- **Empty Category Fall-through:** The rewrite of `get_by_category()` correctly handles empty strings by allowing them to fall through the lookup cleanly, returning the standard "not recognised" ValueError without hitting unexpected exceptions.

### 3. Concerns
- **Encoding Risks during JSONL Rewrite (LOW):** Plan 01 specifies using `json.dumps(obj, separators=(", ", ": "))` for the JSONL rewrite script. While names are said to have emoji stripped, if any non-ASCII characters remain or are introduced later, `json.dumps` by default escapes them into `\uXXXX` sequences. This could cause unintended drift if not explicitly controlled.

### 4. Suggestions
- **Specify ensure_ascii=False:** In Plan 01, when writing the scratchpad script to migrate `data/themes.jsonl`, explicitly pass `ensure_ascii=False` to `json.dumps()` alongside the separators. This ensures the output maintains raw UTF-8 integrity and doesn't accidentally replace characters with unicode escape sequences.
- **Legacy Map Validation:** In Plan 02, while `_LEGACY_CATEGORIES` is a private, hardcoded constant mapping to replacements like `"Holidays"`, it might be worthwhile to add a small test ensuring that all `replacement` values in `_LEGACY_CATEGORIES` (where `resolves=True`) actually map to categories that exist in the generated dataset. This ensures they don't silently break if the app taxonomy changes in the future.

### 5. Risk Assessment
**Overall Risk Level:** **LOW**

**Justification:** The implementation precisely targets the objectives, modifies only what is strictly necessary, and sets up explicit validation rules and comprehensive test cases. The backward compatibility features and clear distinction between legacy usage and app taxonomy ensure that no existing consumers will break silently. The separation of concerns between generation (data) and runtime execution (library) is fully respected. The threat model identifies the most prominent risks (like DoS via catastrophic regex backtracking) and validates that the selected approach circumvents them.

---
