"""Tests for MatrixLight state management using LIFX Emulator."""

from __future__ import annotations

import pytest

from lifx.color import HSBK
from lifx.devices.matrix import MatrixLight, MatrixLightState


class TestMatrixLightStateManagement:
    """Tests for MatrixLight state management using emulator."""

    @pytest.mark.asyncio
    async def test_matrix_state_property_before_init_raises(
        self, emulator_devices
    ) -> None:
        """Test accessing state property before initialization raises RuntimeError."""
        template: MatrixLight = emulator_devices[6]  # d073d5000007
        matrix_light = MatrixLight(
            ip=template.ip, serial=template.serial, port=template.port
        )

        # State is None before using Device.connect()
        with pytest.raises(RuntimeError, match="State not found."):
            _ = matrix_light.state

    @pytest.mark.asyncio
    async def test_initialize_state_creates_matrix_state(
        self, emulator_devices
    ) -> None:
        """Test Device.connect() creates MatrixLightState instance."""
        template: MatrixLight = emulator_devices[6]  # d073d5000007

        # Use Device.connect() to get a properly initialized device
        async with await MatrixLight.connect(
            serial=template.serial, ip=template.ip, port=template.port
        ) as matrix_light:
            # Verify state is MatrixLightState
            assert matrix_light._state is not None
            assert isinstance(matrix_light._state, MatrixLightState)
            assert isinstance(matrix_light._state.label, str)
            assert isinstance(matrix_light._state.power, int)
            assert hasattr(matrix_light._state, "chain")
            assert hasattr(matrix_light._state, "tile_count")

    @pytest.mark.asyncio
    async def test_state_property_after_init_returns_matrix_state(
        self, emulator_devices
    ) -> None:
        """Test state property returns MatrixLightState after initialization."""
        template: MatrixLight = emulator_devices[6]  # d073d5000007

        async with await MatrixLight.connect(
            serial=template.serial, ip=template.ip, port=template.port
        ) as matrix_light:
            # Access state property
            state = matrix_light.state
            assert isinstance(state, MatrixLightState)
            assert isinstance(state.label, str)
            assert hasattr(state, "chain")
            assert hasattr(state, "tile_count")

    @pytest.mark.asyncio
    async def test_refresh_state_updates_tile_chain(self, emulator_devices) -> None:
        """Test refresh_state() updates tile chain."""
        template: MatrixLight = emulator_devices[6]  # d073d5000007

        async with await MatrixLight.connect(
            serial=template.serial, ip=template.ip, port=template.port
        ) as matrix_light:
            assert isinstance(matrix_light, MatrixLight)

            # Refresh state
            await matrix_light.refresh_state()

            # Tile chain should be updated
            assert matrix_light.state.chain is not None
            assert matrix_light.state.tile_count > 0

    @pytest.mark.asyncio
    async def test_get_device_chain_updates_state(self, emulator_devices) -> None:
        """Test get_device_chain() updates state when it exists."""
        template: MatrixLight = emulator_devices[6]  # d073d5000007

        async with await MatrixLight.connect(
            serial=template.serial, ip=template.ip, port=template.port
        ) as matrix_light:
            assert isinstance(matrix_light, MatrixLight)

            # Get device chain
            chain = await matrix_light.get_device_chain()

            # State should be updated
            assert matrix_light.state.chain is not None
            assert len(matrix_light.state.chain) == len(chain)
            assert matrix_light.state.tile_count == len(chain)

    @pytest.mark.asyncio
    async def test_get_tile_count_from_state(self, emulator_devices) -> None:
        """Test tile_count property returns count from state."""
        template: MatrixLight = emulator_devices[6]  # d073d5000007

        async with await MatrixLight.connect(
            serial=template.serial, ip=template.ip, port=template.port
        ) as matrix_light:
            assert isinstance(matrix_light, MatrixLight)

            # Get tile count from property
            count = matrix_light.tile_count

            # Should match state
            assert count == matrix_light.state.tile_count
            assert count > 0

    @pytest.mark.asyncio
    async def test_get64_updates_tile_colors(self, emulator_devices) -> None:
        """Test get64() fetches tile colors."""
        template: MatrixLight = emulator_devices[6]  # d073d5000007

        async with await MatrixLight.connect(
            serial=template.serial, ip=template.ip, port=template.port
        ) as matrix_light:
            assert isinstance(matrix_light, MatrixLight)

            # Get colors for first tile
            colors = await matrix_light.get64(tile_index=0)

            # Should return 64 colors
            assert len(colors) == 64
            assert all(isinstance(c, HSBK) for c in colors)

    @pytest.mark.asyncio
    async def test_set64_updates_tile(self, emulator_devices) -> None:
        """Test set64() sets tile colors."""
        template: MatrixLight = emulator_devices[6]  # d073d5000007

        async with await MatrixLight.connect(
            serial=template.serial, ip=template.ip, port=template.port
        ) as matrix_light:
            assert isinstance(matrix_light, MatrixLight)

            # Create 64 colors (all red)
            colors = [HSBK(hue=0, saturation=1.0, brightness=0.5, kelvin=3500)] * 64

            # Set tile colors (8x8 tile starting at 0,0)
            await matrix_light.set64(
                tile_index=0, length=1, x=0, y=0, width=8, duration=0, colors=colors
            )

            # Verify by getting colors back
            retrieved = await matrix_light.get64(tile_index=0)
            assert len(retrieved) == 64

    @pytest.mark.asyncio
    async def test_get_all_tile_colors_fetches_all_tiles(
        self, emulator_devices
    ) -> None:
        """Test get_all_tile_colors() fetches colors from all tiles in chain."""
        template: MatrixLight = emulator_devices[6]  # d073d5000007

        async with await MatrixLight.connect(
            serial=template.serial, ip=template.ip, port=template.port
        ) as matrix_light:
            assert isinstance(matrix_light, MatrixLight)

            # Get colors for all tiles
            all_colors = await matrix_light.get_all_tile_colors()

            # Should return a list of color lists (one per tile)
            assert isinstance(all_colors, list)
            assert len(all_colors) == matrix_light.tile_count

            # Each tile should have the correct number of colors
            for tile_colors in all_colors:
                assert isinstance(tile_colors, list)
                assert len(tile_colors) == 64  # 8x8 tile
                assert all(isinstance(c, HSBK) for c in tile_colors)

            # State should be updated with flattened colors
            expected_total = matrix_light.tile_count * 64
            assert len(matrix_light.state.tile_colors) == expected_total

    @pytest.mark.asyncio
    async def test_get_effect_updates_state(self, emulator_devices) -> None:
        """Test get_effect() updates state when it exists."""
        template: MatrixLight = emulator_devices[6]  # d073d5000007

        async with await MatrixLight.connect(
            serial=template.serial, ip=template.ip, port=template.port
        ) as matrix_light:
            assert isinstance(matrix_light, MatrixLight)

            # Get effect
            effect = await matrix_light.get_effect()

            # State should be updated
            assert matrix_light.state.effect is not None
            assert matrix_light.state.effect == effect.effect_type

    @pytest.mark.asyncio
    async def test_state_dataclass_properties(self, emulator_devices) -> None:
        """Test MatrixLightState dataclass computed properties."""
        template: MatrixLight = emulator_devices[6]  # d073d5000007

        async with await MatrixLight.connect(
            serial=template.serial, ip=template.ip, port=template.port
        ) as matrix_light:
            state = matrix_light.state

            # Test is_on property
            await matrix_light.set_power(True)
            await matrix_light.refresh_state()
            assert state.is_on is True

            await matrix_light.set_power(False)
            await matrix_light.refresh_state()
            assert state.is_on is False

            # Test age property (should be very recent)
            age = state.age
            assert age >= 0
            assert age < 5  # Should be less than 5 seconds old

            # Test is_fresh property (should be fresh)
            assert state.is_fresh(max_age=10) is True
