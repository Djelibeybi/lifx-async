"""Waveform examples.

Demonstrates the use of set_waveform()
"""

import argparse
import asyncio

from lifx import HSBK, Colors, Light
from lifx.protocol.protocol_types import LightWaveform


async def main(ip: str):
    """Control a single light."""
    print(f"Connecting to light at {ip}...")

    async with await Light.from_ip(ip) as light:
        # Get device name
        label = await light.get_label()
        print(f"Connected to: {label}\n")

        async def reset_light(light: Light, color: HSBK):
            """Reset light."""
            current = await light.get_color()
            if current != color:
                await light.set_color(color)
            await light.set_power(True, duration=1.0)
            await asyncio.sleep(2)

        async def call_set_waveform(
            light: Light,
            color: HSBK,
            waveform: LightWaveform,
            transient: bool = False,
        ):
            """Call set_waveform()."""
            await light.set_waveform(
                color, period=2.0, cycles=2.0, waveform=waveform, transient=transient
            )
            await asyncio.sleep(5)

        async def clear_light(light: Light):
            """Clear light."""
            await light.set_power(False, duration=1.0)
            await asyncio.sleep(2)

        async def demo_waveform(
            light: Light,
            start_color: HSBK,
            waveform_color: HSBK,
            waveform: LightWaveform,
        ):
            """Full demo sequence for waveform."""
            await reset_light(light, start_color)
            await call_set_waveform(light, color=waveform_color, waveform=waveform)
            await clear_light(light)

        print("Pulsing (PULSE) blue to red twice...")
        await demo_waveform(light, Colors.BLUE, Colors.RED, LightWaveform.PULSE)

        print("Breathe (SINE) from red to green twice...")
        await demo_waveform(light, Colors.RED, Colors.GREEN, LightWaveform.SINE)

        print("Custom (SAW) from green to purple twice...")
        await demo_waveform(light, Colors.GREEN, Colors.PURPLE, LightWaveform.SAW)

        print("Custom (TRIANGLE) purple to orange twice...")
        await demo_waveform(light, Colors.PURPLE, Colors.ORANGE, LightWaveform.TRIANGLE)

        print("Custom (HALF-SINE) from orange to blue twice")
        await demo_waveform(light, Colors.ORANGE, Colors.BLUE, LightWaveform.HALF_SINE)

    print("\nDone!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Control a LIFX light")
    parser.add_argument(
        "--ip", required=True, help="IP address of the light (e.g., 192.168.1.100)"
    )
    args = parser.parse_args()

    asyncio.run(main(args.ip))
