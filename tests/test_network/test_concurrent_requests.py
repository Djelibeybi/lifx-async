"""Tests for concurrent request handling with DeviceConnection.

This module tests concurrent request/response handling through the
user-facing DeviceConnection API.
"""

from __future__ import annotations

import asyncio

import pytest

from lifx.exceptions import LifxTimeoutError
from lifx.protocol.packets import Device


class TestConcurrentRequests:
    """Test concurrent request/response handling with DeviceConnection."""

    async def test_timeout_behavior(self):
        """Test that timeout raises LifxTimeoutError with no server response."""
        from lifx.network.connection import DeviceConnection

        conn = DeviceConnection(
            serial="d073d5000001", ip="192.168.1.100", timeout=0.1, max_retries=0
        )

        try:
            # Request should timeout when no server is available
            with pytest.raises(LifxTimeoutError):
                await conn.request(Device.GetPower(), timeout=0.1)
        finally:
            await conn.close()


@pytest.mark.emulator
class TestErrorHandling:
    """Test error handling in concurrent scenarios using DeviceConnection."""

    async def test_timeout_when_server_drops_packets(
        self, emulator_server_with_scenarios
    ):
        """Test handling timeout when server drops packets (simulating no response)."""
        # Create a scenario that drops Device.GetPower packets (pkt_type 20)
        server, _device = await emulator_server_with_scenarios(
            device_type="color",
            serial="d073d5000001",
            scenarios={
                "drop_packets": {
                    "20": 1.0  # Drop 100% of GetPower responses (pkt_type 20)
                }
            },
        )

        from lifx.network.connection import DeviceConnection

        conn = DeviceConnection(
            serial="d073d5000001",
            ip="127.0.0.1",
            port=server.port,
            timeout=0.5,
            max_retries=0,  # No retries for faster test
        )

        try:
            # This should timeout since server drops all GetPower packets
            with pytest.raises(LifxTimeoutError):
                await conn.request(Device.GetPower(), timeout=0.5)
        finally:
            await conn.close()

    async def test_concurrent_requests_with_one_timing_out(
        self, emulator_server_with_scenarios
    ):
        """Test timeout isolation between concurrent requests."""
        # Create a scenario that drops ONLY GetPower packets
        server, _device = await emulator_server_with_scenarios(
            device_type="color",
            serial="d073d5000001",
            scenarios={
                "drop_packets": {
                    "20": 1.0  # Drop 100% of GetPower responses (pkt_type 20)
                }
            },
        )

        from lifx.network.connection import DeviceConnection

        conn = DeviceConnection(
            serial="d073d5000001",
            ip="127.0.0.1",
            port=server.port,
            timeout=1.0,
            max_retries=2,
        )

        # Create multiple concurrent requests where one will timeout
        async def get_power():
            """This will timeout."""
            try:
                await conn.request(Device.GetPower(), timeout=0.3)
                return "power_success"
            except LifxTimeoutError:
                return "power_timeout"

        async def get_label():
            """This should succeed."""
            try:
                await conn.request(Device.GetLabel(), timeout=1.0)
                return "label_success"
            except LifxTimeoutError:
                return "label_timeout"

        try:
            # Run both concurrently
            results = await asyncio.gather(get_power(), get_label())

            # Power request should timeout, label should succeed
            assert results[0] == "power_timeout"
            assert results[1] == "label_success"
        finally:
            await conn.close()


@pytest.mark.emulator
class TestAsyncGeneratorRequests:
    """Test async generator-based request streaming."""

    async def test_request_stream_single_response(self, emulator_server_with_scenarios):
        """Test request_stream with single response exits immediately after break."""
        server, _device = await emulator_server_with_scenarios(
            device_type="color",
            serial="d073d5000001",
            scenarios={},
        )

        from lifx.network.connection import DeviceConnection

        conn = DeviceConnection(
            serial="d073d5000001",
            ip="127.0.0.1",
            port=server.port,
            timeout=2.0,
            max_retries=2,
        )

        try:
            # Stream should yield single response
            received = []
            async for response in conn.request_stream(Device.GetLabel()):
                received.append(response)
                break  # Exit immediately after first response

            assert len(received) == 1
            assert hasattr(received[0], "label")
        finally:
            await conn.close()

    async def test_request_stream_convenience_wrapper(
        self, emulator_server_with_scenarios
    ):
        """Test that request() convenience wrapper works correctly."""
        server, _device = await emulator_server_with_scenarios(
            device_type="color",
            serial="d073d5000001",
            scenarios={},
        )

        from lifx.network.connection import DeviceConnection

        conn = DeviceConnection(
            serial="d073d5000001",
            ip="127.0.0.1",
            port=server.port,
            timeout=2.0,
            max_retries=2,
        )

        try:
            # request() should return single response directly
            response = await conn.request(Device.GetLabel())
            assert hasattr(response, "label")
        finally:
            await conn.close()

    async def test_early_exit_no_resource_leak(self, emulator_server_with_scenarios):
        """Test that breaking early doesn't leak resources."""
        server, _device = await emulator_server_with_scenarios(
            device_type="color",
            serial="d073d5000001",
            scenarios={},
        )

        from lifx.network.connection import DeviceConnection

        conn = DeviceConnection(
            serial="d073d5000001",
            ip="127.0.0.1",
            port=server.port,
            timeout=2.0,
            max_retries=2,
        )

        try:
            # Stream and break early
            async for _response in conn.request_stream(Device.GetLabel()):
                break

            # Verify connection is still functional
            assert conn.is_open

            # Make another request to verify no leak
            response = await conn.request(Device.GetPower())
            assert hasattr(response, "level")
        finally:
            await conn.close()


@pytest.mark.emulator
class TestRetryTimeoutBudget:
    """Test that retry sleep time doesn't consume the timeout budget.

    This test class verifies the fix for the issue where retry sleep time
    was being counted against the overall timeout budget, causing later
    retry attempts to have insufficient time to wait for responses.
    """

    async def test_retry_sleep_excluded_from_timeout_budget(
        self, emulator_server_with_scenarios
    ):
        """Test that retry sleep time is excluded from timeout budget.

        This test verifies that when retries occur with exponential backoff sleep,
        the sleep time doesn't consume the overall timeout budget. Each retry
        attempt should get a fair timeout window.

        Without the fix, this would fail because later attempts would have
        very short timeouts (e.g., 0.613s on attempt 4) due to accumulated sleep time.
        """
        import time

        # Create a scenario that drops all packets to force retries
        server, _device = await emulator_server_with_scenarios(
            device_type="color",
            serial="d073d5000001",
            scenarios={
                "drop_packets": {
                    "20": 1.0  # Drop 100% of GetPower responses (pkt_type 20)
                }
            },
        )

        from lifx.network.connection import DeviceConnection

        # Set up connection with specific timeout and retries
        timeout = 2.0  # 2 second total timeout budget
        max_retries = 3  # 4 total attempts (0, 1, 2, 3)

        conn = DeviceConnection(
            serial="d073d5000001",
            ip="127.0.0.1",
            port=server.port,
            timeout=timeout,
            max_retries=max_retries,
        )

        # Calculate expected timeout distribution with exponential backoff
        # total_weight = (2^(n+1) - 1) = (2^4 - 1) = 15
        # base_timeout = 2.0 / 15 = 0.133s
        # Attempt 0: 0.133 * 2^0 = 0.133s
        # Attempt 1: 0.133 * 2^1 = 0.266s
        # Attempt 2: 0.133 * 2^2 = 0.533s
        # Attempt 3: 0.133 * 2^3 = 1.066s
        # Total: 0.133 + 0.266 + 0.533 + 1.066 = ~2.0s

        start_time = time.monotonic()

        # This should timeout after all retries are exhausted
        with pytest.raises(LifxTimeoutError) as exc_info:
            await conn.request(Device.GetPower(), timeout=timeout)

        elapsed = time.monotonic() - start_time

        # Verify the timeout message
        assert "after 4 attempts" in str(exc_info.value)

        # The total elapsed time should be:
        # - Timeout budget (2.0s)
        # - Plus sleep time between retries (3 sleeps with exponential backoff)
        #   Sleep 0: random(0, 0.1 * 2^0) = random(0, 0.1)
        #   Sleep 1: random(0, 0.1 * 2^1) = random(0, 0.2)
        #   Sleep 2: random(0, 0.1 * 2^2) = random(0, 0.4)
        #   Max total sleep: 0.1 + 0.2 + 0.4 = 0.7s
        # Total expected: 2.0 + 0.7 = 2.7s maximum

        # Allow some tolerance for timing variations
        assert elapsed >= timeout, "Should use at least the timeout budget"
        assert elapsed < timeout + 1.0, (
            f"Elapsed {elapsed}s should not exceed timeout + max_sleep (3.0s)"
        )

        # Key assertion: If sleep was counted against timeout budget,
        # the elapsed time would be close to just the timeout (2.0s)
        # because later attempts would fail immediately.
        # With the fix, we should see elapsed > timeout + some sleep time.
        assert elapsed > timeout + 0.1, (
            "Sleep time should be added on top of timeout budget"
        )

        await conn.close()

    async def test_retry_timeout_calculation_consistency(
        self, emulator_server_with_scenarios
    ):
        """Test that timeout calculation is consistent between GET and SET requests.

        Both _request_stream_impl (GET) and _request_ack_stream_impl (SET)
        should use the same timeout calculation formula.
        """
        import time

        # Create a scenario that drops packets for both GET and SET
        server, _device = await emulator_server_with_scenarios(
            device_type="color",
            serial="d073d5000001",
            scenarios={
                "drop_packets": {
                    "20": 1.0,  # Drop GetPower (GET request)
                    "21": 1.0,  # Drop SetPower (SET request)
                }
            },
        )

        from lifx.network.connection import DeviceConnection

        timeout = 1.5
        max_retries = 2  # 3 total attempts

        conn = DeviceConnection(
            serial="d073d5000001",
            ip="127.0.0.1",
            port=server.port,
            timeout=timeout,
            max_retries=max_retries,
        )

        # Test GET request (uses _request_stream_impl)
        start_get = time.monotonic()
        with pytest.raises(LifxTimeoutError):
            await conn.request(Device.GetPower(), timeout=timeout)
        elapsed_get = time.monotonic() - start_get

        # Test SET request (uses _request_ack_stream_impl)
        start_set = time.monotonic()
        with pytest.raises(LifxTimeoutError):
            await conn.request(Device.SetPower(level=65535), timeout=timeout)
        elapsed_set = time.monotonic() - start_set

        # Both should take approximately the same time (within tolerance)
        # since they use the same timeout calculation and retry logic
        time_diff = abs(elapsed_get - elapsed_set)
        assert time_diff < 0.5, (
            f"GET and SET timeout behavior should be consistent (diff: {time_diff}s)"
        )

        # Both should respect the timeout budget
        assert elapsed_get >= timeout
        assert elapsed_set >= timeout

        await conn.close()

    async def test_retry_all_attempts_get_fair_timeout(
        self, emulator_server_with_scenarios
    ):
        """Test that all retry attempts get adequate timeout windows.

        This verifies that later retry attempts aren't starved of timeout
        due to accumulated sleep time from earlier attempts.
        """
        # Create a scenario that drops packets to force retries
        server, _device = await emulator_server_with_scenarios(
            device_type="color",
            serial="d073d5000001",
            scenarios={
                "drop_packets": {
                    "20": 1.0  # Drop all GetPower responses
                }
            },
        )

        from lifx.network.connection import DeviceConnection

        timeout = 2.0
        max_retries = 2

        conn = DeviceConnection(
            serial="d073d5000001",
            ip="127.0.0.1",
            port=server.port,
            timeout=timeout,
            max_retries=max_retries,
        )

        # This should timeout after all retries
        with pytest.raises(LifxTimeoutError) as exc_info:
            await conn.request(Device.GetPower(), timeout=timeout)

        # Verify all attempts were made
        assert "after 3 attempts" in str(exc_info.value)

        error_msg = str(exc_info.value)
        assert "No response from" in error_msg

        await conn.close()
