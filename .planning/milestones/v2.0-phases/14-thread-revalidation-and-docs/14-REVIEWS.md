---
phase: 14
reviewers: [claude, opencode, antigravity]
reviewed_at: 2026-08-31T14:35:49.847Z
plans_reviewed: [14-01-PLAN.md, 14-02-PLAN.md]
models:
  claude: "claude-opus-5 (reasoning=high)"
  opencode: "openrouter/z-ai/glm-5.3 (reasoning=high)"
  antigravity: "gemini-3.1-pro-high"
model_sources:
  claude: "pinned"
  opencode: "pinned"
  antigravity: "pinned"
---

# Cross-AI Plan Review — Phase 14

## Claude Review

I verified the plans' central claims against source. Here is the review.

# Cross-AI Plan Review — Phase 14: Thread Revalidation and Docs

## 1. Summary

These are unusually rigorous plans, and the research underneath them is real: I independently confirmed the three load-bearing source claims (the request-timing seam, the ACK wrapper that discards the header, and the restore helper that reports success without readback). The evidence architecture — immutable manifest, five append-only journals, deterministic regeneration, one-alias fail-closed mutation, D-16 whole-session restart — is well-matched to the phase's actual risk, which is fabricated or leaked evidence rather than implementation difficulty. The wave split (14-01 hermetic system → 14-02 hardware + publication) is the right dependency order. However, three defects would surface during execution rather than review: **Plan 14-02's `CLAUDE.md` reduction directly breaks an existing, currently-passing test that requires that exact prose**; **the THREAD-04 "absent pair" predicate is undefined across two discovery APIs that measure materially different things**, which can produce a headline SRP-lease number wrong by two orders of magnitude; and **the "already-exposed ACK/expiry values" the animation plan repeatedly promises to record do not exist on any current production surface**. Plan 14-01's estimate is also optimistic by a wide margin.

## 2. Strengths

- **Research claims verified, not asserted.** `_transmit_and_listen` (`src/lifx/network/connection.py:809-1000`) genuinely owns every per-transmission `send_packet` and the accepted header, while `_request_ack_stream_impl` discards it and yields bare `True` (`connection.py:1082-1085`). The observer-at-the-owning-seam design (14-01 Task 1) is the correct answer, not an over-engineered one — sequence is `tx_count` (`connection.py:893`) but the *send timestamps* are not recoverable outside the generator.
- **The named correctness defect is real.** `_restore_device_state` (`scripts/ipv6_thread_probe.py:753-797`) returns `True` after the SETs complete with no readback whatsoever. Requiring class-shaped readback is a genuine, testable correctness fix, exactly as AC-09 demands, and it is not performance tuning.
- **The privacy precedent is genuinely reusable.** `_load_alias_map` (`measure_merged_discovery.py:750-766`) already refuses a map inside the repository; `_FORBIDDEN_KEYS` / `_validate_alias` / `_append_measurement_row` (`:94-143, 499-509`) already validate before opening output. 14-01's extraction is consolidation, not invention.
- **D-16 is specified as a whole-session abort, not a retry.** Requiring a wholly new session directory with no evidence credit is stricter than the usual "mark and continue" and closes the obvious integrity hole.
- **CI isolation is treated as a mechanical property**, not a convention (14-01 Task 3), which matches ROADMAP's "must not block CI" constraint at `.planning/ROADMAP.md:110-112`.
- **The documentation gap is real and correctly sized.** `discover_udp` is exported (`src/lifx/__init__.py:157`) but appears **nowhere** in `docs/` — Phase 13 shipped a public API undocumented. `docs/user-guide/advanced-usage.md:18` still says "two discovery methods".

## 3. Concerns

### HIGH — `CLAUDE.md` reduction (D-24) breaks an existing passing test, and the plan adds a contradictory one

`tests/test_network/test_mdns/test_phase_contract.py:22` lists `Path("CLAUDE.md")` in `_REQUIRED_QUERY_MODEL_PATHS`, and `:195-209` asserts that every such path's prose contains `initial dns-sd ptr service query` plus the one-second and three-second PTR retransmit descriptions. That prose is currently at `CLAUDE.md:151`. Plan 14-02 Task 3 reduces `CLAUDE.md` to "`@AGENTS.md` plus genuinely Claude-specific instructions", which deletes it — and `_normalised_prose` (`:32-41`) only strips heading lines, so an indented continuation still counts.

Worse, the same task adds a test that "prohibits duplicated shared architecture guidance" in `CLAUDE.md`. The two tests would then assert opposite things about the same file. Task 3's `<automated>` block runs the full `uv run --frozen pytest`, so this fails at execution. The plan's `read_first` anticipates only the `advanced-usage.md` path move, not this.

**Failure scenario:** executor performs D-24, runs Task 3 verification, `test_query_model_documents_initial_ptr_and_both_retransmissions` fails on `CLAUDE.md`; the fix requires a Phase 11 contract decision (does `@AGENTS.md` import satisfy an *inherited* prose contract?) that no plan authorises.

### HIGH — THREAD-04's "absent pair" is undefined, and the two legs measure different phenomena

D-04 polls "both discovery paths" and confirms expiry after "three consecutive absent pairs", but no plan defines *absent pair*. This matters because the two APIs are not interchangeable:

- `discover()` routes mDNS candidates through `_discover_verified_devices_mdns` (`src/lifx/api.py:1128`), i.e. FIND-04 unicast verification. A disconnected Thread device fails verification on the very next poll.
- `discover_mdns()` (`src/lifx/api.py:1268-1330`) yields record-derived devices with no verification, so it keeps reporting the device for as long as the border router advertises it.

Only the second leg answers THREAD-04's actual question ("when does it stop being *advertised*"). If "absent pair" means absent in *either* leg, the run confirms "expiry" roughly three minutes after disconnect and publishes that as LIFX's SRP lease — against an OpenThread default of two hours. That result would pass every integrity check the plans specify.

**Failure scenario:** operator disconnects the target; poll 1 `discover()` absent / `discover_mdns()` present; polls 2–3 same; an OR-predicate confirms expiry at ~180 s; `14-REPORT.md` publishes a ~3-minute advertisement lease, and THREAD-04 closes on a number measuring unicast liveness, not SRP.

### HIGH — the "already-exposed ACK/expiry values" for THREAD-03 do not exist

Both plans repeatedly promise to record "any ACK/expiry values already exposed by current production behaviour" (14-01 must-haves and Task 1 behaviour; 14-02's `14-ANIMATION.jsonl` artifact description). Against source:

- `AnimatorStats` exposes exactly `packets_sent`, `total_time_ms`, `gated`, `acks_outstanding` (`src/lifx/animation/animator.py:68-91`).
- `AckGate` declares `__slots__ = ("_outstanding", "_buf")` (`flow.py:78`) and exposes only `gated` and `outstanding_count` (`:87-95`).
- Expiry is pruned silently inside `sweep()` (`flow.py:153-161`) with no counter.

So there is **no** ack-received count and **no** expiry count. A falling `acks_outstanding` is ambiguous between "device acknowledged" and "probe expired unacknowledged after 1 s". Recording it as an ACK diagnostic is precisely the delivery inference D-12 forbids, and D-13 forbids adding the instrumentation that would disambiguate it. The plans leave an executor to resolve this at implementation time, in a phase whose entire point is not overclaiming.

**Failure scenario:** executor maps `acks_outstanding` into an `ack_*` evidence field; on a lossy Thread mesh where every probe expires, the journal shows outstanding counts returning to zero and the generated report reads as acknowledgement activity — an unfalsifiable delivery claim in evidence explicitly barred from making one.

### MEDIUM — the no-op `SetPower` can raise `ValueError` before a packet is sent

D-05 mandates `set_power(captured_power)` and D-03 mandates exactly 100 trials per device. But `set_power` rejects any integer outside `(0, 65535)` (`src/lifx/devices/base.py:1130-1131`; `src/lifx/devices/light.py:551-553`), while `get_power()` returns the device's raw `state.level` uint16 (`base.py:1085`; `light.py:475`). A device mid-fade returns an intermediate level, and the trial then fails client-side with no datagram on the wire. Neither plan handles this outcome category. The same hazard sits in the restore path (`ipv6_thread_probe.py:786, 792`), where a `ValueError` inside `_restore_device_state`'s `except Exception` becomes `restored: False` and, under D-16, aborts the whole session.

**Failure scenario:** a scheduled fade is in progress on the selected alias; `get_power()` returns 32768; `set_power(32768)` raises `ValueError`; the harness either records a network-shaped failure (corrupting the RTT distribution's timeout column) or aborts a three-hour protocol for a client-side validation error.

### MEDIUM — adding the new scripts to coverage puts them under a 100% patch-coverage gate

Task 3 requires extending pytest coverage to the two new modules "without lowering thresholds". Today `pyproject.toml:117-118` measures only `lifx` and `generate_theme_data`, and `codecov.yml` sets `patch.default.target: 100%` with flag paths including `scripts/`. The two existing measurement scripts escape this because they are unmeasured. Adding `thread_revalidation.py` (a seven-mode orchestrator) to `--cov` puts **every** new line — including operator-checkpoint prompts and hardware-only branches — into a 100% patch denominator, enforced across five Python versions. That is achievable with fakes but is a substantial hidden cost the 3-task/60k estimate does not carry, and the likely pressure valve is `pragma: no cover` sprinkling, which weakens the gate the plan is trying to strengthen.

### MEDIUM — Task 3's docs work is gated behind a 3-hour blocking hardware checkpoint for no reason

In Plan 14-02, Task 1 is `checkpoint:human-action gate="blocking-human"` and includes a three-hour staleness cap plus 100 serial requests per device across four classes. Task 3 (DOCS-04/05/06 — the canonical guide, the example, `mkdocs.yml`, the `TaskGroup` correction) has **zero** data dependency on any of it, yet sits behind it in the same sequential plan. ROADMAP explicitly says Phase 14 "must not block CI or any other phase" (`.planning/ROADMAP.md:110-112`); this ordering makes shipping a documentation correction contingent on operator availability and fleet health. Splitting the docs task into its own wave-2 plan would let 14-01, docs, and the hardware run proceed independently.

### MEDIUM — the observation-sink home is unspecified, and the existing precedent is an anti-pattern

`scripts/measure_merged_discovery.py:45-69` loads its observation sink from `tests/test_discovery_observation.py` by anchored path via `importlib` — because the sink lives under `tests/` while the seam lives in `src/lifx/network/discovery/udp.py:51-63` as a *task attribute*. Plan 14-01's `key_links` says connection.py emits "to scripts/thread_revalidation.py" but never says where the request-observation sink type lives, nor whether to use the task-attribute mechanism or the explicit `_observer=` parameter (Phase 13 recorded a decision preferring explicit passing — `.planning/STATE.md:123`). Left unspecified, the most likely outcome is the executor copying the `importlib`-from-tests hack into a second script.

### MEDIUM — the snippet drift protection is weaker than D-23 assumes

`mkdocs.yml:173` enables `pymdownx.snippets` with **no** `base_path` and **no** `check_paths`, and no file under `docs/` currently uses `--8<--` at all — so this path has never been exercised in this repo. With `check_paths` defaulting to `False`, a mistyped or moved example path renders an empty code block and the build still passes. Plan 14-02's drift protection is the pattern `--8<--.*examples/discovery_progressive.py`, which greps the Markdown *source* and would pass even when the include resolves to nothing at build time.

### LOW–MEDIUM — DOCS-06 leaves a Python 3.10-incompatible `TaskGroup` recommendation in shipped user docs

The plans scope DOCS-06 to `AGENTS.md:306` and `CLAUDE.md:302`, but `docs/user-guide/troubleshooting.md:369` tells consumers to run the keepalive poll "with `asyncio.create_task()` or `asyncio.TaskGroup`" — unqualified, in a library that ships a 3.10 floor. It is a different claim (user code, not library internals) but the same defect class the requirement names, and it is the copy consumers actually read.

### LOW — Plan 14-01's estimate is not credible

`estimate: 60000 tokens, 3 tasks, confidence: med` covers: a new production observer in `connection.py`; a shared support module; migrating **both** existing scripts (`ipv6_thread_probe.py` 1408 lines, `measure_merged_discovery.py` 1253 lines) without changing behaviour; a seven-mode orchestrator; and executable tests for 25 edge truths plus four prohibitions. For calibration, `tests/test_scripts/test_ipv6_thread_probe.py` alone is 2221 lines. This is plausibly a 6–10 task plan.

## 4. Suggestions

- **Resolve the `CLAUDE.md` contract conflict explicitly in the plan**, before execution. Either amend `_REQUIRED_QUERY_MODEL_PATHS` in `test_phase_contract.py` to drop `CLAUDE.md` (recording it as a deliberate Phase 11 contract amendment with rationale: `@AGENTS.md` makes the prose reachable), or scope the new "no duplicated shared guidance" test to exclude the mDNS query-model block. Add `tests/test_network/test_mdns/test_phase_contract.py:13-27` to Task 3's `read_first`.
- **Define "absent pair" as absent in *both* legs**, and state in the manifest and report that `discover()` absence measures verified liveness while `discover_mdns()` absence measures border-router advertisement. Record both first-absence timestamps separately; the THREAD-04 headline number must be the `discover_mdns()` one. This should be an edge truth in 14-01, not left to the executor.
- **Replace "ACK/expiry values already exposed" with the exact field list that exists**: `packets_sent`, `total_time_ms`, `gated`, `acks_outstanding`. Add a prohibition that `acks_outstanding` must never be labelled, aggregated, or narrated as acknowledgement receipt, since ack-received and ack-expired are indistinguishable from outside `AckGate` (`flow.py:153-161`).
- **Add an explicit `power_out_of_range` trial outcome** (and restoration outcome) for a captured level that is neither `0` nor `65535`, with a fake-device test. Consider having the harness re-read power once and record the confounder rather than aborting a three-hour session on a transient fade.
- **Split Plan 14-02 into 14-02 (hardware) and 14-03 (documentation)**, both depending on 14-01 but independent of each other. Docs then ship on CI alone.
- **Decide the sink's home in the plan**: put both the discovery and request observation sinks in `scripts/measurement_support.py`, and either retire the `tests/`-import hack at `measure_merged_discovery.py:45-69` as part of the Task 2 migration or state explicitly that it is out of scope.
- **Set `pymdownx.snippets: {check_paths: true, base_path: ["."]}`** in `mkdocs.yml` as part of Task 3, so a broken include fails the build rather than rendering silently.
- **Extend DOCS-06's scope to `docs/user-guide/troubleshooting.md:369`**, or record it explicitly as deferred with a reason.
- **Verify the alias format is compatible before the hardware run.** `_validate_alias` (`measure_merged_discovery.py:135-141`) rejects any 12-hex-char alias as "identifier-shaped", so serial-shaped pseudonyms like those in `.planning/PROJECT.md:314-319` cannot be used. Confirm the operator's private map yields aliases the existing validator accepts, or the first `init` fails.
- **Re-check the estimate** and consider decomposing 14-01 Task 2 into manifest/schedules, mutation+restoration, and validation/ledger.

## 5. Risk Assessment

**Overall risk: MEDIUM-HIGH.**

The design is sound and the research is honest — I found no case where the plans misdescribed the code. Risk concentrates in three places. First, one confirmed execution blocker (`CLAUDE.md` versus `test_phase_contract.py`) that will halt Task 3 and requires a decision the plans do not authorise. Second, two under-specified semantics — the staleness predicate and the animation ACK fields — that will *not* halt execution and will instead produce plausible-looking evidence that is wrong in exactly the way the phase's prohibitions exist to prevent; these are the expensive ones, because they consume a three-hour irreversible hardware run before anyone notices. Third, delivery risk from a materially undersized 14-01 and a 100% patch-coverage gate the plans do not budget for.

None of this is architectural. All of it is resolvable by amending the plans before execution: pin the `CLAUDE.md` contract decision, define "absent pair" as both-legs-absent, replace the ACK/expiry phrasing with the four fields that exist, add the out-of-range power outcome, and split the docs work out from behind the hardware checkpoint.

---

## OpenCode Review

# Cross-AI Plan Review: Phase 14 (Plans 14-01, 14-02)

All source claims below were verified against the actual tree.

---

## Plan 14-01 — Tracer + Hermetic Contract

### Summary
Well-grounded tracer plan. Core architectural claim verified: `DeviceConnection._transmit_and_listen()` (`src/lifx/network/connection.py:739`) owns per-sequence sends (fresh sequence per retransmit, line 896), the shared queue, correlation validation (lines 962–975) and cleanup (990–996), while the ACK wrapper discards the header and yields bare `True` (lines 1039–1085, `yield True` at 1084). No per-send timestamps are retained today — only `start`, `next_tx_at`, `last_response_time` (839, 842, 985) — so the private observer at that seam is genuinely required and genuinely absent. Scope is large for one plan but the wave-1/wave-2 split and hardware isolation are correct.

### Strengths
- **Observer seam is the right one and the plan's justification is verified.** Timing `set_power()` from outside cannot recover winning-sequence RTT: any transmission's sequence completes the request (lines 896–913, 962–975), and the wrapper erases the header (`connection.py:1084`). `tests/test_discovery_observation.py:17-40` supplies a proven repr-suppressed value-only sink precedent.
- **Animation claim verified against source.** `AnimatorStats` fields are `packets_sent`, `total_time_ms`, `gated`, `acks_outstanding` (`src/lifx/animation/animator.py:70-91`); gated frames return `packets_sent=0` (440–445); sends raise `LifxNetworkError` on socket failure (459–462). The offered/sent/gated/failed/interrupted mapping is fully derivable from current production behaviour with no instrumentation change — D-13 is achievable as written.
- **Restoration gap is real.** `_restore_device_state()` (`scripts/ipv6_thread_probe.py:754-797`) returns `True` on command completion with zero readback; the readback requirement is a legitimate correctness fix, not gold-plating.
- **Pitfall 7 verified.** `pyproject.toml:95` Pyright includes only `["src", "scripts/generate_theme_data.py"]`; coverage targets only `lifx` and `generate_theme_data` (`pyproject.toml:117-118`). New scripts would escape both gates without the planned pyproject change.
- **Protocol constants verified.** `REQUEST_RETRANSMIT_GAPS` starts at 0.2 s (`src/lifx/const.py:53-55`); the "200 ms floor" framing in THREAD-02 is accurate. `set_power` accepts exactly 0/65535 (`src/lifx/devices/base.py:1101-1138`).
- Task 3's CI-isolation and quality-gate closure (Pyright include extension, no threshold weakening) directly matches the pyproject reality.

### Concerns
- **MEDIUM — Accepted-ACK timestamp semantics undefined.** The only response timestamp in the engine is taken at yield time (`connection.py:985`), i.e. after the `asyncio.wait_for` queue-get resumes (934–936). Datagrams are queued by the background receiver without timestamps, so an observer emitting "ack_accept_ns" at the yield boundary measures event-loop wake-up latency plus RTT. For Thread RTTs plausibly in the tens of ms under interference, this is a real measurement-validity question the plan never resolves. Decide now: sample at dequeue (documented loop-latency inclusion) or extend the receiver to stamp at put time (second seam, more production change).
- **MEDIUM — ns vs float monotonic clock mismatch.** The engine uses `time.monotonic()` floats throughout (`connection.py:839,867,985`); must_haves demand "raw monotonic integer timestamps" and D-08 aggregation assumes ns. An implementing agent may "helpfully" convert the engine to `monotonic_ns`, changing timing behaviour in the hot path the phase is supposed to observe unmodified. State explicitly that the observer takes its own `time.monotonic_ns()` readings and the engine clock is untouched.
- **MEDIUM — Task 2 is oversized for one autonomous task.** Full D-01–D-20 engine (six modes, five journals, resume, D-16 restart, readback) plus migration of both existing scripts plus their three test suites, estimated within a 60k-token plan. High risk of thin coverage at the edges. Split: (a) manifest/journals/privacy gate, (b) physical modes + D-16, (c) helper migration.
- **LOW — Migration blast radius.** Refactoring `measure_merged_discovery.py` and `ipv6_thread_probe.py` changes Phase 13's historical evidence tooling mid-milestone. The plan keeps their tests green, which is the right guard, but note `_restore_device_state` prints raw `device.serial`/`device.ip` to stdout (`ipv6_thread_probe.py:793`) — the migrated shared helper must keep that output terminal-only and out of any evidence-capture path the orchestrator owns.
- **LOW — Readback comparison policy unspecified.** "Compare the restored fields" without defining exact-match vs tolerance risks spurious D-16 session aborts (e.g. device-side rounding on restored matrix colours). Freeze comparison semantics (exact protocol values) before hardware.

### Suggestions
- Add an explicit acceptance criterion: observer timestamp capture points and their inclusion/exclusion of event-loop latency, documented in the manifest protocol version.
- Add a regression test asserting `connection.py`'s existing float-clock arithmetic and retransmit scheduling are byte-unchanged (beyond the observer insertion), since this is the hot path THREAD-02 measures.
- Consider deferring the two-script migration to a separate task or plan so evidence-system delivery isn't coupled to historical-tooling refactor.

### Risk Assessment
**MEDIUM.** Architecture and source claims are accurate throughout — every cited seam checked out. Residual risk concentrates in timestamp semantics (measurement validity of the entire THREAD-02 dataset) and Task 2 scope, not in correctness of the design.

---

## Plan 14-02 — Physical Session + Docs

### Summary
Correct dependency shape (14-02 blocks on 14-01; hardware behind a blocking-human checkpoint; CI untouched). Documentation targets verified: the false `TaskGroup` claim exists at both `AGENTS.md:306` and `CLAUDE.md:302`, `grep TaskGroup src` returns nothing (only `asyncio.gather` — e.g. `src/lifx/api.py:458,476`), `advanced-usage.md:18` says "two discovery methods", `:359` says "no need to run discovery multiple times", and `docs/api/network.md` claims "Retry logic with exponential backoff and jitter" which contradicts the actual fixed escalating gaps (`src/lifx/const.py:53`). `find_by_ip()` IPv6 literal/zone support exists (`src/lifx/api.py:1518-1572`). All four DOCS requirements target real, verified defects.

### Strengths
- **Every documentation defect claim is verified against source** — rare and valuable; DOCS-04/05/06 will close real inaccuracies, not strawmen.
- Snippet single-sourcing is supported: `pymdownx.snippets` is enabled (`mkdocs.yml:173`), and `tests/test_network/test_mdns/test_phase_contract.py` already exists as the semantic-contract pattern to extend.
- D-16 replacement-session isolation, staleness censoring (three-pair confirmation, three-hour cap), and the "poor result ≠ gap" rule are all mechanically testable as specified, and Plan 14-01 builds those contracts first.
- Evidence-directory layout, env-var-driven private inputs, and staged-diff privacy inspection match `AGENTS.md:17-38` exactly.

### Concerns
- **MEDIUM — Censored-staleness closure deadlock.** Task 1's done criterion requires "a confirmed non-censored staleness experiment", and D-04 says still-advertised-at-3h does not close THREAD-04. If LIFX's actual SRP lease exceeds three hours, there is no defined path to closure — no pre-agreed extended-cap rerun, no operator decision gate, no documented escalation. The phase can wedge on one experiment.
- **MEDIUM — Task 3 (docs) is serialised behind a ~3-hour operator-gated hardware session it doesn't depend on.** Docs, examples, and drift tests are fully independent of fleet evidence but sit after the blocking checkpoint. Reordering (docs before or parallel with the physical session) removes idle wall-clock time and de-risks the phase against hardware unavailability — the SPEC explicitly says hardware must not block other work.
- **LOW — Task 1 command list enumerates `--alias` per invocation but the available-alias set is frozen at `init` from discovery inventory.** If a device drops mid-session, the resume rule ("resume only manifest-declared missing or incomplete units") is sound, but the plan should state that an inventory change is a confounder/incomplete record, not a silent skip — it does in must_haves, keep it in the task action too.
- **LOW — `send_frame()` is synchronous** (`animator.py:370-388`, deliberately, "no event loop required"). The 10-second-per-rate observation script drives a sync API from async orchestration; frame cadence uses `asyncio.sleep` between sync sends. Trivial but worth one line so the implementer doesn't wrap it in `run_in_executor` or misattribute loop-blocking.
- **LOW — Committed evidence under `.planning/.../14-EVIDENCE/`** means the privacy gate is the only barrier between live-derived data and repo history (AGENTS.md:26-28: redaction-after-commit is insufficient). Plan covers pre-staged validation and diff inspection — adequate, but the automated validator must run as part of the staging step, not merely as a manual habit.

### Suggestions
- Pre-authorise the censored-staleness escalation path now: e.g. "censored → operator chooses one extended-cap rerun session or records THREAD-04 as open with dated rationale" so the executor isn't inventing process mid-checkpoint.
- Move Task 3 (docs) ahead of the Task 1 checkpoint, or split Plan 14-02 into a docs plan (autonomous, wave-2-parallel) and an evidence plan (blocking-human). This also matches the SPEC's non-blocking mandate.
- State in Task 1's action that each staleness poll's `discover()` call inherits the default 15 s timeout, so the 60 s cadence math and the 3-hour cap are computed from poll-start, not poll-completion.

### Risk Assessment
**MEDIUM.** Content is accurate and well-verified; risks are schedule and process (staleness closure deadlock, docs serialised behind hardware), not technical correctness.

---

## Overall

**Risk: MEDIUM.** Both plans are unusually source-faithful — every file:line claim I checked (connection seam, ACK wrapper, AnimatorStats, restore-without-readback, pyright/coverage gaps, TaskGroup falsehood, stale docs wording, 200 ms gap floor, set_power 0/65535, find_by_ip IPv6) was correct. The design correctly avoids the three biggest traps: measuring outside the owning seam, expanding production animation instrumentation, and letting hardware gate CI. Fix before execution: (1) define the accepted-ACK timestamp capture point, (2) pin the observer clock policy so the engine's float timing is untouched, (3) pre-agree the censored-staleness escalation path, (4) split 14-01 Task 2 and decouple 14-02 docs from the hardware checkpoint.

---

## Antigravity Review

> [reviewed-without-source-citations] This reviewer declared source-grounded evidence but cited no file:line source evidence, so it reviewed the pasted plan text only — down-weight its verdict in the Consensus Summary.

# Phase 14: Thread Revalidation and Docs - Plan Review

## 1. Plan Quality
The proposed plans (14-01 and 14-02) demonstrate an exceptionally high level of structural rigor and strict adherence to the project's architectural, privacy, and dependency constraints.

**Strengths:**
- **Strict Boundary Enforcement:** The plan correctly identifies the need to isolate live fleet validation and physical mutation from CI via strict CLI subcommands, fulfilling the requirement that physical evidence hardware-gates the phase without breaking CI environments.
- **Accurate Codebase Alignment:** The plan correctly roots itself in current production realities. It accurately references `DeviceConnection._transmit_and_listen()` as the owner of request correlation and `Animator.send_frame()` as the source of truth for animation stats.
- **Privacy and Safety First:** By leaning on external alias maps and explicitly capturing/restoring state using `CapturedState` in a `finally` block, the plan comprehensively mitigates the risk of PII leakage (serials, MACs, IP addresses) and destructive fleet mutation.
- **Accurate Python 3.10 Constraints:** The plan correctly identifies the `asyncio.TaskGroup` hallucination currently present in `AGENTS.md` and replaces it with `asyncio.gather()`, ensuring backwards compatibility with the locked `requires-python = ">=3.10"` baseline.

## 2. Completeness
The plan completely covers all explicitly locked decisions (D-01 through D-24) and all eight requirements (`THREAD-01` to `THREAD-05`, `DOCS-04` to `DOCS-06`).

- **Task 1 (Tracer Engine):** Successfully outlines an opt-in, value-suppressed request observation seam within `src/lifx/network/connection.py`. By capturing events cleanly at the source sequence, it prevents logical latency from being misattributed to winning-transmission ACK RTT.
- **Task 2 (Protocol & Support Helpers):** Appropriately scopes the extraction of reusable elements (`_append_measurement_row`, `_load_alias_map`, `_capture_device_state`) into `scripts/measurement_support.py` and coordinates them through a dedicated `scripts/thread_revalidation.py` orchestrator. It covers all bounded execution schedules (e.g., 5-15s jitter, 1/2/5 FPS intervals).
- **Task 3 (Docs & CI Isolation):** Completely addresses the documentation updates, migrating fragmented UDP usage into a cohesive `docs/user-guide/discovery.md` and integrating a single-source PyMdown snippet (`examples/discovery_progressive.py`) configured via `mkdocs.yml`. Explicit extensions to `pyproject.toml` correctly place the new script files under `ruff`, `pyright`, and `pytest` coverage.

## 3. Risks & Mitigations

**Risk 1: Overhead/Interference in the Critical Path**
- *Description:* Introducing a private observer directly inside `_transmit_and_listen()` could unintentionally block the event loop or modify request timing semantics.
- *Mitigation:* The plan mandates that the observer is strictly opt-in and value-suppressed, executing only when explicit measurement runs are requested. Task 1 correctly requires hermetic test suites to verify that public request results remain completely unchanged.

**Risk 2: Refactoring Existing Scripts**
- *Description:* Refactoring `scripts/measure_merged_discovery.py` and `scripts/ipv6_thread_probe.py` to use a shared `scripts/measurement_support.py` helper module risks breaking previous fleet measurement capabilities.
- *Mitigation:* The plan correctly specifies that shared-helper migrations must leave the existing measurement and probe test suites strictly green.

**Risk 3: Fail-Closed Restoration Breakage**
- *Description:* Network instability during the restore sequence could leave a physical device stranded in an altered state (e.g. frozen animation or changed power state).
- *Mitigation:* The plan adopts a robust fail-closed `D-16` strategy: if post-command readback fails, it stops the session, refuses to merge evidence, and mandates a complete protocol restart with a new identity after operator recovery.

**Risk 4: Documentation Drift**
- *Description:* Executable code snippets in Markdown often decay as APIs change.
- *Mitigation:* Adequately handled by utilizing `examples/discovery_progressive.py` as a single executable source embedded dynamically via PyMdown Snippets, enforced by unit tests running against fakes.

## Conclusion
The plans are robust, accurate to the physical layout of `/Volumes/External/Developer/Djelibeybi/lifx-async`, and ready for execution. Claims made regarding the location and purpose of existing structures (`animator.py`, `connection.py`, PyMdown configuration, `AGENTS.md` inaccuracies, and zero-dependency constraints) are completely factual and verified.

---

## Consensus Summary

The two source-cited reviewers assess the plans as architecturally sound and unusually well grounded, with overall risk in the MEDIUM to MEDIUM-HIGH range. Both verified the request-observation seam, the missing restoration readback, the documentation inaccuracies, and the need for CI-safe hardware isolation. They also agree that the plan set should be revised before execution: measurement semantics must be frozen more precisely, Plan 14-01 is too broad for one implementation unit, and the independent documentation work should not wait behind the long operator-gated hardware protocol. Antigravity's uncited review is included for completeness but is not counted at full consensus weight.

### Agreed Strengths

- The private observer belongs at `DeviceConnection._transmit_and_listen()`, where per-transmission sequence and response correlation are owned; timing from the public `set_power()` wrapper cannot recover the winning-transmission RTT.
- The restoration defect is real: the existing helper reports command completion without verifying restored state through readback, so the Phase 14 correction is a legitimate reliability fix.
- The append-only, alias-safe evidence design, deterministic regeneration, D-16 fail-closed restart rule, and hardware/CI separation match the phase's privacy and evidence-integrity risks.
- The documentation phase addresses concrete current defects, including missing public discovery guidance and inaccurate concurrency/retry descriptions.

### Agreed Concerns

- Measurement semantics need to be pinned before physical execution. OpenCode requires an explicit ACK timestamp capture point and clock policy; Claude additionally requires exact staleness-leg semantics and a prohibition on narrating ambiguous `acks_outstanding` changes as acknowledgements.
- Plan 14-01 is materially oversized. Both cited reviewers recommend splitting the observer/evidence foundation, physical modes and restoration, and historical-script migration into smaller independently verifiable units.
- The documentation task has no dependency on the three-hour hardware checkpoint. Both cited reviewers recommend moving it earlier or splitting it into a parallel plan.
- The staleness protocol lacks a complete closure policy. Claude identifies ambiguity between verified merged discovery and record-derived mDNS absence; OpenCode identifies no pre-authorised path when the result remains censored at the three-hour cap.

### Divergent Views

- Claude found a direct conflict between reducing `CLAUDE.md` to an `@AGENTS.md` import and the existing `tests/test_network/test_mdns/test_phase_contract.py` requirement that the mDNS query-model prose remain in `CLAUDE.md`. OpenCode verified the documentation defects but did not flag this test conflict. This should be checked and resolved explicitly in the revised plan.
- Claude concludes that current animation surfaces expose no ACK-received or expiry counts and warns that `acks_outstanding` is ambiguous. OpenCode concludes the offered/sent/gated/failed/interrupted mapping is derivable from existing `AnimatorStats`. These views are compatible only if the plan names the exact existing fields and expressly forbids interpreting outstanding-count reductions as delivery evidence.
- Claude rates the plan MEDIUM-HIGH because several under-specified mechanisms could produce plausible but invalid hardware evidence. OpenCode rates it MEDIUM because it sees the remaining issues chiefly as measurement semantics and scheduling. Antigravity calls the plans ready, but provided no source citations and is therefore down-weighted.
