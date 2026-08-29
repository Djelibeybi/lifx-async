# Phase 11: mDNS Hardening - Context

**Gathered:** 2026-08-28
**Status:** Amended for independent re-verification

<domain>
## Phase Boundary

Bring the existing mDNS discovery leg to broadcast-grade per-sweep correctness before
Phase 13 merges it into default discovery. Phase 11 proves the ephemeral legacy-unicast
transport, validates and assembles private service records across packets, selects and
retains addresses correctly, follows the RFC cache rules that apply to this transport,
exposes connectivity on `Device`, and documents the resulting contract. It does not merge
discovery legs, add targeted IPv6 lookup, retune Thread behaviour, rejoin multicast, or add
hardware-scale validation.

</domain>

<spec_lock>
## Requirements (locked via SPEC.md)

**8 requirements are locked.** See `11-SPEC.md` for full requirements, boundaries, and
acceptance criteria. The SPEC was amended during this discussion and is now the authority
for the public API, address collection, diagnostics, goodbye, and cache-flush contracts.

Downstream agents MUST read `11-SPEC.md` before planning or implementing. Requirements are
not duplicated here.

**In scope (from SPEC.md):**

- A socket-level ephemeral-port and synthetic legacy-unicast reply regression test
- `Device.connectivity: Literal["wifi", "thread"]`, with exact `tm=2` selecting Thread and
  every other case selecting WiFi
- Explicitly private `_LifxServiceRecord`, `_discover_lifx_services`, and
  `_create_device_from_record` internals, with their public exports, documentation, and
  examples removed and no compatibility aliases
- A bounded internal unordered address collection, with exact duplicate refresh,
  separate packet-source fallback, address-class selection, permanent per-call overflow,
  and fail-closed handling of incomplete owner or sweep state
- Strict TXT serial validation before internal record emission, including recovery after a
  conflicting ID expires from the live cache
- Per-discovery-call RFC 6762 one-second goodbye grace and rescue handling
- Aggregate per-sweep privacy-safe `DEBUG` rejection counters, including
  `unexpected_cache_flush` for the protocol-invalid bit on legacy unicast
- Synthetic discovery-loop tests for cross-packet accumulation and bounded follow-up
  A/AAAA queries
- Public device documentation and private mDNS docstrings describing actual behaviour and
  limitations

**Out of scope (from SPEC.md):**

- Merging mDNS into `discover()` or racing both legs in `find_by_serial()`; Phase 13 owns
  default merged discovery
- IPv6 support in `find_by_ip()` and family-aware broadcast plumbing; Phase 12 owns
  targeted IPv6 lookup
- Thread retry, bandwidth, or animation tuning; Phase 14 owns evidence-backed tuning
- Public exposure of raw mDNS records, the TXT `tm` field, a `TransportMethod` enum, or a
  `Device.addresses` collection
- Rejoining the mDNS multicast group, adding a second receive socket, a responder-population
  comparison probe, or IPv6 multicast mDNS queries
- Fleet-scale hardware validation, downstream Home Assistant changes, Thread commissioning,
  or border-router management

</spec_lock>

<spec_amendments>
## SPEC.md Amendments Made During This Discussion

The initial `11-SPEC.md` was internally consistent but rested on four assumptions the user
explicitly rejected or that RFC 6762 disproved. They were amended in place before this
context was written:

- The public `LifxServiceRecord.tm`/`TransportMethod` contract was replaced by
  `Device.connectivity`, and the low-level record and generator became explicitly private.
- The public deterministic `addresses` tuple was replaced by an unordered internal address
  collection. Address membership and selected class matter; byte-for-byte order does not.
- Invalid-record logging became an aggregate, privacy-safe per-sweep `DEBUG` summary rather
  than unspecified individual events.
- Immediate goodbye deletion and cache-flush replacement were replaced by RFC 6762's
  one-second goodbye grace/rescue and the rule that cache-flush semantics do not apply to
  legacy-unicast responses.

`.planning/PROJECT.md` and `.planning/REQUIREMENTS.md` were reconciled with these decisions.
The Phase 11 success-criteria wording in `.planning/ROADMAP.md` predates them; where it
mentions public `LifxServiceRecord.tm`, deterministic record order, immediate TTL-zero
deletion, or applied cache-flush semantics, this amended SPEC and context supersede it.

**Post-execution authority amendment, 2026-08-28:** After reviewing the completed
security and API-coherence fixes, the developer selected bounded fail-closed address
admission and a fully private record-conversion seam. D-15 supersedes D-05's retain-every-
address interpretation, and D-16 supersedes the earlier D-03 integration interpretation
that preserved a public record-to-device factory. Executed Plans 11-01 through 11-06 and
their summaries remain historical evidence of the authority under which they ran.

</spec_amendments>

<decisions>
## Implementation Decisions

### Public connectivity API

- **D-01:** Every `Device` exposes `connectivity` typed as
  `Literal["wifi", "thread"]`. — **Reversibility:** one-way — callers may persist, compare,
  and branch on these exact public string values after v2.0 ships.
- **D-02:** Exact private TXT `tm=2` maps to `"thread"`; every other value, including
  missing, malformed, unrecognised, and exact `tm=1`, maps to `"wifi"`. Devices constructed
  outside mDNS default to `"wifi"`.
- **D-03:** `LifxServiceRecord` and `discover_lifx_services()` become explicitly private
  `_LifxServiceRecord` and `_discover_lifx_services`. Remove them from top-level and mDNS
  package exports, public API docs, user-guide coverage, and examples. Do not leave
  compatibility aliases. — **Reversibility:** one-way — this deliberately breaks the
  documented v1.x low-level API and downstream code must move to device-level discovery.
  **Supersession note (2026-08-28):** D-16 supplements these named removals and supersedes
  the later integration interpretation that preserved a public conversion factory.
- **D-04:** Do not introduce or expose `TransportMethod`, raw `tm`, or another connectivity
  enum. The raw wire key remains an internal implementation detail and its abbreviation is
  never expanded.

### Internal address semantics

- **D-05:** Retain every unique syntactically valid A/AAAA address in an unordered internal
  collection on `_LifxServiceRecord`. `Device` continues exposing only its selected `ip`.
  **Superseded 2026-08-28 by D-15:** the active contract is bounded, fail-closed address
  admission rather than unbounded retention.
- **D-06:** Keep packet-source fallback separate from advertised addresses because it is
  transport evidence, not an A/AAAA record.
- **D-07:** Preserve selection by address class: IPv4, ULA, GUA, then scoped link-local.
  Never select unscoped link-local. Within one class, follow applicable protocol rules and
  leave any remaining tie-breaker to the planner; tests compare address membership as sets
  and do not impose artificial byte ordering.

### Invalid-record diagnostics

- **D-08:** Count rejected records by stable reason code and emit one aggregate event per
  discovery sweep at `DEBUG`; do not warn or log every record.
- **D-09:** Diagnostic data contains the rejection reason and record type only. It must not
  contain a serial, IP address, hostname, TXT value, raw packet, instance label, hash, or
  other live identifier.
- **D-10:** Missing, malformed, unrecognised, and non-2 `tm` values are valid WiFi outcomes,
  not rejection diagnostics.

### RFC cache and conflict recovery

- **D-11:** Follow RFC 6762 §10.1: a TTL-zero TXT, SRV, A, or AAAA goodbye gives the matching
  cached record a one-second lifetime. A reannouncement during that grace rescues it;
  otherwise it expires.
- **D-12:** A service instance with multiple live valid TXT IDs remains invalid. If goodbye
  expiry leaves exactly one valid ID, the instance recovers and may resolve; historical
  conflict does not poison the rest of the sweep.
- **D-13:** Goodbye grace never extends the caller's overall or idle discovery deadline.
  Unsettled per-sweep state is discarded when the caller's deadline ends.
- **D-14:** RFC 6762 forbids cache-flush bits in legacy-unicast replies to ports other than
  5353. Do not apply replacement semantics and do not reject the otherwise usable record;
  process it normally and increment `unexpected_cache_flush` in the aggregate debug summary.

### Post-execution developer overrides

- **D-15 (2026-08-28):** Admit at most 256 live A/AAAA RR identities for one owner and
  1,024 across one discovery sweep. Exact duplicate identities refresh in place and do not
  consume capacity. An unseen identity beyond either ceiling is rejected without eviction
  and counted only through privacy-safe capacity diagnostics. Owner overflow and sweep
  exhaustion are permanent for that discovery call. Once either applies, address selection,
  record resolution, and follow-up queries fail closed rather than trusting or amplifying
  incomplete attacker-controlled state. D-06 and D-07 remain active only while admitted
  address state is complete. **D-15 supersedes D-05's unbounded retention interpretation.**
- **D-16 (2026-08-28):** `_LifxServiceRecord`, `_discover_lifx_services`, and
  `_create_device_from_record` remain private together. No public or compatibility alias is
  restored. `discover_devices_mdns()` and `lifx.api.discover_mdns()` are the supported
  device-level paths. **D-16 supersedes the earlier D-03 integration interpretation and
  executed-plan expectation that preserved a public `create_device_from_record` export.**

### Planner's Discretion

- The concrete internal collection type for retained addresses
- The timer/expiry data structure used for one-second goodbye grace, provided it remains
  per-sweep and does not extend caller deadlines
- The complete stable rejection-reason vocabulary beyond the locked
  `unexpected_cache_flush` name
- The private storage and constructor plumbing behind the read-only-looking
  `Device.connectivity` property

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Locked phase authority

- `.planning/phases/11-mdns-hardening/11-SPEC.md` — amended requirements, boundaries,
  acceptance criteria, edge coverage, and prohibitions; MUST read before planning
- `.planning/REQUIREMENTS.md` — authoritative MDNS-01 through MDNS-08 wording, reconciled
  with the discussion amendments
- `.planning/PROJECT.md` — v2.0 milestone scope and key decisions, reconciled with the
  device-level connectivity and RFC cache contracts
- `.planning/ROADMAP.md` — Phase 11 dependency and outcome overview, amended under D-15
  and D-16 while preserving the executed-plan history

### Prior phase and research inputs

- `.planning/phases/10-land-the-ipv6-thread-branch/10-CONTEXT.md` — locked legacy-unicast,
  exact-once emission, follow-up query, lifecycle, and privacy baseline inherited by Phase 11
- `.planning/research/PITFALLS.md` — B3/B5/B6 problem evidence; its proposed public tuple,
  immediate goodbye deletion, and cache-flush solution details are superseded by the amended
  SPEC
- `.planning/research/ARCHITECTURE.md` — v2.0 mDNS integration seams and Phase 13 record-level
  merge dependency; public names shown there predate explicit private renaming
- `.agents/skills/spike-findings-lifx-async/SKILL.md` — reliability constraints and the rule
  not to retune WiFi-derived behaviour before Phase 14 evidence

### Protocol and repository rules

- [RFC 6762: Multicast DNS](https://www.rfc-editor.org/rfc/rfc6762.html) §6.7, §10.1,
  §10.2 — legacy-unicast replies, one-second goodbye grace/rescue, and cache-flush exclusion
- `AGENTS.md` — repository coding, privacy, testing, dependency, and commit rules
- `CLAUDE.md` — architecture and test conventions consumed by existing planning material

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- `src/lifx/devices/base.py` — common `Device` construction and property surface where the
  connectivity default belongs
- `src/lifx/network/mdns/discovery.py` — `_LifxRecordCache`, address selection,
  cross-packet accumulation, exact-once emission, bounded follow-up queries, device
  construction, and the low-level generator to make private
- `src/lifx/network/mdns/types.py` — frozen service-record dataclass to rename and extend
  with the private address collection and connectivity hand-off
- `src/lifx/network/mdns/dns.py` — parsed `ttl` and `cache_flush` inputs already available
  to the cache
- `src/lifx/network/mdns/transport.py` — Phase 10's lifecycle-safe ephemeral IPv4
  legacy-unicast transport; Phase 11 adds the real loopback delivery regression, not a
  transport redesign
- `tests/test_network/test_mdns/test_discovery.py` and `test_transport.py` — extensive cache,
  scripted transport, bounds, lifecycle, and dedup test seams to extend

### Established Patterns

- Public surfaces are explicit through package `__all__` lists at `src/lifx/__init__.py`
  and `src/lifx/network/mdns/__init__.py`; internalisation must update both
- Network modules use structured dictionary logging through module loggers; the aggregate
  diagnostic should follow that shape
- `IdleDeadline` owns caller overall and idle timing; goodbye expiry is subordinate to it
- `_LifxRecordCache` and its ledgers are already per-generator-call state and bounded
- Tests and documentation use synthetic identifiers and documentation-range addresses;
  no raw hardware evidence belongs in tracked artefacts

### Integration Points

- `_create_device_from_record()` propagates private mDNS connectivity into the common
  `Device` layer while remaining private with its `_LifxServiceRecord` input under D-16;
  all other construction paths retain the WiFi default
- `discover_devices_mdns()` remains the supported public mDNS path but consumes the renamed
  private generator internally
- `scripts/ipv6_thread_probe.py`, tests, and future Phase 13 record-level merge code consume
  the low-level record internally and must adopt the private names
- `docs/user-guide/advanced-usage.md`, `docs/api/network.md`, `docs/api/index.md`, and
  `examples/discovery_mdns.py` currently promote the low-level API and must be revised or
  removed from that public surface

</code_context>

<specifics>
## Specific Ideas

- The exact public values are lowercase `"wifi"` and `"thread"`.
- `tm=2` is the only Thread sentinel; the implementation does not attempt tolerant integer
  parsing and does not treat malformed values as exceptional.
- Address tests assert set membership and selected address class, not tuple byte order.
- The required cache-flush diagnostic reason is exactly `unexpected_cache_flush`.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within the amended Phase 11 boundary.

</deferred>

---

*Phase: 11-mdns-hardening*
*Context gathered: 2026-08-28*
