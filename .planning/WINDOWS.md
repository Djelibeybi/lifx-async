---
schema_version: 1
open_count: 0
waived_count: 0
fixed_count: 20
total_count: 20
last_updated: 2026-08-28T21:17:27.556Z
---

# Broken Windows Ledger

> Cross-phase defect register. With `workflow.windows_enforce` enabled, `/gsd-ship` blocks while `open_count > 0`.
> Waive with `gsd-tools windows waive <id> "<reason>"` (reason required).
> Mark fixed with `gsd-tools windows fixed <id>`.

| id | phase | kind | file | line | description | status | reason | recorded_at | resolved_at |
|----|-------|------|------|------|-------------|--------|--------|-------------|-------------|
| 1 | 10 | deviation | scripts/check_patch_coverage.py | 69 | Resolved Git to an absolute executable and documented the shell-free subprocess call after the Bandit commit hook rejected the initial implementation | fixed |  | 2026-08-27T22:24:52.871Z | 2026-08-27T22:25:16.569Z |
| 2 | 11 | deviation | tests/test_network/test_mdns/test_transport.py | 264 | Task 3 used a temporary port-5353 mutation to prove regression sensitivity because the Phase 10 transport already satisfied the new test | fixed |  | 2026-08-28T07:27:41.472Z | 2026-08-28T07:27:53.335Z |
| 3 | 11 | deviation | examples/README.md | 52 | The active example index still advertised the removed raw service-record API and was aligned with the supported device-level example. | fixed |  | 2026-08-28T08:55:09.219Z | 2026-08-28T08:55:33.726Z |
| 4 | 11 | deviation | .planning/ROADMAP.md | 266 | The roadmap state handler emitted malformed status-table spacing and stale current-position prose; execution metadata was corrected before commit. | fixed |  | 2026-08-28T08:59:18.415Z | 2026-08-28T08:59:18.583Z |
| 5 | 11 | deviation | .planning/phases/11-mdns-hardening/11-04-SUMMARY.md |  | The GSD metadata commit helper produced a signed commit without the required DCO trailer; the unpushed commit was amended with GPG signing and developer sign-off. | fixed |  | 2026-08-28T09:00:29.108Z | 2026-08-28T09:00:29.213Z |
| 6 | 11 | deviation | src/lifx/network/mdns/__init__.py |  | Temporary legacy-package mutation used to prove the Task 2 cutover regression test fails before restoration | fixed |  | 2026-08-28T09:20:32.504Z | 2026-08-28T09:20:59.364Z |
| 7 | 11 | deviation | .planning/ROADMAP.md | 266 | The roadmap state handler emitted malformed table spacing and stale current-position prose; execution metadata was corrected before commit | fixed |  | 2026-08-28T09:21:46.259Z | 2026-08-28T09:21:46.380Z |
| 8 | 11 | deviation | .planning/phases/11-mdns-hardening/11-05-SUMMARY.md |  | The GSD metadata commit helper signed the final commit but omitted the required DCO trailer; the local unpushed commit was amended with GPG signing and developer sign-off | fixed |  | 2026-08-28T09:23:01.760Z | 2026-08-28T09:23:01.871Z |
| 9 | 11 | deviation | tests/test_network/test_mdns/test_phase_contract.py |  | Controlled mutation supplied a RED proof for the test-only phase contract | fixed |  | 2026-08-28T09:55:16.263Z | 2026-08-28T09:55:58.617Z |
| 10 | 11 | deviation | scripts/check_patch_coverage.py |  | Corrected shell, source-option, and deletion-only selection defects in the planned coverage invocation | fixed |  | 2026-08-28T09:55:16.370Z | 2026-08-28T09:55:58.806Z |
| 11 | 11 | deviation | tests/test_network/test_mdns/test_discovery.py |  | Added defensive cache tests required by the immutable-base patch gate | fixed |  | 2026-08-28T09:55:16.479Z | 2026-08-28T09:55:58.958Z |
| 12 | 11 | deviation | tests/test_network/test_mdns/test_transport.py |  | Removed the conditional bypass from the mandatory loopback transport proof | fixed |  | 2026-08-28T09:55:16.582Z | 2026-08-28T09:55:59.065Z |
| 13 | 11 | deviation | .planning/phases/11-mdns-hardening/11-05-SUMMARY.md |  | Reworded a historical summary literal that falsely matched the anti-weakening scan | fixed |  | 2026-08-28T09:55:16.683Z | 2026-08-28T09:55:59.178Z |
| 14 | 11 | deviation | tests/test_network/test_mdns/test_discovery.py |  | Converted new private-range fixtures to RFC documentation addresses during privacy closure | fixed |  | 2026-08-28T09:55:16.784Z | 2026-08-28T09:55:59.306Z |
| 15 | 11 | deviation | .planning/STATE.md |  | Corrected stale Plan 11-05 prose, duplicated decision prefixes, and malformed roadmap spacing from closeout handlers | fixed |  | 2026-08-28T09:56:55.619Z | 2026-08-28T09:56:55.727Z |
| 16 | 11 | deviation | .planning/phases/11-mdns-hardening/11-06-SUMMARY.md |  | GSD closeout helper signed the metadata commit but omitted the required DCO trailer | fixed |  | 2026-08-28T09:58:42.315Z | 2026-08-28T09:58:42.437Z |
| 17 | 11 | deviation | tests/test_network/test_mdns/test_discovery.py |  | Updated two legacy fixtures to model exact LIFX service provenance | fixed |  | 2026-08-28T20:42:11.219Z | 2026-08-28T20:42:35.485Z |
| 18 | 11 | deviation | tests/test_network/test_mdns/test_discovery.py |  | Replaced a touched private-range test address with an RFC 5737 documentation address | fixed |  | 2026-08-28T20:42:11.320Z | 2026-08-28T20:42:35.592Z |
| 19 | 11 | deviation | .planning/STATE.md |  | Corrected stale Plan 2 position and gap-planning prose emitted by closeout handlers | fixed |  | 2026-08-28T20:45:00.819Z | 2026-08-28T20:45:00.933Z |
| 20 | 11 | deviation | .planning/STATE.md |  | Reconciled partial Plan 11 close-out handler updates across STATE, ROADMAP, and REQUIREMENTS | fixed |  | 2026-08-28T21:17:12.229Z | 2026-08-28T21:17:27.556Z |

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
  },
  {
    "id": 2,
    "kind": "deviation",
    "phase": "11",
    "file": "tests/test_network/test_mdns/test_transport.py",
    "line": 264,
    "description": "Task 3 used a temporary port-5353 mutation to prove regression sensitivity because the Phase 10 transport already satisfied the new test",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-28T07:27:41.472Z",
    "resolved_at": "2026-08-28T07:27:53.335Z"
  },
  {
    "id": 3,
    "kind": "deviation",
    "phase": "11",
    "file": "examples/README.md",
    "line": 52,
    "description": "The active example index still advertised the removed raw service-record API and was aligned with the supported device-level example.",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-28T08:55:09.219Z",
    "resolved_at": "2026-08-28T08:55:33.726Z"
  },
  {
    "id": 4,
    "kind": "deviation",
    "phase": "11",
    "file": ".planning/ROADMAP.md",
    "line": 266,
    "description": "The roadmap state handler emitted malformed status-table spacing and stale current-position prose; execution metadata was corrected before commit.",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-28T08:59:18.415Z",
    "resolved_at": "2026-08-28T08:59:18.583Z"
  },
  {
    "id": 5,
    "kind": "deviation",
    "phase": "11",
    "file": ".planning/phases/11-mdns-hardening/11-04-SUMMARY.md",
    "line": null,
    "description": "The GSD metadata commit helper produced a signed commit without the required DCO trailer; the unpushed commit was amended with GPG signing and developer sign-off.",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-28T09:00:29.108Z",
    "resolved_at": "2026-08-28T09:00:29.213Z"
  },
  {
    "id": 6,
    "kind": "deviation",
    "phase": "11",
    "file": "src/lifx/network/mdns/__init__.py",
    "line": null,
    "description": "Temporary legacy-package mutation used to prove the Task 2 cutover regression test fails before restoration",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-28T09:20:32.504Z",
    "resolved_at": "2026-08-28T09:20:59.364Z"
  },
  {
    "id": 7,
    "kind": "deviation",
    "phase": "11",
    "file": ".planning/ROADMAP.md",
    "line": 266,
    "description": "The roadmap state handler emitted malformed table spacing and stale current-position prose; execution metadata was corrected before commit",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-28T09:21:46.259Z",
    "resolved_at": "2026-08-28T09:21:46.380Z"
  },
  {
    "id": 8,
    "kind": "deviation",
    "phase": "11",
    "file": ".planning/phases/11-mdns-hardening/11-05-SUMMARY.md",
    "line": null,
    "description": "The GSD metadata commit helper signed the final commit but omitted the required DCO trailer; the local unpushed commit was amended with GPG signing and developer sign-off",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-28T09:23:01.760Z",
    "resolved_at": "2026-08-28T09:23:01.871Z"
  },
  {
    "id": 9,
    "kind": "deviation",
    "phase": "11",
    "file": "tests/test_network/test_mdns/test_phase_contract.py",
    "line": null,
    "description": "Controlled mutation supplied a RED proof for the test-only phase contract",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-28T09:55:16.263Z",
    "resolved_at": "2026-08-28T09:55:58.617Z"
  },
  {
    "id": 10,
    "kind": "deviation",
    "phase": "11",
    "file": "scripts/check_patch_coverage.py",
    "line": null,
    "description": "Corrected shell, source-option, and deletion-only selection defects in the planned coverage invocation",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-28T09:55:16.370Z",
    "resolved_at": "2026-08-28T09:55:58.806Z"
  },
  {
    "id": 11,
    "kind": "deviation",
    "phase": "11",
    "file": "tests/test_network/test_mdns/test_discovery.py",
    "line": null,
    "description": "Added defensive cache tests required by the immutable-base patch gate",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-28T09:55:16.479Z",
    "resolved_at": "2026-08-28T09:55:58.958Z"
  },
  {
    "id": 12,
    "kind": "deviation",
    "phase": "11",
    "file": "tests/test_network/test_mdns/test_transport.py",
    "line": null,
    "description": "Removed the conditional bypass from the mandatory loopback transport proof",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-28T09:55:16.582Z",
    "resolved_at": "2026-08-28T09:55:59.065Z"
  },
  {
    "id": 13,
    "kind": "deviation",
    "phase": "11",
    "file": ".planning/phases/11-mdns-hardening/11-05-SUMMARY.md",
    "line": null,
    "description": "Reworded a historical summary literal that falsely matched the anti-weakening scan",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-28T09:55:16.683Z",
    "resolved_at": "2026-08-28T09:55:59.178Z"
  },
  {
    "id": 14,
    "kind": "deviation",
    "phase": "11",
    "file": "tests/test_network/test_mdns/test_discovery.py",
    "line": null,
    "description": "Converted new private-range fixtures to RFC documentation addresses during privacy closure",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-28T09:55:16.784Z",
    "resolved_at": "2026-08-28T09:55:59.306Z"
  },
  {
    "id": 15,
    "kind": "deviation",
    "phase": "11",
    "file": ".planning/STATE.md",
    "line": null,
    "description": "Corrected stale Plan 11-05 prose, duplicated decision prefixes, and malformed roadmap spacing from closeout handlers",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-28T09:56:55.619Z",
    "resolved_at": "2026-08-28T09:56:55.727Z"
  },
  {
    "id": 16,
    "kind": "deviation",
    "phase": "11",
    "file": ".planning/phases/11-mdns-hardening/11-06-SUMMARY.md",
    "line": null,
    "description": "GSD closeout helper signed the metadata commit but omitted the required DCO trailer",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-28T09:58:42.315Z",
    "resolved_at": "2026-08-28T09:58:42.437Z"
  },
  {
    "id": 17,
    "kind": "deviation",
    "phase": "11",
    "file": "tests/test_network/test_mdns/test_discovery.py",
    "line": null,
    "description": "Updated two legacy fixtures to model exact LIFX service provenance",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-28T20:42:11.219Z",
    "resolved_at": "2026-08-28T20:42:35.485Z"
  },
  {
    "id": 18,
    "kind": "deviation",
    "phase": "11",
    "file": "tests/test_network/test_mdns/test_discovery.py",
    "line": null,
    "description": "Replaced a touched private-range test address with an RFC 5737 documentation address",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-28T20:42:11.320Z",
    "resolved_at": "2026-08-28T20:42:35.592Z"
  },
  {
    "id": 19,
    "kind": "deviation",
    "phase": "11",
    "file": ".planning/STATE.md",
    "line": null,
    "description": "Corrected stale Plan 2 position and gap-planning prose emitted by closeout handlers",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-28T20:45:00.819Z",
    "resolved_at": "2026-08-28T20:45:00.933Z"
  },
  {
    "id": 20,
    "kind": "deviation",
    "phase": "11",
    "file": ".planning/STATE.md",
    "line": null,
    "description": "Reconciled partial Plan 11 close-out handler updates across STATE, ROADMAP, and REQUIREMENTS",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-28T21:17:12.229Z",
    "resolved_at": "2026-08-28T21:17:27.556Z"
  }
]
````
