# Phase 13: Merged Discovery — Specification

**Created:** 2026-08-30
**Ambiguity score:** 0.06 (gate: ≤ 0.20)
**Requirements:** 9 locked

## Goal

Thread devices appear through the default `discover()` API while callers retain explicit UDP-only and mDNS-only enumeration, overlapping UDP callers generate only one broadcast sweep, and serial lookup, liveness, timing, validation, and cleanup contracts remain falsifiably intact.

## Background

Phases 11 and 12 have supplied the two hardened discovery legs that Phase 13 consumes. UDP discovery is family-aware, source- and serial-validating, first-wins per serial, bounded by overall and consumer-aware idle deadlines, and proven over IPv4 and IPv6. mDNS discovery uses an ephemeral legacy-unicast socket, invocation-local non-reusable record state, bounded address follow-up, strict construction provenance, private raw-record APIs, and descriptive `Device.connectivity` metadata.

The high-level API has not yet merged those legs. On the current `main`, `discover()` and `find_by_serial()` use UDP only, `discover_mdns()` is the separate mDNS-only enumerator, and no `discover_udp()` name exists. An mDNS advertisement is converted directly into a device without a current direct-response liveness check. The lower-level broadcast invariant suites exist and a focused pre-merge run passed all ten selected timeout, consumer-time, source-validation, serial-validation, and deduplication tests, but the focused public `discover()` contract layer and Phase 13 before/after measurement harness do not exist.

The hardware spikes measured why UDP concurrency is part of the product contract rather than merely an implementation detail. The accepted rebroadcast schedule can provoke roughly 600–850 responses during one sweep on the measured 73-device WiFi fleet. If N callers independently start the same sweep, the library can multiply that load and become a denial-of-service source for access points and bulbs. Phase 13 therefore shares one active compatible UDP sweep across overlapping `discover()` and `discover_udp()` callers. This is active-sweep single-flight, not an unmeasured persistent cache: the shared state is discarded when the sweep finishes. mDNS retains its Phase 11 per-call cache semantics.

## Requirements

1. **Default merged discovery**: `discover()` enumerates UDP and mDNS concurrently, streams devices as they become available, and emits each normalised serial at most once.
   - Current: `discover()` delegates only to `discover_devices()`, so Thread-only devices require a separate caller opt-in to `discover_mdns()`.
   - Target: `discover()` starts both legs under the caller's one discovery window. Every unique answering supported device is streamed once. If both legs produce the same normalised 12-hex serial, the literal first result that completes its required validation and liveness checks wins; no transport receives hidden canonical priority.
   - Acceptance: Controlled async-leg tests prove UDP-only, mDNS-only, mixed, empty, and dual-advertised inputs; Thread connectivity is available through default discovery; duplicates yield exactly once; and reversing which valid duplicate finishes first reverses the selected result without changing the unique result set.

2. **Pre-merge compatibility gate**: Existing lower-level invariants, a focused public `discover()` contract suite, and the measurement harness exist and pass against the broadcast-only implementation before merge behaviour is introduced.
   - Current: Lower-level tests cover the overall deadline, consumer-time exclusion from the idle window, source and serial validation, and first-wins serial deduplication. The focused selected baseline is ten passing tests. No compact public contract layer or Phase 13 measurement harness exists.
   - Target: Before production merge changes land, executable public-API tests pin empty discovery, overall timeout, consumer-time exclusion, first-wins duplicate handling, source/serial validation inheritance, fresh state after a completed call, and early-close cleanup. The same pre-change revision can run the before/after harness in broadcast-only mode.
   - Acceptance: Git and test evidence show the invariant tests and measurement harness passing on the broadcast-only parent revision before the first merge implementation commit; the same assertions remain unchanged and green on the final merged revision.

3. **mDNS failure isolation**: A failed or unavailable mDNS leg never ends or shortens the UDP leg of default discovery.
   - Current: `discover()` has no mDNS leg, so no cross-leg failure contract exists.
   - Target: Expected mDNS discovery failures are isolated to that leg. `discover()` continues streaming UDP results until the UDP leg's own deadline and completes normally. Every later call attempts mDNS afresh because no completed failure is cached.
   - Acceptance: Tests inject mDNS failure before open, during receipt, and after at least one record; UDP results still stream, the UDP schedule and deadline match UDP-only discovery, no exception or task-warning escapes from the failed leg, and a later call starts a fresh mDNS leg.

4. **mDNS liveness before yield**: A device sourced from mDNS is yielded by default discovery only after a valid direct LIFX protocol response proves that it is answering during the current discovery call.
   - Current: The border router's SRP advertisement may outlive a Thread device for hours, and `discover_mdns()` constructs a device from the advertisement without a direct device-response check.
   - Target: Default merged discovery treats the advertisement as an address candidate, not proof of liveness. A valid direct response must arrive within the caller's existing discovery window before the serial becomes eligible to win the cross-leg merge. Failed, malformed, mismatched, stale, spoof-only, or cancelled verification produces no result and allocates no separate unbounded deadline. Each completed discovery call discards its verification state.
   - Acceptance: Synthetic tests cover live response, silence, malformed response, wrong source/serial, cancellation, and a competing live UDP result; only a valid directly answering mDNS candidate can win, and every task, generator, connection, and socket is reaped on every path.

5. **Dual-source serial lookup**: `find_by_serial()` races UDP and mDNS, returns the first valid matching device, and reaps all losing work before returning.
   - Current: `find_by_serial()` scans only UDP discovery and therefore cannot find a Thread-only device.
   - Target: Both legs start concurrently under the caller's one timeout. A leg completing without a match does not end the lookup while the other can still succeed. The first valid matching raw result wins; the loser is cancelled and awaited before device construction or return. Each invocation starts a fresh race and exposes no source selector.
   - Acceptance: Tests cover UDP-first, mDNS-first, one-leg no-match, one-leg expected failure, both no-match, simultaneous matches, caller cancellation, and repeated/concurrent calls; return happens only after losing generators report closure, with no pending task, socket, or unretrieved exception.

6. **Measured timing and result delta**: A reproducible harness records the broadcast-only and merged-discovery timing and result-count delta against the available fleet and the emulator CI path without inventing a regression ceiling.
   - Current: The roadmap records a historical 25-device UDP result and two additional Thread devices over mDNS, but there is no paired Phase 13 harness or current-revision emulator timing record.
   - Target: The harness records paired scenarios with raw monotonic elapsed values, time to first result, completion time, unique result counts, source contribution, and run context. At least six paired fleet rounds are captured because single discovery rounds are known to mislead; at least one current-revision emulator CI run records both modes. Baseline and merged arms run sequentially to avoid network interference. The delta is evidence, not a pass/fail performance threshold, and each run remains a distinct record.
   - Acceptance: A validator accepts complete privacy-safe paired fleet and emulator records, rejects missing arms or incomparable scenario metadata, and calculates the delta without rounding away raw observations. An unavailable fleet is reported explicitly and does not substitute for the mandatory emulator evidence; Phase 13 cannot claim the required fleet comparison until the paired fleet record exists.

7. **Firmware 3.70–3.99 identity evidence**: The low-priority FIND-08 check records whether mDNS TXT `id` equals broadcast serial for every available eligible WiFi device without becoming a Phase 13 gate.
   - Current: No current evidence establishes the relationship for the only firmware population where MAC and serial can differ.
   - Target: Eligibility uses integer `version_major == 3` and inclusive integer `70 <= version_minor <= 99`. For each available eligible device, the comparison uses normalised 12-hex identities and emits only a privacy-safe alias plus match disposition. If no eligible device exists, the evidence records a named non-gating population gap instead of fabricating confirmation from Thread, emulator, or other firmware.
   - Acceptance: Tests pin the 3.69/3.70/3.99/4.0 boundaries, case and separator normalisation, duplicate observations, and empty eligible population; evidence review confirms that only eligible WiFi hardware can close FIND-08 and that evidence row ordering has no semantic effect.

8. **Explicit source-specific public APIs**: Callers can choose UDP-only or mDNS-only enumeration without making the default incomplete.
   - Current: `discover()` is UDP-only and `discover_mdns()` is mDNS-only; no `discover_udp()` exists.
   - Target: `discover()` is the dual-source default, new public `discover_udp()` preserves UDP-only enumeration, and existing public `discover_mdns()` remains mDNS-only. Both `lifx.api` and the top-level `lifx` package export all three. Source selection changes only which discovery sources run; it does not change device routing, retry, tuning, or `Device.connectivity` semantics. `find_by_serial()` remains dual-source, while `find_by_ip()` and `find_by_label()` retain their established contracts.
   - Acceptance: Public-surface and behavioural tests prove exact exports and source participation for all three enumerators, ensure no `transport=` selector is added, and prove source-specific and default calls can be repeated or run concurrently under the UDP sharing contract without cross-call mDNS cache state.

9. **Active UDP single-flight sharing**: Compatible overlapping `discover()` and `discover_udp()` callers share one active UDP broadcast sweep so caller concurrency cannot multiply the rebroadcast schedule or response load.
   - Current: Every public UDP discovery invocation creates a new endpoint and executes the complete escalating rebroadcast schedule independently.
   - Target: Within the process, calls are compatible when `broadcast_address`, `port`, `timeout`, `max_response_time`, and `idle_timeout_multiplier` are equal. Compatible overlapping callers subscribe to one active UDP sweep. A late subscriber first receives each still-active sweep record already accepted, in original discovery order, then receives later records; every subscriber sees each serial at most once. `device_timeout` and `max_retries` remain caller-specific device settings and do not prevent sweep sharing. Closing one subscriber does not disrupt the others; closing the last subscriber cancels and reaps the sweep. When the sweep completes, its positive, empty, and failed state is discarded, so the next call starts a fresh sweep. mDNS remains invocation-local and is not placed behind this shared cache.
   - Acceptance: Deterministic tests start N overlapping compatible callers across both public entry points and prove the observed UDP send destinations, packet bytes, send count, and schedule equal one caller; late subscribers receive the active sweep's accepted prefix and suffix exactly once; one-subscriber and last-subscriber cancellation paths close correctly; incompatible wire/timing arguments do not share; and a post-completion call creates a new sweep.

## Boundaries

**In scope:**

- Default concurrent UDP+mDNS `discover()` with streaming serial-keyed first-valid-result merge.
- Public UDP-only `discover_udp()` alongside the existing mDNS-only `discover_mdns()`.
- One active compatible UDP sweep shared across overlapping `discover()` and `discover_udp()` callers, including active-sweep replay for late subscribers and deterministic subscriber cleanup.
- A pre-merge public `discover()` invariant layer and before/after measurement harness that pass against the broadcast-only baseline.
- Expected mDNS-failure degradation to UDP-only default discovery.
- Direct-response liveness verification for mDNS candidates before default merged discovery yields them.
- Dual-source first-valid-result `find_by_serial()` with complete loser cancellation and reaping.
- Repeated paired fleet timing/result measurements, emulator CI wall-time evidence, and low-priority eligible-firmware identity evidence.
- Privacy-safe synthetic tests and committed measurements.

**Out of scope:**

- A completed-sweep result cache, negative cache, configurable cache TTL, or stale-result replay — no safe post-completion lifetime was measured by the spike series.
- Sharing or persisting mDNS record state across calls — Phase 11 deliberately scopes its cache to one invocation, and the measured response-storm concern is UDP broadcast.
- A `transport=` parameter or caller control over routing, retries, connectivity classification, or tuning — source-specific enumeration uses named public functions only.
- An mDNS path of `find_by_label()`'s own — the milestone retains its established targeted-label mechanism.
- Source selection for `find_by_serial()`, `find_by_ip()`, or `find_by_label()` — only enumeration gains explicit UDP-only and mDNS-only entry points.
- Home Assistant integration changes — this repository supplies the library contract; downstream integration work remains separate.
- Retuning discovery, request-retry, bandwidth, or animation constants — Phase 14 measures Thread behaviour before any WiFi-derived constant changes.
- Thread commissioning, border-router management, IPv6 multicast mDNS queries, or multicast-group rejoin — these remain outside the library or milestone boundary.
- Phase 14 device-class coverage and Thread performance measurements — Phase 13 measures discovery compatibility, not Thread tuning or animation ceilings.
- Runtime dependencies, a threading rewrite, or Python 3.11-only concurrency primitives — the library remains zero-dependency, asyncio-based, and Python 3.10 compatible.

## Constraints

- Python 3.10 through 3.14 remain supported; `asyncio.TaskGroup` is unavailable at the floor and has incorrect cancel-sibling semantics for failure-isolated legs.
- Runtime dependencies remain empty. Python dependency management and test execution use `uv` exclusively.
- The existing UDP rebroadcast, overall-timeout, idle-timeout, validation, deduplication, and retry constants remain unchanged.
- The default `discover()` call is dual-source, while source-specific enumeration remains available through `discover_udp()` and `discover_mdns()`.
- UDP single-flight compatibility is defined by equal UDP wire/timing arguments: `broadcast_address`, `port`, `timeout`, `max_response_time`, and `idle_timeout_multiplier`. Per-device `device_timeout` and `max_retries` remain subscriber-specific.
- UDP shared state lives only for one active sweep. No positive, empty, or failure outcome survives completion.
- mDNS continues to use an IPv4 multicast query from an ephemeral source port, receive legacy-unicast replies, avoid the multicast group and unsolicited announcements, and keep cache state local to one call.
- Every expected one-leg failure leaves the other leg productive; caller cancellation and early generator close synchronously reap every owned generator, task, endpoint, and temporary connection.
- Fleet measurements use at least six paired rounds, quiesce competing pollers where operationally possible, and record confounds rather than converting them into a pass.
- Tests, logs, measurements, documentation, commits, and evidence use synthetic identifiers or stable privacy-safe aliases and contain no live serial, MAC address, IP address, hostname, account identifier, private mapping, or raw discovery output.

## Acceptance Criteria

- [ ] AC1: Before merged production code lands, existing lower-level invariants, the focused public `discover()` contract suite, and the measurement harness pass against the broadcast-only parent revision.
- [ ] AC2: Default `discover()` starts UDP and mDNS concurrently, streams UDP-only and mDNS-only devices, and yields no device on an empty synthetic network.
- [ ] AC3: Cross-leg duplicates are keyed by normalised 12-hex serial and yield exactly once; the first result completing all required validation and liveness checks wins without fixed transport priority.
- [ ] AC4: Expected mDNS failures before open, during receipt, and after a partial result leave the UDP schedule, results, and deadline intact and emit no unhandled task exception.
- [ ] AC5: A later `discover()` call starts fresh mDNS work after any earlier mDNS success, empty result, or failure.
- [ ] AC6: An mDNS candidate is yielded by default discovery only after a valid direct LIFX response during the current caller window; silent, malformed, mismatched, stale, spoof-only, and cancelled candidates are not yielded.
- [ ] AC7: UDP-first, mDNS-first, one-leg no-match, one-leg failure, both no-match, simultaneous-match, repeated-call, concurrent-call, and caller-cancellation tests prove `find_by_serial()` returns the first valid match and reaps both legs before return.
- [ ] AC8: `discover`, `discover_udp`, and `discover_mdns` are public from both `lifx.api` and top-level `lifx`; they run dual, UDP-only, and mDNS-only enumeration respectively, with no `transport=` selector.
- [ ] AC9: `find_by_serial()` remains dual-source with no source selector; `find_by_ip()` and `find_by_label()` retain their existing public signatures and source behaviour.
- [ ] AC10: N overlapping `discover()` and `discover_udp()` callers with equal UDP wire/timing arguments produce byte-for-byte the same UDP destinations, sends, send count, and rebroadcast schedule as one caller.
- [ ] AC11: A late compatible subscriber receives the active UDP sweep's accepted records in original discovery order followed by later records, with each serial delivered once to that subscriber.
- [ ] AC12: Closing one UDP subscriber leaves the shared sweep productive for remaining subscribers; closing the last subscriber cancels and reaps the sweep without a pending task or socket.
- [ ] AC13: Calls differing in `broadcast_address`, `port`, `timeout`, `max_response_time`, or `idle_timeout_multiplier` do not share a UDP sweep; differing `device_timeout` or `max_retries` retain caller-specific device configuration without multiplying the sweep.
- [ ] AC14: After a shared UDP sweep completes with positive, empty, or failed outcome, a later call creates a fresh sweep; no persistent TTL or negative cache exists.
- [ ] AC15: At least six sequential paired fleet rounds and at least one current-revision emulator CI run record raw time-to-first, completion time, unique counts, source contribution, and comparable scenario metadata for broadcast-only and merged discovery.
- [ ] AC16: The timing harness reports the observed delta without a pass/fail regression ceiling, retains raw measurements and integer counts, rejects missing/incomparable arms, and does not retune any constant.
- [ ] AC17: FIND-08 eligibility uses integer firmware boundaries 3.70 through 3.99 inclusive and normalised 12-hex identity comparison; absent eligible hardware produces a named non-gating gap rather than substitute confirmation.
- [ ] AC18: Default and source-specific enumeration affect only discovery participation; device routing, request retries, tuning, and `Device.connectivity` semantics do not change by entry point.
- [ ] AC19: Phase 13 tests, logs, measurements, documentation, commits, and evidence contain no live infrastructure or hardware identifiers, private mapping, or raw discovery output.
- [ ] AC20: Existing discovery, mDNS, IPv6, public API, and lifecycle suites remain green; the complete frozen pytest suite, Ruff format/lint, and Pyright checks pass on the final tree.

## Edge Coverage

**Coverage:** 36/36 applicable edges resolved · 0 unresolved

| Category | Requirement | Status | Resolution / Reason |
|----------|-------------|--------|---------------------|
| Adjacency / touching | R1 | ✅ covered | AC3 specifies the identical-serial collision rule and literal first valid winner. |
| Empty / degenerate | R1 | ✅ covered | AC2 requires an empty network to yield no device. |
| Ordering / stability | R1 | ✅ covered | AC2 and AC3 require stream-as-found ordering without fixed transport priority. |
| Idempotency / repetition | R1 | ✅ covered | AC5 and AC14 require completed calls to discard source state and start fresh work. |
| Concurrency / effect ordering | R1 | ✅ covered | AC2–AC6 and AC10–AC14 specify leg, subscriber, failure, and cancellation ordering. |
| Adjacency / touching | R2 | ✅ covered | AC1 and AC3 pin duplicate-response and first-wins behaviour in both invariant layers. |
| Empty / degenerate | R2 | ✅ covered | AC1 requires the public pre-merge suite to pin empty discovery. |
| Ordering / stability | R2 | ✅ covered | AC1 and AC3 preserve the first accepted record as winner. |
| Idempotency / repetition | R2 | ✅ covered | AC1 requires the same unchanged invariants to pass before and after the merge. |
| Concurrency / effect ordering | R2 | ✅ covered | AC1 includes public early-close cleanup before merge behaviour is introduced. |
| Idempotency / repetition | R3 | ✅ covered | AC5 requires every completed call to attempt mDNS afresh. |
| Concurrency / effect ordering | R3 | ✅ covered | AC4 proves one failed leg cannot cancel or shorten the surviving UDP leg. |
| Idempotency / repetition | R4 | ✅ covered | AC5 and AC6 require fresh current-call liveness rather than persistent verification state. |
| Concurrency / effect ordering | R4 | ✅ covered | AC6 covers competing live results, cancellation, and complete cleanup. |
| Idempotency / repetition | R5 | ✅ covered | AC7 explicitly covers repeated serial lookups with fresh races. |
| Concurrency / effect ordering | R5 | ✅ covered | AC7 covers simultaneous matches, no-match survival, cancellation, and loser reaping. |
| Boundary values | R6 | ✅ covered | AC15 fixes the required fleet/emulator evidence boundary; AC16 specifies that no regression threshold exists. |
| Adjacency / touching | R6 | ✅ covered | AC15 requires paired arms with comparable scenario metadata rather than unrelated runs. |
| Empty / degenerate | R6 | ✅ covered | AC15 requires emulator evidence and records fleet unavailability rather than silently substituting it. |
| Ordering / stability | R6 | ⛔ dismissed | Measurement records are keyed by arm, run, and scenario; row order has no semantic meaning. |
| Precision / overflow | R6 | ✅ covered | AC15 and AC16 retain raw monotonic values and integer counts without rounding away observations. |
| Idempotency / repetition | R6 | ✅ covered | AC15 retains each repeated round as a distinct record rather than overwriting earlier evidence. |
| Concurrency / effect ordering | R6 | ✅ covered | AC15 requires sequential arms so the compared measurements do not interfere on the network. |
| Boundary values | R7 | ✅ covered | AC17 pins 3.69, 3.70, 3.99, and 4.0 using integer version components. |
| Adjacency / touching | R7 | ✅ covered | AC17 compares each eligible physical device once after identity normalisation and duplicate collapse. |
| Empty / degenerate | R7 | ✅ covered | AC17 requires a named non-gating gap when no eligible device exists. |
| Encoding / representation | R7 | ✅ covered | AC17 fixes comparison to normalised case-insensitive 12-hex identities. |
| Ordering / stability | R7 | ⛔ dismissed | Evidence is keyed per privacy-safe device alias; row order has no semantic effect. |
| Precision / overflow | R7 | ✅ covered | AC17 compares integer major/minor components rather than treating firmware as a decimal. |
| Idempotency / repetition | R8 | ✅ covered | AC8, AC9, and AC14 prove repeated calls retain their named source contracts and fresh completed-call state. |
| Concurrency / effect ordering | R8 | ✅ covered | AC10–AC14 specify concurrency across dual and UDP-only enumeration; mDNS remains per-call. |
| Adjacency / touching | R9 | ✅ covered | AC10 and AC14 define the overlap boundary: active compatible calls share; post-completion calls start fresh. |
| Empty / degenerate | R9 | ✅ covered | AC14 requires empty and failed active-sweep state to disappear at completion. |
| Ordering / stability | R9 | ✅ covered | AC11 requires late subscribers to receive the accepted prefix then suffix in original discovery order. |
| Idempotency / repetition | R9 | ✅ covered | AC10 proves N overlapping callers generate one wire schedule; AC14 proves later calls start a new one. |
| Concurrency / effect ordering | R9 | ✅ covered | AC10–AC13 specify compatibility, fan-out, caller-specific configuration, cancellation, and reaping. |

## Prohibitions (must-NOT)

**Coverage:** 5/5 applicable prohibitions resolved · 0 unresolved

| Prohibition (must-NOT statement) | Requirement | Status | Verification / Reason |
|----------------------------------|-------------|--------|------------------------|
| MUST NOT place live serials, MAC addresses, IP addresses, hostnames, account identifiers, private mappings, or raw discovery output in Phase 13 tests, logs, measurements, documentation, commits, or evidence. | R1–R9 | resolved | verification: test — AC19; use the repository's value-suppressed privacy audit pattern, with the wired-check descriptor located during planning rather than fabricated here. |
| MUST NOT make dual-source discovery the only public enumeration mode, remove `discover_mdns()`, add a `transport=` selector, or let entry-point selection change device routing, retry, tuning, or connectivity semantics. | R8 | resolved | verification: test — AC8, AC9, and AC18; wired-check descriptor deferred until the Phase 13 public-surface tests exist. |
| MUST NOT alter WiFi-measured discovery, request-retry, bandwidth, or animation constants in Phase 13. | R1–R9 | resolved | verification: judgment — AC16 and final-diff review; Phase 14 owns evidence-backed retuning. |
| MUST NOT mark FIND-08 confirmed using emulator data, Thread firmware, ineligible WiFi firmware, or an inferred identity relationship. | R7 | resolved | verification: test — AC17; wired-check descriptor deferred until the Phase 13 evidence validator exists. |
| MUST NOT start more than one compatible UDP broadcast sweep for overlapping `discover()` and `discover_udp()` callers; caller concurrency must not multiply UDP sends or response load. | R9 | resolved | verification: test — AC10; wired-check descriptor deferred until the Phase 13 single-flight negative test and fixtures exist. |

Generic UDP/mDNS spoofing, injection, and hostile-network security concerns remain canon work for `$gsd-secure-phase` and the existing source, serial, address, provenance, and resource-bound validation contracts. This specification does not mint duplicate prohibitions for them.

## Ambiguity Report

| Dimension | Score | Min | Status | Notes |
|-----------|-------|-----|--------|-------|
| Goal Clarity | 0.97 | 0.75 | ✓ | Default, source-specific, anti-herd, liveness, and lookup outcomes are explicit. |
| Boundary Clarity | 0.95 | 0.70 | ✓ | Active UDP sharing is separated from persistent caching, mDNS cache changes, downstream integration, and Phase 14 tuning. |
| Constraint Clarity | 0.90 | 0.65 | ✓ | Compatibility keys, process scope, lifecycle, Python floor, measurement repetitions, privacy, and no-retuning rules are locked. |
| Acceptance Criteria | 0.93 | 0.70 | ✓ | Twenty pass/fail checks cover baseline order, modes, wire load, liveness, cleanup, measurements, identity evidence, and quality gates. |
| **Ambiguity** | **0.06** | **≤0.20** | **✓** | Gate passed after the UDP anti-herd boundary replaced the unsupported persistent-cache assumption. |

Status: ✓ = met minimum, ⚠ = below minimum (planner treats as assumption)

## Interview Log

| Round | Perspective | Question summary | Decision locked |
|-------|-------------|------------------|-----------------|
| 1 | Researcher | Which result is canonical for a dual-advertised device? | The literal first result completing required validation and liveness checks wins; no fixed transport priority. |
| 1 | Researcher | Is the timing comparison evidence or a regression ceiling? | Record the before/after delta without inventing a pass/fail slowdown threshold. |
| 1 | Researcher | What constitutes the pre-merge invariant entry gate? | Retain lower-level tests and add a focused public `discover()` contract layer; both pass before merge work. |
| Edge probe | Completeness | How are the original 29 shape edges resolved? | Explicit empty, duplicate, ordering, repetition, concurrency, timing, version, and evidence rules accepted; measurement/evidence row ordering dismissed with reasons. |
| Prohibition probe | Public API intent | Must dual discovery be mandatory? | No. Add `discover_udp()` beside `discover_mdns()` while `discover()` remains the dual-source default; `find_by_serial()` remains dual. |
| 2 | Failure Analyst | Should repeated discovery calls share persistent cached outcomes? | The spike did not measure a safe TTL. Do not retain completed positive, empty, or failed outcomes. |
| 2 | Failure Analyst | Which overlapping discovery traffic presents the measured denial-of-service risk? | UDP broadcast. Compatible `discover()` and `discover_udp()` callers share one active sweep and active-sweep record prefix. mDNS retains per-call cache semantics. |
| Edge probe | Completeness | What are the new API and UDP-sharing edge rules? | Named APIs retain exact source modes; active overlap shares, late subscribers receive prefix then suffix, cancellation is subscriber-safe, and post-completion calls start fresh. |
| Prohibition probe | Must-NOT completeness | Which bespoke constraints remain after the API reversal? | Keep privacy, explicit source choice, no retuning, evidence integrity, and no overlapping compatible UDP sweeps. |

---

*Phase: 13-merged-discovery*
*Spec created: 2026-08-30*
*Next step: $gsd-discuss-phase 13 — implementation decisions (how to build what is specified above)*
