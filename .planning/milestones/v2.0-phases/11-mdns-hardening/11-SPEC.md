# Phase 11: mDNS Hardening - Specification

**Created:** 2026-08-28
**Ambiguity score:** 0.05 (gate: <= 0.20)
**Requirements:** 8 locked

## Goal

Bring the existing mDNS discovery leg to broadcast-grade per-sweep correctness by proving its legacy-unicast transport, validating its internal service metadata, exposing device connectivity honestly, honouring the cache semantics that apply to legacy-unicast replies, and documenting the resulting contract without changing the default discovery entry point.

## Background

Phase 10 landed the IPv6/Thread branch on local `main`. `MdnsTransport.open()` now binds `("", 0)`, `_LifxRecordCache` accumulates records across packets, and the low-level service-record generator issues bounded follow-up address queries. These mechanics are the correct baseline and remain Phase 11 deliverables to harden and prove, not redesign.

The current gaps are concrete. The transport regression test mocks `socket.bind()` but does not prove that a synthetic legacy-unicast response reaches the selected port. The internal service record exposes only one selected address and discards the TXT `tm` value, while `Device` exposes no connectivity property. `_pick_address()` prefers IPv4 but otherwise takes the first non-link-local IPv6 address in packet-arrival order. TXT serial validation is deferred until device construction rather than applied to the internal record. The per-sweep cache ignores TTL-zero goodbye semantics and does not report the protocol-invalid cache-flush bit on legacy-unicast replies. Phase 11 closes those gaps while making the low-level service-record API explicitly private.

The implementation discussion on 2026-08-28 explicitly amended the initial record-level API, ordered-address, and cache assumptions. The requirements and acceptance criteria below are the amended authority.

**Post-execution amendment, 2026-08-28:** After reviewing the completed security and API-coherence fixes, the developer adopted D-15 and D-16. D-15 supersedes the earlier D-05 retain-every-address interpretation with exact bounded fail-closed admission. D-16 supersedes the earlier D-03 integration interpretation that preserved a public record converter. This dated amendment changes current authority without rewriting the executed Plans 11-01 through 11-06, their summaries, review history, or implementation commits.

## Requirements

1. **Legacy-unicast query socket**: The mDNS query socket uses an operating-system-selected ephemeral UDP port and receives replies addressed directly to that port.
   - Current: `MdnsTransport.open()` binds `("", 0)`, and a mocked unit test checks that call, but no socket-level regression proves the selected port is not 5353 and receives a synthetic reply.
   - Target: Opening a real loopback `MdnsTransport` produces a non-zero local port other than 5353; a synthetic UDP datagram addressed to that port is returned by `receive()` without any test socket binding port 5353 or joining the multicast group.
   - Acceptance: A deterministic loopback test asserts `1 <= local_port <= 65535`, `local_port != 5353`, sends a datagram to that port, and receives the same bytes and sender address through `MdnsTransport.receive()`.

2. **Device connectivity metadata**: Every `Device` exposes connectivity as the literal string `"wifi"` or `"thread"` without exposing the undocumented TXT field or a transport enum publicly.
   - Current: Test fixtures contain `tm=1`, but `_LifxRecordCache.resolve()` discards the key, `Device` has no connectivity property, and the low-level `LifxServiceRecord` and `discover_lifx_services()` API are publicly exported and documented.
   - Target: `Device.connectivity` is typed as `Literal["wifi", "thread"]`. Only the exact TXT value `"2"` produces `"thread"`; every other value, including absent, empty, whitespace-padded, malformed, unrecognised, and exact `"1"`, produces `"wifi"` without raising or logging a validation failure. Under D-16, the low-level record, generator, and record-to-device conversion helper remain explicitly private `_LifxServiceRecord`, `_discover_lifx_services`, and `_create_device_from_record`, with no compatibility aliases, public exports, public documentation, or public examples. No public `TransportMethod` type is introduced, and no expansion of `tm` is asserted.
   - Acceptance: Parameterised tests cover exact `"2"` plus exact `"1"`, absence, `""`, `" 2"`, `"02"`, `"+2"`, `"0"`, `"3"`, a negative value, and non-numeric text; only exact `"2"` produces `"thread"` and every other case produces `"wifi"`. Devices created outside the mDNS path default to `"wifi"`. Structured package-surface tests prove that neither converter name is exported.

3. **Cross-packet record accumulation**: One discovery call accumulates the records needed for a service instance across response packets and emits that instance exactly once when complete.
   - Current: `_LifxRecordCache` already retains TXT, SRV, A, and AAAA data across calls to `add_packet()`, with direct cache tests covering a basic split response.
   - Target: Synthetic discovery-loop tests prove that TXT, SRV, and address records may arrive in any packet order, with duplicates or unrelated empty/incomplete packets, without changing the resolved identity, retained address membership, selected address class, or exact-once emission. Concurrent discovery calls have independent per-call caches.
   - Acceptance: Permutations of split TXT/SRV/address packets resolve to the same identity and retained address set; incomplete input yields nothing; duplicate and replayed packets do not duplicate addresses or emissions; two simultaneous discovery calls do not share learned records or resolved-instance state.

4. **Bounded follow-up address queries**: A valid service instance whose SRV target lacks an address triggers bounded follow-up A/AAAA queries and resolves when a later response supplies an address.
   - Current: `pending_targets()` and `build_address_query()` exist, with current loop bounds of two attempts per target and 64 distinct targets per discovery call.
   - Target: The existing behaviour is locked as the contract: no more than two send attempts for one hostname and no more than 64 distinct follow-up targets in one discovery call. A successful send is not repeated, and a later A or AAAA response completes the pending instance.
   - Acceptance: Scripted transport tests prove the exact address-query bytes are sent, a later address packet yields the instance, persistent send failures stop after two attempts per hostname, the 65th distinct target is not queried, and a successfully queried target is not sent again.

5. **Bounded internal multi-address admission and selection**: Learned A and AAAA identities are admitted under exact per-owner and per-sweep ceilings while the selected `ip` follows the compatible address-class preference only from complete state.
   - Current: The cache retains at most one A address, retains up to 16 AAAA addresses in arrival order, and the internal record carries only the selected `ip`. IPv4 wins when present; otherwise the first non-link-local IPv6 address wins.
   - Target: Under D-15, `_LifxServiceRecord.addresses` is an unordered internal collection containing admitted unique, syntactically valid learned A/AAAA addresses, capped at 256 live RR identities per owner and 1,024 per discovery sweep. Exact duplicate identities refresh without consuming capacity. Packet-source fallback remains separate because it is transport evidence, not an advertised address. An unseen over-cap identity is rejected and counted without eviction; owner overflow or sweep exhaustion is permanent for that call. Selection prefers IPv4, then ULA, GUA, and scoped link-local only while state is complete. An unscoped link-local is retained internally but never selected. Incomplete owner or sweep state cannot select an address, resolve a record, or trigger follow-up work.
   - Acceptance: Synthetic records in multiple arrival orders produce equal admitted address sets and select from the highest available address class; duplicates collapse to one entry and refresh at capacity; IPv4 wins over ULA, ULA over GUA, and GUA over scoped link-local; an unscoped link-local remains retained but is never selected. The 257th owner identity and 1,025th sweep identity permanently fail the call closed without eviction, subset selection, record resolution, or follow-up amplification.

6. **TXT serial validation**: The mDNS TXT `id` is validated before an internal service record is yielded.
   - Current: `_LifxRecordCache.resolve()` requires only a non-empty `id`; malformed values can reach the internal record and fail later during device construction.
   - Target: A valid `id` is exactly 12 hexadecimal characters, compared case-insensitively and normalised to lowercase. Values containing separators or non-hexadecimal characters, all-zero and all-ones values, multicast/group identifiers, and other broadcast-invalid serials are rejected. If one service instance presents conflicting valid IDs, that instance remains invalid while the conflict exists in the live cache rather than choosing a first or latest winner. It may recover after RFC-compliant goodbye expiry leaves exactly one valid ID. Rejecting one instance never aborts the rest of the discovery sweep.
   - Acceptance: Parameterised tests cover valid upper/lowercase IDs, empty and malformed values, separators, wrong lengths, all-zero, all-ones, multicast/group values, conflicting IDs, and recovery after one conflicting ID expires; only a currently valid unambiguous ID yields a record, normalised lowercase, while a later valid instance in the same sweep is still yielded.

7. **Per-sweep legacy-unicast cache semantics**: The record cache follows RFC 6762 goodbye semantics, does not apply multicast cache-flush semantics to legacy-unicast replies, and is never reused across calls.
   - Current: `DnsResourceRecord` exposes `ttl` and `cache_flush`, but `_LifxRecordCache.add_packet()` ignores both and only appends or overwrites by its own table shape.
   - Target: A TTL-zero TXT, SRV, A, or AAAA goodbye changes the matching cached record to a one-second lifetime. Reannouncement during that grace rescues the record; otherwise it expires one second later. Grace never extends the caller's overall or idle deadline. A goodbye after an instance was emitted cannot retract the yielded value or cause re-emission. Because RFC 6762 forbids cache-flush bits in legacy-unicast replies to ports other than 5353, an unexpected bit does not replace cached records; the record is processed normally and the sweep increments an `unexpected_cache_flush` diagnostic counter. Empty input and repeated goodbyes or rescues are idempotent.
   - Acceptance: Synthetic packet sequences prove the one-second goodbye grace, rescue, expiry, conflict recovery, post-emission no-retraction/no-re-emission, unchanged caller deadlines, ignored cache-flush semantics, stable repetitions, empty-packet no-op, and empty caches for separate discovery calls.

8. **Honest mDNS documentation**: The public device API and private mDNS internals document their actual legacy-unicast behaviour and intentional limitations without expanding undocumented metadata.
   - Current: `mdns/transport.py` accurately describes the ephemeral-port query socket, but the complete contract does not yet pin all Phase 11 limitations and metadata semantics, while public docs and examples promote the low-level record generator.
   - Target: Public documentation describes `Device.connectivity` as `"thread"` only for exact `tm=2` and `"wifi"` otherwise, without naming or expanding the private wire key. Internal mDNS docstrings state that queries are sent by IPv4 multicast from an ephemeral port, replies are received by legacy unicast, multicast membership is not joined, unsolicited announcements are not received, cache-flush bits do not apply on this path, and the per-sweep cache is not reusable across calls. Public low-level record/generator documentation and examples are removed. Phase 11 does not rejoin the multicast group or add a responder-population probe.
   - Acceptance: Documentation review finds every stated behaviour above, no public low-level service-record API, no public transport enum, no expansion of `tm`, no claim that the socket joins the multicast group, and no Phase 11 code path for multicast rejoin or a responder-population probe.

## Boundaries

**In scope:**

- A socket-level ephemeral-port and synthetic legacy-unicast reply regression test.
- `Device.connectivity: Literal["wifi", "thread"]`, with exact `tm=2` selecting Thread and every other case selecting WiFi.
- Explicitly private `_LifxServiceRecord`, `_discover_lifx_services`, and `_create_device_from_record` internals, with their public exports, documentation, and examples removed and no compatibility aliases under D-16.
- Bounded unordered A/AAAA admission under D-15: 256 live RR identities per owner and 1,024 per sweep, exact-duplicate refresh, separate packet-source fallback, permanent overflow, address-class selection only from complete state, and unscoped link-local non-selection.
- Strict TXT serial validation before internal record emission, including recovery after a conflicting ID expires from the live cache.
- Per-discovery-call RFC 6762 one-second goodbye grace and rescue handling.
- Aggregate per-sweep `DEBUG` rejection counters containing stable reason codes and record types only, plus `unexpected_cache_flush` for a cache-flush bit observed on the legacy-unicast path.
- Synthetic discovery-loop tests for cross-packet accumulation and bounded follow-up A/AAAA queries.
- Public device documentation and private mDNS docstrings describing actual behaviour and limitations.

**Out of scope:**

- Merging mDNS into `discover()` or racing both legs in `find_by_serial()` - Phase 13 owns default merged discovery.
- IPv6 support in `find_by_ip()` and family-aware broadcast plumbing - Phase 12 owns targeted IPv6 lookup.
- Thread retry, bandwidth, or animation tuning - Phase 14 measures the fleet before changing WiFi-derived behaviour; `tm` may inform future evidence-backed tuning.
- Public exposure of raw mDNS records, the TXT `tm` field, or a `TransportMethod` enum.
- A public `Device.addresses` collection; alternative addresses remain internal in Phase 11.
- Rejoining the mDNS multicast group or adding a second receive socket - the ephemeral legacy-unicast design remains locked.
- A responder-population comparison probe - explicitly excluded by the milestone decision recorded in MDNS-08.
- IPv6 multicast mDNS queries - the query leg remains IPv4 multicast by design.
- Fleet-scale hardware validation - Phase 11 uses synthetic multi-packet evidence; hardware confirmation remains future work.
- Broadcast-first consumer guidance and downstream Home Assistant changes - Phase 14 owns guidance, and downstream repositories own their integration code.
- Thread commissioning or border-router management - outside a device-control library's remit.

## Constraints

- Python 3.10 through 3.14, built-in `asyncio`, and zero runtime dependencies.
- This v2.0 phase intentionally removes the documented low-level `LifxServiceRecord`, `discover_lifx_services()`, and `create_device_from_record()` API without aliases under D-16; public `discover_devices_mdns()` and `lifx.api.discover_mdns()` remain supported.
- `Device.connectivity` returns only the literal strings `"wifi"` and `"thread"`; exact `tm=2` is Thread and every other case is WiFi.
- The undocumented `tm` abbreviation is private and never expanded in public names, docstrings, or documentation.
- The ephemeral-port regression must not bind port 5353 or depend on the host's mDNS daemon, multicast routing, or external hardware.
- The record cache exists for one discovery call only and must not become a cross-call or process-wide cache.
- Goodbye grace never extends the caller's overall or idle discovery deadline.
- Cache-flush bits never replace cached records on the legacy-unicast response path.
- Follow-up traffic remains capped at two attempts per hostname and 64 distinct targets per discovery call.
- Address admission is capped at exactly 256 live A/AAAA RR identities per owner and 1,024 per sweep. Exact duplicates refresh without consuming capacity; owner overflow and sweep exhaustion are permanent for the call, and incomplete state cannot select, resolve, or trigger follow-up work.
- Rejection diagnostics are aggregated once per sweep at `DEBUG` and contain no serial, IP address, hostname, TXT value, raw packet, or other live identifier.
- Synthetic fixtures use format-preserving fake serials, documentation-range IP addresses where routable examples are needed, and no live hostnames or raw discovery output.
- Standard gates remain mandatory: Ruff format/check, strict Pyright, full pytest, and 100% branch patch coverage in CI.
- Australian English is used in prose, comments, and documentation.

## Acceptance Criteria

- [ ] AC1: A real loopback `MdnsTransport` binds a port from 1 through 65535 other than 5353 and receives a synthetic datagram addressed to that port; the test never binds 5353.
- [ ] AC2: The Phase 11 query transport neither sets `IP_ADD_MEMBERSHIP` nor introduces another multicast receive socket.
- [ ] AC3: Every `Device` has `connectivity: Literal["wifi", "thread"]`; only exact TXT `tm=2` produces `"thread"`, while every other value and every non-mDNS construction path produces `"wifi"`.
- [ ] AC4: Missing, empty, whitespace-padded, alternate integer spelling, negative, malformed, and unrecognised `tm` values produce `"wifi"` without raising or contributing a validation diagnostic.
- [ ] AC5: `LifxServiceRecord`, `discover_lifx_services()`, `create_device_from_record()`, and `TransportMethod` are absent from public exports, documentation, and examples; `_LifxServiceRecord`, `_discover_lifx_services`, and `_create_device_from_record` remain private with no compatibility aliases, and no public text expands `tm`.
- [ ] AC6: Empty or incomplete mDNS packet sequences yield no internal service record and do not prevent a later complete instance from being yielded.
- [ ] AC7: Every tested permutation of TXT, SRV, A, and AAAA packet arrival produces the same resolved identity, retained address set, and selected address class; no exact within-class order is required.
- [ ] AC8: Duplicate or replayed records do not duplicate retained addresses or cause a service instance to be emitted more than once.
- [ ] AC9: Concurrent `_discover_lifx_services()` calls do not share cached records, pending targets, resolved-instance state, expiry state, or diagnostic counters.
- [ ] AC10: A missing SRV target address sends the expected A/AAAA query and a later address response completes and yields the pending instance.
- [ ] AC11: Follow-up sends stop after two failed attempts per hostname, admit no more than 64 hostnames per discovery call, and do not repeat a successfully sent target.
- [ ] AC12: `_LifxServiceRecord.addresses` contains admitted unique valid A/AAAA identities as an unordered internal collection, excludes packet-source fallback, refreshes exact duplicates without consuming capacity, and enforces exactly 256 identities per owner and 1,024 per sweep with permanent per-call overflow.
- [ ] AC13: `record.ip` selects IPv4 before ULA, ULA before GUA, and GUA before scoped link-local.
- [ ] AC14: An unscoped link-local address remains retained internally but is never selected; without another selectable address, the instance remains unresolved.
- [ ] AC15: A service instance with no selectable address, an overflowed address owner, or a sweep with exhausted address capacity is not selected or emitted, and its incomplete state triggers no follow-up query.
- [ ] AC16: TXT `id` accepts exactly 12 hexadecimal characters, normalises valid uppercase input to lowercase, and rejects empty, separated, malformed, wrong-length, all-zero, all-ones, and multicast/group values.
- [ ] AC17: Conflicting valid TXT IDs invalidate an instance while both remain live; after goodbye expiry leaves exactly one valid ID, the instance may recover and resolve.
- [ ] AC18: Rejecting an invalid service instance does not abort the sweep or suppress a later valid instance; rejection counters are emitted once per sweep at `DEBUG` with reason code and record type only.
- [ ] AC19: TTL-zero TXT, SRV, A, and AAAA records receive a one-second lifetime, may be rescued by reannouncement, expire after that grace, never extend discovery deadlines, and never cause a previously emitted instance to re-emit.
- [ ] AC20: An unexpected cache-flush bit in a legacy-unicast response does not replace cached records or reject the record; it increments the aggregate `unexpected_cache_flush` debug counter.
- [ ] AC21: Empty packets, repeated goodbyes, repeated rescues, and repeated unexpected cache-flush bits are idempotent apart from their bounded aggregate counters.
- [ ] AC22: Every discovery call starts with a new empty record cache; no record, expiry, conflict, diagnostic, or emission state survives across calls.
- [ ] AC23: Public device documentation and private mDNS docstrings state the connectivity mapping, IPv4-multicast query, ephemeral source port, legacy-unicast reply, no-membership, no-unsolicited-announcement, no legacy-unicast cache-flush semantics, and per-call-cache contract.
- [ ] AC24: Phase 11 contains no multicast-group rejoin and no responder-population probe.
- [ ] AC25: Phase 11 tests, documentation, and evidence contain no live serial, IP address, hostname, or raw discovery output.
- [ ] AC26: Focused mDNS tests, the full pytest suite, Ruff formatting/checking, and strict Pyright all pass without weakening coverage configuration.

## Edge Coverage

**Coverage:** 29/29 applicable edges resolved - 0 unresolved - 23 explicit - 0 backstop - 6 dismissed

| Category | Requirement | Status | Resolution / Reason |
|----------|-------------|--------|---------------------|
| boundary | R1 | resolved / explicit | AC1 pins the selected port range and excludes 5353. |
| precision | R1 | dismissed | UDP port values are exact integers; no rounding, precision, or overflow contract applies. |
| concurrency | R1 | dismissed | Phase 10 already verified open/open, open/close, and cancellation lifecycle safety; R1 adds no new lifecycle behaviour. |
| boundary | R2 | resolved / explicit | AC3-AC5 cover exact `"2"`, every value outside the Thread sentinel, and the D-16 private conversion-helper boundary. |
| empty | R2 | resolved / explicit | AC4 maps absence and empty text to `"wifi"`. |
| encoding | R2 | resolved / explicit | AC3-AC4 recognise only exact ASCII `"2"` as Thread. |
| precision | R2 | dismissed | Exact string comparison has no rounding or numeric precision behaviour. |
| adjacency | R3 | resolved / explicit | AC8 covers duplicate records across adjacent or replayed packets. |
| empty | R3 | resolved / explicit | AC6 covers empty and incomplete packet sequences. |
| ordering | R3 | resolved / explicit | AC7 requires packet-order-independent identity, set membership, and selected address class without imposing an internal tuple order. |
| idempotency | R3 | resolved / explicit | AC8 requires replay to preserve one emission and one copy of each address. |
| concurrency | R3 | resolved / explicit | AC9 requires independent state for simultaneous discovery calls. |
| idempotency | R4 | resolved / explicit | AC11 pins successful-send deduplication and the two-attempt/64-target bounds. |
| concurrency | R4 | dismissed | Follow-up sends occur in the existing single discovery loop and create no parallel worker; Phase 10 owns transport interruption cleanup. |
| adjacency | R5 | resolved / explicit | AC12 collapses duplicate addresses. |
| boundary | R5 | resolved / explicit | AC12 and AC15 pin the exact 256-per-owner and 1,024-per-sweep ceilings plus permanent fail-closed overflow transitions under D-15. |
| empty | R5 | resolved / explicit | AC15 prevents emission without a selectable address. |
| ordering | R5 | resolved / explicit | AC12-AC14 pin address-class preference and unscoped-link-local disposition while leaving within-class tie-breaking unconstrained. |
| adjacency | R6 | resolved / explicit | AC17 invalidates live conflicting IDs and permits recovery only after expiry leaves one valid ID. |
| empty | R6 | resolved / explicit | AC16 rejects an absent or empty ID. |
| encoding | R6 | resolved / explicit | AC16 pins exactly 12 hexadecimal characters and lowercase normalisation. |
| ordering | R6 | resolved / explicit | AC17 makes conflicting-ID outcome independent of arrival order. |
| adjacency | R7 | resolved / explicit | AC19-AC20 pin one-second goodbye grace/rescue and non-application of cache-flush semantics. |
| empty | R7 | resolved / explicit | AC21 makes an empty packet a no-op. |
| ordering | R7 | resolved / explicit | AC19 makes rescue and expiry depend on live TTL state rather than packet arrival winning a conflict. |
| idempotency | R7 | resolved / explicit | AC21 covers repeated goodbye, rescue, and unexpected cache-flush input. |
| concurrency | R7 | resolved / explicit | AC22 and AC9 prevent expiry, diagnostic, and record state sharing across calls. |
| empty | R8 | dismissed | R8 is a static documentation contract with no nullable or empty runtime input. |
| encoding | R8 | dismissed | R8 requires factual prose and exact identifiers, not text-length or Unicode normalisation behaviour. |

## Prohibitions (must-NOT)

**Coverage:** 7/7 applicable prohibitions resolved - 0 unresolved - 5 test - 1 judgment - 1 dismissed

| Prohibition (must-NOT statement) | Requirement | Status | Verification / Reason |
|----------------------------------|-------------|--------|------------------------|
| MUST NOT bind the mDNS query socket to port 5353 or join the multicast group, including as a fallback for unsolicited reception. | R1, R8 | resolved | verification: test - AC1, AC2, AC24; wired-check descriptor intentionally deferred until the Phase 11 tests exist. |
| MUST NOT expose `LifxServiceRecord`, `discover_lifx_services()`, `create_device_from_record()`, `TransportMethod`, or the raw `tm` field as public API, documentation, or examples; D-16 permits no compatibility alias. | R2, R8 | resolved | verification: judgment and test - AC5 and AC23 route exports and wording to review. |
| MUST NOT assert an expansion of `tm`; only exact `tm=2` may be described as Thread and every other case is WiFi. | R2, R8 | resolved | verification: judgment - AC3-AC5 and AC23 route behaviour and wording to tests and documentation review. |
| MUST NOT apply cache-flush replacement semantics to legacy-unicast responses. | R7 | resolved | verification: test - AC20-AC21 require ordinary record handling plus an aggregate diagnostic. |
| MUST NOT allow `tm` to influence address selection, routing, connection behaviour, retries, or tuning. | R2 | dismissed | Thread has significantly lower bandwidth, so tuning and animations will almost certainly need to be modified for Thread-based bulbs; Phase 14 owns the evidence and any later behaviour. |
| MUST NOT select an address, resolve a record, or trigger follow-up work from an owner or sweep whose admitted address state is incomplete after D-15 overflow. | R5 | resolved | verification: test - AC12 and AC15 route exact owner/sweep overflow transitions to the existing focused regressions. |
| MUST NOT place live serials, IP addresses, hostnames, or raw discovery output in Phase 11 tests, documentation, or evidence. | R1-R8 | resolved | verification: test - AC25; wired-check descriptor intentionally deferred until the Phase 11 evidence checks exist. |

Generic mDNS spoofing, injection, and denial-of-service concerns are security canon owned by `$gsd-secure-phase`; they are not duplicated as bespoke prohibitions here.

## Ambiguity Report

| Dimension | Score | Min | Status | Notes |
|-----------|-------|-----|--------|-------|
| Goal Clarity | 0.97 | 0.75 | met | Eight roadmap outcomes are stated as observable device, internal record, cache, transport, and documentation changes. |
| Boundary Clarity | 0.95 | 0.70 | met | Phases 12-14, multicast rejoin, probes, hardware validation, and downstream integrations are explicitly excluded. |
| Constraint Clarity | 0.94 | 0.65 | met | Connectivity mapping, address-class selection, query caps, RFC cache lifetime, intentional v2.0 API removal, platform, and privacy constraints are locked. |
| Acceptance Criteria | 0.91 | 0.70 | met | Twenty-six pass/fail checks plus fully resolved edge and prohibition coverage. |
| **Ambiguity** | **0.05** | **<= 0.20** | **met** | Gate passed after interview round 1. |

Status: met = dimension meets its minimum; below = planner must treat it as an assumption.

## Interview Log

| Round | Perspective | Question summary | Decision locked |
|-------|-------------|------------------|-----------------|
| 1 | Researcher | Are already-landed mDNS mechanics still Phase 11 deliverables? | Keep, harden, and prove them; redesign only where a locked requirement exposes a gap. |
| 1 | Researcher | What is the `tm` public contract? | Superseded during discussion: transport metadata is private and `Device.connectivity` carries literal strings. |
| 1 | Researcher | How does dual-stack address selection behave? | Historical D-05 answer: preserve IPv4-first compatibility, then ULA, GUA, and scoped link-local, with unlimited unordered retention. Superseded by D-15 on 2026-08-28: retain that class order only for complete state admitted within the exact 256-per-owner and 1,024-per-sweep ceilings. |
| Gate | Author | Ambiguity reached 0.05; write or continue? | Write the specification after completeness probes. |
| Edge 1 | Edge completeness | Which TXT forms indicate Thread? | Superseded during discussion: only exact `"2"` is Thread; every other form is WiFi. |
| Edge 1 | Edge completeness | What bounds follow-up address traffic? | Two attempts per hostname and 64 distinct targets per discovery call. |
| Edge 1 | Edge completeness | How strict is TXT `id` and how are conflicts handled? | Exactly 12 hex characters; live conflicting IDs invalidate the instance, which may recover after goodbye expiry leaves one valid ID. |
| Edge 2 | Edge completeness | How are goodbyes and cache-flush RRsets handled? | Superseded during discussion: RFC one-second goodbye grace/rescue applies; legacy-unicast cache-flush semantics do not. |
| Edge 2 | Edge completeness | Can an unscoped link-local address be selected? | Retain it for diagnostics but never select it. |
| Prohibition | Must-NOT completeness | Which bespoke constraints must be retained? | Keep no-5353/no-join, no invented `tm` expansion, and no live identifiers in tracked artefacts. |
| Prohibition | Must-NOT completeness | Must `tm` remain diagnostic-only forever? | Dismissed: Phase 14 may use transport evidence for Thread-specific tuning and animation behaviour. |
| Discuss | Public API amendment | Where should connectivity be exposed? | `Device.connectivity` returns `"thread"` only for exact `tm=2` and `"wifi"` otherwise; no public transport enum. |
| Discuss | Low-level API amendment | What happens to the existing record and generator exports? | Rename them explicitly private, remove exports/docs/examples, and provide no compatibility aliases. |
| Discuss | Address amendment | Does retained-address order matter? | Retain an unordered internal set; compare membership, preserve address-class preference, and leave within-class tie-breaking unconstrained. |
| Discuss | Diagnostics amendment | How are invalid records reported? | Aggregate privacy-safe reason-code counters once per sweep at `DEBUG`; non-2 `tm` is valid WiFi and produces no rejection. |
| Discuss | RFC cache amendment | How are goodbye and cache-flush records handled? | Use RFC 6762 one-second goodbye grace/rescue; do not apply cache-flush semantics on legacy unicast, but count the unexpected bit. |

---

*Phase: 11-mdns-hardening*
*Spec created: 2026-08-28*
*Next step: $gsd-discuss-phase 11 - implementation decisions for the locked requirements above*
