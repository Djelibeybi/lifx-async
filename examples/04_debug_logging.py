"""Debug logging example."""

from __future__ import annotations

import asyncio
import logging

from lifx import Light, discover

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


async def main():
    """Discover lights and log label, power and color for each light."""
    async with discover(timeout=4.0) as all:
        # Log the number of each type of light discovered
        logger.info(
            {
                "discovered": {
                    "light": len(all.lights),
                    "multizone": len(all.multizone_lights),
                    "matrix": len(all.tiles),
                }
            }
        )

        async def get_light_info(
            light: Light,
        ) -> dict[str, str | dict[str, float | int]]:
            """Get color, label and power for each light."""
            color = await light.get_color()
            label = await light.get_label()
            power = await light.get_power()
            return {
                "label": label,
                "power": "ON" if power else "OFF",
                "color": {
                    "hue": color.hue,
                    "saturation": color.saturation,
                    "brightness": color.brightness,
                    "kelvin": color.kelvin,
                },
            }

        tasks: list[asyncio.Task[dict[str, str | dict[str, float | int]]]] = []

        # Send get_light_info() requests concurrently to all discovered devices
        async with asyncio.TaskGroup() as tg:
            for light in all.lights:
                tasks.append(tg.create_task(get_light_info(light)))

        # Log label, power, and color for each discovered light
        for task in tasks:
            result = task.result()
            logger.info(
                {
                    "label": result["label"],
                    "power": result["power"],
                    "color": result["color"],
                }
            )


if __name__ == "__main__":
    asyncio.run(main())
