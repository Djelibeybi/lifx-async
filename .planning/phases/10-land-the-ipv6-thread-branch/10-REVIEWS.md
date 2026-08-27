---
phase: 10
reviewers: [codex, opencode, antigravity]
reviewed_at: 2026-08-27T10:36:36Z
plans_reviewed: [10-01-PLAN.md, 10-02-PLAN.md, 10-03-PLAN.md, 10-04-PLAN.md, 10-05-PLAN.md, 10-06-PLAN.md]
models:
  codex: "gpt-5.6-sol (reasoning=high)"
  opencode: "openrouter/z-ai/glm-5.3 (reasoning=high)"
  antigravity: "gemini-3.1-pro-high"
model_sources:
  codex: "pinned"
  opencode: "pinned"
  antigravity: "pinned"
---

# Cross-AI Plan Review — Phase 10

## Codex Review

# Cross-AI Plan Review: Phase 10

## Summary

The phase is well decomposed and respects the locked scope. Its dependency chain correctly forces the rebase before branch-dependent work, then joins the independent CI-fixture and UAT-harness work before release. However, it is not execution-ready: Plan 10-04 contains an unworkable socket setup, Plan 10-05 cannot safely restore a MatrixLight and lacks executable tests for substantial new branching logic, and Plans 10-03/10-06 have state and gate inconsistencies. Overall risk is **HIGH** until these are revised.

Source verification was performed from a clean `main` checkout. The feature head, merge-base and backup ref match the plan: `2f884f5`, `42c9ad2`, and `af17071`. I did not refresh the remote tracking refs.

## Plan 10-01: Rebase and tracer proof

### Summary

A strong, cautious rebase plan with exact commit and tree-equivalence checks. Minor internal contradictions make some acceptance criteria impossible after the required summary commit.

### Strengths

- Exact feature-head and merge-base preconditions make the history rewrite fail closed, and the restricted tree diff is a good pure-replay proof. [10-01-PLAN.md](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/10-land-the-ipv6-thread-branch/10-01-PLAN.md:92)
- The observed branch really has exactly the stated eleven-path surface, and `main` has not modified those paths since the merge-base.
- The tracer uses the real device → connection → transport path rather than mocking family selection. [10-01-PLAN.md](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/10-land-the-ipv6-thread-branch/10-01-PLAN.md:101)
- It correctly stops on an unexpected conflict and preserves the historical backup ref.

### Concerns

- **MEDIUM:** Acceptance requires `main..HEAD` to contain exactly three commits, but the plan then requires committing `10-01-SUMMARY.md`, making four commits. [10-01-PLAN.md](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/10-land-the-ipv6-thread-branch/10-01-PLAN.md:107), [10-01-PLAN.md](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/10-land-the-ipv6-thread-branch/10-01-PLAN.md:149)
- **LOW:** `git log --show-signature` is a presentation check rather than a strict per-commit verifier. [10-01-PLAN.md](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/10-land-the-ipv6-thread-branch/10-01-PLAN.md:99)
- **LOW:** The preflight does not fetch or record the relationship between local `main` and `origin/main`. That need not require equality because local `main` contains planning commits, but remote divergence should be detected before rebasing.

### Suggestions

- Assert the first three commits with `git log --reverse main..HEAD | head -3`, allowing the summary commit above them.
- Use `git verify-commit` on the exact replayed commit SHAs and separately validate DCO trailers.
- Fetch/prune first, then record `main`, `origin/main`, and their ancestry without changing local history.

### Risk Assessment

**MEDIUM.** The rebase mechanics are sound, but the commit-count criterion must be corrected.

---

## Plan 10-02: Shared address helper

### Summary

This is the strongest implementation plan. It centralises the right rules, explicitly targets branch coverage, and avoids the Phase 12 `find_by_ip()` implementation work. One public construction route remains unaddressed.

### Strengths

- The helper’s validation branches and both sides of `family_for()`/`wildcard_for()` are explicitly enumerated, suitable for the 100% branch-patch gate. [10-02-PLAN.md](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/10-land-the-ipv6-thread-branch/10-02-PLAN.md:98)
- The three existing heuristics are real on the branch at `network/transport.py:295`, `network/connection.py:234`, and `animation/animator.py:399`; the proposed helper removes that drift.
- The validation/derivation split correctly permits bind wildcards such as `::` while rejecting them at public device entry points. [10-02-PLAN.md](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/10-land-the-ipv6-thread-branch/10-02-PLAN.md:115)
- It does not implement valid-IPv6 `find_by_ip()` resolution, merged discovery, `tm`, or other deferred work.

### Concerns

- **MEDIUM:** `Device.connect()` is another public IP entry point and bypasses `Device.__init__` when no serial is supplied, constructing `DeviceConnection` before validation at `feat/ipv6-thread-support:src/lifx/devices/base.py:739-750`. The plan validates only `__init__`, `from_ip()` and `find_by_ip()`. [10-02-PLAN.md](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/10-land-the-ipv6-thread-branch/10-02-PLAN.md:184)
- **LOW:** The must-have says `fe80::1%en0` is accepted at all three named entry points, but the test behaviour only explicitly requires successful construction through `Device`. [10-02-PLAN.md](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/10-land-the-ipv6-thread-branch/10-02-PLAN.md:31), [10-02-PLAN.md](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/10-land-the-ipv6-thread-branch/10-02-PLAN.md:174)

### Suggestions

- Either validate at the start of `Device.connect()` or explicitly record it as a deliberate deferred gap in SPEC/CONTEXT.
- Add mocked acceptance tests proving scoped link-local addresses pass validation at `from_ip()` and `find_by_ip()` without waiting on real networking.

### Risk Assessment

**MEDIUM.** The core mechanism is sound; the main risk is incomplete coverage of public IP construction paths.

---

## Plan 10-03: Transport failure handling

### Summary

The send-time assertion and peer-error regression are well targeted. The mDNS cleanup needs to reset logical state as well as close the descriptor.

### Strengths

- The plan preserves the established endpoint-death versus peer-error distinction rather than changing `error_received()`. The branch explicitly treats only `EBADF` and `ENOTSOCK` as fatal at `feat/ipv6-thread-support:src/lifx/network/transport.py:164-190`.
- Both family-mismatch directions and the matching-family branch are planned, which should cover the new comparison fully. [10-03-PLAN.md](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/10-land-the-ipv6-thread-branch/10-03-PLAN.md:83)
- Forced failures at bind, socket option and endpoint creation directly exercise IPV6-04.

### Concerns

- **MEDIUM:** On endpoint-creation failure, the branch has already assigned `_socket` and `_protocol` before awaiting `create_datagram_endpoint()` at `feat/ipv6-thread-support:src/lifx/network/mdns/transport.py:95-105`. Its `is_open` property returns whether `_protocol` is non-`None` at line 227. Merely closing `sock`, as instructed, leaves a phantom-open transport that rejects future `open()` calls. [10-03-PLAN.md](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/10-land-the-ipv6-thread-branch/10-03-PLAN.md:125)
- **LOW:** The concurrency test specifies descriptor accounting but not state invariants or successful reopen after failure. [10-03-PLAN.md](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/10-land-the-ipv6-thread-branch/10-03-PLAN.md:128)

### Suggestions

- On every failed open, close the raw socket and clear `_socket`, `_protocol`, and `_transport`.
- Assert `is_open is False` and that a subsequent `open()` can succeed.
- Use events around the mocked endpoint await to make both race interleavings deterministic.

### Risk Assessment

**MEDIUM.** Descriptor cleanup may pass while leaving the transport permanently unusable.

---

## Plan 10-04: IPv6 emulator and CI proof

### Summary

The CI-cell design is good, but the fixture cannot work as written because it configures `IPV6_V6ONLY` after the socket is bound.

### Strengths

- The existing CI matrix does contain Ubuntu/Python 3.10 in both full and reduced configurations. [ci.yml](/Volumes/External/Developer/Djelibeybi/lifx-async/.github/workflows/ci.yml:150)
- A separate one-device IPv6 emulator avoids doubling the existing seven-device suite.
- Per-test family assertions are useful protection against a false IPv6 green.

### Concerns

- **HIGH:** The plan starts the emulator, then calls `setsockopt(IPV6_V6ONLY)`. [10-04-PLAN.md](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/10-land-the-ipv6-thread-branch/10-04-PLAN.md:88) The installed emulator binds inside `start()` before exposing its transport. [server.py](/Volumes/External/Developer/Djelibeybi/lifx-async/.venv/lib/python3.14/site-packages/lifx_emulator/server.py:515) On this machine, setting `IPV6_V6ONLY` after that bind raises `OSError: [Errno 22] Invalid argument`.
- **MEDIUM:** The Animator test proves only that a local IPv6 socket was created. `send_frame()` increments packet statistics immediately after `sendto()` and does not prove the emulator received or applied the frame. [animator.py](/Volumes/External/Developer/Djelibeybi/lifx-async/src/lifx/animation/animator.py:416), [10-04-PLAN.md](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/10-land-the-ipv6-thread-branch/10-04-PLAN.md:122)
- **MEDIUM:** Neither the skip path nor `LIFX_REQUIRE_IPV6=1` failure path is actually tested. Local and hosted Ubuntu runs only exercise the successful-bind path. [10-04-PLAN.md](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/10-land-the-ipv6-thread-branch/10-04-PLAN.md:87), [10-04-PLAN.md](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/10-land-the-ipv6-thread-branch/10-04-PLAN.md:152)

### Suggestions

- Create and configure the IPv6 socket before bind, then pass it to `create_datagram_endpoint(sock=...)` through a small test-only server subclass or runner. Alternatively, amend the explicit-`V6ONLY` criterion because a `::1`-specific bind already excludes IPv4 capture.
- Prove Animator delivery through emulator activity or colour readback after sending.
- Unit-test capability probing with mocked bind failure for both unset and required environment states.

### Risk Assessment

**HIGH.** The central fixture fails during setup on the verified development platform.

---

## Plan 10-05: Thread UAT harness

### Summary

Extending the existing probe is preferable to another hardware script, but the proposed state restoration is unsafe for the required MatrixLight target and the new logic lacks automated testing.

### Strengths

- The existing probe genuinely uses library mDNS, parsing and device primitives rather than reimplementing them.
- Streaming remains sequential, bounded and explicitly non-gating, respecting Phase 14’s measurement boundary. [10-05-PLAN.md](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/10-land-the-ipv6-thread-branch/10-05-PLAN.md:104)
- The output schema records honest failed/not-run outcomes and the tested commit.

### Concerns

- **HIGH:** Capturing `get_color()` and power cannot restore a MatrixLight’s per-pixel state. [10-05-PLAN.md](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/10-land-the-ipv6-thread-branch/10-05-PLAN.md:79) Matrix devices expose `get_all_tile_colors()` for full state and `set_matrix_colors()` for restoration. [matrix.py](/Volumes/External/Developer/Djelibeybi/lifx-async/src/lifx/devices/matrix.py:610), [matrix.py](/Volumes/External/Developer/Djelibeybi/lifx-async/src/lifx/devices/matrix.py:954) Both the control `set_color()` and Animator streaming can destroy the existing tile image.
- **HIGH:** The plan adds substantial conditional CLI, error-handling, mutation and JSON logic but verifies only `--help`, Ruff and Pyright. [10-05-PLAN.md](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/10-land-the-ipv6-thread-branch/10-05-PLAN.md:83) Pytest currently measures `lifx` and `generate_theme_data`, not `ipv6_thread_probe`. [pyproject.toml](/Volumes/External/Developer/Djelibeybi/lifx-async/pyproject.toml:107) Codecov nevertheless scopes every flag to `scripts/`. [codecov.yml](/Volumes/External/Developer/Djelibeybi/lifx-async/codecov.yml:16)
- **MEDIUM:** Restoration and `Animator.close()` are not explicitly required in `finally` blocks. A control or streaming exception could leave both device state and a socket behind. [animator.py](/Volumes/External/Developer/Djelibeybi/lifx-async/src/lifx/animation/animator.py:432)

### Suggestions

- Capture all MatrixLight tile colours and power before either mutating stage; restore them in `finally`, tile by tile, followed by power.
- Always close Animator in `finally`.
- Add a dedicated probe test module covering target selection, success/failure/not-run states, JSON writing, streaming non-gating behaviour, and restoration after injected failures.
- Include the probe in coverage collection or explicitly justify its coverage treatment without weakening the patch gate.

### Risk Assessment

**HIGH.** It can materially alter real hardware and currently has no executable proof of safe recovery.

---

## Plan 10-06: PR, UAT and merge

### Summary

The human gates and fast-forward strategy are appropriately conservative, but several automated checks do not enforce their stated acceptance criteria, and the exception/summary paths are internally inconsistent.

### Strengths

- CI, physical UAT, and the irreversible merge decision are separate gates. [10-06-PLAN.md](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/10-land-the-ipv6-thread-branch/10-06-PLAN.md:110)
- The XOR requirement prevents simultaneously claiming a UAT pass and an exception.
- A local `--ff-only` merge preserves rebased signatures and stops if `main` moves. [10-06-PLAN.md](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/10-land-the-ipv6-thread-branch/10-06-PLAN.md:189)

### Concerns

- **HIGH:** Coverage is deferred to last-minute reactive “top-up” work, while the local inspection explicitly limits itself to `src/lifx/*` and misses the changed probe script. [10-06-PLAN.md](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/10-land-the-ipv6-thread-branch/10-06-PLAN.md:93) The stated premise that `codecov.yml` has “no flags key” is factually false. [codecov.yml](/Volumes/External/Developer/Djelibeybi/lifx-async/codecov.yml:16)
- **MEDIUM:** The automated UAT validator does not enforce the named device, timestamp window, schema/kind, or `library_head`; the exception validator does not enforce a non-empty reason or THREAD-05 reference. [10-06-PLAN.md](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/10-land-the-ipv6-thread-branch/10-06-PLAN.md:136)
- **MEDIUM:** Task 4 names and stages only `10-UAT-RESULTS.json`, although the approved exception path may instead produce `10-EXCEPTION-OVERRIDE.json`. [10-06-PLAN.md](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/10-land-the-ipv6-thread-branch/10-06-PLAN.md:179)
- **MEDIUM:** `git log ... | head -3` checks the newest stacked commits, not the three base replay commits. [10-06-PLAN.md](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/10-land-the-ipv6-thread-branch/10-06-PLAN.md:104)
- **MEDIUM:** `10-06-SUMMARY.md` is required after the plan is done, but Task 4 has already merged and pushed the branch. The summary therefore cannot “land with the merge” without an additional unreviewed main commit. [10-06-PLAN.md](/Volumes/External/Developer/Djelibeybi/lifx-async/.planning/phases/10-land-the-ipv6-thread-branch/10-06-PLAN.md:236)

### Suggestions

- Resolve all patch coverage in Plans 10-01 through 10-05; Plan 10-06 should verify, not discover and implement unbounded test work.
- Correct the Codecov description to match the real flag configuration.
- Add a repository validator for both UAT artefact schemas and run it before the human checkpoint and merge.
- Parameterise Task 4 over whichever XOR artefact exists.
- Verify exact commit ranges with `git log --reverse` and `git verify-commit`.
- Define whether `10-06-SUMMARY.md` is committed before merge, intentionally follows in a separate signed commit, or is omitted from the one-PR promise.

### Risk Assessment

**HIGH.** The release gates are thoughtfully separated, but their automated enforcement currently falls short of the claims they certify.

## Overall Risk Assessment

**HIGH.** The wave structure, scope discipline, zero-dependency constraint and core address-helper design are strong. Execution should pause for revision because:

1. `IPV6_V6ONLY` cannot be configured at the planned point.
2. The hardware UAT can destroy MatrixLight tile state.
3. The UAT harness has no meaningful automated test or coverage path.
4. Failed mDNS opens can leave phantom-open state.
5. Final coverage, UAT, exception and summary gates contain factual or procedural contradictions.

No deferred Phase 11–14 feature work is improperly pulled into the plans; the issues are within Phase 10’s own implementation and verification mechanisms.


---

## OpenCode Review

# Phase 10 Plan Review — Cross-AI

## 1. Summary

Verified against the repo, not just the plan text. The six plans are unusually well-grounded: every file, line, commit SHA and fixture anchor I checked matches reality (three branch commits at head `2f884f5` with merge-base `42c9ad2`; the three `":" in` heuristic sites at branch `network/transport.py:295`, `network/connection.py:234`, `animation/animator.py:399`; the address-validation block at branch `devices/base.py:486-537`; the stale "joins the mDNS multicast group" docstring and the real socket leak in branch `mdns/transport.py:49-125`; `find_by_ip` at `src/lifx/api.py:906`; conftest anchors at 83/130/148/241/286; `ci.yml:161`'s dual-`fromJSON` matrix; `codecov.yml:12-14`'s 100% patch gate). The wave structure correctly forces the rebase (10-01) before everything consuming branch content. No scope creep: B3/B5/B6/B7/B8, FIND-06 family-aware bind, merged `discover()`, `tm` field and Thread retuning are all absent. Main risk is schedule-shaped, not correctness-shaped: the ~500-line mDNS rewrite has never been scrutinised under the 100% branch-patch gate, and that debt is discovered in Wave 5.

## 2. Strengths

- **Pure-replay premise is verified true.** `git diff 42c9ad2 main -- src/ tests/test_network tests/test_animation pyproject.toml` is empty — zero source changes on main since divergence, so the clean rebase and the "branch tests land unmodified and green" claim (D-19) rest on fact, not hope. The path-restricted `git diff 2f884f5 HEAD` replay proof is a genuinely strong verification mechanism.
- **The three-site inventory is exact.** `git grep '":" in ' feat/ipv6-thread-support -- src/` returns exactly the three sites the plans name, and nothing else — SPEC AC 8's repository grep will work as written, including its comment-text caveat.
- **B2/B4/IPV6-04 are all real defects confirmed in branch source.** The zone-less link-local case is a warning today (`base.py:521-536`), the `MdnsTransport` docstrings still claim group joining (`mdns/transport.py:3-5, 22-31`) while `open()` binds ephemeral, and `open()` leaks the socket if `bind`/`setsockopt` raises (sock created at line ~71, no close in the `except OSError` at ~116). The plans fix exactly what exists.
- **Emulator fixture mechanism verified.** `lifx_emulator/server.py:518-519` calls `create_datagram_endpoint(local_addr=(self.bind_address, self.port))` with no family argument, so `bind_address="::1"` infers `AF_INET6` exactly as SPEC Background claims. `tile_chain_server` (conftest:241) is the right template and `emulator_server`'s seven devices stay untouched.
- **D-02's validate/derive split is correct against Python semantics** — I verified `ipaddress.ip_address('fe80::1%en0').scope_id == 'en0'`, `ipv4_mapped` detection, and that `'fe80::1%'` fails the parse (landing in the malformed rule, satisfying AC 4's empty-zone case). `family_for("0.0.0.0")`/`family_for("::")` work because `family_for` deliberately skips the entry-point rules.
- **T-10-09 is the threat model earning its keep.** The B1 assertion is scoped as a pre-send guard only, and `UdpTransport.send()` (branch lines ~389-415) genuinely separates the "Socket not open" raise from `error_received`/`_FATAL_SOCKET_ERRNOS` — the plan forbids touching the latter and pins the contract with a parameterised errno test. That is the right guard against an over-eager fix.
- **R4 backstop honesty.** Because `open()` assigns `self._protocol` before its only `await`, a concurrent second `open()` most likely early-returns already — the plan treats the interleaving as a test to write, not a bug presupposed. Correct epistemics.
- **D-06 shape change is safe.** `rg "is_loopback|non_private_ip" tests/` finds nothing — no existing test asserts the old `class`/`method` warning shape, so the move to `module`/`function` keys breaks nothing.
- **Wave/dependency structure is sound.** 10-05 depends only on 10-03 (transitively 10-01) and touches only the probe script — correctly parallel with 10-04. 10-06 gates on both. The helper-before-fixes ordering (10-02 before 10-03's `family_for` consumer) is enforced by `depends_on`, not just narrative.

## 3. Concerns

- **MEDIUM — Branch-patch-coverage debt discovered at Wave 5.** The rebased mDNS rewrite (`mdns/discovery.py` ±328 lines, `dns.py` +38) predates the 100% branch-patch gate, as 10-06 Task 1 itself admits ("gaps are likely there"). Discovering the size of that debt in the merge plan — after the CI cycle, PR and UAT sequencing are already in motion — is the phase's biggest schedule risk, and it is also where "never weaken a check" faces its real temptation. `pyproject.toml:117` (`--cov=lifx --cov-branch`) means the gap can be measured locally at any time, so there is no reason to wait.
- **MEDIUM — `validate_address` rule order emits warnings before rejection.** Plan 10-02 Task 1's order is: parse → loopback warn → unspecified raise → non-private warn → zone-less raise → IPv4-mapped raise. An address that will be *rejected* (e.g. an IPv4-mapped literal that is not RFC1918-private) can emit a spurious warning first, because the mapped rejection sits at rule 7 after the rule-3/5 warnings. Cosmetic, but it contradicts "one home of the rules" cleanliness and is trivial to fix by ordering raises before warnings.
- **LOW — `--serial` flag is load-bearing in 10-06 but unverified in 10-05.** The branch probe's argparse (`scripts/ipv6_thread_probe.py:494-513`) has only `--timeout`, `--stage`, `--verbose` — no `--serial`. 10-05 Task 1's action text says to add serial targeting, but its acceptance criteria check only "the control stage and --uat-output" in `--help`. 10-06 Task 2's operator command depends on `--serial` existing. One missing flag turns the blocking checkpoint into a decode-failure loop.
- **LOW — `IPV6_V6ONLY` setsockopt after bind is not portable by contract.** The fixture sets it on the socket *after* `create_datagram_endpoint` has already bound it. Linux and macOS permit this on unconnected UDP sockets (and Windows is excluded from emulator tests anyway, per `conftest.py:148`), but if any platform refuses, the fixture raises and every IPv6 test fails rather than skips. Functionally inert on a `::1` bind, as the plan says — just wrap defensively or accept the risk knowingly.
- **LOW — e2e test reaches into `animator._socket.family`.** Private-attribute assertion is brittle against an Animator refactor; the connection-level tests use `get_extra_info("socket").family`, which is the supported surface. Consistent with the branch's existing mock-based family tests, so acceptable, but worth a note.
- **LOW — 10-01's tracer proof is unrecorded.** The `::1` smoke script is deliberately throwaway; the only durable evidence is the SUMMARY narrative. Fine for a tracer, and 10-04 turns it into committed tests — just make sure the SUMMARY captures the actual output, not just "it passed".

## 4. Suggestions

- **Measure patch coverage immediately after the rebase.** Add to 10-01's verify (or a first task of 10-02): `git diff main...HEAD --name-only -- src/` cross-referenced against the branch-coverage report, producing a written gap list. Distribute the top-up tests into the 10-02/10-03 fix commits where they belong; 10-06 Task 1 then verifies instead of discovers.
- **Reorder `validate_address`: all raises first (empty → parse → mapped → unspecified → zone-less), warnings last (loopback, non-private).** Costs nothing, removes the spurious-warning case, and makes the "single home" rule set cleaner to test.
- **Add `--serial` to 10-05 Task 1's `--help` acceptance criterion**, and to 10-06 Task 2's precondition check, since the operator command hard-depends on it.
- **In 10-04 Task 1, tolerate `IPV6_V6ONLY` setsockopt failure** (log-and-continue rather than raise) or assert it only where the option is settable — the hygiene value does not justify a fixture-hard-failure mode.
- **Consider asserting the family via `get_extra_info("socket").family` for the Animator too** if the socket is exposed through a transport; otherwise document the private-attribute dependency in the test so a refactor knows what to update.
- **10-06 Task 4's subject-grep** (`grep -q "follow the device address family in the frame socket"`) is anchored to a real commit subject today — good — but brittle if the series is ever re-authored; the `--is-ancestor` and signature checks already prove delivery, so the grep is redundant belt-and-braces (harmless).

## 5. Risk Assessment

**MEDIUM.** Correctness risk is low: every mechanism the plans assert (family inference, three heuristic sites, the leak, the docstring staleness, the validator semantics, the CI matrix shape, the clean-rebase premise) is confirmed in the repo, the dependency ordering genuinely enforces rebase-first, and the prohibitions plus threat register actively guard the two classic failure modes (weakening the coverage gate, breaking the peer-error contract). The residual risk is concentrated in (a) the deferred measurement of branch-patch coverage on the never-scrutinised mDNS rewrite, which threatens the Wave 5 timeline and creates late pressure against the "never weaken" prohibition, and (b) the human-gated UAT/merge sequencing, which is well-designed but where a single missing CLI flag (`--serial`) or unreachable device stalls the critical path. Both are manageable with the suggestions above; neither invalidates the plan set.

---

## Antigravity Review

# Cross-AI Plan Review: lifx-async v2.0 Phase 10

## Summary
The implementation plans for Phase 10 provide a rigorous, well-ordered approach to landing the `feat/ipv6-thread-support` branch while adding necessary validation, error handling, and test infrastructure. The phase correctly isolates the initial rebase as a tracer task, systematically introduces address validation and transport fixes in subsequent waves, and concludes with robust CI enforcement and hardware UAT. The plans strictly adhere to the defined scope and effectively defer out-of-scope requirements.

## Strengths
- **Strict Dependency Ordering**: The `depends_on` structure perfectly mirrors the wave progression. Changes to `network/address.py` in Plan 10-02 are correctly sequenced before Plan 10-03 consumes them for the send-time family assertion at `src/lifx/network/transport.py`.
- **Robust Hardware Validation**: Plan 10-05 extends the `scripts/ipv6_thread_probe.py` script to include state restoration (capturing and restoring color/power), safely mitigating T-10-13 (Tampering with live device state).
- **CI Safety Nets**: Plan 10-04 forces the IPv6 test suite to run on the `ubuntu-latest`/`3.10` matrix cell by failing if `::1` is unavailable (via `LIFX_REQUIRE_IPV6=1` in `.github/workflows/ci.yml`), preventing silent test skips (T-10-10).
- **Explicit Scope Boundaries**: The plans explicitly avoid scope creep. For instance, `find_by_ip()` at `src/lifx/api.py:906` adds fast-failure for missing zone identifiers but explicitly defers full IPv6 resolution to Phase 12, matching the SPEC.

## Concerns
- **[MEDIUM] Open-Ended Coverage Requirement for mDNS Rewrite**: Plan 10-06 Task 1 instructs the agent to dynamically inspect branch coverage gaps (especially for the `network/mdns/discovery.py` rewrite landed in Plan 10-01) and write tests to achieve 100% patch coverage before pushing. The `_LifxRecordCache` and DNS accumulation logic are complex; tasking the agent to close these gaps on the fly without a dedicated, specified test plan risks producing fragile tests or stalling the PR process.
- **[LOW] Type Enforcement in `validate_address`**: `validate_address` in Plan 10-02 specifies `ip: str | None`, but at runtime, `ipaddress.ip_address()` will happily parse integers (e.g., `12345` -> `0.0.48.57`). While Pyright catches this for internal usages, external callers passing an integer could bypass validation or experience unexpected behavior.

## Suggestions
- **Pre-define mDNS Test Scenarios**: Instead of relying on the agent to dynamically close coverage gaps during Plan 10-06, consider adding a dedicated task in an earlier plan (e.g., in Plan 10-04) that explicitly defines the required test scenarios for `_LifxRecordCache` (e.g., testing partial packets, bounds checking, and `pending_targets` limits).
- **Explicit Type Checking**: Add an `isinstance(ip, str)` check in `validate_address` before passing the address to `ipaddress.ip_address()`, explicitly raising a `ValueError` for integers and bytes to prevent implicit coercion.
- **Fixture Assertion**: In `tests/conftest.py` (`get_free_port6`), assert that the returned port number is `> 0` to fail fast if port binding silently fails and returns `0`.

## Risk Assessment
**LOW**
The plans are exceptionally detailed, with clear rollback paths, explicit prohibitions against scope creep (e.g., no Thread retuning, no dependencies added), and robust verification steps. The manual UAT gate and the strict CI requirements significantly lower the risk of merging unstable code. The only notable risk is the dynamic test generation for the mDNS rewrite, which is contained to the testing phase and does not threaten production behavior.

---

## Consensus Summary

Three reviewers, three different risk verdicts: **Codex HIGH**, **OpenCode MEDIUM**,
**Antigravity LOW**. That spread is itself the finding, and it tracks evidence density
almost exactly — Codex cited 41 `file:line` locations, OpenCode 13, Antigravity 1.
Antigravity's review declared source grounding but is substantially a restatement of the
plans' own claims, so its LOW verdict is **not counted at full consensus weight**.

Where the reviewers contradicted each other on a HIGH finding, the orchestrator verified
the claim directly rather than averaging the opinions. Six checks were run; **Codex was
correct on all six**, including one where OpenCode explicitly disagreed:

| Contested claim | Verified result |
|---|---|
| `setsockopt(IPV6_V6ONLY)` after bind fails (10-04) | **Codex correct.** `OSError: [Errno 22] Invalid argument` on macOS. OpenCode's "Linux and macOS permit this" is wrong. |
| `codecov.yml` has "no flags key" (10-06 premise) | **Codex correct.** `flags:` exists at `codecov.yml:17`. The plan's stated premise is factually false. |
| `get_color()` cannot restore MatrixLight state (10-05) | **Codex correct.** `matrix.py:610 get_all_tile_colors()` / `matrix.py:954 set_matrix_colors()` are the real full-state API. |
| 10-01 requires exactly 3 commits, then commits a 4th | **Codex correct.** `10-01-PLAN.md:107` vs `:150`. |
| Probe script is outside coverage collection (10-05) | **Codex correct.** `pyproject.toml:117-118` scopes `--cov` to `lifx` and `generate_theme_data` only. |
| `--serial` absent from the branch probe (10-05/10-06) | **OpenCode correct.** Branch argparse has only `--timeout`, `--stage`, `--verbose`. |

**Verdict: the plan set is not execution-ready.** The architecture, scope discipline and
dependency ordering are strong and all three reviewers agree on that. The defects are in
Phase 10's own implementation and verification mechanisms, and two of them are blocking.

### Agreed Strengths

Named by 2+ reviewers, and independently confirmed where checkable:

- **Wave/`depends_on` ordering genuinely enforces rebase-first.** All three reviewers verified
  that no wave-2+ task consumes branch content before 10-01 produces it. 10-04 and 10-05 are
  correctly file-disjoint and parallel.
- **No scope creep.** All three independently confirmed B3/B5/B6/B7/B8, FIND-06's family-aware
  bind, merged `discover()`, the `tm` field and Thread retuning are absent from every plan.
- **The pure-replay premise is true, not hoped for.** `git diff 42c9ad2 main` over the touched
  paths is empty, so the clean rebase and "branch tests land unmodified and green" (D-19) rest
  on fact. The path-restricted replay proof is a genuinely strong mechanism.
- **The three-site heuristic inventory is exact.** `git grep '":" in '` on the branch returns
  exactly the three named sites and nothing else, so SPEC AC 8's grep works as written.
- **Separated release gates.** CI green, physical UAT, and the irreversible merge are three
  distinct gates with an XOR on the UAT/exception artefacts.
- **The B1 threat scoping is right.** The send-time assertion is a pre-send guard only and the
  plans forbid touching `error_received`/`_FATAL_SOCKET_ERRNOS`, pinned by a parameterised
  errno test — the correct guard against an over-eager fix.

### Agreed Concerns

**BLOCKING — must be fixed before execution:**

1. **10-04 Task 1: the IPv6 fixture cannot work as written.** (Codex HIGH, OpenCode LOW —
   *Codex is right, verified*.) The plan starts the emulator, then sets `IPV6_V6ONLY`; the
   emulator binds inside `start()` (`lifx_emulator/server.py:515`), and setting the option
   after bind raises `EINVAL` on macOS. This is not a portability caveat to wrap defensively
   — it is a setup failure on the development platform. Fix: configure the socket before bind
   and pass it via `create_datagram_endpoint(sock=...)`, or drop the explicit-`V6ONLY`
   criterion, since a `::1` bind already excludes IPv4 capture.
2. **10-05: the hardware UAT can destroy MatrixLight tile state.** (Codex HIGH; Antigravity
   asserted the opposite — that restoration "safely mitigates T-10-13" — which the API check
   refutes.) Capturing `get_color()` + power cannot restore a per-pixel image. Both the control
   `set_color()` and Animator streaming overwrite it. Fix: capture via `get_all_tile_colors()`
   and restore via `set_matrix_colors()` in a `finally`, and close the Animator in `finally`.

**HIGH-PRIORITY — raised by 2+ reviewers:**

3. **Branch-patch-coverage debt is discovered in Wave 5, not measured up front.** (Codex HIGH,
   OpenCode MEDIUM, Antigravity MEDIUM — *the one concern all three raised*.) The rebased mDNS
   rewrite (`discovery.py` ±328 lines, `dns.py` +38) predates the 100% branch-patch gate, and
   10-06 Task 1 admits "gaps are likely there". Discovering the size of that debt after the PR
   and UAT sequencing are in motion is the phase's biggest schedule risk, and it is exactly where
   the "never weaken a check" prohibition faces real pressure. `pyproject.toml:117` already
   enables `--cov-branch`, so it can be measured immediately after the rebase. Fix: measure in
   10-01, distribute top-up tests into the 10-02/10-03 commits, leave 10-06 verifying rather than
   discovering.
4. **10-06 Task 1 rests on a false premise about `codecov.yml`.** The plan says there is no
   `flags` key; there is one at line 17, scoping flags to `scripts/`. This directly interacts
   with finding 5.
5. **10-05's new logic has no automated test or coverage path.** (Codex HIGH.) The plan adds
   substantial CLI, error-handling, mutation and JSON logic but verifies only `--help`, Ruff and
   Pyright. `pyproject.toml:117-118` does not collect coverage for the probe, while `codecov.yml`
   scopes a flag to `scripts/`.

**MEDIUM:**

6. **`--serial` does not exist on the branch probe** but 10-06 Task 2's operator command depends
   on it. 10-05's `--help` acceptance criterion does not check for it. One missing flag turns the
   blocking hardware checkpoint into a decode-failure loop.
7. **10-03: closing the socket is not enough on a failed mDNS open.** The branch assigns
   `_socket`/`_protocol` before awaiting `create_datagram_endpoint()`
   (`mdns/transport.py:95-105`), and `is_open` reads `_protocol is not None` (line 227). Closing
   only the raw socket leaves a phantom-open transport that refuses future `open()` calls. Fix:
   clear `_socket`, `_protocol` and `_transport`; assert `is_open is False` and that a
   subsequent `open()` succeeds.
8. **10-01's commit-count criterion is unsatisfiable.** Line 107 requires exactly three commits
   in `main..HEAD`; line 150 then commits `10-01-SUMMARY.md` on the same branch, making four.
   Fix: assert the first three with `git log --reverse main..HEAD | head -3`.
9. **10-02: `Device.connect()` is an unguarded public IP entry point.** It bypasses
   `Device.__init__` when no serial is supplied
   (`feat/ipv6-thread-support:src/lifx/devices/base.py:739-750`). The plan validates only
   `__init__`, `from_ip()` and `find_by_ip()`. Either validate there too, or record it as a
   deliberate deferred gap in SPEC/CONTEXT.
10. **10-06's automated validators do not enforce what they certify.** The UAT validator checks
    neither the named device, timestamp window, schema kind, nor `library_head`; the exception
    validator does not require a non-empty reason or THREAD-05 reference. Task 4 also stages only
    `10-UAT-RESULTS.json`, though the XOR permits `10-EXCEPTION-OVERRIDE.json` instead.

**LOW:**

11. `validate_address` rule order emits warnings before rejections, so a rejected address can emit
    a spurious warning first. Reorder: raises first, warnings last.
12. `10-06-SUMMARY.md` is required after Task 4 has already merged and pushed, so it cannot "land
    with the merge" without an extra unreviewed commit on `main`.
13. The e2e test reaches into `animator._socket.family`; connection-level tests use the supported
    `get_extra_info("socket").family`.
14. `git log ... | head -3` in 10-06 checks the newest stacked commits, not the three base replay
    commits.

### Divergent Views

- **Risk level (HIGH / MEDIUM / LOW).** Resolved above in favour of Codex on evidence. The
  divergence is explained by depth of source verification, not by differing judgement about the
  same facts.
- **`IPV6_V6ONLY` after bind.** A direct factual contradiction: Codex said it raises on the
  development machine, OpenCode said Linux and macOS permit it. Verified — it raises. Worth
  noting that OpenCode reasoned from portability convention while Codex actually ran it.
- **MatrixLight restoration.** Antigravity listed it as a *strength* that mitigates T-10-13;
  Codex flagged it as a HIGH defect. The API check settles it for Codex.
- **Whether coverage debt is schedule risk or correctness risk.** OpenCode framed it as
  "schedule-shaped, not correctness-shaped"; Codex treats late reactive coverage work as a
  correctness gate that will not hold. Both agree it should move earlier.

### Recommended Next Step

Replan incorporating this feedback — findings 1 and 2 are blocking, and 3–5 change where work
sits in the wave structure rather than merely adding detail:

```
/gsd-plan-phase 10 --reviews
```
