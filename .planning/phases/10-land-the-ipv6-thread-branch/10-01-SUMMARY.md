---
phase: 10-land-the-ipv6-thread-branch
plan: 01
subsystem: network
tags: [ipv6, thread, rebase, mdns, udp, transport, coverage]

requires: []
provides:
  - "feat/ipv6-thread-support rebased onto the tip of main as a verified pure replay of b49400b, b88cdb9 and 2f884f5"
  - "IPv6 address-family seam live in the working tree: devices/base.py accepts IPv6, connection.py binds the :: wildcard, transport.py and animator.py open AF_INET6 sockets"
  - "src/lifx/network/mdns/discovery.py + dns.py rewrite (_LifxRecordCache, _pick_address, PTR retransmit, follow-up A/AAAA queries, build_address_query, _encode_name)"
  - "scripts/ipv6_thread_probe.py, the 521-line three-stage hardware probe that plan 10-05 turns into the UAT harness"
  - "10-COVERAGE-GAPS.md, the measured branch patch-coverage debt with per-file owning plans"
affects: [10-02, 10-03, 10-04, 10-05, 10-06]

actuals:
  tokens: 78000
  tasks: 2
  commits: 4

tech-stack:
  added: []
  patterns:
    - "Address-family seam: the socket family follows the address at each of the three socket-creation sites"

key-files:
  created:
    - scripts/ipv6_thread_probe.py
    - .planning/phases/10-land-the-ipv6-thread-branch/10-COVERAGE-GAPS.md
  modified:
    - src/lifx/network/mdns/discovery.py
    - src/lifx/network/mdns/dns.py
    - src/lifx/network/mdns/transport.py
    - src/lifx/network/transport.py
    - src/lifx/network/connection.py
    - src/lifx/devices/base.py
    - src/lifx/animation/animator.py
    - tests/test_network/test_mdns/test_discovery.py
    - tests/test_network/test_mdns/test_transport.py
    - tests/test_animation/test_animator.py

key-decisions:
  - "Topology: the 23 planning commits were replayed on top of the three rebased code commits (human decision at the Task 1 checkpoint), rather than rebasing feat/ipv6-thread-support in isolation, which would have dropped 29 tracked planning files from the working tree"
  - "feat/ipv6-thread-support and gsd/phase-10-land-the-ipv6-thread-branch now resolve to the same SHA, so plan 10-04's branch precondition and GSD's own branch tracking are both satisfied"
  - "The plan's step 0 premise that local main carries planning commits origin/main lacks was false: both were ed17fdb. The preflight ancestor assertion still passed and the rebase base was unaffected"
  - "scripts/ipv6_thread_probe.py is unmeasured by --cov rather than uncovered; plan 10-05 owns the treatment and must not widen --cov inside a 100% patch target"

patterns-established:
  - "Measure patch-coverage debt in the wave that lands the code, not the wave that opens the PR (review finding 3, threat T-10-19)"

requirements-completed: [IPV6-01]

coverage:
  - id: D1
    description: "The three branch commits are replayed onto main as a verified pure replay"
    requirement: IPV6-01
    verification:
      - kind: other
        ref: "git diff --quiet 2f884f5 HEAD -- src/lifx/network src/lifx/animation src/lifx/devices/base.py scripts/ipv6_thread_probe.py tests/test_network/test_mdns tests/test_animation"
        status: pass
      - kind: other
        ref: "git log --reverse main..HEAD --format=%s | head -3"
        status: pass
    human_judgment: false
  - id: D2
    description: "Each replayed commit carries a good GPG signature and its original DCO Signed-off-by trailer"
    verification:
      - kind: other
        ref: "git verify-commit 79a5ce0 b641e22 0d715f0 (each exit 0); trailer counts redding1=1, Avi Miller=2"
        status: pass
    human_judgment: false
  - id: D3
    description: "The full suite passes on the rebased head with no test deleted, skipped or weakened"
    verification:
      - kind: unit
        ref: "uv run --frozen pytest (3526 passed, 12 deselected)"
        status: pass
      - kind: other
        ref: "uv run pyright (0 errors); uv run ruff check . ; uv run ruff format --check ."
        status: pass
      - kind: other
        ref: "git diff main 0d715f0 --name-status --diff-filter=DR -- tests/ (empty); no added pytest.skip/xfail; no added pragma: no cover"
        status: pass
    human_judgment: false
  - id: D4
    description: "A Light controls an in-process emulator bound to ::1 over an AF_INET6 socket (tracer proof for IPV6-01)"
    requirement: IPV6-01
    verification:
      - kind: manual_procedural
        ref: "scratchpad/ipv6_tracer_smoke.py (throwaway, not committed) - verbatim output in this SUMMARY"
        status: pass
    human_judgment: true
    rationale: "The proof is a throwaway script whose only durable evidence is the console transcript below. Plan 10-04 replaces it with committed fixtures and tests in tests/test_api/test_ipv6_e2e.py; until then a human should confirm the transcript, not a green CI job."
  - id: D5
    description: "The branch's patch-coverage debt is enumerated per file with an owning plan"
    verification:
      - kind: other
        ref: "10-COVERAGE-GAPS.md; heading set equals git diff main HEAD --name-only -- 'src/lifx/*' 'scripts/*'; Totals table present"
        status: pass
    human_judgment: false

duration: 25 min
completed: 2026-08-27
status: complete
---

# Phase 10 Plan 01: Rebase the IPv6/Thread Branch Summary

**`feat/ipv6-thread-support` replayed onto `main` byte-identically across all 11 branch paths, signatures and DCO trailers intact, 3526 tests green, an IPv6-only `Light` driven end-to-end against an emulator on `::1`, and 16 uncovered lines plus 10 partial branches of patch-coverage debt measured and assigned to plans 10-02, 10-03 and 10-05.**

## Performance

- **Duration:** 25 min
- **Started:** 2026-08-27T11:27:00Z (approximate)
- **Completed:** 2026-08-27T11:52:13Z
- **Tasks:** 2
- **Files modified:** 12 (11 replayed branch paths + 1 new phase artefact)

## Accomplishments

- The three branch commits sit at the base of the stack on top of `main`, and the path-restricted diff against the pre-rebase head `2f884f5` is empty, so the replay altered no branch content.
- All 26 commits between `main` and the new head carry a good GPG signature (`%G?` is `G` for all 26, key `66D6066620F03B05`), and the three replayed commits keep their original DCO trailers: `redding1` once, `Avi Miller <me@dje.li>` twice.
- The full local gate is green with nothing weakened: 3526 passed, pyright 0 errors, ruff check and ruff format clean, zero test deletions, zero added skips, zero added `pragma: no cover`.
- IPv6 control proven end-to-end: a `Light` at `::1` completed a `get_color()` read and a `set_color()` write over a socket whose family is `socket.AF_INET6`.
- `10-COVERAGE-GAPS.md` records the debt the merge would otherwise have discovered late: 16 uncovered lines and 10 partial branches, every one assigned to an owning plan.

## Task Commits

Task 1 produces no new commit of its own. Its artefact **is** the rewritten history, and it left no working-tree change to stage. The commits it produced are the replayed ones:

1. **Task 1 (replay 1/3): `feat(network): support IPv6 Thread devices in discovery and connections`** - `79a5ce0` (was `b49400b`)
2. **Task 1 (replay 2/3): `feat(scripts): add IPv6/Thread mDNS hardware probe`** - `b641e22` (was `b88cdb9`)
3. **Task 1 (replay 3/3): `fix(animation): follow the device address family in the frame socket`** - `0d715f0` (was `2f884f5`)
4. **Task 2: coverage gap list + plan metadata** - the single documentation commit at the tip of the branch (`HEAD`), per the plan's explicit instruction to commit `10-COVERAGE-GAPS.md` together with this SUMMARY.

The 23 planning commits were replayed above the three code commits (see Deviations), rewriting their SHAs. `d559ace` became `ab37d07`; the head before the documentation commit was `ab37d07`.

## Preflight record (Task 1 step 0)

```
$ git rev-parse main origin/main
ed17fdb07486a3c118e38f4fcb497c996a57af56
ed17fdb07486a3c118e38f4fcb497c996a57af56

$ git merge-base --is-ancestor origin/main main; echo $?
0
```

`origin/main` is an ancestor of local `main`, which is what the preflight required, so the rebase base was sound. The plan's stated expectation that local `main` would carry extra planning commits did not hold: the two refs are identical, and every Phase 10 planning commit lived on `gsd/phase-10-land-the-ipv6-thread-branch`. That discovery is what produced the Task 1 checkpoint and the topology decision below.

## Pure-replay and signature proof

```
$ git diff 2f884f5 HEAD -- src/lifx/network src/lifx/animation src/lifx/devices/base.py \
      scripts/ipv6_thread_probe.py tests/test_network/test_mdns tests/test_animation
(no output)

$ git log --reverse main..HEAD --format=%s | head -3
feat(network): support IPv6 Thread devices in discovery and connections
feat(scripts): add IPv6/Thread mDNS hardware probe
fix(animation): follow the device address family in the frame socket

$ for sha in 79a5ce0 b641e22 0d715f0; do git verify-commit $sha; done
exit 0, exit 0, exit 0

$ git log -1 --format='%h %G? %GK %GS' <each>
79a5ce0 G 66D6066620F03B05 Avi Miller <me@dje.li>
b641e22 G 66D6066620F03B05 Avi Miller <me@dje.li>
0d715f0 G 66D6066620F03B05 Avi Miller <me@dje.li>

DCO trailers: 79a5ce0 -> redding1 <redding1@users.noreply.github.com>
              b641e22 -> Avi Miller <me@dje.li>
              0d715f0 -> Avi Miller <me@dje.li>
```

`backup/ipv6-thread-pre-rebase` still resolves to `af1707183cbfacfea4fe04b5fe90a9ddc2d73ca7`, untouched per D-20.

## Tracer end-to-end proof (verbatim)

Throwaway script under the session scratchpad, run with `uv run python`, not committed. The first run happened to pick a target colour identical to the emulator's default, which would have proven nothing about the write, so the target is now derived from the pre-write reading (`hue + 137`) to force an observable change.

```
{'class': 'Device', 'method': '__init__', 'action': 'is_loopback', 'ip': '::1'}
{'class': 'Device', 'method': '__init__', 'action': 'non_standard_port', 'port': 63395, 'default_port': 56700}
[emulator] started, bind_address='::1' port=63395
[get_color] colour=Hue: 119.9981689453125, Saturation: 1.0000, Brightness: 0.5000, Kelvin: 3500 power=65535 label='LIFX Color 000001'
[socket] family=<AddressFamily.AF_INET6: 30> sockname=('::', 63222, 0, 0)
[assert] socket family is socket.AF_INET6: PASS
[set_color] pre-write hue=119.9981689453125 -> target hue=256.9981689453125
[set_color] wrote=Hue: 256.9981689453125, Saturation: 0.2500, Brightness: 0.9000, Kelvin: 2500
[set_color] read back=Hue: 256.9976806640625, Saturation: 0.2500, Brightness: 0.9000, Kelvin: 2500
[assert] set_color changed device state over ::1: PASS
[emulator] stopped
[RESULT] IPv6 tracer smoke: PASS
```

Reading this transcript against the seam: the `is_loopback` warning fires exactly as D-13 predicted and was left alone. `sockname=('::', 63222, 0, 0)` shows `DeviceConnection._open()` picked the `::` wildcard from the `::1` target, and the 4-tuple plus `AddressFamily.AF_INET6` confirms `UdpTransport.open()` created an IPv6 endpoint. All four HSBK components changed on the write (hue 120 to 257, saturation 1.0 to 0.25, brightness 0.5 to 0.9, kelvin 3500 to 2500), so the round trip is a genuine control operation and not a read of pre-existing state.

## Coverage measurement (Task 2)

Full detail in `10-COVERAGE-GAPS.md`. Headline:

| Owning plan | Uncovered lines | Partial branches |
|---|---|---|
| 10-02 (`devices/base.py`) | 1 | 1 |
| 10-03 (`mdns/discovery.py`, `mdns/dns.py`) | 15 | 9 |
| 10-05 (`scripts/ipv6_thread_probe.py`) | 0 measured (521 lines unmeasured) | 0 measured |
| **Total** | **16** | **10** |

The gaps cluster in exactly the three behaviours the mDNS rewrite added and no test drives: the `_LifxRecordCache` DoS bounds (the T-10-01 mitigation arms), the PTR retransmission slot, and the follow-up A/AAAA query loop with `build_address_query()`. `pyproject.toml` and `codecov.yml` are untouched.

One finding worth flagging beyond the plan's ask: `scripts/ipv6_thread_probe.py` is **unmeasured**, not uncovered. `addopts` declares `--cov=lifx --cov=generate_theme_data`, so the probe contributes no lines to `coverage.xml` at all, even though `codecov.yml` scopes the five Python flags to `scripts/`. Widening `--cov` would drop 521 unmeasured lines into a 100% patch target in the same PR, which is the shape of the false-green pressure T-10-19 exists to prevent. `10-COVERAGE-GAPS.md` records this as plan 10-05's explicit decision.

## Decisions Made

- **Topology.** The 23 planning commits were replayed on top of the three rebased code commits, and both `feat/ipv6-thread-support` and `gsd/phase-10-land-the-ipv6-thread-branch` were pointed at the result. This keeps the plan's "three oldest commits" acceptance criterion true (planning commits touch no scored source path), keeps every downstream plan able to read its own instructions, and matches D-18's single PR carrying code and planning docs together.
- **The tracer gate did not halt mid-flight.** `workflow.human_verify_mode` is unset, so the `end-of-phase` default (#3309) applies and the tracer verification is recorded as coverage entry D1/D4 for the end-of-phase verifier rather than stopping for a fresh executor spawn. The tracer `<verify>` was re-run end-to-end and passed before Task 2 began.
- **The write target is derived from the pre-write reading.** A fixed target colour silently matched the emulator default, so the assertion would have passed without any write reaching the device.

## Deviations from Plan

### 1. [Rule 3 - Blocking] The plan's step 0 premise about `main` versus `origin/main` was false

- **Found during:** Task 1, preflight
- **Issue:** The plan states "Local `main` legitimately carries planning commits that `origin/main` does not." Both refs were `ed17fdb`. All 23 Phase 10 planning commits lived on `gsd/phase-10-land-the-ipv6-thread-branch`, so a bare `git switch feat/ipv6-thread-support` would have dropped 29 tracked files (all six Phase 10 plans, `10-SPEC.md`, `10-CONTEXT.md`, `10-PATTERNS.md`, `10-REVIEWS.md`, `10-DISCUSSION-LOG.md`, five `.planning/research/*.md`, the v1.2 milestone archive and more) from the working tree, leaving later plans unable to read their own instructions.
- **Fix:** Escalated as a `blocking-human` decision checkpoint. The human selected the "stack the planning commits on top of the rebased branch" topology. Executed as `git rebase --onto main 42c9ad2 feat/ipv6-thread-support`, then `git rebase --onto feat/ipv6-thread-support main gsd/phase-10-...`, then `git branch -f feat/ipv6-thread-support gsd/phase-10-...` and `git switch feat/ipv6-thread-support`. Both rebases were conflict-free.
- **Files modified:** none; git refs only
- **Verification:** preflight ancestor assertion still exits 0; the path-restricted pure-replay diff is empty; the three replayed commits are the three oldest in `main..HEAD`
- **Committed in:** the replay itself (`79a5ce0`, `b641e22`, `0d715f0`)

### 2. [Rule 3 - Blocking] Two Task 1 verification commands assumed a three-commit branch and had to be re-aimed

- **Found during:** Task 1, steps 4 and the acceptance criteria
- **Issue:** The plan reads the DCO trailers with `git log -3 --format=%B`, which under the chosen topology returns the three newest commits (planning commits), not the three replayed ones. The same applies to `git rev-list --reverse main..HEAD`, which now yields 26 SHAs.
- **Fix:** Took the first three SHAs from `git rev-list --reverse main..HEAD` and ran `git verify-commit` and the trailer read against those exact SHAs. This is strictly stronger than the positional `-3` form and matches the plan's own stated intent (the Codex review finding that motivated `git verify-commit` in the first place).
- **Verification:** three `verify-commit` exit-0 results; trailer counts `redding1`=1, `Avi Miller <me@dje.li>`=2
- **Committed in:** n/a (verification only)

### 3. [Rule 3 - Blocking] Task 2's last acceptance criterion counts 12 paths, not 11

- **Found during:** Task 2, acceptance verification
- **Issue:** `git diff main HEAD --name-only -- src/ tests/ scripts/` returns 12 paths. The extra one is `tests/test_theme/test_ceiling_supersession.py`, introduced by replayed planning commit `02e352c` (originally `7ae518f`, "guard the 25 superseded ceiling palettes"), which is unrelated to this phase and predates it.
- **Fix:** Verified the criterion's actual intent (that this task added no test and no source line) against the replayed code tip instead: `git diff main 0d715f0 --name-only -- src/ tests/ scripts/` returns exactly the 11 branch paths. No source or test line was added by Task 2.
- **Verification:** 11 paths from the code tip; `git diff main HEAD --name-only -- pyproject.toml codecov.yml` empty
- **Committed in:** n/a (verification only)

### 4. [Rule 1 - Bug] The tracer smoke test's first target colour matched the device's existing state

- **Found during:** Task 1, step 6
- **Issue:** The first version asserted a round trip to a hardcoded HSBK that happened to equal the emulator colour light's default (hue 120, saturation 1.0, brightness 0.5, kelvin 3500). The assertion would have passed even if `set_color()` never reached the device, making the tracer proof vacuous on its write path.
- **Fix:** Derived the target from the pre-write reading (`hue + 137`, plus distinct saturation, brightness and kelvin) and added an explicit assertion that the read-back differs from the pre-write value.
- **Files modified:** scratchpad script only (throwaway, not committed)
- **Verification:** the transcript above shows all four HSBK components changing
- **Committed in:** n/a

---

**Total deviations:** 4 auto-fixed (3 blocking, 1 bug). One of the blocking items required and received a human decision before execution began.
**Impact on plan:** No scope creep. Deviations 1 to 3 are consequences of a single incorrect premise in the plan's step 0 about branch topology; the plan's substantive requirements (pure replay, signatures, DCO, green gate, IPv6 proof, measured debt) were all met as written. Deviation 4 strengthened the tracer proof.

## Issues Encountered

- **`git verify-commit` output initially looked like a failure** because the verification loop ran under `zsh`, which does not word-split unquoted parameters, so a three-line SHA string was passed to `git` as one argument. Re-run with `while read`, all three exit 0. No change to the repository.

## Consequences to carry forward

**`feat/ipv6-thread-support` now requires a force-push.** It is published to the `redding1` remote, and `git switch` reported the branch and `redding1/feat/ipv6-thread-support` have diverged. This rebase also rewrote the SHAs of all 23 planning commits (`d559ace` became `ab37d07`). Those planning commits were unpushed and exist nowhere else, which is why `backup/phase-10-pre-rebase` was created before the rewrite. Plan 10-06 owns the push and must use `--force-with-lease`. Nothing was pushed in this plan.

**Safety refs to retire after the phase verifies** (leave in place until then):

| Ref | SHA | Protects |
|---|---|---|
| `backup/phase-10-pre-rebase` | `d559ace` | the 23 planning commits (unpushed) |
| `backup/feat-ipv6-thread-pre-rebase` | `2f884f5` | the pre-rebase feature branch tip |
| `backup/ipv6-thread-pre-rebase` | `af17071` | pre-existing, untouched per D-20 |

**`IPV6-01` was not marked complete.** `requirements ready-ids` reports 0 of 1 ready: a sibling plan in this phase also declares `IPV6-01` and has not produced a SUMMARY yet. It will mark automatically when the last declaring plan finishes.

**A stale claim worth correcting later:** CONTEXT D-18 states `codecov.yml` has "no `flags:` key, so the status is computed against the merged report". `codecov.yml` now carries a `flags:` block scoping all five Python flags to `src/lifx/` and `scripts/`. This does not change any decision in this plan, but plan 10-06 should not rely on the "merged report" phrasing.

## User Setup Required

None. No external service configuration was required.

## Next Phase Readiness

- Wave 2 can start. The branch content is in the working tree, so the `10-PATTERNS.md` line references marked *(branch)* now resolve.
- Plan 10-02 has its owning gaps written down: `devices/base.py` lines 522 and 527, which close together with the B2 warning-to-raise flip.
- Plan 10-03 has the larger share: 15 uncovered lines and 9 partial branches across `mdns/discovery.py` and `mdns/dns.py`, concentrated in the record-cache bounds, the PTR retransmission slot and the follow-up address-query loop.
- Plan 10-04's precondition ("current branch is `feat/ipv6-thread-support`") is satisfied, and the tracer script under the scratchpad is the shape its `emulator_server_ipv6` fixture and `tests/test_api/test_ipv6_e2e.py` should take.
- **No blockers.**

## Self-Check: PASSED

Files claimed as created/modified exist on disk (`10-01-SUMMARY.md`, `10-COVERAGE-GAPS.md`,
`scripts/ipv6_thread_probe.py`, `src/lifx/network/mdns/discovery.py`,
`src/lifx/animation/animator.py`). All three replayed commits resolve in `git log --all`
(`79a5ce0`, `b641e22`, `0d715f0`), and the documentation commit carrying this file is `HEAD`. The documentation commit deleted no tracked
file, carries a good signature under key `66D6066620F03B05` and a `Signed-off-by: Avi Miller
<me@dje.li>` trailer. `feat/ipv6-thread-support`, `gsd/phase-10-land-the-ipv6-thread-branch`
and `HEAD` all resolve to the same SHA, with `feat/ipv6-thread-support` checked out and the
working tree clean. The documentation commit's own hash is deliberately not quoted here: a
commit cannot name itself, and the self-check ran against the amended commit.

---
*Phase: 10-land-the-ipv6-thread-branch*
*Completed: 2026-08-27*
