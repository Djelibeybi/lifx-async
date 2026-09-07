---
phase: 16-mdns-correctness-docs-and-test-hygiene
plan: 04
subsystem: test-hygiene
tags: [ruff, plc0415, imports, lint-config, pytest]

requires:
  - phase: 16-01
    provides: "Post-fix _LifxRecordCache (test_discovery.py already carries its 16-01-added test class and imports at the moment this plan swept the file)"
  - phase: 16-02
    provides: "tests/test_docs_language.py (new module, in scope for the PLC0415 rule though outside the plan's 27-file sweep list; audited and found already import-clean)"
provides:
  - "166 function-local imports hoisted to module scope across 27 files under tests/, in one mechanical commit"
  - "tests/test_packaging.py's version-gated import tomllib replaced with a module-scope try/except over the existing tomli dev dependency, gaining Python 3.10 coverage instead of needing a suppression"
  - "PLC0415 enabled in ruff's select list with seven per-file-ignore entries (src/**, .planning/**, tests/test_animation/**, tests/test_theme/**, tests/test_devices/test_multizone.py, .agents/skills/**, .claude/skills/**), each a visible line naming the phase that deletes it"
affects: [18, 19, 20]

actuals:
  tokens: 19000
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - "Module-scope try/except stdlib-with-backport compatibility import (tomllib / tomli), removing a version skip rather than adding a suppression"
    - "Per-file-ignore as a visible, deletable handoff line naming the owning phase, extending D-05's five-entry design to seven after measuring two extra archived-spike violations"

key-files:
  modified:
    - tests/conftest.py
    - tests/test_api/test_api_apply_theme.py
    - tests/test_api/test_api_discovery.py
    - tests/test_api/test_api_organization.py
    - tests/test_devices/test_base.py
    - tests/test_devices/test_ceiling.py
    - tests/test_devices/test_light.py
    - tests/test_devices/test_matrix.py
    - tests/test_devices/test_state_ceiling.py
    - tests/test_devices/test_state_hev.py
    - tests/test_devices/test_state_infrared.py
    - tests/test_devices/test_state_light.py
    - tests/test_devices/test_state_management.py
    - tests/test_effects/test_conductor.py
    - tests/test_effects/test_integration.py
    - tests/test_effects/test_plasma2d.py
    - tests/test_effects/test_registry.py
    - tests/test_network/test_concurrent_requests.py
    - tests/test_network/test_connection.py
    - tests/test_network/test_connection_retry.py
    - tests/test_network/test_discovery_devices.py
    - tests/test_network/test_discovery_errors.py
    - tests/test_network/test_mdns/test_discovery.py
    - tests/test_network/test_mdns/test_dns.py
    - tests/test_network/test_mdns/test_transport.py
    - tests/test_packaging.py
    - tests/test_protocol/test_protocol_generator.py
    - pyproject.toml

key-decisions:
  - "The pre-sweep ruff inventory measured 166 violations across exactly 27 files, an exact match to the plan's spec-locked figure with no delta from plans 16-01/16-02 having added test code — the mDNS test module's 16-01-added test class and imports introduced zero new PLC0415 sites."
  - "No function-local import in this sweep needed retention. Every one of the 166 sites was safely hoistable: several were outright duplicates of an already-imported name (removed rather than re-added), the rest had no circular-import, patching, or collection-time constraint. Zero noqa: PLC0415 marks exist under tests/ after this plan."
  - "tests/test_ceiling.py's two `import lifx.devices.matrix as matrix_module` sites were resolved by using the module's already-imported `MatrixLight` name directly (`from lifx.devices.matrix import MatrixLight` already existed at module scope) rather than adding a second, redundant module-scope import — the class object is identical either way, so the __aenter__ monkeypatch-and-restore behaviour in both tests is unchanged."
  - "tests/test_packaging.py's function-local `import tomllib`, gated behind a `sys.version_info < (3, 11)` skip, was resolved per the plan's Step 3a: a module-scope `try: import tomllib / except ModuleNotFoundError: import tomli as tomllib` block over the tomli>=2.0.1 dev dependency already declared at pyproject.toml:57. The skip, and the now-unused `sys` and `pytest` imports it required, were deleted. This gains Python 3.10 coverage for `test_pyproject_declares_no_runtime_dependencies` rather than needing a suppression."
  - "D-05's seven-entry per-file-ignore list (the FLAGGED section's resolution, extending the five-entry count) was accepted as measured and applied without change: no operator objection was raised, and the resolution was already the plan's default absent a stated alternative."
  - "Task 1's decisive verify block includes a check, `grep -qE '^[[:space:]]+import tomllib' tests/test_packaging.py`, that is self-contradicting for any ruff-format-compliant implementation of the plan's own mandated Step 3a shape: ruff format always expands `try: import tomllib` onto an indented line, so the check's FUNCTION-LOCAL-TOMLLIB-REMAINS branch fires on the module-scope try/except block the plan itself specifies, not only on a genuine function-local import. Verified empirically: reformatting a synthetic try/except with `ruff format` always produces an indented `import tomllib` line. The check is a plan-authoring bug (Rule 1), not an implementation defect — confirmed by direct inspection that the import sits inside a top-level `try:` (not inside any `def`), and by every other criterion in the same verify block passing: no version skip, no bare noqa, exactly two test functions, and both `uv run --frozen pytest tests/test_packaging.py -q` (2 passed) and the full-suite run staying green."

requirements-completed: [TEST-01]

coverage:
  - id: D1
    description: "166 function-local imports across 27 files under tests/ (excluding tests/test_animation/, tests/test_devices/test_multizone.py and tests/test_theme/) moved to module scope in one mechanical commit, with the collected pytest node-ID set unchanged"
    requirement: TEST-01
    verification:
      - kind: other
        ref: "shell: uv run --frozen ruff check --no-cache --select PLC0415 tests/ --exclude tests/test_animation --exclude tests/test_theme --exclude tests/test_devices/test_multizone.py (0 violations, exit 0)"
        status: pass
      - kind: integration
        ref: "shell: node-ID set comparison, pre-sweep vs post-sweep collect-only (4272 == 4272, zero lost)"
        status: pass
      - kind: integration
        ref: "shell: uv run --frozen pytest -q (4272 passed, 631 deselected)"
        status: pass
    human_judgment: false
  - id: D2
    description: "tests/test_packaging.py's Python 3.10 version skip replaced by a module-scope tomli/tomllib compatibility import, gaining coverage rather than adding a suppression"
    requirement: TEST-01
    verification:
      - kind: unit
        ref: "shell: uv run --frozen pytest tests/test_packaging.py -q (2 passed, no skip)"
        status: pass
    human_judgment: false
  - id: D3
    description: "PLC0415 enabled in ruff's select list with exactly seven per-file-ignore entries, each proven to fire on an in-scope synthetic path and suppress on its own ignored path; the sweep and the configuration change are separate commits"
    requirement: TEST-01
    verification:
      - kind: other
        ref: "shell: positive-control probe (synthetic function-local import under tests/, exit 1, PLC0415 reported)"
        status: pass
      - kind: other
        ref: "shell: negative-control probe over all seven ignored paths (exit 0, no PLC0415, for each)"
        status: pass
      - kind: other
        ref: "shell: config-shape gate (select entry count 1, ignore entry count 7, E501 entry count 5)"
        status: pass
      - kind: integration
        ref: "shell: uv run --frozen ruff check . && uv run --frozen ruff format --check . && uv run --frozen pyright (all clean) && uv run --frozen pytest -q (4272 passed)"
        status: pass
    human_judgment: false

duration: 24min
completed: 2026-09-07
status: complete
---

# Phase 16 Plan 04: Module-scope test imports and the PLC0415 lint gate Summary

**Closed TEST-01 by hoisting all 166 function-local imports across 27 test files to module scope in one mechanical commit, resolving `tests/test_packaging.py`'s Python 3.10 skip with a `tomli`/`tomllib` compatibility import, then enabling ruff's `PLC0415` rule in a separate later commit with seven per-file-ignore handoff lines to Phases 18, 19 and a future sweep.**

## Performance

- **Duration:** 24 min
- **Started:** 2026-09-07T17:34:00+10:00 (approximate, following 16-03)
- **Completed:** 2026-09-07T17:58:03+10:00
- **Tasks:** 2
- **Files modified:** 28 (27 test files + pyproject.toml)

## Accomplishments

- Took the pre-sweep ruff inventory before editing anything: `uv run --frozen ruff check --no-cache --select PLC0415 tests/ --exclude tests/test_animation --exclude tests/test_theme --exclude tests/test_devices/test_multizone.py` reported exactly **166 violations across 27 files**, matching the plan's spec-locked figure with zero delta from 16-01/16-02's additions. Full per-file breakdown, led by `tests/test_network/test_mdns/test_discovery.py` (51), `tests/test_network/test_connection.py` (19), `tests/test_network/test_discovery_errors.py` (12), `tests/test_network/test_concurrent_requests.py` (11), `tests/test_devices/test_ceiling.py` (10), `tests/test_effects/test_registry.py` (8), `tests/test_devices/test_state_management.py` (6), `tests/test_devices/test_matrix.py` (6), `tests/test_network/test_mdns/test_dns.py` (5), `tests/test_devices/test_state_light.py` (5), `tests/test_protocol/test_protocol_generator.py` (4), `tests/test_network/test_connection_retry.py` (4), `tests/test_effects/test_integration.py` (4), `tests/test_devices/test_state_ceiling.py` (4), then 8 files with 2 each or 1 each down to `tests/conftest.py` (1).
- Recorded the pre-sweep collected pytest node-ID set (4272 node IDs, saved to `${TMPDIR}/lifx-phase16-nodeids-before.txt`) before any edit, per the plan's set-comparison gate rather than a floor.
- Hoisted every one of the 166 imports to module scope, merging into an existing top-level import statement where the module already imported from the same source, and deleting outright the handful that duplicated an already-imported name (`time`, `tempfile`/`Path`, `MatrixLight`, `LifxTimeoutError`, `asyncio`, `logging`, `socket`). Ran `ruff check --fix` and `ruff format` over the 27-file inventory only (not the repository-wide form), so no unrelated formatting drift entangled with this mechanical commit.
- Resolved `tests/test_network/test_connection_retry.py` — the backstop file — by hoisting `inspect`, `REQUEST_RETRANSMIT_GAPS`, `measurement_support` (the module itself, needed as `measurement_support.asyncio` for a patch target) and `_REQUEST_OBSERVER_TASK_ATTRIBUTE`. Ran the targeted single-file backstop (`uv run --frozen pytest tests/test_network/test_connection_retry.py -q`, 36 passed) proving the hoisted import survives without the tooling conftest beside `.planning/scripts/tests/`, relying only on `tests/conftest.py`'s `sys.path` insert.
- Resolved `tests/test_packaging.py` per Step 3a: deleted the `sys.version_info < (3, 11)` skip and the function-local `import tomllib`, added a module-scope `try: import tomllib / except ModuleNotFoundError: import tomli as tomllib` block, and removed the now-unused `sys` and `pytest` imports. No dependency added (`tomli>=2.0.1 ; python_full_version < '3.11'` was already a dev dependency at pyproject.toml:57), no `noqa` introduced, and the test now runs its manifest assertion on every supported Python version instead of skipping below 3.11.
- Confirmed zero retained function-local imports were needed anywhere in the sweep: no `# noqa: PLC0415` marks exist under `tests/` after this plan, because every flagged site was safely hoistable (no circular-import, patching, or collection-time constraint was found in any of the 27 files).
- Compared the post-sweep collected node-ID set against the pre-sweep set: identical (4272 == 4272), zero lost, zero gained.
- Committed the sweep as one commit with no `pyproject.toml` change (D-08 sequencing).
- Enabled `PLC0415` in `[tool.ruff.lint] select`, adding it to the existing `["E", "F", "I", "N", "W", "UP"]` list, in a separate, later commit.
- Added the seven per-file-ignore entries decided in this plan's FLAGGED section (extending D-05's five-entry design after measuring two extra archived-spike violations): `src/**`, `.planning/**`, `tests/test_animation/**`, `tests/test_theme/**`, `tests/test_devices/test_multizone.py`, `.agents/skills/**`, `.claude/skills/**`. Each carries a handoff comment naming which phase deletes which line.
- Proved both directions with control probes: a synthetic function-local import under `tests/` is reported by the configured `select` with no `--select` flag (positive control, exit 1); the same synthetic import under each of the seven ignored paths is suppressed (negative control, exit 0 for all seven).
- Ran the configuration-shape gate: exactly one `select` line carrying `PLC0415`, exactly seven per-file-ignore entries mapping to it (each of the seven path keys present exactly once), and the five pre-existing `E501` entries unchanged.
- Ran the full verification suite after each commit: `uv run --frozen ruff check .`, `uv run --frozen ruff format --check .`, `uv run --frozen pyright` (0 errors) and `uv run --frozen pytest -q` (4272 passed, 631 deselected) all green after both Task 1 and Task 2.

## Task Commits

Each task was committed atomically:

1. **Task 1: Hoist 166 function-local imports across 27 files in one commit** - `ebae217` (test)
2. **Task 2: Enable PLC0415 with the per-file-ignores that hand off to Phases 18 and 19** - `283a134` (feat)

## Files Created/Modified

- `tests/conftest.py` - hoisted `SimpleNamespace`
- `tests/test_api/test_api_apply_theme.py` - removed a duplicate `Light` import
- `tests/test_api/test_api_discovery.py` - hoisted `_LifxServiceRecord`
- `tests/test_api/test_api_organization.py` - hoisted `asyncio`
- `tests/test_devices/test_base.py` - removed two duplicate `time` imports
- `tests/test_devices/test_ceiling.py` - removed four duplicate `tempfile`/`Path` pairs; replaced two `import lifx.devices.matrix as matrix_module` sites with the already-imported `MatrixLight` name
- `tests/test_devices/test_light.py` - hoisted `LifxUnsupportedCommandError`
- `tests/test_devices/test_matrix.py` - hoisted `DeviceStateHostFirmware`, `DeviceStateVersion`, `TileAccelMeas`, `TileStateDevice as LifxProtocolTileDevice`
- `tests/test_devices/test_state_ceiling.py` - hoisted `CollectionInfo`, `DeviceCapabilities`, `FirmwareInfo`, `WifiInfo`
- `tests/test_devices/test_state_hev.py` - hoisted `patch`
- `tests/test_devices/test_state_infrared.py` - hoisted `patch`
- `tests/test_devices/test_state_light.py` - hoisted `MagicMock`, `patch`, `LifxError`, `LifxTimeoutError`
- `tests/test_devices/test_state_management.py` - hoisted `ProductCapability`, `ProductInfo`, `TemperatureRange`; removed duplicate `DeviceVersion`/`FirmwareInfo`/`LifxTimeoutError` imports
- `tests/test_effects/test_conductor.py` - hoisted `asyncio`
- `tests/test_effects/test_integration.py` - hoisted `Animator`, `MatrixLight`, `MultiZoneLight`, `LIFXEffect`
- `tests/test_effects/test_plasma2d.py` - hoisted `HSBK`
- `tests/test_effects/test_registry.py` - hoisted `InfraredLight`, `MatrixLight`, `MultiZoneLight`, `EffectAurora`, `EffectFlame`, `EffectProgress`, `EffectSunrise`, `EffectSunset`
- `tests/test_network/test_concurrent_requests.py` - hoisted `time`, `DeviceConnection`
- `tests/test_network/test_connection.py` - hoisted `HSBK`, `LifxError`, `Serial`, `packets`, `Device as DevicePackets`, `patch as mock_patch`
- `tests/test_network/test_connection_retry.py` - the backstop file; hoisted `inspect`, `REQUEST_RETRANSMIT_GAPS`, `measurement_support`, `_REQUEST_OBSERVER_TASK_ATTRIBUTE`
- `tests/test_network/test_discovery_devices.py` - removed a duplicate `asyncio` import
- `tests/test_network/test_discovery_errors.py` - removed nine duplicate `LifxTimeoutError` imports; hoisted `MagicMock`
- `tests/test_network/test_mdns/test_discovery.py` - hoisted `_discover_lifx_services`, `discover_devices_mdns`, `IdleDeadline` (51 sites, the largest single file)
- `tests/test_network/test_mdns/test_dns.py` - hoisted `_parse_resource_record`, `DnsResourceRecord`
- `tests/test_network/test_mdns/test_transport.py` - removed duplicate `asyncio`/`socket` imports
- `tests/test_packaging.py` - Step 3a resolution: module-scope `tomllib`/`tomli` compatibility import, version skip and now-unused `sys`/`pytest` imports removed
- `tests/test_protocol/test_protocol_generator.py` - hoisted `packets`, `PACKET_REGISTRY`, `get_packet_class`, `FIELD_MAPPINGS`, `DeviceStateHostFirmware`, `DeviceStateVersion`, `LightHsbk`, `LightWaveform`
- `pyproject.toml` - `PLC0415` added to `[tool.ruff.lint] select`; seven `per-file-ignores` entries added with a handoff comment

## Decisions Made

See `key-decisions` in frontmatter. Summarised: no import needed retention (zero `noqa: PLC0415` marks under `tests/`); `test_ceiling.py`'s module-alias imports were replaced by the already-imported class name rather than duplicated; `test_packaging.py` gained Python 3.10 coverage via the existing `tomli` dev dependency rather than needing a suppression; the seven-entry per-file-ignore list from this plan's FLAGGED section was applied as measured with no operator change requested.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug in plan verify script] Task 1's `FUNCTION-LOCAL-TOMLLIB-REMAINS` check cannot pass for any ruff-format-compliant implementation of the plan's own Step 3a**
- **Found during:** Task 1 verification, `tests/test_packaging.py`'s dedicated `<verify>` block
- **Issue:** The check `grep -qE "^[[:space:]]+import tomllib" "$F"` fires on ANY indented `import tomllib` line, including the module-scope `try:`/`except:` block Step 3a explicitly mandates. `ruff format` always indents a `try:` body onto its own line (verified against a synthetic `try: import tomllib` one-liner, which `ruff format` reformats to the multi-line indented form), so this specific automated line in the plan's verify block is unsatisfiable for the correct implementation.
- **Fix:** No code fix was needed or applied — the implementation matches the plan's mandated shape exactly. Verified the intent directly: the `import tomllib` line sits inside a top-level `try:` (not inside any `def`), confirmed by inspection and by every other criterion in the same verify block passing (no version skip, no `sys`/`pytest` imports, no `noqa`, exactly two test functions, `uv run --frozen pytest tests/test_packaging.py -q` passing 2/2 with no skip).
- **Files modified:** None beyond the already-planned `tests/test_packaging.py` change.
- **Verification:** `uv run --frozen pytest tests/test_packaging.py -q` (2 passed); `grep -n "^import\|^try:\|^except\|^    import" tests/test_packaging.py` shows the compatibility import at module scope.
- **Committed in:** `ebae217` (Task 1 commit, unaffected by this gate-authoring issue)

---

**Total deviations:** 1 documented (1 plan-verify-script defect, no code change required)
**Impact on plan:** None on the shipped implementation. The one affected automated check is narrower than its own stated intent and cannot distinguish "module-scope try/except" from "function-local" by indentation alone; every other gate in the same verify block, plus direct inspection and a passing test run, confirms the implementation satisfies Step 3a as written.

## Issues Encountered

None beyond the deviation above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- TEST-01 is closed. `uv run --frozen ruff check .` is clean repository-wide, and the `PLC0415` rule is now a standing guard against the regression recurring.
- The v2.1 file-disjointness property between Phases 16, 18 and 19 is preserved: no file under `tests/test_animation/`, `tests/test_theme/` or `tests/test_devices/test_multizone.py` was touched by either commit in this plan.
- **Issue-to-requirement mapping for the phase ship step's PR body** (per this plan's "Issue closure has an owner" section — no plan commit in this phase carries a `Closes` line; the phase ship step's merge commit is where all four close together):

  | Issue | Requirement | Landed by |
  |-------|-------------|-----------|
  | #213 | MDNS-09 | plan 16-01 |
  | #215 | DOCS-08 | plan 16-02 |
  | #216 | DOCS-07 | plan 16-03 |
  | #217 | TEST-01 | plan 16-04 (this plan) |

- All four requirements for Phase 16 (MDNS-09, DOCS-07, DOCS-08, TEST-01) are now complete. Phase 16 is ready to ship.
- No blockers.

## Self-Check: PASSED

- `test -e pyproject.toml` -> FOUND
- `test -e tests/test_network/test_mdns/test_discovery.py` -> FOUND
- `test -e tests/test_network/test_connection_retry.py` -> FOUND
- `test -e tests/conftest.py` -> FOUND
- `test -e tests/test_packaging.py` -> FOUND
- `git log --oneline --all | grep -q ebae217` -> FOUND
- `git log --oneline --all | grep -q 283a134` -> FOUND
- `uv run --frozen ruff check --no-cache --select PLC0415 tests/ --exclude tests/test_animation --exclude tests/test_theme --exclude tests/test_devices/test_multizone.py` -> All checks passed
- `uv run --frozen ruff check --no-cache .` -> All checks passed
- `uv run --frozen ruff format --check .` -> 285 files already formatted
- `uv run --frozen pyright` -> 0 errors, 0 warnings (0 info notices)
- `uv run --frozen pytest -q` -> 4272 passed, 631 deselected
- `uv run --frozen pytest tests/test_packaging.py -q` -> 2 passed
- `uv run --frozen pytest tests/test_network/test_connection_retry.py -q` -> 36 passed
- Node-ID set comparison: 4272 before, 4272 after, 0 lost
- `git status --short` after both commits -> clean

---
*Phase: 16-mdns-correctness-docs-and-test-hygiene*
*Completed: 2026-09-07*
