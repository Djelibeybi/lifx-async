# Phase 1: Unify duplicated discovery loops - Context

**Gathered:** 2026-06-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Internal refactor of `src/lifx/network/discovery.py`: rebuild `discover_devices()` on top of
`_discover_with_packet()`, removing ~150 near-identical lines that have already drifted. The
documented DoS protections (serial/broadcast-bit validation) move into the shared generator so
every discovery caller gets them, `_parse_device_state_service()` is retired in favour of the
protocol layer's `StateService.unpack()`, the triplicated idle/overall-timeout arithmetic is
extracted into a shared `IdleDeadline` helper (adopted by the unified LIFX loop and
`mdns/discovery.py`), and `UdpTransport.receive_many` is deprecated. Public API behaviour of
`discover_devices()` and the `find_by_*` functions is preserved (modulo the documented
hardening side effects below).

</domain>

<decisions>
## Implementation Decisions

### Validation hoist semantics
- **D-01:** Serial validation (broadcast/multicast bit set, or all-`0xff` serial → reject) moves
  into `_discover_with_packet` and is **unconditional** — no opt-out parameter. No legitimate
  LIFX device produces such serials; this is pure DoS protection.
- **D-02:** Rejected responses are **skipped with a DEBUG log**, mirroring `discover_devices`'
  current behaviour. No WARNING-level per-packet logging — on a hostile network that would
  itself be a flooding vector.
- **D-03:** Hardening `find_by_label` and the label/colour enrichment paths
  (`discovery.py:182/187`, `api.py:1002`) via the hoist is an intended behaviour change —
  responses with invalid serials that previously flowed through are now dropped.

### Dedup placement
- **D-04:** Per-serial dedup lives in the **shared generator**: first response per serial wins;
  each device is yielded at most once. This intentionally fixes `find_by_label`'s latent
  duplicate-yield (a device answering a broadcast twice currently yields twice) and naturally
  retires the vestigial write-only `responses` dict at `discovery.py:322`.

### Unification mechanics
- **D-05:** `discover_devices()` becomes a thin wrapper over
  `_discover_with_packet(DevicePackets.GetService(), ...)`, keeping only `DiscoveredDevice`
  construction and port extraction from the unpacked `StateService` payload.
  `_parse_device_state_service()` (hand-rolled `struct.unpack`) is deleted — the packet
  registry's `StateService.unpack()` is the single source of truth.

### Timeout helper
- **D-06:** Extract a small **class `IdleDeadline`** in `src/lifx/network/utils.py`:
  `__init__(timeout, idle_timeout)`, `remaining() -> float` (returns <= 0 when expired),
  `mark_response()` resets the idle timer. Monotonic-clock based. The caller decides when a
  response counts (calls `mark_response()`) — preserves each loop's existing semantics.
- **D-07:** Both the unified LIFX discovery loop AND `mdns/discovery.py`'s
  `discover_lifx_services` loop adopt `IdleDeadline` this phase (kills the third copy of the
  deadline arithmetic).
- **D-08:** While adopting `IdleDeadline`, the mDNS loop's bare `except Exception` around
  `receive()` is **tightened to match the LIFX loops**: catch `LifxTimeoutError` to stop
  collecting; `LifxNetworkError`/unexpected errors are logged distinctly or propagate. A genuine
  socket error must no longer masquerade as "no responses".

### receive_many deprecation
- **D-09:** `UdpTransport.receive_many` (confirmed zero production callers — definition +
  tests only; multizone multi-response flows go through `connection.request_stream()`) is
  **deprecated this phase, removed in v2.0**: `warnings.warn(..., DeprecationWarning,
  stacklevel=2)` at call time plus a `.. deprecated::` docstring note. The method body is
  otherwise untouched.

### Test strategy
- **D-10:** Tests pinned to retired internals may be **rewritten or deleted freely**
  (`test_discovery_errors.py` exercises `_parse_device_state_service` directly), as long as
  every behaviour they proved (malformed payloads, error paths) stays covered via the shared
  path. `receive_many` tests in `test_transport.py` stay until the method is actually removed.
- **D-11:** Add **new tests for the shared generator** proving serial validation
  (broadcast-bit/0xff rejection) and first-wins dedup at the `_discover_with_packet` level —
  the protection must be proven where it now lives, not just transitively via
  `discover_devices`. Emulator-first per the v1.0 test policy (real `@pytest.mark.emulator`
  flows preferred over mock-only units) where the emulator can produce the traffic; direct
  generator-level tests are acceptable where hostile packets can't be emulated.
- **D-12:** Add one test asserting `receive_many` emits `DeprecationWarning`
  (`pytest.warns(DeprecationWarning)`).

### Claude's Discretion
- Exact DEBUG log message wording/format for rejected serials (match house style: dict-style
  structured log entries).
- Exact deprecation message text (must name `v2.0` as the removal target and point to
  `receive()` / discovery loops as alternatives).
- `IdleDeadline` internals (attribute names, whether `remaining()` caches `monotonic()` calls).
- Test placement and naming within the existing `tests/test_network/` structure.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project conventions and DoS protection contract
- `CLAUDE.md` §"Concurrency Considerations" → "Discovery DoS Protection" — documents the
  source-ID validation, serial validation, overall timeout, and idle timeout this refactor
  must preserve and extend.
- `.planning/codebase/ARCHITECTURE.md` — network-layer structure and data flow.
- `.planning/codebase/TESTING.md` — test layout, emulator usage, fixture conventions.

### No external specs
No ADRs/PRDs exist for this phase — the ROADMAP.md Phase 1 goal plus this CONTEXT.md are the
complete requirements.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/lifx/network/discovery.py` `_discover_with_packet()` (~lines 149–363): the surviving
  generic broadcast-and-collect generator — already does `allocate_source()`, broadcast send,
  source validation, pkt_type filtering, per-packet error handling.
- `src/lifx/protocol/packets.py` packet registry: `get_packet_class()` and
  `Device.StateService` (GetService has `STATE_TYPE = 3`) — replaces
  `_parse_device_state_service()`.
- `src/lifx/network/utils.py` (`allocate_source`) — destination module for `IdleDeadline`.
- `lifx-emulator-core` embedded emulator + existing discovery tests in `tests/test_network/`.

### Established Patterns
- Structured dict-style log entries (`{"class": ..., "method": ..., "action": ...}`).
- `time.monotonic()` for all interval arithmetic (mDNS discovery was converted in commit
  `2f6404a`; `IdleDeadline` must be monotonic too).
- Zero runtime dependencies — stdlib only.
- Strict Pyright; `uv run pyright` must stay at 0 errors.

### Integration Points
- `discover_devices()` callers that must see unchanged behaviour: `api.py:782/887/940`
  (discover, find_by_serial, find_by_ip paths), `devices/base.py:1264/1458`,
  `discovery.py:77`.
- `_discover_with_packet()` callers gaining validation/dedup: `api.py:1002` (`find_by_label`),
  `discovery.py:182/187` (label/colour enrichment).
- `mdns/discovery.py` `discover_lifx_services` loop (~lines 204–340) adopts `IdleDeadline`
  + tightened exception handling.
- Tests touching retired/changed internals: `tests/test_network/test_discovery_errors.py`
  (`_parse_device_state_service`), `tests/test_network/test_transport.py` (21 `receive_many`
  references).

</code_context>

<specifics>
## Specific Ideas

- This phase implements the findings of the 2026-06-13 `/simplify` review of UDP transport
  mechanics. Drift evidence motivating it: the DoS serial validation exists only in
  `discover_devices` (`discovery.py:559`), and the mDNS copy of the timeout loop used
  `time.time()` until commit `2f6404a`.
- The refactor is behaviour-preserving for the public API except for two deliberate hardening
  changes: invalid-serial rejection now covers `find_by_label`/enrichment paths (D-03), and
  duplicate responses from one device no longer double-yield (D-04).

</specifics>

<deferred>
## Deferred Ideas

- **Retry-budget unification** in `connection.py` (`_request_stream_impl` vs
  `_request_ack_stream_impl` duplicate the exponential-backoff budget arithmetic; the ACK path
  lacks the budget-exhaustion check) — explicitly out of scope per the ROADMAP goal; candidate
  follow-up phase.
- **`receive_many` actual removal** — scheduled for v2.0 after this phase's deprecation cycle.
- **Transport base-class extraction** — `UdpTransport`/`MdnsTransport` still share ~100
  parallel lines of send/receive/close scaffolding (the dangerous protocol divergence was
  already fixed in commit `2f6404a`); lower-value churn, revisit if either file changes again.

</deferred>

---

*Phase: 01-unify-duplicated-discovery-loops*
*Context gathered: 2026-06-13*
