# Phase 11: mDNS Hardening - Research

**Researched:** 2026-08-28
**Domain:** RFC 6762 legacy-unicast DNS-SD cache hardening, public device metadata, and synthetic network validation
**Confidence:** HIGH

> **Authority amendment — 2026-08-28:** D-15 and D-16 are the current developer
> authority for address admission and record conversion. They supersede the original
> D-05 unlimited-address recommendation and the later integration interpretation that
> preserved a public factory. Historical investigation below remains useful only where
> it is read with these supersessions: admitted A/AAAA state is capped at 256 identities
> per owner and 1,024 per sweep and fails closed after permanent per-call overflow, while
> `_LifxServiceRecord`, `_discover_lifx_services`, and `_create_device_from_record` remain
> private together with no compatibility aliases.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

### Public connectivity API

- **D-01:** Every `Device` exposes `connectivity` typed as
  `Literal["wifi", "thread"]`. — **Reversibility:** one-way — callers may persist, compare,
  and branch on these exact public string values after v2.0 ships.
- **D-02:** Exact private TXT `tm=2` maps to `"thread"`; every other value, including
  missing, malformed, unrecognised, and exact `tm=1`, maps to `"wifi"`. Devices constructed
  outside mDNS default to `"wifi"`.
- **D-03 (supplemented by D-16):** `LifxServiceRecord` and `discover_lifx_services()` become explicitly private
  `_LifxServiceRecord` and `_discover_lifx_services`. Remove them from top-level and mDNS
  package exports, public API docs, user-guide coverage, and examples. Do not leave
  compatibility aliases. — **Reversibility:** one-way — this deliberately breaks the
  documented v1.x low-level API and downstream code must move to device-level discovery.
- **D-04:** Do not introduce or expose `TransportMethod`, raw `tm`, or another connectivity
  enum. The raw wire key remains an internal implementation detail and its abbreviation is
  never expanded.

### Internal address semantics

- **D-05 (superseded by D-15):** The original decision directed unlimited retention of
  syntactically valid A/AAAA addresses. D-15 replaces only that cardinality interpretation;
  admitted addresses remain an unordered internal collection and `Device` continues exposing
  only its selected `ip`.
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
- **D-15:** Admit exact-deduplicated A/AAAA identities up to 256 per owner and 1,024 per
  discovery sweep. An unseen over-cap identity is rejected and counted without eviction;
  owner overflow or sweep exhaustion is permanent for that call. Incomplete state cannot
  select an address, resolve a record, or trigger address follow-up work. Caller deadlines
  remain unchanged and all per-call state is discarded when discovery ends.
- **D-16:** `_LifxServiceRecord`, `_discover_lifx_services`, and
  `_create_device_from_record` remain private together. No public or compatibility alias is
  restored; supported callers use `discover_devices_mdns()` or `lifx.api.discover_mdns()`.

### the agent's Discretion

- The concrete internal collection type for retained addresses
- The timer/expiry data structure used for one-second goodbye grace, provided it remains
  per-sweep and does not extend caller deadlines
- The complete stable rejection-reason vocabulary beyond the locked
  `unexpected_cache_flush` name
- The private storage and constructor plumbing behind the read-only-looking
  `Device.connectivity` property

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within the amended Phase 11 boundary.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| MDNS-01 | Prove the existing ephemeral legacy-unicast bind with a real loopback datagram test that never binds 5353. | Use the already-open transport socket, obtain its OS-selected port with `getsockname()`, send one synthetic loopback datagram, and assert receipt. [VERIFIED: src/lifx/network/mdns/transport.py:91-130] [CITED: https://docs.python.org/3.10/library/socket.html#socket.socket.getsockname] |
| MDNS-02 | Expose device-level connectivity and internalise the raw mDNS record/generator/converter API. | Add a keyword-only connectivity parameter through the complete device subclass constructor lattice; map only exact private `tm=2` to `"thread"`; keep `_LifxServiceRecord`, `_discover_lifx_services`, and `_create_device_from_record` private in their defining modules with no aliases, and retain only device-level discovery as supported API. [VERIFIED: .planning/phases/11-mdns-hardening/11-CONTEXT.md] |
| MDNS-03 | Accumulate one service instance across multiple response packets. | Retain the existing per-sweep cache architecture and complete-RR identity model. TXT/SRV retain their independent ceilings; A/AAAA admission follows D-15's exact-deduplicated 256-per-owner and 1,024-per-sweep bounds and permanently fails closed on overflow. [VERIFIED: src/lifx/network/mdns/discovery.py] |
| MDNS-04 | Follow up an unresolved SRV target with A and AAAA queries. | Preserve `pending_targets()` and the existing exact bounds: at most `64` admitted targets and `2` attempts per target. [VERIFIED: src/lifx/network/mdns/discovery.py:505-545] |
| MDNS-05 | Bound valid-address admission and select only from complete state by the locked class order. | Deduplicate exact identities; admit at most 256 per owner and 1,024 per sweep; make overflow permanent for the call; count capacity rejection without identifiers; and refuse selection, resolution, or follow-up from incomplete state. Within complete admitted state, use unordered membership and classify ULA by explicit `fc00::/7` membership, GUA with `is_global`, and link-local usability with `scope_id`. [CITED: https://www.rfc-editor.org/rfc/rfc4193.html#section-3.1] [CITED: https://docs.python.org/3.10/library/ipaddress.html] |
| MDNS-06 | Reject broadcast-invalid TXT IDs and recover from live conflicts after goodbye expiry. | Extract every `id=` string rather than trusting the parser's last-wins `pairs` dictionary; validate exact 12-hex, unicast, non-zero identity; resolve only when exactly one live valid ID remains. [VERIFIED: src/lifx/network/mdns/dns.py:219-247] [VERIFIED: src/lifx/network/discovery.py:361-387] |
| MDNS-07 | Implement one-second goodbye grace/rescue and ignore unexpected legacy-unicast cache-flush semantics. | Key cache entries by RR identity `(name, type, class-without-flush, rdata)`, attach optional monotonic expiry, wake the receive loop for the next expiry without touching `IdleDeadline`, and count cache-flush observations only. [CITED: https://www.rfc-editor.org/rfc/rfc6762.html#section-10.1] [CITED: https://www.rfc-editor.org/rfc/rfc6762.html#section-10.2] |
| MDNS-08 | Make documentation match the unicast-only implementation and public API. | Preserve the already-accurate transport overview, extend internal docstrings with the complete unicast-only/cache limitation, document `Device.connectivity`, remove low-level API pages/examples, and audit internal scripts plus repository guidance for renamed symbols. [VERIFIED: src/lifx/network/mdns/transport.py:1-14] [VERIFIED: .planning/phases/11-mdns-hardening/11-SPEC.md:56-59] [VERIFIED: docs/user-guide/advanced-usage.md:40-74] |
</phase_requirements>

## Summary

Phase 11 should be planned as one cohesive change to the per-sweep mDNS cache model, followed by public device plumbing and documentation cleanup. The current cache already accumulates packets and bounds its tables, but it stores only one TXT, SRV, and A value per owner name; that representation cannot express conflicting live IDs, multiple A records, exact goodbye matching, or rescue of one RR without affecting its siblings. [VERIFIED: src/lifx/network/mdns/discovery.py:78-173]

The recommended implementation is a multi-value cache with bounded distinct-owner admission and per-call lifetime. Its entries retain the parsed value, raw RR identity, and an optional monotonic expiry. TXT and SRV keep their existing independent identity ceilings. A/AAAA identities are exact-deduplicated and admitted only up to 256 per owner and 1,024 per sweep; an unseen excess identity is counted without eviction and permanently marks the affected owner or sweep incomplete for that call. Incomplete state cannot select, resolve, or schedule follow-up work. `ttl == 0` marks only the matching admitted TXT/SRV/A/AAAA entry for expiry one second later; an identical positive-TTL reannouncement clears that expiry without consuming capacity. The discovery loop must include the nearest goodbye expiry in its receive timeout calculation, but expiry processing and overflow handling must not call `IdleDeadline.mark_response()` or move either caller deadline. All state is discarded when the call ends. [CITED: https://www.rfc-editor.org/rfc/rfc6762.html#section-10.1] [VERIFIED: src/lifx/network/mdns/discovery.py]

The public surface change is deliberately small: every device gains a read-only-looking `connectivity` property with exactly `"wifi"` or `"thread"`, while raw records remain internal. The larger plumbing cost is that five specialised device classes spell out and forward the base constructor signature, so all of them must accept and forward the new keyword or mDNS construction will work only for plain `Device`/`Light`. [VERIFIED: src/lifx/devices/infrared.py:88-113] [VERIFIED: src/lifx/devices/hev.py:113-138] [VERIFIED: src/lifx/devices/multizone.py:227-252] [VERIFIED: src/lifx/devices/matrix.py:393-418] [VERIFIED: src/lifx/devices/ceiling.py:356-395]

**Primary recommendation:** implement and test the timed multi-value cache first, then layer address selection/identity validation, device connectivity plumbing, diagnostics, API internalisation, and documentation on that stable core. [ASSUMED]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Datagram bind and receipt proof | Network transport | Test suite | `MdnsTransport` owns the socket and the test observes its actual bound port and receive queue. [VERIFIED: src/lifx/network/mdns/transport.py:88-130] |
| RR accumulation, goodbye grace, conflict recovery | Network discovery/cache | DNS parser | The parser exposes `ttl`, `rdata`, parsed data, and `cache_flush`; the per-sweep cache owns temporal meaning and resolution. [VERIFIED: src/lifx/network/mdns/dns.py:111-139] |
| Address retention and selection | Network discovery/cache | Shared address utilities | Selection occurs before device construction, while `validate_address()` remains the final device-address gate. [VERIFIED: src/lifx/network/mdns/discovery.py:201-232] [VERIFIED: src/lifx/network/address.py:76-133] |
| Public connectivity metadata | Device layer | mDNS discovery adapter | mDNS maps the private TXT value, while `Device` exposes the stable public property and non-mDNS construction supplies the WiFi default. [VERIFIED: .planning/phases/11-mdns-hardening/11-CONTEXT.md:94-107] |
| Aggregate rejection diagnostics | Discovery generator | Cache validators | Counters are per call and the generator emits one identifier-free summary when the sweep finishes. [VERIFIED: .planning/phases/11-mdns-hardening/11-CONTEXT.md:120-130] |
| Public API/docs cleanup | Package exports and documentation | Internal scripts/tests | D-16 keeps the record, low-level generator, and converter private in their defining modules; supported device-level discovery and `Device.connectivity` remain public. Historical exports are removed without aliases. [VERIFIED: src/lifx/network/mdns/__init__.py] |

## Project Constraints (from AGENTS.md)

- Use Australian English in code, comments, tests, documentation, and planning artefacts. [VERIFIED: user-provided AGENTS instructions] [VERIFIED: .planning/phases/11-mdns-hardening/11-SPEC.md:101-103]
- Preserve the supported Python range verbatim: `"Programming Language :: Python :: 3.10"`, `"3.11"`, `"3.12"`, `"3.13"`, and `"3.14"`; the runtime remains built on stdlib `asyncio`. [VERIFIED: pyproject.toml:6-7] [VERIFIED: pyproject.toml:22-26]
- Add no runtime dependency: the project declaration is verbatim `dependencies = []`, and Python dependencies are managed only with `uv`. [VERIFIED: pyproject.toml:6-7] [VERIFIED: AGENTS.md:48-65]
- Put all imports at module tops and use the existing Ruff/Pyright/Pytest toolchain. [VERIFIED: user-provided AGENTS instructions] [VERIFIED: AGENTS.md:70-101]
- Never commit real device serials/MACs, IP addresses, hostnames, account names, or raw discovery output; tests and docs must use clearly synthetic identifiers and non-live example addresses, and staged evidence must be privacy-audited. [VERIFIED: AGENTS.md:17-38]
- Do not edit generated protocol/product files manually and do not update `docs/changelog.md` manually. [VERIFIED: AGENTS.md:135-149] [VERIFIED: AGENTS.md:411-414]
- User-visible serials, labels, locations, groups, and similar fields must be strings rather than bytes. [VERIFIED: AGENTS.md:413-415]
- Any commit must use a Conventional Commit message and `git commit -S -s`; planning metadata is not a commit scope. [VERIFIED: AGENTS.md:40-46]

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python standard library | 3.10-compatible; tested through 3.14 | `asyncio`, `socket`, `ipaddress`, `time`, `collections.Counter`, dataclasses, typing | These modules already implement the required UDP, monotonic-clock, address, aggregation, and type primitives without changing the zero-dependency contract. [VERIFIED: pyproject.toml:6-7] [CITED: https://docs.python.org/3.10/library/asyncio-eventloop.html] |
| Existing DNS parser | in-repo | Decode DNS packets and expose RR identity inputs | It already preserves `name`, `rtype`, `rclass`, `ttl`, raw `rdata`, parsed data, and cache-flush state; extend cache interpretation rather than replacing the parser. [VERIFIED: src/lifx/network/mdns/dns.py:111-139] |
| Existing `IdleDeadline` | in-repo | Bound overall and idle collection time | The generator already owns caller deadline semantics; goodbye scheduling must be clamped inside, not replace or extend, this abstraction. [VERIFIED: src/lifx/network/mdns/discovery.py:380-411] |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Pytest | 9.1.1 locked | Synthetic packet/cache tests and real loopback UDP transport test | Every behavioural acceptance criterion; current focused baseline is 151 passing tests. [VERIFIED: uv.lock:820-823] [VERIFIED: local `uv run --frozen pytest tests/test_network/test_mdns -q --no-cov`, 2026-08-28] |
| pytest-asyncio | 1.4.0 locked | Async generator and datagram tests | Transport and discovery loop tests. [VERIFIED: uv.lock:838-842] |
| Ruff | 0.15.20 locked | Formatting/import/lint gate | Per task and phase gate. [VERIFIED: uv.lock:1026-1029] |
| Pyright | 1.1.411 locked | Constructor and `Literal` propagation checks | Especially the specialised device constructor lattice and private record annotations. [VERIFIED: uv.lock:807-810] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Distinct-owner-bounded dictionaries plus monotonic expiry | Heap-based timer queue | A heap helps long-lived caches, but this cache lasts one sweep and only needs one-second goodbye deadlines. Pending-expiry indexing remains subordinate to the caller deadline; D-15 separately caps exact-deduplicated A/AAAA identities at 256 per owner and 1,024 per sweep and makes overflow fail closed. [VERIFIED: src/lifx/network/mdns/discovery.py] |
| `frozenset[str]` record addresses | `set[str]` or tuple | A frozen record already has custom serial equality/hash; `frozenset` represents unordered uniqueness without leaking mutable cache state. [VERIFIED: src/lifx/network/mdns/types.py:9-35] [ASSUMED] |
| Explicit ULA prefix membership | `IPv6Address.is_private` | Python documents maintenance changes to `is_private`/`is_global`; `fc00::/7` is the protocol-defined ULA range and avoids misclassifying other special-use IPv6 space as ULA. [CITED: https://docs.python.org/3.10/library/ipaddress.html] [CITED: https://www.rfc-editor.org/rfc/rfc4193.html#section-3.1] |

**Installation:** none. The phase must add no package and therefore requires no Package Legitimacy Audit. The project declaration remains verbatim `dependencies = []`. [VERIFIED: pyproject.toml:6-7]

## Architecture Patterns

### System Architecture Diagram

```text
PTR query from ephemeral UDP socket
        │
        ▼
legacy-unicast DNS response ──► existing DNS parser
        │                           │
        │                           ▼
        │                 RR validation + diagnostic counts
        │                           │
        │                           ▼
        │                 bounded per-sweep RR cache
        │                  ├─ positive RR: add/rescue
        │                  ├─ TTL-zero: expire in 1 s
        │                  └─ cache-flush: count, do not flush
        │                           │
        │              ┌────────────┴────────────┐
        │              ▼                         ▼
        │       instance incomplete       exactly one valid ID
        │              │                         │
        │              ▼                         ▼
        │       bounded A+AAAA query     retain address set
        │                                        │
        │                                        ▼
        │                           select IPv4→ULA→GUA→scoped LL
        │                                        │
        └────────────────────────────────────────▼
                                private service record
                                         │
                                         ▼
                              device subclass construction
                                         │
                                         ▼
                          public Device(ip, connectivity)
```

This flow preserves the existing boundary: DNS parsing is stateless, `_LifxRecordCache` owns one sweep's temporal/relational state, and the high-level generator is the only public result path. [VERIFIED: src/lifx/network/mdns/dns.py:250-326] [VERIFIED: src/lifx/network/mdns/discovery.py:324-630]

### Recommended Project Structure

```text
src/lifx/
├── devices/
│   ├── base.py                 # connectivity property/default
│   └── {infrared,hev,multizone,matrix,ceiling}.py  # keyword forwarding
├── network/mdns/
│   ├── discovery.py            # timed multi-value cache, validation, diagnostics
│   ├── dns.py                  # existing wire parser; avoid semantic cache logic here
│   ├── transport.py            # truthful unicast-only documentation
│   ├── types.py                # private frozen record + unordered addresses
│   └── __init__.py             # remove low-level public exports
└── __init__.py                 # remove top-level low-level exports
tests/
├── test_network/test_mdns/     # cache, loop, RFC, diagnostics, transport
├── test_devices/               # default/property/subclass constructor coverage
├── test_api/                   # discover_mdns connectivity propagation
└── test_scripts/               # private probe imports remain functional
```

The source-to-test mirroring and mDNS test locations are existing repository conventions. [VERIFIED: AGENTS.md:277-300]

### Pattern 1: Preserve RR Identity, Then Derive Resolution

**What:** index each cacheable RR by lower-cased owner name, numeric type, class with the cache-flush bit masked, and raw `rdata`; store parsed data and optional `expires_at`. [CITED: https://www.rfc-editor.org/rfc/rfc6762.html#section-10.1] [CITED: https://www.rfc-editor.org/rfc/rfc6762.html#section-10.2]

**When to use:** for TXT, SRV, A, and AAAA records. PTR may continue to indicate service membership without entering goodbye/conflict resolution because Phase 11 explicitly scopes goodbye semantics to those four record types. [VERIFIED: .planning/phases/11-mdns-hardening/11-CONTEXT.md:132-142]

**Recommended mechanics:** a positive-TTL identical RR inserts or clears an existing goodbye expiry; a TTL-zero identical RR sets `expires_at = now + 1 second`; `expire(now)` removes elapsed entries and returns whether resolution may have changed. Do not apply positive-TTL natural expiry in this phase because the locked change is specifically goodbye grace inside a short sweep. [CITED: https://www.rfc-editor.org/rfc/rfc6762.html#section-10.1] [ASSUMED]

### Pattern 2: Derive Valid Instance State from All Live Records

**What:** resolution is a pure view over the current complete live cache: gather every admitted valid TXT ID for an instance, require exactly one, obtain product/connectivity/firmware from live TXT data, obtain SRV target/port, and select from admitted syntactically valid addresses only if neither owner nor sweep overflowed. D-15 makes any overflow permanent and blocks selection, resolution, and follow-up rather than trusting a truncated subset. [VERIFIED: .planning/phases/11-mdns-hardening/11-SPEC.md]

**Why:** current `TxtData.pairs` is last-wins, and current `_txt_by_instance` is also last-wins. Conflict detection must inspect `TxtData.strings` or preserve all TXT RRs; otherwise a malicious or malformed later ID silently replaces the first. [VERIFIED: src/lifx/network/mdns/dns.py:219-247] [VERIFIED: src/lifx/network/mdns/discovery.py:92-98]

### Pattern 3: Schedule Cache Expiry Inside, Never Beyond, Caller Deadlines

**What:** calculate the receive timeout from the minimum of caller deadline remaining, next retransmit time, and next goodbye expiry. On a timeout, determine which clock event fired, run expiry/retransmission work, and continue only while `IdleDeadline` remains live. [VERIFIED: src/lifx/network/mdns/discovery.py:375-437] [ASSUMED]

**Why:** the current timeout handler assumes every pre-deadline timeout is a retransmission slot. Adding an expiry clamp without distinguishing causes would either terminate early or skip the one-second deletion. [VERIFIED: src/lifx/network/mdns/discovery.py:429-437]

### Pattern 4: Make Connectivity a Keyword-Only Constructor Concern

**What:** store a private `_connectivity`, expose a getter-only `connectivity: Literal["wifi", "thread"]`, and add the keyword-only parameter to `Device` plus every specialised subclass signature and `super().__init__` call. [VERIFIED: .planning/phases/11-mdns-hardening/11-CONTEXT.md:94-107] [ASSUMED]

**When to use:** all construction defaults to `"wifi"`; `_create_device_from_record()` passes the internal record's mapped value. The explicit keyword avoids rebinding the positional `state_file` parameter on `CeilingLight`. [VERIFIED: src/lifx/devices/ceiling.py:356-395]

### Pattern 5: Aggregate Diagnostics at the Rejection Boundary

**What:** keep a per-generator `Counter[(reason_code, record_type)]`; validators increment it without carrying rejected values, and a single `DEBUG` event emits sorted counts when the sweep closes. [VERIFIED: .planning/phases/11-mdns-hardening/11-CONTEXT.md:120-130] [ASSUMED]

**Recommended stable vocabulary:** `missing_txt_id`, `invalid_txt_id`, `conflicting_txt_id`, `missing_product_id`, `invalid_product_id`, `conflicting_product_id`, `invalid_address`, `malformed_packet`, and locked `unexpected_cache_flush`. [ASSUMED]

The existing per-packet `parse_error` event includes `source_ip`; route record-validation failures into the new summary and ensure the summary path never copies `addr`, exception text, TXT content, names, or hashes. [VERIFIED: src/lifx/network/mdns/discovery.py:547-556]

### Anti-Patterns to Avoid

- **Keep one TXT/SRV/A per name:** overwriting removes the evidence needed for conflict and exact-goodbye semantics. [VERIFIED: src/lifx/network/mdns/discovery.py:92-103]
- **Use cache-flush as replacement:** RFC 6762 forbids the bit on this non-5353 response path; count the violation and process the record normally. [CITED: https://www.rfc-editor.org/rfc/rfc6762.html#section-6.7]
- **Delete TTL-zero immediately:** this prevents rescue and violates the locked one-second behaviour. [CITED: https://www.rfc-editor.org/rfc/rfc6762.html#section-10.1]
- **Sleep one second inside packet handling:** it blocks receipt of rescue packets and can overrun the caller deadline. Use a scheduled expiry integrated with `receive()` timing. [ASSUMED]
- **Use `Serial.from_string()` as the only mDNS ID validator:** it accepts separated serial forms, while the mDNS contract requires exactly twelve hexadecimal characters with no separators. [VERIFIED: src/lifx/protocol/models.py:109-194] [VERIFIED: .planning/phases/11-mdns-hardening/11-SPEC.md:46-49]
- **Select unscoped link-local:** `validate_address()` rejects it at device construction, producing a late failure rather than an unresolved service instance. [VERIFIED: src/lifx/network/address.py:99-110]
- **Make address tuple order an API/test contract:** the user locked set membership and class preference, not artificial within-class byte order. [VERIFIED: .planning/phases/11-mdns-hardening/11-CONTEXT.md:109-118]
- **Add compatibility aliases:** this contradicts the deliberate v2.0 removal. [VERIFIED: .planning/phases/11-mdns-hardening/11-CONTEXT.md:94-107]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| IP literal parsing and scope extraction | Colon heuristics or custom IPv6 parser | `ipaddress.ip_address`, `IPv6Address.scope_id`, explicit `fc00::/7` membership | Handles IPv4/IPv6 syntax and scoped literals consistently across supported Python versions. [CITED: https://docs.python.org/3.10/library/ipaddress.html] |
| UDP endpoint lifecycle | New transport abstraction | Existing `MdnsTransport` and `_UdpProtocol` | The existing code already handles concurrent open/close generations, bounded receive queues, errors, and cleanup. [VERIFIED: src/lifx/network/mdns/transport.py:67-178] |
| DNS wire parsing | A second phase-local decoder | Existing `parse_dns_response()` and `DnsResourceRecord` | The parser already has dedicated and adversarial tests; Phase 11 concerns cache semantics after parsing. [VERIFIED: tests/test_network/test_mdns/test_dns_adversarial.py:1-5] [VERIFIED: src/lifx/network/mdns/dns.py:250-326] |
| Wall-clock timer | `datetime`, `sleep`, or event-loop delayed callbacks detached from the sweep | `time.monotonic()` plus the existing receive loop | Monotonic time is already the discovery convention and keeps all expiry state owned by the sweep. [VERIFIED: src/lifx/network/mdns/discovery.py:357-381] |
| Rejection aggregation | Per-record logging or identifier hashes | `collections.Counter` keyed only by stable reason/type | Bounds key cardinality and enforces the privacy contract structurally. [ASSUMED] |

**Key insight:** the cache semantics are necessarily domain-specific, but the wire parser, clock, address parser, socket lifecycle, and aggregation primitives already exist; the plan should change only the layer that owns each responsibility. [VERIFIED: src/lifx/network/mdns/discovery.py:78-260]

## Runtime State Inventory

| Category | Items Found | Action Required |
|----------|-------------|-----------------|
| Stored data | None in repository scope — the renamed symbols are Python imports/exports, and repository search found no database schema, key, or persisted payload using them. [VERIFIED: repository `rg --hidden 'LifxServiceRecord\|discover_lifx_services\|TransportMethod'`, 2026-08-28] | No data migration. Update source imports and public export tests only. [VERIFIED: src/lifx/__init__.py:76-76] |
| Live service config | None in phase scope — mDNS responder, daemon, router, and hardware configuration changes are explicitly prohibited. [VERIFIED: .planning/phases/11-mdns-hardening/11-SPEC.md:61-87] | No service mutation; synthetic tests only. |
| OS-registered state | None — the phase retains the existing cross-platform wildcard ephemeral bind and does not register a daemon, multicast membership, launch service, or system unit. [VERIFIED: src/lifx/network/mdns/transport.py:91-130] [VERIFIED: .planning/phases/11-mdns-hardening/11-SPEC.md:61-87] | No OS migration. |
| Secrets/env vars | None tied to these symbol names in active source, scripts, docs, examples, CI configuration, or `pyproject.toml`. [VERIFIED: repository `rg` over active paths, 2026-08-28] | No secret/key rename. Keep hardware probe output private under the existing privacy rules. [VERIFIED: AGENTS.md:17-38] |
| Build artifacts / installed packages | The local `.venv` contains an installed editable project and bytecode caches; downstream v1.x installations may retain code importing the removed public names until upgraded. [VERIFIED: local `uv run --frozen python --version`, 2026-08-28] [ASSUMED] | Run `uv sync`/frozen validation after the rename; no committed artefact migration. Downstream import failure is the intentional v2.0 break, not an alias requirement. [VERIFIED: .planning/phases/11-mdns-hardening/11-CONTEXT.md:100-107] |

The active repository references that must move include package exports, mDNS implementation/tests, API discovery tests, `scripts/ipv6_thread_probe.py`, `tests/test_scripts/test_ipv6_thread_probe.py`, API documentation, user guide, example, `AGENTS.md`, and `CLAUDE.md`; historical `.planning` and generated changelog records must remain historical. [VERIFIED: repository active-path `rg`, 2026-08-28] [VERIFIED: AGENTS.md:411-414]

## Common Pitfalls

### Pitfall 1: Double Last-Wins Hides Conflicts

**What goes wrong:** the TXT parser's `pairs` mapping overwrites duplicate keys inside one TXT RR, and `_txt_by_instance` overwrites whole TXT RRs across packets. A conflicting ID can therefore look like one valid ID. [VERIFIED: src/lifx/network/mdns/dns.py:231-245] [VERIFIED: src/lifx/network/mdns/discovery.py:92-103]

**How to avoid:** derive `id` candidates from all live TXT RR `strings` (including repeated `id=` strings within one RR), validate each, and require the set of valid IDs to have cardinality exactly one. [ASSUMED]

**Warning signs:** tests pass when conflicts are placed in separate packets but fail when multiple TXT RRs share one response or one TXT RR has repeated keys. [ASSUMED]

### Pitfall 2: Goodbye Expiry Never Wakes the Loop

**What goes wrong:** if no packet arrives after a goodbye, `expire()` is never called, so the record never disappears and conflict recovery never occurs. [ASSUMED]

**How to avoid:** include `next_expiry - now` in the transport receive timeout and distinguish an expiry timeout from retransmit/deadline timeouts. [ASSUMED]

**Warning signs:** deterministic tests need an unrelated packet to observe expiry, or they use real one-second sleeps. [ASSUMED]

### Pitfall 3: A Rescue Re-emits an Already-Yielded Instance

**What goes wrong:** the generator yields immutable records and deduplicates by serial; it has no retraction channel. A goodbye/reannouncement for a record already yielded must not create a second public emission. [VERIFIED: src/lifx/network/mdns/discovery.py:484-503]

**How to avoid:** preserve `_resolved_instances`/`seen_serials` exact-once semantics; apply expiry-driven recovery only to unresolved/conflicted instances. [VERIFIED: .planning/phases/11-mdns-hardening/11-SPEC.md:96-99]

### Pitfall 4: Scoped Link-Local Cannot Come from AAAA Wire Data Alone

**What goes wrong:** a DNS AAAA RR carries 16 address bytes; the parser produces an unscoped string, while a usable link-local `Device` address requires a zone identifier. The current IPv4-only mDNS receive socket also supplies no IPv6 interface scope. [VERIFIED: src/lifx/network/mdns/dns.py:283-287] [VERIFIED: src/lifx/network/mdns/transport.py:94-107] [VERIFIED: src/lifx/network/address.py:99-110]

**How to avoid:** retain the unscoped address internally but never select it. Keep scoped-link-local classification support for synthetic/internal inputs, without inventing a zone or expanding into routed-interface transport work. [VERIFIED: .planning/phases/11-mdns-hardening/11-CONTEXT.md:109-118] [ASSUMED]

### Pitfall 5: Constructor Propagation Is Incomplete

**What goes wrong:** specialised devices expose explicit constructor signatures rather than `**kwargs`, so passing `connectivity=` from the factory fails unless each subclass forwards it. [VERIFIED: src/lifx/devices/infrared.py:88-113] [VERIFIED: src/lifx/devices/hev.py:113-138] [VERIFIED: src/lifx/devices/multizone.py:227-252] [VERIFIED: src/lifx/devices/matrix.py:393-418] [VERIFIED: src/lifx/devices/ceiling.py:356-395]

**How to avoid:** add parameterised tests across every product-to-device class path, plus direct default-construction tests. [ASSUMED]

### Pitfall 6: Diagnostics Reintroduce Private Data

**What goes wrong:** using current exception text or `source_ip` in the new summary defeats aggregation/privacy; hashes are explicitly forbidden too. [VERIFIED: src/lifx/network/mdns/discovery.py:547-556] [VERIFIED: .planning/phases/11-mdns-hardening/11-CONTEXT.md:120-130]

**How to avoid:** increment from enumerated branches before discarded values leave validator scope, then log only stable reason/type/count fields once. [ASSUMED]

### Pitfall 7: Address Validation and Address Selection Are Confused

**What goes wrong:** calling `validate_address()` while accumulating records rejects an unscoped link-local that the locked contract says to retain, while using only `ipaddress.is_private` cannot express the required ULA class precisely. [VERIFIED: src/lifx/network/address.py:76-133] [CITED: https://www.rfc-editor.org/rfc/rfc4193.html#section-3.1]

**How to avoid:** syntactic parsing determines retention; a separate classifier determines selectability/preference; final `Device` construction keeps the shared validation gate. [ASSUMED]

### Pitfall 8: Public Removal Misses Non-Package Consumers

**What goes wrong:** renaming only source imports leaves public API docs broken and repository hardware-probe tests importing old names. [VERIFIED: docs/api/network.md:21-31] [VERIFIED: examples/discovery_mdns.py:53-72] [VERIFIED: scripts/ipv6_thread_probe.py:80-90]

**How to avoid:** use an active-path `rg` audit after edits; update internal scripts/tests to private names, remove public guide/example coverage, and leave historical planning/changelog text unchanged. [VERIFIED: AGENTS.md:411-414] [ASSUMED]

## Code Examples

Verified patterns from authoritative sources and opened repository definitions follow.

### Exact Connectivity Mapping

The locked values are quoted verbatim: `Literal["wifi", "thread"]`, exact private `tm=2` maps to `"thread"`, and every other value maps to `"wifi"`. [VERIFIED: .planning/phases/11-mdns-hardening/11-CONTEXT.md:94-101]

```python
from typing import Literal


def _connectivity_from_txt(value: str | None) -> Literal["wifi", "thread"]:
    return "thread" if value == "2" else "wifi"
```

This helper must not emit validation diagnostics for the fallback path. [VERIFIED: .planning/phases/11-mdns-hardening/11-CONTEXT.md:126-130]

### Expiry-Aware Receive Scheduling

```python
remaining = deadline.remaining()
if retransmit_delay is not None:
    remaining = min(remaining, retransmit_delay)
if expiry_delay is not None:
    remaining = min(remaining, expiry_delay)

try:
    data, address = await transport.receive(timeout=remaining)
except LifxTimeoutError:
    cache.expire(time.monotonic())
    continue
```

The existing loop already uses `deadline.remaining()`, clamps to a retransmission delay, and catches `LifxTimeoutError`; the example adds expiry as a third wake-up source without changing the deadline object. [VERIFIED: src/lifx/network/mdns/discovery.py:409-437]

### Race-Free Ephemeral Datagram Test

The implementation's exact bind is quoted verbatim as `sock.bind(("", 0))`, and it records the chosen port with `sock.getsockname()[1]`; the same source states the socket must not share `5353`. [VERIFIED: src/lifx/network/mdns/transport.py:94-114]

```python
async with MdnsTransport() as transport:
    port = transport._socket.getsockname()[1]
    assert port != 5353
    sender.sendto(payload, (loopback_host, port))
    received, _ = await transport.receive(timeout=test_timeout)
    assert received == payload
```

The test should keep the transport socket open while sending rather than probe/free/rebind a candidate port; `getsockname()` is the standard API for discovering the port of the bound socket. [CITED: https://docs.python.org/3.10/library/socket.html#socket.socket.getsockname]

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Bind the mDNS listener to 5353 and share with a system daemon | Send from an OS-selected ephemeral port and receive the RFC 6762 legacy-unicast reply directly | Already present before Phase 11; this phase adds the real datagram regression proof | Avoids testing or contending with the runner's daemon. [VERIFIED: src/lifx/network/mdns/transport.py:94-114] [CITED: https://www.rfc-editor.org/rfc/rfc6762.html#section-6.7] |
| One cached value per owner/type | Bounded multi-value RR state with exact identity and goodbye expiry | Phase 11, amended by D-15 on 2026-08-28 | Enables conflict detection, rescue, and recovery while bounding A/AAAA at 256 per owner and 1,024 per sweep and failing closed after overflow. [VERIFIED: .planning/phases/11-mdns-hardening/11-SPEC.md] |
| Low-level record/generator/converter publicly exported and documented | High-level `discover_mdns()` plus `Device.connectivity`; `_LifxServiceRecord`, `_discover_lifx_services`, and `_create_device_from_record` private | Phase 11 / D-16 on 2026-08-28 | Deliberate public API break with no alias. [VERIFIED: .planning/phases/11-mdns-hardening/11-CONTEXT.md] |
| Cache-flush replacement semantics proposed in earlier research | Cache-flush is forbidden on legacy-unicast; count only, retain normally | Context amendment on 2026-08-28 | Prevents applying multicast replacement rules to the wrong transport path. [VERIFIED: .planning/phases/11-mdns-hardening/11-CONTEXT.md:139-142] [CITED: https://www.rfc-editor.org/rfc/rfc6762.html#section-10.2] |

**Deprecated/outdated:**

- Public `LifxServiceRecord` and `discover_lifx_services()` references in `src/lifx/__init__.py`, `src/lifx/network/mdns/__init__.py`, docs, examples, `AGENTS.md`, and `CLAUDE.md` must be removed or changed to private internal terminology. [VERIFIED: repository active-path `rg`, 2026-08-28]
- The transport overview is already truthful about ephemeral IPv4 multicast queries and legacy-unicast replies; Phase 11 must extend internal documentation with the explicit no-membership, no-unsolicited-announcement, non-reusable-cache, and no-cache-flush limitations without regressing that accurate description. [VERIFIED: src/lifx/network/mdns/transport.py:1-14] [VERIFIED: .planning/phases/11-mdns-hardening/11-SPEC.md:56-59]
- Earlier roadmap/research wording that exposed or expanded `tm`, imposed deterministic address tuple order, or applied cache-flush replacement is superseded by the Phase 11 context/spec amendments. [VERIFIED: .planning/phases/11-mdns-hardening/11-CONTEXT.md:68-85]
- The original D-05 unlimited-address recommendation and the later public-factory integration interpretation are superseded by D-15/D-16; they are historical evidence, not current execution guidance. [VERIFIED: .planning/phases/11-mdns-hardening/11-CONTEXT.md]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Use bounded dictionaries with optional monotonic expiry rather than a timer heap. | Standard Stack / Architecture | Low: either structure can satisfy the locked per-sweep behaviour, but a heap may add unnecessary invalidation complexity. |
| A2 | Use `frozenset[str]` for `_LifxServiceRecord.addresses`. | Standard Stack / Requirements | Low: the concrete internal collection is planner discretion; tests must compare membership, not type/order. |
| A3 | Do not implement natural positive-TTL expiry; implement only locked one-second goodbye expiry within the short sweep. | Architecture Pattern 1 | Medium: expanding to all TTL expiry changes more state transitions and tests; the phase acceptance criteria name goodbye behaviour specifically. |
| A4 | Store connectivity privately and expose a getter-only property; pass it keyword-only through every constructor. | Architecture Pattern 4 | Low: alternate storage can work, but keyword-only propagation protects positional compatibility. |
| A5 | Use the proposed nine-code rejection vocabulary. | Architecture Pattern 5 | Medium: diagnostics tests will lock these names; the planner added `conflicting_product_id` and resolved whole-packet aggregation before implementation. |
| A6 | Preserve first-learned selection within an address class while testing only class priority and set membership. | Address selection | Low: the user deliberately left the remaining tie-breaker to planning and prohibited artificial ordering tests. |
| A7 | Inspect repeated `id=` strings within one TXT RR as well as multiple TXT RRs. | Pitfall 1 | Low: it is stricter than the minimum synthetic conflict case and closes the parser's observable last-wins gap. |
| A8 | Integrate the nearest goodbye expiry into the receive timeout rather than sleeping or requiring another packet to drive expiry. | Architecture Pattern 3 / Pitfall 2 | Medium: another scheduler can satisfy the requirement, but detached sleeps complicate deadline ownership and rescue receipt. |
| A9 | Use a sorted per-sweep `Counter[(reason, type)]`, include malformed packets as `malformed_packet`/`PACKET`, and emit it once. | Diagnostics / Resolved Research Questions | Resolved: Plan 11-03 adopts this privacy-safe aggregate handling. |
| A10 | For the sole valid ID, require product consensus across valid identity-bearing TXT RRs, then derive firmware and connectivity from the lexicographically least complete RR identity. | Resolved Research Questions | Resolved: Plan 11-02 locks a packet-order-independent canonical source and permutation tests. |
| A11 | Treat local installed/bytecode artefacts as disposable and require `uv sync`/frozen validation rather than a committed migration; assume downstream v1.x importers upgrade for the v2.0 break. | Runtime State Inventory | Low: compatibility aliases are explicitly forbidden, so no source migration path exists for third-party callers. |
| A12 | The focused Darwin baseline is sufficient to mark IPv4 loopback available locally; CI covers the other supported platforms, and the research remains current for 30 days unless an adjacent phase changes the seam. | Environment / Metadata | Low: environment and neighbouring branches can drift, so execution must recheck them. |
| A13 | Sequence cache tests before plumbing/docs, test every specialised constructor path, and finish with an active-path `rg` audit. | Primary Recommendation / Pitfalls | Low: this is planning structure rather than product behaviour. |

## Resolved Research Questions

1. **Malformed whole DNS packets join the same aggregate as semantic record rejections. — RESOLVED**
   - What we know: the current broad handler logs `parse_error`, exception text, and source IP per packet, while the locked diagnostic schema permits only reason and record type. [VERIFIED: src/lifx/network/mdns/discovery.py:547-556] [VERIFIED: .planning/phases/11-mdns-hardening/11-CONTEXT.md:120-130]
   - Resolution: count malformed packets under stable reason `malformed_packet` with record type `PACKET`, remove identifier-bearing fields from this recoverable path, and retain one per-sweep aggregate. Plan 11-03 implements and permutation-tests this choice. [ASSUMED]

2. **Multiple live non-ID TXT records use product consensus plus a canonical RR. — RESOLVED**
   - What we know: only `id` conflict semantics and exact `tm` mapping are locked; the current parser is last-wins within a TXT RR and the cache is last-wins across TXT RRs. [VERIFIED: src/lifx/network/mdns/dns.py:231-245] [VERIFIED: src/lifx/network/mdns/discovery.py:183-200]
   - Resolution: inspect every live TXT RR carrying the sole valid ID. Reject an individual identity-bearing RR whose required product is absent or invalid. The remaining valid product values must agree; differing valid products leave the instance unresolved with `conflicting_product_id`. Among product-consistent identity-bearing RRs, select the lexicographically least complete preserved RR identity `(lower-case owner, numeric type, masked class, raw rdata)` and derive firmware plus private connectivity from it. Exact private value `2` maps to Thread and every other value maps to WiFi without a diagnostic. Plan 11-02 adds permutations with differing product, firmware, and private connectivity values so packet arrival cannot choose metadata. [ASSUMED]

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `uv` | dependency sync and every Python command | ✓ | 0.11.29 | none; project mandates uv. [VERIFIED: local `uv --version`, 2026-08-28] |
| Python | implementation/tests | ✓ | 3.14.2 locally; code targets 3.10 | CI matrix validates the remaining supported versions. [VERIFIED: local `uv run --frozen python --version`, 2026-08-28] [VERIFIED: pyproject.toml:6-7] |
| Pytest | synthetic and loopback tests | ✓ | 9.1.1 | none required. [VERIFIED: local `uv run --frozen pytest --version`, 2026-08-28] |
| Ruff | format/lint gate | ✓ | 0.15.20 | none required. [VERIFIED: local `uv run --frozen ruff --version`, 2026-08-28] |
| Pyright | type gate | ✓ | 1.1.411 | none required. [VERIFIED: local `uv run --frozen pyright --version`, 2026-08-28] |
| IPv4 loopback UDP | MDNS-01 regression | ✓ | stdlib/OS | Skip only on a platform that cannot create an IPv4 UDP socket; no daemon/hardware fallback is allowed. [VERIFIED: focused mDNS suite completed on Darwin, 2026-08-28] [ASSUMED] |

**Missing dependencies with no fallback:** none. [VERIFIED: local environment audit, 2026-08-28]

**Missing dependencies with fallback:** none. [VERIFIED: local environment audit, 2026-08-28]

## Security Domain

ASVS 5.0 reorganised the older category numbers: positive input validation is now in V2 “Validation and Business Logic”, while authentication is V6 and session management is V7. The compatibility table below retains the requested category labels but maps this phase to the current validation control. [CITED: https://github.com/OWASP/ASVS/blob/master/5.0/docs_en/OWASP_Application_Security_Verification_Standard_5.0.0_en.flat.json]

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication (4.x label) | no | No identity/account authentication is introduced; mDNS identity remains unauthenticated until the separately scoped Phase 13 unicast verification. [VERIFIED: .planning/phases/11-mdns-hardening/11-SPEC.md:76-84] |
| V3 Session Management (4.x label) | no | No browser or application session exists in this library phase. [VERIFIED: .planning/phases/11-mdns-hardening/11-SPEC.md:6-11] |
| V4 Access Control (4.x label) | no | No authorisation boundary or protected resource is introduced. [VERIFIED: .planning/phases/11-mdns-hardening/11-SPEC.md:6-11] |
| V5 Input Validation (4.x label; V2 in ASVS 5.0) | yes | Positive validation of serial shape/unicast identity, numeric product, syntactic IPs, record type, bounds, and logical TXT-ID consistency. [CITED: https://github.com/OWASP/ASVS/blob/master/5.0/docs_en/OWASP_Application_Security_Verification_Standard_5.0.0_en.flat.json] |
| V6 Cryptography (4.x label) | no | Do not add cryptography or claim mDNS authenticity; Phase 11 only rejects structurally invalid/conflicting records. [VERIFIED: .planning/phases/11-mdns-hardening/11-SPEC.md:76-84] |

### Known Threat Patterns for stdlib UDP/DNS-SD

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Spoofed or multicast/broadcast TXT identity | Spoofing | Exact 12-hex unicast serial validation aligned with broadcast rules; conflicting live IDs invalidate the instance. This is structural hardening, not authentication. [VERIFIED: src/lifx/network/discovery.py:361-387] |
| Record flood / follow-up amplification | Denial of Service (high) | D-15 exact-deduplicates A/AAAA identities, admits no more than 256 per owner and 1,024 per sweep, rejects unseen excess identities without eviction, and records privacy-safe reason/type/count diagnostics. Owner overflow or sweep exhaustion is permanent for the call; incomplete state cannot select, resolve, or trigger follow-up. The caller deadline is unchanged, all state is discarded when the call ends, and the independent 64-target/two-attempt follow-up ceiling remains. [VERIFIED: src/lifx/network/mdns/discovery.py] |
| Cache poisoning via last-wins TXT overwrite | Tampering | Preserve multiple RR identities and resolve only a logically consistent live set. [VERIFIED: src/lifx/network/mdns/discovery.py:92-103] |
| Identifier leakage through rejection logs | Information Disclosure | One identifier-free `DEBUG` summary with reason/type/count only; no source, name, value, exception string, hash, or raw packet. [VERIFIED: .planning/phases/11-mdns-hardening/11-CONTEXT.md:120-130] |
| Goodbye causing premature or permanent invalidation | Tampering / Denial of Service | One-second exact-RR grace, rescue on identical reannouncement, no deadline extension, no cache-flush replacement on legacy-unicast. [CITED: https://www.rfc-editor.org/rfc/rfc6762.html#section-10.1] [CITED: https://www.rfc-editor.org/rfc/rfc6762.html#section-10.2] |

## Sources

### Primary (HIGH confidence)

- `.planning/phases/11-mdns-hardening/11-CONTEXT.md` — locked user decisions, scope amendments, and planner discretion. [VERIFIED: .planning/phases/11-mdns-hardening/11-CONTEXT.md:1-259]
- `.planning/phases/11-mdns-hardening/11-SPEC.md` — exact requirements, acceptance criteria, prohibitions, and synthetic-only boundary. [VERIFIED: .planning/phases/11-mdns-hardening/11-SPEC.md:1-221]
- `.planning/REQUIREMENTS.md` — MDNS-01 through MDNS-08 requirement text. [VERIFIED: .planning/REQUIREMENTS.md:41-93]
- Opened mDNS transport, parser, cache/generator, address validation, device constructors, exports, docs, examples, and tests — current implementation seams and discrete values. [VERIFIED: src/lifx/network/mdns/discovery.py:1-630]

### Secondary (MEDIUM confidence)

- RFC 6762 §§6.7, 10.1, 10.2 — legacy-unicast delivery, goodbye grace/rescue, and cache-flush prohibition. [CITED: https://www.rfc-editor.org/rfc/rfc6762.html]
- RFC 4193 §3.1 — verbatim ULA prefix `FC00::/7`. [CITED: https://www.rfc-editor.org/rfc/rfc4193.html#section-3.1]
- Python 3.10 documentation — `ipaddress`, `asyncio` datagram endpoints, and `socket.getsockname()`. [CITED: https://docs.python.org/3.10/library/ipaddress.html] [CITED: https://docs.python.org/3.10/library/asyncio-eventloop.html] [CITED: https://docs.python.org/3.10/library/socket.html#socket.socket.getsockname]
- OWASP ASVS 5.0 official repository — current validation category and security taxonomy. [CITED: https://github.com/OWASP/ASVS]

### Tertiary (LOW confidence)

- Assumptions A1-A13 are explicitly isolated in the Assumptions Log; no tertiary external source is presented as authoritative. [ASSUMED]

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH — no new package; all runtime/test primitives and locked versions were read from the repository and verified locally. [VERIFIED: pyproject.toml:1-129]
- Architecture: HIGH — the current parser/cache/generator/constructor/export seams were opened in full, and the protocol behaviour was checked against official RFC text. [VERIFIED: src/lifx/network/mdns/discovery.py:1-630] [CITED: https://www.rfc-editor.org/rfc/rfc6762.html]
- Pitfalls: HIGH — most are direct consequences of opened last-wins storage, timer flow, constructor signatures, and docs/import references; speculative recommendations are marked `[ASSUMED]`. [VERIFIED: src/lifx/network/mdns/discovery.py:78-260]
- Security: MEDIUM — input and privacy controls are locked and verified, while full authenticity remains explicitly deferred to Phase 13. [VERIFIED: .planning/phases/11-mdns-hardening/11-SPEC.md:76-84]

**Research date:** 2026-08-28
**Valid until:** 2026-09-27 (stable protocol and in-repo architecture; re-read if Phase 10/12 changes the mDNS seams before planning). [ASSUMED]
