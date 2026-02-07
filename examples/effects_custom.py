"""Example demonstrating custom effect creation.

This example shows how to create a custom effect by subclassing LIFXEffect.

Requirements:
- One or more LIFX lights on the network
"""

import asyncio

from lifx import HSBK, Light, discover
from lifx.effects import Conductor, LIFXEffect


class FlashEffect(LIFXEffect):
    """Custom effect that flashes all lights in unison.

    Simple example of a custom effect that demonstrates the basic
    pattern for effect creation.
    """

    def __init__(
        self, flash_count: int = 5, duration: float = 0.5, power_on: bool = True
    ) -> None:
        """Initialize flash effect.

        Args:
            flash_count: Number of flashes
            duration: Duration of each flash in seconds
            power_on: Whether to power on lights if off
        """
        super().__init__(power_on=power_on)
        self.flash_count = flash_count
        self.duration = duration

    async def async_play(self) -> None:
        """Execute the flash effect on all participants."""
        for i in range(self.flash_count):
            print(f"Flash {i + 1}/{self.flash_count}")

            # All devices on
            tasks = [light.set_brightness(1.0) for light in self.participants]
            await asyncio.gather(*tasks)
            await asyncio.sleep(self.duration / 2)

            # All devices off
            tasks = [light.set_brightness(0.0) for light in self.participants]
            await asyncio.gather(*tasks)
            await asyncio.sleep(self.duration / 2)

        # Restore state via conductor
        if self.conductor:
            await self.conductor.stop(self.participants)


class WaveEffect(LIFXEffect):
    """Custom effect that creates a color wave across multiple lights.

    More complex example showing sequential color updates across devices.
    """

    def __init__(
        self, wave_count: int = 3, wave_speed: float = 0.3, power_on: bool = True
    ) -> None:
        """Initialize wave effect.

        Args:
            wave_count: Number of waves to run
            wave_speed: Speed of wave in seconds per light
            power_on: Whether to power on lights if off
        """
        super().__init__(power_on=power_on)
        self.wave_count = wave_count
        self.wave_speed = wave_speed

    async def async_play(self) -> None:
        """Execute the wave effect."""
        # Define wave colors
        colors = [
            HSBK.from_rgb(255, 0, 0),  # Red
            HSBK.from_rgb(255, 127, 0),  # Orange
            HSBK.from_rgb(255, 255, 0),  # Yellow
            HSBK.from_rgb(0, 255, 0),  # Green
            HSBK.from_rgb(0, 0, 255),  # Blue
        ]

        for wave in range(self.wave_count):
            print(f"Wave {wave + 1}/{self.wave_count}")

            # Wave forward
            for i, light in enumerate(self.participants):
                color = colors[i % len(colors)]
                await light.set_color(color, duration=self.wave_speed)
                await asyncio.sleep(self.wave_speed)

            await asyncio.sleep(0.5)  # Pause between waves

        # Restore state via conductor
        if self.conductor:
            await self.conductor.stop(self.participants)


async def main() -> None:
    """Run custom effect examples."""
    print("Discovering LIFX devices...")

    lights: list[Light] = []
    async for device in discover():
        if isinstance(device, Light):
            lights.append(device)

    if not lights:
        print("No lights found")
        return

    print(f"Found {len(lights)} light(s)")
    conductor = Conductor()

    # Example 1: Flash effect
    print("\n1. Flash effect (10 flashes)")
    flash_effect = FlashEffect(flash_count=10, duration=0.3)
    await conductor.start(flash_effect, lights)
    await asyncio.sleep(4)  # Wait for effect to complete

    await asyncio.sleep(2)  # Brief pause

    # Example 2: Wave effect
    print("\n2. Wave effect (3 waves)")
    wave_effect = WaveEffect(wave_count=3, wave_speed=0.4)
    await conductor.start(wave_effect, lights)
    # Calculate total time: waves * (lights * speed + pause)
    total_time = 3 * (len(lights) * 0.4 + 0.5)
    await asyncio.sleep(total_time + 1)

    print("\nAll effects completed!")
    print("Lights have been restored to their original state")


if __name__ == "__main__":
    asyncio.run(main())
