# Phase 13 Deferred Items

## Open

None.

## Resolved

### Coordinator teardown test leaves a blocked executor worker

- **Discovered during:** Plan 13-03 whole-repository verification
- **Introduced before this plan:** `tests/test_network/test_discovery_coordinator.py` at commit `fc9737d4`; the same code is present at the Plan 13-03 starting commit `1c5eb1c`.
- **Evidence:** `test_non_last_detach_preserves_producer_and_last_detach_reaps_it` passes its assertions, then pytest remains in `threading._shutdown` waiting for `concurrent.futures.thread._python_exit`. A focused reproduction reports `1 passed in 0.02s` but does not exit until interrupted.
- **Root cause:** `_GatedDiscoveryProducer` blocks a default-executor worker in `asyncio.to_thread(self.release.wait)`. The test closes the final subscription without first setting `producer.release`, so cancellation closes the async producer but cannot cancel the already-running `threading.Event.wait` call.
- **Resolution:** Replaced the test-only executor wait with cancellation-safe asynchronous polling of the cross-thread event. The final-detach test additionally asserts that the release gate remains unset, preserving proof that subscriber cancellation itself closes the producer.
- **Verification:** The bounded focused reproducer exits normally with 1 passed; the affected Wave 2 selection exits with 186 passed and 1 skipped; the full repository suite exits with 4,232 passed, 1 skipped, and 12 deselected.
- **Scope decision:** Deferred under the executor scope boundary because the defect predates Plan 13-03 and is in the Plan 13-02 coordinator test surface. Plan 13-03 assertions, focused verification, Ruff, and Pyright are green.
- **Load-bearing confirmation (v2.1 Phase 15, TEST-02):** the fix that closed this item is
  `await asyncio.sleep(0.001)` polling at
  `tests/test_network/test_discovery_coordinator.py:75-76`, landed in commit `39bad58`, not the
  `fc61b98` the v2.0 close assumed (`fc61b98` fixes a different test,
  `test_forked_child_lazily_starts_a_fresh_coordinator`). Two bounded process-exit observations
  settled whether the fix is load-bearing: against the fixed form on the main checkout, the child
  process exits cleanly (exit 0, no faulthandler banner, 0.66s against a 60 second watchdog);
  against the pre-fix `await asyncio.to_thread(self.release.wait)` form, reintroduced once in a
  scratch `git worktree` and never committed to the tracked test file, the child hangs and the
  in-child watchdog forces a hard exit at 60 seconds, with a faulthandler dump naming a
  default-executor worker blocked in `threading.Event.wait()` under
  `concurrent.futures.thread`, and the main thread blocked in `_python_exit` awaiting
  `threading._shutdown`. This is exactly the failure mode described above. Full evidence,
  including both machine-readable records, is at
  `.planning/phases/15-coverage-gate-and-test-suite-health/15-TEST-02-EVIDENCE.md`.
  status: resolved and confirmed load-bearing
