# LIFX light control

Language for controlling the independently lit regions of Ceiling and Mirror lights.

## Language

**Light component**:
An independently controlled region of one light: uplight or downlight on a Ceiling,
front or back on a Mirror. Its colors and apparent on/off state can differ from
the other region even though both share the light's power.

**Whole-light operation**:
A color or power change addressed to the light as a whole, affecting both light
components.

**Stored colors**:
Colors remembered for restoring a light component when it is turned on again.
They can differ from the colors it currently displays while dark or fading.

**Transition target**:
The colors or power level a light is fading towards. A target can differ from
what the light reports while the fade is in progress.

**Observed colors**:
Colors reported by the light for the zones covered by a response. During a fade,
they can be intermediate colors rather than the transition target.

**Software effect**:
An effect built into the library. The library computes each frame and streams it
to the light for as long as the effect runs. It draws on its effect
participants: whole lights, or single light components. A light evidenced as
Thread, by its own replies or an mDNS record, takes frames only when the caller
passes `enable_thread=True`, because a Thread mesh is not built for that
traffic.

**Firmware effect**:
An effect built into the light: Move on strips, Morph and Flame on matrix lights,
Sky on matrix lights with recent firmware, and Color Sweep on the Mirror. The light runs it without any software,
and some lights, such as the Mirror and Luna, can start and cycle through them
from a button. It always covers the whole light. Flame always means the firmware
effect; the software effect with a similar look is Flicker. _Avoid_: built-in
effect (both kinds are built in, to different things).

**Waveform**:
A transition the light performs from one waveform command: it swings between its
current color and a target color in a set shape (saw, sine, half-sine, triangle
or pulse) for a set period and number of cycles. Breathe and pulse are waveforms.
_Avoid_: effect (a waveform is neither a software nor a firmware effect).

**Effect participant**:
A light, or a single light component of a light, that a software effect draws
on. One effect can draw on several participants in step. A light component
participant sees its own shape: a Ceiling uplight is one pixel, a Ceiling
downlight is the full grid with the uplight cell dropped, and a Mirror ring is
25 pixels that wrap, running clockwise from the ring origin on both rings. A
whole-light effect on a Mirror runs as two ring participants, the front and the
back, which share the Mirror's one index and simulation and so show the same
frame. The light component that no effect draws on keeps its colors and stays under the caller's control.
Only an effect that draws frames can have a light component as a participant.
A whole-light effect and a light component effect never share a light
component: the newest wins, and a whole-light effect that loses one light
component moves onto the other and stays there.

**Device type**:
The shape an effect participant presents to a software effect, used to say which
effects suit it: a single light, a multizone strip, a matrix, or a Mirror. A Mirror
ring is a Mirror whether the effect draws on the whole light or on that ring
alone, because both present the same 25-pixel ring that wraps. A light component
has a device type even though it is not a device.

**Seam**:
The point on a ring where an effect's first and last pixels meet. On a Mirror
ring it sits at the ring origin (top center by default, set with
`MirrorLight.ring_origin`), not at zone 0. An effect is
seamless when nothing visibly jumps there. Effects without meaningful ends are
always seamless on a ring; effects whose meaning needs a start and an end keep
their seam; effects where both looks suit, such as the pendulum wave and the
double slit, let the caller choose.

**Stopping an effect**:
Ending a software effect on a participant and restoring the participant's
prior state, while any other participants of the same effect carry on.
Stopping a light stops every effect on it, software or firmware, including
the effect on either light component; stopping a light component stops only
that light component's effect. With no effect running (no software run, and no
firmware effect reported by the light) stopping does nothing: no write, no
restore, and the current theme or mood stays. _Avoid_: canceling (that leaves
the prior state unrestored).

**Theme**:
A palette of colors, either named in the theme library or built by the caller.
Painting a theme blends its colors across the light.

**Mood**:
A theme painted the way the LIFX app paints it: the theme chooses the recipe,
and the colors are scaled to the light's brightness. Animating a mood starts
the effect the app's Dynamic toggle starts.

**Current theme**, **current mood**:
The theme a light was last painted with as a theme, or as a mood, for as long as
the light still shows exactly the colors it was painted with. A light has at
most one of the two, and only as a whole light, never per light component.
Turning the light off keeps it. A software effect playing the mood keeps it
while it runs, and so does firmware Morph between its colors. Firmware Move
ends it, because the light no longer reports what it shows in a form that can
be checked.

**Brightness inference**:
Choosing turn-on brightness when no color is supplied: use suitable stored
brightness first, otherwise the other light component's brightness, then the
default brightness.

**Device watcher** (working name, to settle in domain modelling):
The long-lived object that runs discovery on a schedule, holds one device
object per serial, and reports added, updated and removed events. Its terms
(silent, silence threshold, sweep) have no glossary entries yet.
