# Issue Publication Record

Pre-publication baseline and per-post transaction log for the two public issue corrections
this phase publishes. The baseline is captured before the first post so the comment-count
postconditions in Task 5's verify are measurable. The transaction lines are corroboration,
written immediately after each post; the authoritative resume rule is the remote body
comparison against GitHub, not this file.

## Pre-publication baseline

Read with
`gh issue view <n> --repo Djelibeybi/lifx-async --json state,comments --jq '.state, (.comments | length)'`
at 2026-09-06T22:18:49Z.

| Issue | State | Comment count |
|-------|-------|----------------|
| 214   | OPEN  | 0 |
| 209   | OPEN  | 0 |

## Operator decision

At the Task 4 checkpoint the operator selected `publish-both-close-209`: publish both drafted
comments verbatim, close #214 as completed, and additionally close #209. This diverges from
`15-SPEC.md` R5, which requires the #209 correction comment but does not require #209 to be
closed and expects it to remain open. The operator's choice is one of this plan's own sanctioned
checkpoint options, not a deviation from the plan; it is recorded here, and again in the plan
summary, because it is not what the locked spec's default reading anticipated. The recorded
reasoning for closing #209 is that the guard shipped in CI-02 (`.github/patch_coverage_guard.py`)
mitigates the failure mode the issue describes even though the underlying mechanism remains
unestablished; the comment itself states the mechanism as unknown, and closing does not assert
a cause the gathered evidence does not support.

## Transaction log

Appended immediately after each post or recovery, in the order the actions were taken.

- Issue 214: posted. Blob `da513707a4d8204d1179dbb3e4294adae5c2d27c`. URL https://github.com/Djelibeybi/lifx-async/issues/214#issuecomment-5562582035. Closed as completed immediately after.
- Issue 209: posted. Blob `0f89d09a6f43b28dce4ddc64885701a5c1d615bb`. URL https://github.com/Djelibeybi/lifx-async/issues/209#issuecomment-5562583560. Closed as completed immediately after, per the operator's `publish-both-close-209` checkpoint decision (SPEC R5 expected #209 to remain open; see "Operator decision" above).
