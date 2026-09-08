# Phase 17: Fleet Diagnostics and the Staleness Control - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md; this log preserves the alternatives considered.

**Date:** 2026-09-08
**Phase:** 17-fleet-diagnostics-and-the-staleness-control
**Areas discussed:** Refusal-state granularity, Defensive reporting shape, Evidence layout and
pseudonyms, Docs home for the liveness note, Hardware gating and wave shape

---

## Refusal-state granularity

Opened with a scouting finding that reshaped the requirement: `_is_usable_mdns_address()` is
called only from `_pick_address()` (discovery.py:227), never at ingest, so an unscoped `fe80::`
AAAA is admitted to the cache. That makes R1's refused fixture constructible and reveals a third
state SPEC R1 does not name.

### How many states, and read from where

| Option | Description | Selected |
|--------|-------------|----------|
| Two states, public surface only | `addresses_for()` empty vs non-empty. Exact, no private access, matches SPEC R1's wording | ✓ |
| Three states, private cache access | Name the guard refusal by reading `_owner_is_unusable`'s inputs with `noqa: SLF001`, following the `_fallback_ip_by_instance` precedent | |
| Three states, public inference | Infer the guard refusal from absence in `pending_targets()` | |

**User's choice:** Two states, public surface only.
**Notes:** `pending_targets()` skips a target for six reasons, only one of which is a guard
refusal, so the public inference would sometimes name a refusal that did not happen. Private
access was available by precedent but would couple the probe to internals Phase 16 had just
reshaped.

### Refused-message content

| Option | Description | Selected |
|--------|-------------|----------|
| Count plus per-record classification | Name how many records were cached and classify each as the AAAA block does | ✓ |
| Count only | Record count and "none usable"; classification already appears above | |
| Bare distinction, no count | Two sentences, no numbers | |

**User's choice:** Count plus per-record classification.

### Summary block

| Option | Description | Selected |
|--------|-------------|----------|
| Split the summary counts too | Report cached-but-unusable separately from awaiting-records; the removed `linklocal_chosen` line leaves the slot | ✓ |
| Leave the summary as is | Only per-instance output changes | |
| Annotate the existing list | One list, each target marked with its state | |

**User's choice:** Split the summary counts too.
**Notes:** Without this, the summary keeps dumping `pending_targets()`, a different set from the
per-instance refused set, which would read as contradicting the per-instance view.

### Owner normalisation site

| Option | Description | Selected |
|--------|-------------|----------|
| Normalise once in `_instance_view()` | Apply `_normalise_dns_name()` where `target` is derived; every downstream lookup keys the same | ✓ |
| Normalise at each call site | Wrap `addresses_for()`, `records_for()` and `selected_address_for()` individually | |
| Drop `.lower()`, let the cache normalise | Does not satisfy AC-04, since only `selected_address_for()` normalises internally | |

**User's choice:** Normalise once in `_instance_view()`.
**Notes:** A correction was issued after this answer. The option text said
`_normalise_dns_name()` is not idempotent for multi-dot names, which was true during Phase 16
(D-02 declined to change it) but was reversed by commit `f060a90`. The helper now strips every
trailing dot and casefolds, and its docstring states idempotence is load-bearing. The choice is
unaffected; the recorded reason changed to key consistency. The correction also surfaced that the
probe's `.lower()` is redundant and slightly wrong, since the cache casefolds.

---

## Defensive reporting shape

Opened with the finding that only one of R3's three asserts can actually fire.
`_instance_view()` always places a real `list` in `"aaaa"` and a `str | None` in `"chosen"`, so
`assert isinstance(aaaa_ips, list)` and `assert isinstance(chosen, str)` are type-narrowing
appeasement for the `dict[str, object]` return type.

### View return type

| Option | Description | Selected |
|--------|-------------|----------|
| Typed structure | Dataclass or NamedTuple; both narrowing asserts vanish by construction | ✓ |
| Keep the dict, convert all three asserts | Smallest diff, but two become dead branches | |
| Keep the dict, drop the two dead asserts | Use `cast()` or `type: ignore`, convert only the TXT assert | |

**User's choice:** Typed structure.
**Notes:** Converting the two narrowing asserts into runtime branches would create the same
class of defect R2 removes three lines away, and the probe's coverage is not measured so nothing
would catch it.

### Handling location

| Option | Description | Selected |
|--------|-------------|----------|
| `_instance_view()` marks, `report_records()` renders | Keeps the assemble/print separation; marking is assertable without capturing stdout | ✓ |
| `report_records()` only | Convert the assert to an if/else at the print site | |
| `_instance_view()` skips malformed instances | Filter them out before printing | |

**User's choice:** `_instance_view()` marks, `report_records()` renders.
**Notes:** Skipping was described as the inverse of R3: a diagnostic tool dropping the instance
it was run to diagnose.

### Malformed output

| Option | Description | Selected |
|--------|-------------|----------|
| Full block, malformed fields marked | Instance keeps its header, SRV, A, AAAA and CHOSEN lines; the unusable field carries a marker | ✓ |
| Short line then continue | One line naming the instance and the malformed field | |
| Full block plus a summary tally | As the first, with a malformed count in the summary | |

**User's choice:** Full block, malformed fields marked.

### Test home

| Option | Description | Selected |
|--------|-------------|----------|
| Extend `TestSyntheticCacheReporting` | Already builds real caches through `add_packet()` and asserts on `_instance_view()` | ✓ |
| New capsys class for `report_records()` output | The only way to assert the exact message strings the SPEC names | |
| Both | View-level plus a small capsys class | |

**User's choice:** Extend `TestSyntheticCacheReporting`.

### Follow-up: reconciling the test home with AC-01 and AC-02

Raised because AC-01 and AC-02 name printed messages, which view-level assertions cannot pin.

| Option | Description | Selected |
|--------|-------------|----------|
| Add a small capsys class alongside | Keep the view-level tests and add one that pins the message strings | |
| Amend the SPEC to state-level acceptance | Rewrite AC-01 and AC-02 to assert the reported state, leaving wording free | ✓ |
| Name the messages as module constants | Pin the text without capsys, but never prove it reaches stdout | |

**User's choice:** Amend the SPEC to state-level acceptance.
**Notes:** Became SPEC amendment A1.

### Follow-up: AC-08's "run completes" clause

Raised because AC-08 differs in kind from AC-01 and AC-02. Its "run completes" clause is R3's
reason for existing, and no view-level assertion covers it.

| Option | Description | Selected |
|--------|-------------|----------|
| Keep one smoke test that calls it | AC-01 and AC-02 state-level; AC-08 keeps a `report_records()` call asserting normal return | ✓ |
| State-level for all three | Smallest test surface; a future abort inside `report_records()` goes uncaught | |
| Smoke test plus the two message constants | The smoke test, and the messages pinned as constants | |

**User's choice:** Keep one smoke test that calls it.
**Notes:** Folded into SPEC amendment A1.

---

## Evidence layout and pseudonyms

Opened with a scouting finding that changed the shape of the problem.
`_load_target_alias_map()` (thread_revalidation.py:3070) already reads the mapping from outside
the repository into memory only, citing `measure_merged_discovery.py` as precedent, so DISC-04's
evidence is pseudonymised by construction. The manual burden falls entirely on the probe
transcript.

### Keep the SPEC's hand-pseudonymisation decision

| Option | Description | Selected |
|--------|-------------|----------|
| Keep hand-pseudonymisation | The SPEC decision stands; one transcript, substituted by hand | |
| Amend: reuse the alias-map loader | Give the probe an `--alias-map` flag calling the same loader shape | ✓ |
| Hand-pseudonymise now, note the flag as deferred | Manual this phase, flag later | |

**User's choice:** Amend to reuse the alias-map loader.
**Notes:** Became SPEC amendment A2. The spec-phase decision had been made without knowing the
precedent was two scripts deep.

### Follow-up: addresses

Raised because the alias map is serial-keyed but the transcript also carries A, AAAA and
packet-source addresses, which AC-22 forbids.

| Option | Description | Selected |
|--------|-------------|----------|
| Deterministic class-preserving substitution | Rewrite to documentation-range equivalents of the same class, stably per run | ✓ |
| Second map file for addresses | Operator-controlled and exact, but drifts when DHCP moves a device | |
| Suppress addresses entirely | Nothing to substitute, but the transcript cannot show two AAAA records differing | |

**User's choice:** Deterministic class-preserving substitution.

### Follow-up: serials inside names

| Option | Description | Selected |
|--------|-------------|----------|
| Substring replace across the whole line | Covers instance names and SRV hostnames without knowing each field's format | ✓ |
| Per-field structured substitution | Cleaner output; any new serial-bearing field leaks until someone adds it | |
| Substring replace plus a residue check | As the first, with the probe refusing to write serial-shaped residue | |

**User's choice:** Substring replace across the whole line.

### Follow-up: gating

| Option | Description | Selected |
|--------|-------------|----------|
| Opt-in flag, raw by default | Matches how the two sibling scripts already work | ✓ |
| Fail-closed when writing to a file | Structurally safer, but the probe cannot reliably detect a redirect everywhere | |
| Always redact | Zero leak surface, destroys the probe's diagnostic value | |

**User's choice:** Opt-in flag, raw by default.

### Evidence naming

| Option | Description | Selected |
|--------|-------------|----------|
| Mirror Phase 14 exactly | `17-MANIFEST.json`, `17-STALENESS.jsonl`, `session_id` `"seed-002"` | ✓ |
| Name it for the control | `17-WIFI-STALENESS.jsonl`, `session_id` `"disc-04-wifi"` | |
| Full Phase 14 file set | Every file even where empty | |

**User's choice:** Mirror Phase 14 exactly.

### Finding home

| Option | Description | Selected |
|--------|-------------|----------|
| Its own document | `17-STALENESS-CONTROL.md`, following the `15-TEST-02-EVIDENCE.md` precedent | ✓ |
| A section of the phase SUMMARY | Fewer files, harder to cite | |
| Document plus a `docs/` excerpt | Two homes, one source | |

**User's choice:** Its own document.

### Transcript form

| Option | Description | Selected |
|--------|-------------|----------|
| Markdown wrapper around fenced output | Run date, revision, invocation, which messages appeared, then redacted stdout | ✓ |
| Plain `.txt` of stdout | Smallest; AC-11's narration then lives elsewhere | |
| Both | Raw `.txt` plus narration in the finding | |

**User's choice:** Markdown wrapper around fenced output.

---

## Docs home for the liveness note

Constraints surfaced before questioning: `test_phase_contract.py:121` locks 16 approved phrases
on `discovery.md`, `:373` forbids private-looking IPv4 literals, and `:147` only forbids
"faster/fastest" near "mdns", so numeric figures are permitted.

### Placement

| Option | Description | Selected |
|--------|-------------|----------|
| Extend the Limitations proxy paragraph | The measurement sits next to the claim it quantifies | ✓ |
| New section in `discovery.md` | More room, splits claim from quantification | |
| New page under User Guide | Most room, a fifteenth nav entry, missed by Limitations readers | |

**User's choice:** Extend the Limitations proxy paragraph.

### Figures

| Option | Description | Selected |
|--------|-------------|----------|
| Exact values with resolutions | 4140 to 4200 s, 69.4 s, the WiFi values, each with its resolution | ✓ |
| Rounded and qualified | "over an hour", "about a minute" | |
| A small comparison table | Clearest comparison, heavier than surrounding prose | |

**User's choice:** Exact values with resolutions.
**Notes:** The disclaimer paragraph directly below already forbids sizing timeouts from the
documentation, so precision does not become the guarantee prohibition P1 forbids.

### Contract lock

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, short fragments | Two or three fragments added to the existing tuple, per Phase 16 D-16 | ✓ |
| No lock | Lighter; Phase 20 could recast the claim away with nothing failing | |
| Lock plus a negative | Fragments, and a forbidden phrase making prohibition P1 mechanical | |

**User's choice:** Yes, short fragments.

### Troubleshooting cross-reference

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, a cross-referenced entry | Short entry in `troubleshooting.md` linking to the discovery.md paragraph | ✓ |
| `discovery.md` only | One home, missed by symptom searchers | |
| Both, fully stated | Two homes for the same figures, which the Phase 14 linking contract prevents | |

**User's choice:** Yes, a cross-referenced entry.

---

## Hardware gating and wave shape

Added after the four originally selected areas, at the user's request.

### Wave shape

| Option | Description | Selected |
|--------|-------------|----------|
| Three waves on the hardware boundary | Code and tests, then both hardware runs in one sitting, then the numbers-dependent prose | ✓ |
| Two waves | All code, then everything hardware and prose | |
| Split by requirement | Eight plans; separates the two hardware runs despite being one sitting | |

**User's choice:** Three waves on the hardware boundary.

### If the WiFi run cannot happen

| Option | Description | Selected |
|--------|-------------|----------|
| MDNS-10 ships, DISC-04 stays open | Probe work is self-contained; DISC-04 carries forward | ✓ |
| Named gap, phase closes | Mirrors Phase 14's `named_gap`, risks laundering an unrun experiment | |
| Whole phase blocks | Atomic, but holds three finished fixes hostage to an unplug cycle | |

**User's choice:** MDNS-10 ships, DISC-04 stays open.

### Docs ordering

| Option | Description | Selected |
|--------|-------------|----------|
| No, docs wait for the numbers | One commit, one complete claim, one lock edit | ✓ |
| Land Thread-only, amend after | Documents a real hazard sooner, two commits and two lock edits | |
| Draft in the plan, commit after | Prose authored during planning with placeholders | |

**User's choice:** No, docs wait for the numbers.

### `--alias-map` commit and tests

| Option | Description | Selected |
|--------|-------------|----------|
| Own commit, own tests | Independent bisect story from the three diagnostic fixes | ✓ |
| Folded into the probe fix commit | Fewer commits, a revert of one takes the other | |
| Own commit, tested only through the transcript run | Substitution logic unproven until run against live identifiers | |

**User's choice:** Own commit, own tests.

---

## Claude's Discretion

- The exact wording of the two new probe messages and the malformed-field marker.
- Whether the typed view structure is a `dataclass` or a `NamedTuple`, and its field names.
- The `--alias-map` implementation seam, and whether address substitution is a helper function
  or a small class.
- The exact prose of the `discovery.md` extension and the `troubleshooting.md` entry.
- Which two or three fragments the approved-phrase lock adds.
- Commit ordering within each wave, subject to the `--alias-map` separation.

## Deferred Ideas

- Naming the guard-refusal state, if the cache ever grows a public predicate for it.
- `--alias-map` on `serial_mac_audit.py`, the one measurement script that would still lack one.
- Repeated WiFi trials, or repeated Thread trials, to bound variance on the lease question.
- Reading the granted lease directly with `ot-ctl srp server service`, impractical while the
  OTBR runs inside a Home Assistant add-on container.
- Refreshing `.planning/codebase/` maps, carried forward from Phase 16.

## Corrections issued during this discussion

- `_normalise_dns_name()` was described as non-idempotent. Commit `f060a90` reversed Phase 16
  D-02; the helper now strips every trailing dot and casefolds. The affected decision was
  unchanged, its recorded reason was not.
