# Phase 17: Fleet Diagnostics and the Staleness Control - Pattern Map

**Mapped:** 2026-09-08
**Files analyzed:** 10 (create/modify)
**Analogs found:** 10 / 10

**Important framing note for the planner:** this phase touches no `src/lifx/` code. Every
touched file except the two docs pages is operator tooling under `.planning/scripts/` or a
committed evidence/finding artefact. `.planning/scripts/` is explicitly **outside** the
measured coverage tree (`AGENTS.md` "Measured Tree"; confirmed `pyproject.toml` `--cov=lifx
--cov=generate_theme_data` only). Do not import coverage-driven patterns (e.g. "add a test for
every branch to hit patch-coverage") from `src/lifx/` analogs into Wave 1 tasks — the tooling
tests run only via `uv run --frozen pytest --tooling`, are never counted by
`codecov/patch`, and are not gated by CI at all (`.planning/**` absent from `ci.yml`'s
`pull_request.paths`).

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `.planning/scripts/ipv6_thread_probe.py` (`_instance_view`, `report_records`, `is_reachable_choice`→renamed) | utility (CLI diagnostic) | transform (cache → typed view → stdout) | itself, `TargetOutcome` dataclass at same file lines 656-668 | exact (self-analog) |
| `.planning/scripts/ipv6_thread_probe.py` (`--alias-map` flag, redaction helper) | utility (CLI flag + transform) | transform (raw stdout/records → redacted stdout) | `.planning/scripts/thread_revalidation.py:3070` `_load_target_alias_map()`; `.planning/scripts/measure_merged_discovery.py:731` `_load_alias_map()` | exact |
| `.planning/scripts/tests/test_ipv6_thread_probe.py` (`TestSyntheticCacheReporting` extensions + smoke test) | test | CRUD-ish (fixture build → assert on view) | itself, `TestSyntheticCacheReporting.test_instance_view_retains_unordered_advertised_addresses` (same file) | exact (self-analog) |
| `.planning/scripts/tests/test_ipv6_thread_probe.py` (new `--alias-map` tests) | test | transform (input map → substituted output) | `TestSelectTarget` class in same file (dataclass-result assertion idiom) | role-match |
| `17-EVIDENCE/14-MANIFEST.json`, `17-EVIDENCE/14-STALENESS.jsonl` | config/data (evidence, machine-read) | batch (one CLI run → committed JSON/JSONL) | `.planning/milestones/v2.0-phases/14-thread-revalidation-and-docs/14-EVIDENCE/14-MANIFEST.json`, `14-STALENESS.jsonl` | exact |
| `17-EVIDENCE/17-PROBE-TRANSCRIPT.md` | test/evidence (narrated artefact) | file-I/O (stdout capture → narrated markdown) | no direct phase-14 analog (14 has no probe transcript); closest shape is `15-TEST-02-EVIDENCE.md`'s "Run N" narration blocks | role-match |
| `17-EVIDENCE/17-STALENESS-CONTROL.md` | test/evidence (finding document) | transform (two JSONL rows → verdict prose) | `.planning/phases/15-coverage-gate-and-test-suite-health/15-TEST-02-EVIDENCE.md` | exact |
| `docs/user-guide/discovery.md` (Limitations section extension) | component (docs prose) | request-response (caller reads a hazard/guarantee statement) | itself, existing "A Thread border router advertises..." paragraph (lines ~132-137) | exact (self-analog, extend in place) |
| `docs/user-guide/troubleshooting.md` (new cross-referenced entry) | component (docs prose) | request-response | itself, existing "No devices found with `discover_mdns()`" entry pattern (cross-reference to discovery.md, no restatement) | exact (self-analog) |
| `tests/test_network/test_mdns/test_phase_contract.py` (`approved_phrases` tuple extension) | test (contract lock) | CRUD (append tuple entries) | itself, `test_public_guidance_uses_the_approved_limitation_phrases` (lines 121-146) | exact (self-analog) |
| `.planning/ROADMAP.md`, `.planning/REQUIREMENTS.md` (figure correction) | config/data (planning doc) | transform (text edit) | no code analog; plain prose correction, no pattern needed | n/a |

## Pattern Assignments

### `.planning/scripts/ipv6_thread_probe.py` — `_instance_view()` / `report_records()` (utility, transform)

**Analog:** itself (existing file, lines 355-513, plus `TargetOutcome`/`TargetNotFound` dataclasses at 656-676 as the typed-return precedent already living in the same file).

**Current untyped return** (lines 355-403, current state before fix — this is what R1/R3/D-04/D-05 replace):
```python
def _instance_view(cache: _LifxRecordCache) -> list[tuple[str, dict[str, object]]]:
    """Pull the per-instance record set out of the cache for reporting."""
    fallback: dict[str, str] = cache._fallback_ip_by_instance  # noqa: SLF001
    ...
    target = srv.target.lower() if srv is not None else None
    addresses = cache.addresses_for(target) if target else frozenset()
    ...
    views.append(
        (
            instance,
            {
                "txt": txt,
                "txt_count": len(txt_values),
                ...
                "chosen": cache.selected_address_for(target) if target else None,
                "fallback": fallback.get(instance),
            },
        )
    )
    return views
```

**Typed-dataclass precedent to follow for D-05** (lines 656-676, exact code — this is the shape
the new view structure should match, not invent fresh):
```python
@dataclass(frozen=True)
class TargetNotFound:
    """Why a --serial value could not be turned into a controllable device.

    Returned by `_select_target()` instead of raising, so a mistyped serial or
    an absent device is recorded as a failed connect stage rather than ending
    the run in a traceback.
    """

    serial: str
    reason: str


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
Use `@dataclass` (mutable, matches `TargetOutcome`) or `@dataclass(frozen=True)` (matches
`TargetNotFound`) — Claude's Discretion per CONTEXT. Either way, follow the existing one-line
docstring-with-rationale convention seen on both, and give the malformed-field marker a typed
slot (e.g. `txt_malformed: bool = False`) rather than reusing `None`/sentinel values that need
`isinstance` narrowing downstream — that narrowing-for-typing-only pattern is exactly what D-05
forbids reintroducing (see Anti-Pattern below).

**Owner normalisation fix (D-04)** — replace line 374's `srv.target.lower()` with the already
project-imported normaliser. The probe currently imports these private discovery symbols
directly (lines 90-94):
```python
from lifx.network.discovery.mdns.discovery import (
    _create_device_from_record,
    _discover_lifx_services,
    _LifxRecordCache,
)
```
Add `_normalise_dns_name` to this same tuple — this is the established pattern in this file for
consuming library-private symbols (the probe already does it for three others), so no new import
style is needed.

**`classify_address()` reuse for D-02 and D-11** (lines 172-186, exact code, do not duplicate):
```python
def classify_address(addr: str) -> str:
    """Classify an address the way _pick_address's preference order sees it."""
    try:
        parsed = ipaddress.ip_address(addr)
    except ValueError:
        return "invalid"
    if parsed.version == 4:
        return "IPv4"
    if parsed.is_link_local:
        return "link-local"
    if parsed in _ULA_NETWORK:
        return "ULA"
    if parsed.is_global:
        return "GUA"
    return "IPv6-other"
```
D-02's refused-record message ("N cached, both unscoped link-local") and D-11's address
redaction both call this, never a second classifier.

**`is_reachable_choice()` — three call sites, rename don't delete (Pitfall 3):**
```python
# Source: ipv6_thread_probe.py:189-194 [current]
def is_reachable_choice(addr: str) -> bool:
    """Whether an address can be connected to without a zone/scope ID."""
    classification = classify_address(addr)
    if classification != "link-local":
        return classification != "invalid"
    return "%" in addr
```
Called at line 505 (`report_records()`, the branch R2 removes — delete this call site along with
`linklocal_chosen`), line 598 (`stage_connect()`, live, keep), and line 695 (`_select_target()`,
live, keep, and covered by
`TestSelectTarget::test_returns_not_found_for_a_zoneless_link_local_address`, same test file
lines ~1113-1118). AC-06's literal grep for the string `is_reachable_choice` demands the *name*
vanish; rename the function (e.g. `_has_routable_scope()`) and update the two surviving call
sites, preserving their behaviour and that existing test unchanged.

### `.planning/scripts/ipv6_thread_probe.py` — `--alias-map` flag (utility, transform)

**Analog:** `.planning/scripts/thread_revalidation.py:3070-3087` `_load_target_alias_map()`
(exact code to mirror the shape of, per D-09's explicit instruction to reuse it rather than
invent a second validator):
```python
def _load_target_alias_map(path: Path) -> dict[str, str]:
    """Load an external raw-serial-to-alias mapping only into memory (D-19).

    Mirrors ``.planning/scripts/measure_merged_discovery.py``'s alias-map precedent:
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
Secondary analog (older sibling precedent, cited in the docstring above):
`.planning/scripts/measure_merged_discovery.py:731-746` `_load_alias_map()` — same shape, adds
an explicit `"--alias-map must be outside the repository"` guard the probe should also consider
copying (D-09 gives discretion on the exact seam but not on reusing validated serial/alias
handling).

Whole-line substring replace for serials (D-10) has no existing helper to copy verbatim — this
is new composition, but it must operate on the **already-classified-and-normalised** serial
strings this loader produces, not raw text scanning.

Address class-preserving substitution (D-11) is new code; `classify_address()` above is the only
reused primitive. Target ranges are fixed by the CONTEXT and already validated elsewhere in the
repo: `tests/test_network/test_mdns/test_phase_contract.py:373` already forbids private-looking
IPv4 literals outside `192.0.2.0/24`/`2001:db8::/32` in docs, confirming these are the
repository's established documentation-safe ranges — reuse the same ranges, do not invent new
ones.

### `.planning/scripts/tests/test_ipv6_thread_probe.py` — R1/R3 test additions (test)

**Analog:** itself. `TestSyntheticCacheReporting` (class starts ~line 1039) and its helper
`_cache_chain()` (lines 131-159, exact code):
```python
def _cache_chain(
    *,
    instance: str = "synthetic._lifx._udp.local",
    target: str = "synthetic-host.local",
    address: str = "192.0.2.20",
    ttl: int = 120,
) -> list[DnsResourceRecord]:
    """Build a complete synthetic TXT/SRV/A chain."""
    txt = TxtData(
        strings=["id=d073d5aa11bb", "p=57", "fw=4.10"],
        pairs={"id": "d073d5aa11bb", "p": "57", "fw": "4.10"},
    )
    srv = SrvData(priority=0, weight=0, port=56700, target=target)
    return [
        DnsResourceRecord(instance, 16, 1, ttl, b"\x0fid=d073d5aa11bb\x04p=57\x07fw=4.10", txt),
        DnsResourceRecord(instance, 33, 1, ttl, b"synthetic-srv", srv),
        DnsResourceRecord(target, 1, 1, ttl, ipaddress.ip_address(address).packed, address),
    ]
```
And the existing assertion idiom in `TestSyntheticCacheReporting`
(`test_instance_view_retains_unordered_advertised_addresses`, exact code):
```python
def test_instance_view_retains_unordered_advertised_addresses(self) -> None:
    """Synthetic inspection needs no socket, daemon, or hardware access."""
    instance = "synthetic._lifx._udp.local"
    host = "synthetic-host.local"
    txt = TxtData(...)
    ...
    cache = probe._LifxRecordCache()
    cache.add_packet([...], "192.0.2.10")

    [(reported_instance, view)] = probe._instance_view(cache)

    assert reported_instance == instance
    assert view["addresses"] == frozenset({"192.0.2.20", "fd00::20"})
    assert view["chosen"] == "192.0.2.20"
    assert view["fallback"] == "192.0.2.10"
```
**Migration required by D-05:** every `view["addresses"]`/`view["chosen"]`/`view["fallback"]`
dict-subscript in this class (and any other consumer in the test file) moves to attribute access
(`view.addresses`, `view.chosen`, `view.fallback`) in the same change that lands the typed
structure — CONTEXT explicitly calls this "reversibility: costly" for exactly this reason.

New R1 fixtures (absent-record and refused-record cases) should be built as `_cache_chain()`
variants: one with the A/AAAA record omitted entirely (target has an SRV but nothing cached at
`cache.addresses_for()`), one with the A record swapped for an unscoped link-local AAAA and no
usable selection — the CONTEXT and RESEARCH both call out `_cache_chain()` as the reusable
scaffold for both.

New R3 fixture (malformed middle instance): build three instances via `_cache_chain()`-style
construction, but for the middle one, feed `cache.add_packet()` a TXT-type resource record whose
`parsed_data` is not a `TxtData` (e.g. `None` or a raw string) — the existing filter
`if isinstance(record.parsed_data, TxtData)` at line ~362 in `_instance_view()` is what currently
produces `txt = None` for that owner, which is the exact condition R3 must survive.

### `.planning/scripts/tests/test_ipv6_thread_probe.py` — `--alias-map` tests (test)

**Analog:** `TestSelectTarget` in the same file (dataclass-result-assertion idiom, exact code):
```python
def test_returns_not_found_for_a_zoneless_link_local_address(self) -> None:
    """A link-local literal with no zone ID cannot be routed to."""
    result = probe._select_target([make_record(ip="fe80::1")], TARGET_SERIAL)

    assert isinstance(result, probe.TargetNotFound)
    assert "no zone ID" in result.reason
```
D-12 requires this be its own commit with its own tests, separate from the three
`report_records()` fixes: (1) serial substring replacement inside instance names and SRV
hostnames, (2) class-preserving address substitution, (3) raw-by-default (no `--alias-map` given
→ output unchanged from current behaviour, asserted against a fixture run with and without the
flag).

### `17-EVIDENCE/14-MANIFEST.json`, `17-EVIDENCE/14-STALENESS.jsonl` (config/data, batch)

**Analog:**
`.planning/milestones/v2.0-phases/14-thread-revalidation-and-docs/14-EVIDENCE/14-MANIFEST.json`
and `14-STALENESS.jsonl` (both git-tracked source, confirmed present under
`.planning/milestones/`).

**Manifest shape** (excerpt, exact JSON):
```json
{
  "animation_schedule": [[1, 10.0], [2, 10.0], [5, 10.0]],
  "confounders": [],
  "discovery_round_gaps_s": [6.19..., 8.97..., 13.64..., 7.48..., 7.46...],
  "inventory": [
    {"alias": "LIFX-DL-Intl-1", "available": true, "device_class": "Light"},
    {"alias": "LIFX-Mini-1", "available": true, "device_class": "Light"},
    {"alias": "LIFX-Ceiling-13x26-1", "available": true, "device_class": "CeilingLight"},
    ...
  ]
}
```
Confirmed fields also include (per RESEARCH) `staleness_cap_s: 10800.0`,
`staleness_poll_interval_s: 60.0`, `staleness_confirm_absent_polls: 3` — these are
tool-populated, not authored, since D-13 mandates the WiFi session is produced by the unmodified
`thread_revalidation.py init`/`staleness` CLI, never hand-written.

**Staleness JSONL row schema** (per RESEARCH, `14-STALENESS.jsonl` exact keys): `alias`,
`confirmed_expiry_poll`, `confounders`, `disconnect_ns`, `disposition`, `first_absence_poll`,
`kind`, `polls` (array of `{discover_mdns_present, discover_present, elapsed_s, poll}`),
`protocol_version`, `provenance`, `restoration_duration_s`, `restored_available_ns`, `revision`,
`schema_version`, `session_id`. The WiFi row must carry `session_id: "seed-002"` (D-13) in place
of Phase 14's `"seed-001"`.

**Critical naming note (Pitfall 1, RESEARCH):** these two evidence files are produced under the
tool's own hardcoded literal filenames `14-MANIFEST.json`/`14-STALENESS.jsonl` regardless of
`--session-dir`. Point `--session-dir` at `17-EVIDENCE/`; do **not** rename the output files
afterward — the tool's own resume/idempotency checks (`reload_staleness_events()`,
`_cli_staleness()`'s same-alias-resume guard) look for exactly `14-STALENESS.jsonl` by that
literal name. The directory gets the `17-` phase prefix; the files keep the tool's `14-` prefix.
Document this explicitly in `17-STALENESS-CONTROL.md` rather than silently deviating from
`17-CONTEXT.md` D-13's (incorrect) assumption — D-13 has already been amended in-context to
acknowledge this (see the `*Amended during planning*` note in `17-CONTEXT.md`).

### `17-EVIDENCE/17-PROBE-TRANSCRIPT.md` (test/evidence, file-I/O)

**No exact phase-14 analog exists** (Phase 14 produced no probe transcript). Closest available
shape is `15-TEST-02-EVIDENCE.md`'s per-run narration block pattern (excerpt):
```markdown
## Run 1: the fixed form, against the main checkout

Command:

\`\`\`
uv run --frozen python .planning/phases/.../15-TEST-02-observe.py \
    --node '...' \
    --timeout 60 --repo-root . \
    --output .../15-TEST-02-record-fixed.json
\`\`\`

Recorded in [`15-TEST-02-record-fixed.json`](15-TEST-02-record-fixed.json):

| Field | Value |
|---|---|
| Working directory | `<repo>` (the main checkout) |
```
D-15 requires: run date, git revision, invocation, a statement of which new messages appeared
and which did not (AC-11), then redacted stdout in a fenced block. Follow 15-TEST-02-EVIDENCE.md's
command-then-recorded-table-then-narration structure, substituting a fenced transcript block for
the JSON-link-and-table pairing (the transcript itself, not a separate JSON, is the recorded
artefact here).

### `17-EVIDENCE/17-STALENESS-CONTROL.md` (test/evidence, transform)

**Analog:**
`.planning/phases/15-coverage-gate-and-test-suite-health/15-TEST-02-EVIDENCE.md` (full file
read; git-tracked). Structure to copy: `# <ID>: <Title> Evidence` heading, `**Recorded:** <date>`,
a `## What this settles` section stating the prior assumption and what corrects it, a
`## The instrument` section naming exact commands, then per-observation sections with tables and
narration, closing with an explicit verdict statement bounded by what the evidence supports (the
`15-TEST-02-EVIDENCE.md` negative-control paragraph — "Without that control there would be no way
to tell whether..." — is the precedent for D-14's "pre-stated opposite-observation clause"
requirement, R6/AC-18).

Required content per D-14/R6: both Thread figures (4140-4200 s interval, 69.4 s restoration),
both WiFi figures (with the 60 s cadence bound named per D-17), each figure's measurement
resolution, the verdict with its limits, the pre-stated opposite-observation clause, and the
69.4 s conflation correction.

### `docs/user-guide/discovery.md` — Limitations extension (component, request-response)

**Analog:** itself — extend the existing paragraph in place (D-16), do not add a new section.
Current exact prose to extend (lines ~132-137):
```markdown
A Thread border router advertises every device on its mesh over mDNS,
whether or not each advertised device is currently reachable. An mDNS
result therefore proves an advertisement exists, not that the advertised
device is currently reachable. The next action is to confirm it with a
request, or to use `discover()`, whose mDNS candidates must answer a
correlated device request before they are yielded.
```
And the disclaimer paragraph immediately below it (lines ~139-143, already in place, D-17 relies
on it to avoid over-claiming):
```markdown
Behaviour on a large or congested network is not characterised by this
documentation. Any physical observations of Thread/mDNS behaviour, where
referenced in this documentation set, describe the specific fleet measured
at that time, not a universal benchmark or a performance guarantee for
every network or every LIFX firmware revision. Do not size timeouts or
retry policy from this documentation; measure them against your own
network instead.
```
New prose must state the quantified interval (4140-4200 s Thread, restoration figures both
directions, WiFi figures with 60 s cadence bound named) directly beneath/within this paragraph,
in Australian English, with no em dash (there is a pre-existing em dash at the end of the
bounded-discovery paragraph a few lines above — leave it untouched, add none of your own).

### `docs/user-guide/troubleshooting.md` — cross-referenced entry (component, request-response)

**Analog:** itself — existing cross-reference idiom at the top of "Discovery Issues" (exact
code):
```markdown
## Discovery Issues

See the [Discovery Guide troubleshooting section](discovery.md#troubleshooting)
for mDNS-specific and IPv6 zone issues. The general UDP broadcast issues below
apply to `discover()` and `discover_udp()` alike.
```
D-19 requires a short entry that **points at** discovery.md's paragraph rather than restating the
figures — copy this exact "See the [...](discovery.md#...) for..." pattern, one or two sentences,
no duplicated figures. `test_phase_contract.py`'s `TestPhase14DiscoveryLinkingContract` (around
line 393) is the enforcement mechanism for no-duplication — read it before writing this entry.

### `tests/test_network/test_mdns/test_phase_contract.py` — approved-phrase lock (test, CRUD)

**Analog:** itself, exact code (lines ~121-146):
```python
def test_public_guidance_uses_the_approved_limitation_phrases(self) -> None:
    """The user guide states the exact supported legacy-unicast limits."""
    guidance = _normalised_prose(_PUBLIC_GUIDANCE_PATH)
    approved_phrases = (
        "ephemeral source port",
        "legacy-unicast replies",
        ...
        "does not extend the overall timeout",
    )
    folded_guidance = guidance.casefold()

    for phrase in approved_phrases:
        assert phrase.casefold() in folded_guidance
    assert "only replies to its own queries" not in guidance
```
D-18 requires adding 2-3 short distinctive fragments from the new discovery.md prose to this
tuple, following exactly this convention (short literal substrings, casefold-compared). Do not
create a second phrase tuple or a new test function — extend this one, matching Phase 16 D-16's
precedent the CONTEXT cites.

## Shared Patterns

### Alias-map loading and validation
**Source:** `.planning/scripts/thread_revalidation.py:3070-3087` (`_load_target_alias_map()`),
secondary precedent `.planning/scripts/measure_merged_discovery.py:731-746` (`_load_alias_map()`)
**Apply to:** `.planning/scripts/ipv6_thread_probe.py`'s new `--alias-map` flag
**Why shared:** both existing loaders already normalise serials via `Serial.from_string()`,
validate aliases via `validate_alias()`, reject duplicates and empty maps, and keep the raw
mapping outside tracked evidence. Do not re-derive this logic a third time.

### Address classification
**Source:** `.planning/scripts/ipv6_thread_probe.py:172-186` (`classify_address()`)
**Apply to:** D-02's refused-record message (record count + per-record classification) and
D-11's address redaction (class-preserving substitution)
**Why shared:** exactly one classifier in the file; both features need the same class labels
(`IPv4`, `link-local`, `ULA`, `GUA`, `IPv6-other`, `invalid`).

### Documentation-safe address ranges
**Source:** `tests/test_network/test_mdns/test_phase_contract.py:373`
(`test_discovery_surfaces_use_only_documentation_safe_addresses`)
**Apply to:** D-11's address-substitution targets (`192.0.2.0/24` for IPv4, `2001:db8::/32` for
GUA)
**Why shared:** this test already enforces that documentation-facing content in this repo uses
only these ranges; reuse rather than invent alternate documentation ranges for the redacted
transcript.

### Evidence-artefact naming convention
**Source:** `.planning/**/*-EVIDENCE/`, `.planning/**/*-EVIDENCE.md` project-wide (Phase 14, 15)
**Apply to:** `17-EVIDENCE/17-PROBE-TRANSCRIPT.md`, `17-EVIDENCE/17-STALENESS-CONTROL.md`
**Why shared:** `NN-` phase-prefixed filenames, Markdown for narrated artefacts, JSON/JSONL for
machine-read ones. Exception: the two files a tool itself writes (`14-MANIFEST.json`,
`14-STALENESS.jsonl`) keep the *tool's own* prefix inside the `17-`-prefixed directory — do not
force phase-prefix consistency onto files a running tool names for you (see Pitfall 1 above).

### Approved-phrase / no-duplication docs contract
**Source:** `tests/test_network/test_mdns/test_phase_contract.py` (`approved_phrases` tuple,
`TestPhase14DiscoveryLinkingContract`)
**Apply to:** both `docs/user-guide/discovery.md` and `docs/user-guide/troubleshooting.md` edits
**Why shared:** this is a hard test gate, not a style suggestion — new prose must satisfy the
extended tuple, and troubleshooting.md's entry must cross-reference rather than restate.

## No Analog Found

None. All ten touched files have a concrete analog, most of them the same file's own prior
version (this phase is almost entirely modification-in-place of existing tooling/docs, not
greenfield creation).

## Metadata

**Analog search scope:** `.planning/scripts/`, `.planning/scripts/tests/`,
`.planning/phases/15-coverage-gate-and-test-suite-health/`,
`.planning/milestones/v2.0-phases/14-thread-revalidation-and-docs/14-EVIDENCE/`,
`docs/user-guide/`, `tests/test_network/test_mdns/test_phase_contract.py`
**Files scanned:** `ipv6_thread_probe.py` (full, 1375 lines, prior sessions), targeted reads this
session at lines 1-30, 160-200, 350-520, 640-700; `test_ipv6_thread_probe.py` targeted reads at
120-200, 1039-1130; `thread_revalidation.py` targeted read 3050-3100; `measure_merged_discovery.py`
grep for `alias_map`; `15-TEST-02-EVIDENCE.md` lines 1-60; `discovery.md` lines 100-155;
`troubleshooting.md` lines 1-40; `test_phase_contract.py` lines 100-150; `14-MANIFEST.json` head;
`14-EVIDENCE/` directory listing.
**Pattern extraction date:** 2026-09-08
