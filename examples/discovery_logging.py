"""Debug logging example."""

from __future__ import annotations

import asyncio
import logging

from lifx import Light, discover

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """Discover lights and log label, power and color for each light."""
    # Collect devices as they're discovered
    async for device in discover(timeout=4.0):
        if isinstance(device, Light):
            color, power, label = await device.get_color()
            logger.info(
                {
                    "serial": device.serial,
                    "label": label,
                    "power": power,
                    "color": color,
                }
            )


if __name__ == "__main__":
    asyncio.run(main())
