# Phase 8: Hardware Fidelity Validation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md; this log preserves the alternatives considered.

**Date:** 2026-08-15
**Phase:** 08-hardware-fidelity-validation
**Areas discussed:** Probe workflow, Theme pair, Device safety, Evidence format

---

## Probe workflow

| Question | Alternatives considered | Selected |
|----------|-------------------------|----------|
| App-cycle control | Operator-assisted; fully automated UIAutomator; hybrid fallback | Fully automated UIAutomator |
| UI lookup failure | Two retries then fail closed; immediate failure; manual takeover | Two retries then fail closed |
| Post-Save readiness | Bounded stability polling; fixed delay and one read; immediate read | Record all reads; require two identical consecutive palettes |
| Source ordering | Interleaved pairs; three app then three library; counterbalanced | Three app cycles, then three library cycles |
| Android journey | Full home-screen navigation; start on MORPH; resume from any screen | Full semantic navigation from home |
| Picker lookup | Category plus exact name; exact name only; recorded position | Category plus one exact display-name match |
| Cycle reset point | Return home; force-stop; remain on MORPH | Return to app home before every cycle |
| Failure diagnostics | Local screenshot and UI hierarchy; semantic trace; screenshot only | Local screenshot and UI hierarchy, sanitised summary only |
| Android preflight | Complete fail-closed; connection-only; operator assertion | Complete fail-closed preflight |
| Drift guard | App version plus catalogue fingerprint; app version only; none | App version plus semantic catalogue fingerprint |
| Stable mismatch | Complete all cycles; stop immediately; finish source block | Complete every fixed cycle and fail the criterion |
| Screen state | Temporary keep-awake and restore; wake per action; operator prepares | Temporary keep-awake and restore |
| Runner ownership | Phase-local UAT; extend capture sweep; permanent script | Phase-local UAT harness |
| Live feedback | Detailed redacted trace; milestones only; quiet by default | Detailed progress plus local JSONL trace |
| Timeouts | Defaults with recorded overrides; fixed constants; calibration | Documented defaults with explicit recorded overrides |
| Exit contract | Distinct statuses; binary; evidence-only | Distinct pass, mismatch, incomplete and restoration statuses |
| Raw diagnostic retention | Delete on pass/retain on failure; always retain; always delete | Delete on pass and retain locally on failure |
| Interrupted run | Fresh run; resume next cycle; restart interrupted block | Resume at the next unfinished cycle |
| Resume gate | Exact provenance; device/theme only; operator override | Exact provenance match |
| Private checkpoint identity | Local private details; hashes; rediscovery | Restrictive local-only checkpoint |

**User's choice:** Fully automated, resumable, fail-closed UAT runner with complete
diagnostics and provenance.

**Notes:** The first answer to the catalogue-drift question was an accidental backtick;
the question was repeated and the app-version plus catalogue-fingerprint option was
selected. Full fixed cycle collection continues after a mismatch so no failure can be
retried away.

---

## Theme pair

| Question | Alternatives considered | Selected |
|----------|-------------------------|----------|
| Selection criterion | Boundary-adjacent palette; previously confirmed theme; earliest UI position | Earliest qualifying themes to minimise scrolling |
| Fixed pair | Several below-ceiling and Art Series candidates | Cheerful and Mondrian |
| Cross-path binding | Slugs plus derived metadata; copied records; raw capture binding | Freeze slugs and derive/hash shipped metadata |
| Theme order | Cheerful first; Mondrian first; alternating | Cheerful, then Mondrian |
| Overrides | None; diagnostic CLI overrides; manifest-controlled | No theme overrides for official runs |

**User's choice:** `cheerful` followed by `mondrian`, fixed for Phase 8.

**Notes:** The user rejected choosing primarily by palette boundary and advised selecting
themes high in the Android picker so automation scrolls as little as possible. Inspection
confirmed Cheerful is the first theme overall and Mondrian is the first qualifying Art
Series theme.

---

## Device safety

| Question | Alternatives considered | Selected |
|----------|-------------------------|----------|
| Target supply | Private local file; CLI addresses; allowlisted discovery | Private git-ignored target file |
| Non-Tile product | Candle; Ceiling; any qualified product | Ceiling first, Luna fallback |
| Restoration snapshot | Capability-complete; changed state only; best effort | Capability-complete and fail before mutation if incomplete |
| LAN/app identity | Exact private binding; model match; operator confirmation | Exact IP/serial/label binding kept out of committed evidence |

**User's choice:** Explicit source Tile plus Ceiling, with Luna fallback, under exact
private identity binding and complete state restoration.

**Notes:** Current `src/lifx/products/registry.py` was checked during discussion and marks
both Ceiling and Luna product families as matrix-capable.

---

## Evidence format

| Question | Alternatives considered | Selected |
|----------|-------------------------|----------|
| Canonical format | JSON plus Markdown; JSON only; Markdown only | Machine-checkable JSON plus rendered Markdown |
| Run history | One stable official pair; append-only runs; overwrite latest | One stable complete or definitively failed pair |
| Ceiling table | Generated from shipped data; hand-maintained Markdown; CSV source | Mechanically generated from `data/themes.jsonl` |
| Finalisation gate | Fail-closed schema; redaction pass; manual review | Fail-closed allowlist and completeness validation |

**User's choice:** `08-UAT-RESULTS.json` as authority with `08-UAT.md` for review,
generated and validated from repository sources.

**Notes:** Interrupted checkpoints remain local; a designated complete or definitively
failed run produces the stable official pair.

---

## Agent's Discretion

None.

## 2026-08-16 activation and restoration correction

**User's observation:** Saving a theme against stopped Morph left the Tile white. Manually
starting Morph retained a clickable/enabled `play_button`; it did not become a stop control or
an active-state indicator. A read-only LAN effect read independently reported MORPH with a
non-empty palette.

**Selected:** Capture the static OFF baseline first, then perform one exact play activation for
the attested role and require stable LAN MORPH/palette confirmation before theme Save work.
Restore writes once and waits for bounded stable full-state rereads at the configured poll
interval. The failed preliminary live run is private and non-finalisable; no official evidence
is produced from it.

## 2026-08-16 mutation-boundary correction

**Observation:** The clean run `fead749fc8d240c7bb637caf45df2708` failed before contact,
snapshot, checkpoint, activation or cycle evidence. The lifecycle's unconditional cleanup
misclassified its missing snapshots as restoration failures.

**Selected:** Treat the durable initial checkpoint after both contacts, metadata/preflight and
complete OFF snapshots as the explicit mutation boundary. Before it, close only best-effort and
return redacted incomplete exit 2 without a restoration record or terminal checkpoint. After it,
restore both captured roles on every terminal path; restoration or close failure has exit 3
precedence. The observed run remains private, non-finalisable and has no mutation evidence.

## 2026-08-16 alternating picker correction

**User observation:** The LIFX picker cannot reselect its current theme, while the Morph
configuration hierarchy does not expose the current theme. Run
`1a5bdd47875c48cfa65d1c44f4934935` activated Morph and completed the first Cheerful Save, then
opened the second picker and failed attempting to select current Cheerful.

**Selected:** Before a run/resume reaches an app key, the operator positions that role’s static
OFF Morph configuration with Cheerful configured and supplies matching private
`--attest-role` plus `--attest-initial-theme cheerful`. This is an operator claim, not UI
observation. App Saves alternate Mondrian 1, Cheerful 1, Mondrian 2, Cheerful 2, Mondrian 3,
Cheerful 3; library keys remain grouped Cheerful 1–3 then Mondrian 1–3. The changed schedule
digest rejects old grouped checkpoints. A library-only resume continues only until its next app
key, which requires fresh positioning and both claims. The observed run is private,
non-finalisable and has no official evidence.

## 2026-08-16 picker traversal and Tile restoration correction

**User observation:** The Android picker has no category switch button. Mondrian is reached
by scrolling the already-open picker; headings such as Art Series are display observations,
not controls. Run `12dc7a6b8e994077b664bd2b71999ce3` activated Morph and then stopped before
its first cycle when the runner searched for a category control instead of scrolling. It is
private, non-finalisable and contributes no official evidence.

**Selected:** After the exact in-panel theme button, each lookup reads a fresh hierarchy and
matches the exact theme name. If absent, it requires exactly one currently scrollable picker,
derives the swipe solely from that control's current bounds, and stops on an ambiguous, stale,
repeated or exhausted surface. It never taps a category control. Cheerful remains initially
visible; Mondrian is found by bounded picker scrolling.

**Restoration finding:** `MatrixLight.set_color()` is device-wide. The old restore sequence
wrote exact Tile pixels and then restored base colour, which overwrote those pixels. Restoration
now writes base colour before the exact per-tile frame and verifies the complete pixel readback
after bounded settling. Chain comparison retains only static geometry needed to address pixels;
accelerometer readings are live telemetry and cannot be restored. Checkpoint snapshots are
private audit records only: an interrupted process takes a fresh static OFF snapshot and does
not claim out-of-process restoration from serialised checkpoint data.

## Deferred Ideas

None.

---

## 2026-08-16 execution supersession

**User's choice:** Make positioning a manual operator checkpoint. The app's selector close
obscures target identity, so automated Home/group/selector/close navigation is retired. Each app
cycle requires an explicit `--attest-role` operator claim for its configured target and separately
proves only the in-panel Morph configuration signature (`effect_name` `Morph`, `effect_subtitle`
`Effect`, configuration scroll and enabled/clickable theme button). The hierarchy cannot prove
the selected label, parent group or raw count on this screen; the private LAN binding digest
bridges the explicit claim to exact device identity. The
source and non-Tile roles require separate positioning checkpoints. This remains one-off UAT,
not a recurring hardware test.

**2026-08-16 read-only contact observation:** The full preflight exhausted a single initial
connection while isolated fresh connections could succeed. The selected containment is at most one
fresh retry inside Phase 8's initial bound-device adapter, only after an expected contact failure
and only after closing a partial device. No metadata, snapshot, app or mutation operation retries.

## 2026-08-16 guided app-cycle supersession

**User decision:** Stop automating the LIFX picker. Repeated picker attempts produced zero
completed cycles and were materially slower than the 130+ themes manually mapped the previous day.

**Selected:** Every scheduled app cycle prints an exact public role/theme action: the operator
applies and saves that theme in Morph, then starts or keeps Morph running. The runner makes no
Android input, picker, Save, play, scrolling, category or recovery call. It accepts only two equal,
complete LAN MORPH palette observations after the prompt. Later app cycles must differ from the
previous app palette under exact unordered uint16 multiset equality. Stable mismatches remain
evidence and continue; OFF, incomplete, unstable or unchanged observations checkpoint then fail
closed and restore. Each invocation owns one role block from fresh OFF baselines through
restoration; a subsequent role begins only from a fresh matching role/initial-theme attestation.

## 2026-08-16 guided-run correction

The newest guided source-Tile attempt is private and non-finalisable: it produced zero completed
measurements and its source restoration remains unverified. It must never be resumed. The runner
had incorrectly spent the 15-second LAN stability timeout while waiting for an operator and chat
relay to apply a theme; operator action now has its own bounded 300-second deadline, after which
the existing stability timeout begins for the second equivalent MORPH read. Its checkpoint path
also incorrectly placed an incomplete cycle in the completed schedule prefix. Incomplete or failed
cycles are now retained only in private trace and terminal diagnostics, with the same key still
pending; a complete stable mismatch has `matches_expected: false` with no failure and continues as
valid evidence. The guided observer still performs no Android input.

## 2026-08-16 Luna-only reconciliation decision

**User decision:** Retain the twelve observed Tile theme comparisons as private fidelity
observations, acknowledge the unresolved Tile restoration/device-state failure, and test Luna
next without retrying or resuming that run. The Luna session is fresh and role-local: preflight,
baseline, checkpoint, twelve alternating guided-app/library keys and restoration address Luna
only. It cannot contact, write, restore or load Tile state; it has no resume or finalise path and
its result is permanently private (`finalisable=false`). A completed Luna block exits as
`role-complete/manual-reconciliation-needed`, not as a 24-cycle pass; later human reconciliation
must not conflate the two role-local artefacts into official evidence.

## 2026-08-16 non-Tile settling correction

**User observation:** Luna and Ceiling products need about five seconds after a manual app theme
Save to settle into the new Morph palette. The Tile settles faster.

**Selected:** For guided `non-tile-matrix` app observations only, the first fresh complete,
non-empty MORPH palette starts a recorded default 5.0-second settle interval. The trigger palette
is discarded. A new, separately budgeted stability window then requires two equivalent complete
MORPH palettes, both still different from the prior completed app observation under unordered
uint16 comparison. Any OFF, incomplete, unchanged or unstable post-settle read is incomplete.
The 300-second operator window remains only for detecting the fresh change; the settle time does
not reduce the post-settle stability timeout. The Tile path gets no added wait. The value is a
finite non-negative CLI override and is retained in private safe settings and provenance.

**Historical classification:** The prior fresh Luna-only run captured one Mondrian observation
before this required settle period. It remains private and non-finalisable, is now provisional and
not accepted as a Luna measurement, and must never be resumed.

## 2026-08-16 operator-approved exception closeout

**User decision:** Close Plan 08-04 with exception. The source Tile's twelve stable expected
theme matches are accepted as hardware-fidelity observations, while its restoration/device-state
failure remains an unresolved safety/infrastructure exception. The later non-Tile role-only block
has twelve stable expected matches, used the five-second non-Tile settling rule, and restored
successfully.

**Selected:** Do not retry hardware, resume either role-local record, or manufacture a combined
24-cycle artefact. Official JSON/Markdown finalisation is deliberately withheld because no one
designated run satisfies the complete two-role restoration gate. The closeout records the operator
acceptance and the exception without changing Phase 8 requirement status; a later verifier owns
that classification.
