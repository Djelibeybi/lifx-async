# Milestones

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
