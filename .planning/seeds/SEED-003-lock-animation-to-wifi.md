---
seed: 003
planted_during: v2.0 Thread/IPv6 Support (2026-09-04)
trigger_when: A milestone touches src/lifx/animation/ or extends the animation public API
---

# SEED-003: Lock `Animator` to WiFi devices

## The Idea

Restrict `Animator` (`src/lifx/animation/`) so it refuses, or clearly degrades, when asked
to drive a Thread device. Right now `Animator.for_light()` / `for_multizone()` /
`for_matrix()` build and run against any device that reaches the required protocol
surface, WiFi or Thread alike, with no connectivity check anywhere in the construction
path.

## Why This Matters

Thread does not have the bandwidth to sustain animation at usable or smooth frame rates,
and pushing that volume of data onto a Thread mesh is bad practice regardless of what any
single measurement would show — every hop adds latency and consumes shared mesh airtime
that other Thread traffic (including the device's own SRP/mDNS keepalive) depends on.
This is a decision that follows from how Thread mesh networking works, not from a
performance number this project measured and could be argued down: even a Thread mesh
with zero interference would still be the wrong transport for a 20 FPS pixel stream.

Phase 14 (THREAD-03) accordingly declined to build out per-class Thread animation
evidence and recorded animation as an explicit scope boundary instead of a measurement.
One physical observation exists from before that scope decision: alias `LIFX-Candle-C-1`
completed all three declared rate observations (1, 2, and 5 FPS) without failing, which is
worth keeping as "Thread carries the frames without falling over" — explicitly not as
evidence that Thread animation is usable, smooth, or fit for a real effect. See
`.planning/phases/14-thread-revalidation-and-docs/14-CONTEXT.md`'s D-09 through D-16
amendment and `.planning/REQUIREMENTS.md`'s rescoped THREAD-03 for the full reasoning.

Today, nothing in `Animator` or its `for_*` factories stops a caller from pointing it at a
Thread device. A consumer who does so gets no warning that they are about to sustain
20 FPS of pixel traffic over a mesh designed for sparse, low-duty-cycle control messages.

## What An Implementation Would Need To Decide

- **How is a Thread device detected at `Animator` construction?** `Device.connectivity`
  (`src/lifx/devices/base.py`, added in this milestone from the parsed frame-address
  `thread_connection` bit) already reports `Connectivity.WIFI` / `Connectivity.THREAD`
  as a property on an already-connected device, with no extra network query needed. The
  `for_light()` / `for_multizone()` / `for_matrix()` classmethods each receive a `device`
  argument already, so a `device.connectivity == Connectivity.THREAD` check would fit
  there. The gap: `Animator.__init__()` itself takes only `ip`/`serial`/`framebuffer`/
  `packet_generator`/`port`, with no connectivity information at all, so a caller who
  bypasses the `for_*` factories and constructs `Animator` directly would not be caught
  by a check placed only in the factories. Decide whether the restriction belongs in the
  factories, in `__init__` itself (which would need a new parameter or a device
  reference), or in both.
- **Does the restriction raise or degrade?** A hard `LifxUnsupportedCommandError` (or a
  new, more specific exception) at construction time is the safest default and matches
  the existing exception hierarchy's precedent for "this device cannot do this." A
  softer degrade — construct successfully but clamp frame rate, or log a warning once per
  `Animator` instance — is more permissive but risks the exact silent-overload behaviour
  this seed exists to prevent, and re-opens the door to a caller unknowingly sustaining
  pixel-rate traffic on a mesh.
- **What should the error tell the caller?** At minimum: which device (by serial, not
  raw identity — this project's privacy posture applies to error text too) and why
  (Thread bandwidth/mesh-practice reasoning, not "unsupported device"). A caller who
  hits this needs enough information to understand this is a deliberate library
  boundary, not a bug, and that WiFi animation is unaffected.
- **Does this apply to the whole `Animator` surface, or only frame-rate-sensitive
  paths?** A single non-animated colour set already goes through `Light.set_color()`,
  not `Animator`, so this restriction is scoped to the dedicated Animation Layer only —
  confirm no legitimate low-rate Thread use case (occasional wake-effect, single frame)
  gets caught by an overly broad check before deciding whether the restriction is
  all-or-nothing or duty-cycle-aware.

## When to Surface

- A milestone modifies `src/lifx/animation/` (`animator.py`, `flow.py`, the packet
  generators, or the effects layer that renders through them)
- A consumer (e.g. LedFx) reports unexpected behaviour animating a Thread device
- Thread mesh bandwidth or SRP/mDNS keepalive reliability work makes the shared-airtime
  cost of animation traffic newly measurable
- Someone proposes adding Thread-specific animation tuning constants (this seed's answer
  should generally be "no" — the point is to not run animation on Thread at all, not to
  tune it to fit)
