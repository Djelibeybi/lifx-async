---
status: complete
phase: 16-mdns-correctness-docs-and-test-hygiene
source: [16-01-SUMMARY.md, 16-02-SUMMARY.md, 16-03-SUMMARY.md, 16-04-SUMMARY.md]
started: 2026-09-07T09:13:26Z
updated: 2026-09-07T09:13:26Z
---

## Current Test

[testing complete]

## Tests

### 1. selected_address_for() routes its owner argument through _normalise_dns_name(); a trailing-dot owner and its bare form reach the identical guard set and result
expected: selected_address_for() routes its owner argument through _normalise_dns_name(); a trailing-dot owner and its bare form reach the identical guard set and result
result: pass
source: automated
coverage_id: D1 (16-01-SUMMARY.md)

### 2. Empty and DNS-root owner names are refused fail-closed even when an address record is genuinely cached under that key
expected: Empty and DNS-root owner names are refused fail-closed even when an address record is genuinely cached under that key
result: pass
source: automated
coverage_id: D2 (16-01-SUMMARY.md)

### 3. An owner whose .lower() and .casefold() forms differ is driven into an owner-keyed guard on the casefolded form, not merely producing a successful lookup
expected: An owner whose .lower() and .casefold() forms differ is driven into an owner-keyed guard on the casefolded form, not merely producing a successful lookup
result: pass
source: automated
coverage_id: D3 (16-01-SUMMARY.md)

### 4. pending_targets() refuses a target the sweep-budget guard and the byte-incomplete-AAAA guard reject, each proven against a paired control
expected: pending_targets() refuses a target the sweep-budget guard and the byte-incomplete-AAAA guard reject, each proven against a paired control
result: pass
source: automated
coverage_id: D4 (16-01-SUMMARY.md)

### 5. No fail-closed guard became fail-open and no public API surface changed; whole mDNS suite, default suite, pyright and ruff all pass
expected: No fail-closed guard became fail-open and no public API surface changed; whole mDNS suite, default suite, pyright and ruff all pass
result: pass
source: automated
coverage_id: D5 (16-01-SUMMARY.md)

### 6. docs/user-guide/discovery.md names bounded discovery, proxy responses and testing limitations in caller terms, with the five locked approved-phrase fragments present
expected: docs/user-guide/discovery.md names bounded discovery, proxy responses and testing limitations in caller terms, with the five locked approved-phrase fragments present
result: pass
source: automated
coverage_id: D1 (16-02-SUMMARY.md)

### 7. discover_mdns() docstring, docs/migration/mdns-low-level-api-7.0.0.md and docs/getting-started/quickstart.md carry no internal validation language and do not contradict discovery.md
expected: discover_mdns() docstring, docs/migration/mdns-low-level-api-7.0.0.md and docs/getting-started/quickstart.md carry no internal validation language and do not contradict discovery.md
result: pass
source: automated
coverage_id: D2 (16-02-SUMMARY.md)

### 8. The proxy paragraph attributes correlated-device-request verification to discover()'s mDNS candidates, never to its UDP leg, and a repository-wide negative assertion enforces this
expected: The proxy paragraph attributes correlated-device-request verification to discover()'s mDNS candidates, never to its UDP leg, and a repository-wide negative assertion enforces this
result: pass
source: automated
coverage_id: D3 (16-02-SUMMARY.md)

### 9. Both test_phase_contract.py phrase lists (approved_phrases and _MOVED_MDNS_LIMITATION_PHRASES) move to the replacement wording in the same commit as the prose, and the mDNS contract suite stays green
expected: Both test_phase_contract.py phrase lists (approved_phrases and _MOVED_MDNS_LIMITATION_PHRASES) move to the replacement wording in the same commit as the prose, and the mDNS contract suite stays green
result: pass
source: automated
coverage_id: D4 (16-02-SUMMARY.md)

### 10. A repository-wide assertion proves the removed internal validation language and the false verification attribution appear nowhere under src/ or docs/, docs/changelog.md excluded by name and existing on disk, and this new module runs in the default suite alongside the mDNS contract suite
expected: A repository-wide assertion proves the removed internal validation language and the false verification attribution appear nowhere under src/ or docs/, docs/changelog.md excluded by name and existing on disk, and this new module runs in the default suite alongside the mDNS contract suite
result: pass
source: automated
coverage_id: D5 (16-02-SUMMARY.md)

### 11. Device.connectivity moved under the first ##### Non-State Properties heading in docs/user-guide/advanced-usage.md, absent from the state-backed #### Device Properties list above it
expected: Device.connectivity moved under the first ##### Non-State Properties heading in docs/user-guide/advanced-usage.md, absent from the state-backed #### Device Properties list above it
result: pass
source: automated
coverage_id: D1 (16-03-SUMMARY.md)

### 12. AGENTS.md carries a third Derived, not cached caching category naming exactly connectivity, with no em dash and derivation scoped to a correlated response, matching src/lifx/network/connection.py:1075
expected: AGENTS.md carries a third Derived, not cached caching category naming exactly connectivity, with no em dash and derivation scoped to a correlated response, matching src/lifx/network/connection.py:1075
result: pass
source: automated
coverage_id: D2 (16-03-SUMMARY.md)

### 13. A contract assertion proves connectivity appears in exactly one of the three AGENTS.md state-caching categories (count, not membership, so zero and duplicate both fail)
expected: A contract assertion proves connectivity appears in exactly one of the three AGENTS.md state-caching categories (count, not membership, so zero and duplicate both fail)
result: pass
source: automated
coverage_id: D3 (16-03-SUMMARY.md)

### 14. docs/api/devices.md is unmodified and its Connectivity section still carries no caching claim; AGENTS.md retains ### State Caching and CLAUDE.md does not duplicate it
expected: docs/api/devices.md is unmodified and its Connectivity section still carries no caching claim; AGENTS.md retains ### State Caching and CLAUDE.md does not duplicate it
result: pass
source: automated
coverage_id: D4 (16-03-SUMMARY.md)

### 15. The whole default suite, ruff, ruff format and pyright stay green; the plan's four declared files are the only ones changed
expected: The whole default suite, ruff, ruff format and pyright stay green; the plan's four declared files are the only ones changed
result: pass
source: automated
coverage_id: D5 (16-03-SUMMARY.md)

### 16. 166 function-local imports across 27 files under tests/ (excluding tests/test_animation/, tests/test_devices/test_multizone.py and tests/test_theme/) moved to module scope in one mechanical commit, with the collected pytest node-ID set unchanged
expected: 166 function-local imports across 27 files under tests/ (excluding tests/test_animation/, tests/test_devices/test_multizone.py and tests/test_theme/) moved to module scope in one mechanical commit, with the collected pytest node-ID set unchanged
result: pass
source: automated
coverage_id: D1 (16-04-SUMMARY.md)

### 17. tests/test_packaging.py's Python 3.10 version skip replaced by a module-scope tomli/tomllib compatibility import, gaining coverage rather than adding a suppression
expected: tests/test_packaging.py's Python 3.10 version skip replaced by a module-scope tomli/tomllib compatibility import, gaining coverage rather than adding a suppression
result: pass
source: automated
coverage_id: D2 (16-04-SUMMARY.md)

### 18. PLC0415 enabled in ruff's select list with exactly seven per-file-ignore entries, each proven to fire on an in-scope synthetic path and suppress on its own ignored path; the sweep and the configuration change are separate commits
expected: PLC0415 enabled in ruff's select list with exactly seven per-file-ignore entries, each proven to fire on an in-scope synthetic path and suppress on its own ignored path; the sweep and the configuration change are separate commits
result: pass
source: automated
coverage_id: D3 (16-04-SUMMARY.md)

## Summary

total: 18
passed: 18
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

[none]
