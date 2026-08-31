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
