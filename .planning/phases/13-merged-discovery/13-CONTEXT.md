# Phase 13: Merged Discovery - Context

**Gathered:** 2026-08-30
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 13 makes the default `discover()` path enumerate the hardened UDP and mDNS legs
concurrently, retains explicit UDP-only and mDNS-only enumeration, shares compatible active UDP
sweeps across overlapping callers, verifies mDNS candidates before yielding them, races both legs
for serial lookup, and records the timing and result delta without changing established discovery
or request tuning.

</domain>

<spec_lock>
## Requirements (locked via SPEC.md)

**9 requirements are locked.** See `13-SPEC.md` for full requirements, boundaries, and acceptance
criteria.

Downstream agents MUST read `13-SPEC.md` before planning or implementing. Requirements are not
duplicated here.

**In scope (from SPEC.md):**

- Default concurrent UDP+mDNS `discover()` with streaming serial-keyed first-valid-result merge.
- Public UDP-only `discover_udp()` alongside the existing mDNS-only `discover_mdns()`.
- One active compatible UDP sweep shared across overlapping `discover()` and `discover_udp()`
  callers, including active-sweep replay for late subscribers and deterministic subscriber cleanup.
- A pre-merge public `discover()` invariant layer and before/after measurement harness that pass
  against the broadcast-only baseline.
- Expected mDNS-failure degradation to UDP-only default discovery.
- Direct-response liveness verification for mDNS candidates before default merged discovery yields
  them.
- Dual-source first-valid-result `find_by_serial()` with complete loser cancellation and reaping.
- Repeated paired fleet timing/result measurements, emulator CI wall-time evidence, and
  low-priority eligible-firmware identity evidence.
- Privacy-safe synthetic tests and committed measurements.

**Out of scope (from SPEC.md):**

- A completed-sweep result cache, negative cache, configurable cache TTL, or stale-result replay.
- Sharing or persisting mDNS record state across calls.
- A `transport=` parameter or caller control over routing, retries, connectivity classification,
  or tuning.
- An mDNS path of `find_by_label()`'s own.
- Source selection for `find_by_serial()`, `find_by_ip()`, or `find_by_label()`.
- Home Assistant integration changes.
- Retuning discovery, request-retry, bandwidth, or animation constants.
- Thread commissioning, border-router management, IPv6 multicast mDNS queries, or
  multicast-group rejoin.
- Phase 14 device-class coverage and Thread performance measurements.
- Runtime dependencies, a threading rewrite, or Python 3.11-only concurrency primitives.

</spec_lock>

<decisions>
## Implementation Decisions

### mDNS failure boundary

- **D-01:** Use a stage-aware explicit availability allowlist. A sweep-level network or timeout
  failure ends only the mDNS leg. Candidate-level connection, timeout, malformed-response, or
  identity-mismatch failure drops only that candidate. Do not use a blanket `except Exception`
  degradation path.
- **D-02:** Emit one privacy-safe `DEBUG` event per absorbed mDNS-leg failure. It carries a stable
  stage/reason and exception type only; it must not contain exception text, addresses, identifiers,
  TXT values, raw packets, or other live network data.
- **D-03:** An unexpected programming or invariant error fails fast. Cancel and await the UDP leg
  and all mDNS work, reap every generator/task/connection/socket, then propagate the original
  error without waiting out the normal discovery window.
- **D-04:** Caller cancellation is never classified as mDNS unavailability. It propagates after
  deterministic cleanup.

### mDNS candidate liveness proof

- **D-05:** Classify the candidate using the validated mDNS TXT `p` product ID. For a product the
  registry classifies as a light, send `GetColor` and require a valid correlated `StateColor`. For
  a non-light product, use `EchoRequest`/`EchoResponse`. If `p` classifies a product as a light but
  the device returns `StateUnhandled`, reject that candidate.
- **D-06:** A successful `StateColor` seeds the constructed device's existing state snapshot with
  label, colour, and power. This does not create a volatile-value cache: later `get_color()` and
  `get_power()` calls continue making fresh requests under their existing contracts.
- **D-07:** Verify mDNS candidates with bounded concurrency behind a deterministic internal cap.
  A queued candidate receives only the caller's remaining discovery window; queueing or starting a
  probe never extends the overall deadline.
- **D-08:** Reuse the established request machinery and honour that caller's `device_timeout` and
  `max_retries`, but cap all liveness work by the one existing discovery deadline. Add no Phase 13
  retry schedule or tuning constant.

### Process-wide active UDP fan-out

- **D-09:** Store accepted records once in an append-only active-sweep log. Each subscriber owns an
  independent cursor. The producer never waits for a consumer, and a late subscriber reads the
  accepted prefix followed by later records in original discovery order. Discard the log at sweep
  completion.
- **D-10:** Compatible callers share the same active UDP sweep across the whole process, including
  callers on different event loops or OS threads. — **Reversibility:** costly — narrowing this to
  per-loop sharing would break the locked no-multiplied-sweep contract for multi-loop processes and
  require corresponding public-contract and concurrency-test changes.
- **D-11:** A lazily started library-internal coordinator thread runs an asyncio event loop that owns
  process-wide shared UDP sweeps. Caller loops subscribe through a narrow thread-safe hand-off. The
  coordinator starts on demand and stops when no active sweep or subscriber remains; this is
  orchestration around the asyncio core, not a transport rewrite.
- **D-12:** Every subscriber `aclose()` waits until the coordinator confirms detachment. A non-last
  subscriber then returns without waiting for the sweep. The last subscriber additionally waits
  until the sweep task is cancelled and its UDP endpoint is closed.

### Measurement and evidence workflow

- **D-13:** Store raw measurements as append-only JSONL: one immutable record per arm and round,
  linked by scenario and pair IDs. Retain raw nanosecond elapsed values and integer counts. A
  validator regenerates the human-readable delta summary; derived summaries are not source data.
- **D-14:** Provide one `uv run` script with explicit `baseline-only`, `merged-only`, and `paired`
  modes. The pre-merge entry gate runs `baseline-only`; final fleet and emulator evidence runs
  sequential baseline-then-merged pairs in one invocation.
- **D-15:** Require each fleet run to declare `quiesced`, `not_quiesced`, or `unknown` and record
  stable categorical confounds. Do not refuse a non-clean run, but the validator and summary must
  label non-quiesced or unknown evidence as confounded rather than presenting it as an unqualified
  comparison.
- **D-16:** Committed measurement rows include stable operator-controlled privacy-safe device
  aliases and each alias's contributing source so overlap, deduplication, and source contribution
  can be reconstructed. Resolve live identifiers through the external private mapping and never
  write raw identifiers or that mapping to repository files.

### Planner's Discretion

- The exact bounded mDNS verification concurrency cap, after research against the existing socket,
  fleet-size, and deadline constraints.
- Concrete stable diagnostic reason names beyond the locked stage distinctions.
- Internal coordinator classes, thread-safe bridge primitives, and module placement, provided the
  ownership and synchronous cleanup contracts above remain exact.
- Measurement script and artefact filenames, JSONL field names, and human-readable summary layout.
- Test module placement and test-only schedulers, barriers, spies, and fake clocks.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Locked phase and milestone authority

- `.planning/phases/13-merged-discovery/13-SPEC.md` — the nine locked requirements,
  boundaries, acceptance criteria, edge coverage, and prohibitions. MUST read before planning.
- `.planning/PROJECT.md` — v2.0 milestone scope and key decisions for dual discovery,
  source-specific APIs, single-flight UDP, and dual-source serial lookup.
- `.planning/REQUIREMENTS.md` — authoritative FIND-01 through FIND-05 and FIND-07 through FIND-10
  wording and traceability.
- `.planning/ROADMAP.md` — Phase 13 goal, dependencies, entry gate, and success criteria.
- `.planning/STATE.md` — current milestone position and accumulated Phase 13 entry-gate context.

### Inherited discovery contracts

- `.planning/phases/11-mdns-hardening/11-CONTEXT.md` — private mDNS record boundaries,
  per-call state, address admission, connectivity, and privacy-safe diagnostics.
- `.planning/phases/12-ipv6-discovery-plumbing/12-CONTEXT.md` — family-aware discovery,
  public lookup, cancellation, endpoint cleanup, and cross-platform test decisions.
- `.agents/skills/spike-findings-lifx-async/SKILL.md` — measured reliability constraints,
  real-hardware evidence requirements, and the retained asyncio architecture.
- `.agents/skills/spike-findings-lifx-async/references/discovery.md` — accepted rebroadcast
  schedule, first-wins deduplication, repeated-round evidence, and single-sweep response load.
- `AGENTS.md` — repository coding, privacy, testing, dependency, and commit rules.

### Live implementation and test seams

- `src/lifx/api.py` — current UDP-only `discover()`, mDNS-only `discover_mdns()`, UDP-only
  `find_by_serial()`, construction isolation, and public exports.
- `src/lifx/network/discovery/udp.py` — `_discover_with_packet()`, `discover_devices()`,
  `DiscoveredDevice.create_device()`, validation, deduplication, deadlines, rebroadcast, and cleanup.
- `src/lifx/network/discovery/mdns/discovery.py` — private record stream, TXT `p` parsing,
  invocation-local record cache, and current product-based device construction.
- `src/lifx/network/discovery/mdns/types.py` — internal mDNS record fields including `product_id`.
- `src/lifx/devices/light.py` — `get_color()` response processing, state seeding, label decoding,
  and `StateUnhandled` handling.
- `src/lifx/network/connection.py` — established correlated request/retry machinery and existing
  Echo packet handling.
- `tests/test_api/test_api_discovery.py` — current public discovery and generator-cleanup tests.
- `tests/test_network/test_discovery_rebroadcast.py` — rebroadcast timing, deduplication, and
  consumer-time exclusions.
- `tests/test_network/test_discovery_errors.py` — source/serial validation, invalid-response, and
  discovery failure seams.
- `tests/test_network/test_mdns/` — mDNS parsing, lifecycle, record-cache, and transport contracts.
- `scripts/mdns_probe.py` — existing operator-facing mDNS probe pattern; raw output remains private.

### External protocol and runtime references

- `https://lan.developer.lifx.com/docs/querying-the-device-for-data` — official `GetColor`,
  `GetVersion`, `GetService`, and Echo request/response purposes.
- `https://docs.python.org/3.10/library/asyncio-task.html` — Python 3.10 task cancellation,
  waiting, deadlines, and cleanup semantics.
- `https://docs.python.org/3.10/library/asyncio-eventloop.html` — event-loop ownership and
  thread-safe scheduling boundary.
- `https://docs.python.org/3/library/asyncio-queue.html` — queue blocking and backpressure
  semantics relevant to subscriber fan-out.
- `https://docs.python.org/3.10/library/time.html` — monotonic nanosecond timing contract.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- `IdleDeadline` and `_discover_with_packet()` already own broadcast timing, consumer-time
  exclusion, serial validation, first-wins deduplication, and deterministic endpoint closure.
- `DiscoveredDevice.create_device()` already queries a live device through normal request
  machinery and adopts fetched metadata into the correctly typed instance.
- `_discover_lifx_services()` already yields private validated records from invocation-local state;
  its `product_id`, address, serial, port, and connectivity fields are the merged leg's candidate
  input.
- `Light.get_color()` already decodes `StateColor`, raises on `StateUnhandled`, and updates label and
  existing state fields. The liveness path should reuse that response-processing behaviour rather
  than duplicate decoding rules.
- `DeviceConnection` already supports `EchoRequest`/`EchoResponse`, correlation, retries, and
  cleanup on Python 3.10.
- The preserved discovery spike harness demonstrates repeated-round operation and JSONL evidence
  patterns against real hardware.

### Established Patterns

- Async generators are wrapped with `aclosing()` and cleanup is awaited before return or exception.
- UDP discovery validates before deduplication, streams accepted results, and does not cache a
  completed sweep.
- mDNS record state and rejection aggregates belong to one invocation and never become a shared
  persistent cache.
- Structured diagnostic events suppress raw live values; tracked hardware evidence uses aliases
  from an external operator-controlled mapping.
- Label may be retained as semi-static metadata, while colour and power getters remain fresh
  network reads.
- Runtime code remains stdlib-only and compatible with Python 3.10 through 3.14.

### Integration Points

- `src/lifx/api.py`: split the current public UDP enumerator into `discover_udp()`, orchestrate
  merged legs in `discover()`, race both legs in `find_by_serial()`, and update exports/docstrings.
- `src/lifx/network/discovery/udp.py`: connect the process-wide active-sweep coordinator below
  the public API while preserving `_discover_with_packet()` as the wire-level producer.
- `src/lifx/network/discovery/mdns/discovery.py`: expose the existing private record stream internally to the
  merged orchestrator so liveness happens before device construction and yield.
- `src/lifx/__init__.py`: export `discover_udp` alongside `discover` and `discover_mdns`.
- `tests/test_api/` and `tests/test_network/`: add deterministic leg, fan-out, multi-loop,
  cancellation, failure, liveness, and entry-gate coverage without weakening lower-level suites.
- `scripts/`: add the single mode-driven measurement harness and privacy-safe validator inputs.

</code_context>

<specifics>
## Specific Ideas

- The user selected `GetColor` for advertised light products because its response contains label,
  colour, and power that callers are likely to need immediately. After confirming that mDNS already
  supplies product ID through TXT `p`, they retained `GetColor` and chose Echo only for non-lights.
- A purported light returning `StateUnhandled` is an identity/capability contradiction and must be
  rejected, not silently accepted through the Echo fallback.
- Process-wide means genuinely cross-event-loop, not merely a module-level registry whose asyncio
  objects remain usable only from one loop.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 13-merged-discovery*
*Context gathered: 2026-08-30*
