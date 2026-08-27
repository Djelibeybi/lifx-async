---
phase: 08-hardware-fidelity-validation
verified: 2026-08-16T08:25:13Z
status: passed
score: 3/3 must-haves verified
behavior_unverified: 0
overrides_applied: 1
overrides:
  - must_have: "One designated 24-cycle hardware run has all required observations and verified restoration for both selected roles, permitting sanitised official evidence."
    reason: "Operator-approved exception scoped only to Tile restoration and two-role finalisation. It accepts the recorded Tile and Luna fidelity observations, retains Tile restoration as unverified, deliberately withholds 08-UAT-RESULTS.json, prohibits a synthetic merge, and requires no further hardware run."
    accepted_by: "operator"
    accepted_at: "2026-08-16"
re_verification:
  previous_status: passed
  previous_score: 3/3
  gaps_closed: []
  gaps_remaining: []
  regressions: []
---

# Phase 08: Hardware Fidelity Validation Verification Report

**Phase Goal:** The shipped palettes are demonstrated to render as the app renders them, on more than the capture product, and the 16-colour question has an evidenced answer either way.
**Verified:** 2026-08-16T08:25:13Z
**Status:** passed — with one applied operator override
**Re-verification:** Yes — current uncommitted closeout state after Phase 8 completion

This verification inspected committed source, tests, and phase artefacts only. It did not access ignored run data, hardware, Android/ADB, LAN, or private target data. Physical observations remain the explicit operator decision recorded in the committed closeout.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | A sampled theme applied through the library renders on hardware the same as the identical app theme. | ✓ VERIFIED (operator evidence) | [08-UAT.md](08-UAT.md) records 12 accepted Tile stable expected matches: six app and six library across Cheerful and Mondrian. The comparison is unordered and duplicate-sensitive; public finalisation recomputes every verdict from committed theme data. |
| 2 | A palette read back from a matrix product other than the Tile matches the Tile capture as an unordered HSBK set. | ✓ VERIFIED (operator evidence) | [08-UAT.md](08-UAT.md) and [08-EXCEPTION-OVERRIDE.json](08-EXCEPTION-OVERRIDE.json) record 12 accepted Luna matches, its five-second post-change settling contract, and verified Luna restoration. |
| 3 | Each of the 25 shipped non-sport `lifx-app` 16-colour themes carries a committed determination. | ✓ VERIFIED | [08-CEILING-DETERMINATIONS.json](08-CEILING-DETERMINATIONS.json) has 25 unique sorted rows. A current-head import of `derive_ceiling_determinations()` produced the exact same projection from `data/themes.jsonl`. |

**Score:** 3/3 roadmap truths verified.

### Applied Exception

| Finalisation condition | Status | Evidence |
| --- | --- | --- |
| One designated 24-cycle hardware run has all required observations and verified restoration for both selected roles, permitting sanitised official evidence. | PASSED (override) | This condition is deliberately false: Tile restoration is `unverified`, `08-UAT-RESULTS.json` is absent, and synthetic merging is prohibited. The structured operator decision accepts exactly that exception without asserting restoration passed. |

### Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `uat_theme_fidelity.py` | Fail-closed runner, restoration, evidence validation, ceiling derivation | ✓ VERIFIED | 1,897 covered statements. It derives the 25-row ceiling set, rejects malformed private/public inputs, recomputes public cycle verdicts, and refuses non-finalisable results. |
| `tests/test_uat_theme_fidelity.py` | Hardware-free runner contracts | ✓ VERIFIED | Focused tests exercise schedules, private-path containment, live identity/provenance, restoration/finalisation gates, public-verdict recomputation, and Luna-only non-finalisability. |
| `tests/test_documentation_counts.py` | Ceiling and exception-boundary regressions | ✓ VERIFIED | Four tests verify 25/26/Carlton, active claims, exact committed runner projection, and the exception’s non-finalisation boundary. |
| `08-CEILING-DETERMINATIONS.json` | Privacy-safe per-slug determination | ✓ VERIFIED | Exact 25-row sorted runner projection. |
| `08-EXCEPTION-OVERRIDE.json` | Machine-reviewable exception scope | ✓ VERIFIED | Exactly one operator-approved exception: Luna restoration verified, Tile restoration unverified, no official JSON, no synthetic merge, and no further run. |
| `08-UAT.md` | Public closeout explanation | ✓ VERIFIED (exception record) | Explains accepted observations and withheld authority without claiming a finalisable UAT. |
| `08-UAT-RESULTS.json` | Normal authoritative UAT evidence | ⚠️ DELIBERATELY ABSENT | The runner requires both verified restorations before writing it. Its absence is permitted only by the applied override. |

### Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| `data/themes.jsonl` | `derive_ceiling_determinations()` | literal `lifx-app`/16-colour filter | ✓ WIRED | Direct current-head execution returned 25 unique sorted rows. |
| `derive_ceiling_determinations()` | `08-CEILING-DETERMINATIONS.json` | committed reduced projection | ✓ WIRED | Direct equality check and documentation regression passed. |
| complete private run | `08-UAT-RESULTS.json` | `finalise_private_results()` | ✓ FAIL-CLOSED | Role-only or non-finalisable results are rejected; no official JSON exists. |
| operator-approved observations | public closeout decision | `08-UAT.md` + `08-EXCEPTION-OVERRIDE.json` | ✓ WIRED | Both records retain unverified Tile restoration and prohibit synthetic merging. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Status |
| --- | --- | --- | --- |
| `08-CEILING-DETERMINATIONS.json` | determinations | `data/themes.jsonl` → runner derivation | ✓ FLOWING |
| official public results | palette verdict | strict stable palette → committed ThemeLibrary/source cross-check | ✓ FAIL-CLOSED |
| closeout docs | accepted observation outcome | operator-approved aggregate | ⚠️ LIMITED — not an authoritative UAT projection |

### Behavioural Spot-Checks

| Behaviour | Command | Result | Status |
| --- | --- | --- | --- |
| Runner and documentation contracts | focused hardware-free pytest with `-o addopts=''` | 252 passed | ✓ PASS |
| Statement/branch coverage | targeted coverage report | 1,897/1,897 statements; 596/596 branches; 100% | ✓ PASS |
| Ceiling projection | direct runner import versus committed JSON | 25 exact sorted rows | ✓ PASS |
| Static quality | Ruff check, Ruff format check, Pyright | clean; Pyright 0 errors/warnings/information | ✓ PASS |
| Hardware equivalence | no hardware interaction permitted | committed operator decision retained | ✓ HUMAN ACCEPTED |

### Probe Execution

No declared or conventional `scripts/*/tests/probe-*.sh` probe exists for this phase.

### Requirements Coverage

| Requirement | Source Plan | Status | Evidence |
| --- | --- | --- | --- |
| FIDELITY-01 | 08-02, 08-03, 08-04 | ✓ SATISFIED | Exact 25-row projection, direct runner comparison, and regression coverage. The current closeout marks the requirement complete. |
| FIDELITY-02 | 08-01, 08-02, 08-04 | ✓ SATISFIED (operator evidence) | 12 accepted stable expected Tile matches. Tile restoration remains separately unverified. |
| FIDELITY-03 | 08-02, 08-04 | ✓ SATISFIED (operator evidence) | 12 accepted stable expected Luna matches with five-second settlement and verified Luna restoration. |

All three Phase 8 requirement IDs are declared by Phase 8 plans; no orphaned requirement was found.

### Prohibition Checks

| Prohibition | Status | Evidence |
| --- | --- | --- |
| Do not use undocumented endpoints or identifiable cloud credentials. | ✓ JUDGMENT ACCEPTED | No HTTP endpoint/client in the runner; no live or cloud action in this re-verification. |
| Do not overclaim source length or fidelity. | ✓ VERIFIED | The 25 rows say `device-ceiling-unresolvable`; the exception keeps Tile restoration unverified and synthetic merging prohibited. |
| Do not commit private identifiers. | ✓ VERIFIED | Private-value/schema and path-containment behaviour is tested; committed records contain no target fields. |
| Do not normalise mismatches away or substitute hardware. | ✓ VERIFIED | Tests recompute verdicts and retain fail-closed identity/finalisation boundaries. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| --- | --- | --- | --- | --- |
| — | — | No unresolved `TBD`, `FIXME`, `XXX`, `TODO`, `HACK`, or placeholder marker in the runner, tests, or closeout artefacts | — | — |
| Current Phase 8 commits | — | Independent `git verify-commit` checks report valid signatures from the required project key | ✓ VERIFIED | The sandbox-only `%G? = N` result was a trust-store visibility artefact, not unsigned history. |

### Residual Warning / Accepted Debt

The source Tile’s captured state was **not** restored to the runner’s required verification standard. No finalisable two-role 24-cycle bundle or `08-UAT-RESULTS.json` exists; role-local Tile and Luna records must never be merged. The sole override accepts closure without further hardware work. It does not waive, repair, or hide that restoration fault.

The current Phase 8 commit chain was independently verified with `git verify-commit`; all checked commits carry good signatures from the required project key.

---

_Verified: 2026-08-16T08:25:13Z_
_Verifier: Codex (gsd-verifier)_
