---
phase: 16-mdns-correctness-docs-and-test-hygiene
reviewed: 2026-09-07T00:00:00Z
depth: deep
files_reviewed: 36
files_reviewed_list:
  - src/lifx/network/discovery/mdns/discovery.py
  - src/lifx/api.py
  - pyproject.toml
  - AGENTS.md
  - docs/user-guide/advanced-usage.md
  - docs/user-guide/discovery.md
  - tests/conftest.py
  - tests/test_docs_language.py
  - tests/test_packaging.py
  - tests/test_repository_guidance.py
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
  - tests/test_network/test_mdns/test_phase_contract.py
  - tests/test_network/test_mdns/test_transport.py
  - tests/test_protocol/test_protocol_generator.py
findings:
  critical: 0
  warning: 0
  info: 2
  total: 2
status: clean
---

# Phase 16: Code Review Report

**Reviewed:** 2026-09-07T00:00:00Z
**Depth:** deep
**Files Reviewed:** 36
**Status:** clean

## Summary

This phase delivers four requirements: an internal guard-predicate refactor in the mDNS record
cache (MDNS-09), two documentation-accuracy passes with new repository-wide prose contracts
(DOCS-08, DOCS-07), and a mechanical hoist of 166 function-local test imports to module scope with
`ruff` `PLC0415` newly enabled (TEST-01).

**MDNS-09 (`src/lifx/network/discovery/mdns/discovery.py`)** was reviewed hardest per the scope
note. The extracted `_owner_is_unusable()` predicate is shared correctly by
`_selected_address_for_normalised()` and `pending_targets()`. Traced by hand:

- The new `not owner` guard term is a genuine improvement, not a regression: the old
  `pending_targets()` had no such guard, so an SRV target that wire-normalises to the empty
  string (a malformed responder advertising a root-domain `SRV` target) could previously have been
  appended to the pending-target list and triggered a follow-up `build_address_query("")` call.
  The new guard closes that gap.
- The retained-payload term of `_owner_is_unusable()` is provably unreachable inside
  `pending_targets()` (an early return for `_retained_payload_budget_exhausted` precedes the loop,
  and nothing inside the loop can set that flag), matching the code's own comment and confirmed by
  reading `_add_record()`, the only writer of that flag.
- The public `selected_address_for()` / private `_selected_address_for_normalised()` split
  preserves the pre-existing (and explicitly documented) double-trailing-dot residual rather than
  introducing a new guard-key/lookup-key divergence: both the old and new code pass the same,
  possibly-still-dotted `owner`/`target` argument to both the guard checks and the address lookup,
  so whatever mismatch could occur against `_records_by_owner`'s single-normalised keys was already
  present before this phase.
- Extensive new tests (`TestLifxRecordCacheOwnerNormalisation`,
  `test_pending_targets_refuses_a_target_the_address_guards_reject`) exercise exactly the guard
  terms this refactor touches, including casefold-vs-`.lower()` divergence (`HOẞT.LOCAL`), root-name
  normalisation, and the whole-sweep address-budget and byte-incomplete-AAAA terms specifically
  inside `pending_targets()`.

**DOCS-08 / DOCS-07**: the new `tests/test_docs_language.py` prose contract correctly forbids the
retired "proven synthetically" / "mesh scale" phrasing and the false verification-attribution
phrasing across `src/**/*.py` and `docs/**/*.md`; a repo-wide grep confirms zero residual matches.
The corrected `discover_mdns()` docstring and `docs/user-guide/discovery.md` text now attribute
correlated-request verification to `discover()`'s merged mDNS leg (`_discover_verified_devices_mdns`)
rather than to `discover_mdns()`/`discover_udp()` themselves — verified against the actual call
graph in `src/lifx/api.py` (`discover_mdns()` calls the unverified `discover_devices_mdns()`; only
`discover()`, via `_race_serial_sources`/the merged path, calls the verifying function). The
`AGENTS.md` "Derived, not cached" bullet for `connectivity` matches the actual `Device.connectivity`
property implementation in `src/lifx/devices/base.py` (recomputed from `connection.thread_connection`
on every read, falling back to discovery metadata).

**TEST-01**: all 27 test-file diffs were inspected individually for the three named hazards
(monkeypatch-target defeat, import-order breakage, masked circular import). All 166 hoists are
plain, non-hazardous relocations — mock/patch targets are resolved by string or by direct module
attribute (`measurement_support.asyncio`, `lifx.network.discovery.mdns.discovery.MdnsTransport`,
`MatrixLight.__aenter__` on the already-identical class object), none of which are sensitive to
where the importing name lives in the test file. One file (`tests/test_packaging.py`) goes beyond a
mechanical hoist: it replaces a `sys.version_info < (3, 11)` skip with a `try: import tomllib /
except ModuleNotFoundError: import tomli as tomllib` fallback, extending
`test_pyproject_declares_no_runtime_dependencies` to run (rather than skip) on Python 3.10. This is
a net improvement and not a defect: `tomli` was already declared as a `python_full_version < '3.11'`
dev dependency before this phase (`pyproject.toml:57`, unchanged by this diff), and it closes a
Python-3.10 coverage gap the project's own CI matrix (3.10–3.14) otherwise leaves open.

The new `pyproject.toml` `PLC0415` per-file-ignore list was checked against a live `ruff check
--select PLC0415 .` run: it passes cleanly, and the seven ignored globs are exactly the paths that
still contain function-local imports (`src/**`, `.planning/**`, `tests/test_animation/**`,
`tests/test_theme/**`, `tests/test_devices/test_multizone.py`, `.agents/skills/**`,
`.claude/skills/**|`) — none are stale or overbroad.

**Verification performed**: full default test suite (`uv run --frozen pytest`) passes at
4272 passed / 631 deselected with no regressions; `ruff check` and `pyright` are clean on the
changed Python files; a repository-wide grep confirms no forbidden internal-validation phrases, no
real-looking IPs/MACs/serials, and no newly introduced em dashes or American spellings in the
prose changes.

No Critical or Warning findings. Two Info-level nits below.

## Info

### IN-01: Redundant `patch` alias left after hoisting in `test_connection.py`

**File:** `tests/test_network/test_connection.py:7`
**Issue:** The module already imports `patch` at line 4
(`from unittest.mock import AsyncMock, MagicMock, patch`). The hoist of
`test_send_packet_uses_precomputed_target`'s local imports adds a second, redundant top-level
import, `from unittest.mock import patch as mock_patch`, whose only use (line ~802) could just call
`patch(...)` directly. This is harmless (both names bind the identical object) but is dead
duplication that a mechanical hoist introduced rather than removed.
**Fix:**
```python
# Drop the redundant alias import and the second name:
-from unittest.mock import patch as mock_patch
...
-with mock_patch(
+with patch(
```

### IN-02: Dense run-on sentence in the new discovery-guide Limitations prose

**File:** `docs/user-guide/discovery.md:129`
**Issue:** "The next action is to confirm it with a request, or to use `discover()`, whose mDNS
candidates must answer a correlated device request before they are yielded." packs two clauses and
an embedded relative clause into one sentence, which is harder to parse than the surrounding
prose in the same section. The content is accurate (verified against `discover()`'s actual call
graph), so this is a readability nit, not a correctness issue.
**Fix:** Split into two sentences, e.g.: "The next action is to confirm it with a request, or to
use `discover()` instead. Its mDNS candidates must answer a correlated device request before they
are yielded."

---

_Reviewed: 2026-09-07T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
