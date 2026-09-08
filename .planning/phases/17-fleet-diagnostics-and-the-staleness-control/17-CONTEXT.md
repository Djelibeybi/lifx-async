# Phase 17: Fleet Diagnostics and the Staleness Control - Context

**Gathered:** 2026-09-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Three reporting defects in the operator-facing IPv6 Thread probe, one new opt-in redaction
flag on that probe, one WiFi staleness control run against the frozen THREAD-04 protocol, the
written verdict that gives v2.0's two Thread figures a comparison and corrects a conflated
number in the roadmap, and the caller-facing consequence of both directions published where a
caller will meet it. Delivers changes confined to `.planning/scripts/` (outside the measured
tree), a `17-EVIDENCE/` directory, one finding document, and prose in two `docs/user-guide/`
pages with a contract-test lock.

</domain>

<spec_lock>
## Requirements (locked via SPEC.md)

**8 requirements are locked.** See `17-SPEC.md` for full requirements, boundaries, edge
coverage, prohibitions and acceptance criteria.

Downstream agents MUST read `17-SPEC.md` before planning or implementing. Requirements are not
duplicated here.

**In scope (from SPEC.md):**
- The three `report_records()` fixes in `.planning/scripts/ipv6_thread_probe.py` (R1, R2, R3)
- Tooling tests in `.planning/scripts/tests/test_ipv6_thread_probe.py` covering each fix
- One pseudonymised probe transcript from the real Thread fleet (R4)
- One WiFi staleness trial through the unchanged `staleness` subcommand, with a WiFi roster
  satisfying `validate_expected_roster()` (R5)
- A `17-EVIDENCE/` directory holding the WiFi session manifest and staleness JSONL (R5)
- A written finding with the verdict and the figure correction (R6)
- ROADMAP and REQUIREMENTS corrections for the conflated 69 s figure (R6)
- One caller-facing discovery liveness passage in `docs/` (R7)
- Pseudonymisation of every committed artefact (R8)
- **Added by amendment A2:** an opt-in `--alias-map` redaction flag on the probe, with its own
  tooling tests

**Out of scope (from SPEC.md):**
- Changes to `src/lifx/` library code
- Changes to `validate_expected_roster()` or to `STALENESS_CAP_S`
- A finer poll cadence for the WiFi leg
- Repeated WiFi trials or additional device classes
- Root-causing a surprising WiFi result
- Settling LIFX's SRP lease value
- Editing `docs/changelog.md`
- The em dash sweep of pre-existing `docs/` prose (Phase 20 owns DOCS-09). `discovery.md`
  already contains an em dash at the end of the bounded-discovery paragraph. This phase leaves
  it alone and adds none of its own.

**Two SPEC amendments were made during this discussion.** Both are recorded in `17-SPEC.md`
under `## Amendments`. Neither changes a requirement; both change how one is evidenced.

- **A1:** AC-01, AC-02 and AC-08 become state-level rather than message-text assertions,
  because D-06 puts the malformed handling in `_instance_view()` and D-08 puts the tests in a
  class that asserts on the view rather than stdout. AC-08 retains one `report_records()`
  smoke assertion, since "the run completes" is R3's reason for existing.
- **A2:** the hand-pseudonymisation decision is replaced by an opt-in `--alias-map` redaction
  on the probe itself. The spec-phase choice was made without knowing that two sibling scripts
  already carry an alias-map loader.

</spec_lock>

<decisions>
## Implementation Decisions

### Refusal-state reporting (R1)

- **D-01:** The probe distinguishes **two** non-resolving states, using the cache's public
  surface only: `addresses_for(target)` empty means no address record has been cached;
  non-empty with no selection means the cached records exist and none was usable.

  A third state exists and is deliberately not named. `_owner_is_unusable()` refuses an owner
  for budget exhaustion, byte-incompleteness or address overflow, independently of what is
  cached. Naming it would require either reading private cache attributes, which couples the
  probe to internals Phase 16 has just reshaped, or inferring it from absence in
  `pending_targets()`, which is wrong whenever the target was skipped for one of that method's
  five other reasons. A guard refusal therefore reads as "cached but unusable" when records
  exist and as "nothing cached" when they do not, which is true in both cases.
  **Reversibility:** reversible. Local to one reporting branch.

- **D-02:** The refused-record message names the record count **and** classifies each record
  the way the existing AAAA block does. An operator seeing "2 cached, both unscoped
  link-local" reads the cause directly rather than inferring it from the block above.

- **D-03:** The summary block splits its counts to match the per-instance view: cached-but-
  unusable is reported separately from awaiting-records. The line removed by R2 leaves the
  slot. Without this the summary would keep dumping `pending_targets()`, which is a different
  set from the per-instance refused set and would read as contradicting it.

- **D-04:** Owner normalisation happens **once**, in `_instance_view()`, where `target` is
  derived. Every downstream lookup in the view then keys on the same normalised owner, and the
  view's `target` field becomes the key the cache actually uses.

  The probe's current `.lower()` is both redundant and slightly wrong: `_normalise_dns_name()`
  casefolds. Note the reason differs from what Phase 16 recorded. D-02 of Phase 16 declined to
  make the helper idempotent, but commit `f060a90` reversed that; the helper now strips every
  trailing dot and casefolds, and its docstring states idempotence is load-bearing. The single
  normalisation site is chosen for key consistency, not because repeat application is unsafe.
  **Reversibility:** reversible.

### Probe reporting structure (R3)

- **D-05:** `_instance_view()` returns a **typed structure** (dataclass or NamedTuple) instead
  of `list[tuple[str, dict[str, object]]]`.

  Two of the three asserts R3 removes are type-narrowing appeasement for the untyped dict, not
  runtime guards: `_instance_view()` always places a real `list` in `"aaaa"` and a `str | None`
  in `"chosen"`. Converting them to runtime branches would create exactly the defect R2 is
  removing, an unreachable branch, and the probe's coverage is not measured so nothing would
  catch it. Typing the structure removes both by construction and leaves the TXT case as the
  only genuine defensive handling.
  **Reversibility:** costly. Every consumer of the view dict, including the existing
  `TestSyntheticCacheReporting` assertions, moves to attribute access in the same change.

- **D-06:** `_instance_view()` **marks** which fields were unusable; `report_records()`
  renders the marking. The existing separation between assembling and printing is preserved,
  and the marking is assertable without capturing stdout.

- **D-07:** A malformed instance still prints its **full block**, with the unusable field
  carrying an explicit marker. Its header, SRV, address and selection lines print as normal.
  Skipping the instance was rejected outright: a diagnostic tool dropping the instance it was
  run to diagnose is the inverse of R3.

- **D-08:** The R1 and R3 tests extend `TestSyntheticCacheReporting`, which already builds real
  `_LifxRecordCache` instances through `add_packet()` with real `DnsResourceRecord`s and
  asserts on `_instance_view()` output. One additional smoke test calls `report_records()` over
  a three-instance cache with a malformed middle and asserts it returns normally. That smoke
  test asserts no message text; SPEC amendment A1 exists because the original AC-01, AC-02 and
  AC-08 assumed message-text assertions this placement cannot make.

### Probe redaction (R4, R8; SPEC amendment A2)

- **D-09:** The probe gains an **opt-in** `--alias-map` flag. With no flag, output is raw
  exactly as today. Raw output is what makes the probe useful, because an operator needs to
  know which physical device is misbehaving; the flag is used only for the run whose output
  gets committed. This matches how `thread_revalidation.py` and `measure_merged_discovery.py`
  already treat their alias maps.
  **Reversibility:** reversible. A new optional flag with no effect on the default path.

- **D-10:** Serial substitution is a **whole-line replace** of any mapped serial, wherever it
  appears. mDNS instance names and SRV target hostnames both embed the serial, so a per-field
  approach would leak through any field nobody thought to cover. This is what makes AC-23
  mechanical rather than a review obligation.

- **D-11:** Addresses are rewritten to a **literal inside a documentation range, from a
  sub-range reserved for that address's source class**, stably within a run, with no two source
  classes sharing a sub-range. Every IPv6 pseudonym comes from inside `2001:db8::/32`: GUA to
  `2001:db8:1::x`, IPv6-other to `2001:db8:2::x`, ULA to `2001:db8:3::x` and link-local to
  `2001:db8:4::x`. IPv4 goes to `192.0.2.x` and an IPv4-mapped value to `::ffff:192.0.2.x`, so
  the mapped shape the cache deliberately retains stays legible. The
  serial-keyed alias map does not cover A records, AAAA records or the packet-source fallback,
  all of which AC-22 forbids in a committed artefact. The reserved prefix is what carries the
  class, because classification is the substance of what R1's refused case demonstrates, and
  stability within a run keeps a device recognisable across the transcript.

  `192.0.2.0/24` and `2001:db8::/32` are the documentation ranges the repository already uses;
  `test_phase_contract.py:373` forbids private-looking IPv4 literals in the discovery guide on
  the same principle.
  **Reversibility:** reversible.

  *Amended twice during planning (2026-09-08). First: this said "documentation-range equivalent
  of the same class" and claimed class is preserved, which is unsatisfiable for GUA, because
  `2001:db8::/32` is the documentation range and `is_global` is False for it, so
  `classify_address()` calls any documentation-range IPv6 address `IPv6-other`. The redactor
  reserves a distinct sub-range per class instead; the distinction survives, but re-running
  `classify_address()` over redacted text does not recover it (amendment A4). Second: the table
  that first amendment settled on sent ULA to `fd00::x` and link-local to `fe80::x`, which are
  operational ranges, not documentation ranges, and the staged-diff backstop was whitelisting
  those forms as safe output. All four IPv6 classes now sit inside `2001:db8::/32`, so any
  `fd00::` or `fe80::` token in a staged diff is a leak by definition (amendment A5).*

- **D-12:** The `--alias-map` flag is its **own commit** with its **own tooling tests**,
  separate from the three `report_records()` fixes. Its tests cover serial substring
  replacement inside instance names and SRV hostnames, class-preserving address substitution,
  and the raw-by-default path. Mixing a redaction feature into three correctness fixes would
  make a revert of either take the other.

### Evidence layout (R4, R5, R6)

- **D-13:** The WiFi session mirrors Phase 14 exactly, and "exactly" includes the
  filenames the tool itself writes. `thread_revalidation.py` hardcodes its eight evidence
  filenames as module-level constants (`_MANIFEST_FILENAME = "14-MANIFEST.json"`,
  `STALENESS_FILENAME = "14-STALENESS.jsonl"`, and siblings, at
  `.planning/scripts/thread_revalidation.py:310-321`); they are not parameterised by
  `--session-dir`, and both `reload_staleness_events()` and `_cli_staleness()`'s
  same-alias-resume check read them back by those literal names. The WiFi session therefore
  lands at `17-EVIDENCE/14-MANIFEST.json` and `17-EVIDENCE/14-STALENESS.jsonl` — a `17-`
  prefix on the directory, the tool's own `14-` prefix on the files — with `session_id`
  `"seed-002"` matching the seed the requirement fired from, as Phase 14 used `"seed-001"`.
  The directory carries the phase identity; the filenames carry the tool's. Renaming the
  files after the run would break resume and the same-alias-rerun guarantee (AC-15), and
  parameterising the constants is a change to a tool R5 and the Out-of-Scope list both treat
  as unchanged. A verifier that can read Phase 14's evidence reads this without learning a
  second shape.

  *Amended during planning (2026-09-08): the original text specified `17-MANIFEST.json` and
  `17-STALENESS.jsonl`, which the unmodified tool cannot produce.*

- **D-14:** R6's verdict lives in its **own document**,
  `17-EVIDENCE/17-STALENESS-CONTROL.md`, carrying both Thread figures, both WiFi figures,
  each figure's measurement resolution, the verdict with its limits, the pre-stated
  opposite-observation clause, and the 69.4 s correction. Precedent:
  `15-TEST-02-EVIDENCE.md`. A finding buried in an execution SUMMARY is hard to cite from
  ROADMAP or a later phase.

- **D-15:** The probe transcript is `17-EVIDENCE/17-PROBE-TRANSCRIPT.md`: run date, git
  revision, invocation, a statement of which new messages appeared and which did not, then the
  redacted stdout in a fenced block. AC-11 requires that narration regardless, so a bare
  `.txt` would only displace it into another file.

### Documentation (R7)

- **D-16:** The liveness note **extends the existing Limitations proxy paragraph** in
  `docs/user-guide/discovery.md`. Phase 16 wrote "proves an advertisement exists, not that the
  advertised device is currently reachable" there; R7 quantifies exactly that claim and adds
  its converse. Placing the measurement away from the claim it quantifies was rejected.

- **D-17:** Figures are stated as **exact values with their measurement resolutions**: the
  4140 to 4200 s Thread interval, 69.4 s Thread restoration, and the WiFi values with the 60 s
  cadence bound named. The paragraph immediately below already disclaims universal
  applicability and forbids sizing timeouts from the documentation, so precision here does not
  become the guarantee SPEC prohibition P1 forbids.

- **D-18:** The new prose gets an **approved-phrase lock**: two or three short distinctive
  fragments added to the tuple at
  `tests/test_network/test_mdns/test_phase_contract.py:124`, following Phase 16 D-16's
  convention. Phase 20 is about to recast this page; a fragment lock survives rewording around
  it while preventing the claim being recast away.
  **Reversibility:** reversible.

- **D-19:** The converse direction also reaches `docs/user-guide/troubleshooting.md` as a
  short cross-referenced entry pointing at the discovery.md paragraph, not a restatement of
  the figures. Someone hitting "my device disappeared after a power blip" looks in
  troubleshooting, and Phase 14's DOCS-05/DOCS-06 linking contract at
  `test_phase_contract.py:393` forbids duplicating the content itself.

### Sequencing and the hardware gate

- **D-20:** Three waves, split on the hardware boundary.
  - **Wave 1** (no hardware): the three `report_records()` fixes, the typed view structure,
    the `--alias-map` flag, and all tooling tests.
  - **Wave 2** (hardware, one operator sitting): the Thread-fleet probe run producing the
    redacted transcript, and the WiFi staleness trial.
  - **Wave 3** (needs Wave 2's numbers): `17-STALENESS-CONTROL.md`, the ROADMAP and
    REQUIREMENTS figure corrections, and both docs surfaces.

- **D-21:** **Each hardware arm can fail independently, and an arm that cannot run leaves its
  evidence requirement open rather than closed.** The probe code work is self-contained and its
  commits are complete without any hardware, so waves 1 and 2 land either way.

  If the **WiFi** run cannot be performed, DISC-04 stays open. If the **Thread** run cannot be
  performed, R4 stays open, and MDNS-10 ships its code and tests with that evidence obligation
  carried forward. Both carry forward the way THREAD-01 to THREAD-05 carried from v1.1 into
  v2.0. Recording either as a `named_gap` and closing the phase was rejected: that would launder
  an unrun experiment as a completed one, which Phase 14's roster gate exists to prevent.

  The two arms are file-disjoint in what they write and neither depends on the other's result,
  so one being impossible never blocks the other. Note that file-disjointness is not by itself
  sufficient for them to run concurrently; they share a git index and an evidence directory.

  *Amended during planning (2026-09-08): this originally covered only the WiFi arm, so
  `17-03-PLAN.md`'s "no thread hardware" exit left R4 open without any decision authorising it.
  Raised by the Codex lane of the second `/gsd-review --phase 17` pass.*

- **D-23:** The staged-diff identity backstop reports **two categories, and only one of them
  blocks**. A token that can only be an identifier fails the automated gate: any twelve-character
  hex run containing at least one `a`-`f` character, any MAC-shaped token, any IPv4 or IPv6
  literal outside the reserved documentation sub-ranges, and any `.local` hostname whose labels
  are not alias-derived. A twelve-character run of decimal digits is reported separately as an
  ambiguous numeric token, does not fail the gate, and must be adjudicated by name at the
  operator checkpoint before that checkpoint may be resumed.

  The split is principled rather than a loosening. Every LIFX serial begins `d073d5`, so it
  always carries hex letters and can never be an all-decimal run; conversely the tool's own
  output carries nanosecond-derived floats and counters whose digit runs collide with the serial
  shape. Without the split the gate had no reachable escape: it exited non-zero on every flagged
  token while task acceptance required `IDENTITY-SHAPED-TOKENS: none`, and execution blocks on
  acceptance, so the checkpoint that was supposed to adjudicate a false positive could never be
  reached. The consequence of that dead end lands after a hardware sitting, which is the most
  expensive place in this phase to discover it.

  The operator, not the gate, remains the authority on an ambiguous token: SPEC's prohibition on
  committing before a staged-diff inspection is resolved as `judgment` precisely because only the
  operator holds the private mapping. This decision makes that judgment reachable; it does not
  transfer it to a regular expression.
  **Reversibility:** reversible.

  *Recorded during planning (2026-09-08), after the third `/gsd-review --phase 17` pass found the
  adjudication path added in the previous round to be unreachable under the execution workflow.*

- **D-22:** No documentation lands before the WiFi numbers exist. AC-20 requires both
  directions with figures and the trial count, so a Thread-only version would publish an
  incomplete claim and force two edits to the same paragraph and its approved-phrase lock.

### Claude's Discretion

- The exact wording of the two new probe messages and the malformed-field marker, subject to
  D-01, D-02 and D-07.
- Whether the typed view structure in D-05 is a `dataclass` or a `NamedTuple`, and its field
  names.
- The name of the `--alias-map` flag's implementation seam and whether address substitution is
  a helper function or a small class.
- The exact prose of the discovery.md extension and the troubleshooting.md entry, subject to
  D-16 through D-19, SPEC prohibition P1, and no em dash.
- Which two or three fragments D-18 locks.
- Commit ordering within each wave, subject to D-12.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Locked requirements
- `.planning/phases/17-fleet-diagnostics-and-the-staleness-control/17-SPEC.md`: locked
  requirements, boundaries, edge coverage, prohibitions and acceptance criteria. MUST read
  before planning. Carries the two amendments made during this discussion under
  `## Amendments`.
- `.planning/ROADMAP.md`: Phase 17 goal, five success criteria, the serial-after-16
  dependency, and the v2.1 constraints. **Criterion 3 and 4 both call 69 s the
  disappearance-to-expiry figure; R6 corrects this file.**
- `.planning/REQUIREMENTS.md`: MDNS-10 and DISC-04 as originally written. **The DISC-04 entry
  carries the same conflated figure; R6 corrects it too.**

### Subject under change (R1, R2, R3, R4)
- `.planning/scripts/ipv6_thread_probe.py:354-403`: `_instance_view()`, whose return type D-05
  changes and where D-04 normalises.
- `.planning/scripts/ipv6_thread_probe.py:404-508`: `report_records()`, holding all three
  defects. Line 481 is the conflated message; 428, 494, 505 and 508 are the dead counter and
  warning; 436, 437 and 485 are the asserts.
- `.planning/scripts/ipv6_thread_probe.py:172-195`: `classify_address()` and
  `is_reachable_choice()`. The first is reused by D-02 and D-11; the second is deleted by R2.
- `.planning/scripts/tests/test_ipv6_thread_probe.py:1039`: `TestSyntheticCacheReporting`, the
  test home D-08 extends.
- `.planning/scripts/tests/test_ipv6_thread_probe.py:131`: `_cache_chain()`, the synthetic
  TXT/SRV/A builder the new fixtures extend with an unscoped link-local AAAA.

### Library surface the probe drives (read, never edited)
- `src/lifx/network/discovery/mdns/discovery.py:144`: `_normalise_dns_name()`. Strips every
  trailing dot and casefolds; idempotent since `f060a90`, which reversed Phase 16 D-02.
- `src/lifx/network/discovery/mdns/discovery.py:201`: `_is_usable_mdns_address()`. Called
  **only** from `_pick_address()` at line 227, never at ingest, which is why an unscoped
  `fe80::` AAAA is admitted to the cache and R1's refused fixture is constructible.
- `src/lifx/network/discovery/mdns/discovery.py:215`: `_pick_address()`. Its rejection of
  unscoped link-local is what makes R2's counter unreachable.
- `src/lifx/network/discovery/mdns/discovery.py:357`: `_owner_is_unusable()`, the third
  refusal state D-01 declines to name.
- `src/lifx/network/discovery/mdns/discovery.py:376`: `selected_address_for()`.
- `src/lifx/network/discovery/mdns/discovery.py:846`: `pending_targets()`. Skips a target for
  six reasons, only one of which is a guard refusal, which is why D-01 rejects inferring the
  third state from it.

### Staleness tooling (R5)
- `.planning/scripts/thread_revalidation.py:3409`: `_cli_staleness()`. No roster gate.
- `.planning/scripts/thread_revalidation.py:2890`: `_cli_init()`, which calls
  `validate_expected_roster()` and demands `Light`, `MultiZoneLight`, two distinct
  `MatrixLight` aliases and `CeilingLight` before writing a manifest.
- `.planning/scripts/thread_revalidation.py:3070`: `_load_target_alias_map()`, the loader
  precedent SPEC amendment A2 reuses. Its docstring names
  `.planning/scripts/measure_merged_discovery.py` as the earlier precedent.
- `.planning/scripts/measurement_support.py`: shared discovery, capture and restore
  primitives the staleness path uses.

### Prior evidence being controlled (read, never modified; SPEC prohibition P6)
- `.planning/milestones/v2.0-phases/14-thread-revalidation-and-docs/14-EVIDENCE/14-STALENESS.jsonl`:
  the single Thread trial. Disposition `confirmed_expiry`, first absence poll 70, confirmed
  poll 72.
- `.planning/milestones/v2.0-phases/14-thread-revalidation-and-docs/14-EVIDENCE/14-MANIFEST.json`:
  the session shape D-13 mirrors, including `staleness_cap_s` 10800.0,
  `staleness_poll_interval_s` 60.0 and `staleness_confirm_absent_polls` 3.
- `.planning/milestones/v2.0-phases/14-thread-revalidation-and-docs/14-06-SUMMARY.md`: the
  paragraph recording 4140 to 4200 s and 69.4 s as different quantities.
- `.planning/seeds/SEED-002-wifi-advertisement-staleness-control.md`: what the control is for,
  the trap in the Thread number, and the two consumer-facing consequences R7 publishes.

### Documentation surfaces (R7)
- `docs/user-guide/discovery.md:110-143`: the Limitations section. The proxy-response
  paragraph D-16 extends sits at 132-137; the universal-benchmark disclaimer D-17 relies on
  sits at 139-143.
- `docs/user-guide/troubleshooting.md`: D-19's cross-referenced entry.
- `tests/test_network/test_mdns/test_phase_contract.py:121-146`:
  `test_public_guidance_uses_the_approved_limitation_phrases` and its 16-entry
  `approved_phrases` tuple, which D-18 extends.
- `tests/test_network/test_mdns/test_phase_contract.py:373-386`:
  `test_discovery_surfaces_use_only_documentation_safe_addresses`, the precedent behind
  D-11's documentation-range choice.
- `tests/test_network/test_mdns/test_phase_contract.py:393`:
  `TestPhase14DiscoveryLinkingContract`, the no-duplication rule D-19 respects.

### Repository guidance
- `AGENTS.md`: the privacy rule binding SPEC prohibitions P2a and P2b, the measured-tree rule
  placing `.planning/scripts/` outside coverage, and the `--tooling` opt-in category.
- `pyproject.toml`: the two-target `--cov` rule and ruff's `PLC0415` per-file-ignore covering
  `.planning/**`, which means the probe's own function-local imports are not swept here.

### Prior context that binds this phase
- `.planning/phases/16-mdns-correctness-docs-and-test-hygiene/16-CONTEXT.md`: D-01 and D-03
  reshaped what `selected_address_for()` returns and where its guards live; the Deferred Ideas
  section names this phase's handoff explicitly. D-16's fragment-lock convention is what D-18
  follows.
- `.planning/phases/15-coverage-gate-and-test-suite-health/15-CONTEXT.md`: the relocation of
  the probe to `.planning/scripts/` and the `--tooling` opt-in mechanism.
- `.planning/STATE.md`: v2.1 working notes, including the Phase 17 serialisation reason and
  the pseudonym rule for both hardware-evidence requirements.

### External issues
- https://github.com/Djelibeybi/lifx-async/issues/212: MDNS-10, PR #211 finding 10.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `.planning/scripts/tests/test_ipv6_thread_probe.py:131` `_cache_chain()` builds a complete
  synthetic TXT/SRV/A chain from real `DnsResourceRecord` objects fed through
  `cache.add_packet()`. R1's two fixtures are this helper with the A record swapped for an
  unscoped link-local AAAA, or omitted entirely.
- `.planning/scripts/ipv6_thread_probe.py:172` `classify_address()` already returns exactly
  the class labels D-11 needs for address substitution, and D-02 needs for the refused
  message. No second classifier.
- `.planning/scripts/thread_revalidation.py:3070` `_load_target_alias_map()` is a complete,
  validated loader: normalises serials through `Serial.from_string()`, runs `validate_alias()`,
  rejects duplicates and empty maps. D-09 reuses its shape rather than inventing one.
- `.planning/scripts/ipv6_thread_probe.py:356` already does private cache access with
  `# noqa: SLF001` for `_fallback_ip_by_instance`, so the precedent exists. D-01 chose not to
  extend it.

### Established Patterns
- The probe imports library internals directly (`_LifxRecordCache`, `parse_dns_response`,
  `build_address_query`, `MdnsTransport`). It is a consumer of private surface by design,
  which is exactly why it belongs outside the measured tree and why Phase 16 had to settle
  before it.
- Evidence files under `.planning/**/` carry a `NN-` phase prefix and are JSON or JSONL for
  machine-read artefacts, Markdown for narrated ones. D-13, D-14 and D-15 follow it.
- `.planning/**` is per-file-ignored for ruff `PLC0415` (Phase 16 D-05), so the probe's
  existing function-local imports are not this phase's problem.
- `.planning/**` is absent from `ci.yml`'s `pull_request.paths` filter, so a change confined to
  Wave 1 does not trigger CI at all. The tooling tests are run by hand with
  `uv run --frozen pytest --tooling` or `uv run --frozen pytest .planning/scripts/tests`.

### Integration Points
- Wave 3's docs changes are the only part of this phase inside `--cov=lifx`'s blast radius,
  and even those touch no measured source. The `codecov/patch` gate therefore scores nothing
  for this phase, which is exactly the condition Phase 15's vacuous-gate guard
  (`.github/patch_coverage_guard.py`) exists to distinguish from a real miss. The guard is
  cause-agnostic and passes when the changed measured set is empty, so a docs-and-tooling
  phase should pass it, but the planner should confirm rather than assume.
- `tests/test_docs_language.py` (Phase 16 D-10) walks every `.md` under `docs/` for prose
  negatives. D-18's new prose must satisfy it, and Phase 20 will extend the same module with
  the em dash rule.

### Stale map warning
`.planning/codebase/TESTING.md` and `CONVENTIONS.md` are dated 2026-06-11 and predate Phase 15.
They describe a 30-second test timeout and `-m "not benchmark"` selection, both replaced by the
60-second timeout and the `--tooling`/`--benchmark` opt-in flags. Trust `pyproject.toml` and
`AGENTS.md` over the maps.

</code_context>

<specifics>
## Specific Ideas

- The three-state truth was surfaced and then deliberately narrowed to two. The operator's
  position was that a probe naming a refusal it inferred imprecisely is the same class of
  defect as the one MDNS-10 is fixing.
- Two of R3's three asserts turned out to be type-narrowing appeasement rather than runtime
  guards. Converting them to branches was rejected on the grounds that an unreachable branch is
  what R2 is removing three lines away.
- The alias-map amendment was accepted specifically because the precedent is two scripts deep.
  The operator's framing was that a structural guarantee beats a manual step once the
  mechanism already exists elsewhere in the same directory.
- Redaction stays opt-in because the probe's value to the operator depends on naming the
  physical device. A probe that cannot tell you which bulb is broken is not a diagnostic.
- Exact figures were chosen over rounded ones because a reader cannot compare the Thread and
  WiFi arms without them, and the disclaimer paragraph is already in place directly below.
- DISC-04 staying open rather than closing as a named gap was the operator's explicit
  preference, on the grounds that Phase 14's roster gate exists to stop exactly that laundering.

</specifics>

<deferred>
## Deferred Ideas

- **Naming the guard-refusal state.** D-01 leaves the `_owner_is_unusable()` refusal unnamed.
  If the cache ever grows a public predicate for it, the probe can name three states without
  private access or imprecise inference.
- **`--alias-map` on the remaining scripts.** After this phase, three of the four measurement
  scripts carry an alias map. `serial_mac_audit.py` does not, and it reads the ARP table.
- **Repeated WiFi trials.** One trial mirrors THREAD-04's design. Bounding variance, or
  chasing the SRP lease value with repeated Thread trials, is SEED-002's own stretch and was
  ruled out of scope in the SPEC.
- **Reading the granted lease directly.** `ot-ctl srp server service` would settle the lease
  question that no number of trials can. Impractical while the OTBR runs inside a Home
  Assistant add-on container.
- **Refreshing `.planning/codebase/` maps.** Carried from Phase 16. TESTING.md and
  CONVENTIONS.md contradict Phase 15's delivered mechanisms; a map-codebase run before the
  v2.1 close would stop the next phase inheriting the same warning.

</deferred>

---

*Phase: 17-fleet-diagnostics-and-the-staleness-control*
*Context gathered: 2026-09-08*
