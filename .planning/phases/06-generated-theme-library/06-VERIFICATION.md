---
phase: 06-generated-theme-library
verified: 2026-08-15T00:05:00Z
status: passed
score: 16/16 must-haves verified
behavior_unverified: 0
overrides_applied: 1
overrides:
  - must_have: "The 2 already-identical shared slugs are carried without diff at uint16 multiset precision — only the 25 differing shared slugs change palettes; exciting is one of the two"
    reason: "Measured: at strict uint16 only kwanzaa is byte-identical; exciting drifts 1 ulp on hues 239/271/294 because the app truncates where the old transcription rounded. THEME-02 binds shipped == captured (app is source of truth); wire-visible positional behaviour unchanged (leading trio 0/7282/10923 pinned). Documented in 06-02-SUMMARY.md Finding 3 for Phase 8."
    accepted_by: "orchestrator (verification_notes, phase 06 verify dispatch)"
    accepted_at: "2026-08-14T23:50:00Z"
---

# Phase 6: Generated Theme Library Verification Report

**Phase Goal:** Every non-sport app theme resolves by ASCII slug with app-accurate colours and app metadata, generated from the capture, and no name that resolved before v1.2 breaks
**Verified:** 2026-08-15T00:05:00Z
**Status:** passed
**Re-verification:** No — initial verification

All claims below were verified by executing probes against the working tree, the raw
capture (`.claude/theme-capture/themes.jsonl`) and git history (`3ab50ee~1` pre-phase
`library.py`) — never by trusting SUMMARY.md. All 7 SUMMARY-claimed commits (3ab50ee,
586e769, a0e0209, bda5da2, cbd451a, bf3bcd8, f9f5da4) exist in history.

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria + PLAN must_haves, merged)

| # | Truth | Status | Evidence |
| --- | ----- | ------ | -------- |
| 1 | All 138 non-sport app slugs resolve via `ThemeLibrary.get()` with palettes multiset-equal to the captured palettes at uint16 (SC1, THEME-01/02) | ✓ VERIFIED | Independent probe: re-derived 138 slugs from the 179-record raw capture (own D-09 reimplementation, not the shipped one), uint16-normalised each captured palette via `HSBK(...).as_tuple()`, compared Counter multisets through the public API — 0 missing, 0 mismatched |
| 2 | The 25 differing shared slugs return the app palette; `soothing` carries kelvin 8000 (SC2, THEME-03) | ✓ VERIFIED | Pre-v1.2 palettes recovered from `git show 3ab50ee~1:.../library.py` and executed; 26 of 27 shared slugs differ from pre-v1.2, `soothing` kelvins = {3500, 8000} |
| 3 | The 2 already-identical shared slugs carried without diff at uint16 | ✓ PASSED (override) | Only `kwanzaa` is strict-uint16-identical; `exciting` drifts 1 ulp (app truncation vs old rounding). Accepted deviation — see frontmatter override; wire behaviour pinned unchanged (truth 7) |
| 4 | All 57 pre-v1.2 keys still resolve (SC3, COMPAT-01) | ✓ VERIFIED | All 57 keys from the executed pre-phase `_THEMES` resolve; committed literal `PRE_V12_KEYS` fixture confirmed as 57 literal strings via AST parse, parametrised test passing |
| 5 | Rename pairs resolve both ways with the target's identity (COMPAT-03, D-14) | ✓ VERIFIED | `aurora_borealis`/`aurora` and `forest`/`forrest`: multiset-equal palettes, identical (slug, name, category) triples, and `THEMES[alias] is THEMES[target]` — same frozen record object |
| 6 | A retrieved theme exposes emoji-stripped display name and category distinct from its slug (SC4, META-01/02) | ✓ VERIFIED | `get('forrest').name == 'Forrest'`; `get('christmas').category == 'Holidays'`; sweep over all 168 names: name/category non-None, pure ASCII, name ≠ slug; categories exactly the 9-value set {Moods, Art Series, Music, Nature, Space, Play, Holidays, Archives, Library} |
| 7 | Regenerating from the committed data file reproduces `data.py` exactly (SC5, THEME-04) | ✓ VERIFIED | Ran `uv run python -m lifx.theme.generator` in this verification: shasum identical before/after (`0c037fdf…`), `git status --porcelain` clean afterwards. Canonical D-24 order held; `exciting` leading trio [0, 7282, 10923] pinned by literal in `test_rule_trio.py:82`, test passing |
| 8 | 28 Library orphans carried unchanged from pre-v1.2 (D-12) | ✓ VERIFIED | All 28 Library-category records multiset-equal to the executed pre-phase `_THEMES` at uint16; 0 differing |
| 9 | Every key is a lowercase ASCII identifier; listing sorted, exactly what `get()` accepts (THEME-01/D-15) | ✓ VERIFIED | `get_available_themes()` = 168 sorted names, all `isidentifier() and isascii() and islower()`, every one resolves |
| 10 | No key ends the retired legacy suffix (COMPAT-02 replacement criterion) | ✓ VERIFIED | `not any(k.endswith('_legacy'))` over all 168 keys |
| 11 | Unknown slug raises short KeyError: name + pointer, no listing (THEME-01 empty edge) | ✓ VERIFIED | Probe: `"Theme 'nonexistent' not found. Use ThemeLibrary.get_available_themes() to list the available themes."` — 103 chars, no theme names leaked |
| 12 | Caller-constructed `Theme` unchanged: identity None, iteration/indexing/add_color as before (META-01 empty edge, D-16/17) | ✓ VERIFIED | Behavioural probe: `Theme([HSBK(...)])` → slug/name/category all None, len/index/add_color work; `Theme()` defaults to 1 white colour |
| 13 | `Theme.__eq__` palette-only multiset, non-Theme returns NotImplemented, Theme unhashable (D-19/20) | ✓ VERIFIED | `Theme.__hash__ is None`; equal consecutive gets; `theme == 3` False without raising; pinned by TestThemeEquality (in the 426 passing tests) |
| 14 | Mutating a returned Theme does not change the next `get()` (mutation-leak fix) | ✓ VERIFIED (behavioural) | State transition exercised directly in probe: `add_color` on returned Theme, re-`get` length unchanged; also pinned by committed TestMutationIsolation |
| 15 | Generator writes atomically; interrupted run leaves target and directory unchanged (THEME-04 concurrency, D-05) | ✓ VERIFIED (behavioural) | Named test `TestMainAtomicWrite::test_interrupted_run_leaves_target_and_directory_unchanged` collected and passing; generator uses `mkstemp` + `replace` + `finally` unlink (code confirmed) |
| 16 | `get_by_category()` still returns themes for its existing category names, textually untouched (Phase 7 seam) | ✓ VERIFIED | All 6 pre-existing category names (seasonal, holiday, mood, ambient, functional, atmosphere) return non-empty results; method body diff vs `3ab50ee~1` shows only the `_THEMES = THEMES` aliasing above it, dict keys unchanged. (SPEC background's "sports category" wording was inaccurate pre-phase: `sports` was never a key of the hardcoded dict — verified by executing the pre-phase class; no behaviour change) |

**Score:** 16/16 truths verified (1 via accepted override; 0 present-but-behaviour-unverified)

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `data/themes.jsonl` | 166 records, pure ASCII, sorted, canonically sorted palettes | ✓ VERIFIED | 166 lines; generator re-consumed it without diff; palettes trace to capture/pre-v1.2 (see prohibitions) |
| `src/lifx/theme/generator.py` | Validating generator, `def main`, atomic write | ✓ VERIFIED | 516 lines; `main` callable; mkstemp/replace/finally-unlink present; runnable via `-m` (executed twice) |
| `src/lifx/theme/data.py` | `DO NOT EDIT`, `ThemeRecord`, `THEMES` dict, 168 keys | ✓ VERIFIED | All present; 5665 lines; alias assignments bind target record by identity |
| `src/lifx/theme/library.py` | Generated-dict-only ThemeLibrary, `_THEMES` deleted | ✓ VERIFIED | 211 lines (was 560); `grep -c 'HSBK(' == 0` equivalent confirmed (no hand-written literals); `_THEMES: dict[str, ThemeRecord] = THEMES` at line 45 |
| `src/lifx/theme/theme.py` | Identity kwargs + multiset `__eq__`, no `__hash__` | ✓ VERIFIED | Behavioural probes above |
| `tests/test_theme/test_theme_generator.py` | Generator hardening tests | ✓ VERIFIED | Exists (22 KB); atomic-write test collected; part of 426 passing |
| `tests/test_theme/test_library.py` | `PRE_V12_KEYS` + compat/metadata pins | ✓ VERIFIED | 57-entry literal tuple (AST-verified), parametrised at line 329 |
| `tests/test_effects/test_rule_trio.py` | Literal uint16 trio pin (D-24 regression gate) | ✓ VERIFIED | `[0, 7282, 10923]` literal at line 82, passing |
| `pyproject.toml` / `codecov.yml` | Coverage omit/ignore for generator + data module | ✓ VERIFIED | Each path exactly once in each file (grep -c = 1 × 4) |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| `generator.py` | `data/themes.jsonl` | local read, no download | ✓ WIRED | `DATA_FILE = ... / "data" / "themes.jsonl"` (line 33); no urlopen/http/socket anywhere in `src/lifx/theme/` |
| `library.py` | `data.py` | `from lifx.theme.data import THEMES, ThemeRecord` | ✓ WIRED | Line 17; `get()` and listing serve from it (executed) |
| `data.py` | `color.py` | `from lifx.color import HSBK` full-precision literals | ✓ WIRED | Line 22; every emitted `as_tuple()` round-trips (verified via full multiset sweep) |
| `library.py` | `theme.py` | `get()` attaches identity over fresh list | ✓ WIRED | `slug=record.slug` at line 80; fresh-list behaviour proven by mutation probe |
| `library.py` | `data.py` | `_THEMES: dict[str, ThemeRecord] = THEMES` | ✓ WIRED | Line 45; `get_by_category()` works over it |
| `test_library.py` | `library.py` | `PRE_V12_KEYS` literal fixture | ✓ WIRED | Parametrised test resolves every historical name |
| `data/themes.jsonl` | `.claude/theme-capture/themes.jsonl` | mechanical conversion, multiset-equal | ✓ WIRED | Re-verified independently in this verification (not trusting the executor's script): all 138 app palettes multiset-equal to capture, all 28 orphans multiset-equal to pre-v1.2 `_THEMES` |

### Data-Flow Trace (Level 4)

| Value | Source | Produces Real Data | Status |
| ----- | ------ | ------------------ | ------ |
| `Theme.colors` from `get()` | `THEMES[key].colors` tuple → fresh list | Yes — capture-exact uint16 palettes | ✓ FLOWING |
| `Theme.slug/name/category` | `ThemeRecord` fields | Yes — app metadata, ASCII | ✓ FLOWING |
| `get_available_themes()` | `sorted(THEMES)` | Yes — 168 real keys | ✓ FLOWING |

### Behavioural Spot-Checks

| Behaviour | Command | Result | Status |
| --------- | ------- | ------ | ------ |
| Regeneration idempotent | `uv run python -m lifx.theme.generator` ×1 vs committed | shasum equal, git clean | ✓ PASS |
| 138 capture palettes exact | independent probe vs raw capture | 0 missing, 0 mismatched | ✓ PASS |
| 57 pre-v1.2 keys resolve | probe vs executed git-history table | 0 unresolved | ✓ PASS |
| Mutation isolation | add_color then re-get | length unchanged | ✓ PASS |
| Phase test surface | `pytest tests/test_theme/ test_rule_trio test_spin test_api_apply_theme` | 426 passed | ✓ PASS |

### Probe Execution

No `scripts/*/tests/probe-*.sh` probes exist or are declared for this phase — N/A.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ----------- | ----------- | ------ | -------- |
| THEME-01 | 06-02 | 138 app themes by ASCII slug | ✓ SATISFIED | Truths 1, 9 |
| THEME-02 | 06-02 | Palettes match capture as uint16 multiset | ✓ SATISFIED | Truth 1 (independent capture comparison) |
| THEME-03 | 06-02 | Shared slugs resynced; soothing kelvin 8000 | ✓ SATISFIED | Truths 2, 3 (with documented override) |
| THEME-04 | 06-01, 06-02 | Generated, atomic, regeneration reproduces exactly | ✓ SATISFIED | Truths 7, 15; generator executed live |
| COMPAT-01 | 06-01, 06-02 | No pre-v1.2 key vanishes | ✓ SATISFIED | Truth 4; literal fixture committed |
| COMPAT-03 | 06-01, 06-02 | Renames resolve both ways | ✓ SATISFIED | Truth 5 |
| META-01 | 06-01, 06-02 | Display name, emoji-stripped, distinct from slug | ✓ SATISFIED | Truth 6; caller-constructed Theme unchanged (truth 12) |
| META-02 | 06-01, 06-02 | Category exposed; christmas → Holidays; twin dropped | ✓ SATISFIED | Truth 6; exactly one christmas record, ARCHIVES twin absent |
| COMPAT-02 | — | RETIRED 2026-08-14 | N/A (not a gap) | Replacement criterion verified: truth 10 |

No orphaned requirements: REQUIREMENTS.md maps exactly these 8 to Phase 6; COMPAT-04,
META-03/04 are Phase 7, FIDELITY-* Phase 8, TOOL-*/DOCS-03 Phase 9.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| — | — | No TBD/FIXME/XXX/TODO/HACK/placeholder markers in any phase-modified file | — | — |

Code-review warnings from 06-REVIEW.md, assessed against Phase 6 must-haves:

- **WR-01** (split-brain `_THEMES` vs module `THEMES` reads): real inconsistency, but no Phase 6 must-have depends on rebinding `_THEMES` — today `_THEMES is THEMES` and all 6 legacy category names return themes (truth 16). Hazard is for Phase 7, which owns the taxonomy replacement (META-04) and will touch exactly these lines. ℹ️ Info here; already recorded in 06-REVIEW.md.
- **WR-03** (regenerated `data.py` mode 0600): confirmed in working tree (`-rw-------`). Git tracks content, not mode, so the "regeneration reproduces the committed file" criterion holds at byte level (verified). ⚠️ Worth fixing but blocks no must-have.
- **WR-02** (taxonomy dead names/docstring) and **WR-04** (`Theme.__init__` aliases caller's list): pre-existing behaviour, out of the phase's declared scope (SPEC: taxonomy → Phase 7; Theme immutability rejected). No must-have threatened.

### Prohibitions (judgment tier — all resolved in SPEC, corroborated here)

| Prohibition | Verdict | Evidence |
| ----------- | ------- | -------- |
| No palette value unsupported by a capture record | ✓ upheld | Full-library provenance sweep executed: every one of the 168 keys' palettes multiset-matches either a raw capture record or a pre-v1.2 `_THEMES` entry — zero untraced |
| No undocumented LIFX endpoints; regeneration offline | ✓ upheld | grep over `src/lifx/theme/`: zero hits for urlopen/http/api.lifx.com/themes/v1/themes/v2/urllib/requests/socket; generator executed offline in this verification |
| No fidelity overclaim | ✓ upheld | `library.py` docstring claims only "synced from the LIFX app via hardware capture on 2026-08-14" and states palette order carries no meaning; no product-coverage or length-recovery claims |

### Human Verification Required

None. Every truth was verifiable programmatically; state-transition truths (mutation
isolation, atomic write) have passing behavioural tests/probes executed during this
verification.

### Known Accepted Deviations (not gaps)

1. **exciting 1-ulp uint16 drift** vs pre-v1.2 (hues 239/271/294) — shipped as captured
   per THEME-02; documented for Phase 8 in 06-02-SUMMARY.md Finding 3; recorded as an
   override in this report's frontmatter.
2. **COMPAT-02 retired** — replacement criterion (no legacy-suffixed key) verified.

### Gaps Summary

No gaps. The phase goal is achieved and independently evidenced: all 138 non-sport app
slugs resolve with capture-exact uint16 palettes and app metadata, all 57 pre-v1.2 names
resolve (28 orphans palette-unchanged), both rename pairs share their target's record,
the library is generated from the committed data file with live-verified byte-identical
regeneration, and the D-24 canonical order is pinned by a committed literal regression
gate.

---

_Verified: 2026-08-15T00:05:00Z_
_Verifier: Claude (gsd-verifier)_
