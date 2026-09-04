# STATE Archive

Pruned entries from STATE.md. Recoverable but no longer loaded into agent context.

## Pruned 2026-08-28 (phases 1-10, kept recent 1)

### Decisions

- [Phase 10]: Phase 10 topology: replay the 23 planning commits on top of the three rebased IPv6 code commits; feat/ipv6-thread-support and gsd/phase-10-land-the-ipv6-thread-branch resolve to the same SHA — Rebasing the feature branch in isolation would have dropped 29 tracked planning files from the working tree, leaving downstream plans unable to read their own instructions
- [Phase 10]: scripts/ipv6_thread_probe.py is unmeasured by --cov rather than uncovered; plan 10-05 owns the treatment and must not widen --cov inside a 100% patch target — Widening --cov would drop 521 unmeasured lines into the 100% patch gate in the same PR, which is the false-green pressure threat T-10-19 exists to prevent
- [Phase 10]: lifx.network.address is the single home of address-family selection and address validation, consumed by all three socket-creation sites and all four public entry points — IPV6-03 audit finding B9: the same colon-membership heuristic was written out by hand at three sites and Device.__init__ held a fourth, independent opinion
- [Phase 10]: A zone-less IPv6 link-local address raises ValueError at Device.__init__, Device.from_ip(), Device.connect() and find_by_ip() instead of logging a warning and proceeding — IPV6-02 audit finding B2: the warning cost a silent 16 second timeout for a permanent configuration error. connect() was the fourth entry point the cross-AI review found unguarded
- [Phase 10]: The three coverage-exemption markers on the moved address checks were removed rather than carried into the new module, and every branch got a unit test — D-04: the markers existed because the branches were awkward to reach through a Device constructor, not because they were unreachable. Carrying them into a new file would be the weakening SPEC prohibition 3 forbids
- [Phase 10]: The B1 send-time family assertion is a pre-send guard placed after the transport-liveness check, so a dead endpoint still reports Socket not open — SPEC AC 11 and threat T-10-09: error_received, _FATAL_SOCKET_ERRNOS and _endpoint_lost are untouched, pinned by a parameterised EHOSTUNREACH/EHOSTDOWN/ENETUNREACH regression test, because converting peer-unreachable storms into raises would tear down healthy request flows
- [Phase 10]: A failed MdnsTransport.open() clears _socket, _protocol and _transport together as well as closing the descriptor — Cross-AI review finding 7: closing alone leaves is_open reporting True and the already-open early return refusing to rebuild, producing a transport that is descriptor-clean and permanently unusable
- [Phase 10]: No _is_opening guard was added to MdnsTransport.open(); the R4 concurrency backstop is kept purely as a regression pin — The backstop was written first and passed against the unfixed code: no await sits between the already-open check and the _protocol assignment, so the early return is atomic in practice. The plan asked for a minimal fix, not a restructure
- [Phase 10]: 10-COVERAGE-GAPS.md was corrected for the B1 misattribution but deliberately not annotated as closed — It is the independent checklist plan 10-06 verifies against before the PR opens; marking it done inside the plan that closed it would invite a rubber-stamp, so the closure evidence lives in 10-03-SUMMARY.md instead
- [Phase 10]: The ::1 emulator hosts a matrix-capable Tile rather than a plain colour light, while the library-side object under test stays a plain Light — The emulator's Set64Handler returns early when the device has no matrix capability, so against a plain colour light the animation test could only ever prove a datagram was sent, never that a frame arrived and was applied
- [Phase 10]: IPV6_V6ONLY is set by a test-only EmulatedLifxServer subclass that owns socket creation, and only read back in the fixture — Setting the option after a bind raises EINVAL on macOS and the stock start() binds internally via local_addr, so owning socket creation is the only way to set it explicitly; getsockopt stays legal on a bound socket
- [Phase 10]: The must-not-skip CI gate is a conditional env var on the existing pytest step, not a new job — LIFX_REQUIRE_IPV6=1 on the ubuntu/Python 3.10 cell flips the ipv6_available probe from skip to fail; that cell is present in every matrix configuration including the reduced ubuntu-only path, so no artefact plumbing or junit parsing is needed
- [Phase 10]: scripts/ipv6_thread_probe.py stays OUT of the global --cov and codecov.yml is untouched; the probe helpers are covered by a scoped local assertion instead — The probe is unmeasured, not uncovered. Widening --cov would drop 521 lines of a hardware script whose three original stages need real Thread devices into a PR carrying a 100 percent branch patch target, creating pressure to lower the target or add pragma markers (threat T-10-19). The six new helpers are factored out and asserted to have zero missing lines and zero partial branches. Plan 10-06 verifies this treatment rather than reopening it.
- [Phase 10]: The UAT harness refuses --uat-output without --serial — An honest not_run is always a valid stage value, but a record naming no device cannot satisfy SPEC AC 19 and would be a repudiation surface (T-10-14) rather than evidence.
- [Phase 10]: Mutation testing replaced the unreachable TDD RED gate in plan 10-05 Task 3 — The plan assigns implementation to Tasks 1 and 2 and tests to Task 3, so a red commit was impossible. Five mutations of the probe were applied and reverted; the one that survived exposed that the outer restore finally had no test that could fail, which is why a KeyboardInterrupt test now exists.
- [Phase 10]: Bare link-local mDNS records are skipped only inside the public discovery sweep; direct construction and all four user-input entry points remain strict — Improves availability for mixed-quality advertisements without weakening IPV6-02 or duplicating the shared IPV6-03 validator
- [Phase 10]: Resolved mDNS records are yielded before auxiliary sends, with separate successful-send and attempt ledgers — Preserves exact-once delivery while allowing one retry and bounding all traffic-bearing targets to 64
- [Phase 10]: Patch coverage is measured from immutable base b4e9b365f4f388ad4dd6800be8e7f9144f027bd6 using branch-aware coverage.py JSON — Provides one deterministic fail-closed authority for plans 10-07 and 10-08 without a dependency or coverage-configuration change
- [Phase 10]: MdnsTransport serialises open() calls with an asyncio.Lock so a concurrent opener waits for cancellation cleanup and then establishes the replacement endpoint
- [Phase 10]: MdnsTransport.close() remains outside the open lock so a close-racing-cancelled-open schedule cannot deadlock
- [Phase 10]: Both UDP transports wrap only OSError after cleanup; cancellation and other BaseException failures retain their original identity
- [Phase 10]: The phase branch MUST remain off main until Phase 10 ships; merging to main is the post-phase shipment action, so branch-only delivery is not a verification gap
- [Phase 10]: Patch coverage remains recorded but is advisory and operator-overridable because it does not affect runtime functionality
- [Phase 10]: Transport lifecycle races and DeviceConnection opener-waiter failures are blocking defects and require deterministic regression fixes
- [Phase 10]: UAT state restoration is best-effort operator hygiene and does not gate the control result or phase completion

## Pruned 2026-09-04 (phases 1-11, kept recent 3)

### Decisions

- [Phase 11]: Connectivity is adopted with registry-derived metadata — Future serial de-duplication must preserve Thread classification without changing address, routing, retry, or tuning behaviour
- [Phase 11, superseded 2026-08-28 by D-15]: The earlier decision treated admitted addresses as lossless within the 1,024-owner cache. D-15 now exact-deduplicates A/AAAA identities, admits at most 256 per owner and 1,024 per sweep, rejects and privacy-safely counts unseen excess identities without eviction, makes owner overflow or sweep exhaustion permanent for the call, and refuses selection, resolution, or follow-up from incomplete state while leaving caller deadlines unchanged.
- [Phase 11, supersession recorded 2026-08-28 as D-16]: The earlier D-03 integration interpretation preserved a public factory. D-16 keeps `_LifxServiceRecord`, `_discover_lifx_services`, and `_create_device_from_record` private together with no public or compatibility alias; supported callers use `discover_devices_mdns()` or `lifx.api.discover_mdns()`.
- [Phase 11]: mDNS TXT construction metadata and SRV endpoints resolve only through full live-set consensus; record ordering never selects a trusted winner.
- [Phase 11]: Goodbye scheduling indexes only complete RR identities under TTL-zero grace; ordinary retained addresses stay outside timer traversal.
- [Phase 11]: Recoverable mDNS parsing is limited to ValueError, IndexError, and struct.error, followed by one privacy-safe rejection summary per sweep.
- [Phase 11]: Packet-source fallback is validated and deferred until sweep completion so later advertised endpoints win without arrival-order bias.
- [Phase 11]: Deletion-only source files remain anti-weakening and public-surface inputs but are excluded from changed-executable coverage.
- [Phase 11]: IPv4 UDP loopback availability is mandatory evidence for the MDNS-01 legacy-unicast transport proof.
- [Phase 11]: Preserve the completed D-15 and D-16 authority commits without replay or amendment. — Current-file and draft recovery is distinct from historical authority work.
- [Phase 11]: Keep branch-history disposition in Plan 11-08 and fresh full gates in Plan 11-09. — Plan 11-07 is limited to current-file sanitisation, draft guidance, and structural closeout.
- [Phase 11]: Preserve history under the Plan 11-08 `no-rewrite` disposition. — The operator confirmed the historical candidate is an approved stable pseudonym; Plan 11-09 owns fresh privacy and full gates.
- [Phase 11]: Only exact canonical LIFX service-instance ownership creates mDNS construction provenance.
- [Phase 11]: A and AAAA records remain bounded candidates until linked by a live exact-service SRV record.
- [Phase 11]: TXT construction metadata uses one-pass effective-value consensus with immediate conflict rejection.
- [Phase 11]: Charge only exact retained variable payload and release the stored cost only when expiry removes the cached identity.
- [Phase 11]: Filter unusable mDNS addresses before the IPv4, ULA, GUA, scoped-link-local ranking and use lexical same-class order.
