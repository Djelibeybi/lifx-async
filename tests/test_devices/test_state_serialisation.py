"""Tests that every device state's as_dict is fully serialisable.

HSBK is not a dataclass, so dataclasses.asdict leaves colors as objects. Each
state class expands them via HSBK.as_dict so the result survives json.dumps.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from lifx.color import HSBK
from lifx.devices.base import CollectionInfo, DeviceCapabilities, FirmwareInfo
from lifx.devices.ceiling import CeilingLightState
from lifx.devices.hev import HevLightState
from lifx.devices.infrared import InfraredLightState
from lifx.devices.light import LightState
from lifx.devices.matrix import MatrixLightState, TileInfo
from lifx.devices.multizone import MultiZoneLightState
from lifx.protocol.models import HevConfig, HevCycleState
from lifx.protocol.protocol_types import FirmwareEffect, LightLastHevCycleResult

COLOR = HSBK(hue=180, saturation=0.5, brightness=0.75, kelvin=3500)
COLOR_DICT = {"hue": 180, "saturation": 0.5, "brightness": 0.75, "kelvin": 3500}


def _base_fields() -> dict[str, Any]:
    """Return the DeviceState/LightState fields common to every state class."""
    return {
        "model": "LIFX Test",
        "label": "Test",
        "serial": "d073d5000100",
        "mac_address": "d0:73:d5:00:01:00",
        "power": 65535,
        "capabilities": DeviceCapabilities(
            has_color=True,
            has_multizone=False,
            has_chain=True,
            has_matrix=True,
            has_infrared=False,
            has_hev=False,
            has_extended_multizone=False,
            kelvin_min=1500,
            kelvin_max=9000,
        ),
        "host_firmware": FirmwareInfo(build=1, version_minor=0, version_major=3),
        "wifi_firmware": FirmwareInfo(build=1, version_minor=0, version_major=3),
        "location": CollectionInfo(uuid="u", label="", updated_at=0),
        "group": CollectionInfo(uuid="u", label="", updated_at=0),
        "color": COLOR,
        "last_updated": 0,
    }


def _tile() -> TileInfo:
    """Return a single TileInfo for chain tests."""
    return TileInfo(
        tile_index=0,
        accel_meas_x=1,
        accel_meas_y=2,
        accel_meas_z=3,
        user_x=0.0,
        user_y=0.0,
        width=8,
        height=8,
        supported_frame_buffers=1,
        device_version_vendor=1,
        device_version_product=176,
        device_version_version=0,
        firmware_build=0,
        firmware_version_minor=0,
        firmware_version_major=3,
    )


def _matrix_fields() -> dict[str, Any]:
    """Return the matrix-specific fields."""
    return {
        "chain": [_tile()],
        "tile_orientations": {0: "rotate_right"},
        "tile_colors": [COLOR],
        "tile_count": 1,
        "effect": FirmwareEffect.OFF,
    }


def _ceiling_state(*, stored: bool) -> CeilingLightState:
    """Return a CeilingLightState with stored/last colors set or left unset."""
    return CeilingLightState(
        **_base_fields(),
        **_matrix_fields(),
        uplight_color=COLOR,
        downlight_colors=[COLOR],
        uplight_is_on=True,
        downlight_is_on=True,
        uplight_zone=63,
        downlight_zones=slice(0, 63),
        stored_uplight_color=COLOR if stored else None,
        stored_downlight_colors=[COLOR] if stored else None,
        last_uplight_color=COLOR if stored else None,
        last_downlight_colors=[COLOR] if stored else None,
    )


def _all_states() -> dict[str, Any]:
    """Return one instance of every state class."""
    return {
        "light": LightState(**_base_fields()),
        "infrared": InfraredLightState(**_base_fields(), infrared=0.5),
        "hev": HevLightState(
            **_base_fields(),
            hev_cycle=HevCycleState(duration_s=7200, remaining_s=0, last_power=0),
            hev_config=HevConfig(indication=False, duration_s=7200),
            hev_result=LightLastHevCycleResult.SUCCESS,
        ),
        "multizone": MultiZoneLightState(
            **_base_fields(),
            zones=[COLOR],
            zone_count=1,
            effect=FirmwareEffect.OFF,
        ),
        "matrix": MatrixLightState(**_base_fields(), **_matrix_fields()),
        "ceiling": _ceiling_state(stored=True),
    }


class TestStateSerialisation:
    """Every state class expands its HSBK fields in as_dict."""

    @pytest.mark.parametrize("name", list(_all_states()))
    def test_as_dict_is_json_serialisable(self, name: str) -> None:
        """Test as_dict survives json.dumps for every state class."""
        state = _all_states()[name]

        json.dumps(state.as_dict)

    @pytest.mark.parametrize("name", list(_all_states()))
    def test_color_is_expanded(self, name: str) -> None:
        """Test the inherited LightState color is expanded everywhere."""
        state = _all_states()[name]

        assert state.as_dict["color"] == COLOR_DICT

    def test_multizone_expands_zones(self) -> None:
        """Test MultiZoneLightState expands its zone colors."""
        state = _all_states()["multizone"]

        assert state.as_dict["zones"] == [COLOR_DICT]

    def test_matrix_expands_tile_colors(self) -> None:
        """Test MatrixLightState expands its tile colors."""
        state = _all_states()["matrix"]

        assert state.as_dict["tile_colors"] == [COLOR_DICT]

    def test_matrix_chain_is_expanded(self) -> None:
        """Test the chain becomes dicts rather than TileInfo objects."""
        state = _all_states()["matrix"]

        chain = state.as_dict["chain"]
        assert chain == [_tile().as_dict]
        assert not isinstance(chain[0], TileInfo)

    def test_matrix_tile_orientations_survive_a_json_round_trip(self) -> None:
        """Test orientation keys are strings so JSON does not change them.

        JSON object keys are always strings. Leaving the int keys in place
        made json.dumps succeed while silently coercing them, so a consumer
        that persisted the state lost every orientation lookup on restore.
        """
        result = _all_states()["matrix"].as_dict

        assert result["tile_orientations"] == {"0": "rotate_right"}
        assert json.loads(json.dumps(result))["tile_orientations"] == {
            "0": "rotate_right"
        }

    @pytest.mark.parametrize("name", list(_all_states()))
    def test_capabilities_are_curated(self, name: str) -> None:
        """Test every state gets DeviceState's capability expansion.

        LightState used to call dataclasses.asdict, which bypassed
        DeviceState.as_dict entirely, so light states were missing
        has_variable_color_temp and kept None kelvin bounds.
        """
        capabilities = _all_states()[name].as_dict["capabilities"]

        assert capabilities["has_variable_color_temp"] is True
        assert capabilities["kelvin_min"] == 1500
        assert capabilities["kelvin_max"] == 9000

    @pytest.mark.parametrize("name", list(_all_states()))
    def test_firmware_omits_build(self, name: str) -> None:
        """Test the firmware expansion drops build, as DeviceState intends."""
        result = _all_states()[name].as_dict

        assert result["host_firmware"] == {"version_major": 3, "version_minor": 0}
        assert result["wifi_firmware"] == {"version_major": 3, "version_minor": 0}

    def test_subclass_fields_are_all_present(self) -> None:
        """Test building field-by-field did not drop any subclass field."""
        states = _all_states()

        assert states["infrared"].as_dict["infrared"] == 0.5
        assert states["hev"].as_dict["hev_cycle"] == {
            "duration_s": 7200,
            "remaining_s": 0,
            "last_power": 0,
        }
        assert states["hev"].as_dict["hev_config"] == {
            "indication": False,
            "duration_s": 7200,
        }
        assert states["hev"].as_dict["hev_result"] == LightLastHevCycleResult.SUCCESS
        assert states["multizone"].as_dict["zone_count"] == 1
        assert states["multizone"].as_dict["effect"] == FirmwareEffect.OFF
        assert states["matrix"].as_dict["tile_count"] == 1
        assert states["matrix"].as_dict["effect"] == FirmwareEffect.OFF
        assert states["ceiling"].as_dict["uplight_is_on"] is True
        assert states["ceiling"].as_dict["downlight_is_on"] is True
        assert states["ceiling"].as_dict["uplight_zone"] == 63

    def test_ceiling_expands_component_colors(self) -> None:
        """Test CeilingLightState expands uplight and downlight colors."""
        result = _ceiling_state(stored=True).as_dict

        assert result["uplight_color"] == COLOR_DICT
        assert result["downlight_colors"] == [COLOR_DICT]
        assert result["stored_uplight_color"] == COLOR_DICT
        assert result["stored_downlight_colors"] == [COLOR_DICT]
        assert result["last_uplight_color"] == COLOR_DICT
        assert result["last_downlight_colors"] == [COLOR_DICT]

    def test_ceiling_keeps_none_for_unset_colors(self) -> None:
        """Test the optional stored/last color fields stay None when unset."""
        result = _ceiling_state(stored=False).as_dict

        assert result["stored_uplight_color"] is None
        assert result["stored_downlight_colors"] is None
        assert result["last_uplight_color"] is None
        assert result["last_downlight_colors"] is None

    def test_ceiling_still_expands_downlight_zones(self) -> None:
        """Test the slice expansion survives alongside the color expansion."""
        result = _ceiling_state(stored=False).as_dict

        assert result["downlight_zones"] == {"start": 0, "stop": 63, "step": 1}
        assert not isinstance(result["downlight_zones"], slice)

    @pytest.mark.parametrize("zones", [slice(0, 63), slice(0, 127)])
    def test_ceiling_normalises_unset_downlight_zones_step(self, zones: slice) -> None:
        """Test an unset step becomes 1.

        The layouts in quirks.py build slice(0, 63) and slice(0, 127), which
        leave slice.step as None even though the zones step by one.
        """
        state = _ceiling_state(stored=False)
        state.downlight_zones = zones

        assert state.as_dict["downlight_zones"] == {
            "start": 0,
            "stop": zones.stop,
            "step": 1,
        }

    def test_ceiling_preserves_explicit_downlight_zones_step(self) -> None:
        """Test a step that was set explicitly is kept as-is."""
        state = _ceiling_state(stored=False)
        state.downlight_zones = slice(0, 63, 2)

        assert state.as_dict["downlight_zones"] == {"start": 0, "stop": 63, "step": 2}

    def test_ceiling_downlight_zones_can_rebuild_the_slice(self) -> None:
        """Test the mapping carries enough detail to recreate the slice.

        slice() takes no keyword arguments, so a consumer must pass the three
        values positionally.
        """
        original = slice(0, 63)
        state = _ceiling_state(stored=False)
        state.downlight_zones = original

        zones = state.as_dict["downlight_zones"]
        rebuilt = slice(zones["start"], zones["stop"], zones["step"])

        # Not == to the original, whose step is None, but indexes identically.
        assert rebuilt.indices(64) == original.indices(64)
        assert list(range(64))[rebuilt] == list(range(64))[original]
