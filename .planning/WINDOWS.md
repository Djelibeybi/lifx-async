---
schema_version: 1
open_count: 0
waived_count: 0
fixed_count: 41
total_count: 41
last_updated: 2026-08-30T21:40:23.059Z
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
| 21 | 12 | deviation | src/lifx/network/transport.py |  | Windows asyncio requires canonical four-field IPv6 datagram destinations | fixed |  | 2026-08-29T11:02:38.890Z | 2026-08-29T11:03:01.137Z |
| 22 | 13 | deviation | tests/test_api/test_api_discovery.py |  | Corrected obsolete discovery-default expectations in the initial RED test before committing the entry gate | fixed |  | 2026-08-30T14:53:37.103Z | 2026-08-30T14:54:14.206Z |
| 23 | 13 | deviation | .planning/STATE.md |  | Reconciled stale plan activity text, metric spacing, and roadmap table spacing emitted by closeout handlers | fixed |  | 2026-08-30T14:55:32.193Z | 2026-08-30T14:55:36.654Z |
| 24 | 13 | deviation | .planning/phases/13-merged-discovery/13-01-SUMMARY.md |  | The GSD metadata commit helper signed the final commit but omitted the required DCO trailer | fixed |  | 2026-08-30T14:56:26.541Z | 2026-08-30T14:56:26.647Z |
| 25 | 13 | deviation | src/lifx/network/discovery_coordinator.py |  | Concurrent coordinator starters now wait for the shared readiness handshake | fixed |  | 2026-08-30T15:28:36.249Z | 2026-08-30T15:29:05.624Z |
| 26 | 13 | deviation | src/lifx/network/discovery_coordinator.py |  | Idle-stop requests are coalesced and shutdown tolerates concurrent loop closure | fixed |  | 2026-08-30T15:28:36.355Z | 2026-08-30T15:29:05.733Z |
| 27 | 13 | deviation | tests/test_network/test_discovery_coordinator.py |  | Late-subscriber tests await replay receipt instead of assuming registration timing | fixed |  | 2026-08-30T15:28:36.461Z | 2026-08-30T15:29:05.840Z |
| 28 | 13 | deviation | .planning/STATE.md | 11 | Reconciled stale activity prose, duplicated decision prefixes, and malformed roadmap spacing emitted by closeout handlers | fixed |  | 2026-08-30T15:29:44.020Z | 2026-08-30T15:29:44.128Z |
| 29 | 13 | deviation | .planning/phases/13-merged-discovery/13-02-SUMMARY.md | 190 | Restored the mandatory DCO trailer omitted by the GSD metadata commit helper | fixed |  | 2026-08-30T15:31:50.928Z | 2026-08-30T15:31:54.973Z |
| 30 | 13 | deviation | src/lifx/network/mdns/discovery.py |  | Restored the context-manager transport seam required by adjacent mDNS compatibility tests. | fixed |  | 2026-08-30T16:00:48.566Z | 2026-08-30T16:01:16.820Z |
| 31 | 13 | unrun-verify | tests/test_network/test_discovery_coordinator.py |  | Whole-suite assertions pass, but pytest cannot exit because a pre-existing coordinator test leaves Event.wait blocked in a default-executor worker. | fixed |  | 2026-08-30T16:00:48.571Z | 2026-08-30T16:11:10.722Z |
| 32 | 13 | deviation | src/lifx/devices/light.py |  | Generated StateColor label typing required an explicit decoded-string cast at the private adoption boundary. | fixed |  | 2026-08-30T16:01:12.272Z | 2026-08-30T16:01:17.013Z |
| 33 | 13 | deviation | .planning/STATE.md |  | Reconciled stale Plan 13-02 activity prose, realised duration, and malformed roadmap spacing emitted by closeout handlers. | fixed |  | 2026-08-30T16:03:27.690Z | 2026-08-30T16:03:27.879Z |
| 34 | 13 | deviation | .planning/phases/13-merged-discovery/13-03-SUMMARY.md |  | Restored the mandatory DCO trailer omitted by the GSD metadata commit helper. | fixed |  | 2026-08-30T16:04:12.129Z | 2026-08-30T16:04:12.329Z |
| 35 | 13 | deviation | src/lifx/network/discovery_observation.py |  | Private source seams expanded to carry the exact merged deadline and observation dispositions. | fixed |  | 2026-08-30T16:34:19.049Z | 2026-08-30T16:34:39.092Z |
| 36 | 13 | deviation | .planning/STATE.md |  | Reconciled stale Plan 13-03 activity prose, duration spacing, and malformed roadmap spacing emitted by closeout handlers. | fixed |  | 2026-08-30T16:35:21.465Z | 2026-08-30T16:35:24.958Z |
| 37 | 13 | deviation | .planning/phases/13-merged-discovery/13-04-SUMMARY.md |  | Restored the mandatory DCO trailer omitted by the GSD metadata commit helper. | fixed |  | 2026-08-30T16:36:03.962Z | 2026-08-30T16:36:07.092Z |
| 38 | 13 | deviation | src/lifx/api.py |  | Held winning source pumps at the yield boundary so aggregate cleanup cannot interrupt async generator finalisers. | fixed |  | 2026-08-30T16:56:28.695Z | 2026-08-30T16:56:52.937Z |
| 39 | 13 | deviation | .planning/STATE.md |  | Reconciled stale Plan 13-04 activity prose, duration spacing, and malformed roadmap spacing emitted by closeout handlers. | fixed |  | 2026-08-30T16:58:47.096Z | 2026-08-30T16:58:52.188Z |
| 40 | 13 | deviation | .planning/phases/13-merged-discovery/13-05-SUMMARY.md |  | Restored the mandatory DCO trailer omitted by the GSD metadata commit helper. | fixed |  | 2026-08-30T16:59:36.117Z | 2026-08-30T16:59:39.218Z |
| 41 | 13 | deviation | .planning/phases/13-merged-discovery/13-06-PLAN.md |  | Phase 13-specific CI measurement was replaced by exact-head ordinary CI qualification followed by executor-run hermetic evidence | fixed |  | 2026-08-30T21:39:56.701Z | 2026-08-30T21:40:23.059Z |

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
  },
  {
    "id": 21,
    "kind": "deviation",
    "phase": "12",
    "file": "src/lifx/network/transport.py",
    "line": null,
    "description": "Windows asyncio requires canonical four-field IPv6 datagram destinations",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-29T11:02:38.890Z",
    "resolved_at": "2026-08-29T11:03:01.137Z"
  },
  {
    "id": 22,
    "kind": "deviation",
    "phase": "13",
    "file": "tests/test_api/test_api_discovery.py",
    "line": null,
    "description": "Corrected obsolete discovery-default expectations in the initial RED test before committing the entry gate",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-30T14:53:37.103Z",
    "resolved_at": "2026-08-30T14:54:14.206Z"
  },
  {
    "id": 23,
    "kind": "deviation",
    "phase": "13",
    "file": ".planning/STATE.md",
    "line": null,
    "description": "Reconciled stale plan activity text, metric spacing, and roadmap table spacing emitted by closeout handlers",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-30T14:55:32.193Z",
    "resolved_at": "2026-08-30T14:55:36.654Z"
  },
  {
    "id": 24,
    "kind": "deviation",
    "phase": "13",
    "file": ".planning/phases/13-merged-discovery/13-01-SUMMARY.md",
    "line": null,
    "description": "The GSD metadata commit helper signed the final commit but omitted the required DCO trailer",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-30T14:56:26.541Z",
    "resolved_at": "2026-08-30T14:56:26.647Z"
  },
  {
    "id": 25,
    "kind": "deviation",
    "phase": "13",
    "file": "src/lifx/network/discovery_coordinator.py",
    "line": null,
    "description": "Concurrent coordinator starters now wait for the shared readiness handshake",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-30T15:28:36.249Z",
    "resolved_at": "2026-08-30T15:29:05.624Z"
  },
  {
    "id": 26,
    "kind": "deviation",
    "phase": "13",
    "file": "src/lifx/network/discovery_coordinator.py",
    "line": null,
    "description": "Idle-stop requests are coalesced and shutdown tolerates concurrent loop closure",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-30T15:28:36.355Z",
    "resolved_at": "2026-08-30T15:29:05.733Z"
  },
  {
    "id": 27,
    "kind": "deviation",
    "phase": "13",
    "file": "tests/test_network/test_discovery_coordinator.py",
    "line": null,
    "description": "Late-subscriber tests await replay receipt instead of assuming registration timing",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-30T15:28:36.461Z",
    "resolved_at": "2026-08-30T15:29:05.840Z"
  },
  {
    "id": 28,
    "kind": "deviation",
    "phase": "13",
    "file": ".planning/STATE.md",
    "line": 11,
    "description": "Reconciled stale activity prose, duplicated decision prefixes, and malformed roadmap spacing emitted by closeout handlers",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-30T15:29:44.020Z",
    "resolved_at": "2026-08-30T15:29:44.128Z"
  },
  {
    "id": 29,
    "kind": "deviation",
    "phase": "13",
    "file": ".planning/phases/13-merged-discovery/13-02-SUMMARY.md",
    "line": 190,
    "description": "Restored the mandatory DCO trailer omitted by the GSD metadata commit helper",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-30T15:31:50.928Z",
    "resolved_at": "2026-08-30T15:31:54.973Z"
  },
  {
    "id": 30,
    "kind": "deviation",
    "phase": "13",
    "file": "src/lifx/network/mdns/discovery.py",
    "line": null,
    "description": "Restored the context-manager transport seam required by adjacent mDNS compatibility tests.",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-30T16:00:48.566Z",
    "resolved_at": "2026-08-30T16:01:16.820Z"
  },
  {
    "id": 31,
    "kind": "unrun-verify",
    "phase": "13",
    "file": "tests/test_network/test_discovery_coordinator.py",
    "line": null,
    "description": "Whole-suite assertions pass, but pytest cannot exit because a pre-existing coordinator test leaves Event.wait blocked in a default-executor worker.",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-30T16:00:48.571Z",
    "resolved_at": "2026-08-30T16:11:10.722Z"
  },
  {
    "id": 32,
    "kind": "deviation",
    "phase": "13",
    "file": "src/lifx/devices/light.py",
    "line": null,
    "description": "Generated StateColor label typing required an explicit decoded-string cast at the private adoption boundary.",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-30T16:01:12.272Z",
    "resolved_at": "2026-08-30T16:01:17.013Z"
  },
  {
    "id": 33,
    "kind": "deviation",
    "phase": "13",
    "file": ".planning/STATE.md",
    "line": null,
    "description": "Reconciled stale Plan 13-02 activity prose, realised duration, and malformed roadmap spacing emitted by closeout handlers.",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-30T16:03:27.690Z",
    "resolved_at": "2026-08-30T16:03:27.879Z"
  },
  {
    "id": 34,
    "kind": "deviation",
    "phase": "13",
    "file": ".planning/phases/13-merged-discovery/13-03-SUMMARY.md",
    "line": null,
    "description": "Restored the mandatory DCO trailer omitted by the GSD metadata commit helper.",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-30T16:04:12.129Z",
    "resolved_at": "2026-08-30T16:04:12.329Z"
  },
  {
    "id": 35,
    "kind": "deviation",
    "phase": "13",
    "file": "src/lifx/network/discovery_observation.py",
    "line": null,
    "description": "Private source seams expanded to carry the exact merged deadline and observation dispositions.",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-30T16:34:19.049Z",
    "resolved_at": "2026-08-30T16:34:39.092Z"
  },
  {
    "id": 36,
    "kind": "deviation",
    "phase": "13",
    "file": ".planning/STATE.md",
    "line": null,
    "description": "Reconciled stale Plan 13-03 activity prose, duration spacing, and malformed roadmap spacing emitted by closeout handlers.",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-30T16:35:21.465Z",
    "resolved_at": "2026-08-30T16:35:24.958Z"
  },
  {
    "id": 37,
    "kind": "deviation",
    "phase": "13",
    "file": ".planning/phases/13-merged-discovery/13-04-SUMMARY.md",
    "line": null,
    "description": "Restored the mandatory DCO trailer omitted by the GSD metadata commit helper.",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-30T16:36:03.962Z",
    "resolved_at": "2026-08-30T16:36:07.092Z"
  },
  {
    "id": 38,
    "kind": "deviation",
    "phase": "13",
    "file": "src/lifx/api.py",
    "line": null,
    "description": "Held winning source pumps at the yield boundary so aggregate cleanup cannot interrupt async generator finalisers.",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-30T16:56:28.695Z",
    "resolved_at": "2026-08-30T16:56:52.937Z"
  },
  {
    "id": 39,
    "kind": "deviation",
    "phase": "13",
    "file": ".planning/STATE.md",
    "line": null,
    "description": "Reconciled stale Plan 13-04 activity prose, duration spacing, and malformed roadmap spacing emitted by closeout handlers.",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-30T16:58:47.096Z",
    "resolved_at": "2026-08-30T16:58:52.188Z"
  },
  {
    "id": 40,
    "kind": "deviation",
    "phase": "13",
    "file": ".planning/phases/13-merged-discovery/13-05-SUMMARY.md",
    "line": null,
    "description": "Restored the mandatory DCO trailer omitted by the GSD metadata commit helper.",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-30T16:59:36.117Z",
    "resolved_at": "2026-08-30T16:59:39.218Z"
  },
  {
    "id": 41,
    "kind": "deviation",
    "phase": "13",
    "file": ".planning/phases/13-merged-discovery/13-06-PLAN.md",
    "line": null,
    "description": "Phase 13-specific CI measurement was replaced by exact-head ordinary CI qualification followed by executor-run hermetic evidence",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-30T21:39:56.701Z",
    "resolved_at": "2026-08-30T21:40:23.059Z"
  }
]
````
