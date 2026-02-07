"""Animation example using NumPy for efficient frame generation.

This example demonstrates how to use NumPy for high-performance animation
frame generation. NumPy enables vectorized operations that are significantly
faster than Python loops, especially for large pixel counts.

Requires: numpy (pip install numpy)

Key optimizations:
- Vectorized RGB to HSBK conversion
- Vectorized frame generation with no Python loops
- Pre-allocated arrays to avoid memory allocation per frame
- Direct conversion to protocol-ready uint16 format

Use --profile to run performance benchmarks:
  --profile alone: runs synthetic micro-benchmarks (no device needed)
  --profile with --serial/--ip: also profiles the animation loop against a device
"""

import argparse
import asyncio
import statistics
import time

try:
    import numpy as np
    from numpy.typing import NDArray
except ImportError:
    print("This example requires NumPy. Install it with:")
    print("  pip install numpy")
    print("  # or")
    print("  uv add --dev numpy")
    raise SystemExit(1)

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


def rgb_to_hsbk_numpy(
    rgb: NDArray[np.uint8],
    kelvin: int = 3500,
) -> NDArray[np.uint16]:
    """Convert RGB array to protocol-ready HSBK using vectorized operations.

    Args:
        rgb: Array of shape (N, 3) with RGB values 0-255
        kelvin: Color temperature for all pixels

    Returns:
        Array of shape (N, 4) with HSBK values in protocol format:
        - Hue: 0-65535
        - Saturation: 0-65535
        - Brightness: 0-65535
        - Kelvin: 1500-9000
    """
    # Normalize RGB to 0-1 float
    rgb_norm = rgb.astype(np.float32) / 255.0

    r = rgb_norm[:, 0]
    g = rgb_norm[:, 1]
    b = rgb_norm[:, 2]

    # Calculate max, min, delta
    max_c = np.maximum(np.maximum(r, g), b)
    min_c = np.minimum(np.minimum(r, g), b)
    delta = max_c - min_c

    # Brightness is just the max
    brightness = max_c

    # Saturation
    saturation = np.where(max_c > 0, delta / max_c, 0)

    # Hue calculation (vectorized)
    hue = np.zeros_like(max_c)

    # Where delta > 0, calculate hue
    mask = delta > 0

    # Red is max
    red_max = mask & (max_c == r)
    hue[red_max] = 60 * (((g[red_max] - b[red_max]) / delta[red_max]) % 6)

    # Green is max
    green_max = mask & (max_c == g)
    hue[green_max] = 60 * (((b[green_max] - r[green_max]) / delta[green_max]) + 2)

    # Blue is max
    blue_max = mask & (max_c == b)
    hue[blue_max] = 60 * (((r[blue_max] - g[blue_max]) / delta[blue_max]) + 4)

    # Convert to protocol format (uint16)
    hsbk = np.zeros((len(rgb), 4), dtype=np.uint16)
    hsbk[:, 0] = (hue / 360 * 65535).astype(np.uint16)
    hsbk[:, 1] = (saturation * 65535).astype(np.uint16)
    hsbk[:, 2] = (brightness * 65535).astype(np.uint16)
    hsbk[:, 3] = kelvin

    return hsbk


def hsbk_array_to_list(
    hsbk: NDArray[np.uint16],
) -> list[tuple[int, int, int, int]]:
    """Convert NumPy HSBK array to list of tuples for the animator.

    Args:
        hsbk: Array of shape (N, 4) with HSBK values

    Returns:
        List of (H, S, B, K) tuples
    """
    return [tuple(row) for row in hsbk.tolist()]  # type: ignore[misc]


class NumpyFrameGenerator:
    """Efficient frame generator using NumPy for vectorized operations."""

    def __init__(self, pixel_count: int, width: int = 8, height: int = 8):
        """Initialize the frame generator.

        Args:
            pixel_count: Total number of pixels
            width: Width for 2D calculations (for matrix devices)
            height: Height for 2D calculations (for matrix devices)
        """
        self.pixel_count = pixel_count
        self.width = width
        self.height = height

        # Pre-allocate arrays
        self.hsbk = np.zeros((pixel_count, 4), dtype=np.uint16)
        self.hsbk[:, 3] = 3500  # Default kelvin

        # Pre-compute coordinate grids for matrix effects
        if width * height == pixel_count:
            # Single tile or multizone
            y_coords, x_coords = np.mgrid[0:height, 0:width]
            self.x = x_coords.flatten().astype(np.float32)
            self.y = y_coords.flatten().astype(np.float32)
        else:
            # Multi-tile: repeat coordinate grid
            tiles = pixel_count // (width * height)
            y_coords, x_coords = np.mgrid[0:height, 0:width]
            self.x = np.tile(x_coords.flatten(), tiles).astype(np.float32)
            self.y = np.tile(y_coords.flatten(), tiles).astype(np.float32)

        # Pre-compute center and distances for radial effects
        self.center_x = width / 2
        self.center_y = height / 2
        self.dx = self.x - self.center_x
        self.dy = self.y - self.center_y
        self.distance = np.sqrt(self.dx**2 + self.dy**2)
        self.angle = np.arctan2(self.dy, self.dx)

        # For linear effects (multizone)
        self.index = np.arange(pixel_count, dtype=np.float32)

    def generate_rainbow_spiral(
        self, time_offset: float
    ) -> list[tuple[int, int, int, int]]:
        """Generate a rainbow spiral pattern (good for matrix devices).

        Args:
            time_offset: Animation time in seconds

        Returns:
            List of HSBK tuples ready for the animator
        """
        # Hue based on distance and angle, rotating over time
        hue = (
            self.distance * 0.15 + self.angle / (2 * np.pi) + time_offset * 0.5
        ) % 1.0

        # Brightness varies with distance from center
        brightness = np.clip(1.0 - self.distance * 0.08, 0.3, 1.0)

        # Convert to protocol format
        self.hsbk[:, 0] = (hue * 65535).astype(np.uint16)
        self.hsbk[:, 1] = 65535  # Full saturation
        self.hsbk[:, 2] = (brightness * 65535).astype(np.uint16)

        return hsbk_array_to_list(self.hsbk)

    def generate_rainbow_wave(
        self, time_offset: float
    ) -> list[tuple[int, int, int, int]]:
        """Generate a rainbow wave pattern (good for multizone devices).

        Args:
            time_offset: Animation time in seconds

        Returns:
            List of HSBK tuples ready for the animator
        """
        # Hue gradient along the strip, moving over time
        hue = (self.index / self.pixel_count + time_offset * 0.3) % 1.0

        # Brightness wave
        wave_phase = self.index / self.pixel_count * 4 * np.pi + time_offset * 3
        brightness = 0.5 + 0.5 * np.sin(wave_phase)

        # Convert to protocol format
        self.hsbk[:, 0] = (hue * 65535).astype(np.uint16)
        self.hsbk[:, 1] = 65535  # Full saturation
        self.hsbk[:, 2] = (brightness * 65535).astype(np.uint16)

        return hsbk_array_to_list(self.hsbk)

    def generate_plasma(self, time_offset: float) -> list[tuple[int, int, int, int]]:
        """Generate a plasma effect using sine waves.

        Args:
            time_offset: Animation time in seconds

        Returns:
            List of HSBK tuples ready for the animator
        """
        t = time_offset

        # Classic plasma formula with multiple sine waves
        v1 = np.sin(self.x * 0.5 + t)
        v2 = np.sin((self.y * 0.5 + t) * 0.5)
        v3 = np.sin((self.x * 0.5 + self.y * 0.5 + t) * 0.5)
        v4 = np.sin(np.sqrt(self.dx**2 + self.dy**2) * 0.5 + t)

        # Combine and normalize to 0-1
        v = (v1 + v2 + v3 + v4) / 4
        hue = (v + 1) / 2  # Convert from -1..1 to 0..1

        # Brightness variation
        brightness = 0.6 + 0.4 * np.sin(t * 2 + self.distance * 0.3)

        # Convert to protocol format
        self.hsbk[:, 0] = (hue * 65535).astype(np.uint16)
        self.hsbk[:, 1] = 65535
        self.hsbk[:, 2] = (brightness * 65535).astype(np.uint16)

        return hsbk_array_to_list(self.hsbk)

    def generate_fire(self, time_offset: float) -> list[tuple[int, int, int, int]]:
        """Generate a fire effect (warm colors, flickering).

        Args:
            time_offset: Animation time in seconds

        Returns:
            List of HSBK tuples ready for the animator
        """
        t = time_offset

        # Fire rises from bottom, so invert y
        fire_y = (self.height - 1 - self.y) / self.height

        # Random-ish flickering using sine combinations
        flicker = (
            np.sin(self.x * 2 + t * 10) * np.sin(self.y * 3 + t * 7) * np.sin(t * 15)
        )
        flicker = (flicker + 1) / 2 * 0.3  # 0 to 0.3 variation

        # Brightness decreases toward top with flickering
        brightness = np.clip(fire_y + flicker, 0, 1)

        # Hue from red (0) to yellow (60/360 = 0.167) based on height
        hue = fire_y * 0.12  # Red to orange-yellow

        # Saturation decreases slightly at the tips (more white/yellow)
        saturation = np.clip(1.0 - fire_y * 0.3, 0.7, 1.0)

        # Convert to protocol format
        self.hsbk[:, 0] = (hue * 65535).astype(np.uint16)
        self.hsbk[:, 1] = (saturation * 65535).astype(np.uint16)
        self.hsbk[:, 2] = (brightness * 65535).astype(np.uint16)
        self.hsbk[:, 3] = 2700  # Warm kelvin for fire

        return hsbk_array_to_list(self.hsbk)

    def generate_numpy_only(self, time_offset: float) -> NDArray[np.uint16]:
        """Generate a rainbow spiral as a NumPy array (no list conversion).

        Used by profiling to separate NumPy generation from list conversion.

        Args:
            time_offset: Animation time in seconds

        Returns:
            HSBK array of shape (N, 4) with uint16 values
        """
        hue = (
            self.distance * 0.15 + self.angle / (2 * np.pi) + time_offset * 0.5
        ) % 1.0
        brightness = np.clip(1.0 - self.distance * 0.08, 0.3, 1.0)

        self.hsbk[:, 0] = (hue * 65535).astype(np.uint16)
        self.hsbk[:, 1] = 65535
        self.hsbk[:, 2] = (brightness * 65535).astype(np.uint16)

        return self.hsbk


async def run_profile(
    device: MatrixLight | MultiZoneLight,
    iterations: int = 2000,
    warmup: int = 200,
) -> None:
    """Profile the animation loop against a real device.

    Separates timing into: NumPy generation, hsbk_array_to_list conversion,
    and animator.send_frame().
    """
    is_matrix = isinstance(device, MatrixLight)

    if is_matrix:
        animator = await Animator.for_matrix(device)
        tiles = device.device_chain
        width = tiles[0].width if tiles else 8
        height = tiles[0].height if tiles else 8
    else:
        animator = await Animator.for_multizone(device)
        width = animator.pixel_count
        height = 1

    pixel_count = animator.pixel_count
    generator = NumpyFrameGenerator(pixel_count, width, height)

    effect = "spiral" if is_matrix else "wave"

    gen_times: list[float] = []
    convert_times: list[float] = []
    send_times: list[float] = []

    total_iterations = warmup + iterations
    print(
        f"\n=== Animation Profile ({iterations} iterations, "
        f"{'matrix' if is_matrix else 'multizone'} "
        f"{animator.canvas_width}x{animator.canvas_height}, "
        f"{pixel_count} pixels, effect={effect}) ==="
    )
    print(f"  Warmup: {warmup} iterations")

    try:
        for i in range(total_iterations):
            t_offset = i * 0.033  # Simulate 30fps timing

            # Time NumPy frame generation
            t0 = time.perf_counter()
            hsbk_array = generator.generate_numpy_only(t_offset)
            t1 = time.perf_counter()

            # Time list conversion
            frame = hsbk_array_to_list(hsbk_array)
            t2 = time.perf_counter()

            # Time send_frame
            animator.send_frame(frame)
            t3 = time.perf_counter()

            if i >= warmup:
                gen_times.append((t1 - t0) * 1000)
                convert_times.append((t2 - t1) * 1000)
                send_times.append((t3 - t2) * 1000)
    finally:
        animator.close()

    total_times = [g + c + s for g, c, s in zip(gen_times, convert_times, send_times)]

    print()
    print_stats("NumPy frame generation", percentile_stats(gen_times))
    print_stats(
        "hsbk_array_to_list conversion",
        percentile_stats(convert_times),
    )
    print_stats(
        "send_frame (orient + pack + send)",
        percentile_stats(send_times),
    )
    print_stats("Total per-frame", percentile_stats(total_times))

    if total_times:
        mean_total = statistics.mean(total_times)
        if mean_total > 0:
            throughput = 1000.0 / mean_total
            print(f"\n  Throughput: {throughput:,.0f} frames/sec")


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


async def run_animation(
    device: MatrixLight | MultiZoneLight,
    duration: float = 10.0,
    fps: float = 30.0,
    effect: str = "auto",
) -> None:
    """Run animation with NumPy-optimized frame generation."""
    is_matrix = isinstance(device, MatrixLight)

    # Create animator
    if is_matrix:
        animator = await Animator.for_matrix(device)
        tiles = device.device_chain
        width = tiles[0].width if tiles else 8
        height = tiles[0].height if tiles else 8
    else:
        animator = await Animator.for_multizone(device)
        width = animator.pixel_count
        height = 1

    pixel_count = animator.pixel_count
    print(f"\nPixel count: {pixel_count}")
    print(f"Dimensions: {width}x{height}")

    # Print debug info
    print_animator_info(animator)

    # Create frame generator
    generator = NumpyFrameGenerator(pixel_count, width, height)

    # Select effect
    if effect == "auto":
        effect = "spiral" if is_matrix else "wave"

    effect_funcs = {
        "spiral": generator.generate_rainbow_spiral,
        "wave": generator.generate_rainbow_wave,
        "plasma": generator.generate_plasma,
        "fire": generator.generate_fire,
    }

    if effect not in effect_funcs:
        print(f"Unknown effect '{effect}', using 'spiral'")
        effect = "spiral"

    generate_frame = effect_funcs[effect]
    print(f"Effect: {effect}")
    print(f"Duration: {duration:.1f}s at {fps:.0f} FPS")
    print()

    # Animation loop
    start_time = time.monotonic()
    frame_count = 0
    total_packets = 0
    total_gen_time = 0.0
    total_send_time = 0.0
    last_status_time = start_time

    try:
        while time.monotonic() - start_time < duration:
            t = time.monotonic() - start_time

            # Generate frame (timed)
            gen_start = time.perf_counter()
            frame = generate_frame(t)
            gen_end = time.perf_counter()
            total_gen_time += gen_end - gen_start

            # Send frame (timed) - synchronous for maximum speed
            send_start = time.perf_counter()
            stats = animator.send_frame(frame)
            send_end = time.perf_counter()
            total_send_time += send_end - send_start

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

            # Target FPS
            await asyncio.sleep(1 / fps)

    except KeyboardInterrupt:
        print("\nAnimation interrupted")
    finally:
        animator.close()

    # Print statistics
    elapsed = time.monotonic() - start_time
    actual_fps = frame_count / elapsed if elapsed > 0 else 0
    avg_gen_ms = (total_gen_time / frame_count * 1000) if frame_count > 0 else 0
    avg_send_ms = (total_send_time / frame_count * 1000) if frame_count > 0 else 0
    avg_packets = total_packets / frame_count if frame_count > 0 else 0

    print("\nAnimation complete!")
    print(f"  Frames: {frame_count}")
    print(f"  Duration: {elapsed:.1f}s")
    print(f"  Average FPS: {actual_fps:.1f}")
    print(f"  Total packets: {total_packets}")
    print(f"  Avg packets/frame: {avg_packets:.2f}")
    print("\nPerformance:")
    print(f"  Avg frame generation: {avg_gen_ms:.2f}ms")
    print(f"  Avg frame send: {avg_send_ms:.2f}ms")
    print(f"  Frame budget ({fps:.0f} FPS): {1000 / fps:.1f}ms")


async def main(
    serial: str | None = None,
    ip: str | None = None,
    duration: float = 10.0,
    fps: float = 30.0,
    effect: str = "auto",
    profile: bool = False,
    iterations: int = 2000,
    warmup: int = 200,
) -> None:
    """Find device and run animation."""
    if profile and not serial and not ip:
        # Synthetic-only mode
        print("=" * 70)
        print("LIFX Animation Profiler - NumPy (synthetic benchmarks only)")
        print("=" * 70)
        run_synthetic_benchmarks()
        return

    if not serial and not ip:
        print("Error: --serial or --ip is required (unless using --profile alone)")
        return

    print("=" * 70)
    print("LIFX Animation Example (NumPy)" + (" (profiling)" if profile else ""))
    print("=" * 70)

    # Find the device
    if serial and ip:
        # Both serial and IP provided - connect directly without discovery
        print(f"\nConnecting directly to {ip} (serial: {serial})")
        device = await Device.connect(ip=ip, serial=serial)
    elif ip:
        print(f"\nSearching for device at IP: {ip}")
        device = await find_by_ip(ip, timeout=5.0)
        if device is None:
            print(f"No device found at IP '{ip}'")
            return
    else:
        assert serial is not None
        print(f"\nSearching for device with serial: {serial}")
        device = await find_by_serial(serial, timeout=5.0)
        if device is None:
            print(f"No device found with serial '{serial}'")
            return

    print(f"Found: {type(device).__name__} at {device.ip}")

    # Connect and run animation
    async with device:
        _, power, label = await device.get_color()  # type: ignore[union-attr]
        print(f"Label: {label}")

        # Check device type
        is_matrix = isinstance(device, MatrixLight)
        is_multizone = isinstance(device, MultiZoneLight)

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
            print("Requires a Matrix or MultiZone device.")
            return

        # Turn on if off
        was_off = power == 0
        if was_off:
            print("\nTurning device ON...")
            await device.set_power(True)
            await asyncio.sleep(1)

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
                    await run_animation(device, duration, fps, effect)
                else:
                    assert isinstance(device, MultiZoneLight)
                    await run_animation(device, duration, fps, effect)
        finally:
            if was_off:
                print("\nTurning device back OFF...")
                await device.set_power(False)

    # Always run synthetic benchmarks after device profiling
    if profile:
        run_synthetic_benchmarks()

    print("\n" + "=" * 70)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run NumPy-optimized animation on a LIFX device",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Effects:
  auto    - Automatically select based on device type (default)
  spiral  - Rainbow spiral pattern (best for matrix)
  wave    - Rainbow wave pattern (best for multizone)
  plasma  - Classic plasma effect
  fire    - Fire/flame effect

Examples:
  # Run with auto-selected effect
  python animation_numpy.py --serial d073d5123456

  # Run plasma effect for 30 seconds at 60 FPS
  python animation_numpy.py --serial d073d5123456 --effect plasma \\
    --duration 30 --fps 60

  # Specify IP for faster connection
  python animation_numpy.py --serial d073d5123456 --ip 192.168.1.100

  # Run synthetic benchmarks only (no device needed)
  python animation_numpy.py --profile

  # Profile animation loop against a device + synthetic benchmarks
  python animation_numpy.py --serial d073d5123456 --ip 192.168.1.100 --profile
        """,
    )
    parser.add_argument(
        "--serial",
        "-s",
        help="Device serial number (12 hex digits)",
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
        "--effect",
        "-e",
        default="auto",
        choices=["auto", "spiral", "wave", "plasma", "fire"],
        help="Animation effect (default: auto)",
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
                args.effect,
                args.profile,
                args.iterations,
                args.warmup,
            )
        )
    except KeyboardInterrupt:
        print("\n\nCancelled by user.")
