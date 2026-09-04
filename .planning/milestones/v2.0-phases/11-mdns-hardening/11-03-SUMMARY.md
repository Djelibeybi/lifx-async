---
phase: 11-mdns-hardening
plan: 03
subsystem: network-discovery
tags: [mdns, rfc6762, expiry, diagnostics, concurrency, tdd]

requires:
  - phase: 11-mdns-hardening
    plan: 02
    provides: complete live RR identities, lossless advertised addresses, and fail-closed TXT/SRV consensus
provides:
  - Exact-RR one-second goodbye grace and identical positive-TTL rescue within caller deadlines
  - One ordered reason/type/count-only rejection summary per discovery sweep
  - Receive-loop packet permutation, concurrent-call isolation, and bounded follow-up completion proofs
  - Packet-source fallback deferred until collection closes so later advertised endpoints win
affects: [11-04, 11-05, 11-06, phase-13-merged-discovery]

actuals:
  tokens: 14590
  tasks: 3
  commits: 6

tech-stack:
  added: []
  patterns:
    - Pending-only monotonic expiry index keyed by complete live RR identity
    - Per-sweep synchronous final diagnostic aggregate with fixed scalar fields
    - Separate follow-up attempt and successful-send ledgers bounded per invocation

key-files:
  created: []
  modified:
    - src/lifx/network/mdns/discovery.py
    - tests/test_network/test_mdns/test_discovery.py

key-decisions:
  - "Goodbye scheduling traverses only TTL-zero-marked identities; ordinary retained A/AAAA records never enter the timer index."
  - "Recoverable DNS parsing catches only ValueError, IndexError, and struct.error; cache, resolution, and construction defects propagate after final diagnostics."
  - "Packet-source fallback is validated and deferred until sweep completion so later SRV and advertised address evidence cannot be preempted by arrival order."

patterns-established:
  - "Timer ordering: expire every due RR, process a due PTR retransmit, then re-evaluate the unchanged IdleDeadline."
  - "Diagnostic finalisation: one class/action/rejections dictionary containing only sorted reason, type, and integer count entries."

requirements-completed: [MDNS-03, MDNS-04, MDNS-06, MDNS-07]

coverage:
  - id: D1
    description: "TTL-zero TXT, SRV, A, and AAAA identities receive exact one-second grace, identical rescue, conflict recovery, and deadline-safe expiry."
    requirement: MDNS-07
    verification:
      - kind: unit
        ref: "tests/test_network/test_mdns/test_discovery.py#TestLifxRecordCacheGoodbyeExpiry and TestMdnsGoodbyeExpiryScheduling"
        status: pass
    human_judgment: false
  - id: D2
    description: "Every discovery sweep emits one bounded privacy-safe rejection summary while recoverable parse errors remain narrowly classified."
    requirement: MDNS-06
    verification:
      - kind: unit
        ref: "tests/test_network/test_mdns/test_discovery.py#TestMdnsRejectionDiagnostics"
        status: pass
    human_judgment: false
  - id: D3
    description: "Packet boundaries, empty packets, replay, and concurrent generators preserve exact-once isolated service discovery."
    requirement: MDNS-03
    verification:
      - kind: integration
        ref: "tests/test_network/test_mdns/test_discovery.py#test_generator_packet_permutations_yield_one_equal_record and test_concurrent_generators_cannot_complete_each_others_instances"
        status: pass
    human_judgment: false
  - id: D4
    description: "Missing target addresses use exact combined A/AAAA queries with one success, two-attempt failure, and 64-host admission bounds."
    requirement: MDNS-04
    verification:
      - kind: integration
        ref: "tests/test_network/test_mdns/test_discovery.py#TestMdnsFollowUpAddressQueries"
        status: pass
    human_judgment: false
  - id: D5
    description: "The hardened discovery implementation remains compatible with the complete library and strict static-analysis gates."
    verification:
      - kind: other
        ref: "uv run --frozen pytest -q -p no:sugar (3836 passed, 12 deselected)"
        status: pass
      - kind: other
        ref: "uv run pyright (0 errors, 0 warnings)"
        status: pass
    human_judgment: false

duration: 23 min
completed: 2026-08-28
status: complete
---

# Phase 11 Plan 03: Goodbye, Diagnostics, and Generator Isolation Summary

**Exact-RR goodbye grace with monotonic rescue, one privacy-safe rejection aggregate, and bounded isolated receive-loop completion across packet permutations**

## Performance

- **Duration:** 23 min
- **Started:** 2026-08-28T08:11:28Z
- **Completed:** 2026-08-28T08:33:59Z
- **Tasks:** 3
- **Files modified:** 2

## Accomplishments

- Added a per-cache pending-goodbye index that grants matching TXT, SRV, A, and AAAA identities one second of grace, supports identical rescue, releases capacity only after expiry, and never scans ordinary retained addresses.
- Integrated expiry wake-ups under the existing caller-owned idle and overall deadlines, with deterministic expiry-before-retransmit processing and no clock-only idle reset.
- Replaced identifier-bearing rejection logs with one sorted reason/type/count-only DEBUG summary on normal exhaustion, early close, cancellation, or propagated implementation failure.
- Narrowed recoverable packet parsing to `ValueError`, `IndexError`, and `struct.error`, counted unexpected cache-flush bits without replacement semantics, and validated source fallback before record emission.
- Proved complete receive-loop packet permutations, concurrent state isolation, exact combined A/AAAA follow-up bytes, successful-send suppression, two-attempt failure limits, and the 64-host admission cap.

## Task Commits

Each TDD step was committed atomically:

1. **Task 1: Schedule exact-RR goodbye expiry and rescue inside caller deadlines**
   - `1d3a346` — `test(mdns): add goodbye expiry regressions`
   - `b952264` — `feat(mdns): honour goodbye grace and rescue`
2. **Task 2: Emit one bounded privacy-safe rejection summary per sweep**
   - `8af49d9` — `test(mdns): add rejection summary regressions`
   - `f175d6e` — `feat(mdns): aggregate rejection diagnostics`
3. **Task 3: Prove packet permutations, concurrent isolation, and bounded follow-up completion**
   - `d7411b8` — `test(mdns): add generator isolation regressions`
   - `22b97d6` — `fix(mdns): defer packet source fallback`

## Files Created/Modified

- `src/lifx/network/mdns/discovery.py` — Pending expiry scheduling, exact parse-error boundary, aggregate finalisation, validated/deferred fallback, and invocation-local receive-loop state.
- `tests/test_network/test_mdns/test_discovery.py` — Deterministic goodbye/rescue, diagnostic privacy, packet permutation, concurrent isolation, and bounded follow-up regressions.

## Decisions Made

- Pending expiry state is keyed by complete masked-class RR identity and contains only identities under goodbye grace. Positive TTL refresh removes only an identical pending entry.
- The public generator is a thin finalising wrapper around one invocation-local sweep, allowing synchronous exactly-once diagnostics without swallowing failures or leaking cache state.
- Source-address fallback remains separate from advertised addresses and is withheld until collection ends; a later SRV endpoint therefore wins without changing the yield-before-auxiliary-send rule for advertised records.
- Unexpected cache-flush bits are diagnostic observations only. Their records follow normal admission and sibling-retention semantics with the high class bit masked from identity.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- The managed sandbox initially blocked uv cache and Git index/GPG access. Approved execution used the existing project environment; no dependency, lockfile, remote, or hardware state changed.
- Codespell rejected one hyphenated spelling in a comment. The spelling was corrected before the Task 3 GREEN commit and all hooks then passed.
- GSD state handlers advanced the machine fields but left stale human-readable plan prose and malformed the roadmap table's empty date cell. Both tracking artefacts were corrected before the final bookkeeping commit.

## Verification

- Task 1 focused goodbye/rescue/expiry/deadline gate passed within the final 149-test discovery module run.
- Task 2 focused diagnostic/cache-flush/malformed-packet/privacy gate: `15 passed, 130 deselected`.
- Task 3 focused follow-up and serial-dedupe gate: `11 passed`.
- Full mDNS discovery module: `149 passed`.
- Full frozen suite: `3836 passed, 12 deselected` with seven pre-existing deprecation warnings.
- Ruff check passed and both scoped files were already formatted.
- Pyright passed with `0 errors, 0 warnings, 0 information messages`.
- All six task commits have good signatures from the mandated GPG key and include developer sign-off.
- The evidence-privacy audit covered the two modified files and the complete local-only commit range `e5be677..22b97d6`. Candidates were confined to clearly synthetic serials/hostnames and documentation or deliberate synthetic address fixtures; no live identifier, raw discovery output, account data, or credential was found.
- Stub scan found only normal empty state initialisation and negative test assertions; no goal-blocking placeholder, skipped test, or unwired data source exists.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 11-04 can build on one hardened per-call discovery sweep with exact live-record timing, bounded private diagnostics, isolated follow-up ledgers, and complete synthetic receive-loop evidence.
- No blocker remains. Live hardware, multicast routing, daemons, external services, push, merge, and deployment were not used or changed.

## Self-Check: PASSED

- Both modified implementation/test files and this summary exist.
- All six task commit objects exist and their signatures were verified with the mandated key.
- Requirements and deterministic coverage metadata are present with `status: complete`.

---
*Phase: 11-mdns-hardening*
*Completed: 2026-08-28*
