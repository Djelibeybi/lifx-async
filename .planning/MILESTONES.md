# Milestones

## v2.0 Thread/IPv6 Support (Shipped: 2026-09-05)

**Phases completed:** 5 phases, 41 plans, 93 tasks

**Key accomplishments:**

- `feat/ipv6-thread-support` replayed onto `main` byte-identically across all 11 branch paths, signatures and DCO trailers intact, 3526 tests green, an IPv6-only `Light` driven end-to-end against an emulator on `::1`, and 16 uncovered lines plus 10 partial branches of patch-coverage debt measured and assigned to plans 10-02, 10-03 and 10-05.
- `lifx.network.address` created as the single implementation of address-family selection and address validation, adopted at all three socket-creation sites and gating all four public entry points, so a zone-less IPv6 link-local address now raises a named `ValueError` in microseconds instead of costing a silent 16 second timeout, with the helper at 100% line and branch coverage and three coverage-exemption markers removed rather than carried across.
- A send-time address-family assertion that turns a swallowed `gaierror` timeout into a typed sub-millisecond failure, a leak-safe and reopenable `MdnsTransport.open()`, honest mDNS docstrings, and `lifx.network.mdns` taken to 100% branch coverage with zero partials
- A second emulator on `::1` with `IPV6_V6ONLY` set before bind, an end-to-end suite that asserts the socket family every call actually used and proves frame arrival by reading the device's state back, and one CI cell that fails rather than skips when IPv6 is missing
- `scripts/ipv6_thread_probe.py` grew a `--serial`-targeted control UAT with full matrix-image and firmware-effect restore in a `finally`, an opt-in non-gating `--stream` stage, and `--uat-output` emitting the record plan 10-06's merge gate reads, backed by 38 hardware-free tests whose assertions were each proven able to fail.
- Resilient mDNS delivery now skips unusable records, preserves already-resolved devices across auxiliary send failures, and proves every changed executable line and branch from one immutable base.
- Cancellation-safe mDNS and UDP endpoint creation now restores coherent closed state, releases owned resources, preserves exception semantics, and remains reusable across IPv4 and IPv6 paths.
- Device-level WiFi/Thread classification with exact private metadata mapping, adoption-safe propagation, and real ephemeral-socket legacy-unicast receipt proof
- Complete live DNS record retention with lossless advertised addresses, locked address-class selection, and fail-closed TXT/SRV construction consensus
- Exact-RR goodbye grace with monotonic rescue, one privacy-safe rejection aggregate, and bounded isolated receive-loop completion across packet permutations
- Device-level WiFi/Thread discovery guidance now matches the ephemeral legacy-unicast implementation while raw service records remain absent from public documentation and examples.
- Raw mDNS records and the record-yielding generator are now private implementation details, while the supported device discovery APIs and separately exported record-to-device factory retain full class and connectivity behaviour.
- Phase 11 now has an executable public-surface and documentation contract, a passing immutable-base 100% patch-coverage gate, an anti-weakening proof, and a complete privacy-reviewed regression suite.
- Value-suppressed current-file recovery with D-15/D-16 guidance, complete source coverage, and branch-history authority deferred to Plan 11-08.
- Value-suppressed reachability evidence with an operator-approved no-rewrite disposition and every pre-existing commit preserved.
- Authorised no-rewrite preservation with bounded privacy evidence and fresh green Phase 11 quality gates.
- Exact LIFX service ownership now gates every mDNS construction boundary, and TXT metadata reaches one bounded linear consensus without Cartesian expansion.
- mDNS discovery now bounds retained attacker-controlled payload bytes through their exact cache lifetime and ranks only usable endpoints, allowing a valid Thread ULA to survive unusable IPv4 evidence.
- The IPv6/Thread diagnostic sweep now matches production mDNS deadline, goodbye, retransmission, and bounded follow-up-query semantics without touching hardware or the broadcast path.
- Repository, agent, and quickstart guidance now describe the actual bounded mDNS query sequence and are protected by semantic anti-drift tests.
- Supported-device failures are now unskippable, and the complete Phase 11 gap tree has current 100%-patch-covered, privacy-safe, signed and DCO-verified evidence.
- Public IPv4 and IPv6 targeted lookups now select, exercise, and synchronously close the correct real UDP discovery endpoint while preserving the established discovery loop.
- Concurrent and cancelled public IPv6 targeted lookups now have deterministic real-socket evidence for per-call isolation, endpoint cleanup, and immediate path reuse.
- A narrowly opted-in Windows tracer and the unchanged Ubuntu full suite now prove public IPv6 targeted discovery across runners, with canonical datagram destinations for Windows asyncio compatibility.
- Numeric and named IPv6 zones now survive the real UDP send conversion, while invalid zones fail immediately with a typed network error and current-revision Windows and Ubuntu jobs prove the repaired path.
- UDP-only public enumeration with explicit source observation, a hermetic paired-measurement harness, and immutable privacy-safe pre-merge evidence
- Process-wide active UDP single-flight with ordered raw replay, subscriber-owned deadlines and observations, and deterministic cross-loop lifecycle cleanup
- Current-call, product-directed mDNS verification with one bounded deadline, privacy-safe failure events, and pre-yield StateColor adoption
- Concurrent UDP and verified mDNS discovery with first-valid serial winners, bounded degradation, and cancellation-safe cleanup
- Exact serial lookup now races shared UDP and verified mDNS under one deadline, reaping both source legs before returning any result
- Ordinary exact-head PR CI and 100.00% patch coverage qualify a locally executed hermetic UDP/mDNS emulator pair without permanent Phase 13 CI machinery
- Current-revision fleet evidence closes merged discovery while preserving confounds, filtering unsupported products, and retaining exact 100% patch coverage
- A private, opt-in request observer on `DeviceConnection`'s retry engine emits identity-free logical-start/sent/accepted/timeout/send_error/cancelled/cleanup events on a `time.monotonic_ns()` metadata clock, proven end to end by tracing a retransmitted fake `SetPower` acknowledgement through `scripts/thread_revalidation.py` into a validated, append-only, privacy-safe JSONL journal that round-trips losslessly.
- An immutable, create-exclusive session manifest plus five closed-schema, privacy-validated, append-only JSONL journals (discovery/requests/animation/staleness/closure), with exact D-01..D-08 seeded schedules and statistics, deterministic order-independent summary/ledger/report generation, and a minimal init/validate CLI -- schema-only, no hardware I/O, ready for Plan 14-06 to feed real rows.
- One canonical `scripts/measurement_support.py` now owns both discovery and request observation plus a shared `capture_device_state()`/`restore_and_verify_device_state()` pair that proves restoration with a fresh recapture instead of trusting acknowledged commands, with a `power_out_of_range` preflight that refuses mutation on an intermediate captured power -- backed by explicit Pyright and patch-coverage evidence with a fully accounted, non-weakened residual gap.
- Every THREAD-01..05 physical mode (discovery, request, animation, staleness) is now a production-quality, hermetically fake-fleet-proven driver, plus a roster-driven six-class ledger derivation and a Git-index staged-evidence validator that never echoes a matched private value -- ready for Plan 14-06 to drive against real Thread hardware.
- One executable-example discovery guide (docs/user-guide/discovery.md + examples/discovery_progressive.py) replacing duplicated UDP/mDNS prose across advanced-usage.md/network.md/troubleshooting.md, strict pymdownx.snippets path checking in mkdocs.yml, a corrected Python 3.10 asyncio.gather()/create_task() story in place of the false asyncio.TaskGroup claim, and CLAUDE.md reduced to a literal @AGENTS.md import.

---

## v1.2 Theme Library Update (Shipped: 2026-08-27)

**Phases completed:** 4 phases (6–9), 11 plans, 28 tasks
**Closeout:** override_closeout — 16/16 live requirements satisfied, 8 cross-phase seams
checked, 3520 tests at 97% coverage. Known verification overrides: 1 newly acknowledged,
0 carried forward from a prior close (see STATE.md Deferred Items). Audit closed at
`tech_debt` with both findings remediated before archiving and a third withdrawn as
mistaken.

**Delivered:** the built-in theme palettes — hand-transcribed from photons years ago and
never resynced — are now generated from committed data, carry the app's own names,
categories and dispositions, and ship at their full untruncated lengths. COMPAT-02 was
retired 2026-08-14 and TOOL-01..03 withdrawn 2026-08-19 to the private `lifx-theme-resync`
repository.

**Note on the accomplishments below:** these are the phase summaries' own one-liners,
recorded as written at the time. Two were overtaken by later work in the same milestone.
The `_LEGACY_CATEGORIES` shim named in the Phase 7 line was deleted post-ship in
`2e78de9`, so the six legacy names now raise a `ValueError` instead of mapping; and the
"168 names" in the Phase 6 line became 169 once `renamed` aliases got their own records.

**Key accomplishments:**

- Four-record JSONL seed travels data file → validating generator → generated data.py → ThemeLibrary.get() with app-accurate palettes and identity, plus palette-only multiset Theme equality and 69 generator hardening tests
- 166-record data file built mechanically from the hardware capture plus the pre-v1.2 orphans, ThemeLibrary cut over to the generated dict alone (hand-written table deleted), and every compatibility/metadata guarantee pinned — 168 names resolve with app-accurate uint16 palettes
- COMPAT-04 disposition schema wired end-to-end: all 166 JSONL records carry a machine-readable fate (138 lifx-app / 19 library-only / 9 deprecated with replaced_by), validated by three D-08 generator aborts and surfaced on the public Theme via get()
- Category navigation rewritten over the app's 9-category taxonomy read from the generated records: get_categories() lists them, get_by_category() matches with D-09 slug normalisation on both sides, the 6 pre-v1.2 legacy names get their locked fates via the private _LEGACY_CATEGORIES shim, and generator + library share one derive_slug in the new lifx.theme.slug leaf module — closing the WR-02 defect
- The 6.4.0 theme-taxonomy migration documented as a dated point-in-time record: a new page under both Migration nav sections carrying the 9 categories with counts, the 6 legacy-name fates and the 9 deprecated→replacement pairs — every After example executed against the shipped library — plus the last two stale doc sites corrected (D-11 sites 3-4)
- Phase-local MORPH tracer contracts with semantic Android navigation, exact LIFX palette comparison, and fail-closed private hardware boundaries.
- A fail-closed, resumable 24-cycle Tile/non-Tile fidelity runner with complete restoration and privacy-safe JSON/Markdown finalisation.
- Phase 8 now defines its 16-colour determination scope as 25 shipped non-sport `lifx-app` themes, with the 26th raw record identified as excluded Carlton.
- Operator-approved hardware theme-fidelity observations for both roles, with the source-Tile restoration failure retained and no synthetic official 24-cycle record.
- The theme record contract became an importable, independently tested library module, palettes became untruncated user-facing floats resynced from the LIFX Cloud API, and slug derivation collapsed to one rule with one implementation.
- The shipped library gained a live catalogue page listing its nine categories with counts and recording that the redefined pre-6.4.0 palettes were not carried forward, bound to the library by a test that fails when the two disagree.

---

## v1.1 Wire Reliability (Shipped: 2026-07-26)

**Phases completed:** 4 phases (2–5), 24 plans, 52 tasks
**Closeout:** override_closeout — 13/13 requirements satisfied, 25/25 must-have truths
verified, 7/7 cross-phase connections wired, all four phases Nyquist-compliant. Known
verification overrides: 3 (see STATE.md Deferred Items).

**Delivered:** the library's wire behaviour — discovery coverage, request retries and
animation frame delivery — is now measurably as reliable as the reference clients, with
the asyncio core and public API untouched.

**Key accomplishments:**

- **Discovery re-broadcast (DISC-01..03):** `GetService` re-sent on an escalating
  Photons-shaped schedule inside the discovery window. A 6-round measurement against the
  73-device production fleet moved median single-call coverage from 48/73 to 73/73.

- **Retry schedule reshape (RETRY-01..04):** both `DeviceConnection` request paths
  collapsed onto one shared `_transmit_and_listen()` engine — a single monotonic wall
  deadline, retransmit-while-listening, and shared-queue correlation across GET and ACK.
  Hardware harness: 1.37 → 1.017 packets/request, 62 ms → 12.6 ms median latency, and no
  29 s overruns of a 16 s budget.

- **Animation flow control (ANIM-01..04):** ack-gated frame pacing owned inside the
  animation layer with no consumer-facing toggle. The gated arm won directionally in
  every session ever measured (1.28×–5.25×); certified by operator ruling over a recorded
  statistical FAIL, never presented as a statistical pass (`04-RULING.md`).

- **Latent large-tile bug fixed:** raw 64-pixel colour slicing replaced with row-aligned
  rect offsets, which had garbled frames on any tile width not dividing 64 (Ceiling
  13×26).

- **Reliability documentation (DOCS-01..02):** workaround recipes and inflated 30+ FPS
  claims removed, gen4 wake-tail and streaming-consumer guidance added, and the docs
  build taken from an 8-warning "baseline" to zero warnings under `--strict`, gated in CI.

- **Close-out fixes:** phase 4's validation strategy reconciled (`049902b`) and
  `api.discover()` stopped letting a slow or dead device expire the discovery idle window
  (`dca9e39`, with docs and tests corrected in the `9afe8df` follow-up), both found by the
  milestone audit's cross-phase integration check.

**Deferred:** SEED-001 Thread/IPv6 revalidation (dormant), PERS-01 persistence mixin,
02-01-SUMMARY.md's missing requirements frontmatter (cross-checked manually), and the
disputed D5-09 docs rule.

---

## v1.0 Ceiling Save-on-Exit (Shipped: 2026-06-12)

**Phases completed:** 1 phases, 1 plans, 3 tasks

**Key accomplishments:**

- `CeilingLight.__aexit__` override that persists in-memory state to `state_file` before `close()`, proven by three emulator-backed TDD tests covering happy-path write, no-op without state_file, and exception-propagation-with-save-failure.

---
