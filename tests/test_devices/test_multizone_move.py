"""Tests for MultiZoneEffect.move(): the golden-packet backstop and emulator round trip.

This module carries module-scope imports only, so ``PLC0415`` applies to it
unchanged.
"""

from __future__ import annotations

import ast
import dataclasses
import inspect
import logging
import re
import textwrap
import warnings
from collections.abc import Iterator
from contextlib import contextmanager
from itertools import permutations
from pathlib import Path
from typing import Any, cast
from unittest.mock import AsyncMock, patch

import pytest
from lifx_emulator import EmulatedLifxServer
from lifx_emulator.scenarios import HierarchicalScenarioManager

from lifx.api import DeviceGroup
from lifx.color import HSBK, Colors
from lifx.devices.multizone import MultiZoneEffect, MultiZoneLight
from lifx.exceptions import (
    LifxDeviceNotFoundError,
    LifxProtocolError,
    LifxTimeoutError,
    LifxUnsupportedCommandError,
)
from lifx.protocol import packets
from lifx.protocol.protocol_types import Direction, FirmwareEffect
from lifx.theme.generators import MultiZoneGenerator
from lifx.theme.theme import Theme


def _python_example(obj: object) -> str:
    """Extract the single fenced ``python`` example from obj's docstring.

    Args:
        obj: An object whose docstring holds exactly one ```python fenced
            block.

    Returns:
        The dedented source of that block.
    """
    doc = inspect.getdoc(obj)
    assert doc is not None, f"{obj!r} has no docstring"
    blocks = re.findall(r"```python\n(.*?)```", doc, re.DOTALL)
    assert len(blocks) == 1, (
        f"expected exactly one python example in {obj!r}'s docstring, "
        f"found {len(blocks)}"
    )
    return textwrap.dedent(blocks[0])


def _markdown_section_examples(path: Path, heading: str) -> list[str]:
    """Return every fenced ``python`` block in a markdown section.

    The section runs from the line exactly equal to ``heading`` up to (but
    not including) the next line starting with ``## ``.

    Args:
        path: Markdown file to read.
        heading: Exact heading line to find, for example
            ``"## Firmware Move effect"``.

    Returns:
        The dedented source of each fenced ```python block found in the
        section, in document order.
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    start = lines.index(heading) + 1
    end = start
    while end < len(lines) and not lines[end].startswith("## "):
        end += 1
    body = "\n".join(lines[start:end])
    blocks = re.findall(r"```python\n(.*?)```", body, re.DOTALL)
    assert blocks, f"no python examples found under {heading!r} in {path}"
    return [textwrap.dedent(block) for block in blocks]


async def _run_example(source: str, namespace: dict[str, Any]) -> None:
    """Compile and execute a docstring example, awaiting it if it is async.

    Args:
        source: Python source, possibly containing a top-level ``await``.
        namespace: Globals the example runs against (for example
            ``{"light": strip}``).
    """
    code = compile(
        source, "<docstring example>", "exec", flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT
    )
    # The source is this repository's own docstring, extracted at test time,
    # not untrusted external input, so compile()+eval() is the intended
    # verbatim-execution harness rather than a code-injection risk.
    result = eval(code, namespace)  # noqa: S307
    if inspect.iscoroutine(result):
        await result


@contextmanager
def _received_packets(
    server: EmulatedLifxServer, serial: str, pkt_type: int | None = None
) -> Iterator[list[tuple[Any, Any]]]:
    """Capture packets an emulated device received, in arrival order.

    Wraps ``server.get_device(serial).process_packet`` so every call the
    server thread makes to it is recorded. The caller MUST end the ``with``
    block with a request-response round trip to the same device (for
    example, an awaited ``get_effect()``): on lifx-emulator-core 3.7.0, an
    acknowledged SET returns to the caller when the emulator's fast-path ack
    is sent, which precedes ``process_packet()`` running on the emulator
    thread, so a capture closed straight after an awaited SET can miss it.
    The emulator handles datagrams in arrival order, so a reply to the
    closing round trip proves every earlier packet was already processed.

    Args:
        server: The emulator server hosting the device.
        serial: Serial of the device to watch.
        pkt_type: When given, only calls whose header carries this
            ``pkt_type`` are kept.

    Yields:
        A list that, once the ``with`` block exits, holds a
        ``(header, packet)`` tuple per recorded call, in arrival order,
        filtered to ``pkt_type`` when one was given.
    """
    device = server.get_device(serial)
    assert device is not None, f"no emulated device for serial {serial}"
    captured: list[tuple[Any, Any]] = []
    with patch.object(
        device, "process_packet", wraps=device.process_packet
    ) as mock_process_packet:
        yield captured
        for call in mock_process_packet.call_args_list:
            args, kwargs = call.args, call.kwargs
            header = args[0] if args else kwargs["header"]
            packet = args[1] if len(args) > 1 else kwargs.get("packet")
            if pkt_type is None or header.pkt_type == pkt_type:
                captured.append((header, packet))


class TestGoldenMovePacket:
    """The raw Home Assistant construction and move() serialise identically."""

    @pytest.mark.parametrize("direction", [Direction.FORWARD, Direction.REVERSED])
    @pytest.mark.parametrize("speed", [0.0, 0.0015, 5.0, 12.345])
    async def test_raw_and_typed_paths_serialise_identically(
        self,
        multizone_light: MultiZoneLight,
        direction: Direction,
        speed: float,
    ) -> None:
        """Home Assistant's hand-encoded parameters and move() match on the wire."""
        raw = MultiZoneEffect(
            FirmwareEffect.MOVE,
            round(speed * 1000),
            parameters=[0, int(direction), 0, 0, 0, 0, 0, 0],
        )
        typed = MultiZoneEffect.move(direction, speed)
        assert typed == raw

        multizone_light.connection.request.return_value = True

        await multizone_light.set_effect(raw)
        raw_packet = multizone_light.connection.request.call_args[0][0]
        raw_bytes = raw_packet.pack()
        multizone_light.connection.request.reset_mock()

        await multizone_light.set_effect(typed)
        typed_packet = multizone_light.connection.request.call_args[0][0]
        typed_bytes = typed_packet.pack()

        assert raw_bytes == typed_bytes


@pytest.mark.emulator
class TestMoveBuilderRoundTrip:
    """MultiZoneEffect.move() reaches an emulated strip with the right wire values."""

    async def test_move_reaches_emulated_strip_with_direction_and_speed(
        self,
        emulator_devices: DeviceGroup,
        emulator_server: tuple[int, EmulatedLifxServer, HierarchicalScenarioManager],
    ) -> None:
        """Direction comes from the received packet; type/speed from get_effect().

        lifx-emulator-core 3.7.0's ``GetEffectHandler`` hard-codes every Move
        parameter slot to 0, so direction cannot be read back through
        ``get_effect()``; it stores speed as whole seconds
        (``speed // 1000``), so only a whole-second speed round-trips.
        """
        _, server, _ = emulator_server
        strip = cast(MultiZoneLight, emulator_devices[4])

        with _received_packets(server, strip.serial, pkt_type=508) as captured:
            async with strip:
                await strip.set_effect(MultiZoneEffect.move(Direction.FORWARD, 5.0))
                effect = await strip.get_effect()

        assert effect.effect_type is FirmwareEffect.MOVE
        assert effect.speed == 5000
        assert len(captured) == 1
        _, packet = captured[0]
        assert packet.settings.speed == 5000
        assert packet.settings.parameter.parameter1 == int(Direction.FORWARD)


class TestMoveBuilderValidation:
    """Every R4 direction, boundary, precision and type rule on move()."""

    @pytest.mark.parametrize(
        ("direction", "expected"),
        [
            (Direction.FORWARD, Direction.FORWARD),
            (Direction.REVERSED, Direction.REVERSED),
            ("forward", Direction.FORWARD),
            ("Reversed", Direction.REVERSED),
            ("FORWARD", Direction.FORWARD),
        ],
    )
    def test_direction_accepts_member_or_case_insensitive_name(
        self, direction: Direction | str, expected: Direction
    ) -> None:
        effect = MultiZoneEffect.move(direction, 1.0)
        assert effect.parameters is not None
        assert effect.parameters[1] == int(expected)

    @pytest.mark.parametrize("direction", ["sideways", "", 1, None, True])
    def test_direction_rejects_everything_else(self, direction: object) -> None:
        with pytest.raises(ValueError, match="forward") as exc_info:
            MultiZoneEffect.move(direction, 1.0)  # type: ignore[arg-type]
        assert "reversed" in str(exc_info.value)

    def test_speed_and_duration_accept_zero(self) -> None:
        effect = MultiZoneEffect.move(Direction.FORWARD, 0.0, duration=0)
        assert effect.speed == 0
        assert effect.duration == 0

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"speed": -1.0},
            {"speed": -0.0001},
            {"speed": float("inf")},
            {"speed": float("nan")},
            {"duration": -1.0},
            {"duration": float("inf")},
        ],
    )
    def test_negative_or_non_finite_raises_value_error(
        self, kwargs: dict[str, float]
    ) -> None:
        args: dict[str, object] = {
            "direction": Direction.FORWARD,
            "speed": 1.0,
            "duration": 0,
        }
        args.update(kwargs)
        with pytest.raises(ValueError):
            MultiZoneEffect.move(**args)  # type: ignore[arg-type]

    def test_non_numeric_seconds_raise_type_error(self) -> None:
        """A non-numeric or bool speed/duration raises TypeError, not ValueError."""
        cases: list[dict[str, object]] = [
            {"speed": "5"},
            {"speed": None},
            {"speed": True},
            {"duration": "2"},
            {"duration": None},
        ]
        for case in cases:
            kwargs: dict[str, object] = {
                "direction": Direction.FORWARD,
                "speed": 1.0,
                "duration": 0,
            }
            kwargs.update(case)
            with pytest.raises(TypeError) as exc_info:
                MultiZoneEffect.move(**kwargs)  # type: ignore[arg-type]
            assert type(exc_info.value) is TypeError
            field = next(iter(case))
            assert field in str(exc_info.value)

    def test_huge_seconds_raise_value_error_not_overflow_error(self) -> None:
        """No numeric input escapes the ValueError contract as OverflowError."""
        cases: list[dict[str, object]] = [
            {"speed": 10**400},
            {"duration": 10**400},
            {"speed": 1e306},
            {"duration": 1e300},
        ]
        for case in cases:
            kwargs: dict[str, object] = {
                "direction": Direction.FORWARD,
                "speed": 1.0,
                "duration": 0,
            }
            kwargs.update(case)
            with pytest.raises(ValueError) as exc_info:
                MultiZoneEffect.move(**kwargs)  # type: ignore[arg-type]
            assert type(exc_info.value) is ValueError

    def test_speed_uint32_boundary(self) -> None:
        max_speed_seconds = (2**32 - 1) / 1000
        effect = MultiZoneEffect.move(Direction.FORWARD, max_speed_seconds)
        assert effect.speed == 2**32 - 1

        with pytest.raises(ValueError):
            MultiZoneEffect.move(Direction.FORWARD, 2**32 / 1000)

    def test_duration_uint64_boundary(self) -> None:
        # The largest whole-second duration still fits in a uint64 of nanoseconds.
        max_whole_seconds = (2**64 - 1) // 1_000_000_000
        effect = MultiZoneEffect.move(
            Direction.FORWARD, 1.0, duration=max_whole_seconds
        )
        assert effect.duration == max_whole_seconds * 1_000_000_000

        with pytest.raises(ValueError):
            MultiZoneEffect.move(Direction.FORWARD, 1.0, duration=max_whole_seconds + 1)
        with pytest.raises(ValueError):
            MultiZoneEffect.move(Direction.FORWARD, 1.0, duration=2**64 / 1e9 + 1)

    def test_duration_precision(self) -> None:
        effect = MultiZoneEffect.move(Direction.FORWARD, 1.0, duration=2.5)
        assert effect.duration == 2_500_000_000

    def test_speed_precision_rounds_to_nearest_millisecond(self) -> None:
        effect = MultiZoneEffect.move(Direction.FORWARD, 0.0015)
        assert effect.speed == 2

    def test_int_speed_is_accepted(self) -> None:
        effect = MultiZoneEffect.move(Direction.FORWARD, 5)
        assert effect.speed == 5000


class TestDirectionSetterWidening:
    """The direction setter shares move()'s parsing rule (D-09)."""

    def test_setter_accepts_case_insensitive_name(self) -> None:
        effect = MultiZoneEffect(FirmwareEffect.MOVE, 5000)
        effect.direction = "reversed"
        assert effect.direction == Direction.REVERSED

    def test_setter_accepts_direction_member(self) -> None:
        effect = MultiZoneEffect(FirmwareEffect.MOVE, 5000)
        effect.direction = Direction.FORWARD
        assert effect.direction == Direction.FORWARD

    def test_setter_rejects_unknown_name(self) -> None:
        effect = MultiZoneEffect(FirmwareEffect.MOVE, 5000)
        with pytest.raises(ValueError, match="forward"):
            effect.direction = "sideways"  # type: ignore[assignment]

    def test_setter_rejects_bare_int(self) -> None:
        """D-09's deliberate narrowing: the old setter stored any int unchecked."""
        effect = MultiZoneEffect(FirmwareEffect.MOVE, 5000)
        with pytest.raises(ValueError, match="forward"):
            effect.direction = 1  # type: ignore[assignment]

    def test_setter_rejects_any_value_on_off_effect(self) -> None:
        effect = MultiZoneEffect(FirmwareEffect.OFF, 0)
        with pytest.raises(ValueError, match="MOVE effects"):
            effect.direction = Direction.FORWARD


class TestRawPathUnchanged:
    """The raw MultiZoneEffect(parameters=...) construction path is untouched."""

    def test_raw_construction_emits_no_warning_or_log(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.DEBUG)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            MultiZoneEffect(
                FirmwareEffect.MOVE, 5000, parameters=[0, 1, 0, 0, 0, 0, 0, 0]
            )
        assert caught == []
        assert caplog.records == []

    async def test_set_effect_emits_only_the_existing_debug_log(
        self, multizone_light: MultiZoneLight, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.DEBUG)
        multizone_light.connection.request.return_value = True
        effect = MultiZoneEffect(
            FirmwareEffect.MOVE, 5000, parameters=[0, 1, 0, 0, 0, 0, 0, 0]
        )
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            await multizone_light.set_effect(effect)
        assert caught == []
        assert len(caplog.records) == 1
        assert caplog.records[0].msg["method"] == "set_effect"

    def test_dataclass_fields_are_exactly_four(self) -> None:
        assert [f.name for f in dataclasses.fields(MultiZoneEffect)] == [
            "effect_type",
            "speed",
            "duration",
            "parameters",
        ]


class TestDocumentedMoveExamples:
    """The move() and set_move_effect() docstring examples run verbatim."""

    @pytest.mark.emulator
    async def test_move_docstring_example_runs_verbatim(
        self,
        emulator_devices: DeviceGroup,
        emulator_server: tuple[int, EmulatedLifxServer, HierarchicalScenarioManager],
    ) -> None:
        _, server, _ = emulator_server
        strip = cast(MultiZoneLight, emulator_devices[4])
        source = _python_example(MultiZoneEffect.move)

        with _received_packets(server, strip.serial, pkt_type=508) as captured:
            async with strip:
                await _run_example(source, {"light": strip})
                effect = await strip.get_effect()

        assert effect.effect_type is FirmwareEffect.MOVE
        assert len(captured) == 1
        _, packet = captured[0]
        assert packet.settings.speed == 5000
        assert packet.settings.parameter.parameter1 == int(Direction.FORWARD)

    @pytest.mark.emulator
    async def test_set_move_effect_docstring_example_runs_verbatim(
        self,
        emulator_devices: DeviceGroup,
        emulator_server: tuple[int, EmulatedLifxServer, HierarchicalScenarioManager],
    ) -> None:
        _, server, _ = emulator_server
        strip = cast(MultiZoneLight, emulator_devices[4])
        source = _python_example(MultiZoneLight.set_move_effect)

        with _received_packets(server, strip.serial, pkt_type=508) as captured:
            async with strip:
                await _run_example(source, {"light": strip})
                effect = await strip.get_effect()

        assert effect.effect_type is FirmwareEffect.MOVE
        assert len(captured) == 1
        _, packet = captured[0]
        assert packet.settings.speed == 5000
        assert packet.settings.parameter.parameter1 == int(Direction.FORWARD)

    @pytest.mark.emulator
    async def test_user_guide_move_example_runs_verbatim(
        self,
        emulator_devices: DeviceGroup,
        emulator_server: tuple[int, EmulatedLifxServer, HierarchicalScenarioManager],
    ) -> None:
        """Every python block under the user-guide Move heading runs, in order.

        The blocks run in document order against one strip, but each block
        is self-contained: it imports what it uses and relies on no name an
        earlier block defined. This test gives each block a fresh namespace
        holding only ``light``, so a block that leaned on an earlier
        block's names would fail here.
        """
        _, _, _ = emulator_server
        strip = cast(MultiZoneLight, emulator_devices[4])
        docs_path = (
            Path(__file__).resolve().parents[2] / "docs" / "user-guide" / "effects.md"
        )
        blocks = _markdown_section_examples(docs_path, "## Firmware Move effect")

        async with strip:
            for block in blocks:
                await _run_example(block, {"light": strip})
            effect = await strip.get_effect()

        assert effect.effect_type is FirmwareEffect.MOVE


@pytest.mark.emulator
class TestSetMoveEffectEmulator:
    """set_move_effect() paints a single-colour strip before Move starts (R9)."""

    async def test_single_colour_strip_is_painted_then_moved(
        self,
        emulator_devices: DeviceGroup,
        emulator_server: tuple[int, EmulatedLifxServer, HierarchicalScenarioManager],
    ) -> None:
        """Single-colour strip: derive, paint via apply_theme(), then Move."""
        _, server, _ = emulator_server
        strip = cast(MultiZoneLight, emulator_devices[4])

        async with strip:
            zones = await strip.get_all_color_zones()
            n = len(zones)
            c = HSBK(180, 1.0, 1.0, 3500)
            await strip.set_all_color_zones([c] * n)
            painted = await strip.get_all_color_zones()
            assert all(z == c for z in painted)

            with (
                patch.object(
                    strip, "apply_theme", wraps=strip.apply_theme
                ) as mock_apply_theme,
                _received_packets(server, strip.serial) as captured,
            ):
                await strip.set_move_effect(Direction.FORWARD, 5.0)
                effect = await strip.get_effect()

            mock_apply_theme.assert_awaited_once()
            apply_theme_call = mock_apply_theme.await_args
            assert apply_theme_call is not None
            theme_arg = apply_theme_call.args[0]
            assert apply_theme_call.kwargs.get("duration") == 0
            expected_palette = [
                c,
                HSBK((c.hue + 45) % 360, c.saturation, c.brightness, c.kelvin),
                HSBK((c.hue - 45) % 360, c.saturation, c.brightness, c.kelvin),
            ]
            assert theme_arg.colors == expected_palette

            candidates = []
            for order in permutations(expected_palette):
                generator = MultiZoneGenerator()
                with patch("lifx.theme.theme.random.shuffle", lambda seq: None):
                    candidates.append(generator.get_theme_colors(Theme(list(order)), n))

            final_zones = await strip.get_all_color_zones()
            assert final_zones in candidates
            assert len(set(final_zones)) > 1

        packet_types = [header.pkt_type for header, _ in captured]
        set_extended_indices = [i for i, t in enumerate(packet_types) if t == 510]
        set_effect_indices = [i for i, t in enumerate(packet_types) if t == 508]
        assert set_extended_indices, "expected at least one SetExtendedColorZones"
        assert len(set_effect_indices) == 1
        assert max(set_extended_indices) < set_effect_indices[0]

        assert effect.effect_type is FirmwareEffect.MOVE
        assert effect.speed == 5000

        set_effect_packets = [pkt for hdr, pkt in captured if hdr.pkt_type == 508]
        assert len(set_effect_packets) == 1
        assert set_effect_packets[0].settings.parameter.parameter1 == int(
            Direction.FORWARD
        )


@pytest.mark.emulator
class TestSetMoveEffectPalette:
    """Explicit palettes, multi-colour strips and the timeout fallback (R9)."""

    @pytest.mark.parametrize("bad_palette", [[], [Colors.RED] * 17])
    async def test_explicit_bad_palette_raises_with_no_packet(
        self,
        emulator_devices: DeviceGroup,
        emulator_server: tuple[int, EmulatedLifxServer, HierarchicalScenarioManager],
        bad_palette: list[HSBK],
    ) -> None:
        """An empty or oversized explicit palette raises before any packet."""
        _, server, _ = emulator_server
        strip = cast(MultiZoneLight, emulator_devices[4])

        async with strip:
            with _received_packets(server, strip.serial) as captured:
                with pytest.raises(ValueError, match="[Ee]ffect palette"):
                    await strip.set_move_effect(
                        Direction.FORWARD, 5.0, palette=bad_palette
                    )
                await strip.get_effect()

        assert len(captured) == 1
        assert captured[0][0].pkt_type == 507

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"direction": "sideways", "speed": 5.0},
            {"direction": Direction.FORWARD, "speed": -1.0},
            {"direction": Direction.FORWARD, "speed": 10**400},
        ],
    )
    async def test_invalid_move_arguments_raise_before_any_packet(
        self,
        emulator_devices: DeviceGroup,
        emulator_server: tuple[int, EmulatedLifxServer, HierarchicalScenarioManager],
        kwargs: dict[str, object],
    ) -> None:
        """set_move_effect()'s invalid direction/speed match move()'s own errors."""
        _, server, _ = emulator_server
        strip = cast(MultiZoneLight, emulator_devices[4])

        async with strip:
            with (
                patch.object(
                    strip, "get_all_color_zones", wraps=strip.get_all_color_zones
                ) as mock_get_all_color_zones,
                _received_packets(server, strip.serial) as captured,
            ):
                with pytest.raises(ValueError) as exc_info:
                    await strip.set_move_effect(**kwargs)  # type: ignore[arg-type]
                await strip.get_effect()
            mock_get_all_color_zones.assert_not_awaited()

        assert type(exc_info.value) is ValueError
        assert len(captured) == 1
        assert captured[0][0].pkt_type == 507

    async def test_explicit_palette_passed_to_apply_theme_unchanged(
        self,
        emulator_devices: DeviceGroup,
        emulator_server: tuple[int, EmulatedLifxServer, HierarchicalScenarioManager],
    ) -> None:
        """An explicit palette skips the zone read and reaches apply_theme() as-is."""
        _, server, _ = emulator_server
        strip = cast(MultiZoneLight, emulator_devices[4])
        palette = [Colors.RED, Colors.BLUE]

        async with strip:
            with (
                patch.object(
                    strip, "apply_theme", wraps=strip.apply_theme
                ) as mock_apply_theme,
                patch.object(
                    strip, "get_all_color_zones", wraps=strip.get_all_color_zones
                ) as mock_get_all_color_zones,
                _received_packets(server, strip.serial) as captured,
            ):
                await strip.set_move_effect(Direction.FORWARD, 5.0, palette=palette)
                effect = await strip.get_effect()

            mock_get_all_color_zones.assert_not_awaited()
            mock_apply_theme.assert_awaited_once()
            apply_theme_call = mock_apply_theme.await_args
            assert apply_theme_call is not None
            assert apply_theme_call.args[0].colors == palette
            assert apply_theme_call.kwargs.get("duration") == 0

        assert effect.effect_type is FirmwareEffect.MOVE
        packet_types = [header.pkt_type for header, _ in captured]
        set_extended_indices = [i for i, t in enumerate(packet_types) if t == 510]
        set_effect_indices = [i for i, t in enumerate(packet_types) if t == 508]
        assert set_extended_indices
        assert len(set_effect_indices) == 1
        assert max(set_extended_indices) < set_effect_indices[0]

    async def test_multi_colour_strip_left_untouched(
        self,
        emulator_devices: DeviceGroup,
        emulator_server: tuple[int, EmulatedLifxServer, HierarchicalScenarioManager],
    ) -> None:
        """A strip already showing several colours keeps those zones untouched."""
        _, server, _ = emulator_server
        strip = cast(MultiZoneLight, emulator_devices[4])

        async with strip:
            n = await strip.get_zone_count()
            colors = [Colors.RED if i % 2 == 0 else Colors.BLUE for i in range(n)]
            await strip.set_all_color_zones(colors)
            before = await strip.get_all_color_zones()

            with _received_packets(server, strip.serial) as captured:
                await strip.set_move_effect(Direction.FORWARD, 5.0)
                effect = await strip.get_effect()

            after = await strip.get_all_color_zones()

        assert after == before
        packet_types = [header.pkt_type for header, _ in captured]
        assert 501 not in packet_types
        assert 510 not in packet_types
        assert packet_types.count(508) == 1
        assert effect.effect_type is FirmwareEffect.MOVE

    async def test_zone_read_timeout_falls_back_to_no_palette(
        self,
        emulator_devices: DeviceGroup,
        emulator_server: tuple[int, EmulatedLifxServer, HierarchicalScenarioManager],
        scenario_manager: Any,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """A zone-read timeout logs once at DEBUG and Move still starts unpainted."""
        _, server, _ = emulator_server
        strip = cast(MultiZoneLight, emulator_devices[4])
        caplog.set_level(logging.DEBUG)

        async with strip:
            with scenario_manager(
                "devices", strip.serial, {"drop_packets": {511: 1.0, 502: 1.0}}
            ):
                with _received_packets(server, strip.serial) as captured:
                    await strip.set_move_effect(Direction.FORWARD, 5.0)
                    effect = await strip.get_effect()

        packet_types = [header.pkt_type for header, _ in captured]
        assert 501 not in packet_types
        assert 510 not in packet_types
        assert packet_types.count(508) == 1
        assert effect.effect_type is FirmwareEffect.MOVE

        debug_records = [
            record
            for record in caplog.records
            if isinstance(record.msg, dict)
            and record.msg.get("method") == "set_move_effect"
        ]
        assert len(debug_records) == 1
        assert debug_records[0].msg["values"]["serial"] == strip.serial


@pytest.mark.emulator
class TestRawPathPaintsNothing:
    """The raw set_effect(MultiZoneEffect) path reads and paints nothing (R6/R9)."""

    async def test_raw_set_effect_sends_only_set_effect_and_zones_unchanged(
        self,
        emulator_devices: DeviceGroup,
        emulator_server: tuple[int, EmulatedLifxServer, HierarchicalScenarioManager],
    ) -> None:
        _, server, _ = emulator_server
        strip = cast(MultiZoneLight, emulator_devices[4])

        async with strip:
            n = await strip.get_zone_count()
            c = HSBK(200, 1.0, 1.0, 3500)
            await strip.set_all_color_zones([c] * n)
            # The paint is unacknowledged; a round trip ensures the emulator has
            # processed it before the capture window opens.
            before = await strip.get_all_color_zones()

            with _received_packets(server, strip.serial) as captured:
                await strip.set_effect(MultiZoneEffect.move(Direction.FORWARD, 5.0))
                effect = await strip.get_effect()

            after = await strip.get_all_color_zones()

        assert [header.pkt_type for header, _ in captured] == [508, 507]
        assert all(z == c for z in before)
        assert after == before
        assert effect.effect_type is FirmwareEffect.MOVE


class TestSetMoveEffectErrors:
    """Error propagation from set_move_effect(), mock and emulator (R5)."""

    @pytest.mark.emulator
    async def test_state_unhandled_comes_from_set_effect(
        self,
        switch_device: Any,
        emulator_server: tuple[int, EmulatedLifxServer, HierarchicalScenarioManager],
    ) -> None:
        """StateUnhandled on SetEffect is what raises, not the read or the paint."""
        _, server, _ = emulator_server
        light = MultiZoneLight(
            serial=switch_device.serial,
            ip=switch_device.ip,
            port=switch_device.port,
        )
        await light.connection.open()
        palette = [Colors.RED, Colors.BLUE]

        try:
            with (
                patch.object(
                    light, "get_all_color_zones", new_callable=AsyncMock
                ) as mock_get_all_color_zones,
                patch.object(
                    light, "apply_theme", AsyncMock(return_value=None)
                ) as mock_apply_theme,
                _received_packets(server, switch_device.serial, 508) as captured,
            ):
                with pytest.raises(LifxUnsupportedCommandError):
                    await light.set_move_effect(Direction.FORWARD, 5.0, palette=palette)

            mock_get_all_color_zones.assert_not_awaited()
            mock_apply_theme.assert_awaited_once()
            apply_theme_call = mock_apply_theme.await_args
            assert apply_theme_call is not None
            assert apply_theme_call.args[0].colors == palette
            assert apply_theme_call.kwargs.get("duration") == 0
            assert len(captured) == 1
        finally:
            await light.connection.close()

    async def test_malformed_zone_read_falls_back_to_no_palette(
        self,
        multizone_light: MultiZoneLight,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """A malformed zone reply logs once at DEBUG and Move still starts."""
        multizone_light.get_all_color_zones = AsyncMock(
            side_effect=LifxProtocolError("malformed")
        )
        multizone_light.apply_theme = AsyncMock()
        caplog.set_level(logging.DEBUG)

        await multizone_light.set_move_effect(Direction.FORWARD, 5.0)

        multizone_light.apply_theme.assert_not_awaited()
        multizone_light.connection.request.assert_awaited_once()
        debug_records = [
            record
            for record in caplog.records
            if isinstance(record.msg, dict)
            and record.msg.get("method") == "set_move_effect"
        ]
        assert len(debug_records) == 1
        assert debug_records[0].msg["error"] == "LifxProtocolError"

    @pytest.mark.parametrize(
        ("outcome", "expected"),
        [
            ("state_unhandled", LifxUnsupportedCommandError),
            ("timeout", LifxTimeoutError),
            ("device_not_found", LifxDeviceNotFoundError),
        ],
    )
    async def test_set_effect_errors_propagate_from_mock(
        self,
        multizone_light: MultiZoneLight,
        outcome: str,
        expected: type[Exception],
    ) -> None:
        """set_effect()'s error paths reach the caller through set_move_effect()."""
        multizone_light.get_all_color_zones = AsyncMock(
            return_value=[HSBK(0, 1.0, 1.0, 3500), HSBK(120, 1.0, 1.0, 3500)]
        )
        if outcome == "state_unhandled":
            multizone_light.connection.request.return_value = (
                packets.Device.StateUnhandled(unhandled_type=508)
            )
        elif outcome == "timeout":
            multizone_light.connection.request.side_effect = LifxTimeoutError(
                "no response"
            )
        else:
            multizone_light.connection.request.side_effect = LifxDeviceNotFoundError(
                "not found"
            )

        with pytest.raises(expected):
            await multizone_light.set_move_effect(Direction.FORWARD, 5.0)
