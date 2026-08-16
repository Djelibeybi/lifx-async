# Phase 8: Hardware Fidelity Validation - Context

**Gathered:** 2026-08-15
**Status:** Ready for planning

<domain>
## Phase Boundary

Produce replayable, sanitised real-hardware evidence that the shipped MORPH palettes for
two fixed themes match the LIFX app on the source Tile and one indoor non-Tile matrix
product, while recording an evidenced determination for every shipped 16-colour theme.

</domain>

<spec_lock>
## Requirements (locked via SPEC.md)

**4 requirements are locked.** See `08-SPEC.md` for full requirements, boundaries and
acceptance criteria.

Downstream agents MUST read `08-SPEC.md` before planning or implementing. Requirements are
not duplicated here.

**In scope (from SPEC.md):**

- A 25-row, slug-keyed determination table for the shipped exactly-16-colour themes
- Correction of the stale 26/21 counts in active planning and capture documentation
- Two fixed samples: one palette below the ceiling and one exactly-16-colour Art Series
  palette
- Three sequential app MORPH and three sequential library MORPH readbacks per sample on
  the source Tile
- The same repeated comparison on one real indoor non-Tile matrix product
- A committed, replayable and sanitised Phase 8 validation record
- Focused probe/support code and automated tests when required for reliable evidence

**Out of scope (from SPEC.md):**

- Static `MatrixLight.apply_theme()` canvas/pixel fidelity
- Visual or photographic comparison
- Testing every category, theme or matrix product
- Exterior devices
- Recovering a palette longer than 16 from any device
- Undocumented LIFX theme endpoints or identifiable cloud credentials
- Capture/resync tooling and end-user theme documentation owned by Phase 9
- Changing shipped theme palettes in response to a mismatch

</spec_lock>

<decisions>
## Implementation Decisions

### 2026-08-16 manual-positioning supersession

- **D-01 supersession:** This once-off Phase 8 UAT no longer automates Home, group expansion,
  target selection, selector closing, FX navigation or MORPH navigation. Before preflight the
  operator explicitly supplies `--attest-role source-tile` to claim the configured target and
  role are already positioned. Preflight performs no UI tap, navigation, theme selection or Save;
  it freshly proves only the exact detail panel's in-panel `effect_name` `Morph`, `effect_subtitle`
  `Effect`, one configuration scroll surface and one enabled/clickable theme-button entry, then
  proves both LAN bindings, classes, products and stable OFF snapshots. The Morph configuration
  hierarchy cannot prove a selected label, parent group or raw count; those are never claimed as
  UI observations. The same explicit operator claim and fresh Morph proof are required for the
  relevant role before every app cycle. Loss or ambiguity is incomplete and requires manual
  reset/reposition; no automatic recovery is permitted.
- **D-01 identity bridge:** Once LIFX closes the selector, UI text cannot establish the selected
  target's identity. The ignored private record therefore distinguishes the explicit operator
  claim (role, run ID, opaque binding digest and timestamp) from the independently observed Morph
  semantic booleans; exact private LAN host/serial/live-label proof bridges the claim to device
  identity. Neither record enters public evidence.
- **D-01 read-only contact exception:** A 2026-08-16 live observation found that an exhausted
  initial `Device.connect` source could fail while an isolated fresh connection succeeded. Only
  Phase 8's initial bound-device preflight adapter may therefore make one wholly fresh second
  read-only contact after a timeout/not-found/connection failure, closing any partial device
  first. Metadata, snapshots, app Save, palette reads and all mutations remain one-shot; a second
  contact failure is redacted incomplete. This is not a general library retry policy.
- **D-01 private stage trace:** Every preflight writes only fixed `preflight-stage` role/stage/status
  records below the existing mode-0600 private trace. It distinguishes UI attestation, read-only
  contact (including a fresh retry), metadata and snapshot boundaries without identifiers, raw UI
  or exception text; public progress remains redacted and unchanged.
- **D-01 MatrixLight integration correction:** A healthy 2026-08-16 source snapshot exposed a
  phase-local stale chain method name. `MatrixLight` exposes `get_device_chain()`, which the
  snapshot helper now uses in place of `get_tile_chain()`; this changes neither the preflight
  criteria nor the restoration contract.
- **D-11 resume-evidence correction:** A 2026-08-16 review found that the mode-0600 checkpoint
  retained only scheduling fields, which could erase completed Tile palette evidence at the
  mandatory non-Tile checkpoint. Every cycle now stores deterministic protocol-uint16 palette
  observations, explicit nullable stable palette, match and failure fields. Resume accepts only
  a strict exact schedule prefix with its matching next key; legacy partial records fail closed.
- **D-01 Morph activation correction:** Live observation established that Save does not start a
  stopped Morph effect. After the static OFF baseline is captured, the runner taps exactly one
  in-panel enabled/clickable `play_button` once per role/invocation, then accepts activation only
  after two equivalent read-only LAN observations report MORPH with a non-empty HSBK palette.
  The persistent play control has no active-state semantics. Activation never occurs for
  library-only work or without the matching current-role operator attestation.
- **D-17 restoration timing correction:** Restoration performs its writes once, then makes
  bounded full, stable snapshot rereads separated by the configured poll interval; it never
  repeats writes to force convergence. Both roles attempt restoration independently and expected
  LIFX errors remain restoration failures. The failed preliminary live run is private,
  non-finalisable and creates no official evidence.
- **D-22 role-local Luna reconciliation:** The operator accepted the completed Tile theme
  observations as fidelity observations after the Tile itself failed restoration. They remain
  private and non-finalisable. Luna is tested only through a fresh role-only session: it never
  connects to, resumes, restores, or merges evidence from the Tile run. Its 12 observations and
  checkpoint are private reconciliation material, `finalisable=false`, and cannot emit or
  satisfy the 24-cycle official result. The role-only terminal is explicitly
  `role-complete/manual-reconciliation-needed`; an independent Luna restore failure remains
  exit 3.
- **D-23 non-Tile application settling:** The operator observed that Luna and Ceiling products
  can take about five seconds after a manual app Save to settle into a new Morph theme, unlike
  the faster Tile. For `non-tile-matrix` app keys only, the first fresh complete non-empty MORPH
  palette starts a fixed, recorded 5.0-second settle interval. That trigger is discarded, then a
  new independent stability window requires two equivalent, complete MORPH palettes that remain
  different from the prior completed app palette. The settle interval never consumes the 300-second
  operator-action deadline or the post-settle stability timeout; OFF, incomplete, unchanged or
  unstable post-settle reads fail closed. The duration has a finite, non-negative CLI override and
  private safe-settings/provenance record. Tile app observations receive no extra settle interval.
  The earlier Luna-only one-cycle Mondrian run preceded this contract, is permanently private and
  non-finalisable, and its observation is provisional rather than accepted evidence; it must never
  resume.
- **D-24 operator-approved exception closeout:** The operator accepted the hardware theme-fidelity
  outcome after two separate role-local blocks: the source Tile produced twelve stable expected
  matches, but its restoration/device-state verification failed; the non-Tile matrix role produced
  twelve stable expected matches under D-23's 5.0-second settling contract and restored
  successfully. These records remain separate and private. They must never be merged into, resumed
  as, or represented as a designated finalisable 24-cycle run. Plan 08-04 closes with this explicit
  safety/infrastructure exception, records no public evidence artefact, requires no further
  hardware action, and leaves Phase 8 requirement and phase verification status to the verifier.
  [08-EXCEPTION-OVERRIDE.json](08-EXCEPTION-OVERRIDE.json) is the committed structured decision;
  it is an override, not restoration evidence or a finalisable UAT result.
- **D-25 decoupled ceiling determination:**
  [08-CEILING-DETERMINATIONS.json](08-CEILING-DETERMINATIONS.json) commits the exact 25 sorted
  `lifx-app`/literal-16-colour slug determinations directly from `data/themes.jsonl`. It records
  `device-ceiling-unresolvable` because `MAX_PALETTE_COLORS` limits both effect packet forms to
  16 colours. This answers only true-length determinability and does not finalise hardware UAT.
- **D-17 mutation-boundary correction:** Restoration is mandatory only after both devices have
  connected, passed metadata/preflight, yielded complete OFF snapshots and the initial private
  checkpoint has been durably written. The boundary is set immediately before the first
  activation or app/library callback, so a callback fault restores both captured roles. A contact,
  metadata, snapshot or initial-checkpoint failure is pre-mutation: best-effort closes only,
  redacted incomplete exit 2, no fabricated restoration verdict and no final checkpoint. A close
  failure is likewise exit 2 before the boundary but has restoration-failure exit 3 precedence
  after it. The clean run `fead749fc8d240c7bb637caf45df2708` failed before the boundary; it is
  private, non-finalisable and has no mutation evidence.
- **D-06/D-13 alternating-app supersession:** LIFX cannot reselect the picker’s current theme,
  and the Morph configuration hierarchy does not expose that current theme. For each role the
  operator therefore positions static OFF Morph with Cheerful configured and supplies the private
  `--attest-role <role> --attest-initial-theme cheerful` claim before any invocation reaching an
  app key. The claim stores only run ID, role, opaque binding digest, timestamp and `cheerful`; it
  is separate from, and never represented as, UI observation. After the durable baseline the
  app keys are `mondrian` 1, `cheerful` 1, `mondrian` 2, `cheerful` 2, `mondrian` 3, `cheerful` 3,
  so a Save never reselects the immediately prior app theme. The six library keys stay grouped
  Cheerful 1–3 then Mondrian 1–3. A library-only resume may continue until its next app key,
  where missing/mismatched claims stop before play or Save. The schedule digest invalidates old
  grouped checkpoints. Run `1a5bdd47875c48cfa65d1c44f4934935` is private and non-finalisable:
  activation passed, its first Cheerful Save completed, and the second picker failed because
  Cheerful could not be reselected; it produces no official evidence.
- **D-11 supersession:** An app key on a fresh invocation or after interruption requires a fresh
  role attestation tied to the current run ID and binding digest. A pending library key needs no
  UI attestation, but the next app key does. Source attestation cannot satisfy non-Tile work: the
  switch at key 13 stops at a separate manual non-Tile checkpoint.
- **D-08 clarification:** Hardware access is solely a one-off Phase 8 acceptance activity. The
  committed runner tests use injected fakes; CI and regular validation do not require this tablet
  or either light.

### Automated probe workflow

- **D-01:** The app path is fully automated with UIAutomator. Each app cycle first issues the
  declared `lifx:/home` VIEW deep link with fixed arguments, without force-stopping the app, then
  uses exactly-two fresh hierarchy retries to prove Home exposes every bound device label or its
  exact configured group-card before it uses the exact approved device label. A hierarchy with raw
  `Select lights` is never Home, even when it exposes an exact bound label, and consumes a fresh
  retry instead; if the label is
  hidden, it expands only that target's private exact group-card accessibility-ID suffix
  `ax_device_list_group_card_button_<app_group>`, then requires exactly one right detail panel
  whose raw resource-ID basename is `detail_panel` and one raw-text configured group heading
  whose centre lies inside it. It next resolves a stateful selector marker inside that panel whose
  raw text is exactly `Lights` (the known zero-selection state), then taps only its unique
  smallest-area clickable container (never the global content-description tab or unrelated numeric
  node). A positive ASCII decimal count is an opaque pre-existing selection and fails closed before
  the selector or target can be tapped. It requires raw-text `Select lights` from a
  fresh hierarchy, then re-requires the exact device label using at most five fresh dumps: while absent, it requires
  exactly one current `android.widget.ScrollView` with `scrollable="true"`, swipes from that
  control's lower to upper quartile, and fails closed on no progress, ambiguity or exhaustion.
  After exactly one tap of that exact target, it does not require the now-hidden label or a device-detail
  surface: fresh retries must instead prove the configured in-panel group heading and stateful raw
  selector count exactly `1`. If exactly one raw `Select lights` label is still present, it taps
  only the unique clickable close control with accessibility-ID suffix
  `ax_device_control_close_button`, whose centre is in and horizontally overlaps the detail panel
  and whose bounds are above that selector; it then freshly proves the selector is absent, count
  remains `1`, and the FX tab is unique. If the app auto-closes the selector, only that direct
  selector-absent count-`1`/FX proof is accepted. It opens FX through accessibility-ID suffix
  `ax_device_control_effects_tab`, then opens MORPH, selects the theme and taps Save.
  The app is not force-stopped between cycles. Preflight opens Home once and proves both bindings
  there without opening either selector, then reconnoitres the full zero-to-one/FX/MORPH/picker
  chain for the source Tile only; the non-Tile receives exact Home and LAN identity/capability
  proof before its scheduled app cycles. Source reconnaissance omits Save, so it does not change
  either light, but its app target selection may persist as count `1`; this is manually reset to
  raw `Lights` at the blocking checkpoint before Task 2. It never retries a target tap, uses a
  generic close control, or uses Android Back after the one exact semantic close attempt.
- **D-02:** Theme lookup uses one exact display-name match in the already-open semantic
  picker grid. Category headings may be observed but are never controls: the Android picker
  has no category switch button. When the theme is not currently rendered, the runner reads a
  fresh hierarchy, requires one current scrollable picker and derives its gesture from that
  control's bounds. Recorded grid positions, remembered containers and coordinate-only
  selection are not authoritative.
- **D-03:** Before either light is touched, preflight requires exactly one authorised
  Android tablet, the installed and signed-in LIFX app, an unlocked screen, both target
  devices visible, and the exact manually positioned Morph configuration surface.  It records
  the live app version and a stable canonical fingerprint of two current Morph hierarchy reads.
  That fingerprint binds the current read-only surface, not an enumeration of the picker (manual
  operation deliberately performs no navigation, picker opening, or Save).  The separately frozen
  Cheerful/Mondrian theme-record hashes bind the approved catalogue entries; any live app surface
  or firmware drift fails the run before checkpoint or mutation.
- **D-04:** A missing expected theme or Save control gets two semantic-lookup retries.
  Exhausting them records the failure, captures local diagnostics, restores device and
  tablet state, and stops the run.
- **D-05:** After Save, bounded stability polling records every LAN read. Two consecutive
  identical unordered palettes establish the official stable readback. Timeout fails the
  cycle; a stable palette unequal to the expected shipped theme is retained as mismatch
  evidence. Transitional reads remain local evidence except the D-23 non-Tile action trigger,
  which is deliberately discarded before the post-settle window. The 2026-08-16 correction
  supersedes the capture-era reset-palette assumption: it was never a canonical
  reusable signature and requires neither operator input nor a guessed constant.
  For the non-Tile guided app path, D-23 adds a fixed recorded settle interval after the fresh
  trigger and before a new two-read stability window; the trigger cannot become the cycle result.
- **D-06:** Per role, app cycles alternate Mondrian 1, Cheerful 1, Mondrian 2, Cheerful 2,
  Mondrian 3, Cheerful 3 from an operator-attested hidden Cheerful configuration, then library
  cycles remain grouped Cheerful 1–3 then Mondrian 1–3. A stable mismatch does not shorten the
  dataset: all remaining fixed cycles run, every mismatch remains recorded, restoration still
  runs, and the criterion fails.
- **D-07:** The runner temporarily enables Android keep-awake after capturing the prior
  setting and restores that setting on every exit path.
- **D-08:** The runner is a phase-local UAT harness at
  `.planning/phases/08-hardware-fidelity-validation/uat_theme_fidelity.py`, not permanent
  Phase 9 capture tooling. It shows detailed redacted progress and mirrors events to a
  local JSONL trace.
- **D-09:** UI and stability waits have documented defaults with explicit CLI overrides;
  every effective value is recorded, including the non-Tile settle interval and selected
  mode/role in the first private safe-settings trace. Exit statuses distinguish pass, validation
  mismatch,
  incomplete/preflight failure and restoration failure.
- **D-10:** Raw screenshots, UI hierarchies and JSONL traces stay outside committed
  evidence. Delete them after a full pass; retain them locally after failure and print the
  diagnostic directory for review.
- **D-11:** Interrupted runs resume at the next unfinished cycle rather than starting
  over. Resume recaptures the current app version, read-only Morph-surface fingerprint, exact
  binding digests, and firmware from the connected bound devices, then requires exact provenance
  equality for those values plus runner revision, themes, ordering and effective timeouts. The
  interrupted record and all completed cycle evidence remain intact.
- **D-12:** Resumable private connection details live in a restrictive local-only
  checkpoint outside git. Committed evidence identifies targets only as `source-tile` and
  `non-tile-matrix` plus the permitted product metadata.

### Fixed theme pair

- **D-13:** Official Phase 8 runs always use only `cheerful` and `mondrian`, with no theme
  override. Cheerful is the hidden operator-attested starting configuration, while app Saves
  alternate Mondrian then Cheerful to avoid selecting the current theme; library cycles stay
  grouped Cheerful then Mondrian. Cheerful is the first theme in the captured UI and has five
  colours; Mondrian is the first Art Series theme and has 16 colours. This deliberately
  minimises picker scrolling.
- **D-14:** The runner hardcodes only the two shipped slugs. Preflight derives category,
  display name and expected palette from `data/themes.jsonl`, then freezes a hash of the
  resolved records into the run provenance.

### Device targeting and restoration

- **D-15:** A private, git-ignored local target file explicitly names one source Tile and
  one indoor non-Tile matrix device. The runner does not choose targets through unrestricted
  fleet discovery.
- **D-16:** Prefer a Ceiling as the non-Tile product, with Luna as fallback. Both product
  families must still pass live capability validation as non-Tile matrix devices before
  mutation.
- **D-17:** Preflight must capture a capability-complete restoration snapshot: power, base
  colour, active effect and settings, full matrix pixels, and Ceiling uplight/downlight
  state where applicable. Any missing required read aborts before mutation. Restore writes the
  device-wide base colour before per-tile pixels, then verifies exact pixel readback after
  bounded settling. The snapshot must observe equal power and base-colour reads twice as well
  as equal effect/pixels. It compares only static Tile geometry; accelerometer telemetry is
  neither restorable nor part of the restoration verdict.
- **D-17a:** Private checkpoint snapshots are audit state, not a crash-recovery serialisation.
  A resumed process must establish a new complete static OFF baseline before it can run; it does
  not decode checkpoint records to write a prior light state.
- **D-18:** The private target file binds LAN address, serial and app-visible label. LAN
  metadata and the app-selected label must prove both paths address the same physical
  light. None of those private identifiers may enter committed evidence.

### Committed evidence

- **D-19:** Structured JSON is the machine-checkable authority and rendered Markdown is
  the human review surface. The stable official pair is `08-UAT-RESULTS.json` and
  `08-UAT.md`, finalised from the designated complete or definitively failed run.
  Interrupted checkpoints remain local and are referenced only by opaque run ID.
- **D-20:** Generate the 25-row ceiling table mechanically from the sorted records in
  `data/themes.jsonl` whose disposition is `lifx-app` and whose colour count is 16. Attach
  the applicable cited length determination to every row; do not maintain a parallel slug
  list or CSV.
- **D-21:** Official evidence finalisation is fail closed. An allowlist schema rejects
  private fields and address/identifier patterns, then verifies the exact 25-slug set,
  required cycle counts, palette comparisons and restoration verdicts before either
  official file is written.

### Agent's Discretion

None — every implementation question discussed was answered directly.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Locked requirements and milestone context

- `.planning/phases/08-hardware-fidelity-validation/08-SPEC.md` — Locked requirements,
  scope, constraints, acceptance criteria, edge coverage and prohibitions. **MUST read
  before planning.**
- `.planning/REQUIREMENTS.md` — FIDELITY-01 through FIDELITY-03 and the stale count that
  Phase 8 must correct.
- `.planning/ROADMAP.md` — Phase goal, dependencies and relationship to Phase 9.
- `.planning/PROJECT.md` — Real-hardware constraints, authorised capture approach and
  project-wide quality gates.

### Theme data and prior decisions

- `data/themes.jsonl` — Shipped source of truth for the fixed theme records and mechanical
  25-theme ceiling set.
- `.planning/phases/06-generated-theme-library/06-CONTEXT.md` — Canonical ordering,
  unordered-multiset equality, generated-data boundaries and test patterns.
- `.planning/phases/07-taxonomy-legacy-dispositions/07-CONTEXT.md` — App categories,
  dispositions and the rule that Phase 8 does not alter palettes.

### App capture method

- `.claude/theme-capture/README.md` — Authoritative Save-before-readback method, reset
  palette caveat and existing capture commands.
- `.claude/theme-capture/themes.jsonl` — Captured picker order proving Cheerful and
  Mondrian are the earliest qualifying pair.
- `.claude/theme-capture/tools/sweep_themes.py` — Existing semantic UI selectors and
  Android navigation patterns to reuse rather than replace with coordinates.

### Device and protocol integration

- `src/lifx/devices/matrix.py` — `get_effect()`, `set_effect()`, palette-count slicing and
  matrix state operations used by the runner.
- `src/lifx/devices/ceiling.py` — Ceiling component state and save/restore behaviour that
  capability-complete restoration must preserve.
- `src/lifx/products/registry.py` — Current Ceiling and Luna matrix capabilities and
  product metadata.
- `src/lifx/theme/theme.py` — `Theme.palette_equals()` unordered-multiset comparison.
- `src/lifx/const.py` — Protocol palette ceiling shared by Tile and multizone effects.

### Real-hardware safeguards

- `.agents/skills/spike-findings-lifx-async/SKILL.md` — Real-hardware, quiescence and
  repeated-measurement constraints.
- `.agents/skills/spike-findings-lifx-async/references/concurrency-and-keepalive.md` —
  Single-shot measurement and hardware timing facts.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- `MatrixLight.get_effect()` and `MatrixLight.set_effect()` already expose the reported
  MORPH palette and accept the shipped palette without a new public API.
- `Theme.palette_equals()` already supplies exact unordered uint16 HSBK multiset equality
  with duplicate counts preserved.
- `.claude/theme-capture/tools/sweep_themes.py` already contains semantic `theme_button`
  and `save_button` lookup plus picker traversal patterns; its capture-era reset observation
  is not an authoritative Phase 8 sentinel.
- The product registry already distinguishes Tile, Ceiling and Luna capabilities and
  supplies model/product metadata for sanitised evidence.

### Established Patterns

- Phase-local hardware harnesses and JSON result artefacts already exist under prior
  `.planning/phases/*` directories; Phase 8 follows that UAT pattern.
- Hardware evidence complements but never replaces emulator-backed unit tests and 100%
  branch patch coverage for support-code changes.
- Generated or mechanically derived inventories use one committed source of truth rather
  than parallel hand-maintained lists.

### Integration Points

- The UAT harness uses Android only for input-free app/version/Morph-config preflight.
  During a run, the operator applies and saves each requested app theme while the runner
  observes only the bound device's LAN MORPH palette; it writes candidate evidence only
  after restoration and schema validation.
- Ceiling restoration must include the component APIs in `ceiling.py`; Luna uses the
  standard matrix path after live product validation.
- Focused tests belong beside the phase harness or in the matching test modules, while
  runtime library dependencies remain at zero.

</code_context>

<specifics>
## Specific Ideas

- Minimise Android picker scrolling: Cheerful is first overall and Mondrian is the first
  Art Series theme.
- App picker automation is deliberately superseded by concise operator action prompts.
  Repeated zero-cycle picker failures on 2026-08-16 made it slower than the prior day's
  130+ manual mappings. The runner retains exact role/theme ordering, fresh attestation,
  bounded LAN polling and durable checkpoints rather than pretending UI automation is a
  reliability feature.
- An interrupted run may resume, but only under byte-for-byte-equivalent provenance inputs
  and the same privately bound devices.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 08-hardware-fidelity-validation*
*Context gathered: 2026-08-15*
