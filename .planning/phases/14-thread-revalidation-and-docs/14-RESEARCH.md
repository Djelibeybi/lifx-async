# Phase 14: Thread Revalidation and Docs - Research

**Researched:** 2026-08-31
**Domain:** Privacy-safe Thread hardware measurement, UDP reliability instrumentation, and discovery documentation
**Confidence:** HIGH

## Operator correction: WiFi animation findings do not transfer to Thread

The animation spike and its empirical results are WiFi-only. They have no evidentiary or predictive authority for Thread pacing, throughput, ACK latency, smoothness, delivery semantics, or acceptance. Phase 14 must not reproduce the WiFi spike as a Thread benchmark and must not add production animation instrumentation or tuning solely for THREAD-03. The current authority is CONTEXT D-09 through D-15: one small, non-gating observation through existing production behaviour, where zero useful throughput is a valid completed result. [VERIFIED: operator clarification, 2026-08-31; CONTEXT D-09–D-15]

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Non-animation sampling protocol

- **D-01:** THREAD-01 uses six paired discovery rounds.
- **D-02:** Alternate the order of `discover()` and `discover_mdns()` within the paired rounds, with a recorded, pre-generated bounded-jitter sequence between rounds.
- **D-03:** THREAD-02 attempts 100 requests for every available Thread device; failed, timed-out, and retransmitted attempts remain part of the evidence.
- **D-04:** THREAD-04 polls both discovery paths every 60 seconds, confirms expiry only after three consecutive absent pairs, and stops after three hours. A target still advertised at the cap is a censored result and does not close the requirement.
- **D-05:** Each acknowledgement trial uses a no-op `SetPower` carrying the device's captured current power level through the normal acknowledgement and retransmission path, with restoration evidence.
- **D-06:** Space the 100 request trials with a recorded, pre-generated bounded-jitter sequence whose intervals are 0.5 to 1.5 seconds.
- **D-07:** Record and summarise both logical completion latency measured from the initial send and acknowledgement RTT measured from the transmission whose sequence receives the first valid acknowledgement.
- **D-08:** For each completed latency distribution independently, report the ordinary median, empirical nearest-rank p95 at `ceil(0.95 * N)`, and observed maximum. Report timeouts separately with undefined latency.

#### Secondary Thread animation observation

- **D-09:** THREAD-03 is secondary and non-gating; the WiFi-only animation spike supplies no Thread assumption.
- **D-10:** Run one ten-second observation at 1, 2, and 5 FPS per explicitly selected available animation-capable alias, without refinement, counterbalancing, or repetitions.
- **D-11:** Add no WiFi-derived concurrent-query workload; use only pre/post liveness and record unrelated activity as a confounder.
- **D-12:** Record existing transport-side offered/sent/gated/failed/interrupted and optional ACK/expiry observations. Zero useful throughput is valid and never fails the phase.
- **D-13:** Add or change no production animation instrumentation, flow-control constant, delivery strategy, or public API solely for THREAD-03.
- **D-14:** Use a fresh `Animator`, capture state, and restore plus read back on every exit path.
- **D-15:** Closure requires an honest bounded attempt and restoration outcome, not a minimum FPS, ceiling, ACK sample count, parity result, or successful frame.
- **D-16:** A restoration failure preserves the failed session, stops mutation, requires operator recovery, and restarts the complete physical protocol under a wholly new identity; old records remain historical rather than closing the replacement session.

#### Harness and evidence ownership

- **D-17:** A new Phase 14 Thread-revalidation orchestrator owns discovery, request, animation, staleness, and validation modes while reusing extracted evidence and restoration helpers from the existing measurement scripts.
- **D-18:** One immutable session manifest freezes the protocol version, repository revision, inventory snapshot, confounders, and schedule seeds. Stages append independently and resume only missing or incomplete work without overwriting history.
- **D-19:** Resolve live identities through the external alias map in memory and append only privacy-safe events at the write boundary. No raw-identifier file is required; optional diagnostic captures remain private and cannot directly feed tracked summaries.
- **D-20:** A completed session contains one manifest plus separate append-only discovery, request, animation, staleness, and closure JSONL journals. Validation deterministically generates the summary, six-class ledger, and human-readable report; generated outputs are never hand-edited.

#### Consumer guidance structure

- **D-21:** Create `docs/user-guide/discovery.md` as the canonical discovery guide and move the existing UDP material from `docs/user-guide/advanced-usage.md` into it. Keep `docs/api/network.md` concise and factual, and leave only a summary and link in advanced usage.
- **D-22:** Organise the guide around the consumer journey: an unchanged `discover()` caller, explicit `discover_udp()` and `discover_mdns()` control, targeted lookup and IPv6, method selection, limitations, then troubleshooting.
- **D-23:** Maintain one executable progressive example as the source for the guide's migration flow. It covers merged `discover()` and both explicit source APIs using synthetic values, with documentation checks to prevent drift.
- **D-24:** Keep shared and GSD-facing guidance canonical in `AGENTS.md`. Reduce `CLAUDE.md` to an `@AGENTS.md` import plus genuinely Claude-specific instructions. Tests must verify the import, prohibit duplicated shared architecture guidance, require an accurate Python 3.10-compatible `asyncio.gather()` description in `AGENTS.md`, and forbid the false `TaskGroup` claim in both files. This direction was retained after checking the installed GSD runtime policy: the configured Codex runtime uses and preserves `AGENTS.md`.

### The agent's Discretion

- Exact orchestrator command and subcommand names, extracted-helper module placement, schema field names, and evidence filenames or subdirectories.
- Exact PRNG and seed encoding for reproducible schedules, plus the bounded discovery inter-round jitter range.
- Exact script-level event field names and presentation for the bounded observation, provided integer counts remain descriptive only and D-09 through D-15 are preserved exactly.
- Selection of the private target alias for the staleness experiment; no live identity may enter planning or tracked evidence.
- Markdown layout and supporting copy within the locked consumer journey.
- Test doubles, fake clocks, schedulers, and fixtures used to prove mechanics without mislabelling synthetic evidence as hardware evidence.

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| THREAD-01 | Discovery coverage over Thread is measured across repeated rounds. Single rounds mislead. | Six paired, order-alternated rounds; immutable schedules; unique alias/source/round aggregation; empty/failure retention. |
| THREAD-02 | WiFi-tuned retry constants are measured against Thread acknowledgement RTT; constants do not change without evidence. | Private request observation at the actual send/accept boundary distinguishes initial-send completion latency from the winning transmission's RTT. |
| THREAD-03 | Current production animation behaviour receives one small, per-alias, non-gating observation. | The script calls an unmodified fresh `Animator`, records its existing return/stat values as offered/sent/gated/failed/interrupted observations, performs pre/post liveness and verified restoration, and accepts zero useful throughput. |
| THREAD-04 | Border-router advertisement staleness is measured directly. | Operator-marked disconnect, paired 60-second polls, first absence plus three-pair confirmation, three-hour censoring, and restored-availability closure. |
| THREAD-05 | Every public lighting class has Thread evidence or a named gap. | Manifest inventory and validator join per-device journals into an exact six-class ledger without converting poor results into gaps. |
| DOCS-04 | Broadcast-first consumers can understand Thread reachability and select default or source-specific discovery. | Canonical consumer-journey guide and one executable, snippet-included progressive example cover `discover()`, `discover_udp()`, `discover_mdns()`, and targeting. |
| DOCS-05 | The four mDNS limitations are explicit. | Current transport and RFC 6762 semantics support exact wording for IPv4 multicast queries, legacy-unicast replies, no unsolicited announcements, and synthetic mesh scale. |
| DOCS-06 | False `asyncio.TaskGroup` architecture guidance is corrected. | Source proves `DeviceGroup` uses `asyncio.gather()` and the project floor is Python 3.10; drift tests make `AGENTS.md` canonical and `CLAUDE.md` narrow. |
</phase_requirements>

## Summary

Phase 14 should be planned as an evidence system first and a hardware run second. The implementation must freeze an immutable manifest and deterministic schedules, emit privacy-safe append-only journals at the measurement boundary, and derive every summary, class disposition, and report from those journals. Physical execution must be an explicit hardware-gated plan or checkpoint: synthetic tests prove mechanics, but neither CI nor later phases should require a Thread fleet. This preserves the phase's non-blocking boundary while still requiring genuine fleet evidence before Phase 14 itself closes. [VERIFIED: `.planning/phases/14-thread-revalidation-and-docs/14-SPEC.md:87-117`]

One instrumentation gap governs production changes: `_transmit_and_listen()` owns every request transmission timestamp and the accepted response header, but its ACK wrapper yields only `True`; a harness outside that boundary cannot recover the winning-sequence RTT correctly. Add a private, opt-in, value-suppressed request observer at that exact seam and test it with fake clocks and queues. THREAD-03 requires no production animation change: the script calls the existing `Animator.send_frame()` and records only the existing result/stat fields that production already returns. [VERIFIED: `src/lifx/network/connection.py:739-784,845-986,1039-1085`; `src/lifx/animation/animator.py:69-91,370-474`; CONTEXT D-09–D-15]

The existing evidence scripts are strong precedents but not reusable unchanged. `measure_merged_discovery.py` validates before append and keeps the external alias map outside the repository; `ipv6_thread_probe.py` captures device-shaped state. Extract common privacy, append/load, and state helpers into a scripts-only module, then strengthen restoration evidence with post-restore readback. The current restore helper returns `True` after commands complete but does not verify that the restored state was applied, so it cannot by itself satisfy D-16's honest restoration gate. [VERIFIED: `scripts/measure_merged_discovery.py:499-532,750-766`; `scripts/ipv6_thread_probe.py:647-663,719-797`]

**Primary recommendation:** Build one resumable, mode-driven orchestrator around the private request observer, current unmodified `Animator.send_frame()`/stats, and fail-closed evidence validation; complete deterministic/synthetic proof before the separately gated, serial hardware runs.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Protocol freeze, schedules, stage resumption | CLI / orchestration | Filesystem / storage | The scripts layer owns operator intent and stage lifecycle; the manifest and journals are durable source-of-truth artefacts. [VERIFIED: CONTEXT D-17–D-20] |
| Request transmission and winning-ACK timing | Network transport | CLI observer | Only the connection engine sees each sequence's send and accepted ACK; the CLI must consume a privacy-safe event, not duplicate transport logic. [VERIFIED: `src/lifx/network/connection.py:739-784,845-986`] |
| Bounded animation observation | CLI orchestration | Existing animation layer | The CLI owns the fixed 1/2/5 FPS schedule, alias safety, liveness, state capture/restoration, and evidence; the animation layer stays unchanged and supplies only current `send_frame()` results/stats. [VERIFIED: `src/lifx/animation/animator.py:370-474`; CONTEXT D-09–D-15] |
| Discovery and staleness observation | High-level API | CLI orchestration | The public default and explicit mDNS APIs are the measured consumer surfaces; fresh paired calls expose border-router advertisements without adding a parallel discovery implementation. [VERIFIED: `src/lifx/api.py:1209-1330`; CONTEXT D-01–D-04] |
| Identity privacy and evidence integrity | CLI write boundary | Validator | Raw identity exists only transiently in memory; only mapped aliases pass schema validation into append-only files. [VERIFIED: `AGENTS.md:17-38`; `scripts/measure_merged_discovery.py:94-143,499-509,750-766`] |
| Consumer documentation | Documentation | Examples/tests | The guide owns the migration narrative; one executable source example and contract tests prevent drift. [VERIFIED: CONTEXT D-21–D-24] |
| Six-class closure | Validator / storage | Human-readable report | Exact ledger validation joins the frozen inventory to evidence or dated gaps; generated prose is secondary. [VERIFIED: `.planning/phases/14-thread-revalidation-and-docs/14-SPEC.md:43-46,107-117`] |

## Project Constraints (from AGENTS.md)

- Use Australian English, keep imports at the top, use the latest version for any dependency, diagnose and fix encountered failures, and do not ignore uncommitted files. [VERIFIED: project instruction supplied for this session]
- Use `uv` exclusively for Python dependency management and execution; the normal full test command is `uv run --frozen pytest`, with `uv run ruff` and `uv run pyright` for quality checks. [VERIFIED: `AGENTS.md:48-138`]
- Preserve the declared Python floor and dependency boundary: the project says **"Python Versions: 3.10, 3.11, 3.12, 3.13, 3.14"** and **"Runtime Dependencies: Zero - completely dependency-free!"** [VERIFIED: `AGENTS.md:12-15`]
- Never track live device serials/MACs, addresses, hostnames, account names, raw discovery output, or the private alias map. Tracked evidence must use stable format-preserving pseudonyms, and staged evidence must be inspected before commit. [VERIFIED: `AGENTS.md:17-38`]
- Use Conventional Commit messages, no phase-number scope, and `git commit -S -s`. [VERIFIED: `AGENTS.md:40-46`]
- Do not manually edit generated protocol/product files or `docs/changelog.md`; Phase 14 does not need any of them. [VERIFIED: `AGENTS.md:154-160,440-444`]
- User-visible fields must not be bytes; conversion belongs near packet send/receive. [VERIFIED: `AGENTS.md:440-444`]
- Keep runtime code on built-in `asyncio`; the current `TaskGroup` statement is itself a Phase 14 defect and must not be treated as authority. [VERIFIED: `AGENTS.md:8-15,303-309`; `.planning/phases/14-thread-revalidation-and-docs/14-SPEC.md:58-61`]

## Standard Stack

### Core

| Library / facility | Version | Purpose | Why Standard |
|--------------------|---------|---------|--------------|
| Python | Project floor `>=3.10`; local research runtime `3.10.11` | Async orchestration, deterministic statistics, monotonic timing, JSONL | Required project runtime; using the floor catches accidental 3.11-only primitives. [VERIFIED: `pyproject.toml:1-7`; local command probe 2026-08-31] |
| `asyncio` stdlib | Python 3.10 | Discovery, control-query scheduling, cancellation and cleanup | Existing architecture and Python-floor-compatible concurrency implementation. [VERIFIED: `AGENTS.md:8-15`; `src/lifx/api.py:442-478`] |
| `time.monotonic_ns`, `statistics.median`, `math.ceil`, `random.Random` | Python 3.10 stdlib | Raw timestamps, locked aggregates, seeded schedules | Avoid wall-clock jumps and external dependencies; use a local PRNG instance so schedules do not perturb global random state. [CITED: https://docs.python.org/3.10/library/time.html; https://docs.python.org/3.10/library/statistics.html; https://docs.python.org/3.10/library/math.html; https://docs.python.org/3.10/library/random.html] |
| Existing `lifx` connection/discovery/animation layers | Repository revision frozen in manifest | Exercise production wire behaviour | The phase measures the shipped stack; parallel senders would invalidate the result. [VERIFIED: `.planning/phases/14-thread-revalidation-and-docs/14-SPEC.md:13-17,28-36`] |

### Supporting

| Library / facility | Version | Purpose | When to Use |
|--------------------|---------|---------|-------------|
| `uv` | `0.11.29` locally | Reproducible execution and tests | Every script/test/quality invocation. [VERIFIED: local command probe 2026-08-31; `AGENTS.md:48-138`] |
| `pytest` | Declared `>=8.4.2` | Fake-clock/socket, schema, privacy, resume, docs-contract tests | All deterministic mechanics; never label emulator or fakes as fleet evidence. [VERIFIED: `pyproject.toml:40-59,107-135`; SPEC constraints lines 89-96] |
| Zensical + PyMdown Snippets | Declared `zensical>=0.0.37`; configured extension | Build docs and include the executable progressive example directly | Make the example the single source using `--8<--`, then run the documentation build. [VERIFIED: `pyproject.toml:40-59`; `mkdocs.yml:160-174`] |
| Ruff / Pyright | Declared `ruff>=0.14.2`, `pyright>=1.1.407` | Formatting, lint, type checks | Include the new hand-written scripts module in Pyright scope. [VERIFIED: `pyproject.toml:40-59,68-102`] |

### Alternatives Considered

| Instead of | Could Use | Trade-off |
|------------|-----------|-----------|
| Existing request engine | A probe-only UDP sender | Reject: it would not exercise the production retransmit/correlation path required by THREAD-02. [VERIFIED: CONTEXT D-05; `src/lifx/network/connection.py:739-784`] |
| Existing `Animator.send_frame()` and current stats | A script-specific frame sender | Reject: THREAD-03 observes current production behaviour and must not create a parallel sender or production instrumentation surface. [VERIFIED: `src/lifx/animation/animator.py:370-474`; CONTEXT D-09–D-15] |
| Stdlib statistics | NumPy/Pandas/metrics package | Reject: the request-latency formulas are locked and small, and the phase forbids a runtime dependency. [VERIFIED: CONTEXT D-08; SPEC line 84] |
| Snippet inclusion | Copying code into guide and example | Reject: two editable copies undermine D-23's single-source and drift requirement. [VERIFIED: CONTEXT D-23; `mkdocs.yml:160-174`] |

**Installation:** No installation and no lockfile change. The project declaration is exactly `dependencies = []`. [VERIFIED: `pyproject.toml:1-7`]

## Package Legitimacy Audit

Not applicable. This phase must add no external package and recommends none. [VERIFIED: `.planning/phases/14-thread-revalidation-and-docs/14-SPEC.md:77-85`; `pyproject.toml:1-7`]

## Architecture Patterns

### System Architecture Diagram

```text
operator + private alias map + quiescence declaration
                         |
                         v
              immutable session manifest
                         |
       +-----------------+-------------------+
       |                 |                   |
       v                 v                   v
 discovery mode     request mode       animation mode
 6 paired calls     100 no-op SETs      one 1/2/5 FPS observation
       |          private TX/ACK sink   existing send_frame()/stats
       +-----------------+-------------------+
                         |
                         +------> staleness mode
                                  operator disconnect
                                  paired polls -> reconnect
                         |
                         v
 privacy gate -> separate append-only JSONL journals
                         |
                         v
              deterministic validation
                         |
          +--------------+---------------+
          v              v               v
       summary      six-class ledger   human report
          |
          v
 canonical discovery guide <- executable progressive example
```

The diagram separates external operator actions and private mapping from tracked outputs; no live identity crosses the privacy gate. [VERIFIED: CONTEXT D-17–D-20; `AGENTS.md:17-38`]

### Recommended Project Structure

```text
scripts/
├── thread_revalidation.py          # mode-driven Phase 14 orchestrator
└── measurement_support.py          # shared alias, JSONL, scheduling, state helpers
tests/
├── test_scripts/test_thread_revalidation.py
├── test_network/test_connection_retry.py
└── test_repository_guidance.py
examples/
└── discovery_progressive.py        # single executable migration-flow source
docs/user-guide/
└── discovery.md                    # canonical consumer guide, includes example
```

These exact new names are recommended, not locked; their placement follows D-17/D-21 and the repository's mirrored test convention. [ASSUMED]

### Pattern 1: Immutable manifest, append-only stages, derived products

**What:** Create the manifest exclusively; if it exists, byte/semantic-compare all immutable fields and refuse drift. Each stage validates a privacy-safe row before appending, assigns stable session/stage/trial identities, and resumes only absent or explicitly incomplete units. Validation loads every journal, rejects unknown/duplicate/inconsistent rows, and atomically regenerates the summary, class ledger, and report. [VERIFIED: CONTEXT D-18–D-20; `scripts/measure_merged_discovery.py:499-545`]

**When to use:** Every Phase 14 mode. A command interruption is an outcome row, not permission to truncate or rewrite history. [VERIFIED: SPEC AC-08, AC-16]

**Planner detail:** Separate “attempt started” from “attempt completed” records, or write one terminal row from a cancellation-safe `finally`; otherwise a process kill cannot distinguish not-run from interrupted. A resume must never silently repeat a completed mutating trial. [ASSUMED]

### Pattern 2: Private observer at the owning seam

**What:** Emit value-only request events immediately beside send and accepted-response timestamps inside `_transmit_and_listen()`. Retain transmission ordinal/sequence mapping in the request scope, then expose logical start, transmission send, accepted ACK, timeout, and send-error categories through an opt-in private sink. The sink must omit target, serial, address, packet bytes and exception text from repr and tracked data. [VERIFIED: `src/lifx/network/connection.py:739-784,821-986`; `tests/test_discovery_observation.py:17-30,33-74`]

**When to use:** The normal no-op `Device.set_power(captured_power)` path. `get_power()` returns an integer and `set_power()` sends `Device.SetPower` through normal acknowledgement handling. The exact accepted values are **"0"** and **"65535"**. [VERIFIED: `src/lifx/devices/base.py:1060-1100,1101-1138`; `src/lifx/protocol/packets.py:286-300`]

**Why:** The current ACK wrapper yields only **"True for successful ACK"**; measuring around `set_power()` gives logical completion only, not winning-transmission RTT. [VERIFIED: `src/lifx/network/connection.py:1039-1085`]

### Pattern 3: Read-only current animation behaviour at script level

**What:** The orchestrator creates a fresh unmodified `Animator`, calls the existing `send_frame()` path on the fixed script schedule, and records only the result/stat values production already returns. Count each scheduled call as offered; classify a successful full socket send as `sent`; preserve existing gated, failed, and interrupted outcomes; and record ACK/expiry values only if the current public or already-exposed result provides them. Never infer rendering or delivery. [VERIFIED: `src/lifx/animation/animator.py:69-91,370-487`; CONTEXT D-09–D-15]

**When to use:** Once per explicitly selected available animation-capable alias at ascending 1, 2, and 5 FPS for ten seconds per rate. The script performs only pre/post liveness, captures state before the attempt, and restores plus reads it back on every exit path. Zero successful sends and zero useful throughput remain valid completed observations. [VERIFIED: CONTEXT D-10–D-15]

**Testing:** Inject an Animator fake into `tests/test_scripts/test_thread_revalidation.py` and prove the fixed schedule, exact alias selection, current stats mapping, interruption, zero-throughput completion, and restoration. Existing animation production tests remain the regression authority and require no Phase 14 edits. [VERIFIED: CONTEXT D-09–D-15]

### Pattern 4: Fail-closed mutation and verified restoration

**What:** Select exactly one alias before opening a mutating stage; resolve it through the private map; capture the full class-shaped state once; record capture; mutate serially; restore in `finally`; then read back and compare the restored fields. Record restore-command outcome and restore-verification outcome separately. A mismatch is restoration failure even if every SET was acknowledged. [VERIFIED: SPEC constraints lines 90-96 and AC-14; `scripts/ipv6_thread_probe.py:647-663,719-797`]

**When to use:** Request, animation, and staleness modes. For staleness, the operator disconnect/reconnect moments need explicit interactive checkpoints and immediate monotonic timestamps; the final gate is a successful paired rediscovery after reconnection. [VERIFIED: CONTEXT D-04, D-16; SPEC AC-06]

### Pattern 5: Frozen non-animation schedules plus one fixed animation observation

**What:** Generate the discovery and request jitter sequences into the immutable manifest before hardware work, then record D-10's fixed ascending 1/2/5 FPS animation schedule exactly as declared. Use monotonic absolute deadlines for cadence. The animation schedule has one attempt per selected alias and produces descriptive integer counts only; it has no comparison, qualification frontier, or performance decision. [VERIFIED: CONTEXT D-02, D-06, D-09–D-15]

### Pattern 6: One documentation source for executable code

**What:** Put the progressive synthetic example in `examples/discovery_progressive.py` and include it from `docs/user-guide/discovery.md` with the already-enabled PyMdown Snippets extension. Test that it compiles/executes against fakes, that docs include the source, and that the guide names the three public APIs and four limitations. [VERIFIED: CONTEXT D-21–D-23; `mkdocs.yml:160-174`; `src/lifx/__init__.py:10-19,90-105,157-158`]

### Anti-Patterns to Avoid

- **Timing outside the request engine:** Total `await set_power()` duration cannot identify which retransmission won. Instrument sequence send and ACK accept at the owner. [VERIFIED: `src/lifx/network/connection.py:778-784,891-986`]
- **Logging then scraping:** Debug logs can contain live endpoints and are not a stable event contract. Use typed, repr-suppressed sinks and map at write time. [VERIFIED: `AGENTS.md:17-38`; `scripts/measure_merged_discovery.py:94-143`]
- **Overwriting a “latest” evidence file:** This hides failures and invalidates resumption. Journals append; generated views may be replaced atomically. [VERIFIED: CONTEXT D-18–D-20]
- **Pooling devices:** Keep each alias and class observation distinct; D-15 requires one honest per-alias bounded attempt and never authorises pooling. [VERIFIED: CONTEXT D-15]
- **Expanding production animation for the observation:** New observers, drains, ACK requirements, flow-control changes, or tuning would turn a small script-level observation into unauthorised product work. Use only the current `Animator.send_frame()` behaviour and stats. [VERIFIED: CONTEXT D-09–D-15]
- **Equating a censored staleness run with an expiry:** Still advertised at three hours remains censored and does not close THREAD-04. [VERIFIED: CONTEXT D-04]
- **Calling synthetic proof “fleet evidence”:** Synthetic DNS/mesh tests prove mechanics only. [VERIFIED: SPEC AC-17]
- **Duplicating discovery prose:** Move detail to the canonical guide; keep the API page factual and advanced usage linked. [VERIFIED: CONTEXT D-21]
- **Adding `TaskGroup`:** It is unavailable on the declared Python 3.10 floor; the current multi-device implementation calls `asyncio.gather()`. [VERIFIED: `pyproject.toml:1-7`; `src/lifx/api.py:442-478`; CITED: https://docs.python.org/3.10/library/asyncio-task.html]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Request retries and correlation | A harness-specific UDP request loop | `DeviceConnection._transmit_and_listen()` plus private observer | It already owns one source, fresh sequences, shared queue, hard deadline and cleanup. [VERIFIED: `src/lifx/network/connection.py:739-784`] |
| Animation sending | A benchmark sender or production observer surface | Existing `Animator.send_frame()` plus current stats, consumed by the script | It observes the shipped path without adding production behaviour or a second wire implementation. [VERIFIED: `src/lifx/animation/animator.py:69-105,370-487`; CONTEXT D-09–D-15] |
| DNS/mDNS discovery | A daemon listener or new parser | `discover()` and `discover_mdns()` | The requirement measures public consumer paths; current mDNS is deliberately legacy-unicast and per-call. [VERIFIED: `src/lifx/api.py:1209-1330`; `src/lifx/network/discovery/mdns/transport.py:1-20`] |
| Statistics framework | Percentile/benchmark dependency | `statistics.median`, sorted nearest-rank, `math.ceil` | The request-latency formulas are locked and dependency-free. Animation counts remain descriptive only. [VERIFIED: CONTEXT D-08, D-12] |
| Evidence identity model | Hashing or embedding raw identifiers | Existing external alias-map pattern | Format-preserving stable aliases support joins without leaking identities. [VERIFIED: `AGENTS.md:17-38`; `scripts/measure_merged_discovery.py:750-766`] |
| Docs code synchronisation | A custom docs generator | Existing PyMdown Snippets + tests | The build already supports inclusion from one executable source. [VERIFIED: `mkdocs.yml:160-174`] |

**Key insight:** The phase's value is faithful observation of production paths. Reimplementing wire behaviour, pacing, discovery, or identity handling would measure the harness instead of lifx-async.

## Common Pitfalls

### Pitfall 1: Logical latency presented as ACK RTT

**What goes wrong:** Retransmitted requests appear slow but the report attributes the entire logical duration to the winning ACK.

**Why it happens:** Every transmission has a fresh sequence and any sequence can complete the request, while the current wrapper erases the response header. [VERIFIED: `src/lifx/network/connection.py:778-784,891-986,1039-1085`]

**How to avoid:** Retain send timestamps per sequence and compute `ack_accept_ns - winning_sequence_send_ns`; separately compute `ack_accept_ns - initial_send_ns`.

**Warning signs:** Identical logical and ACK RTT values on retransmitted trials; retransmit counts without per-transmission events.

### Pitfall 2: Turning the bounded observation into production animation work

**What goes wrong:** The phase adds animation observers, close-time behaviour, ACK requirements, or tuning so the script can make stronger claims than current production stats support.

**Why it happens:** Internal flow-control details look measurable, but D-09 through D-15 deliberately make THREAD-03 a small non-gating current-behaviour observation. [VERIFIED: CONTEXT D-09–D-15]

**How to avoid:** Keep all new animation scheduling, classification, liveness, and restoration logic in the script and its tests. Read current `send_frame()` results/stats as-is, label successful full socket sends only as `sent`, and accept missing optional diagnostics and zero useful throughput.

**Warning signs:** A production animation file appears in the implementation diff, script completion depends on ACK samples or successful frames, or generated evidence claims rendering/delivery.

### Pitfall 3: Reporting command success as restored state

**What goes wrong:** A device is marked restored after successful SET acknowledgements even if only part of its matrix/zones/effect/power state applied.

**Why it happens:** The existing helper catches exceptions and returns `True`, but performs no readback. [VERIFIED: `scripts/ipv6_thread_probe.py:754-797`]

**How to avoid:** Verify all captured fields after restoration, persist mismatch categories without values that reveal identity, and stop the run per D-16.

**Warning signs:** A single `restored: true` Boolean with no readback event or field coverage.

### Pitfall 4: Resume creates duplicate or changed trials

**What goes wrong:** A rerun regenerates jitter/order, repeats a completed mutation, or overwrites a failed row.

**Why it happens:** Schedules and completion identity are inferred at runtime instead of frozen.

**How to avoid:** Manifest owns seeds plus generated schedules; journal uniqueness keys include session, mode, device alias, rate/round/trial/repetition; validation rejects duplicates and manifest mismatch. [VERIFIED: CONTEXT D-18–D-20]

**Warning signs:** Same session ID with a changed revision/schedule; summaries that cannot be reproduced byte-for-byte.

### Pitfall 5: Staleness confuses one miss, cache expiry and border-router expiry

**What goes wrong:** One missed response becomes a claimed SRP lease time.

**Why it happens:** The implementation has invocation-local cache state and does not receive unsolicited announcements; fresh calls observe only replies delivered to their per-call socket. [VERIFIED: `src/lifx/network/discovery/mdns/transport.py:15-20`; `src/lifx/network/discovery/mdns/discovery.py:914-946`]

**How to avoid:** Require a successful paired precondition, record the operator disconnect timestamp, preserve every 60-second pair, distinguish first absence from three-pair confirmed expiry, and verify rediscovery after reconnection. [VERIFIED: CONTEXT D-04; SPEC AC-06]

**Warning signs:** A result with no precondition, no intervening polls, only one absence, or no restored-availability event.

### Pitfall 7: New scripts escape type and coverage gates

**What goes wrong:** The orchestrator imports and runs in tests but is absent from the normal Pyright and coverage target lists.

**Why it happens:** Pyright currently includes only **`["src", "scripts/generate_theme_data.py"]`** and pytest coverage names only **`lifx`** and **`generate_theme_data`**. [VERIFIED: `pyproject.toml:90-124`]

**How to avoid:** Add the new hand-written scripts modules to Pyright's include and pytest coverage configuration, or invoke equivalent explicit checks in their task acceptance commands.

**Warning signs:** `uv run pyright` stays green after an intentional type error in the new script; coverage omits the module.

### Pitfall 8: Hardware gating leaks into CI

**What goes wrong:** CI hangs or fails because Thread devices, a border router, operator disconnect, or the private map is absent.

**Why it happens:** Physical modes are called by ordinary tests or imports have side effects.

**How to avoid:** Put hardware activity behind explicit CLI subcommands and target aliases; unit tests inject fakes; no default test discovers live devices. Hardware execution is a documented checkpoint, not a test marker required by CI. [VERIFIED: SPEC constraints lines 89-96]

**Warning signs:** A test reads the private map, opens multicast sockets without injection, or uses environment-specific addresses.

## Code Examples

Verified patterns and implementation skeletons:

### Exact nearest-rank aggregation

```python
import math
import statistics


def summarise_ns(values: list[int]) -> tuple[float, int, int] | None:
    if not values:
        return None
    ordered = sorted(values)
    p95 = ordered[math.ceil(0.95 * len(ordered)) - 1]
    return statistics.median(ordered), p95, ordered[-1]
```

Source: locked D-08 request-latency formulas; Python stdlib APIs documented at https://docs.python.org/3.10/library/statistics.html and https://docs.python.org/3.10/library/math.html. The empty distribution stays undefined rather than becoming zero. [VERIFIED: CONTEXT D-08]

### No-op request through the production path

```python
captured_power = await device.get_power()
await device.set_power(captured_power)
```

Source: `get_power()` returns the protocol level and `set_power()` accepts the exact integer states **`0`** or **`65535`**, then requests `Device.SetPower` with acknowledgement handling. Observation must wrap the internal request seam, not replace this call. [VERIFIED: `src/lifx/devices/base.py:1060-1100,1101-1138`; `src/lifx/protocol/packets.py:286-300`]

### Progressive example as a single docs source

````markdown
```python
--8<-- "examples/discovery_progressive.py"
```
````

Source: PyMdown Snippets is already enabled. Keep all addresses/serials in the example clearly synthetic. [VERIFIED: `mkdocs.yml:160-174`; `AGENTS.md:32-34`]

### Python 3.10-compatible repository guidance

```python
await asyncio.gather(*(device_operation(device) for device in devices))
```

Source: `DeviceGroup.set_power()` and related batch operations use `asyncio.gather()`, while the project floor is Python 3.10. Document independent per-device connections plus gather-based coordination; do not claim `TaskGroup`. [VERIFIED: `src/lifx/api.py:326-370,442-478`; `pyproject.toml:1-7`; CITED: https://docs.python.org/3.10/library/asyncio-task.html]

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| One discovery observation | Six paired, order-alternated rounds | Locked for Phase 14 | Single-round luck cannot close THREAD-01. [VERIFIED: CONTEXT D-01–D-02; project spike discovery reference] |
| One duration around a request | Logical completion plus winning-transmission ACK RTT | Locked for Phase 14 | Retransmission cost and network RTT remain distinguishable. [VERIFIED: CONTEXT D-07] |
| WiFi animation spike or an exhaustive Thread ceiling sweep | One small, restored, non-gating current-behaviour observation per available Thread class | Operator correction, 2026-08-31 | Prevents a WiFi-only experiment from becoming a Thread benchmark or phase gate. [VERIFIED: operator clarification; CONTEXT D-09–D-16] |
| Discovery detail embedded in advanced usage | Canonical discovery guide with concise links/reference | Locked for Phase 14 | One consumer journey covers default, explicit and targeted paths. [VERIFIED: CONTEXT D-21–D-23] |
| Duplicated `AGENTS.md` / `CLAUDE.md` architecture and false TaskGroup claim | Canonical `AGENTS.md`, narrow `CLAUDE.md` import, accurate `asyncio.gather()` | Locked for Phase 14 | Removes a Python 3.10-incompatible planning trap and prevents drift. [VERIFIED: CONTEXT D-24; `AGENTS.md:303-309`; `CLAUDE.md:1-15,302`] |

**Deprecated/outdated:**

- The advanced guide's statement **"There is no need to run discovery multiple times"** conflicts with this phase's evidence protocol; keep consumer retry guidance distinct from the requirement to repeat measurements. [VERIFIED: `docs/user-guide/advanced-usage.md:359-362`; CONTEXT D-01]
- The advanced guide says the library provides **"two discovery methods"**, but the exported high-level surface is `discover`, `discover_udp`, and `discover_mdns`. [VERIFIED: `docs/user-guide/advanced-usage.md:16-22`; `src/lifx/__init__.py:10-19,157-158`]
- The `TaskGroup` sentence in both agent guides is false; source contains gather-based batch operations and no `TaskGroup`. [VERIFIED: `AGENTS.md:303-309`; `CLAUDE.md:302`; `src/lifx/api.py:442-478`; codebase search 2026-08-31]

The negative source audit was run against the real tree and produced no matches:

```text
$ rg -n "TaskGroup" src
# exit status 1; no output
```

[VERIFIED: positive falsification probe against `src/`, 2026-08-31]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | No Thread delivery or rendering claim is made. A successful full socket send is recorded only as `sent`; ACK/expiry values are optional diagnostics already exposed by current production behaviour. | Operator correction | Low: THREAD-03 has no performance threshold or required ceiling. |
| A2 | The recommended orchestrator/helper/test/example filenames are acceptable. | Recommended Project Structure | Low; names are explicitly discretionary, but plan task paths would change. |
| A3 | Integer offered/sent/gated/failed counts are observations only and never choose a performance pass/fail result. | CONTEXT D-12 | Low: zero useful throughput is explicitly valid. |
| A4 | Attempt-start plus terminal rows are the preferred interruption model. | Architecture Pattern 1 | Another append-only event model may be equally valid; incomplete work must still remain distinguishable and resumable. |

## Resolved Planning Questions

1. **Animation delivery semantics:** No delivered/rendered claim or ceiling is required. Record successful full socket sends as `sent`; optional ACK/expiry data remains diagnostic. Zero useful throughput is valid. [VERIFIED: operator clarification, 2026-08-31; CONTEXT D-09–D-15]
2. **Discovery inter-round jitter:** Freeze 5.0 through 15.0 seconds in the manifest as the planner-selected value within the explicit discretion granted by CONTEXT D-02. This is a protocol choice, not an empirical claim. [VERIFIED: CONTEXT D-02 and discretion]
3. **Initial correctness defect:** Correct the restoration helper's unverified-success behaviour by requiring class-shaped readback. Hardware may expose a different defect later, but animation performance alone cannot trigger a correction or tuning. [VERIFIED: `scripts/ipv6_thread_probe.py:754-797`; SPEC AC-09; operator clarification]

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| Python via `uv` | Harness/tests | ✓ | Python `3.10.11` | Use the floor intentionally. [VERIFIED: local command probe 2026-08-31] |
| `uv` | All Python execution | ✓ | `0.11.29` | None permitted by AGENTS. [VERIFIED: local command probe 2026-08-31; `AGENTS.md:48-138`] |
| Git | Manifest revision and commits | ✓ | `2.50.1` | No evidence session without an exact revision. [VERIFIED: local command probe 2026-08-31; `scripts/measure_merged_discovery.py:769-780`] |
| Thread-capable LIFX fleet + border router | Physical evidence | Operator-reported; not probed during research | Live revision/inventory must be re-derived | Synthetic tests prove mechanics only and cannot close THREAD-01–04. [VERIFIED: SPEC lines 17,89-96] |
| External private alias map | Privacy-safe fleet modes | Required at execution; deliberately not inspected | — | Hardware modes fail closed; no repository fallback. [VERIFIED: `AGENTS.md:17-38`; `scripts/measure_merged_discovery.py:750-766`] |
| Operator quiescence and physical disconnect/reconnect | Performance/staleness | Manual checkpoint | — | Record confounder or censor/incomplete; never silently upgrade evidence. [VERIFIED: SPEC lines 90-96; CONTEXT D-04] |

**Missing dependencies with no fallback:** A reachable Thread fleet, private alias map, and operator action are mandatory for the physical evidence plan, but deliberately absent from CI.

**Missing dependencies with fallback:** None for closing hardware requirements. Fake clocks, sockets and synthetic records are valid only for harness verification.

## Security Domain

Security enforcement is enabled because `.planning/config.json` does not set `security_enforcement` to `false`. The section uses the ASVS 4.0 category labels requested by the research contract. [VERIFIED: `.planning/config.json:1-73`; CITED: https://github.com/OWASP/ASVS/tree/master/4.0/en]

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | The local CLI has no user/account authentication boundary; do not invent one. Target identity is handled as operator selection under access control/privacy. [CITED: https://github.com/OWASP/ASVS/blob/master/4.0/en/0x11-V2-Authentication.md] |
| V3 Session Management | No | Evidence session IDs are experiment provenance, not authenticated user sessions. [CITED: https://github.com/OWASP/ASVS/blob/master/4.0/en/0x12-V3-Session-management.md] |
| V4 Access Control | Yes, adapted | Explicit one-alias target selection, external allow-map, serial mutation, fail-closed restoration, and no fleet-wide mutation. [VERIFIED: SPEC AC-14; CITED: https://github.com/OWASP/ASVS/blob/master/4.0/en/0x12-V4-Access-Control.md] |
| V5 Input Validation | Yes | Validate CLI ranges, seeds, revision, manifest/journal schemas, alias syntax, counts, state transitions, and every untrusted UDP/DNS event before state or disk mutation. [VERIFIED: `scripts/measure_merged_discovery.py:72-143,499-532`; CITED: https://github.com/OWASP/ASVS/blob/master/4.0/en/0x13-V5-Validation-Sanitization-Encoding.md] |
| V6 Stored Cryptography | No new cryptography | Do not add custom encryption or identity hashing. Keep the private map outside the repository and use the required signed commit process. [VERIFIED: `AGENTS.md:17-46`; CITED: https://github.com/OWASP/ASVS/blob/master/4.0/en/0x14-V6-Cryptography.md] |

### Known Threat Patterns for the Measurement Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Raw identifier or endpoint reaches a journal/report/exception | Information disclosure | Forbidden-key/value scan before append, repr-suppressed observations, external mapping, staged-diff scan. [VERIFIED: `AGENTS.md:17-38`; `scripts/measure_merged_discovery.py:90-143,499-509`] |
| Injected Animator fake reports malformed script results | Spoofing / tampering | Validate offered/sent/gated/failed/interrupted counts and state transitions before appending; current production animation internals remain unchanged. [VERIFIED: CONTEXT D-12–D-15] |
| Crafted or duplicate journal rows alter closure | Tampering | Exact schema, uniqueness keys, immutable manifest, line-numbered load errors, deterministic regeneration. [VERIFIED: CONTEXT D-18–D-20; `scripts/measure_merged_discovery.py:499-545`] |
| Wrong device or entire fleet is mutated | Elevation of privilege / tampering | Require explicit private alias, one selected target, captured state and restoration gate; no “all” mutating mode. [VERIFIED: SPEC AC-14] |
| Endless or excessive staleness polling | Denial of service | Fixed 60-second cadence, three-hour hard cap, one selected target, cancellation-safe cleanup. [VERIFIED: CONTEXT D-04] |
| Untrusted DNS/UDP values become filesystem paths or prose | Tampering / information disclosure | Never derive output paths or report text from raw packet values; map to validated controlled aliases and enumerated failure categories first. [VERIFIED: `scripts/measure_merged_discovery.py:94-143,750-766`] |

## Validation Strategy

The formal `## Validation Architecture` section is intentionally omitted because `workflow.nyquist_validation` is explicitly `false`. Phase planning still needs focused acceptance commands because this work changes transport instrumentation, scripts and docs. [VERIFIED: `.planning/config.json:18-36`]

Recommended validation layers:

1. Connection tests prove initial/retransmit event ordering, winning-sequence RTT, timeouts, send failures, sink absence/no-op behaviour, cancellation cleanup, and no raw identity in events or repr. Extend `tests/test_network/test_connection_retry.py`. [VERIFIED: existing test path via repository scan 2026-08-31]
2. Existing animation tests remain the regression gate for current production behaviour. THREAD-03 adds only script-level tests for the bounded schedule, existing stats capture, explicit alias selection, non-gating zero-throughput completion, and restoration; it does not require new Flow/Animator event surfaces. [VERIFIED: operator clarification; CONTEXT D-09–D-15]
3. Script tests prove manifest immutability, the frozen discovery/request schedules and fixed animation observation, all boundary cases, exact request aggregates, append-only resume, cancellation, alias-map exclusion, forbidden values/keys, restoration readback, D-16 stop behaviour, staleness censoring, and exact six-class closure. Build on `tests/test_scripts/test_measure_merged_discovery.py` and `tests/test_scripts/test_ipv6_thread_probe.py`. [VERIFIED: CONTEXT canonical references; repository scan 2026-08-31]
4. Documentation tests compile/run the progressive example against fakes, ensure the guide includes it, check all three APIs/four limitations/synthetic qualification, verify nav, enforce `CLAUDE.md` import-only ownership, forbid TaskGroup claims and require accurate gather text in `AGENTS.md`. [VERIFIED: CONTEXT D-21–D-24]
5. Run focused tests per task, then `uv run --frozen pytest`, `uv run ruff format --check .`, `uv run ruff check .`, `uv run pyright`, `uv run zensical build`, and `uv run llmstxt-standalone build`. [VERIFIED: `AGENTS.md:48-138`]
6. Before committing any physical evidence, run both schema/privacy validation and a staged-diff privacy inspection; do not rely on a later redaction commit. [VERIFIED: `AGENTS.md:17-38`]

## Sources

### Primary (HIGH confidence)

- `.planning/phases/14-thread-revalidation-and-docs/14-CONTEXT.md` — locked protocol, harness and documentation decisions.
- `.planning/phases/14-thread-revalidation-and-docs/14-SPEC.md` — scope, acceptance and prohibitions.
- `AGENTS.md`, `pyproject.toml`, `mkdocs.yml` — project authority, supported stack and docs build.
- `src/lifx/network/connection.py` — production retransmit/correlation owner and missing request observation surface.
- `src/lifx/animation/animator.py` — factual read-only authority for current `send_frame()` results/stats and lifecycle behaviour used by the script-level observation.
- `src/lifx/api.py`, `src/lifx/network/discovery/mdns/transport.py`, `src/lifx/network/discovery/mdns/discovery.py` — public discovery and mDNS behaviour.
- `scripts/measure_merged_discovery.py`, `scripts/ipv6_thread_probe.py` — reusable evidence/privacy/state precedents and restoration-verification gap.
- Project skill `spike-findings-lifx-async` — discovery and retry findings remain relevant where their own evidence applies. The animation reference is WiFi-only history and is explicitly excluded as Thread evidence or authority. [VERIFIED: operator clarification, 2026-08-31]

### Secondary (MEDIUM confidence)

- https://docs.python.org/3.10/library/asyncio-task.html — Python 3.10 `asyncio.gather()` semantics.
- https://docs.python.org/3.10/library/time.html — monotonic timing.
- https://docs.python.org/3.10/library/statistics.html — median.
- https://docs.python.org/3.10/library/math.html — ceiling.
- https://docs.python.org/3.10/library/random.html — deterministic seeded PRNG behaviour.
- https://lan.developer.lifx.com/docs/packet-contents and https://lan.developer.lifx.com/docs/changing-a-device — ACK correlation and Device SetPower wire contract.
- https://www.rfc-editor.org/rfc/rfc6762.html — legacy-unicast query/reply and cache/goodbye semantics.
- https://github.com/OWASP/ASVS/tree/master/4.0/en — ASVS category definitions used for the security applicability check.

### Tertiary (LOW confidence)

- None. All assumptions are isolated in the Assumptions Log and must be frozen or confirmed before hardware execution.

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH — current project declaration, installed tools and official Python 3.10 documentation were checked.
- Architecture: HIGH — the owning request, discovery, evidence and restoration seams were read directly; animation remains unchanged production behaviour observed only at script level.
- Pitfalls: HIGH — most follow from observed data loss/privacy/resume boundaries; no Thread animation performance assumption remains.

**Research date:** 2026-08-31
**Valid until:** 2026-09-07 for live fleet availability and tool versions; architectural findings remain valid until the cited source seams change.
