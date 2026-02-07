"""MatrixLight large tile handling example.

Demonstrates handling matrix devices with >64 zones (e.g., 16x8 = 128 zones).
The library automatically uses the frame buffer strategy for these devices.
"""

import argparse
import asyncio

from lifx import HSBK, MatrixLight


async def main(ip: str):
    """Demonstrate handling large MatrixLight tiles (>64 zones)."""
    print(f"Connecting to MatrixLight at {ip}...\n")

    async with await MatrixLight.from_ip(ip) as matrix:
        # Get device info
        _, power, label = await matrix.get_color()
        print(f"Connected to: {label}\n")

        # Get device chain to check tile sizes
        device_chain = await matrix.get_device_chain()
        print(f"Device has {len(device_chain)} tile(s):\n")

        large_tiles = []
        for tile in device_chain:
            print(
                f"  Tile {tile.tile_index}: {tile.width}x{tile.height} = "
                f"{tile.total_zones} zones"
            )
            if tile.requires_frame_buffer:
                print("    → Requires frame buffer strategy (>64 zones)")
                large_tiles.append(tile)
            else:
                print("    → Standard tile (≤64 zones)")
        print()

        if not large_tiles:
            print("Note: No large tiles found on this device.")
            print(
                "This example is designed for tiles with >64 zones (e.g., 16x8 = 128)."
            )
            print("The set_matrix_colors() method will still work on smaller tiles.")
            print()

        if power == 0:
            print("Turning device ON...")
            await matrix.set_power(True)
            await asyncio.sleep(1)

        # Demonstrate setting colors on first tile (any size)
        first_tile = device_chain[0]
        print(
            f"Creating rainbow pattern on tile 0 "
            f"({first_tile.width}x{first_tile.height})..."
        )
        print()

        # Zone addressing: row-by-row from top-left (0,0)
        # For 16x8 tile: rows 0-3 = first 64 zones, rows 4-7 = next 64 zones
        # For 8x8 tile: all 64 zones in single batch
        # For 5x6 tile: 30 zones padded to 64

        rainbow_colors = []
        for row in range(first_tile.height):
            for col in range(first_tile.width):
                # Create rainbow gradient based on position
                hue = (col / first_tile.width) * 360
                brightness = 1.0 - (row / first_tile.height) * 0.5
                rainbow_colors.append(
                    HSBK(hue=hue, saturation=1.0, brightness=brightness, kelvin=3500)
                )

        print(f"Setting {len(rainbow_colors)} colors...")
        print()

        if first_tile.requires_frame_buffer:
            print("Note: This tile requires frame buffer strategy:")
            print(
                f"  1. First set64(): rows 0-{first_tile.height // 2 - 1} "
                f"(64 zones) to buffer 1"
            )
            print(
                f"  2. Second set64(): rows {first_tile.height // 2}-"
                f"{first_tile.height - 1} (64 zones) to buffer 1"
            )
            print("  3. copy_frame_buffer(): Copy buffer 1 → buffer 0 (visible)")
            print()
            print("The set_matrix_colors() method handles this automatically!")
            print()

        await matrix.set_matrix_colors(
            tile_index=0,
            colors=rainbow_colors,
            duration=2000,  # 2 second transition
        )
        print("Rainbow pattern applied!")
        await asyncio.sleep(3)

        # Create vertical stripes pattern
        print("\nCreating vertical stripes pattern...")
        stripe_colors = []
        for row in range(first_tile.height):
            for col in range(first_tile.width):
                # Alternate between blue and yellow stripes
                if col % 2 == 0:
                    stripe_colors.append(
                        HSBK(hue=240, saturation=1.0, brightness=1.0, kelvin=3500)
                    )
                else:
                    stripe_colors.append(
                        HSBK(hue=60, saturation=1.0, brightness=1.0, kelvin=3500)
                    )

        await matrix.set_matrix_colors(
            tile_index=0, colors=stripe_colors, duration=1000
        )
        print("Vertical stripes applied!")
        await asyncio.sleep(3)

        # Create checkerboard pattern
        print("\nCreating checkerboard pattern...")
        checker_colors = []
        for row in range(first_tile.height):
            for col in range(first_tile.width):
                # Checkerboard: alternate based on row + col parity
                if (row + col) % 2 == 0:
                    checker_colors.append(
                        HSBK(hue=0, saturation=1.0, brightness=1.0, kelvin=3500)
                    )  # Red
                else:
                    checker_colors.append(
                        HSBK(hue=0, saturation=0.0, brightness=1.0, kelvin=6500)
                    )  # White

        await matrix.set_matrix_colors(
            tile_index=0, colors=checker_colors, duration=1000
        )
        print("Checkerboard applied!")
        await asyncio.sleep(3)

        # Clear to single color
        print("\nClearing to cyan...")
        clear_colors = [
            HSBK(hue=180, saturation=1.0, brightness=0.5, kelvin=3500)
        ] * first_tile.total_zones
        await matrix.set_matrix_colors(tile_index=0, colors=clear_colors, duration=1000)
        await asyncio.sleep(2)

        if power == 0:
            print("\nTurning device back OFF...")
            await matrix.set_power(False)

    print("\nDone!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Demonstrate LIFX MatrixLight large tile handling"
    )
    parser.add_argument(
        "--ip",
        required=True,
        help="IP address of the MatrixLight (e.g., 192.168.1.100)",
    )
    args = parser.parse_args()

    asyncio.run(main(args.ip))
