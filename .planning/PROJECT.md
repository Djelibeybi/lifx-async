# lifx-async — Theme Library Update

## Current State (post-v1.1)

**v1.1 Wire Reliability shipped 2026-07-26.** Phases 2–5 delivered and verified; all 13
requirements (DISC-01..03, RETRY-01..04, ANIM-01..04, DOCS-01..02) satisfied. Measured
outcomes: discovery re-broadcast took a single call from a median 48/73 devices to 73/73;
the retry reshape cut packets-per-request from 1.37 to 1.017 and latency from 62 ms to
12.6 ms; ack-gated animation pacing won directionally on every device ever measured
(1.28×–5.25×), accepted by operator ruling over a recorded statistical FAIL rather than a
statistical pass (`04-RULING.md`).

The close-out audit found no unsatisfied requirements, no orphans, and no blocking
integration gaps across 7 verified cross-phase connections. Two items it raised were
fixed before archiving: phase 4's VALIDATION.md was reconciled (all four phases are now
Nyquist-compliant), and `api.discover()` no longer lets a slow or dead device expire the
discovery idle window (quick task 260726-824). See
`milestones/v1.1-MILESTONE-AUDIT.md`.

**Next milestone:** v1.2 Theme Library Update — started 2026-08-14 (see below).

**Shipped:** v1.0 Ceiling Save-on-Exit (2026-06-12) — see `.planning/MILESTONES.md`.
**Also shipped post-v1.0:** Phase 1 discovery unification (verified 2026-06-13) — rebuilt
`discover_devices()` on `_discover_with_packet()` with hoisted DoS serial validation and
first-wins per-serial dedup.

**Spike series completed 2026-07-16** (`.planning/spikes/`, packaged as the
`spike-findings-lifx-async` skill): five real-hardware experiments that disproved the
"switch to threading" hypothesis and located the actual reliability levers.

## Current Milestone: v1.2 Theme Library Update

**Goal:** Resync `lifx.theme.library` with the LIFX app's live theme set — 139 non-sport
themes captured from hardware on 2026-08-14 — without silently changing colours existing
callers already depend on.

**Target features:**

- Import the 139 non-sport app themes as ASCII slugs, carrying the app's display name and
  category as metadata
- Resync the 27 shared slugs to the app's values (6 differ only by a uniform ×1.1087
  brightness scale, 19 are genuinely redefined); every overwritten palette keeps a
  `*_legacy` alias holding the current values
- Resolve the 30 orphaned library keys — map the renames (`aurora_borealis` → Aurora 🌌,
  `forest` → Forrest 🌳), decide keep-or-deprecate for the remainder
- Expose the app's category taxonomy as queryable theme metadata
- Establish the true colour count for the 26 themes that returned exactly 16 colours, or
  record on the record that it cannot be established from a device
- Ship the capture tooling (`enumerate_themes.py`, `sweep_themes.py`,
  `analyse_themes.py`) so a future app update can be resynced rather than re-derived

**Key context:**

- Raw capture lives in `.claude/theme-capture/` — `themes.jsonl` (179 records: name,
  category, picker index, palette), `picker-order.txt`, and `tools/`.
- Sport categories are dropped: 🏆 AUSSIE RULES (19), 🏉 LEAGUE (17), 🏉 UNION (4) = 40
  themes. That sidesteps 5 of the 6 slug collisions (`brisbane`, `melbourne`, `sydney`,
  `gold_coast`, `new_zealand`). `christmas` still collides — Holidays against Archives —
  but both carry identical palettes, so it collapses cleanly.
- **Palette order is meaningless.** The app shuffles the sequence on every application;
  the same theme applied twice returns the same colours in a different order. All
  comparison is unordered-set comparison.
- **16 is the protocol palette ceiling** for both `SetTileEffect` and
  `SetMultiZoneEffect`, so no device-based method can ever recover a palette longer than
  16. The 26 exactly-16 themes (all 10 of 🎨 ART SERIES among them) may or may not be
  clipped, and the capture method cannot tell. Resolving this needs a non-device source.
- Capture came from a single product (Tile, product 55). Palette is effect configuration
  rather than rendered output, so product-invariance is expected but untested.
- Themes are server-driven (`com.lifx.shared.data.cloud.themes.ThemeDTO`, cached in a
  local SQLite table) — no theme name appears in the APK. The internal endpoints
  (`api.lifx.com/themes/v2` 401, `themes/v1/palette` 405 POST-only) are undocumented and
  were deliberately not called.

## Shipped Milestone: v1.1 Wire Reliability (2026-07-26)

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

## What This Is

`lifx-async` is a mature, zero-dependency, type-safe async Python library for controlling
LIFX smart devices over the local network (published on PyPI as `lifx-async`). v1.1 made
its wire behaviour measurably as reliable as the best reference clients. This milestone
turns to what the library *renders*: its built-in theme palettes, transcribed from photons
years ago and never resynced, are now mostly wrong — the app ships 179 themes, the library
carries 57, and most shared names no longer match.

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
  across retry attempts (`connection.py`) — existing; retry reshape must preserve it
- ✓ Zero-allocation prebaked packet templates for animation (`animation/packets.py`) —
  existing; flow control must preserve this send path
- ✓ Discovery re-broadcast on an escalating schedule (DISC-01..03) — v1.1
- ✓ Retry schedule reshape (RETRY-01..04) — v1.1
- ✓ Animation-layer-owned ack-gated flow control (ANIM-01..04) — v1.1
- ✓ Reliability documentation (DOCS-01..02) — v1.1
- ✓ Consumer time cannot expire the discovery idle window — v1.1 close-out
  (quick task 260726-824)

### Active

<!-- Next milestone's scope. REQ-IDs are defined in a fresh REQUIREMENTS.md by
     /gsd-new-milestone; these are carried-forward candidates, not commitments. -->

v1.2 Theme Library Update — REQ-IDs defined in `.planning/REQUIREMENTS.md`:

- [ ] Import the 139 non-sport app themes with ASCII slugs, display names and categories
- [ ] Resync the 27 shared slugs; `*_legacy` aliases preserve every overwritten palette
- [ ] Resolve the 30 orphaned library keys (renames mapped, remainder kept or deprecated)
- [ ] Expose the category taxonomy as queryable metadata
- [ ] Settle the 26 exactly-16-colour themes: true count, or a recorded finding that a
      device cannot supply it
- [ ] Ship the capture tooling for future resyncs

Carried-forward candidates, not committed to v1.2:

- [ ] PERS-01: generalise `state_file` persistence into a reusable mixin (deferred since
      2026-06-11)
- [ ] THREAD-01 / SEED-001: revalidate wire behaviour over Thread/IPv6 when LIFX Thread
      firmware lands (dormant; acknowledged as deferred at the v1.1 close)
- [ ] Spike 006: measure the impact of publishing tuning constants vs behaviour only —
      the D5-09 rule is disputed and remains an OPEN decision

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
- **Calling the undocumented LIFX theme endpoints** — `api.lifx.com/themes/v2` and
  `themes/v1/palette` are internal, unauthenticated to us, and deliberately untouched;
  the device stays the source of truth
- **MirrorLight (PR #194)** — complete and open, lands on its own schedule, not folded
  into this milestone (user decision, 2026-08-14)

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
- Theme capture (2026-08-14): the app was driven over adb — apply a theme as MORPH, tap
  Save (the palette does not reach the device until Save), then read it back over the LAN
  via `StateTileEffect`, which `MatrixLight.get_effect()` slices to `palette_count` with
  brightness and kelvin intact. Method and caveats: `.claude/theme-capture/README.md`.

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
| Overwrite redefined themes but keep `*_legacy` aliases | App accuracy is the point of the milestone, but 19 palettes change under callers who never asked for it; an alias makes the old values recoverable by name instead of by git archaeology | Decided 2026-08-14 — v1.2 scope |
| ASCII slugs, drop the sport categories | Emoji are poor Python identifiers and CLI arguments; dropping AFL/League/Union removes 5 of the 6 slug collisions outright rather than inventing suffixes for club branding | Decided 2026-08-14 — v1.2 scope |
| Device readback as the only capture source | Themes are server-driven and absent from the APK; the internal endpoints are undocumented and were not called. Accepted cost: palettes are capped at the protocol's 16 colours and order is lost | Applied to the 2026-08-14 capture; the 16-colour consequence is an open v1.2 question |
| Reset the discovery idle timer on consumer resume, not just before the yield | `api.discover()` constructs a Device per response; those round trips would otherwise spend the idle window and truncate the sweep | ✓ Shipped — v1.1 close-out (260726-824). Overall timeout untouched, so a slow consumer still cannot extend discovery indefinitely |

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
*Last updated: 2026-08-14 at the start of the v1.2 Theme Library Update milestone*
