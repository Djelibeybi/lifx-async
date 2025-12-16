"""Tests for InfraredLight state management using LIFX Emulator."""

from __future__ import annotations

import pytest

from lifx.devices.infrared import InfraredLight, InfraredLightState


class TestInfraredLightStateManagement:
    """Tests for InfraredLight state management using emulator."""

    @pytest.mark.asyncio
    async def test_infrared_state_property_before_init_raises(
        self, emulator_devices
    ) -> None:
        """Test accessing state property before initialization raises RuntimeError."""
        infrared_light: InfraredLight = emulator_devices[2]  # d073d5000003

        # State is None before using Device.connect()
        with pytest.raises(RuntimeError, match="State not found."):
            _ = infrared_light.state

    @pytest.mark.asyncio
    async def test_initialize_state_creates_infrared_state(
        self, emulator_devices
    ) -> None:
        """Test Device.connect() creates InfraredLightState instance."""
        template: InfraredLight = emulator_devices[2]  # d073d5000003

        # Use Device.connect() to get a properly initialized device
        async with await InfraredLight.connect(
            serial=template.serial, ip=template.ip, port=template.port
        ) as infrared_light:
            # Verify state is InfraredLightState
            assert infrared_light._state is not None
            assert isinstance(infrared_light._state, InfraredLightState)
            assert isinstance(infrared_light._state.label, str)
            assert isinstance(infrared_light._state.power, int)
            assert hasattr(infrared_light._state, "infrared")
            assert isinstance(infrared_light._state.infrared, float)

    @pytest.mark.asyncio
    async def test_state_property_after_init_returns_infrared_state(
        self, emulator_devices
    ) -> None:
        """Test state property returns InfraredLightState after initialization."""
        template: InfraredLight = emulator_devices[2]  # d073d5000003

        async with await InfraredLight.connect(
            serial=template.serial, ip=template.ip, port=template.port
        ) as infrared_light:
            # Access state property
            state = infrared_light.state
            assert isinstance(state, InfraredLightState)
            assert isinstance(state.label, str)
            assert hasattr(state, "infrared")

    @pytest.mark.asyncio
    async def test_refresh_state_updates_infrared(self, emulator_devices) -> None:
        """Test refresh_state() updates infrared field."""
        template: InfraredLight = emulator_devices[2]  # d073d5000003

        async with await InfraredLight.connect(
            serial=template.serial, ip=template.ip, port=template.port
        ) as infrared_light:
            assert isinstance(infrared_light, InfraredLight)

            # Set infrared to a specific value
            await infrared_light.set_infrared(0.75)

            # Refresh state
            await infrared_light.refresh_state()

            # Infrared should be updated
            assert infrared_light._state.infrared >= 0.0
            assert infrared_light._state.infrared <= 1.0

    @pytest.mark.asyncio
    async def test_get_infrared_updates_state(self, emulator_devices) -> None:
        """Test get_infrared() updates state when it exists."""
        template: InfraredLight = emulator_devices[2]  # d073d5000003

        async with await InfraredLight.connect(
            serial=template.serial, ip=template.ip, port=template.port
        ) as infrared_light:
            assert isinstance(infrared_light, InfraredLight)

            # Get infrared
            infrared = await infrared_light.get_infrared()

            # State should be updated
            assert infrared_light._state.infrared == infrared
            assert 0.0 <= infrared <= 1.0

    @pytest.mark.asyncio
    async def test_set_infrared_optimistic_update(self, emulator_devices) -> None:
        """Test set_infrared() updates state optimistically."""
        template: InfraredLight = emulator_devices[2]  # d073d5000003

        async with await InfraredLight.connect(
            serial=template.serial, ip=template.ip, port=template.port
        ) as infrared_light:
            assert isinstance(infrared_light, InfraredLight)

            # Set infrared
            await infrared_light.set_infrared(0.5)

            # State should be updated immediately (optimistic)
            assert infrared_light._state.infrared == 0.5

    @pytest.mark.asyncio
    async def test_state_dataclass_properties(self, emulator_devices) -> None:
        """Test InfraredLightState dataclass computed properties."""
        template: InfraredLight = emulator_devices[2]  # d073d5000003

        async with await InfraredLight.connect(
            serial=template.serial, ip=template.ip, port=template.port
        ) as infrared_light:
            state = infrared_light.state

            # Test is_on property
            await infrared_light.set_power(True)
            await infrared_light.refresh_state()
            assert state.is_on is True

            await infrared_light.set_power(False)
            await infrared_light.refresh_state()
            assert state.is_on is False

            # Test age property (should be very recent)
            age = state.age
            assert age >= 0
            assert age < 5  # Should be less than 5 seconds old

            # Test is_fresh property (should be fresh)
            assert state.is_fresh(max_age=10) is True

    @pytest.mark.asyncio
    async def test_refresh_state_calls_initialize_on_none(self, emulator_port):
        """Test refresh_state() raises calls _initialize_sate() when state is None."""
        infrared_light = InfraredLight(
            serial="d073d5000003",
            ip="127.0.0.1",
            port=emulator_port,
        )

        # Don't initialize state - it should be None
        assert infrared_light._state is None
        await infrared_light.refresh_state()  # type: ignore
        assert isinstance(infrared_light.state, InfraredLightState)
        await infrared_light.close()


class TestInfraredAcknowledgementBasedStateUpdates:
    """Tests that infrared state is only updated when acknowledgements are received."""

    @pytest.mark.asyncio
    async def test_set_infrared_updates_state_on_ack(self, emulator_devices) -> None:
        """Test set_infrared() updates both cache and state when ack received."""
        template: InfraredLight = emulator_devices[2]  # d073d5000003

        async with await InfraredLight.connect(
            serial=template.serial, ip=template.ip, port=template.port
        ) as infrared_light:
            # Get initial infrared value
            assert isinstance(infrared_light, InfraredLight)
            initial_ir = infrared_light._state.infrared

            # Set infrared to a specific value
            await infrared_light.set_infrared(0.75)

            # Both cache and state should be updated to the new value
            assert infrared_light._infrared == 0.75
            assert infrared_light._state.infrared == 0.75
            assert infrared_light._state.infrared != initial_ir

    @pytest.mark.asyncio
    async def test_set_infrared_no_update_without_ack(self, emulator_devices) -> None:
        """Test set_infrared() does NOT update state when ack not received."""
        from unittest.mock import patch

        template: InfraredLight = emulator_devices[2]  # d073d5000003

        async with await InfraredLight.connect(
            serial=template.serial, ip=template.ip, port=template.port
        ) as infrared_light:
            # Get initial infrared value
            assert isinstance(infrared_light, InfraredLight)
            initial_ir = infrared_light._state.infrared

            with patch(
                "lifx.network.connection.DeviceConnection.request", return_value=False
            ):
                # Set infrared
                await infrared_light.set_infrared(0.75)

                # State should NOT be updated
                assert infrared_light._infrared != 0.75
                assert infrared_light._state.infrared == initial_ir
