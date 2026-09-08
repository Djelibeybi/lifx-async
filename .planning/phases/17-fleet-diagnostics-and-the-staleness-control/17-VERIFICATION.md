---
phase: 17-fleet-diagnostics-and-the-staleness-control
verified: 2026-09-08T00:00:00Z
status: passed
score: 12/12 must-haves verified
behavior_unverified: 0
overrides_applied: 0
---

# Phase 17: Fleet Diagnostics and the Staleness Control Verification Report

**Phase Goal:** The hardware-facing diagnostics report what they actually observed, and v2.0's
Thread disappearance-to-expiry interval of 4140 to 4200 s (not to be confused with its separate
69.4 s restoration duration) gains a WiFi control instead of standing alone.
**Verified:** 2026-09-08
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | The probe distinguishes an instance holding no address data at all from one holding a cached but unusable unscoped link-local AAAA record, and says which it saw | ✓ VERIFIED | `.planning/scripts/ipv6_thread_probe.py` carries the typed `_InstanceView` with five `_Selection` literals (`selected`, `fallback`, `refused`, `absent`, `no-target`); `_non_resolving_lines()` renders `none - N cached address record(s) for the SRV target, none usable` for refused vs `none - no address record cached for the SRV target` for absent. Two dedicated tooling tests (`test_instance_view_reports_refused_when_cached_addresses_yield_no_selection`, `test_instance_view_reports_absent_when_no_address_record_is_cached`) pass. Committed hardware transcript's summary block shows `cached but no usable address : 0` / `awaiting address records : 0` as the new split counters, replacing the old `chose a bare link-local addr` line |
| 2 | The `linklocal_chosen` summary counter and its warning are reachable/truthful or removed; a partially assembled instance no longer terminates diagnostics through the TXT assertion | ✓ VERIFIED | `grep -n 'linklocal_chosen\|is_reachable_choice' .planning/scripts/ipv6_thread_probe.py` returns nothing (re-run directly, confirmed). The predicate was renamed to `_has_routable_scope` with both live call sites intact and `TestSelectTarget::test_returns_not_found_for_a_zoneless_link_local_address` still green. `assert isinstance(txt, TxtData)` replaced by a rendered marker; `test_report_records_completes_over_a_malformed_middle_instance` and `test_instance_view_marks_a_malformed_txt_and_keeps_the_remaining_instances` both pass. `grep -c "assert isinstance"` returns 0 in the probe source (the one remaining `assert` is an unrelated CLI invariant) |
| 3 | Advertisement staleness is measured against a WiFi bulb using the same protocol THREAD-04 used on Thread | ✓ VERIFIED | `17-EVIDENCE/14-MANIFEST.json` (`session_id: seed-002`) and `17-EVIDENCE/14-STALENESS.jsonl` committed, produced by `thread_revalidation.py staleness` with R5's frozen constants (60 s cadence, 3 confirm polls, 10800 s cap) unchanged in `measurement_support.py`. Disposition `confirmed_expiry`, `first_absence_poll: 1`, `confirmed_expiry_poll: 3`. The four SPEC-amendment-A8 tool departures (explicit 45 s timeout, measured `elapsed_s`, first-leg-present restoration close, InfraredLight/HevLight roster acceptance) are disclosed explicitly, and the finding states "not a fully protocol-matched pair" rather than presenting the arms as matched |
| 4 | The recorded result states whether the 4140–4200 s interval is Thread-specific or a general mDNS TTL/goodbye artefact | ✓ VERIFIED | `17-EVIDENCE/17-STALENESS-CONTROL.md` states the verdict (Thread-specific, attributed to the absence of a rebroadcasting border router on WiFi), names the observation that would have supported the opposite verdict in advance, and bounds the claim to "one trial per arm establishes a direction, not a distribution" |
| 5 | Every committed artefact from both runs carries format-preserving pseudonyms, with no live serial, MAC address, IP address or hostname in the staged diff | ✓ VERIFIED | Direct grep of `17-EVIDENCE/` for LIFX OUI prefixes (`d073d5`, `d0:73:d5`), private IPv4 ranges and unbounded `fe80::`/`fd`-prefixed literals returns nothing. All addresses in the committed transcript are `192.0.2.x` / `2001:db8:{1..4}::x`. Operator checkpoints at 17-03 Task 3 and 17-04 Task 5 both recorded explicit adjudication (local-tokens-for-operator classified into two known classes; AMBIGUOUS-NUMERIC-TOKENS: none both times) |

### Sceptical-Review Checks (from task brief)

| # | Check | Status | Evidence |
|---|-------|--------|----------|
| 1 | WiFi disappearance figure stated as a bound, not a point value | ✓ VERIFIED | `17-STALENESS-CONTROL.md`: "at most 80.8548 s ... `first_absence_poll: 1` means the device was already gone by the time poll 1's two discovery legs finished, so the bound is the real elapsed time that poll took". `docs/user-guide/discovery.md`: "was confirmed gone at most 80.8548 seconds after power loss, the measured completion time of the first poll rather than a point observed inside that window." The 204.65 s confirmation-poll elapsed time (poll 3) is never presented as the interval anywhere checked |
| 2 | Accuracy caveat travelled into the published verdict, prominently | ✓ VERIFIED | `17-STALENESS-CONTROL.md` carries a dedicated `### Precision limits on the WiFi figures` subsection under `## The verdict`, naming all four precision-limiting reasons, the supported/not-supported split, and the planned third round. `17-04-SUMMARY.md` records the operator explicitly mandated this be "prominent... not buried as a footnote" |
| 3 | Two arms never described as a matched control | ✓ VERIFIED | Every occurrence found (`17-STALENESS-CONTROL.md`, `17-SPEC.md` A8, `17-04-SUMMARY.md`, `17-05-SUMMARY.md`) is a negation: "not a fully protocol-matched pair", "not a protocol-matched control", "neither protocol-matched... nor condition-matched". No assertion of matched-control status found |
| 4 | A7/A8 amendments consistent with artefacts; R5 frozen constants untouched | ✓ VERIFIED | A7 (firmware-hex SRV labels committable): 10 bare-hex 16-char `.local` labels present in the committed transcript and explicitly adjudicated in `17-03-SUMMARY.md`. A8 (four `thread_revalidation.py` changes): confirmed via `THREAD-REVALIDATION-AUTHORISED` blob-hash gate in `17-04-PLAN.md`, and `measurement_support.py` (`STALENESS_CAP_S`, `STALENESS_POLL_INTERVAL_S`, `STALENESS_CONFIRM_ABSENT_POLLS`) is absent from `git diff --stat` for this phase's commits — confirmed no modification |
| 5 | DISC-04's conflated "69 s" wording corrected in ROADMAP.md and REQUIREMENTS.md | ✓ VERIFIED | `grep -nE '\b69s\b' .planning/ROADMAP.md .planning/REQUIREMENTS.md` returns nothing. Both files now read "4140 to 4200 s" for disappearance-to-expiry and "69.4 s restoration duration" as a distinct, correctly labelled figure |
| 6 | No live device serial, MAC, IP or hostname in any committed artefact | ✓ VERIFIED | See truth 5 above. Additionally spot-checked `docs/user-guide/discovery.md`'s new prose — carries only the aggregate figures (4140-4200 s, 80.8548 s, 69.4 s, 14.6 s), no identifiers |
| 7 | R4 and R5 closure supported by committed artefacts | ✓ VERIFIED | R4: `17-EVIDENCE/17-PROBE-TRANSCRIPT.md` committed (`e950cc8`), 289+ transcript lines, `Probe exit status: 0`, AC-11 observed/not-observed disposition for all five new message states. R5: `17-EVIDENCE/14-MANIFEST.json` + `14-STALENESS.jsonl` committed (`072159d`), validated by the tool's own `load_manifest()`/`reload_staleness_events()` |

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `.planning/scripts/ipv6_thread_probe.py` | Typed instance view, redaction, dead-code removal | ✓ VERIFIED | `_InstanceView`, `_TranscriptRedactor`, `_RedactingStream`, `_load_probe_alias_map` all present; `linklocal_chosen`/`is_reachable_choice` absent |
| `.planning/scripts/tests/test_ipv6_thread_probe.py` | Tooling tests for all fixes | ✓ VERIFIED | 161 tests, all pass (139 pre-phase + 22 redaction tests) |
| `17-EVIDENCE/17-PROBE-TRANSCRIPT.md` | Redacted real-hardware probe run | ✓ VERIFIED | Committed, 23 instances, 59 packets, pseudonymised throughout |
| `17-EVIDENCE/14-MANIFEST.json` | WiFi session manifest | ✓ VERIFIED | `session_id: seed-002`, frozen constants intact |
| `17-EVIDENCE/14-STALENESS.jsonl` | WiFi staleness row | ✓ VERIFIED | One row, `confirmed_expiry`, all required fields present |
| `17-EVIDENCE/17-STALENESS-CONTROL.md` | Verdict with corrected figures | ✓ VERIFIED | All four figures, resolutions, opposite-observation clause, caveat |
| `docs/user-guide/discovery.md` | Caller-facing liveness statement | ✓ VERIFIED | Extends Phase-16 paragraph with both directions, both figure sets, trial count, correct attribution (`discover_mdns()` vs `discover()`/`find_by_serial()`) |
| `.planning/ROADMAP.md` / `.planning/REQUIREMENTS.md` | 69 s correction | ✓ VERIFIED | Corrected, grep-confirmed |

### Requirements Coverage

| Requirement | Source Plan(s) | Status | Evidence |
|---|---|---|---|
| MDNS-10 | 17-01, 17-02, 17-03 | ✓ SATISFIED | `REQUIREMENTS.md` marks `[x]` complete; probe fixes + redaction + hardware transcript all present and tested |
| DISC-04 | 17-04, 17-05 | ✓ SATISFIED | `REQUIREMENTS.md` marks `[x]` complete; WiFi trial evidence + published verdict + docs + ROADMAP/REQUIREMENTS correction all present |

No orphaned requirements found: `.planning/REQUIREMENTS.md`'s phase-mapping table lists exactly MDNS-10 and DISC-04 against Phase 17, matching the task brief.

### Anti-Patterns Found

None blocking. `TBD`/`FIXME`/`XXX` scan of phase-modified files returns nothing. Two pre-existing, deliberately-left Warning findings from `17-REVIEW.md` (WR-01 unanchored serial regex; WR-02 dropped restoration fields in `generate_summary()`) are known open items per the task brief — not re-litigated here, and confirmed unfixed but non-blocking (WR-01 caused zero actual leaks in the committed transcript; WR-02 affects a downstream report projection, not the committed evidence).

### Automated Verification (re-run directly by this verifier)

| Check | Result |
|---|---|
| `grep -n 'linklocal_chosen\|is_reachable_choice' .planning/scripts/ipv6_thread_probe.py` | empty (pass) |
| `uv run --frozen pytest .planning/scripts/tests/test_ipv6_thread_probe.py -q --no-cov` | 161 passed |
| `uv run --frozen pyright` | 0 errors, 0 warnings |
| `uv run --frozen ruff check .` | all checks passed |
| `uv run --frozen ruff format --check .` | 285 files already formatted |
| `uv run zensical build --clean --strict` | exit 0, "No issues found" |
| `uv run --frozen pytest tests/test_network/test_mdns/test_phase_contract.py tests/test_docs_language.py -q` | 28 passed |
| `uv run --frozen pytest -q` (full suite) | 4272 passed, 674 deselected |
| `git status --porcelain` | clean |
| `git diff --name-only main...HEAD -- .planning/milestones/v2.0-phases/` | empty |
| Privacy grep of `17-EVIDENCE/` for OUI/private-IP/unbounded fe80/fd literals | no matches |
| em-dash scan of `17-PROBE-TRANSCRIPT.md`, `17-STALENESS-CONTROL.md`, and newly added `discovery.md` lines | none |
| `git cat-file -e` on all 10 commits cited across the five SUMMARYs | all found |

### Human Verification Required

None. Both hardware arms are already evidenced by committed artefacts and operator checkpoints that occurred during execution (recorded in 17-03-SUMMARY.md and 17-04-SUMMARY.md); nothing remains that requires a fresh human check to close this verification pass.

### Gaps Summary

No gaps found. All five plans executed, all ROADMAP success criteria verified against actual codebase state (not SUMMARY claims), the task brief's seven sceptical-review points all resolved correctly in the committed artefacts, and the three explicitly-flagged known-open-items (WR-01, WR-02, absent 17-SECURITY.md) are confirmed present but correctly classified as non-blocking per the task brief.

---

_Verified: 2026-09-08_
_Verifier: Claude (gsd-verifier)_
