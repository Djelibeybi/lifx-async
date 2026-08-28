---
schema_version: 1
open_count: 0
waived_count: 0
fixed_count: 1
total_count: 1
last_updated: 2026-08-27T22:25:16.569Z
---

# Broken Windows Ledger

> Cross-phase defect register. With `workflow.windows_enforce` enabled, `/gsd-ship` blocks while `open_count > 0`.
> Waive with `gsd-tools windows waive <id> "<reason>"` (reason required).
> Mark fixed with `gsd-tools windows fixed <id>`.

| id | phase | kind | file | line | description | status | reason | recorded_at | resolved_at |
|----|-------|------|------|------|-------------|--------|--------|-------------|-------------|
| 1 | 10 | deviation | scripts/check_patch_coverage.py | 69 | Resolved Git to an absolute executable and documented the shell-free subprocess call after the Bandit commit hook rejected the initial implementation | fixed |  | 2026-08-27T22:24:52.871Z | 2026-08-27T22:25:16.569Z |

````json
[
  {
    "id": 1,
    "kind": "deviation",
    "phase": "10",
    "file": "scripts/check_patch_coverage.py",
    "line": 69,
    "description": "Resolved Git to an absolute executable and documented the shell-free subprocess call after the Bandit commit hook rejected the initial implementation",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-27T22:24:52.871Z",
    "resolved_at": "2026-08-27T22:25:16.569Z"
  }
]
````
