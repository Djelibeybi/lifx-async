"""Shared fixtures for performance benchmark tests."""

from __future__ import annotations

from typing import Any


def pytest_benchmark_update_machine_info(
    config: Any,
    machine_info: dict[str, Any],  # noqa: ARG001
) -> None:
    """Redact hostname from saved benchmark data."""
    machine_info["node"] = "redacted"
