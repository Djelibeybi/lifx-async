# Phase 17: Fleet Diagnostics and the Staleness Control - Research

**Researched:** 2026-09-08
**Domain:** Operator-tooling diagnostics (`.planning/scripts/`) for an mDNS/Thread discovery probe, plus a hardware staleness-measurement CLI. No `src/lifx/` library changes.
**Confidence:** HIGH (every claim below was verified by reading the actual source this session; no library behaviour was assumed)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

D-01 through D-22 in `17-CONTEXT.md` are locked. Key ones a plan must honour verbatim:

- **D-01:** Two states only, read from the cache's public surface (`addresses_for()` empty vs. non-empty-with-no-selection). The third state (`_owner_is_unusable()` guard refusal) is deliberately left unnamed — do not infer it from `pending_targets()` absence, and do not add private access beyond the existing `# noqa: SLF001` precedent at `ipv6_thread_probe.py:357`.
- **D-02:** The refused message names the record count and classifies each record the way the AAAA block already does (reuse `classify_address()`).
- **D-03:** The summary block splits cached-but-unusable from awaiting-records; do not keep dumping `pending_targets()` as the sole "unresolved" count.
- **D-04:** Owner normalisation happens once, in `_instance_view()`, using `_normalise_dns_name()` (not `.lower()`). This helper is **not currently imported** by the probe — it must be added to the import list from `lifx.network.discovery.mdns.discovery`.
- **D-05:** `_instance_view()` returns a typed structure (dataclass or NamedTuple), not `list[tuple[str, dict[str, object]]]`. Reversibility is "costly": every consumer, including the existing `TestSyntheticCacheReporting` assertions (which use `view["addresses"]`, `view["chosen"]`, `view["fallback"]` dict-subscript access), must migrate to attribute access in the same change.
- **D-06:** `_instance_view()` marks which fields were unusable; `report_records()` renders the marking. Keep the assemble/print separation.
- **D-07:** A malformed instance still prints its full block; only the unusable field carries a marker. Never skip the instance.
- **D-08:** R1/R3 tests extend `TestSyntheticCacheReporting` (view-level assertions). Exactly one `report_records()` smoke test (for AC-08's "run completes" clause) asserts no message text.
- **D-09 through D-12:** `--alias-map` is a new, opt-in, separately-committed flag with its own tests, reusing `_load_target_alias_map()`'s shape (`thread_revalidation.py:3070`) for serials and a new class-preserving address substitution for A/AAAA/fallback addresses. Whole-line substring replace for serials (covers mDNS instance names and SRV hostnames).
- **D-13:** WiFi evidence mirrors Phase 14's file *names* exactly (see Common Pitfalls — the tool hardcodes these names regardless of directory), with `session_id` `"seed-002"`.
- **D-14:** The verdict lives in its own document, `17-EVIDENCE/17-STALENESS-CONTROL.md`, following the `15-TEST-02-EVIDENCE.md` precedent shape.
- **D-15:** The probe transcript is `17-EVIDENCE/17-PROBE-TRANSCRIPT.md` (run date, git revision, invocation, which new messages appeared/did not, then redacted stdout in a fenced block).
- **D-16 through D-19:** Docs extend the existing Limitations proxy paragraph in `docs/user-guide/discovery.md` (do not create a new section/page); exact figures with resolutions; 2-3 new fragments added to the `approved_phrases` tuple at `tests/test_network/test_mdns/test_phase_contract.py:124`; a short cross-referenced (not restated) entry in `troubleshooting.md`.
- **D-20:** Three waves split on the hardware boundary — Wave 1 (no hardware: three fixes + typed view + `--alias-map` + tests), Wave 2 (hardware, one sitting: Thread-fleet probe transcript + WiFi staleness trial), Wave 3 (numbers-dependent: finding doc, ROADMAP/REQUIREMENTS correction, both docs surfaces).
- **D-21:** If the WiFi run cannot happen, MDNS-10 still ships; DISC-04 stays open (not a `named_gap`, not a blocked phase).
- **D-22:** No documentation lands before the WiFi numbers exist — one commit, one complete claim, one lock edit.

### Claude's Discretion

- Exact wording of the two new probe messages and the malformed-field marker (subject to D-01, D-02, D-07).
- `dataclass` vs `NamedTuple` for the typed view structure, and its field names.
- Name of the `--alias-map` implementation seam; whether address substitution is a function or small class.
- Exact prose of the `discovery.md` extension and `troubleshooting.md` entry (subject to D-16 through D-19, SPEC prohibition P1, no em dash).
- Which 2-3 fragments the approved-phrase lock adds.
- Commit ordering within each wave (subject to D-12's separate-commit rule).

### Deferred Ideas (OUT OF SCOPE)

- Naming the guard-refusal state (if the cache ever grows a public predicate for it).
- `--alias-map` on `serial_mac_audit.py` (the one measurement script that would still lack one).
- Repeated WiFi or Thread trials to bound variance on the SRP lease question.
- Reading the granted lease directly via `ot-ctl srp server service` (impractical inside the Home Assistant OTBR add-on).
- Refreshing `.planning/codebase/` maps (carried from Phase 16; TESTING.md/CONVENTIONS.md predate Phase 15's delivered mechanisms — trust `pyproject.toml`/`AGENTS.md` over the maps).

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| MDNS-10 | The IPv6 Thread probe distinguishes an instance with no address data from one holding a cached-but-unusable unscoped link-local AAAA record; `linklocal_chosen`/`is_reachable_choice()` made truthful/reachable or removed; the TXT assertion becomes defensive handling. | See "The probe source: exact defect sites" and "Common Pitfalls" below — every line number for the three defects, and the `is_reachable_choice()` grep-vs-live-call-sites contradiction the planner must resolve. |
| DISC-04 | Advertisement staleness measured against a WiFi bulb with THREAD-04's identical protocol, producing a comparable figure and a verdict on whether the Thread figure is Thread-specific. | See "The THREAD-04 protocol and its exact reproduction" — command, manifest/roster shape, schema fields, and the filename-mismatch pitfall for the `17-EVIDENCE/` naming. |

</phase_requirements>

## Project Constraints (from CLAUDE.md / AGENTS.md)

These bind every task in this phase's plan:

- Australian English spelling throughout all new prose (global CLAUDE.md).
- Use the latest version when adding a dependency — not applicable this phase; no new dependency is installed anywhere (script or library).
- `git commit -S -s` (GPG-signed, DCO sign-off) for every commit (global CLAUDE.md + `AGENTS.md`).
- Conventional Commit messages; never use a GSD phase/plan number as the commit scope (e.g. not `fix(17): ...` — use a repository-component scope such as `fix(probe): ...`, `docs(discovery): ...`, or omit the scope) (`AGENTS.md` "Git Commits").
- Privacy: no live serial, MAC, IP address or hostname in any committed artefact from either hardware run; format-preserving pseudonyms only, inspected in the staged diff before each commit (`AGENTS.md` "Privacy and Hardware Identifiers"; `REQUIREMENTS.md` Out of Scope table).
- Measured tree: `.planning/scripts/` is **not** measured by coverage; only `--cov=lifx` and `--cov=generate_theme_data` count. Nothing in Wave 1 or Wave 2 changes the coverage denominator (`AGENTS.md` "Measured Tree"; confirmed at `pyproject.toml:153-154`).
- `.planning/**` is per-file-ignored for ruff `PLC0415` (`pyproject.toml:99`), so the probe's existing function-local imports (e.g. inside `_create_device_from_record()`) are not this phase's problem.
- No em dash in any new prose this phase adds (project-wide house style; DOCS-09/Phase 20 owns the pre-existing sweep — do not touch existing em dashes in `docs/user-guide/discovery.md`).
- Never update `docs/changelog.md` manually (generated by the release workflow).
- If a field is user-visible it must never be `bytes` — not directly relevant here (no new user-visible fields), but the alias-map's serial substitution must stay string-based throughout.

## Summary

This phase has two independent halves that share one hardware sitting (Wave 2). MDNS-10 is a
pure code-and-test change confined to one file, `.planning/scripts/ipv6_thread_probe.py`, with
its three defects at precisely known lines. DISC-04 is a single invocation of an existing,
unmodified CLI (`thread_revalidation.py staleness`) against a WiFi bulb, using a tool that
already implements the exact THREAD-04 protocol; the work is authoring a WiFi roster/alias map
and running the command, not writing new code.

The single most important finding for planning is a **discrepancy between `17-CONTEXT.md` D-13
and the actual tool behaviour**: `thread_revalidation.py`'s evidence filenames
(`_MANIFEST_FILENAME`, `STALENESS_FILENAME`, etc.) are hardcoded module-level constants —
literally `"14-MANIFEST.json"` and `"14-STALENESS.jsonl"` — regardless of the `--session-dir`
passed on the command line. D-13's plan to produce `17-EVIDENCE/17-MANIFEST.json` and
`17-EVIDENCE/17-STALENESS.jsonl` is **not what the unmodified tool writes**. A plan must decide
how to reconcile this (see Common Pitfalls, Pitfall 1) before Wave 2 begins, because renaming
the files after the fact breaks the tool's own idempotency check (AC-15) on any resumed run.

A second load-bearing finding: `thread_revalidation.py validate-staged` (the automated
staged-evidence checker) hardcodes an expectation of **all nine** Phase-14 session files
(manifest + five journals + summary + class-ledger + report). A staleness-only WiFi trial never
produces `14-DISCOVERY.jsonl`, `14-REQUESTS.jsonl`, `14-ANIMATION.jsonl`, `14-CLOSURE.jsonl`,
`14-SUMMARY.json`, `14-CLASS-LEDGER.json` or `14-REPORT.md`, so this checker **cannot be used**
to validate DISC-04's evidence. The only gate available for R8's privacy requirement over this
artefact is the manual staged-diff inspection the SPEC's own edge-coverage table already
names as a "backstop... cannot be a committed test."

A third finding directly affects MDNS-10's grep-based acceptance criterion: `is_reachable_choice()`
has **three** call sites, not one. Only the call at `ipv6_thread_probe.py:500` (inside
`report_records()`) is the unreachable branch R2 targets. The other two, at line 598
(`stage_connect()`) and line 695 (`_select_target()`), are live, tested (`_select_target`'s is
covered by an existing test), and unrelated to the removed counter. AC's literal
`grep -n 'linklocal_chosen\|is_reachable_choice' ipv6_thread_probe.py` returning nothing therefore
requires renaming the helper (updating both surviving call sites to the new name) rather than
conditionally deleting it — R2's prose ("deleted... if nothing else calls it") under-describes
what the AC actually demands.

**Primary recommendation:** Treat Wave 1 as five small, code-verified edits to one file (plus
its typed-view test migration and a new `--alias-map` commit); treat Wave 2 as running two
already-correct CLIs and writing down exactly what filenames they actually produced (not what
D-13 assumed); treat Wave 3 as prose-only, gated behind Wave 2's real numbers.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| mDNS record cache / address selection (`_LifxRecordCache`, `selected_address_for()`, `_pick_address()`) | Library (`src/lifx/network/discovery/mdns/discovery.py`) | — | Settled by Phase 16 (MDNS-09); this phase reads it, never edits it |
| Probe reporting (`_instance_view()`, `report_records()`) | Operator tooling (`.planning/scripts/`) | — | Diagnostic consumer of the private cache API; outside the measured tree by Phase 15's CI-01 reversal |
| Probe redaction (`--alias-map`) | Operator tooling | — | Mirrors `thread_revalidation.py`/`measure_merged_discovery.py`'s existing alias-map precedent |
| WiFi staleness experiment (`run_staleness_experiment()`, `_cli_staleness()`) | Operator tooling | — | Unmodified; this phase is a consumer, not an author, of this code path |
| Evidence artefacts (`17-EVIDENCE/*`) | Filesystem / git-tracked evidence | — | Produced by the operator-tooling tier, committed as data, never re-derived by library code |
| Consumer-facing liveness prose | Documentation (`docs/user-guide/`) | Test contract (`test_phase_contract.py`) | Gated by an approved-phrase lock, not by runtime code |

## Standard Stack

No new runtime or dev dependency is added anywhere in this phase. Every symbol used is either
already imported by `ipv6_thread_probe.py` / `thread_revalidation.py`, or is one additional
stdlib-only import (`_normalise_dns_name` from the already-imported `lifx.network.discovery.mdns.discovery`
module).

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| (none new) | — | — | Both scripts are PEP 723 standalone scripts (`requires-python = ">=3.10"`, `dependencies = ["lifx-async"]`) already declaring everything they need |

### Alternatives Considered

Not applicable — no library or dependency choice is open in this phase.

**Installation:** none required.

## Package Legitimacy Audit

**Not applicable.** This phase installs no new packages in any ecosystem. `[VERIFIED: .planning/scripts/ipv6_thread_probe.py:1-8, .planning/scripts/thread_revalidation.py header]` — both scripts' PEP 723 headers list only `lifx-async` as a dependency, unchanged by this phase's scope.

## Architecture Patterns

### System Architecture Diagram — probe reporting path (MDNS-10)

```
mDNS UDP packets
      │
      ▼
sweep()  ── parses via parse_dns_response() ──▶ cache.add_packet()
      │                                              │
      │                                              ▼
      │                                     _LifxRecordCache (private,
      │                                     imported by the probe)
      │                                              │
      ▼                                              │
result: SweepResult(cache, ...)                       │
      │                                              │
      ▼                                              ▼
_instance_view(cache)  ──── for each TXT owner ────▶ cache.addresses_for(target)
      │                                              cache.selected_address_for(target)
      │  (D-04: normalise `target` ONCE here,        (already normalises internally,
      │   via _normalise_dns_name — not `.lower()`)   MDNS-09/Phase 16)
      ▼
typed view (D-05: dataclass/NamedTuple, not dict)
      │  marks which fields are malformed (D-06)
      ▼
report_records(result)  ── renders the marking, prints per-instance block (D-07)
      │
      ▼
stdout  ── optionally rewritten by --alias-map (D-09..D-12) before it reaches
            the committed 17-PROBE-TRANSCRIPT.md
```

### System Architecture Diagram — WiFi staleness control (DISC-04)

```
operator                     thread_revalidation.py                 evidence dir
   │                                  │                                   │
   ├─ author WiFi roster JSON ───────▶│                                   │
   │  (Light/MultiZoneLight/          │  init: validate_expected_roster() │
   │   2×MatrixLight/CeilingLight)    │        (unchanged gate; a WiFi    │
   │                                  │        roster satisfies it)      │
   │                                  ├─ init_manifest() ────────────────▶ 14-MANIFEST.json
   │                                  │  (hardcoded filename — see        (inside whatever
   │                                  │   Pitfall 1)                      --session-dir was
   │                                  │                                   given)
   ├─ author --alias-map (outside ───▶│
   │  the repo; WiFi serial→alias)    │
   │                                  │
   ├─ run staleness --power-off/on ──▶│  run_staleness_experiment()
   │  (same 60s cadence, 3-poll        │  (UNCHANGED from THREAD-04:
   │   confirm, 3h cap as Thread)      │   identical function, no new
   │                                  │   code path for WiFi)
   │                                  ├─ append_staleness_event() ───────▶ 14-STALENESS.jsonl
   │                                  │                                   (same hardcoded name)
   │                                  ▼
   │                       JSON verdict on stdout:
   │                       disposition, first_absence_poll,
   │                       confirmed_expiry_poll, restoration_duration_s
   │
   ├─ redact + commit 14-MANIFEST.json, 14-STALENESS.jsonl into
   │  17-EVIDENCE/ (operator inspects staged diff; validate-staged
   │  CANNOT check this — see Pitfall 2)
   │
   └─ write 17-EVIDENCE/17-STALENESS-CONTROL.md (Wave 3, numbers-gated)
```

### Recommended Project Structure

No new directories. The phase writes into the existing tree:

```
.planning/scripts/
├── ipv6_thread_probe.py         # Wave 1: three fixes + typed view + --alias-map
├── thread_revalidation.py       # Read-only this phase (staleness path unmodified)
├── measurement_support.py       # Read-only (already shared by both scripts)
└── tests/
    └── test_ipv6_thread_probe.py   # Wave 1: new tests extend TestSyntheticCacheReporting

.planning/phases/17-fleet-diagnostics-and-the-staleness-control/
├── 17-EVIDENCE/
│   ├── 14-MANIFEST.json         # Wave 2: hardcoded name, see Pitfall 1
│   ├── 14-STALENESS.jsonl       # Wave 2: hardcoded name, see Pitfall 1
│   ├── 17-PROBE-TRANSCRIPT.md   # Wave 2: D-15 wrapper around redacted stdout
│   └── 17-STALENESS-CONTROL.md  # Wave 3: D-14 verdict document
└── 17-RESEARCH.md               # this file

docs/user-guide/
├── discovery.md                 # Wave 3: extend the existing Limitations paragraph
└── troubleshooting.md           # Wave 3: short cross-referenced entry

tests/test_network/test_mdns/
└── test_phase_contract.py       # Wave 3: extend approved_phrases tuple (line 124)

.planning/ROADMAP.md              # Wave 3: correct the conflated 69s figure
.planning/REQUIREMENTS.md         # Wave 3: correct DISC-04's entry
```

### Pattern 1: Typed reporting structure replacing an untyped dict

**What:** `_instance_view()` currently returns
`list[tuple[str, dict[str, object]]]` [VERIFIED: .planning/scripts/ipv6_thread_probe.py:355] —
quote: `def _instance_view(cache: _LifxRecordCache) -> list[tuple[str, dict[str, object]]]:`.
D-05 requires a dataclass or NamedTuple instead.

**When to use:** Any time a private reporting seam needs `isinstance` narrowing today purely
because its return type is untyped — the narrowing asserts are a symptom of the dict, not a
runtime guard. The repository already has this exact pattern for other reporting shapes:
`TargetOutcome` (`ipv6_thread_probe.py:656-668`) and `CapturedState` (`measurement_support.py:577-595`)
are both plain dataclasses with concrete field types, no defensive `isinstance` needed by their
consumers.

**Example — the existing repo precedent to follow:**
```python
# Source: .planning/scripts/ipv6_thread_probe.py:656-668 [VERIFIED]
@dataclass
class TargetOutcome:
    """Per-stage results for the named target.
    ...
    """
    connect: str = STAGE_NOT_RUN
    control: str = STAGE_NOT_RUN
    streaming: str = STAGE_NOT_RUN
    restored: bool = True
```

### Pattern 2: Reusing the existing alias-map loader shape (D-09)

**What:** `_load_target_alias_map()` [VERIFIED: .planning/scripts/thread_revalidation.py:3070-3087]
already reads an external JSON file, normalises each key through `Serial.from_string(...).to_string()`,
validates each value through `validate_alias()`, and rejects duplicate normalised serials — entirely
in memory, never touching tracked evidence.

**When to use:** For the probe's new `--alias-map` flag. Do not re-derive serial normalisation or
alias-grammar validation; import and call the same helper (or a probe-local copy with an identical
contract) rather than inventing a second validator.

**Example:**
```python
# Source: .planning/scripts/thread_revalidation.py:3070-3087 [VERIFIED]
def _load_target_alias_map(path: Path) -> dict[str, str]:
    """Load an external raw-serial-to-alias mapping only into memory (D-19).

    Mirrors .planning/scripts/measure_merged_discovery.py's alias-map precedent:
    the file lives outside the repository, is read once into memory, and
    its raw identities never reach any tracked evidence.
    """
    value = json.loads(path.expanduser().resolve().read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not value:
        raise ValueError("alias map must be a non-empty JSON object")
    aliases: dict[str, str] = {}
    for raw_serial, raw_alias in value.items():
        serial = Serial.from_string(raw_serial).to_string()
        alias = validate_alias(raw_alias)
        if serial in aliases:
            raise ValueError("alias map contains a duplicate normalised serial")
        aliases[serial] = alias
    return aliases
```

### Anti-Patterns to Avoid

- **Converting the two type-narrowing asserts (`aaaa_ips`, `chosen`) into runtime `if`/`else`
  branches instead of typing the structure:** creates an unreachable branch that nothing
  measures (the probe is outside the coverage tree), which is exactly the class of defect R2
  removes three lines away. D-05 explicitly rejects this option.
- **Renaming or deleting `is_reachable_choice()` without checking every call site:** it is called
  three times, not once (`ipv6_thread_probe.py:500,598,695`). Deleting the function breaks
  `stage_connect()` and `_select_target()`. See Common Pitfalls, Pitfall 3.
- **Assuming the WiFi evidence files will be named `17-MANIFEST.json`/`17-STALENESS.jsonl`:**
  they will not, unless the plan explicitly copies/renames them post-write and accepts the
  idempotency consequence. See Common Pitfalls, Pitfall 1.
- **Running `thread_revalidation.py validate-staged` against the WiFi evidence directory and
  treating a failure as informative:** it will always fail (missing discovery/request/animation/
  closure/summary/ledger/report files), because it is scoped to a complete six-class session, not
  a staleness-only trial. See Common Pitfalls, Pitfall 2.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Serial-to-alias redaction | A new alias-loading/validation routine for the probe | `_load_target_alias_map()`'s exact contract (`thread_revalidation.py:3070`) | Already handles serial normalisation, alias grammar, duplicate rejection, and keeps the raw mapping outside the repo — re-deriving it risks a subtly different validation surface |
| Address classification for the refused-message count (D-02) and for address substitution (D-11) | A second IPv6/IPv4 classifier | `classify_address()` (`ipv6_thread_probe.py:172-186`) | Already returns exactly the class labels (`IPv4`, `link-local`, `ULA`, `GUA`, `IPv6-other`, `invalid`) both D-02 and D-11 need |
| WiFi staleness measurement protocol | A new WiFi-specific poll loop | `run_staleness_experiment()` (`thread_revalidation.py:2241-2416`), invoked unchanged via `_cli_staleness()` | It already implements the exact 60s absolute cadence, 3-poll confirmation, 3h cap, and unbounded restoration-wait THREAD-04 used; SPEC explicitly forbids changing it |
| Roster completeness gate for the WiFi session | A relaxed or WiFi-specific roster check | `validate_expected_roster()` (`thread_revalidation.py:1753-1777`), unchanged | SPEC forbids changing it; the production WiFi fleet already satisfies all four required classes |
| Typed reporting fields | A hand-rolled `TypedDict` requiring the same `isinstance` narrowing the dict already needed | `dataclass` or `NamedTuple`, per D-05 | Removes the narrowing requirement by construction rather than papering over it |

**Key insight:** Every non-trivial primitive this phase needs (alias loading, address
classification, staleness protocol, roster gating) already exists in this repository, proven
against real hardware in Phase 14/16. The work is composition and defect-fixing, not new
algorithm design.

## Common Pitfalls

### Pitfall 1: The WiFi evidence filenames will not be `17-MANIFEST.json`/`17-STALENESS.jsonl`

**What goes wrong:** `17-CONTEXT.md` D-13 states the WiFi session "mirrors Phase 14 exactly:
`17-EVIDENCE/17-MANIFEST.json` and `17-EVIDENCE/17-STALENESS.jsonl`". The actual tool does not
parameterise these names by session or phase at all.

[VERIFIED: .planning/scripts/thread_revalidation.py:310-321] — quote:
```
_MANIFEST_SCHEMA_VERSION = 1
_MANIFEST_KIND = "session_manifest"
_MANIFEST_FILENAME = "14-MANIFEST.json"

DISCOVERY_FILENAME = "14-DISCOVERY.jsonl"
REQUESTS_FILENAME = "14-REQUESTS.jsonl"
ANIMATION_FILENAME = "14-ANIMATION.jsonl"
STALENESS_FILENAME = "14-STALENESS.jsonl"
CLOSURE_FILENAME = "14-CLOSURE.jsonl"
SUMMARY_FILENAME = "14-SUMMARY.json"
CLASS_LEDGER_FILENAME = "14-CLASS-LEDGER.json"
REPORT_FILENAME = "14-REPORT.md"
```
These are literal module-level string constants used verbatim as `session_dir / _MANIFEST_FILENAME`
[VERIFIED: .planning/scripts/thread_revalidation.py:507-509] and `session_dir / STALENESS_FILENAME`
[VERIFIED: .planning/scripts/thread_revalidation.py:2295, 3447]. Pointing `--session-dir` at
`.planning/phases/17-.../17-EVIDENCE/` produces files literally named `14-MANIFEST.json` and
`14-STALENESS.jsonl` **inside** a `17-EVIDENCE/` directory — a "14-" prefix on the file, a "17-"
prefix on the directory.

**Why it happens:** These constants were written once, for Phase 14, and never made
session-relative. R5's target text ("using the frozen 60s...cap unchanged") and Out-of-Scope list
("Changes to `validate_expected_roster()` or `STALENESS_CAP_S`") do not mention the filename
constants at all — they were not in view when the constraint was written, and D-13 was drafted
from the CONTEXT session's assumption that "mirror Phase 14" meant a phase-relative rename.

**How to avoid:** Do not rename the files after they are written. `reload_staleness_events()`
[VERIFIED: .planning/scripts/thread_revalidation.py:2300-2304] and `_cli_staleness()`'s own
same-alias-resume check [VERIFIED: .planning/scripts/thread_revalidation.py:3445-3463] both look
for the row by loading `args.session_dir / STALENESS_FILENAME` — i.e. they look for a file
literally named `14-STALENESS.jsonl`, not `17-STALENESS.jsonl`. Renaming the committed file
between the tool run and the commit would make any resumed/repeated invocation treat the alias as
never-recorded, satisfy neither AC-15 (same-alias rerun records nothing) nor the prohibition
against re-running the power cycle. The plan should either:
1. Accept the tool's real names (`14-MANIFEST.json`, `14-STALENESS.jsonl`) inside `17-EVIDENCE/`,
   documenting the mismatch explicitly in `17-STALENESS-CONTROL.md` rather than silently
   contradicting D-13, or
2. Explicitly scope a small, separately-reasoned change to `thread_revalidation.py`'s filename
   constants (turning them phase/session-relative) — outside SPEC's stated scope and Out-of-Scope
   list, so this would need a discretion call or a SPEC amendment, not a silent code change.
Recommendation: option 1. It requires zero code changes to an "unchanged" tool (matching R5's
target wording) and the acceptance criteria (R5, AC-13/14/15/16) never actually require the
phase-numbered filename — only D-13's prose does.

**Warning signs:** A plan task that says "the tool writes `17-MANIFEST.json`" without a citation
to a source line; a task that includes a `mv`/rename step for the evidence files before commit.

### Pitfall 2: `thread_revalidation.py validate-staged` cannot validate a staleness-only session

**What goes wrong:** SPEC's edge-coverage table (row "ordering / R8") already flags that
substitution-order double-substitution is a "held-out check... cannot be a committed test." A
plan might still reach for `thread_revalidation.py validate-staged --evidence-dir 17-EVIDENCE/`
expecting it to be a usable automated gate for R8/AC-23's pseudonymisation requirement over the
WiFi evidence. It is not, for a different reason: it demands nine specific files, not two.

[VERIFIED: .planning/scripts/thread_revalidation.py:2648-2658] — quote:
```
_EVIDENCE_FILENAMES: tuple[str, ...] = (
    _MANIFEST_FILENAME,
    DISCOVERY_FILENAME,
    REQUESTS_FILENAME,
    ANIMATION_FILENAME,
    STALENESS_FILENAME,
    CLOSURE_FILENAME,
    SUMMARY_FILENAME,
    CLASS_LEDGER_FILENAME,
    REPORT_FILENAME,
)
```
and `validate_staged_evidence()` [VERIFIED: .planning/scripts/thread_revalidation.py:2707-2736]
reports `missing_evidence_path` for every one of the nine not present in the staged diff,
returning early before reading any blob content.

**Why it happens:** `validate-staged` was built as the Phase 14 six-class-closure gate (THREAD-01
through THREAD-05 all completed in one session). DISC-04's scope is explicitly narrower — SPEC
Out-of-Scope: "Repeated WiFi trials or additional device classes... one trial mirrors THREAD-04's
design" — no discovery/request/animation rounds, no closure ledger, no `generate` step.

**How to avoid:** Do not add `thread_revalidation.py validate-staged` to any `<automated>` verify
step for R5/R8's evidence. Rely on the manual staged-diff inspection the prohibition list already
names as authoritative ("MUST NOT commit before the operator has inspected the staged diff against
the private mapping" — resolved as `judgment`, not `test`, in SPEC's own prohibitions table). A
plan-level `<automated>` grep for IPv4/IPv6/serial-shaped literals in the staged diff (mirroring
`test_phase_contract.py:373`'s private-IPv4 pattern approach, or reusing
`measurement_support.py`'s `_string_exposes_identity()`/`contains_forbidden_value()` helpers as a
standalone script) is a reasonable automated backstop *in addition to* the manual check, but is
not what `validate-staged` already provides for this artefact shape.

**Warning signs:** A plan task whose verify command is
`thread_revalidation.py validate-staged --evidence-dir .../17-EVIDENCE` for the WiFi trial alone —
this will fail even on a perfectly correct staleness-only run.

### Pitfall 3: `is_reachable_choice()` has three call sites; the AC demands the string vanish entirely

**What goes wrong:** R2's descriptive text says "`is_reachable_choice()` is deleted with them if
nothing else calls it," which reads as conditional. The acceptance criterion is unconditional:

[VERIFIED: 17-SPEC.md Acceptance Criteria] — quote: `` `grep -n 'linklocal_chosen\|is_reachable_choice' .planning/scripts/ipv6_thread_probe.py` returns nothing ``.

[VERIFIED: .planning/scripts/ipv6_thread_probe.py:189,500,598,695] — the function is called at:
- line 500, inside `report_records()` — this is the R2-unreachable branch (`chosen` can no longer
  be an unscoped link-local address at this point, because `_pick_address()` already rejects it —
  Phase 16).
- line 598, inside `stage_connect()`:
  `if not is_reachable_choice(record.ip):` — a live branch over a resolved `_LifxServiceRecord.ip`,
  which *can* still be a packet-source-fallback address; not proven unreachable by Phase 16.
- line 695, inside `_select_target()`:
  `if not is_reachable_choice(record.ip):` — also live, and directly covered by an existing test,
  `TestSelectTarget::test_returns_not_found_for_a_zoneless_link_local_address`
  [VERIFIED: .planning/scripts/tests/test_ipv6_thread_probe.py:1113-1118], which asserts
  `"no zone ID" in result.reason` for `make_record(ip="fe80::1")`.

**Why it happens:** The SPEC's background analysis reasoned about `_pick_address()` making the
*report_records()* branch unreachable, and generalised that to the whole function without
checking `stage_connect()`/`_select_target()`, which classify a *different* value
(`record.ip` from a fully resolved record, not `chosen` from the raw per-instance view).

**How to avoid:** The literal grep AC can only be satisfied by removing the *name*
`is_reachable_choice` from the file, not by conditionally keeping the function. Two viable
approaches: (a) rename the helper (e.g. `_has_routable_scope()`) and update the two surviving
call sites to the new name, preserving their exact behaviour and the existing
`test_returns_not_found_for_a_zoneless_link_local_address` test unchanged; or (b) inline the
now-two-line check directly at both remaining call sites and delete the shared helper entirely.
(a) is lower-risk (one function, one behavioural contract, two call sites updated) and keeps
`classify_address()` reuse intact.

**Warning signs:** A task whose diff deletes `is_reachable_choice()` and its two call sites at
`stage_connect()`/`_select_target()` without touching them, or one that keeps the function name
unchanged and expects the grep AC to somehow still pass.

### Pitfall 4: `_normalise_dns_name` is not currently imported by the probe

**What goes wrong:** D-04 requires calling `_normalise_dns_name()` inside `_instance_view()`, but
the probe's current import block only pulls in `_create_device_from_record`,
`_discover_lifx_services`, `_LifxRecordCache` from `lifx.network.discovery.mdns.discovery`
[VERIFIED: .planning/scripts/ipv6_thread_probe.py:90-94]. `_normalise_dns_name` is absent.

**How to avoid:** Add `_normalise_dns_name` to that same import tuple (it is already a
module-level function in `discovery.py`, no new access pattern needed — it is used as a plain,
non-underscore-prefixed... actually it *is* underscore-prefixed and private, consistent with the
probe's existing pattern of importing other private discovery symbols directly). Replace
`srv.target.lower()` [VERIFIED: .planning/scripts/ipv6_thread_probe.py:374] with
`_normalise_dns_name(srv.target)`.

### Pitfall 5: AC-09's "missing id/p/fw key" case is already handled — do not re-fix it

**What goes wrong:** A plan might allocate a task to make `report_records()` print `?` for a
`TxtData` missing `id`/`p`/`fw`, assuming this is part of R3's defensive-handling work.

**Why it is not needed:** [VERIFIED: .planning/scripts/ipv6_thread_probe.py:439-441] — quote:
```
        serial = txt.pairs.get("id", "?")
        product_id = txt.pairs.get("p", "?")
        firmware = txt.pairs.get("fw", "?")
```
This already uses `.get(key, "?")`, so a `TxtData` with missing keys already prints `?` without
raising. AC-09 is satisfied by existing code. The genuine gap R3 must close is
`assert isinstance(txt, TxtData)` at line 436 — which fires only when `txt` itself is `None`
(no TXT record for the instance parsed into a `TxtData` at all, a wire-level parse failure, not a
missing-key case).

**How to avoid:** Scope R3's fix precisely to the three `assert` statements at
[VERIFIED: .planning/scripts/ipv6_thread_probe.py:436-437,485] — `assert isinstance(txt, TxtData)`,
`assert isinstance(aaaa_ips, list)`, `assert isinstance(chosen, str)` — plus D-05's typed-view
migration. Do not add redundant `.get()`-with-default work that already exists.

## Code Examples

### The exact three defect sites in `report_records()` (before any change)

```python
# Source: .planning/scripts/ipv6_thread_probe.py:426-513 [VERIFIED]
    v4_count = 0
    aaaa_count = 0
    linklocal_chosen = 0                                   # R2: declared here

    for instance, view in views:
        txt = view["txt"]
        srv = view["srv"]
        target = view["target"]
        a_ip = view["a"]
        aaaa_ips = view["aaaa"]
        assert isinstance(txt, TxtData)                    # R3 defect #1 (line 436)
        assert isinstance(aaaa_ips, list)                   # R3 defect #2 (line 437, type-narrowing only)
        ...
        if view["addresses"]:
            chosen = view["chosen"]
        elif isinstance(view["fallback"], str):
            chosen = view["fallback"]
        else:
            chosen = None

        if chosen is None:
            if target is not None:
                print("  CHOSEN   : none - pending address records for SRV target")  # R1 defect:
                # fires identically whether view["addresses"] is EMPTY (no cache
                # entry at all) or NON-EMPTY-but-refused (selected_address_for()
                # returned None). D-01/D-02 must split this branch on
                # `view["addresses"]` truthiness.
            else:
                print("  CHOSEN   : none - no SRV record and no fallback source")
            continue
        assert isinstance(chosen, str)                       # R3 defect #3 (line 485, type-narrowing only)

        classification = classify_address(chosen)
        if isinstance(a_ip, str) and chosen == a_ip:
            reason = "A record present; IPv4 preferred over IPv6"
        elif chosen == view["fallback"]:
            reason = "no SRV record; fell back to the response packet's source"
        elif classification == "link-local":
            reason = "ONLY link-local AAAA records available"
            linklocal_chosen += 1                            # R2: incremented here, but chosen
                                                               # can never be link-local once
                                                               # _pick_address() rejects unscoped
                                                               # link-local (Phase 16) -- unreachable
        else:
            reason = f"routable {classification} preferred over link-local"

        print(f"  CHOSEN   : {chosen}  [{classification}]")
        print(f"  WHY      : {reason}")
        if not is_reachable_choice(chosen):                  # R2: unreachable for the same reason
            print("  WARNING  : link-local without a zone ID is not connectable")

    print(f"\n{THIN}")
    print("Summary:")
    print(f"  instances with an A record    : {v4_count}")
    print(f"  instances with AAAA record(s) : {aaaa_count}")
    print(f"  resolved to a usable record   : {len(result.resolved)}")
    print(f"  chose a bare link-local addr  : {linklocal_chosen}")  # R2: always prints 0
```

### The exact WiFi staleness invocation (unchanged tool, per D-13/R5)

```bash
# Wave 2, one operator sitting. --alias-map lives outside the repository.
# Mirrors the exact command SEED-002 already documents.
uv run .planning/scripts/thread_revalidation.py init \
  --session-dir .planning/phases/17-fleet-diagnostics-and-the-staleness-control/17-EVIDENCE \
  --session-id seed-002 \
  --seed <fresh-uint64> \
  --inventory <wifi-roster.json>   # Light, MultiZoneLight, 2x MatrixLight, CeilingLight aliases

uv run .planning/scripts/thread_revalidation.py staleness \
  --session-dir .planning/phases/17-fleet-diagnostics-and-the-staleness-control/17-EVIDENCE \
  --alias-map <path-outside-repo>.json \
  --alias <wifi-alias> \
  --power-off <off.sh> --power-on <on.sh>
```

Real filenames produced (see Pitfall 1):
`.../17-EVIDENCE/14-MANIFEST.json`, `.../17-EVIDENCE/14-STALENESS.jsonl`.

### Phase 14's staleness JSONL schema (exact shape a WiFi row must match)

[VERIFIED: .planning/milestones/v2.0-phases/14-thread-revalidation-and-docs/14-EVIDENCE/14-STALENESS.jsonl]
— one row, keys `alias`, `confirmed_expiry_poll`, `confounders`, `disconnect_ns`, `disposition`,
`first_absence_poll`, `kind`, `polls` (array of `{discover_mdns_present, discover_present, elapsed_s,
poll}`), `protocol_version`, `provenance`, `restoration_duration_s`, `restored_available_ns`,
`revision`, `schema_version`, `session_id`. The Thread row: `disposition: "confirmed_expiry"`,
`first_absence_poll: 70`, `confirmed_expiry_poll: 72`, `restoration_duration_s: 69.35774216699065`,
`session_id: "seed-001"`. The WiFi row must carry `session_id: "seed-002"` (D-13) and — per SPEC
R5's acceptance — a `disposition`, `first_absence_poll` and `restoration_duration_s` always, with
`confirmed_expiry_poll` present only if `disposition == "confirmed_expiry"` (a `censored`
disposition is an equally valid closing result, per AC-14 and the schema's own
`_validate_staleness_event()` [VERIFIED: .planning/scripts/thread_revalidation.py:1179-1200]).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The production WiFi fleet holds at least one `Light`, one `MultiZoneLight`, one `CeilingLight`, and two distinct `MatrixLight`-class devices, satisfying `validate_expected_roster()` without any tooling change. | Background (SPEC, restated in Architecture Patterns) | If the WiFi fleet is missing one of these classes, `init` fails outright (`incomplete_expected_roster`) and Wave 2 cannot start until the roster is amended or the gate is deliberately not touched (out of scope) — this would need an operator confirmation before Wave 2 planning proceeds. Not independently re-verified this session (no access to the live fleet roster); carried from `17-SPEC.md`'s own Background claim. |
| A2 | Recommendation to keep the tool's hardcoded `14-*` evidence filenames inside `17-EVIDENCE/` (Pitfall 1, option 1) is the lower-risk resolution of the D-13-vs-code discrepancy. | Common Pitfalls, Pitfall 1 | This is a judgment call, not a verified fact — the alternative (scoping a small filename-parameterisation change to `thread_revalidation.py`) is also viable and was not ruled out by any SPEC text; the planner or a `checkpoint:human-verify` should confirm this reconciliation before Wave 2 commits evidence under a name D-13 did not anticipate. |

## Open Questions

1. **Does the WiFi roster/alias-map already exist from a prior phase, or must it be authored fresh for this phase?**
   - What we know: Phase 14's `_load_target_alias_map()` precedent and roster JSON shape are fully documented and reusable; the production fleet inventory referenced in `.planning/STATE.md`'s "Fleet Validation"/`project_test_fleet.md` memory entry ("~73 production LIFX devices...") implies WiFi devices of every required class exist.
   - What's unclear: whether an existing WiFi-scoped alias map/roster file from a prior session can be reused, or whether Wave 2 must author one from scratch as a private, outside-the-repo artefact.
   - Recommendation: treat "author a WiFi roster JSON and a private alias-map JSON, both outside/adjacent to the repo per the existing precedent" as a Wave 2 task, gated by a `checkpoint:human-verify` confirming the operator has these files ready before the power-cycle scripts run.

2. **Is `--power-off`/`--power-on` scripting available for the chosen WiFi bulb, or will the run use `--disconnect-ns` (manual/hermetic path)?**
   - What we know: `_cli_staleness()` requires exactly one of the two mutually exclusive paths (`main()`'s argparse gate at `thread_revalidation.py:3768-3769`); THREAD-04's Thread trial used the power-script path.
   - What's unclear: whether the WiFi bulb sits behind a controllable smart-plug/power script, or whether the operator must physically unplug it and capture `--disconnect-ns` by hand.
   - Recommendation: a Wave 2 task should let the operator choose either path at execution time; the plan should not hardcode `--power-off`/`--power-on` as the only option, since SPEC does not mandate the scripted path specifically for WiFi (only "the same protocol" — the protocol is `run_staleness_experiment()`, which accepts either disconnect-capture mechanism identically).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| git | staged-diff evidence inspection, commits | ✓ | 2.50.1 | — |
| uv | running both PEP 723 scripts, tests, docs build | ✓ | 0.12.7 | — |
| zensical (docs builder) | R7's `--strict` docs build gate | ✓ (installs via `uv run`) | `zensical>=0.0.37` per `pyproject.toml:59` | — |
| Real Thread-fleet hardware | R4 (probe transcript) | Not probeable from this environment | — | None — this is the hardware gate; D-21 explicitly allows MDNS-10 to ship without it, with DISC-04-adjacent work carrying forward only if the Thread transcript specifically cannot be captured (R4 is MDNS-10's own evidence requirement, separate from DISC-04) |
| A controllable WiFi LIFX bulb + power on/off mechanism | R5 (DISC-04) | Not probeable from this environment | — | None with a fallback that still satisfies R5; D-21 governs the "cannot happen" case (MDNS-10 ships, DISC-04 stays open) |

**Missing dependencies with no fallback:** the two hardware items above are the entire Wave 2 gate; this is expected and already governed by D-21/D-22, not a defect in this research.

## Security Domain

**`security_enforcement`** is absent from `.planning/config.json`'s `workflow` block (treated as enabled per protocol), so this section is included, but the phase's own SPEC already carries a canon referral: "argv handling and path safety in the operator-supplied power-off and power-on scripts is canon security, owned by `/gsd-secure-phase`, and is not minted here" [CITED: 17-SPEC.md, Prohibitions section]. This phase touches no authentication, session, or network-input-validation surface in `src/lifx/`; it is operator tooling and documentation only.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | N/A — no auth surface touched |
| V3 Session Management | no | N/A |
| V4 Access Control | no | N/A |
| V5 Input Validation | yes (narrow) | `--alias-map` file parsing reuses `_load_target_alias_map()`'s existing `Serial.from_string()`/`validate_alias()` validation (already hardened); the probe's own CLI argument parsing is unchanged by this phase except for the new flag |
| V6 Cryptography | no | N/A |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Operator-supplied `--power-off`/`--power-on` scripts executed as subprocesses | Tampering/Elevation | Already run directly, never through a shell (`_run_power_script`, unmodified by this phase); path/argv safety is explicitly out of this phase's scope per the SPEC's canon referral above |
| Accidental leak of live serials/addresses into committed evidence | Information Disclosure | `--alias-map`'s substring/class-preserving substitution (D-09/D-10/D-11), plus mandatory operator staged-diff inspection before every commit (SPEC prohibition, `judgment`-verified — see Pitfall 2 for why no automated `validate-staged` check covers this artefact) |

## Sources

### Primary (HIGH confidence — read directly this session)

- `.planning/scripts/ipv6_thread_probe.py` (full file, 1375 lines) — every line number cited above
- `.planning/scripts/thread_revalidation.py` (targeted reads: 118-509, 1112-1257, 1713-1785, 2230-2428, 2648-2870, 2892-3120, 3400-3782)
- `.planning/scripts/measurement_support.py` (full file, 765 lines)
- `.planning/scripts/tests/test_ipv6_thread_probe.py` (full file, 2260 lines)
- `.planning/scripts/tests/conftest.py` (full file)
- `src/lifx/network/discovery/mdns/discovery.py` (full file, 1658 lines)
- `.planning/milestones/v2.0-phases/14-thread-revalidation-and-docs/14-EVIDENCE/14-MANIFEST.json` and `14-STALENESS.jsonl`
- `.planning/milestones/v2.0-phases/14-thread-revalidation-and-docs/14-06-SUMMARY.md` (lines 1-110)
- `.planning/phases/15-coverage-gate-and-test-suite-health/15-TEST-02-EVIDENCE.md` (full — the finding-document precedent D-14 cites)
- `.planning/seeds/SEED-002-wifi-advertisement-staleness-control.md` (full)
- `docs/user-guide/discovery.md` (lines 100-155, the Limitations section D-16/D-17 extend)
- `docs/user-guide/troubleshooting.md` (full, 584 lines)
- `tests/test_network/test_mdns/test_phase_contract.py` (lines 100-410, approved_phrases + linking-contract tests)
- `pyproject.toml` (grep for cov/PLC0415/tooling/zensical entries)
- `tests/test_docs_language.py` (lines 1-60)
- `17-CONTEXT.md`, `17-SPEC.md`, `17-DISCUSSION-LOG.md`, `.planning/REQUIREMENTS.md`, `.planning/STATE.md`, `.planning/config.json` (all read in full)

### Secondary (MEDIUM confidence)

- None — no external web sources were consulted; this is a purely internal-codebase phase per the research brief.

### Tertiary (LOW confidence)

- None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependencies; verified by reading both scripts' PEP 723 headers
- Architecture: HIGH — every data-flow claim traces to a specific read line range this session
- Pitfalls: HIGH — all three pitfalls are backed by direct source reads with quoted line ranges, not inference
- WiFi fleet roster completeness (Assumption A1): MEDIUM — asserted by `17-SPEC.md`'s own Background section, not independently re-verified against live inventory in this session

**Research date:** 2026-09-08
**Valid until:** Stable for the life of this phase; re-check if `thread_revalidation.py`'s filename constants or `validate-staged` scope change before Wave 2 executes (would invalidate Pitfalls 1-2), or if Phase 16 lands further changes to `discovery.py` before Wave 1 begins (unlikely — MDNS-09 already shipped and is the last dependency this phase names).
