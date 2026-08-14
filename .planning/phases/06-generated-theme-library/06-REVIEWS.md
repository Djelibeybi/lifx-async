---
phase: 6
round: 3
reviewers: [codex]
reviewed_at: 2026-08-14T23:00:00+10:00
plans_reviewed:
  - 06-01-PLAN.md
  - 06-02-PLAN.md
verdict: "LOW — ready to execute"
reviews_round_1: "commit f6a6497 — codex, opencode, antigravity (2 HIGH, 4 MEDIUM, 1 LOW; incorporated in a6fdb6c)"
reviews_round_2: "commit c627689 — codex (all 7 round-1 findings confirmed fixed; 2 MEDIUM, 1 LOW new; incorporated in 6545a7d)"
---

# Cross-AI Plan Review — Phase 6 (Round 3, confirming pass)

Codex, reviewing revision `6545a7d`. **Verdict: LOW — ready to execute. Remaining
concerns: none.**

## Review history

| Round | Reviewers | Findings | Outcome |
|-------|-----------|----------|---------|
| 1 (`f6a6497`) | codex, opencode, antigravity | 2 HIGH, 4 MEDIUM, 1 LOW | All incorporated in `a6fdb6c`; new operator decision D-24 locked in response to the palette-ordering HIGH |
| 2 (`c627689`) | codex | All 7 round-1 findings CORRECTLY FIXED; 2 new MEDIUM, 1 LOW | Incorporated in `6545a7d`; rated MEDIUM — not ready unchanged |
| 3 (this file) | codex | None | **LOW — ready to execute** |

## Round-3 outcome

All three round-2 amendments verified CORRECTLY FIXED against source:

1. **Halloween stochastic failure.** The reviewer confirmed the existing test leaves `theme` bound to the Halloween `Theme` before asserting (`test_api_apply_theme.py:227`), that single-zone application selects via `theme.random()` (`light.py:897,926`), that the old palette holds only hues 31–34 (`library.py:136`) while the captured one holds ~10/30/33/40/40/46 (`themes.jsonl:67`) — so the assertion genuinely becomes stochastic. The prescribed wire-precision membership replacement is deterministic whichever member `random()` returns, and **is not a D-23 drift check**: it opens no committed data file and compares no generated output against committed source, only runtime application behaviour against the `Theme` the test already applied.
2. **`name`/`category` validation.** Non-string values can no longer reach slug derivation and raise `AttributeError`; Unicode can no longer fail first at an emit-time assertion; an empty `category` is explicitly rejected and cannot ship. Emit-time asserts correctly retained as defence in depth only.
3. **Stale seven-colour wording.** Corrected; `library.py:64` confirms five entries.

## Regression check — nothing settled was disturbed

`6545a7d` modifies only the two plan files. The reviewer independently re-derived the
full inventory once more (179 raw → 139 non-sport → 138 distinct app slugs; 57 current
keys, 27 shared, 30 orphans; minus the 2 rename aliases = 28 Library records; 166 records
→ 168 resolvable keys) and re-confirmed the rename-alias design, D-24's canonical
ordering, the `[0, 7282, 10923]` RuleTrio pin recomputed from the captured `Exciting`
record, the `tempfile.mkstemp` atomic write, `validate_key()` and the colour-field
checks, requirement metadata, and the commit-boundary guarantee.

## Note carried forward

`examples/matrix_effects.py` has a pre-existing unstaged modification, unrelated to
Phase 6 and outside every commit in this planning cycle. It remains unreviewed and
untouched by deliberate operator choice.

---

## Codex Review

## Summary

All three round-2 amendments are correctly incorporated and supported by the checked-out source. Commit `6545a7d` changes only the two Phase 6 plan files; it does not disturb the previously settled inventory, canonical ordering, validation, atomic-write, requirement, or commit-boundary decisions. I found nothing standing between these plans and execution.

## Amendment verification

1. **Halloween stochastic failure — CORRECTLY FIXED**

The existing test applies `evening`, `christmas`, then `halloween`, leaving `theme` bound to the Halloween `Theme`, before asserting the resulting colour ([test_api_apply_theme.py:227](/Volumes/External/Developer/Djelibeybi/lifx-async/tests/test_api/test_api_apply_theme.py:227)). The current assertion incorrectly assumes every Halloween colour has hue 25–40 ([test_api_apply_theme.py:234](/Volumes/External/Developer/Djelibeybi/lifx-async/tests/test_api/test_api_apply_theme.py:234)).

Source confirms that single-zone application selects `theme.random()` ([light.py:897](/Volumes/External/Developer/Djelibeybi/lifx-async/src/lifx/devices/light.py:897), [light.py:926](/Volumes/External/Developer/Djelibeybi/lifx-async/src/lifx/devices/light.py:926)). The old palette contains only hues 31–34 ([library.py:136](/Volumes/External/Developer/Djelibeybi/lifx-async/src/lifx/theme/library.py:136)), while the captured palette contains approximately 46, 10, 40, 30, 40 and 33 ([themes.jsonl:67](/Volumes/External/Developer/Djelibeybi/lifx-async/.claude/theme-capture/themes.jsonl:67)). Thus the existing assertion genuinely becomes stochastic.

The prescribed replacement uses wire-precision membership against that same runtime Halloween `Theme` ([06-02-PLAN.md:383](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/06-generated-theme-library/06-02-PLAN.md:383), [06-02-PLAN.md:394](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/06-generated-theme-library/06-02-PLAN.md:394)). It is deterministic regardless of which palette member `random()` selects.

This is not a D-23 drift check: it neither opens `data/themes.jsonl` nor compares generated output with committed source data. It verifies runtime application behaviour using the `Theme` already applied by the test.

2. **`name`/`category` validation — CORRECTLY FIXED**

The plan now requires `validate_records()` to reject both fields unless they are non-empty ASCII strings, using controlled `RuntimeError`s that name the record and JSONL line ([06-01-PLAN.md:277](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/06-generated-theme-library/06-01-PLAN.md:277), [06-01-PLAN.md:284](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/06-generated-theme-library/06-01-PLAN.md:284)). Consequently:

- Non-string values cannot reach slug derivation and raise `AttributeError`.
- Unicode cannot first fail an emit-time assertion.
- Empty `category` is explicitly rejected and cannot ship.

The six discriminating tests—non-string, empty and Unicode for each field—must assert `RuntimeError` plus record and line evidence ([06-01-PLAN.md:501](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/06-generated-theme-library/06-01-PLAN.md:501)). Emit-time assertions are correctly retained only as defence in depth ([06-01-PLAN.md:314](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/06-generated-theme-library/06-01-PLAN.md:314)).

3. **Stale seven-colour wording — CORRECTLY FIXED**

The tracer now states that both app and pre-v1.2 `cheerful` palettes have five colours and therefore requires multiset comparison rather than a vacuous length check ([06-01-PLAN.md:214](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/06-generated-theme-library/06-01-PLAN.md:214)). The current hand-written palette indeed contains five entries ([library.py:64](/Volumes/External/Developer/Djelibeybi/lifx-async/src/lifx/theme/library.py:64)).

## Regression check

No settled area was disturbed.

- **Diff scope:** `6545a7d` modifies only `06-01-PLAN.md` and `06-02-PLAN.md`.
- **Inventory recomputation:** 179 raw records → 139 non-sport records → 138 distinct app slugs; the current library has 57 keys, with 27 shared and 30 orphaned keys; removing the two rename aliases leaves 28 Library records, producing 166 records and 168 resolvable keys. This agrees with [06-02-PLAN.md:243](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/06-generated-theme-library/06-02-PLAN.md:243).
- **Rename aliases:** `aurora_borealis` and `forest` are old-only keys; `aurora` and `forrest` are app slugs. The two-alias design remains intact ([06-02-PLAN.md:216](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/06-generated-theme-library/06-02-PLAN.md:216)).
- **D-24:** canonical uint16 tuple sorting remains required in storage, generation and runtime acceptance ([06-01-PLAN.md:274](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/06-generated-theme-library/06-01-PLAN.md:274)).
- **RuleTrio arithmetic:** recomputation from captured `Exciting` yields sorted leading hue values `[0, 7282, 10923]`, matching the literal regression pin ([themes.jsonl:58](/Volumes/External/Developer/Djelibeybi/lifx-async/.claude/theme-capture/themes.jsonl:58), [06-02-PLAN.md:371](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/06-generated-theme-library/06-02-PLAN.md:371)).
- **Atomic write:** unique same-directory `tempfile.mkstemp`, formatting before replacement and unconditional cleanup remain unchanged ([06-01-PLAN.md:329](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/06-generated-theme-library/06-01-PLAN.md:329)).
- **Key and colour validation:** ASCII/lowercase/identifier checks for primary and alias keys and exact-int colour checks remain unchanged ([06-01-PLAN.md:263](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/06-generated-theme-library/06-01-PLAN.md:263), [06-01-PLAN.md:281](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/06-generated-theme-library/06-01-PLAN.md:281)).
- **Requirement metadata:** `06-01` still includes COMPAT-01 and `06-02` still includes THEME-04 ([06-01-PLAN.md:18](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/06-generated-theme-library/06-01-PLAN.md:18), [06-02-PLAN.md:16](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/06-generated-theme-library/06-02-PLAN.md:16)).
- **Commit boundary:** Plan 06-01 retains the 57-key fallback; Plan 06-02 regenerates the complete module before deleting it ([06-01-PLAN.md:377](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/06-generated-theme-library/06-01-PLAN.md:377), [06-02-PLAN.md:309](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/06-generated-theme-library/06-02-PLAN.md:309)).

## Remaining concerns

None.

The unrelated pre-existing modification to `examples/matrix_effects.py` remains unreviewed and untouched; it is outside commit `6545a7d` and Phase 6’s plan revision.

## Risk Assessment

**LOW — ready to execute.**

The two previous MEDIUM blockers and the LOW wording defect are correctly resolved, and the narrow revision introduced no regression in the settled plan structure or evidence.

---
