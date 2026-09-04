---
phase: 10-land-the-ipv6-thread-branch
plan: 06
subsystem: network
tags: [ipv6, thread, uat, hardware, merge, ci, coverage, release]

requires:
  - phase: 10-01
    provides: "the rebased branch itself, and 10-COVERAGE-GAPS.md — the independent checklist this plan verifies as closed before pushing, rather than discovering the debt against the merge deadline"
  - phase: 10-02
    provides: "lifx.network.address and the four gated entry points, so the PR carries B9 and B2 closed"
  - phase: 10-03
    provides: "the B1 send-time family assertion, the leak-safe MdnsTransport.open(), and 100% branch coverage across lifx.network.mdns"
  - phase: 10-04
    provides: "the ::1 emulator fixtures, the AF_INET6 family assertions and the LIFX_REQUIRE_IPV6 CI cell that make the IPv6 path unable to pass silently over IPv4"
  - phase: 10-05
    provides: "the probe's control stage, --serial, --uat-output and the state capture/restore this plan's hardware run depends on"
provides:
  - "PR #208, the single PR carrying the whole phase (D-18), driven to full CI green including the codecov branch patch gate"
  - "10-UAT-RESULTS.json: a passed control run against a real Thread-only MatrixLight, pinned to the merged head"
  - "the phase landed on main by local fast-forward, so every commit signature survives"
affects: [11, 14]

actuals:
  tokens: 0
  tasks: 4
  commits: 1

tech-stack:
  added: []
  patterns:
    - "One-way gates are held by the operator, not by the orchestrator: the merge decision was an explicit blocking-human checkpoint and stayed held until lifted"
    - "An acceptance criterion that a later decision makes unsatisfiable is amended to assert its original intent, with the amendment and its reasoning recorded as a numbered decision — never silently dropped"

key-files:
  created:
    - .planning/phases/10-land-the-ipv6-thread-branch/10-UAT-RESULTS.json
    - .planning/phases/10-land-the-ipv6-thread-branch/10-06-SUMMARY.md
  modified:
    - .planning/phases/10-land-the-ipv6-thread-branch/10-SPEC.md
    - .planning/phases/10-land-the-ipv6-thread-branch/10-06-PLAN.md
    - .planning/phases/10-land-the-ipv6-thread-branch/10-CONTEXT.md

key-decisions:
  - "D-24: pushes go to origin only. feat/ipv6-thread-support was fetched from the redding1 fork and its branch config still had a pushRemote pointing there, so a bare `git push` would have published this work into a contributor's fork. pushRemote was repointed at origin, fetch-tracking deliberately left alone, and every push in this plan names its remote explicitly"
  - "D-25: the series was squashed to two commits — redding1's 79a5ce0 replayed byte-identically, plus one authored commit carrying the rest. Trees verified identical before and after; only history collapsed"
  - "SPEC AC 17 and 10-06's matching checks were amended rather than dropped. The criterion said 'all three replayed commits', which the squash makes literally unsatisfiable; its intent was that the merge preserve signatures, DCO sign-off and redding1's authorship, none of which the squash weakened. The amended form asserts that intent directly and is strictly stronger — it now requires a Signed-off-by on every commit the merge adds, which the commit-count form did not"
  - "Plan 10-01's 'three oldest commits' criterion was deliberately NOT amended. It was true when 10-01 executed and its SUMMARY holds the proof; rewriting a completed plan's acceptance record to match a later decision would falsify the history the record exists to preserve"
  - "The UAT record is committed separately from the code it certifies, not amended into it. library_head pins the head the run was made against, so a record living inside that same commit could never name its own SHA. The artefact commit is docs-only, so the pin still names the code under test"
  - "The UAT was re-run against every head the amendments produced rather than editing the recorded SHA. A hand-edited library_head is exactly the repudiation surface T-10-16 exists to prevent"
  - "Identifiers in all committed planning artefacts are pseudonymised against a private map held outside the repository. The published record names d073d5e00002 at fd00:2::; the physical device it refers to is a LIFX Tube (product 217, firmware 4.200) with no A record and a single ULA AAAA record"

patterns-established:
  - "Re-run the evidence, never retro-fit it: when the head moved, the hardware UAT was re-run rather than having its library_head rewritten"
  - "When an amendment introduces a SHA that the amendment itself invalidates, make the check SHA-agnostic instead of chasing a fixed point"

requirements-completed: [IPV6-01, IPV6-02, IPV6-03, IPV6-04]

coverage:
  - id: D1
    description: "PR #208 carries the whole phase as a single PR and reaches full CI green, including the codecov branch patch gate at 100% with zero partial branches"
    requirement: IPV6-01
    verification:
      - kind: other
        ref: "gh pr checks 208 — every check SUCCESS, none failing; deploy-docs skipping by design on a non-main ref"
        status: pass
      - kind: other
        ref: "10-COVERAGE-GAPS.md verified closed before the push: lifx.network.mdns at 100% line and branch, lifx.network.address at 100% line and branch with zero exemption markers"
        status: pass
    human_judgment: false
  - id: D2
    description: "The IPv6 control path is proven against real Thread hardware: a device whose only address is IPv6 is connected to, driven through set_power and set_color roundtrips with readback, and fully restored"
    requirement: IPV6-01
    verification:
      - kind: other
        ref: "10-UAT-RESULTS.json — stages.connect passed, stages.control passed, restored true, library_head equal to the merged head"
        status: pass
      - kind: other
        ref: "probe stage 1 shows the target with `A: (none)` and a single ULA AAAA record, so the run cannot have fallen back to IPv4"
        status: pass
    human_judgment: true
    rationale: "No automated test can reach a physical Thread device. The operator named the target, approved the mutating run, and confirmed the record reflects a genuine run — the blocking-human gate D-22 and SPEC R9 exist for exactly this."
  - id: D3
    description: "Exactly one gate artefact exists and every field it certifies is enforced"
    requirement: IPV6-01
    verification:
      - kind: other
        ref: "the plan's Task 2 validator run verbatim — XOR, schema_version, kind, phase, device_serial against the known Thread serials, timezone-aware timestamp inside the seven-day window, library_head against the PR head, both stages passed, streaming recorded, restored true: 'gate artefact ok'"
        status: pass
    human_judgment: false
  - id: D4
    description: "The series lands on main with every signature and DCO trailer intact"
    requirement: IPV6-01
    verification:
      - kind: other
        ref: "git verify-commit exits 0 for every SHA the merge adds to main, and each carries a Signed-off-by trailer"
        status: pass
      - kind: other
        ref: "79a5ce09b71ea076d1065953aee72609e154fa0a is present unmodified and is the oldest commit in main..HEAD; redding1 is credited by Co-Authored-By on the squashed commit"
        status: pass
    human_judgment: false

duration: TBD
completed: 2026-08-28
status: complete
---

## Accomplishments

- **The phase is deliverable.** A caller can connect to, control and stream animation frames to a
  LIFX device whose only address is IPv6 — proven against an emulator on `::1` in CI on every
  matrix cell that can bind IPv6 loopback, and proven once against a real Thread-only device on
  the operator's fleet.
- **All four branch-audit findings are closed.** B9 (the `":" in ip` heuristic written out three
  times) collapsed into `lifx.network.address`; B2 (a zone-less link-local logged a warning and
  then cost a silent 16-second timeout) now raises at all four public entry points; B1 (an IPv6
  literal on an `AF_INET` socket surfaced as an indistinguishable timeout) fails typed at send
  time; B4 (three stale docstrings claiming the mDNS group was joined) is corrected.
- **Nothing was weakened to get green.** No test deleted, no skip added, no `pragma: no cover`
  added; three exemption markers came *off* `devices/base.py` on the way. `pyproject.toml` and
  `codecov.yml` are byte-identical to `main`, so the 100% branch patch gate was met by covering
  the code rather than by narrowing what the gate measures.
- **The IPv6 tests cannot pass silently over IPv4.** Every emulator-backed IPv6 test asserts the
  family of the socket the call actually used, read off the real socket. `LIFX_REQUIRE_IPV6=1` on
  the ubuntu/Python 3.10 cell turns a skip into a failure naming its cause, so the suite can never
  report green by skipping everywhere at once.
- **Hardware UAT passed on a genuinely IPv6-only device.** The probe's own record sweep shows the
  target with `A: (none)` and one ULA AAAA record; its OMR prefix had drifted since the previous
  run, which is why the probe identifies targets by serial and never by address.
- **The commit series is honest about its authorship.** redding1's original commit survives
  byte-identically at the base of the stack with its own sign-off, and is additionally credited by
  `Co-Authored-By` on the squashed commit.

## Task Commits

1. **Task 4: gate artefact and phase summary** — `10-UAT-RESULTS.json` and this file, committed
   together on the feature branch as the last commit before the fast-forward (D-22).

Tasks 1 to 3 produce no commits of their own by design: Task 1 pushes and opens the PR, Task 2 is
the hardware run and its blocking-human confirmation, Task 3 is the one-way merge decision.

## Files Created/Modified

**Created:** `10-UAT-RESULTS.json`, `10-06-SUMMARY.md`
**Modified:** `10-SPEC.md`, `10-06-PLAN.md`, `10-CONTEXT.md` (all three amended in the squashed
commit, per D-25)

## The `library_head` fixed point

`10-UAT-RESULTS.json` records `library_head` so a UAT record cannot be quietly reused across a
code change. That makes the record and its own commit mutually constraining: writing the record
into a commit changes that commit's SHA, which invalidates the SHA the record just recorded.
There is no fixed point.

The resolution is the one the plan already specified: the record lands in a **separate, docs-only**
commit on top of the code it certifies. `library_head` then names the head the library code was
actually tested at, and the artefact commit changes no library code, so the pin stays meaningful.

Two amendment rounds were needed to reach a stable head. The first amendment hardcoded the
then-current head SHA into 10-06's Task 4 check and into D-25's proof table — SHAs that the
amendment itself invalidated. Those references were made SHA-agnostic (the
`feat/ipv6-thread-support` ancestor check already covers the head; only `79a5ce0`, which is
genuinely fixed, stays pinned by SHA), and the UAT was re-run after each. It was re-run, never
retro-fitted: editing a recorded `library_head` by hand is precisely the repudiation surface
T-10-16 exists to prevent.

## Decisions Made

See `key-decisions` above. The two that shaped the phase's ending are D-24 (origin-only pushes)
and D-25 (the squash, and the acceptance-criteria amendment it forced).

## Deviations from Plan

### 1. [Rule 3 — Blocking] The merge gate was held, then lifted

- **Plan expectation:** Task 3 presents the one-way merge decision and proceeds on approval.
- **What happened:** The operator answered HOLD. Execution stopped at the gate with Tasks 3 and 4
  incomplete, and three operator-directed pieces of work followed before the hold was lifted: a
  conventional-commit scope rewrite, a PII scrub of the working tree and PR description, and the
  squash.
- **Why this is correct:** a `blocking-human` gate that can be talked past is not a gate. The
  orchestrator's job at HOLD is to stop and report, which is what happened.

### 2. [Rule 2 — Amendment] SPEC AC 17 and three 10-06 checks were amended after the squash

- **Issue:** the squash made four checks unsatisfiable as literal text: SPEC AC 17 and 10-06's
  must-have truth ("all three replayed commits"), Task 1's three-subject `git log --reverse` read,
  Task 4's `grep` for a commit subject the squash removed, and Task 4's fixed `-25` trailer window
  which assumed the pre-squash stack depth.
- **Fix:** each was amended to assert the criterion's original intent. See D-25 for the full
  reasoning and for why this is strictly stronger, not weaker, than what it replaced.
- **Verification:** all four amended assertions were run against the branch before the merge and
  pass.

### 3. [Rule 1 — Correction] Committed identifiers are pseudonymised

- **Issue:** the probe writes the real device serial and address into the UAT record. The
  operator directed that local network information not be published.
- **Fix:** the record's `device_serial` and `device_ip` are rewritten against a private map held
  outside the repository, consistently with every other committed artefact in this phase. A
  repository-wide sweep for the real identifiers returns nothing.

## Issues Encountered

- **The Thread target's OMR prefix had drifted** between the first UAT attempt and the re-runs.
  This is expected: OMR prefixes are auto-generated ULAs that re-derive whenever the border router
  re-forms the mesh. The durable identifier is the serial, which is what `--serial` selects on.

## Known Stubs

None.

## Threat Flags

- **T-10-16 (repudiation: fabricated or mis-attributed UAT pass)** — mitigated as designed. The
  record was re-run against each head rather than edited, the validator pins schema, kind, device,
  timestamp window and `library_head`, and the operator confirmed the run at the blocking gate.
- **T-10-17 (tampering: signature loss at merge)** — mitigated as designed. The merge is a local
  `--ff-only`, and `main`'s own ruleset requires signatures while allowing only rebase merges
  through the web UI, so the button would have stripped the signatures its ruleset then rejects.

## Verification Record

| Check | Result |
|---|---|
| `gh pr checks 208` | every check SUCCESS; `deploy-docs` skipping by design off `main` |
| `git verify-commit` over `main..HEAD` | exit 0 on every commit |
| `Signed-off-by` on every commit `main..HEAD` | present |
| Oldest commit in `main..HEAD` | `79a5ce0`, redding1's, unmodified |
| Task 2 gate validator | `gate artefact ok` |
| `git diff` against the pre-squash tree | empty |
| PII sweep over `.planning/` | 0 hits |

## User Setup Required

None.

## Next Phase Readiness

Phase 11 hardens what landed: the mDNS rewrite's `_LifxRecordCache` DoS bounds, the PTR
retransmission slot and the follow-up A/AAAA query loop are the behaviours 10-01 measured as
untested. THREAD-05 (Thread frame-rate ceilings) remains deferred; the streaming stage exists and
is recorded as `not_run`, which is the honest value for a run that was not made.

## Self-Check: PASSED
