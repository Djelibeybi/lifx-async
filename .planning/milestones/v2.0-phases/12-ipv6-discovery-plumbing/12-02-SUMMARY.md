---
phase: 12-ipv6-discovery-plumbing
plan: 02
subsystem: network
tags: [ipv6, discovery, validation, address-representation, asyncio]
requires:
  - phase: 12-01
    provides: Family-aware targeted discovery transport and generator ownership
provides:
  - Exact caller-literal preservation through targeted device construction
  - Deterministic public-API coverage for six IPv6 address representations
  - Proof that invalid targets fail before discovery transport construction
affects: [phase-12, phase-13, find-by-ip]
tech-stack:
  added: []
  patterns:
    - Instrument the network boundary without opening route-dependent sockets
    - Treat the validated targeted lookup literal as authoritative after response parsing
    - Use fail-on-construction transport sentinels to prove validation order
key-files:
  created:
    - .planning/phases/12-ipv6-discovery-plumbing/12-02-SUMMARY.md
  modified:
    - src/lifx/api.py
    - tests/test_api/test_api_discovery.py
    - .planning/STATE.md
    - .planning/ROADMAP.md
key-decisions:
  - Targeted find_by_ip preserves the already validated caller literal through device construction.
  - Representation tests exercise the public API and real discovery parser while replacing only transport delivery.
  - Permanent invalid inputs are pinned with a transport that fails if it is ever constructed.
patterns-established:
  - "Target literal authority: targeted lookup restores the validated input after sockaddr parsing."
  - "Validation-order proof: invalid-input tests assert zero transport lifecycle activity."
requirements-completed: [FIND-06]
coverage:
  - dimension: IPv6 representation matrix and split-scope restoration
    requirement: FIND-06
    evidence: TestFindByIpAddressGate representation and zoned-address cases
    human: false
  - dimension: Validation before transport use
    requirement: FIND-06
    evidence: TestFindByIpAddressGate invalid-representation cases and test_address.py
    human: false
  - dimension: Static quality and type safety
    requirement: FIND-06
    evidence: Scoped Ruff checks and repository-wide Pyright
    human: false
actuals:
  tokens: 2879
  tasks: 2
  commits: 3
metrics:
  duration: 7 min
  completed: 2026-08-29
status: complete
---

# Phase 12 Plan 02: IPv6 Representation and Validation Boundaries Summary

Targeted IPv6 lookup now preserves every accepted caller representation, including a zoned link-local literal reconstructed across the public API boundary, with deterministic proof that permanently invalid targets never touch transport setup.

## Performance

- **Duration:** 7 min
- **Started:** 2026-08-29T10:08:03Z
- **Completed:** 2026-08-29T10:15:00Z
- **Tasks:** 2
- **Files modified:** 2 production/test files

## Accomplishments

- Added a public `find_by_ip()` representation matrix covering compressed and expanded documentation global-unicast forms, a ULA, another documentation GUA, loopback, and zoned link-local input.
- Preserved the validated caller literal after discovery response parsing so a split IPv6 sockaddr scope remains visible to device construction.
- Proved empty, malformed, and unscoped link-local targets raise before discovery transport construction or lifecycle activity.
- Kept all network identifiers synthetic and made timeout behaviour yield to the event loop instead of busy-looping.

## Task Commits

Each task was committed atomically:

1. **Task 1: Pin and preserve accepted IPv6 representations**
   - `7744213` (`test`) — failing targeted IPv6 representation regressions
   - `fdba13c` (`fix`) — preserve zoned IPv6 target through lookup
2. **Task 2: Prove permanent failures precede transport setup**
   - `a82db18` (`test`) — pin validation before discovery transport use

## Files Created/Modified

- `.planning/phases/12-ipv6-discovery-plumbing/12-02-SUMMARY.md` — execution evidence, decisions, and verification results.
- `src/lifx/api.py` — restores the validated target literal before targeted device construction.
- `tests/test_api/test_api_discovery.py` — deterministic transport doubles, representation coverage, split-scope parsing, and validation-order assertions.
- `.planning/STATE.md` — sequential execution position and metrics.
- `.planning/ROADMAP.md` — Phase 12 plan progress.

## Decisions Made

- The validated `find_by_ip()` argument is authoritative for the returned device address. Discovery parsing still validates the response path, while the public targeted-lookup contract retains the exact accepted literal.
- The zoned-link-local regression uses the real packet builder and discovery parser; only transport delivery and device construction are intercepted.
- Invalid-input tests use a fail-on-construction transport sentinel so future reordering cannot silently allocate network resources before validation.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Task 2's regression test passed immediately because the required validation order was already present. The test remains valuable as a permanent boundary contract; no artificial production change was introduced.
- Focused pytest selections emitted the existing coverage warning that `generate_theme_data` was not imported. All selected tests passed, and this warning is expected outside the full suite.
- The managed environment required Git index approval and a writable private uv cache path. No dependency or lockfile changed.

## Authentication Gates

None.

## Known Stubs

None.

## Test and Quality Results

- `uv run pytest tests/test_api/test_api_discovery.py::TestFindByIpAddressGate -q` — 10 passed.
- `uv run pytest tests/test_network/test_address.py -q` — 31 passed.
- `uv run ruff format --check src/lifx/api.py tests/test_api/test_api_discovery.py` — 2 files already formatted.
- `uv run ruff check src/lifx/api.py tests/test_api/test_api_discovery.py` — all checks passed.
- `uv run pyright` — 0 errors, 0 warnings, 0 information messages.

## TDD Gate Compliance

- Task 1 followed RED/GREEN: `7744213` failed specifically because the split IPv6 sockaddr lost its numeric zone, then `fdba13c` made the full representation gate pass.
- Task 2 added regression-only coverage for behaviour already implemented; the new test passed on first execution and was committed without manufacturing a false RED state.

## Privacy Boundary

All committed addresses are documentation, loopback, ULA, or synthetic link-local literals. The packet serial is a synthetic locally administered value; no live device, route, hostname, account, or raw discovery output is present.

## User Setup Required

None.

## Next Phase Readiness

- Plan 12-03 can build on an exact, representation-stable targeted IPv6 API boundary.
- FIND-06 remains a shared Phase 12 requirement and should be marked complete only after every plan that claims it has a summary.

## Self-Check: PASSED

- Created and modified files exist.
- Task commits `7744213`, `fdba13c`, and `a82db18` exist in repository history.
- Verification commands above completed successfully.
