# Phase 5: Reliability Documentation - Research

**Researched:** 2026-07-17
**Domain:** User-facing documentation (mkdocs-Material-style site built with zensical) for v1.1 wire-reliability behaviour
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Placement & navigation
- **D5-01:** Extend existing pages — no new dedicated reliability page, no new nav
  entries in `mkdocs.yml`. DOCS-02 streaming guidance lives in
  `docs/user-guide/animation.md`; DOCS-01 wake-tail guidance lives in
  `docs/user-guide/troubleshooting.md` with a short entry in `docs/faq.md` that
  links to it.
- **D5-02:** Targeted cross-links only: `docs/user-guide/ceiling-lights.md` links to
  the wake-tail section; `docs/user-guide/animation.md` and the troubleshooting
  wake-tail section link to each other where streaming meets gen4 power-save.
  No broad linking from API reference or getting-started pages.

#### Wake-tail guidance (DOCS-01)
- **D5-03:** Concise + key numbers: what happens (gen4 power-save adds a sub-250 ms
  wake tail to the first command after idle), when it matters, what to do. No spike
  methodology or measurement narrative.
- **D5-04:** Concrete polling recipe: a small code snippet (periodic state poll,
  e.g. `get_power()`/`get_color()` loop) with a recommended interval **sourced from
  the Spike 001 findings** — the researcher must extract the supportable number from
  `.claude/skills/spike-findings-lifx-async/references/concurrency-and-keepalive.md`
  (and raw spike data if needed). Do not invent an interval.
- **D5-05:** Gen4 identification is concrete: document which product families /
  firmware versions are gen4 (via `host_firmware` version and/or the products
  registry) so readers can positively identify affected devices. The researcher
  determines the supportable identification method — do not hand-wave.
- **D5-06:** "The library deliberately ships no keepalive daemon" is a visible
  admonition callout (not an inline sentence), including the why: Spike 001 measured
  zero idle-related loss on healthy networks; periodic polling is the application's
  choice, not the library's job.

#### Streaming-consumer guidance (DOCS-02)
- **D5-07:** Shape: short narrative of what the animation layer now handles
  (ack-gated pacing, latest-frame-wins) + an explicit do-not-reimplement list
  (your own acks, keepalives, frame-retry wrappers) + a minimal streaming-loop code
  example showing the consumer's whole job: generate frames, call `send_frame()` at
  the chosen FPS.
- **D5-08:** Per-device-class FPS guidance with concrete numbers: ~20 FPS is the
  platform ceiling over WiFi/Set64; larger multi-packet matrix devices saturate
  sooner — the Ceiling Capsule (16×8 zones, 3 packets/frame) sustains ~10 FPS.
  Explain the observable symptom of oversending: stutter caused by latest-frame-wins
  dropping frames — degradation by design, never a backlog or freeze. Source: the
  04-13 operator visual verdict (recorded in `.planning/STATE.md`), explicitly
  earmarked for DOCS-02.
- **D5-09:** Behavioural contract only: document observable behaviour (delivery is
  paced against device acks; a saturated device causes frame drops; no consumer
  configuration exists). Do NOT document internal tuning constants (probe placement,
  gate threshold, ack expiry) — they are internal and may change.

#### Coverage breadth
- **D5-10:** Stale-content audit: audit existing `docs/` prose pages (user-guide,
  faq, getting-started, architecture) for claims made stale by the v1.1 work — old
  advice about discovery misses, retry timing, or streaming workarounds — and fix
  contradictions in place. No new "v1.1 reliability overview" page or section.
- **D5-11:** Audit scope is prose pages only. Source docstrings (which feed
  `docs/api/*.md`) stay untouched; if the audit discovers a flatly wrong docstring,
  surface it as a finding rather than editing source in this phase.

### Claude's Discretion
- Section headings, placement/ordering within the host pages, admonition type and
  exact wording (match existing docs conventions).
- Code example style — match the existing examples in `docs/user-guide/animation.md`.
- Whether the FAQ addition is one entry or two (wake-tail + "why no keepalive?").
- Australian English throughout (project rule).

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DOCS-01 | Gen4 power-save wake-tail behaviour documented (sub-250 ms; when apps may want periodic polling) | All figures extracted and verified (§Verified Numbers): sub-250 ms bound (max observed 224 ms), zero idle loss, polling interval 10–15 s (15 s spike-tested, 10 s Photons precedent), gen4 identification via `host_firmware.version_major >= 4` empirically verified against the test fleet |
| DOCS-02 | Streaming-consumer guidance (LedFx pattern): what the animation layer now handles, what consumers should not reimplement | Shipped behaviour confirmed in `src/lifx/animation/animator.py` + `flow.py` (§Shipped Animation Behaviour): `send_frame()` returns `AnimatorStats` with `gated`/`acks_outstanding`; D4-01/D4-02 wording verified from 04-CONTEXT.md; FPS numbers verified from STATE.md 04-13 verdict |
</phase_requirements>

## Summary

This is a documentation-only phase with zero new dependencies and zero code changes. The
research questions were all answerable from project-internal sources plus two live
verifications: (1) a read-only firmware probe against the quiesced test fleet, which
empirically confirmed the gen4 identification method, and (2) a baseline
`uv run zensical build`, which succeeds in ~8 s with exactly 8 pre-existing anchor
warnings, all in `docs/api/effects.md` and `docs/api/index.md` — outside this phase's
edit scope.

Every number the locked decisions demand is now pinned with provenance: the wake-tail
figures and the "no keepalive daemon" rationale come from Spike 001's raw data
(315 trials, 7 bulbs, 3 generations, zero loss anywhere); the polling interval is
15 s (the spike-tested cadence) corroborated by Photons' DeviceFinder polling
`GetColor` every 10 s (verified in the Photons source checkout); gen4 identification
is `host_firmware.version_major >= 4`, verified live against gen2 (fw 2.90), gen3
(fw 3.50), and two gen4 devices (both fw 4.112); the FPS guidance is ~20 FPS platform
ceiling with the Capsule (16×8 zones, 3 packets/frame) sustaining ~10 FPS, per the
04-13 operator verdict in STATE.md.

The stale-content audit (D5-10) found concrete superseded claims on five prose pages,
enumerated below with line numbers — the largest being the "Batched Discovery" and
"Fire-and-Forget Mode" workaround sections in `advanced-usage.md`, the multi-pass
discovery recipe in `troubleshooting.md`, and pervasive "30+ FPS" framing in
`animation.md` and `architecture/overview.md`.

**Primary recommendation:** Plan three edit clusters — (1) DOCS-01 content in
troubleshooting.md + FAQ entry + ceiling-lights cross-link, (2) DOCS-02 content in
animation.md including fixing that page's own stale claims in the same pass, (3) the
remaining stale-content fixes (advanced-usage.md, architecture/overview.md,
troubleshooting.md discovery/retry sections) — each verified by `uv run zensical build`
producing no new warnings.

## Project Constraints (from CLAUDE.md)

Directives from `./CLAUDE.md` and the user's global CLAUDE.md that bind this phase:

- **Australian English spelling** throughout all new prose (global rule; also D5 discretion note)
- **Never update `docs/changelog.md`** — auto-generated by the release workflow
- **Never edit generated files** (`src/lifx/products/registry.py`, protocol files) — not needed this phase
- **uv exclusively**: `uv run zensical build`, `uv run zensical serve`; never pip/poetry
- **Git commits**: `git commit -s`, GPG-signed (automatic)
- **Docs pipeline**: `uv run zensical build` + `uv run llmstxt-standalone build` (CI runs both)
- **HSBK dual formats gotcha**: animation examples use raw uint16 tuples, not the float `HSBK` class — existing animation.md examples already follow this; new examples must too
- **`get_color()` returns `(color, power, label)`** — the most efficient single-request poll; use it in the D5-04 polling recipe
- **Internal specs go in `.claude/` not `docs/`** (memory: feedback_specs_location) — nothing from `.planning/` or spike narratives leaks into the published docs (D5-03 already mandates no methodology narrative)
- **CCT terminology** (memory: feedback_cct_terminology): use "CCT/brightness-only", never "white-only" — unlikely to arise but binding if device classes are described

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Wake-tail guidance (DOCS-01) | Docs site (`docs/user-guide/troubleshooting.md`) | `docs/faq.md` (link-only entry) | D5-01 locked placement |
| Streaming guidance (DOCS-02) | Docs site (`docs/user-guide/animation.md`) | — | D5-01 locked placement |
| Cross-links | `docs/user-guide/ceiling-lights.md`, animation ↔ troubleshooting | — | D5-02 locked; no nav changes |
| Stale-content fixes | Docs prose pages (user-guide, faq, getting-started, architecture) | — | D5-10/D5-11; `docs/api/*.md` and source docstrings out of scope |
| Build verification | Local toolchain (`uv run zensical build`) | CI docs workflow | Success criterion 3 |

No runtime code tier is touched. All work lands in markdown files under `docs/`.

## Standard Stack

### Core (existing — no additions)
| Tool | Version | Purpose | Why Standard |
|------|---------|---------|--------------|
| zensical | dev dependency (already in lockfile) | Builds the docs site from `mkdocs.yml` + `docs/` | Project's existing docs builder; success criterion names it `[VERIFIED: build ran successfully in this session]` |
| mkdocs-Material markdown conventions | via zensical | Admonitions, superfences, tabs | `mkdocs.yml` enables `admonition`, `pymdownx.details`, `pymdownx.superfences`, `pymdownx.tabbed` etc. `[VERIFIED: mkdocs.yml:156-189]` |
| llmstxt-standalone | dev dependency | llms.txt build in docs pipeline | CLAUDE.md docs commands `[CITED: CLAUDE.md]` |

### Alternatives Considered
None — the toolchain is locked by the project. **No packages are installed by this phase.**

**Installation:** none required (`uv sync` already provides the toolchain).

## Package Legitimacy Audit

No external packages are installed by this phase. **Packages removed due to [SLOP] verdict:** none. **Packages flagged as suspicious [SUS]:** none.

## Verified Numbers (the load-bearing facts)

These are the figures the locked decisions require. Each is pinned to its source.

### DOCS-01: gen4 wake tail (Spike 001, run 20260716-201013 — 315 trials, 1573 probes, 7 bulbs across 3 generations)

| Fact | Value | Provenance |
|------|-------|------------|
| Packet loss when idle (0–120 s) | **Zero, everywhere** — every first probe after every idle duration answered within 2 s, all 7 bulbs, keepalive or not | `[VERIFIED: .planning/spikes/001-modem-sleep-keepalive/README.md Results; summary JSON]` |
| Wake-tail bound | **Sub-250 ms** (max observed first-probe RTT without keepalive: 224 ms) | `[VERIFIED: spike 001 README — "max 224→81 ms"]` |
| Keepalive effect, pooled at 60 s idle | median 16.5→8.9 ms, p90 69.8→42.3 ms, max 224→81 ms | `[VERIFIED: spike 001 README Results]` |
| Effect concentration | Gen4 downlights only (e.g. Downlight 2: median 45.1→7.0 ms); gen2/gen3 show no meaningful difference; gen2 is the fastest in the fleet (2–4 ms medians, no power-save signature) | `[VERIFIED: spike 001 README Results]` |
| Mechanism (plausible, not confirmed by LIFX) | ESP32 WiFi power-save (modem sleep) with fast wake | `[ASSUMED — spike README labels this "likely"; LIFX has neither confirmed nor denied]` |
| Mesh-network caveat | Unverified on mesh networks (TP-Link Deco/Orbi); the effect may be larger there | `[CITED: concurrency-and-keepalive.md caveat]` |
| No keepalive daemon rationale (D5-06 admonition) | Zero idle-related loss on healthy networks; keepalive is a modest tail-latency optimisation only, so it is the application's choice | `[VERIFIED: spike 001 verdict — "PARTIAL: strong modem-sleep hypothesis INVALIDATED; keepalive gives a modest, consistent tail-latency benefit on gen4 only"]` |

### DOCS-01: polling interval (D5-04 — do not invent)

| Fact | Value | Provenance |
|------|-------|------------|
| Spike-tested cadence | **15 s** (unicast `GetService` every 15 s was the measured keepalive arm; it produced the tail-shrink figures above) | `[VERIFIED: spike 001 README frontmatter + Glowup parity design]` |
| Corroborating precedent | Photons' DeviceFinder refreshes device state with `GetColor` every **10 s** (and "gets this incidentally") | `[VERIFIED: /Volumes/External/Developer/Djelibeybi/photons/modules/photons_control/device_finder.py — InfoPoints.LIGHT_STATE = Point(LightMessages.GetColor(), [...], 10)]` |
| **Supportable docs claim** | Poll every **10–15 seconds**; the code snippet should use 15 s (the directly spike-tested cadence). Any packet that makes the device respond works; `get_color()` is the natural choice (one request returns colour + power + label) | Synthesis of the two verified numbers — no interpolation risk since both endpoints are attested |

### DOCS-01: gen4 identification (D5-05 — determined and empirically verified)

**Method: host firmware major version.** `(await device.get_host_firmware()).version_major >= 4`
identifies gen4. After `async with` context entry, the cached `device.host_firmware`
property is already populated (fetched in `_setup()`).

Live verification this session (read-only `GetHostFirmware`/`GetVersion` against the
quiesced test fleet):

| Device | Product ID | Host firmware | Generation |
|--------|-----------|---------------|------------|
| Test Downlight 5 | 36 | **2.90** | gen2 |
| System Test Tiles I | 55 | **3.50** | gen3 |
| Test Downlight 2 | 224 | **4.112** | gen4 |
| My Office Ceiling Capsule | 201 | **4.112** | gen4 |

`[VERIFIED: live probe 2026-07-17 using lifx-async Device.from_ip()]`

Supporting evidence:
- The codebase itself already keys generation-specific behaviour on firmware major:
  `devices/base.py:677` applies the gen3 MAC-address quirk when `version_major == 3` `[VERIFIED: src/lifx/devices/base.py:677]`
- Photons classifies product 201 as `Family.LCMX` — its post-LCM3 (newest) family bucket `[VERIFIED: photons_products/registry.py — LCMX_LIFX_CEILING_13x26_US, pid=201, family=Family.LCMX]`
- **The lifx-async products registry has NO generation/family field** (`ProductInfo` carries pid, name, vendor, capabilities, temperature_range, min_ext_mz_firmware only) — the docs must NOT claim generation lookup via the registry `[VERIFIED: src/lifx/products/registry.py ProductInfo dataclass]`
- Firmware-major ⇔ generation across the whole product line is generalised from the 4 probed devices + the base.py gen3 quirk; treat "all gen4 products report major 4" as strongly supported but see Assumptions Log A2

**Docs framing:** "gen4" = devices whose host firmware reports major version 4 or later
(products released roughly from the LIFX Ceiling/newer-Downlight era onward). Show the
one-liner check; do not enumerate product IDs (the registry can't support it and the
list would rot).

### DOCS-02: FPS guidance (D5-08 — verified against STATE.md)

| Fact | Value | Provenance |
|------|-------|------------|
| Platform ceiling | **~20 FPS** over WiFi/Set64 — "a platform ceiling, not a client defect" | `[VERIFIED: REQUIREMENTS.md Out of Scope table; animation-flow-control.md Constraints]` |
| Capsule sustainable rate | **~10 FPS** at its 16×8-zone (128 zones), 3-packets-per-frame chain shape | `[VERIFIED: STATE.md 04-13 entry + Blockers section — "the Capsule's sustainable rate is ~10 FPS at its 16x8/3-packets-per-frame chain shape"]` |
| Oversending symptom | **Stutter** from latest-frame-wins dropping frames — degradation by design, never a backlog, freeze, or crawl | `[VERIFIED: STATE.md 04-13 operator verdict — "Geometry was fine. It was as smooth as the tiles. No multi-second freezes but it stuttered throughout."]` |
| Capsule dims (corrected) | 16×8 zones = 128 zones; 26 in × 13 in physical (early "13×26 zone grid" was a units mix-up) | `[VERIFIED: STATE.md + REQUIREMENTS.md ANIM-04 + fleet memory]` |

Do NOT write "30+ FPS" anywhere; that framing is what the stale-content audit removes.

## Shipped Animation Behaviour (what DOCS-02 describes)

Confirmed against the Phase 4 shipped code:

- `Animator.send_frame()` is still synchronous and returns `AnimatorStats` `[VERIFIED: src/lifx/animation/animator.py]`
- `AnimatorStats` public fields: `packets_sent: int`, `gated: bool` ("whether this frame was dropped by ack-gated flow control… latest-frame-wins"), `acks_outstanding: int` `[VERIFIED: animator.py AnimatorStats dataclass]`
- Flow control is internal (`lifx/animation/flow.py` `AckGate`); there is **no consumer-facing configuration** `[VERIFIED: flow.py + D4-02 in 04-CONTEXT.md]`
- D4-01 (behaviour to state): frame delivery is paced against device acknowledgements; when the device falls behind, new frames are dropped (never queued) — latest-frame-wins
- D4-02 (behaviour to state): no downstream toggle — consumers just send frames; the library decides delivery strategy

**D5-09 boundary — what NOT to document:** probe placement (which packet carries
`ack_required`), the gate threshold (2 outstanding), and the ack expiry (~1 s). These
appear in the `Animator` docstring (which feeds `docs/api/animation.md` — untouched per
D5-11) but must not be restated in the user guide. `stats.gated` and
`stats.acks_outstanding` are observable public API and MAY be referenced (e.g. in a
monitoring aside), but the minimal streaming loop should stay minimal per D5-07.

**Do-not-reimplement list (D5-07), grounded in what the layer now owns:**
consumers must not add their own acknowledgement tracking, keepalive daemons, or
frame-retry wrappers. Retrying a dropped frame is actively wrong: latest-frame-wins
means the correct recovery is simply the next frame.

## Architecture Patterns

### Docs conventions on the host pages (match these)

- **Admonitions:** Material style with custom title — `!!! note "State Properties Require Recent Data"` and `!!! tip "Choosing the right origin"` are the two in-repo exemplars, both in `docs/user-guide/ceiling-lights.md` (lines 126, 373). `admonition` + `pymdownx.details` are enabled in `mkdocs.yml`. For the D5-06 keepalive callout, `!!! note "…"` or `!!! info "…"` with a custom title matches convention. `[VERIFIED: grep across docs/ + mkdocs.yml]`
- **animation.md code style:** plain fenced ```python blocks, full runnable snippets with `import asyncio` + `asyncio.run(main())` for top-level examples, shorter fragments for patterns; raw uint16 HSBK tuples `(hue, sat, bright, kelvin)`; the canonical loop shape is `stats = animator.send_frame(frame)` + `await asyncio.sleep(1 / target_fps)` in try/finally with `animator.close()` `[VERIFIED: docs/user-guide/animation.md]`
- **troubleshooting.md structure:** `### <Problem>` headed sections with **Symptom / Causes / Solution** bold labels and code blocks; page has a Table of Contents list at top (new sections need a TOC entry) `[VERIFIED: docs/user-guide/troubleshooting.md:5-11]`
- **faq.md structure:** `## <Category>` / `### <Question>` — the wake-tail entry belongs under `## Performance` or `## Troubleshooting` `[VERIFIED: docs/faq.md]`
- **No nav changes:** all four host pages are already in `mkdocs.yml` nav `[VERIFIED: mkdocs.yml:191-221]`

### Recommended edit plan shape

```
docs/
├── user-guide/troubleshooting.md   # + wake-tail section (DOCS-01) + fix stale discovery/retry advice
├── user-guide/animation.md         # + streaming-consumer section (DOCS-02) + fix own stale claims
├── faq.md                          # + short wake-tail entry linking to troubleshooting
├── user-guide/ceiling-lights.md    # + one cross-link to wake-tail section
├── user-guide/advanced-usage.md    # stale-content fixes (batched discovery, fast=True section)
└── architecture/overview.md        # stale-content fixes (30+ FPS, Layer 5 description)
```

### Pattern 1: Anchor-stable cross-links

Cross-page links use relative paths with heading anchors, e.g.
`[Animation Guide](animation.md)` and `[FAQ](../faq.md)` from user-guide pages
`[VERIFIED: existing links in troubleshooting.md:404-407]`. The toc extension
generates anchors from headings (`toc permalink: true`). Choose stable heading text
for the wake-tail section since three pages will link to it (faq.md via
`user-guide/troubleshooting.md#<anchor>`, ceiling-lights.md and animation.md via
`troubleshooting.md#<anchor>`).

### Anti-Patterns to Avoid

- **Restating internal tuning constants** in user-guide prose (violates D5-09)
- **Spike/measurement narrative** in the docs (violates D5-03) — numbers yes, methodology no
- **New pages or nav entries** (violates D5-01)
- **Editing `docs/api/*.md` mkdocstrings content or source docstrings** (violates D5-11)
- **Editing `docs/changelog.md`** (auto-generated)
- **Inventing product-ID lists for gen4** — the registry has no generation field; use the firmware-major check

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Numbers for the docs | New estimates or rounded-up figures | The verified figures in §Verified Numbers, verbatim provenance | D5-04/D5-05/D5-08 explicitly forbid invention |
| Gen4 detection recipe | Product-ID whitelist | `host_firmware.version_major >= 4` one-liner | Registry has no generation field; ID lists rot |
| Polling snippet | Custom keepalive class/daemon example | Plain `get_color()` + `asyncio.sleep(15)` loop | The whole point (D5-06) is that no daemon ships; the example must model application-level simplicity |
| Streaming example | Frame queue/retry scaffolding | `send_frame()` + `sleep(1/fps)` loop (existing animation.md pattern) | The layer owns pacing; consumer job is generate-and-send |

**Key insight:** this phase's failure mode is not missing libraries — it is documentation
drift. Every claim must trace to a verified source or the shipped code.

## Stale-Content Audit Findings (D5-10) — enumerated fixes

Audited: all of `docs/user-guide/*.md`, `docs/faq.md`, `docs/getting-started/*.md`,
`docs/architecture/*.md`, `docs/index.md` (grep for FPS/packet-loss/discovery/retry/
keepalive/ack claims + full reads of the four host pages and advanced-usage.md).

### docs/user-guide/animation.md (fix in the DOCS-02 pass)
1. **Line 4:** "push color data at 30+ FPS" — contradicts the ~20 FPS platform ceiling. Reword to ~20 FPS framing.
2. **Line 10:** "High frame rates (20+ FPS)" — adjust to match ceiling framing.
3. **Lines 44, 71, 276:** examples use `await asyncio.sleep(1 / 30)  # 30 FPS` — above the ceiling; change to 20 FPS (and the Capsule-class caveat lands in the new DOCS-02 section).
4. **Lines 329-340 "Flickering or Glitches":** cause given as "Packet loss on the network", advice includes "Accept that some packet loss is normal for UDP" — superseded. The primary observable cause is now device saturation: latest-frame-wins drops frames (stutter by design). Rewrite the section to distinguish saturation-stutter (reduce FPS toward the device's sustainable rate) from genuine network loss.

### docs/user-guide/troubleshooting.md (fix in the DOCS-01 pass)
5. **Lines 89-113 "Partial Device Discovery":** solution is a manual multi-pass `discover_devices()` loop — superseded by DISC-01: a single `discover_devices()` call now re-broadcasts `GetService` on an escalating schedule within the discovery window. Replace the workaround with "one call already re-broadcasts; increase `timeout` if needed".
6. **Line 220:** `async with discover(timeout=10.0) as group:` — **pre-existing API misuse**: `discover()` is an async generator (`async for device in discover()`), not a context manager `[VERIFIED: src/lifx/api.py:746 + correct usage in faq.md:70]`. Fix while editing the page.
7. **Line 220 comment:** "# Default is 3.0" — stale. `DISCOVERY_TIMEOUT` is **15.0 s** `[VERIFIED: src/lifx/const.py:28]`.
8. **Lines 152-185 "Connection Drops":** recommends an application-level exponential-backoff retry wrapper. Partially stale: RETRY-01..04 reshaped the library's own retry (first window floored ~200 ms, escalating gaps, listen-during-backoff, wall-time honoured). App-level retry of whole operations remains legitimate, but the framing should note the library already retransmits within each request's timeout — the wrapper is for whole-operation failures, not per-packet reliability.

### docs/user-guide/advanced-usage.md
9. **Lines 280-303 "Batched Discovery":** two-pass quick/thorough discovery pattern — superseded by DISC-01 re-broadcasts (same rationale as #5).
10. **Lines 553-594 "Fire-and-Forget Mode for High-Frequency Animations":** recommends `set_extended_color_zones(..., fast=True)` device-method loops "at ~30 FPS" as the streaming pattern, and says "waiting for device acknowledgement creates unacceptable latency". This is the pre-v1.1 streaming workaround DOCS-02 supersedes: streaming consumers should use the Animation layer, which paces via acks *without* per-call latency. Rework to point at the animation guide for sustained streaming; `fast=True` remains valid for occasional low-latency one-shots. Also fix the 30 FPS figure.
11. **Lines 327-346 "Robust Error Handling":** same soft-stale framing as #8 (retry wrapper) — contextualise, don't delete.

### docs/architecture/overview.md
12. **Line 186:** "High-frequency frame delivery for real-time effects (30+ FPS)" → ~20 FPS ceiling framing.
13. **Layer 5 bullets + Key Files (lines 188-197):** "Direct UDP: Bypasses request/response" is still true but incomplete — add ack-gated pacing as internal behaviour and add `animation/flow.py` to Key Files.

### docs/faq.md
14. **Lines 47-61 "Why can't discovery find my devices?":** advice is compatible with v1.1 (timeout increase still valid) — optionally add that discovery re-broadcasts automatically. Minor; not a contradiction.
15. **Addition (not a fix):** the D5-01 FAQ entry (wake-tail, optionally + "why no keepalive?") linking to the troubleshooting section.

### docs/getting-started/*, docs/index.md, docs/user-guide/ceiling-lights.md, effects pages
16. **No stale reliability claims found.** effects-troubleshooting.md's "rate limit: max 20/sec" advice (line ~440) is consistent with the ceiling. ceiling-lights.md needs only the D5-02 cross-link.

### Findings to surface, not fix (out of audit scope per D5-10/D5-11)
- **F1:** `docs/api/animation.md:5` (hand-written prose intro, not docstring-fed): "optimized for real-time effects at 30+ FPS" — api/ pages are outside the D5-10 audit scope. Surface for a user decision; it is a one-line prose fix if the user opts in (it is NOT a docstring).
- **F2:** Project `CLAUDE.md` Animation Layer section says "Optimized for high-frequency frame delivery (30+ FPS)" and its Discovery DoS Protection section says discovery default timeout is 5.0 (actual: 15.0) — not a docs-site page; surface as repo-hygiene finding.
- **F3:** No flatly wrong docstrings found in the animation layer — the `Animator`/`AnimatorStats` docstrings were updated in Phase 4 and correctly describe ack-gated behaviour.

## Common Pitfalls

### Pitfall 1: Breaking the success criterion with a broken anchor
**What goes wrong:** Three pages link to the new wake-tail section; a heading rename after links are written produces new "anchor does not exist" build warnings.
**Why it happens:** anchors derive from heading text via the toc extension.
**How to avoid:** fix the wake-tail heading text first, in the DOCS-01 task, and have cross-link tasks depend on it. Verify with `uv run zensical build` after each page edit.
**Warning signs:** warning count above the 8-warning baseline.

### Pitfall 2: Treating the pre-existing build warnings as this phase's failure
**What goes wrong:** verification fails the phase on warnings that predate it.
**How to avoid:** baseline is recorded: build exits 0 with exactly 8 anchor warnings, all in `api/effects.md` (5) and `api/index.md` (3) `[VERIFIED: this session]`. "Builds cleanly" = exit 0 and no NEW warnings; the 8 baseline warnings are in files this phase must not edit.

### Pitfall 3: Leaking tuning constants into the user guide
**What goes wrong:** copying the (accurate, public) `Animator` docstring text — which names the 2-outstanding gate and ~1 s expiry — into animation.md violates D5-09.
**How to avoid:** write the user-guide narrative from the D4-01/D4-02 behavioural summary (ack-paced, latest-frame-wins, no configuration), not from the docstring.

### Pitfall 4: Mixing HSBK formats in new examples
**What goes wrong:** a polling snippet in troubleshooting.md (device layer, float `HSBK`) styled after animation.md examples (raw uint16 tuples), or vice versa.
**How to avoid:** the wake-tail snippet uses device-layer calls (`get_color()` — no colour construction needed at all); the streaming snippet uses uint16 tuples like every other animation.md example.

### Pitfall 5: Overstating the wake tail
**What goes wrong:** framing the wake tail as a reliability problem. Spike 001 measured **zero loss**; the tail is latency-only, sub-250 ms, gen4-only.
**How to avoid:** D5-03's frame: what happens, when it matters (latency-sensitive first command after ≥~60 s idle), what to do (optional periodic polling). The D5-06 admonition carries the "no daemon, by design" message.

## Code Examples

Verified patterns for the planner to adapt (all match existing docs conventions):

### DOCS-01 polling recipe (troubleshooting.md — device layer, float-free)
```python
# Source: spike 001 (15 s tested cadence); Photons DeviceFinder polls at 10 s
import asyncio
from lifx import Light

async def keep_awake(light: Light) -> None:
    """Optional: poll periodically so a gen4 device's radio stays awake."""
    while True:
        # Any request works; get_color() returns colour, power and label
        # in a single request/response pair.
        await light.get_color()
        await asyncio.sleep(15)  # 10-15 s keeps the wake tail away
```
Run it alongside the application with `asyncio.TaskGroup` or `asyncio.create_task()`.

### DOCS-01 gen4 identification (verified live this session)
```python
# gen4 devices report host firmware major version 4 or later
firmware = await device.get_host_firmware()
if firmware.version_major >= 4:
    print("This device uses WiFi power-save (sub-250 ms wake tail)")
```
(Inside `async with`, `device.host_firmware` is already cached.)

### DOCS-02 minimal streaming loop (animation.md — uint16 tuples, existing style)
```python
# Source: existing animation.md loop pattern + shipped Animator API
async with await MatrixLight.from_ip("192.168.1.100") as device:
    animator = await Animator.for_matrix(device)

target_fps = 20  # platform ceiling over WiFi; large matrix devices sustain less
try:
    while running:
        frame = generate_frame()          # your only job: produce frames
        animator.send_frame(frame)        # the library paces delivery
        await asyncio.sleep(1 / target_fps)
finally:
    animator.close()
```

### D5-06 admonition shape (matches ceiling-lights.md convention)
```markdown
!!! note "lifx-async deliberately ships no keepalive daemon"

    Measured on real hardware, idle devices lose zero packets on healthy
    networks -- the wake tail is a small, bounded latency cost, not a
    reliability problem. Whether to spend a packet every 10-15 seconds to
    avoid it is the application's choice, so the library does not make it
    for you.
```
(Exact wording is Claude's discretion; Australian English; content must include the
"why" per D5-06.)

## State of the Art (what changed, v1.0 → v1.1)

| Old Approach (documented today) | Current Approach (to document) | When Changed | Impact on docs |
|---------------------------------|-------------------------------|--------------|----------------|
| Multi-pass discovery workarounds | Single call re-broadcasts on an escalating schedule (DISC-01) | Phase 2 | Remove workaround recipes (audit #5, #9) |
| App-level backoff wrappers for reliability | Library retry reshaped: ~200 ms floored first window, escalating gaps, listen-during-backoff, wall-time honoured (RETRY-01..04) | Phase 3 | Contextualise retry examples (audit #8, #11) |
| Blind-fire animation; `fast=True` device loops for streaming | Ack-gated pacing + latest-frame-wins internal to Animator (ANIM-01/02) | Phase 4 | New DOCS-02 section; rework fast=True section (audit #10) |
| "30+ FPS" performance framing | ~20 FPS platform ceiling; ~10 FPS for Capsule-class multi-packet frames | Phase 4 / 04-13 verdict | Fix framing everywhere (audit #1-3, #12) |
| (undocumented) | Gen4 sub-250 ms wake tail + optional polling | Spike 001 → this phase | New DOCS-01 section |

**Deprecated/outdated:** none removed from the API — all changes were internal behaviour; the docs work is purely re-description.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Polling intervals between the two attested endpoints (10 s Photons, 15 s spike-tested) behave equivalently — "10–15 s" is presented as a range | Verified Numbers / polling | Low — both endpoints measured/attested; the docs snippet uses the tested 15 s |
| A2 | ALL gen4-era products report host firmware major ≥ 4 (verified on products 224 and 201 only; generalised across the LCMX family) | Gen4 identification | Low-medium — a gen4 product on major-3 firmware would be missed by the check; no counter-example exists in the fleet or Photons registry |
| A3 | Wake-tail behaviour on mesh networks (TP-Link Deco/Orbi) matches the healthy-network measurement | Wake-tail guidance | Medium — spike explicitly flags this unverified; docs should scope claims to "healthy networks" as the spike does |
| A4 | The ESP32 modem-sleep mechanism explanation | Wake-tail guidance | None if omitted — D5-03 says no methodology/mechanism narrative needed; recommend omitting the mechanism from docs entirely |

## Open Questions (RESOLVED)

1. **Should the one stale prose line in `docs/api/animation.md:5` ("30+ FPS") be fixed?**
   - What we know: it is hand-written prose in the .md file, NOT docstring-fed; D5-10's audit scope lists user-guide/faq/getting-started/architecture only.
   - What's unclear: whether the user intends api/ prose (as opposed to mkdocstrings output) to be off-limits.
   - Recommendation: surface as finding F1 in the plan; a `checkpoint:human-verify` or a one-line ask during planning. Cheap either way.
   - **RESOLVED (planning):** surfaced, not fixed — plan 05-03 Task 2 records F1 verbatim in its SUMMARY "Findings" section for an operator decision; docs/api/ stays untouched (D5-10/D5-11 scope held, enforced by 05-03's `git diff --name-only` gate).
2. **How hard to prune the app-level retry examples (troubleshooting.md Connection Drops, advanced-usage.md Robust Error Handling)?**
   - What we know: whole-operation retries remain legitimate; per-request reliability is now the library's job.
   - Recommendation: contextualise (add one sentence that the library already retransmits within each request) rather than delete — smaller diff, no lost guidance.
   - **RESOLVED (planning):** contextualise, don't delete — encoded in plan 05-01 Task 2 (troubleshooting.md "Connection Drops") and plan 05-03 Task 1 (advanced-usage.md "Robust Error Handling"): the wrapper examples are kept, with one–two added sentences noting the library already retransmits within each request's timeout, so wrappers are for whole-operation failures, not per-packet reliability.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| uv | all commands | ✓ | project standard | — |
| zensical | build criterion | ✓ (build ran, exit 0, 7.66 s) | lockfile dev dep | — |
| llmstxt-standalone | docs pipeline (optional check) | ✓ (dev dep) | lockfile | skip — not in success criteria |
| Test fleet (gen2/3/4 devices) | already consumed by research | ✓ (probed this session) | — | not needed at execution time |

**Missing dependencies with no fallback:** none.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | zensical build (docs); pytest exists but no code changes occur |
| Config file | `mkdocs.yml` |
| Quick run command | `uv run zensical build` (~8 s) |
| Full suite command | `uv run zensical build` (same — docs-only phase) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DOCS-01 | Wake-tail section present in troubleshooting.md with sub-250 ms figure + polling recipe + no-keepalive admonition | content check | `grep -qi "wake" docs/user-guide/troubleshooting.md && grep -q "250" docs/user-guide/troubleshooting.md` | ✅ (pages exist; content added by phase) |
| DOCS-01 | FAQ entry links to the wake-tail section | content check | `grep -q "troubleshooting.md#" docs/faq.md` | ✅ |
| DOCS-02 | Streaming section in animation.md names latest-frame-wins + do-not-reimplement list + FPS numbers | content check | `grep -qi "latest-frame" docs/user-guide/animation.md && grep -q "10 FPS" docs/user-guide/animation.md` | ✅ |
| DOCS-01+02 | Site builds cleanly with new content | build | `uv run zensical build` exits 0 with **no new warnings vs the 8-warning baseline** (all baseline warnings are in api/effects.md and api/index.md) | ✅ |
| DOCS-01+02 | Accuracy of numbers vs sources | manual-only | Read-through against §Verified Numbers | justification: factual review is not mechanisable |

### Sampling Rate
- **Per task commit:** `uv run zensical build` (exit 0, warning count ≤ 8, none on edited pages)
- **Per wave merge:** same + grep content checks above
- **Phase gate:** full build green + manual accuracy read-through before `/gsd-verify-work`

### Wave 0 Gaps
None — existing docs toolchain covers all phase requirements. (Optional: a task may capture the baseline warning count with `uv run zensical build 2>&1 | grep -c Warning` before first edit.)

## Security Domain

Markdown-only documentation phase: no authentication, session, access-control, input-validation, or cryptography surface is created or modified. No ASVS category applies to the changed artefacts.

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | no | — |
| V5 Input Validation | no | — (no code changes) |
| V6 Cryptography | no | — |

One documentation-content consideration: the polling recipe and streaming examples must not encourage patterns that flood devices (the ~20 msg/sec device limit in CLAUDE.md) — the recommended 10–15 s poll and ≤20 FPS framing are consistent with it.

## Sources

### Primary (HIGH confidence)
- `.planning/spikes/001-modem-sleep-keepalive/README.md` + `summary-20260716-201013.json` — wake-tail figures, zero-loss result, 15 s keepalive cadence
- Live read-only device probe (this session, lifx-async `Device.from_ip`) — firmware majors 2.90/3.50/4.112 across gen2/gen3/gen4
- `src/lifx/animation/animator.py`, `src/lifx/animation/flow.py` — shipped DOCS-02 behaviour and public stats surface
- `src/lifx/const.py`, `src/lifx/api.py`, `src/lifx/devices/base.py`, `src/lifx/products/registry.py` — discovery default, discover() shape, gen3 firmware quirk, registry fields
- `/Volumes/External/Developer/Djelibeybi/photons/modules/photons_control/device_finder.py` — 10 s GetColor refresh; `photons_products/registry.py` — product 201 = Family.LCMX
- `.planning/STATE.md` — 04-13 operator verdict verbatim; `.planning/phases/04-animation-flow-control/04-CONTEXT.md` — D4-01/D4-02
- `uv run zensical build` (this session) — baseline: exit 0, 8 pre-existing anchor warnings (api/effects.md ×5, api/index.md ×3)

### Secondary (MEDIUM confidence)
- `.claude/skills/spike-findings-lifx-async/references/concurrency-and-keepalive.md`, `animation-flow-control.md` — synthesised findings (cross-checked against raw spike READMEs above)

### Tertiary (LOW confidence)
- ESP32 modem-sleep mechanism explanation (spike README "plausible mechanism") — recommend omitting from published docs

## Metadata

**Confidence breakdown:**
- Verified numbers (wake tail, polling, FPS): HIGH — every figure traced to raw spike data, STATE.md, or live measurement this session
- Gen4 identification: HIGH for the method on probed devices; MEDIUM for generalisation to unprobed gen4 products (Assumption A2)
- Stale-content audit: HIGH — every finding cites file + line, from full reads of the affected pages
- Docs conventions/build: HIGH — build executed, conventions grepped

**Research date:** 2026-07-17
**Valid until:** 2026-08-16 (stable domain — internal docs of shipped behaviour; only rot vector is further code changes before execution)
