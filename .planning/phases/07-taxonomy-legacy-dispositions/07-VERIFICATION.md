---
phase: 07-taxonomy-legacy-dispositions
verified: 2026-08-15T00:00:00Z
status: passed
score: 29/29 must-haves verified
behavior_unverified: 0
overrides_applied: 0
human_verification:

  - test: "Read docs/migration/theme-taxonomy-v1.2.md (categories section + Library table row), the library.py module/class docstrings and the get_by_category() docstring, and confirm the synthetic Library category is everywhere attributed to this library and never presented as one the LIFX app defines"
    expected: "Every mention attributes Library to lifx-async (e.g. 'Library is defined by this library, not the app', 'pre-v1.2 keys with no app counterpart'); no wording implies the app publishes it"
    why_human: "Judgment-tier prohibition (SPEC / plans 07-02, 07-03). Non-authoritative LLM-judge verdict: SATISFIED — page states 'Library is defined by this library, not the app'; library.py:14 states 'the 28 Library records are not app captures'. unverified-prohibition — human review recommended"

  - test: "Confirm no independent palette/semantic judgement was exercised when assigning the 28 orphan dispositions — the shipped values must be a verbatim copy of the SPEC R4 locked table"
    expected: "9 deprecated pairs and 19 library-only keys exactly equal the SPEC R4 table; no deviation, no extra call"
    why_human: "Judgment-tier prohibition (plan 07-01). Non-authoritative LLM-judge verdict: SATISFIED with deterministic support — set-equality against the locked table was machine-verified in this run (exact match, both directions). unverified-prohibition — human review recommended"
---

# Phase 7: Taxonomy & Legacy Dispositions — Verification Report

**Phase Goal:** Callers can navigate the library by the app's category taxonomy, and every legacy category name and orphaned key has a recorded, working fate
**Verified:** 2026-08-15 (branch `chore/theme-taxonomy`, clean tree at 9e3ff6a)
**Status:** human_needed (all automated checks passed; 2 judgment-tier prohibitions flagged for human sign-off)
**Re-verification:** No — initial verification

All evidence below was produced by executing the delivered code in this run — not taken from SUMMARY.md or 07-REVIEW.md claims.

## Goal Achievement

### Observable Truths — ROADMAP Success Criteria

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| SC1 | Caller can list the app's categories and list the themes within any one of them | ✓ VERIFIED | `get_categories()` returned exactly `["Archives", "Art Series", "Holidays", "Library", "Moods", "Music", "Nature", "Play", "Space"]`; `get_by_category(record.category)` succeeded and contained the record for **all 168 resolvable names**, executed live |
| SC2 | Every category name `get_by_category()` accepted before v1.2 either still returns themes or fails with a message naming its replacement | ✓ VERIFIED | Pre-phase accepted set extracted from `main:src/lifx/theme/library.py` — exactly 6 names. Executed all 6: `holiday`→15 Holidays themes, `mood`→13 Moods themes; `seasonal`/`ambient`/`functional`/`atmosphere` each raise `ValueError` naming `Nature`/`Play`/`Library`/`Moods`. `HOLIDAY` behaves identically to `holiday`. See wording-drift note below re the ROADMAP parenthetical |
| SC3 | Each of the orphaned library keys carries a recorded disposition — kept as library-only, or deprecated naming its replacement — and a deprecated key still resolves | ✓ VERIFIED | 28 Library orphans (see drift note re "30"): 9 deprecated / 19 library-only, both sets exactly equal to the SPEC R4 locked table (machine-compared). All 9 deprecated keys still resolve via `get()` and surface `disposition`/`replaced_by`. Every `replaced_by` resolves in `THEMES` |

### Observable Truths — Plan must_haves (26)

| # | Truth (condensed) | Status | Evidence |
|---|-------------------|--------|----------|
| 1 | 166 JSONL records carry disposition; 9/19/138 split per SPEC R4 | ✓ VERIFIED | Parsed `data/themes.jsonl` directly: 166 records, `Counter == {'lifx-app':138,'library-only':19,'deprecated':9}`, `('replaced_by' in r) == (disposition=='deprecated')` for all |
| 2 | Every replaced_by resolves in THEMES; no chain exists | ✓ VERIFIED | All 9 targets checked in `THEMES`; all 9 replacements are lifx-app records |
| 3 | replaced_by None unless deprecated; generator aborts on deprecated-without-replacement | ✓ VERIFIED | Runtime sweep over 166 records passed; `TestValidateRecordsDispositions` (8 tests incl. `test_deprecated_without_replacement_aborts`) run by name — all pass |
| 4 | disposition/replaced_by ASCII, canonical-key check | ✓ VERIFIED | Generator validations run green; `test_bad_value_branches_abort` covers non-canonical replaced_by |
| 5 | disposition on all records incl. 138 lifx-app; palette_equals ignores new fields | ✓ VERIFIED | Executed: two Themes, equal palettes, different dispositions → `palette_equals()` True |
| 6 | fire/hygge/christmas triples per SPEC R5 | ✓ VERIFIED | Executed: `('deprecated','warm_ember')`, `('library-only',None)`, `('lifx-app',None)` |
| 7 | Theme.__eq__ identity, hashable, `Theme([...])` still constructs | ✓ VERIFIED | Executed: `hash()` works, `t1 != t2` with equal palettes, bare constructor defaults both fields to None |
| 8 | 168 names resolve; PRE_V12_KEYS passes; alias identity | ✓ VERIFIED | `len(THEMES)==168`; `THEMES['forest'] is THEMES['forrest']`, `THEMES['aurora_borealis'] is THEMES['aurora']`; `test_pre_v12_key_resolves` (57-key parametrised) in the 83 green library tests |
| 9 | Regeneration byte-idempotent (THEME-04) | ✓ VERIFIED | Ran generator twice, `cmp` byte-identical, `git diff --exit-code` clean against committed data.py |
| 10 | get_categories() exact 9-name codepoint-sorted list | ✓ VERIFIED | Exact-list assertion executed; "Archives" precedes "Art Series" |
| 11 | Category names derive from record set; empty library returns [] | ✓ VERIFIED | `get_categories()` reads `cls._THEMES`; subclass-empty case covered in `TestGetCategories` (suite green) |
| 12 | ASCII-only names/comparison | ✓ VERIFIED | All 9 names pure ASCII; slug rule is `[^a-z0-9]+` |
| 13 | All 168 names reachable via `get_by_category(record.category)` by slug key | ✓ VERIFIED | Executed over all `THEMES.items()` |
| 14 | Lookup order: app taxonomy first, legacy second | ✓ VERIFIED | `library.py` body: `_slugs_for_category` checked before `_LEGACY_CATEGORIES`; no name collides |
| 15 | Unknown/empty raises ValueError listing categories; "" gets generic error | ✓ VERIFIED | Executed both; messages contain "Available categories" + "Archives" and never "replacement" |
| 16 | D-09 slug normalisation both sides; artseries raises | ✓ VERIFIED | Executed: `art_series` == `Art Series` == `ART SERIES` key sets; `artseries` raises |
| 17 | Returned dict keyed by slug, sorted by slug | ✓ VERIFIED | Executed on Holidays result |
| 18 | holiday→15, mood→13, HOLIDAY==holiday | ✓ VERIFIED | Executed |
| 19 | 4 legacy names raise naming Nature/Play/Library/Moods | ✓ VERIFIED | Executed all 4; exact pinned message text observed |
| 20 | Hardcoded dict deleted; no time category or seasonal example in docstrings | ✓ VERIFIED | `grep '"seasonal"'` = 1 (map entry only); winter/romantic/dramatic = 0; `time, etc`/`get_by_category("seasonal")`/`not recognized` all absent |
| 21 | One derive_slug, in-package, shared by generator | ✓ VERIFIED | `def derive_slug` count: slug.py=1, generator=0, library=0; both import `from lifx.theme.slug`; slug.py has zero lifx imports (leaf); identity test in suite |
| 22 | Migration page exists, in both nav sections, names 9 categories+counts, 6 legacy names, 9 deprecated keys | ✓ VERIFIED | Per-row regex over all 9 category/count pairs passed; all 15 fate rows matched line-level; `grep -c mkdocs.yml` = 2; `zensical build` exit 0 |
| 23 | One row per legacy name / per deprecated key, no empty sections | ✓ VERIFIED | Row-level assertions for all 6 + all 9 passed |
| 24 | Point-in-time "As of" stamp; no CI count-pinning | ✓ VERIFIED | "As of" present; no test in tests/test_theme/ pins 9/19/138 (grep — sole `== 9` hit is a colour count in test_apply_theme.py) |
| 25 | No docstring or doc page mentions a time category; no shipped doc teaches a raising name | ✓ VERIFIED | `grep -rn "seasonal, mood, holiday, time" docs/ src/lifx/` empty; doc-wide scan executed every `get_by_category(...)` example in docs/**/*.md outside the migration page — all resolve |
| 26 | getting-started uses app names; stale api/themes.md admonition gone | ✓ VERIFIED | `get_by_category("Holidays")`/`("Moods")` present, lowercase forms absent, `get_categories` present; "older grouping" absent; migration link present |

**Score:** 29/29 truths verified (0 present-but-behaviour-unverified — every behaviour was executed directly)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `data/themes.jsonl` | 166 lines with disposition; 9 with replaced_by | ✓ VERIFIED | Parsed and counted directly |
| `scripts/generate_theme_data.py` | _DISPOSITIONS, required/optional fields, 3 validations, extended emit | ✓ VERIFIED | Validations exercised via 8 abort tests; local derive_slug deleted, imports from package |
| `src/lifx/theme/data.py` | Regenerated; ThemeRecord.disposition / replaced_by | ✓ VERIFIED | Byte-idempotent regeneration; fields present and populated at runtime |
| `src/lifx/theme/theme.py` | Keyword-only disposition/replaced_by defaulting None | ✓ VERIFIED | Executed: additive constructor holds |
| `src/lifx/theme/library.py` | get() threads fields; get_categories(); rewritten get_by_category(); _LEGACY_CATEGORIES | ✓ VERIFIED | All behaviour executed; map private (`_LEGACY_CATEGORIES` at :39, absent from `lifx.theme.__all__`) |
| `src/lifx/theme/slug.py` | New leaf module housing derive_slug | ✓ VERIFIED | Exists; only stdlib import; sole implementation |
| `docs/migration/theme-taxonomy-v1.2.md` | New migration page | ✓ VERIFIED | Exists; all tables verified row-level |
| `mkdocs.yml` | Page in both Migration nav sections | ✓ VERIFIED | 2 references; `zensical build` clean |
| `docs/api/themes.md`, `docs/getting-started/themes.md` | Corrections | ✓ VERIFIED | All plan assertions pass |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| data/themes.jsonl | Theme.disposition | validate_records → emit → ThemeRecord → get() | ✓ WIRED | Full pipeline exercised live: JSONL value observed on the public Theme for all three disposition classes |
| THEMES alias emission | R7 alias identity | aliases assigned after dict literal | ✓ WIRED | `is`-identity holds for both alias pairs with new fields present |
| lifx.theme.slug.derive_slug | library.py + generator | shared import | ✓ WIRED | Both importers confirmed; zero duplicate definitions; identity test in suite |
| get_by_category()/get_categories() | cls._THEMES | subclass-safe indirection | ✓ WIRED | Empty-subclass test in suite; source confirmed |
| _LEGACY_CATEGORIES raising branch | replacement name in message | tagged-tuple values (D-02) | ✓ WIRED | All 4 raising messages observed naming their replacement |
| mkdocs.yml nav | migration page | 2 nav entries | ✓ WIRED | Build exit 0, no issues |

### Behavioural Spot-Checks

| Behaviour | Command | Result | Status |
|-----------|---------|--------|--------|
| Full SPEC R1–R5, R7 acceptance | inline `uv run python` script (all acceptance assertions) | ALL BEHAVIOURAL CHECKS PASSED | ✓ PASS |
| JSONL source-of-truth invariants | inline parse + Counter | 138/19/9 exact | ✓ PASS |
| Regeneration idempotence | generate → snapshot → generate → `cmp` + `git diff --exit-code` | byte-identical, tree clean | ✓ PASS |
| D-08 abort validations | `pytest ...::TestValidateRecordsDispositions` | 8 passed | ✓ PASS |
| Library/category/legacy/PRE_V12 tests | `pytest test_library.py -k ...` | 83 passed | ✓ PASS |
| Full theme suite | `pytest tests/test_theme/ -q` | 380 passed | ✓ PASS |
| Full workspace suite (regression, run once) | `uv run --frozen pytest -q` | **3390 passed, 0 failed** in 119s | ✓ PASS |
| Branch coverage on changed sources | coverage JSON assertion | 100% line+branch on generator, theme.py, library.py, slug.py | ✓ PASS |
| Static checks | `pyright` (3 files), `ruff check` | 0 errors / all checks passed | ✓ PASS |
| Docs build | `uv run zensical build` | exit 0, no issues | ✓ PASS |
| No-network prohibition (test-tier) | AST import assertion over 8 files | no network-capable imports | ✓ PASS |
| Changelog untouched (test-tier) | `git log main..HEAD -- docs/changelog.md` | 0 commits | ✓ PASS |
| Legacy map privacy (test-tier) | `__all__` assertions | `_LEGACY_CATEGORIES` and `derive_slug` unexported; `get_categories` callable | ✓ PASS |
| SUMMARY commit hashes | `git cat-file -t` on all 9 claimed hashes | all exist as commits | ✓ PASS |

### Probe Execution

No `scripts/*/tests/probe-*.sh` probes exist in this project and no plan declares any. N/A.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| META-03 | 07-02 | Caller can list the categories, and list the themes within one | ✓ SATISFIED | SC1 evidence above |
| META-04 | 07-02, 07-03 | Hand-made taxonomy reconciled with the app's categories; old names keep working or fail naming their replacement | ✓ SATISFIED | SC2 evidence + migration page tables |
| COMPAT-04 | 07-01, 07-03 | Each orphaned library key carries a recorded disposition | ✓ SATISFIED | SC3 evidence + docs deprecated-key table |

No orphaned requirements: REQUIREMENTS.md maps exactly these three IDs to Phase 7 (lines 127, 130, 131), all claimed by plans.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | none | — | No TBD/FIXME/XXX/TODO/HACK/placeholder markers in any file this phase modified |

Pre-adjudicated review items honoured per instruction: WR-01 fixed in 466253d (independently confirmed — the doc-wide raising-example scan passes); WR-02 / R2-05 / D-08 generator non-enforcement is a recorded user decision with test-side enforcement (independently confirmed the test-side sweep exists: `test_replaced_by_only_on_deprecated_records`) — not re-filed.

### Prohibitions

| Prohibition | Tier | Disposition |
|-------------|------|-------------|
| No network fetch of taxonomy/disposition data (07-01, 07-02) | test | ✓ VERIFIED — AST assertion executed, enforcement wired in plan acceptance criteria |
| No public accessor / export of _LEGACY_CATEGORIES (07-02) | test | ✓ VERIFIED — `__all__` assertions executed |
| docs/changelog.md untouched (07-03) | test | ✓ VERIFIED — 0 branch commits touch it |
| Library never presented as app-defined (07-02, 07-03) | judgment | ⚑ FLAGGED for human sign-off; non-authoritative verdict SATISFIED (explicit attribution wording found at every surface) |
| No subject-matter disposition judgement (07-01) | judgment | ⚑ FLAGGED for human sign-off; non-authoritative verdict SATISFIED (shipped 9/19 split machine-compared equal to the locked SPEC R4 table) |

### Human Verification Required

#### 1. Library-category attribution wording

**Test:** Read the migration page's category section and Library table row, plus the `library.py` module docstring and `get_by_category()` docstring.
**Expected:** The synthetic `Library` category is always attributed to lifx-async ("defined by this library, not the app"; "not app captures"), never presented as a LIFX-app category.
**Why human:** Judgment-tier prohibition — wording honesty is an operator call. Non-authoritative verdict: SATISFIED (exact quotes located at docs page :30-31 and library.py :14).

#### 2. Disposition split provenance

**Test:** Confirm the 28 orphan dispositions are a verbatim copy of the SPEC R4 locked table with no independent judgement exercised.
**Expected:** 9 deprecated pairs and 19 library-only keys exactly match the table.
**Why human:** Judgment-tier prohibition about process. Non-authoritative verdict: SATISFIED with deterministic support — exact set equality machine-verified in this run.

### Gaps Summary

No gaps. Every automated check passed against the live codebase. Two informational ROADMAP wording drifts, neither a gap:

1. **"30 orphaned library keys" (ROADMAP SC3)** — the measured, SPEC-locked count is **28** (166 records − 138 app records); the "30" counted the 2 rename aliases Phase 6 already wired. Verified against 28 per SPEC/CONTEXT.
2. **SC2's parenthetical `(seasonal, hygge, tranquil, sports, …)`** — `hygge`/`tranquil`/`sports` were never category names `get_by_category()` accepted; extracted from `main:library.py`, the accepted set was exactly the 6 names (`seasonal`, `holiday`, `mood`, `ambient`, `functional`, `atmosphere`), all of which now have verified working fates. The three listed names are theme *keys*, all of which still resolve (`hygge` library-only, `tranquil` lifx-app, `sports` library-only).

---

## Post-Verification Addendum (2026-08-15)

Recorded after the original run so this file stays the newest artifact in the phase
(the staleness resolver reads mtimes — see STATE.md Blockers, open-gsd/gsd-core#2348).

**Human verification closed.** Both judgement-tier items above were confirmed by the
operator during `/gsd-verify-work 7`; `07-UAT.md` records 2/2 passing. Item 1 was
re-tested after the version-label fix and passes against the current wording.

**One defect found by UAT and fixed on the branch (gap G-07-1, resolved).** The migration
page and the shipped docstrings identified this work by `v1.2`, the internal `.planning/`
milestone number, which carries no meaning outside this repository. Corrected to the
lifx-async release version. The first attempt used 6.3.0, computed from a checkout that
had not been fetched; `origin` already carried that release (`ca52da5`, tag `v6.3.0`) from
Phase 6 via PR #196. Final label is **6.4.0**, derived after rebasing onto `origin/main`.
Re-verified against the rebased tree: 3390 tests pass, pyright 0 errors, ruff clean,
`zensical build` reports no issues, and every documented example in the migration page
executes correctly.

**Security review completed.** `07-SECURITY.md` records 10 threats, 0 open, at ASVS L1.

**Two summary corrections** made during transition (see `0a26177`): `07-03-SUMMARY.md`
pointed at the pre-rename page path, and `07-02-SUMMARY.md` described a "no-network AST
assertion" that does not exist — the underlying control is real and was verified directly,
but Phase 6 recorded it as a review-time inspection (`06-SECURITY.md:71`), not a test.

Status remains **passed**. None of the above changes a verified behaviour.

## Post-Ship Code Review Addendum (2026-08-15, commit `582f74b`)

A `max`-effort review of PR #202 found 15 defects. Twelve were fixed by the review
pass itself; three required an operator decision and produced a **behaviour change
that invalidates two verified acceptance criteria**. `07-SPEC.md` R3, R5 and R7 were
amended post-ship and carry the full rationale; this records what stopped being true
here.

**Two criteria this report verified are no longer the contract:**

1. *"`get_by_category("holiday")` returns 15 themes; `get_by_category("mood")` returns
   13; `seasonal`, `ambient`, `functional`, `atmosphere` each raise naming `Nature`,
   `Play`, `Library`, `Moods`."* All six names now raise the generic
   unrecognised-category error. The verification was accurate against the SPEC as
   written; the SPEC was wrong. Its resolve/raise split was inverted against its own
   stated criterion — `functional` retained 3/3 of its old themes and raised while
   `holiday` retained 7/12 and resolved — and two of the four named replacements did
   not hold a majority of what the name used to return (`seasonal → Nature`: 0/2).

2. *"Both rename aliases still share their target's record object."* Deliberately
   broken. That binding meant `forest` and `aurora_borealis` reported
   `disposition="lifx-app"` with `replaced_by=None`, so the only two keys whose name
   had changed were the only two reporting that nothing had. Each alias is now its own
   `disposition="renamed"` record naming the live key, sharing only the palette object.

**Why the phase's own gates missed both.** Every automated check confirmed the code
matched the SPEC; nothing compared the SPEC's rule to the SPEC's own measurement
table, which already recorded `seasonal | Library 2` on line 36 while R3 named
`Nature`. The alias gap was invisible for a different reason: R4's closed disposition
set had no value able to express a rename, so the phase shipped 28 orphan fates for
30 orphans and no criterion counted the difference.

**Re-verified after the change:** 3428 tests pass, pyright 0 errors, ruff clean, 100%
branch coverage on `src/lifx/theme/` and `scripts/generate_theme_data.py`, generator
byte-idempotent.

Status for the amended requirements: **re-verified**. R1, R2, R4 and R6 are unaffected.

---

_Verified: 2026-08-15_
_Verifier: Claude (gsd-verifier)_
_Addendum: 2026-08-15 after UAT, security review, and phase transition_
