---
phase: 17-fleet-diagnostics-and-the-staleness-control
reviewed: 2026-09-09T00:00:00Z
depth: deep
iteration: 4
files_reviewed: 5
files_reviewed_list:
  - .planning/scripts/ipv6_thread_probe.py
  - .planning/scripts/tests/test_ipv6_thread_probe.py
  - .planning/scripts/thread_revalidation.py
  - .planning/scripts/tests/test_thread_revalidation.py
  - tests/test_network/test_mdns/test_phase_contract.py
findings:
  critical: 0
  warning: 0
  info: 2
  total: 2
status: clean
---

# Phase 17: Code Review Report (re-review, iteration 4 — closing pass)

**Reviewed:** 2026-09-09T00:00:00Z
**Depth:** deep
**Files Reviewed:** 5
**Status:** clean

## Summary

Fourth and final pass over the same five files, closing out the `--fix --auto` loop. Iteration 3
(`892cc4a`, `26cb8ad`) fixed iteration 2's one Warning and two Info findings; this pass
independently re-verifies all three rather than accepting `17-REVIEW-FIX.md`'s account, and finds
no defect surviving above Info in any of the five files.

`src/`, `.planning/scripts/measurement_support.py`, `17-EVIDENCE/`, and
`.planning/milestones/v2.0-phases/` remain absent from every diff since iteration 2's review point
(`96ae951..HEAD` for the first three, `51beea7..HEAD` for the milestone tree) — confirmed with
`git diff --stat`, not assumed. The three frozen staleness constants
(`STALENESS_POLL_INTERVAL_S = 60.0`, `STALENESS_CONFIRM_ABSENT_POLLS = 3`,
`STALENESS_CAP_S = 10800.0`) are unchanged in `measurement_support.py`. `thread_revalidation.py`,
its test file, and `test_phase_contract.py` were not touched by either of iteration 3's commits
(both are scoped entirely to `ipv6_thread_probe.py` and its test file per `git show --stat`), so
this pass carries iteration 2's independent deep verification of those three files forward rather
than re-deriving it from nothing, while still re-reading the restoration OR-semantics and
second-leg-bound logic directly to confirm nothing has drifted. `uv run --frozen pytest
.planning/scripts/tests` is green (687 passed, up from iteration 2's 679 by exactly the 8 tests the
two fix commits added). `uv run ruff check` is clean on all five files, and `uv run pyright` (full
repo, using the project's own `pyproject.toml` include list rather than an ad hoc per-file
invocation, which produces false-positive noise on test-double signatures the project does not
type-check) reports 0 errors.

**All three carried-forward findings were independently re-verified against the live code, not
read from `17-REVIEW-FIX.md`:**

- **WR-01 (iteration 2): the fail-closed check skipped `KeyboardInterrupt` and any uncaught
  exception — confirmed resolved.** `_warn_if_tokens_went_unmapped()` now runs from a `finally`
  wrapping the whole `try`/`except KeyboardInterrupt` block in `main()`. Traced both paths by hand:
  an uncaught non-`KeyboardInterrupt` exception propagates through the `with` block (which still
  restores `sys.stdout` correctly), the `finally` runs and prints the warning if applicable, and
  the *same* exception continues propagating afterward — confirmed unaltered by
  `test_main_restores_stdout_when_the_run_raises`, which asserts `pytest.raises(RuntimeError, ...)`
  around `probe.main()`. The `KeyboardInterrupt` path is caught inside the inner `try`, sets
  `interrupted = True`, and the `finally` still runs before `main()` returns. The unit-level test
  `test_unmapped_warning_survives_being_called_from_a_finally` directly proves the extracted
  function neither raises nor swallows an in-flight exception when called from a `finally`. See
  IN-01 below for the one narrow gap left in this area: the returned exit code, not the warning
  itself.
- **IN-01 (iteration 2): the boundary class was wider than the address pattern's, a latent miss
  risk — confirmed resolved, and confirmed non-regressive.** Both `_serial_pattern` and
  `_UNMAPPED_IDENTIFIER_PATTERN` are narrowed from `[0-9A-Za-z:-]` to `[0-9A-Fa-f:-]`. Loaded the
  pre-narrowing code (`892cc4a`) and the current code side by side via `importlib` (distinct module
  names, to avoid `sys.modules` caching hiding the difference) and ran the exact adjacency cases:
  `xd073d5aa11bb` and `d073d5aa11bby` now substitute (`'xdevice-a'`, `'device-ay'`) where the old
  code left them raw, and `xd073d5ccddee` is now counted by the unmapped detector (1) where the old
  code missed it (0) — the new regression tests genuinely fail against the pre-fix code, not
  vacuously. Separately re-ran WR-01's original (iteration 1) corruption repro cases,
  `aad073d5aa11bbbb` and `1234d0:73:d5:aa:11:bbcd`, against the live code: both are still left
  fully unchanged, because the boundary still blocks on a hex neighbour, which is the adjacency
  that actually occurs in this file's own call sites (SPEC amendment A7's firmware SRV labels).
  Every match is either the complete alternation string or nothing — the lookaround boundaries are
  zero-width, so narrowing the boundary class can only ever gain substitutions, never partially
  overlap or corrupt one; there is no code path by which the narrower class produces a broken
  hybrid the wider class would have avoided. The code's own comments (lines 338–346, 148–152) state
  the miss-vs-hybrid trade-off honestly and match what the code does. Confirmed detector/substituter
  symmetry directly: every adjacency case that would substitute is *not* reported unmapped, and
  every adjacency case that would not substitute (the hex-embedded WR-01 cases) *is* reported
  unmapped when the serial isn't in the map, matching `test_unmapped_detector_uses_the_same_
  boundaries_as_substitution`.
- **IN-02 (iteration 2): non-IPv4 pseudonym classes had no capacity ceiling — confirmed resolved,
  and confirmed to close the emitter/backstop contract exactly, in both directions.**
  `_IPV6_SUBRANGE_CAPACITY = 0xFFFF` now gates the `else` branch of `_pseudonym_for()` the same way
  `_IPV4_DOCUMENTATION_CAPACITY` already gated the IPv4 branch. Extracted the staged-diff backstop's
  actual whitelist regex verbatim from both `17-03-PLAN.md` and `17-04-PLAN.md` (character-identical
  in both, as the plans claim) — `^(?:2001:db8:[1-4]::[0-9a-f]{1,4}(?:%...)?|::ffff:192\.0\.2\.
  [0-9]{1,3})$` — and confirmed `[0-9a-f]{1,4}` is exactly a one-hextet, 1-to-4-digit cap, matching
  `0xFFFF` precisely; the IPv4 side's `[0-9]{1,3}` similarly matches the 254-address ceiling exactly.
  Reproduced the pre-fix behaviour directly: loading `892cc4a`'s code and forcing the `GUA` counter
  to `0xFFFF` before redacting one more address emits `2001:db8:1::10000` (five hex digits, silently
  outside the whitelist) with no exception; the current code raises `ValueError` at that same point.
  The new regression test therefore also genuinely fails against the pre-fix code.

**No new findings above Info.** Two narrow, non-blocking observations surfaced while directly
verifying WR-01's fix in `main()`'s exit-code path (iteration-4 attention item 3); both are
documented design choices confirmed correct by tracing and by the commit message, not defects, and
neither is worth blocking on:

## Info

### IN-01 (iteration 4): the interrupted-vs-unsafe-transcript exit-code precedence is explained only in the commit message, not in the code

**File:** `.planning/scripts/ipv6_thread_probe.py:1822-1826` (`main()`)

**Issue:** `_warn_if_tokens_went_unmapped()` in the `finally` correctly prints the warning on every
exit path, including `KeyboardInterrupt` — that gap is fully closed. But the code immediately after
the `try`/`finally`:

```python
if interrupted:
    return 130
if unsafe_transcript:
    return 1
return exit_code
```

gives `interrupted` unconditional priority: if a run is Ctrl-C'd *and* an unmapped token was
printed, the operator sees the stderr warning (correct — the `finally` already guarantees that),
but the process exit code is `130`, not `1`. `892cc4a`'s commit message states this is deliberate
("Interrupt still exits 130, which the capture gate already treats as re-run-do-not-capture"), and
that reasoning holds: nothing downstream distinguishes "interrupted because of X" from "interrupted
because of Y", so 130 unconditionally routing to "re-run, do not capture" is functionally sound
regardless of whether an unmapped token was also seen. No in-code comment states this precedence
choice, though — the comment above the `finally` explains only why the warning itself now fires on
every path, not why the two boolean outcomes are ordered the way they are afterward. A future
change to either branch (for example, adding a third terminal state) has no comment nearby to warn
it against silently reordering these two checks.

**Fix (optional, documentation only):** A one-line comment immediately above `if interrupted:`
stating the precedence is deliberate and citing the same reasoning already in the commit message
(the capture gate treats 130 as re-run-regardless-of-cause) would make this self-contained for a
future reader who does not have `git log` open.

### IN-02 (iteration 4): the commit message's "driven through main() end to end" claim for the interrupt path is not backed by a persisted automated test

**File:** `.planning/scripts/tests/test_ipv6_thread_probe.py` (no test at this scope currently
exists)

**Issue:** `892cc4a`'s commit message states "the interrupt path was driven through main() end to
end" as part of its verification account. Searched the full test file for any `main()`-level test
that raises `KeyboardInterrupt` from a stubbed `main_async()`: none exists. The four tests added in
that commit exercise `_warn_if_tokens_went_unmapped()` directly (count-and-never-the-token, silent
without a map, silent when fully mapped, and safe-from-a-`finally`) — solid unit coverage of the
extracted function's own contract, and sufficient to prove it does not raise or swallow an
exception, but none of them drives `probe.main()` itself through a `KeyboardInterrupt` with an
unmapped token already printed and asserts exit code `130` plus the stderr message, the way
`test_main_fails_closed_when_an_unmapped_token_was_printed_raw` does for the plain non-interrupt
fail-closed case. The claim in the commit message most likely describes a manual verification step
taken by the fix author rather than something codified as regression coverage. The underlying
behaviour was independently confirmed correct in this review by direct code trace (see the WR-01
carry-forward note above), so this is a traceability gap between what the commit message asserts
and what is checked on every future change, not a live defect.

**Fix (optional hardening):** Add one test at the `main()` scope: monkeypatch `main_async()` to
print an unmapped token and then raise `KeyboardInterrupt`, assert `probe.main()` returns `130`,
and assert the "N unmapped identifier-shaped token(s)" message is present in `capsys`'s stderr.

---

_Reviewed: 2026-09-09T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
_Iteration: 4 (closing pass — re-review after `17-REVIEW-FIX.md` iteration 1 and its two follow-up
fix commits `892cc4a`, `26cb8ad`)_
