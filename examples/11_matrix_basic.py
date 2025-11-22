"""Basic MatrixLight control example.

Demonstrates controlling LIFX matrix devices (Tile, Candle, Path) including
getting device chain information and setting colors on individual tiles.
"""

import argparse
import asyncio

from lifx import HSBK, MatrixLight


async def main(ip: str):
    """Control a MatrixLight device."""
    print(f"Connecting to MatrixLight at {ip}...\n")

    async with await MatrixLight.from_ip(ip) as matrix:
        # Get basic device info
        color, power, label = await matrix.get_color()
        print(f"Connected to: {label}")
        print(f"Power: {'ON' if power > 0 else 'OFF'}")
        print(f"Current color: {color}\n")

        # Get device chain information
        print("Fetching device chain information...")
        device_chain = await matrix.get_device_chain()
        print(f"Device has {len(device_chain)} tile(s):\n")

        for tile in device_chain:
            print(f"  Tile {tile.tile_index}:")
            print(f"    Size: {tile.width}x{tile.height} ({tile.total_zones} zones)")
            if tile.requires_frame_buffer:
                print("    Note: >64 zones, requires frame buffer strategy")
            print()

        # Get current colors from first tile
        print("Getting current colors from tile 0...")
        tile_colors = await matrix.get64()
        print(f"Retrieved {len(tile_colors)} colors\n")

        if power == 0:
            print("Turning device ON...")
            await matrix.set_power(True)
            await asyncio.sleep(1)

        # Set first tile to blue gradient
        print("Creating blue gradient on tile 0...")
        tile_0 = device_chain[0]
        gradient_colors = []
        for i in range(tile_0.total_zones):
            # Gradient from bright blue to dim blue
            brightness = 1.0 - (i / tile_0.total_zones) * 0.7
            gradient_colors.append(
                HSBK(hue=240, saturation=1.0, brightness=brightness, kelvin=3500)
            )
        await matrix.set_matrix_colors(
            tile_index=0, colors=gradient_colors, duration=1500
        )
        await asyncio.sleep(3)

        # Restore original colors
        print("Restoring original colors...")
        await matrix.set_matrix_colors(tile_index=0, colors=tile_colors)
        await asyncio.sleep(1)

        if power == 0:
            print("Turning device back OFF...")
            await matrix.set_power(False)

    print("\nDone!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Control a LIFX MatrixLight device")
    parser.add_argument(
        "--ip",
        required=True,
        help="IP address of the MatrixLight (e.g., 192.168.1.100)",
    )
    args = parser.parse_args()

    asyncio.run(main(args.ip))
