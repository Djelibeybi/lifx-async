---
phase: 7
round: 2
reviewers: [codex]
reviewed_at: 2026-08-15T02:36:01Z
plans_reviewed: [07-01-PLAN.md, 07-02-PLAN.md, 07-03-PLAN.md]
supersedes: "round 1 (codex, opencode, antigravity) — commit 9338667"
---

# Cross-AI Plan Review — Phase 7, Round 2 (post-revision)

Round 1 (Codex + OpenCode + Antigravity, 18 findings) is preserved in git at commit
`9338667`. Its findings were incorporated in `4a87c9b`. This round re-runs Codex — the
reviewer that raised both findings that mattered — to check whether the revision landed
and whether it broke anything.

## Verdict

**11 CLOSED · 1 SUPERSEDED · 1 PARTIAL · 1 MISSED · 2 new MEDIUM defects introduced.**

Codex's overall risk: **MEDIUM**, "not quite ready to execute". Two of the new defects
are acceptance criteria that **cannot pass as written** — they would fail the executor on
correct work. Both were independently reproduced by the orchestrator against the live tree.

## Actionable — must fix before execution

**R2-01 — MEDIUM — The no-network acceptance criterion is guaranteed to fail.**
`07-01-PLAN.md:231`. Reproduced verbatim on the unchanged tree: the grep emits
`src/lifx/theme/library.py:* https://github.com/pkivolowitz/lifx — the palette themes ...`.
The exclusion `grep -vE "docstring|Djelibeybi/(aiolifx|lifx)"` covers the aiolifx-themes
attribution at `library.py:18` but not the pkivolowitz attribution at `library.py:19`, and
the first filter `grep -v "^.*#.*github.com"` does not match because the line carries no `#`.
The criterion claims it "finds no new network access"; it finds a line today.
**Fix:** exclude attribution lines robustly, or replace the whole sweep with the
import/AST assertion that F12 declined — Codex notes the F12 deferral rationale
("this sweep is adequate") is now falsified by the sweep failing.

**R2-02 — MEDIUM — The idempotence check compares against git, not against the previous generation.**
`07-01-PLAN.md:229`. Task 1 intentionally rewrites `data.py`, then asserts
`uv run scripts/generate_theme_data.py` followed by `git diff --exit-code src/lifx/theme/data.py`
exits 0. Before the task's commit, `git diff` necessarily contains the intended schema and
record changes, so the check cannot prove second-run byte-idempotence — it proves only
"matches whatever is committed", and fails outright if evaluated pre-commit.
**Fix:** checksum the first generation, regenerate, and compare — or copy the first output
to a temp file and `cmp`. Make it independent of commit state.

**R2-03 — LOW — Migration-page verification is weaker than the plan's claim.**
`07-03-PLAN.md:144` requires exact category/count pairs and every "After" example to run;
the verification at `:160` only checks each category name occurs somewhere and manually
exercises one deprecated lookup. A swapped count or a broken `get_categories()` /
`get_by_category("Holidays")` snippet would pass.
**Fix:** add category-to-count row checks, and either execute the fenced After block or
mirror every statement from it in the verification script.

**R2-04 — LOW — The coverage acceptance pipeline observes rather than enforces.**
`07-01-PLAN.md:374` pipes pytest output into `grep` and says it "shows no Missing entries".
`grep` can exit 0 while printing uncovered lines, and without `pipefail` a pytest failure is
masked. The earlier full-suite command limits practical risk.
**Fix:** use `--cov-fail-under` or a parsed coverage assertion so the criterion is executable.

## Carried concern — a judgement call, not a defect

**R2-05 — PARTIAL — `replaced_by` permitted on non-deprecated records.**
Codex accepts the deferral is now *explicit* but argues the rationale is *inadequate*:
D-08 locks three validation **concerns**, and it reads making the existing replacement
validation bidirectional as tightening one of those three rather than adding a prohibited
fourth. It notes SPEC `07-SPEC.md:108` states `replaced_by` is `None` unless deprecated and
`:209` describes that invariant as covered — so the generator currently accepts a state the
locked public contract prohibits. Its suggested one-liner lives inside the existing check:

```
if disposition != "deprecated" and "replaced_by" in record:
    raise _fail(...)
```

plus one failing-record test and an equivalent emit-time backstop.

This is a real tension between D-08's scope lock and the SPEC's stated invariant, and it is
**the user's call**, not the planner's. If the deferral stands, Codex asks that the plan and
threat model explicitly acknowledge the generator does not enforce the locked invariant.

## Findings confirmed closed

Generator branch coverage (the round-1 HIGH) — Codex confirms the six specified branches
match real paths around `scripts/generate_theme_data.py:248`, and that the coverage config
at `pyproject.toml:113` / `codecov.yml:12` is as the corrected plan now describes.
Emit-time asymmetry documented; "all 168 names" reworded off object equality; the v1.x
compatibility promise removed; task-boundary atomicity declared; `_slugs_for_category()`
used by both paths; public-surface wording fixed; type-guard decline accepted as adequate;
doc verification moved to exact old/replacement pairing; the raising-name scan widened;
Before/After framing corrected.

`derive_slug` bootstrap cycle — **SUPERSEDED**. Codex independently re-traced the chain
(`generate_theme_data.py:31` → `lifx/__init__.py:86` → `theme/__init__.py:40` →
`library.py:27`) and agrees the dependency predates this phase, and that keeping `slug.py`
as a guarded leaf module is reasonable.

---

## Codex Review

## Round-1 finding closure

| Finding | Verdict | Evidence |
|---|---|---|
| Generator branch coverage | CLOSED | Plan 07-01 now identifies the generator as branch-covered and specifies all six missing paths, including two new rows in the existing emit-time matrix ([07-01-PLAN.md](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/07-taxonomy-legacy-dispositions/07-01-PLAN.md:303)). This matches the real compound validation and emit branches around [generate_theme_data.py](/Volumes/External/Developer/Djelibeybi/lifx-async/scripts/generate_theme_data.py:248). Coverage is explicitly configured for `generate_theme_data` with branch measurement, and Codecov requires 100% patch coverage ([pyproject.toml](/Volumes/External/Developer/Djelibeybi/lifx-async/pyproject.toml:113), [codecov.yml](/Volumes/External/Developer/Djelibeybi/lifx-async/codecov.yml:12)). |
| `replaced_by` allowed on non-deprecated records | PARTIAL | The shipped-data sweep catches this state, but the generator deliberately continues accepting it ([07-01-PLAN.md](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/07-taxonomy-legacy-dispositions/07-01-PLAN.md:175)). The rationale is explicit but not adequate: D-08 identifies three validation concerns; it does not prohibit making the deprecated/replacement validation bidirectional. The locked specification says `replaced_by` is `None` unless deprecated ([07-SPEC.md](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/07-taxonomy-legacy-dispositions/07-SPEC.md:108)) and describes that invariant as covered ([07-SPEC.md](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/07-taxonomy-legacy-dispositions/07-SPEC.md:209)). |
| Emit-time validation weaker than normal validation | CLOSED | The asymmetry is now accurately documented: canonicality is checked at emit time, while resolution requires the whole validated record set ([07-01-PLAN.md](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/07-taxonomy-legacy-dispositions/07-01-PLAN.md:190)). Given that the production generator calls validation before emission, this rationale is adequate. |
| `derive_slug` import/bootstrap cycle | SUPERSEDED | The revision correctly demonstrates that the dependency already exists: the generator imports `lifx.color` ([generate_theme_data.py](/Volumes/External/Developer/Djelibeybi/lifx-async/scripts/generate_theme_data.py:31)), while package initialisation eagerly imports `lifx.theme` ([lifx/__init__.py](/Volumes/External/Developer/Djelibeybi/lifx-async/src/lifx/__init__.py:86)), which imports `library.py` and generated `data.py` ([theme/__init__.py](/Volumes/External/Developer/Djelibeybi/lifx-async/src/lifx/theme/__init__.py:40), [library.py](/Volumes/External/Developer/Djelibeybi/lifx-async/src/lifx/theme/library.py:27)). Keeping `slug.py` as a leaf module is a reasonable scoped decision ([07-02-PLAN.md](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/07-taxonomy-legacy-dispositions/07-02-PLAN.md:133)). |
| “All 168 names contains `t`” implied value equality | CLOSED | The revised test asserts canonical slug-key membership instead of `Theme` equality ([07-02-PLAN.md](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/07-taxonomy-legacy-dispositions/07-02-PLAN.md:212)). This is consistent with `Theme` retaining identity equality and `get_by_category()` being keyed by record slug. |
| New v1.x compatibility promise | CLOSED | The page is now instructed to use the locked contract—deprecation records a fate, while removal would be a v2.0 decision—without promising support throughout v1.x ([07-03-PLAN.md](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/07-taxonomy-legacy-dispositions/07-03-PLAN.md:133)). |
| Brittle no-network grep | MISSED | A rationale was added, but the proposed check already fails against the unchanged attribution URL in [library.py](/Volumes/External/Developer/Djelibeybi/lifx-async/src/lifx/theme/library.py:19). Its exclusions only cover `Djelibeybi/(aiolifx|lifx)`, not `pkivolowitz/lifx` ([07-01-PLAN.md](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/07-taxonomy-legacy-dispositions/07-01-PLAN.md:231)). |
| Task-boundary red window | CLOSED | Plan 07-01 explicitly declares tasks 1–3 atomic for patch coverage and no longer claims every intermediate task state satisfies the final gate ([07-01-PLAN.md](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/07-taxonomy-legacy-dispositions/07-01-PLAN.md:84)). |
| Duplicate category scans | CLOSED | Both application and legacy paths now use `_slugs_for_category()`; caching is declined with a proportionate bounded-cost rationale ([07-02-PLAN.md](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/07-taxonomy-legacy-dispositions/07-02-PLAN.md:260)). |
| Public-surface wording | CLOSED | The acceptance criterion now correctly distinguishes a class method reachable on exported `ThemeLibrary` from a module-level `__all__` symbol ([07-02-PLAN.md](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/07-taxonomy-legacy-dispositions/07-02-PLAN.md:344)). |
| No runtime type guard | CLOSED | The decline is explicit and adequate: the API is typed as `str`, Pyright covers typed callers, and runtime enforcement is outside the locked scope ([07-02-PLAN.md](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/07-taxonomy-legacy-dispositions/07-02-PLAN.md:310)). |
| Substring-only documentation verification | CLOSED | Deprecated and legacy rows are now checked as exact old/replacement pairs on the same line ([07-03-PLAN.md](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/07-taxonomy-legacy-dispositions/07-03-PLAN.md:160)). |
| Narrow “no shipped doc teaches a raising name” check | CLOSED | The revised script scans every Markdown `get_by_category()` literal outside the historical migration page and calls the delivered API ([07-03-PLAN.md](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/07-taxonomy-legacy-dispositions/07-03-PLAN.md:229)). |
| Before/After framing implied removal | CLOSED | The plan now requires an explicitly historical label and states that `holiday` and `mood` remain valid while their result sets change ([07-03-PLAN.md](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/07-taxonomy-legacy-dispositions/07-03-PLAN.md:144)). |

## New concerns introduced by the revision

### MEDIUM — The no-network acceptance command is guaranteed to fail

The command at [07-01-PLAN.md](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/07-taxonomy-legacy-dispositions/07-01-PLAN.md:231) currently prints:

```text
src/lifx/theme/library.py:* https://github.com/pkivolowitz/lifx ...
```

That source is an existing attribution in [library.py](/Volumes/External/Developer/Djelibeybi/lifx-async/src/lifx/theme/library.py:18). Either exclude all known attribution-only lines robustly or replace this with an import/AST check for network-capable modules. As written, the acceptance criterion cannot pass.

### MEDIUM — Plan 07-01’s idempotence check compares against Git, not the pre-regeneration file

Task 1 intentionally changes generated `data.py`, then requires:

```sh
uv run scripts/generate_theme_data.py
git diff --exit-code src/lifx/theme/data.py
```

([07-01-PLAN.md](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/07-taxonomy-legacy-dispositions/07-01-PLAN.md:229)).

Before the task commit, `git diff` necessarily contains the intended schema and record changes, so it cannot prove second-run idempotence. Record a checksum before the second generation and compare it afterwards, or copy the first output to a temporary file and use `cmp`.

### LOW — Migration-page counts and runnable examples are claimed more strongly than verified

The page must contain exact category/count pairs and every After example must run ([07-03-PLAN.md](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/07-taxonomy-legacy-dispositions/07-03-PLAN.md:144)). The verification only checks that each category name occurs somewhere and manually exercises one deprecated lookup ([07-03-PLAN.md](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/07-taxonomy-legacy-dispositions/07-03-PLAN.md:160)). A swapped category count or broken `get_categories()`/`get_by_category("Holidays")` snippet could pass.

Add category-to-count row checks and either execute the fenced After block or duplicate every statement from it in the verification script.

### LOW — The coverage acceptance pipeline is observational, not enforcing

The command pipes pytest output into `grep` and says it “shows no Missing entries” ([07-01-PLAN.md](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/07-taxonomy-legacy-dispositions/07-01-PLAN.md:374)). `grep` can return success while displaying uncovered lines, and without `pipefail` it can also mask pytest failure. The earlier full-suite command limits the practical risk, but an explicit `--cov-fail-under` or parsed coverage assertion would make this criterion executable.

## Remaining concerns

The only substantive carried concern is the one-way `replaced_by` validation. The current deferral knowingly permits the source-of-truth generator to accept a state prohibited by the public contract. This should be handled inside the existing replacement validation rather than treated as a fourth unrelated validation:

```python
if disposition != "deprecated" and "replaced_by" in record:
    raise _fail(...)
```

Add one failing-record test and an equivalent emit-time backstop if direct unvalidated emission is intended to preserve every source invariant.

## Risk Assessment

Overall risk: **MEDIUM**.

The revision closes almost all round-1 findings, and the branch-test matrix now matches the real generator paths. The `derive_slug` decision is also correct after checking the live import chain.

The plans are **not quite ready to execute**. Fix the guaranteed-failing no-network check and the invalid plan-07-01 idempotence check first. I also recommend resolving, rather than deferring, the non-deprecated `replaced_by` hole; otherwise the plan and threat model should explicitly acknowledge that the generator does not enforce the locked invariant.
