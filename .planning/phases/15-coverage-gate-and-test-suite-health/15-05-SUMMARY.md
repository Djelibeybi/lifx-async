---
phase: 15-coverage-gate-and-test-suite-health
plan: 05
subsystem: docs
tags: [ci, coverage, agents-md, roadmap, requirements, spec-amendment, github-issues]

requires:
  - phase: 15-02
    provides: "The relocated .planning/scripts/ tree and the flat-import repointing that this plan's AGENTS.md correction and reference sweep depend on"
  - phase: 15-03
    provides: "The delivered vacuous-gate guard (.github/patch_coverage_guard.py) that CI-01's reversal reasoning and the #214/#209 comments cite as CI-02's resolution"
provides:
  - "AGENTS.md's Measured Tree rule and corrected direct uv run .planning/scripts/<script>.py invocations, replacing the retired python -m module form"
  - "CI-01 recorded as reversed in REQUIREMENTS.md, PROJECT.md and ROADMAP.md, with every live path reference to a moved or deleted script corrected across the planning record"
  - "15-SPEC.md amended in five allowlisted regions so the locked spec agrees with the delivered mechanism, proven by a remainder hash over everything else"
  - "Issue #214 closed on the CI-01 reversal reasoning and issue #209 corrected with the four evidence points, both published and both closed per the operator's checkpoint decision"
affects: [17]

actuals:
  tokens: 9966
  tasks: 5
  commits: 5

tech-stack:
  added: []
  patterns:
    - "Normalise-and-rematch stale-path sweep: git grep candidates through a sed substitution that removes the relocated prefix, then re-match the same pattern, so a relocated path is not reported as stale while a mixed corrected-and-stale line still is"
    - "Remainder-hash gate over an allowlist of regions for amending a locked spec: excise the authorised regions by anchor lines the amendment does not touch, hash what remains, and compare against a recorded literal"
    - "Publication idempotence resolved from the remote rather than a local file: list existing comments, diff each body against the approved draft, and branch on the match count before ever posting"

key-files:
  created:
    - .planning/phases/15-coverage-gate-and-test-suite-health/15-ISSUE-214-COMMENT.md
    - .planning/phases/15-coverage-gate-and-test-suite-health/15-ISSUE-209-COMMENT.md
    - .planning/phases/15-coverage-gate-and-test-suite-health/15-ISSUE-PUBLICATION-RECORD.md
  modified:
    - AGENTS.md
    - .planning/REQUIREMENTS.md
    - .planning/PROJECT.md
    - .planning/ROADMAP.md
    - .planning/STATE.md
    - .planning/seeds/SEED-002-wifi-advertisement-staleness-control.md
    - .planning/phases/15-coverage-gate-and-test-suite-health/15-SPEC.md
    - .planning/phases/15-coverage-gate-and-test-suite-health/15-02-SUMMARY.md
    - .planning/phases/15-coverage-gate-and-test-suite-health/15-03-SUMMARY.md

key-decisions:
  - "Operator selected publish-both-close-209 at the Task 4 checkpoint: both drafted comments were published verbatim, #214 was closed as completed on the CI-01 reversal reasoning, and #209 was also closed as completed, diverging from 15-SPEC.md R5, which required the #209 correction comment but expected #209 to stay open. The reasoning recorded at the checkpoint and in 15-ISSUE-PUBLICATION-RECORD.md: CI-02's guard mitigates the failure mode #209 describes even though the underlying Codecov mechanism remains unestablished, and the comment itself states the mechanism as unknown rather than asserting a cause the evidence does not support."
  - "15-SPEC.md's requirement-2 acceptance criterion was amended from a single .planning/milestones/ exclusion to a six-category enumeration (also covering STATE-ARCHIVE.md, MILESTONES.md, WINDOWS.md, research/, and this phase's own before-state artefacts including 15-REVIEWS.md), because the reference sweep needed to skip those same historical records and a plan cannot widen a locked acceptance boundary by assumption alone."
  - "The locked-spec amendment scope was widened from one region to an allowlist of five (requirement 2's acceptance criterion, the Boundaries in-scope bullet, two phase-global Acceptance Criteria bullets, and the unclassified/R2 Edge Coverage row), because 15-SPEC.md restates its commitments twice and four of those restatements contradicted the delivered mechanism."

requirements-completed: [CI-01, CI-02]

coverage:
  - id: D1
    description: "AGENTS.md documents the corrected direct uv run .planning/scripts/<script>.py invocations, the Measured Tree rule and its two --cov targets, and how the deselected tooling tests are run"
    requirement: CI-01
    verification:
      - kind: other
        ref: "grep gates in Task 1's verify: corrected-invocations>=3, measured-tree-headings=1, no python -m scripts. survivor, tooling-flag-mentions>=1, old-path-citations=0"
        status: pass
    human_judgment: false
  - id: D2
    description: "CI-01 recorded as reversed with its reasoning across REQUIREMENTS.md, PROJECT.md and ROADMAP.md; every live tracked reference to a moved or deleted script corrected; Phase 17's ROADMAP.md dependency line no longer asserts CI-01 makes the probe's changed lines scoreable"
    requirement: CI-01
    verification:
      - kind: other
        ref: "Task 2 verify: SWEEP-CLEAN and DRAFTS-CLEAN normalise-and-rematch sweeps, reversal-mentions>=1, ROADMAP.md Phase 16/18/19/20 byte-identical to merge-base with main and Phase 17 byte-identical once its Depends on line is stripped"
        status: pass
    human_judgment: false
  - id: D3
    description: "15-SPEC.md's five locked restatements amended to agree with the delivered mechanism (direct uv run invocations, opt-in --tooling flag, import-then-deselect collection semantics), with the remainder of the file proven byte-identical outside those five regions"
    requirement: CI-01
    verification:
      - kind: other
        ref: "Task 3 verify: outside-authorised-regions remainder hash equals 6297894fc56c8a5385a3690d4f465ff434a988ed, enumerated-names=12, marker-phrasings=1, edge-row-prefix=1"
        status: pass
    human_judgment: false
  - id: D4
    description: "Issue #214 closed with the CI-01 reversal reasoning; issue #209 corrected with the four evidence points and the guard named as the resolution; the operator's publish-both-close-209 decision recorded"
    requirement: CI-02
    verification:
      - kind: other
        ref: "gh issue view 214/209 (state CLOSED, stateReason COMPLETED); exact-body-matches=0 direct diff (trailing-newline retrieval artefact only, confirmed identical once normalised); blob ids da513707a4d8204d1179dbb3e4294adae5c2d27c and 0f89d09a6f43b28dce4ddc64885701a5c1d615bb match git hash-object of the committed drafts"
        status: pass
    human_judgment: true
    rationale: "The byte-for-byte read-back diff is not literally empty because GitHub's comment-retrieval API appends one trailing newline to both bodies; this was confirmed a retrieval artefact rather than a content divergence by stripping exactly one trailing newline from both sides and re-diffing, which then matched exactly. A human should sight the two live issue threads once, because the plan's own acceptance criterion is phrased as diff --strip-trailing-cr producing empty output, and this particular divergence needed the extra normalisation step to explain rather than the literal command in the plan text."
  - id: D5
    description: "Publication proven idempotent and traceable: pre-publication baseline and per-post transaction log committed to 15-ISSUE-PUBLICATION-RECORD.md, no untracked files left behind"
    requirement: CI-02
    verification:
      - kind: other
        ref: "PUBLICATION-RECORD-PRESENT check; git status --porcelain clean; comment counts exactly one greater than the recorded baseline (0 to 1) for both issues"
        status: pass
    human_judgment: false

duration: ~20min (continuation session only)
completed: 2026-09-06
status: complete
---

# Phase 15 Plan 05: Measured-Tree Record Correction and Issue Publication Summary

**AGENTS.md states the measured-tree rule and every live path reference is corrected; CI-01 is recorded as reversed; 15-SPEC.md's five locked restatements are amended to match; issues #214 and #209 are published and closed.**

## Performance

- **Duration:** Tasks 1 to 4 and Task 5's irreversible publication were completed in a prior, interrupted session. This continuation covers the remaining bookkeeping: committing the transaction-log append, running Task 5's read-only read-back verification against live GitHub, re-running the plan's repeatable phase-level gates, and writing this summary. Continuation duration: approximately 20 minutes.
- **Started:** 2026-09-06 (prior session, Task 1); continuation started 2026-09-06T22:1x, completed 2026-09-06T22:49:59Z
- **Tasks:** 5 (4 auto tasks, 1 blocking-human checkpoint), all complete
- **Files modified:** 12 (9 declared in the plan's frontmatter plus 2 collateral em-dash fixes in 15-02-SUMMARY.md and 15-03-SUMMARY.md, plus the new 15-ISSUE-PUBLICATION-RECORD.md)

## Accomplishments

- `AGENTS.md` documents the corrected direct `uv run .planning/scripts/<script>.py` invocations, a new `## Measured Tree` section stating the rule (shipped library plus CI-executed code, nothing else) and its two `--cov` targets, and how the deselected tooling tests are run.
- `REQUIREMENTS.md`, `PROJECT.md`, `ROADMAP.md`, `STATE.md` and `SEED-002` all record CI-01 as reversed and cite only current script paths; `ROADMAP.md`'s Phase 17 dependency line no longer claims CI-01 makes the probe's changed lines scoreable.
- `15-SPEC.md`, a locked artefact, was amended in exactly five allowlisted regions so every place it restates its commitments (once per requirement, and again phase-globally in Boundaries, Acceptance Criteria and Edge Coverage) agrees with the delivered mechanism. The remainder of the file is proven byte-identical outside those regions by a recorded hash.
- Issue #214 is closed with the CI-01 reversal reasoning; issue #209 carries the four evidence points that contradict its original recorded cause and names this phase's guard as the resolution. Both were approved verbatim at the Task 4 checkpoint (`publish-both-close-209`) and both are now closed.
- Publication was proven idempotent and byte-identical to the approved drafts through GitHub's own state rather than a local file, and the pre-publication baseline plus the per-post transaction log are committed to `15-ISSUE-PUBLICATION-RECORD.md`.

## Task Commits

Each task was committed atomically. Tasks 1 to 4's commits, and Task 5's irreversible publication, were made in the prior, interrupted session; this continuation adds the transaction-log commit and this summary's metadata commit.

1. **Task 1: Correct AGENTS.md and state the measured-tree rule** - `246480b` (docs)
2. **Task 2: Record the CI-01 reversal and correct every live path reference** - `532228b` (docs)
3. **Task 3: Amend the five locked-SPEC statements the delivered mechanism contradicts** - `a4a5bc0` (docs)
4. **Checkpoint: Approve the two public issue corrections before they are published** - resolved by the operator selecting `publish-both-close-209`, recorded in `15-ISSUE-PUBLICATION-RECORD.md`'s "Operator decision" section
5. **Task 5: Publish the two issue corrections and prove the posted bodies match the approved ones** - baseline captured in `77eb737` (docs); both comments posted and both issues closed against live GitHub (not a local commit); transaction-log append committed in this continuation as `418ded3` (docs)

**Plan metadata:** committed by this continuation (see below).

## Files Created/Modified

- `AGENTS.md` - Measured Tree rule, corrected script invocations, tooling-test documentation, both `sys.path` insert explanations
- `.planning/REQUIREMENTS.md` - CI-01 recorded as reversed with reasoning, CI-02 recorded as delivered by the guard, both issue links current
- `.planning/PROJECT.md` - measured-tree rule replaces the probe-included-in-coverage claim
- `.planning/ROADMAP.md` - Phase 15 outcome corrected, Phase 17's `Depends on` parenthetical corrected, all other Phase 16 to 20 entries byte-identical
- `.planning/STATE.md` - v2.1 Working Notes bullets citing the probe repointed to its relocated path without stale line numbers
- `.planning/seeds/SEED-002-wifi-advertisement-staleness-control.md` - staleness command repointed to `.planning/scripts/thread_revalidation.py`
- `.planning/phases/15-coverage-gate-and-test-suite-health/15-SPEC.md` - five locked restatements amended, remainder proven unchanged by hash
- `.planning/phases/15-coverage-gate-and-test-suite-health/15-ISSUE-214-COMMENT.md` - approved and published closing comment for #214
- `.planning/phases/15-coverage-gate-and-test-suite-health/15-ISSUE-209-COMMENT.md` - approved and published correction comment for #209
- `.planning/phases/15-coverage-gate-and-test-suite-health/15-ISSUE-PUBLICATION-RECORD.md` - pre-publication baseline and transaction log for both posts
- `.planning/phases/15-coverage-gate-and-test-suite-health/15-02-SUMMARY.md`, `15-03-SUMMARY.md` - collateral em-dash corrections found by Task 2's phase-level sweep

## Decisions Made

- Operator selected `publish-both-close-209` at the Task 4 checkpoint: both drafts published verbatim, #214 closed on the reversal reasoning, and #209 also closed even though `15-SPEC.md` R5 only required the correction comment and expected #209 to remain open. Reasoning recorded in `15-ISSUE-PUBLICATION-RECORD.md`: CI-02's guard mitigates the failure mode #209 describes even though the underlying Codecov mechanism is unestablished, and the published comment itself states the mechanism as unknown rather than asserting an unsupported cause.
- `15-SPEC.md` R2's acceptance criterion was widened from a single `.planning/milestones/` exclusion to a twelve-name enumeration spanning six categories (`.planning/milestones/`, `.planning/STATE-ARCHIVE.md`, `.planning/MILESTONES.md`, `.planning/WINDOWS.md`, `.planning/research/`, and this phase's own before-state artefacts: `15-SPEC.md`, `15-CONTEXT.md`, `15-PATTERNS.md`, `15-DISCUSSION-LOG.md`, `15-REVIEWS.md`, and the phase's `PLAN`/`SUMMARY` files), matching the exclusion arguments in Task 2's repository-wide sweep item for item.
- The locked-spec amendment's authorised scope was widened from one region to an allowlist of five, because `15-SPEC.md` states its commitments twice (per requirement and again phase-globally) and four of the phase-global restatements contradicted what the phase actually delivers.

## Deviations from Plan

None beyond what is already documented in `15-ISSUE-PUBLICATION-RECORD.md`'s "Operator decision" section (the `publish-both-close-209` divergence from `15-SPEC.md` R5, which is a sanctioned checkpoint option, not an unplanned deviation). Tasks 1 to 3 and Task 5's publication mechanics executed exactly as written, verified and committed in the prior session.

### Additional out-of-scope observation (not fixed, not blocking)

While re-running the plan's repeatable gates during this continuation, the whole-phase coverage-exemption sweep (`src tests scripts .planning/scripts pyproject.toml codecov.yml .github`, Task 2's own verify) was also re-run as a check and reported two matches: a `# pragma: no cover - environment guard` comment on a defensive `except ModuleNotFoundError` branch in `.github/patch_coverage_guard.py`, and the literal string `"pragma: no cover"` inside a fixture string in `.planning/scripts/tests/test_patch_coverage_guard.py` that the guard's own test suite writes to a temporary `pyproject.toml` to exercise the guard's parsing. Both predate this plan entirely: they were introduced by plan 15-03 (the vacuous-gate guard), already summarised and committed before this plan's Task 1 ran. Per the scope boundary rule, pre-existing content from a different, already-completed plan is out of scope for this continuation's auto-fix authority, and neither match is a real coverage weakening: `.github/` is maintainer tooling the phase's own Measured Tree rule places outside the measured tree, so a `pragma: no cover` comment there has no effect on any coverage gate, and the second match is test fixture data, not an active exemption. Not fixed here; noted for visibility rather than treated as a Task 5 blocker, since it is not part of Task 5's own verify block or this continuation's assigned remaining work.

## Issues Encountered

None. The read-back diff against the live-retrieved comment bodies was not literally empty for either issue (each read-back showed the retrieved body carrying one extra trailing newline), which was confirmed to be a GitHub API retrieval artefact rather than a divergence in content by stripping exactly one trailing newline from both the retrieved and drafted text and re-comparing, which then matched exactly for both #214 and #209. Both `git hash-object` blob ids recorded in the transaction log (`da513707a4d8204d1179dbb3e4294adae5c2d27c` for #214, `0f89d09a6f43b28dce4ddc64885701a5c1d615bb` for #209) match the committed draft files exactly, confirming what was approved is what was posted.

## User Setup Required

None. No external service configuration required.

## Next Phase Readiness

- Phase 15 is complete: all five plans (15-01 through 15-05) have committed SUMMARY.md files, CI-01 is recorded as reversed, CI-02's guard is delivered and documented, and both public issue corrections are published and closed.
- Phase 17 inherits the relocated `.planning/scripts/ipv6_thread_probe.py`, outside the measured tree, per the corrected `ROADMAP.md` dependency line.
- No blockers carried forward from this plan.

## Self-Check: PASSED

- `AGENTS.md` contains the Measured Tree section and corrected invocations: confirmed present.
- `.planning/phases/15-coverage-gate-and-test-suite-health/15-ISSUE-PUBLICATION-RECORD.md` exists, is tracked, and carries the transaction log: confirmed.
- Commits `246480b`, `532228b`, `a4a5bc0`, `77eb737`, `418ded3` all found in `git log --oneline --all`.
- `gh issue view 214` and `209` both report `CLOSED`/`COMPLETED`; both comment counts are 1, exactly one greater than the recorded baseline of 0.
- `git hash-object` on both committed draft files matches the blob ids in the transaction log.
- Stale-path sweep (`SWEEP-CLEAN`), draft sweep (`DRAFTS-CLEAN`), ROADMAP block comparison (`CHANGED []`, block sizes matching the plan's recorded `{16: 16, 17: 17, 18: 17, 19: 17, 20: 15}`), `codecov.yml` unchanged, `pyproject.toml` coverage keys unchanged, phase-level em-dash sweep (`NO-EM-DASH-IN-PHASE-PROSE`, `gated-added-lines=2678`), `uv run --frozen pyright` (0 errors), `uv run --frozen ruff check .` (all checks passed), `uv run --frozen ruff format --check .` (284 files already formatted) and `uv run --frozen pytest -q` (4256 passed, 631 deselected) all re-run clean in this continuation.
- `git status --porcelain` clean after the transaction-log commit.
