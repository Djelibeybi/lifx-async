---
status: complete
phase: 03-retry-schedule-reshape
source: [03-01-SUMMARY.md, 03-02-SUMMARY.md, 03-03-SUMMARY.md]
started: 2026-07-17T15:18:28Z
updated: 2026-07-17T15:19:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Real-Hardware Zero-Loss Measurement (RETRY-02)
expected: Reshaped retry sends ~1 packet/trial on a healthy link (recorded: 60 trials, 0 failures, mean/median 1.0, ~8ms median latency vs spike 002 baseline of 1.37 packets/trial, 62ms). The earlier run's mean 1.083 FAIL is attributed to a genuine two-trial WiFi loss event, not a duplicate-packet regression. Sanity-check that interpretation and confirm the zero-loss result.
result: pass
coverage_id: D2 (03-03)

### 2. Floored first-attempt window (RETRY-01)
expected: REQUEST_RETRANSMIT_GAPS Photons-shaped schedule constant added to const.py, floors the first-attempt window at 0.2s.
result: pass
source: automated
coverage_id: D1 (03-02)

### 3. Listen-during-backoff engine (RETRY-02)
expected: Shared _transmit_and_listen() engine — retransmit-while-listening, no blind sleeps between attempts.
result: pass
source: automated
coverage_id: D2 (03-02)

### 4. Wall-time deadline honoured (RETRY-03)
expected: Single monotonic wall deadline honoured on both GET and ACK paths — failing requests complete at timeout, not timeout+overrun.
result: pass
source: automated
coverage_id: D3 (03-02)

### 5. Shared-queue correlation (RETRY-04)
expected: Shared-queue correlation across all issued sequences on both GET and ACK paths — late replies accepted, duplicates silently discarded.
result: pass
source: automated
coverage_id: D4 (03-02)

### 6. Existing callers unmodified
expected: Existing callers (12+ mock-seam tests in test_connection.py, all StateUnhandled emulator tests) pass unmodified against the reshaped engine.
result: pass
source: automated
coverage_id: D5 (03-02)

### 7. Branch coverage + full-suite regression
expected: 100% branch-patch coverage on the new/changed connection.py ranges; full suite green (2563 passed) with no regressions.
result: pass
source: automated
coverage_id: D6 (03-02)

### 8. Zero-loss harness contract
expected: Standalone uat_zero_loss.py harness drives the shipped DeviceConnection.request() with a send-count spy, fixed 0/1/2 exit-code contract, and a reachability guard (--help exits 0, no packets sent; ruff + pyright clean).
result: pass
source: automated
coverage_id: D1 (03-03)

## Summary

total: 8
passed: 8
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

[none yet]
