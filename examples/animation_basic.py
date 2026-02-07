"""Animation module example with device auto-detection.

Demonstrates the animation module for high-frequency frame delivery to LIFX
devices. Automatically detects whether the device is a matrix (Tile, Candle,
Path) or multizone (Strip, Beam) device and runs an appropriate animation.

The animation module sends frames via direct UDP for maximum throughput -
no connection layer overhead, no ACKs, just fire packets as fast as possible.

Use --profile to run performance benchmarks:
  --profile alone: runs synthetic micro-benchmarks (no device needed)
  --profile with --serial/--ip: also profiles the animation loop against a device
"""

import argparse
import asyncio
import math
import statistics
import time

from lifx import (
    Animator,
    Device,
    MatrixLight,
    MultiZoneLight,
    find_by_ip,
    find_by_serial,
)
from lifx.animation.packets import MatrixPacketGenerator, MultiZonePacketGenerator
from lifx.protocol.header import LifxHeader
from lifx.protocol.packets import Light
from lifx.protocol.protocol_types import LightHsbk


def print_animator_info(animator: Animator) -> None:
    """Print information about the animator configuration."""
    print("\n--- Animator Info ---")
    w, h, p = animator.canvas_width, animator.canvas_height, animator.pixel_count
    print(f"  Canvas: {w}x{h} ({p} pixels)")
    print("  Network: Direct UDP (fire-and-forget)")
    print("---------------------\n")


def percentile_stats(times_ms: list[float]) -> dict[str, float]:
    """Compute summary statistics from a list of times in milliseconds."""
    if not times_ms:
        return {
            "mean": 0.0,
            "median": 0.0,
            "p95": 0.0,
            "p99": 0.0,
            "min": 0.0,
            "max": 0.0,
        }
    times_ms.sort()
    n = len(times_ms)
    return {
        "mean": statistics.mean(times_ms),
        "median": statistics.median(times_ms),
        "p95": times_ms[int(n * 0.95)],
        "p99": times_ms[int(n * 0.99)],
        "min": times_ms[0],
        "max": times_ms[-1],
    }


def print_stats(label: str, stats: dict[str, float]) -> None:
    """Print a single stats line."""
    print(
        f"  {label}:\n"
        f"    mean={stats['mean']:.3f}ms  median={stats['median']:.3f}ms  "
        f"p95={stats['p95']:.3f}ms  p99={stats['p99']:.3f}ms  "
        f"min={stats['min']:.3f}ms  max={stats['max']:.3f}ms"
    )


async def run_profile(
    device: MatrixLight | MultiZoneLight,
    iterations: int = 2000,
    warmup: int = 200,
) -> None:
    """Profile the animation loop against a real device."""
    is_matrix = isinstance(device, MatrixLight)

    if is_matrix:
        animator = await Animator.for_matrix(device)
        canvas_width = animator.canvas_width
        canvas_height = animator.canvas_height
    else:
        animator = await Animator.for_multizone(device)
        canvas_width = animator.pixel_count
        canvas_height = 1

    pixel_count = animator.pixel_count

    # Pre-compute wave constants for matrix
    wave_angle = math.radians(30)
    cos_wave = math.cos(wave_angle)
    sin_wave = math.sin(wave_angle)
    max_pos = canvas_width * cos_wave + canvas_height * sin_wave

    gen_times: list[float] = []
    send_times: list[float] = []

    total_iterations = warmup + iterations
    print(
        f"\n=== Animation Profile ({iterations} iterations, "
        f"{'matrix' if is_matrix else 'multizone'} "
        f"{canvas_width}x{canvas_height}, {pixel_count} pixels) ==="
    )
    print(f"  Warmup: {warmup} iterations")

    try:
        for i in range(total_iterations):
            hue_offset = (i * 1000) % 65536

            # Time frame generation
            t0 = time.perf_counter()
            if is_matrix:
                frame = []
                for y in range(canvas_height):
                    for x in range(canvas_width):
                        pos = x * cos_wave + y * sin_wave
                        hue = int((pos / max_pos) * 65535 + hue_offset) % 65536
                        frame.append((hue, 65535, 65535, 3500))
            else:
                frame = []
                for j in range(pixel_count):
                    hue_val = int((j / pixel_count) * 65536)
                    hue = (hue_offset + hue_val) % 65536
                    frame.append((hue, 65535, 65535, 3500))
            t1 = time.perf_counter()

            # Time send_frame
            animator.send_frame(frame)
            t2 = time.perf_counter()

            if i >= warmup:
                gen_times.append((t1 - t0) * 1000)
                send_times.append((t2 - t1) * 1000)
    finally:
        animator.close()

    total_times = [g + s for g, s in zip(gen_times, send_times)]

    print()
    print_stats("Frame generation", percentile_stats(gen_times))
    print_stats("send_frame (orient + pack + send)", percentile_stats(send_times))
    print_stats("Total per-frame", percentile_stats(total_times))

    if total_times:
        mean_total = statistics.mean(total_times)
        if mean_total > 0:
            throughput = 1000.0 / mean_total
            print(f"\n  Throughput: {throughput:,.0f} frames/sec")


def _bench(label: str, func: object, n: int) -> None:
    """Run a tight-loop benchmark and print results."""
    t0 = time.perf_counter()
    for _ in range(n):
        func()  # type: ignore[operator]
    elapsed = time.perf_counter() - t0
    rate = n / elapsed
    per_call = elapsed / n * 1000
    print(
        f"{label}:\n"
        f"  {n:,} calls in {elapsed:.2f}s  "
        f"({rate:,.0f} calls/sec, {per_call:.4f}ms/call)"
    )


def run_synthetic_benchmarks() -> None:
    """Run synthetic micro-benchmarks of optimized code paths."""
    print("\n=== Synthetic Benchmarks ===\n")

    dummy_target = b"\xd0\x73\xd5\x01\x02\x03"
    dummy_source = 12345

    # --- update_colors: matrix (5 tiles, 320 pixels) ---
    matrix_gen = MatrixPacketGenerator(tile_count=5, tile_width=8, tile_height=8)
    matrix_templates = matrix_gen.create_templates(dummy_source, dummy_target)
    matrix_pixels = matrix_gen.pixel_count()
    matrix_hsbk = [(32768, 65535, 32768, 3500)] * matrix_pixels

    n = 100_000
    _bench(
        f"update_colors (matrix, 5 tiles, {matrix_pixels}px)",
        lambda: matrix_gen.update_colors(matrix_templates, matrix_hsbk),
        n,
    )

    # --- update_colors: multizone (82 zones) ---
    mz_gen = MultiZonePacketGenerator(zone_count=82)
    mz_templates = mz_gen.create_templates(dummy_source, dummy_target)
    mz_hsbk = [(32768, 65535, 32768, 3500)] * 82

    print()
    _bench(
        "update_colors (multizone, 82 zones)",
        lambda: mz_gen.update_colors(mz_templates, mz_hsbk),
        n,
    )

    # --- LifxHeader.pack() ---
    header = LifxHeader.create(
        pkt_type=102,
        source=dummy_source,
        target=dummy_target,
        payload_size=13,
    )
    n_header = 500_000

    print()
    _bench("LifxHeader.pack()", header.pack, n_header)

    # --- LifxHeader.unpack() ---
    packed_header = header.pack()

    print()
    _bench(
        "LifxHeader.unpack()",
        lambda: LifxHeader.unpack(packed_header),
        n_header,
    )

    # --- Packet.pack (Light.SetColor) ---
    hsbk = LightHsbk(hue=32768, saturation=65535, brightness=32768, kelvin=3500)
    packet = Light.SetColor(color=hsbk, duration=1000)

    print()
    _bench("Packet.pack (Light.SetColor)", packet.pack, n)

    # --- Packet.unpack (Light.SetColor) ---
    packed_packet = packet.pack()

    print()
    _bench(
        "Packet.unpack (Light.SetColor)",
        lambda: Light.SetColor.unpack(packed_packet),
        n,
    )


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
    serial: str | None = None,
    ip: str | None = None,
    duration: float = 10.0,
    fps: float = 30.0,
    profile: bool = False,
    iterations: int = 2000,
    warmup: int = 200,
) -> None:
    """Find device and run appropriate animation."""
    if profile and not serial and not ip:
        # Synthetic-only mode
        print("=" * 70)
        print("LIFX Animation Profiler (synthetic benchmarks only)")
        print("=" * 70)
        run_synthetic_benchmarks()
        return

    if not serial and not ip:
        print("Error: --serial or --ip is required (unless using --profile alone)")
        return

    print("=" * 70)
    print("LIFX Animation Example" + (" (profiling)" if profile else ""))
    print("=" * 70)

    # Find the device
    if serial and ip:
        # Both serial and IP provided - connect directly without discovery
        print(f"\nConnecting directly to {ip} (serial: {serial})")
        device = await Device.connect(ip=ip, serial=serial)
    elif ip:
        print(f"\nSearching for device at IP: {ip}")
        device = await find_by_ip(ip)
        if device is None:
            print(f"No device found at IP '{ip}'")
            return
    else:
        assert serial is not None
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

        # Run appropriate animation or profile
        try:
            if profile:
                if is_matrix:
                    assert isinstance(device, MatrixLight)
                    await run_profile(device, iterations, warmup)
                else:
                    assert isinstance(device, MultiZoneLight)
                    await run_profile(device, iterations, warmup)
            else:
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

    # Always run synthetic benchmarks after device profiling
    if profile:
        run_synthetic_benchmarks()

    print("\n" + "=" * 70)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run animation on a LIFX matrix or multizone device",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Find device by serial and run animation
  python animation_basic.py --serial d073d5123456

  # Specify IP address for faster connection
  python animation_basic.py --serial d073d5123456 --ip 192.168.1.100

  # Run animation for 30 seconds at 60 FPS
  python animation_basic.py --serial d073d5123456 --duration 30 --fps 60

  # Run synthetic benchmarks only (no device needed)
  python animation_basic.py --profile

  # Profile animation loop against a device + synthetic benchmarks
  python animation_basic.py --serial d073d5123456 --ip 192.168.1.100 --profile

  # Serial number formats (both work):
  python animation_basic.py --serial d073d5123456
  python animation_basic.py --serial d0:73:d5:12:34:56
        """,
    )
    parser.add_argument(
        "--serial",
        "-s",
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
    parser.add_argument(
        "--profile",
        action="store_true",
        help="Enable profiling mode (no sleep between frames)",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=2000,
        help="Number of profiling iterations (default: 2000)",
    )
    parser.add_argument(
        "--warmup",
        type=int,
        default=200,
        help="Warmup iterations excluded from stats (default: 200)",
    )

    args = parser.parse_args()

    if not args.profile and not args.serial:
        parser.error("--serial is required unless using --profile alone")

    try:
        asyncio.run(
            main(
                args.serial,
                args.ip,
                args.duration,
                args.fps,
                args.profile,
                args.iterations,
                args.warmup,
            )
        )
    except KeyboardInterrupt:
        print("\n\nCancelled by user.")
