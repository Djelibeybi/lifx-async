# Phase 11 mDNS Gap Closure Evidence

**Recorded:** 2026-08-29T00:18:35Z
**Immutable gap base:** `1b9b564a028c1d3e28f3601077e49e144f37e343`
**Tested tree HEAD:** `07e78fe26d0c736a3a21b8daac1413b0c7e39e38`
**Scope:** synthetic mDNS, diagnostic-probe, API, documentation, privacy, and
commit-provenance evidence only

The immutable base is one full commit, is reachable from the tested HEAD, and
was not changed. A metadata-only local history repair added the one missing DCO
trailer and re-signed its descendants; an exact tree comparison proved that the
tested file tree did not change.

## Gate Results

All Python commands used `uv` with the frozen lock. Output containing values was
not copied into this report.

| Gate | Current command or check | Actual result |
|---|---|---|
| Strict label construction | `uv run --frozen pytest` with the four named `TestFindByLabel` nodes and `ResourceWarning` promoted | PASS: 4 passed |
| Focused closure suite | `uv run --frozen pytest tests/test_network/test_mdns tests/test_scripts/test_ipv6_thread_probe.py tests/test_api/test_api_discovery.py -q -W error::ResourceWarning` | PASS: 401 passed |
| Full suite | `uv run --frozen pytest -q -p no:sugar` | PASS: 3,935 passed, 12 deselected, 7 pre-existing deprecation warnings |
| Branch coverage | `uv run --frozen pytest -q -p no:sugar --cov=lifx --cov=scripts.ipv6_thread_probe --cov-branch --cov-report=json:/private/tmp/lifx-async-11-gap-coverage.json` | PASS: 3,935 passed, 12 deselected; fresh JSON produced |
| mDNS patch coverage | `uv run --frozen python scripts/check_patch_coverage.py --base <immutable-base> --coverage <fresh-json> --source src/lifx/network/mdns/discovery.py` | PASS: 130 changed executable lines and 88 changed branches |
| Probe patch coverage | Same checker with `--source scripts/ipv6_thread_probe.py` | PASS: 45 changed executable lines and 26 changed branches |
| Coverage weakening audit | Same checker with `--check-weakening-only` | PASS: no added exemptions, skips, or gate changes |
| Ruff lint | `uv run --frozen ruff check .` | PASS |
| Ruff format | `uv run --frozen ruff format --check .` | PASS: 261 files already formatted |
| Pyright | `uv run --frozen pyright` | PASS: 0 errors, 0 warnings, 0 information messages |
| Zensical | `uv run --frozen zensical build` | PASS |
| llmstxt | `uv run --frozen llmstxt-standalone build` | PASS: both text outputs and 29 Markdown files generated |
| Commit signatures | `git verify-commit` with output suppressed for every commit in `base..HEAD` | PASS: 26 of 26 |
| DCO trailers | Count commits containing a `Signed-off-by:` trailer and compare with `git rev-list --count` | PASS: 26 of 26; identities suppressed |
| Diff integrity | `git diff --check` | PASS |

The first fresh patch-coverage attempt failed on six changed mDNS guard lines.
After focused guard tests were added, a second attempt failed on two address
selection branch arcs. After those were covered, the probe file was absent from
the JSON because its tests imported a different module name; aligning the test
import exposed three further changed probe lines. Focused tests covered those
lines. The complete coverage suite and both patch checkers were then rerun from
scratch and produced the passing results above. None of the failed attempts is
presented as a pass.

## Privacy Audit

The location-only scanner from the evidence privacy skill was run over all 19
files changed since the immutable base, the complete diff, and the complete
local commit history. Candidate values were never printed into this report.

| Surface | Scanner result | Contextual disposition |
|---|---|---|
| Current changed files | 572 candidate-bearing lines | Synthetic test fixtures, static documentation examples, protocol-format examples, and reserved documentation addresses only |
| Complete `base..HEAD` diff | 148 candidate-bearing lines | Synthetic or static examples only; no raw discovery payload or live infrastructure identifier |
| Complete `base..HEAD` history | 211 candidate-bearing lines | Synthetic/static content plus required commit-metadata candidates; signer and account identities were not copied into evidence |
| Staged test repairs | Candidate locations inspected before commit | Reserved documentation addresses and synthetic hostnames only |

Candidate categories were IPv4, IPv6, mDNS hostname, 12-hex serial shape, MAC
shape, and commit-metadata email shape. Context inspection classified every
content candidate as synthetic, reserved, static documentation, or protocol
format. No live serial, MAC address, IP address, hostname, account identifier,
private mapping, or raw discovery output is committed in the closure evidence.
No hardware identity attestation was required because hardware paths were not
run.

## Verifier Gap Closure

| Gap | Current implementation evidence | Current test or contract evidence | Result |
|---|---|---|---|
| 1. Exact service provenance | `_is_lifx_service_instance()`, `_LifxRecordCache.add_packet()`, `resolve()`, and `pending_targets()` | `test_complete_unrelated_service_chain_is_rejected_at_every_boundary`, `test_public_generator_rejects_record_without_exact_service_provenance`, and direct defensive-guard coverage | CLOSED |
| 2. Linear TXT consensus | `_txt_values()` and `_resolve_txt_metadata()` accumulate and compare each field once | `test_txt_consensus_constructs_at_most_one_tuple_for_repeated_values`, early-conflict tests, and duplicate/malformed optional-value tests | CLOSED |
| 3. Retained byte envelope | `_retained_payload_cost()`, per-record and per-sweep byte ceilings, exact refresh accounting, and fail-closed incomplete-owner state | `TestLifxRecordCacheByteBounds`, including exact limits, one-byte overflow, refresh, goodbye, and accounting guards | CLOSED |
| 4. Usable route selection | `_is_usable_mdns_address()` filters before `_pick_address()` class ranking | unspecified, mapped, unusable-only, ULA-preference, public-generator, and complete priority tests | CLOSED |
| 5. Honest query documentation | repository guidance and quickstart describe initial PTR, one- and three-second retransmissions, conditional bounded follow-ups, and unicast limitations | `TestMdnsPhaseContract` query-model and public-boundary tests | CLOSED |

## Review Finding Closure

| Finding | Closure evidence | Result |
|---|---|---|
| CR-01 unrelated service accepted | Exact service-instance checks at admission and both consumers; cache and public-generator rejection tests | CLOSED |
| CR-02 repeated TXT Cartesian product | Linear consensus resolver plus bounded repeated-value and early-conflict tests | CLOSED |
| CR-03 retained raw payload unbounded | Exact per-record/per-sweep retained-byte accounting and `TestLifxRecordCacheByteBounds` | CLOSED |
| CR-04 unusable IPv4 suppresses valid ULA | Pre-ranking usability predicate plus mixed unusable/ULA and unusable-only tests | CLOSED |
| WR-01 probe never expires goodbyes | Probe calls `expire()` around waits/final resolution and clamps to `next_expiry_delay()`; `TestSweepClockParity` | CLOSED |
| WR-02 probe bypasses follow-up cap | Probe attempt/success ledgers enforce two attempts and 64 targets; `TestSweepFollowUpLedger` | CLOSED |
| WR-03 guides claim one query | Corrected guidance and exact `TestMdnsPhaseContract` wording checks | CLOSED |

## Requirement Traceability

| Requirement | Current evidence | Result |
|---|---|---|
| MDNS-01 legacy-unicast query socket | `MdnsTransport.open()` ephemeral bind and `test_ephemeral_socket_receives_direct_loopback_datagram`; AST contract forbids membership/rejoin | COVERED |
| MDNS-02 connectivity and private boundary | exact connectivity parsing, device default/adoption tests, package-surface tests, and four unskippable label construction paths | COVERED |
| MDNS-03 cross-packet accumulation | split-packet permutations, duplicate/exact-once emission, and concurrent-generator isolation | COVERED |
| MDNS-04 bounded address follow-ups | later-response completion, two-attempt failure, successful-send deduplication, and 64th/65th target tests | COVERED |
| MDNS-05 bounded multi-address admission | exact identity/byte ceilings, permanent fail-closed overflow, complete-state selection, and locked class-order tests | COVERED |
| MDNS-06 TXT serial validation | strict format, normalisation, conflict-order, invalid-neighbour isolation, and goodbye recovery tests | COVERED |
| MDNS-07 per-sweep legacy-unicast cache | goodbye/rescue/expiry, cache-flush accounting, exact-once emission, and concurrent state-isolation tests | COVERED |
| MDNS-08 honest documentation | public/private phrase contracts and bounded query-model tests across guidance and quickstart | COVERED |

## SPEC Edge Coverage

| # | Edge | Resolution and current evidence | Result |
|---:|---|---|---|
| 1 | boundary / R1 | AC1; real loopback test proves non-5353 ephemeral receipt | COVERED |
| 2 | precision / R1 | Exact integer UDP ports have no rounding or precision dimension | DISMISSED AS SPECIFIED |
| 3 | concurrency / R1 | No new lifecycle behaviour; existing transport race/cancellation tests remain green | DISMISSED AS SPECIFIED |
| 4 | boundary / R2 | AC3-AC5; exact sentinel behaviour and private converter/package surface | COVERED |
| 5 | empty / R2 | AC4; absent and empty connectivity metadata default to WiFi | COVERED |
| 6 | encoding / R2 | AC3-AC4; only exact ASCII sentinel selects Thread | COVERED |
| 7 | precision / R2 | Exact string comparison has no numeric precision dimension | DISMISSED AS SPECIFIED |
| 8 | adjacency / R3 | AC8; duplicate replay collapses addresses and emissions | COVERED |
| 9 | empty / R3 | AC6; empty/incomplete packets do not block a later valid instance | COVERED |
| 10 | ordering / R3 | AC7; packet permutations yield equal identity, membership, and class | COVERED |
| 11 | idempotency / R3 | AC8; replay preserves exact-once emission and address identity | COVERED |
| 12 | concurrency / R3 | AC9; concurrent generators cannot complete each other's state | COVERED |
| 13 | idempotency / R4 | AC11; success deduplicates and failures stop at exact limits | COVERED |
| 14 | concurrency / R4 | Follow-ups remain in the single discovery loop with existing cleanup ownership | DISMISSED AS SPECIFIED |
| 15 | adjacency / R5 | AC12; duplicate address identities refresh without duplication | COVERED |
| 16 | boundary / R5 | AC12/AC15; exact owner, sweep, record-byte, and sweep-byte limits | COVERED |
| 17 | empty / R5 | AC15; no selectable address means no emission or follow-up amplification | COVERED |
| 18 | ordering / R5 | AC12-AC14; class ranking is locked and complete-state only | COVERED |
| 19 | adjacency / R6 | AC17; conflicts fail closed until expiry leaves one valid identity | COVERED |
| 20 | empty / R6 | AC16; absent and empty IDs are rejected | COVERED |
| 21 | encoding / R6 | AC16; exact hexadecimal shape and lowercase normalisation | COVERED |
| 22 | ordering / R6 | AC17; conflict outcome is permutation-independent | COVERED |
| 23 | adjacency / R7 | AC19-AC20; one-second goodbye/rescue and non-replacing cache-flush handling | COVERED |
| 24 | empty / R7 | AC21; empty packet is a no-op | COVERED |
| 25 | ordering / R7 | AC19; live TTL state, not arrival-winner selection, controls rescue/expiry | COVERED |
| 26 | idempotency / R7 | AC21; repeated goodbye, rescue, and cache-flush observations stay bounded | COVERED |
| 27 | concurrency / R7 | AC22/AC9; records, expiries, diagnostics, and emissions are per call | COVERED |
| 28 | empty / R8 | Static documentation contract has no nullable runtime input | DISMISSED AS SPECIFIED |
| 29 | encoding / R8 | Exact factual prose/identifiers have no Unicode normalisation requirement | DISMISSED AS SPECIFIED |

All 29 SPEC rows are represented: 23 explicit closures and six justified
dismissals, with no unresolved edge.

## SPEC Prohibitions

| # | Must-not contract | Current evidence | Result |
|---:|---|---|---|
| 1 | No bind to 5353, membership join, fallback receive socket, or unsolicited-announcement path | loopback transport test plus executable AST membership/rejoin contract | RESPECTED |
| 2 | No public raw record, generator, converter, enum, wire field, or compatibility alias | package-surface and public-document token tests | RESPECTED |
| 3 | No expansion of the private connectivity wire abbreviation | exact public-guidance phrase contract and public token exclusions | RESPECTED |
| 4 | No cache-flush replacement on legacy-unicast replies | cache-flush count-without-replacement and repetition tests | RESPECTED |
| 5 | Connectivity metadata does not influence selection, routing, connection, retries, or tuning | `test_connectivity_does_not_change_device_network_configuration`; Phase 14 retains future tuning ownership | RESPECTED; FUTURE TUNING OUT OF PHASE |
| 6 | Incomplete owner/sweep state cannot select, resolve, or schedule follow-up | owner/sweep count and byte overflow tests plus direct consumer guards | RESPECTED |
| 7 | No live identifiers or raw discovery evidence | location-only changed-file, diff, staged, and history audit with contextual classification | RESPECTED |

## Threat and Scope Disposition

| Item | Disposition |
|---|---|
| T-11-14-01 hidden supported-device failure | MITIGATED by four explicit non-None assertions and exact-node pass |
| T-11-14-02 private evidence disclosure | MITIGATED by location-only scans and contextual inspection |
| T-11-14-03 gate tampering | MITIGATED by immutable base, frozen full branch coverage, two 100% patch checks, and weakening scan |
| T-11-14-04 unverifiable provenance | MITIGATED: signature and DCO counts both equal the gap commit count |
| T-11-14-05 unsupported completion claim | MITIGATED by complete matrices and explicit failed-attempt/exclusion recording |
| Package supply chain | ACCEPTED low risk: frozen existing dependencies; no lock or dependency change |

Assumption delta: **no-change**. The phrase “one-second” describes a duration,
not a new wall-clock or calendar assumption.

External API/SDK matrix: **not applicable**. This phase changes no external SDK
or third-party API integration.

Broadcast schedule and hardware paths: **not executed**. No live discovery,
hardware control, responder-population probe, multicast rejoin, default
discovery promotion, downstream integration, or fleet validation is claimed.

## Closure Verdict

All five verifier gaps, seven review findings, eight locked requirements, 29
edge rows, and seven prohibitions have current source-backed evidence on the
tested tree. Every required final gate passes. The initial failed patch checks
are retained above as failed attempts, followed by fresh passing reruns.

**Phase 11 gap closure evidence: COMPLETE.** Independent phase re-verification
remains a separate workflow and status boundary.
