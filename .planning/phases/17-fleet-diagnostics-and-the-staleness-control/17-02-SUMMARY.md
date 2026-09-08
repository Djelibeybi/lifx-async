---
phase: 17-fleet-diagnostics-and-the-staleness-control
plan: 02
subsystem: diagnostics
tags: [redaction, privacy, regex, mdns, ipv6, thread, tooling]

requires:
  - phase: 17-fleet-diagnostics-and-the-staleness-control (plan 01)
    provides: "Typed _InstanceView and the survivable per-instance reporting loop this plan's redaction wraps unchanged"
provides:
  - "_load_probe_alias_map(): the sibling loader contract (thread_revalidation.py / measure_merged_discovery.py) reused verbatim for the probe's own --alias-map"
  - "_TranscriptRedactor: single-pass whole-text serial substitution (all three wire spellings) plus single-pass address substitution onto per-class documentation sub-ranges reserved inside 2001:db8::/32 and 192.0.2.0/24"
  - "_RedactingStream and an --alias-map CLI flag whose only effect is a contextlib.redirect_stdout() install for the duration of one run, restored on both return and exception"
  - "Raw output remains the unconditional default: no flag means no context entered and sys.stdout untouched, proven at both the function and the CLI boundary"
affects: [17-03-fleet-diagnostics-and-the-staleness-control, 17-04-fleet-diagnostics-and-the-staleness-control]

actuals:
  tokens: 6392
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - "Single combined regex alternation (IPv6 branch first, dotted-quad tried before hex tail) so an IPv4-mapped IPv6 literal is consumed as one token in one re.sub() pass rather than corrupted by two sequential IPv4-then-IPv6 passes"
    - "Per-class documentation sub-range reservation (not a classify_address() round trip) as the redaction contract, since no documentation-safe IPv6 range classifies as GUA/ULA/link-local"
    - "contextlib.redirect_stdout() + ExitStack for a restoring install, replacing the discarded bare sys.stdout assignment design that a prior review round flagged as leaking into later in-process test invocations"

key-files:
  created: []
  modified:
    - .planning/scripts/ipv6_thread_probe.py
    - .planning/scripts/tests/test_ipv6_thread_probe.py

key-decisions:
  - "Reused _load_target_alias_map()'s exact validation contract (Serial.from_string() normalisation, shared validate_alias(), outside-the-repository guard, duplicate-serial rejection) rather than re-deriving it, per D-09"
  - "IPv4-mapped IPv6 addresses are redacted through the IPv4 counter/prefix (emitting ::ffff:192.0.2.N) rather than a separate mapped-form counter, so the mapped shape the cache deliberately retains stays legible as mapped"
  - "The redacting stream is installed only for the duration of asyncio.run(main_async(args)) via contextlib.redirect_stdout() inside an ExitStack, never via direct sys.stdout assignment, so this module's own in-process tooling tests cannot inherit a redacting stream from an earlier invocation"

requirements-completed: [MDNS-10]

coverage:
  - id: D1
    description: "An external raw-serial-to-alias JSON map is loaded with the same validation contract as the two sibling measurement scripts, rejecting a path inside the repository, an empty map, a duplicate normalised serial, and an identifier-shaped alias"
    requirement: "MDNS-10"
    verification:
      - kind: unit
        ref: "test_ipv6_thread_probe.py#TestAliasMapRedaction::test_alias_map_loader_rejects_path_inside_repository"
        status: pass
      - kind: unit
        ref: "test_ipv6_thread_probe.py#TestAliasMapRedaction::test_alias_map_loader_rejects_empty_object"
        status: pass
      - kind: unit
        ref: "test_ipv6_thread_probe.py#TestAliasMapRedaction::test_alias_map_loader_rejects_duplicate_normalised_serial"
        status: pass
      - kind: unit
        ref: "test_ipv6_thread_probe.py#TestAliasMapRedaction::test_alias_map_loader_rejects_identifier_shaped_alias"
        status: pass
    human_judgment: false
  - id: D2
    description: "A mapped serial is replaced wherever it appears (mDNS instance name, SRV hostname, TXT id value) in all three wire spellings and mixed case"
    requirement: "MDNS-10"
    verification:
      - kind: unit
        ref: "test_ipv6_thread_probe.py#TestAliasMapRedaction::test_replaces_mapped_serial_everywhere_in_all_spellings"
        status: pass
    human_judgment: false
  - id: D3
    description: "Every parsing address literal is rewritten to a documentation-range pseudonym drawn from the sub-range reserved for its own classify_address() class (IPv4, GUA, IPv6-other, ULA, link-local), stable within a run, with no pseudonym drawn from operational fd00:: or fe80:: space"
    requirement: "MDNS-10"
    verification:
      - kind: unit
        ref: "test_ipv6_thread_probe.py#TestAliasMapRedaction::test_each_source_class_lands_on_its_reserved_subrange"
        status: pass
      - kind: unit
        ref: "test_ipv6_thread_probe.py#TestAliasMapRedaction::test_repeated_address_yields_stable_pseudonym"
        status: pass
      - kind: unit
        ref: "test_ipv6_thread_probe.py#TestAliasMapRedaction::test_distinct_addresses_of_one_class_yield_distinct_pseudonyms"
        status: pass
      - kind: unit
        ref: "test_ipv6_thread_probe.py#TestAliasMapRedaction::test_zone_suffix_survives_substitution_verbatim"
        status: pass
      - kind: other
        ref: "runtime redactor-contract check driving _TranscriptRedactor({}) directly over all five classes plus operational-range assertions (17-02-PLAN.md Task 1 verify)"
        status: pass
    human_judgment: false
  - id: D4
    description: "An IPv4-mapped IPv6 literal such as ::ffff:198.51.100.4 is consumed as one token in a single combined regex pass and rewritten whole to ::ffff:192.0.2.N, with no bare dotted-quad fragment or truncated ::ffff:192 residue left behind"
    requirement: "MDNS-10"
    verification:
      - kind: unit
        ref: "test_ipv6_thread_probe.py#TestAliasMapRedaction::test_ipv4_mapped_ipv6_rewritten_whole"
        status: pass
      - kind: other
        ref: "grep -c _ADDRESS_LITERAL_PATTERN.sub .planning/scripts/ipv6_thread_probe.py (returns 1)"
        status: pass
    human_judgment: false
  - id: D5
    description: "A token that does not parse as an address (a MAC-shaped literal, a clock time, an ISO timestamp) passes through unchanged, and the loopback/unspecified addresses land on IPv6-other rather than raising"
    requirement: "MDNS-10"
    verification:
      - kind: unit
        ref: "test_ipv6_thread_probe.py#TestAliasMapRedaction::test_mac_shaped_token_without_mapping_passes_through_unchanged"
        status: pass
      - kind: unit
        ref: "test_ipv6_thread_probe.py#TestAliasMapRedaction::test_clock_time_passes_through_unchanged"
        status: pass
      - kind: unit
        ref: "test_ipv6_thread_probe.py#TestAliasMapRedaction::test_iso_timestamp_passes_through_unchanged"
        status: pass
      - kind: unit
        ref: "test_ipv6_thread_probe.py#TestAliasMapRedaction::test_loopback_lands_on_ipv6_other"
        status: pass
      - kind: unit
        ref: "test_ipv6_thread_probe.py#TestAliasMapRedaction::test_unspecified_address_lands_on_ipv6_other"
        status: pass
    human_judgment: false
  - id: D6
    description: "--alias-map is opt-in: with no flag, sys.stdout is never wrapped and the probe's output is unchanged from today, proven at both the function boundary (report_records()) and the CLI boundary (main() with a monkeypatched main_async seam, no live network sweep)"
    requirement: "MDNS-10"
    verification:
      - kind: unit
        ref: "test_ipv6_thread_probe.py#TestAliasMapRedaction::test_report_records_prints_raw_serial_without_a_redacting_stream"
        status: pass
      - kind: unit
        ref: "test_ipv6_thread_probe.py#TestAliasMapRedaction::test_main_leaves_stdout_unwrapped_with_no_alias_map"
        status: pass
    human_judgment: false
  - id: D7
    description: "With a valid --alias-map, sys.stdout is a _RedactingStream during the run and the original object again once main() returns, and the same restoration holds when the run raises, so a redacted invocation cannot contaminate a later in-process caller"
    requirement: "MDNS-10"
    verification:
      - kind: unit
        ref: "test_ipv6_thread_probe.py#TestAliasMapRedaction::test_main_wraps_and_restores_stdout_with_a_valid_alias_map"
        status: pass
      - kind: unit
        ref: "test_ipv6_thread_probe.py#TestAliasMapRedaction::test_main_restores_stdout_when_the_run_raises"
        status: pass
      - kind: other
        ref: "runtime stdout-install-seam check driving main() through the real argparse boundary (17-02-PLAN.md Task 2 verify)"
        status: pass
    human_judgment: false
  - id: D8
    description: "A bad --alias-map (path inside the repository, or malformed JSON) exits through argparse's error path rather than a traceback"
    requirement: "MDNS-10"
    verification:
      - kind: unit
        ref: "test_ipv6_thread_probe.py#TestAliasMapRedaction::test_main_rejects_an_alias_map_inside_the_repository"
        status: pass
      - kind: unit
        ref: "test_ipv6_thread_probe.py#TestAliasMapRedaction::test_main_rejects_a_malformed_alias_map_file"
        status: pass
    human_judgment: false

duration: 20min
completed: 2026-09-08
status: complete
---

# Phase 17 Plan 2: Opt-in --alias-map redaction for the IPv6 Thread probe Summary

**A single combined regex substitution rewrites every mapped serial and every parsing address literal onto a per-class documentation-range pseudonym, installed for one run through a restoring `contextlib.redirect_stdout()` seam, with raw output remaining the unconditional default.**

## Performance

- **Duration:** 20 min
- **Started:** 2026-09-08T14:20:00+10:00
- **Completed:** 2026-09-08T14:40:00+10:00
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Added `_load_probe_alias_map()`, reusing `_load_target_alias_map()`'s exact validation contract (Serial normalisation, `validate_alias()`, outside-the-repository guard, duplicate-serial rejection) rather than re-deriving it
- Added `_TranscriptRedactor`, running exactly two forward-only `re.sub()` passes: whole-text serial substitution across all three wire spellings, then a single combined `_ADDRESS_LITERAL_PATTERN` alternation (IPv6 branch first, dotted-quad tried before hex tail) so an IPv4-mapped IPv6 literal such as `::ffff:198.51.100.4` is consumed as one token rather than corrupted across two sequential passes
- Reserved `_REDACTION_PREFIX_BY_CLASS`, a five-entry table mapping each `classify_address()` label to its own sub-range: `IPv4` to `192.0.2.`, `GUA` to `2001:db8:1::`, `IPv6-other` to `2001:db8:2::`, `ULA` to `2001:db8:3::`, `link-local` to `2001:db8:4::`, with the IPv4-mapped form emitted as `::ffff:192.0.2.N` from the IPv4 counter. Every IPv6 sub-range sits inside `2001:db8::/32`; no pseudonym is drawn from operational `fd00::` or `fe80::` space
- Added `_RedactingStream`, a thin per-write wrapper delegating to `_TranscriptRedactor`, and the `--alias-map` CLI flag, whose only effect is a `contextlib.redirect_stdout()` install for the duration of `asyncio.run(main_async(args))`, entered through a `contextlib.ExitStack` so the no-flag path enters no context at all
- Confirmed the redaction is scoped to one run: `sys.stdout` is the original object again once `main()` returns, whether it returned normally or raised, driven through a monkeypatched `main_async` seam so no test performs a live network sweep
- Added 22 new tooling tests to `TestAliasMapRedaction` (15 in Task 1, 7 in Task 2), all passing; full tooling suite now at 161 tests (139 pre-existing + 22 new), full library suite unaffected at 4272 passed

## Task Commits

Each task was committed atomically, bundling its production edit and its tests together (D-08's TDD structure), with the RED phase recorded below before each source change landed:

1. **Task 1: External alias loader and the single-pass transcript redactor with per-class documentation sub-ranges** - `74dfcfc` (feat)
2. **Task 2: The opt-in --alias-map flag and its stdout install seam, with raw output as the default** - `d4ac4df` (feat)

## Files Created/Modified

- `.planning/scripts/ipv6_thread_probe.py` - `_load_probe_alias_map()`, `_TranscriptRedactor`, `_ADDRESS_LITERAL_PATTERN`, `_REDACTION_PREFIX_BY_CLASS`, `_RedactingStream`, the `--alias-map` flag and its restoring install seam
- `.planning/scripts/tests/test_ipv6_thread_probe.py` - `TestAliasMapRedaction` (22 tests): serial substitution, per-class sub-range reservation, IPv4-mapped rewriting, within-run pseudonym stability, zone-suffix preservation, unparseable-token passthrough, loader rejection, raw-by-default at both boundaries, install/restoration on return and on exception, and both CLI rejection paths

## Decisions Made

- Treated an IPv4-mapped IPv6 source address as sharing the IPv4 counter/prefix rather than a separate mapped-form sub-range, since D-11 names `::ffff:192.0.2.x` as the mapped form's target and the mapped shape the cache retains should stay legible as mapped
- Kept `_TranscriptRedactor` as a plain class (not a dataclass) so its computed serial-pattern, pseudonym memo, and per-class counters could be built once in `__init__` from the `aliases` mapping, rather than exposing them as dataclass fields a caller could construct incorrectly
- Verified `contextlib.redirect_stdout()` accepts `_RedactingStream` under pyright standard mode without a `cast` or `type: ignore`, since typeshed's `IO[str]` bound is satisfied structurally by the `write`/`flush`/`isatty` trio the class implements

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None. One local-environment quirk surfaced while running Task 2's own verify gates: the literal `grep -qF "$s" "$F"` command from the plan's verify block fails against this machine's grep when `"$s"` is `"--alias-map"`, because a bare double-dash-prefixed pattern is parsed as an unrecognised long option rather than as the search string. This is a shell/grep argument-parsing quirk, not a source defect; the same check re-run with `grep -qF -- "$s" "$F"` (or any grep implementation that treats a `-F` operand positionally) confirms the string is present. All Task 2 gates were independently confirmed to pass by this route.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `.planning/scripts/ipv6_thread_probe.py` and its test suite are ready for `17-03-PLAN.md` (Wave 2: the real Thread-fleet probe run producing the redacted transcript) and `17-04-PLAN.md`, both of which reuse `--alias-map` directly rather than hand-substituting the committed transcript
- MDNS-10 is not yet fully satisfied at the requirement level: `17-03-PLAN.md` also declares it, and `requirements.mark-complete` will hold the checkbox open until every plan declaring it has a `*-SUMMARY.md`
- No blockers. All verification gates (tooling pytest, full pytest, pyright, ruff check, ruff format, the plan's own runtime redactor-contract and stdout-install-seam checks) pass on the current tree

## Self-Check: PASSED

- `.planning/scripts/ipv6_thread_probe.py` — FOUND
- `.planning/scripts/tests/test_ipv6_thread_probe.py` — FOUND
- Commit `74dfcfc` — FOUND
- Commit `d4ac4df` — FOUND

---
*Phase: 17-fleet-diagnostics-and-the-staleness-control*
*Completed: 2026-09-08*
