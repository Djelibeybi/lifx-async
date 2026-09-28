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
to the light for as long as the effect runs. It draws on a whole light.

**Firmware effect**:
An effect built into the light, such as Morph, Flame, Sky or Move. The light runs
it without any software, and some lights, such as the Mirror and Luna, can start
and cycle through them from a button. It always covers the whole light. _Avoid_:
built-in effect (both kinds are built in, to different things).

**Effect participant**:
A light that a software effect draws on. One effect can draw on several
participants in step.

**Brightness inference**:
Choosing turn-on brightness when no colour is supplied: use suitable stored
brightness first, otherwise the other light component's brightness, then the
default brightness.
