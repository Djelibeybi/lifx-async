# lifx-async

## Current State (post-v1.2)

**v1.2 Theme Library Update shipped 2026-08-27.** Phases 6 to 9 delivered and verified;
all 16 live requirements satisfied. The hand-written 366-line palette table is gone.
`data/themes.jsonl` (166 committed records) is the source of truth,
`scripts/generate_theme_data.py` emits `src/lifx/theme/data.py` (169 resolvable keys), and
`ThemeLibrary` reads the generated dict alone. Every record carries a machine-readable
fate, the app's nine-category taxonomy is queryable, and the record contract ships as the
importable, independently tested `lifx.theme.schema`.

Two locked decisions reversed mid-milestone, both recorded in Key Decisions below. The
`*_legacy` aliases were retired before Phase 6 shipped. The second reversal mattered more:
the "device readback is the only capture source" rule was set aside in Phase 9, when the
palettes were resynced from an internal LIFX HTTP API endpoint. That resync answered the
16-colour question the milestone opened with: the 25 themes the protocol had clipped at 16
now ship at their true lengths, 18 to 68 colours.

The close-out audit found no unsatisfied requirements and no orphans. It returned
`tech_debt` over two bookkeeping findings at the Phase 8 to Phase 9 seam, both closed
before archiving. The ceiling determinations were restamped as a historical record pinned
to the pre-resync blob, and `tests/test_theme/test_ceiling_supersession.py` now pins the
supersession that the archived Phase 8 harness can no longer check. A third finding, that
Phase 7 lacked operator sign-off, was withdrawn: the sign-off had been recorded in
`07-UAT.md` all along and only a stale body line suggested otherwise. See
`milestones/v1.2-MILESTONE-AUDIT.md`.

**Next milestone: v2.0 Thread/IPv6 Support** (opened 2026-08-27). SEED-001 has fired: its
trigger condition, LIFX Thread firmware shipping, was met during the v1.2 close-out, when
probing confirmed Thread devices answer over IPv6 and located the gaps that v2.0 closes.

**Merged discovery completed 2026-08-31.** `discover()` now merges shared UDP and verified
mDNS discovery under one caller deadline, while `discover_udp()` and `discover_mdns()`
retain explicit source control. Unsupported products are filtered before the public API
yields devices, so relay-only Switches remain outside the library's lighting-device fleet.
Phase 14 now owns the remaining Thread hardware revalidation and consumer guidance.

**Shipped:** v1.0 Ceiling Save-on-Exit (2026-06-12) and v1.1 Wire Reliability
(2026-07-26). See `.planning/MILESTONES.md`.
**Also shipped post-v1.0:** Phase 1 discovery unification (verified 2026-06-13), which
rebuilt `discover_devices()` on `_discover_with_packet()` with hoisted DoS serial
validation and first-wins per-serial dedup.

**Spike series completed 2026-07-16** (`.planning/spikes/`, packaged as the
`spike-findings-lifx-async` skill): five real-hardware experiments that disproved the
"switch to threading" hypothesis and located the actual reliability levers.

## Current Milestone: v2.0 Thread/IPv6 Support

**Goal:** A Thread device becomes a first-class device in this library: found, addressed,
controlled and animated without the caller needing to know it is on Thread. The v1.1
wire-reliability findings are then revalidated over Thread, because every one of them was
measured on WiFi/IPv4.

**Target features:**

- **Land `feat/ipv6-thread-support`** (3 commits, roughly 1100 lines, not yet on `main`):
  IPv6 device addresses, socket family following the target address, AAAA parsing that
  prefers routable addresses over link-local, per-instance mDNS record accumulation across
  packets, PTR retransmit per RFC 6762 5.2, follow-up A/AAAA queries for SRV targets whose
  address records did not fit one reply, and the animator frame-socket family fix
- **mDNS ephemeral-port bind as its own regression-tested requirement.** Measured 25
  devices found bound ephemeral against 9 bound on 5353 with `SO_REUSEPORT`: system mDNS
  daemons were stealing legacy-unicast replies. This is an IPv4 defect that predates
  Thread, so it earns a test of its own rather than riding along uncredited
- **`discover()` runs broadcast and mDNS together**, merging by serial, so every existing
  caller reaches Thread devices without opting in
- **Source-specific discovery remains public.** `discover_udp()` exposes UDP-only
  enumeration alongside the existing mDNS-only `discover_mdns()`, while `discover()`
  remains the dual-source default
- **Overlapping UDP enumeration is single-flight.** Compatible `discover()` and
  `discover_udp()` callers share one active broadcast sweep and its already-seen records,
  so caller bursts cannot multiply the measured rebroadcast response load
- **`find_by_serial()` runs both legs concurrently, first hit wins.** Neither alone is
  sufficient: broadcast covers WiFi devices whose firmware does not advertise over mDNS,
  mDNS covers Thread devices that have no IPv4 address to broadcast to
- **`find_by_ip()` accepts an IPv6 literal** instead of returning `None`
- **Every `Device` exposes `connectivity` as `"wifi"` or `"thread"`.** Exact private TXT
  `tm=2` means Thread; every other case means WiFi. The low-level mDNS record and generator
  become explicitly private in Phase 11
- **Synthetic multi-packet mDNS tests** exercising cross-packet record accumulation and
  the follow-up A/AAAA path, neither of which two Thread devices can trigger
- **Thread revalidation (SEED-001)** of discovery coverage, retry schedule and animation
  flow control, evidenced per device class as hardware becomes available
- **Consumer guidance docs** for broadcast-first integrations

## Shipped Milestone: v1.2 Theme Library Update (2026-08-27)

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
categories and dispositions, and ship at their full untruncated lengths.

## Core Value

Commands stick, devices are found, streaming never starves control traffic — and a theme
by name looks like the theme of that name in the LIFX app.

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

### Active

<!-- v2.0 Thread/IPv6 Support. Authoritative REQ-IDs live in .planning/REQUIREMENTS.md;
     the list below is the milestone's scope in prose. -->

**Milestone v2.0: Thread/IPv6 Support.** Full detail in `## Current Milestone` above.

- [ ] Land `feat/ipv6-thread-support` onto `main` with the network, mDNS and animation
      changes intact
- [x] mDNS ephemeral-port bind, regression-tested in its own right as an IPv4 defect
- [x] `discover()` runs a broadcast leg and an mDNS leg, merged by serial
- [x] `discover_udp()` preserves explicit UDP-only enumeration, and overlapping compatible
      `discover()` / `discover_udp()` calls share one active UDP sweep
- [x] `find_by_serial()` runs both legs concurrently, first hit wins
- [x] `find_by_ip()` resolves a device from an IPv6 literal
- [x] `Device.connectivity` exposes `"thread"` for exact private TXT `tm=2` and `"wifi"`
      otherwise; the low-level mDNS record and generator are explicitly private
- [x] Synthetic multi-packet mDNS tests for cross-packet accumulation and follow-up
      A/AAAA queries
- [ ] THREAD-01 / SEED-001: revalidate discovery coverage, retry schedule and animation
      flow control over Thread, evidenced per device class as hardware becomes available
- [ ] Consumer guidance docs for broadcast-first integrations

Carried-forward candidates, not in v2.0 scope:

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
- Prior Thread work lives on `feat/ipv6-thread-support`: `b49400b` (network and mDNS),
  `b88cdb9` (`scripts/ipv6_thread_probe.py`, a three-stage records/ports/connect hardware
  probe driving the library's own primitives), `2f884f5` (animator frame-socket family).
  `backup/ipv6-thread-pre-rebase` holds the pre-rebase state.

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
*Last updated: 2026-08-31 after Phase 13 completion*
