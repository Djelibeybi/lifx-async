# Phase 11: mDNS Hardening - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-28
**Phase:** 11-mdns-hardening
**Areas discussed:** Public type exposure, address tuple semantics, invalid-record
diagnostics, conflict recovery

---

## Public Type Exposure

### Transport metadata surface

| Option | Description | Selected |
|--------|-------------|----------|
| mDNS and top-level `lifx` | Export `TransportMethod` alongside the already-public `LifxServiceRecord` | |
| Only `lifx.network.mdns` | Keep the type public but off the top-level package | |
| Only its defining module | Require callers to import the implementation module | |
| Device-level connectivity | Do not expose the record transport type; put connectivity on every device | ✓ |

**User's choice:** "I'm not sure why we're exporting the `LifxServiceRecord` at all. I
don't think this needs to be exported either. I think each device should have a
`connectivity` property that returns either `wifi` or `thread`."

**Notes:** The user then locked the mapping: `tm == 2` means Thread and every other case
means WiFi. This replaced the initial SPEC's record-level unknown/enum contract.

### Connectivity value representation

| Option | Description | Selected |
|--------|-------------|----------|
| Strings `"wifi"` / `"thread"` | Simple public literals with no additional runtime type | ✓ |
| Public `Connectivity` enum | Strong symbolic API but another exported type | |
| Internal enum members | Public property values depend on a non-public type | |

**User's choice:** Strings `"wifi"` and `"thread"`.

### Existing low-level API

| Option | Description | Selected |
|--------|-------------|----------|
| Remove only top-level exports | Keep the API public through `lifx.network.mdns` | |
| Make both implementation details | Retain internal use but remove the public contract | ✓ |
| Preserve current exports | Compatibility-first | |

**User's choice:** Make both implementation details.

**Notes:** A codebase trace established that the record and generator are used by the cache,
device construction, public device-level discovery, the hardware probe, tests, docs, and
examples. Their public exports are not needed for those internal call paths.

### Internalisation strength

| Option | Description | Selected |
|--------|-------------|----------|
| Soft-private | Remove exports/docs but retain public-looking symbol names | |
| Explicitly private | Rename both symbols with leading underscores and update all callers | ✓ |
| Compatibility aliases | Introduce private names while retaining deprecated aliases | |

**User's choice:** Explicitly private with no compatibility aliases.

---

## Address Tuple Semantics

### Exposure of retained addresses

| Option | Description | Selected |
|--------|-------------|----------|
| Internal record only | Keep alternative addresses inside mDNS resolution; `Device` exposes selected `ip` | ✓ |
| Add `Device.addresses` | Expose every retained address publicly | |
| Do not retain alternatives | Select one and discard the rest | |

**User's choice:** Internal record only.

### Packet-source fallback

| Option | Description | Selected |
|--------|-------------|----------|
| Keep separate | Treat source fallback as transport evidence, not advertised DNS data | ✓ |
| Include in address collection | Make selected fallback a member of the address collection | |
| Remove fallback | Require A/AAAA for all resolution | |

**User's choice:** Keep source fallback separate.

### Within-class address order

| Option | Description | Selected |
|--------|-------------|----------|
| Numeric address order | Stable packed-address ordering | |
| Canonical text order | Stable lexicographic ordering | |
| Packet order | Preserve responder arrival order | |
| Follow the protocol | Do not ask the user to invent a network rule | ✓ |

**User's choice:** "Wouldn't this be a protocol definition, i.e. we don't get to chose
something, we have to follow the rule?"

**Notes:** RFC 6724 supplies destination-selection rules but can end with local-policy or
original-order ties. The planner should follow applicable protocol rules; any remaining
internal tie-breaker is implementation discretion.

### Byte-for-byte determinism

| Option | Description | Selected |
|--------|-------------|----------|
| Unordered address collection | Assert unique membership and selected class, not tuple byte order | ✓ |
| Deterministically ordered tuple | Preserve the original SPEC's observable ordering contract | |

**User's choice:** Address order does not matter when the addresses match.

**Notes:** This became an explicit SPEC amendment. The retained collection is private and
unordered; tests compare sets. Address-class preference and unscoped-link-local
non-selection remain locked.

---

## Invalid-Record Diagnostics

### Log level

| Option | Description | Selected |
|--------|-------------|----------|
| Debug | Available for diagnosis without alarming ordinary applications | ✓ |
| Warning | Visible by default but vulnerable to network-driven log floods | |
| Silent | Quiet but difficult to diagnose | |

**User's choice:** Debug.

### Diagnostic content

| Option | Description | Selected |
|--------|-------------|----------|
| Reason code only | Structured reason and record type, no identifiers or raw values | ✓ |
| Sanitised instance context | Include a hash or redacted label for correlation | |
| Raw metadata | Include network and hardware values at debug level | |

**User's choice:** Reason code and record type only.

### Rate limiting

| Option | Description | Selected |
|--------|-------------|----------|
| Aggregate once per sweep | Emit bounded counters by rejection reason at discovery end | ✓ |
| Distinct instance once | Track and log each rejected instance once | |
| Every record | Log every rejected input | |

**User's choice:** Aggregate once per sweep.

### Non-2 `tm` values

| Option | Description | Selected |
|--------|-------------|----------|
| No rejection diagnostic | Every non-2 value is accepted as WiFi | ✓ |
| Count malformed values | WiFi outcome plus malformed-metadata counter | |
| Count every non-2 value | Treat normal WiFi and all fallbacks as diagnostic | |

**User's choice:** No diagnostic; non-2 is WiFi.

---

## Conflict Recovery

### Goodbye and cache-flush authority

| Option | Description | Selected |
|--------|-------------|----------|
| Follow RFC 6762 | One-second goodbye grace/rescue; no cache-flush semantics on legacy unicast | ✓ |
| Keep simplified SPEC | Immediate goodbye deletion and applied cache-flush replacement | |
| Hybrid | RFC goodbye grace but defensive cache-flush replacement | |

**User's choice:** Follow RFC 6762.

**Notes:** Research found that the initial SPEC conflicted with RFC 6762 §10.1 and §10.2.
The SPEC was amended rather than preserving the incorrect simplified model.

### Recovery after conflicting-ID expiry

| Option | Description | Selected |
|--------|-------------|----------|
| Recover and resolve | Validity follows the live cache once one valid ID remains | ✓ |
| Poison the sweep | Historical conflict remains invalid until the next call | |
| First valid wins | Ignore the live conflict | |

**User's choice:** Recover and resolve.

### Deadline interaction

| Option | Description | Selected |
|--------|-------------|----------|
| Do not extend deadline | Caller timeout remains authoritative | ✓ |
| Wait one extra second | Let goodbye grace settle beyond caller timeout | |
| Resolve despite goodbye | Bypass the grace period | |

**User's choice:** Do not extend the deadline.

### Unexpected legacy-unicast cache-flush bit

| Option | Description | Selected |
|--------|-------------|----------|
| Ignore semantics and count | Process the record normally and increment a debug counter | ✓ |
| Ignore silently | Process normally with no diagnostic | |
| Reject record or packet | Strictly discard protocol-invalid input | |

**User's choice:** Ignore replacement semantics and count `unexpected_cache_flush`.

---

## Planner's Discretion

- Concrete internal collection type for retained addresses
- Remaining within-class address tie-breaker after applicable protocol rules
- Goodbye expiry data structure and timer integration under the caller's deadline
- Complete rejection-reason vocabulary beyond `unexpected_cache_flush`
- Private storage and constructor plumbing for `Device.connectivity`

## Deferred Ideas

None. The discussion amended Phase 11's contract but did not add later-phase capabilities.
