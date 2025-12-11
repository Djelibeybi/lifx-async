"""Tests for CeilingLight state management using LIFX Emulator."""

from __future__ import annotations

import pytest

from lifx.color import HSBK
from lifx.devices.ceiling import CeilingLight, CeilingLightState
from lifx.devices.matrix import MatrixLightState


class TestCeilingLightStateDataclass:
    """Tests for CeilingLightState dataclass."""

    def test_from_matrix_state_creates_ceiling_state(self, emulator_devices) -> None:
        """Test from_matrix_state creates CeilingLightState from MatrixLightState."""
        # Create a minimal MatrixLightState for testing
        from lifx.devices.base import CollectionInfo, DeviceCapabilities, FirmwareInfo

        matrix_state = MatrixLightState(
            model="LIFX Ceiling",
            label="Test Ceiling",
            serial="d073d5000100",
            mac_address="d0:73:d5:00:01:00",
            power=65535,
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
            host_firmware=FirmwareInfo(build=1, version_minor=0, version_major=3),
            wifi_firmware=FirmwareInfo(build=1, version_minor=0, version_major=3),
            location=CollectionInfo(
                uuid="00000000-0000-0000-0000-000000000000",
                label="Home",
                updated_at=0,
            ),
            group=CollectionInfo(
                uuid="00000000-0000-0000-0000-000000000000",
                label="Living Room",
                updated_at=0,
            ),
            color=HSBK(hue=120, saturation=1.0, brightness=0.5, kelvin=3500),
            chain=[],
            tile_orientations={},
            tile_colors=[],
            tile_count=0,
            effect="OFF",
            last_updated=0,
        )

        uplight_color = HSBK(hue=30, saturation=0.2, brightness=0.3, kelvin=2700)
        downlight_colors = [
            HSBK(hue=0, saturation=0, brightness=1.0, kelvin=3500) for _ in range(127)
        ]
        uplight_zone = 127
        downlight_zones = slice(0, 127)

        ceiling_state = CeilingLightState.from_matrix_state(
            matrix_state=matrix_state,
            uplight_color=uplight_color,
            downlight_colors=downlight_colors,
            uplight_zone=uplight_zone,
            downlight_zones=downlight_zones,
        )

        # Verify inherited fields from MatrixLightState
        assert ceiling_state.model == "LIFX Ceiling"
        assert ceiling_state.label == "Test Ceiling"
        assert ceiling_state.serial == "d073d5000100"
        assert ceiling_state.power == 65535
        assert ceiling_state.color == matrix_state.color

        # Verify ceiling-specific fields
        assert ceiling_state.uplight_color == uplight_color
        assert ceiling_state.downlight_colors == downlight_colors
        assert ceiling_state.uplight_zone == 127
        assert ceiling_state.downlight_zones == slice(0, 127)

        # Verify computed is_on fields
        assert ceiling_state.uplight_is_on is True  # brightness 0.3 > 0
        assert (
            ceiling_state.downlight_is_on is True
        )  # at least one zone has brightness > 0

    def test_uplight_is_on_false_when_brightness_zero(self) -> None:
        """Test uplight_is_on is False when uplight brightness is 0."""
        from lifx.devices.base import CollectionInfo, DeviceCapabilities, FirmwareInfo

        matrix_state = MatrixLightState(
            model="LIFX Ceiling",
            label="Test",
            serial="d073d5000100",
            mac_address="d0:73:d5:00:01:00",
            power=65535,
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
            host_firmware=FirmwareInfo(build=1, version_minor=0, version_major=3),
            wifi_firmware=FirmwareInfo(build=1, version_minor=0, version_major=3),
            location=CollectionInfo(
                uuid="00000000-0000-0000-0000-000000000000", label="", updated_at=0
            ),
            group=CollectionInfo(
                uuid="00000000-0000-0000-0000-000000000000", label="", updated_at=0
            ),
            color=HSBK(hue=0, saturation=0, brightness=0, kelvin=3500),
            chain=[],
            tile_orientations={},
            tile_colors=[],
            tile_count=0,
            effect="OFF",
            last_updated=0,
        )

        # Uplight with zero brightness
        uplight_color = HSBK(hue=30, saturation=0.2, brightness=0.0, kelvin=2700)
        downlight_colors = [HSBK(hue=0, saturation=0, brightness=1.0, kelvin=3500)]

        ceiling_state = CeilingLightState.from_matrix_state(
            matrix_state=matrix_state,
            uplight_color=uplight_color,
            downlight_colors=downlight_colors,
            uplight_zone=127,
            downlight_zones=slice(0, 1),
        )

        assert ceiling_state.uplight_is_on is False
        assert ceiling_state.downlight_is_on is True

    def test_downlight_is_on_false_when_all_zero_brightness(self) -> None:
        """Test downlight_is_on is False when all zones have zero brightness."""
        from lifx.devices.base import CollectionInfo, DeviceCapabilities, FirmwareInfo

        matrix_state = MatrixLightState(
            model="LIFX Ceiling",
            label="Test",
            serial="d073d5000100",
            mac_address="d0:73:d5:00:01:00",
            power=65535,
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
            host_firmware=FirmwareInfo(build=1, version_minor=0, version_major=3),
            wifi_firmware=FirmwareInfo(build=1, version_minor=0, version_major=3),
            location=CollectionInfo(
                uuid="00000000-0000-0000-0000-000000000000", label="", updated_at=0
            ),
            group=CollectionInfo(
                uuid="00000000-0000-0000-0000-000000000000", label="", updated_at=0
            ),
            color=HSBK(hue=0, saturation=0, brightness=0, kelvin=3500),
            chain=[],
            tile_orientations={},
            tile_colors=[],
            tile_count=0,
            effect="OFF",
            last_updated=0,
        )

        # All downlight zones with zero brightness
        uplight_color = HSBK(hue=30, saturation=0.2, brightness=1.0, kelvin=2700)
        downlight_colors = [
            HSBK(hue=0, saturation=0, brightness=0.0, kelvin=3500) for _ in range(63)
        ]

        ceiling_state = CeilingLightState.from_matrix_state(
            matrix_state=matrix_state,
            uplight_color=uplight_color,
            downlight_colors=downlight_colors,
            uplight_zone=63,
            downlight_zones=slice(0, 63),
        )

        assert ceiling_state.uplight_is_on is True
        assert ceiling_state.downlight_is_on is False

    def test_as_dict_returns_dictionary(self) -> None:
        """Test as_dict property returns a dictionary representation."""
        from lifx.devices.base import CollectionInfo, DeviceCapabilities, FirmwareInfo

        matrix_state = MatrixLightState(
            model="LIFX Ceiling",
            label="Test",
            serial="d073d5000100",
            mac_address="d0:73:d5:00:01:00",
            power=65535,
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
            host_firmware=FirmwareInfo(build=1, version_minor=0, version_major=3),
            wifi_firmware=FirmwareInfo(build=1, version_minor=0, version_major=3),
            location=CollectionInfo(
                uuid="00000000-0000-0000-0000-000000000000", label="", updated_at=0
            ),
            group=CollectionInfo(
                uuid="00000000-0000-0000-0000-000000000000", label="", updated_at=0
            ),
            color=HSBK(hue=0, saturation=0, brightness=0.5, kelvin=3500),
            chain=[],
            tile_orientations={},
            tile_colors=[],
            tile_count=0,
            effect="OFF",
            last_updated=0,
        )

        uplight_color = HSBK(hue=30, saturation=0.2, brightness=0.5, kelvin=2700)
        downlight_colors = [HSBK(hue=0, saturation=0, brightness=1.0, kelvin=3500)]

        ceiling_state = CeilingLightState.from_matrix_state(
            matrix_state=matrix_state,
            uplight_color=uplight_color,
            downlight_colors=downlight_colors,
            uplight_zone=63,
            downlight_zones=slice(0, 1),
        )

        result = ceiling_state.as_dict
        assert isinstance(result, dict)
        assert result["model"] == "LIFX Ceiling"
        assert result["label"] == "Test"
        assert result["uplight_zone"] == 63
        assert result["downlight_zones"] == slice(0, 1)
        assert result["uplight_is_on"] is True
        assert result["downlight_is_on"] is True


class TestCeilingLightStateManagement:
    """Tests for CeilingLight state management using emulator."""

    @pytest.mark.asyncio
    async def test_ceiling_state_property_before_init_raises(
        self, ceiling_device
    ) -> None:
        """Test accessing state property before initialization raises RuntimeError."""
        ceiling_light = CeilingLight(
            serial=ceiling_device.serial,
            ip=ceiling_device.ip,
            port=ceiling_device.port,
        )

        # State is None before using Device.connect()
        with pytest.raises(RuntimeError, match="State not found."):
            _ = ceiling_light.state

    @pytest.mark.asyncio
    async def test_initialize_state_creates_ceiling_state(self, ceiling_device) -> None:
        """Test Device.connect() creates CeilingLightState instance."""
        # Use Device.connect() to get a properly initialized device
        async with await CeilingLight.connect(
            serial=ceiling_device.serial,
            ip=ceiling_device.ip,
            port=ceiling_device.port,
        ) as ceiling_light:
            # Verify state is CeilingLightState
            assert ceiling_light._state is not None
            assert isinstance(ceiling_light._state, CeilingLightState)
            assert isinstance(ceiling_light._state.label, str)
            assert isinstance(ceiling_light._state.power, int)

            # Verify ceiling-specific attributes
            assert hasattr(ceiling_light._state, "uplight_color")
            assert hasattr(ceiling_light._state, "downlight_colors")
            assert hasattr(ceiling_light._state, "uplight_is_on")
            assert hasattr(ceiling_light._state, "downlight_is_on")
            assert hasattr(ceiling_light._state, "uplight_zone")
            assert hasattr(ceiling_light._state, "downlight_zones")

    @pytest.mark.asyncio
    async def test_state_property_after_init_returns_ceiling_state(
        self, ceiling_device
    ) -> None:
        """Test state property returns CeilingLightState after initialization."""
        async with await CeilingLight.connect(
            serial=ceiling_device.serial,
            ip=ceiling_device.ip,
            port=ceiling_device.port,
        ) as ceiling_light:
            # Access state property
            state = ceiling_light.state
            assert isinstance(state, CeilingLightState)
            assert isinstance(state.uplight_color, HSBK)
            assert isinstance(state.downlight_colors, list)
            assert isinstance(state.uplight_is_on, bool)
            assert isinstance(state.downlight_is_on, bool)

    @pytest.mark.asyncio
    async def test_refresh_state_updates_ceiling_components(
        self, ceiling_device
    ) -> None:
        """Test refresh_state() updates ceiling component state."""
        async with await CeilingLight.connect(
            serial=ceiling_device.serial,
            ip=ceiling_device.ip,
            port=ceiling_device.port,
        ) as ceiling_light:
            # Initial state
            initial_state = ceiling_light.state

            # Refresh state
            await ceiling_light.refresh_state()

            # State should still have ceiling components
            state = ceiling_light.state
            assert isinstance(state.uplight_color, HSBK)
            assert isinstance(state.downlight_colors, list)
            assert state.uplight_zone == initial_state.uplight_zone
            assert state.downlight_zones == initial_state.downlight_zones

    @pytest.mark.asyncio
    async def test_state_uplight_zone_matches_property(self, ceiling_device) -> None:
        """Test state.uplight_zone matches ceiling_light.uplight_zone property."""
        async with await CeilingLight.connect(
            serial=ceiling_device.serial,
            ip=ceiling_device.ip,
            port=ceiling_device.port,
        ) as ceiling_light:
            state = ceiling_light.state
            assert state.uplight_zone == ceiling_light.uplight_zone

    @pytest.mark.asyncio
    async def test_state_downlight_zones_matches_property(self, ceiling_device) -> None:
        """Test state.downlight_zones matches ceiling_light.downlight_zones property."""
        async with await CeilingLight.connect(
            serial=ceiling_device.serial,
            ip=ceiling_device.ip,
            port=ceiling_device.port,
        ) as ceiling_light:
            state = ceiling_light.state
            assert state.downlight_zones == ceiling_light.downlight_zones

    @pytest.mark.asyncio
    async def test_state_uplight_is_on_reflects_brightness(
        self, ceiling_device
    ) -> None:
        """Test state.uplight_is_on correctly reflects uplight brightness."""
        async with await CeilingLight.connect(
            serial=ceiling_device.serial,
            ip=ceiling_device.ip,
            port=ceiling_device.port,
        ) as ceiling_light:
            # Turn uplight on with color
            await ceiling_light.turn_uplight_on(
                HSBK(hue=30, saturation=0.2, brightness=0.5, kelvin=2700)
            )
            await ceiling_light.refresh_state()

            state = ceiling_light.state
            assert state.uplight_is_on is True
            assert state.uplight_color.brightness > 0

    @pytest.mark.asyncio
    async def test_state_downlight_is_on_reflects_brightness(
        self, ceiling_device
    ) -> None:
        """Test state.downlight_is_on correctly reflects downlight brightness."""
        async with await CeilingLight.connect(
            serial=ceiling_device.serial,
            ip=ceiling_device.ip,
            port=ceiling_device.port,
        ) as ceiling_light:
            # Turn downlight on with color
            await ceiling_light.turn_downlight_on(
                HSBK(hue=0, saturation=0, brightness=1.0, kelvin=3500)
            )
            await ceiling_light.refresh_state()

            state = ceiling_light.state
            assert state.downlight_is_on is True
            # At least one downlight zone should have brightness > 0
            assert any(c.brightness > 0 for c in state.downlight_colors)

    @pytest.mark.asyncio
    async def test_state_inherits_matrix_properties(self, ceiling_device) -> None:
        """Test CeilingLightState inherits MatrixLightState properties."""
        async with await CeilingLight.connect(
            serial=ceiling_device.serial,
            ip=ceiling_device.ip,
            port=ceiling_device.port,
        ) as ceiling_light:
            state = ceiling_light.state

            # Matrix properties should be present
            assert hasattr(state, "chain")
            assert hasattr(state, "tile_orientations")
            assert hasattr(state, "tile_colors")
            assert hasattr(state, "tile_count")
            assert hasattr(state, "effect")

            # Device properties should be present
            assert hasattr(state, "model")
            assert hasattr(state, "label")
            assert hasattr(state, "serial")
            assert hasattr(state, "power")
            assert hasattr(state, "color")
