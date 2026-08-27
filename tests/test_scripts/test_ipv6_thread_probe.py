"""Tests for the IPv6/Thread hardware probe's UAT harness.

`scripts/ipv6_thread_probe.py` talks to real Thread devices, so none of its
network stages can be tested here. What *is* testable is everything the UAT
harness added around them: target selection, full-state capture and restore,
the record's shape, and the rule that streaming never gates. Every test below
drives a fake device or a fake animator, and none of them opens a socket.

The probe is imported by module name because `pyproject.toml` puts `scripts`
on `pythonpath`, the same route `tests/test_theme/test_theme_generator.py`
uses for `scripts/generate_theme_data.py`.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import ipv6_thread_probe as probe
import pytest

from lifx.animation.animator import AnimatorStats
from lifx.color import HSBK
from lifx.devices.light import Light
from lifx.devices.matrix import MatrixEffect, MatrixLight
from lifx.network.mdns.types import LifxServiceRecord
from lifx.protocol.protocol_types import FirmwareEffect

# A matrix product (LIFX Candle C), a plain colour bulb, and a switch, so that
# create_device_from_record() returns a MatrixLight, a Light and None
# respectively without any of the three being invented.
MATRIX_PRODUCT_ID = 57
LIGHT_PRODUCT_ID = 27
SWITCH_PRODUCT_ID = 70

# A Thread-shaped ULA literal. Deliberately NOT read as a record of the live
# fleet: an OMR prefix is auto-generated and re-derives whenever the border
# router re-forms the mesh, so no test should encode one as a fact. These
# tests only need an address that parses as a routable IPv6 ULA.
ULA_ADDRESS = "fd00:1::"
TARGET_SERIAL = "d073d5aa11bb"

TILE_COLOURS = [
    [HSBK(10.0, 1.0, 1.0, 3500), HSBK(20.0, 0.5, 0.5, 4000)],
    [HSBK(30.0, 0.25, 0.75, 2700), HSBK(40.0, 0.0, 1.0, 6500)],
]


def make_record(
    serial: str = TARGET_SERIAL,
    ip: str = ULA_ADDRESS,
    product_id: int = MATRIX_PRODUCT_ID,
) -> LifxServiceRecord:
    """Build a service record the way a resolved mDNS sweep would."""
    return LifxServiceRecord(
        serial=serial, ip=ip, port=56700, product_id=product_id, firmware="4.10"
    )


class FakeMatrix(MatrixLight):
    """A MatrixLight that answers from memory and records every write.

    Subclasses the real class rather than duck-typing it, because the probe
    branches on `isinstance(device, MatrixLight)` to decide which state shape
    to capture. A duck would take the plain-light path and prove nothing.
    """

    def __init__(
        self,
        *,
        power: int = 0,
        effect_type: FirmwareEffect = FirmwareEffect.MORPH,
        applies_writes: bool = True,
        colour: HSBK | None = None,
    ) -> None:
        super().__init__(serial=TARGET_SERIAL, ip=ULA_ADDRESS)
        self.calls: list[tuple[str, Any]] = []
        self.applies_writes = applies_writes
        self._effect_type = effect_type
        self._power_level = power
        self._colour = colour if colour is not None else HSBK(10.0, 1.0, 1.0, 3500)

    async def __aenter__(self) -> FakeMatrix:
        """Enter without opening a connection."""
        return self

    async def __aexit__(self, *args: object) -> bool:
        """Exit without closing anything."""
        return False

    async def get_all_tile_colors(self) -> list[list[HSBK]]:
        """Return the captured per-tile image."""
        self.calls.append(("get_all_tile_colors", None))
        return [list(tile) for tile in TILE_COLOURS]

    async def get_power(self) -> int:
        """Return the current power level."""
        self.calls.append(("get_power", None))
        return self._power_level

    async def set_power(self, level: bool | int) -> None:
        """Record the write, applying it only when this fake obeys writes."""
        self.calls.append(("set_power", level))
        if self.applies_writes:
            self._power_level = 65535 if level in (True, 65535) else 0

    async def get_effect(self) -> MatrixEffect:
        """Return the running firmware effect."""
        self.calls.append(("get_effect", None))
        return MatrixEffect(
            effect_type=self._effect_type, speed=5000, duration=0, from_device=True
        )

    async def set_effect(self, *args: object, **kwargs: object) -> None:
        """Record a firmware effect re-application."""
        self.calls.append(("set_effect", kwargs))

    async def set_matrix_colors(
        self, tile_index: int, colors: list[HSBK], duration: int = 0
    ) -> None:
        """Record a per-tile restore."""
        self.calls.append(("set_matrix_colors", (tile_index, list(colors))))

    async def get_color(self) -> tuple[HSBK, int, str]:
        """Return the colour, power and label triple."""
        self.calls.append(("get_color", None))
        return (self._colour, self._power_level, "Test Candle")

    async def set_color(self, color: HSBK, duration: float = 0.0) -> None:
        """Record the write, applying it only when this fake obeys writes."""
        self.calls.append(("set_color", color))
        if self.applies_writes:
            self._colour = color


class RampingMatrix(FakeMatrix):
    """A FakeMatrix whose power readback ramps, the way real firmware does.

    `get_power()` yields each value in `ramp` once before it starts reporting
    what the last write actually set. This is the shape measured against the
    Thread Tube on 2026-08-28: 4980 at t+0.098s, 65535 at t+0.525s. Without a
    double of this shape the settle loop cannot be shown to do anything.
    """

    def __init__(self, *, ramp: list[int], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.ramp = list(ramp)
        self._ramping = False

    async def set_power(self, level: bool | int) -> None:
        """Apply the write and start reporting the ramp, as firmware does."""
        await super().set_power(level)
        self._ramping = True

    async def get_power(self) -> int:
        """Yield the next ramp reading, then defer to the settled level.

        Reads taken before any power write report the resting level, so the
        stage's pre-write capture sees the truth and the ramp only stands
        between the write and its result, which is where it sits in reality.
        """
        if self._ramping and self.ramp:
            self.calls.append(("get_power", None))
            return self.ramp.pop(0)
        return await super().get_power()


class StuckPowerMatrix(FakeMatrix):
    """A FakeMatrix whose power never leaves the ramp.

    Stands for a light that acknowledges the write and then never gets there,
    which is the failure the settle loop must still catch rather than paper
    over.
    """

    async def get_power(self) -> int:
        """Report the same mid-ramp level forever."""
        self.calls.append(("get_power", None))
        return 5242


class LaggingColourMatrix(FakeMatrix):
    """A FakeMatrix that applies colour writes but reports them late."""

    def __init__(self, *, lag: int = 1, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.lag = lag
        self._stale: HSBK | None = None

    async def set_color(self, color: HSBK, duration: float = 0.0) -> None:
        """Apply the write, remembering what the device showed before it."""
        self._stale = self._colour
        await super().set_color(color, duration)

    async def get_color(self) -> tuple[HSBK, int, str]:
        """Report the pre-write colour until the lag is spent."""
        if self._stale is not None and self.lag > 0:
            self.lag -= 1
            self.calls.append(("get_color", None))
            return (self._stale, self._power_level, "Test Candle")
        return await super().get_color()


class FakeLight(Light):
    """A plain Light that answers from memory."""

    def __init__(self) -> None:
        super().__init__(serial=TARGET_SERIAL, ip=ULA_ADDRESS)
        self.calls: list[tuple[str, Any]] = []
        self._colour = HSBK(200.0, 0.4, 0.6, 3000)

    async def get_color(self) -> tuple[HSBK, int, str]:
        """Return the colour, power and label triple."""
        self.calls.append(("get_color", None))
        return (self._colour, 65535, "Desk Lamp")

    async def set_color(self, color: HSBK, duration: float = 0.0) -> None:
        """Record the write."""
        self.calls.append(("set_color", color))

    async def set_power(self, level: bool | int) -> None:
        """Record the write."""
        self.calls.append(("set_power", level))


class FakeAnimator:
    """An Animator double that counts frames and close() calls."""

    def __init__(self, *, raises: bool = False) -> None:
        self.pixel_count = 4
        self.frames = 0
        self.closed = 0
        self.raises = raises

    def send_frame(self, hsbk: list[tuple[int, int, int, int]]) -> AnimatorStats:
        """Count the frame, or blow up if this double is the failing one."""
        self.frames += 1
        if self.raises:
            raise OSError("radio went away mid-frame")
        return AnimatorStats(packets_sent=2, total_time_ms=0.5)

    def close(self) -> None:
        """Record that the socket was released."""
        self.closed += 1


@pytest.fixture
def fast_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    """Shrink the streaming run to a single frame so tests stay quick."""
    monkeypatch.setattr(probe, "_STREAM_SECONDS", 0.05)
    monkeypatch.setattr(probe, "_STREAM_FPS", 20.0)


@pytest.fixture(autouse=True)
def fast_settle(monkeypatch: pytest.MonkeyPatch) -> None:
    """Shrink the control stage's settle window so tests stay quick.

    `run_control_stage` reads these two at call time instead of binding them
    as default arguments, precisely so they can be shrunk here. Without this
    every test driving a device that refuses a write would wait out the real
    two second deadline twice over.
    """
    monkeypatch.setattr(probe, "_SETTLE_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(probe, "_SETTLE_POLL_SECONDS", 0.005)


def use_animator(monkeypatch: pytest.MonkeyPatch, animator: FakeAnimator) -> None:
    """Point the streaming stage at a double instead of the real factories."""

    async def _factory(device: Light) -> Any:
        return animator

    monkeypatch.setattr(probe, "_build_animator", _factory)


class TestSelectTarget:
    """_select_target() resolves --serial to exactly one device, or explains."""

    def test_returns_the_device_matching_the_requested_serial(self) -> None:
        """A serial present in the sweep yields the right device class."""
        records = [make_record(serial="d073d5000001"), make_record()]

        target = probe._select_target(records, TARGET_SERIAL)

        assert isinstance(target, MatrixLight)
        assert target.serial == TARGET_SERIAL
        assert target.ip == ULA_ADDRESS

    def test_tolerates_colons_hyphens_and_upper_case_in_the_serial(self) -> None:
        """Operators paste serials in whatever shape their notes hold."""
        target = probe._select_target([make_record()], "D0:73-D5:AA:11:BB")

        assert isinstance(target, MatrixLight)
        assert target.serial == TARGET_SERIAL

    def test_returns_not_found_for_a_serial_no_record_carries(self) -> None:
        """A mistyped serial is a recorded failure, not a traceback."""
        result = probe._select_target([make_record()], "d073d5ffffff")

        assert isinstance(result, probe.TargetNotFound)
        assert result.serial == "d073d5ffffff"
        assert "no discovered device carries that serial" in result.reason

    def test_returns_not_found_when_the_sweep_found_nothing(self) -> None:
        """An empty record set cannot produce a target."""
        result = probe._select_target([], TARGET_SERIAL)

        assert isinstance(result, probe.TargetNotFound)
        assert "no discovered device carries that serial" in result.reason

    def test_returns_not_found_for_a_zoneless_link_local_address(self) -> None:
        """A link-local literal with no zone ID cannot be routed to."""
        result = probe._select_target([make_record(ip="fe80::1")], TARGET_SERIAL)

        assert isinstance(result, probe.TargetNotFound)
        assert "no zone ID" in result.reason

    def test_returns_not_found_for_a_relay_only_product(self) -> None:
        """A switch has nothing to control, so there is no target."""
        record = make_record(product_id=SWITCH_PRODUCT_ID)

        result = probe._select_target([record], TARGET_SERIAL)

        assert isinstance(result, probe.TargetNotFound)
        assert "relay/button-only" in result.reason


class TestStageResult:
    """_stage_result() maps an observed outcome onto the record's vocabulary."""

    def test_a_successful_stage_is_passed(self) -> None:
        """True means the stage ran and every operation held."""
        assert probe._stage_result(True) == "passed"

    def test_a_stage_that_ran_and_failed_is_failed(self) -> None:
        """False means the stage ran and something did not hold."""
        assert probe._stage_result(False) == "failed"

    def test_a_stage_that_raised_is_failed(self) -> None:
        """An exception is an observed failure, not an absence of evidence."""
        assert probe._stage_result(OSError("boom")) == "failed"

    def test_a_stage_never_attempted_is_not_run(self) -> None:
        """None is the honest "we never got there" value."""
        assert probe._stage_result(None) == "not_run"


class TestBuildUatRecord:
    """_build_uat_record() assembles what plan 10-06's gate reads."""

    def test_carries_every_field_the_merge_gate_checks(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The full key set, with the stages exactly as observed."""
        monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/git")
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *args, **kwargs: subprocess.CompletedProcess(
                args=args, returncode=0, stdout="abc1234\n", stderr=""
            ),
        )
        outcome = probe.TargetOutcome(
            connect="passed", control="passed", streaming="failed", restored=True
        )

        record = probe._build_uat_record(TARGET_SERIAL, ULA_ADDRESS, outcome)

        assert set(record) == {
            "schema_version",
            "kind",
            "phase",
            "device_serial",
            "device_ip",
            "timestamp",
            "library_head",
            "stages",
            "restored",
        }
        assert record["schema_version"] == 1
        assert record["kind"] == "thread-hardware-uat"
        assert record["phase"] == "10"
        assert record["device_serial"] == TARGET_SERIAL
        assert record["device_ip"] == ULA_ADDRESS
        assert record["library_head"] == "abc1234"
        assert record["stages"] == {
            "connect": "passed",
            "control": "passed",
            "streaming": "failed",
        }
        assert record["restored"] is True

    def test_timestamp_is_iso_8601_with_a_timezone(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A naive timestamp cannot be checked against the phase window."""
        from datetime import datetime

        monkeypatch.setattr(shutil, "which", lambda name: None)

        record = probe._build_uat_record(TARGET_SERIAL, None, probe.TargetOutcome())

        stamp = record["timestamp"]
        assert isinstance(stamp, str)
        assert datetime.fromisoformat(stamp).tzinfo is not None

    def test_library_head_is_none_when_git_is_not_on_the_path(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No git means no head SHA, recorded honestly as null."""
        monkeypatch.setattr(shutil, "which", lambda name: None)

        record = probe._build_uat_record(
            TARGET_SERIAL, ULA_ADDRESS, probe.TargetOutcome()
        )

        assert record["library_head"] is None

    def test_library_head_is_none_when_git_rev_parse_fails(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A git that exists but cannot answer is not a reason to crash."""
        monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/git")

        def _boom(*args: object, **kwargs: object) -> None:
            raise subprocess.CalledProcessError(128, "git")

        monkeypatch.setattr(subprocess, "run", _boom)

        record = probe._build_uat_record(
            TARGET_SERIAL, ULA_ADDRESS, probe.TargetOutcome()
        )

        assert record["library_head"] is None


class TestWriteUatRecord:
    """_write_uat_record() puts valid JSON on disk."""

    def test_writes_json_that_round_trips(self, tmp_path: Path) -> None:
        """The gate reads this file with json.loads, so it must parse."""
        outcome = probe.TargetOutcome(connect="passed", control="passed")
        record = probe._build_uat_record(TARGET_SERIAL, ULA_ADDRESS, outcome)
        path = tmp_path / "nested" / "10-UAT-RESULTS.json"

        probe._write_uat_record(record, path)

        loaded = json.loads(path.read_text(encoding="utf-8"))
        assert loaded["stages"]["control"] == "passed"
        assert loaded["kind"] == "thread-hardware-uat"

    def test_the_serial_is_a_12_digit_hex_string_never_bytes(
        self, tmp_path: Path
    ) -> None:
        """User-visible serials are strings on the way out (CLAUDE.md)."""
        record = probe._build_uat_record(
            TARGET_SERIAL, ULA_ADDRESS, probe.TargetOutcome()
        )
        path = tmp_path / "record.json"

        probe._write_uat_record(record, path)

        serial = json.loads(path.read_text(encoding="utf-8"))["device_serial"]
        assert isinstance(serial, str)
        assert len(serial) == 12
        assert int(serial, 16) >= 0


class TestCaptureDeviceState:
    """_capture_device_state() reads the shape the device actually holds."""

    async def test_a_matrix_capture_reads_tiles_power_and_effect(self) -> None:
        """get_color() cannot represent a per-pixel image or a running effect."""
        device = FakeMatrix(power=65535, effect_type=FirmwareEffect.MORPH)

        state = await probe._capture_device_state(device)

        called = [name for name, _ in device.calls]
        assert "get_all_tile_colors" in called
        assert "get_power" in called
        assert "get_effect" in called
        assert state.kind == "matrix"
        assert state.tiles == TILE_COLOURS
        assert state.power == 65535
        assert state.effect is not None
        assert state.effect.effect_type is FirmwareEffect.MORPH

    async def test_a_matrix_with_no_running_effect_captures_none(self) -> None:
        """OFF is not an effect to put back, so nothing is recorded."""
        device = FakeMatrix(effect_type=FirmwareEffect.OFF)

        state = await probe._capture_device_state(device)

        assert state.effect is None

    async def test_a_plain_light_capture_takes_the_get_color_path(self) -> None:
        """A bulb holds one colour, and get_color() carries its power too."""
        device = FakeLight()

        state = await probe._capture_device_state(device)

        assert [name for name, _ in device.calls] == ["get_color"]
        assert state.kind == "light"
        assert state.color == HSBK(200.0, 0.4, 0.6, 3000)
        assert state.power == 65535


class TestRestoreDeviceState:
    """_restore_device_state() puts a device back exactly as it was found."""

    async def test_restores_each_tile_then_power_then_the_effect(self) -> None:
        """Order matters: paint, then power, then re-arm the firmware effect."""
        device = FakeMatrix(power=65535, effect_type=FirmwareEffect.MORPH)
        state = await probe._capture_device_state(device)
        device.calls.clear()

        restored = await probe._restore_device_state(device, state)

        assert restored is True
        names = [name for name, _ in device.calls]
        assert names == [
            "set_matrix_colors",
            "set_matrix_colors",
            "set_power",
            "set_effect",
        ]
        writes = [
            payload for name, payload in device.calls if name == "set_matrix_colors"
        ]
        assert writes == [(0, TILE_COLOURS[0]), (1, TILE_COLOURS[1])]
        assert device.calls[2][1] == 65535

    async def test_speed_is_converted_back_to_seconds_for_set_effect(self) -> None:
        """get_effect() reports milliseconds; set_effect() takes seconds."""
        device = FakeMatrix(effect_type=FirmwareEffect.MORPH)
        state = await probe._capture_device_state(device)
        device.calls.clear()

        await probe._restore_device_state(device, state)

        kwargs = next(payload for name, payload in device.calls if name == "set_effect")
        assert kwargs["speed"] == 5.0
        assert kwargs["effect_type"] is FirmwareEffect.MORPH

    async def test_no_effect_is_reapplied_when_none_was_running(self) -> None:
        """Arming an effect the device never had would not be a restore."""
        device = FakeMatrix(effect_type=FirmwareEffect.OFF)
        state = await probe._capture_device_state(device)
        device.calls.clear()

        await probe._restore_device_state(device, state)

        assert "set_effect" not in [name for name, _ in device.calls]

    async def test_a_plain_light_is_restored_by_colour_and_power(self) -> None:
        """The light path writes the captured triple back."""
        device = FakeLight()
        state = await probe._capture_device_state(device)
        device.calls.clear()

        restored = await probe._restore_device_state(device, state)

        assert restored is True
        assert [name for name, _ in device.calls] == ["set_color", "set_power"]
        assert device.calls[0][1] == HSBK(200.0, 0.4, 0.6, 3000)
        assert device.calls[1][1] == 65535

    async def test_power_alone_is_restored_when_no_colour_was_captured(self) -> None:
        """The defensive arm: a colourless capture still restores power.

        `_capture_device_state()` never produces this today, so the guard is
        purely defensive. Covering it here keeps the helper free of partial
        branches, which is the standard the rest of this project holds
        (auto-memory project_codecov_branch_patch).
        """
        device = FakeLight()
        state = probe.CapturedState(kind="light", power=0, color=None)

        restored = await probe._restore_device_state(device, state)

        assert restored is True
        assert [name for name, _ in device.calls] == ["set_power"]

    async def test_a_failing_restore_is_reported_and_returns_false(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A device left mid-run must be visible, never silently swallowed."""
        device = FakeMatrix()
        state = await probe._capture_device_state(device)

        async def _boom(*args: object, **kwargs: object) -> None:
            raise OSError("device stopped answering")

        device.set_matrix_colors = _boom  # type: ignore[method-assign]

        restored = await probe._restore_device_state(device, state)

        assert restored is False
        printed = capsys.readouterr().out
        assert "could not restore" in printed
        assert TARGET_SERIAL in printed
        assert "by hand" in printed


class TestSettle:
    """_settle() waits out a ramp without ever relaxing the predicate."""

    async def test_an_already_correct_reading_costs_no_extra_polling(self) -> None:
        """The happy path must not add latency to a device that is ready."""
        reads = 0

        async def read() -> int:
            nonlocal reads
            reads += 1
            return 65535

        settled, value = await probe._settle(read, lambda v: v == 65535, 1.0, 0.001)

        assert settled is True
        assert value == 65535
        assert reads == 1

    async def test_a_late_value_inside_the_deadline_is_accepted(self) -> None:
        """The ramp shape measured on real hardware has to pass."""
        values = iter([4980, 20000, 65535])

        async def read() -> int:
            return next(values)

        settled, value = await probe._settle(read, lambda v: v == 65535, 1.0, 0.001)

        assert settled is True
        assert value == 65535

    async def test_a_value_that_never_arrives_fails_and_names_what_it_saw(self) -> None:
        """A real failure must stay diagnosable, not collapse into a timeout."""

        async def read() -> int:
            return 5242

        settled, value = await probe._settle(read, lambda v: v == 65535, 0.02, 0.001)

        assert settled is False
        assert value == 5242


class TestStageTarget:
    """The mutating section always restores and always records honestly."""

    async def test_a_device_that_applies_writes_passes_control(self) -> None:
        """The happy path: both roundtrips read back as asked."""
        device = FakeMatrix()
        outcome = probe.TargetOutcome()

        await probe.stage_target(device, outcome)

        assert outcome.connect == "passed"
        assert outcome.control == "passed"
        assert outcome.streaming == "not_run"
        assert outcome.restored is True
        assert probe._exit_code(outcome) == 0

    async def test_a_device_that_ignores_writes_fails_control(self) -> None:
        """The readback assertion must be able to fail, or it proves nothing."""
        device = FakeMatrix(applies_writes=False)
        outcome = probe.TargetOutcome()

        await probe.stage_target(device, outcome)

        assert outcome.control == "failed"
        assert probe._exit_code(outcome) == 1

    async def test_a_ramping_power_readback_still_passes(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The regression this fix exists for.

        Against the real Tube on 2026-08-28 the probe read 5242 one round trip
        after `set_power(True)` and failed the stage, even though the device
        reached 65535 a few hundred milliseconds later. Before the settle loop
        this test fails with exactly that reading.
        """
        device = RampingMatrix(ramp=[4980, 20000], power=0)
        outcome = probe.TargetOutcome()

        await probe.stage_target(device, outcome)

        assert outcome.control == "passed"
        assert device.ramp == []
        assert "moved power 0 -> 65535" in capsys.readouterr().out

    async def test_power_that_never_settles_fails_with_the_last_reading(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Waiting longer must not become waiting forever, or passing anyway."""
        device = StuckPowerMatrix(power=0)
        outcome = probe.TargetOutcome()

        await probe.stage_target(device, outcome)

        assert outcome.control == "failed"
        assert "never reached 65535" in capsys.readouterr().out

    async def test_an_already_on_light_is_driven_off_first(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Turning an on light on again would assert nothing.

        The stage drives it off first so the on-write is an observable
        transition, mirroring how the colour target is derived from the
        pre-write reading rather than hardcoded.
        """
        device = FakeMatrix(power=65535)
        outcome = probe.TargetOutcome()

        await probe.stage_target(device, outcome)

        assert outcome.control == "passed"
        assert ("set_power", False) in device.calls
        assert "moved power 0 -> 65535" in capsys.readouterr().out

    async def test_an_on_light_that_ignores_the_off_write_is_not_a_pass(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A level the device already held cannot count as a successful write."""
        device = FakeMatrix(power=65535, applies_writes=False)
        outcome = probe.TargetOutcome()

        await probe.stage_target(device, outcome)

        out = capsys.readouterr().out
        assert outcome.control == "failed"
        assert "never reached 0" in out
        assert "already held" in out

    async def test_a_lagging_colour_readback_still_passes(self) -> None:
        """Colour is polled for the same reason as power.

        The colour readback won the race on the 2026-08-28 hardware run, but
        winning once is not evidence that it cannot lose, so the same settle
        loop covers it and this pins the behaviour.
        """
        device = LaggingColourMatrix(lag=2, power=0)
        outcome = probe.TargetOutcome()

        await probe.stage_target(device, outcome)

        assert outcome.control == "passed"
        assert device.lag == 0

    async def test_restoration_runs_after_an_injected_control_failure(self) -> None:
        """A raising set_color must not skip the restore."""
        device = FakeMatrix()

        async def _boom(*args: object, **kwargs: object) -> None:
            raise OSError("set_color went nowhere")

        device.set_color = _boom  # type: ignore[method-assign]
        outcome = probe.TargetOutcome()

        await probe.stage_target(device, outcome)

        assert outcome.control == "failed"
        assert outcome.restored is True
        assert "set_matrix_colors" in [name for name, _ in device.calls]

    async def test_restoration_runs_after_a_keyboard_interrupt(self) -> None:
        """An interrupt must not leave a production light mid-run.

        A KeyboardInterrupt is a BaseException, so it slips past the per-stage
        `except Exception` handlers and is the only thing that actually
        exercises the outer `finally`. Without this test a mutation moving the
        restore out of that `finally` and onto the happy path passes the whole
        suite, which is how this case was found.
        """
        device = FakeMatrix()

        async def _interrupt(*args: object, **kwargs: object) -> None:
            raise KeyboardInterrupt

        device.set_color = _interrupt  # type: ignore[method-assign]
        outcome = probe.TargetOutcome()

        with pytest.raises(KeyboardInterrupt):
            await probe.stage_target(device, outcome)

        assert outcome.restored is True
        assert "set_matrix_colors" in [name for name, _ in device.calls]
        assert outcome.control == "not_run"

    async def test_a_failing_restore_lands_in_the_record(self) -> None:
        """`restored: false` is how the operator learns to fix it by hand."""
        device = FakeMatrix()

        async def _boom(*args: object, **kwargs: object) -> None:
            raise OSError("no route to host")

        device.set_matrix_colors = _boom  # type: ignore[method-assign]
        outcome = probe.TargetOutcome()

        await probe.stage_target(device, outcome)

        assert outcome.restored is False
        record = probe._build_uat_record(device.serial, device.ip, outcome)
        assert record["restored"] is False

    async def test_a_capture_failure_is_recorded_as_a_failed_connect(self) -> None:
        """If the pre-run state cannot be read, nothing may be written."""
        device = FakeMatrix()

        async def _boom(*args: object, **kwargs: object) -> None:
            raise OSError("timed out reading tiles")

        device.get_all_tile_colors = _boom  # type: ignore[method-assign]
        outcome = probe.TargetOutcome()

        await probe.stage_target(device, outcome)

        assert outcome.connect == "failed"
        assert outcome.control == "not_run"
        assert "set_matrix_colors" not in [name for name, _ in device.calls]
        assert probe._exit_code(outcome) == 1


class TestStreamingStage:
    """Streaming is an artefact: it is recorded, and it gates nothing."""

    async def test_frames_are_delivered_and_the_socket_is_closed(
        self, monkeypatch: pytest.MonkeyPatch, fast_stream: None
    ) -> None:
        """A clean run sends frames and releases the animator's socket."""
        animator = FakeAnimator()
        use_animator(monkeypatch, animator)

        result = await probe.run_streaming_stage(FakeMatrix())

        assert result is True
        assert animator.frames >= 1
        assert animator.closed == 1

    async def test_close_runs_even_when_the_frame_run_raises(
        self, monkeypatch: pytest.MonkeyPatch, fast_stream: None
    ) -> None:
        """A streaming exception must not strand the raw UDP socket."""
        animator = FakeAnimator(raises=True)
        use_animator(monkeypatch, animator)

        with pytest.raises(OSError):
            await probe.run_streaming_stage(FakeMatrix())

        assert animator.closed == 1

    async def test_a_failed_stream_does_not_change_the_exit_code(
        self, monkeypatch: pytest.MonkeyPatch, fast_stream: None
    ) -> None:
        """Control passing while streaming fails is an allowed outcome."""
        animator = FakeAnimator(raises=True)
        use_animator(monkeypatch, animator)
        outcome = probe.TargetOutcome()

        await probe.stage_target(FakeMatrix(), outcome, stream=True)

        assert outcome.control == "passed"
        assert outcome.streaming == "failed"
        assert outcome.restored is True
        assert probe._exit_code(outcome) == 0

    async def test_streaming_is_not_run_when_the_flag_is_absent(
        self, monkeypatch: pytest.MonkeyPatch, fast_stream: None
    ) -> None:
        """Without --stream no animator is built at all."""
        animator = FakeAnimator()
        use_animator(monkeypatch, animator)
        outcome = probe.TargetOutcome()

        await probe.stage_target(FakeMatrix(), outcome)

        assert outcome.streaming == "not_run"
        assert animator.frames == 0
        record = probe._build_uat_record("d073d5aa11bb", ULA_ADDRESS, outcome)
        stages = record["stages"]
        assert isinstance(stages, dict)
        assert stages["streaming"] == "not_run"


class TestExitCode:
    """_exit_code() reads the gating stages and only those."""

    def test_a_clean_control_run_exits_zero(self) -> None:
        """Both gating stages passed."""
        outcome = probe.TargetOutcome(connect="passed", control="passed")

        assert probe._exit_code(outcome) == 0

    def test_a_failed_connect_exits_non_zero(self) -> None:
        """Connect gates: nothing downstream can be trusted without it."""
        outcome = probe.TargetOutcome(connect="failed")

        assert probe._exit_code(outcome) == 1

    def test_a_failed_stream_alone_exits_zero(self) -> None:
        """SPEC Requirement 9: the streaming run does not gate."""
        outcome = probe.TargetOutcome(
            connect="passed", control="passed", streaming="failed"
        )

        assert probe._exit_code(outcome) == 0
