"""Animation module example with device auto-detection.

Demonstrates the animation module for high-frequency frame delivery to LIFX
devices. Automatically detects whether the device is a matrix (Tile, Candle,
Path) or multizone (Strip, Beam) device and runs an appropriate animation.

The animation module sends frames via direct UDP for maximum throughput -
no connection layer overhead, no ACKs, just fire packets as fast as possible.
"""

import argparse
import asyncio
import math
import time

from lifx import Animator, MatrixLight, MultiZoneLight, find_by_ip, find_by_serial


def print_animator_info(animator: Animator) -> None:
    """Print information about the animator configuration."""
    print("\n--- Animator Info ---")
    w, h, p = animator.canvas_width, animator.canvas_height, animator.pixel_count
    print(f"  Canvas: {w}x{h} ({p} pixels)")
    print("  Network: Direct UDP (fire-and-forget)")
    print("---------------------\n")


async def run_matrix_animation(
    device: MatrixLight,
    duration: float = 10.0,
    fps: float = 30.0,
) -> None:
    """Run a rainbow wave animation on a matrix device.

    For multi-tile devices (like the original LIFX Tile), the animation spans
    the entire canvas - a unified coordinate space based on tile positions.
    This means the rainbow wave flows across all tiles as one continuous image.
    """
    print(f"\nRunning matrix animation for {duration:.1f} seconds...")
    print(f"Animation: Rainbow wave (30 degree angle) at {fps:.0f} FPS")

    # Create animator (queries device once, then sends via direct UDP)
    animator = await Animator.for_matrix(device)

    # Get canvas dimensions (may span multiple tiles)
    canvas_width = animator.canvas_width
    canvas_height = animator.canvas_height
    pixel_count = animator.pixel_count  # canvas_width * canvas_height

    # Get tile info
    tiles = device.device_chain
    if not tiles:
        print("Error: No tiles found")
        return

    print(f"Device: {len(tiles)} tile(s)")
    print(f"Canvas: {canvas_width}x{canvas_height} ({pixel_count} pixels)")
    if len(tiles) > 1:
        print("  (Animation spans all tiles as one unified canvas)")

    # Print debug info
    print_animator_info(animator)

    # Wave direction: 30 degrees from horizontal
    wave_angle = math.radians(30)
    cos_wave = math.cos(wave_angle)
    sin_wave = math.sin(wave_angle)

    # Calculate max position for normalization (using canvas dimensions)
    max_pos = canvas_width * cos_wave + canvas_height * sin_wave

    start_time = time.monotonic()
    frame_count = 0
    total_packets = 0
    hue_offset = 0
    last_status_time = start_time

    try:
        while time.monotonic() - start_time < duration:
            frame = []

            # Generate canvas-sized frame (row-major order)
            for y in range(canvas_height):
                for x in range(canvas_width):
                    # Project position onto wave direction (like multizone but angled)
                    pos = x * cos_wave + y * sin_wave

                    # Map position to hue (0-65535)
                    hue = int((pos / max_pos) * 65535 + hue_offset) % 65536

                    frame.append(
                        (
                            hue,
                            65535,  # Full saturation
                            65535,  # Full brightness
                            3500,  # Kelvin
                        )
                    )

            # send_frame is synchronous for maximum speed
            stats = animator.send_frame(frame)
            frame_count += 1
            total_packets += stats.packets_sent

            # Print periodic status (every 2 seconds)
            now = time.monotonic()
            if now - last_status_time >= 2.0:
                elapsed_so_far = now - start_time
                current_fps = frame_count / elapsed_so_far
                print(
                    f"  [{elapsed_so_far:.1f}s] frames={frame_count}, "
                    f"packets={total_packets}, fps={current_fps:.1f}"
                )
                last_status_time = now

            # Shift the rainbow
            hue_offset = (hue_offset + 1000) % 65536

            # Target FPS
            await asyncio.sleep(1 / fps)

    except KeyboardInterrupt:
        print("\nAnimation interrupted")
    finally:
        animator.close()

    elapsed = time.monotonic() - start_time
    actual_fps = frame_count / elapsed if elapsed > 0 else 0
    avg_packets_per_frame = total_packets / frame_count if frame_count > 0 else 0
    print("\nAnimation complete!")
    print(f"  Frames: {frame_count}")
    print(f"  Duration: {elapsed:.1f}s")
    print(f"  Average FPS: {actual_fps:.1f}")
    print(f"  Total packets: {total_packets}")
    print(f"  Avg packets/frame: {avg_packets_per_frame:.2f}")


async def run_multizone_animation(
    device: MultiZoneLight,
    duration: float = 10.0,
    fps: float = 30.0,
) -> None:
    """Run a rainbow wave animation on a multizone device."""
    print(f"\nRunning multizone animation for {duration:.1f} seconds...")
    print(f"Animation: Rainbow wave at {fps:.0f} FPS")

    # Create animator (queries device once, then sends via direct UDP)
    animator = await Animator.for_multizone(device)
    zone_count = animator.pixel_count

    print(f"Device: {zone_count} zones")

    # Print debug info
    print_animator_info(animator)

    start_time = time.monotonic()
    frame_count = 0
    total_packets = 0
    hue_offset = 0
    last_status_time = start_time

    try:
        while time.monotonic() - start_time < duration:
            frame = []

            for i in range(zone_count):
                # Create rainbow gradient across zones, shifting over time
                hue_val = int((i / zone_count) * 65536)
                hue = (hue_offset + hue_val) % 65536

                frame.append(
                    (
                        hue,
                        65535,  # Full saturation
                        65535,  # Full brightness
                        3500,  # Kelvin
                    )
                )

            # send_frame is synchronous for maximum speed
            stats = animator.send_frame(frame)
            frame_count += 1
            total_packets += stats.packets_sent

            # Print periodic status (every 2 seconds)
            now = time.monotonic()
            if now - last_status_time >= 2.0:
                elapsed_so_far = now - start_time
                current_fps = frame_count / elapsed_so_far
                print(
                    f"  [{elapsed_so_far:.1f}s] frames={frame_count}, "
                    f"packets={total_packets}, fps={current_fps:.1f}"
                )
                last_status_time = now

            # Rotate the rainbow
            hue_offset = (hue_offset + 1000) % 65536

            # Target FPS
            await asyncio.sleep(1 / fps)

    except KeyboardInterrupt:
        print("\nAnimation interrupted")
    finally:
        animator.close()

    elapsed = time.monotonic() - start_time
    actual_fps = frame_count / elapsed if elapsed > 0 else 0
    avg_packets_per_frame = total_packets / frame_count if frame_count > 0 else 0
    print("\nAnimation complete!")
    print(f"  Frames: {frame_count}")
    print(f"  Duration: {elapsed:.1f}s")
    print(f"  Average FPS: {actual_fps:.1f}")
    print(f"  Total packets: {total_packets}")
    print(f"  Avg packets/frame: {avg_packets_per_frame:.2f}")


async def main(
    serial: str,
    ip: str | None = None,
    duration: float = 10.0,
    fps: float = 30.0,
) -> None:
    """Find device and run appropriate animation."""
    print("=" * 70)
    print("LIFX Animation Example")
    print("=" * 70)

    # Find the device
    if ip:
        print(f"\nSearching for device at IP: {ip}")
        device = await find_by_ip(ip)
        if device is None:
            print(f"No device found at IP '{ip}'")
            return
        # Verify serial matches if both provided
        if device.serial.lower().replace(":", "") != serial.lower().replace(":", ""):
            print(f"Warning: Device serial {device.serial} doesn't match {serial}")
    else:
        print(f"\nSearching for device with serial: {serial}")
        device = await find_by_serial(serial)
        if device is None:
            print(f"No device found with serial '{serial}'")
            print("\nTroubleshooting:")
            print("1. Check that the serial number is correct (12 hex digits)")
            print("2. Ensure the device is powered on and on the network")
            print("3. Try providing the --ip address if discovery is slow")
            return

    print(f"Found: {type(device).__name__} at {device.ip}")

    # Connect and get device info
    async with device:
        # get_color() is available on Light and subclasses
        _, power, label = await device.get_color()  # type: ignore[union-attr]
        print(f"Label: {label}")
        print(f"Power: {'ON' if power > 0 else 'OFF'}")

        # Check device type and capabilities
        is_matrix = isinstance(device, MatrixLight)
        is_multizone = isinstance(device, MultiZoneLight)

        if not is_matrix and not is_multizone:
            # Check capabilities as fallback
            if device.capabilities:
                is_matrix = device.capabilities.has_matrix
                is_multizone = device.capabilities.has_multizone

        # Print capability info for debugging
        print("\n--- Device Capabilities ---")
        print(f"  Device class: {type(device).__name__}")
        print(f"  Is matrix: {is_matrix}")
        print(f"  Is multizone: {is_multizone}")
        if device.capabilities:
            caps = device.capabilities
            print(f"  has_matrix: {caps.has_matrix}")
            print(f"  has_multizone: {caps.has_multizone}")
            print(f"  has_extended_multizone: {caps.has_extended_multizone}")
        else:
            print("  capabilities: None (not detected)")
        print("---------------------------")

        if not is_matrix and not is_multizone:
            print("\nThis device does not support animations.")
            print("The animation module requires a Matrix or MultiZone device:")
            print("  - Matrix: Tile, Candle, Path, Ceiling")
            print("  - MultiZone: Strip, Beam")
            return

        # Turn on if off
        was_off = power == 0
        if was_off:
            print("\nTurning device ON...")
            await device.set_power(True)
            await asyncio.sleep(1)

        # Run appropriate animation
        try:
            if is_matrix:
                assert isinstance(device, MatrixLight)
                await run_matrix_animation(device, duration, fps)
            else:
                assert isinstance(device, MultiZoneLight)
                await run_multizone_animation(device, duration, fps)
        finally:
            # Restore power state
            if was_off:
                print("\nTurning device back OFF...")
                await device.set_power(False)

    print("\n" + "=" * 70)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run animation on a LIFX matrix or multizone device",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Find device by serial and run animation
  python 15_animation.py --serial d073d5123456

  # Specify IP address for faster connection
  python 15_animation.py --serial d073d5123456 --ip 192.168.1.100

  # Run animation for 30 seconds at 60 FPS
  python 15_animation.py --serial d073d5123456 --duration 30 --fps 60

  # Serial number formats (both work):
  python 15_animation.py --serial d073d5123456
  python 15_animation.py --serial d0:73:d5:12:34:56
        """,
    )
    parser.add_argument(
        "--serial",
        "-s",
        required=True,
        help="Device serial number (12 hex digits, with or without colons)",
    )
    parser.add_argument(
        "--ip",
        "-i",
        help="Optional IP address for faster connection",
    )
    parser.add_argument(
        "--duration",
        "-d",
        type=float,
        default=10.0,
        help="Animation duration in seconds (default: 10)",
    )
    parser.add_argument(
        "--fps",
        "-f",
        type=float,
        default=30.0,
        help="Target frames per second (default: 30)",
    )

    args = parser.parse_args()

    try:
        asyncio.run(
            main(
                args.serial,
                args.ip,
                args.duration,
                args.fps,
            )
        )
    except KeyboardInterrupt:
        print("\n\nCancelled by user.")
