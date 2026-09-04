# lifx-async

## Current State (post-v2.0)

**v2.0 Thread/IPv6 Support shipped 2026-09-05.** Phases 10 to 14 delivered and verified;
all 28 live requirements satisfied, 41/41 plans. A Thread device is now a first-class
device: found by default (`discover()` merges a UDP broadcast leg and a unicast-verified
mDNS leg by serial), addressed by IPv6 literal (`find_by_ip()`), raced concurrently in
`find_by_serial()`, and self-identified via `Device.connectivity` (`"wifi"` or
`"thread"`). The mDNS leg reached broadcast-grade quality along the way: an IPv4-defect
ephemeral-port fix (25 devices found vs. 9 with `SO_REUSEPORT` contention), RFC
6762-compliant goodbye/cache-flush handling, and bounded fail-closed record admission
against attacker-controlled payloads.

Every v1.1 wire-reliability finding was then revalidated against a real 8-device Thread
fleet in Phase 14 (SEED-001, planted 2026-07-16, fired at the v1.2 close). Discovery
coverage held across repeated rounds; the WiFi-tuned retry schedule needed no change
against measured Thread ack RTT (medians 37-57ms across 8 aliases); advertisement
staleness was measured directly by unplugging a device (69s from disappearance to
confirmed expiry). Every device class now carries either Thread evidence
(`CeilingLight`, `Light`, `MatrixLight`, `MultiZoneLight`) or a named gap (`HevLight`,
`InfraredLight` — no Thread-capable hardware of either class exists in the fleet).
Thread animation throughput was recorded as an explicit scope boundary rather than
measured: the mesh doesn't have the bandwidth to sustain animation usably, so `Animator`
is intended to be locked to WiFi devices in a future milestone (SEED-003) rather than
chasing Thread animation performance.

Close-out acknowledged three items rather than blocking on them: two still-dormant seeds
(SEED-002 WiFi-control staleness experiment, SEED-003 lock `Animator` to WiFi) and one
Phase 13 deferred item (a coordinator teardown test's blocked-executor-worker hang, whose
`deferred-items.md` entry wasn't updated when a later commit likely already fixed it —
worth a quick recheck next session). See `.planning/STATE.md` Deferred Items and
`milestones/v2.0-ROADMAP.md`.

**v1.2 Theme Library Update shipped 2026-08-27** and **v1.1 Wire Reliability shipped
2026-07-26** — see the collapsed history below and `.planning/MILESTONES.md`.
**Also shipped post-v1.0:** Phase 1 discovery unification (verified 2026-06-13), which
rebuilt `discover_devices()` on `_discover_with_packet()` with hoisted DoS serial
validation and first-wins per-serial dedup.

**Spike series completed 2026-07-16** (`.planning/spikes/`, packaged as the
`spike-findings-lifx-async` skill): five real-hardware experiments that disproved the
"switch to threading" hypothesis and located the actual reliability levers.

## Next Milestone Goals

No v2.1/v3.0 milestone is open yet. Candidates carried forward or surfaced during v2.0:

- **SEED-003**: Lock `Animator` to WiFi devices — Thread doesn't have the bandwidth for
  usable animation frame rates (recorded as a scope boundary in Phase 14, THREAD-03)
- **SEED-002**: Run the staleness experiment against WiFi bulbs as a control, to know
  whether THREAD-04's 69s expiry figure is Thread-specific or a general mDNS TTL/goodbye
  artefact
- **FLEET-01/FLEET-02**: Cross-packet mDNS accumulation, follow-up A/AAAA queries, and
  multi-border-router topologies — currently proven only synthetically; revalidate once
  the fleet or network grows enough to exercise them on hardware
- Seven open GitHub issues deferred from PR #211 (mDNS) and PR #196 (themes) review that
  are still unresolved: [#217](https://github.com/Djelibeybi/lifx-async/issues/217),
  [#216](https://github.com/Djelibeybi/lifx-async/issues/216),
  [#215](https://github.com/Djelibeybi/lifx-async/issues/215),
  [#214](https://github.com/Djelibeybi/lifx-async/issues/214),
  [#213](https://github.com/Djelibeybi/lifx-async/issues/213),
  [#212](https://github.com/Djelibeybi/lifx-async/issues/212),
  [#209](https://github.com/Djelibeybi/lifx-async/issues/209) (mDNS test/docs/coverage
  cleanup), plus theme issues
  [#201](https://github.com/Djelibeybi/lifx-async/issues/201),
  [#199](https://github.com/Djelibeybi/lifx-async/issues/199),
  [#198](https://github.com/Djelibeybi/lifx-async/issues/198), and
  [#191](https://github.com/Djelibeybi/lifx-async/issues/191) (typed Move-effect API)
- **PERS-01, SPIKE-006, STYLE-01**: long-carried candidates, see Active requirements below

## Shipped Milestone: v2.0 Thread/IPv6 Support (2026-09-05)

**Goal:** A Thread device becomes a first-class device in this library: found, addressed,
controlled and animated without the caller needing to know it is on Thread. The v1.1
wire-reliability findings are then revalidated over Thread, because every one of them was
measured on WiFi/IPv4.

**Delivered:**

- **IPv6/Thread transport landed through Phase 10 and PR #210:** IPv6 device addresses,
  socket family following the target address, AAAA parsing that prefers routable addresses
  over link-local, per-instance mDNS record accumulation across packets, PTR retransmit per
  RFC 6762 5.2, follow-up A/AAAA queries for SRV targets whose address records did not fit
  one reply, and the animator frame-socket family fix (IPV6-01..04)
- **mDNS ephemeral-port bind as its own regression-tested requirement.** Measured 25
  devices found bound ephemeral against 9 bound on 5353 with `SO_REUSEPORT`: system mDNS
  daemons were stealing legacy-unicast replies. This is an IPv4 defect that predates
  Thread, so it earns a test of its own rather than riding along uncredited (MDNS-01)
- **`discover()` runs broadcast and mDNS together**, merging by serial, so every existing
  caller reaches Thread devices without opting in (FIND-01..04)
- **Source-specific discovery remains public.** `discover_udp()` exposes UDP-only
  enumeration alongside the existing mDNS-only `discover_mdns()`, while `discover()`
  remains the dual-source default; overlapping compatible callers share one active
  broadcast sweep (FIND-09, FIND-10)
- **`find_by_serial()` runs both legs concurrently, first hit wins** (FIND-05); **`find_by_ip()`
  accepts an IPv6 literal** instead of returning `None` (FIND-06)
- **Every `Device` exposes `connectivity` as `"wifi"` or `"thread"`.** Exact private TXT
  `tm=2` means Thread; every other case means WiFi. The low-level mDNS record and generator
  are explicitly private (MDNS-02, D-16)
- **Synthetic multi-packet mDNS tests** exercising cross-packet record accumulation and
  the follow-up A/AAAA path, neither of which two Thread devices can trigger (MDNS-03, MDNS-04)
- **Thread revalidation (SEED-001, THREAD-01..05)** measured against a real 8-device
  fleet: discovery coverage held across repeated rounds, WiFi-tuned retry constants held
  against measured Thread ack RTT, advertisement staleness measured directly (69s
  disappearance-to-expiry on one alias), and every device class closed evidence-backed or
  as a named gap. Animation throughput was recorded as a scope boundary, not measured
  (THREAD-03) — `Animator` is intended to be locked to WiFi devices in a future milestone
  (SEED-003)
- **Consumer guidance docs**: one executable discovery guide replacing duplicated
  UDP/mDNS prose, and the false `asyncio.TaskGroup` claim in `CLAUDE.md`/`AGENTS.md`
  corrected for the Python 3.10 floor (DOCS-04..06)

**Closed with 3 acknowledged items** (override closeout): SEED-002 and SEED-003 remain
dormant seeds for a future milestone, and one Phase 13 deferred item (coordinator teardown
test hang) whose `deferred-items.md` entry wasn't confirmed against a later possible fix.
See `.planning/STATE.md` Deferred Items.

Full details: [milestones/v2.0-ROADMAP.md](milestones/v2.0-ROADMAP.md)

<details>
<summary>Shipped Milestone: v1.2 Theme Library Update (2026-08-27)</summary>

**Goal:** Resync `lifx.theme.library` with the LIFX app's live theme set without silently
changing colours existing callers already depend on.

**Delivered:**

- **Generated theme data.** 166 committed JSONL records drive a validating generator into
  `src/lifx/theme/data.py`; the hand-written table is deleted and 169 names resolve.
  Regeneration is byte-idempotent and gated in CI (THEME-01..04).
- **Compatibility held.** All 57 pre-v1.2 keys still resolve, and both rename pairs
  resolve under either name (COMPAT-01, COMPAT-03).
- **Every orphan has a recorded fate.** 138 `lifx-app` / 19 library-only / 9 deprecated
  with a resolving `replaced_by`, plus `renamed` added post-ship for the alias keys
  (COMPAT-04).
- **Taxonomy is queryable.** `get_categories()` lists the app's nine categories;
  `get_by_category()` reads them from the generated records with slug normalisation on
  both sides. The six pre-6.4.0 names raise a `ValueError` naming the nine real ones
  (META-01..04).
- **Hardware fidelity evidenced on two products.** A fail-closed, resumable Tile and
  non-Tile runner with full restoration and privacy-safe artefacts, closed under an
  explicit operator exception that retains the unverified Tile restoration
  (FIDELITY-01..03).
- **The record contract became a library module.** `lifx.theme.schema` is importable and
  independently tested, and slug derivation collapsed to one rule in one leaf module
  shared by library and generator (TOOL-04).
- **A live catalogue page** bound to the library by a drift test that fails when the two
  disagree (DOCS-03).

**Withdrawn 2026-08-19:** TOOL-01..03 (capture tooling, diff analysis, resync runbook).
That tooling is maintained in the separate private `lifx-theme-resync` repository, so
shipping it here stopped being a requirement of this milestone.

**Retired 2026-08-14:** COMPAT-02 (`*_legacy` aliases). See Key Decisions.

</details>

<details>
<summary>Shipped Milestone: v1.1 Wire Reliability (2026-07-26)</summary>

**Goal:** Close the empirically-measured reliability gap between lifx-async and the
reference clients (Glowup, Photons) using the spike-validated blueprints, without changing
the asyncio core or public API.

**Delivered:**

- **Discovery re-broadcast** — re-send `GetService` on an escalating schedule inside the
  discovery window. Spike 005: single broadcast finds median 48/73 devices on a multi-AP
  network; re-broadcast schedules find 73/73.
- **Animation flow control** — the Animation layer owns delivery strategy internally
  (Photons-style ack-gated pacing); **decided by the animation library, not downstream
  consumers**. Spike 003: eliminates the 14.6% concurrent-query loss during streaming and
  produced the best visual smoothness.
- **Retry schedule reshape** — floor the 31 ms first-attempt window (~200 ms), keep
  listening during backoff instead of sleeping blind, count sleeps against the caller's
  timeout. Spike 002: kills duplicate-firing on healthy networks and 29 s wall-time
  overruns of the 16 s budget.
- **Docs** — gen4 power-save wake-tail footnote; guidance for streaming consumers (LedFx).

</details>

## What This Is

`lifx-async` is a mature, zero-dependency, type-safe async Python library for controlling
LIFX smart devices over the local network (published on PyPI as `lifx-async`). v1.1 made
its wire behaviour measurably as reliable as the best reference clients. v1.2 turned to
what the library *renders*: the built-in palettes, transcribed from photons years ago and
never resynced, had drifted until most shared names no longer matched the app. They are
now generated from committed data rather than hand-written, carry the app's own names,
categories and dispositions, and ship at their full untruncated lengths. v2.0 turned to
*what the library can reach*: a Thread device — IPv6-only, mDNS-advertised, no broadcast
address — is now found, addressed, controlled and animated exactly like a WiFi device,
with every existing caller's wire behaviour revalidated on real Thread hardware rather
than assumed to transfer from WiFi/IPv4.

## Core Value

Commands stick, devices are found — over WiFi or Thread, transparently — streaming never
starves control traffic, and a theme by name looks like the theme of that name in the
LIFX app.

## Requirements

### Validated

<!-- Inferred from existing code — already shipped and relied upon. -->

- ✓ v1.0 Ceiling save-on-exit lifecycle (see MILESTONES.md) — shipped
- ✓ Unified discovery generator with serial validation and first-wins dedup
  (`_discover_with_packet()`, post-v1.0 Phase 1) — shipped
- ✓ Request/response correlation on (source, sequence, serial) with shared response queue
  across retry attempts (`connection.py`) — existing
- ✓ Zero-allocation prebaked packet templates for animation (`animation/packets.py`) —
  existing
- ✓ Discovery re-broadcast on an escalating schedule (DISC-01..03) — v1.1
- ✓ Retry schedule reshape (RETRY-01..04) — v1.1
- ✓ Animation-layer-owned ack-gated flow control (ANIM-01..04) — v1.1
- ✓ Reliability documentation (DOCS-01..02) — v1.1
- ✓ Consumer time cannot expire the discovery idle window — v1.1 close-out
  (quick task 260726-824)
- ✓ Theme data is generated from committed JSONL, not hand-transcribed, and regeneration
  reproduces the committed module exactly (THEME-01..04) — v1.2 Phase 6
- ✓ No shipped theme key vanished, and both rename pairs resolve under either name
  (COMPAT-01, COMPAT-03) — v1.2 Phase 6
- ✓ A theme exposes its emoji-stripped app display name and category, distinct from its
  ASCII slug (META-01, META-02) — v1.2 Phase 6
- ✓ Category taxonomy is queryable — `ThemeLibrary.get_categories()` lists the nine
  categories and `get_by_category()` reads them from the generated records
  (META-03, META-04) — v1.2 Phase 7. The six pre-6.4.0 names raise a `ValueError` naming
  the nine real ones; the mapping shim was deleted post-ship in `2e78de9` because no old
  name mapped onto a single category
- ✓ The orphaned library keys carry recorded fates — `Theme.disposition` is
  `lifx-app` / `library-only` / `deprecated` / `renamed`, and every deprecated or renamed
  key names a `Theme.replaced_by` that resolves (COMPAT-04) — v1.2 Phase 7. `renamed` was
  added post-ship (`582f74b`): the closed three-value set had no way to express a rename,
  so the two alias keys inherited their target's `lifx-app` fate and COMPAT-04's 30
  orphans shipped with only 28 recorded fates
- ✓ Theme fidelity evidenced on hardware across two products, and the 16-colour ceiling
  question answered (FIDELITY-01..03) — v1.2 Phase 8, completed under an operator-approved
  exception that retains the unverified Tile restoration. FIDELITY-01 was ultimately
  satisfied by its *first* branch, not its second: Phase 9's resync supplied the true
  lengths that no device-based method could
- ✓ The theme record contract is importable as `lifx.theme.schema` and independently
  tested, with slug derivation collapsed to one rule in one leaf module (TOOL-04) —
  v1.2 Phase 9
- ✓ Theme documentation lists the themes and categories and records that the redefined
  pre-6.4.0 palettes were not carried forward, bound to the library by a drift test
  (DOCS-03) — v1.2 Phase 9
- ✓ IPv6/Thread transport: any socket-creation site derives family from the target
  address, a zone-less link-local address raises immediately instead of a silent 16s
  timeout (IPV6-01..04) — v2.0 Phase 10
- ✓ mDNS hardened to broadcast-grade quality: ephemeral-port bind, `Device.connectivity`,
  cross-packet record accumulation, bounded fail-closed address admission, RFC
  6762-compliant goodbye/cache-flush handling (MDNS-01..08) — v2.0 Phase 11
- ✓ IPv6 targeted lookup: `find_by_ip()` resolves an IPv6 literal, family-aware bind,
  proven concurrent/cancellation-safe on Windows and Ubuntu (FIND-06) — v2.0 Phase 12
- ✓ Merged discovery: `discover()` runs UDP and verified mDNS legs concurrently merged by
  serial with the pre-existing contract intact; `discover_udp()`/`discover_mdns()` stay
  explicit; overlapping UDP callers share one active sweep; `find_by_serial()` races both
  legs (FIND-01..05, FIND-07..10) — v2.0 Phase 13
- ✓ Every v1.1 wire-reliability finding revalidated against a real 8-device Thread fleet;
  every device class evidence-backed or a named gap; consumer guidance and doc
  corrections shipped (THREAD-01..05, DOCS-04..06) — v2.0 Phase 14

### Active

<!-- Next milestone not yet opened. Candidates carried forward from v2.0 close; see
     "Next Milestone Goals" above for the full list with links. -->

- [ ] SEED-003: lock `Animator` to WiFi devices — Thread lacks the bandwidth for usable
      animation frame rates (recorded as a scope boundary in v2.0 Phase 14, THREAD-03)
- [ ] SEED-002: run the staleness experiment against WiFi bulbs as a control
- [ ] FLEET-01: cross-packet mDNS accumulation and follow-up A/AAAA queries confirmed on
      real hardware, once the fleet is large enough to overflow one legacy-unicast reply
- [ ] FLEET-02: multi-address and multi-border-router topologies revalidated
- [ ] PERS-01: generalise `state_file` persistence into a reusable mixin (deferred since
      2026-06-11)
- [ ] Spike 006: measure the impact of publishing tuning constants vs behaviour only.
      The D5-09 rule is disputed and remains an OPEN decision
- [ ] No-em-dash house style: roughly 200 em dashes across `docs/`, deferred by the user
      during Phase 7 UAT. Preference is to recast each sentence rather than swap the
      character

### Out of Scope

- **Switching from asyncio to threading** — disproven by Spike 004: wire-equivalent at
  idle, threading collapses under CPU load
- **Keepalive daemon** — disproven by Spike 001: zero idle-related loss on healthy
  networks; gen4-only sub-250 ms wake tail warrants a docs footnote, not a feature
- **Glowup-style query retries (3× fresh 2 s deadlines)** — disproven by Spike 002:
  40% failure at 50% loss
- **Downstream-facing flow-control toggles** — delivery strategy is the animation
  library's decision (user decision, 2026-07-16)
- Generalising `state_file` persistence into a reusable mixin (PERS-01) — still deferred;
  unrelated to this milestone
- mDNS discovery changes — Spike 005's finding applies to UDP broadcast discovery
- **Sport themes** (🏆 AUSSIE RULES, 🏉 LEAGUE, 🏉 UNION — 40 of the 179 captured) —
  club-branded palettes with colliding slugs and no general appeal (user decision,
  2026-08-14)
- ~~**Calling the undocumented LIFX theme endpoints**~~ — **reversed during v1.2 Phase 9.**
  The rule held through Phases 6 to 8, and it is what forced FIDELITY-01 to settle for
  "no device-based method can supply it". Phase 9 set it aside and resynced the palettes
  from an internal LIFX HTTP API endpoint, which returned the true palette for exactly the
  25 themes the protocol had clipped at 16. The capture and resync tooling that talks to
  it lives in the separate private `lifx-theme-resync` repository, not here, so this
  library still ships no code that calls those endpoints
- **MirrorLight (PR #194)** — complete and open, lands on its own schedule, not folded
  into this milestone (user decision, 2026-08-14)
- **`find_by_label()` gaining an mDNS path of its own** (v2.0) — it keeps the broadcast
  `GetLabel` trick and picks up Thread devices through `discover()`'s new mDNS leg, so a
  second addressing scheme would buy nothing (user decision, 2026-08-27)
- **Home Assistant integration code** (v2.0) — this milestone ships the library capability
  and the guidance a broadcast-first consumer needs; changes to any downstream integration
  land in their own repositories (user decision, 2026-08-27)
- **Thread coverage for `HevLight` and `InfraredLight`** (v2.0) — no Thread-capable
  hardware of either class exists in the fleet; the existing bulbs predate Thread. Newer
  models may gain it, so these classes are unevidenced rather than permanently excluded
- **Fleet-scale Thread hardware validation** (v2.0) — deferred until enough of the fleet is
  migrated for a border router to overflow a single legacy-unicast reply. Covered
  synthetically in the test suite in the meantime and recorded as a named gap, not a
  blocker (user decision, 2026-08-27)

## Context

- Brownfield: full codebase map in `.planning/codebase/` (refreshed 2026-06-11).
- Implementation blueprints with working reference code live in
  `./.claude/skills/spike-findings-lifx-async/` (references/ + sources/); raw spike data
  in `.planning/spikes/*/results-*.jsonl`.
- Reference clients studied: Glowup (threaded,
  `/Volumes/External/Developer/pkivolowitz/glowup/`) and Photons (asyncio,
  insider-authored, `/Volumes/External/Developer/Djelibeybi/photons`). Techniques port;
  dependencies don't.
- Real-hardware validation available: 7 quiesced test devices across gen2/3/4 plus a
  73-device production fleet (see auto-memory `project_test_fleet`). Repeated rounds are
  mandatory for discovery/loss claims — single rounds mislead.
- lifx-async is the LIFX provider for LedFx — the streaming + concurrent-control pattern
  Spike 003 measured is LedFx's exact workload.
- Theme data (current): `data/themes.jsonl`, 166 committed records, regenerated into
  `src/lifx/theme/data.py` by `scripts/generate_theme_data.py` and gated in CI. The
  importable contract is `lifx.theme.schema`.
- Theme capture history: the 2026-08-14 capture drove the app over adb (apply as MORPH,
  tap Save, read back via `StateTileEffect`), which is why every palette arrived clipped
  at the protocol's 16 colours. Phase 9 resynced from an internal LIFX HTTP API endpoint
  and replaced them with full palettes. The capture tooling and its README lived in
  `.claude/theme-capture/`, which was never tracked and has since been removed; both now
  live in the private `lifx-theme-resync` repository.
- Thread hardware available for v2.0, measured 2026-08-28 by Phase 10's discovery
  sweep: six IPv6-only devices answer on the Thread mesh, none of them carrying an A
  record. The `CeilingLight`, `MultiZoneLight` and single-zone `Light` migrations that
  were recorded as planned have since happened, so every class below is live rather than
  pending:

  | Serial | Product | Library class |
  |---|---|---|
  | `d073d5e00001` | 215 LIFX Candle C (Test Candle) | `MatrixLight` |
  | `d073d5e00002` | 217 LIFX Tube (Test Tube) | `MatrixLight` |
  | `d073d5e00003` | 177 LIFX Ceiling | `CeilingLight` |
  | `d073d5e00004` | 161 LIFX Neon Outdoor | `MultiZoneLight` |
  | `d073d5e00005` | 182 LIFX Mini | `Light` |
  | `d073d5e00006` | 182 LIFX Mini | `Light` |

  `InfraredLight` and `HevLight` hardware in the fleet is too old for Thread, so both
  close as named gaps under THREAD-05.
- Phase 14's THREAD-05 six-class ledger closed against an 8-alias fleet (`LIFX-Candle-C-1`,
  `LIFX-Ceiling-13x26-1`, `LIFX-DL-Intl-1`, `LIFX-DL-Intl-2`, `LIFX-Luna-1`, `LIFX-Mini-1`,
  `LIFX-Mini-2`, `LIFX-Tube-1`): `CeilingLight`, `Light`, `MatrixLight` and
  `MultiZoneLight` are `evidence_backed`; `HevLight` and `InfraredLight` are `named_gap`
  (no Thread-capable hardware of either class exists in the fleet). See
  `milestones/v2.0-phases/14-thread-revalidation-and-docs/14-EVIDENCE/14-REPORT.md`.
- Current size post-v2.0: ~44,700 lines of library source (`src/`), 4,856 tests
  collected (4,844 run + 12 deselected benchmark tests), zero runtime dependencies.
  Version at close: 7.1.3 published, `v7.2.0` tag cut by semantic-release for the
  NullHandler feat commit.
- **The Thread OMR prefix is not an identifier. Match on serial.** It measured
  `fd00:2::/64` on 2026-08-28, distinct from the WiFi fleet's
  `fd00:3::`, but a Thread OMR prefix is an auto-generated ULA that the border
  router re-derives whenever it re-forms the mesh, so it changes with no notice and no
  migration. This fleet was recorded on `fd00:1::` until 2026-08-28, and Phase 10's
  sweep then found nothing whatsoever on that prefix. Resolve the address at discovery
  time and key on the serial, which is stable across every re-formation.
- Thread revalidation evidence is recorded per device class, following the v1.2 FIDELITY
  pattern: a class closes when evidenced, and an unavailable class closes as a named gap
  rather than staying open indefinitely. The v1.2 lesson applies directly, where a capture
  taken entirely from one product left product-invariance assumed rather than tested.
- Phase 10 shipped the prior Thread work through PR #210 as `7f54ad7`: `b49400b`
  (network and mDNS), `b88cdb9` (`scripts/ipv6_thread_probe.py`, a three-stage
  records/ports/connect hardware probe driving the library's own primitives), and `2f884f5`
  (animator frame-socket family). The temporary feature and backup branches were removed
  after merge; the Phase 10 artefacts retain the reconciliation record.

## Constraints

- **Tech stack**: Python 3.10–3.14, `asyncio`, zero runtime dependencies — no new deps.
- **Compatibility**: Public async API unchanged. Additive/internal changes only; existing
  callers of `discover_devices()`, `DeviceConnection.request()`, and the Animation layer
  must work unmodified.
- **Emulator limits**: the emulator cannot model per-AP broadcast delivery, WiFi loss, or
  power-save — hardware validation runs complement, not replace, the test suite.
- **Quality gates**: `uv run pyright` (strict) clean, `uv run ruff check`/`format` clean,
  `uv run pytest` green across supported versions; CI requires 100% branch patch coverage.
- **Spelling**: Australian English in all prose/comments.
- **Theme names are public API**: every existing key in `lifx.theme.library` is importable
  and callable today. A key may gain values or an alias; it may not silently vanish.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| v1.0 decisions | See MILESTONES.md and git history | ✓ Shipped |
| Investigate wire behaviour instead of porting to threading | Bulbs can only observe packets/timing, not the concurrency model | ✓ Validated (Spikes 001–005) |
| Adopt Photons-shaped schedules (discovery + retries) | Best measured balance: full coverage / 1-in-180 failure at moderate packet cost | ✓ Validated — Phases 2–3. Discovery: median 48/73 → 73/73 on one call. Retries: 1.37 → 1.017 packets/request, 62 ms → 12.6 ms, no 29 s overruns of the 16 s budget |
| Animation flow control owned by the library, not downstream | Consumers (LedFx) shouldn't need to choose delivery strategy; the layer that sends frames decides | ✓ Shipped — Phase 4. No consumer-facing toggle. Gated arm won directionally in every measured session (1.28×–5.25×); certified by operator ruling over a recorded FAIL, never a statistical pass (`04-RULING.md`) |
| Publish behaviour, not tuning constants (D5-09 as written) | Rendered docstrings state the behavioural contract; thresholds/expiries stay in `flow.py` and comments where they can change without a docs lie | ✓ Applied — Phase 5. **The rule itself is disputed by the operator and remains an OPEN decision** in `05-CONTEXT.md`, with spike candidate 006 (cap-impact measurement) linked. Phase 5 complied with it as written; its future is unsettled |
| Drop the 8-warning docs baseline instead of pinning it | The "pre-existing" warnings were a defect set (5 annotations parsed as link refs; 3 anchors to never-rendered mDNS symbols), not a constant | ✓ Shipped — Phase 5 (D5-23). Zero warnings under `--strict`, gated in CI so the class cannot drift back |
| Discovery keeps its own re-broadcast schedule rather than reusing the Phase 3 retransmit engine | `_transmit_and_listen()` stops retransmitting after its first yield, which would defeat DISC-01's requirement to keep broadcasting after early responders answer | ✓ Validated at the v1.1 close audit — disjoint sockets, packets and sources, so the two schedules cannot double-send |
| ~~Overwrite redefined themes but keep `*_legacy` aliases~~ | App accuracy is the point of the milestone, but 19 palettes change under callers who never asked for it; an alias makes the old values recoverable by name instead of by git archaeology | **Reversed 2026-08-14** in the Phase 6 discussion. Measuring the 19: 10 shift by only one or two colours, 9 change wholesale (`tranquil` and `zombie` share nothing with their old palettes). Not worth 19 name collisions and a second addressing scheme — the app is the source of truth and the old palettes stay in git history |
| Strip emoji from theme names and categories | The app is built to display them; downstream consumers of a Python library are not. 'Forrest 🌳' ships as `Forrest`, '🎉 HOLIDAYS' as `Holidays` | Decided 2026-08-14 — verified no name strips to empty and only `christmas` duplicates, which was already collapsing |
| ASCII slugs, drop the sport categories | Emoji are poor Python identifiers and CLI arguments; dropping AFL/League/Union removes 5 of the 6 slug collisions outright rather than inventing suffixes for club branding | Decided 2026-08-14 — v1.2 scope |
| ~~Device readback as the only capture source~~ | Themes are server-driven and absent from the APK; the internal endpoints are undocumented and were not called. Accepted cost: palettes are capped at the protocol's 16 colours and order is lost | **Reversed 2026-08-19, Phase 9.** The accepted cost turned out to be the milestone's central open question, and no device could answer it: a readback cannot reveal a seventeenth source colour. Phase 9 resynced from an internal LIFX HTTP API endpoint instead, and the 25 clipped palettes came back at 18 to 68 colours. The rule was right about what devices can do and wrong about it being sufficient |
| Reset the discovery idle timer on consumer resume, not just before the yield | `api.discover()` constructs a Device per response; those round trips would otherwise spend the idle window and truncate the sweep | ✓ Shipped — v1.1 close-out (260726-824). Overall timeout untouched, so a slow consumer still cannot extend discovery indefinitely |
| Generate the theme table from committed data rather than hand-writing it | A 366-line hand-transcribed palette table had silently drifted from the app for years with nothing to detect it | ✓ Shipped — Phase 6. `data/themes.jsonl` is the source of truth, regeneration is byte-idempotent, and CI regenerates and diffs on every change to `data/**` |
| Move the generator out of the package into `scripts/` | The wheel shipped the generator without `data/themes.jsonl`, so the shipped code could not run | ✓ Shipped — Phase 6 (PR #196 review). The generator's input sits outside `src/` and is deliberately not in the wheel |
| Palette comparison via named `palette_equals()`, not `Theme.__eq__` | Overriding `__eq__` made `Theme` unhashable and would have needed a BREAKING CHANGE footer for 6.3.0 | ✓ Shipped — Phase 6 (D-19a/D-20a). `==` stays identity, `Theme` stays hashable |
| Legacy category names fail rather than map | No pre-6.4.0 name mapped onto a single new category; `seasonal` held none of what it used to return. Naming a replacement would have been a false promise about the old result set | ✓ Shipped — Phase 7, then hardened post-ship in `2e78de9` by deleting the mapping shim entirely. All six raise a `ValueError` listing the nine real categories |
| Close Phase 8 under an operator exception rather than re-running hardware | The source-Tile role never verified restoration, so the designated 24-cycle run could not be finalised. Publishing a merged two-role record would have claimed a run that never happened | ✓ Accepted 2026-08-16. Observations accepted, restoration exception retained, `08-UAT-RESULTS.json` deliberately absent, synthetic merge prohibited |
| Maintain the capture and resync tooling outside this repository | It talks to undocumented internal endpoints and needs adb, hardware and private data; none of that belongs in a zero-dependency library | ✓ Applied 2026-08-19. TOOL-01..03 withdrawn from v1.2; `lifx-theme-resync` owns them, and this library keeps only the importable contract (TOOL-04) |
| Keep Phase 8's ceiling record as history rather than regenerating it | Its selection rule re-derives to nothing post-resync, but the 25 rows and the finding were correct when made, and the finding is still true about devices | ✓ Applied at the v1.2 close. Restamped `status: historical`, pinned to `data/themes.jsonl@291e7e6~1`, with a connected guard replacing the archived harness |
| `discover()` gains an mDNS leg rather than staying broadcast-only | Thread devices have no IPv4 address, so a broadcast-only `discover()` returns an incomplete fleet with no error. Measured: `discover()` found 25 devices and neither Thread serial; `discover_mdns()` found both. Requiring every consumer to opt in means the obvious default silently under-reports | Decided 2026-08-27 (option 2 of 3). Accepted cost: `discover()`'s timing and network behaviour change for every existing caller |
| Preserve explicit source-specific discovery and single-flight overlapping UDP sweeps | Default dual discovery must not remove operational control when a caller specifically needs UDP-only or mDNS-only enumeration. The measured rebroadcast schedule already produces hundreds of replies on a large WiFi fleet, so concurrent callers must not multiply it | Decided 2026-08-30 during Phase 13 specification. Add public `discover_udp()` beside `discover_mdns()`; compatible overlapping `discover()` and `discover_udp()` callers share one active UDP sweep, with no unmeasured post-completion cache |
| Filter unsupported products before public discovery yields them | The package controls lighting devices, so relay-only Switches must not appear in `discover()` merely because their UDP or mDNS records are visible. Raw observations remain available only to the private measurement boundary and are intersected with yielded devices before fleet analysis | ✓ Shipped — Phase 13. Both UDP and mDNS paths apply the supported-product classifier before public yield; unsupported serials need no alias-map entry |
| `find_by_serial()` runs both legs, not mDNS alone | An mDNS-only lookup would miss a WiFi device whose firmware does not advertise over mDNS. Neither leg alone covers the fleet | Decided 2026-08-27, revising the original option 3, which proposed mDNS as a fallback only |
| `find_by_ip()` accepts IPv6; `find_by_label()` does not change | A caller passing an IPv6 literal got `None`, which reads as "no such device" rather than "wrong function". `find_by_label()` needs nothing of its own once `discover()` carries mDNS | Decided 2026-08-27. `Device.from_ip()` already proved the IPv6 connection path, so this is the targeted-lookup leg, not new transport work |
| Prove the fleet-scale mDNS paths synthetically first, on hardware later | Cross-packet record accumulation and follow-up A/AAAA queries never fired with two Thread devices, and they are the claims most likely to break at mesh scale. Blocking the milestone on hardware not yet purchased would stall it | Decided 2026-08-27. Hardware confirmation follows once the Home Assistant path works and more of the fleet is migrated |
| The mDNS ephemeral-port bind is a v2.0 requirement in its own right | It is an IPv4 defect, not a Thread feature: system mDNS daemons sharing 5353 under `SO_REUSEPORT` were stealing legacy-unicast replies, costing 16 of 25 devices on plain WiFi discovery. Landing it uncredited inside the Thread work would leave it without a regression test | Decided 2026-08-27 |
| Expose connectivity on `Device`, not the low-level mDNS record | Consumers care whether a device is on WiFi or Thread, not about a DNS cache hand-off object. Exact private `tm=2` means `"thread"`; every other case means `"wifi"` | Decided 2026-08-28 in Phase 11 discussion. Supersedes the 2026-08-27 record-level `tm` decision; `LifxServiceRecord`, `discover_lifx_services()` and any transport enum become explicitly private without aliases |
| Treat retained mDNS addresses as an unordered internal set | Address membership and the selected address class matter; byte-for-byte tuple ordering does not once the record is private. Packet-source fallback is transport evidence and remains separate | Decided 2026-08-28 in Phase 11 discussion |
| Apply RFC 6762's legacy-unicast cache rules exactly | TTL-zero goodbyes receive one-second grace/rescue without extending discovery deadlines. Cache-flush is forbidden on legacy-unicast replies, so its semantics are ignored and an unexpected bit is counted in a privacy-safe debug summary | Decided 2026-08-28 in Phase 11 discussion; supersedes the initial immediate-eviction/cache-flush SPEC contract |
| Resolve numeric and named IPv6 zones at the UDP send boundary, in the native sockaddr field | A caller's scoped link-local literal (`fe80::1%en0`) must survive the real send call, not just address parsing; an invalid zone should fail immediately rather than silently drop | ✓ Shipped — Phase 12. Reports invalid zone resolution as a typed `LifxNetworkError` while keeping the endpoint reusable |
| Measure Thread discovery and retry timing before changing any constant, never assume | The project's spike-first discipline (2026-07-16 lineage): a WiFi-tuned constant only changes on Thread-measured evidence, not on suspicion that Thread is slower | ✓ Applied — Phase 14. Discovery coverage held across repeated rounds; ack RTT medians (37-57ms across 8 aliases) did not warrant retuning any constant |
| Record Thread animation as an explicit scope boundary, not a throughput measurement | Thread doesn't have the bandwidth to sustain animation at usable frame rates, and pushing that volume onto a mesh is bad practice regardless of what a measurement would show | Decided in Phase 14 (THREAD-03). One alias completing 1/2/5 FPS without failing is preserved as evidence Thread carries frames, explicitly not evidence of usable animation. `Animator` is intended to be locked to WiFi devices in a future milestone (SEED-003) |
| Close v2.0 with 3 acknowledged items rather than blocking on them | SEED-002 and SEED-003 are genuinely future-milestone work, not v2.0 scope; the Phase 13 deferred item's underlying test-hang bug appears already fixed by a later commit but `deferred-items.md` was never confirmed against it | Accepted 2026-09-05 at milestone close (override_closeout). Recorded in `.planning/STATE.md` Deferred Items; worth a `/gsd-audit-uat` recheck next session |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-09-05 after v2.0 milestone*
