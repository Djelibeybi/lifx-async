---
status: complete
phase: 02-discovery-rebroadcast
source: [02-01-SUMMARY.md, 02-02-SUMMARY.md]
started: 2026-07-17T14:48:01Z
updated: 2026-07-17T15:10:40Z
---

## Current Test

[testing complete]

## Tests

### 1. Full-Fleet Discovery in a Single Call
expected: A single `discover_devices()` call against the production network finds the full fleet (~73 devices), not the partial 27-48/73 the single-broadcast baseline returned. No manual re-run loop needed to catch devices behind other APs.
result: pass

### 2. No Duplicate Devices Across the Re-broadcast Window
expected: Even though GetService is now broadcast up to 6 times per discovery, each device is yielded exactly once. No serial appears twice in the results, and no duplicate `Device` objects reach your code.
result: pass

### 3. Discovery Completion Time
expected: Discovery on a populated network completes in roughly 11-12 seconds (the full escalating schedule plus idle wind-down), and always inside the 15 s `DISCOVERY_TIMEOUT`. It should feel slower than the old single-broadcast call but must never hang or overrun the cap.
result: pass
note: "User: completes in time and does not feel slower than before."

### 4. Quiet-Network Exit Timing
expected: Running discovery on a network with no LIFX devices (or a filter that matches nothing) still exits promptly on the idle deadline (~4 s) rather than being stretched out by the re-broadcasts. Re-sends must not reset the idle window and hold the call open.
result: pass
source: automated
note: "User has no LIFX-free network to test manually. Behaviour is deterministically covered by passing automated tests: test_quiet_slice_rebroadcast_then_idle_exit (idle-exit timing) and test_send_does_not_reset_idle_window (re-sends do not reset the idle window). Both green in the 10/10 rebroadcast-test re-run."

### 5. Targeted Finders Benefit Too
expected: `find_by_serial()`, `find_by_label()`, and `find_by_ip()` share the re-broadcast code path, so they now reliably locate a device on a distant AP that previously needed several attempts. Each should find its target on the first call.
result: pass
note: "User's PC is wired, so all devices are on distant APs by definition; test 1's single-call full-fleet discovery already exercised this path. Finders share the identical _discover_with_packet re-broadcast loop."

### 6. DISC-03 measurement harness drives the real discover_devices() over N rounds, compares against the spike 005 baseline, and writes a machine-readable results JSON with a 0/1/2 exit-code contract
expected: DISC-03 measurement harness drives the real discover_devices() over N rounds, compares against the spike 005 baseline, and writes a machine-readable results JSON with a 0/1/2 exit-code contract
result: pass
source: automated
coverage_id: D1

### 7. 6-round measurement against the 73-device production fleet: median per-round coverage equals the full roster (73/73), versus the recorded single-broadcast baseline of 27/48/73
expected: 6-round measurement against the 73-device production fleet: median per-round coverage equals the full roster (73/73), versus the recorded single-broadcast baseline of 27/48/73
result: pass
source: automated
coverage_id: D2

## Summary

total: 7
passed: 7
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

[none yet]
