"""Tests for the append-only merged-discovery measurement harness."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from lifx.const import MDNS_ADDRESS, MDNS_PORT
from lifx.network.connection import DeviceConnection
from lifx.network.discovery import discover_devices
from lifx.network.discovery.mdns.discovery import (
    _current_mdns_service_source_override,
    _discover_lifx_services,
    _override_mdns_service_source,
)
from lifx.network.discovery.mdns.transport import MdnsTransport
from lifx.network.discovery.mdns.types import _LifxServiceRecord
from scripts.measure_merged_discovery import (
    _append_measurement_row,
    _arms_for_mode,
    _build_measurement_row,
    _eligible_find08_firmware,
    _EmbeddedMeasurementEmulator,
    _find08_from_observations,
    _load_alias_map,
    _load_measurements,
    _measure_arm,
    _measurement_revision,
    _normalise_find08_observations,
    _render_measurement_summary,
    _source_contributions,
    _validate_measurements,
    main_async,
)
from scripts.measurement_support import (
    _capture_discovery_observations,
    _current_discovery_observation_sink,
    _DiscoveryObservation,
)


def _row(
    *,
    arm: str = "baseline",
    pair_id: str = "pair-alpha",
    environment: str = "emulator",
    revision: str = "a" * 40,
    round_number: int = 1,
    quiescence: str = "quiesced",
) -> dict[str, object]:
    """Build one compact synthetic row through the production helper."""
    return _build_measurement_row(
        scenario_id="scenario-alpha",
        pair_id=pair_id,
        round_number=round_number,
        arm=arm,
        implementation_path=("direct_udp" if arm == "baseline" else "merged_dual"),
        environment=environment,
        revision=revision,
        quiescence=quiescence,
        confounds=[] if quiescence == "quiesced" else ["background_pollers"],
        elapsed_ns=200,
        first_result_ns=100,
        devices=[
            {
                "alias": "synthetic-primary",
                "sources": ["udp"],
                "winner": "udp",
                "source_order": ["udp"],
            }
        ],
        target="owned_loopback_dynamic" if environment == "emulator" else "fleet",
        find08={"disposition": "no_eligible_find08_population", "devices": []},
    )


class TestMeasurementSchema:
    """Raw rows stay precise, append-only, comparable, and reproducible."""

    def test_append_preserves_every_prior_byte(self, tmp_path: Path) -> None:
        output = tmp_path / "measurements.jsonl"
        first = _row()
        second = _row(arm="merged")

        _append_measurement_row(output, first)
        prefix = output.read_bytes()
        _append_measurement_row(output, second)

        assert output.read_bytes().startswith(prefix)
        assert _load_measurements(output) == [first, second]

    @pytest.mark.parametrize(
        "mode, expected",
        [
            ("baseline-only", ("baseline",)),
            ("merged-only", ("merged",)),
            ("paired", ("baseline", "merged")),
        ],
    )
    def test_mode_order_is_explicit(self, mode: str, expected: tuple[str, ...]) -> None:
        assert _arms_for_mode(mode) == expected

    def test_pair_validation_rejects_missing_and_duplicate_arms(self) -> None:
        with pytest.raises(ValueError, match="complete baseline and merged arms"):
            _validate_measurements([_row()], require_complete_pairs=True)

        with pytest.raises(ValueError, match="duplicate arm"):
            _validate_measurements(
                [_row(), _row(), _row(arm="merged")],
                require_complete_pairs=True,
            )

    def test_pair_validation_rejects_incomparable_metadata(self) -> None:
        with pytest.raises(ValueError, match="incomparable"):
            _validate_measurements(
                [_row(), _row(arm="merged", environment="fleet")],
                require_complete_pairs=True,
            )

    def test_validation_rejects_unbounded_or_duplicate_confounds(self) -> None:
        """Durable evidence accepts only the finite categorical vocabulary."""
        row = _row(quiescence="not_quiesced")
        row["confounds"] = ["synthetic-host-detail"]
        with pytest.raises(ValueError, match="invalid confounds"):
            _validate_measurements([row])

        row["confounds"] = ["background_pollers", "background_pollers"]
        with pytest.raises(ValueError, match="invalid confounds"):
            _validate_measurements([row])

    def test_validation_rejects_duplicate_source_order_entries(self) -> None:
        """Winner order is a permutation, not an arbitrary source sequence."""
        row = _row()
        devices = row["devices"]
        assert isinstance(devices, list)
        device = devices[0]
        assert isinstance(device, dict)
        device["source_order"] = ["udp", "udp"]

        with pytest.raises(ValueError, match="source order"):
            _validate_measurements([row])

    def test_expected_revision_selects_exactly_one_qualified_pair(self) -> None:
        historical = _row(pair_id="historical-pair", revision="a" * 40)
        historical.pop("evidence_classification")
        historical.pop("round_classification")
        revision = "b" * 40
        pair = [
            _row(revision=revision),
            _row(arm="merged", revision=revision),
        ]

        _validate_measurements(
            [historical, *pair],
            expected_revision=revision,
        )

        with pytest.raises(ValueError, match="exactly one two-row"):
            _validate_measurements([historical], expected_revision=revision)
        with pytest.raises(ValueError, match="exactly one two-row"):
            _validate_measurements(
                [
                    *pair,
                    _row(pair_id="second-pair", revision=revision),
                    _row(
                        arm="merged",
                        pair_id="second-pair",
                        revision=revision,
                    ),
                ],
                expected_revision=revision,
            )

    @pytest.mark.parametrize(
        "revision",
        ["a" * 39, "a" * 41, "A" * 40, "not-a-commit"],
    )
    def test_explicit_revision_requires_full_lowercase_sha(self, revision: str) -> None:
        with pytest.raises(ValueError, match="40-character lowercase SHA"):
            _measurement_revision(revision)
        with pytest.raises(ValueError, match="40-character lowercase SHA"):
            _validate_measurements([], expected_revision=revision)

    def test_expected_revision_rejects_mixed_or_unqualified_pair(self) -> None:
        revision = "c" * 40
        mixed = _row(arm="merged", revision="d" * 40)
        with pytest.raises(ValueError, match="incomparable"):
            _validate_measurements(
                [_row(revision=revision), mixed],
                expected_revision=revision,
            )

        unqualified = [
            _row(revision=revision),
            _row(arm="merged", revision=revision),
        ]
        for row in unqualified:
            row.pop("evidence_classification")
            row.pop("round_classification")
        with pytest.raises(ValueError, match="requires evidence qualifications"):
            _validate_measurements(unqualified, expected_revision=revision)

    def test_evidence_qualification_matches_environment(self) -> None:
        emulator = _row()
        assert emulator["evidence_classification"] == "synthetic_mdns_lower_bound"
        assert emulator["round_classification"] == "single_round"

        fleet = _row(environment="fleet")
        assert fleet["evidence_classification"] == "representative"
        assert fleet["round_classification"] == "repeated_rounds"

        emulator["evidence_classification"] = "representative"
        with pytest.raises(ValueError, match="evidence_classification"):
            _validate_measurements([emulator])

    def test_integer_precision_and_nullable_first_result_are_strict(self) -> None:
        row = _row()
        row["elapsed_ns"] = 1.5
        with pytest.raises(ValueError, match="elapsed_ns"):
            _validate_measurements([row])

        row = _row()
        row["first_result_ns"] = None
        with pytest.raises(ValueError, match="first_result_ns"):
            _validate_measurements([row])

        empty = _row()
        empty["devices"] = []
        empty["unique_count"] = 0
        empty["first_result_ns"] = None
        _validate_measurements([empty])

    def test_summary_is_deterministic_and_row_order_independent(self) -> None:
        baseline = _row()
        merged = _row(arm="merged")
        summary = _render_measurement_summary([baseline, merged])
        assert summary == (_render_measurement_summary([merged, baseline]))
        assert "## Pair deltas" in summary
        assert "| +0 | +0 | +0 |" in summary
        assert "## Raw observations" in summary
        assert "synthetic_mdns_lower_bound" in summary
        assert "reasoned D-07 safety bound, not a measured optimum" in summary

    def test_non_clean_evidence_is_labelled_confounded(self) -> None:
        baseline = _row(quiescence="unknown")
        merged = _row(arm="merged", quiescence="unknown")
        summary = _render_measurement_summary([baseline, merged])
        assert "confounded" in summary.casefold()
        assert "background_pollers" in summary

    def test_summary_preserves_null_first_result_delta(self) -> None:
        baseline = _row()
        baseline["devices"] = []
        baseline["unique_count"] = 0
        baseline["first_result_ns"] = None
        merged = _row(arm="merged")
        merged["devices"] = []
        merged["unique_count"] = 0
        merged["first_result_ns"] = None

        summary = _render_measurement_summary([baseline, merged])

        assert "| +0 | null | +0 |" in summary

    def test_fleet_summary_reports_advisory_variable_baseline_counts(self) -> None:
        first_baseline = _row(environment="fleet", pair_id="fleet-one")
        first_merged = _row(arm="merged", environment="fleet", pair_id="fleet-one")
        second_baseline = _row(environment="fleet", pair_id="fleet-two", round_number=2)
        second_baseline["unique_count"] = 2
        second_merged = _row(
            arm="merged",
            environment="fleet",
            pair_id="fleet-two",
            round_number=2,
        )

        summary = _render_measurement_summary(
            [first_baseline, first_merged, second_baseline, second_merged]
        )

        assert "Complete physical fleet pairs: 2" in summary
        assert "`representative` and `repeated_rounds`" in summary
        assert "`variable_baseline_counts` (advisory only" in summary
        assert "`no_eligible_find08_population`" in summary

    def test_final_evidence_requires_fleet_repetition_and_current_emulator(
        self,
    ) -> None:
        revision = "b" * 40
        rows: list[dict[str, object]] = []
        for round_number in range(1, 7):
            pair_id = f"fleet-pair-{round_number}"
            rows.extend(
                [
                    _row(
                        pair_id=pair_id,
                        environment="fleet",
                        revision=revision,
                        round_number=round_number,
                    ),
                    _row(
                        arm="merged",
                        pair_id=pair_id,
                        environment="fleet",
                        revision=revision,
                        round_number=round_number,
                    ),
                ]
            )

        with pytest.raises(ValueError, match="current-revision emulator pair"):
            _validate_measurements(
                rows,
                require_complete_pairs=True,
                require_final_evidence=True,
                current_revision=revision,
            )

        rows.extend(
            [
                _row(pair_id="emulator-pair", revision=revision),
                _row(arm="merged", pair_id="emulator-pair", revision=revision),
            ]
        )
        _validate_measurements(
            rows,
            require_complete_pairs=True,
            require_final_evidence=True,
            current_revision=revision,
        )

    def test_final_evidence_rejects_cross_revision_fleet_pairs(self) -> None:
        """The selected final revision owns both fleet and emulator evidence."""
        fleet_revision = "a" * 40
        final_revision = "b" * 40
        rows: list[dict[str, object]] = [
            _row(pair_id="emulator-pair", revision=final_revision),
            _row(
                arm="merged",
                pair_id="emulator-pair",
                revision=final_revision,
            ),
        ]
        for round_number in range(1, 7):
            pair_id = f"fleet-pair-{round_number}"
            rows.extend(
                [
                    _row(
                        pair_id=pair_id,
                        environment="fleet",
                        revision=fleet_revision,
                        round_number=round_number,
                    ),
                    _row(
                        arm="merged",
                        pair_id=pair_id,
                        environment="fleet",
                        revision=fleet_revision,
                        round_number=round_number,
                    ),
                ]
            )

        with pytest.raises(ValueError, match="current-revision fleet pairs"):
            _validate_measurements(
                rows,
                require_complete_pairs=True,
                require_final_evidence=True,
                current_revision=final_revision,
            )

        with pytest.raises(ValueError, match="40-character lowercase SHA"):
            _validate_measurements(
                rows,
                require_complete_pairs=True,
                require_final_evidence=True,
                current_revision="not-a-revision",
            )

    def test_final_evidence_requires_current_revision(self) -> None:
        """Final validation cannot infer a revision from mixed history."""
        with pytest.raises(ValueError, match="current revision is required"):
            _validate_measurements([], require_final_evidence=True)

    @pytest.mark.parametrize(
        "mutation",
        [
            pytest.param(
                lambda row: row.update({"serial": "020000000001"}),
                id="forbidden-key",
            ),
            pytest.param(
                lambda row: row.update({"confounds": ["host=192.0.2.10"]}),
                id="address-hidden-in-value",
            ),
            pytest.param(
                lambda row: row.update(
                    {"devices": [{"alias": "020000000001", "sources": ["udp"]}]}
                ),
                id="identifier-shaped-alias",
            ),
        ],
    )
    def test_privacy_rejects_before_output_is_opened(
        self,
        tmp_path: Path,
        mutation,
    ) -> None:
        output = tmp_path / "must-not-exist.jsonl"
        row = _row()
        mutation(row)
        with pytest.raises(ValueError, match="privacy|identifier|alias|confounds"):
            _append_measurement_row(output, row)
        assert not output.exists()

    async def test_validate_only_infers_unique_shared_final_revision(
        self, tmp_path: Path
    ) -> None:
        """Historical emulator pairs do not invalidate a later fleet revision."""
        output = tmp_path / "measurements.jsonl"
        historical_revision = "a" * 40
        final_revision = "b" * 40
        rows = [
            _row(pair_id="historical-emulator", revision=historical_revision),
            _row(
                arm="merged",
                pair_id="historical-emulator",
                revision=historical_revision,
            ),
            _row(pair_id="final-emulator", revision=final_revision),
            _row(
                arm="merged",
                pair_id="final-emulator",
                revision=final_revision,
            ),
        ]
        for round_number in range(1, 7):
            pair_id = f"fleet-pair-{round_number}"
            rows.extend(
                [
                    _row(
                        pair_id=pair_id,
                        environment="fleet",
                        revision=final_revision,
                        round_number=round_number,
                    ),
                    _row(
                        arm="merged",
                        pair_id=pair_id,
                        environment="fleet",
                        revision=final_revision,
                        round_number=round_number,
                    ),
                ]
            )
        for row in rows:
            _append_measurement_row(output, row)

        args = argparse.Namespace(
            validate_only=True,
            output=output,
            expected_revision=None,
            final_revision=None,
            summary=None,
        )

        assert await main_async(args) == 0


class TestAliasAndFind08Evidence:
    """Live identities stay transient and firmware eligibility is exact."""

    def test_alias_map_must_be_external_and_normalises_serials(
        self, tmp_path: Path
    ) -> None:
        alias_path = tmp_path / "aliases.json"
        alias_path.write_text(
            json.dumps({"02:00:00:00:00:01": "fleet-alpha"}),
            encoding="utf-8",
        )
        assert _load_alias_map(alias_path) == {"020000000001": "fleet-alpha"}

        repo_path = Path.cwd() / "aliases.json"
        with pytest.raises(ValueError, match="outside the repository"):
            _load_alias_map(repo_path)

    def test_alias_map_preserves_uppercase_ascii_pseudonyms(
        self, tmp_path: Path
    ) -> None:
        alias_path = tmp_path / "aliases.json"
        alias_path.write_text(
            json.dumps({"02:00:00:00:00:01": "Fleet-Alpha"}),
            encoding="utf-8",
        )

        assert _load_alias_map(alias_path) == {"020000000001": "Fleet-Alpha"}

    @pytest.mark.parametrize(
        "alias",
        [
            "-Fleet",
            "Fleet_Name",
            "Fleet Alpha",
            "Équipe",
            "A" * 65,
            "A00000000001",
        ],
    )
    def test_alias_map_rejects_malformed_or_identifier_shaped_aliases(
        self,
        tmp_path: Path,
        alias: str,
    ) -> None:
        alias_path = tmp_path / "aliases.json"
        alias_path.write_text(
            json.dumps({"02:00:00:00:00:01": alias}),
            encoding="utf-8",
        )

        with pytest.raises(ValueError, match="alias|identifier"):
            _load_alias_map(alias_path)

    @pytest.mark.parametrize(
        "firmware, eligible",
        [((3, 69), False), ((3, 70), True), ((3, 99), True), ((4, 0), False)],
    )
    def test_find08_integer_boundaries(
        self, firmware: tuple[int, int], eligible: bool
    ) -> None:
        assert _eligible_find08_firmware(*firmware) is eligible

    def test_find08_normalises_and_collapses_duplicate_observations(self) -> None:
        evidence = _normalise_find08_observations(
            [
                ("02:00:00:00:00:01", "020000000001", 3, 70, "fleet-alpha"),
                ("02-00-00-00-00-01", "020000000001", 3, 70, "fleet-alpha"),
                ("020000000002", "020000000003", 3, 99, "fleet-beta"),
                ("020000000004", "020000000004", 4, 0, "fleet-ineligible"),
            ]
        )
        assert evidence == {
            "disposition": "observed",
            "devices": [
                {"alias": "fleet-alpha", "match": True},
                {"alias": "fleet-beta", "match": False},
            ],
        }

    def test_find08_empty_population_is_explicit_and_non_gating(self) -> None:
        assert _normalise_find08_observations([]) == {
            "disposition": "no_eligible_find08_population",
            "devices": [],
        }

    def test_find08_ignores_accepted_unsupported_device_without_alias(self) -> None:
        aliases = {
            "020000000001": "fleet-alpha",
            "020000000002": "fleet-alpha",
        }
        observations = [
            _DiscoveryObservation(
                source="udp", stage="accepted", raw_identity="020000000001"
            ),
            _DiscoveryObservation(
                source="mdns",
                stage="accepted",
                raw_identity="020000000002",
                connectivity="wifi",
                firmware_major=3,
                firmware_minor=70,
            ),
            _DiscoveryObservation(
                source="udp", stage="accepted", raw_identity="020000000099"
            ),
        ]

        assert _find08_from_observations(observations, {"020000000001"}, aliases) == {
            "disposition": "observed",
            "devices": [{"alias": "fleet-alpha", "match": False}],
        }

    def test_source_order_reconstructs_cross_source_winner(self) -> None:
        aliases = {
            "020000000001": "fleet-alpha",
            "020000000002": "fleet-alpha",
        }
        mdns = _DiscoveryObservation(
            source="mdns", stage="accepted", raw_identity="020000000002"
        )
        udp = _DiscoveryObservation(
            source="udp", stage="accepted", raw_identity="020000000001"
        )
        identities = set(aliases)

        mdns_first = _source_contributions([mdns, udp], identities, aliases)
        udp_first = _source_contributions([udp, mdns], identities, aliases)

        assert mdns_first == [
            {
                "alias": "fleet-alpha",
                "sources": ["mdns", "udp"],
                "winner": "mdns",
                "source_order": ["mdns", "udp"],
            }
        ]
        assert udp_first[0]["sources"] == mdns_first[0]["sources"]
        assert udp_first[0]["winner"] == "udp"
        assert udp_first[0]["source_order"] == ["udp", "mdns"]


class TestObservationScopeIsolation:
    """Only the exact caller context selects the measurement sink."""

    async def test_unrelated_concurrent_discovery_has_no_sink(self) -> None:
        seen = []

        async def _discover_with_packet(*args, _observer=None, **kwargs):
            seen.append(_observer)
            return
            yield

        async def _consume() -> None:
            async for _ in discover_devices(timeout=0.01):
                pass

        with patch(
            "lifx.network.discovery.udp._discover_with_packet",
            side_effect=_discover_with_packet,
        ):
            unrelated = asyncio.create_task(_consume())
            await asyncio.sleep(0)
            with _capture_discovery_observations() as sink:
                await _consume()
            await unrelated

        assert seen[0] is None
        assert getattr(seen[1], "__self__", None) is sink


class _FailIfConstructedMdnsTransport:
    """Prove an injected record source cannot touch ambient multicast I/O."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise AssertionError("MdnsTransport constructed inside private source override")


def _record() -> _LifxServiceRecord:
    return _LifxServiceRecord(
        serial="020000000001",
        ip="127.0.0.1",
        port=56700,
        product_id=91,
        firmware="3.70",
        connectivity="wifi",
        service_instance="synthetic._lifx._udp.local",
    )


class TestPrivateMdnsSourceOverride:
    """The hermetic record source is caller-local and always closed."""

    async def test_injected_source_bypasses_transport_and_resets(self) -> None:
        finalised = False

        async def _source():
            nonlocal finalised
            try:
                yield _record()
            finally:
                finalised = True

        with (
            patch(
                "lifx.network.discovery.mdns.discovery.MdnsTransport",
                _FailIfConstructedMdnsTransport,
            ),
            _override_mdns_service_source(_source),
        ):
            assert [record async for record in _discover_lifx_services()] == [_record()]
            assert _current_mdns_service_source_override() is not None

        assert finalised is True
        assert _current_mdns_service_source_override() is None

    async def test_failure_closes_source_and_resets_context(self) -> None:
        finalised = False

        async def _source():
            nonlocal finalised
            try:
                yield _record()
                raise RuntimeError("synthetic source failure")
            finally:
                finalised = True

        with pytest.raises(RuntimeError, match="synthetic source failure"):
            with _override_mdns_service_source(_source):
                async for _ in _discover_lifx_services():
                    pass

        assert finalised is True
        assert _current_mdns_service_source_override() is None

    async def test_cancellation_closes_source_and_resets_context(self) -> None:
        entered = asyncio.Event()
        finalised = asyncio.Event()

        async def _source():
            try:
                entered.set()
                await asyncio.Future()
                yield _record()
            finally:
                finalised.set()

        async def _consume() -> None:
            with _override_mdns_service_source(_source):
                async for _ in _discover_lifx_services():
                    pass

        task = asyncio.create_task(_consume())
        await entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        assert finalised.is_set()
        assert _current_mdns_service_source_override() is None


@pytest.mark.emulator
class TestEmbeddedEmulatorMeasurement:
    """The CLI owns a loopback endpoint and writes only categorical evidence."""

    async def test_baseline_mode_discovers_owned_synthetic_devices(
        self, tmp_path: Path
    ) -> None:
        output = tmp_path / "measurements.jsonl"
        args = argparse.Namespace(
            mode="baseline-only",
            validate_only=False,
            revision="e" * 40,
            expected_revision=None,
            environment="emulator",
            rounds=1,
            timeout=0.25,
            max_response_time=0.05,
            idle_timeout_multiplier=1.0,
            quiescence="quiesced",
            confound=[],
            alias_map=None,
            output=output,
            summary=None,
        )

        assert await main_async(args) == 0
        rows = _load_measurements(output)
        assert len(rows) == 1
        row = rows[0]
        assert row["arm"] == "baseline"
        assert row["implementation_path"] == "direct_udp"
        assert row["target"] == "owned_loopback_dynamic"
        assert row["revision"] == "e" * 40
        assert row["evidence_classification"] == "synthetic_mdns_lower_bound"
        assert row["round_classification"] == "single_round"
        unique_count = row["unique_count"]
        devices = row["devices"]
        assert isinstance(unique_count, int)
        assert isinstance(devices, list)
        assert unique_count >= 1
        assert all(
            isinstance(device, dict) and device["sources"] == ["udp"]
            for device in devices
        )
        assert "127.0.0.1" not in output.read_text(encoding="utf-8")
        assert "020000000001" not in output.read_text(encoding="utf-8")

    async def test_owned_emulator_feeds_private_mdns_source_without_transport(
        self,
    ) -> None:
        emulator = _EmbeddedMeasurementEmulator()
        async with emulator:
            assert emulator.server is not None
            assert emulator.port > 0
            assert emulator.server.port == emulator.port
            assert emulator.existing_device_ports
            assert set(emulator.existing_device_ports) == {emulator.port}
            assert emulator.later_device_port == emulator.port
            assert emulator.advertised_service_ports
            assert set(emulator.advertised_service_ports) == {emulator.port}
            assert all(
                device.state.port == emulator.port
                for device in emulator.server.get_all_devices()
            )
            with (
                patch(
                    "lifx.network.discovery.mdns.discovery.MdnsTransport",
                    _FailIfConstructedMdnsTransport,
                ),
                _override_mdns_service_source(emulator.service_source),
            ):
                records = [
                    record async for record in _discover_lifx_services(timeout=0.1)
                ]

            assert len(records) == 1
            assert records[0].port == emulator.port
            assert emulator.source_finalised is True

        assert emulator.server is None

    async def test_paired_mode_exercises_exact_merged_call_hermetically(
        self, tmp_path: Path
    ) -> None:
        output = tmp_path / "paired.jsonl"
        revision = "f" * 40
        args = argparse.Namespace(
            mode="paired",
            validate_only=False,
            revision=revision,
            expected_revision=None,
            environment="emulator",
            rounds=1,
            timeout=0.5,
            max_response_time=0.05,
            idle_timeout_multiplier=1.0,
            quiescence="quiesced",
            confound=[],
            alias_map=None,
            output=output,
            summary=None,
        )
        closed_connections: list[DeviceConnection] = []
        original_close = DeviceConnection.close

        async def _track_close(connection: DeviceConnection) -> None:
            await original_close(connection)
            closed_connections.append(connection)

        with (
            patch(
                "lifx.network.discovery.mdns.discovery.MdnsTransport",
                _FailIfConstructedMdnsTransport,
            ),
            patch.object(
                MdnsTransport,
                "open",
                autospec=True,
                side_effect=AssertionError("ambient mDNS socket opened"),
            ) as open_spy,
            patch.object(
                MdnsTransport,
                "send",
                autospec=True,
                side_effect=AssertionError(
                    f"fixed multicast send attempted: {MDNS_ADDRESS}:{MDNS_PORT}"
                ),
            ) as send_spy,
            patch.object(DeviceConnection, "close", new=_track_close),
        ):
            assert await main_async(args) == 0

        assert not open_spy.called
        assert not send_spy.called
        assert closed_connections
        assert all(not connection.is_open for connection in closed_connections)
        assert _current_mdns_service_source_override() is None
        assert _current_discovery_observation_sink() is None

        rows = _load_measurements(output)
        _validate_measurements(rows, expected_revision=revision)
        assert [row["arm"] for row in rows] == ["baseline", "merged"]
        baseline, merged = rows
        assert baseline["implementation_path"] == "direct_udp"
        assert all(device["sources"] == ["udp"] for device in baseline["devices"])
        primary = next(
            device
            for device in merged["devices"]
            if device["alias"] == "synthetic-primary"
        )
        assert set(primary["sources"]) == {"udp", "mdns"}
        assert merged["implementation_path"] == "merged_dual"
        assert all(row["unique_count"] > 0 for row in rows)

    async def test_exact_merged_measurement_reaps_failed_source(self) -> None:
        emulator = _EmbeddedMeasurementEmulator()
        source_finalised = False
        transport = None

        async with emulator:
            assert emulator.server is not None
            transport = emulator.server.transport

            async def _failing_source():
                nonlocal source_finalised
                assert emulator.mdns_record is not None
                try:
                    yield emulator.mdns_record
                    raise RuntimeError("synthetic source failure")
                finally:
                    source_finalised = True

            with (
                patch.object(emulator, "service_source", new=_failing_source),
                pytest.raises(RuntimeError, match="synthetic source failure"),
            ):
                await _measure_arm(
                    arm="merged",
                    scenario_id="scenario-failure",
                    pair_id="pair-failure",
                    round_number=1,
                    environment="emulator",
                    revision="1" * 40,
                    quiescence="quiesced",
                    confounds=[],
                    aliases=emulator.aliases,
                    timeout=0.5,
                    max_response_time=0.05,
                    idle_timeout_multiplier=1.0,
                    emulator=emulator,
                )

        assert source_finalised is True
        assert transport is not None
        assert transport.is_closing()
        assert emulator.server is None
        assert _current_mdns_service_source_override() is None
        assert _current_discovery_observation_sink() is None

    async def test_exact_merged_measurement_reaps_cancelled_source(self) -> None:
        emulator = _EmbeddedMeasurementEmulator()
        source_entered = asyncio.Event()
        source_finalised = asyncio.Event()
        transport = None

        async with emulator:
            assert emulator.server is not None
            transport = emulator.server.transport

            async def _blocked_source():
                try:
                    source_entered.set()
                    await asyncio.Future()
                    yield _record()
                finally:
                    source_finalised.set()

            with patch.object(emulator, "service_source", new=_blocked_source):
                task = asyncio.create_task(
                    _measure_arm(
                        arm="merged",
                        scenario_id="scenario-cancel",
                        pair_id="pair-cancel",
                        round_number=1,
                        environment="emulator",
                        revision="2" * 40,
                        quiescence="quiesced",
                        confounds=[],
                        aliases=emulator.aliases,
                        timeout=1.0,
                        max_response_time=0.05,
                        idle_timeout_multiplier=1.0,
                        emulator=emulator,
                    )
                )
                await source_entered.wait()
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task

        assert source_finalised.is_set()
        assert transport is not None
        assert transport.is_closing()
        assert emulator.server is None
        assert _current_mdns_service_source_override() is None
        assert _current_discovery_observation_sink() is None

    async def test_server_closes_on_failure_and_cancellation(self) -> None:
        failing = _EmbeddedMeasurementEmulator()
        transport = None
        with pytest.raises(RuntimeError, match="synthetic body failure"):
            async with failing:
                assert failing.server is not None
                transport = failing.server.transport
                raise RuntimeError("synthetic body failure")
        assert transport is not None
        assert transport.is_closing()

        entered = asyncio.Event()
        cancelling = _EmbeddedMeasurementEmulator()
        observed_transport = None

        async def _run() -> None:
            nonlocal observed_transport
            async with cancelling:
                assert cancelling.server is not None
                observed_transport = cancelling.server.transport
                entered.set()
                await asyncio.Future()

        task = asyncio.create_task(_run())
        await entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert observed_transport is not None
        assert observed_transport.is_closing()
