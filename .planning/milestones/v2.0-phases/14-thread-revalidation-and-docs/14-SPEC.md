# Phase 14: Thread Revalidation and Docs - Specification

**Created:** 2026-08-31
**Ambiguity score:** 0.08 (gate: <= 0.20)
**Requirements:** 8 locked

## Goal

Revalidate discovery, request timing, and advertisement expiry on the currently available Thread lighting classes; record Thread animation as an explicit, non-gating scope boundary rather than a measurement to complete; preserve privacy-safe and explicitly qualified evidence for every public device class; and publish accurate consumer and architecture guidance without treating the operator's currently interference-affected mesh as an authoritative performance benchmark.

## Background

Phases 10 to 13 delivered IPv6 transport, hardened mDNS, IPv6 targeted discovery, and the merged public discovery surface. `discover()` now combines shared UDP discovery with directly verified mDNS candidates, while `discover_udp()` and `discover_mdns()` retain explicit source control. `find_by_serial()` races both validated sources. These behaviours make Thread devices reachable, but the reliability constants and measurement precedents still come from WiFi/IPv4.

The existing `scripts/ipv6_thread_probe.py` can inspect mDNS records and ports, run targeted control checks, and optionally send a short 10 FPS stream. Its streaming result is deliberately non-gating. The animation spike validated WiFi behaviour only: it has no evidentiary or predictive authority for Thread and must not supply a Thread pacing schedule, throughput target, ACK expectation, delivery denominator, or acceptance threshold. Thread does not have the bandwidth to sustain animation at usable or smooth frame rates, and sending that volume of data over a Thread mesh is bad practice regardless of what a measurement would show, so Thread animation performance is a recorded scope boundary rather than a gap Phase 14 fills: `Animator` is intended to be locked to WiFi devices in a future milestone (SEED-003). One physical observation exists and is preserved: alias `LIFX-Candle-C-1` completed all three declared rate observations (1, 2 and 5 FPS) without failing, which shows Thread carries the frames without falling over -- it is explicitly not evidence that Thread animation is usable. Phase 14 builds the request, discovery, staleness, privacy, restoration, and class-ledger evidence that does not yet exist, and class closure never depends on an animation attempt.

The available Thread hardware now spans `Light`, `MultiZoneLight`, `MatrixLight`, and `CeilingLight`. `InfraredLight` and `HevLight` have no Thread-capable fleet hardware and therefore close through explicit named gaps. The Thread network currently appears to have unresolved interference. Measurements from it remain useful observations of this fleet, but they are not authoritative performance gates or universal Thread benchmarks.

The documentation also lags the shipped behaviour: consumer guidance does not yet explain the merged default and the explicit source APIs together, and both `CLAUDE.md` and `AGENTS.md` incorrectly claim that multi-device work uses `asyncio.TaskGroup`, which is absent from `src/` and unavailable on the supported Python 3.10 floor.

## Requirements

1. **THREAD-01 - Repeated paired discovery evidence**: Measure Thread discovery coverage through repeated, paired observations of `discover()` and `discover_mdns()` for every available Thread device, with results separated by stable operator-controlled alias and source.
   - Current: The merged and source-specific APIs exist, and Phase 13 has paired discovery infrastructure, but there is no Phase 14 per-device Thread coverage record across the available four classes.
   - Target: A predeclared protocol runs more than one paired round, records every success, miss, failure, and confounder, and reports per-device and per-class observed coverage without allowing duplicate packets to inflate it. Exact sample count and cadence are implementation decisions for discuss-phase, but a single round is invalid.
   - Acceptance: The committed privacy-safe evidence proves that each planned paired round was attempted through both APIs, retains empty or failed rounds, and reports unique discovery outcomes for every available Thread device without raw infrastructure identifiers.

2. **THREAD-02 - Request timing and retransmission evidence**: Measure acknowledgement round-trip time and retransmission behaviour for every available Thread device against the current 200 ms first retransmit floor.
   - Current: `REQUEST_RETRANSMIT_GAPS` starts at 200 ms based on WiFi measurements. No per-device Thread RTT distribution or retransmit-rate evidence exists.
   - Target: A versioned, predeclared protocol records raw monotonic timing samples, timeouts, retransmit counts, and median/p95/maximum summaries for every available device under serial, quiesced runs. Exact trial counts belong to discuss-phase. Interference is recorded as a confounder, not removed after results are known.
   - Acceptance: Every available Thread device has a privacy-safe request record containing the protocol version, environmental qualification, attempted and completed sample counts, timeouts, retransmits, raw timing observations, and deterministic aggregates. The current performance constants remain unchanged unless separately replicated, unconfounded evidence demonstrates a concrete correctness or reliability defect.

3. **THREAD-03 - Thread animation is a recorded scope boundary, not a measurement**: Thread does not have the bandwidth to sustain animation at usable or smooth frame rates, and pushing that volume of data onto a Thread mesh is bad practice regardless of what a measurement would show. Measuring Thread animation performance is therefore not a gap to be filled later; it is a measurement of something the library will not support. `Animator` is intended to be locked to WiFi devices in a future milestone (see `.planning/seeds/SEED-003-lock-animation-to-wifi.md`).
   - Current: Existing Thread probing demonstrates only that a short stream can be attempted. WiFi spike results are intentionally excluded: they do not establish Thread pacing, throughput, ACK behaviour, smoothness, or delivery semantics. One physical observation exists from before this scope decision: alias `LIFX-Candle-C-1` completed all three declared rate observations (1, 2, and 5 FPS) without failing.
   - Target: The Candle observation is preserved and cited for exactly what it shows -- Thread carries the frames without falling over -- and explicitly not as evidence that Thread animation is usable. No further alias receives an animation attempt as part of this phase. The `animation` CLI subcommand, `run_animation_observation()`, and the animation journal contract remain available and tested for future WiFi work, but an animation attempt is neither required nor sufficient for any class to close.
   - Acceptance: THREAD-05 class closure depends only on physical discovery evidence and complete physical request trials for every expected alias; `derive_class_ledger_from_roster()` takes no animation input. The one Candle observation is documented in the evidence and report as a "does not fall over" data point, never as a usability, parity, or performance result, and it cannot block or gate any class's closure.

4. **THREAD-04 - Observed advertisement staleness measurement**: Directly measure how long a consumer keeps seeing a selected Thread device advertised after it is deliberately disconnected. The quantity is end-to-end observable staleness, not a device property: it is the composite of LIFX firmware's requested SRP lease, the border router's granted lease, and the border router's mDNS TTL on the infrastructure link, and the method cannot decompose them. Nothing in `lifx-async` can change any of the three. The value of measuring it is that the library's mDNS TTL and goodbye handling is proven only synthetically, so a real observation is the one check on whether that model resembles reality, and that the resulting figure is a consumer-facing fact worth stating rather than inferring.
   - Current: The mDNS cache handles TTL and goodbye semantics synthetically, and no end-to-end staleness observation exists for this fleet and border-router set.
   - Target: After a predeclared run of successful paired discovery, one explicitly selected device is disconnected and both discovery paths are polled at a frozen cadence until repeated absence confirms expiry. The protocol distinguishes first absence from confirmed expiry so one missed round cannot end the measurement.
   - Acceptance: The evidence identifies the selected target only by stable alias, records monotonic disconnect, first-absence, and confirmed-expiry times, includes every intervening poll result, and restores the device to its starting availability after the experiment. THREAD-04 does not pass on a single missed round or an unconfirmed lower bound. The reported figure must be stated as this fleet's and this border-router set's observed staleness, and must not be presented as LIFX's SRP lease, a universal Thread limit, or a tuning input for any library constant.

5. **THREAD-05 - Per-class evidence or named gap**: Close every public lighting device class with either individual privacy-safe Thread evidence for every currently available device or an explicit named hardware gap.
   - Current: `Light`, `MultiZoneLight`, `MatrixLight`, and `CeilingLight` are available on Thread; `InfraredLight` and `HevLight` hardware in the fleet predates Thread. There is no Phase 14 class ledger joining those facts to evidence records.
   - Target: The four available classes link to their individual device evidence records. `InfraredLight` and `HevLight` link to dated named-gap records that state the missing hardware capability without implying permanent product exclusion. Availability and gap status are frozen per evidence session and any later change is recorded explicitly. Closure depends on physical discovery evidence and complete physical request trials for every expected alias; per THREAD-03, an animation attempt is never part of the closure criterion.
   - Acceptance: A machine-readable ledger contains exactly one closure disposition for each of the six public lighting classes, resolves every available device to its own evidence record, rejects an empty or duplicate disposition, and never substitutes a named gap merely because an available device performed poorly. `derive_class_ledger_from_roster()` closes a class without consulting animation evidence.

6. **DOCS-04 - Broadcast-first consumer guidance**: Publish guidance explaining what changes for existing broadcast-first consumers, what Thread support does and does not provide, and how to use the default and source-specific discovery APIs.
   - Current: The high-level documentation describes `discover()` and `discover_mdns()` separately but does not present the merged default, `discover_udp()`, and Thread reachability as one migration story.
   - Target: Consumer-facing guidance states that existing `discover()` callers gain verified Thread candidates through mDNS, documents `discover_udp()` and `discover_mdns()` as explicit controls, explains IPv6 targeting, and provides runnable examples using synthetic addresses and serials only.
   - Acceptance: Documentation tests and review confirm that the default and both source-specific APIs are named accurately, at least one runnable broadcast-first migration example is present, and no private network detail appears.

7. **DOCS-05 - Known limitations**: Publish the four discovery limitations instead of leaving consumers to infer them.
   - Current: The implementation uses IPv4 multicast queries and receives direct legacy-unicast replies, does not join for unsolicited announcements, and proves mesh-scale record behaviour synthetically; those facts are not assembled into clear consumer guidance.
   - Target: The documentation explicitly states the IPv4 multicast query leg, legacy-unicast-only reception, absence of unsolicited announcements, and synthetic rather than current-hardware fleet-scale proof. It distinguishes these limits from device control over IPv6.
   - Acceptance: A documentation check finds all four limitations and the synthetic-versus-hardware qualification in the consumer guidance, with no claim that the present fleet proves mesh-scale behaviour.

8. **DOCS-06 - Accurate concurrency architecture**: Remove every false repository-guidance claim that multi-device operations use `asyncio.TaskGroup` and replace it with the Python 3.10-compatible behaviour present in source.
   - Current: Both `CLAUDE.md` and `AGENTS.md` contain the false claim even though `TaskGroup` does not occur in `src/` and cannot support the project's Python 3.10 floor.
   - Target: Both architecture guides describe independent per-device connections and the actual supported coordination pattern without inventing a concurrency primitive.
   - Acceptance: A targeted search finds no false `TaskGroup` claim in either guide, the replacement text agrees with current source and Python 3.10 support, and automated checks prevent the two tracked guides from drifting apart on this statement.

## Boundaries

**In scope:**

- A Phase 14 hardware-measurement protocol and privacy-safe evidence schema.
- Repeated paired discovery observations for `discover()` and `discover_mdns()`.
- Per-device Thread request RTT and retransmission observations.
- Recording Thread animation as an explicit, non-gating scope boundary, citing the one existing Candle observation for exactly what it shows.
- One directly observed border-router advertisement-expiry experiment.
- A complete six-class Thread evidence or named-gap ledger.
- Evidence-backed correction of a concrete correctness or reliability defect found by the phase.
- Broadcast-first Thread consumer guidance and the four known mDNS limitations.
- Correction and drift protection for the false `asyncio.TaskGroup` statement in both `CLAUDE.md` and `AGENTS.md`.

**Out of scope:**

- An authoritative or universal Thread performance benchmark, regression threshold, or WiFi-parity gate, because the current mesh has unresolved interference and Thread is expected to have materially lower bandwidth.
- Retuning performance constants from interference-confounded measurements; a later clean, replicated run must isolate the library behaviour first.
- Home Assistant or other downstream consumer implementation changes; this phase ships library evidence and guidance only.
- Real-hardware fleet-scale mesh proof, multiple border-router topology proof, or overflow behaviour; FLEET-01 and FLEET-02 remain deferred and synthetic proof remains clearly labelled.
- Thread hardware evidence for `InfraredLight` and `HevLight`; no capable fleet hardware exists, so both receive named gaps.
- A new public discovery API, a public async-API redesign, or a runtime dependency.
- Committing private alias mappings, serials, addresses, hostnames, or raw discovery captures.
- Measuring Thread animation performance for any class beyond the one already-collected Candle observation; the library will not support sustained Thread animation, so this is a recorded scope boundary, not deferred work. Locking `Animator` to WiFi devices is captured as `.planning/seeds/SEED-003-lock-animation-to-wifi.md` and is not implemented in this phase.

## Constraints

- The library must continue to support Python 3.10 through 3.14 and remain runtime-dependency-free.
- Hardware measurements must use real LIFX Thread devices; emulator and synthetic results may prove harness mechanics but cannot replace physical evidence.
- Runs that make performance claims must be serial and quiesced from known background pollers. Any interference or inability to quiesce the environment must be recorded as a confounder.
- Each measurement protocol must be versioned and frozen before its hardware run. Exact sample counts, the small animation observation schedule, run duration, polling cadence, and statistical presentation are discuss-phase decisions, not post-result choices.
- Raw observations may exist only in operator-controlled private storage. Tracked evidence uses stable aliases and format-preserving synthetic examples, never the alias mapping itself.
- Empty, failed, interrupted, and censored observations are data. They cannot be silently removed from the evidence set.
- Animation observation has no WiFi comparison, minimum FPS, required ceiling, or performance pass threshold. Zero useful throughput is valid evidence. The phase evaluates execution safety, evidence integrity, and restoration, not transport parity.
- Mutable hardware stages require explicit target selection, serial execution, full pre-state capture, best-effort restoration on every exit path, and an honest restoration outcome.
- Australian English spelling is required in prose.

## Acceptance Criteria

- [ ] **AC-01:** A versioned Phase 14 protocol is frozen before hardware execution and requires repeated, paired `discover()` and `discover_mdns()` rounds; a single round cannot satisfy THREAD-01.
- [ ] **AC-02:** Every planned discovery round, including zero-result, failed, and interrupted rounds, remains represented in privacy-safe evidence and duplicate packets do not inflate per-device coverage.
- [ ] **AC-03:** Every available Thread device has raw request timing, timeout, and retransmit observations plus deterministic median, p95, and maximum summaries, qualified by the recorded environment.
- [ ] **AC-04:** The evidence and report record Thread animation as an out-of-scope, non-gating boundary, citing the one existing Candle observation (`LIFX-Candle-C-1`, all three of 1/2/5 FPS completed) only as proof Thread carries the frames without failing; no further alias receives an animation attempt.
- [ ] **AC-05:** Animation evidence states that the WiFi-only spike and the single Candle observation are not usability, parity, minimum-FPS, ceiling, smoothness, ACK-latency, or universal-limit evidence, and cannot block the non-animation deliverables, gate any class's closure, or justify tuning.
- [ ] **AC-06:** Advertisement staleness records the complete sequence from successful precondition through disconnect, first absence, repeated confirmation, confirmed expiry, and restored availability; one missed round is insufficient.
- [ ] **AC-07:** The class ledger gives `Light`, `MultiZoneLight`, `MatrixLight`, and `CeilingLight` individual evidence-backed closure and gives `InfraredLight` and `HevLight` explicit dated named gaps.
- [ ] **AC-08:** Every tracked measurement row includes a session identity, protocol version, revision, source, round/trial identity, stable device alias where applicable, outcome, and confounder classification.
- [ ] **AC-09:** No performance constant changes solely because of interference-confounded Phase 14 results; any correction cites replicated evidence of a concrete correctness or reliability defect and carries focused automated tests.
- [ ] **AC-10:** Consumer guidance accurately covers merged `discover()`, `discover_udp()`, `discover_mdns()`, Thread reachability, and a runnable broadcast-first migration example.
- [ ] **AC-11:** Consumer guidance explicitly documents IPv4 multicast queries, legacy-unicast-only replies, no unsolicited announcements, and synthetic rather than current-hardware fleet-scale proof.
- [ ] **AC-12:** `CLAUDE.md` and `AGENTS.md` contain no false `asyncio.TaskGroup` architecture claim and agree on the Python 3.10-compatible behaviour present in source.
- [ ] **AC-13 (prohibition):** Tracked evidence contains no raw serial, address, hostname, raw discovery capture, or private alias mapping.
- [ ] **AC-14 (prohibition):** Hardware tooling cannot run a fleet-wide mutation, cannot control an unselected target, and cannot report a mutating stage as passed without a restoration outcome.
- [ ] **AC-15 (prohibition):** Reviews do not describe interference-confounded results as authoritative benchmarks, universal limits, regression gates, or sufficient grounds for performance retuning.
- [ ] **AC-16 (prohibition):** Evidence generation cannot silently discard, overwrite, or exclude failed, empty, interrupted, censored, or inconvenient observations.
- [ ] **AC-17 (prohibition):** Synthetic evidence cannot be labelled as physical-fleet evidence, and poor results from available hardware cannot be converted into a named-gap disposition.

## Edge Coverage

**Coverage:** 43/43 applicable edges resolved - 0 unresolved

| Category | Requirement | Status | Resolution / Reason |
|----------|-------------|--------|---------------------|
| boundary | THREAD-01 | ✅ covered | AC-01 requires a predeclared repeated paired protocol; one round is invalid. |
| adjacency | THREAD-01 | ✅ covered | AC-02 counts unique alias/source/round outcomes, not duplicate packets. |
| empty | THREAD-01 | ✅ covered | AC-02 retains zero-result and failed rounds. |
| ordering | THREAD-01 | ⛔ dismissed | Aggregation is keyed by session, source, round, and alias; input order has no semantic effect. |
| precision | THREAD-01 | ✅ covered | AC-02 retains integer counts and underlying observations; display rounding cannot change coverage. |
| idempotency | THREAD-01 | ✅ covered | AC-08 requires session identity, so a rerun creates distinct evidence rather than overwriting. |
| concurrency | THREAD-01 | ✅ covered | Constraints require serial, quiesced performance runs and mark interruption honestly. |
| boundary | THREAD-02 | ✅ covered | AC-03 records the full RTT distribution around the current 200 ms floor; the protocol freezes trial boundaries before execution. |
| adjacency | THREAD-02 | ✅ covered | AC-03 correlates retransmits with one logical request, so duplicate replies do not create extra trials. |
| empty | THREAD-02 | ✅ covered | AC-03 records timeouts and absent acknowledgements as outcomes. |
| ordering | THREAD-02 | ✅ covered | AC-08 preserves trial identity and chronological raw observations while summaries remain deterministic. |
| precision | THREAD-02 | ✅ covered | AC-03 requires raw monotonic observations plus deterministic median/p95/maximum summaries. |
| idempotency | THREAD-02 | ✅ covered | AC-08 separates repeated sessions by identity and revision. |
| concurrency | THREAD-02 | ✅ covered | Constraints prohibit unlabelled concurrent load and require environmental confounders to be recorded. |
| boundary | THREAD-03 | ✅ covered | AC-04 records Thread animation as an out-of-scope boundary rather than a per-class measurement; no additional attempt is required at the edge of the fleet. |
| adjacency | THREAD-03 | ✅ covered | AC-04 keeps the one existing Candle observation a separate record from discovery/request/staleness evidence for the same alias. |
| empty | THREAD-03 | ✅ covered | AC-04 does not require a non-empty animation record for any class; zero animation attempts is the expected, documented state. |
| ordering | THREAD-03 | ⛔ dismissed | There is no further attempt sequence to order; the single pre-existing Candle observation is cited as-is. |
| precision | THREAD-03 | ✅ covered | AC-04 retains the existing observation's integer offered/sent/gated/failed counts; AC-05 forbids turning them into a WiFi comparison or performance gate. |
| idempotency | THREAD-03 | ✅ covered | The scope-boundary statement and the one cited observation do not change on a rerun of the phase's documentation checks. |
| concurrency | THREAD-03 | ⛔ dismissed | No animation observation runs as part of this phase; there is no concurrent-load boundary to test. |
| boundary | THREAD-04 | ✅ covered | AC-06 distinguishes successful precondition, first absence, repeated confirmation, and confirmed expiry. |
| precision | THREAD-04 | ✅ covered | AC-06 requires monotonic timestamps for disconnect and both expiry observations. |
| idempotency | THREAD-04 | ✅ covered | AC-08 gives every repeated staleness experiment a distinct session identity. |
| concurrency | THREAD-04 | ✅ covered | One selected device is disconnected at a time and AC-06 requires restored availability. |
| adjacency | THREAD-05 | ✅ covered | AC-07 keeps individual devices separate even when they share a class. |
| empty | THREAD-05 | ✅ covered | AC-07 requires one valid closure disposition for every class; empty dispositions fail. |
| encoding | THREAD-05 | ✅ covered | AC-08 uses exact class names and stable operator-controlled aliases while AC-13 excludes raw identifiers. |
| ordering | THREAD-05 | ⛔ dismissed | Class-ledger row order has no contract meaning because closure is keyed by exact class name. |
| idempotency | THREAD-05 | ✅ covered | Availability changes and reruns create explicit new evidence rather than silently replacing the prior disposition. |
| concurrency | THREAD-05 | ✅ covered | Inventory is frozen per session; concurrent availability changes must be recorded explicitly. |
| adjacency | DOCS-04 | ⛔ dismissed | Guidance sections are independent prose; touching or equal collection elements do not exist. |
| empty | DOCS-04 | ✅ covered | AC-10 requires all three APIs and a runnable migration example. |
| encoding | DOCS-04 | ⛔ dismissed | API names are exact Python identifiers in code spans; no text-length or normalisation comparison exists. |
| ordering | DOCS-04 | ⛔ dismissed | Section order does not alter the documented API contract. |
| adjacency | DOCS-05 | ⛔ dismissed | The four limitations are independent facts rather than mergeable collection intervals. |
| empty | DOCS-05 | ✅ covered | AC-11 requires every named limitation and the evidence qualification. |
| encoding | DOCS-05 | ⛔ dismissed | Standard Markdown text has no length/equality contract in this requirement. |
| ordering | DOCS-05 | ⛔ dismissed | The limitations may appear in any readable order without changing meaning. |
| adjacency | DOCS-06 | ⛔ dismissed | Architecture-guide matches are independently corrected; adjacency has no semantic effect. |
| empty | DOCS-06 | ✅ covered | AC-12 requires zero false claims and accurate replacement text in both guides. |
| encoding | DOCS-06 | ⛔ dismissed | `asyncio.TaskGroup` is an exact ASCII code identifier; no alternate normalisation is accepted. |
| ordering | DOCS-06 | ⛔ dismissed | Guide ordering does not affect whether the factual claim is correct. |

## Prohibitions (must-NOT)

**Coverage:** 5/5 applicable prohibitions resolved - 0 unresolved

| Prohibition (must-NOT statement) | Requirement | Status | Verification / Reason |
|----------------------------------|-------------|--------|------------------------|
| MUST NOT place raw serials, addresses, hostnames, raw discovery output, or the private alias mapping in tracked evidence or documentation. | THREAD-01..05 | resolved | test; AC-13. Mechanical check to be wired by plan-phase; no descriptor exists yet. |
| MUST NOT mutate the fleet broadly, control an unselected device, or report success without recording restoration after a mutating stage. | THREAD-03..04 | resolved | test; AC-14. Mechanical check to be wired by plan-phase; no descriptor exists yet. |
| MUST NOT present interference-confounded observations as authoritative benchmarks, universal Thread limits, regression gates, or sufficient grounds for tuning constants. | THREAD-02..03 | resolved | judgment; AC-15 routes to evidence-language review. |
| MUST NOT discard, overwrite, or silently exclude failed, empty, interrupted, censored, or inconvenient observations. | THREAD-01..05 | resolved | test; AC-16. Mechanical check to be wired by plan-phase; no descriptor exists yet. |
| MUST NOT label synthetic evidence as physical-fleet evidence or turn poor results from available hardware into a named gap. | THREAD-05, DOCS-05 | resolved | test; AC-17. Mechanical check to be wired by plan-phase; no descriptor exists yet. |

Generic network-security and dependency-supply-chain controls remain canon requirements for `$gsd-secure-phase`; they are not duplicated as Phase 14 prohibitions.

## Ambiguity Report

| Dimension | Score | Min | Status | Notes |
|-----------|-------|-----|--------|-------|
| Goal Clarity | 0.96 | 0.75 | ✓ | Four measurement areas, class ledger, and documentation outcome are explicit. |
| Boundary Clarity | 0.91 | 0.70 | ✓ | Current hardware classes, named gaps, downstream exclusions, and benchmark limits are explicit. |
| Constraint Clarity | 0.94 | 0.65 | ✓ | Interference, privacy, hardware safety, version support, and protocol-freeze rules are locked. |
| Acceptance Criteria | 0.84 | 0.70 | ✓ | Seventeen pass/fail criteria; exact sampling mechanics deliberately belong to discuss-phase. |
| **Ambiguity** | **0.08** | **<=0.20** | **✓** | Gate passed after Round 2. |

Status: ✓ = met minimum, ⚠ = below minimum (planner treats as assumption)

## Interview Log

| Round | Perspective | Question summary | Decision locked |
|-------|-------------|------------------|-----------------|
| 1 | Researcher | Which hardware, discovery paths, and evidence-triggered changes belong to Phase 14? | Available hardware extends beyond MatrixLight; discovery pairs `discover()` with `discover_mdns()`; concrete evidence may drive scoped correctness fixes. |
| 2 | Researcher + Simplifier | Which classes are available, what evidence is class-relevant, and must Thread match WiFi? | `Light`, `MultiZoneLight`, `MatrixLight`, and `CeilingLight` are available; each gets applicable evidence; `InfraredLight` and `HevLight` are named gaps; lower Thread animation performance is expected and acceptable. |
| Gate | Seed Closer | Is clarity sufficient to proceed? | Ambiguity 0.08 accepted; proceed to completeness probes and SPEC generation. |
| Edge | Edge-completeness probe | Which quantitative and lifecycle edges are locked now? | Exact sampling mechanics move to discuss-phase; protocols freeze before runs; all outcomes remain; current interference makes performance results qualified rather than authoritative; both architecture guides are corrected. |
| Prohibition | Must-NOT probe | Which privacy, safety, integrity, and transparency failures are forbidden? | All five surfaced prohibitions retained with test or judgment verification tiers. |

---

*Phase: 14-thread-revalidation-and-docs*
*Spec created: 2026-08-31*
*Next step: $gsd-discuss-phase 14 - implementation decisions (measurement protocol, evidence schema, harness ownership, and documentation structure)*
