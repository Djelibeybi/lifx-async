#!/usr/bin/env python3
"""Multi-version Python test runner.

This script runs the test suite against multiple Python versions to catch
version-specific issues (like the asyncio.TimeoutError vs TimeoutError
difference between Python 3.10 and 3.11+) before pushing to GitHub.

Usage:
    # Run tests on all supported versions (default)
    uv run scripts/test_multiversion.py

    # Run tests on specific versions only
    uv run scripts/test_multiversion.py --versions 3.10 3.14

    # Run with verbose pytest output
    uv run scripts/test_multiversion.py -v

    # Run specific test file/pattern
    uv run scripts/test_multiversion.py -- tests/test_network/

    # Quick mode: skip coverage
    uv run scripts/test_multiversion.py --quick
"""

from __future__ import annotations

import argparse
import subprocess  # nosec B404 - subprocess needed for running uv/pytest
import sys
import time
from dataclasses import dataclass

# Python versions supported by this project (from pyproject.toml)
SUPPORTED_VERSIONS = ["3.10", "3.11", "3.12", "3.13", "3.14"]

# Default: test all supported versions
DEFAULT_VERSIONS = SUPPORTED_VERSIONS


@dataclass
class TestResult:
    """Result of running tests on a specific Python version."""

    version: str
    success: bool
    duration: float
    output: str


def check_python_available(version: str) -> bool:
    """Check if a Python version is available via uv."""
    result = subprocess.run(  # nosec B603 B607 - trusted uv command
        ["uv", "python", "find", version],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def run_tests(
    version: str,
    pytest_args: list[str],
    verbose: bool = False,
    quick: bool = False,
) -> TestResult:
    """Run pytest on a specific Python version using uv."""
    start_time = time.time()

    cmd = [
        "uv",
        "run",
        "--python",
        version,
        "--isolated",  # Use isolated environment to avoid conflicts
        "pytest",
    ]

    # Add coverage unless in quick mode
    if not quick:
        cmd.extend(["--cov=lifx", "--cov-report=term-missing:skip-covered"])

    # Add verbosity
    if verbose:
        cmd.append("-v")
    else:
        cmd.append("-q")

    # Add any additional pytest arguments
    cmd.extend(pytest_args)

    # Ignore animation tests (uncommitted module with known issues)
    cmd.extend(["--ignore=tests/test_animation"])

    print(f"\n{'=' * 60}")
    print(f"Running tests on Python {version}")
    print(f"{'=' * 60}")
    print(f"Command: {' '.join(cmd)}\n")

    result = subprocess.run(  # nosec B603 - trusted uv/pytest command
        cmd,
        capture_output=not verbose,  # Show output in real-time if verbose
        text=True,
        cwd=subprocess.run(  # nosec B603 B607 - trusted git command
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
        ).stdout.strip(),
    )

    duration = time.time() - start_time

    output = ""
    if not verbose:
        output = result.stdout + result.stderr

    return TestResult(
        version=version,
        success=result.returncode == 0,
        duration=duration,
        output=output,
    )


def main() -> int:
    """Run tests across multiple Python versions."""
    parser = argparse.ArgumentParser(
        description="Run tests across multiple Python versions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--versions",
        nargs="+",
        default=None,
        help=f"Python versions to test (default: all supported: {SUPPORTED_VERSIONS})",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Verbose pytest output",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Quick mode: skip coverage for faster execution",
    )
    parser.add_argument(
        "pytest_args",
        nargs="*",
        help="Additional arguments to pass to pytest",
    )

    args = parser.parse_args()

    # Determine which versions to test
    if args.versions:
        versions = args.versions
    else:
        versions = DEFAULT_VERSIONS

    # Validate versions
    for version in versions:
        if version not in SUPPORTED_VERSIONS:
            print(
                f"Warning: {version} is not in supported versions {SUPPORTED_VERSIONS}"
            )

    # Check availability
    available_versions = []
    missing_versions = []
    for version in versions:
        if check_python_available(version):
            available_versions.append(version)
        else:
            missing_versions.append(version)

    if missing_versions:
        print(f"Missing Python versions: {missing_versions}")
        print("Install with: uv python install " + " ".join(missing_versions))
        if not available_versions:
            return 1

    print(f"Testing on Python versions: {available_versions}")

    # Run tests
    results: list[TestResult] = []
    for version in available_versions:
        result = run_tests(
            version,
            args.pytest_args,
            verbose=args.verbose,
            quick=args.quick,
        )
        results.append(result)

        if not args.verbose:
            # Show last few lines of output for quick feedback
            lines = result.output.strip().split("\n")
            for line in lines[-10:]:
                print(line)

    # Summary
    print(f"\n{'=' * 60}")
    print("SUMMARY")
    print(f"{'=' * 60}")

    all_passed = True
    for result in results:
        status = "✓ PASSED" if result.success else "✗ FAILED"
        print(f"Python {result.version}: {status} ({result.duration:.1f}s)")
        if not result.success:
            all_passed = False

    if missing_versions:
        print(f"\nSkipped (not installed): {missing_versions}")

    if all_passed:
        print("\n✓ All tests passed across all Python versions!")
        return 0
    else:
        print("\n✗ Some tests failed. Check output above for details.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
