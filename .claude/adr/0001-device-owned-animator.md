---
status: accepted (not yet implemented; tracked in #241)
---

# Each device owns one Animator

Every device owns a single Animator (`device.animator`). The Conductor and direct
users such as LedFx borrow it instead of constructing their own, and the
`Animator.for_matrix` / `for_multizone` / `for_light` factories return the device's
Animator rather than a new one. On Ceiling and Mirror lights, the Animator is
component-aware: each light component is a slot that an effect writes frames into,
and the Animator merges the slots into the one tile the firmware accepts.

We chose this because both light components share one tile, every frame write
replaces the whole tile, and the Animator's ack-gated flow control is per device.
Two Animators on one light would each erase the other's pixels and would put two
independent ack gates in front of one device, neither seeing the other's traffic.
One Animator per device gives one tile writer and one gate, so traffic stays capped
per device regardless of how many effects run on its components.

## Considered Options

- **A tile writer beneath several Animators.** Rejected: it still leaves one ack gate
  per Animator in front of the same device.
- **Each Animator writes the full tile, filling the other component from its last
  frame.** Rejected: doubles traffic and races.
- **Conductor-owned Animator per serial.** Rejected: direct Animator users and
  Conductor effects on the same light would again create two writers.

## Consequences

- The factories change behaviour (two calls return the same object) without
  changing signature; they are deprecated in favour of `device.animator`.
- While a component is animating, the other component's colour, power and theme
  calls go through the Animator's slot instead of writing to the device.
- This makes `device.start_effect` / `device.stop_effect` and their component
  equivalents possible.
