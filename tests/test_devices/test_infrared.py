"""Tests for infrared light device class."""

from __future__ import annotations

import pytest

from lifx.devices.infrared import InfraredLight
from lifx.protocol import packets


class TestInfraredLight:
    """Tests for InfraredLight class."""

    def test_create_infrared_light(self) -> None:
        """Test creating an infrared light."""
        light = InfraredLight(
            serial="d073d5010203",
            ip="192.168.1.100",
            port=56700,
        )
        assert light.serial == "d073d5010203"
        assert light.ip == "192.168.1.100"
        assert light.port == 56700

    async def test_get_infrared(self, infrared_light: InfraredLight) -> None:
        """Test getting infrared brightness."""
        # Mock StateInfrared response with 50% brightness
        mock_state = packets.Light.StateInfrared(brightness=32768)  # 50% of 65535
        infrared_light.connection.request.return_value = mock_state

        brightness = await infrared_light.get_infrared()

        assert brightness == pytest.approx(0.5, abs=0.01)
        infrared_light.connection.request.assert_called_once()

    async def test_get_infrared_full(self, infrared_light: InfraredLight) -> None:
        """Test getting infrared brightness at 100%."""
        mock_state = packets.Light.StateInfrared(brightness=65535)  # 100%
        infrared_light.connection.request.return_value = mock_state

        brightness = await infrared_light.get_infrared()

        assert brightness == pytest.approx(1.0, abs=0.01)

    async def test_get_infrared_zero(self, infrared_light: InfraredLight) -> None:
        """Test getting infrared brightness at 0%."""
        mock_state = packets.Light.StateInfrared(brightness=0)  # 0%
        infrared_light.connection.request.return_value = mock_state

        brightness = await infrared_light.get_infrared()

        assert brightness == pytest.approx(0.0, abs=0.01)

    async def test_set_infrared(self, infrared_light: InfraredLight) -> None:
        """Test setting infrared brightness."""
        # Mock SET operation returns True
        infrared_light.connection.request.return_value = True

        await infrared_light.set_infrared(0.75)

        # Verify packet was sent
        infrared_light.connection.request.assert_called_once()
        call_args = infrared_light.connection.request.call_args
        packet = call_args[0][0]

        assert isinstance(packet, packets.Light.SetInfrared)
        # 0.75 * 65535 = 49151
        assert packet.brightness == pytest.approx(49151, abs=1)

    async def test_set_infrared_full(self, infrared_light: InfraredLight) -> None:
        """Test setting infrared brightness to 100%."""
        infrared_light.connection.request.return_value = True

        await infrared_light.set_infrared(1.0)

        call_args = infrared_light.connection.request.call_args
        packet = call_args[0][0]

        assert packet.brightness == 65535

    async def test_set_infrared_zero(self, infrared_light: InfraredLight) -> None:
        """Test setting infrared brightness to 0%."""
        infrared_light.connection.request.return_value = True

        await infrared_light.set_infrared(0.0)

        call_args = infrared_light.connection.request.call_args
        packet = call_args[0][0]

        assert packet.brightness == 0

    async def test_set_infrared_invalid_high(
        self, infrared_light: InfraredLight
    ) -> None:
        """Test setting invalid infrared brightness (too high)."""
        with pytest.raises(ValueError, match="Brightness must be between"):
            await infrared_light.set_infrared(1.5)

    async def test_set_infrared_invalid_low(
        self, infrared_light: InfraredLight
    ) -> None:
        """Test setting invalid infrared brightness (too low)."""
        with pytest.raises(ValueError, match="Brightness must be between"):
            await infrared_light.set_infrared(-0.1)

    async def test_infrared_caching(self, infrared_light: InfraredLight) -> None:
        """Test infrared brightness caching."""
        # Set up mock
        mock_state = packets.Light.StateInfrared(brightness=32768)
        infrared_light.connection.request.return_value = mock_state

        # First call should hit the device and store the value
        brightness1 = await infrared_light.get_infrared()
        assert infrared_light.connection.request.call_count == 1

        # Check that value is stored in cache
        stored = infrared_light.infrared
        assert stored is not None
        assert stored == pytest.approx(brightness1, abs=0.01)

    async def test_infrared_property(self, infrared_light: InfraredLight) -> None:
        """Test infrared property returns cached value."""
        # Initially no stored value
        assert infrared_light.infrared is None

        # Set stored value
        infrared_light._infrared = 0.6

        # Property should return stored value
        stored = infrared_light.infrared
        assert stored is not None
        assert stored == pytest.approx(0.6, abs=0.01)

    async def test_set_infrared_updates_store(
        self, infrared_light: InfraredLight
    ) -> None:
        """Test that setting infrared updates the store."""
        infrared_light.connection.request.return_value = True

        await infrared_light.set_infrared(0.8)

        # Check store was updated in cache
        stored = infrared_light.infrared
        assert stored is not None
        assert stored == pytest.approx(0.8, abs=0.01)
