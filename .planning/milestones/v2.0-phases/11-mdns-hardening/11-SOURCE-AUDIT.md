# Phase 11 Multi-Source Coverage Audit

**Reconciled:** 2026-08-28 under D-15 and D-16. Executed Plans 11-01 through 11-06,
their summaries, review narration, and implementation commits remain immutable historical
evidence; Plan 11-07 amends only current authority and guidance pending independent
re-verification.

| SOURCE | ID | Feature / requirement | Plan | Status | Notes |
|---|---|---|---|---|---|
| GOAL | - | Broadcast-grade per-sweep mDNS quality before default promotion | 11-01..11-07 | COVERED | Existing implementation plus D-15/D-16 authority closure; no merged discovery enters Phase 11. |
| REQ | MDNS-01 | Real ephemeral-port legacy-unicast receipt proof | 11-01, 11-06 | COVERED | Real IPv4 loopback datagram; no port 5353 or daemon dependency. |
| REQ | MDNS-02 | `Device.connectivity` and private raw record/generator/converter | 11-01, 11-04..11-07 | COVERED | D-16 aligns authority with the existing private `_LifxServiceRecord`, `_discover_lifx_services`, and `_create_device_from_record`; device-level discovery remains supported. |
| REQ | MDNS-03 | Cross-packet accumulation and exact-once emission | 11-02, 11-03 | COVERED | Multi-value cache, packet permutations, and concurrent-call isolation remain unchanged. |
| REQ | MDNS-04 | Bounded follow-up A/AAAA queries | 11-03, 11-07 | COVERED | Existing two-attempt/64-target ceiling remains; D-15 additionally suppresses follow-up from incomplete overflow state. |
| REQ | MDNS-05 | Bounded advertised-address admission and fail-closed selection | 11-02, 11-03, 11-07 | COVERED | Exact duplicates refresh; 256 identities per owner and 1,024 per sweep; unseen excess is counted without eviction; permanent per-call overflow blocks selection, resolution, and follow-up. |
| REQ | MDNS-06 | Strict TXT serial validation and conflict recovery | 11-02, 11-03 | COVERED | Exact identity validation and goodbye-expiry recovery remain unchanged. |
| REQ | MDNS-07 | Goodbye grace, rescue, and cache-flush handling | 11-03 | COVERED | Per-sweep monotonic expiry remains subordinate to caller deadlines; overflow remains permanent for the call. |
| REQ | MDNS-08 | Honest supported/private documentation | 11-04, 11-06, 11-07 | COVERED | D-16 aligns documentation with the private converter and supported device-level paths. |
| RESEARCH | RR identity | Multi-value cache keyed by complete RR identity | 11-02, 11-03 | COVERED | `_CachedResourceRecord` and exact positive/goodbye transitions remain current. |
| RESEARCH | Deadline ownership | Expiry and overflow remain subordinate to `IdleDeadline` | 11-03, 11-07 | COVERED | Neither expiry nor capacity handling extends the caller deadline; all state is discarded per call. |
| RESEARCH | Address modelling | Unordered admitted membership and class-aware selection | 11-02, 11-07 | COVERED | D-15 bounds admission; selection retains IPv4, ULA, GUA, then scoped link-local order only for complete state. |
| RESEARCH | Diagnostics | Stable privacy-safe per-sweep counts | 11-03, 11-07 | COVERED | Reason/type/count only, including capacity rejection; no live identifier enters diagnostics. |
| RESEARCH | Cache DoS | Bound attacker-controlled address cardinality and refuse incomplete state | 11-02, 11-03, 11-07 | COVERED | TXT/SRV retain independent ceilings; D-15 supplies exact A/AAAA deduplication, 256/1,024 ceilings, permanent overflow, and fail-closed consumption. |
| RESEARCH | TXT ambiguity | Full-live-set consensus rather than packet-order winner | 11-02, 11-03 | COVERED | Conflicting product, firmware, connectivity, target, or port remains unresolved until expiry leaves a consistent value. |
| RESEARCH | Public cutover | Keep raw record, generator, and converter internal | 11-04..11-07 | COVERED | D-16 supersedes the earlier preserved-public-factory interpretation; defining-module private imports and device-level public APIs are current. |
| REVIEW | TXT/SRV admission and non-displacement | First-admitted identity ceilings and live-set consensus | 11-02, 11-03 | COVERED | Later attacker-controlled identities cannot displace admitted state or become effective sources. |
| REVIEW | Address residual | Reconcile A/AAAA memory bounds with the original D-05 direction | 11-02, 11-03, 11-07 | COVERED | The original unlimited/lossless interpretation is superseded by D-15's bounded fail-closed policy; pending-only expiry keeps CPU work bounded. |
| REVIEW | Expiry scheduling | Avoid scanning all retained records on each wake | 11-03 | COVERED | Pending-goodbye indexing drives expiry with scale regression evidence. |
| REVIEW | Diagnostic privacy | Aggregate identifier-bearing failure paths | 11-03, 11-07 | COVERED | Parser and capacity events contain reason/type/count only; operator provenance remains external. |
| REVIEW | Recoverable parser failures | Exact exception tuple | 11-03 | COVERED | Only `ValueError`, `IndexError`, and `struct.error` are recoverable parser failures. |
| REVIEW | Compatibility | Defaults, constructor propagation, and full-suite gate | 11-01, 11-02, 11-07 | COVERED | WiFi and empty-address defaults remain; Plan 11-07 reruns the complete frozen suite. |
| REVIEW | Connectivity hand-off | Type-strict setter and metadata adoption | 11-01 | COVERED | Literal runtime validation and metadata adoption remain unchanged. |
| REVIEW | API cutover scope | Private conversion helper with its private record type | 11-05..11-07 | COVERED | The earlier public-factory expectation is superseded by D-16; structured surface tests prove no converter alias is exported. |
| REVIEW | Non-vacuous assertions | Positive schema/count and replay checks | 11-02, 11-03 | COVERED | Rejected replay increments counts without mutating membership. |
| REVIEW | Documentation coherence | Describe only landed behaviour | 11-04..11-07 | COVERED | Current documentation follows D-15/D-16 while executed history remains unchanged. |
| REVIEW | Deterministic timing | Explicit monotonic advances and event-loop barriers | 11-03 | COVERED | Timing tests remain packet-order independent. |
| REVIEW | Final audit | Structured phase-contract and privacy evidence | 11-06, 11-07 | COVERED | Existing surface tests plus value-suppressed range/diff inspection are mandatory proof. |
| CONTEXT | D-01 | Public literal connectivity property | 11-01 | COVERED | One-way public values remain unchanged. |
| CONTEXT | D-02 | Only exact private value `2` selects Thread | 11-01 | COVERED | All other values map to WiFi without a rejection diagnostic. |
| CONTEXT | D-03 | Private record and generator without aliases | 11-04..11-07 | COVERED + SUPPLEMENTED | Named removals remain active; D-16 supplements them by making the converter private too. |
| CONTEXT | D-04 | No public transport enum or raw metadata | 11-04, 11-05 | COVERED | Export and documentation assertions enforce this. |
| CONTEXT | D-05 | Original unlimited advertised-address retention | 11-02, 11-03 | SUPERSEDED | D-15 replaces the unlimited aspect after developer review; unordered membership and class selection remain for complete admitted state. |
| CONTEXT | D-06 | Packet source separate from advertised addresses | 11-02 | COVERED | Fallback evidence remains outside the record address set. |
| CONTEXT | D-07 | IPv4, ULA, GUA, scoped-link-local preference | 11-02, 11-07 | COVERED | Applied only when D-15 admission state is complete; unscoped link-local remains ineligible. |
| CONTEXT | D-08 | One aggregate DEBUG event per sweep | 11-03 | COVERED | Stable reason/type/count entries. |
| CONTEXT | D-09 | No live identifiers in diagnostics | 11-03, 11-06, 11-07 | COVERED | Automated inspection is value-suppressed and operator provenance remains outside the repository. |
| CONTEXT | D-10 | Non-Thread metadata is valid WiFi | 11-01, 11-03 | COVERED | Mapping and diagnostic-absence assertions remain. |
| CONTEXT | D-11 | One-second goodbye grace and rescue | 11-03 | COVERED | Exact RR identity and monotonic expiry remain. |
| CONTEXT | D-12 | Live conflict invalidation and expiry recovery | 11-02, 11-03 | COVERED | Resolution derives only from current consistent state. |
| CONTEXT | D-13 | Goodbye work never extends caller deadlines | 11-03 | COVERED | Expiry only shortens receive timeout. |
| CONTEXT | D-14 | Cache-flush bit counted but not applied | 11-03 | COVERED | Otherwise usable records are processed normally. |
| CONTEXT | D-15 | Exact address ceilings and fail-closed overflow | 11-07 | COVERED | Primary authority, current guidance, source constants, and owner/sweep overflow tests align. |
| CONTEXT | D-16 | Private record-to-device conversion | 11-07 | COVERED | No public or compatibility alias; existing package-surface test is the executable proof. |
| SPEC EDGE | R1 | Port boundary | 11-01 | COVERED | Port is 1..65535 and never 5353. |
| SPEC EDGE | R2 | Connectivity and private API boundary/empty/encoding | 11-01, 11-04..11-07 | COVERED | Exact mapping plus D-16 private record/generator/converter and supported device APIs. |
| SPEC EDGE | R3 | Replay, incomplete input, ordering, idempotency, concurrency | 11-02, 11-03 | COVERED | Five explicit truths remain. |
| SPEC EDGE | R4 | Follow-up idempotency | 11-03, 11-07 | COVERED | Two attempts, 64 targets, no repeat after success, and none from incomplete D-15 state. |
| SPEC EDGE | R5 | Deduplication, exact ceilings, overflow, ordering | 11-02, 11-07 | COVERED | Seven current truths cover 256/1,024 admission, permanent overflow, no selection/resolution/follow-up, and class order. |
| SPEC EDGE | R6 | Conflict adjacency/empty/encoding/ordering | 11-02, 11-03 | COVERED | Four explicit truths remain. |
| SPEC EDGE | R7 | Grace empty/ordering/idempotency/concurrency | 11-03 | COVERED | Five explicit truths remain. |
| SPEC EDGE | Totals | Applicable and dismissed edge classes | 11-01..11-07 | COVERED | 29/29 applicable truths covered; six non-applicable rows retain their recorded rationale. |
| SPEC PROHIBITION | P1 | No 5353 bind or multicast join | 11-01, 11-06 | COVERED | Real socket and structured AST proof. |
| SPEC PROHIBITION | P2 | No public raw record/generator/converter/enum/key | 11-04..11-07 | COVERED | D-16 and package-surface tests enforce the boundary. |
| SPEC PROHIBITION | P3 | No expansion of the private abbreviation | 11-04, 11-06 | COVERED | Exact mapping and documentation assertions. |
| SPEC PROHIBITION | P4 | No cache-flush replacement | 11-03, 11-06 | COVERED | Behavioural proof remains. |
| SPEC PROHIBITION | P5 | No routing/retry/tuning effect from connectivity | 11-01, 11-06 | COVERED | Phase 14 remains the evidence-gated owner. |
| SPEC PROHIBITION | P6 | No use of incomplete D-15 state | 11-07 | COVERED | Owner overflow or sweep exhaustion cannot select, resolve, or trigger follow-up. |
| SPEC PROHIBITION | P7 | No live identifiers or raw discovery output | 11-01..11-07 | COVERED | Synthetic fixtures and value-suppressed automated inspection cover this boundary; operator attestation remains external and unissued. |
| DETECTOR | API coverage | No external integration capability matrix | COVERAGE.md, 11-06, 11-07 | COVERED | This dependency-free LAN protocol phase adds no SDK, hosted service, endpoint, webhook, account, secret, dashboard, or user setup. |
| DETECTOR | Assumption delta | `one-second` is a duration | 11-06, 11-07 | UNCHANGED | It does not alter the identity model or require a contribution decision. |
| DETECTOR | API surface | `API-SURFACE.md` zero-symbol output is non-authoritative | 11-05..11-07 | EXCLUDED AS AUTHORITY | Runtime imports, explicit `__all__`, and the structured D-16 surface test determine the contract. |
| DETECTOR | Codebase drift | Codebase map is advisory | 11-01..11-07 | COVERED | Current source, review evidence, and executable tests take precedence. |

No source item is missing or unplanned. Deferred and other-phase features remain excluded by
the Phase 11 SPEC.
