# TEST-02: Coordinator Teardown Evidence

**Recorded:** 2026-09-06

## What this settles

The v2.0 Phase 13 deferred item recorded a blocked-executor-worker hang in
`test_non_last_detach_preserves_producer_and_last_detach_reaps_it`. The v2.0
close assumed commit `fc61b98` fixed it. That commit fixes a different test,
`test_forked_child_lazily_starts_a_fresh_coordinator`. The present fix is
`await asyncio.sleep(0.001)` polling of the cross-thread event at
`tests/test_network/test_discovery_coordinator.py:75-76`, landed in
`39bad58`. This document records two observations run under a hard timeout,
with process exit as the signal, that establish whether that fix is
load-bearing rather than coincidental.

## The instrument

Both runs used the observation runner
[`15-TEST-02-observe.py`](15-TEST-02-observe.py), invoked as
`uv run --frozen python 15-TEST-02-observe.py --node <node> --timeout 60
--repo-root <dir> --output <path>`. The runner launches the pytest node in a
child interpreter under `sys.executable`, arming
`faulthandler.dump_traceback_later(60, exit=True)` before importing pytest.
This matters because the recorded failure mode happens *after* pytest
reports a result, inside `threading._shutdown` awaiting
`concurrent.futures.thread._python_exit`, which is past the point where
suite-level `pytest-timeout`'s thread method can act.

The child's exit code is the evidence signal. The child ends with
`raise SystemExit(pytest.main([node, "--no-cov", "-p", "no:cacheprovider"]))`
rather than a bare `pytest.main(...)` call, because `pytest.main()` returns
its status rather than raising: discarding that return value would leave the
child exiting 0 whatever pytest reported, and a mistyped node id, a
collection error or a genuinely failing test would all be recorded as a
clean exit. A negative control against a deliberately invalid node id,
`tests/test_network/test_discovery_coordinator.py::test_this_node_does_not_exist`,
recorded a non-zero child exit code (4, a pytest collection error), proving
the child propagates pytest's own verdict rather than reporting every
invocation as clean. Without that control there would be no way to tell
whether the zero exit code in the first run below means "the process exited
cleanly" or "the instrument reports zero regardless".

## Run 1: the fixed form, against the main checkout

Command:

```
uv run --frozen python .planning/phases/15-coverage-gate-and-test-suite-health/15-TEST-02-observe.py \
    --node 'tests/test_network/test_discovery_coordinator.py::test_non_last_detach_preserves_producer_and_last_detach_reaps_it' \
    --timeout 60 --repo-root . \
    --output .planning/phases/15-coverage-gate-and-test-suite-health/15-TEST-02-record-fixed.json
```

Recorded in
[`15-TEST-02-record-fixed.json`](15-TEST-02-record-fixed.json):

| Field | Value |
|---|---|
| Working directory | `<repo>` (the main checkout) |
| `HEAD` SHA | `0e7f9489a0012b410da097a365cf820ce34d0048` |
| Test file dirty | `false` |
| Watchdog | 60s |
| Parent backstop | 90s |
| Bound fired | none |
| Child exit code | `0` |
| Elapsed | 0.662s |
| Faulthandler banner | `false` |
| Platform | `macOS-26.6.2-arm64-arm-64bit-Mach-O` |
| Python version | `3.14.7` |

The process exited cleanly, well inside the 60 second watchdog. This is a
stronger claim than the test passing: the child interpreter itself
terminated, which is exactly the property the Phase 13 record says the
pre-fix form lacked.

## Run 2: the pre-fix form, against a scratch worktree

The pre-fix `await asyncio.to_thread(self.release.wait)` form was
reintroduced as
[`15-TEST-02-prefix-executor-wait.patch`](15-TEST-02-prefix-executor-wait.patch),
generated inside a throwaway `git worktree` and applied only there. The
tracked `tests/test_network/test_discovery_coordinator.py` was never
modified; the patch is the reproducible artefact.

Command (run from inside the scratch worktree, against the main checkout's
copy of the runner, so the interpreter resolved is the worktree's own synced
environment):

```
uv run --frozen python <main-checkout>/.planning/phases/15-coverage-gate-and-test-suite-health/15-TEST-02-observe.py \
    --node 'tests/test_network/test_discovery_coordinator.py::test_non_last_detach_preserves_producer_and_last_detach_reaps_it' \
    --timeout 60 --repo-root . \
    --output <main-checkout>/.planning/phases/15-coverage-gate-and-test-suite-health/15-TEST-02-record-prefix.json
```

Recorded in
[`15-TEST-02-record-prefix.json`](15-TEST-02-record-prefix.json):

| Field | Value |
|---|---|
| Working directory | `<worktree>` (the scratch checkout, distinct from `<repo>` above) |
| `HEAD` SHA | `fdcbbc449aa0157d371138f3831571cd16713247` |
| Test file dirty | `true` (the reintroduced pre-fix form) |
| Watchdog | 60s |
| Parent backstop | 90s |
| Bound fired | `child_watchdog` |
| Child exit code | `1` |
| Elapsed | 60.053s |
| Faulthandler banner | `true` |
| Platform | `macOS-26.6.2-arm64-arm-64bit-Mach-O` |
| Python version | `3.14.7` |

The in-child watchdog fired at the 60 second mark and forced a hard process
exit (`faulthandler.dump_traceback_later(..., exit=True)`), rather than the
parent's 90 second backstop, so the record shows which of the two bounds
fired. The retained `stderr_tail` names two blocked threads:

```
Thread 0x000000016fbeb000 [asyncio_0] (most recent call first):
  File "<home>/.../threading.py", line 369 in wait
  File "<home>/.../threading.py", line 670 in wait
  File "<home>/.../concurrent/futures/thread.py", line 73 in run
  File "<home>/.../concurrent/futures/thread.py", line 86 in run
  File "<home>/.../concurrent/futures/thread.py", line 119 in _worker
  ...

Thread 0x00000001f691a180 (most recent call first):
  File "<home>/.../threading.py", line 1133 in join
  File "<home>/.../concurrent/futures/thread.py", line 31 in _python_exit
  File "<home>/.../threading.py", line 1548 in <lambda>
  File "<home>/.../threading.py", line 1577 in _shutdown
```

This is precisely the recorded failure mode: a default-executor worker
thread blocked in `threading.Event.wait()` inside
`concurrent.futures.thread`, and the main thread blocked in
`concurrent.futures.thread._python_exit` awaiting that worker inside
`threading._shutdown`. The `stderr_tail` field is the positive evidence for
this classification, not merely the absence of another signal: the exit
code is non-zero *and* the record names exactly the blocked call chain
`deferred-items.md` describes.

## Conclusion

Both runs were bounded, and process exit rather than test result was the
signal in both. The fixed form exits cleanly in well under a second. The
reintroduced pre-fix form hangs, is detected only because the in-child
watchdog forces a hard exit at the 60 second mark, and its thread dump
names the exact blocked worker the deferred item describes. This
establishes that the fix at `tests/test_network/test_discovery_coordinator.py:75-76`,
landed in `39bad58` (not the `fc61b98` the v2.0 close assumed), is
load-bearing rather than coincidental: removing it reproduces the hang on
the first and only attempt, with no repeat runs, per SPEC R6.

Neither run's non-zero exit is ambiguous here: run 2's exit code of 1 carries
both a faulthandler banner and a fired bound (`child_watchdog`), which is the
positive signature of a hang rather than an ordinary test failure. No
classification-by-absence was needed for this pair of records.

The tracked `tests/test_network/test_discovery_coordinator.py` is unchanged
by this investigation. Its only edit was inside the scratch worktree, and
that worktree is removed; `git worktree list` matches the baseline captured
before the experiment.
