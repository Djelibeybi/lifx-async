# Light Effects

lifx-async includes 25+ built-in light effects — from simple pulse and color loops to complex animations like aurora, flame, fireworks, and cellular automata. The effects framework handles state management automatically: it captures your lights' current state, runs the effect, and restores everything when done.

## Quick Example

```python
import asyncio
from lifx import discover, DeviceGroup
from lifx.effects import Conductor, EffectPulse

async def main():
    devices = []
    async for device in discover():
        devices.append(device)
    group = DeviceGroup(devices)

    if not group.lights:
        print("No lights found")
        return

    # Create a conductor to manage effects
    conductor = Conductor()

    # Blink all lights 5 times
    effect = EffectPulse(mode='blink', cycles=5)
    await conductor.start(effect, group.lights)

    # Wait for effect to complete
    await asyncio.sleep(6)
    print("Done - lights restored to original state")

asyncio.run(main())
```

## How It Works

1. Create a **Conductor** — the central orchestrator for all effects
2. Create an **Effect** instance with your desired parameters
3. Call `conductor.start(effect, lights)` to run it
4. The conductor captures state, runs the effect, and restores state when done

Effects complete in different ways:

- **Cycle-based** (Pulse) — completes after configured cycles
- **Duration-based** (Sunrise, Sunset) — completes after a set duration
- **Continuous** (ColorLoop, Rainbow, Flame, Aurora) — runs until `conductor.stop()` is called

## Built-in Effects

| Category | Effects |
|----------|---------|
| **Basic** | Pulse (blink/breathe/strobe), ColorLoop, Rainbow |
| **Ambient** | Flame, Aurora, Twinkle, Embers, Sunrise, Sunset |
| **Physics** | Wave, Sine, Pendulum Wave, Double Slit, Ripple, Newton's Cradle |
| **Generative** | Rule 30, Rule Trio, Plasma, Plasma 2D, Spectrum Sweep |
| **Visual** | Cylon, Spin, Fireworks, Jacob's Ladder, Sonar, Progress |

See the [Effects Gallery](../user-guide/effects-gallery.md) for animated previews of every effect.

## Next Steps

- **[Effects Guide](../user-guide/effects.md)** — Full usage guide with all effects, patterns, and best practices
- **[Effects Gallery](../user-guide/effects-gallery.md)** — Animated GIF previews of every effect
- **[Custom Effects](../user-guide/effects-custom.md)** — Create your own effects
- **[Effects Reference](../api/effects.md)** — Complete API documentation
