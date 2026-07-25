# Phase 5: Reliability Documentation - Context

**Gathered:** 2026-07-17
**Status:** Ready for planning

<domain>
## Phase Boundary

User-facing documentation of the v1.1 wire-reliability behaviour: gen4 power-save
wake-tail guidance (DOCS-01) and streaming-consumer guidance for the LedFx pattern
(DOCS-02), written into the existing docs site (`docs/` + `mkdocs.yml`), plus a
stale-content audit of existing prose pages against the shipped v1.1 behaviour.
The documentation must build cleanly (`uv run zensical build`) with the new content
linked from the relevant device/animation pages. No code changes, no new features,
no changelog edits (auto-generated).

</domain>

<decisions>
## Implementation Decisions

### Placement & navigation
- **D5-01:** Extend existing pages — no new dedicated reliability page, no new nav
  entries in `mkdocs.yml`. DOCS-02 streaming guidance lives in
  `docs/user-guide/animation.md`; DOCS-01 wake-tail guidance lives in
  `docs/user-guide/troubleshooting.md` with a short entry in `docs/faq.md` that
  links to it.
- **D5-02:** Targeted cross-links only: `docs/user-guide/ceiling-lights.md` links to
  the wake-tail section; `docs/user-guide/animation.md` and the troubleshooting
  wake-tail section link to each other where streaming meets gen4 power-save.
  No broad linking from API reference or getting-started pages.

### Wake-tail guidance (DOCS-01)
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

### Streaming-consumer guidance (DOCS-02)
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

### Coverage breadth
- **D5-10:** Stale-content audit: audit existing `docs/` prose pages (user-guide,
  faq, getting-started, architecture) for claims made stale by the v1.1 work — old
  advice about discovery misses, retry timing, or streaming workarounds — and fix
  contradictions in place. No new "v1.1 reliability overview" page or section.
- **D5-11:** Audit scope is prose pages only. Source docstrings (which feed
  `docs/api/*.md`) stay untouched; if the audit discovers a flatly wrong docstring,
  surface it as a finding rather than editing source in this phase.

### Gap closure amendments (2026-07-17, operator-authorised)

Added after the 05-VERIFICATION.md gap report and 05-REVIEW.md. These supersede the
original decisions where they conflict.

- **D5-12:** Version-neutral phrasing for the wire-behaviour claims. The "Since v1.1"
  wording that 05-01 Task 2 and 05-02 Task 2 mandated is withdrawn: `v1.1` is the
  internal milestone name, but real PyPI releases v1.1.0–v1.1.3 exist and the package
  is at v5.5.x, so it reads as a false version claim (CR-01). The behaviour is stated
  without any version attribution — **not** pinned to a predicted release, because
  python-semantic-release derives the version from conventional commits at release
  time (`[tool.semantic_release]`, pyproject.toml:139), so the shipping version is
  not knowable at authoring time. This closes the DOCS-02 edge the 05-02 flagged
  planner assumption routed back as a gap.
- **D5-13:** D5-11 is **narrowly overridden** for one line: `src/lifx/api.py:758`,
  the `discover()` docstring `(default 3.0)` → the real `DISCOVERY_TIMEOUT` of 15.0
  (WR-02). This docstring renders into the published API reference, so leaving it
  makes the site contradict the user-guide statement this phase added. Every other
  source docstring stays out of scope — D5-11 otherwise holds.
- **D5-14:** D5-10 and prohibition 7 are **narrowly overridden** for one line:
  `docs/api/animation.md:5`, the hand-written prose intro claiming "optimized for
  real-time effects at 30+ FPS" (F1) → `~20 FPS`, Australian spelling. This line is
  hand-written prose, not docstring-fed. Docstring-fed `docs/api/` content and
  `docs/changelog.md` remain fenced — never edit them.
- **D5-15:** Residual accuracy closure in the same pass — the operator opted into the
  full set: WR-01 (CLAUDE.md:256 idle timeout 2 s → ~4 s, `MAX_RESPONSE_TIME` 1.0 ×
  `IDLE_TIMEOUT_MULTIPLIER` 4.0, const.py:30-34), WR-03 (faq.md:63 `await Light(...)`
  → non-awaitable constructor), WR-04–WR-08 (broken examples: HSBK float/uint16
  mixing, `in` on `ProductInfo`, `registry.items()`, misplaced parenthesis) and
  IN-01–IN-03 (AU spelling, overview.md layer numbering, double spaces). Every fix
  must be verified against the shipped source, not against the review text.

### Second gap-closure amendments (2026-07-17, operator-authorised)

Added after the 05-VERIFICATION.md **re-verification** (36/37 — goal-derived accuracy
truth #23 failed on a newly surfaced edge) and the **re-review** 05-REVIEW.md
(2026-07-17T03:13:38Z). These supersede earlier decisions where they conflict.

> **Finding-ID collision warning.** The re-review restarted its own `CR-`/`WR-`/`IN-`
> numbering, which does **not** match the first review's numbering that D5-15 cites
> (old WR-01 = CLAUDE.md idle timeout; new WR-01 = `Colors.WARM_WHITE`). Every item
> below is therefore pinned by `file:line`, and `file:line` wins over any ID.

- **D5-16:** Close the failing accuracy truth (#23) — the phase's own broken discovery
  recipe. `discover_devices()` is an **async generator** (`src/lifx/network/discovery.py:477-485`
  → `AsyncGenerator[DiscoveredDevice, None]`), so `devices = await discover_devices(...)`
  raises `TypeError` and the recommended recipe cannot run. Rewrite
  `docs/user-guide/troubleshooting.md:110` as async-for collection, matching the page's
  own correct example at 223-225. **Attribution correction (load-bearing):** line 110 was
  written by **05-01** (commit `015a112`), *not* by 05-04 — the re-review's CR-01 claim
  that "the instance at line 110 was introduced by the 05-04 gap-closure diff itself" is
  factually wrong, disproven by `git log -L 110,110` and a zero-hit `discover_devices`
  grep over the whole 05-04 diff. It is an original-execution defect that slipped both the
  first review and the first verification; do not plan a "revert 05-04" fix.
  Fix the two pre-existing same-file, same-defect companions in the same pass —
  **line 27** (`await` then `len()`) and **lines 70-84** (`diagnose_discovery` awaits, then
  tests `if not devices:` and iterates) — because fixing only line 110 leaves the page
  self-contradictory three lines apart. `if not devices:` works unchanged once `devices`
  is a list.

- **D5-17:** Full doc-side residual closure — the operator opted into the whole remaining
  set (the D5-15 pattern, second round). All are confirmed real against shipped source:
  - `docs/user-guide/ceiling-lights.md:259-273` — three dead APIs: `get_tile_chain()` →
    `get_device_chain()` (`matrix.py:378`); `TileEffectType` → `FirmwareEffect` (the
    generator merges it away, `generator.py:302-338`); `set_tile_effect(speed=5000)` →
    `set_effect()` (`matrix.py:926`) whose `speed` is **seconds** (`float`, default 3.0),
    so 5000 is also wrong by three orders of magnitude. All three: zero definitions in `src/`.
  - `docs/faq.md:199`, `docs/user-guide/advanced-usage.md:229`, `CLAUDE.md:244` — the
    "requests are serialized / `_request_lock`" concurrency claim is false: **zero
    `_request_lock` in `src/`**. The shipped model is a background receiver task routing
    to per-request `asyncio.Queue`s keyed by `(source, sequence, serial)`
    (`connection.py:147-152, 200-201`) — mixing is prevented by *correlation*, not
    serialisation. `advanced-usage.md` self-contradicts (line 229 vs. the `asyncio.gather`
    demo at 241-253 claiming "maximum parallelism"); `docs/architecture/overview.md:392-412`
    already describes the real model and is the wording anchor.
  - `docs/architecture/overview.md:150` — "exponential backoff" mischaracterises
    `REQUEST_RETRANSMIT_GAPS` (`const.py:53-65`), an escalating/stepped schedule. This is
    the very v1.1 retry behaviour the phase exists to document accurately, and the phase's
    own prose elsewhere already says "escalating schedule".
  - `docs/faq.md:247-249` — restore the "on healthy networks" qualifier the canonical
    section it links to (`troubleshooting.md:323-324`) carries; the unqualified absolute
    overclaims.
  - `docs/user-guide/troubleshooting.md:239-261` — `measure_latency` uses `asyncio.gather`
    with no `import asyncio` (`NameError`).
  - `docs/user-guide/advanced-usage.md:338-351` — `Colors` used without import
    (`NameError`). **Also 369-386 and 396-410** — the verifier found the same missing
    import in both capability examples whose `if`-lines 05-04 edited (05-04 was barred from
    touching the bodies).
  - `docs/user-guide/advanced-usage.md:456-471` — `wave_effect` discards
    `asyncio.create_task` results and returns without awaiting: under `asyncio.run()` the
    loop closes before any colour change, and the unreferenced tasks may be GC'd mid-flight.
    Use `asyncio.TaskGroup` (or collect + `gather`).
  - `docs/architecture/overview.md:173, 178-185` — add `CeilingLight` / `ceiling.py`; the
    page's own mermaid diagram (line 36) already shows it.
  - `CLAUDE.md` Animation Layer file list — add `animation/flow.py` (exists on disk;
    `overview.md:212` already lists it).
  - `docs/user-guide/ceiling-lights.md:170` — add `tile_orientations` to the inherited
    `MatrixLightState` list (`matrix.py:285-289`).
  - Australian English on prose (not API identifiers): `docs/api/animation.md:138`
    "initialization"; `docs/architecture/overview.md:117` "Serialization", `:291`
    "acknowledgment", `:293` "Deserialize"; `docs/user-guide/advanced-usage.md:14,473`
    "Optimization", `:430` "Synchronized"; `docs/user-guide/animation.md:186` "Normalize",
    `:308` "vectorized"; `CLAUDE.md:160` "Optimized".

  Carried forward from D5-15: **every fix must be verified against the shipped source, not
  against the review text.** The re-review's own CR-01 attribution error is the standing
  proof that review claims are leads, not truth.

- **D5-18:** Fence adjustments — two narrow D5-11 overrides, plus the D5-14 fence's shape.
  - `src/lifx/network/connection.py:64` — the class docstring's "Request serialization to
    prevent response mixing" is the same false claim as D5-17's prose sites and renders into
    the published API reference; leaving it makes the site contradict the prose this phase
    is fixing (the exact D5-13 argument). Rewrite to the receiver/correlation model.
  - `src/lifx/api.py:620` — `Colors.WARM_WHITE` does not exist (only repo-wide occurrence
    is this docstring; `AttributeError` if run) → `Colors.WARM` (`color.py:873`).
  - **D5-14 widened, not breached:** hand-written prose lines in `docs/api/animation.md`
    are editable (its `:138` "initialization" is hand-written prose, the same class as the
    `:5` line D5-14 already overrode — verified: the surrounding section is authored
    markdown, not an mkdocstrings block). **mkdocstrings-fed content and
    `docs/changelog.md` remain absolutely fenced — never edit them.**
  - **D5-11 otherwise holds:** no source docstring edits beyond `connection.py:64` and
    `api.py:620` (plus `api.py:758`, already spent under D5-13). D5-01 (no nav changes),
    D5-09 (no internal tuning constants) and D5-12 (no version attribution of any kind)
    continue to hold unchanged.

- **D5-19:** The re-review's `src/lifx/api.py` findings at `:260-267, 273-279, 313-319,
  325-331` (gather without `return_exceptions`; docstrings promising logging that does not
  exist; dead `None` branches), `:974-976, 996-999, 1013-1016` (`exact_match` promises "at
  most one device", yields every match), and `:515-523, 549-557` (result cache keyed only on
  `is None`, so a warm cache silently ignores `include_unassigned`) are **real behavioural
  code defects, not documentation defects**. They are **deferred out of Phase 5**: the phase
  boundary is explicitly "No code changes", and fixing them needs real code plus tests and
  the project's 100% branch patch coverage. Recorded as **API-01** under REQUIREMENTS.md
  *Future Requirements*. Do **not** fix them in this phase, and do **not** paper over them
  by editing their docstrings to match the broken behaviour.

- **D5-20:** Fence extension (2026-07-17, operator-authorised during planning of 05-05).
  Planning surfaced three further instances of the **same two defect classes** D5-16/D5-17
  already close, sitting in files the D5-14/D5-11 fences excluded. Leaving them makes the
  **published API reference contradict the guide this phase just fixed** — identical to the
  reasoning that authorised D5-13. All three are in scope for 05-05:
  - `docs/api/network.md:50-59` — the discovery example is **triply** wrong: it awaits the
    async generator (`TypeError`); prints `device.label`, which `DiscoveredDevice` does not
    have (its fields are `serial`, `ip`, `port`, `timeout`, `max_retries`, `first_seen`,
    `response_time` — `AttributeError`); and passes `timeout=3.0`, the exact stale default
    D5-13 corrected at `api.py:758`.
  - `docs/api/network.md:63-84` — the hand-written `### Request Serialization on Single
    Connection` section ("serializes requests using a lock", plus the `# Sequential requests
    (serialized by internal lock)` comment) repeats the false claim D5-17/D5-18 remove
    everywhere else.
  - `src/lifx/network/discovery.py:79-85` — the `create_device()` docstring `Example:`
    awaits the generator. **Third narrow D5-11 override**; it renders into the API reference.

  **Both `docs/api/network.md` spans are verified hand-written prose**, not mkdocstrings
  output: the file's `:::` blocks are at lines 9, 15, 25, 36 and 111, so 48-84 lies between
  the `UdpTransport` and `DeviceConnection` blocks. D5-18's docs/api prose carve-out
  therefore extends from `docs/api/animation.md` to **hand-written prose in
  `docs/api/network.md`** on the same terms.

  **Unchanged:** mkdocstrings-fed content (the `:::` blocks) and `docs/changelog.md` remain
  absolutely fenced — never edit. D5-11 now permits exactly four source-docstring edits and
  no others: `api.py:758` (D5-13, already spent), `connection.py:64` and `api.py:620`
  (D5-18), `discovery.py:79-85` (D5-20). D5-01, D5-09, D5-12 and D5-19 all continue to hold.

  Also authorised under D5-20: the planner-identified `docs/api/animation.md:131-134` fix
  ("No ACKs, no waiting, no retries" / "Maximum throughput for real-time effects"), made
  false by Phase 4's shipped ack gate. It falls under D5-10's in-place staleness mandate ∧
  D5-18's prose carve-out, and describes the very ack-gating DOCS-02 documents.

- **D5-21:** `create_device()` Example — guard the None, route the rest to API-01
  (2026-07-17, operator-authorised during planning of 05-05). D5-20's
  `src/lifx/network/discovery.py:79-85` override **extends to the Example body**: add a
  `None` guard so the example is actually runnable.

  **Why the None is reachable** (the operator correctly noted relays/buttons are out of
  scope — that is *why* the None exists, not a reason it cannot happen):
  - `discover_devices()` yields **every** responder with no relay/button filter at the
    discovery layer (`discovery.py:544`); `create_device()` is where filtering happens.
  - `get_device_class_for_product()` **raises** `LifxUnsupportedDeviceError` for
    relay-only/button-only products (`detection.py:33`), which `create_device()` catches →
    `None`. An out-of-scope LIFX Switch still answers a `GetService` broadcast, so a user
    with one on the network hits `None` from the documented example.
  - More broadly, `except Exception: return None` (`discovery.py:115-116`) makes `None` the
    outcome of **any** transient failure — a timeout or dropped packet on a busy network,
    nothing to do with switches.

  **Explicitly NOT fixed here — routed to API-01(d):** the same docstring's `Returns:`
  (says "Device instance of the appropriate type", omitting `None` despite the
  `Device | None` signature) and `Raises:` (promises `LifxDeviceNotFoundError`,
  `LifxTimeoutError`, `LifxProtocolError` — **all three swallowed by the catch-all**, so
  none can ever escape). Correcting them requires first deciding whether
  `except Exception: return None` is intended behaviour; rewriting `Raises:` to match the
  code would be exactly the paper-over **D5-19 prohibits**. The docstring edit authorised
  here is confined to the `Example:` block.

- **D5-22:** Rendered docstrings are in scope — D5-11 lifted for anything mkdocstrings publishes
  (2026-07-17, operator-authorised during UAT of Phase 5, `/gsd-verify-work 5`).

  **What changed the ruling.** Operator UAT surfaced four defects that D5-11 made unfixable by
  policy. The fence assumed "docstrings are source, not docs" — but `docs/api/*.md` renders them
  via `:::` directives, so a fenced docstring *is* a published page. D5-11 held perfectly through
  a 37/37 verification, which is exactly how these survived. The fence, not the executor, was the
  defect.

  **Scope — supersedes the D5-11 three-site budget (D5-18/D5-20/D5-21):** any docstring reachable
  from a `:::` render target may be edited, for **prose and whitespace**, to close G-05-4, G-05-5
  and G-05-6. This is deliberately broader than every prior override.

  **Fences that still hold — D5-22 grants no relief from any of these:**
  - **D5-19 / API-01** — the three deferred `api.py` behavioural defects (lines 260-331, 515-557,
    974-1016) stay untouched, and no docstring may be rewritten to make a promise match broken
    behaviour. D5-22 authorises *clarity*, never paper-over. `create_device()`'s `Returns:`/`Raises:`
    remain routed to API-01(d) per D5-21 — unchanged by this override.
  - **D5-09** — no internal tuning constants in the rewrite. Note `packets.py:164` currently
    publishes a measured spike figure ("0.0% concurrent-query loss"); the rewrite must not carry it
    forward.
  - **D5-12** — no version attribution.
  - **D5-14 (widened)** — the `:::` directive blocks themselves and `docs/changelog.md` stay
    untouched. D5-22 covers the *docstrings they render*, not the directive blocks.
  - **D5-01** — no `mkdocs.yml` nav changes, no new pages.

  **Out of scope — `#` comments stay as they are.** Internal IDs in comments
  (`discovery.py:250`, `connection.py:507/548/601/657`, all of `animation/flow.py`) do not render
  and are legitimate engineering traceability. Only *published* docstrings are in scope. Where a
  rendered docstring loses an internal ID for reader clarity, prefer demoting it to a `#` comment
  over deleting the traceability.

  **Audit is part of the work, not optional.** The operator chose full closure in Phase 5 over a
  separately-planned phase, accepting the stated risk that the leak list is incomplete. The known
  sites were found by pulling one thread the operator started — there is no basis to believe they
  are exhaustive. The gap-closure plan MUST therefore carry an audit task over every `:::`-reachable
  docstring for: internal vocabulary (other libraries' internals, planning IDs, spike/plan numbers),
  missing blank lines before lists, and D5-09 tuning constants. Findings the audit surfaces beyond
  G-05-4/05/06 are in scope for the same plan.

- **D5-09 — OPEN: operator disputes the prohibition** (2026-07-17, raised during Phase 5 UAT).
  Not a verdict dispute: plan 05-05 complied with D5-09 and verdict 6 holds. The operator disputes
  **the rule itself** — "it would be really useful to document the default flow control mechanics
  with timing so folk know ahead of time what to expect."

  **The tension is real.** The phase goal promises "accurate guidance on the **wire behaviour** the
  library now guarantees" while D5-09 forbids stating the numbers that behaviour consists of.
  "Escalating schedule" is honest and useless to an integrator. The cadence is also not meaningfully
  *internal* — it is observable on the wire.

  **What the operator asked to document:**
  1. The default mechanics with real timings.
  2. How to override `REQUEST_RETRANSMIT_GAPS`, `DEFAULT_MAX_RETRIES`, `DEFAULT_REQUEST_TIMEOUT`.
  3. A diagram of how the three values interact between lifx-async and a target bulb.

  **Blocker found while scoping (2) — two of the three knobs are real, one is not.** `timeout` and
  `max_retries` are genuine parameters (`DeviceConnection`, `from_ip`, `request`). The gaps are
  **not overridable by any public API**: `REQUEST_RETRANSMIT_GAPS` is `Final` in `const.py`, absent
  from `lifx/__init__.py`'s `__all__`, and bound at import time by `connection.py:18`. The only
  override is `patch("lifx.network.connection.REQUEST_RETRANSMIT_GAPS", ...)` — note *that* binding,
  not `lifx.const`'s — which `connection.py:516` states outright is a test seam. Documenting it would
  publish an internal seam as public API and contradict its own `Final`. **Unresolved:** document the
  schedule as fixed, or add a real `retransmit_gaps` parameter first (source-behaviour work, not docs).

  **Drift risk if D5-09 is relaxed.** `lifx.const` is not a mkdocstrings target — nothing renders it.
  Any published figure is hand-copied, and Phase 5 exists *because* hand-maintained docs drifted from
  source (`TileEffectType`, `Colors.WARM_WHITE`, the "no discovery" claim). Whatever is published
  should be pinned by a test asserting the documented values match `const.py`/`flow.py`, or rendered
  from source — otherwise this seeds the next stale-content defect.

  **Provenance worth publishing** (argues for relaxation): the tuple is not arbitrary tuning. It is
  Photons' schedule verbatim — `timeouts=[(0.2,0.2),(0.1,0.5),(0.2,1),(1,5)]`
  (`photons_transport/targets/__init__.py:25`) expands to `0.2, 0.3, 0.4, 0.5, 0.7, 0.9, 1.0, 2, 3,
  4, 5` plateauing on the final gap — which spike 002 raced as `regime_photons` and which won at
  1 failure in 180 trials. *(Expansion derived from the `Gaps` docstring contract, corroborated by
  this MANIFEST's own summary; not verified by executing `RetryTicker`.)*

  **Flow-on to D5-22:** `packets.py:164`'s "spike 003 measured at 0.0% concurrent-query loss" was
  flagged for removal as a D5-09 constant. If D5-09 relaxes, the *measurement* may stay — but
  "spike 003" is still an unresolvable planning reference and G-05-6 should still demote it.

  **Linked spike candidate:** `.planning/spikes/MANIFEST.md` #006 `retry-cap-vs-photons-envelope` —
  the shipped `max_retries=8` envelope was never raced; only the gap tuple was. Recorded as a
  candidate, not scheduled. It cannot resolve the override question above.

- **D5-23:** The 8-warning baseline is a defect, not a constant — D5-14 lifted for `api/effects.md`
  and `api/index.md`; CI gates on `--strict` (2026-07-17, operator-authorised during UAT: "There are
  8 warnings in strict mode when running Zensical, btw. We should look into those too" → "Amend it").

  **What changed the ruling.** D5-14 deferred these deliberately — "every other docs/api page stays
  fenced *even where it carries known defects (surfaced as findings, not fixed)*" — and every plan in
  the phase then pinned "exits 0 at the 8-issue baseline" as a must_have. Pinning a broken-link count
  as a success criterion is what made it permanent. The operator reopened it.

  **Scope — narrow. D5-23 lifts D5-14 for exactly two pages, for exactly these defects:**
  - `docs/api/effects.md` (5 sites: :60, :82, :101, :115, :194) — backtick the type annotations.
    `` `participants` (list[Light]) `` leaves `[Light]` outside the backticks, so markdown parses it
    as a shortcut link reference and cannot resolve it. A markdown bug, not a content error.
  - `docs/api/index.md` (3 sites: :58, :95, :96) — resolved by rendering the missing targets, NOT by
    editing index.md. The links are correct; their destinations never existed.

  **mDNS ruling: render the missing `:::` targets.** `discover_mdns`, `discover_lifx_services` and
  `LifxServiceRecord` are all exported from `lifx/__init__.py`'s `__all__` (:143, :151, :152) and
  from `lifx.network.mdns.__all__`; CLAUDE.md documents the whole `mdns/` module as a shipped
  feature. A reference that omits a headline feature is a worse defect than three dead links, and
  deleting the links would silently shrink the documented API. Add:
  - `::: lifx.api.discover_mdns` → `docs/api/high-level.md`, beside `::: lifx.api.discover` (:8)
  - `::: lifx.network.mdns.discover_lifx_services` → `docs/api/network.md`, beside
    `::: lifx.network.discovery.discover_devices` (:9)
  - `::: lifx.network.mdns.LifxServiceRecord` → `docs/api/network.md`, same group
  Match the surrounding blocks' `options:` exactly.

  **D5-01 is NOT touched and still holds.** Both destination pages already exist and the dead links
  already name them — no new page, no `mkdocs.yml` nav change. This is three `:::` blocks on two
  existing pages.

  **The gate inverts.** `zensical build --strict` ("abort the build on warnings") exists but CI runs
  plain `uv run zensical build --clean` (`.github/workflows/docs.yml:56`, `:114`) — nothing has ever
  failed on these 8. Every plan's must_have changes from "exits 0 at the pinned 8-issue baseline" to
  "`--strict` exits 0", and both docs.yml invocations gain `--strict`. Without the CI change this is
  just resetting a counter that will drift again.

  **Consumes the pinned baseline.** Plan 05-06 (created 2026-07-17, pre-dates this ruling) carries
  the old 8-issue must_have and MUST be amended; it cannot execute as written alongside G-05-7.

  **The newly-rendered mDNS docstrings inherit D5-22.** They have never been published before, so
  they have never been audited — they are in scope for the same audit task (internal vocabulary,
  blank lines before lists, D5-09 constants) before they go live.

### Claude's Discretion
- Section headings, placement/ordering within the host pages, admonition type and
  exact wording (match existing docs conventions).
- Code example style — match the existing examples in `docs/user-guide/animation.md`.
- Whether the FAQ addition is one entry or two (wake-tail + "why no keepalive?").
- Australian English throughout (project rule).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Spike findings (source of truth for numbers)
- `.claude/skills/spike-findings-lifx-async/SKILL.md` — findings index and requirements
- `.claude/skills/spike-findings-lifx-async/references/concurrency-and-keepalive.md` —
  gen4 wake-tail data + keepalive disproof; source for DOCS-01 figures and the
  polling interval (D5-04)
- `.claude/skills/spike-findings-lifx-async/references/animation-flow-control.md` —
  ack-gate behaviour and measured baselines; background for DOCS-02

### Phase 4 record (shipped behaviour DOCS-02 documents)
- `.planning/STATE.md` — 04-13 Capsule verdict + explicit Phase 5 recommendation
  (choose streaming FPS per device class; Capsule ~10 FPS at 16×8/3-packets-per-frame)
- `.planning/phases/04-animation-flow-control/04-CONTEXT.md` — D4-01 (ack-gated
  internal flow control), D4-02 (no downstream toggle) decisions the docs must state

### Docs infrastructure
- `mkdocs.yml` — nav (no new entries needed per D5-01); site config
- `docs/user-guide/animation.md` — DOCS-02 host page
- `docs/user-guide/troubleshooting.md` — DOCS-01 host page
- `docs/faq.md` — FAQ entry linking to the wake-tail section
- `docs/user-guide/ceiling-lights.md` — cross-link source (D5-02)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Docs build: `uv run zensical build` (success criterion); `uv run zensical serve`
  for local preview; `llmstxt-standalone build` also runs in the docs pipeline.
- Products registry (`src/lifx/products/`) — candidate mechanism for the gen4
  identification guidance (D5-05).

### Established Patterns
- Docs are mkdocs-Material-style markdown under `docs/` with nav in `mkdocs.yml`;
  match existing admonition and code-block conventions on the host pages.
- `docs/changelog.md` is auto-generated by the release workflow — never edit.

### Integration Points
- Host pages: `docs/user-guide/animation.md`, `docs/user-guide/troubleshooting.md`,
  `docs/faq.md`; cross-link from `docs/user-guide/ceiling-lights.md`.

</code_context>

<specifics>
## Specific Ideas

- The 04-13 operator visual verdict is the canonical wording anchor for the FPS
  guidance: "Geometry was fine. It was as smooth as the tiles. No multi-second
  freezes but it stuttered throughout." — stutter at 20 FPS on the Capsule is the
  documented latest-frame-wins degradation under device saturation, not a fault.
- The do-not-reimplement list exists because lifx-async is LedFx's LIFX provider —
  DOCS-02 is written for that integration pattern.

</specifics>

<deferred>
## Deferred Ideas

- **API-01 — three `src/lifx/api.py` behavioural defects** (deferred 2026-07-17 per D5-19,
  operator-authorised). Surfaced by this phase's docs audit but outside its "No code
  changes" boundary; they need code, tests, and 100% branch patch coverage. Recorded under
  *Future Requirements* in `.planning/REQUIREMENTS.md`:
  1. `_fetch_location_metadata` / `_fetch_group_metadata` (`:260-267, 273-279, 313-319,
     325-331`) — docstrings promise "logs warnings for failed queries but continues
     gracefully"; there is no logger and `asyncio.gather()` runs without
     `return_exceptions=True`, so one offline device aborts the whole
     `organize_by_location()` / `organize_by_group()` call. The `CollectionInfo | None`
     annotations and `if ... is None: continue` branches are dead code masking the mismatch.
  2. `find_by_label(exact_match=True)` (`:974-976, 996-999, 1013-1016`) — docstring, inline
     comment and example all promise "at most one device", but the generator never
     `return`s after yielding, and LIFX labels are not unique.
  3. `organize_by_location` / `organize_by_group` (`:515-523, 549-557`) — the result cache
     is keyed only on `self._locations_cache is None`, not on `include_unassigned`, so a
     warm cache silently drops the "Unassigned" group.

</deferred>

---

*Phase: 5-reliability-documentation*
*Context gathered: 2026-07-17*
