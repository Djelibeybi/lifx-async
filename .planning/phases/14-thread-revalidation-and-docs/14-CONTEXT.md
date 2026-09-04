# Phase 14: Thread Revalidation and Docs - Context

**Gathered:** 2026-08-31
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 14 freezes and runs privacy-safe, versioned hardware protocols for repeated paired discovery, request acknowledgement timing and retransmissions, and one advertisement-expiry experiment on the currently available Thread lighting classes. Thread animation is recorded as an explicit, non-gating scope boundary rather than a per-class measurement (see SEED-003): the library does not intend to support sustained Thread animation, so class closure depends only on discovery and request evidence, never an animation attempt. The one animation observation already collected (`LIFX-Candle-C-1`, all three of 1/2/5 FPS) is preserved and cited only as proof Thread carries the frames without failing. It closes all six public lighting classes with per-device evidence or a dated named gap, publishes accurate broadcast-first and source-specific discovery guidance, and corrects repository architecture guidance. It does not extrapolate the WiFi-only animation spike to Thread, set an animation performance gate, claim universal Thread performance, retune constants from interference-confounded observations, modify downstream consumers, add public APIs or runtime dependencies, or commit private identifiers or raw captures.

</domain>

<spec_lock>
## Requirements (locked via SPEC.md)

**8 requirements are locked.** See `14-SPEC.md` for full requirements, boundaries, and acceptance criteria.

Downstream agents MUST read `14-SPEC.md` before planning or implementing. Requirements are not duplicated here.

**In scope (from SPEC.md):**

- A Phase 14 hardware-measurement protocol and privacy-safe evidence schema.
- Repeated paired discovery observations for `discover()` and `discover_mdns()`.
- Per-device Thread request RTT and retransmission observations.
- Recording Thread animation as an out-of-scope, non-gating boundary, citing the one existing Candle observation.
- One directly observed border-router advertisement-expiry experiment.
- A complete six-class Thread evidence or named-gap ledger.
- Evidence-backed correction of a concrete correctness or reliability defect found by the phase.
- Broadcast-first Thread consumer guidance and the four known mDNS limitations.
- Correction and drift protection for the false `asyncio.TaskGroup` statement in both `CLAUDE.md` and `AGENTS.md`.

**Out of scope (from SPEC.md):**

- An authoritative or universal Thread performance benchmark, regression threshold, or WiFi-parity gate, because the current mesh has unresolved interference and Thread is expected to have materially lower bandwidth.
- Retuning performance constants from interference-confounded measurements; a later clean, replicated run must isolate the library behaviour first.
- Home Assistant or other downstream consumer implementation changes; this phase ships library evidence and guidance only.
- Real-hardware fleet-scale mesh proof, multiple border-router topology proof, or overflow behaviour; FLEET-01 and FLEET-02 remain deferred and synthetic proof remains clearly labelled.
- Thread hardware evidence for `InfraredLight` and `HevLight`; no capable fleet hardware exists, so both receive named gaps.
- A new public discovery API, a public async-API redesign, or a runtime dependency.
- Committing private alias mappings, serials, addresses, hostnames, or raw discovery captures.

</spec_lock>

<decisions>
## Implementation Decisions

### Non-animation sampling protocol

- **D-01:** THREAD-01 uses six paired discovery rounds.
- **D-02:** Alternate the order of `discover()` and `discover_mdns()` within the paired rounds, with a recorded, pre-generated bounded-jitter sequence between rounds.
- **D-03:** THREAD-02 attempts 100 requests for every available Thread device; failed, timed-out, and retransmitted attempts remain part of the evidence.
- **D-04:** THREAD-04 polls both discovery paths every 60 seconds, confirms expiry only after three consecutive absent pairs, and stops after three hours. A target still advertised at the cap is a censored result and does not close the requirement.
- **D-05:** Each acknowledgement trial uses a no-op `SetPower` carrying the device's captured current power level through the normal acknowledgement and retransmission path, with restoration evidence.
- **D-06:** Space the 100 request trials with a recorded, pre-generated bounded-jitter sequence whose intervals are 0.5 to 1.5 seconds.
- **D-07:** Record and summarise both logical completion latency measured from the initial send and acknowledgement RTT measured from the transmission whose sequence receives the first valid acknowledgement.
- **D-08:** For each completed latency distribution independently, report the ordinary median, empirical nearest-rank p95 at `ceil(0.95 * N)`, and observed maximum. Report timeouts separately with undefined latency.

### Secondary Thread animation observation

**Amendment (2026-09-04):** Thread does not have the bandwidth to sustain animation at usable or smooth frame rates, and pushing that volume of data onto a Thread mesh is bad practice regardless of what a measurement would show. Measuring Thread animation performance is therefore not a gap to be filled later; it is a measurement of something the library will not support. `Animator` is intended to be locked to WiFi devices in a future milestone (`.planning/seeds/SEED-003-lock-animation-to-wifi.md`). D-09 through D-14 below describe the mechanics of the one animation observation already collected under the original protocol (alias `LIFX-Candle-C-1`, all three of 1/2/5 FPS completed) and remain accurate as a record of how that observation was run; D-15 is superseded by this amendment, since closure no longer depends on an animation attempt at all.

- **D-09:** THREAD-03 is a deliberately secondary, non-gating current-behaviour observation. The WiFi-only animation spike has no authority for Thread pacing, throughput, ACK latency, smoothness, delivery semantics, or acceptance.
- **D-10:** Freeze one small ascending observation at 1, 2, and 5 FPS for ten seconds per rate, once per explicitly selected available animation-capable alias. Do not refine, counterbalance, repeat, or compare with WiFi. Under the amendment above, no further alias needs this observation for Phase 14 to close.
- **D-11:** Do not add a WiFi-derived concurrent-query workload. Use only a pre/post liveness check and record unrelated activity as a confounder.
- **D-12:** Record offered frames, successful full socket sends, gated frames, send failures, interruption, and any ACK/expiry values already exposed by current production behaviour. These are transport-side observations, never proof of rendering. Zero useful throughput or no qualified rate is a valid completed result and cannot fail Phase 14.
- **D-13:** Do not add or change production animation instrumentation, flow-control constants, delivery strategy, or public API solely for THREAD-03. The observation cannot justify performance tuning.
- **D-14:** Use a fresh `Animator`, capture state before the selected-alias observation, and restore plus read back state on success, ordinary failure, cancellation, and early exit.
- **D-15 (superseded by the amendment above):** Phase closure never depends on an animation attempt or its restoration outcome for any class. `derive_class_ledger_from_roster()` takes no animation input; it does not require a minimum FPS, ceiling, ACK sample count, parity result, successful frame, or bounded attempt of any kind.
- **D-16:** If state restoration fails, retain the failed attempt as immutable evidence, stop before the next device, and require operator-confirmed recovery. Once the operator confirms recovery, the same session resumes: the affected alias is re-attempted as a new appended row, and evidence collected before the failure remains valid, because a restoration failure confounds only measurements taken after it. If the device cannot be recovered, its alias stays incomplete and blocks its own class, not the session.

### Harness and evidence ownership

- **D-17:** A new Phase 14 Thread-revalidation orchestrator owns discovery, request, animation, staleness, and validation modes while reusing extracted evidence and restoration helpers from the existing measurement scripts.
- **D-18:** One immutable session manifest freezes the protocol version, repository revision, inventory snapshot, confounders, and schedule seeds. Stages append independently and resume only missing or incomplete work without overwriting history.
- **D-19:** Resolve live identities through the external alias map in memory and append only privacy-safe events at the write boundary. No raw-identifier file is required; optional diagnostic captures remain private and cannot directly feed tracked summaries.
- **D-20:** A completed session contains one manifest plus separate append-only discovery, request, animation, staleness, and closure JSONL journals. Validation deterministically generates the summary, six-class ledger, and human-readable report; generated outputs are never hand-edited.

### Consumer guidance structure

- **D-21:** Create `docs/user-guide/discovery.md` as the canonical discovery guide and move the existing UDP material from `docs/user-guide/advanced-usage.md` into it. Keep `docs/api/network.md` concise and factual, and leave only a summary and link in advanced usage.
- **D-22:** Organise the guide around the consumer journey: an unchanged `discover()` caller, explicit `discover_udp()` and `discover_mdns()` control, targeted lookup and IPv6, method selection, limitations, then troubleshooting.
- **D-23:** Maintain one executable progressive example as the source for the guide's migration flow. It covers merged `discover()` and both explicit source APIs using synthetic values, with documentation checks to prevent drift.
- **D-24:** Keep shared and GSD-facing guidance canonical in `AGENTS.md`. Reduce `CLAUDE.md` to an `@AGENTS.md` import plus genuinely Claude-specific instructions. Tests must verify the import, prohibit duplicated shared architecture guidance, require an accurate Python 3.10-compatible `asyncio.gather()` description in `AGENTS.md`, and forbid the false `TaskGroup` claim in both files. This direction was retained after checking the installed GSD runtime policy: the configured Codex runtime uses and preserves `AGENTS.md`.

### The agent's Discretion

- Exact orchestrator command and subcommand names, extracted-helper module placement, schema field names, and evidence filenames or subdirectories.
- Exact PRNG and seed encoding for reproducible schedules, plus the bounded discovery inter-round jitter range.
- Exact event field names and presentation for the bounded animation observation, provided D-09 through D-15 remain non-gating and contain no WiFi-derived assumptions.
- Selection of the private target alias for the staleness experiment; no live identity may enter planning or tracked evidence.
- Markdown layout and supporting copy within the locked consumer journey.
- Test doubles, fake clocks, schedulers, and fixtures used to prove mechanics without mislabelling synthetic evidence as hardware evidence.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Locked phase and project authority

- `.planning/phases/14-thread-revalidation-and-docs/14-SPEC.md` — Locked Phase 14 requirements, boundaries, constraints, acceptance criteria, and prohibitions.
- `.planning/PROJECT.md` — Project goal, public API commitments, runtime-dependency boundary, and privacy posture.
- `.planning/REQUIREMENTS.md` — Milestone requirement ownership and deferred fleet-scale requirements.
- `.planning/ROADMAP.md` — Phase ordering, Phase 14 goal, and downstream milestone relationships.
- `.planning/STATE.md` — Current milestone state and planning continuity.
- `.planning/phases/13-merged-discovery/13-CONTEXT.md` — Preceding merged-discovery decisions, evidence boundaries, and terminology carried into revalidation.

### Repository-specific implementation findings

- `.agents/skills/spike-findings-lifx-async/SKILL.md` — Index and routing rules for validated repository findings.
- `.agents/skills/spike-findings-lifx-async/references/discovery.md` — Discovery architecture, shared sweeps, validation, and observation patterns.
- `.agents/skills/spike-findings-lifx-async/references/retry-schedule.md` — Connection retry schedule and acknowledgement correlation details.
- `.agents/skills/spike-findings-lifx-async/references/animation-flow-control.md` — Animation flow-control window, acknowledgement gating, expiry, and statistics.
- `.agents/skills/spike-findings-lifx-async/references/concurrency-and-keepalive.md` — Python 3.10-compatible concurrency and connection-lifecycle behaviour.

### Existing evidence and instrumentation code

- `scripts/measure_merged_discovery.py` — Append-only, alias-safe discovery evidence, confounder capture, validation, and summary precedents.
- `scripts/ipv6_thread_probe.py` — Per-target Thread probing, state capture and restoration, privacy checks, and non-gating short animation probe.
- `tests/test_scripts/test_measure_merged_discovery.py` — Existing measurement-script safety, validation, and deterministic-summary coverage.
- `tests/test_scripts/test_ipv6_thread_probe.py` — Existing probe privacy, selection, restoration, and reporting coverage.
- `tests/test_discovery_observation.py` — Discovery observation hooks and deterministic discovery test support.
- `src/lifx/network/connection.py` — Normal request retransmission path, sequence correlation, and transmission observations.
- `src/lifx/animation/flow.py` — Acknowledgement-gated animation send window and expiry behaviour.
- `src/lifx/animation/animator.py` — Animation lifecycle, frame delivery, and current statistics integration.
- `tests/test_animation/test_flow.py` — Flow-control boundary tests.
- `tests/test_animation/test_animator.py` — Animator lifecycle and frame-statistics tests.

### Discovery APIs and documentation

- `src/lifx/api.py` — Public merged, UDP-only, mDNS-only, and targeted discovery behaviour.
- `src/lifx/network/discovery/udp.py` — UDP discovery implementation and discovered-device construction.
- `src/lifx/network/discovery/mdns/discovery.py` — mDNS record assembly, follow-up queries, and supported-device construction.
- `docs/user-guide/advanced-usage.md` — Current UDP and advanced discovery material to migrate or summarise.
- `docs/api/network.md` — Current network API reference to keep concise and accurate.
- `examples/discovery_broadcast.py` — Existing broadcast discovery example.
- `examples/discovery_mdns.py` — Existing explicit mDNS example.
- `examples/discovery_find_device.py` — Existing targeted discovery example.
- `mkdocs.yml` — Documentation navigation and build integration.

### Agent guidance ownership

- `AGENTS.md` — Canonical shared repository and GSD-facing guidance after this phase.
- `CLAUDE.md` — Claude-specific entry point that will import canonical shared guidance.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- `scripts/measure_merged_discovery.py` already demonstrates append-only JSONL events, external alias-map enforcement, quiescence and confounder capture, deterministic validation, and generated summaries.
- `scripts/ipv6_thread_probe.py` already provides explicit per-target selection, state capture and restoration, privacy-safe reporting, and a short non-gating stream. Its 10 FPS result must not be reused as a sustained animation ceiling.
- `src/lifx/network/connection.py` already owns the escalating retransmit schedule, fresh sequence allocation, valid-response correlation, and request observations needed to distinguish logical latency from winning-transmission RTT.
- `src/lifx/animation/flow.py` and `src/lifx/animation/animator.py` already expose the two-in-flight, one-second-expiry flow-control path and `FrameSendStats`; Phase 14 should extend instrumentation around that behaviour rather than build a parallel sender.

### Established Patterns

- Live identifiers are resolved through an operator-controlled mapping outside the repository; tracked evidence contains stable aliases only. Empty, failed, interrupted, censored, and restoration-failed results remain explicit records.
- Async generators and device contexts require deterministic cleanup on early exit. Hardware mutation is serial, explicitly targeted, and paired with captured state and honest restoration outcomes.
- The library remains standard-library-only at runtime and supports Python 3.10, so concurrency guidance and implementation must use compatible primitives.
- Tests mirror source structure. Emulator and synthetic fixtures may prove harness mechanics, but only privacy-safe physical-device sessions close hardware requirements.
- Journals are the source of truth; summaries, the class ledger, and the human report are regenerated deterministically and are not manually repaired.

### Integration Points

- Add the Phase 14 orchestrator under `scripts/`, with focused tests under `tests/test_scripts/`; extract shared helpers only where both existing scripts and the new orchestrator genuinely use them.
- Extend connection and animation observations at their existing boundaries, retaining current public API behaviour and adding focused network and animation tests.
- Add the canonical discovery guide and progressive example, wire them into `mkdocs.yml`, and add documentation checks for API names, limitations, synthetic values, and guide/example drift.
- Replace duplicated agent guidance with canonical `AGENTS.md` content and a narrow `CLAUDE.md` import, protected by targeted repository tests.

</code_context>

<specifics>
## Specific Ideas

- Six discovery rounds deliberately match the established Phase 13 physical-evidence precedent while pairing the merged default with explicit mDNS.
- The request probe must be an exact no-op `SetPower` using captured state, not an echo-only proxy, so it exercises the production acknowledgement and retransmission path without an intended visible change.
- The three-hour staleness cap is an experiment boundary, not an assumed device lease. A device that remains advertised at the cap is reported as censored rather than forced into a pass or failure.
- The documentation move is substantive: the existing UDP discovery material belongs in the new canonical discovery guide rather than being duplicated there.
- `AGENTS.md` remains canonical because the live installed GSD Codex policy maps project instructions to it and preserves it during updates; the earlier conditional request to reverse ownership therefore did not apply.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 14-thread-revalidation-and-docs*
*Context gathered: 2026-08-31*
