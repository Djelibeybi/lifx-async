# LIFX light control

Language for controlling the independently lit regions of Ceiling and Mirror lights.

## Language

**Light component**:
An independently controlled region of one light: uplight or downlight on a Ceiling,
front or back on a Mirror. Its colours and apparent on/off state can differ from
the other region even though both share the light's power.

**Whole-light operation**:
A colour or power change addressed to the light as a whole, affecting both light
components.

**Stored colours**:
Colours remembered for restoring a light component when it is turned on again.
They can differ from the colours it currently displays while dark or fading.

**Transition target**:
The colours or power level a light is fading towards. A target can differ from
what the light reports while the fade is in progress.

**Observed colours**:
Colours reported by the light for the zones covered by a response. During a fade,
they can be intermediate colours rather than the transition target.

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
current colour and a target colour in a set shape (saw, sine, half-sine, triangle
or pulse) for a set period and number of cycles. Breathe and pulse are waveforms.
_Avoid_: effect (a waveform is neither a software nor a firmware effect).

**Effect participant**:
A light, or a single light component of a light, that a software effect draws
on. One effect can draw on several participants in step. A light component
participant sees its own shape: a Ceiling uplight is one pixel, a Ceiling
downlight is the full grid with the uplight cell dropped, and a Mirror ring is
25 pixels in zone order that wrap. A whole-light effect on a Mirror runs as two
ring participants, the front and the back, which share the Mirror's one index
and simulation and so show the same frame. The light component
that no effect draws on keeps its colours and stays under the caller's control.
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
The point on a ring where an effect's first and last pixels meet. An effect is
seamless when nothing visibly jumps there. Effects without meaningful ends are
always seamless on a ring; effects whose meaning needs a start and an end keep
their seam; effects where both looks suit, such as the pendulum wave and the
double slit, let the caller choose.

**Stopping an effect**:
Ending a software effect on a participant and restoring the participant's
prior state, while any other participants of the same effect carry on.
Stopping a light stops every effect on it, software or firmware, including
the effect on either light component; stopping a light component stops only
that light component's effect. _Avoid_: cancelling (that leaves the prior
state unrestored).

**Brightness inference**:
Choosing turn-on brightness when no colour is supplied: use suitable stored
brightness first, otherwise the other light component's brightness, then the
default brightness.
