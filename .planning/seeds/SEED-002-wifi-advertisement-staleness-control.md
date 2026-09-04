---
seed: 002
planted_during: v2.0 Thread/IPv6 Support (2026-09-04)
trigger_when: A milestone touches discovery liveness, cache TTLs, or consumer guidance about device reachability
audit_acknowledged:
  milestone: v2.0
  at: 2026-09-04
  status: dormant
---

# SEED-002: Run the staleness experiment against WiFi bulbs as a control

## The Idea

Phase 14's THREAD-04 measured how long a disconnected Thread device keeps being
advertised. Run the same protocol against a WiFi bulb, so the Thread figure has a
baseline to be compared against instead of standing alone.

## What Phase 14 Actually Measured

One trial, on 2026-09-04, on this fleet and this border-router set:

- `discover()` (UDP broadcast) lost the device at the **first** poll, t+60s. The bulb
  answers broadcast itself, and it was unpowered, so this leg is unambiguous.
- `discover_mdns()` kept reporting it for **70 minutes** (first absence at poll 70,
  t+4200s; confirmed expiry at poll 72). True disappearance fell between t+4140s and
  t+4200s.
- Restoration took **69.4 seconds** from the power-on edge to both legs reporting
  present again.

## Why a WiFi Control Matters

The 70 minutes is attributable to the Thread path, but only by reasoning, not by
measurement. A WiFi bulb has no SRP registration and no border router answering on its
behalf, so nothing should outlive the device: broadcast discovery ought to lose it
almost immediately, as the Thread device's own UDP leg did.

If that holds, it isolates the lingering as purely an SRP/border-router artefact rather
than anything about LIFX firmware or this library. If it does **not** hold, something
else in the discovery path is caching, and that is a finding about `lifx-async` itself.

The restoration figure deserves the same treatment. 69 seconds covers boot, Thread
rejoin and SRP re-registration. A WiFi bulb only has to boot and associate, so the
difference is the cost of Thread commissioning on the rediscovery path. That is a
number worth having before anyone writes guidance about power-blip recovery.

## The Trap in the Thread Number

Do not treat 70 minutes as a lease. SRP clients renew before expiry, so the measurement
is the **remaining lease at the instant the device died**, which depends on where in its
renewal cycle power was cut. If LIFX takes OpenThread's 7200s default and renews at
halfway, remaining-at-death is distributed roughly between 3600s and 7200s, and 4200s
sits inside that. A single trial cannot distinguish a genuine 70-minute lease from the
2-hour default sampled mid-cycle.

Settling that needs repeated trials, where the maximum observed creeps toward the real
lease, or a direct read of the granted lease from the border router
(`ot-ctl srp server service`, which was impractical here because the OTBR runs inside a
Home Assistant add-on container).

Multiple Thread trials are worth pairing with this WiFi control if the lease value ever
becomes load-bearing for a library decision. Right now it is descriptive only.

## Consumer-Facing Consequence Already Established

Both directions are hazards, and neither is currently documented:

- A dead bulb stays discoverable for over an hour. `discover()` yielding a device is not
  evidence it is reachable.
- A live bulb stays undiscoverable for 69 seconds after power returns. A power blip
  means more than a minute of a device that exists but cannot be found.

## How to Run It

The Phase 14 tooling works unchanged against WiFi hardware. Freeze a roster naming the
WiFi devices, then use the same power-script driven experiment:

```
uv run --frozen python -m scripts.thread_revalidation staleness \
  --session-dir <dir> --alias-map <map> --alias <wifi-alias> \
  --power-off <off.sh> --power-on <on.sh>
```

Expect this to finish in minutes rather than an evening. The three-hour censoring cap
only matters if something is holding the record open, which is exactly the surprising
outcome worth chasing.

## When to Surface

- Consumer guidance is written about discovery liveness or reachability
- Any cache TTL, staleness threshold or liveness check is proposed in the discovery layer
- A milestone revisits `discover()`'s merged-source behaviour
- Someone proposes treating the Thread staleness figure as a constant
