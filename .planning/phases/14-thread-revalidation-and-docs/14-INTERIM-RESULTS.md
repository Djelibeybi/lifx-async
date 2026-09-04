# Phase 14 interim physical results

**Session:** `seed-001`
**Revision that produced this evidence:** `687c8d8`
**Collected:** 2026-09-04, 17:42 to 20:23 AEST
**Roster:** 8 devices across Light, MultiZoneLight, MatrixLight (x2) and CeilingLight

This records the physical evidence collected before the animation stage was
deferred. It is deliberately not a Task 3 product: `generate` refuses to write
`14-SUMMARY.json`, `14-CLASS-LEDGER.json` or `14-REPORT.md` while any class is
incomplete, and animation evidence is incomplete by decision rather than by
failure. The raw journals are committed alongside this file as the record.

## What is complete

### THREAD-01 — merged and mDNS discovery

Six paired rounds, both sources, all 12 arms recorded.

**Every round found all 8 devices on both legs.** No partial round, no source
disagreement, no missing alias.

### THREAD-02 — request and retransmission behaviour

800 trials, 100 per device.

| Outcome | Count |
|---|---|
| `completed` | 800 |

No timeouts, no failures, no retransmissions, and no `power_out_of_range`.

Acknowledgement round-trip across all 800 trials:

| min | p50 | p95 | max |
|---|---|---|---|
| 31.5 ms | 43.9 ms | 94.3 ms | 326.8 ms |

Two things worth carrying forward. The p50 of 43.9 ms sits **below** the ~100 ms
ack RTT the v1.1 WiFi spike series measured under streaming load, so Thread is
not the latency penalty that series' assumptions implied. The max of 326.8 ms
does exceed the 200 ms "an acked bulb has answered by now" constant, so that
constant is not safe as an upper bound on this transport even though the median
is comfortably inside it.

### Thread connection bit

`thread_connection` was `true` on all 800 trials. This is the first validation of
the frame-address bit parsing added in `b4ae1b8` against real Thread hardware;
until now it was proven only against constructed headers.

### THREAD-04 — observed advertisement staleness

One trial, `disposition: confirmed_expiry`.

| Observation | Value |
|---|---|
| `discover()` lost the device | poll 1, t+60s |
| `discover_mdns()` first absence | poll 70, t+4200s |
| Confirmed expiry | poll 72, t+4320s |
| True disappearance | between t+4140s and t+4200s |
| Restoration after power-on | 69.4 s |

The UDP leg losing the device at the first poll is what makes this clean: the
bulb answers broadcast itself and was unpowered, so everything lingering past
t+60s is the border router alone.

**Do not read 4200s as a lease.** SRP clients renew before expiry, so this is the
remaining lease at the instant power was cut, which depends on where in the
renewal cycle the device died. If LIFX takes OpenThread's 7200s default and
renews at halfway, remaining-at-death falls roughly between 3600s and 7200s, and
4200s sits inside that. A single trial cannot distinguish a genuine 70-minute
lease from the 2-hour default sampled mid-cycle. See
`.planning/seeds/SEED-002-wifi-advertisement-staleness-control.md`.

Both directions are consumer-facing hazards and neither is currently documented:
a dead bulb stays discoverable for over an hour, and a live bulb stays
undiscoverable for 69 seconds after power returns. `discover()` yielding a device
is not evidence that the device is reachable, in either direction.

## What is deferred

### THREAD-03 — animation

One attempt was recorded, for `LIFX-Candle-C-1`, with `restored: true` and
`restoration_verified: false`. The stage was then stopped by decision, not by the
failure.

The animation payload is not fit for the measurement it claims to make:

```python
frame = [(0, 0, 0, 3500)] * animator.pixel_count
return lambda: animator.send_frame(frame)
```

Every call sends the **identical** frame, and that frame is brightness 0. Firmware
that short-circuits an unchanged frame, or skips the LED driver for all-zero
brightness, does almost no work, so the transport figures would look good
precisely because nothing downstream of the packet parser had to happen. The
existing docstring defends this as observing "transport-side behaviour only",
which is the flaw rather than its justification.

A sound measurement needs frames whose content varies per frame, at real
brightness, deterministically derived from the frozen session seed so the
evidence stays reproducible. Whether the stage should also power devices on for
the observation is unresolved: an unpowered bulb renders nothing regardless, so
buffer-only measurement can never speak to visual effectiveness.

The `restoration_verified: false` result is also unexplained, and the journal
records only the boolean rather than which facet mismatched, so it cannot be
diagnosed after the fact. `restore_and_verify_device_state()` recaptures
immediately after the restore commands with no settle time and then demands exact
equality, which for a Candle means 30 tile colours written and instantly read
back. A race there is plausible but was never confirmed.

### THREAD-05 — per-class closure

Blocked by THREAD-03, not by its own evidence.
`derive_class_ledger_from_roster()` requires
`_alias_has_physical_animation_attempt()` for every alias before a class closes
`evidence_backed`, so no class can close while animation is deferred.

Closing the phase on the evidence above requires deciding whether class closure
should depend on an animation attempt at all. The argument for dropping the
dependency is that discovery and request evidence are what actually demonstrate
Thread reachability and reliability, and that animation over a mesh was never the
point of Thread support.

## D-16 is disproportionate and remains unfixed

D-16 currently says a restoration failure requires restarting the complete
physical protocol under a new session identity, with earlier records preserved
but not satisfying closure. That would have discarded a 70-minute staleness
experiment over a latent tile-buffer difference on a bulb that was switched off.
Discovery, requests and staleness are all collected before any animation runs, so
a restoration failure during animation cannot retroactively confound them. The
halt-immediately and operator-confirmed-recovery clauses are sound; the
session-restart clause is not.
