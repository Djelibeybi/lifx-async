---
phase: 16-mdns-correctness-docs-and-test-hygiene
verified: 2026-09-07T09:21:26Z
status: passed
score: 4/4 must-haves verified
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: passed
  previous_score: 4/4
  gaps_closed: []
  gaps_remaining: []
  regressions: []
---

# Phase 16: mDNS Correctness, Docs and Test Hygiene Verification Report

**Phase Goal:** The mDNS surface behaves correctly at its fail-closed boundary and describes
itself to callers in caller-facing terms.
**Verified:** 2026-09-07T09:21:26Z
**Status:** passed
**Re-verification:** Yes — triggered by `gsd_run query verification.status` reporting `stale`
after commit `8e76f2f` edited `kind: lint-rule` to `kind: other` in twelve `coverage:` entries
across `16-02-SUMMARY.md`, `16-03-SUMMARY.md` and `16-04-SUMMARY.md` (`lint-rule` is not in the
coverage schema's allowed enum and was mis-routing automatically-covered deliverables to human
checkpoints in `uat classify-coverage`).

## Re-verification premise check

The trigger claims nothing affecting the verdict changed. Both premises were independently
confirmed rather than assumed:

- `git diff --name-only 71cae4b..HEAD -- . ':!.planning/'` returned **empty** — no production
  file changed between the initial verification commit and the current tree.
- `git diff 71cae4b..HEAD -- .../16-02-SUMMARY.md .../16-03-SUMMARY.md .../16-04-SUMMARY.md`
  showed **only** `kind: lint-rule` → `kind: other` token substitutions (12 occurrences across
  the three files); every `ref`, `status`, `description`, `requirement` and `human_judgment`
  value was byte-for-byte unchanged.

Both checks held, so this re-verification re-runs the phase's acceptance gates against the
current (unchanged-in-production) tree rather than treating the prior evidence as still valid by
assumption.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | An owner name supplied with a trailing dot resolves to the same address decision as the same name without one; a regression test fails if the normalisation is removed from `selected_address_for()` | ✓ VERIFIED | Re-read `_owner_is_unusable()`, `_selected_address_for_normalised()` and `selected_address_for()` in `src/lifx/network/discovery/mdns/discovery.py:354-398` — unchanged since the initial verification. **Mutation check re-run independently**: replaced `_normalise_dns_name(owner)` with `owner.lower()` inside `selected_address_for()`, ran `TestLifxRecordCacheOwnerNormalisation` — 3 of 8 tests went red (`test_trailing_dot_owner_is_refused_when_the_overflow_guard_fires`, `test_empty_and_root_owners_are_refused_even_when_an_address_is_cached`, `test_owner_whose_lower_and_casefold_differ_agrees_on_the_casefolded_form`), matching the prior run's result exactly. Restored via `git checkout -- src/lifx/network/discovery/mdns/discovery.py`; `git status --porcelain` confirmed clean immediately after. |
| 2 | A caller reading `Device.connectivity` learns it is derived from request outcomes rather than stored device state, and no repository or published guidance lists it among the state-backed cached properties | ✓ VERIFIED | Re-checked `docs/user-guide/advanced-usage.md:143-148`: `Device.connectivity` sits under `##### Non-State Properties`, separate from the `#### Device Properties` list. `AGENTS.md:351` carries the third `**Derived, not cached**` category naming exactly `connectivity`, scoped to "the most recent correlated response". Confirmed `connectivity` appears in neither the `Cached (semi-static)` list (`AGENTS.md:349`) nor the `Never cached` list (`AGENTS.md:350`). Re-read `docs/api/devices.md:345-355` — the Connectivity section makes no caching claim. Re-ran `tests/test_repository_guidance.py tests/test_network/test_mdns/test_phase_contract.py` (see combined run below) — all pass. |
| 3 | The mDNS discovery docstrings and related pages state bounded discovery, proxy responses and testing limitations in terms a caller can act on, with no internal validation language such as mesh scale being "proven synthetically" remaining | ✓ VERIFIED | `grep -rniE "mesh scale|proven synthetically"` over `src/`, `docs/`, and `tests/test_network/test_mdns/test_phase_contract.py` returns zero matches (re-run independently). Re-read `docs/user-guide/discovery.md`'s `## Limitations` section (lines 110-138): bounded discovery, proxy-response ("advertises every device on its mesh... proves an advertisement exists... confirm it with a request") and testing-limitations ("Do not size timeouts or retry policy from this documentation") language is present and caller-actionable. `tests/test_docs_language.py` exists (4517 bytes) and, run together with the contract suites, passes. |
| 4 | The mDNS discovery tests import at module scope, ruff and the mDNS suite pass, and any retained function-local import carries a named reason | ✓ VERIFIED | `pyproject.toml:81,98-104` — `PLC0415` in `select`, exactly 7 per-file-ignore entries. `uv run --frozen ruff check --no-cache --select PLC0415 tests/ --exclude tests/test_animation --exclude tests/test_theme --exclude tests/test_devices/test_multizone.py` → 0 violations (re-run independently). `grep -rn "noqa: PLC0415" tests/` → 0 matches, no retained function-local imports need a reason. **PLC0415 genuinely fires — re-confirmed with a fresh probe, not trusted from config**: piped a synthetic function-local import to `ruff check --stdin-filename tests/test_gate_probe.py -` (via stdin, no file created) → exit 1, `PLC0415` reported. Re-ran the same synthetic snippet against all 7 ignored paths (`src/lifx/__init__.py`, `.planning/scripts/probe.py`, `tests/test_animation/probe.py`, `tests/test_theme/probe.py`, `tests/test_devices/test_multizone.py`, `.agents/skills/probe.py`, `.claude/skills/probe.py`) via stdin — all 7 exit 0, no PLC0415 reported. No probe file was created on disk (stdin only); `git status --porcelain` confirmed clean throughout. |

**Score:** 4/4 truths verified (0 present, behavior-unverified)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/lifx/network/discovery/mdns/discovery.py` | `_owner_is_unusable()`, `_selected_address_for_normalised()`, rewired `selected_address_for()` | ✓ VERIFIED | Present, wired, mutation-tested afresh this run |
| `tests/test_network/test_mdns/test_discovery.py` | `TestLifxRecordCacheOwnerNormalisation` class | ✓ VERIFIED | 8 methods present, 5 pass / 3 correctly fail under mutation |
| `tests/test_docs_language.py` | Repository-wide prose contract module | ✓ VERIFIED | Exists, runs in default suite, module-scope imports |
| `docs/user-guide/discovery.md` | Caller-facing prose for bounded discovery, proxy responses, testing limitations | ✓ VERIFIED | All fragments present, no internal jargon |
| `src/lifx/api.py` | `discover_mdns()` docstring recast | ✓ VERIFIED | 0 forbidden-phrase matches |
| `docs/user-guide/advanced-usage.md` | `Device.connectivity` under Non-State Properties | ✓ VERIFIED | Confirmed positionally |
| `AGENTS.md` | Third `Derived, not cached` category | ✓ VERIFIED | Present, scoped correctly |
| `pyproject.toml` | `PLC0415` select entry + 7 per-file-ignores | ✓ VERIFIED | Exact match; positive and negative probes re-run and confirmed |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `selected_address_for()` (public) | `_selected_address_for_normalised()` (private) | `_normalise_dns_name()` | ✓ WIRED | Confirmed by source read and independent mutation test |
| `discover()` | `_discover_verified_devices_mdns()` | mDNS leg | ✓ WIRED | api.py:1128 (line numbers stable since production tree is unchanged) |
| `AGENTS.md` bullet | `docs/user-guide/advanced-usage.md` bullet | consistent wording | ✓ WIRED | Both describe correlated-response-only derivation |
| `ruff [tool.ruff.lint] select` PLC0415 | test-tree enforcement | per-file-ignores | ✓ WIRED | Positive probe fires; all 7 negative probes suppress, re-confirmed this run |

### Behavioral Spot-Checks / Mutation Tests (re-run independently)

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Regression test fails when normalisation removed | Replaced `_normalise_dns_name(owner)` with `owner.lower()`, ran `TestLifxRecordCacheOwnerNormalisation` | 3/8 failed (same 3 as prior run) | ✓ PASS |
| Working tree restored after mutation | `git checkout -- src/lifx/network/discovery/mdns/discovery.py && git status --porcelain` | Clean, no diff | ✓ PASS |
| PLC0415 rule fires (positive control) | Synthetic function-local import via stdin, `tests/test_gate_probe.py` filename | Exit 1, PLC0415 reported | ✓ PASS |
| PLC0415 rule suppressed on all 7 ignored paths (negative controls) | Same synthetic snippet via stdin against each ignored path | All 7: exit 0, no PLC0415 | ✓ PASS |
| No probe files left on disk | `git status --porcelain` after probes | Clean | ✓ PASS |
| PLC0415 zero violations across in-scope tests | `uv run --frozen ruff check --no-cache --select PLC0415 tests/ --exclude ...` | All checks passed | ✓ PASS |
| Docs + contract suites | `uv run --frozen pytest tests/test_docs_language.py tests/test_network/test_mdns/test_phase_contract.py tests/test_repository_guidance.py -q` | 38 passed | ✓ PASS |
| mDNS suite alone | `uv run --frozen pytest tests/test_network/test_mdns -q` | 400 passed | ✓ PASS |
| Full default test suite | `uv run --frozen pytest -q` | 4272 passed, 631 deselected | ✓ PASS |
| Lint | `uv run --frozen ruff check --no-cache .` | All checks passed | ✓ PASS |
| Format | `uv run --frozen ruff format --check .` | 285 files already formatted | ✓ PASS |
| Type checking | `uv run pyright` | 0 errors, 0 warnings | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| MDNS-09 | 16-01 | Owner-name normalisation at fail-closed boundary | ✓ SATISFIED | `.planning/REQUIREMENTS.md:20` marked `[x]`, `:173` Complete; mutation-tested afresh |
| DOCS-07 | 16-03 | `Device.connectivity` documented as derived, not cached | ✓ SATISFIED | `.planning/REQUIREMENTS.md:79` marked `[x]`, `:181` Complete; contract tests re-run |
| DOCS-08 | 16-02 | Caller-facing mDNS prose | ✓ SATISFIED | `.planning/REQUIREMENTS.md:84` marked `[x]`, `:182` Complete; jargon-absence re-grepped |
| TEST-01 | 16-04 | Module-scope test imports + standing ruff rule | ✓ SATISFIED | `.planning/REQUIREMENTS.md:95` marked `[x]`, `:184` Complete; PLC0415 probes re-run |

No orphaned requirements found for Phase 16 in REQUIREMENTS.md's phase mapping table.

### Anti-Patterns Found

None. Re-scanned the phase's summary edits (`8e76f2f`) — confined to `kind:` enum-value token
substitutions in YAML frontmatter, no `TBD`/`FIXME`/`XXX`/`TODO`/`HACK`/`PLACEHOLDER` introduced.
Production tree confirmed unchanged since the initial verification (`71cae4b`), so the initial
verification's anti-pattern scan of the actual delivered code remains valid without needing to
repeat it in full.

### Human Verification Required

None. All four roadmap success criteria are mechanically verifiable and were independently
re-verified this run, including a fresh live mutation test for criterion 1 and fresh positive/
negative PLC0415 probes for criterion 4.

### Gaps Summary

No gaps found. This re-verification did not copy forward the initial report's evidence —
`selected_address_for()`'s mutation test, the `Device.connectivity` documentation placement, the
internal-jargon grep, and both PLC0415 probe directions were all re-executed against the current
tree. The working tree is clean (`git status --porcelain` empty except for this file); the
mutation and probe checks performed during this verification were fully reverted before
completion. The metadata-only `kind: lint-rule` → `kind: other` edit in `8e76f2f` has no bearing
on the phase goal and is confirmed not to have altered any verified behaviour.

---

_Verified: 2026-09-07T09:21:26Z_
_Verifier: Claude (gsd-verifier)_
