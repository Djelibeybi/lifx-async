"""The onboarding guide's examples run, and the API page names everything public.

Every ``python`` block in ``docs/user-guide/onboarding.md`` is executed, in
order and in one shared namespace, against the fakes in ``conftest.py``. The
examples never override a timing default, so the fakes are arranged to make
every phase succeed at once: the host leaves the SoftAP as soon as it is asked
to, the SoftAP accepts every probe, and a watcher reports each device on the
LAN the moment verification starts listening.
"""

from __future__ import annotations

import ast
import asyncio
import getpass
import inspect
import re
from pathlib import Path
from typing import Any

import pytest

import lifx
import lifx.onboard
from lifx import DeviceEventType
from lifx.onboard import bulk as bulk_module
from lifx.onboard import machine
from tests.test_onboard.conftest import (
    HOME_PASSWORD,
    ORIGINAL_SSID,
    FakeSoftApClient,
    FakeWatcher,
    make_joiner,
    make_scanner,
    softap_network,
)

ROOT = Path(__file__).resolve().parents[2]
GUIDE = ROOT / "docs" / "user-guide" / "onboarding.md"
API_PAGE = ROOT / "docs" / "api" / "onboarding.md"

#: The environment variable the guide reads the home password from.
PASSWORD_VARIABLE = "LIFX_HOME_PASSWORD"
#: The guide's synthetic devices, as the scanner shows them and as the LAN
#: later reports them.
GUIDE_SOFTAPS = ("LIFX Candle Color 8274eb", "LIFX Beam 61a0c3")
GUIDE_SERIALS = ("d073d58274eb", "d073d561a0c3")
LAN_ADDRESS = "192.0.2.10"

_PYTHON_BLOCK = re.compile(
    r"^```python[ \t]*\n(.*?)^```[ \t]*$", re.DOTALL | re.MULTILINE
)
_TIMING_KEYWORD = re.compile(
    r"\b(find_timeout|find_poll|wait_timeout|wait_poll|dial_timeout|rejoin_timeout"
    r"|rejoin_poll|auto_join_wait|verify_timeout|verify_poll|scan_interval)\s*="
)
_LITERAL_PASSWORD = re.compile(
    r"""password\s*=\s*["'][^"']|HomeNetwork\(\s*["'][^"']*["']\s*,\s*["'][^"']"""
)


def python_blocks(path: Path) -> list[str]:
    """The source of every ``python`` fenced block in a Markdown file."""
    return _PYTHON_BLOCK.findall(path.read_text(encoding="utf-8"))


class GuideWatcher(FakeWatcher):
    """A watcher that reports every guide device on the LAN once listened to.

    Stands in for ``DeviceWatcher`` wherever the guide constructs one, whether
    the example does it (``async with DeviceWatcher()``) or the library does
    (``verify=True``). Accepts and ignores the real constructor's keywords.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__()

    def add_listener(self, listener: Any) -> Any:
        remove = super().add_listener(listener)
        asyncio.get_running_loop().call_soon(self._announce)
        return remove

    def _announce(self) -> None:
        for serial in GUIDE_SERIALS:
            self.emit(DeviceEventType.ADDED, serial, LAN_ADDRESS)


@pytest.fixture
def guide_namespace(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Names the guide says the reader already has, plus the fakes behind them."""
    monkeypatch.setenv(PASSWORD_VARIABLE, HOME_PASSWORD)
    monkeypatch.setattr(getpass, "getpass", lambda prompt="": HOME_PASSWORD)
    monkeypatch.setattr(lifx, "DeviceWatcher", GuideWatcher)
    for module in (machine, bulk_module):
        monkeypatch.setattr(module, "DeviceWatcher", GuideWatcher)
    # Both entry points build their default control channel in machine.py.
    monkeypatch.setattr(machine, "SoftApConnection", lambda *a, **k: FakeSoftApClient())
    joiner = make_joiner(
        current=ORIGINAL_SSID, reporter=True, forgetter=True, disassociator=True
    )
    joiner.after_disassociate.append(ORIGINAL_SSID)
    disassociate = joiner.disassociate  # type: ignore[attr-defined]

    async def leave_softap() -> None:
        # The fake only clears its SoftAP on rejoin(); leaving ends it too.
        await disassociate()
        joiner.on_softap = None

    joiner.disassociate = leave_softap  # type: ignore[attr-defined]
    return {
        "scanner": make_scanner([softap_network(ssid) for ssid in GUIDE_SOFTAPS]),
        "joiner": joiner,
    }


async def run_block(source: str, namespace: dict[str, Any], name: str) -> None:
    """Execute one block, allowing the top-level ``await`` the guide uses."""
    code = compile(source, name, "exec", flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT)
    # The source is this repository's own checked-in guide, never user input.
    outcome = eval(code, namespace)
    if inspect.isawaitable(outcome):
        await outcome


class TestGuideExamples:
    def test_the_guide_has_examples(self) -> None:
        assert len(python_blocks(GUIDE)) >= 8

    async def test_every_example_runs_with_the_timing_defaults(
        self, guide_namespace: dict[str, Any], capsys: pytest.CaptureFixture[str]
    ) -> None:
        for index, source in enumerate(python_blocks(GUIDE), start=1):
            await run_block(source, guide_namespace, f"onboarding.md block {index}")
        output = capsys.readouterr().out
        assert HOME_PASSWORD not in output

    def test_no_example_overrides_a_timing_default(self) -> None:
        for index, source in enumerate(python_blocks(GUIDE), start=1):
            assert not _TIMING_KEYWORD.search(source), f"block {index}"

    def test_no_example_carries_a_literal_password(self) -> None:
        for index, source in enumerate(python_blocks(GUIDE), start=1):
            assert not _LITERAL_PASSWORD.search(source), f"block {index}"

    @pytest.mark.parametrize("path", [GUIDE, API_PAGE], ids=lambda p: p.name)
    def test_pages_hold_no_em_dash(self, path: Path) -> None:
        assert "\N{EM DASH}" not in path.read_text(encoding="utf-8")


class TestApiPage:
    def test_every_public_name_is_documented(self) -> None:
        page = API_PAGE.read_text(encoding="utf-8")
        missing = [
            name
            for name in lifx.onboard.__all__
            if not re.search(rf"\b{re.escape(name)}\b", page)
        ]
        assert missing == []

    def test_every_mkdocstrings_target_exists(self) -> None:
        page = API_PAGE.read_text(encoding="utf-8")
        for target in re.findall(r"^::: (\S+)", page, re.MULTILINE):
            module_path, _, attribute = target.rpartition(".")
            module = __import__(module_path, fromlist=[attribute])
            assert hasattr(module, attribute), target
