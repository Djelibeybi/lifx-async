The gathered evidence does not support this issue's original explanation, that Codecov scored
the documentation-only head commit's diff instead of the pull request's full range.

Four points, gathered while planning phase 15 of the v2.1 milestone:

1. CI ran on `d68d36a` under both the `pull_request` and `push` events, both successful, with
   all five Python-version flags uploaded.
2. The compare endpoints were correct: `ed17fdb..d68d36a` spans three commits, and `d68d36a`'s
   parent is `a56bd2c`, not the base.
3. `codecov/project` reported `96.69% (target 90.00%)` on that same commit, so the reports
   themselves were sound.
4. Codecov had the right base, the right head and five valid reports, and still scored zero
   lines.

The mechanism is unknown. The leading hypothesis is Codecov's own fetch of the pull request diff
from the GitHub API, but that is not established, and this issue's resolution does not depend on
finding it.

Because the cause is not established, this phase ships a cause-agnostic guard rather than a fix
aimed at an unverified theory. `.github/patch_coverage_guard.py` computes both the changed
measured lines and the scored lines from the repository's own data, a merge-base diff intersected
with `coverage.py`'s own source analysis, and fails the build whenever the changed measured set is
non-empty and none of it was scored. It reads `codecov/patch` only as a cross-check and never lets
that status decide the build on its own.
