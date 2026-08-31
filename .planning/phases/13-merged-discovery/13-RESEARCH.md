# Phase 13: Merged Discovery - Research

> **Path amendment (Plan 13-07):** Source paths in this pre-implementation
> research snapshot remain historical. See
> [`13-PATH-AMENDMENT.md`](13-PATH-AMENDMENT.md) for current canonical paths.

**Researched:** 2026-08-30
**Domain:** Python 3.10 asyncio discovery orchestration, cross-thread single-flight fan-out, and privacy-safe measurement
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

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

### the agent's Discretion

- The exact bounded mDNS verification concurrency cap, after research against the existing socket,
  fleet-size, and deadline constraints.
- Concrete stable diagnostic reason names beyond the locked stage distinctions.
- Internal coordinator classes, thread-safe bridge primitives, and module placement, provided the
  ownership and synchronous cleanup contracts above remain exact.
- Measurement script and artefact filenames, JSONL field names, and human-readable summary layout.
- Test module placement and test-only schedulers, barriers, spies, and fake clocks.

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| FIND-01 | `discover()` finds Thread devices without the caller opting in, running a broadcast leg and an mDNS leg concurrently and merging by serial, first wins. | Merge architecture, error boundary, liveness gate, and cleanup pattern below. |
| FIND-02 | `discover()`'s existing contract survives the merge, specifically its overall timeout, its idle timeout resetting on consumer resume, first-wins per-serial dedup, and DoS source and serial validation. The invariant tests are written before the merge, as its entry gate, not after it. | Entry-gate ordering and raw-response sharing seam below. |
| FIND-03 | An mDNS leg that fails or is unavailable degrades `discover()` to today's broadcast-only behaviour rather than ending discovery. `asyncio.TaskGroup` is unavailable regardless (Python 3.11 or later; this library ships 3.10 for LedFx), and its cancel-siblings semantics would be wrong here anyway. | Explicit stage allowlist and manual task supervision below. |
| FIND-04 | An mDNS-sourced device is unicast-verified before it is yielded, so `discover()` never yields a device that is not answering. A border router's SRP registration can outlive the device by up to a 2 hour default lease, and `discover()` has never broken that liveness contract. Verification also closes the mDNS leg's spoofing exposure, since it carries none of the broadcast leg's validation. | Product-directed `GetColor`/Echo proof below. |
| FIND-05 | `find_by_serial()` races a broadcast leg and an mDNS leg, first hit wins, and the losing leg is cancelled and reaped so no task or socket leaks. Both legs are required: broadcast covers WiFi devices whose firmware does not advertise over mDNS, mDNS covers Thread devices with no IPv4 address to broadcast to. | First-valid-match race state machine below. |
| FIND-07 | The timing change merged discovery imposes on existing callers is a measured before-and-after number against the fleet, not an assumption. Emulator CI wall time is part of that measurement. | Append-only paired measurement workflow below. |
| FIND-08 | The mDNS TXT `id` is confirmed to match the broadcast serial for firmware 3.70 to 3.99 WiFi devices, the only population where the two could diverge. Low priority and not a gate: Thread requires firmware 4 or later, and `Device.get_mac_address()` fires only on `version_major == 3 and version_minor >= 70`, so a Thread device structurally cannot exhibit the off-by-one quirk. | Boundary eligibility and privacy-safe observation below. |
| FIND-09 | Source-specific enumeration remains public: `discover_udp()` provides UDP-only discovery, the existing `discover_mdns()` remains mDNS-only, and `discover()` is the default dual-source path. `find_by_serial()` remains a dual-source lookup without a source selector. | Public API and entry-gate migration order below. |
| FIND-10 | Compatible overlapping `discover()` and `discover_udp()` callers share one active UDP broadcast sweep and its already-seen results, so N overlapping callers produce the same wire schedule and response load as one caller. Sharing is limited to the active sweep: completed positive, empty, and failed outcomes are not retained behind an unmeasured cache lifetime. | Process-wide coordinator and lifecycle tests below. |
</phase_requirements>

## Summary

Phase 13 should be planned as three separable mechanisms: a process-wide raw UDP sweep coordinator, a caller-loop merged stream, and a bounded mDNS liveness verifier. The coordinator must sit below `discover_devices()`: that wrapper embeds `device_timeout` and `max_retries` into each `DiscoveredDevice`, while the locked compatibility key deliberately excludes those subscriber-specific values. Share accepted raw `DiscoveryResponse` records, then construct each subscriber's `DiscoveredDevice` with its own settings. The existing raw sweep already owns source/serial validation, first-wins deduplication, rebroadcast timing, consumer-resume idle reset, and endpoint closure, so it should remain the only UDP producer. [VERIFIED: src/lifx/network/discovery.py:217-621] [VERIFIED: src/lifx/network/discovery.py:624-711]

Default merging and serial lookup need explicit Python 3.10 task supervision. One leg finishing empty must not cancel the other; an expected mDNS failure ends only that leg; an unexpected error or caller cancellation cancels and awaits every task and closes every generator/connection. `asyncio.run_coroutine_threadsafe()` and `loop.call_soon_threadsafe()` are the supported cross-thread boundaries, while asyncio queues themselves are not thread-safe. [CITED: https://docs.python.org/3.10/library/asyncio-task.html] [CITED: https://docs.python.org/3.10/library/asyncio-dev.html] [CITED: https://docs.python.org/3.10/library/asyncio-eventloop.html]

The principal live-code gap is D-06: a newly constructed `Light` has `_state = None`, and `adopt_cached_metadata()` intentionally excludes live state; full `LightState` is only built later by `_initialize_state()`. The plan therefore needs an explicit internal adoption seam for the verified `StateColor` payload, rather than assuming current construction can seed colour and power. It must preserve fresh-network semantics for later `get_color()` and `get_power()` calls. [VERIFIED: src/lifx/devices/base.py:546-586] [VERIFIED: src/lifx/devices/light.py:1041-1088]

**Primary recommendation:** Add a production-neutral UDP-only API and invariant/measurement entry gate first; then implement raw-response single-flight, the verified merged stream, and the serial race as independently testable layers before collecting paired evidence.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| UDP sweep timing, validation, and socket lifecycle | Network layer | — | `_discover_with_packet()` already owns these invariants and must remain the sole producer. [VERIFIED: src/lifx/network/discovery.py:217-621] |
| Process-wide active-sweep ownership and replay | Network orchestration | Caller event loop | A coordinator-loop registry owns sweep state; caller loops own only subscription delivery queues. [CITED: https://docs.python.org/3.10/library/asyncio-eventloop.html] |
| mDNS record assembly | mDNS network layer | — | Records and cache state are currently invocation-local and must remain so. [VERIFIED: src/lifx/network/mdns/discovery.py:1102-1188] |
| Candidate liveness and typed construction | API/network boundary | Device layer | Verification uses `DeviceConnection`; final class selection uses the product registry's classifier. [VERIFIED: src/lifx/network/connection.py:1253-1295] [VERIFIED: src/lifx/devices/detection.py:21-64] |
| Serial-keyed streaming merge and public APIs | High-level API | Network orchestration | `discover()`, `discover_udp()`, `discover_mdns()`, and `find_by_serial()` are API contracts. [VERIFIED: src/lifx/api.py:775-966] |
| Measurement and privacy-safe evidence | Operator script | Test/CI fixtures | Raw observations belong outside runtime code and must use aliases rather than live identifiers. [VERIFIED: AGENTS.md:17-38] |

## Project Constraints (from AGENTS.md)

- Use Australian English and keep imports at file tops. [VERIFIED: user-provided AGENTS instructions] Preserve full strict typing. [VERIFIED: AGENTS.md:267-274]
- Support Python `3.10`, `3.11`, `3.12`, `3.13`, and `3.14`; retain built-in `asyncio` and zero runtime dependencies. The exact project values are `requires-python = ">=3.10"` and `dependencies = []`. [VERIFIED: pyproject.toml:1-7]
- Use `uv` exclusively: dependency sync is `uv sync`, the full test gate is `uv run --frozen pytest`, formatting/linting use Ruff, and strict typing uses Pyright. [VERIFIED: AGENTS.md:45-86]
- Do not change generated protocol files manually; change the official input/generator when protocol generation is actually required. Phase 13 should not require generated-code edits. [VERIFIED: AGENTS.md:92-106] [VERIFIED: AGENTS.md:273-306]
- Never commit live device serials/MACs, IP addresses, local hostnames, account names, raw discovery output, or the private pseudonym mapping. Tests use clearly synthetic identifiers; staged evidence must be inspected for leakage before commit. [VERIFIED: AGENTS.md:17-38]
- Do not edit `docs/changelog.md`; it is release-generated. User-visible fields must be strings, never bytes. [VERIFIED: AGENTS.md:439-440]
- Do not retune discovery, request, bandwidth, or animation constants in this phase. [VERIFIED: .planning/phases/13-merged-discovery/13-SPEC.md:93-104]
- Conventional commits must use `git commit -S -s`; GSD phase/plan numbers are not commit scopes. [VERIFIED: AGENTS.md:40-49]
- Do not ignore dirty files or failing tests; diagnose and resolve them within the authorised scope or ask the operator when unrelated ownership prevents a safe fix. [VERIFIED: user-provided AGENTS instructions]

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python standard-library `asyncio` | Python 3.10 contract | Caller-loop task supervision, coordinator-loop sweep task, async generators | Already the runtime architecture; Python 3.10 rules out `TaskGroup`. [VERIFIED: pyproject.toml:1-7] |
| Python standard-library `threading` | Python 3.10 contract | Lazy coordinator thread, short synchronous lifecycle lock/event | Required by locked D-10/D-11; do not move transport I/O to blocking threads. |
| Python standard-library `concurrent.futures` bridge | Python 3.10 contract | Await coordinator submissions from caller loops | `run_coroutine_threadsafe()` returns a concurrent future; `asyncio.wrap_future()` makes it awaitable. [CITED: https://docs.python.org/3.10/library/asyncio-task.html] [CITED: https://docs.python.org/3.10/library/asyncio-future.html] |
| Existing `DeviceConnection` | In-repo | Correlated GetColor/Echo requests, retries, receiver cleanup | It already allocates sequence IDs, correlates `(source, sequence, serial)`, enforces a monotonic deadline, and removes request queues in `finally`. [VERIFIED: src/lifx/network/connection.py:718-980] |
| Existing pytest suite | pytest 9.1.1 in audited environment | Deterministic lifecycle, merge, error, and platform tests | Existing configuration uses asyncio auto mode and project timeout/retry rules. [VERIFIED: pyproject.toml:107-135] |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `asyncio.Queue(maxsize=0)` | Python 3.10 contract | Per-subscriber caller-loop delivery and per-call merge events | An unbounded queue makes `put_nowait()` non-blocking; asyncio queues stay confined to their owning loop. [CITED: https://docs.python.org/3.10/library/asyncio-queue.html] |
| `time.monotonic_ns()` | Python 3.10 contract | Raw elapsed evidence | It returns integer nanoseconds from a monotonic clock; only differences are meaningful. [CITED: https://docs.python.org/3.10/library/time.html] |
| `json` | Python 3.10 contract | Append-only JSONL rows and validator input | Runtime dependency-free and sufficient for immutable measurement records. |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Coordinator loop + thread-safe hand-off | One registry per caller loop | Violates process-wide sharing across OS threads and multiplies wire sweeps. |
| Explicit task state machine | `asyncio.gather()` alone | `gather()` does not model “one leg ended empty, keep waiting for the other” or stage-specific failure disposition clearly. [CITED: https://docs.python.org/3.10/library/asyncio-task.html] |
| Explicit task state machine | `asyncio.TaskGroup` | Python 3.11-only and its sibling-cancellation policy does not match expected mDNS degradation. [CITED: https://docs.python.org/3.11/library/asyncio-task.html] |
| Caller-loop queue delivery via `call_soon_threadsafe()` | Access one asyncio queue from both threads | Asyncio objects are generally not thread-safe. [CITED: https://docs.python.org/3.10/library/asyncio-dev.html] |
| Existing request machinery | Raw one-off datagram probe | Would duplicate correlation, retry, deadline, IPv4/IPv6, and cleanup behaviour. |

**Installation:** No package installation. Phase 13 must retain the exact zero-runtime-dependency declaration `dependencies = []`. [VERIFIED: pyproject.toml:5-7]

## Package Legitimacy Audit

Not applicable: the recommended stack adds no external package.

## Architecture Patterns

### System Architecture Diagram

```text
discover()/discover_udp() on any caller loop
        |
        | subscribe(key, caller loop, per-caller device settings)
        v
thread-safe bridge --> lazy coordinator thread / asyncio loop
                          |
                          +--> active sweep registry keyed by
                          |    (broadcast_address, port, timeout,
                          |     max_response_time, idle_timeout_multiplier)
                          |          |
                          |          +--> one raw _discover_with_packet producer
                          |          +--> append-only accepted-response log
                          |          +--> ordered prefix + suffix fan-out
                          |
                          +--> no completed entry; stop loop when idle

discover() caller loop
   |                         |
   | UDP subscription pump   | fresh per-call mDNS record sweep
   |                         v
   |                  bounded liveness workers
   |                  GetColor -> StateColor (light)
   |                  Echo -> matching EchoResponse (non-light)
   |                         |
   +-------------> serial-keyed first-valid event merge
                                |
                         construct/yield Device
                                |
                    finally cancel, await, aclose all
```

The compatibility key values are exactly `broadcast_address`, `port`, `timeout`, `max_response_time`, and `idle_timeout_multiplier`; `device_timeout` and `max_retries` remain subscriber-specific. [VERIFIED: .planning/phases/13-merged-discovery/13-SPEC.md:61-64]

### Recommended Project Structure

```text
src/lifx/
├── api.py                         # public source-specific APIs and merged/lookup state machines
├── network/
│   ├── discovery.py               # raw UDP producer plus process-wide subscription facade
│   ├── discovery_coordinator.py   # recommended coordinator ownership/lifecycle module [ASSUMED]
│   ├── connection.py              # existing correlated liveness requests
│   └── mdns/discovery.py          # private per-call record stream, no shared cache
└── devices/
    └── light.py                   # central StateColor decoding/adoption seam
tests/
├── test_api/test_api_discovery.py
├── test_network/test_discovery_coordinator.py  # recommended deterministic lifecycle coverage [ASSUMED]
└── test_network/test_mdns/test_liveness.py      # recommended candidate verification coverage [ASSUMED]
scripts/
└── measure_merged_discovery.py                  # recommended one-script evidence entry point [ASSUMED]
```

### Pattern 1: Share the validated raw UDP seam

**What:** Refactor the current wrapper so `_discover_with_packet()` continues producing accepted `DiscoveryResponse` records, but an active coordinator sweep consumes that raw generator once and distributes those records. Each caller then applies its own `device_timeout` and `max_retries` while constructing `DiscoveredDevice`. [VERIFIED: src/lifx/network/discovery.py:624-711]

**Why:** Sharing `DiscoveredDevice` objects would make the first subscriber's settings observable by all later compatible subscribers even though those settings are not in the sweep key.

**Ordering contract:** On the coordinator loop, append a record to the active log, then synchronously schedule that same record to every attached caller loop with `call_soon_threadsafe(queue.put_nowait, record)`. Subscription registration schedules the complete current prefix before adding the subscriber to future delivery. Because registration and append both execute serially on the one coordinator loop, the subscriber sees prefix then suffix in discovery order. [CITED: https://docs.python.org/3.10/library/asyncio-eventloop.html]

### Pattern 2: Idempotent subscription lifecycle

**What:** Allocate a subscription token before cross-thread registration; registration, detach, producer completion, delivery-loop closure, and caller cancellation all converge on one idempotent detach operation. Await the concurrent future with `asyncio.wrap_future()` so the caller loop never blocks. [CITED: https://docs.python.org/3.10/library/asyncio-future.html]

**Required terminal states:**

1. Non-last detach: acknowledge after removal; leave sweep running.
2. Last detach: cancel and await the producer; acknowledge only after `_discover_with_packet()` has exited and its endpoint context has closed.
3. Producer completion/error: schedule terminal delivery, remove the active registry entry, discard the active log, and allow current subscribers to drain their caller-loop queues.
4. Caller loop already closed: treat `call_soon_threadsafe()` failure as subscriber detachment, not coordinator failure.
5. Coordinator idle: stop only after the registry and subscriber set are empty; run `shutdown_asyncgens()` before closing the manually managed loop. [CITED: https://docs.python.org/3.10/library/asyncio-eventloop.html]

### Pattern 3: Per-call merged event state machine

**What:** Start an independent UDP subscription pump and mDNS pump on the caller loop. Both enqueue typed events into one unbounded local queue: valid candidate, leg done, absorbed mDNS failure, or unexpected error. The merger yields the first valid candidate for each normalised serial and continues until both legs are done. It does not wait for device construction before continuing to drain source pumps.

**Error rules:** Sweep-level `LifxNetworkError` or `LifxTimeoutError` ends only mDNS; candidate-level `LifxConnectionError`, `LifxTimeoutError`, `LifxProtocolError`, `LifxUnsupportedCommandError`, or explicit identity/response mismatch drops that candidate. `CancelledError` is a `BaseException` and must be re-raised after cleanup; any other exception triggers fail-fast cancellation/reaping and original-error propagation. The exact exception classes are `LifxTimeoutError`, `LifxProtocolError`, `LifxConnectionError`, `LifxNetworkError`, and `LifxUnsupportedCommandError`. [VERIFIED: src/lifx/exceptions.py:6-88] [CITED: https://docs.python.org/3.10/library/asyncio-task.html]

**Diagnostic recommendation:** Use stable value-suppressed reason names such as `sweep_open_network`, `sweep_send_network`, `sweep_receive_network`, `sweep_address_followup_network`, `sweep_timeout`, `candidate_connect`, `candidate_timeout`, `candidate_protocol`, `candidate_unsupported`, `candidate_identity`, and `candidate_response`. Plan 13-03 resolves the sweep seam with private `_MdnsSweepFailure(stage, reason, error_type)` delivery from the live `_discover_lifx_services_sweep()` open/send/receive/follow-up catch boundaries. Because `MdnsTransport` also logs `str(error)` and send destinations before raising, the merged sink path constructs it with one private detail-logging flag disabled; the no-sink default retains existing standalone transport/sweep logs. The catch invokes the sink exactly once, and Plan 13-04 routes that typed event through the merger to emit the one D-02 DEBUG diagnostic. Tests must exercise the real transport catches before any result and after a partial result, and assert that merged logs contain stage/reason/exception type but no exception text, target, destination, or network/device fields. Ordinary receive timeout used by the existing retransmission/idle/overall-deadline state machine remains clean completion rather than a failure diagnostic.

### Pattern 4: Product-directed mDNS liveness

**What:** Consume the private `_LifxServiceRecord`, classify `product_id` through `get_product()` plus `get_device_class_for_product()`, and run one direct request against its validated address/port/serial. The classifier's order is Ceiling, Matrix, MultiZone, Infrared, HEV, unsupported relay/button-only, then `Light`; using only `has_color` would incorrectly exclude brightness-only or white-temperature lights. [VERIFIED: src/lifx/devices/detection.py:21-64] [VERIFIED: src/lifx/products/registry.py:39-112]

For a light, send the exact packet `GetColor` (`PKT_TYPE = 101`, `STATE_TYPE = 107`) and accept only `StateColor` (`PKT_TYPE = 107`) carrying the exact fields `color`, `power`, and `label`; `StateUnhandled` is exact packet type `223` and rejects the candidate with no Echo fallback. [VERIFIED: src/lifx/protocol/packets.py:527-539] [VERIFIED: src/lifx/protocol/packets.py:768-787] [VERIFIED: src/lifx/protocol/packets.py:448-461]

For a non-light, send `EchoRequest` exact packet type `58` with a `64`-byte payload and require `EchoResponse` exact packet type `59` with the identical payload. [VERIFIED: src/lifx/protocol/packets.py:47-78] [CITED: https://lan.developer.lifx.com/docs/querying-the-device-for-data]

Use a single discovery deadline created before queueing. At probe start compute remaining time and pass `min(device_timeout, remaining)` into the existing request machinery; never grant a fresh full timeout after queueing. Always close the temporary `DeviceConnection` in `finally`. The connection already owns retry scheduling and correlation; no new probe retry constant is warranted. [VERIFIED: src/lifx/network/connection.py:718-980]

**Selected cap:** `16` concurrent liveness probes `[RESOLVED by Plan 13-03]`. This bounds sockets/receiver tasks while allowing a roughly 73-device fleet to verify in about five healthy batches. Make it one private named constant, patchable in tests, and collect specific concurrency/deadline coverage plus fleet context for the selected value.

**D-06 implementation seam:** Extract StateColor decoding/adoption from `Light.get_color()` into one private helper used both by normal `get_color()` and liveness construction. Since the newly constructed object has no full `_state`, attach a private, read-only discovery snapshot containing decoded label/colour/power, seed `_label`, and update `_state` only when it exists. Do not make `get_color()` or `get_power()` consult this snapshot; their next call still sends a request. This recommendation resolves the observed live-code mismatch without creating a volatile-value cache. [VERIFIED: src/lifx/devices/base.py:546-586] [VERIFIED: src/lifx/devices/light.py:121-186]

### Pattern 5: `find_by_serial()` races matches, not leg completion

**What:** Normalise the serial once, start a UDP raw-response scan and verified mDNS scan under the caller's one timeout, and enqueue only an exact valid match or leg-done/error event. A no-match completion from one leg does not end the other. The first matching event accepted by the caller-loop queue wins; there is no UDP/mDNS priority. Before constructing or returning the final device, cancel and await the losing task and `aclose()` both generators. [VERIFIED: src/lifx/api.py:903-966] [VERIFIED: .planning/phases/13-merged-discovery/13-SPEC.md:41-44]

### Pattern 6: Entry-gate-first measurement migration

**What:** In the first production-neutral wave, add `discover_udp()` as the existing broadcast behaviour, make the still-UDP-only `discover()` delegate to it, add public invariant tests, and add the one measurement script. The baseline arm can then call `discover_udp()` both before and after the merge; later changing `discover()` to merged behaviour cannot contaminate baseline measurement.

The script should append one JSON object per arm/round with scenario ID, pair ID, round, exact arm (`baseline` or `merged`), exact environment (`fleet` or `emulator`), exact quiescence (`quiesced`, `not_quiesced`, or `unknown`), categorical confounds, total elapsed nanoseconds, nullable first-result nanoseconds, integer unique count, and per-alias source contribution. Field names and artefact paths are recommendations `[ASSUMED]`; the locked values above are copied from CONTEXT.md.

Run `paired` sequentially baseline then merged, not concurrently. Validate arm completeness and comparable scenario metadata, then regenerate the human-readable delta summary from JSONL. Retain raw integer nanoseconds and counts. The existing spike conventions support repeated, quiesced, append-only JSONL observations, but its historical raw discovery data must not be copied because Phase 13 evidence requires operator-controlled aliases. [VERIFIED: .planning/spikes/CONVENTIONS.md:8-32] [VERIFIED: AGENTS.md:17-38]

For FIND-08, observe only WiFi devices whose exact firmware tuple satisfies major `3` and minor `70` through `99`, compare the raw mDNS identity and UDP serial locally, then write only alias/match outcome. Add synthetic boundary tests for `(3, 69)`, `(3, 70)`, `(3, 99)`, `(4, 0)`, and an empty-eligible-population non-gating record. These exact eligibility values come from the locked requirement and the existing MAC rule `version_major == 3 and version_minor >= 70`. [VERIFIED: .planning/REQUIREMENTS.md:137-141] [VERIFIED: AGENTS.md:186-191]

### Anti-Patterns to Avoid

- **Sharing `DiscoveredDevice`:** leaks first-subscriber request settings; share raw validated responses instead.
- **Per-loop active registries:** fail D-10 when callers use separate OS threads/event loops.
- **Cross-thread asyncio queue access:** asyncio queues are not thread-safe; schedule delivery onto the owning loop. [CITED: https://docs.python.org/3.10/library/asyncio-queue.html]
- **Backpressured fan-out:** `await queue.put()` on a bounded subscriber queue lets a slow consumer delay the producer; use unbounded caller-loop queues and `put_nowait()`.
- **`asyncio.to_thread(queue.get)`:** cancellation can leave a blocked worker thread after the async task is gone.
- **Completed or failed sweep retention:** any registry entry after terminal delivery becomes the prohibited cache.
- **Blanket mDNS `except Exception`:** masks programming defects and can misclassify cancellation.
- **Fresh probe timeouts after queueing:** extend discovery beyond the caller's original deadline.
- **`has_color` as light classification:** misses non-colour classes represented by `Light`.
- **Echo payload-only acceptance:** require both correlated response type and exact payload.
- **Constructing a serial winner before loser cleanup:** allows background packets/tasks to survive the returned lookup.
- **Concurrent baseline/merged arms:** changes network load and invalidates the comparison.
- **Raw identifiers in fixtures/evidence:** a later redaction commit does not remove secrets from history. [VERIFIED: AGENTS.md:17-38]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Request correlation/retry | A probe-specific datagram client | `DeviceConnection.request()` | Existing source/sequence/serial routing, hard deadline, retries, IPv4/IPv6, and cleanup are already tested. [VERIFIED: src/lifx/network/connection.py:718-980] |
| UDP timing and validation | A second broadcast loop in the coordinator | `_discover_with_packet()` | Preserves source/serial validation, rebroadcast, idle reset, dedup, and endpoint ownership. [VERIFIED: src/lifx/network/discovery.py:217-621] |
| Product-to-device type logic | Capability predicates in merged discovery | `get_device_class_for_product()` | One ordered source of truth already covers all supported device classes. [VERIFIED: src/lifx/devices/detection.py:21-64] |
| Serial parsing | String stripping/comparison variants | Existing `Serial` and current API normalisation seam | Prevents distinct normalisation rules across source legs. [VERIFIED: src/lifx/protocol/models.py:50-133] |
| Thread-to-loop bridge | Polling or shared mutable asyncio primitives | `run_coroutine_threadsafe`, `call_soon_threadsafe`, `wrap_future` | These are the documented Python 3.10 boundaries. [CITED: https://docs.python.org/3.10/library/asyncio-task.html] [CITED: https://docs.python.org/3.10/library/asyncio-eventloop.html] |
| Measurement timing | Wall-clock subtraction or rounded-only summaries | `time.monotonic_ns()` plus append-only JSONL | Wall-clock changes do not affect elapsed values; raw integer observations remain regenerable. [CITED: https://docs.python.org/3.10/library/time.html] |

**Key insight:** Phase 13 is orchestration around proven primitives. Reimplementing transport, request, identity, or type-classification logic would create a second source of truth precisely where regression risk is highest.

## Common Pitfalls

### Pitfall 1: Subscriber registration races cancellation

**What goes wrong:** A caller is cancelled after submitting registration but before receiving its token; the coordinator retains a ghost subscriber and sweep.

**How to avoid:** Allocate the token first, make registration/detach idempotent, and always submit/await best-effort detach in the generator's `finally`.

**Warning signs:** Coordinator thread remains alive after every caller has closed, or a later test unexpectedly joins an old sweep.

### Pitfall 2: Terminal delivery overtakes replay

**What goes wrong:** A late subscriber sees done/error before its accepted prefix, losing devices.

**How to avoid:** Schedule prefix records, register suffix delivery, then schedule terminal state from the same coordinator-loop serialisation point. Test a subscriber joining immediately before producer completion.

**Warning signs:** Late-subscriber counts vary with scheduling while producer counts remain stable.

### Pitfall 3: Availability handling becomes fail-silent

**What goes wrong:** An assertion, decoding bug, or unexpected lifecycle error is treated as “mDNS unavailable,” so default discovery silently omits Thread devices.

**How to avoid:** Use the explicit expected exception allowlist and fail fast for everything else; never include exception text in absorbed diagnostics.

**Warning signs:** Unexpected mocked `RuntimeError` produces UDP results instead of raising promptly.

### Pitfall 4: Liveness cap does not bound the deadline

**What goes wrong:** Queued candidates each receive a fresh request timeout and the call lasts verification-cap batches beyond the discovery deadline.

**How to avoid:** One monotonic deadline covers record sweep, queue wait, every retry, and construction. Workers skip candidates with no remaining time.

**Warning signs:** Test duration grows linearly with candidate count divided by the cap after the source sweep deadline.

### Pitfall 5: Liveness creates a stale volatile cache

**What goes wrong:** A later `get_color()` returns discovery-time values without network I/O.

**How to avoid:** Treat the verified StateColor as construction provenance/snapshot only; normal volatile getters retain fresh requests. Add a request-spy regression test.

**Warning signs:** `get_color()` or `get_power()` call count becomes zero after mDNS discovery.

### Pitfall 6: Cross-platform lifecycle passes only on macOS

**What goes wrong:** Tests depend on one loop policy, fixed sleeps, or implicit thread shutdown and hang on Windows.

**How to avoid:** Use `threading.Barrier`/`Event` and fake producer gates, create separate `asyncio.run()` loops in real OS threads, join with bounds, and assert coordinator/sockets/tasks terminate. The CI matrix's exact OS values are `ubuntu-latest`, `macos-latest`, and `windows-latest`, across Python `3.10`–`3.14`. [VERIFIED: pyproject.toml:1-7] [VERIFIED: .github/workflows/ci.yml:150-201]

**Warning signs:** Tests need arbitrary sleeps or leave non-daemon threads/processes at interpreter shutdown.

### Pitfall 7: Evidence is technically complete but incomparable

**What goes wrong:** Missing arms, different fleet state, non-quiesced traffic, or aliases without source contribution are summarised as a clean performance delta.

**How to avoid:** Validator rejects missing pair structure and labels `not_quiesced`/`unknown` rows as confounded. Preserve raw rows and regenerate summary.

**Warning signs:** Summary contains a delta that cannot be traced to exactly two immutable rows.

## Regression Invariants and Test Strategy

Nyquist validation is explicitly disabled (`"nyquist_validation": false`), so the formal Validation Architecture section is intentionally omitted. [VERIFIED: .planning/config.json:18-23]

Plan tests in this order:

1. **Entry gate, before merged production behaviour:** freeze public signature/defaults, streaming-before-completion, first-wins serial dedup, overall timeout, consumer-body exclusion from idle timeout, source/serial validation, endpoint closure on exhaustion/`aclose()`/cancellation/error, and broadcast-only output equivalence. The existing API and lower-level suites provide the starting seams. [VERIFIED: tests/test_api/test_api_discovery.py:1-732] [VERIFIED: tests/test_network/test_discovery_rebroadcast.py:1-330] [VERIFIED: tests/test_network/test_discovery_errors.py:1-520]
2. **Coordinator deterministic unit tests:** compatible overlap produces one producer schedule; incompatible key produces two; late subscriber receives prefix then suffix; slow subscriber cannot stall producer; non-last close returns while sweep continues; last close waits producer cancellation/endpoint close; completion/empty/error is not reused; cross-loop callers in two OS threads share; caller-loop closure does not kill coordinator; registration-cancellation leaves no ghost.
3. **Merged-stream tests:** UDP-first, mDNS-first, simultaneous deterministic enqueue order, overlap dedup, one leg empty, expected mDNS sweep failure, expected candidate drop, unexpected error fail-fast, caller cancellation, consumer early close, and source contribution metadata.
4. **Liveness tests:** every supported light-classification branch uses GetColor; non-light uses Echo; valid type but wrong serial/source/sequence is rejected by request correlation; wrong Echo payload rejected; StateUnhandled rejects light; malformed response drops only candidate; cap never exceeded; queue time consumes deadline; temporary connection closes on every outcome; later volatile getters still send.
5. **Serial-race tests:** each source wins, no-match leg doesn't terminate the other, expected mDNS failure permits UDP, simultaneous first-completion ordering, loser cancelled/awaited before construction, and caller cancellation closes both.
6. **Evidence tests:** JSONL append semantics, schema validation, paired ordering baseline then merged, raw nanoseconds/counts, quiescence/confound labelling, no raw identifier fields, alias/source reconstruction, firmware boundary eligibility, and empty eligible population.
7. **Full cross-platform gate:** `uv run --frozen pytest`, `uv run ruff format --check .`, `uv run ruff check .`, and `uv run pyright`. [VERIFIED: AGENTS.md:64-86]

The focused live baseline command `uv run --frozen pytest -o addopts='' tests/test_api/test_api_discovery.py tests/test_network/test_discovery_rebroadcast.py tests/test_network/test_discovery_errors.py -q` passed `84` tests in `27.45s` during research. This confirms the current UDP/API invariant seams are green before Phase 13 production changes; it is not a substitute for the eventual full suite or cross-platform matrix. [VERIFIED: local test run 2026-08-30]

## Code Examples

Verified patterns from official sources:

### Await coordinator work without blocking the caller loop

```python
# Source: Python 3.10 asyncio task/future documentation
submitted = asyncio.run_coroutine_threadsafe(register(subscription), coordinator_loop)
registration = await asyncio.wrap_future(submitted)
```

`run_coroutine_threadsafe()` is for submission from another OS thread and returns a `concurrent.futures.Future`; `wrap_future()` adapts it to the caller loop. [CITED: https://docs.python.org/3.10/library/asyncio-task.html] [CITED: https://docs.python.org/3.10/library/asyncio-future.html]

### Python 3.10-safe cancellation and reaping

```python
# Source: Python 3.10 asyncio task documentation
tasks = {asyncio.create_task(run_udp()), asyncio.create_task(run_mdns())}
try:
    # Consume typed events until both legs finish or an error must propagate.
    ...
finally:
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
```

Cancellation should be performed explicitly and cancelled tasks awaited; `CancelledError` should normally be propagated. [CITED: https://docs.python.org/3.10/library/asyncio-task.html]

### One deadline for queued liveness work

```python
# Source: existing DeviceConnection request API and Python monotonic clock
remaining = discovery_deadline - time.monotonic()
if remaining <= 0:
    return None
response = await connection.request(packet, timeout=min(device_timeout, remaining))
```

The existing request call accepts a per-call timeout and internally enforces a hard monotonic deadline and retry schedule. [VERIFIED: src/lifx/network/connection.py:718-980] [VERIFIED: src/lifx/network/connection.py:1253-1295]

## State of the Art

| Old Approach | Current Phase 13 Approach | Impact |
|--------------|---------------------------|--------|
| Public `discover()` runs UDP only. [VERIFIED: src/lifx/api.py:775-835] | Concurrent UDP plus verified mDNS, serial first-valid merge. | Thread devices appear by default while source-specific enumeration remains. |
| Every UDP caller starts a sweep. [VERIFIED: src/lifx/network/discovery.py:624-711] | One compatible active raw sweep with ordered replay. | Overlap does not multiply broadcast traffic; completed calls are never cached. |
| `discover_mdns()` constructs from advertisements without a direct liveness exchange. [VERIFIED: src/lifx/network/mdns/discovery.py:1134-1188] | Default merged path verifies each candidate before yielding. | Stale/spoofed advertisements do not enter the default stream. Explicit `discover_mdns()` remains source-level enumeration. |
| `find_by_serial()` scans UDP only. [VERIFIED: src/lifx/api.py:903-966] | Race UDP and verified mDNS; first valid match wins after loser cleanup. | WiFi broadcast and IPv6-only Thread are both covered. |

**Deprecated/outdated:** Do not introduce `transport=` source selectors, shared mDNS record state, completed-result caches, Phase 13 tuning constants, Python 3.11 `TaskGroup`, or new runtime dependencies; all are explicitly out of scope. [VERIFIED: .planning/phases/13-merged-discovery/13-SPEC.md:93-104]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Use `16` concurrent mDNS liveness probes. [RESOLVED by Plan 13-03] | Architecture Pattern 4 | Deterministic cap/deadline tests and recorded fleet context verify the selected planner-discretion value without adding a retry or timing constant. |
| A2 | Place coordinator code in `src/lifx/network/discovery_coordinator.py` and the harness in `scripts/measure_merged_discovery.py`. [ASSUMED] | Recommended Project Structure | File placement may conflict with planner decomposition, but does not alter behaviour. |
| A3 | Use the Plan 13-03 bounded diagnostic reason names and the proposed JSONL field names. [RESOLVED for diagnostics; ASSUMED for JSONL names] | Patterns 3 and 6 | The live sweep catch and merger tests pin diagnostic categories; evidence validation pins JSONL names before rows are committed. |

## Open Questions (RESOLVED)

1. **RESOLVED — How should the verified StateColor snapshot be represented before full state initialisation?**
   - What we know: new devices have `_state = None`; only `_label` exists, and `adopt_cached_metadata()` excludes live state. [VERIFIED: src/lifx/devices/base.py:546-586]
   - Selected disposition: Plan 13-03 creates a private immutable `_DiscoveryLightSnapshot` and one `_adopt_state_color()` helper, seeds `_label`, updates full `_state` only when present, and proves normal volatile getters still perform I/O. This fulfils D-06 without public cache semantics or a partial `LightState`.

2. **RESOLVED — What exact liveness concurrency cap is supported by the real fleet?**
   - What we know: the target fleet is roughly 73 devices and the locked contract requires a deterministic cap without new retry/deadline tuning. [VERIFIED: .planning/phases/13-merged-discovery/13-SPEC.md:131-134]
   - Selected disposition: Plan 13-03 fixes the private, test-patchable cap at `16`, proves observed concurrency never exceeds it and queue time consumes the original deadline, and Plan 13-06 records the cap in fleet context. This is a planner-discretion implementation choice, not a new retry or timing schedule.

3. **RESOLVED — Is an eligible firmware 3.70–3.99 WiFi device present during evidence collection?**
   - What we know: FIND-08 is low-priority and non-gating. [VERIFIED: .planning/REQUIREMENTS.md:137-141]
   - Selected disposition: Plan 13-06 Task 2 keeps inventory operator-gated. Eligible physical WiFi hardware records privacy-safe match/mismatch evidence; when no eligible hardware exists, the task appends the named non-gating `no_eligible_find08_population` gap. Emulator, Thread, and ineligible firmware observations never substitute for confirmation.

4. **RESOLVED — How does emulator-mode merged discovery avoid the ambient mDNS multicast destination?**
   - What we know: passing loopback `broadcast_address` and a dynamic `port` controls only the UDP leg; the normal mDNS sweep still constructs `MdnsTransport` for the fixed multicast destination.
   - Selected disposition: Plan 13-01 adds private `_override_mdns_service_source()` backed by a `ContextVar`. The measurement script enters that scope only around the exact emulator-mode `discover()` call and supplies one synthetic `_LifxServiceRecord` for the script-owned device. `_discover_lifx_services()` owns and closes the injected async source instead of constructing `MdnsTransport`; the normal no-override path and public signatures remain unchanged. The later liveness verifier still performs the real correlated GetColor request against the same loopback emulator. Tests prove that no ambient `MdnsTransport` socket/destination opens and that the source scope, generator, liveness connection, and emulator server close on success, failure, and cancellation.

5. **RESOLVED — How do receive-time mDNS failures reach D-02 after the sweep has already caught them?**
   - What we know: `_discover_lifx_services_sweep()` currently absorbs `LifxNetworkError` during `receive()` and logs `str(error)`, so an outer merged pump cannot observe that failure.
   - Selected disposition: Plan 13-03 adds a private typed sweep-failure sink at the actual open/send/receive/follow-up catches and disables `MdnsTransport` detail logs only while that merged sink is installed. The merged path receives bounded stage/reason/exception-class fields and suppresses legacy raw-text/target/destination logs; the no-sink standalone path retains existing `discover_mdns()` compatibility. Plan 13-04 converts each event once into the merger's absorbed-failure event and one privacy-safe DEBUG record, with real before-open, receive-time, and post-partial-result tests.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `uv` | All Python commands | ✓ | 0.11.29 [VERIFIED: environment probe] | — |
| Python 3.10 | Minimum-version concurrency validation | ✓ | 3.10.11 [VERIFIED: environment probe] | CI matrix also covers supported versions. [VERIFIED: .github/workflows/ci.yml:155-201] |
| pytest | Invariant/lifecycle tests | ✓ | 9.1.1 [VERIFIED: environment probe] | — |
| `lifx-emulator-core` | Emulator evidence/integration | ✓ | 3.7.0 [VERIFIED: environment probe] | — |
| macOS/Darwin | Local research host | ✓ | Darwin [VERIFIED: environment probe] | Linux and Windows are CI targets. [VERIFIED: .github/workflows/ci.yml:155-201] |
| Physical LIFX fleet/private mapping | Repeated fleet and FIND-08 evidence | Operator-gated | Not probed | Emulator covers deterministic CI, not physical evidence. |

The installed versions above were probed with `uv --version`, `uv run --frozen python --version`, and `uv run --frozen pytest --version` during this research. Physical inventory was deliberately not enumerated because raw infrastructure identifiers and mappings must remain outside the repository. [VERIFIED: AGENTS.md:17-38]

**Missing dependencies with no fallback:** None for implementation and deterministic tests.

**Missing dependencies with fallback:** Physical fleet evidence cannot be replaced by the emulator; if hardware is temporarily unavailable, implementation can proceed but final fleet evidence remains an explicit operator gate.

## Security Domain

Security enforcement is enabled because `.planning/config.json` does not set `security_enforcement` to `false`. [VERIFIED: .planning/config.json:1-73]

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No user identity/authentication boundary in local discovery. |
| V3 Session Management | no | No application session is created. |
| V4 Access Control | no | No authorisation decision is introduced. |
| V5 Input Validation | yes | Preserve UDP source/serial validation; use validated mDNS record fields; require correlated packet type/identity/payload before yield. [VERIFIED: src/lifx/network/discovery.py:413-555] |
| V6 Stored Cryptography | no | No secret storage or cryptographic protocol is introduced; do not describe liveness as authentication. |

The category names follow OWASP ASVS 4's V2–V6 structure. [CITED: https://github.com/OWASP/ASVS]

### Known Threat Patterns for merged discovery

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Spoofed or stale mDNS advertisement | Spoofing | Direct correlated GetColor/Echo exchange; identity/type/payload checks; candidate-local rejection. |
| UDP response injection | Spoofing/Tampering | Retain established source ID, serial, packet type, endpoint, and correlation validation. [VERIFIED: src/lifx/network/discovery.py:413-555] |
| Response/subscriber amplification | Denial of service | One compatible active sweep; accepted-record dedup; bounded liveness workers; no producer backpressure; active log discarded at completion. |
| Slow or abandoned subscriber | Denial of service | Independent unbounded caller-loop queue, idempotent detach, last-subscriber cancellation, and one overall discovery deadline. |
| Diagnostic/evidence identifier leakage | Information disclosure | Stable category-only DEBUG values and operator aliases; no exception text, raw network fields, or mapping in repository. [VERIFIED: AGENTS.md:17-38] |

## Sources

### Primary (HIGH confidence)

- `src/lifx/network/discovery.py` — live validation, deadlines, deduplication, response wrapper, and cleanup seams.
- `src/lifx/network/mdns/discovery.py` and `types.py` — live per-call record assembly and candidate fields.
- `src/lifx/network/connection.py` — live request correlation, retry, timeout, Echo, and cleanup behaviour.
- `src/lifx/api.py` — current public discovery and lookup contracts.
- `src/lifx/devices/detection.py`, `base.py`, and `light.py` — class selection and the D-06 state-storage gap.
- `tests/test_api/test_api_discovery.py`, `tests/test_network/test_discovery_rebroadcast.py`, `tests/test_network/test_discovery_errors.py`, and `tests/test_network/test_mdns/` — existing invariant/lifecycle seams.
- `.planning/phases/13-merged-discovery/13-CONTEXT.md`, `13-SPEC.md`, `.planning/REQUIREMENTS.md`, and `AGENTS.md` — locked scope and project constraints.

### Secondary (MEDIUM confidence)

- https://docs.python.org/3.10/library/asyncio-task.html — task waiting, cancellation, and cross-thread coroutine submission.
- https://docs.python.org/3.10/library/asyncio-eventloop.html — thread-safe callback scheduling and manual loop shutdown.
- https://docs.python.org/3.10/library/asyncio-queue.html — queue ownership and backpressure semantics.
- https://docs.python.org/3.10/library/asyncio-future.html — concurrent-future adaptation.
- https://docs.python.org/3.10/library/time.html — monotonic nanosecond measurement.
- https://lan.developer.lifx.com/docs/querying-the-device-for-data — official Echo and GetColor purposes.
- https://lan.developer.lifx.com/docs/information-messages — StateColor/StateUnhandled protocol roles.
- https://lan.developer.lifx.com/docs/packet-contents — official response-correlation fields.
- https://github.com/OWASP/ASVS — ASVS category reference.

### Tertiary (LOW confidence)

- Exact `16`-probe cap, recommended new filenames, diagnostic reason names, and JSONL field names; all are marked `[ASSUMED]` and require planner/operator confirmation.

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH — no dependency change; verified against live package metadata, project instructions, and Python 3.10 official documentation.
- Architecture: HIGH — grounded in locked decisions and inspected raw discovery, mDNS record, request, device-construction, and cleanup seams.
- Pitfalls: HIGH — derived from concrete ownership/deadline/state mismatches in live code plus official asyncio rules.
- Exact liveness cap and new internal/file names: LOW — no isolated real-fleet cap measurement exists yet.

**Research date:** 2026-08-30
**Valid until:** 2026-09-29 for architecture; recheck environment/package versions and physical fleet availability at execution time.
