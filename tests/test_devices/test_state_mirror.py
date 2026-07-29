"""Tests for MirrorLight state management and lifecycle."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lifx.color import HSBK
from lifx.devices.base import CollectionInfo, DeviceCapabilities, FirmwareInfo
from lifx.devices.matrix import MatrixLightState
from lifx.devices.mirror import MirrorLight, MirrorLightState
from lifx.exceptions import LifxError
from lifx.products import get_mirror_layout

FRONT = [HSBK(hue=120, saturation=1.0, brightness=0.9, kelvin=3500)] * 25
BACK = [HSBK(hue=200, saturation=0.8, brightness=0.4, kelvin=2700)] * 25
DARK = HSBK(hue=0, saturation=0.0, brightness=0.0, kelvin=3500)

_LAYOUT = get_mirror_layout(267)
assert _LAYOUT is not None
FRONT_POSITIONS = _LAYOUT.front_positions
BACK_POSITIONS = _LAYOUT.back_positions
BUFFER_SIZE = _LAYOUT.buffer_size


def _buffer(front: list[HSBK], back: list[HSBK]) -> list[HSBK]:
    """Build a full Set64 buffer from front and back component colours."""
    buffer = [DARK] * BUFFER_SIZE
    for position, color in zip(FRONT_POSITIONS, front):
        buffer[position] = color
    for position, color in zip(BACK_POSITIONS, back):
        buffer[position] = color
    return buffer


def _front_of(buffer: list[HSBK]) -> list[HSBK]:
    """Read the front component out of a Set64 buffer."""
    return [buffer[position] for position in FRONT_POSITIONS]


def _back_of(buffer: list[HSBK]) -> list[HSBK]:
    """Read the back component out of a Set64 buffer."""
    return [buffer[position] for position in BACK_POSITIONS]


def _matrix_state(power: int = 65535, tile_colors: list[HSBK] | None = None):
    """Build a minimal MatrixLightState for dataclass tests."""
    return MatrixLightState(
        model="LIFX Mirror",
        label="Test Mirror",
        serial="d073d5000100",
        mac_address="d0:73:d5:00:01:00",
        power=power,
        capabilities=DeviceCapabilities(
            has_color=True,
            has_multizone=False,
            has_chain=False,
            has_matrix=True,
            has_infrared=False,
            has_hev=False,
            has_extended_multizone=False,
            kelvin_min=1500,
            kelvin_max=9000,
        ),
        host_firmware=FirmwareInfo(build=1, version_minor=0, version_major=4),
        wifi_firmware=FirmwareInfo(build=1, version_minor=0, version_major=4),
        location=CollectionInfo(
            uuid="00000000-0000-0000-0000-000000000000",
            label="Home",
            updated_at=0,
        ),
        group=CollectionInfo(
            uuid="00000000-0000-0000-0000-000000000000",
            label="Bathroom",
            updated_at=0,
        ),
        color=HSBK(hue=120, saturation=1.0, brightness=0.5, kelvin=3500),
        chain=[],
        tile_orientations={},
        tile_colors=tile_colors if tile_colors is not None else _buffer(FRONT, BACK),
        tile_count=1,
        effect="OFF",
        last_updated=0,
    )


def _mirror_state(power: int = 65535) -> MirrorLightState:
    """Build a MirrorLightState via from_matrix_state."""
    return MirrorLightState.from_matrix_state(
        matrix_state=_matrix_state(power),
        front_colors=list(FRONT),
        back_colors=list(BACK),
        front_positions=FRONT_POSITIONS,
        back_positions=BACK_POSITIONS,
    )


def _connected_mirror(power: int = 65535, product: int = 267) -> MirrorLight:
    """Build a MirrorLight with a real state object and mocked transport."""
    mirror = MirrorLight(serial="d073d5000100", ip="192.168.1.100")
    mirror.connection = AsyncMock()
    mirror._state = _mirror_state(power)
    mirror._version = MagicMock()
    mirror._version.product = product
    mirror.set_matrix_colors = AsyncMock()
    mirror.get_all_tile_colors = AsyncMock(return_value=[_buffer(FRONT, BACK)])
    mirror.get_power = AsyncMock(return_value=power)
    return mirror


class TestMirrorLightStateDataclass:
    """Tests for the MirrorLightState dataclass."""

    def test_from_matrix_state_copies_matrix_fields(self) -> None:
        """Test that matrix fields carry across and component flags compute."""
        state = _mirror_state()

        assert state.model == "LIFX Mirror"
        assert state.serial == "d073d5000100"
        assert state.front_colors == FRONT
        assert state.back_colors == BACK
        assert state.front_positions == FRONT_POSITIONS
        assert state.back_positions == BACK_POSITIONS
        assert state.front_is_on is True
        assert state.back_is_on is True
        assert state.last_front_colors == FRONT
        assert state.last_back_colors == BACK

    def test_components_off_when_power_off(self) -> None:
        """Test that a powered-off device reports both components off."""
        state = _mirror_state(power=0)

        assert state.front_is_on is False
        assert state.back_is_on is False

    def test_component_off_when_all_zones_dark(self) -> None:
        """Test that an all-dark component reports off while powered."""
        state = MirrorLightState.from_matrix_state(
            matrix_state=_matrix_state(),
            front_colors=[DARK] * 25,
            back_colors=list(BACK),
            front_positions=FRONT_POSITIONS,
            back_positions=BACK_POSITIONS,
        )

        assert state.front_is_on is False
        assert state.back_is_on is True

    def test_as_dict_is_serialisable(self) -> None:
        """Test that as_dict expands slices and colours for JSON."""
        state = _mirror_state()
        state.stored_front_colors = list(FRONT)
        state.stored_back_colors = None

        result = state.as_dict

        assert result["front_positions"] == list(FRONT_POSITIONS)
        assert result["back_positions"] == list(BACK_POSITIONS)
        assert result["front_is_on"] is True
        assert len(result["front_colors"]) == 25
        assert isinstance(result["front_colors"][0], dict)
        assert len(result["stored_front_colors"]) == 25
        assert result["stored_back_colors"] is None
        assert result["last_back_colors"] is not None

        # The whole payload must survive json.dumps
        json.dumps(result)


class TestMirrorLightLifecycle:
    """Tests for connection lifecycle and state initialisation."""

    async def test_aenter_rejects_non_mirror_product(self) -> None:
        """Test that a non-Mirror product is refused on entry."""
        mirror = MirrorLight(serial="d073d5000100", ip="192.168.1.100")
        mirror._version = MagicMock()
        mirror._version.product = 176

        with patch.object(
            MirrorLight.__mro__[1], "__aenter__", AsyncMock(return_value=mirror)
        ):
            with pytest.raises(LifxError, match="is not a supported Mirror light"):
                await mirror.__aenter__()

    async def test_aenter_loads_state_file(self, tmp_path: Path) -> None:
        """Test that entry loads any persisted component colours."""
        mirror = MirrorLight(serial="d073d5000100", ip="192.168.1.100")
        mirror._version = MagicMock()
        mirror._version.product = 267
        mirror._state_file = str(tmp_path / "mirror.json")
        mirror._load_state_from_file = MagicMock()

        with patch.object(
            MirrorLight.__mro__[1], "__aenter__", AsyncMock(return_value=mirror)
        ):
            await mirror.__aenter__()

        mirror._load_state_from_file.assert_called_once()

    async def test_aexit_saves_state_then_closes(self, tmp_path: Path) -> None:
        """Test that exit saves state before delegating to the parent."""
        mirror = MirrorLight(serial="d073d5000100", ip="192.168.1.100")
        mirror._state_file = str(tmp_path / "mirror.json")
        mirror._save_state_to_file = MagicMock()
        parent_exit = AsyncMock()

        with patch.object(MirrorLight.__mro__[1], "__aexit__", parent_exit):
            await mirror.__aexit__(None, None, None)

        mirror._save_state_to_file.assert_called_once()
        parent_exit.assert_awaited_once()

    async def test_aexit_swallows_save_failure(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test that a failed save is logged, not raised, and cleanup still runs."""
        mirror = MirrorLight(serial="d073d5000100", ip="192.168.1.100")
        mirror._state_file = str(tmp_path / "mirror.json")
        mirror._save_state_to_file = MagicMock(side_effect=OSError("disk full"))
        parent_exit = AsyncMock()

        with patch.object(MirrorLight.__mro__[1], "__aexit__", parent_exit):
            await mirror.__aexit__(None, None, None)

        assert "Failed to save state" in caplog.text
        parent_exit.assert_awaited_once()

    async def test_aexit_cleanup_runs_when_save_cancelled(self, tmp_path: Path) -> None:
        """Test that cancellation during the save still runs parent cleanup."""
        mirror = MirrorLight(serial="d073d5000100", ip="192.168.1.100")
        mirror._state_file = str(tmp_path / "mirror.json")
        parent_exit = AsyncMock()

        async def _cancel(*_args, **_kwargs) -> None:
            raise asyncio.CancelledError

        with (
            patch("lifx.devices.mirror.asyncio.to_thread", _cancel),
            patch.object(MirrorLight.__mro__[1], "__aexit__", parent_exit),
        ):
            with pytest.raises(asyncio.CancelledError):
                await mirror.__aexit__(None, None, None)

        parent_exit.assert_awaited_once()

    async def test_initialize_state_splits_components(self) -> None:
        """Test that initialisation splits tile colours into components."""
        mirror = MirrorLight(serial="d073d5000100", ip="192.168.1.100")
        mirror._version = MagicMock()
        mirror._version.product = 267

        with patch.object(
            MirrorLight.__mro__[1],
            "_initialize_state",
            AsyncMock(return_value=_matrix_state()),
        ):
            state = await mirror._initialize_state()

        assert state.front_colors == FRONT
        assert state.back_colors == BACK
        assert mirror.state is state

    async def test_refresh_state_updates_components(self) -> None:
        """Test that a refresh re-splits the tile colours."""
        mirror = _connected_mirror()
        refreshed_front = [
            HSBK(hue=10, saturation=1.0, brightness=0.2, kelvin=3500)
        ] * 25
        refreshed_back = [DARK] * 25

        async def _parent_refresh(_self) -> None:
            mirror._state.tile_colors = _buffer(refreshed_front, refreshed_back)

        with patch.object(MirrorLight.__mro__[1], "refresh_state", _parent_refresh):
            await mirror.refresh_state()

        assert mirror.state.front_colors == refreshed_front
        assert mirror.state.back_colors == refreshed_back
        assert mirror.state.front_is_on is True
        assert mirror.state.back_is_on is False

    async def test_from_ip_sets_state_file(self, tmp_path: Path) -> None:
        """Test that the factory threads state_file onto the instance."""
        built = MirrorLight(serial="d073d5000100", ip="192.168.1.100")

        with patch.object(
            MirrorLight.__mro__[1], "from_ip", AsyncMock(return_value=built)
        ):
            device = await MirrorLight.from_ip(
                "192.168.1.100", state_file=str(tmp_path / "mirror.json")
            )

        assert device._state_file == str(tmp_path / "mirror.json")

    def test_state_before_initialisation_raises(self) -> None:
        """Test that the state property requires initialisation."""
        mirror = MirrorLight(serial="d073d5000100", ip="192.168.1.100")

        with pytest.raises(RuntimeError, match="State not found"):
            _ = mirror.state

    def test_repr(self) -> None:
        """Test the string representation."""
        mirror = MirrorLight(serial="d073d5000100", ip="192.168.1.100", port=56700)

        assert repr(mirror) == (
            "MirrorLight(serial=d073d5000100, ip=192.168.1.100, port=56700)"
        )


class TestMirrorComponentFlags:
    """Tests for the front_is_on and back_is_on properties."""

    def test_flags_follow_last_known_colors(self) -> None:
        """Test that the flags read the last-known component colours."""
        mirror = _connected_mirror()

        assert mirror.front_is_on is True
        assert mirror.back_is_on is True

        mirror.state.last_back_colors = [DARK] * 25
        assert mirror.back_is_on is False

    def test_flags_false_when_power_off(self) -> None:
        """Test that both flags are false while the device is off."""
        mirror = _connected_mirror(power=0)

        assert mirror.front_is_on is False
        assert mirror.back_is_on is False

    def test_flags_false_without_last_known_colors(self) -> None:
        """Test that the flags are false before any colours are cached."""
        mirror = _connected_mirror()
        mirror.state.last_front_colors = None

        assert mirror.front_is_on is False

    def test_flags_false_without_state(self) -> None:
        """Test that the flags are false before state initialisation."""
        mirror = MirrorLight(serial="d073d5000100", ip="192.168.1.100")

        assert mirror.front_is_on is False
        assert mirror.back_is_on is False


class TestMirrorWholeDeviceOperations:
    """Tests for set_power and set_color overrides."""

    async def test_set_power_off_captures_both_components(self) -> None:
        """Test that powering off stores both components for restoration."""
        mirror = _connected_mirror()
        parent_power = AsyncMock()

        with patch.object(MirrorLight.__mro__[1], "set_power", parent_power):
            await mirror.set_power(False)

        assert mirror.state.stored_front_colors == FRONT
        assert mirror.state.stored_back_colors == BACK
        assert mirror.state.front_is_on is False
        assert mirror.state.back_is_on is False
        parent_power.assert_awaited_once()

    async def test_set_power_on_recomputes_flags(self) -> None:
        """Test that powering on recomputes the flags from cached colours."""
        mirror = _connected_mirror(power=0)
        mirror.state.last_front_colors = list(FRONT)
        mirror.state.last_back_colors = [DARK] * 25

        with patch.object(MirrorLight.__mro__[1], "set_power", AsyncMock()):
            await mirror.set_power(True)

        assert mirror.state.front_is_on is True
        assert mirror.state.back_is_on is False

    async def test_set_power_accepts_raw_levels(self) -> None:
        """Test that the raw 0/65535 levels are accepted."""
        mirror = _connected_mirror()

        with patch.object(MirrorLight.__mro__[1], "set_power", AsyncMock()):
            await mirror.set_power(65535)

        assert mirror.state.front_is_on is True

    async def test_set_power_rejects_other_ints(self) -> None:
        """Test that an out-of-range integer level is rejected."""
        mirror = _connected_mirror()

        with pytest.raises(ValueError, match="Power level must be 0 or 65535"):
            await mirror.set_power(1234)

    async def test_set_power_rejects_wrong_type(self) -> None:
        """Test that a non-integer level is rejected."""
        mirror = _connected_mirror()

        with pytest.raises(TypeError, match="Expected bool or int"):
            await mirror.set_power("on")  # type: ignore[arg-type]

    async def test_set_power_initialises_state_when_missing(self) -> None:
        """Test that set_power initialises state before capturing colours."""
        mirror = _connected_mirror()
        state = mirror._state
        mirror._state = None
        mirror._initialize_state = AsyncMock(
            side_effect=lambda: setattr(mirror, "_state", state)
        )

        with patch.object(MirrorLight.__mro__[1], "set_power", AsyncMock()):
            await mirror.set_power(False)

        mirror._initialize_state.assert_awaited_once()

    async def test_set_power_persists_on_power_off(self, tmp_path: Path) -> None:
        """Test that powering off writes the state file when configured."""
        mirror = _connected_mirror()
        mirror._state_file = str(tmp_path / "mirror.json")
        mirror._save_state_to_file = MagicMock()

        with patch.object(MirrorLight.__mro__[1], "set_power", AsyncMock()):
            await mirror.set_power(False)

        mirror._save_state_to_file.assert_called_once()

    async def test_set_color_syncs_both_components(self) -> None:
        """Test that a whole-device colour updates both component caches."""
        mirror = _connected_mirror()
        color = HSBK(hue=45, saturation=0.5, brightness=0.6, kelvin=3000)

        with patch.object(MirrorLight.__mro__[1], "set_color", AsyncMock()):
            await mirror.set_color(color)

        assert mirror.state.front_colors == [color] * 25
        assert mirror.state.back_colors == [color] * 25
        assert mirror.state.stored_front_colors == [color] * 25
        assert mirror.state.stored_back_colors == [color] * 25
        assert mirror.state.front_is_on is True
        assert mirror.state.back_is_on is True

    async def test_set_color_persists_when_configured(self, tmp_path: Path) -> None:
        """Test that set_color writes the state file when configured."""
        mirror = _connected_mirror()
        mirror._state_file = str(tmp_path / "mirror.json")
        mirror._save_state_to_file = MagicMock()

        with patch.object(MirrorLight.__mro__[1], "set_color", AsyncMock()):
            await mirror.set_color(
                HSBK(hue=0, saturation=0.0, brightness=1.0, kelvin=3500)
            )

        mirror._save_state_to_file.assert_called_once()


class TestMirrorStoredStateValidity:
    """Tests for stored-state comparison."""

    def test_matching_stored_state_is_valid(self) -> None:
        """Test that matching H, S, K counts as valid regardless of brightness."""
        mirror = _connected_mirror()
        dimmed = [
            HSBK(hue=c.hue, saturation=c.saturation, brightness=0.1, kelvin=c.kelvin)
            for c in FRONT
        ]
        mirror.state.stored_front_colors = dimmed

        assert mirror._is_stored_state_valid("front", list(FRONT)) is True

    def test_mismatched_hue_is_invalid(self) -> None:
        """Test that a different hue invalidates the stored state."""
        mirror = _connected_mirror()
        mirror.state.stored_back_colors = list(FRONT)

        assert mirror._is_stored_state_valid("back", list(BACK)) is False

    def test_missing_or_wrong_length_is_invalid(self) -> None:
        """Test that absent or wrongly sized stored state is invalid."""
        mirror = _connected_mirror()
        mirror.state.stored_front_colors = None
        assert mirror._is_stored_state_valid("front", list(FRONT)) is False

        mirror.state.stored_front_colors = list(FRONT[:5])
        assert mirror._is_stored_state_valid("front", list(FRONT)) is False


class TestMirrorStateFileEdgeCases:
    """Tests for state file failure handling."""

    def test_save_without_state_file_is_noop(self) -> None:
        """Test that saving without a configured file does nothing."""
        mirror = _connected_mirror()
        mirror._state_file = None

        mirror._save_state_to_file()  # must not raise

    def test_load_without_state_file_is_noop(self) -> None:
        """Test that loading without a configured file does nothing."""
        mirror = _connected_mirror()
        mirror._state_file = None

        mirror._load_state_from_file()  # must not raise

    def test_load_ignores_unknown_serial(self, tmp_path: Path) -> None:
        """Test that a document without this device is ignored."""
        state_file = tmp_path / "mirror.json"
        state_file.write_text(json.dumps({"d073d5ffffff": {"front": []}}))

        mirror = _connected_mirror()
        mirror._state_file = str(state_file)
        mirror.state.stored_front_colors = None

        mirror._load_state_from_file()

        assert mirror.state.stored_front_colors is None

    def test_load_accepts_colors_before_version_is_known(self, tmp_path: Path) -> None:
        """Test that stored colours load even before the product is known."""
        state_file = tmp_path / "mirror.json"
        payload = [
            {"hue": 0.0, "saturation": 0.0, "brightness": 1.0, "kelvin": 3500}
        ] * 3
        state_file.write_text(json.dumps({"d073d5000100": {"back": payload}}))

        mirror = _connected_mirror()
        mirror._state_file = str(state_file)
        mirror._version = None  # zone count lookup will raise LifxError
        mirror.state.stored_back_colors = None

        mirror._load_state_from_file()

        assert mirror.state.stored_back_colors is not None
        assert len(mirror.state.stored_back_colors) == 3

    def test_load_handles_corrupt_json(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test that a corrupt state file is logged, not raised."""
        state_file = tmp_path / "mirror.json"
        state_file.write_text("{not json")

        mirror = _connected_mirror()
        mirror._state_file = str(state_file)

        mirror._load_state_from_file()

        assert "Failed to load state" in caplog.text

    def test_save_handles_write_failure(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test that a failed write is logged, not raised."""
        mirror = _connected_mirror()
        mirror._state_file = str(tmp_path / "mirror.json")
        mirror.state.stored_front_colors = list(FRONT)

        with patch(
            "lifx.devices.mirror.write_state_document",
            side_effect=OSError("disk full"),
        ):
            mirror._save_state_to_file()

        assert "Failed to save state" in caplog.text

    def test_save_merges_with_existing_entry(self, tmp_path: Path) -> None:
        """Test that saving preserves other devices in the same file."""
        state_file = tmp_path / "mirror.json"
        state_file.write_text(json.dumps({"d073d5ffffff": {"front": []}}))

        mirror = _connected_mirror()
        mirror._state_file = str(state_file)
        mirror.state.stored_front_colors = list(FRONT)
        mirror.state.stored_back_colors = list(BACK)

        mirror._save_state_to_file()

        document = json.loads(state_file.read_text())
        assert "d073d5ffffff" in document
        assert len(document["d073d5000100"]["front"]) == 25
        assert len(document["d073d5000100"]["back"]) == 25


class TestMirrorBufferValidation:
    """Tests for Set64 buffer gather and scatter."""

    def test_short_buffer_is_rejected_on_read(self) -> None:
        """Test that a device returning too few zones is reported clearly."""
        from lifx.devices.mirror import _gather

        with pytest.raises(LifxError, match="too few for the component layout"):
            _gather([DARK] * 10, FRONT_POSITIONS)

    def test_short_buffer_is_rejected_on_write(self) -> None:
        """Test that scattering into a short buffer is reported clearly."""
        from lifx.devices.mirror import _scatter

        with pytest.raises(LifxError, match="too few for the component layout"):
            _scatter([DARK] * 10, BACK_POSITIONS, list(BACK))

    def test_scatter_leaves_unused_positions_untouched(self) -> None:
        """Test that scattering never writes the two unused buffer slots."""
        from lifx.devices.mirror import _scatter
        from lifx.products.quirks import MIRROR_ZONE_MAP

        buffer = [DARK] * BUFFER_SIZE
        _scatter(buffer, FRONT_POSITIONS, list(FRONT))
        _scatter(buffer, BACK_POSITIONS, list(BACK))

        unused = [position for position, zone in enumerate(MIRROR_ZONE_MAP) if zone < 0]
        assert all(buffer[position] is DARK for position in unused)


class TestMirrorComponentCoverage:
    """Tests covering the remaining per-component branches."""

    async def test_set_back_colors_persists(self, tmp_path: Path) -> None:
        """Test that writing the back component persists stored colours."""
        mirror = _connected_mirror()
        mirror._state_file = str(tmp_path / "mirror.json")
        mirror._save_state_to_file = MagicMock()

        await mirror.set_back_colors(BACK[0])

        mirror._save_state_to_file.assert_called_once()

    async def test_normalise_rejects_all_dark_list(self) -> None:
        """Test that an all-dark colour list is rejected."""
        mirror = _connected_mirror()

        with pytest.raises(ValueError, match="Use turn_back_off"):
            await mirror.set_back_colors([DARK] * 25)

    async def test_turn_back_on_from_cold_infers_and_persists(
        self, tmp_path: Path
    ) -> None:
        """Test the powered-off back turn-on path: infer, zero front, persist."""
        mirror = _connected_mirror(power=0)
        mirror._state_file = str(tmp_path / "mirror.json")
        mirror._save_state_to_file = MagicMock()
        mirror.set_power = AsyncMock()

        await mirror.turn_back_on()

        written = mirror.set_matrix_colors.call_args.args[1]
        assert all(c.brightness == 0 for c in _front_of(written))
        assert all(c.brightness > 0 for c in _back_of(written))
        assert mirror.state.back_is_on is True
        assert mirror.state.front_is_on is False
        mirror._save_state_to_file.assert_called_once()

    async def test_turn_front_off_with_supplied_colors_persists(
        self, tmp_path: Path
    ) -> None:
        """Test turning the front off while supplying the colours to store."""
        mirror = _connected_mirror()
        mirror._state_file = str(tmp_path / "mirror.json")
        mirror._save_state_to_file = MagicMock()
        supplied = HSBK(hue=15, saturation=0.6, brightness=0.7, kelvin=2500)

        await mirror.turn_front_off(supplied)

        written = mirror.set_matrix_colors.call_args.args[1]
        assert all(c.brightness == 0 for c in _front_of(written))
        assert all(c.hue == 15 and c.kelvin == 2500 for c in _front_of(written))
        assert mirror.state.stored_front_colors == [supplied] * 25
        assert mirror.state.front_is_on is False
        mirror._save_state_to_file.assert_called_once()

    async def test_turn_front_off_rejects_dark_supplied_colors(self) -> None:
        """Test that supplying an unlit palette to turn-off is rejected."""
        mirror = _connected_mirror()

        with pytest.raises(ValueError, match="Omit the parameter"):
            await mirror.turn_front_off(DARK)

    async def test_determine_brightness_fetches_when_not_supplied(self) -> None:
        """Test that brightness inference fetches colours when none are passed."""
        mirror = _connected_mirror()

        result = await mirror._determine_component_brightness("front")

        assert len(result) == 25
        mirror.get_all_tile_colors.assert_awaited_once()

    async def test_set_power_on_leaves_flags_when_caches_empty(self) -> None:
        """Test that power-on without cached colours leaves the flags alone."""
        mirror = _connected_mirror(power=0)
        mirror.state.last_front_colors = None
        mirror.state.last_back_colors = None
        mirror.state.front_is_on = False
        mirror.state.back_is_on = False

        with patch.object(MirrorLight.__mro__[1], "set_power", AsyncMock()):
            await mirror.set_power(True)

        assert mirror.state.front_is_on is False
        assert mirror.state.back_is_on is False

    def test_save_skips_absent_components(self, tmp_path: Path) -> None:
        """Test that unset stored colours are omitted from the document."""
        state_file = tmp_path / "mirror.json"
        mirror = _connected_mirror()
        mirror._state_file = str(state_file)
        mirror.state.stored_front_colors = None
        mirror.state.stored_back_colors = None

        mirror._save_state_to_file()

        document = json.loads(state_file.read_text())
        assert document["d073d5000100"] == {}

    async def test_aenter_without_state_file_skips_load(self) -> None:
        """Test that entry skips loading when no state file is configured."""
        mirror = MirrorLight(serial="d073d5000100", ip="192.168.1.100")
        mirror._version = MagicMock()
        mirror._version.product = 267
        mirror._load_state_from_file = MagicMock()

        with patch.object(
            MirrorLight.__mro__[1], "__aenter__", AsyncMock(return_value=mirror)
        ):
            assert await mirror.__aenter__() is mirror

        mirror._load_state_from_file.assert_not_called()

    async def test_aexit_without_state_file_skips_save(self) -> None:
        """Test that exit skips saving when no state file is configured."""
        mirror = MirrorLight(serial="d073d5000100", ip="192.168.1.100")
        mirror._save_state_to_file = MagicMock()
        parent_exit = AsyncMock()

        with patch.object(MirrorLight.__mro__[1], "__aexit__", parent_exit):
            await mirror.__aexit__(None, None, None)

        mirror._save_state_to_file.assert_not_called()
        parent_exit.assert_awaited_once()
