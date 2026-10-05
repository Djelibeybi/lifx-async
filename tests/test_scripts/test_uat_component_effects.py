"""Tests for the component effects hardware UAT script."""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

from lifx.exceptions import LifxUnsupportedCommandError

SCRIPT = Path(__file__).parents[2] / "scripts" / "uat_component_effects.py"
SERIAL = "d073d5000123"
ADDRESS = "192.0.2.10"


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("uat_component_effects", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class _RefusingLight:
    """A connected light whose first streaming call is refused as Thread."""

    async def __aenter__(self) -> _RefusingLight:
        raise LifxUnsupportedCommandError(
            f"start_effect() would stream animation frames to {SERIAL}, a Thread "
            "device. Pass enable_thread=True to stream to it anyway"
        )

    async def __aexit__(self, *exc: object) -> None:
        return None


async def test_thread_refusal_prints_no_identifiers(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    uat = _load_script()

    async def connect(ip: str) -> _RefusingLight:
        return _RefusingLight()

    monkeypatch.setattr(uat.Device, "connect", connect)
    args = argparse.Namespace(
        ceiling=ADDRESS, mirror=None, report=None, enable_thread=False
    )

    assert await uat.main(args) == 2

    output = capsys.readouterr().out
    assert "--enable-thread" in output
    assert SERIAL not in output
    assert ADDRESS not in output
