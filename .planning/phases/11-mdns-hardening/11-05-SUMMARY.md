---
phase: 11-mdns-hardening
plan: 05
subsystem: networking
tags: [mdns, public-api, private-api, connectivity, regression-testing]

requires:
  - phase: 11-mdns-hardening
    plan: 03
    provides: hardened per-call discovery, record assembly, and connectivity propagation
  - phase: 11-mdns-hardening
    plan: 04
    provides: device-level public mDNS documentation with raw record guidance removed
provides:
  - Private raw mDNS record and discovery-generator symbols in their defining modules
  - Supported record-to-device factory retained as an explicit mDNS package export
  - Internal probe and test consumers migrated to the private defining-module symbols
  - Regression coverage for package exports and all six supported device classes across WiFi and Thread
affects: [11-06, phase-13-merged-discovery, phase-14-thread-revalidation-and-docs]

actuals:
  tokens: 16172
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - Private raw discovery data stays importable only from its defining module
    - Public mDNS conversion remains available independently of raw record package exports
    - Package-surface regressions are checked through both __all__ and runtime attributes

key-files:
  created: []
  modified:
    - src/lifx/network/mdns/types.py
    - src/lifx/network/mdns/discovery.py
    - src/lifx/network/mdns/__init__.py
    - src/lifx/__init__.py
    - scripts/ipv6_thread_probe.py
    - tests/test_network/test_mdns/test_discovery.py
    - tests/test_api/test_api_discovery.py
    - tests/test_scripts/test_ipv6_thread_probe.py

key-decisions:
  - "None - followed the locked cutover scope: internalise only the raw record and generator while retaining create_device_from_record, discover_devices_mdns(), and lifx.api.discover_mdns()."

patterns-established:
  - "Internal consumers import _LifxServiceRecord and _discover_lifx_services directly from their defining modules, never through package re-exports."
  - "API cutover tests reject both legacy public names and private replacements on the lifx and lifx.network.mdns package surfaces."

requirements-completed: [MDNS-02, MDNS-08]

coverage:
  - id: C1
    description: "Raw record and discovery-generator names are absent from both public package surfaces while create_device_from_record remains exported and callable."
    requirement: MDNS-08
    verification:
      - kind: test
        ref: "TestMdnsPublicSurface"
        status: pass
      - kind: other
        ref: "runtime import and __all__ assertion"
        status: pass
    human_judgment: false
  - id: C2
    description: "The retained factory selects plain, infrared, HEV, multizone, matrix, and ceiling device classes while preserving WiFi or Thread connectivity."
    requirement: MDNS-02
    verification:
      - kind: test
        ref: "TestCreateDeviceFromRecord::test_device_class_lattice_preserves_connectivity"
        status: pass
    human_judgment: false
  - id: C3
    description: "All internal discovery, high-level API, and probe paths use the private defining-module symbols without behavioural regression."
    requirement: MDNS-08
    verification:
      - kind: test
        ref: "392-test focused mDNS/device/API/probe suite"
        status: pass
      - kind: test
        ref: "3850-test repository-wide frozen suite"
        status: pass
    human_judgment: false

duration: 15 min
completed: 2026-08-28
status: complete
---

# Phase 11 Plan 05: Deliberate mDNS API Cutover Summary

**Raw mDNS records and the record-yielding generator are now private implementation details, while the supported device discovery APIs and separately exported record-to-device factory retain full class and connectivity behaviour.**

## Performance

- **Duration:** 15 min
- **Started:** 2026-08-28T09:04:24Z
- **Completed:** 2026-08-28T09:19:02Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments

- Renamed the raw record to `_LifxServiceRecord` and the record-yielding generator to `_discover_lifx_services`, removing both legacy names and both private replacements from the `lifx` and `lifx.network.mdns` package surfaces.
- Preserved `create_device_from_record` at its existing location and mDNS package export, together with `discover_devices_mdns()` and `lifx.api.discover_mdns()` as supported device-level paths.
- Migrated the IPv6/Thread probe and all affected tests to direct defining-module imports without running or changing live network or hardware state.
- Added package-surface regression assertions and a 12-case matrix covering all six supported concrete light classes under both WiFi and Thread connectivity.

## Task Commits

Each task was committed atomically with GPG signature and DCO sign-off:

1. **Task 1: Internalise raw discovery symbols and migrate the probe**
   - `2a217aa` — `feat(mdns): internalise raw discovery symbols`
2. **Task 2: Migrate tests and prove the deliberate API cutover**
   - `c2811a1` — `test(mdns): prove private discovery cutover`

## Files Created/Modified

- `src/lifx/network/mdns/types.py` — Private raw service-record class.
- `src/lifx/network/mdns/discovery.py` — Private record generator, internal call sites, annotations, and diagnostics; supported factory unchanged.
- `src/lifx/network/mdns/__init__.py` — Narrow package exports retaining device discovery and the record-to-device factory.
- `src/lifx/__init__.py` — Removed legacy raw mDNS names from the top-level package.
- `scripts/ipv6_thread_probe.py` — Direct imports of private defining-module symbols.
- `tests/test_network/test_mdns/test_discovery.py` — Private-symbol migration, package-surface assertions, and class/connectivity matrix.
- `tests/test_api/test_api_discovery.py` — High-level discovery mocks patched through the private generator.
- `tests/test_scripts/test_ipv6_thread_probe.py` — Probe fixtures migrated to the private record type.

## Decisions Made

None - followed the locked Phase 11 cutover boundary: only the raw record and generator were internalised; the separately supported conversion factory and device-level discovery APIs remain public.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Proved the Task 2 cutover assertion with a temporary mutation**
- **Found during:** Task 2 TDD RED gate
- **Issue:** Task 1 necessarily completed the source cutover before the test-only Task 2 migration, so the new export assertion could not fail naturally against the intended implementation.
- **Fix:** Temporarily restored one legacy package attribute, confirmed the new regression test failed for that exact surface leak, then removed the mutation before the green run and commit.
- **Files modified:** `src/lifx/network/mdns/__init__.py` temporarily; no mutation remained in the committed diff.
- **Verification:** The mutation run failed on `hasattr(mdns, "discover_lifx_services")`; after restoration, all 14 package-surface and class-matrix cases passed.
- **Committed in:** No persistent mutation; regression coverage committed in `c2811a1`.

**2. [Rule 1 - Bug] Corrected generated execution-state prose**
- **Found during:** Final state and roadmap update
- **Issue:** The state handlers advanced the counters but retained Plan 11-04 in human-readable current-position fields and emitted malformed roadmap table spacing.
- **Fix:** Aligned the current status, activity, operator next step, and roadmap row with completed Plan 11-05 and upcoming Plan 11-06.
- **Files modified:** `.planning/STATE.md`, `.planning/ROADMAP.md`
- **Verification:** State reports Plan 6 of 6 with Plan 11-05 complete; the roadmap reports 5/6 with a valid table row.
- **Committed in:** Final plan metadata commit.

**3. [Rule 1 - Bug] Restored the required DCO trailer on the metadata commit**
- **Found during:** Final commit signature and trailer verification
- **Issue:** The GSD commit helper signed the metadata commit but omitted the repository-mandated developer sign-off.
- **Fix:** Amended the local, unpushed metadata commit with both `-S` and `-s`, preserving the required `11-05` message.
- **Files modified:** Final commit metadata only.
- **Verification:** `git verify-commit` passes and the final commit body contains the `Signed-off-by` trailer.
- **Committed in:** Final plan metadata commit.

---

**Total deviations:** 3 auto-fixed issues (1 blocking TDD issue, 2 execution/tooling bugs).
**Impact on plan:** The mutation supplied a valid RED proof for the test-only migration without changing the final source scope or commit history; the metadata corrections keep the execution record accurate and policy-compliant.

## Issues Encountered

- The managed sandbox could not access the existing uv cache or Git/GPG state. Approved execution used the established project cache and signing key; no dependency, lockfile, remote, hardware, or network state changed.
- The full suite emitted seven expected `UdpTransport.receive_many()` deprecation warnings from tests that deliberately exercise the deprecated compatibility method; all tests passed and no new warning source was introduced.

## Known Stubs

None. The conditional skip branches already present in emulator-backed API tests were not introduced or taken by this plan.

## Verification

- TDD mutation RED: the new package-surface assertion failed when a legacy mDNS attribute was deliberately restored.
- TDD GREEN: 14 package-surface and six-class/two-connectivity cases passed.
- `uv run --frozen pytest tests/test_network/test_mdns tests/test_devices/test_base.py tests/test_api/test_api_discovery.py tests/test_scripts/test_ipv6_thread_probe.py -q` passed: 392 tests.
- `uv run --frozen pytest -q` passed: 3,850 tests, 12 deselected, seven expected deprecation warnings.
- `uv run --frozen pyright` passed with zero errors and zero warnings.
- Ruff check and format verification passed for all modified source, probe, and test files.
- The runtime import contract confirms both legacy raw names and both private replacements are absent from `lifx` and `lifx.network.mdns`, while `create_device_from_record` remains exported and callable.
- Active-path symbol audit found no legacy import, definition, patch target, or consumer; the only unprefixed legacy spellings are negative-test string literals.
- The staged privacy audit found only documentation-range or pre-existing synthetic test fixtures and no live identifiers or raw discovery output.
- Both task commits and the final metadata commit have good signatures from the required GPG key and contain developer sign-off.
- Stub scan found no introduced placeholder, TODO, FIXME, skipped test, or unwired data source.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 11-06 can enforce the final private/public symbol, documentation, lint, typing, and full-suite contracts against the completed cutover.
- The supported `discover_mdns()` path, `Device.connectivity`, and `create_device_from_record` remain ready for downstream merged-discovery and Thread revalidation work.
- No blockers; live hardware, multicast routing, daemons, external services, push, merge, and deployment were not used or changed.

## Self-Check: PASSED

- All eight implementation/test files and this summary exist.
- Task commits `2a217aa` and `c2811a1` are present in repository history.

---
*Phase: 11-mdns-hardening*
*Completed: 2026-08-28*
