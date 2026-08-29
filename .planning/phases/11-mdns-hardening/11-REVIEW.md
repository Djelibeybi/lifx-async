---
phase: 11-mdns-hardening
reviewed: 2026-08-29T01:48:05Z
depth: deep
files_reviewed: 23
files_reviewed_list:
  - AGENTS.md
  - CLAUDE.md
  - docs/api/devices.md
  - docs/api/index.md
  - docs/api/network.md
  - docs/getting-started/quickstart.md
  - docs/user-guide/advanced-usage.md
  - examples/README.md
  - examples/discovery_mdns.py
  - scripts/ipv6_thread_probe.py
  - src/lifx/__init__.py
  - src/lifx/api.py
  - src/lifx/devices/base.py
  - src/lifx/network/mdns/__init__.py
  - src/lifx/network/mdns/discovery.py
  - src/lifx/network/mdns/transport.py
  - src/lifx/network/mdns/types.py
  - tests/test_api/test_api_discovery.py
  - tests/test_devices/test_base.py
  - tests/test_network/test_mdns/test_discovery.py
  - tests/test_network/test_mdns/test_phase_contract.py
  - tests/test_network/test_mdns/test_transport.py
  - tests/test_scripts/test_ipv6_thread_probe.py
findings:
  critical: 0
  warning: 0
  info: 0
  total: 0
status: clean
---

# Phase 11: Code Review Report

**Reviewed:** 2026-08-29T01:48:05Z
**Depth:** deep
**Files Reviewed:** 23
**Status:** clean

## Summary

All reviewed files meet quality standards. No current issues were found.

The final iteration-3 change closes the remaining complete-record privacy gap without weakening the schema-v2 contract. The validator scans dictionary keys, string values, nested dictionaries, and lists for the selected serial after case folding and separator removal. It runs before output-path creation and before field validation, so identifier-bearing malformed records fail closed. Valid producer records still pass, while malformed non-sensitive fields continue to receive their field-specific structural rejection.

No live hardware probe was run. Phase 11 explicitly excludes live device mutation, and the synthetic coverage exercises the required restoration, discovery, privacy, consumer-contract, and exit-status behaviours.

## Narrative Findings (AI reviewer)

No BLOCKER or WARNING findings remain in the 23-file review scope.

## Resolution Audit

- **CR-01 — resolved:** pending mDNS address follow-ups depend on usable selection, not merely retained address data, while the existing incompleteness and resource-budget guards remain fail closed.
- **CR-02 — resolved:** multizone capture records zones, effect, and power, and restoration uses the public capability-aware setter for both extended and legacy products before restoring effect and power.
- **CR-03 — resolved:** failed restoration independently forces a non-zero process status.
- **CR-04 — resolved:** evidence omits raw serial and address fields, aliases are constrained and revalidated, and the complete record now rejects the normalised raw serial in every string key or value before writing. Regressions cover exact, mixed-case, separator-formatted, nested-key, nested-value, list, alias, and `library_head` placements.
- **CR-05 — resolved:** the producer and consumer share an exact Phase 11 schema-v2 contract with distinct kind, phase, destination, help text, key sets, value vocabularies, and typed structural checks. Phase 10-shaped records are rejected.
- **WR-01 — resolved:** DNS packets with QR clear are discarded before counters, source tracking, cache mutation, idle activity, or resolution.

The seven older findings closed by Phase 11 gap plans remain historical and are not counted as current findings.

## Automated Proof

- All six test files in the 23-file review scope: **481 passed**.
- Combined mDNS discovery and probe regressions: **333 passed**.
- Full non-hardware suite: **3,985 passed, 12 deselected**, with seven existing `receive_many` deprecation warnings.
- Ruff format check: **passed**.
- Ruff check: **passed**.
- Project-wide Pyright: **0 errors, 0 warnings, 0 information messages**.

---

_Reviewed: 2026-08-29T01:48:05Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: deep_
