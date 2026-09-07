# Phase 15 API Capability Coverage

**Scope:** the only external service this phase touches is the GitHub REST API, read through the
`gh` CLI by `.github/patch_coverage_guard.py` as a cross-check that can never decide the build
(SPEC R4), plus two one-off issue writes performed by hand under an operator checkpoint (SPEC R5).
Everything else in the phase is local: file relocation, pytest collection policy, coverage
configuration, and a local process observation.

Codecov's own API is deliberately **not** integrated. The guard computes both sides of its
comparison from the repository's own data precisely because the component most likely to have
failed on PR #208 is the one that would otherwise be trusted.

## Capability matrix

The matrix carries the three columns the `api-coverage` gate parses, `capability`, `decision` and
`reason`, with each capability's endpoint or command named at the head of its reason. An earlier
revision split the endpoint into a fourth column, which the parser reads as the decision, so every
row failed validation despite carrying a valid disposition.

| Capability | Decision | Reason |
|---|---|---|
| Read a commit's combined status | INTEGRATE | `GET /repos/{owner}/{repo}/commits/{sha}/status` via `gh api`. The `codecov/patch` cross-check. Bounded wait, four reporting outcomes, never affects the exit code. |
| Post an issue comment | INTEGRATE | `gh issue comment`. SPEC R5's #209 correction and SPEC R3's #214 closing reasoning. Body supplied from a file so the published text matches the approved text. |
| Close an issue | INTEGRATE | `gh issue close`. #214 is closed on the CI-01 reversal reasoning. |
| Create a commit status | OPT-OUT | `POST /repos/{owner}/{repo}/statuses/{sha}`. The guard fails the job directly. Its own status check would be a second gate to keep in sync with branch protection. |
| Read the pull request diff | OPT-OUT | `gh pr diff` or `GET /repos/{owner}/{repo}/pulls/{n}/files`. SPEC R4 wants the changed set from the repository's own merge-base diff; the GitHub fetch is the #208 suspect. |
| Read Codecov's own API | OPT-OUT | Codecov reports and statuses read directly. Out of scope by SPEC. The guard is cause-agnostic and treats Codecov's report of itself as evidence, not as input to the decision. |
| Check-run annotations | OPT-OUT | `POST /repos/{owner}/{repo}/check-runs`. The guard prints its counts to the job log and fails the step. Annotations would need `checks: write`, widening the job's token scope for presentation only. |
| List or modify branch protection | OPT-OUT | `GET/PUT /repos/{owner}/{repo}/branches/{branch}/protection`. Promoting a coverage tool to a required status check was considered and declined during the spec interview. |
| Workflow dispatch or re-run | OPT-OUT | `gh workflow run` and `gh run rerun`. Nothing in the phase triggers or re-triggers CI programmatically. |

## Token scope

The guard needs `statuses: read` in addition to the workflow's default `contents: read`. It needs
no write scope of any kind, and it prints only the status entry's context, state and description,
never the environment or a token.
