---
phase: 17-fleet-diagnostics-and-the-staleness-control
fixed_at: 2026-09-09T00:00:00Z
review_path: .planning/phases/17-fleet-diagnostics-and-the-staleness-control/17-REVIEW.md
iteration: 1
findings_in_scope: 5
fixed: 5
skipped: 0
status: all_fixed
---

# Phase 17: Code Review Fix Report

**Fixed at:** 2026-09-09T00:00:00Z
**Source review:** .planning/phases/17-fleet-diagnostics-and-the-staleness-control/17-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 5 (fix scope: all — Critical, Warning, Info)
- Fixed: 5
- Skipped: 0

All five findings were fixed, each in its own commit so any can be reverted independently.
`src/`, `.planning/scripts/measurement_support.py`, `.planning/milestones/`, and every
planning artefact (PLAN/SPEC/SUMMARY/SECURITY/VERIFICATION) are untouched — verified with
`git diff --name-only 96ae951 HEAD`, which lists only `.planning/scripts/ipv6_thread_probe.py`,
`.planning/scripts/thread_revalidation.py`, and their two test files. Both v2.0's committed
evidence (`.planning/milestones/v2.0-phases/14-thread-revalidation-and-docs/14-EVIDENCE/`) and this
phase's own (`.planning/phases/17-fleet-diagnostics-and-the-staleness-control/17-EVIDENCE/`) were
loaded through `reload_staleness_events()`/`load_manifest()`/`generate_summary()`/`generate_report()`
after every fix and still parse and validate — demonstrated directly, not assumed; this also proved
the WR-02 fix end-to-end, since the phase's own evidence carries exactly the two values the finding
cited (`restoration_discover_s=15.530575042008422`, `restoration_mdns_s=14.557117625008686`) and both
now surface in the summary/report. `uv run --frozen pytest --tooling` is green (4951 passed, 12
deselected — the opt-in benchmark tests). `uv run ruff check`/`ruff format --check` and `uv run
pyright` (full repo) are both clean.

## Fixed Issues

### WR-01: Serial-substitution regex has no boundary anchors, unlike the address regex

**Files modified:** `.planning/scripts/ipv6_thread_probe.py`, `.planning/scripts/tests/test_ipv6_thread_probe.py`
**Commit:** `7682501`
**Applied fix:** Wrapped `_TranscriptRedactor._serial_pattern`'s alternation in the same
hex/separator-aware lookaround boundaries `_ADDRESS_LITERAL_PATTERN` already carries
(`(?<![0-9A-Za-z:-])...(?![0-9A-Za-z:-])`), so a mapped 12-character serial can no longer match as a
substring of a longer all-hex token. Added two regression tests reproducing the exact finding
cases — `aad073d5aa11bbbb` and `1234d0:73:d5:aa:11:bbcd` both now pass through unchanged with a
mapped `d073d5aa11bb` — plus a whole-token control test proving the fix does not regress ordinary
matching. All pre-existing `TestAliasMapRedaction` tests still pass unchanged.

### WR-02: New per-leg restoration fields are dropped by `generate_summary()`/`generate_report()`

**Files modified:** `.planning/scripts/thread_revalidation.py`, `.planning/scripts/tests/test_thread_revalidation.py`
**Commit:** `9306a0a`
**Applied fix:** Added `restoration_discover_s`/`restoration_mdns_s` to the `staleness_summary` dict
comprehension inside `generate_summary()`, using `.get()` so a legacy row committed before this phase
(missing both keys entirely) still summarises without a `KeyError` — verified directly by loading
v2.0's committed staleness JSONL through the fixed code path, which returns `None` for both fields
rather than raising. Two new tests: one asserts the summary and the Markdown report both surface the
per-leg values for a row that carries them (using the exact reproduction values from the finding),
and one constructs a v2.0-shaped legacy row with the keys deleted and asserts it still summarises
with `None`/`None`.

### IN-02: IPv4 pseudonym pool exhausts at 254 distinct addresses and raises mid-write

**Files modified:** `.planning/scripts/ipv6_thread_probe.py`, `.planning/scripts/tests/test_ipv6_thread_probe.py`
**Commit:** `69bfb32`
**Applied fix:** Chose "widen the pool" over "catch and degrade gracefully" — degrading gracefully
would mean either falling back to raw (unacceptable: reintroduces a privacy leak) or a placeholder
that's indistinguishable from a real pseudonym (worse for a reader trying to tell classes apart), so
neither is actually safer than a clear, fail-closed raise. `_pseudonym_for()` now cycles through all
three RFC 5737 IPv4 documentation `/24`s (`192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`) rather
than just the first, giving 762 addresses instead of 254 — comfortable headroom over the project's
~73-device fleet. The existing 254-address ceiling still exists at 762 and still raises, but now with
a message naming the total capacity and range count rather than a bare `ValueError`. Two new tests:
one proves the pool cycles into the second range once the first 254 are exhausted, and one drives all
762 addresses to confirm the clear message fires exactly once capacity is genuinely exhausted.

### IN-03: Bounded second-leg restoration wait can soft-overrun its documented bound

**Files modified:** `.planning/scripts/thread_revalidation.py`, `.planning/scripts/tests/test_thread_revalidation.py`
**Commit:** `d612bf4`
**Applied fix:** Chose "tighten" over "document as approximate" — the finding's own fix section
offered a concrete mechanism ("check the deadline again... so the last iteration cannot itself run a
full 90s past the bound"), and a `_STALENESS_DISCOVERY_TIMEOUT_S`-derived worst-case figure was
already available, so tightening cost little and produces an honestly-documented figure rather than
a caveat. Implemented as a pure predicate, `_second_leg_poll_would_overrun_bound(now, deadline,
poll_worst_case_s)`, extracted specifically so the boundary arithmetic is unit-testable without
touching the real monotonic clock or asyncio's own loop timing (patching `time.monotonic()` globally
to fake a ~90s-wide window risked destabilising `asyncio`'s own scheduling in-process). The phase-2
loop now refuses to start a poll unless there is enough headroom (`_POLL_WORST_CASE_S = 2 *
_STALENESS_DISCOVERY_TIMEOUT_S`) left before the deadline for a full worst-case `_poll()` to
complete. **Behaviour change a reader should notice:** the loop can now stop up to ~90s *before*
`_RESTORATION_SECOND_LEG_BOUND_S` in the worst case (never after), trading a small amount of
observation window for a bound that is actually a hard ceiling rather than "up to 900s, usually, plus
a possible ~90s tail." Five new unit tests exercise the predicate directly (exact-headroom boundary,
one-second-short refusal, well-before-deadline, at-and-after deadline), plus the two existing
`TestCliStalenessPowerScripts` restoration tests (including the one that monkeypatches the bound to
`0.0`) still pass unchanged, confirming the tightening does not regress the documented "OR-based
first leg, bounded second leg, `None` rather than a hang" behaviour A8 authorised.

### IN-01: `--alias-map` redaction is fail-open for identifiers absent from the map

**Files modified:** `.planning/scripts/ipv6_thread_probe.py`, `.planning/scripts/tests/test_ipv6_thread_probe.py`
**Commit:** `518931c`
**Applied fix:** This is the one behaviour change in this set, applied deliberately and narrowly.
Two things were preserved on purpose: (1) the raw-by-default path when **no** `--alias-map` is given
is untouched — `test_main_leaves_stdout_unwrapped_with_no_alias_map` still passes unchanged, and the
new detection logic never runs in that mode; (2) `redact()` itself still returns the token unchanged
in place (the existing `test_mac_shaped_token_without_mapping_passes_through_unchanged` test, run
against an empty-map `_TranscriptRedactor` directly, is untouched and still passes) — this is D-10's
documented hand-off to the staged-diff identity backstop, not something this fix removes.

**What changed:** when `--alias-map` *is* supplied, `redact()` now also scans the fully-substituted
text (after both existing passes) for identifier-shaped tokens that survived unmapped, using the same
boundary anchors WR-01 gave the serial pattern and the same D-23 discriminator the staged-diff
backstop uses elsewhere in this phase (a token must carry at least one `a`-`f` hex digit, since every
LIFX serial begins `d073d5` and cannot be all-decimal — this keeps nanosecond-derived decimal values
from being falsely flagged). Only a **count** of distinct tokens is ever recorded, never the token
text itself. `main()` checks that count after the run finishes (deliberately outside the
`redirect_stdout` context, so the check can never itself be redacted or fire mid-print the way IN-02's
old crash did) and, if non-zero, prints a stderr message naming the count and exits 1 — the run's own
stdout output is left exactly as printed (still committable-in-appearance, just not safe to actually
commit), and the message tells the operator to extend the alias map and re-run rather than naming
which tokens leaked.

**Why this is additive, not a replacement:** the staged-diff identity backstop
(`AGENTS.md`: "Before staging hardware or network evidence, inspect the staged diff...") remains the
actual gate before anything is committed. This fix gives the operator a much earlier, louder signal
at run time instead of relying solely on that later manual/scripted step — it does not remove or
weaken the existing backstop.

**Test coverage:** nine new tests — five exercising `_TranscriptRedactor.unmapped_token_count`
directly (unmapped token counted but still passes through unredacted; two spellings of one unmapped
serial count once; an all-decimal 12-digit token is never counted; a *mapped* serial does not count;
a real address whose hex digits happen to collide with a serial's is not falsely counted, since it was
already replaced with a pseudonym before the unmapped scan runs) and one end-to-end `main()` test
proving the CLI exits 1 with the count-only stderr message and does not print the leaked token to
stderr, when a run prints an unmapped MAC-shaped token through a `--alias-map`-wrapped stdout.

## Skipped Issues

None — all five in-scope findings were fixed.

---

_Fixed: 2026-09-09T00:00:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
