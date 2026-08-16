"""Contract tests for the Phase 8 hardware-fidelity tracer."""

from __future__ import annotations

import asyncio
import dataclasses
import json
import os
from collections.abc import Callable, Mapping
from pathlib import Path
from types import SimpleNamespace

import pytest
import uat_theme_fidelity as runner
from uat_theme_fidelity import (
    EXIT_INCOMPLETE,
    EXIT_MISMATCH,
    EXIT_PASS,
    EXIT_RESTORATION_FAILURE,
    OFFICIAL_THEME_SLUGS,
    AdbCommandError,
    CycleResult,
    RunnerSettings,
    SemanticLookupError,
    ThemeSpec,
    adb,
    build_parser,
    load_target_bindings,
    normalise_category_heading,
    poll_stable_palette,
    run_tracer_cycle,
    scroll_to_semantic_theme,
    theme_from_readback,
    with_android_keep_awake,
    write_diagnostics,
)

from lifx.color import HSBK
from lifx.protocol.protocol_types import FirmwareEffect
from lifx.theme import Theme

CANONICAL_RUN_ID = "0123456789abcdef0123456789abcdef"


@pytest.fixture(autouse=True)
def inject_private_path_boundary(monkeypatch: pytest.MonkeyPatch) -> None:
    """Translate legacy fake CLI fixtures into the in-process path seam.

    Production no longer accepts a root override.  Existing fake-only dispatch
    tests retain their isolated filesystems by supplying ``PrivatePathBoundary``
    directly to the production ``main`` function, rather than exercising an
    alternate CLI path.
    """
    production_main = runner.main

    async def isolated_main(
        argv: list[str] | None = None,
        *,
        private_paths: runner.PrivatePathBoundary | None = None,
    ) -> int:
        arguments = list(argv or ())
        if "--private-root" not in arguments:
            return await production_main(arguments, private_paths=private_paths)
        root_index = arguments.index("--private-root")
        root = Path(arguments[root_index + 1])
        del arguments[root_index : root_index + 2]
        target: Path | None = None
        if "--targets" in arguments:
            target_index = arguments.index("--targets")
            target = Path(arguments[target_index + 1])
            del arguments[target_index : target_index + 2]
        canonical_target = root / "targets.json"
        if target is not None and target.exists():
            root.mkdir(parents=True, exist_ok=True)
            canonical_target.write_bytes(target.read_bytes())
        return await production_main(
            arguments,
            private_paths=runner.PrivatePathBoundary(root, canonical_target),
        )

    monkeypatch.setattr(runner, "main", isolated_main)


def colour(hue: float) -> HSBK:
    """Build a visibly distinct colour for equality contract tests."""
    return HSBK(hue=hue, saturation=1.0, brightness=1.0, kelvin=3500)


def complete_palette() -> list[HSBK]:
    """Build one complete synthetic Morph palette for public-evidence contracts."""
    return [colour(hue) for hue in range(16)]


def canonical_theme_palette(slug: str) -> list[HSBK]:
    """Return one exact committed palette for public-result validation tests."""
    return list(runner.load_theme_specs()[slug].expected_palette)


def test_palette_uses_theme_multiset_equality_and_keeps_duplicate_counts() -> None:
    """Readbacks remain duplicate-sensitive but ignore device shuffle order."""
    expected = Theme([colour(0), colour(120), colour(120)])
    reordered = theme_from_readback([colour(120), colour(0), colour(120)])
    changed_count = theme_from_readback([colour(120), colour(0), colour(0)])

    assert expected.palette_equals(reordered)
    assert not expected.palette_equals(changed_count)


def test_none_readback_becomes_empty_not_default_white() -> None:
    """An absent palette must not turn into Theme's default white palette."""
    assert theme_from_readback(None).colors == []


def test_manual_position_attestation_requires_the_exact_morph_config_surface() -> None:
    """Operator positioning is accepted only when the live semantic state is exact."""
    binding = runner.TargetBinding(
        "source-tile", "private", "d073d5000001", "private label", True, True, "group"
    )
    controls = [
        {"resource-id": "app:id/detail_panel", "bounds": "[900,0][1800,2880]"},
        {
            "text": "Morph",
            "resource-id": "app:id/effect_name",
            "bounds": "[950,213][1755,290]",
        },
        {
            "text": "Effect",
            "resource-id": "app:id/effect_subtitle",
            "bounds": "[950,290][1755,342]",
        },
        {
            "resource-id": "app:id/effect_settings_controller_scroll_view",
            "bounds": "[950,342][1755,1313]",
        },
        {
            "resource-id": "app:id/theme_button",
            "clickable": "true",
            "enabled": "true",
            "bounds": "[950,463][1293,586]",
        },
    ]

    with pytest.raises(runner.PreflightError):
        runner.attest_manual_role_position(
            binding, controls, run_id="opaque", timestamp="2026-08-16T00:00:00Z"
        )
    with pytest.raises(runner.PreflightError):
        runner.attest_manual_role_position(
            binding,
            controls,
            run_id="opaque",
            timestamp="2026-08-16T00:00:00Z",
            attested_role="non-tile-matrix",
        )
    record = runner.attest_manual_role_position(
        binding,
        controls,
        run_id="opaque",
        timestamp="2026-08-16T00:00:00Z",
        attested_role="source-tile",
    )

    assert record.operator_attested_role == "source-tile"
    assert record.operator_attested and record.ui_morph_config_observed
    assert (
        record.effect_name
        and record.effect_subtitle
        and record.effect_settings
        and record.theme_button
    )
    assert runner.manual_attestation_record(record) == {
        "event": "manual-role-attestation",
        "run_id": "opaque",
        "role": "source-tile",
        "binding_digest": runner.binding_digest(binding),
        "timestamp": "2026-08-16T00:00:00Z",
        "operator_attested": True,
        "ui_morph_config_observed": True,
        "effect_name": True,
        "effect_subtitle": True,
        "effect_settings": True,
        "theme_button": True,
    }
    for rejected in (
        [
            *controls,
            {
                "text": "Morph",
                "resource-id": "other/effect_name",
                "bounds": "[950,213][1755,290]",
            },
        ],
        [
            {**control, "text": "MORPH"}
            if control.get("resource-id", "").endswith("effect_name")
            else dict(control)
            for control in controls
        ],
        [
            {**control, "text": "Effects"}
            if control.get("resource-id", "").endswith("effect_subtitle")
            else dict(control)
            for control in controls
        ],
        [
            control
            for control in controls
            if not control.get("resource-id", "").endswith("effect_subtitle")
        ],
        [
            control
            for control in controls
            if not control.get("resource-id", "").endswith(
                "effect_settings_controller_scroll_view"
            )
        ],
        [
            *controls,
            {
                "resource-id": "other/effect_settings_controller_scroll_view",
                "bounds": "[950,342][1755,1313]",
            },
        ],
        [
            control
            for control in controls
            if not control.get("resource-id", "").endswith("theme_button")
        ],
        [
            *controls,
            {
                "resource-id": "other/theme_button",
                "clickable": "true",
                "enabled": "true",
                "bounds": "[950,463][1293,586]",
            },
        ],
        [
            {**control, "enabled": "false"}
            if control.get("resource-id", "").endswith("theme_button")
            else dict(control)
            for control in controls
        ],
        [
            {**control, "clickable": "false"}
            if control.get("resource-id", "").endswith("theme_button")
            else dict(control)
            for control in controls
        ],
        [
            {**control, "bounds": "[0,0][10,10]"}
            if control.get("resource-id", "").endswith("theme_button")
            else dict(control)
            for control in controls
        ],
    ):
        with pytest.raises(runner.SemanticLookupError):
            runner.attest_manual_role_position(
                binding,
                rejected,
                run_id="opaque",
                timestamp="2026-08-16T00:00:00Z",
                attested_role="source-tile",
            )
    generic_fx = [
        *controls[:1],
        {"text": "FX", "resource-id": "app:id/ax_device_control_effects_tab"},
        {"text": "MORPH", "resource-id": "app:id/current_effect"},
    ]
    with pytest.raises(runner.SemanticLookupError):
        runner.attest_manual_role_position(
            binding,
            generic_fx,
            run_id="opaque",
            timestamp="2026-08-16T00:00:00Z",
            attested_role="source-tile",
        )


def test_manual_attestation_cannot_cross_run_or_role_or_binding() -> None:
    """Private progress can never turn a source position into a second role position."""
    binding = runner.TargetBinding(
        "source-tile", "private", "d073d5000001", "private label", True, True, "group"
    )
    record = runner.ManualRoleAttestation(
        run_id="opaque",
        operator_attested_role="source-tile",
        binding_digest=runner.binding_digest(binding),
        timestamp="2026-08-16T00:00:00Z",
        operator_attested=True,
        ui_morph_config_observed=True,
        effect_name=True,
        effect_subtitle=True,
        effect_settings=True,
        theme_button=True,
    )
    runner.validate_manual_role_attestation(record, binding, run_id="opaque")
    with pytest.raises(runner.PreflightError):
        runner.validate_manual_role_attestation(record, binding, run_id="other")
    with pytest.raises(runner.PreflightError):
        runner.validate_manual_role_attestation(
            dataclasses.replace(record, binding_digest="different"),
            binding,
            run_id="opaque",
        )


def test_initial_theme_attestation_is_an_explicit_private_operator_claim() -> None:
    """The hidden current picker theme is never inferred from the Morph UI."""
    binding = runner.TargetBinding(
        "source-tile", "private", "d073d5000001", "private label", True, True, "group"
    )
    with pytest.raises(runner.PreflightError):
        runner.attest_initial_theme(
            binding,
            run_id="opaque",
            timestamp="2026-08-16T00:00:00Z",
            attested_role="source-tile",
            attested_initial_theme=None,
        )
    with pytest.raises(runner.PreflightError):
        runner.attest_initial_theme(
            binding,
            run_id="opaque",
            timestamp="2026-08-16T00:00:00Z",
            attested_role="source-tile",
            attested_initial_theme="mondrian",
        )
    record = runner.attest_initial_theme(
        binding,
        run_id="opaque",
        timestamp="2026-08-16T00:00:00Z",
        attested_role="source-tile",
        attested_initial_theme="cheerful",
    )
    runner.validate_initial_theme_attestation(record, binding, run_id="opaque")
    assert runner.initial_theme_attestation_record(record) == {
        "event": "initial-theme-attestation",
        "run_id": "opaque",
        "role": "source-tile",
        "binding_digest": runner.binding_digest(binding),
        "timestamp": "2026-08-16T00:00:00Z",
        "initial_theme": "cheerful",
        "operator_attested": True,
    }
    assert "initial_theme" not in runner._PUBLIC_ROOT_KEYS
    assert "attestation" not in runner._PUBLIC_ROOT_KEYS
    with pytest.raises(SystemExit):
        runner.build_parser().parse_args(
            ["--run", "--attest-initial-theme", "mondrian"]
        )
    with pytest.raises(runner.PreflightError):
        runner.validate_initial_theme_attestation(
            dataclasses.replace(record, binding_digest="different"),
            binding,
            run_id="opaque",
        )


def test_production_app_cycle_refuses_a_role_without_current_attestation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A source position is never sufficient to operate the non-Tile role."""
    binding = runner.TargetBinding(
        "non-tile-matrix",
        "private",
        "d073d5000002",
        "private label",
        True,
        True,
        "group",
    )

    with pytest.raises(runner.PreflightError):
        asyncio.run(
            runner._production_app_cycle(
                "non-tile-matrix",
                ThemeSpec("cheerful", "Cheerful", "Moods", [], "hash"),
                1,
                object(),
                binding=binding,
                settings=RunnerSettings(),
                run_directory=tmp_path,
                run_id="opaque",
                timestamp="2026-08-16T00:00:00Z",
                attested_role="source-tile",
            )
        )

    async def forbidden_save(*args: object, **kwargs: object) -> None:
        raise AssertionError("semantic app save must not run without an attestation")

    monkeypatch.setattr(runner, "semantic_app_save", forbidden_save)
    with pytest.raises(runner.PreflightError):
        asyncio.run(
            runner._production_app_cycle(
                "non-tile-matrix",
                ThemeSpec("cheerful", "Cheerful", "Moods", [], "hash"),
                1,
                object(),
                binding=binding,
                settings=RunnerSettings(),
                run_directory=tmp_path,
                run_id="opaque",
                timestamp="2026-08-16T00:00:00Z",
                attested_role=None,
            )
        )


def test_category_normalisation_uses_the_shipped_slug_rule() -> None:
    """Picker headings may add emoji and uppercase without changing category."""
    assert normalise_category_heading("Art Series") == "art_series"
    assert normalise_category_heading("🎨 ART SERIES") == "art_series"


def test_scroll_reaches_offscreen_exact_mondrian_with_fresh_hierarchies() -> None:
    """Each scroll inspects a new hierarchy and display names stay exact."""
    dumps = iter(
        [
            [
                {"text": "Other", "bounds": "[0,0][10,10]"},
                {
                    "class": "android.widget.ScrollView",
                    "scrollable": "true",
                    "bounds": "[10,20][110,220]",
                },
            ],
            [{"text": "Mondrian", "bounds": "[0,0][10,10]"}],
        ]
    )
    swipes: list[runner.Control] = []

    control = scroll_to_semantic_theme(
        "Mondrian",
        dump_hierarchy=lambda: next(dumps),
        swipe_scrollable=swipes.append,
        max_scrolls=2,
    )

    assert control["text"] == "Mondrian"
    assert swipes == [
        {
            "class": "android.widget.ScrollView",
            "scrollable": "true",
            "bounds": "[10,20][110,220]",
        }
    ]


def test_scroll_exhaustion_fails_before_save() -> None:
    """A bounded semantic miss cannot silently use a remembered grid position."""
    with pytest.raises(SemanticLookupError) as failure:
        scroll_to_semantic_theme(
            "Mondrian",
            dump_hierarchy=lambda: [],
            swipe_scrollable=lambda control: None,
            max_scrolls=1,
        )

    assert failure.value.exit_code == EXIT_INCOMPLETE


@pytest.mark.parametrize(
    "drift",
    [
        {"app_version": "4.97.0"},
        {"catalogue_fingerprint": "different-catalogue"},
        {"firmware_by_role": {"source-tile": "3.51", "non-tile-matrix": "4.0"}},
        {"firmware_by_role": {"source-tile": "3.50", "non-tile-matrix": "4.1"}},
    ],
)
def test_main_resume_rejects_live_provenance_drift_before_lifecycle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    drift: dict[str, object],
) -> None:
    """Main recaptures live app, surface, and firmware provenance before writes."""
    root = tmp_path / "runs"
    targets = tmp_path / "targets.json"
    target_document = approved_targets()
    write_targets(targets, target_document)
    bindings = {
        role: runner.TargetBinding(
            role,
            item["host"],  # type: ignore[index,arg-type]
            item["serial"],  # type: ignore[index,arg-type]
            item["app_label"],  # type: ignore[index,arg-type]
            True,
            True,
            item["app_group"],  # type: ignore[index,arg-type]
        )
        for role, item in (
            ("source-tile", target_document["source-tile"]),
            ("non-tile-matrix", target_document["non-tile-matrix"]),
        )
    }
    settings = runner.RunnerSettings(targets_path=targets, private_root=root)
    saved_preflight = runner.PreflightReport(
        "4.96.0",
        "catalogue",
        {
            "source-tile": {"firmware": "3.50"},
            "non-tile-matrix": {"firmware": "4.0"},
        },
    )
    saved_provenance = runner.build_live_provenance(
        runner_revision="phase-08",
        preflight=saved_preflight,
        bindings=bindings,
        theme_specs=runner.load_theme_specs(),
        settings=settings,
    )
    run_directory = root / CANONICAL_RUN_ID
    runner.write_checkpoint(
        run_directory / "checkpoint.json",
        runner.RunCheckpoint(
            CANONICAL_RUN_ID,
            saved_provenance,
            runner.build_cycle_schedule()[0],
            [],
            None,
            False,
        ),
    )
    report_values = {
        "app_version": saved_preflight.app_version,
        "catalogue_fingerprint": saved_preflight.catalogue_fingerprint,
        "firmware_by_role": {
            role: metadata["firmware"]
            for role, metadata in saved_preflight.metadata_by_role.items()
        },
    }
    report_values.update(drift)
    firmware = report_values["firmware_by_role"]
    assert isinstance(firmware, dict)
    live_preflight = runner.PreflightReport(
        report_values["app_version"],  # type: ignore[arg-type]
        report_values["catalogue_fingerprint"],  # type: ignore[arg-type]
        {role: {"firmware": value} for role, value in firmware.items()},
    )
    preflight_calls: list[str] = []
    lifecycle_calls: list[str] = []

    async def preflight(**kwargs: object) -> runner.PreflightReport:
        preflight_calls.append("preflight")
        return live_preflight

    async def forbidden_lifecycle(**kwargs: object) -> runner.LifecycleResult:
        lifecycle_calls.append("lifecycle")
        raise AssertionError("provenance drift reached lifecycle")

    monkeypatch.setattr(runner, "run_non_mutating_preflight", preflight)
    monkeypatch.setattr(runner, "run_designated_lifecycle", forbidden_lifecycle)
    monkeypatch.setattr(runner, "_write_private_event", lambda *args, **kwargs: None)

    result = asyncio.run(
        runner.main(
            [
                "--resume",
                CANONICAL_RUN_ID,
                "--attest-role",
                "source-tile",
                "--attest-initial-theme",
                "cheerful",
                "--targets",
                str(targets),
                "--private-root",
                str(root),
            ]
        )
    )

    assert result == runner.EXIT_INCOMPLETE
    assert preflight_calls == ["preflight"]
    assert lifecycle_calls == []


@pytest.mark.parametrize(
    "controls",
    [
        [],
        [
            {"scrollable": "true", "bounds": "[0,0][10,10]"},
            {"scrollable": "true", "bounds": "[20,0][30,10]"},
        ],
    ],
)
def test_theme_scroll_requires_one_current_picker_container(
    controls: list[runner.Control],
) -> None:
    """An absent or ambiguous picker cannot receive a coordinate-only swipe."""
    with pytest.raises(SemanticLookupError):
        scroll_to_semantic_theme(
            "Mondrian",
            dump_hierarchy=lambda: controls,
            swipe_scrollable=lambda control: None,
            max_scrolls=1,
        )


def test_theme_scroll_rejects_a_repeated_picker_surface() -> None:
    """A gesture that does not change the fresh hierarchy cannot be retried blindly."""
    picker = [
        {"text": "Other", "bounds": "[0,0][10,10]"},
        {
            "class": "android.widget.ScrollView",
            "scrollable": "true",
            "bounds": "[10,20][110,220]",
        },
    ]
    dumps = iter([picker, picker])

    with pytest.raises(SemanticLookupError):
        scroll_to_semantic_theme(
            "Mondrian",
            dump_hierarchy=lambda: next(dumps),
            swipe_scrollable=lambda control: None,
            max_scrolls=2,
        )


def test_scrollable_bounds_remain_a_pure_geometry_helper() -> None:
    """Retired group navigation helpers do not provide a production command path."""
    assert runner._scrollable_swipe_points({"bounds": "[950,1331][1755,1862]"}) == (
        1352,
        1729,
        1352,
        1463,
    )


def test_group_expansion_refuses_an_ambiguous_exact_device_label() -> None:
    """A configured group never turns a duplicate target label into a valid selector."""
    binding = runner.TargetBinding(
        "source-tile", "private", "d073d5000001", "private label", True, True, "group"
    )
    taps: list[str] = []

    with pytest.raises(runner.SemanticLookupError):
        runner.resolve_bound_device_control(
            binding,
            dump_hierarchy=lambda: [
                {"text": "private label"},
                {"text": "private label"},
                {"text": "group"},
            ],
            tap_control=lambda control: taps.append(runner._text(control)),
            swipe_scrollable=lambda control: None,
        )

    assert taps == []


def test_preflight_home_reset_fails_closed_when_fresh_home_never_appears() -> None:
    """Launch success cannot substitute for a fresh semantic Home surface."""
    bindings = {
        role: runner.TargetBinding(
            role,
            "private",
            f"d073d500000{index}",
            f"private {role}",
            True,
            True,
            f"group_{index}",
        )
        for index, role in enumerate(("source-tile", "non-tile-matrix"), 1)
    }
    opened: list[str] = []

    with pytest.raises(runner.SemanticLookupError):
        runner.preflight_app_reconnaissance(
            bindings,
            {},
            max_theme_scrolls=0,
            open_home=lambda: opened.append("home"),
            dump_hierarchy=lambda: [{"text": "MORPH"}],
            tap_control=lambda control: None,
            return_to_morph=lambda: None,
            swipe=lambda: None,
            swipe_device_list=lambda control: None,
        )

    assert opened == ["home"]


@pytest.mark.parametrize("selector_count", [1, 2])
def test_home_readiness_rejects_selector_exposed_label(
    selector_count: int,
) -> None:
    """Neither one nor many target selectors can impersonate the Home hierarchy."""
    binding = runner.TargetBinding(
        "source-tile", "private", "d073d5000001", "private label", True, True, "group"
    )

    with pytest.raises(runner.SemanticLookupError):
        runner._require_home_ready(
            {binding.role: binding},
            [
                *[{"text": "Select lights"} for _ in range(selector_count)],
                {"text": "private label"},
            ],
        )


def test_preflight_retries_selector_surface_before_any_target_or_selector_tap() -> None:
    """A residual selector exhausts Home proof before target navigation begins."""
    binding = runner.TargetBinding(
        "source-tile", "private", "d073d5000001", "private label", True, True, "group"
    )
    dumps = iter(
        [
            [{"text": "Select lights"}, {"text": "private label"}],
            [{"text": "Select lights"}, {"text": "private label"}],
            [{"text": "Select lights"}, {"text": "private label"}],
        ]
    )
    taps: list[runner.Control] = []
    opened: list[str] = []

    with pytest.raises(runner.SemanticLookupError):
        runner.preflight_app_reconnaissance(
            {binding.role: binding},
            {},
            max_theme_scrolls=0,
            open_home=lambda: opened.append("home"),
            dump_hierarchy=lambda: next(dumps),
            tap_control=taps.append,
            return_to_morph=lambda: None,
            swipe=lambda: None,
            swipe_device_list=lambda control: None,
        )

    assert opened == ["home"]
    assert taps == []


@pytest.mark.parametrize(
    "home_controls",
    [
        [{"text": "private label"}],
        [{"resource-id": "app:id/ax_device_list_group_card_button_group"}],
    ],
)
def test_home_readiness_accepts_real_label_or_group_card(
    home_controls: list[runner.Control],
) -> None:
    """A selector-free Home remains valid through either approved semantic proof."""
    binding = runner.TargetBinding(
        "source-tile", "private", "d073d5000001", "private label", True, True, "group"
    )

    assert runner._require_home_ready({binding.role: binding}, home_controls) is None


def test_semantic_cycle_rejects_selector_before_any_tap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Scheduled app cycles inherit the same selector-free Home requirement."""
    binding = runner.TargetBinding(
        "source-tile", "private", "d073d5000001", "private label", True, True, "group"
    )
    commands: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        runner,
        "dump_ui_hierarchy",
        lambda *args, **kwargs: [
            {"text": "Select lights"},
            {"text": "private label"},
        ],
    )
    monkeypatch.setattr(
        runner, "adb", lambda *args, **kwargs: commands.append(tuple(args)) or ""
    )

    with pytest.raises(runner.SemanticLookupError):
        asyncio.run(
            runner.semantic_app_save(
                binding,
                ThemeSpec("cheerful", "Cheerful", "Moods", [], "hash"),
                settings=RunnerSettings(),
                run_directory=tmp_path,
                attested_role="source-tile",
                open_home=lambda: None,
            )
        )

    assert commands == []


def test_preflight_proves_both_hidden_roles_then_reconnoitres_source_only() -> None:
    """One selector-free Home proof precedes the only preflight target selection."""
    source = runner.TargetBinding(
        "source-tile", "private", "d073d5000001", "source label", True, True, "source"
    )
    secondary = runner.TargetBinding(
        "non-tile-matrix",
        "private",
        "d073d5000002",
        "secondary label",
        True,
        True,
        "secondary",
    )
    source_card = {
        "resource-id": "app:id/ax_device_list_group_card_button_source",
        "bounds": "[0,0][10,10]",
    }
    secondary_card = {
        "resource-id": "app:id/ax_device_list_group_card_button_secondary",
        "bounds": "[20,0][30,10]",
    }
    source_page = [
        {"resource-id": "app:id/detail_panel", "bounds": "[950,900][1755,1900]"},
        {"text": "source", "bounds": "[950,990][1165,1067]"},
        {"clickable": "true", "bounds": "[950,1110][1085,1218]"},
        {"text": "Lights", "bounds": "[1040,1139][1058,1188]"},
    ]
    selected_source_page = [
        {"resource-id": "app:id/detail_panel", "bounds": "[950,900][1755,1900]"},
        {"text": "source", "bounds": "[950,990][1165,1067]"},
        {"clickable": "true", "bounds": "[950,1110][1085,1218]"},
        {"text": "1", "bounds": "[1040,1139][1058,1188]"},
        {"resource-id": "app:id/ax_device_control_effects_tab"},
    ]
    selector_after_target = [
        *selected_source_page,
        {"text": "Select lights", "bounds": "[950,1200][1300,1260]"},
        {
            "resource-id": "app:id/ax_device_control_close_button",
            "clickable": "true",
            "bounds": "[936,857][1044,965]",
        },
    ]
    opened: list[str] = []
    taps: list[runner.Control] = []
    dumps = iter(
        [
            [source_card, secondary_card],
            [source_card],
            source_page,
            [{"text": "Select lights"}],
            [{"text": "source label"}],
            selector_after_target,
            selected_source_page,
            [{"text": "MORPH"}],
            [{"text": "MORPH"}, {"text": "Moods"}, {"text": "Art Series"}],
            [{"text": "Cheerful"}, {"resource-id": "app:id/save_button"}],
            [{"text": "MORPH"}, {"text": "Art Series"}],
            [{"text": "Mondrian"}, {"resource-id": "app:id/save_button"}],
            [{"text": "Mondrian"}, {"resource-id": "app:id/save_button"}],
            [{"text": "Mondrian"}, {"resource-id": "app:id/save_button"}],
        ]
    )

    runner.preflight_app_reconnaissance(
        {source.role: source, secondary.role: secondary},
        {
            "cheerful": ThemeSpec("cheerful", "Cheerful", "Moods", [], "x"),
            "mondrian": ThemeSpec("mondrian", "Mondrian", "Art Series", [], "y"),
        },
        max_theme_scrolls=0,
        open_home=lambda: opened.append("home"),
        dump_hierarchy=lambda: next(dumps),
        tap_control=taps.append,
        return_to_morph=lambda: None,
        swipe=lambda: None,
        swipe_device_list=lambda control: None,
    )

    assert opened == ["home"]
    assert [control for control in taps if control.get("text") == "source label"] == [
        {"text": "source label"}
    ]
    assert sum(control is secondary_card for control in taps) == 0
    assert sum(control.get("text") == "Lights" for control in taps) == 0
    close_index = next(
        index
        for index, control in enumerate(taps)
        if control.get("resource-id", "").endswith("ax_device_control_close_button")
    )
    target_index = next(
        index
        for index, control in enumerate(taps)
        if control.get("text") == "source label"
    )
    assert target_index < close_index


@pytest.mark.parametrize(
    "home_controls",
    [
        [{"resource-id": "app:id/ax_device_list_group_card_button_source"}],
        [
            {"resource-id": "app:id/ax_device_list_group_card_button_source"},
            {"resource-id": "app:id/ax_device_list_group_card_button_source"},
            {"resource-id": "app:id/ax_device_list_group_card_button_secondary"},
        ],
    ],
)
def test_home_proof_rejects_missing_or_duplicate_required_binding(
    home_controls: list[runner.Control],
) -> None:
    """Both approved roles must have one unambiguous selector-free Home proof."""
    bindings = {
        "source-tile": runner.TargetBinding(
            "source-tile", "private", "d073d5000001", "source", True, True, "source"
        ),
        "non-tile-matrix": runner.TargetBinding(
            "non-tile-matrix",
            "private",
            "d073d5000002",
            "secondary",
            True,
            True,
            "secondary",
        ),
    }

    with pytest.raises(runner.SemanticLookupError):
        runner._require_home_ready(bindings, home_controls)


def test_home_readiness_rejects_duplicate_bound_label() -> None:
    """Home cannot resolve a target when its exact approved label is duplicated."""
    binding = runner.TargetBinding(
        "source-tile", "private", "d073d5000001", "private label", True, True, "group"
    )

    with pytest.raises(runner.SemanticLookupError):
        runner._require_home_ready(
            {binding.role: binding},
            [{"text": "private label"}, {"text": "private label"}],
        )


def test_group_card_expansion_requires_one_exact_configured_box() -> None:
    """Repeated group text cannot substitute for the one bound group-card control."""
    binding = runner.TargetBinding(
        "source-tile", "private", "d073d5000001", "private label", True, True, "group"
    )
    group_box = {
        "text": "group",
        "resource-id": "app:id/ax_device_list_group_card_button_group",
    }
    repeated_group_text = [{"text": "group"} for _ in range(6)]
    selector_button = {"clickable": "true", "bounds": "[950,1110][1085,1218]"}
    selector_marker = {"text": "Lights", "bounds": "[1040,1139][1058,1188]"}
    group_page = [
        {"resource-id": "app:id/detail_panel", "bounds": "[950,900][1755,1900]"},
        {"text": "group", "bounds": "[108,2060][264,2113]"},
        {"text": "group", "bounds": "[950,990][1165,1067]"},
        {"content-desc": "Lights", "resource-id": "app:id/ax_home_tab_lights"},
        selector_button,
        selector_marker,
    ]
    dumps = iter(
        [
            [*repeated_group_text, group_box],
            group_page,
            [{"text": "Select lights"}],
            [{"text": "private label"}],
        ]
    )
    taps: list[dict[str, str]] = []

    control = runner.resolve_bound_device_control(
        binding,
        dump_hierarchy=lambda: next(dumps),
        tap_control=taps.append,
        swipe_scrollable=lambda control: None,
    )

    assert control == {"text": "private label"}
    assert taps == [group_box, selector_button]
    for invalid_boxes in (
        [
            {
                "text": "group",
                "resource-id": "app:id/ax_device_list_group_card_button_other",
            }
        ],
        [group_box, group_box],
    ):
        with pytest.raises(runner.SemanticLookupError):
            runner.resolve_bound_device_control(
                binding,
                dump_hierarchy=lambda invalid_boxes=invalid_boxes: invalid_boxes,
                tap_control=lambda control: None,
                swipe_scrollable=lambda control: None,
            )
    for invalid_lights in (
        [{"content-desc": "Lights", "resource-id": "app:id/ax_home_tab_lights"}],
        [{"text": "Lights"}, {"text": "Lights"}],
    ):
        invalid_group_page = [*group_page[:3], *invalid_lights]
        invalid_dumps = iter([[group_box], invalid_group_page])
        with pytest.raises(runner.SemanticLookupError):
            runner.resolve_bound_device_control(
                binding,
                dump_hierarchy=lambda: next(invalid_dumps),
                tap_control=lambda control: None,
                swipe_scrollable=lambda control: None,
            )


def test_group_transition_waits_for_detail_heading_and_select_lights() -> None:
    """Stale source controls cannot prove a different configured group transition."""
    binding = runner.TargetBinding(
        "non-tile-matrix",
        "private",
        "d073d5000002",
        "private label",
        True,
        True,
        "secondary_group",
    )
    group_box = {
        "resource-id": "app:id/ax_device_list_group_card_button_secondary_group",
        "bounds": "[0,0][4,4]",
    }
    detail_panel = {
        "resource-id": "app:id/detail_panel",
        "bounds": "[950,900][1755,1900]",
    }
    stale_group_page = [
        detail_panel,
        {"text": "secondary_group", "bounds": "[108,2060][264,2113]"},
        {"text": "source group", "bounds": "[950,990][1165,1067]"},
        {"text": "Lights", "bounds": "[0,0][4,4]"},
    ]
    configured_group_page = [
        detail_panel,
        {
            "resource-id": "app:id/setup_navigation_controller_detail_panel",
            "bounds": "[0,0][900,1900]",
        },
        {"text": "secondary_group", "bounds": "[108,2060][264,2113]"},
        {"text": "secondary_group", "bounds": "[950,990][1165,1067]"},
        {"clickable": "true", "bounds": "[950,1110][1085,1218]"},
        {"text": "Lights", "bounds": "[1040,1139][1058,1188]"},
    ]
    dumps = iter(
        [
            [group_box],
            stale_group_page,
            configured_group_page,
            [{"text": "Lights", "bounds": "[10,10][20,20]"}],
            [{"text": "Select lights"}],
            [{"text": "private label"}],
        ]
    )
    taps: list[runner.Control] = []

    control = runner.resolve_bound_device_control(
        binding,
        dump_hierarchy=lambda: next(dumps),
        tap_control=taps.append,
        swipe_scrollable=lambda control: None,
    )

    assert control == {"text": "private label"}
    assert taps == [
        group_box,
        {"clickable": "true", "bounds": "[950,1110][1085,1218]"},
    ]


def test_group_transition_rejects_missing_or_ambiguous_detail_proofs() -> None:
    """One exact right panel and in-panel group heading must prove a group."""
    binding = runner.TargetBinding(
        "non-tile-matrix",
        "private",
        "d073d5000002",
        "private label",
        True,
        True,
        "group",
    )
    detail_panel = {
        "resource-id": "app:id/detail_panel",
        "bounds": "[950,900][1755,1900]",
    }
    heading = {"text": "group", "bounds": "[950,990][1165,1067]"}

    for controls in (
        [],
        [detail_panel, detail_panel],
        [detail_panel],
        [detail_panel, heading, heading],
    ):
        with pytest.raises(runner.SemanticLookupError):
            runner._configured_group_page_controls(binding, controls)


@pytest.mark.parametrize(
    "select_surface", [[], [{"text": "Select lights"}, {"text": "Select lights"}]]
)
def test_group_transition_requires_unique_select_lights(
    select_surface: list[runner.Control],
) -> None:
    """A stale or ambiguous Lights transition cannot enter the target list."""
    binding = runner.TargetBinding(
        "non-tile-matrix",
        "private",
        "d073d5000002",
        "private label",
        True,
        True,
        "group",
    )
    group_box = {"resource-id": "app:id/ax_device_list_group_card_button_group"}
    group_page = [
        {"resource-id": "app:id/detail_panel", "bounds": "[950,900][1755,1900]"},
        {"text": "group", "bounds": "[950,990][1165,1067]"},
        {"text": "Lights"},
    ]
    dumps = iter(
        [[group_box], group_page, select_surface, select_surface, select_surface]
    )

    with pytest.raises(runner.SemanticLookupError):
        runner.resolve_bound_device_control(
            binding,
            dump_hierarchy=lambda: next(dumps),
            tap_control=lambda control: None,
            swipe_scrollable=lambda control: None,
        )


def test_group_target_selector_accepts_only_unset_lights_marker() -> None:
    """Only the known zero-selection marker may open a target selector."""
    detail_panel = {
        "resource-id": "app:id/detail_panel",
        "bounds": "[950,900][1755,1900]",
    }
    selector_button = {
        "class": "android.widget.Button",
        "clickable": "true",
        "bounds": "[950,1110][1085,1218]",
    }
    marker = {"text": "Lights", "bounds": "[1040,1139][1058,1188]"}
    unrelated_palette_count = {"text": "2", "bounds": "[1300,1300][1320,1320]"}

    control = runner.resolve_group_target_selector(
        [detail_panel, selector_button, marker, unrelated_palette_count]
    )

    assert control == selector_button


@pytest.mark.parametrize("marker_text", ["1", "2"])
def test_group_target_selector_rejects_preselected_count_before_opening(
    marker_text: str,
) -> None:
    """An opaque existing selection cannot be opened and toggled by the runner."""
    controls: list[runner.Control] = [
        {"resource-id": "app:id/detail_panel", "bounds": "[950,900][1755,1900]"},
        {"clickable": "true", "bounds": "[950,1110][1085,1218]"},
        {"text": marker_text, "bounds": "[1040,1139][1058,1188]"},
    ]

    with pytest.raises(runner.SemanticLookupError):
        runner.resolve_group_target_selector(controls)


@pytest.mark.parametrize(
    "controls",
    [
        [
            {"resource-id": "app:id/detail_panel", "bounds": "[950,900][1755,1900]"},
            {"clickable": "true", "bounds": "[950,1110][1085,1218]"},
            {"text": "0", "bounds": "[1040,1139][1058,1188]"},
        ],
        [
            {"resource-id": "app:id/detail_panel", "bounds": "[950,900][1755,1900]"},
            {"clickable": "true", "bounds": "[950,1110][1085,1218]"},
        ],
        [
            {"resource-id": "app:id/detail_panel", "bounds": "[950,900][1755,1900]"},
            {"clickable": "true", "bounds": "[950,1110][1085,1218]"},
            {"text": "1", "bounds": "[1040,2060][1058,2088]"},
        ],
        [
            {"resource-id": "app:id/detail_panel", "bounds": "[950,900][1755,1900]"},
            {"clickable": "true", "bounds": "[950,1110][1085,1218]"},
            {"clickable": "true", "bounds": "[950,1110][1085,1218]"},
            {"text": "1", "bounds": "[1040,1139][1058,1188]"},
        ],
        [
            {"resource-id": "app:id/detail_panel", "bounds": "[950,900][1755,1900]"},
            {"clickable": "true", "bounds": "[950,1110][1085,1218]"},
            {"text": "Lights", "bounds": "[1040,1139][1058,1188]"},
            {"clickable": "true", "bounds": "[1200,1110][1335,1218]"},
            {"text": "Lights", "bounds": "[1240,1139][1258,1188]"},
        ],
    ],
)
def test_group_target_selector_fails_closed_for_invalid_association(
    controls: list[runner.Control],
) -> None:
    """Zero, missing or ambiguous selector associations cannot open the target list."""
    with pytest.raises(runner.SemanticLookupError):
        runner.resolve_group_target_selector(controls)


def test_preflight_stops_when_selector_persists_after_exact_close() -> None:
    """A selector that survives its one validated close tap fails without Back."""
    binding = runner.TargetBinding(
        "source-tile", "private", "d073d5000001", "private label", True, True, "group"
    )
    group_card = {"resource-id": "app:id/ax_device_list_group_card_button_group"}
    group_page = [
        {"resource-id": "app:id/detail_panel", "bounds": "[950,900][1755,1900]"},
        {"text": "group", "bounds": "[950,990][1165,1067]"},
        {"clickable": "true", "bounds": "[950,1110][1085,1218]"},
        {"text": "Lights", "bounds": "[1040,1139][1058,1188]"},
    ]
    selector = [{"text": "Select lights", "bounds": "[950,1200][1300,1260]"}]
    target = {"text": "private label", "bounds": "[1040,1400][1200,1450]"}
    selected_selector = [
        {"resource-id": "app:id/detail_panel", "bounds": "[950,900][1755,1900]"},
        {"text": "group", "bounds": "[950,990][1165,1067]"},
        {"clickable": "true", "bounds": "[950,1110][1085,1218]"},
        {"text": "1", "bounds": "[1040,1139][1058,1188]"},
        *selector,
        {
            "resource-id": "app:id/ax_device_control_close_button",
            "clickable": "true",
            "bounds": "[936,857][1044,965]",
        },
    ]
    dumps = iter(
        [
            [group_card],
            [group_card],
            group_page,
            selector,
            [target],
            *[selected_selector] * 4,
        ]
    )
    taps: list[runner.Control] = []

    with pytest.raises(runner.SemanticLookupError):
        runner.preflight_app_reconnaissance(
            {binding.role: binding},
            {},
            max_theme_scrolls=0,
            open_home=lambda: None,
            dump_hierarchy=lambda: next(dumps),
            tap_control=taps.append,
            return_to_morph=lambda: None,
            swipe=lambda: None,
            swipe_device_list=lambda control: None,
        )

    assert [control for control in taps if control.get("text") == "private label"] == [
        target
    ]
    assert [
        control
        for control in taps
        if control.get("resource-id", "").endswith("ax_device_control_close_button")
    ] == [selected_selector[-1]]
    assert all("back" not in runner._text(control).casefold() for control in taps)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda controls: controls.pop(),
        lambda controls: controls.__setitem__(
            5,
            {
                "resource-id": "app:id/ax_device_control_other_button",
                "clickable": "true",
                "bounds": "[936,857][1044,965]",
            },
        ),
        lambda controls: controls.append(dict(controls[-1])),
        lambda controls: controls.__setitem__(
            3, {"text": "2", "bounds": "[1040,1139][1058,1188]"}
        ),
        lambda controls: controls.__setitem__(
            5,
            {
                "resource-id": "app:id/ax_device_control_close_button",
                "clickable": "true",
                "bounds": "[950,1300][1044,1400]",
            },
        ),
    ],
)
def test_selected_target_close_requires_one_exact_control_above_selector(
    mutate: Callable[[list[runner.Control]], None],
) -> None:
    """Only the unique validated close control may dismiss a selected target list."""
    binding = runner.TargetBinding(
        "source-tile", "private", "d073d5000001", "private label", True, True, "group"
    )
    controls: list[runner.Control] = [
        {"resource-id": "app:id/detail_panel", "bounds": "[950,900][1755,1900]"},
        {"text": "group", "bounds": "[950,990][1165,1067]"},
        {"clickable": "true", "bounds": "[950,1110][1085,1218]"},
        {"text": "1", "bounds": "[1040,1139][1058,1188]"},
        {"text": "Select lights", "bounds": "[950,1200][1300,1260]"},
        {
            "resource-id": "app:id/ax_device_control_close_button",
            "clickable": "true",
            "bounds": "[936,857][1044,965]",
        },
    ]

    assert (
        runner.resolve_selected_target_selector_close(binding, controls) == controls[-1]
    )
    mutate(controls)

    with pytest.raises(runner.SemanticLookupError):
        runner.resolve_selected_target_selector_close(binding, controls)


def test_post_target_transition_rejects_duplicate_selector_labels() -> None:
    """Duplicate raw selector labels cannot choose a close or direct FX path."""
    binding = runner.TargetBinding(
        "source-tile", "private", "d073d5000001", "private label", True, True, "group"
    )
    controls: list[runner.Control] = [
        {"resource-id": "app:id/detail_panel", "bounds": "[950,900][1755,1900]"},
        {"text": "group", "bounds": "[950,990][1165,1067]"},
        {"clickable": "true", "bounds": "[950,1110][1085,1218]"},
        {"text": "1", "bounds": "[1040,1139][1058,1188]"},
        {"text": "Select lights", "bounds": "[950,1200][1300,1260]"},
        {"text": "Select lights", "bounds": "[950,1260][1300,1320]"},
    ]

    with pytest.raises(runner.SemanticLookupError):
        runner.resolve_post_target_selection_transition(binding, controls)


def test_semantic_cycle_rejects_preselected_target_before_selector_tap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A scheduled app cycle cannot open an opaque preselected target list."""
    binding = runner.TargetBinding(
        "source-tile", "private", "d073d5000001", "private label", True, True, "group"
    )
    group_card = {
        "resource-id": "app:id/ax_device_list_group_card_button_group",
        "bounds": "[0,0][10,10]",
    }
    preselected_group_page = [
        {"resource-id": "app:id/detail_panel", "bounds": "[950,900][1755,1900]"},
        {"text": "group", "bounds": "[950,990][1165,1067]"},
        {"clickable": "true", "bounds": "[950,1110][1085,1218]"},
        {"text": "1", "bounds": "[1040,1139][1058,1188]"},
    ]
    dumps = iter([[group_card], [group_card], preselected_group_page])
    commands: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        runner,
        "dump_ui_hierarchy",
        lambda *args, **kwargs: next(dumps, preselected_group_page),
    )
    monkeypatch.setattr(
        runner, "adb", lambda *args, **kwargs: commands.append(tuple(args)) or ""
    )

    with pytest.raises(runner.SemanticLookupError):
        asyncio.run(
            runner.semantic_app_save(
                binding,
                ThemeSpec("cheerful", "Cheerful", "Moods", [], "hash"),
                settings=RunnerSettings(),
                run_directory=tmp_path,
                attested_role="source-tile",
                open_home=lambda: None,
            )
        )

    taps = [command for command in commands if command[:3] == ("shell", "input", "tap")]
    assert taps == []
    assert not any("back" in command or "close" in command for command in commands)


def test_selected_group_control_surface_uses_count_one_and_fx_without_label() -> None:
    """After selection, Android proves the group surface rather than device detail."""
    binding = runner.TargetBinding(
        "source-tile", "private", "d073d5000001", "private label", True, True, "group"
    )
    controls = [
        {"resource-id": "app:id/detail_panel", "bounds": "[950,900][1755,1900]"},
        {"text": "group", "bounds": "[950,990][1165,1067]"},
        {"clickable": "true", "bounds": "[950,1110][1085,1218]"},
        {"text": "1", "bounds": "[1040,1139][1058,1188]"},
        {
            "resource-id": "app:id/ax_device_control_effects_tab",
            "bounds": "[1000,1900][1100,1950]",
        },
    ]

    assert runner.resolve_selected_group_fx_control(binding, controls) == controls[-1]


@pytest.mark.parametrize(
    "mutate",
    [
        lambda controls: controls.__setitem__(
            3, {"text": "Lights", "bounds": "[1040,1139][1058,1188]"}
        ),
        lambda controls: controls.__setitem__(
            3, {"text": "2", "bounds": "[1040,1139][1058,1188]"}
        ),
        lambda controls: controls.__setitem__(
            1, {"text": "other", "bounds": "[950,990][1165,1067]"}
        ),
        lambda controls: controls.pop(),
    ],
)
def test_selected_group_control_surface_fails_closed_without_count_one_or_fx(
    mutate: Callable[[list[runner.Control]], None],
) -> None:
    """Lights, other counts, wrong group or missing FX cannot prove selection."""
    binding = runner.TargetBinding(
        "source-tile", "private", "d073d5000001", "private label", True, True, "group"
    )
    controls: list[runner.Control] = [
        {"resource-id": "app:id/detail_panel", "bounds": "[950,900][1755,1900]"},
        {"text": "group", "bounds": "[950,990][1165,1067]"},
        {"clickable": "true", "bounds": "[950,1110][1085,1218]"},
        {"text": "1", "bounds": "[1040,1139][1058,1188]"},
        {"resource-id": "app:id/ax_device_control_effects_tab"},
    ]
    mutate(controls)

    with pytest.raises(runner.SemanticLookupError):
        runner.resolve_selected_group_fx_control(binding, controls)


def test_group_lights_scrolls_only_one_current_device_list_until_label_is_visible() -> (
    None
):
    """The group page scrolls its bound list, never a global or remembered surface."""
    binding = runner.TargetBinding(
        "non-tile-matrix",
        "private",
        "d073d5000002",
        "private label",
        True,
        True,
        "group",
    )
    group_box = {
        "resource-id": "app:id/ax_device_list_group_card_button_group",
        "bounds": "[0,0][4,4]",
    }
    selector_button = {"clickable": "true", "bounds": "[950,1110][1085,1218]"}
    lights = {"text": "Lights", "bounds": "[1040,1139][1058,1188]"}
    scroll_view = {
        "class": "android.widget.ScrollView",
        "scrollable": "true",
        "bounds": "[950,1331][1755,1862]",
    }
    dumps = iter(
        [
            [group_box],
            [
                {
                    "resource-id": "app:id/detail_panel",
                    "bounds": "[950,900][1755,1900]",
                },
                {"text": "group", "bounds": "[108,2060][264,2113]"},
                {"text": "group", "bounds": "[950,990][1165,1067]"},
                {"content-desc": "Lights"},
                selector_button,
                lights,
            ],
            [{"text": "Select lights"}],
            [scroll_view, {"text": "other device"}],
            [scroll_view, {"text": "private label"}],
        ]
    )
    taps: list[runner.Control] = []
    swipes: list[runner.Control] = []

    control = runner.resolve_bound_device_control(
        binding,
        dump_hierarchy=lambda: next(dumps),
        tap_control=taps.append,
        swipe_scrollable=swipes.append,
        max_group_device_scrolls=1,
    )

    assert control == {"text": "private label"}
    assert taps == [group_box, selector_button]
    assert swipes == [scroll_view]


@pytest.mark.parametrize(
    ("first_surface", "second_surface"),
    [
        ([], []),
        ([{"text": "private label"}, {"text": "private label"}], []),
        (
            [
                {
                    "class": "android.widget.ScrollView",
                    "scrollable": "true",
                },
                {
                    "class": "android.widget.ScrollView",
                    "scrollable": "true",
                },
            ],
            [],
        ),
        (
            [
                {
                    "class": "android.widget.ScrollView",
                    "scrollable": "true",
                    "bounds": "[0,0][4,4]",
                }
            ],
            [
                {
                    "class": "android.widget.ScrollView",
                    "scrollable": "true",
                    "bounds": "[0,0][4,4]",
                }
            ],
        ),
    ],
)
def test_group_lights_scroll_fails_closed_for_invalid_or_stale_surfaces(
    first_surface: list[runner.Control], second_surface: list[runner.Control]
) -> None:
    """No target is inferred when the unique device-list scroll cannot progress."""
    binding = runner.TargetBinding(
        "non-tile-matrix",
        "private",
        "d073d5000002",
        "private label",
        True,
        True,
        "group",
    )
    group_box = {"resource-id": "app:id/ax_device_list_group_card_button_group"}
    dumps = iter(
        [
            [group_box],
            [
                {
                    "resource-id": "app:id/detail_panel",
                    "bounds": "[950,900][1755,1900]",
                },
                {"text": "group", "bounds": "[950,990][1165,1067]"},
                {"clickable": "true", "bounds": "[950,1110][1085,1218]"},
                {"text": "Lights", "bounds": "[1040,1139][1058,1188]"},
            ],
            [{"text": "Select lights"}],
            first_surface,
            second_surface,
        ]
    )

    with pytest.raises(runner.SemanticLookupError):
        runner.resolve_bound_device_control(
            binding,
            dump_hierarchy=lambda: next(dumps),
            tap_control=lambda control: None,
            swipe_scrollable=lambda control: None,
            max_group_device_scrolls=1,
        )


@pytest.mark.parametrize("bounds", ["", "[0,0][1,1]"])
def test_group_device_scroll_swipe_requires_safe_current_bounds(bounds: str) -> None:
    """Malformed or too-small list bounds cannot generate an arbitrary gesture."""
    with pytest.raises(runner.SemanticLookupError):
        runner._scrollable_swipe_points({"bounds": bounds})

    with pytest.raises(runner.SemanticLookupError):
        runner.scroll_to_bound_device_control(
            "private label",
            dump_hierarchy=lambda: [],
            swipe_scrollable=lambda control: None,
            max_group_device_scrolls=-1,
        )


def test_adb_allows_only_successful_pull_progress_on_stderr(tmp_path: Path) -> None:
    """Routine pull progress is harmless; every other stderr remains fail-closed."""

    def runner(*args: object, **kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(returncode=1, stdout="", stderr="tablet-serial failed")

    with pytest.raises(AdbCommandError) as failure:
        adb("shell", "echo", "private-label", run=runner)

    assert "private-label" not in str(failure.value)
    assert "tablet-serial" not in str(failure.value)

    def successful_pull(*args: object, **kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(returncode=0, stdout="", stderr="92 bytes pulled")

    assert (
        adb(
            "pull", "/sdcard/private", str(tmp_path / "pulled.xml"), run=successful_pull
        )
        == ""
    )

    with pytest.raises(AdbCommandError) as stderr_failure:
        adb(
            "shell",
            "echo",
            "private-label",
            run=lambda *args, **kwargs: SimpleNamespace(
                returncode=0, stdout="", stderr="tablet-serial warning"
            ),
        )

    assert "tablet-serial" not in str(stderr_failure.value)


def test_stable_palette_needs_two_consecutive_theme_comparisons() -> None:
    """One transitional read never completes a MORPH operation."""
    reads = iter(
        [
            [colour(0)],
            [colour(120), colour(0)],
            [colour(0), colour(120)],
        ]
    )

    result = asyncio.run(
        poll_stable_palette(
            read_palette=lambda: next(reads),
            timeout=1.0,
            poll_interval=0.0,
        )
    )

    assert result.stable_palette == [colour(0), colour(120)]
    assert len(result.observations) == 3


def test_tracer_drives_app_save_then_library_morph_and_restores() -> None:
    """The injected orchestration follows the complete production order."""
    expected = Theme([colour(0), colour(120)])
    spec = ThemeSpec("cheerful", "Cheerful", "Moods", expected.colors, "digest")
    events: list[str] = []
    palettes = iter(
        [
            expected.colors,
            list(reversed(expected.colors)),
            expected.colors,
            list(reversed(expected.colors)),
        ]
    )

    class Device:
        async def get_effect(self) -> object:
            events.append("read")
            return type("Effect", (), {"palette": next(palettes)})()

        async def set_effect(self, **kwargs: object) -> None:
            assert kwargs["palette"] == expected.colors
            events.append("library-morph")

    async def app_save() -> None:
        events.extend(
            [
                "home",
                "device",
                "device-surface",
                "morph",
                "morph-surface",
                "category",
                "theme",
                "save",
            ]
        )

    async def restore() -> bool:
        events.append("restore")
        return True

    result = asyncio.run(
        run_tracer_cycle(
            device=Device(),
            theme_spec=spec,
            app_save=app_save,
            restore=restore,
            settings=RunnerSettings(poll_interval=0.0),
            device_role="source-tile",
        )
    )

    assert isinstance(result, CycleResult)
    assert result.matches_expected
    assert events == [
        "home",
        "device",
        "device-surface",
        "morph",
        "morph-surface",
        "category",
        "theme",
        "save",
        "read",
        "read",
        "library-morph",
        "read",
        "read",
        "restore",
    ]
    assert OFFICIAL_THEME_SLUGS == ("cheerful", "mondrian")


def approved_targets() -> dict[str, object]:
    """Return the smallest private schema that authorises no more than two roles."""
    binding = {
        "host": "192.0.2.1",
        "serial": "d073d5000001",
        "app_label": "private label",
        "app_group": "test group",
        "indoor_confirmed": True,
        "quiesced_confirmed": True,
    }
    return {
        "schema_version": 1,
        "source-tile": binding,
        "non-tile-matrix": {**binding, "serial": "d073d5000002"},
    }


def write_targets(path: Path, document: dict[str, object]) -> None:
    """Create a mode-0600 temporary operator target file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document), encoding="utf-8")
    os.chmod(path, 0o600)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda document: document.update({"extra-role": {}}),
        lambda document: document["source-tile"].update({"indoor_confirmed": False}),  # type: ignore[index]
        lambda document: document["source-tile"].update({"serial": "invalid"}),  # type: ignore[index]
        lambda document: document["source-tile"].pop("app_group"),  # type: ignore[index]
        lambda document: document.update({"reset_palette": []}),
    ],
)
def test_target_preflight_rejects_permissive_or_invalid_private_schema(
    tmp_path: Path, mutate: Callable[[dict[str, object]], None]
) -> None:
    """Bad targets fail before any ADB or LAN adapter is reachable."""
    document = approved_targets()
    mutate(document)
    private_root = tmp_path / "private"
    target_path = private_root / "targets.json"
    write_targets(target_path, document)

    with pytest.raises(Exception) as failure:
        load_target_bindings(target_path, private_root=private_root)

    assert "192.0.2.1" not in str(failure.value)
    assert private_root.stat().st_mode & 0o777 == 0o700


def test_target_schema_accepts_only_two_approved_roles_with_restrictive_modes(
    tmp_path: Path,
) -> None:
    """The local input and all generated private directories remain non-public."""
    private_root = tmp_path / "private"
    target_path = private_root / "targets.json"
    write_targets(target_path, approved_targets())

    bindings = load_target_bindings(target_path, private_root=private_root)

    assert set(bindings) == {"source-tile", "non-tile-matrix"}
    assert target_path.stat().st_mode & 0o777 == 0o600
    assert private_root.stat().st_mode & 0o777 == 0o700


def test_private_path_boundary_rejects_escapes_and_symlinks_before_access(
    tmp_path: Path,
) -> None:
    """Only the direct designated targets file may enter the private boundary."""
    root = tmp_path / "phase-08"
    targets = root / "targets.json"
    boundary = runner.PrivatePathBoundary(root, targets)
    canonical = runner.resolve_private_path_boundary(None, injected_boundary=boundary)
    assert canonical == runner.PrivatePathBoundary(root, targets)

    with pytest.raises(runner.PreflightError):
        runner.resolve_private_path_boundary(
            None,
            injected_boundary=runner.PrivatePathBoundary(root, root / "other.json"),
        )
    with pytest.raises(runner.PreflightError):
        runner.resolve_private_path_boundary(
            None,
            injected_boundary=runner.PrivatePathBoundary(
                root, root / ".." / "targets.json"
            ),
        )

    root.mkdir()
    outside = tmp_path / "outside.json"
    write_targets(outside, approved_targets())
    targets.symlink_to(outside)
    with pytest.raises(runner.PreflightError):
        runner.resolve_private_path_boundary(None, injected_boundary=boundary)

    symlink_root = tmp_path / "symlink-root"
    symlink_root.symlink_to(root, target_is_directory=True)
    with pytest.raises(runner.PreflightError):
        runner.resolve_private_path_boundary(
            None,
            injected_boundary=runner.PrivatePathBoundary(
                symlink_root, symlink_root / "targets.json"
            ),
        )


def test_private_cli_path_overrides_are_not_a_production_escape(tmp_path: Path) -> None:
    """The test-only boundary is deliberately absent from the CLI grammar."""
    with pytest.raises(SystemExit):
        runner.build_parser().parse_args(["--private-root", str(tmp_path / "other")])
    with pytest.raises(runner.PreflightError):
        runner.resolve_private_path_boundary(
            Path("targets.json"),
            injected_boundary=runner.PrivatePathBoundary(
                tmp_path / "phase-08-test",
                tmp_path / "phase-08-test" / "targets.json",
            ),
        )


def test_private_boundary_defensive_failures_and_target_load_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Unavailable, non-regular, and alternate private paths fail before use."""
    root = tmp_path / "root"
    target = root / "targets.json"
    boundary = runner.PrivatePathBoundary(root, target)

    def unavailable(self: Path, *, strict: bool = False) -> Path:
        raise OSError("unavailable")

    monkeypatch.setattr(Path, "resolve", unavailable)
    with pytest.raises(runner.PreflightError):
        runner.resolve_private_path_boundary(None, injected_boundary=boundary)
    monkeypatch.undo()

    root.write_text("not a directory")
    with pytest.raises(runner.PreflightError):
        runner.resolve_private_path_boundary(None, injected_boundary=boundary)
    root.unlink()
    root.mkdir()
    target.mkdir()
    with pytest.raises(runner.PreflightError):
        runner.resolve_private_path_boundary(None, injected_boundary=boundary)
    target.rmdir()
    write_targets(target, approved_targets())

    original_lstat = Path.lstat

    def unavailable_lstat(self: Path) -> os.stat_result:
        if self == target:
            raise OSError("unavailable")
        return original_lstat(self)

    monkeypatch.setattr(Path, "lstat", unavailable_lstat)
    with pytest.raises(runner.PreflightError):
        runner.resolve_private_path_boundary(None, injected_boundary=boundary)
    monkeypatch.undo()

    original_resolve = Path.resolve

    def unavailable_target_resolve(self: Path, *, strict: bool = False) -> Path:
        if self == target:
            raise OSError("unavailable")
        return original_resolve(self, strict=strict)

    monkeypatch.setattr(Path, "resolve", unavailable_target_resolve)
    with pytest.raises(runner.PreflightError):
        runner.resolve_private_path_boundary(None, injected_boundary=boundary)
    monkeypatch.undo()

    with pytest.raises(runner.PreflightError):
        runner.resolve_private_path_boundary(Path("/alternate"))
    monkeypatch.setattr(runner, "production_private_path_boundary", lambda: boundary)
    assert (
        runner.resolve_private_path_boundary(runner.PRIVATE_ROOT / "targets.json")
        == boundary
    )

    with pytest.raises(runner.PreflightError):
        runner.load_target_bindings(
            root / "other.json",
            private_root=root,
            private_paths=boundary,
        )
    target.unlink()
    with pytest.raises(runner.PreflightError):
        runner.load_target_bindings(target, private_root=root, private_paths=boundary)
    target.write_text("not-json")
    with pytest.raises(runner.PreflightError):
        runner.load_target_bindings(target, private_root=root, private_paths=boundary)
    write_targets(target, {**approved_targets(), "schema_version": 2})
    with pytest.raises(runner.PreflightError):
        runner.load_target_bindings(target, private_root=root, private_paths=boundary)
    invalid_host = approved_targets()
    invalid_host["source-tile"]["host"] = ""  # type: ignore[index]
    write_targets(target, invalid_host)
    with pytest.raises(runner.PreflightError):
        runner.load_target_bindings(target, private_root=root, private_paths=boundary)


def test_live_provenance_requires_all_observed_dimensions() -> None:
    """No missing live app, surface, binding, or firmware value becomes a checkpoint."""
    bindings, specs, _provenance = _lifecycle_inputs()
    valid = runner.PreflightReport(
        "4.96.0",
        "catalogue",
        {
            "source-tile": {"firmware": "3.50"},
            "non-tile-matrix": {"firmware": "4.0"},
        },
    )
    assert runner.build_live_provenance(
        runner_revision="phase-08",
        preflight=valid,
        bindings=bindings,
        theme_specs=specs,
        settings=runner.RunnerSettings(),
    ).firmware_by_role == {"source-tile": "3.50", "non-tile-matrix": "4.0"}
    for report, candidate_bindings in (
        (dataclasses.replace(valid, app_version=""), bindings),
        (dataclasses.replace(valid, catalogue_fingerprint=""), bindings),
        (valid, {"source-tile": bindings["source-tile"]}),
        (
            dataclasses.replace(
                valid,
                metadata_by_role={
                    "source-tile": {"firmware": "unknown"},
                    "non-tile-matrix": {"firmware": "4.0"},
                },
            ),
            bindings,
        ),
    ):
        with pytest.raises(runner.PreflightError):
            runner.build_live_provenance(
                runner_revision="phase-08",
                preflight=report,
                bindings=candidate_bindings,
                theme_specs=specs,
                settings=runner.RunnerSettings(),
            )


def test_main_rejects_invalid_private_boundary_and_completed_run_before_hardware(
    tmp_path: Path,
) -> None:
    """Main fails before configuration writes for a bad boundary or finished run."""
    invalid_root = tmp_path / "not-a-directory"
    invalid_root.write_text("file")
    assert (
        asyncio.run(
            runner.main(
                [],
                private_paths=runner.PrivatePathBoundary(
                    invalid_root, invalid_root / "targets.json"
                ),
            )
        )
        == runner.EXIT_INCOMPLETE
    )

    root = tmp_path / "runs"
    targets = root / "targets.json"
    write_targets(targets, approved_targets())
    specs = runner.load_theme_specs()
    completed = [
        runner.CycleResult(*key, [], [colour(index)], True, None)
        for index, key in enumerate(runner.build_cycle_schedule())
    ]
    runner.write_checkpoint(
        root / CANONICAL_RUN_ID / "checkpoint.json",
        runner.RunCheckpoint(
            CANONICAL_RUN_ID,
            runner.build_provenance(
                runner_revision="phase-08",
                app_version="version",
                catalogue="catalogue",
                target_fingerprints={},
                firmware_by_role={},
                theme_specs=specs,
                settings=runner.RunnerSettings(),
            ),
            None,
            completed,
            None,
            False,
        ),
    )
    assert (
        asyncio.run(
            runner.main(["--resume", CANONICAL_RUN_ID, "--private-root", str(root)])
        )
        == runner.EXIT_INCOMPLETE
    )


@pytest.mark.parametrize(
    "adb_devices",
    [
        "List of devices attached\n",
        "List of devices attached\na\tdevice\nb\tdevice\n",
        "List of devices attached\na\toffline\n",
    ],
)
def test_preflight_rejects_ambiguous_or_unauthorised_adb_states(
    adb_devices: str,
) -> None:
    """Only one authorised, fully connected Android tablet is accepted."""
    from uat_theme_fidelity import require_one_authorised_adb_device

    def runner(*args: object, **kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(returncode=0, stdout=adb_devices, stderr="")

    with pytest.raises(Exception) as failure:
        require_one_authorised_adb_device(timeout=1.0, run=runner)

    assert "\ta" not in str(failure.value)


def test_keep_awake_restores_exact_prior_value_after_failure() -> None:
    """The Android global setting is restored in the outermost finally."""
    commands: list[tuple[str, ...]] = []

    def runner(*args: object, **kwargs: object) -> SimpleNamespace:
        command = tuple(args[0])  # type: ignore[index]
        commands.append(command)
        stdout = "3\n" if command[-1] == "stay_on_while_plugged_in" else ""
        return SimpleNamespace(returncode=0, stdout=stdout, stderr="")

    async def fail() -> None:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        asyncio.run(with_android_keep_awake(fail, timeout=1.0, run=runner))

    assert commands == [
        ("adb", "shell", "settings", "get", "global", "stay_on_while_plugged_in"),
        ("adb", "shell", "settings", "put", "global", "stay_on_while_plugged_in", "7"),
        ("adb", "shell", "settings", "put", "global", "stay_on_while_plugged_in", "3"),
        ("adb", "shell", "settings", "get", "global", "stay_on_while_plugged_in"),
    ]


def test_private_diagnostics_are_mode_0600_and_progress_is_redacted(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Failure artefacts remain local and identifiers never reach console output."""
    diagnostics = write_diagnostics(
        tmp_path,
        screenshot=b"image",
        hierarchy="private label and tablet serial",
        role="source-tile",
    )

    captured = capsys.readouterr()
    assert all(path.stat().st_mode & 0o777 == 0o600 for path in diagnostics)
    assert "private label" not in captured.err
    assert "tablet serial" not in captured.err


def test_parser_has_only_locked_plan_01_flags_and_distinct_exit_codes() -> None:
    """No CLI option can select an arbitrary device, theme, or fleet scan."""
    parser = build_parser()
    help_text = parser.format_help()

    for flag in (
        "--targets",
        "--ui-wait-timeout",
        "--operator-action-timeout",
        "--stability-timeout",
        "--poll-interval",
        "--max-theme-scrolls",
        "--preflight-only",
        "--attest-initial-theme",
    ):
        assert flag in help_text
    assert "--host" not in help_text
    assert "--serial" not in help_text
    assert "--theme" not in help_text
    assert parser.parse_args([]).operator_action_timeout == 300.0
    assert (
        len({EXIT_PASS, EXIT_MISMATCH, EXIT_INCOMPLETE, EXIT_RESTORATION_FAILURE}) == 4
    )


def test_main_rejects_an_invalid_operator_action_timeout_before_preflight() -> None:
    """A negative human-action deadline cannot reach private targets or hardware."""
    assert (
        asyncio.run(runner.main(["--operator-action-timeout", "-1"]))
        == runner.EXIT_INCOMPLETE
    )


def test_schedule_has_the_locked_24_cycle_order() -> None:
    """App saves alternate away from Cheerful before grouped library checks."""
    from uat_theme_fidelity import build_cycle_schedule

    schedule = build_cycle_schedule()

    assert len(schedule) == 24
    assert len(set(schedule)) == 24
    source_app = [
        ("source-tile", "mondrian", "app", 1),
        ("source-tile", "cheerful", "app", 1),
        ("source-tile", "mondrian", "app", 2),
        ("source-tile", "cheerful", "app", 2),
        ("source-tile", "mondrian", "app", 3),
        ("source-tile", "cheerful", "app", 3),
    ]
    assert schedule[:6] == source_app
    assert schedule[6:12] == [
        ("source-tile", "cheerful", "library", 1),
        ("source-tile", "cheerful", "library", 2),
        ("source-tile", "cheerful", "library", 3),
        ("source-tile", "mondrian", "library", 1),
        ("source-tile", "mondrian", "library", 2),
        ("source-tile", "mondrian", "library", 3),
    ]
    assert [key[1] for key in source_app] == [
        "mondrian",
        "cheerful",
        "mondrian",
        "cheerful",
        "mondrian",
        "cheerful",
    ]
    for role in ("source-tile", "non-tile-matrix"):
        for slug in runner.OFFICIAL_THEME_SLUGS:
            assert sum(key[:3] == (role, slug, "app") for key in schedule) == 3
            assert sum(key[:3] == (role, slug, "library") for key in schedule) == 3
    old_grouped = {
        ("source-tile", "cheerful", "app", index): runner.CycleResult(
            "source-tile", "cheerful", "app", index, [], [], True, None
        )
        for index in (1, 2, 3)
    }
    with pytest.raises(runner.PreflightError):
        runner._validate_completed_cycle_prefix(old_grouped)
    with pytest.raises(runner.PreflightError):
        runner._validate_completed_cycle_prefix(
            {
                schedule[0]: runner.CycleResult(
                    "source-tile", "mondrian", "app", 2, [], [], True, None
                )
            }
        )
    assert schedule[-1] == ("non-tile-matrix", "mondrian", "library", 3)


def test_resume_rejects_every_provenance_change_without_mutation() -> None:
    """A resume may continue only the same frozen experiment."""
    from uat_theme_fidelity import RunProvenance, validate_resume

    provenance = RunProvenance(
        runner_revision="one",
        app_version="two",
        catalogue_fingerprint="three",
        target_fingerprints={"source-tile": "four"},
        firmware_by_role={"source-tile": "five"},
        theme_records_sha256="six",
        schedule_sha256="seven",
        effective_settings={"timeout": 1},
    )
    assert validate_resume(provenance, provenance) == 0
    changed = RunProvenance(**{**provenance.__dict__, "app_version": "changed"})
    with pytest.raises(Exception, match="provenance"):
        validate_resume(provenance, changed)


@pytest.mark.parametrize(
    "metadata",
    [
        {"product_id": 55, "is_matrix": True, "indoor": True},
        {"product_id": 200, "is_matrix": True, "indoor": False},
        {"product_id": 200, "is_matrix": False, "indoor": True},
        {"product_id": 200, "is_matrix": True, "indoor": True, "emulator": True},
    ],
)
def test_non_tile_preflight_rejects_unsafe_or_wrong_target(
    metadata: dict[str, object],
) -> None:
    """The secondary role rejects Tile, Exterior, emulator and non-matrix targets."""
    from uat_theme_fidelity import validate_non_tile_metadata

    with pytest.raises(Exception):
        validate_non_tile_metadata(metadata)


def test_effect_speed_restore_avoids_the_setter_default_for_off() -> None:
    """A zero-millisecond OFF effect must not use the setter's three-second default."""
    from uat_theme_fidelity import EffectSnapshot, effect_speed_seconds_for_restore

    off = EffectSnapshot(FirmwareEffect.OFF, 0, 0, None, None, 0, 0)
    active = EffectSnapshot(FirmwareEffect.MORPH, 3000, 0, [], None, 0, 0)

    assert effect_speed_seconds_for_restore(active) == 3.0
    zero_speed = effect_speed_seconds_for_restore(off)
    assert zero_speed > 0
    assert round(zero_speed * 1000) == 0
    assert round((zero_speed if zero_speed else 3.0) * 1000) == 0


def test_capture_snapshot_rejects_a_running_or_incomplete_baseline() -> None:
    """No mutation can follow a changing or partially read restoration baseline."""
    from uat_theme_fidelity import capture_snapshot

    class Device:
        async def get_power(self) -> int:
            return 65535

        async def get_color(self) -> tuple[HSBK, int, str]:
            return colour(0), 65535, "private label"

        async def get_effect(self) -> object:
            return SimpleNamespace(
                effect_type=FirmwareEffect.MORPH,
                speed=3000,
                duration=0,
                palette=[],
                sky_type=None,
                cloud_saturation_min=0,
                cloud_saturation_max=0,
            )

        async def get_device_chain(self) -> list[object]:
            return [object()]

        async def get_all_tile_colors(self) -> list[list[HSBK]]:
            return [[colour(0)]]

    with pytest.raises(Exception, match="static"):
        asyncio.run(capture_snapshot(Device()))


@pytest.mark.parametrize(
    "first_power, second_power, first_colour, second_colour",
    [
        (1, 0, colour(0), colour(0)),
        (1, 1, colour(0), colour(1)),
    ],
)
def test_capture_snapshot_rejects_a_power_or_base_colour_change(
    first_power: int,
    second_power: int,
    first_colour: HSBK,
    second_colour: HSBK,
) -> None:
    """A complete static baseline includes the base colour and reported power."""

    class Device:
        def __init__(self) -> None:
            self.power_reads = iter([first_power, second_power])
            self.colour_reads = iter([first_colour, second_colour])

        async def get_power(self) -> int:
            return next(self.power_reads)

        async def get_color(self) -> tuple[HSBK, int, str]:
            current = next(self.colour_reads)
            return current, first_power, "private label"

        async def get_effect(self) -> object:
            return off_effect()

        async def get_device_chain(self) -> list[object]:
            return [object()]

        async def get_all_tile_colors(self) -> list[list[HSBK]]:
            return [[colour(0)]]

    with pytest.raises(runner.PreflightError, match="stable"):
        asyncio.run(runner.capture_snapshot(Device()))


def test_capture_snapshot_uses_the_current_matrix_device_chain_api() -> None:
    """A real MatrixLight-shaped device needs get_device_chain, not a retired alias."""

    class MatrixDevice:
        async def get_power(self) -> int:
            return 1

        async def get_color(self) -> tuple[HSBK, int, str]:
            return colour(0), 1, "private"

        async def get_effect(self) -> object:
            return off_effect()

        async def get_device_chain(self) -> list[object]:
            return [object()]

        async def get_all_tile_colors(self) -> list[list[HSBK]]:
            return [[colour(0)]]

    class MissingDeviceChain:
        async def get_power(self) -> int:
            return 1

        async def get_color(self) -> tuple[HSBK, int, str]:
            return colour(0), 1, "private"

        async def get_effect(self) -> object:
            return off_effect()

        async def get_all_tile_colors(self) -> list[list[HSBK]]:
            return [[colour(0)]]

    device = MatrixDevice()
    assert not hasattr(device, "get_tile_chain")
    assert asyncio.run(runner.capture_snapshot(device)).chain
    with pytest.raises(runner.PreflightError, match="incomplete"):
        asyncio.run(runner.capture_snapshot(MissingDeviceChain()))


def test_restore_reinstates_effect_pixels_colour_then_power() -> None:
    """The saved OFF effect settles before base colour and exact pixels."""
    from uat_theme_fidelity import (
        EffectSnapshot,
        RestorationSnapshot,
        restore_snapshot,
    )

    events: list[str] = []

    class Device:
        async def set_effect(self, **kwargs: object) -> None:
            events.append("effect")

        async def get_effect(self) -> object:
            return SimpleNamespace(
                effect_type=FirmwareEffect.OFF,
                speed=0,
                duration=0,
                palette=None,
                sky_type=None,
                cloud_saturation_min=0,
                cloud_saturation_max=0,
            )

        async def set_matrix_colors(self, tile_index: int, colors: list[HSBK]) -> None:
            events.append(f"pixels-{tile_index}")

        async def set_color(self, colour_value: HSBK) -> None:
            events.append("colour")

        async def set_power(self, power: int) -> None:
            events.append("power")

    snapshot = RestorationSnapshot(
        power=65535,
        base_colour=colour(0),
        effect=EffectSnapshot(FirmwareEffect.OFF, 0, 0, None, None, 0, 0),
        chain=[object()],
        tile_colours=[[colour(0)]],
        uplight_colour=None,
        downlight_colours=None,
    )

    assert asyncio.run(restore_snapshot(Device(), snapshot, poll_interval=0.0))
    assert events == ["effect", "colour", "pixels-0", "power"]


def test_restoration_comparison_ignores_transient_tile_acceleration_only() -> None:
    """Accelerometer readings are not restorable, unlike Tile topology and pixels."""
    expected = runner.RestorationSnapshot(
        power=1,
        base_colour=colour(0),
        effect=runner.EffectSnapshot(FirmwareEffect.OFF, 0, 0, None, None, 0, 0),
        chain=[
            runner.MatrixTileTopology(
                tile_index=0,
                user_x=0.0,
                user_y=0.0,
                width=8,
                height=8,
            )
        ],
        tile_colours=[[colour(0)]],
        uplight_colour=None,
        downlight_colours=None,
    )
    same_topology = dataclasses.replace(
        expected,
        chain=[
            runner.MatrixTileTopology(
                tile_index=0,
                user_x=0.0,
                user_y=0.0,
                width=8,
                height=8,
            )
        ],
    )
    changed_pixels = dataclasses.replace(expected, tile_colours=[[colour(1)]])
    changed_topology = dataclasses.replace(
        expected,
        chain=[
            runner.MatrixTileTopology(
                tile_index=0,
                user_x=1.0,
                user_y=0.0,
                width=8,
                height=8,
            )
        ],
    )

    assert runner.restoration_snapshots_match(expected, same_topology)
    assert not runner.restoration_snapshots_match(expected, changed_pixels)
    assert not runner.restoration_snapshots_match(expected, changed_topology)


def test_snapshot_topology_projects_only_restorable_tile_geometry() -> None:
    """The live accelerometer is intentionally absent from the restoration snapshot."""
    topology = runner._matrix_tile_topology(
        SimpleNamespace(
            tile_index=0,
            user_x=1,
            user_y=-2,
            width=8,
            height=8,
            accel_meas_x=123,
            accel_meas_y=456,
            accel_meas_z=789,
        )
    )

    assert topology == runner.MatrixTileTopology(0, 1.0, -2.0, 8, 8)


def test_private_snapshot_record_is_audit_only_not_crash_recovery_material() -> None:
    """A process restart must take a fresh snapshot rather than decode repr strings."""
    snapshot = runner.RestorationSnapshot(
        power=1,
        base_colour=colour(0),
        effect=runner.EffectSnapshot(FirmwareEffect.OFF, 0, 0, None, None, 0, 0),
        chain=[
            runner.MatrixTileTopology(
                tile_index=0,
                user_x=0.0,
                user_y=0.0,
                width=8,
                height=8,
            ),
            object(),
        ],
        tile_colours=[[colour(0)]],
        uplight_colour=None,
        downlight_colours=None,
    )

    record = runner._private_snapshot_record(snapshot)

    assert record["snapshot_format"] == "audit-only-v1"
    assert record["restore_from_checkpoint"] is False
    assert record["topology"] == [
        {"tile_index": 0, "user_x": 0.0, "user_y": 0.0, "width": 8, "height": 8},
        None,
    ]
    assert "chain" not in record


def test_restoration_verification_polls_without_repeating_writes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Delayed settling needs bounded full-state reads, never another write."""
    snapshot = runner.RestorationSnapshot(
        0,
        colour(0),
        runner.EffectSnapshot(FirmwareEffect.OFF, 0, 0, None, None, 0, 0),
        [object()],
        [[colour(0)]],
        None,
        None,
    )
    reads = iter([object(), snapshot])
    pauses: list[float] = []

    async def capture(device: object) -> object:
        return next(reads)

    async def sleep(interval: float) -> None:
        pauses.append(interval)

    monkeypatch.setattr(runner, "capture_snapshot", capture)
    monkeypatch.setattr(runner.asyncio, "sleep", sleep)
    assert asyncio.run(
        runner.verify_restoration(object(), snapshot, poll_interval=0.25)
    )
    assert pauses == [0.25]

    async def unavailable(device: object) -> object:
        raise runner.LifxTimeoutError("private")

    monkeypatch.setattr(runner, "capture_snapshot", unavailable)
    assert not asyncio.run(runner.verify_restoration(object(), snapshot))

    pauses.clear()

    eventual_reads = iter([runner.PreflightError("settling"), snapshot])

    async def eventually_settles(device: object) -> object:
        value = next(eventual_reads)
        if isinstance(value, Exception):
            raise value
        return value

    monkeypatch.setattr(runner, "capture_snapshot", eventually_settles)
    assert asyncio.run(runner.verify_restoration(object(), snapshot, poll_interval=0.5))
    assert pauses == [0.5]

    pauses.clear()

    async def never_settles(device: object) -> object:
        return object()

    monkeypatch.setattr(runner, "capture_snapshot", never_settles)
    assert not asyncio.run(
        runner.verify_restoration(object(), snapshot, poll_interval=0.5)
    )
    assert pauses == [0.5, 0.5]


def test_ceiling_determinations_are_mechanical_and_exclude_carlton() -> None:
    """The 25 public rows come only from the shipped source, not a slug fixture."""
    from uat_theme_fidelity import derive_ceiling_determinations

    rows = derive_ceiling_determinations()

    assert len(rows) == 25
    assert [row["slug"] for row in rows] == sorted(row["slug"] for row in rows)
    assert "carlton" not in {row["slug"] for row in rows}
    assert all(row["determination"] == "device-ceiling-unresolvable" for row in rows)


def test_public_validation_rejects_private_identifiers_before_writing() -> None:
    """Evidence is an allowlist projection rather than a redacted private checkpoint."""
    from uat_theme_fidelity import validate_public_results

    with pytest.raises(Exception, match="private"):
        validate_public_results({"host": "192.0.2.1"})


def test_validated_public_evidence_renders_and_writes_as_a_pair(tmp_path: Path) -> None:
    """A complete restored synthetic run renders without hardware or identities."""
    from uat_theme_fidelity import (
        PaletteObservation,
        PublicDeviceRecord,
        RestorationResult,
        RunProvenance,
        build_cycle_schedule,
        build_public_results,
        load_theme_specs,
        render_uat_markdown,
        validate_public_results,
        write_official_evidence,
    )

    specs = load_theme_specs()
    cycles = [
        CycleResult(
            device_role=role,
            theme_slug=slug,
            source=source,
            cycle_index=index,
            observations=[PaletteObservation(0.0, canonical_theme_palette(slug))],
            stable_palette=canonical_theme_palette(slug),
            matches_expected=True,
            failure=None,
        )
        for role, slug, source, index in build_cycle_schedule()
    ]
    provenance = RunProvenance(
        "revision", "version", "catalogue", {}, {}, "themes", "schedule", {}
    )
    results = build_public_results(
        run_id="run-opaque",
        provenance=provenance,
        theme_specs=specs,
        devices=[
            PublicDeviceRecord("source-tile", "MatrixLight", "LIFX Tile", 55, "1.0"),
            PublicDeviceRecord(
                "non-tile-matrix", "CeilingLight", "LIFX Ceiling", 100, "1.0"
            ),
        ],
        cycles=cycles,
        restorations=[
            RestorationResult("source-tile", True, True, True, None),
            RestorationResult("non-tile-matrix", True, True, True, None),
        ],
        outcome="pass",
        completed_at_utc="2026-08-16T00:00:00Z",
    )

    validate_public_results(results)
    markdown = render_uat_markdown(results)
    json_path, markdown_path = write_official_evidence(
        results, output_directory=tmp_path
    )

    assert "Outcome: `pass`" in markdown
    assert json.loads(json_path.read_text())["outcome"] == "pass"
    assert markdown_path.read_text() == markdown


def public_results() -> dict[str, object]:
    """Build a fully valid, deliberately synthetic public record for rejection tests."""
    specs = runner.load_theme_specs()
    cycles = [
        CycleResult(
            device_role=role,
            theme_slug=slug,
            source=source,
            cycle_index=index,
            observations=[
                runner.PaletteObservation(0.0, canonical_theme_palette(slug))
            ],
            stable_palette=canonical_theme_palette(slug),
            matches_expected=True,
            failure=None,
        )
        for role, slug, source, index in runner.build_cycle_schedule()
    ]
    return runner.build_public_results(
        run_id="run-opaque",
        provenance=runner.RunProvenance(
            "revision", "version", "catalogue", {}, {}, "themes", "schedule", {}
        ),
        theme_specs=specs,
        devices=[
            runner.PublicDeviceRecord(
                "source-tile", "MatrixLight", "LIFX Tile", 55, "1.0"
            ),
            runner.PublicDeviceRecord(
                "non-tile-matrix", "CeilingLight", "LIFX Ceiling", 100, "1.0"
            ),
        ],
        cycles=cycles,
        restorations=[
            runner.RestorationResult("source-tile", True, True, True, None),
            runner.RestorationResult("non-tile-matrix", True, True, True, None),
        ],
        outcome="pass",
        completed_at_utc="2026-08-16T00:00:00Z",
    )


@pytest.mark.parametrize(
    "mutate",
    [
        lambda record: record.update({"extra": True}),
        lambda record: record.update({"outcome": "incomplete"}),
        lambda record: record.update({"cycles": record["cycles"][:-1]}),  # type: ignore[index]
        lambda record: record["cycles"].reverse(),  # type: ignore[index]
        lambda record: record.update({"devices": record["devices"][:1]}),  # type: ignore[index]
        lambda record: record.update(
            {
                "devices": [
                    record["devices"][0],  # type: ignore[index]
                    {
                        "role": "non-tile-matrix",
                        "device_class": "Light",
                        "model": "LIFX Candle",
                        "product_id": 55,
                        "host_firmware": "1.0",
                    },
                ]
            }
        ),
        lambda record: record.update({"restorations": []}),
        lambda record: record.update({"ceiling_determinations": []}),
        lambda record: record["themes"][0].update({"token": "".join(())}),  # type: ignore[index]
        lambda record: record.update({"run_id": "serial d073d5000001"}),
    ],
)
def test_public_finalisation_rejects_every_incomplete_or_private_shape(
    mutate: Callable[[dict[str, object]], None],
) -> None:
    """Public evidence is validated before rendering or staging either official file."""
    results = public_results()
    mutate(results)

    with pytest.raises(runner.PreflightError):
        runner.validate_public_results(results)


def test_public_finalisation_keeps_a_restored_mismatch_as_failed_evidence() -> None:
    """A fully measured mismatch is finalisable but never relabelled as pass."""
    results = public_results()
    results["outcome"] = "mismatch"
    cycle = results["cycles"][0]  # type: ignore[index]
    cycle["stable_palette"][0] = cycle["stable_palette"][11]  # type: ignore[index]
    cycle.update({"matches_expected": False, "failure": None})

    runner.validate_public_results(results)
    assert "Outcome: `mismatch`" in runner.render_uat_markdown(results)


@pytest.mark.parametrize("cycle_offset", [0, 9])
def test_public_finalisation_recomputes_app_and_library_multiset_verdicts(
    cycle_offset: int,
) -> None:
    """A forged flag cannot hide one changed duplicate in either cycle source."""
    results = public_results()
    cycle = results["cycles"][cycle_offset]  # type: ignore[index]

    assert cycle["theme_slug"] == "mondrian"
    assert cycle["source"] == ("app" if cycle_offset == 0 else "library")
    cycle["stable_palette"][0] = cycle["stable_palette"][11]  # type: ignore[index]

    with pytest.raises(runner.PreflightError, match="verdict disagrees"):
        runner.validate_public_results(results)

    cycle["matches_expected"] = False
    results["outcome"] = "mismatch"
    runner.validate_public_results(results)


@pytest.mark.parametrize("cycle_offset", [0, 9])
def test_public_finalisation_rejects_false_flag_for_matching_app_or_library_palette(
    cycle_offset: int,
) -> None:
    """A correct palette cannot be forged into a mismatch for either source."""
    results = public_results()
    cycle = results["cycles"][cycle_offset]  # type: ignore[index]

    assert cycle["source"] == ("app" if cycle_offset == 0 else "library")
    cycle["matches_expected"] = False
    results["outcome"] = "mismatch"

    with pytest.raises(runner.PreflightError, match="verdict disagrees"):
        runner.validate_public_results(results)


def test_public_finalisation_rejects_empty_stable_palette() -> None:
    """A stable readback must retain at least one decoded protocol colour."""
    results = public_results()
    results["cycles"][0]["stable_palette"] = []  # type: ignore[index]

    with pytest.raises(runner.PreflightError, match="complete stable palette"):
        runner.validate_public_results(results)


def test_public_cycle_validation_rejects_a_slug_missing_from_locked_themes() -> None:
    """Schedule validation is not the only boundary protecting the library lookup."""
    results = public_results()
    themes = runner._locked_public_themes()
    del themes["mondrian"]

    with pytest.raises(runner.PreflightError, match="theme is unknown"):
        runner._validate_public_cycles(results["cycles"], themes)  # type: ignore[arg-type]


def test_public_finalisation_rejects_missing_committed_library_theme(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The finaliser fails closed if the committed library cannot resolve a slug."""

    def missing_theme(_: str) -> Theme:
        raise KeyError("missing")

    monkeypatch.setattr(runner.ThemeLibrary, "get", staticmethod(missing_theme))

    with pytest.raises(runner.PreflightError, match="library is incomplete"):
        runner.validate_public_results(public_results())


def test_public_finalisation_rejects_library_source_disagreement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The finaliser checks the library palette against its committed source record."""
    monkeypatch.setattr(
        runner.ThemeLibrary,
        "get",
        staticmethod(lambda _: Theme([colour(42)])),
    )

    with pytest.raises(runner.PreflightError, match="library disagrees"):
        runner.validate_public_results(public_results())


@pytest.mark.parametrize(
    ("key", "value", "message"),
    [
        ("schema_version", 2, "identity"),
        ("commands", ["uat_theme_fidelity.py --run"], "commands"),
        ("runner_revision", 1, "root fields"),
    ],
)
def test_public_finalisation_validates_root_constants_and_types(
    key: str, value: object, message: str
) -> None:
    """Untrusted public roots cannot alter phase identity, commands, or field types."""
    results = public_results()
    results[key] = value

    with pytest.raises(runner.PreflightError, match=message):
        runner.validate_public_results(results)


def test_public_finalisation_rejects_theme_metadata_changed_from_source() -> None:
    """Published theme metadata is a source projection, not caller-controlled prose."""
    results = public_results()
    results["themes"][0]["display_name"] = "forged"  # type: ignore[index]

    with pytest.raises(runner.PreflightError, match="theme records changed"):
        runner.validate_public_results(results)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda record: record["cycles"][0].update(  # type: ignore[index]
            {"matches_expected": False}
        ),
        lambda record: record.update({"outcome": "mismatch"}),
        lambda record: record["cycles"][0].update(  # type: ignore[index]
            {"stable_palette": None}
        ),
        lambda record: record["cycles"][0].update(  # type: ignore[index]
            {"stable_palette": [[0, 0, 0, 3500]]}
        ),
        lambda record: record["cycles"][0].update(  # type: ignore[index]
            {"stable_palette": [["bad", 0, 0, 3500]] * 16}
        ),
        lambda record: record["cycles"][0]["stable_palette"][0].__setitem__(  # type: ignore[index]
            0, 65536
        ),
        lambda record: record["cycles"][0].update(  # type: ignore[index]
            {"theme_slug": "unknown-theme"}
        ),
        lambda record: record["cycles"][0].update(  # type: ignore[index]
            {"failure": "forged failure"}
        ),
        lambda record: record["cycles"][0].update(  # type: ignore[index]
            {"cycle_index": True}
        ),
        lambda record: record["cycles"][0].update(  # type: ignore[index]
            {"poll_count": 0}
        ),
        lambda record: record["cycles"][0].update(  # type: ignore[index]
            {"matches_expected": 1}
        ),
        lambda record: record["cycles"][0].update(  # type: ignore[index]
            {"extra": True}
        ),
        lambda record: record["devices"][0].update(  # type: ignore[index]
            {"extra": True}
        ),
        lambda record: record["devices"][0].update(  # type: ignore[index]
            {"host_firmware": 1}
        ),
        lambda record: record["devices"][0].update(  # type: ignore[index]
            {"product_id": 54}
        ),
        lambda record: record.update(
            {"devices": [record["devices"][0], record["devices"][0]]}  # type: ignore[index]
        ),
        lambda record: record.update({"devices": record["devices"][:-1]}),  # type: ignore[index]
        lambda record: record.update(
            {
                "restorations": [
                    {"verified": True},
                    record["restorations"][1],  # type: ignore[index]
                ]
            }
        ),
        lambda record: record.update(
            {
                "restorations": [
                    record["restorations"][0],  # type: ignore[index]
                    record["restorations"][0],  # type: ignore[index]
                ]
            }
        ),
        lambda record: record["restorations"][0].update(  # type: ignore[index]
            {"snapshot_complete": False}
        ),
    ],
)
def test_finalisation_rejects_forged_public_cycle_device_and_restoration_records(
    tmp_path: Path, mutate: Callable[[dict[str, object]], None]
) -> None:
    """Private input cannot forge a pass, roles, or restoration proof into evidence."""
    private_result = tmp_path / "result.json"
    evidence = public_results()
    mutate(evidence)
    private_result.write_text(
        json.dumps({"finalisable": True, "public_results": evidence}),
        encoding="utf-8",
    )

    with pytest.raises(runner.PreflightError):
        runner.finalise_private_results(private_result, output_directory=tmp_path)


def test_public_writer_cleans_temporary_pair_when_staging_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed second replace leaves no temporary evidence artefacts behind."""
    calls = 0
    real_replace = runner.os.replace

    def fail_second_replace(source: object, destination: object) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("simulated replace failure")
        real_replace(source, destination)

    monkeypatch.setattr(runner.os, "replace", fail_second_replace)
    with pytest.raises(runner.PreflightError, match="could not be written"):
        runner.write_official_evidence(public_results(), output_directory=tmp_path)

    assert not list(tmp_path.glob("*.tmp"))


@pytest.mark.parametrize(
    "record",
    [
        {},
        {"hue": "0", "saturation": 0, "brightness": 0, "kelvin": 3500},
        {"hue": -1, "saturation": 0, "brightness": 0, "kelvin": 3500},
    ],
)
def test_invalid_theme_records_fail_closed(record: dict[str, object]) -> None:
    """The public record conversion admits only complete uint16 protocol tuples."""
    with pytest.raises(runner.PreflightError):
        runner._record_colour(record)


def test_theme_source_errors_and_empty_readbacks_are_rejected(tmp_path: Path) -> None:
    """Broken sources cannot silently become theme evidence."""
    invalid = tmp_path / "themes.jsonl"
    invalid.write_text("not-json\n")
    with pytest.raises(runner.PreflightError):
        runner._read_theme_records(invalid)
    with pytest.raises(runner.PreflightError):
        runner.load_theme_specs(invalid)
    assert runner.theme_from_readback([]).colors == []


def test_private_value_scanner_covers_nested_mappings_sequences_and_bytes() -> None:
    """Privacy rejection walks public value containers without byte-text matching."""
    assert runner._contains_private_value({"safe": ["192.0.2.1"]})
    assert runner._contains_private_value({"safe": [{"account": "x"}]})
    assert not runner._contains_private_value(b"serial d073d5000001")


def off_effect(*, palette: list[HSBK] | None = None) -> SimpleNamespace:
    """Return the complete OFF state exposed by the public matrix API."""
    return SimpleNamespace(
        effect_type=FirmwareEffect.OFF,
        speed=0,
        duration=0,
        palette=palette,
        sky_type=None,
        cloud_saturation_min=0,
        cloud_saturation_max=0,
    )


def test_provenance_and_next_unfinished_are_deterministic() -> None:
    """The resumption seam fingerprints settings and skips only completed keys."""
    settings = RunnerSettings(
        ui_wait_timeout=1,
        operator_action_timeout=300,
        stability_timeout=2,
        poll_interval=3,
    )
    specs = runner.load_theme_specs()
    provenance = runner.build_provenance(
        runner_revision="revision",
        app_version="version",
        catalogue="catalogue",
        target_fingerprints={"source-tile": "target"},
        firmware_by_role={"source-tile": "firmware"},
        theme_specs=specs,
        settings=settings,
    )
    first = runner.build_cycle_schedule()[0]
    assert provenance.effective_settings["operator_action_timeout"] == 300
    assert provenance.effective_settings["poll_interval"] == 3
    assert runner.next_unfinished_cycle({}) == first
    assert (
        runner.next_unfinished_cycle(
            {key: None for key in runner.build_cycle_schedule()}
        )
        is None
    )  # type: ignore[dict-item]


def test_snapshot_helpers_cover_complete_ceiling_and_fail_closed_paths() -> None:
    """All restoration inputs must be complete, static and stable before mutation."""

    class Device:
        def __init__(self, *, ceiling: bool = False, unstable: bool = False) -> None:
            self.ceiling = ceiling
            self.unstable = unstable
            self.effect_reads = 0
            self.pixel_reads = 0

        async def get_power(self) -> int:
            return 65535

        async def get_color(self) -> tuple[HSBK, int, str]:
            return colour(0), 65535, "private"

        async def get_effect(self) -> object:
            self.effect_reads += 1
            return off_effect(
                palette=[] if self.unstable and self.effect_reads == 2 else None
            )

        async def get_device_chain(self) -> list[object]:
            return [object()]

        async def get_all_tile_colors(self) -> list[list[HSBK]]:
            self.pixel_reads += 1
            return [[colour(float(self.pixel_reads)) if self.unstable else colour(0)]]

        async def get_uplight_color(self) -> HSBK:
            return colour(1)

        async def get_downlight_colors(self) -> list[HSBK]:
            return [colour(2)]

    ceiling = asyncio.run(runner.capture_snapshot(Device(ceiling=True)))
    assert ceiling.uplight_colour == colour(1)
    assert ceiling.downlight_colours == [colour(2)]
    with pytest.raises(runner.PreflightError, match="stable"):
        asyncio.run(runner.capture_snapshot(Device(unstable=True)))

    for effect in (
        SimpleNamespace(effect_type="OFF", speed=0, duration=0, palette=None),
        SimpleNamespace(
            effect_type=FirmwareEffect.OFF, speed="0", duration=0, palette=None
        ),
        SimpleNamespace(
            effect_type=FirmwareEffect.OFF, speed=0, duration=0, palette="bad"
        ),
    ):
        with pytest.raises(runner.PreflightError):
            runner._effect_snapshot(effect)


def test_snapshot_missing_and_ceiling_component_errors_stop_before_mutation() -> None:
    """Incomplete generic and Ceiling state never becomes best-effort restore data."""

    class Missing:
        async def get_power(self) -> int:
            return 1

        async def get_color(self) -> tuple[HSBK, int, str]:
            return colour(0), 1, "private"

        async def get_effect(self) -> object:
            return off_effect()

        async def get_device_chain(self) -> list[object]:
            return []

        async def get_all_tile_colors(self) -> list[list[HSBK]]:
            return []

    with pytest.raises(runner.PreflightError, match="incomplete"):
        asyncio.run(runner.capture_snapshot(Missing()))

    class BrokenCeiling(Missing):
        async def get_device_chain(self) -> list[object]:
            return [object()]

        async def get_all_tile_colors(self) -> list[list[HSBK]]:
            return [[colour(0)]]

        async def get_uplight_color(self) -> object:
            return None

        async def get_downlight_colors(self) -> list[HSBK]:
            return []

    with pytest.raises(runner.PreflightError, match="Ceiling"):
        asyncio.run(runner.capture_snapshot(BrokenCeiling()))

    class PartialCeiling(Missing):
        async def get_device_chain(self) -> list[object]:
            return [object()]

        async def get_all_tile_colors(self) -> list[list[HSBK]]:
            return [[colour(0)]]

        async def get_downlight_colors(self) -> list[HSBK]:
            return [colour(0)]

    with pytest.raises(runner.PreflightError, match="Ceiling"):
        asyncio.run(runner.capture_snapshot(PartialCeiling()))

    class Flat:
        async def get_power(self) -> int:
            return 1

        async def get_color(self) -> tuple[HSBK, int, str]:
            return colour(0), 1, "private"

        async def get_effect(self) -> object:
            return off_effect()

        async def get_device_chain(self) -> list[object]:
            return [object()]

        async def get_all_tile_colors(self) -> list[list[HSBK]]:
            return [[colour(0)]]

    assert asyncio.run(runner.capture_snapshot(Flat())).uplight_colour is None


def test_restore_failure_and_verify_failure_are_distinct() -> None:
    """Effect polling and restore calls fail closed instead of claiming restoration."""
    snapshot = runner.RestorationSnapshot(
        1,
        colour(0),
        runner.EffectSnapshot(FirmwareEffect.OFF, 0, 0, None, None, 0, 0),
        [object()],
        [[colour(0)]],
        None,
        None,
    )

    class NeverSettles:
        async def set_effect(self, **kwargs: object) -> None:
            return None

        async def get_effect(self) -> object:
            return off_effect(palette=[colour(1)])

        async def set_matrix_colors(self, *args: object) -> None:
            return None

        async def set_color(self, value: HSBK) -> None:
            return None

        async def set_power(self, value: int) -> None:
            return None

    assert not asyncio.run(
        runner.restore_snapshot(NeverSettles(), snapshot, poll_interval=0.0)
    )
    assert not asyncio.run(runner.verify_restoration(object(), snapshot))
    with pytest.raises(runner.RestorationError):
        runner.effect_speed_seconds_for_restore(
            runner.EffectSnapshot(FirmwareEffect.MORPH, 0, 0, None, None, 0, 0)
        )


def test_adb_ui_and_semantic_helpers_cover_injected_error_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every Android boundary is exercised with a fake process, never a real tablet."""
    with pytest.raises(runner.AdbCommandError):
        runner.adb(
            "devices", run=lambda *args, **kwargs: (_ for _ in ()).throw(OSError())
        )
    assert runner._control_from_element(runner.ET.fromstring('<node text="x"/>')) == {
        "text": "x"
    }
    assert runner._tap_point({"bounds": "[0,0][4,6]"}) == (2, 3)
    with pytest.raises(runner.SemanticLookupError):
        runner._tap_point({"bounds": "bad"})

    destination = tmp_path / "hierarchy.xml"

    def fake_run(command: list[str], **kwargs: object) -> SimpleNamespace:
        if command[1] == "pull":
            destination.write_text('<hierarchy><node text="MORPH"/></hierarchy>')
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    controls = runner.dump_ui_hierarchy(tmp_path, run=fake_run)
    assert controls == [{"text": "MORPH"}]
    destination.write_text("not xml")
    monkeypatch.setattr(runner, "adb", lambda *args, **kwargs: "")
    with pytest.raises(runner.SemanticLookupError):
        runner.dump_ui_hierarchy(tmp_path)

    calls = 0

    def eventually() -> str:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise runner.SemanticLookupError("missing")
        return "found"

    assert runner._with_semantic_retries(eventually) == "found"
    with pytest.raises(runner.SemanticLookupError):
        runner._with_semantic_retries(
            lambda: (_ for _ in ()).throw(runner.SemanticLookupError("x"))
        )


def test_poll_and_tracer_failure_outcomes_are_retained() -> None:
    """Unexpected stable palettes, timeout, UI failure and mismatches stay visible."""
    unexpected = iter([[colour(9)], [colour(9)]])
    stable_mismatch = asyncio.run(
        runner.poll_stable_palette(
            read_palette=lambda: next(unexpected),
            timeout=1,
            poll_interval=0,
        )
    )
    assert stable_mismatch.stable_palette == [colour(9)]
    assert [observation.palette for observation in stable_mismatch.observations] == [
        [colour(9)],
        [colour(9)],
    ]
    timeout = asyncio.run(
        runner.poll_stable_palette(
            read_palette=lambda: [colour(1)], timeout=-1, poll_interval=0
        )
    )
    assert timeout.observations == []

    spec = ThemeSpec("cheerful", "Cheerful", "Moods", [colour(0)], "hash")

    class Device:
        async def get_effect(self) -> object:
            return SimpleNamespace(palette=[colour(1)])

        async def set_effect(self, **kwargs: object) -> None:
            return None

    async def fails() -> None:
        raise runner.SemanticLookupError("private")

    async def restore_bad() -> bool:
        return False

    result = asyncio.run(
        runner.run_tracer_cycle(
            device=Device(),
            theme_spec=spec,
            app_save=fails,
            restore=restore_bad,
            settings=RunnerSettings(stability_timeout=-1, poll_interval=0),
            device_role="source-tile",
        )
    )
    assert result.failure == "restoration failed"


def test_private_file_catalogue_and_android_lifecycle_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Private persistence, device selection and Android restoration reject bad data."""
    with pytest.raises(runner.PreflightError):
        runner.load_target_bindings(
            tmp_path / "missing", private_root=tmp_path / "private"
        )
    bad = tmp_path / "bad.json"
    bad.write_text("not json")
    with pytest.raises(runner.PreflightError):
        runner.load_target_bindings(bad, private_root=tmp_path / "private2")
    runner.require_one_authorised_adb_device(
        1,
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0, stdout="List of devices attached\na\tdevice\n", stderr=""
        ),
    )

    events: list[str] = []
    responses = iter(["bad\n", "", ""])

    def fake_adb(*args: str, **kwargs: object) -> str:
        events.append(args[-1])
        return next(responses)

    monkeypatch.setattr(runner, "adb", fake_adb)
    with pytest.raises(runner.PreflightError):
        asyncio.run(runner.with_android_keep_awake(lambda: asyncio.sleep(0), timeout=1))

    assert runner.catalogue_fingerprint([{"text": "b"}, {"content-desc": "a"}])
    with pytest.raises(runner.PreflightError):
        runner.require_catalogue_stable("a", "b")
    with pytest.raises(runner.PreflightError):
        runner._redacted_progress("private", "bad")


def test_main_preflight_is_fully_injected_and_never_connects_hardware(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The CLI preflight uses fake ADB and private files, not a live device."""
    targets = tmp_path / "targets.json"
    write_targets(targets, approved_targets())
    monkeypatch.setattr(
        runner, "require_one_authorised_adb_device", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        runner,
        "load_theme_specs",
        lambda: {
            "cheerful": ThemeSpec("cheerful", "Cheerful", "Moods", [], "x"),
            "mondrian": ThemeSpec("mondrian", "Mondrian", "Art Series", [], "y"),
        },
    )
    monkeypatch.setattr(
        runner,
        "adb",
        lambda *args, **kwargs: (
            "package:test"
            if args[1] == "pm"
            else "mDreamingLockscreen=false"
            if args[1] == "dumpsys"
            else "1"
        ),
    )

    async def preflight(**kwargs: object) -> runner.PreflightReport:
        record_event = kwargs["record_event"]
        assert callable(record_event)
        record_event(
            {
                "event": "preflight-stage",
                "role": "source-tile",
                "stage": "manual-ui-attestation",
                "status": "passed",
            }
        )
        contact_observer = getattr(kwargs["device_adapter"], "_contact_observer")
        contact_observer("source-tile", "contact", "retrying")
        return runner.PreflightReport(
            "7.1.0",
            "catalogue",
            {
                "source-tile": {
                    "device_class": "MatrixLight",
                    "model": "LIFX Tile",
                    "product_id": 55,
                    "firmware": "3.50",
                },
                "non-tile-matrix": {
                    "device_class": "CeilingLight",
                    "model": "LIFX Ceiling",
                    "product_id": 176,
                    "firmware": "4.0",
                },
            },
        )

    monkeypatch.setattr(runner, "run_non_mutating_preflight", preflight)
    assert (
        asyncio.run(
            runner.main(
                [
                    "--targets",
                    str(targets),
                    "--private-root",
                    str(tmp_path / "private"),
                    "--preflight-only",
                    "--attest-role",
                    "source-tile",
                ]
            )
        )
        == runner.EXIT_PASS
    )
    trace = (tmp_path / "private").glob("*/trace.jsonl")
    assert "private" not in next(trace).read_text()
    assert (
        asyncio.run(
            runner.main(
                [
                    "--targets",
                    str(targets),
                    "--private-root",
                    str(tmp_path / "private2"),
                    "--poll-interval",
                    "-1",
                ]
            )
        )
        == runner.EXIT_INCOMPLETE
    )


def test_main_preflight_requires_explicit_source_attestation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The CLI cannot turn a default preflight into an implicit operator claim."""
    targets = tmp_path / "targets.json"
    write_targets(targets, approved_targets())
    calls: list[str] = []
    monkeypatch.setattr(runner, "load_theme_specs", lambda: {})
    monkeypatch.setattr(
        runner,
        "production_manual_position_callbacks",
        lambda *args: (lambda *command: calls.append("adb") or "", lambda: []),
    )

    assert (
        asyncio.run(
            runner.main(
                [
                    "--targets",
                    str(targets),
                    "--private-root",
                    str(tmp_path / "private"),
                    "--preflight-only",
                ]
            )
        )
        == runner.EXIT_INCOMPLETE
    )
    assert calls == []


def test_non_mutating_preflight_validates_both_roles_without_secondary_navigation() -> (
    None
):
    """Preflight proves both roles on Home but opens only the source selector."""

    class Device:
        async def get_power(self) -> int:
            return 0

        async def get_color(self) -> tuple[HSBK, int, str]:
            return colour(0), 0, "private label"

        async def get_effect(self) -> object:
            return SimpleNamespace(
                effect_type=FirmwareEffect.OFF,
                speed=0,
                duration=0,
                palette=None,
            )

        async def get_device_chain(self) -> list[object]:
            return [object()]

        async def get_all_tile_colors(self) -> list[list[HSBK]]:
            return [[colour(0)]]

    class Devices:
        def __init__(self) -> None:
            self.connected: list[str] = []
            self.closed: list[Device] = []

        async def connect(self, binding: runner.TargetBinding) -> Device:
            self.connected.append(binding.role)
            return Device()

        async def metadata(
            self, binding: runner.TargetBinding, device: Device
        ) -> dict[str, object]:
            if binding.role == "source-tile":
                return {
                    "product_id": 55,
                    "is_matrix": True,
                    "indoor": True,
                    "emulator": False,
                    "model": "LIFX Tile",
                    "device_class": "MatrixLight",
                    "firmware": "3.50",
                }
            return {
                "product_id": 176,
                "is_matrix": True,
                "indoor": True,
                "emulator": False,
                "model": "LIFX Ceiling",
                "device_class": "CeilingLight",
                "firmware": "4.0",
            }

        async def close(self, device: Device) -> None:
            self.closed.append(device)

    bindings = {
        "source-tile": runner.TargetBinding(
            "source-tile", "private", "d073d5000001", "Tile", True, True, "source group"
        ),
        "non-tile-matrix": runner.TargetBinding(
            "non-tile-matrix",
            "private",
            "d073d5000002",
            "Ceiling",
            True,
            True,
            "secondary_group",
        ),
    }
    secondary_group_card_id = "app:id/ax_device_list_group_card_button_secondary_group"
    home = [
        {
            "resource-id": "app:id/ax_device_list_group_card_button_source group",
            "bounds": "[0,0][10,10]",
        },
        {
            "text": "secondary group",
            "resource-id": secondary_group_card_id,
            "bounds": "[10,0][20,10]",
        },
    ]
    selected_source_page = [
        {"resource-id": "app:id/detail_panel", "bounds": "[900,0][1800,2880]"},
        {"text": "source group", "bounds": "[950,990][1165,1067]"},
        {"clickable": "true", "bounds": "[950,1110][1085,1218]"},
        {"text": "1", "bounds": "[1040,1139][1058,1188]"},
        {
            "text": "Morph",
            "resource-id": "app:id/effect_name",
            "bounds": "[950,213][1755,290]",
        },
        {
            "text": "Effect",
            "resource-id": "app:id/effect_subtitle",
            "bounds": "[950,290][1755,342]",
        },
        {
            "resource-id": "app:id/effect_settings_controller_scroll_view",
            "bounds": "[950,342][1755,1313]",
        },
        {
            "resource-id": "app:id/theme_button",
            "clickable": "true",
            "enabled": "true",
            "bounds": "[950,463][1293,586]",
        },
    ]
    _controls = iter(
        [
            [{"text": "MORPH"}],
            home,
            home,
            [
                {
                    "resource-id": "app:id/detail_panel",
                    "bounds": "[950,900][1755,1900]",
                },
                {"text": "source group", "bounds": "[950,990][1165,1067]"},
                {"clickable": "true", "bounds": "[950,1110][1085,1218]"},
                {"text": "Lights", "bounds": "[1040,1139][1058,1188]"},
            ],
            [{"text": "Select lights"}],
            [{"text": "Tile", "bounds": "[0,10][10,20]"}],
            selected_source_page,
            [
                {"text": "FX", "resource-id": "app:id/ax_device_control_effects_tab"},
                {"text": "Colours"},
            ],
            [
                {"text": "FX", "resource-id": "app:id/ax_device_control_effects_tab"},
                {"text": "MORPH"},
            ],
            [{"text": "MORPH"}, {"text": "Moods"}, {"text": "Art Series"}],
            [{"text": "Cheerful"}, {"resource-id": "app:id/save_button"}],
            [{"text": "MORPH"}, {"text": "Art Series"}],
            [{"text": "Other"}],
            [{"text": "Mondrian"}, {"resource-id": "app:id/save_button"}],
            [{"text": "Mondrian"}, {"resource-id": "app:id/save_button"}],
            [{"text": "Mondrian"}, {"resource-id": "app:id/save_button"}],
        ]
    )
    commands: list[tuple[str, ...]] = []
    taps: list[tuple[str, str]] = []
    swipes: list[str] = []
    device_list_swipes: list[runner.Control] = []
    home_resets: list[str] = []
    navigation: list[str] = []
    events: list[Mapping[str, object]] = []

    def adb_command(*arguments: str) -> str:
        commands.append(arguments)
        if arguments == ("devices",):
            return "List of devices attached\na\tdevice\n"
        if arguments[:3] == ("shell", "pm", "path"):
            return "package:test"
        if arguments == ("shell", "dumpsys", "window"):
            return "mDreamingLockscreen=false"
        if arguments[:3] == ("shell", "dumpsys", "package"):
            return "versionName=7.1.0"
        if arguments[-1] == "stay_on_while_plugged_in":
            return "3"
        return ""

    def record_tap(control: runner.Control) -> None:
        navigation.append("tap")
        taps.append((runner._text(control), control.get("bounds", "")))

    def record_home_reset() -> None:
        home_resets.append("home")
        navigation.append("home")

    adapters = Devices()
    report = asyncio.run(
        runner.run_non_mutating_preflight(
            bindings=bindings,
            theme_specs={
                "cheerful": ThemeSpec("cheerful", "Cheerful", "Moods", [], "x"),
                "mondrian": ThemeSpec("mondrian", "Mondrian", "Art Series", [], "y"),
            },
            settings=RunnerSettings(max_theme_scrolls=1),
            device_adapter=adapters,
            adb_command=adb_command,
            attested_role="source-tile",
            record_event=events.append,
            open_home=record_home_reset,
            dump_hierarchy=lambda: selected_source_page,
            tap_control=record_tap,
            return_to_morph=lambda: None,
            swipe=lambda: swipes.append("swipe"),
            swipe_device_list=device_list_swipes.append,
        )
    )

    assert report.app_version == "7.1.0"
    assert report.catalogue_fingerprint
    assert home_resets == []
    assert navigation == []
    assert adapters.connected == ["source-tile", "non-tile-matrix"]
    assert len(adapters.closed) == 2
    assert taps == []
    assert swipes == []
    assert device_list_swipes == []
    assert all("input" not in command for command in commands)
    assert events == [
        {
            "event": "preflight-stage",
            "role": "source-tile",
            "stage": "manual-ui-attestation",
            "status": "passed",
        },
        {
            "event": "preflight-stage",
            "role": "source-tile",
            "stage": "contact",
            "status": "starting",
        },
        {
            "event": "preflight-stage",
            "role": "source-tile",
            "stage": "contact",
            "status": "passed",
        },
        {
            "event": "preflight-stage",
            "role": "non-tile-matrix",
            "stage": "contact",
            "status": "starting",
        },
        {
            "event": "preflight-stage",
            "role": "non-tile-matrix",
            "stage": "contact",
            "status": "passed",
        },
        {
            "event": "preflight-stage",
            "role": "source-tile",
            "stage": "metadata",
            "status": "starting",
        },
        {
            "event": "preflight-stage",
            "role": "source-tile",
            "stage": "metadata",
            "status": "passed",
        },
        {
            "event": "preflight-stage",
            "role": "non-tile-matrix",
            "stage": "metadata",
            "status": "starting",
        },
        {
            "event": "preflight-stage",
            "role": "non-tile-matrix",
            "stage": "metadata",
            "status": "passed",
        },
        {
            "event": "preflight-stage",
            "role": "source-tile",
            "stage": "snapshot",
            "status": "starting",
        },
        {
            "event": "preflight-stage",
            "role": "source-tile",
            "stage": "snapshot",
            "status": "passed",
        },
        {
            "event": "preflight-stage",
            "role": "non-tile-matrix",
            "stage": "snapshot",
            "status": "starting",
        },
        {
            "event": "preflight-stage",
            "role": "non-tile-matrix",
            "stage": "snapshot",
            "status": "passed",
        },
        {"event": "preflight-stage", "stage": "preflight-complete", "status": "passed"},
    ]


@pytest.mark.parametrize(
    ("boundary", "role"),
    [
        ("contact", "source-tile"),
        ("contact", "non-tile-matrix"),
        ("metadata", "source-tile"),
        ("snapshot", "non-tile-matrix"),
    ],
)
def test_preflight_stage_records_failures_without_private_diagnostics(
    boundary: str, role: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every read-only boundary emits a safe fixed failure stage before stopping."""
    bindings = {
        "source-tile": runner.TargetBinding(
            "source-tile", "private-host", "d073d5000001", "Tile", True, True
        ),
        "non-tile-matrix": runner.TargetBinding(
            "non-tile-matrix", "private-host", "d073d5000002", "Ceiling", True, True
        ),
    }
    controls: list[runner.Control] = [
        {"resource-id": "app:id/detail_panel", "bounds": "[900,0][1800,2880]"},
        {
            "text": "Morph",
            "resource-id": "app:id/effect_name",
            "bounds": "[950,213][1755,290]",
        },
        {
            "text": "Effect",
            "resource-id": "app:id/effect_subtitle",
            "bounds": "[950,290][1755,342]",
        },
        {
            "resource-id": "app:id/effect_settings_controller_scroll_view",
            "bounds": "[950,342][1755,1313]",
        },
        {
            "resource-id": "app:id/theme_button",
            "clickable": "true",
            "enabled": "true",
            "bounds": "[950,463][1293,586]",
        },
    ]

    class Adapter:
        async def connect(self, binding: runner.TargetBinding) -> object:
            if boundary == "contact" and binding.role == role:
                raise runner.PreflightError("private-host contact")
            return SimpleNamespace(role=binding.role)

        async def metadata(
            self, binding: runner.TargetBinding, device: object
        ) -> Mapping[str, object]:
            if boundary == "metadata" and binding.role == role:
                raise runner.PreflightError("private-host metadata")
            if binding.role == "source-tile":
                return {
                    "product_id": 55,
                    "is_matrix": True,
                    "indoor": True,
                    "emulator": False,
                    "model": "LIFX Tile",
                    "device_class": "MatrixLight",
                    "firmware": "3.50",
                }
            return {
                "product_id": 176,
                "is_matrix": True,
                "indoor": True,
                "emulator": False,
                "model": "LIFX Ceiling",
                "device_class": "CeilingLight",
                "firmware": "4.0",
            }

        async def close(self, device: object) -> None:
            return None

    async def snapshot(device: object) -> runner.RestorationSnapshot:
        if boundary == "snapshot" and getattr(device, "role") == role:
            raise runner.PreflightError("private-host snapshot")
        return SimpleNamespace()  # type: ignore[return-value]

    monkeypatch.setattr(runner, "capture_snapshot", snapshot)
    events: list[Mapping[str, str]] = []

    def adb_command(*arguments: str) -> str:
        if arguments == ("devices",):
            return "List of devices attached\na\tdevice\n"
        if arguments[:3] == ("shell", "pm", "path"):
            return "package:test"
        if arguments == ("shell", "dumpsys", "window"):
            return "mDreamingLockscreen=false"
        if arguments[:3] == ("shell", "dumpsys", "package"):
            return "versionName=7.1.0"
        if arguments[-1] == "stay_on_while_plugged_in":
            return "3"
        return ""

    with pytest.raises(runner.PreflightError):
        asyncio.run(
            runner.run_non_mutating_preflight(
                bindings=bindings,
                theme_specs={
                    "cheerful": ThemeSpec("cheerful", "Cheerful", "Moods", [], "x"),
                    "mondrian": ThemeSpec(
                        "mondrian", "Mondrian", "Art Series", [], "y"
                    ),
                },
                settings=RunnerSettings(),
                device_adapter=Adapter(),
                adb_command=adb_command,
                dump_hierarchy=lambda: controls,
                attested_role="source-tile",
                record_event=events.append,
            )
        )

    assert events[-1] == {
        "event": "preflight-stage",
        "role": role,
        "stage": boundary,
        "status": "failed",
    }
    assert "private-host" not in json.dumps(events)


@pytest.mark.parametrize(
    ("source", "non_tile"),
    [
        ({"model": "wrong", "device_class": "MatrixLight"}, None),
        (
            {"model": "LIFX Tile", "device_class": "MatrixLight"},
            {"model": "wrong", "device_class": "MatrixLight"},
        ),
        (
            {"model": "LIFX Tile", "device_class": "MatrixLight"},
            {"model": "LIFX Ceiling", "device_class": "MatrixLight"},
        ),
        (
            {"model": "LIFX Tile", "device_class": "MatrixLight"},
            {"model": "LIFX Luna", "device_class": "CeilingLight"},
        ),
    ],
)
def test_live_preflight_identity_rejections_are_fail_closed(
    source: dict[str, object], non_tile: dict[str, object] | None
) -> None:
    """Only the bound Tile plus Ceiling or Luna role can become a run target."""
    metadata = {
        "source-tile": source,
        "non-tile-matrix": non_tile
        or {"model": "LIFX Ceiling", "device_class": "CeilingLight"},
    }

    with pytest.raises(runner.PreflightError):
        runner.validate_live_preflight_metadata(metadata)

    with pytest.raises(runner.PreflightError):
        runner.parse_app_version("private diagnostics")


@pytest.mark.parametrize(
    "secondary",
    [
        {"product_id": 219, "model": "LIFX Path", "device_class": "MatrixLight"},
        {"product_id": 57, "model": "LIFX Candle", "device_class": "MatrixLight"},
        {
            "product_id": 999,
            "model": "Unapproved Matrix",
            "device_class": "MatrixLight",
        },
    ],
)
def test_full_lifecycle_rejects_unapproved_matrix_before_checkpoint_or_mutation(
    tmp_path: Path,
    secondary: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A direct run cannot reach snapshots, writes, or callbacks for substitutes."""
    bindings, specs, provenance = _lifecycle_inputs()
    events: list[str] = []

    class Adapter:
        async def connect(self, binding: runner.TargetBinding) -> object:
            events.append(f"connect:{binding.role}")
            return SimpleNamespace(role=binding.role)

        async def metadata(
            self, binding: runner.TargetBinding, device: object
        ) -> dict[str, object]:
            events.append(f"metadata:{binding.role}")
            if binding.role == "source-tile":
                return {
                    "product_id": 55,
                    "is_matrix": True,
                    "indoor": True,
                    "emulator": False,
                    "model": "LIFX Tile",
                    "device_class": "MatrixLight",
                }
            return {
                "is_matrix": True,
                "indoor": True,
                "emulator": False,
                **secondary,
            }

        async def close(self, device: object) -> None:
            events.append(f"close:{device.role}")  # type: ignore[attr-defined]

    class Store:
        def write(self, path: Path, checkpoint: runner.RunCheckpoint) -> None:
            events.append("checkpoint")

        def load(self, path: Path) -> dict[str, object]:
            raise AssertionError("not used")

    async def forbidden_snapshot(device: object) -> runner.RestorationSnapshot:
        events.append("snapshot")
        raise AssertionError("unapproved target reached snapshot")

    async def forbidden_cycle(*args: object) -> runner.CycleResult:
        events.append("cycle")
        raise AssertionError("unapproved target reached mutation callback")

    monkeypatch.setattr(runner, "capture_snapshot", forbidden_snapshot)
    result = asyncio.run(
        runner.run_designated_lifecycle(
            run_id="opaque",
            bindings=bindings,
            theme_specs=specs,
            provenance=provenance,
            device_adapter=Adapter(),  # type: ignore[arg-type]
            checkpoint_store=Store(),  # type: ignore[arg-type]
            checkpoint_path=tmp_path / "checkpoint.json",
            app_cycle=forbidden_cycle,  # type: ignore[arg-type]
            library_cycle=forbidden_cycle,  # type: ignore[arg-type]
        )
    )

    assert result.exit_code == runner.EXIT_INCOMPLETE
    assert events == [
        "connect:source-tile",
        "connect:non-tile-matrix",
        "metadata:source-tile",
        "metadata:non-tile-matrix",
        "close:source-tile",
        "close:non-tile-matrix",
    ]


def test_preflight_adapter_callbacks_and_restore_verification_are_injected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Manual positioning callbacks expose no navigation or input-tap path."""
    commands: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        runner,
        "adb",
        lambda *arguments, **kwargs: commands.append(arguments) or "3",
    )
    monkeypatch.setattr(
        runner,
        "dump_ui_hierarchy",
        lambda *args, **kwargs: [{"text": "safe"}],
    )
    adb_command, dump = runner.production_manual_position_callbacks(
        RunnerSettings(), tmp_path
    )
    assert adb_command("devices") == "3" and dump() == [{"text": "safe"}]
    assert commands == [("devices",)]

    reads = iter(["3", "4"])
    with pytest.raises(runner.RestorationError):
        asyncio.run(
            runner.with_android_keep_awake(
                lambda: asyncio.sleep(0),
                timeout=1,
                adb_command=lambda *args: (
                    next(reads) if args[1] == "settings" and args[2] == "get" else ""
                ),
            )
        )


@pytest.mark.parametrize("attested_role", [None])
def test_non_mutating_preflight_requires_explicit_role_attestation_before_lan(
    attested_role: str | None,
) -> None:
    """No UI observation can authorise LAN contact without the selected role claim."""
    calls: list[tuple[str, ...]] = []

    async def forbidden(*args: object) -> object:
        raise AssertionError("LAN must not be contacted without a role attestation")

    bindings = {
        role: runner.TargetBinding(
            role, "private", f"d073d500000{index}", role, True, True
        )
        for index, role in enumerate(("source-tile", "non-tile-matrix"), 1)
    }
    adapter = SimpleNamespace(connect=forbidden, metadata=forbidden, close=forbidden)

    with pytest.raises(runner.PreflightError):
        asyncio.run(
            runner.run_non_mutating_preflight(
                bindings=bindings,
                theme_specs={},
                settings=RunnerSettings(),
                device_adapter=adapter,
                adb_command=lambda *args: calls.append(args) or "",
                dump_hierarchy=lambda: [],
                attested_role=attested_role,
            )
        )

    assert calls == []


@pytest.mark.parametrize(
    ("package", "window"),
    [("not-package", "mDreamingLockscreen=false"), ("package:test", "locked")],
)
def test_non_mutating_preflight_rejects_app_before_ui_or_lan(
    package: str, window: str
) -> None:
    """Unavailable app or locked screen returns incomplete before any target connect."""

    async def never_connect(binding: runner.TargetBinding) -> object:
        raise AssertionError("LAN must not be contacted")

    adapter = type(
        "Adapter",
        (),
        {
            "connect": never_connect,
            "metadata": never_connect,
            "close": never_connect,
        },
    )()
    bindings = {
        role: runner.TargetBinding(
            role, "private", f"d073d500000{index}", role, True, True
        )
        for index, role in enumerate(("source-tile", "non-tile-matrix"), 1)
    }

    def adb_command(*arguments: str) -> str:
        if arguments == ("devices",):
            return "List of devices attached\na\tdevice\n"
        if arguments[:3] == ("shell", "pm", "path"):
            return package
        return window

    with pytest.raises(runner.PreflightError):
        asyncio.run(
            runner.run_non_mutating_preflight(
                bindings=bindings,
                theme_specs={},
                settings=RunnerSettings(),
                device_adapter=adapter,
                adb_command=adb_command,
                attested_role="source-tile",
                open_home=lambda: None,
                dump_hierarchy=lambda: [],
                tap_control=lambda control: None,
                return_to_morph=lambda: None,
                swipe=lambda: None,
                swipe_device_list=lambda control: None,
            )
        )


def test_semantic_app_save_requires_manual_position_then_taps_only_theme_controls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The production app boundary scrolls the picker, never a category control."""
    binding = runner.TargetBinding(
        "source-tile",
        "private",
        "d073d5000001",
        "private label",
        True,
        True,
        "test_group",
    )
    spec = ThemeSpec("mondrian", "Mondrian", "Art Series", [colour(0)], "hash")
    _dumps = iter(
        [
            [{"text": "MORPH"}],
            [
                {
                    "text": "test group",
                    "resource-id": "app:id/ax_device_list_group_card_button_test_group",
                    "bounds": "[0,0][4,4]",
                }
            ],
            [
                {
                    "text": "test group",
                    "resource-id": "app:id/ax_device_list_group_card_button_test_group",
                    "bounds": "[0,0][4,4]",
                }
            ],
            [
                {
                    "resource-id": "app:id/detail_panel",
                    "bounds": "[950,900][1755,1900]",
                },
                {"text": "test_group", "bounds": "[108,2060][264,2113]"},
                {"text": "test_group", "bounds": "[950,990][1165,1067]"},
                {"content-desc": "Lights", "resource-id": "app:id/ax_home_tab_lights"},
                {"clickable": "true", "bounds": "[950,1110][1085,1218]"},
                {"text": "Lights", "bounds": "[1040,1139][1058,1188]"},
            ],
            [{"text": "Lights", "bounds": "[0,0][4,4]"}],
            [{"text": "Select lights"}],
            [
                {
                    "class": "android.widget.ScrollView",
                    "scrollable": "true",
                    "bounds": "[950,1331][1755,1862]",
                }
            ],
            [{"text": "private label", "bounds": "[0,0][4,4]"}],
            [{"text": "private label", "bounds": "[0,0][4,4]"}],
            [
                {
                    "resource-id": "app:id/detail_panel",
                    "bounds": "[950,900][1755,1900]",
                },
                {"text": "test_group", "bounds": "[950,990][1165,1067]"},
                {"clickable": "true", "bounds": "[950,1110][1085,1218]"},
                {"text": "Lights", "bounds": "[1040,1139][1058,1188]"},
                {
                    "text": "FX",
                    "resource-id": "app:id/ax_device_control_effects_tab",
                    "bounds": "[0,0][4,4]",
                },
            ],
            [
                {
                    "resource-id": "app:id/detail_panel",
                    "bounds": "[950,900][1755,1900]",
                },
                {"text": "test_group", "bounds": "[950,990][1165,1067]"},
                {"clickable": "true", "bounds": "[950,1110][1085,1218]"},
                {"text": "1", "bounds": "[1040,1139][1058,1188]"},
                {"text": "Select lights", "bounds": "[950,1200][1300,1260]"},
                {
                    "resource-id": "app:id/ax_device_control_close_button",
                    "clickable": "true",
                    "bounds": "[936,857][1044,965]",
                },
                {
                    "text": "FX",
                    "resource-id": "app:id/ax_device_control_effects_tab",
                    "bounds": "[0,0][4,4]",
                },
            ],
            [
                {
                    "resource-id": "app:id/detail_panel",
                    "bounds": "[950,900][1755,1900]",
                },
                {"text": "test_group", "bounds": "[950,990][1165,1067]"},
                {"clickable": "true", "bounds": "[950,1110][1085,1218]"},
                {"text": "1", "bounds": "[1040,1139][1058,1188]"},
                {
                    "text": "FX",
                    "resource-id": "app:id/ax_device_control_effects_tab",
                    "bounds": "[0,0][4,4]",
                },
            ],
            [
                {
                    "text": "FX",
                    "resource-id": "app:id/ax_device_control_effects_tab",
                    "bounds": "[0,0][4,4]",
                }
            ],
            [
                {
                    "text": "FX",
                    "resource-id": "app:id/ax_device_control_effects_tab",
                    "bounds": "[0,0][4,4]",
                },
                {"text": "Colours", "bounds": "[0,0][4,4]"},
            ],
            [
                {
                    "text": "FX",
                    "resource-id": "app:id/ax_device_control_effects_tab",
                    "bounds": "[0,0][4,4]",
                },
                {"text": "MORPH", "bounds": "[0,0][4,4]"},
            ],
            [{"text": "MORPH", "bounds": "[0,0][4,4]"}],
            [{"text": "MORPH", "bounds": "[0,0][4,4]"}],
            [{"text": "🎨 MOODS", "bounds": "[0,0][4,4]"}],
            [{"text": "Other", "bounds": "[0,0][4,4]"}],
            [{"text": "Cheerful", "bounds": "[0,0][4,4]"}],
            [{"resource-id": "app:id/save_button", "bounds": "[0,0][4,4]"}],
        ]
    )
    commands: list[tuple[str, ...]] = []
    navigation: list[str] = []
    manual_surface = [
        {"resource-id": "app:id/detail_panel", "bounds": "[900,0][1800,2880]"},
        {"text": "test_group", "bounds": "[950,990][1165,1067]"},
        {"clickable": "true", "bounds": "[950,1110][1085,1218]"},
        {"text": "1", "bounds": "[1040,1139][1058,1188]"},
        {
            "text": "Morph",
            "resource-id": "app:id/effect_name",
            "bounds": "[950,213][1755,290]",
        },
        {
            "text": "Effect",
            "resource-id": "app:id/effect_subtitle",
            "bounds": "[950,290][1755,342]",
        },
        {
            "resource-id": "app:id/effect_settings_controller_scroll_view",
            "bounds": "[950,342][1755,1313]",
        },
        {
            "resource-id": "app:id/theme_button",
            "clickable": "true",
            "enabled": "true",
            "bounds": "[950,463][1293,586]",
        },
    ]
    manual_dumps = iter(
        [
            manual_surface,
            [
                {
                    "text": "🎨 ART SERIES",
                    "resource-id": "app:id/ax_button_theme_category",
                    "bounds": "[0,5][4,9]",
                },
                {
                    "class": "android.widget.ScrollView",
                    "scrollable": "true",
                    "bounds": "[10,20][110,220]",
                },
            ],
            [
                {"text": "🎨 ART SERIES", "bounds": "[0,5][4,9]"},
                {"text": "Mondrian", "bounds": "[10,0][14,4]"},
            ],
            [{"resource-id": "app:id/save_button", "bounds": "[20,0][24,4]"}],
        ]
    )
    monkeypatch.setattr(
        runner,
        "dump_ui_hierarchy",
        lambda *args, **kwargs: navigation.append("dump") or next(manual_dumps),
    )
    monkeypatch.setattr(
        runner, "adb", lambda *args, **kwargs: commands.append(tuple(args)) or ""
    )
    asyncio.run(
        runner.semantic_app_save(
            binding,
            spec,
            settings=RunnerSettings(max_theme_scrolls=1),
            run_directory=tmp_path,
            attested_role="source-tile",
            open_home=lambda: navigation.append("home"),
        )
    )
    assert navigation == ["dump", "dump", "dump", "dump"]
    assert commands == [
        ("shell", "input", "tap", "1121", "524"),
        ("shell", "input", "swipe", "60", "170", "60", "70", "400"),
        ("shell", "input", "tap", "12", "2"),
        ("shell", "input", "tap", "22", "2"),
    ]
    events = [
        json.loads(line)["stage"]
        for line in (tmp_path / "trace.jsonl").read_text().splitlines()
        if "stage" in json.loads(line)
    ]
    assert events == [
        "theme-picker-opened",
        "theme-picker-scrolled",
        "theme-selected",
        "save-selected",
    ]
    with pytest.raises(runner.SemanticLookupError):
        runner.scroll_to_semantic_theme(
            "Cheerful",
            dump_hierarchy=lambda: [],
            swipe_scrollable=lambda control: None,
            max_scrolls=-1,
        )


def test_semantic_app_save_does_not_open_home_when_manual_position_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A lost manual position fails closed without automated recovery navigation."""
    binding = runner.TargetBinding(
        "source-tile", "private", "d073d5000001", "private label", True, True, "group"
    )
    commands: list[tuple[str, ...]] = []
    dumps = iter([[{"text": "private label"}], [{"text": "private label"}], []])
    monkeypatch.setattr(
        runner, "dump_ui_hierarchy", lambda *args, **kwargs: next(dumps)
    )
    monkeypatch.setattr(
        runner, "adb", lambda *args, **kwargs: commands.append(tuple(args)) or ""
    )

    with pytest.raises(runner.SemanticLookupError):
        asyncio.run(
            runner.semantic_app_save(
                binding,
                ThemeSpec("cheerful", "Cheerful", "Moods", [], "hash"),
                settings=RunnerSettings(),
                run_directory=tmp_path,
                attested_role="source-tile",
            )
        )

    assert commands == []


def test_semantic_morph_activation_requires_lan_proof_and_taps_play_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A persistent play control is not evidence that Morph is actually active."""
    binding = runner.TargetBinding(
        "source-tile", "private", "d073d5000001", "private label", True, True, "group"
    )
    surface = [
        {"resource-id": "app:id/detail_panel", "bounds": "[900,0][1800,2880]"},
        {
            "text": "Morph",
            "resource-id": "app:id/effect_name",
            "bounds": "[950,213][1755,290]",
        },
        {
            "text": "Effect",
            "resource-id": "app:id/effect_subtitle",
            "bounds": "[950,290][1755,342]",
        },
        {
            "resource-id": "app:id/effect_settings_controller_scroll_view",
            "bounds": "[950,342][1755,1313]",
        },
        {
            "resource-id": "app:id/theme_button",
            "clickable": "true",
            "enabled": "true",
            "bounds": "[950,463][1293,586]",
        },
        {
            "resource-id": "app:id/play_button",
            "clickable": "true",
            "enabled": "true",
            "selected": "false",
            "bounds": "[1269,2603][1436,2770]",
        },
    ]
    commands: list[tuple[str, ...]] = []
    monkeypatch.setattr(runner, "dump_ui_hierarchy", lambda *args, **kwargs: surface)
    monkeypatch.setattr(
        runner, "adb", lambda *args, **kwargs: commands.append(tuple(args)) or ""
    )

    class Device:
        def __init__(self, effect: object) -> None:
            self.effect = effect
            self.reads = 0

        async def get_effect(self) -> object:
            self.reads += 1
            return self.effect

    active = SimpleNamespace(
        effect_type=FirmwareEffect.MORPH,
        speed=1000,
        duration=0,
        palette=[colour(0)],
        sky_type=None,
        cloud_saturation_min=0,
        cloud_saturation_max=0,
    )
    device = Device(active)
    pauses: list[float] = []

    async def sleep(interval: float) -> None:
        pauses.append(interval)

    monkeypatch.setattr(runner.asyncio, "sleep", sleep)
    failed_directory = tmp_path / "failed"
    failed_directory.mkdir()
    for initial_theme in (None, "mondrian"):
        with pytest.raises(runner.PreflightError):
            asyncio.run(
                runner.semantic_morph_activation(
                    binding,
                    device,
                    settings=RunnerSettings(stability_timeout=1, poll_interval=1),
                    run_directory=failed_directory,
                    run_id="opaque",
                    timestamp="2026-08-16T00:00:00Z",
                    attested_role="source-tile",
                    attested_initial_theme=initial_theme,
                )
            )
    assert commands == []
    asyncio.run(
        runner.semantic_morph_activation(
            binding,
            device,
            settings=RunnerSettings(stability_timeout=1, poll_interval=1),
            run_directory=tmp_path,
            run_id="opaque",
            timestamp="2026-08-16T00:00:00Z",
            attested_role="source-tile",
            attested_initial_theme="cheerful",
        )
    )
    assert commands == [("shell", "input", "tap", "1352", "2686")]
    assert device.reads == 2
    assert pauses == [1]
    assert [
        json.loads(line) for line in (tmp_path / "trace.jsonl").read_text().splitlines()
    ] == [
        {"event": "morph-activation", "role": "source-tile", "status": "starting"},
        {
            "event": "initial-theme-attestation",
            "run_id": "opaque",
            "role": "source-tile",
            "binding_digest": runner.binding_digest(binding),
            "timestamp": "2026-08-16T00:00:00Z",
            "initial_theme": "cheerful",
            "operator_attested": True,
        },
        {"event": "morph-activation", "role": "source-tile", "status": "passed"},
    ]

    inactive = Device(
        SimpleNamespace(
            effect_type=FirmwareEffect.OFF,
            speed=0,
            duration=0,
            palette=None,
            sky_type=None,
            cloud_saturation_min=0,
            cloud_saturation_max=0,
        )
    )
    with pytest.raises(runner.PreflightError):
        asyncio.run(
            runner.semantic_morph_activation(
                binding,
                inactive,
                settings=RunnerSettings(stability_timeout=0, poll_interval=0),
                run_directory=tmp_path,
                attested_role="source-tile",
                attested_initial_theme="cheerful",
            )
        )
    assert commands.count(("shell", "input", "tap", "1352", "2686")) == 2
    with pytest.raises(runner.PreflightError):
        asyncio.run(
            runner.semantic_morph_activation(
                binding,
                device,
                settings=RunnerSettings(stability_timeout=1, poll_interval=0),
                run_directory=tmp_path,
                attested_role="non-tile-matrix",
                attested_initial_theme="cheerful",
            )
        )
    assert commands.count(("shell", "input", "tap", "1352", "2686")) == 2


def test_source_and_private_error_paths_are_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Malformed data and failed private permission enforcement stop evidence."""
    source = tmp_path / "themes.jsonl"
    source.write_text("1\n")
    with pytest.raises(runner.PreflightError):
        runner._read_theme_records(source)
    with pytest.raises(runner.PreflightError):
        runner.derive_ceiling_determinations(source)
    bad_disposition = tmp_path / "bad-disposition.jsonl"
    bad_disposition.write_text(
        json.dumps({"slug": "cheerful", "disposition": "other"}) + "\n"
    )
    with pytest.raises(runner.PreflightError):
        runner.load_theme_specs(bad_disposition)
    with pytest.raises(runner.PreflightError):
        runner.load_theme_specs(tmp_path / "missing.jsonl")
    assert runner._public_palette(None) is None
    monkeypatch.setattr(
        runner.os, "chmod", lambda *args: (_ for _ in ()).throw(OSError())
    )
    with pytest.raises(runner.PreflightError):
        runner._chmod(tmp_path, 0o700)


def test_restore_writer_and_keep_awake_negative_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cleanup errors cannot become successful restoration or finalisation."""
    snapshot = runner.RestorationSnapshot(
        1,
        colour(0),
        runner.EffectSnapshot(FirmwareEffect.OFF, 0, 0, None, None, 0, 0),
        [object()],
        [[colour(0)]],
        None,
        None,
    )

    class Broken:
        async def set_effect(self, **kwargs: object) -> None:
            raise AttributeError("broken")

    assert not asyncio.run(runner.restore_snapshot(Broken(), snapshot, poll_interval=0))
    real_read_text = Path.read_text

    def mismatch_markdown(path: Path, *args: object, **kwargs: object) -> str:
        if path.name.endswith(".md.tmp"):
            return "changed"
        return real_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", mismatch_markdown)
    with pytest.raises(runner.PreflightError, match="Markdown"):
        runner.write_official_evidence(public_results(), output_directory=tmp_path)

    def failing_adb(*args: str, **kwargs: object) -> str:
        if args[2] == "get":
            return "3"
        if args[-1] == "7":
            return ""
        raise runner.AdbCommandError("failed")

    monkeypatch.setattr(runner, "adb", failing_adb)
    with pytest.raises(runner.RestorationError):
        asyncio.run(runner.with_android_keep_awake(lambda: asyncio.sleep(0), timeout=1))


def test_remaining_public_and_theme_branches_are_rejected(tmp_path: Path) -> None:
    """Invalid nested public records and incomplete fixed themes cannot be published."""
    candles = public_results()
    candles["devices"] = [
        candles["devices"][0],  # type: ignore[index]
        {
            "role": "source-tile",
            "device_class": "MatrixLight",
            "model": "LIFX Tile",
            "product_id": 55,
            "host_firmware": "1.0",
        },
    ]
    with pytest.raises(runner.PreflightError, match="roles"):
        runner.validate_public_results(candles)
    with pytest.raises(runner.PreflightError, match="Candle"):
        runner.validate_non_tile_metadata(
            {
                "product_id": 100,
                "is_matrix": True,
                "indoor": True,
                "model": "LIFX Candle",
            }
        )

    for record in (
        {
            "slug": "cheerful",
            "disposition": "lifx-app",
            "name": 1,
            "category": "Moods",
            "colors": [],
        },
        {
            "slug": "cheerful",
            "disposition": "lifx-app",
            "name": "Cheerful",
            "category": "Moods",
            "colors": [1],
        },
    ):
        source = tmp_path / f"{len(record)}.jsonl"
        source.write_text(json.dumps(record) + "\n")
        with pytest.raises(runner.PreflightError):
            runner.load_theme_specs(source)
    incomplete = tmp_path / "incomplete.jsonl"
    incomplete.write_text(
        json.dumps(
            {
                "slug": "cheerful",
                "disposition": "lifx-app",
                "name": "Cheerful",
                "category": "Moods",
                "colors": [],
            }
        )
        + "\n"
    )
    with pytest.raises(runner.PreflightError, match="missing"):
        runner.load_theme_specs(incomplete)


def test_remaining_restore_and_checkpoint_branches_are_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Slow effect reads, invalid private schemas and stable catalogues are explicit."""
    target = runner.EffectSnapshot(FirmwareEffect.OFF, 0, 0, None, None, 0, 0)
    reads = iter([off_effect(palette=[colour(1)]), off_effect(), off_effect()])

    class Device:
        async def get_effect(self) -> object:
            return next(reads)

    assert asyncio.run(
        runner._wait_for_effect_snapshot(Device(), target, poll_interval=0.001)
    )
    target_path = tmp_path / "targets.json"
    document = approved_targets()
    document["schema_version"] = 2
    write_targets(target_path, document)
    with pytest.raises(runner.PreflightError):
        runner.load_target_bindings(target_path, private_root=tmp_path / "private")
    runner.require_catalogue_stable("same", "same")


def test_connect_and_main_live_paths_are_fully_faked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Connection identity and CLI cleanup use injected fake classes only."""
    binding = runner.TargetBinding(
        "source-tile", "private", "d073d5000001", "label", True, True
    )
    close_events: list[str] = []

    class FakeMatrix:
        label = "label"

        async def __aenter__(self) -> None:
            close_events.append("enter")

        async def close(self) -> None:
            close_events.append("close")

        async def get_version(self) -> object:
            return SimpleNamespace(product=55)

    class FakeDevice:
        @staticmethod
        async def connect(host: str, serial: str) -> object:
            return FakeMatrix()

    monkeypatch.setattr(runner, "Device", FakeDevice)
    monkeypatch.setattr(runner, "MatrixLight", FakeMatrix)
    device = asyncio.run(runner._connect_source_tile(binding))
    assert isinstance(device, FakeMatrix) and close_events == ["enter"]

    targets = tmp_path / "targets.json"
    write_targets(targets, approved_targets())
    monkeypatch.setattr(
        runner, "require_one_authorised_adb_device", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(runner, "load_theme_specs", lambda: {})
    monkeypatch.setattr(
        runner,
        "adb",
        lambda *args, **kwargs: (
            "package:test"
            if args[1] == "pm"
            else "mDreamingLockscreen=false"
            if args[1] == "dumpsys"
            else "1"
        ),
    )
    monkeypatch.setattr(
        runner, "_connect_source_tile", lambda value: asyncio.sleep(0, result=device)
    )

    async def preflight(**kwargs: object) -> runner.PreflightReport:
        return runner.PreflightReport(
            "7.1.0",
            "catalogue",
            {},
            runner.ManualRoleAttestation(
                run_id="opaque",
                operator_attested_role="source-tile",
                binding_digest="digest",
                timestamp="2026-08-16T00:00:00Z",
                operator_attested=True,
                ui_morph_config_observed=True,
                effect_name=True,
                effect_subtitle=True,
                effect_settings=True,
                theme_button=True,
            ),
        )

    monkeypatch.setattr(runner, "run_non_mutating_preflight", preflight)
    assert (
        asyncio.run(
            runner.main(
                ["--targets", str(targets), "--private-root", str(tmp_path / "private")]
            )
        )
        == runner.EXIT_PASS
    )
    assert close_events == ["enter"]
    assert (
        asyncio.run(
            runner.main(
                [
                    "--targets",
                    str(targets),
                    "--private-root",
                    str(tmp_path / "private2"),
                    "--max-theme-scrolls",
                    "-1",
                ]
            )
        )
        == runner.EXIT_INCOMPLETE
    )


def test_remaining_safety_branches_are_executed_with_fakes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """All final failure paths are deterministic and never use a real target."""
    empty = tmp_path / "empty.jsonl"
    empty.write_text("")
    with pytest.raises(runner.PreflightError):
        runner.derive_ceiling_determinations(empty)

    class CeilingFailure:
        async def get_power(self) -> int:
            return 1

        async def get_color(self) -> tuple[HSBK, int, str]:
            return colour(0), 1, "private"

        async def get_effect(self) -> object:
            return off_effect()

        async def get_device_chain(self) -> list[object]:
            return [object()]

        async def get_all_tile_colors(self) -> list[list[HSBK]]:
            return [[colour(0)]]

        async def get_uplight_color(self) -> HSBK:
            raise AttributeError("missing")

        async def get_downlight_colors(self) -> list[HSBK]:
            return [colour(0)]

    with pytest.raises(runner.PreflightError, match="Ceiling"):
        asyncio.run(runner.capture_snapshot(CeilingFailure()))

    timed_out = asyncio.run(
        runner.poll_stable_palette(
            read_palette=lambda: [colour(1)],
            timeout=0.001,
            poll_interval=0.001,
        )
    )
    assert timed_out.stable_palette is None and len(timed_out.observations) == 1

    spec = ThemeSpec("cheerful", "Cheerful", "Moods", [colour(0)], "hash")

    class ReadbackDevice:
        def __init__(self, palettes: list[list[HSBK]]) -> None:
            self.palettes = iter(palettes)

        async def get_effect(self) -> object:
            return SimpleNamespace(palette=next(self.palettes))

        async def set_effect(self, **kwargs: object) -> None:
            return None

    async def save() -> None:
        return None

    async def restored() -> bool:
        return True

    app_timeout = asyncio.run(
        runner.run_tracer_cycle(
            device=ReadbackDevice([[colour(9)]]),
            theme_spec=spec,
            app_save=save,
            restore=restored,
            settings=RunnerSettings(stability_timeout=0, poll_interval=0),
            device_role="source-tile",
        )
    )
    assert app_timeout.failure == "app readback did not stabilise"

    class AlternatingLibraryReadbackDevice:
        def __init__(self) -> None:
            self.calls = 0

        async def get_effect(self) -> object:
            self.calls += 1
            if self.calls <= 2:
                return SimpleNamespace(palette=[colour(0)])
            hue = 9 if self.calls % 2 else 8
            return SimpleNamespace(palette=[colour(hue)])

        async def set_effect(self, **kwargs: object) -> None:
            return None

    library_timeout = asyncio.run(
        runner.run_tracer_cycle(
            device=AlternatingLibraryReadbackDevice(),
            theme_spec=spec,
            app_save=save,
            restore=restored,
            settings=RunnerSettings(stability_timeout=0.003, poll_interval=0.001),
            device_role="source-tile",
        )
    )
    assert library_timeout.failure == "library readback did not stabilise"

    file_path = tmp_path / "permissions"
    file_path.write_text("x")
    monkeypatch.setattr(runner.os, "chmod", lambda *args: None)
    with pytest.raises(runner.PreflightError, match="permissive"):
        runner._chmod(file_path, 0o700)

    app_mismatch = asyncio.run(
        runner.run_tracer_cycle(
            device=ReadbackDevice([[colour(9)], [colour(9)]]),
            theme_spec=spec,
            app_save=save,
            restore=restored,
            settings=RunnerSettings(stability_timeout=1, poll_interval=0),
            device_role="source-tile",
        )
    )
    assert app_mismatch.failure is None
    assert app_mismatch.stable_palette == [colour(9)]
    assert not app_mismatch.matches_expected
    assert [observation.palette for observation in app_mismatch.observations] == [
        [colour(9)],
        [colour(9)],
    ]


def test_target_and_source_identity_rejections_are_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Bad target subshapes and each LAN identity mismatch close their fake device."""
    target_path = tmp_path / "targets.json"
    invalid_fields = approved_targets()
    invalid_fields["source-tile"] = {"host": "x"}
    write_targets(target_path, invalid_fields)
    with pytest.raises(runner.PreflightError):
        runner.load_target_bindings(target_path, private_root=tmp_path / "private")
    invalid_host = approved_targets()
    invalid_host["source-tile"]["host"] = ""  # type: ignore[index]
    write_targets(target_path, invalid_host)
    with pytest.raises(runner.PreflightError):
        runner.load_target_bindings(target_path, private_root=tmp_path / "private2")

    binding = runner.TargetBinding(
        "source-tile", "private", "d073d5000001", "label", True, True
    )
    closed: list[str] = []

    class FakeMatrix:
        label = "wrong"

        async def __aenter__(self) -> None:
            return None

        async def close(self) -> None:
            closed.append("close")

        async def get_version(self) -> object:
            return SimpleNamespace(product=1)

    class FakeDevice:
        @staticmethod
        async def connect(host: str, serial: str) -> object:
            return FakeMatrix()

    monkeypatch.setattr(runner, "Device", FakeDevice)
    monkeypatch.setattr(runner, "MatrixLight", FakeMatrix)
    with pytest.raises(runner.PreflightError, match="identity"):
        asyncio.run(runner._connect_source_tile(binding))
    assert closed == ["close"]
    FakeMatrix.label = "label"
    with pytest.raises(runner.PreflightError, match="product"):
        asyncio.run(runner._connect_source_tile(binding))
    assert closed == ["close", "close"]


def test_last_mismatch_identity_and_cli_error_paths_are_fully_injected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The remaining terminal branches retain failure status without hardware access."""
    spec = ThemeSpec("cheerful", "Cheerful", "Moods", [colour(0)], "hash")

    class MismatchDevice:
        def __init__(self) -> None:
            self.palettes = iter([[colour(0)], [colour(0)], [colour(9)], [colour(9)]])

        async def get_effect(self) -> object:
            return SimpleNamespace(palette=next(self.palettes))

        async def set_effect(self, **kwargs: object) -> None:
            return None

    async def save() -> None:
        return None

    async def restored() -> bool:
        return True

    mismatch = asyncio.run(
        runner.run_tracer_cycle(
            device=MismatchDevice(),
            theme_spec=spec,
            app_save=save,
            restore=restored,
            settings=RunnerSettings(stability_timeout=1, poll_interval=0),
            device_role="source-tile",
        )
    )
    assert mismatch.failure is None

    binding = runner.TargetBinding(
        "source-tile", "private", "d073d5000001", "label", True, True
    )
    closed: list[str] = []

    class NotMatrix:
        async def close(self) -> None:
            closed.append("close")

    class FakeDevice:
        @staticmethod
        async def connect(host: str, serial: str) -> object:
            return NotMatrix()

    monkeypatch.setattr(runner, "Device", FakeDevice)
    monkeypatch.setattr(runner, "MatrixLight", type("Matrix", (), {}))
    with pytest.raises(runner.PreflightError, match="not a matrix"):
        asyncio.run(runner._connect_source_tile(binding))
    assert closed == ["close"]

    targets = tmp_path / "targets.json"
    write_targets(targets, approved_targets())
    monkeypatch.setattr(
        runner, "require_one_authorised_adb_device", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(runner, "load_theme_specs", lambda: {})
    monkeypatch.setattr(runner, "adb", lambda *args, **kwargs: "not-package")
    assert (
        asyncio.run(
            runner.main(
                ["--targets", str(targets), "--private-root", str(tmp_path / "private")]
            )
        )
        == runner.EXIT_INCOMPLETE
    )
    monkeypatch.setattr(
        runner,
        "adb",
        lambda *args, **kwargs: (
            "package:test" if len(args) > 1 and args[1] == "pm" else "locked"
        ),
    )
    assert (
        asyncio.run(
            runner.main(
                [
                    "--targets",
                    str(targets),
                    "--private-root",
                    str(tmp_path / "private2"),
                ]
            )
        )
        == runner.EXIT_INCOMPLETE
    )
    monkeypatch.setattr(
        runner,
        "load_target_bindings",
        lambda *args, **kwargs: (_ for _ in ()).throw(runner.RestorationError("x")),
    )
    assert (
        asyncio.run(
            runner.main(
                [
                    "--targets",
                    str(targets),
                    "--private-root",
                    str(tmp_path / "private3"),
                ]
            )
        )
        == runner.EXIT_RESTORATION_FAILURE
    )


def test_preflight_checkpoint_and_official_schedule_are_fully_injected(
    tmp_path: Path,
) -> None:
    """The run lifecycle has deterministic private persistence and no hardware calls."""
    specs = runner.load_theme_specs()
    provenance = runner.build_provenance(
        runner_revision="revision",
        app_version="version",
        catalogue="catalogue",
        target_fingerprints={"source-tile": "a", "non-tile-matrix": "b"},
        firmware_by_role={"source-tile": "one", "non-tile-matrix": "two"},
        theme_specs=specs,
        settings=RunnerSettings(),
    )
    bindings = {
        "source-tile": runner.TargetBinding(
            "source-tile", "private", "d073d5000001", "tile", True, True
        ),
        "non-tile-matrix": runner.TargetBinding(
            "non-tile-matrix", "private", "d073d5000002", "ceiling", True, True
        ),
    }
    metadata = {
        "source-tile": {"product_id": 55, "is_matrix": True},
        "non-tile-matrix": {
            "product_id": 100,
            "is_matrix": True,
            "indoor": True,
            "model": "LIFX Ceiling",
        },
    }
    runner.run_preflight(
        bindings=bindings,
        metadata_by_role=metadata,
        theme_specs=specs,
        provenance=provenance,
    )
    checkpoint_path = tmp_path / "private" / "checkpoint.json"
    checkpoint = runner.RunCheckpoint(
        "opaque", provenance, runner.build_cycle_schedule()[0], [], None, False
    )
    runner.write_checkpoint(checkpoint_path, checkpoint)
    loaded = runner.load_checkpoint(checkpoint_path)
    assert loaded["run_id"] == "opaque"
    assert checkpoint_path.stat().st_mode & 0o777 == 0o600

    calls: list[tuple[str, str, int]] = []

    async def callback(role: str, spec: ThemeSpec, index: int) -> CycleResult:
        calls.append((role, spec.slug, index))
        source = "app" if len(calls) % 2 else "library"
        return CycleResult(role, spec.slug, source, index, [], [], False, "mismatch")

    async def app(role: str, spec: ThemeSpec, index: int) -> CycleResult:
        calls.append((role, spec.slug, index))
        return CycleResult(role, spec.slug, "app", index, [], [], False, "mismatch")

    async def library(role: str, spec: ThemeSpec, index: int) -> CycleResult:
        calls.append((role, spec.slug, index))
        return CycleResult(role, spec.slug, "library", index, [], [], False, "mismatch")

    results = asyncio.run(
        runner.run_official_cycles(
            theme_specs=specs, completed={}, app_cycle=app, library_cycle=library
        )
    )
    assert len(results) == 24 and len(calls) == 24
    assert results[0].source == "app" and results[6].source == "library"
    with pytest.raises(runner.PreflightError):
        asyncio.run(
            runner.run_official_cycles(
                theme_specs=specs,
                completed={},
                app_cycle=callback,
                library_cycle=callback,
            )
        )


@pytest.mark.parametrize(
    "mode",
    [
        "bad_bindings",
        "unquiesced",
        "bad_source",
        "missing_non_tile",
        "bad_provenance",
    ],
)
def test_preflight_rejects_each_missing_safety_boundary(mode: str) -> None:
    """No incomplete target/provenance boundary may enter the sequential runner."""
    specs = runner.load_theme_specs()
    provenance = runner.build_provenance(
        runner_revision="revision",
        app_version="version",
        catalogue="catalogue",
        target_fingerprints={},
        firmware_by_role={},
        theme_specs=specs,
        settings=RunnerSettings(),
    )
    bindings = {
        "source-tile": runner.TargetBinding(
            "source-tile", "private", "d073d5000001", "tile", True, True
        ),
        "non-tile-matrix": runner.TargetBinding(
            "non-tile-matrix", "private", "d073d5000002", "ceiling", True, True
        ),
    }
    metadata: dict[str, dict[str, object]] = {
        "source-tile": {"product_id": 55, "is_matrix": True},
        "non-tile-matrix": {
            "product_id": 100,
            "is_matrix": True,
            "indoor": True,
            "model": "LIFX Ceiling",
        },
    }
    if mode == "bad_bindings":
        bindings = {"source-tile": bindings["source-tile"]}
    elif mode == "unquiesced":
        bindings["source-tile"] = runner.TargetBinding(
            "source-tile", "private", "d073d5000001", "tile", True, False
        )
    elif mode == "bad_source":
        metadata["source-tile"] = {"product_id": 1, "is_matrix": False}
    elif mode == "missing_non_tile":
        del metadata["non-tile-matrix"]
    else:
        provenance = runner.RunProvenance(
            **{**provenance.__dict__, "catalogue_fingerprint": ""}
        )
    with pytest.raises(runner.PreflightError):
        runner.run_preflight(
            bindings=bindings,
            metadata_by_role=metadata,
            theme_specs=specs,
            provenance=provenance,
        )


def test_checkpoint_cycle_evidence_round_trips_as_a_strict_schedule_prefix(
    tmp_path: Path,
) -> None:
    """Private resume data retains palette polls and cannot invent a partial prefix."""
    _bindings, _specs, provenance = _lifecycle_inputs()
    schedule = runner.build_cycle_schedule()
    source_cycles = [
        runner.CycleResult(
            *key,
            [
                runner.PaletteObservation(0.0, [colour(0), colour(120)]),
                runner.PaletteObservation(0.25, [colour(120), colour(0)]),
            ],
            [colour(120), colour(0)],
            index != 2,
            None,
        )
        for role, slug, source, index in schedule[:12]
        for key in [(role, slug, source, index)]
    ]
    checkpoint = runner.RunCheckpoint(
        "opaque", provenance, schedule[12], source_cycles, None, False
    )
    path = tmp_path / "private" / "checkpoint.json"
    runner.write_checkpoint(path, checkpoint)
    loaded = runner.load_checkpoint(path)

    completed = runner.completed_cycles_from_checkpoint(
        loaded["cycles"], loaded["next_cycle"]
    )

    assert list(completed) == schedule[:12]
    restored = completed[schedule[2]]
    assert [item.monotonic_offset for item in restored.observations] == [0.0, 0.25]
    assert [colour.as_tuple() for colour in restored.stable_palette or []] == [
        colour(120).as_tuple(),
        colour(0).as_tuple(),
    ]
    assert not restored.matches_expected
    assert restored.failure is None
    assert path.stat().st_mode & 0o777 == 0o600

    async def app(role: str, spec: ThemeSpec, index: int) -> CycleResult:
        return CycleResult(role, spec.slug, "app", index, [], None, True, None)

    async def library(role: str, spec: ThemeSpec, index: int) -> CycleResult:
        return CycleResult(role, spec.slug, "library", index, [], None, True, None)

    resumed_cycles = asyncio.run(
        runner.run_official_cycles(
            theme_specs=runner.load_theme_specs(),
            completed=completed,
            app_cycle=app,
            library_cycle=library,
        )
    )
    public = runner.build_public_results(
        run_id="opaque",
        provenance=provenance,
        theme_specs=runner.load_theme_specs(),
        devices=[
            runner.PublicDeviceRecord(
                "source-tile", "MatrixLight", "LIFX Tile", 55, "1.0"
            ),
            runner.PublicDeviceRecord(
                "non-tile-matrix", "CeilingLight", "LIFX Ceiling", 100, "1.0"
            ),
        ],
        cycles=resumed_cycles,
        restorations=[
            runner.RestorationResult("source-tile", True, True, True, None),
            runner.RestorationResult("non-tile-matrix", True, True, True, None),
        ],
        outcome="mismatch",
        completed_at_utc="2026-08-16T00:00:00Z",
    )
    assert [
        (item.device_role, item.theme_slug, item.source, item.cycle_index)
        for item in resumed_cycles
    ] == schedule
    assert public["cycles"][2]["poll_count"] == 2  # type: ignore[index]
    assert public["cycles"][2]["matches_expected"] is False  # type: ignore[index]

    malformed = dict(loaded)
    malformed_cycles = list(loaded["cycles"])
    malformed_cycles[0] = {
        **malformed_cycles[0],
        "observations": [{"monotonic_offset": 0.0}],
    }
    malformed["cycles"] = malformed_cycles
    with pytest.raises(runner.PreflightError):
        runner.completed_cycles_from_checkpoint(
            malformed["cycles"], malformed["next_cycle"]
        )
    for invalid in (
        {**loaded["cycles"][0], "unexpected": "private"},
        {**loaded["cycles"][0], "cycle_index": True},
        {**loaded["cycles"][0], "source": "unknown"},
        {**loaded["cycles"][0], "stable_palette": "not-a-palette"},
        {
            **loaded["cycles"][0],
            "observations": [
                {"monotonic_offset": 1.0, "palette": [[0, 0, 0, 3500]]},
                {"monotonic_offset": 0.5, "palette": [[0, 0, 0, 3500]]},
            ],
        },
        {
            **loaded["cycles"][0],
            "observations": [{"monotonic_offset": -1.0, "palette": [[0, 0, 0, 3500]]}],
        },
        {
            **loaded["cycles"][0],
            "stable_palette": [[65536, 0, 0, 3500]],
        },
        {
            **loaded["cycles"][0],
            "stable_palette": [[True, 0, 0, 3500]],
        },
        {
            **loaded["cycles"][0],
            "stable_palette": [[0, 0, 0, 1]],
        },
    ):
        with pytest.raises(runner.PreflightError):
            runner.cycle_from_checkpoint_record(invalid)
    with pytest.raises(runner.PreflightError):
        runner.completed_cycles_from_checkpoint(
            list(reversed(loaded["cycles"])), loaded["next_cycle"]
        )
    with pytest.raises(runner.PreflightError):
        runner.completed_cycles_from_checkpoint(loaded["cycles"], list(schedule[7]))
    with pytest.raises(runner.PreflightError):
        runner.completed_cycles_from_checkpoint("not-a-list", loaded["next_cycle"])
    with pytest.raises(runner.PreflightError):
        runner.completed_cycles_from_checkpoint([], ["source-tile", "cheerful"])
    with pytest.raises(runner.PreflightError):
        runner.completed_cycles_from_checkpoint(
            [loaded["cycles"][0], loaded["cycles"][0]], loaded["next_cycle"]
        )
    with pytest.raises(runner.PreflightError):
        runner._validate_completed_cycle_prefix(
            {
                ("source-tile", "cheerful", "app", 1): runner.CycleResult(
                    "source-tile", "cheerful", "app", 1, [], None, True, None
                )
            }
        )
    with pytest.raises(runner.PreflightError):
        runner._validate_completed_cycle_prefix(
            {
                schedule[0]: runner.CycleResult(
                    *schedule[0], [], None, False, "app readback did not stabilise"
                )
            }
        )
    final_records = [
        runner._cycle_to_record(runner.CycleResult(*key, [], None, True, None))
        for key in schedule
    ]
    assert runner.completed_cycles_from_checkpoint(final_records, None)


def test_checkpoint_keeps_terminal_incomplete_cycle_private_and_strict(
    tmp_path: Path,
) -> None:
    """A terminal failed key is diagnostic-only and cannot weaken checkpoint schema."""
    _bindings, _specs, provenance = _lifecycle_inputs()
    key = runner.build_cycle_schedule()[0]
    terminal = runner.CycleResult(
        *key, [], None, False, "app readback did not stabilise"
    )
    path = tmp_path / "private" / "checkpoint.json"
    runner.write_checkpoint(
        path,
        runner.RunCheckpoint(
            "opaque", provenance, key, [], "incomplete", False, terminal_cycle=terminal
        ),
    )
    loaded = runner.load_checkpoint(path)
    assert loaded["cycles"] == []
    assert runner.cycle_from_checkpoint_record(loaded["terminal_cycle"]) == terminal
    malformed = dict(loaded)
    malformed["terminal_cycle"] = "not-a-cycle"
    path.write_text(json.dumps(malformed))
    with pytest.raises(runner.PreflightError):
        runner.load_checkpoint(path)


def test_checkpoint_and_schedule_error_branches_remain_private(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Partial writes and skipped completed keys cannot alter a frozen private run."""
    specs = runner.load_theme_specs()
    provenance = runner.build_provenance(
        runner_revision="revision",
        app_version="version",
        catalogue="catalogue",
        target_fingerprints={},
        firmware_by_role={},
        theme_specs=specs,
        settings=RunnerSettings(),
    )
    first_key = runner.build_cycle_schedule()[0]
    first = CycleResult(*first_key, [], [], True, None)
    checkpoint = runner.RunCheckpoint(
        "opaque", provenance, first_key, [first], None, False
    )
    checkpoint_path = tmp_path / "private" / "checkpoint.json"
    runner.write_checkpoint(checkpoint_path, checkpoint)
    assert (
        runner.load_checkpoint(checkpoint_path)["cycles"][0]["theme_slug"] == "mondrian"
    )  # type: ignore[index]
    with pytest.raises(runner.PreflightError):
        runner.load_checkpoint(tmp_path / "missing.json")
    checkpoint_path.write_text("{}")
    with pytest.raises(runner.PreflightError):
        runner.load_checkpoint(checkpoint_path)
    checkpoint_path.write_text(
        json.dumps(
            {
                "run_id": "opaque",
                "provenance": {},
                "next_cycle": None,
                "cycles": "invalid",
                "terminal_status": None,
                "finalisable": False,
            }
        )
    )
    with pytest.raises(runner.PreflightError):
        runner.load_checkpoint(checkpoint_path)

    failing = tmp_path / "failing" / "checkpoint.json"
    monkeypatch.setattr(
        runner.os, "replace", lambda *args: (_ for _ in ()).throw(OSError())
    )
    with pytest.raises(runner.PreflightError):
        runner.write_checkpoint(failing, checkpoint)
    assert not failing.with_suffix(".json.tmp").exists()

    bindings = {
        "source-tile": runner.TargetBinding(
            "source-tile", "private", "d073d5000001", "tile", True, True
        ),
        "non-tile-matrix": runner.TargetBinding(
            "non-tile-matrix", "private", "d073d5000002", "ceiling", True, True
        ),
    }
    metadata = {
        "source-tile": {"product_id": 55, "is_matrix": True},
        "non-tile-matrix": {
            "product_id": 100,
            "is_matrix": True,
            "indoor": True,
            "model": "LIFX Ceiling",
        },
    }
    with pytest.raises(runner.PreflightError):
        runner.run_preflight(
            bindings=bindings,
            metadata_by_role=metadata,
            theme_specs={},
            provenance=provenance,
        )

    calls: list[int] = []

    async def app(role: str, spec: ThemeSpec, index: int) -> CycleResult:
        calls.append(index)
        return CycleResult(role, spec.slug, "app", index, [], [], True, None)

    async def library(role: str, spec: ThemeSpec, index: int) -> CycleResult:
        calls.append(index)
        return CycleResult(role, spec.slug, "library", index, [], [], True, None)

    results = asyncio.run(
        runner.run_official_cycles(
            theme_specs=specs,
            completed={first_key: first},
            app_cycle=app,
            library_cycle=library,
        )
    )
    assert len(results) == 24 and len(calls) == 23


def _lifecycle_inputs() -> tuple[
    dict[str, runner.TargetBinding], dict[str, runner.ThemeSpec], runner.RunProvenance
]:
    """Return the private, two-role inputs used by injected lifecycle tests."""
    specs = runner.load_theme_specs()
    bindings = {
        "source-tile": runner.TargetBinding(
            "source-tile", "private", "d073d5000001", "tile", True, True
        ),
        "non-tile-matrix": runner.TargetBinding(
            "non-tile-matrix", "private", "d073d5000002", "ceiling", True, True
        ),
    }
    provenance = runner.build_provenance(
        runner_revision="revision",
        app_version="version",
        catalogue="catalogue",
        target_fingerprints={"source-tile": "one", "non-tile-matrix": "two"},
        firmware_by_role={"source-tile": "one", "non-tile-matrix": "two"},
        theme_specs=specs,
        settings=runner.RunnerSettings(),
    )
    return bindings, specs, provenance


def test_resume_can_finish_library_keys_but_stops_before_unattested_app_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A library-only resume cannot implicitly authorise the following app cycle."""
    bindings, specs, provenance = _lifecycle_inputs()
    snapshot = runner.RestorationSnapshot(
        0,
        colour(0),
        runner.EffectSnapshot(runner.FirmwareEffect.OFF, 0, 0, None, None, 0, 0),
        [object()],
        [[colour(0)]],
        None,
        None,
    )
    saved: list[str] = []
    library_keys: list[runner.CycleKey] = []

    class Adapter:
        async def connect(self, binding: runner.TargetBinding) -> object:
            return SimpleNamespace(role=binding.role)

        async def metadata(
            self, binding: runner.TargetBinding, device: object
        ) -> dict[str, object]:
            return {
                "product_id": 55 if binding.role == "source-tile" else 100,
                "is_matrix": True,
                "indoor": True,
                "emulator": False,
                "device_class": (
                    "MatrixLight" if binding.role == "source-tile" else "CeilingLight"
                ),
                "model": "LIFX Tile"
                if binding.role == "source-tile"
                else "LIFX Ceiling",
            }

        async def close(self, device: object) -> None:
            return None

    class Store:
        def __init__(self) -> None:
            self.items: list[runner.RunCheckpoint] = []

        def write(self, path: Path, checkpoint: runner.RunCheckpoint) -> None:
            self.items.append(checkpoint)

        def load(self, path: Path) -> dict[str, object]:
            raise AssertionError("not used")

    async def capture(device: object) -> runner.RestorationSnapshot:
        return snapshot

    async def restore(device: object, snap: object, *, poll_interval: float) -> bool:
        return True

    async def verify(device: object, snap: object) -> bool:
        return True

    async def forbidden_save(*args: object, **kwargs: object) -> None:
        saved.append("called")

    monkeypatch.setattr(runner, "capture_snapshot", capture)
    monkeypatch.setattr(runner, "restore_snapshot", restore)
    monkeypatch.setattr(runner, "verify_restoration", verify)
    monkeypatch.setattr(runner, "semantic_app_save", forbidden_save)

    async def app(
        role: str, spec: runner.ThemeSpec, index: int, device: object
    ) -> runner.CycleResult:
        return await runner._production_app_cycle(
            role,
            spec,
            index,
            device,
            binding=bindings[role],
            settings=runner.RunnerSettings(),
            run_directory=tmp_path,
            run_id="opaque",
            timestamp="2026-08-16T00:00:00Z",
            attested_role=None,
        )

    async def library(
        role: str, spec: runner.ThemeSpec, index: int, device: object
    ) -> runner.CycleResult:
        key = (role, spec.slug, "library", index)
        library_keys.append(key)
        return runner.CycleResult(*key, [], [], True, None)

    completed = {
        key: runner.CycleResult(*key, [], [], True, None)
        for key in runner.build_cycle_schedule()[:6]
    }
    store = Store()
    result = asyncio.run(
        runner.run_designated_lifecycle(
            run_id="opaque",
            bindings=bindings,
            theme_specs=specs,
            provenance=provenance,
            device_adapter=Adapter(),  # type: ignore[arg-type]
            checkpoint_store=store,  # type: ignore[arg-type]
            checkpoint_path=tmp_path / "checkpoint.json",
            app_cycle=app,
            library_cycle=library,
            completed=completed,
        )
    )

    assert library_keys == runner.build_cycle_schedule()[6:12]
    assert saved == []
    assert result.outcome == "incomplete"
    assert store.items[-1].next_cycle == runner.build_cycle_schedule()[12]


def test_designated_lifecycle_runs_all_cycles_checkpoints_and_restores(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The actual two-device lifecycle is sequential, resumable and fully injected."""
    bindings, specs, provenance = _lifecycle_inputs()
    snapshot = runner.RestorationSnapshot(
        0,
        colour(0),
        runner.EffectSnapshot(runner.FirmwareEffect.OFF, 0, 0, None, None, 0, 0),
        [object()],
        [[colour(0)]],
        None,
        None,
    )
    events: list[str] = []

    class Devices:
        async def connect(self, binding: runner.TargetBinding) -> object:
            events.append(f"connect:{binding.role}")
            return SimpleNamespace(role=binding.role)

        async def metadata(
            self, binding: runner.TargetBinding, device: object
        ) -> dict[str, object]:
            return {
                "product_id": 55 if binding.role == "source-tile" else 100,
                "is_matrix": True,
                "indoor": True,
                "emulator": False,
                "device_class": (
                    "MatrixLight" if binding.role == "source-tile" else "CeilingLight"
                ),
                "model": "LIFX Tile"
                if binding.role == "source-tile"
                else "LIFX Ceiling",
            }

        async def close(self, device: object) -> None:
            events.append(f"close:{device.role}")  # type: ignore[attr-defined]

    class Store:
        def __init__(self) -> None:
            self.items: list[runner.RunCheckpoint] = []

        def write(self, path: Path, checkpoint: runner.RunCheckpoint) -> None:
            self.items.append(checkpoint)

        def load(self, path: Path) -> dict[str, object]:
            raise AssertionError("not used")

    async def capture(device: object) -> runner.RestorationSnapshot:
        events.append(f"snapshot:{device.role}")  # type: ignore[attr-defined]
        return snapshot

    async def restore(device: object, snap: object, *, poll_interval: float) -> bool:
        events.append(f"restore:{device.role}")  # type: ignore[attr-defined]
        return True

    async def verify(device: object, snap: object) -> bool:
        events.append(f"verify:{device.role}")  # type: ignore[attr-defined]
        return True

    monkeypatch.setattr(runner, "capture_snapshot", capture)
    monkeypatch.setattr(runner, "restore_snapshot", restore)
    monkeypatch.setattr(runner, "verify_restoration", verify)

    async def app(
        role: str, spec: runner.ThemeSpec, index: int, device: object
    ) -> runner.CycleResult:
        events.append(f"cycle:{role}:{spec.slug}:app:{index}")
        return runner.CycleResult(
            role, spec.slug, "app", index, [], [colour(0)], True, None
        )

    async def library(
        role: str, spec: runner.ThemeSpec, index: int, device: object
    ) -> runner.CycleResult:
        events.append(f"cycle:{role}:{spec.slug}:library:{index}")
        return runner.CycleResult(
            role, spec.slug, "library", index, [], [colour(0)], True, None
        )

    async def activate(role: str, device: object) -> None:
        events.append(f"activate:{role}")

    store = Store()
    result = asyncio.run(
        runner.run_designated_lifecycle(
            run_id="opaque",
            bindings=bindings,
            theme_specs=specs,
            provenance=provenance,
            device_adapter=Devices(),  # type: ignore[arg-type]
            checkpoint_store=store,  # type: ignore[arg-type]
            checkpoint_path=tmp_path / "checkpoint.json",
            app_cycle=app,
            library_cycle=library,
            activate_morph=activate,  # type: ignore[arg-type]
        )
    )
    assert result.outcome == "pass" and result.finalisable and len(result.cycles) == 24
    assert len(store.items) == 26
    assert store.items[-1].snapshots and all(
        item.verified for item in result.restorations
    )
    assert (
        events.index("snapshot:source-tile")
        < events.index("activate:source-tile")
        < events.index("cycle:source-tile:mondrian:app:1")
    )
    assert [event for event in events if event.startswith("cycle:source-tile")] == [
        f"cycle:{role}:{slug}:{source}:{index}"
        for role, slug, source, index in runner.build_cycle_schedule()[:12]
    ]
    source_app_events = [
        event
        for event in events
        if event == "activate:source-tile"
        or event.startswith("cycle:source-tile:")
        and ":app:" in event
    ]
    assert source_app_events == [
        "activate:source-tile",
        "cycle:source-tile:mondrian:app:1",
        "cycle:source-tile:cheerful:app:1",
        "cycle:source-tile:mondrian:app:2",
        "cycle:source-tile:cheerful:app:2",
        "cycle:source-tile:mondrian:app:3",
        "cycle:source-tile:cheerful:app:3",
    ]
    assert events.count("activate:source-tile") == 1
    assert events.count("activate:non-tile-matrix") == 1
    assert events[-6:] == [
        "restore:source-tile",
        "verify:source-tile",
        "restore:non-tile-matrix",
        "verify:non-tile-matrix",
        "close:source-tile",
        "close:non-tile-matrix",
    ]


def test_lifecycle_retains_mismatch_and_marks_restore_or_preflight_faults(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mismatch continues, while failure to snapshot/restore cannot be finalised."""
    bindings, specs, provenance = _lifecycle_inputs()
    snapshot = runner.RestorationSnapshot(
        0,
        colour(0),
        runner.EffectSnapshot(runner.FirmwareEffect.OFF, 0, 0, None, None, 0, 0),
        [object()],
        [[colour(0)]],
        None,
        None,
    )

    class Adapter:
        async def connect(self, binding: runner.TargetBinding) -> object:
            return SimpleNamespace(role=binding.role)

        async def metadata(
            self, binding: runner.TargetBinding, device: object
        ) -> dict[str, object]:
            return {
                "product_id": 55 if binding.role == "source-tile" else 100,
                "is_matrix": True,
                "indoor": True,
                "emulator": False,
                "device_class": (
                    "MatrixLight" if binding.role == "source-tile" else "CeilingLight"
                ),
                "model": "LIFX Tile"
                if binding.role == "source-tile"
                else "LIFX Ceiling",
            }

        async def close(self, device: object) -> None:
            if device.role == "non-tile-matrix":  # type: ignore[attr-defined]
                raise RuntimeError("close")

    class Store:
        def write(self, path: Path, checkpoint: runner.RunCheckpoint) -> None:
            return None

        def load(self, path: Path) -> dict[str, object]:
            return {}

    async def capture(device: object) -> runner.RestorationSnapshot:
        return snapshot

    async def restore(device: object, snap: object, *, poll_interval: float) -> bool:
        return device.role == "source-tile"  # type: ignore[attr-defined]

    async def verify(device: object, snap: object) -> bool:
        return True

    monkeypatch.setattr(runner, "capture_snapshot", capture)
    monkeypatch.setattr(runner, "restore_snapshot", restore)
    monkeypatch.setattr(runner, "verify_restoration", verify)

    async def app(
        role: str, spec: runner.ThemeSpec, index: int, device: object
    ) -> runner.CycleResult:
        return runner.CycleResult(
            role, spec.slug, "app", index, [], [colour(120)], False, None
        )

    async def library(
        role: str, spec: runner.ThemeSpec, index: int, device: object
    ) -> runner.CycleResult:
        return runner.CycleResult(
            role, spec.slug, "library", index, [], [colour(120)], False, None
        )

    result = asyncio.run(
        runner.run_designated_lifecycle(
            run_id="opaque",
            bindings=bindings,
            theme_specs=specs,
            provenance=provenance,
            device_adapter=Adapter(),
            checkpoint_store=Store(),
            checkpoint_path=tmp_path / "checkpoint.json",
            app_cycle=app,
            library_cycle=library,
        )
    )  # type: ignore[arg-type]
    assert len(result.cycles) == 24
    assert result.outcome == "restoration_failure" and not result.finalisable


def test_production_adapters_cycles_and_private_finalisation_are_fakeable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Concrete ADB/LAN/file adapters are tested only against local fakes."""
    monkeypatch.setattr(runner, "adb", lambda *args, **kwargs: "ok")
    assert runner.ProductionAdbAdapter().command("shell", "true", timeout=1) == "ok"
    assert runner.ProductionClockAdapter().utc_now().endswith("Z")

    class Matrix:
        label = "safe"

        def __init__(self) -> None:
            self.closed = False

        async def __aenter__(self) -> None:
            return None

        async def close(self) -> None:
            self.closed = True

        async def get_version(self) -> object:
            return SimpleNamespace(product=100, version="1.2")

    class FakeDevice:
        @staticmethod
        async def connect(host: str, serial: str) -> object:
            return Matrix()

    binding = runner.TargetBinding(
        "non-tile-matrix", "private", "d073d5000002", "safe", True, True
    )
    monkeypatch.setattr(runner, "Device", FakeDevice)
    monkeypatch.setattr(runner, "MatrixLight", Matrix)
    adapter = runner.ProductionDeviceAdapter()
    device = asyncio.run(adapter.connect(binding))
    metadata = asyncio.run(adapter.metadata(binding, device))
    assert metadata["product_id"] == 100 and metadata["is_matrix"] is False

    class MissingProduct:
        async def get_version(self) -> object:
            return SimpleNamespace(product=None)

    with pytest.raises(runner.PreflightError):
        asyncio.run(adapter.metadata(binding, MissingProduct()))
    asyncio.run(adapter.close(device))
    assert device.closed  # type: ignore[attr-defined]
    Matrix.label = "wrong"
    with pytest.raises(runner.PreflightError, match="label"):
        asyncio.run(adapter.connect(binding))

    filesystem = runner.ProductionFileSystemAdapter()
    directory = tmp_path / "output"
    filesystem.mkdir(directory)
    source = directory / "source"
    destination = directory / "destination"
    filesystem.write_text(source, "value", 0o600)
    assert filesystem.read_text(source) == "value"
    filesystem.replace(source, destination)
    filesystem.unlink(destination)
    filesystem.unlink(destination)

    specs = runner.load_theme_specs()
    spec = specs["cheerful"]
    saved: list[str] = []

    async def save(*args: object, **kwargs: object) -> None:
        saved.append("save")

    monkeypatch.setattr(runner, "semantic_app_save", save)

    class EffectDevice:
        def __init__(self) -> None:
            self.calls = 0
            self.effect_calls: list[object] = []

        async def get_effect(self) -> object:
            self.calls += 1
            return SimpleNamespace(palette=spec.expected_palette)

        async def set_effect(self, **kwargs: object) -> None:
            self.effect_calls.append(kwargs["effect_type"])

    effect_device = EffectDevice()
    app = asyncio.run(
        runner._production_app_cycle(
            "source-tile",
            spec,
            1,
            effect_device,
            binding=runner.TargetBinding(
                "source-tile", "private", "d073d5000001", "safe", True, True
            ),
            settings=runner.RunnerSettings(stability_timeout=1, poll_interval=0),
            run_directory=tmp_path,
            run_id="opaque",
            timestamp="2026-08-16T00:00:00Z",
            attested_role="source-tile",
            attested_initial_theme="cheerful",
        )
    )
    library = asyncio.run(
        runner._production_library_cycle(
            "source-tile",
            spec,
            1,
            effect_device,
            settings=runner.RunnerSettings(stability_timeout=1, poll_interval=0),
        )
    )
    assert app.matches_expected and library.matches_expected and saved == ["save"]
    assert effect_device.effect_calls == [runner.FirmwareEffect.MORPH]

    result_file = tmp_path / "result.json"
    result_file.write_text(
        json.dumps({"finalisable": True, "public_results": public_results()})
    )
    writer_calls: list[dict[str, object]] = []

    class Writer:
        def write(
            self, results: dict[str, object], *, output_directory: Path
        ) -> tuple[Path, Path]:
            writer_calls.append(results)
            return output_directory / "one", output_directory / "two"

    assert runner.finalise_private_results(
        result_file, output_directory=tmp_path, evidence_writer=Writer()
    ) == (tmp_path / "one", tmp_path / "two")  # type: ignore[arg-type]
    assert (
        writer_calls
        and runner.validate_evidence_file(
            tmp_path / "evidence.json",
            filesystem=type(
                "FS", (), {"read_text": lambda self, path: json.dumps(public_results())}
            )(),
        )
        is None
    )  # type: ignore[arg-type]
    result_file.write_text("not-json")
    with pytest.raises(runner.PreflightError):
        runner.finalise_private_results(result_file, output_directory=tmp_path)


def test_production_initial_connect_retries_only_a_fresh_read_only_contact(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """One fresh contact retry cannot mask partial or identity failures."""
    binding = runner.TargetBinding(
        "source-tile", "private-host", "d073d5000001", "safe", True, True
    )

    class Matrix:
        label = "safe"

        def __init__(self, *, timeout_on_enter: bool = False) -> None:
            self.timeout_on_enter = timeout_on_enter
            self.closed = False

        async def __aenter__(self) -> None:
            if self.timeout_on_enter:
                raise runner.LifxTimeoutError("private-host")

        async def close(self) -> None:
            self.closed = True

    monkeypatch.setattr(runner, "MatrixLight", Matrix)
    first = Matrix()
    second = Matrix()
    calls: list[str] = []

    async def first_success(host: str, serial: str) -> object:
        calls.append(host)
        return first

    assert (
        asyncio.run(
            runner.ProductionDeviceAdapter(device_factory=first_success).connect(
                binding
            )
        )
        is first
    )
    assert calls == ["private-host"]
    calls.clear()

    async def timeout_then_success(host: str, serial: str) -> object:
        calls.append(host)
        if len(calls) == 1:
            raise runner.LifxTimeoutError("private-host")
        return second

    contact_events: list[tuple[str, str, str]] = []
    adapter = runner.ProductionDeviceAdapter(
        device_factory=timeout_then_success,
        contact_observer=lambda role, stage, status: contact_events.append(
            (role, stage, status)
        ),
    )
    assert asyncio.run(adapter.connect(binding)) is second
    assert calls == ["private-host", "private-host"]
    assert contact_events == [("source-tile", "contact", "retrying")]
    assert not first.closed and not second.closed

    partial = Matrix(timeout_on_enter=True)
    replacement = Matrix()
    partial_calls: list[str] = []

    async def partial_timeout_then_success(host: str, serial: str) -> object:
        partial_calls.append(host)
        return partial if len(partial_calls) == 1 else replacement

    assert (
        asyncio.run(
            runner.ProductionDeviceAdapter(
                device_factory=partial_timeout_then_success
            ).connect(binding)
        )
        is replacement
    )
    assert partial.closed and partial_calls == ["private-host", "private-host"]

    class BrokenClose(Matrix):
        async def close(self) -> None:
            raise runner.LifxConnectionError("private-host")

    broken_close = BrokenClose(timeout_on_enter=True)
    close_failure_calls: list[str] = []

    async def close_failure_then_success(host: str, serial: str) -> object:
        close_failure_calls.append(host)
        return broken_close if len(close_failure_calls) == 1 else Matrix()

    asyncio.run(
        runner.ProductionDeviceAdapter(
            device_factory=close_failure_then_success
        ).connect(binding)
    )
    assert close_failure_calls == ["private-host", "private-host"]

    two_timeout_calls: list[str] = []

    async def always_timeout(host: str, serial: str) -> object:
        two_timeout_calls.append(host)
        raise runner.LifxTimeoutError("private-host")

    with pytest.raises(runner.PreflightError, match="contact") as error:
        asyncio.run(
            runner.ProductionDeviceAdapter(device_factory=always_timeout).connect(
                binding
            )
        )
    assert "private-host" not in str(error.value)
    assert two_timeout_calls == ["private-host", "private-host"]

    class MetadataTimeout:
        calls = 0

        async def get_version(self) -> object:
            self.calls += 1
            raise runner.LifxTimeoutError("private-host")

    metadata_timeout = MetadataTimeout()
    with pytest.raises(runner.LifxTimeoutError):
        asyncio.run(adapter.metadata(binding, metadata_timeout))
    assert metadata_timeout.calls == 1

    mismatch = Matrix()
    mismatch.label = "wrong"
    mismatch_calls: list[str] = []

    async def mismatched_label(host: str, serial: str) -> object:
        mismatch_calls.append(host)
        return mismatch

    with pytest.raises(runner.PreflightError, match="label"):
        asyncio.run(
            runner.ProductionDeviceAdapter(device_factory=mismatched_label).connect(
                binding
            )
        )
    assert mismatch.closed and mismatch_calls == ["private-host"]

    class NotMatrix:
        async def close(self) -> None:
            return None

    type_calls: list[str] = []

    async def wrong_type(host: str, serial: str) -> object:
        type_calls.append(host)
        return NotMatrix()

    with pytest.raises(runner.PreflightError, match="matrix"):
        asyncio.run(
            runner.ProductionDeviceAdapter(device_factory=wrong_type).connect(binding)
        )
    assert type_calls == ["private-host"]

    targets = tmp_path / "targets.json"
    write_targets(targets, approved_targets())

    async def preflight_timeout(**kwargs: object) -> runner.PreflightReport:
        raise runner.LifxTimeoutError("private-host")

    monkeypatch.setattr(runner, "load_theme_specs", lambda: {})
    monkeypatch.setattr(runner, "run_non_mutating_preflight", preflight_timeout)
    assert (
        asyncio.run(
            runner.main(
                [
                    "--targets",
                    str(targets),
                    "--private-root",
                    str(tmp_path / "private"),
                    "--preflight-only",
                    "--attest-role",
                    "source-tile",
                ]
            )
        )
        == runner.EXIT_INCOMPLETE
    )
    assert "private-host" not in capsys.readouterr().err

    writes: list[str] = []

    async def write_timeout(*args: object, **kwargs: object) -> None:
        writes.append("save")
        raise runner.LifxTimeoutError("private-host")

    monkeypatch.setattr(runner, "semantic_app_save", write_timeout)
    with pytest.raises(runner.LifxTimeoutError):
        asyncio.run(
            runner._production_app_cycle(
                "source-tile",
                ThemeSpec("cheerful", "Cheerful", "Moods", [], "hash"),
                1,
                object(),
                binding=binding,
                settings=RunnerSettings(),
                run_directory=tmp_path,
                attested_role="source-tile",
                attested_initial_theme="cheerful",
            )
        )
    assert writes == ["save"]


def test_cli_modes_dispatch_without_live_hardware(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The actual parser dispatches validate, finalise, run and resume through seams."""
    calls: list[str] = []
    monkeypatch.setattr(
        runner, "validate_evidence_file", lambda path: calls.append("validate")
    )
    monkeypatch.setattr(
        runner,
        "finalise_private_results",
        lambda *args, **kwargs: calls.append("finalise"),
    )
    assert (
        asyncio.run(runner.main(["--validate-evidence", str(tmp_path / "x")]))
        == runner.EXIT_PASS
    )
    assert (
        asyncio.run(
            runner.main(
                ["--finalise", CANONICAL_RUN_ID, "--private-root", str(tmp_path)]
            )
        )
        == runner.EXIT_PASS
    )
    assert calls == ["validate", "finalise"]
    with pytest.raises(SystemExit):
        runner.build_parser().parse_args(["--run", "--resume", "opaque"])

    targets = tmp_path / "targets.json"
    write_targets(targets, approved_targets())
    monkeypatch.setattr(runner, "require_one_authorised_adb_device", lambda *args: None)
    monkeypatch.setattr(
        runner,
        "adb",
        lambda *args, **kwargs: (
            "package:test"
            if args[1] == "pm"
            else "mDreamingLockscreen=false"
            if args[1] == "dumpsys"
            else "1"
        ),
    )
    monkeypatch.setattr(runner, "_write_private_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(runner, "catalogue_fingerprint", lambda controls: "catalogue")

    async def preflight(**kwargs: object) -> runner.PreflightReport:
        event_recorder = kwargs.get("record_event")
        if callable(event_recorder):
            event_recorder(
                {"event": "preflight-stage", "stage": "test", "status": "passed"}
            )
        contact_observer = getattr(kwargs["device_adapter"], "_contact_observer")
        contact_observer("source-tile", "contact", "passed")
        return runner.PreflightReport(
            "7.1.0",
            "catalogue",
            {
                "source-tile": {"firmware": "3.50"},
                "non-tile-matrix": {"firmware": "4.0"},
            },
            runner.ManualRoleAttestation(
                "opaque",
                "source-tile",
                "digest",
                "now",
                True,
                True,
                True,
                True,
                True,
                True,
            ),
        )

    monkeypatch.setattr(runner, "run_non_mutating_preflight", preflight)

    async def lifecycle(**kwargs: object) -> runner.LifecycleResult:
        provenance = kwargs["provenance"]
        assert isinstance(provenance, runner.RunProvenance)
        assert provenance.app_version == "7.1.0"
        assert provenance.catalogue_fingerprint == "catalogue"
        assert provenance.firmware_by_role == {
            "source-tile": "3.50",
            "non-tile-matrix": "4.0",
        }
        calls.append("lifecycle")
        return runner.LifecycleResult(
            "opaque", [], [], "mismatch", runner.EXIT_MISMATCH, False
        )

    monkeypatch.setattr(runner, "run_designated_lifecycle", lifecycle)
    assert (
        asyncio.run(
            runner.main(
                [
                    "--run",
                    "--targets",
                    str(targets),
                    "--private-root",
                    str(tmp_path / "missing-attestation"),
                ]
            )
        )
        == runner.EXIT_INCOMPLETE
    )
    assert (
        asyncio.run(
            runner.main(
                [
                    "--run",
                    "--attest-role",
                    "source-tile",
                    "--targets",
                    str(targets),
                    "--private-root",
                    str(tmp_path / "missing-initial-theme"),
                ]
            )
        )
        == runner.EXIT_INCOMPLETE
    )
    assert (
        asyncio.run(
            runner.main(
                [
                    "--run",
                    "--attest-role",
                    "source-tile",
                    "--attest-initial-theme",
                    "cheerful",
                    "--targets",
                    str(targets),
                    "--private-root",
                    str(tmp_path / "runs"),
                ]
            )
        )
        == runner.EXIT_MISMATCH
    )

    async def incomplete_lifecycle(**kwargs: object) -> runner.LifecycleResult:
        return runner.LifecycleResult(
            "opaque", [], [], "incomplete", runner.EXIT_INCOMPLETE, False
        )

    monkeypatch.setattr(runner, "run_designated_lifecycle", incomplete_lifecycle)
    assert (
        asyncio.run(
            runner.main(
                [
                    "--run",
                    "--attest-role",
                    "source-tile",
                    "--attest-initial-theme",
                    "cheerful",
                    "--targets",
                    str(targets),
                    "--private-root",
                    str(tmp_path / "incomplete-run"),
                ]
            )
        )
        == runner.EXIT_INCOMPLETE
    )
    assert "run finished: incomplete" in capsys.readouterr().err
    monkeypatch.setattr(runner, "run_designated_lifecycle", lifecycle)
    bound_targets = approved_targets()
    bindings = {
        role: runner.TargetBinding(
            role,
            target["host"],  # type: ignore[index,arg-type]
            target["serial"],  # type: ignore[index,arg-type]
            target["app_label"],  # type: ignore[index,arg-type]
            True,
            True,
            target["app_group"],  # type: ignore[index,arg-type]
        )
        for role, target in (
            ("source-tile", bound_targets["source-tile"]),
            ("non-tile-matrix", bound_targets["non-tile-matrix"]),
        )
    }
    checkpoint = {
        "run_id": CANONICAL_RUN_ID,
        "provenance": runner.build_live_provenance(
            runner_revision="phase-08",
            preflight=runner.PreflightReport(
                "7.1.0",
                "catalogue",
                {
                    "source-tile": {"firmware": "3.50"},
                    "non-tile-matrix": {"firmware": "4.0"},
                },
            ),
            bindings=bindings,
            theme_specs=runner.load_theme_specs(),
            settings=runner.RunnerSettings(
                targets_path=targets, private_root=tmp_path / "runs"
            ),
        ).__dict__,
        "next_cycle": list(runner.build_cycle_schedule()[6]),
        "cycles": [
            runner._cycle_to_record(runner.CycleResult(*key, [], None, True, None))
            for key in runner.build_cycle_schedule()[:6]
        ],
        "snapshots": {},
        "restorations": [],
        "events_path": "",
        "diagnostics_path": "",
        "terminal_cycle": None,
        "terminal_status": None,
        "finalisable": False,
    }
    resume_dir = tmp_path / "runs" / CANONICAL_RUN_ID
    resume_dir.mkdir(parents=True)
    (resume_dir / "checkpoint.json").write_text(json.dumps(checkpoint))
    assert (
        asyncio.run(
            runner.main(
                [
                    "--resume",
                    CANONICAL_RUN_ID,
                    "--attest-role",
                    "source-tile",
                    "--targets",
                    str(targets),
                    "--private-root",
                    str(tmp_path / "runs"),
                ]
            )
        )
        == runner.EXIT_MISMATCH
    )
    assert calls.count("lifecycle") == 2
    checkpoint["run_id"] = "wrong"
    (resume_dir / "checkpoint.json").write_text(json.dumps(checkpoint))
    assert (
        asyncio.run(
            runner.main(
                [
                    "--resume",
                    CANONICAL_RUN_ID,
                    "--targets",
                    str(targets),
                    "--private-root",
                    str(tmp_path / "runs"),
                ]
            )
        )
        == runner.EXIT_INCOMPLETE
    )
    checkpoint["run_id"] = CANONICAL_RUN_ID
    checkpoint["provenance"] = {"changed": True}
    (resume_dir / "checkpoint.json").write_text(json.dumps(checkpoint))
    assert (
        asyncio.run(
            runner.main(
                [
                    "--resume",
                    CANONICAL_RUN_ID,
                    "--targets",
                    str(targets),
                    "--private-root",
                    str(tmp_path / "runs"),
                ]
            )
        )
        == runner.EXIT_INCOMPLETE
    )


@pytest.mark.parametrize(
    "run_id",
    [
        "../outside",
        "/private/tmp/outside",
        ".",
        "0123456789ABCDEF0123456789ABCDEF",
        "0123456789abcdef0123456789abcde",
        "0123456789abcdef0123456789abcdef/child",
    ],
)
def test_resume_and_finalise_reject_noncanonical_run_ids_before_private_access(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, run_id: str
) -> None:
    """Operator input cannot create, chmod, read or write outside the private root."""
    root = tmp_path / "private"
    finalise_calls: list[Path] = []
    monkeypatch.setattr(
        runner,
        "finalise_private_results",
        lambda path, **kwargs: finalise_calls.append(path),
    )

    assert (
        asyncio.run(runner.main(["--resume", run_id, "--private-root", str(root)]))
        == runner.EXIT_INCOMPLETE
    )
    assert not root.exists()
    assert (
        asyncio.run(runner.main(["--finalise", run_id, "--private-root", str(root)]))
        == runner.EXIT_INCOMPLETE
    )
    assert finalise_calls == []


def test_designated_run_directory_rejects_an_escaping_existing_symlink(
    tmp_path: Path,
) -> None:
    """A canonical ID is still rejected when a prior run entry is a symlink."""
    root = tmp_path / "private"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / CANONICAL_RUN_ID).symlink_to(outside, target_is_directory=True)

    with pytest.raises(runner.PreflightError, match="escaped"):
        runner.resolve_designated_run_directory(root, CANONICAL_RUN_ID)


def test_designated_run_directory_redacts_resolve_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Path resolution errors never fall through to private-root access."""

    def unavailable(self: Path, *, strict: bool = False) -> Path:
        raise OSError("unavailable")

    monkeypatch.setattr(Path, "resolve", unavailable)
    with pytest.raises(runner.PreflightError, match="unavailable"):
        runner.resolve_designated_run_directory(tmp_path, CANONICAL_RUN_ID)


def test_remaining_production_failure_boundaries_are_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Injected failures cover the same boundaries the live run will encounter."""
    invalid_checkpoint = {
        "run_id": "opaque",
        "provenance": {},
        "next_cycle": None,
        "cycles": [],
        "snapshots": [],
        "restorations": {},
        "events_path": "",
        "diagnostics_path": "",
        "terminal_status": None,
        "finalisable": False,
    }
    checkpoint_path = tmp_path / "checkpoint.json"
    checkpoint_path.write_text(json.dumps(invalid_checkpoint))
    with pytest.raises(runner.PreflightError):
        runner.load_checkpoint(checkpoint_path)
    store = runner.PrivateCheckpointStore()
    checkpoint = runner.RunCheckpoint(
        "opaque", _lifecycle_inputs()[2], None, [], None, False
    )
    store.write(tmp_path / "good.json", checkpoint)
    assert store.load(tmp_path / "good.json")["run_id"] == "opaque"
    assert (
        runner.ProductionEvidenceWriter()
        .write(public_results(), output_directory=tmp_path)[0]
        .exists()
    )

    class NotMatrix:
        closed = False

        async def close(self) -> None:
            self.closed = True

    class FakeDevice:
        @staticmethod
        async def connect(host: str, serial: str) -> object:
            return NotMatrix()

    monkeypatch.setattr(runner, "Device", FakeDevice)
    monkeypatch.setattr(runner, "MatrixLight", type("Matrix", (), {}))
    with pytest.raises(runner.PreflightError, match="not a matrix"):
        asyncio.run(
            runner.ProductionDeviceAdapter().connect(
                _lifecycle_inputs()[0]["source-tile"]
            )
        )

    for content in ("not-json", "[]"):
        (tmp_path / "bad.json").write_text(content)
        with pytest.raises(runner.PreflightError):
            runner.validate_evidence_file(tmp_path / "bad.json")
    for document in (
        {"finalisable": False},
        {"finalisable": True},
    ):
        (tmp_path / "private.json").write_text(json.dumps(document))
        with pytest.raises(runner.PreflightError):
            runner.finalise_private_results(
                tmp_path / "private.json", output_directory=tmp_path
            )

    monkeypatch.setattr(
        runner,
        "validate_evidence_file",
        lambda path: (_ for _ in ()).throw(runner.PreflightError("bad")),
    )
    monkeypatch.setattr(
        runner,
        "finalise_private_results",
        lambda *args, **kwargs: (_ for _ in ()).throw(runner.PreflightError("bad")),
    )
    assert (
        asyncio.run(runner.main(["--validate-evidence", str(tmp_path / "x")]))
        == runner.EXIT_INCOMPLETE
    )
    assert (
        asyncio.run(
            runner.main(
                ["--finalise", CANONICAL_RUN_ID, "--private-root", str(tmp_path)]
            )
        )
        == runner.EXIT_INCOMPLETE
    )

    bindings, specs, provenance = _lifecycle_inputs()
    snapshot = runner.RestorationSnapshot(
        0,
        colour(0),
        runner.EffectSnapshot(runner.FirmwareEffect.OFF, 0, 0, None, None, 0, 0),
        [object()],
        [[colour(0)]],
        None,
        None,
    )

    class Adapter:
        async def connect(self, binding: runner.TargetBinding) -> object:
            if binding.role == "non-tile-matrix":
                raise runner.PreflightError("missing")
            return SimpleNamespace(role=binding.role)

        async def metadata(
            self, binding: runner.TargetBinding, device: object
        ) -> dict[str, object]:
            return {
                "product_id": 55,
                "is_matrix": True,
                "indoor": True,
                "emulator": False,
                "model": "LIFX Tile",
            }

        async def close(self, device: object) -> None:
            return None

    class MemoryStore:
        def write(self, path: Path, item: runner.RunCheckpoint) -> None:
            return None

        def load(self, path: Path) -> dict[str, object]:
            return {}

    async def capture(device: object) -> runner.RestorationSnapshot:
        return snapshot

    async def restore(device: object, snap: object, *, poll_interval: float) -> bool:
        return True

    async def verify(device: object, snap: object) -> bool:
        return True

    monkeypatch.setattr(runner, "capture_snapshot", capture)
    monkeypatch.setattr(runner, "restore_snapshot", restore)
    monkeypatch.setattr(runner, "verify_restoration", verify)

    async def callback(
        role: str, spec: runner.ThemeSpec, index: int, device: object
    ) -> runner.CycleResult:
        return runner.CycleResult(
            role, spec.slug, "wrong", index, [], None, False, "wrong"
        )

    incomplete = asyncio.run(
        runner.run_designated_lifecycle(
            run_id="opaque",
            bindings=bindings,
            theme_specs=specs,
            provenance=provenance,
            device_adapter=Adapter(),
            checkpoint_store=MemoryStore(),
            checkpoint_path=tmp_path / "x",
            app_cycle=callback,
            library_cycle=callback,
        )
    )  # type: ignore[arg-type]
    assert incomplete.outcome == "incomplete" and not incomplete.finalisable
    assert incomplete.exit_code == runner.EXIT_INCOMPLETE
    assert incomplete.restorations == []


def test_lifecycle_mutation_boundary_classifies_pre_and_post_write_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only a durable baseline checkpoint makes restoration mandatory."""
    bindings, specs, provenance = _lifecycle_inputs()
    snapshot = runner.RestorationSnapshot(
        0,
        colour(0),
        runner.EffectSnapshot(runner.FirmwareEffect.OFF, 0, 0, None, None, 0, 0),
        [object()],
        [[colour(0)]],
        None,
        None,
    )

    def completed_before_library() -> dict[runner.CycleKey, runner.CycleResult]:
        return {
            key: runner.CycleResult(*key, [], [], True, None)
            for key in runner.build_cycle_schedule()[:3]
        }

    async def run(stage: str) -> tuple[runner.LifecycleResult, list[str], int]:
        events: list[str] = []

        class Adapter:
            async def connect(self, binding: runner.TargetBinding) -> object:
                events.append(f"connect:{binding.role}")
                if f"contact:{binding.role}" in stage:
                    raise runner.PreflightError("contact")
                return SimpleNamespace(role=binding.role)

            async def metadata(
                self, binding: runner.TargetBinding, device: object
            ) -> dict[str, object]:
                events.append(f"metadata:{binding.role}")
                if f"metadata:{binding.role}" in stage:
                    raise runner.PreflightError("metadata")
                return {
                    "product_id": 55 if binding.role == "source-tile" else 219,
                    "is_matrix": True,
                    "indoor": True,
                    "emulator": False,
                    "device_class": (
                        "MatrixLight"
                        if binding.role == "source-tile"
                        else "MatrixLight"
                    ),
                    "model": "LIFX Tile"
                    if binding.role == "source-tile"
                    else "LIFX Luna",
                }

            async def close(self, device: object) -> None:
                role = device.role  # type: ignore[attr-defined]
                events.append(f"close:{role}")
                if f"close:{role}" in stage:
                    raise RuntimeError("close")

        class Store:
            writes = 0

            def write(self, path: Path, checkpoint: runner.RunCheckpoint) -> None:
                self.writes += 1
                events.append(f"checkpoint:{self.writes}")
                if stage == "checkpoint" and self.writes == 1:
                    raise runner.PreflightError("checkpoint")

            def load(self, path: Path) -> dict[str, object]:
                raise AssertionError("not used")

        async def capture(device: object) -> runner.RestorationSnapshot:
            role = device.role  # type: ignore[attr-defined]
            events.append(f"snapshot:{role}")
            if f"snapshot:{role}" in stage:
                raise runner.PreflightError("snapshot")
            return snapshot

        async def restore(
            device: object, snap: object, *, poll_interval: float
        ) -> bool:
            events.append(f"restore:{device.role}")  # type: ignore[attr-defined]
            if stage == "restore-error" and device.role == "source-tile":  # type: ignore[attr-defined]
                raise runner.RestorationError("restore")
            return True

        async def verify(device: object, snap: object) -> bool:
            events.append(f"verify:{device.role}")  # type: ignore[attr-defined]
            return True

        async def activate(role: str, device: object) -> None:
            events.append(f"activate:{role}")
            if stage == "activation":
                raise runner.PreflightError("activation")

        async def app(
            role: str, spec: runner.ThemeSpec, index: int, device: object
        ) -> runner.CycleResult:
            events.append(f"app:{role}")
            if stage == "app":
                raise runner.PreflightError("app")
            matches = stage != "mismatch"
            return runner.CycleResult(
                role,
                spec.slug,
                "app",
                index,
                [],
                [],
                matches,
                None,
            )

        async def library(
            role: str, spec: runner.ThemeSpec, index: int, device: object
        ) -> runner.CycleResult:
            events.append(f"library:{role}")
            if stage == "library":
                raise runner.PreflightError("library")
            matches = stage != "mismatch"
            return runner.CycleResult(
                role,
                spec.slug,
                "library",
                index,
                [],
                [],
                matches,
                None,
            )

        monkeypatch.setattr(runner, "capture_snapshot", capture)
        monkeypatch.setattr(runner, "restore_snapshot", restore)
        monkeypatch.setattr(runner, "verify_restoration", verify)
        store = Store()
        result = await runner.run_designated_lifecycle(
            run_id="opaque",
            bindings=bindings,
            theme_specs=specs,
            provenance=provenance,
            device_adapter=Adapter(),  # type: ignore[arg-type]
            checkpoint_store=store,  # type: ignore[arg-type]
            checkpoint_path=tmp_path / stage / "checkpoint.json",
            app_cycle=app,
            library_cycle=library,
            completed=completed_before_library() if stage == "library" else None,
            activate_morph=activate,
        )
        return result, events, store.writes

    for stage in (
        "contact:source-tile",
        "contact:non-tile-matrix",
        "metadata:source-tile",
        "metadata:non-tile-matrix",
        "snapshot:source-tile",
        "snapshot:non-tile-matrix",
        "checkpoint",
    ):
        result, events, writes = asyncio.run(run(stage))
        assert result.outcome == "incomplete"
        assert result.exit_code == runner.EXIT_INCOMPLETE
        assert not result.finalisable and result.restorations == []
        assert not any(event.startswith("restore:") for event in events)
        assert writes == (1 if stage == "checkpoint" else 0)

    for stage in ("activation", "app", "library"):
        result, events, _writes = asyncio.run(run(stage))
        assert result.outcome == "incomplete"
        assert result.exit_code == runner.EXIT_INCOMPLETE
        assert [item.device_role for item in result.restorations] == [
            "source-tile",
            "non-tile-matrix",
        ]
        assert all(item.verified for item in result.restorations)
        assert events.count("restore:source-tile") == 1
        assert events.count("restore:non-tile-matrix") == 1

    pre_close, pre_events, _writes = asyncio.run(
        run("contact:non-tile-matrix|close:source-tile")
    )
    assert pre_close.exit_code == runner.EXIT_INCOMPLETE
    assert pre_close.restorations == []
    assert pre_events == [
        "connect:source-tile",
        "connect:non-tile-matrix",
        "close:source-tile",
    ]

    post_close, post_events, _writes = asyncio.run(run("close:source-tile"))
    assert post_close.outcome == "restoration_failure"
    assert post_close.exit_code == runner.EXIT_RESTORATION_FAILURE
    assert post_events.count("restore:source-tile") == 1
    assert post_events.count("restore:non-tile-matrix") == 1

    restore_error, restore_events, _writes = asyncio.run(run("restore-error"))
    assert restore_error.exit_code == runner.EXIT_RESTORATION_FAILURE
    assert not restore_error.finalisable
    assert restore_events.count("restore:source-tile") == 1
    assert restore_events.count("restore:non-tile-matrix") == 1

    mismatch, mismatch_events, _writes = asyncio.run(run("mismatch"))
    assert mismatch.outcome == "mismatch"
    assert mismatch.exit_code == runner.EXIT_MISMATCH
    assert mismatch.finalisable
    assert all(item.verified for item in mismatch.restorations)
    assert mismatch_events.count("restore:source-tile") == 1
    assert mismatch_events.count("restore:non-tile-matrix") == 1


def test_lifecycle_skip_bad_key_and_cancellation_paths_are_restored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Resume skips only a known key; malformed/cancelled work still hits finally."""
    bindings, specs, provenance = _lifecycle_inputs()
    snapshot = runner.RestorationSnapshot(
        0,
        colour(0),
        runner.EffectSnapshot(runner.FirmwareEffect.OFF, 0, 0, None, None, 0, 0),
        [object()],
        [[colour(0)]],
        None,
        None,
    )

    class Adapter:
        async def connect(self, binding: runner.TargetBinding) -> object:
            return SimpleNamespace(role=binding.role)

        async def metadata(
            self, binding: runner.TargetBinding, device: object
        ) -> dict[str, object]:
            return {
                "product_id": 55 if binding.role == "source-tile" else 100,
                "is_matrix": True,
                "indoor": True,
                "emulator": False,
                "device_class": (
                    "MatrixLight" if binding.role == "source-tile" else "CeilingLight"
                ),
                "model": "LIFX Tile"
                if binding.role == "source-tile"
                else "LIFX Ceiling",
            }

        async def close(self, device: object) -> None:
            return None

    class Store:
        def write(self, path: Path, checkpoint: runner.RunCheckpoint) -> None:
            return None

        def load(self, path: Path) -> dict[str, object]:
            return {}

    async def capture(device: object) -> runner.RestorationSnapshot:
        return snapshot

    async def restore(device: object, snap: object, *, poll_interval: float) -> bool:
        return True

    async def verify(device: object, snap: object) -> bool:
        return True

    monkeypatch.setattr(runner, "capture_snapshot", capture)
    monkeypatch.setattr(runner, "restore_snapshot", restore)
    monkeypatch.setattr(runner, "verify_restoration", verify)
    first_key = runner.build_cycle_schedule()[0]
    first = runner.CycleResult(*first_key, [], [colour(0)], True, None)

    async def wrong(
        role: str, spec: runner.ThemeSpec, index: int, device: object
    ) -> runner.CycleResult:
        return runner.CycleResult(role, spec.slug, "bad", index, [], None, False, "bad")

    incomplete = asyncio.run(
        runner.run_designated_lifecycle(
            run_id="opaque",
            bindings=bindings,
            theme_specs=specs,
            provenance=provenance,
            device_adapter=Adapter(),
            checkpoint_store=Store(),
            checkpoint_path=tmp_path / "checkpoint",
            app_cycle=wrong,
            library_cycle=wrong,
            completed={first_key: first},
        )
    )  # type: ignore[arg-type]
    assert incomplete.outcome == "incomplete" and incomplete.cycles == [first]

    async def cancelled(
        role: str, spec: runner.ThemeSpec, index: int, device: object
    ) -> runner.CycleResult:
        raise asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(
            runner.run_designated_lifecycle(
                run_id="opaque",
                bindings=bindings,
                theme_specs=specs,
                provenance=provenance,
                device_adapter=Adapter(),
                checkpoint_store=Store(),
                checkpoint_path=tmp_path / "checkpoint",
                app_cycle=cancelled,
                library_cycle=cancelled,
            )
        )  # type: ignore[arg-type]


def test_private_result_projection_makes_only_restored_complete_runs_finalisable(
    tmp_path: Path,
) -> None:
    """The private CLI hand-off projects public data only after restored completion."""
    _bindings, specs, provenance = _lifecycle_inputs()
    cycles = [
        runner.CycleResult(role, slug, source, index, [], [colour(0)], True, None)
        for role, slug, source, index in runner.build_cycle_schedule()
    ]
    result = runner.LifecycleResult(
        "opaque",
        cycles,
        [
            runner.RestorationResult("source-tile", True, True, True, None),
            runner.RestorationResult("non-tile-matrix", True, True, True, None),
        ],
        "pass",
        runner.EXIT_PASS,
        True,
        [
            runner.PublicDeviceRecord(
                "source-tile", "MatrixLight", "LIFX Tile", 55, "1"
            ),
            runner.PublicDeviceRecord(
                "non-tile-matrix", "CeilingLight", "LIFX Ceiling", 100, "1"
            ),
        ],
    )
    output = tmp_path / "result.json"
    runner.write_private_run_result(
        result, provenance=provenance, theme_specs=specs, output_path=output
    )
    saved = json.loads(output.read_text())
    assert saved["finalisable"] is True and saved["public_results"]["outcome"] == "pass"


def test_guided_app_cycle_uses_only_lan_reads_and_retains_a_genuine_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The operator applies the app theme; the runner neither drives nor trusts UI."""
    spec = runner.ThemeSpec("mondrian", "Mondrian", "Art Series", [colour(0)], "hash")
    changed = [colour(120)]
    commands: list[tuple[str, ...]] = []

    class Device:
        async def get_effect(self) -> object:
            return SimpleNamespace(
                effect_type=FirmwareEffect.MORPH,
                speed=0,
                duration=0,
                palette=changed,
            )

    monkeypatch.setattr(
        runner, "adb", lambda *args, **kwargs: commands.append(args) or ""
    )
    result = asyncio.run(
        runner._guided_operator_app_cycle(
            "source-tile",
            spec,
            1,
            Device(),
            settings=runner.RunnerSettings(stability_timeout=1, poll_interval=0),
            run_directory=tmp_path,
            previous_app_palette=None,
            attested_role="source-tile",
            attested_initial_theme="cheerful",
        )
    )

    assert commands == []
    assert "ACTION apply and Save Mondrian in Morph" in capsys.readouterr().err
    assert result.stable_palette == changed
    assert not result.matches_expected
    assert result.failure is None
    assert json.loads((tmp_path / "trace.jsonl").read_text().splitlines()[0]) == {
        "elapsed_seconds": 0.0,
        "event": "operator-action",
        "role": "source-tile",
        "status": "requested",
        "theme": "mondrian",
    }


def test_guided_app_cycle_requires_a_fresh_changed_morph_palette(
    tmp_path: Path,
) -> None:
    """An unchanged prior app result cannot be re-recorded as the next alternation."""
    spec = runner.ThemeSpec("cheerful", "Cheerful", "Moods", [colour(0)], "hash")
    unchanged = [colour(120)]

    class Device:
        async def get_effect(self) -> object:
            return SimpleNamespace(
                effect_type=FirmwareEffect.MORPH,
                speed=0,
                duration=0,
                palette=unchanged,
            )

    result = asyncio.run(
        runner._guided_operator_app_cycle(
            "source-tile",
            spec,
            1,
            Device(),
            settings=runner.RunnerSettings(stability_timeout=0, poll_interval=0),
            run_directory=tmp_path,
            previous_app_palette=list(reversed(unchanged)),
            attested_role="source-tile",
            attested_initial_theme="cheerful",
        )
    )

    assert result.stable_palette is None
    assert not result.matches_expected
    assert result.failure == "app readback was unchanged"


def test_guided_operator_wait_uses_a_separate_five_minute_action_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A delayed human Save cannot consume the short readback stability budget."""
    spec = runner.ThemeSpec("mondrian", "Mondrian", "Art Series", [colour(0)], "hash")
    now = [0.0]
    calls = [0]

    class Device:
        async def get_effect(self) -> object:
            calls[0] += 1
            if calls[0] <= 17:
                return off_effect()
            return SimpleNamespace(
                effect_type=FirmwareEffect.MORPH,
                speed=0,
                duration=0,
                palette=[colour(0)],
            )

    async def advance(seconds: float) -> None:
        now[0] += seconds

    monkeypatch.setattr(runner.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(runner.asyncio, "sleep", advance)
    result = asyncio.run(
        runner._guided_operator_app_cycle(
            "source-tile",
            spec,
            1,
            Device(),
            settings=runner.RunnerSettings(
                operator_action_timeout=300,
                stability_timeout=1,
                poll_interval=1,
            ),
            run_directory=tmp_path,
            previous_app_palette=None,
            attested_role="source-tile",
            attested_initial_theme="cheerful",
        )
    )

    assert result.matches_expected
    events = [
        json.loads(line) for line in (tmp_path / "trace.jsonl").read_text().splitlines()
    ]
    assert events[0]["elapsed_seconds"] == 0.0
    assert events[-1]["status"] == "observed"
    assert events[-1]["action_elapsed_seconds"] > 15
    assert events[-1]["stability_elapsed_seconds"] == 1.0


def test_guided_operator_first_observation_starts_a_new_stability_window(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The second equal palette receives its own bounded stability interval."""
    now = [0.0]

    class Device:
        async def get_effect(self) -> object:
            return SimpleNamespace(
                effect_type=FirmwareEffect.MORPH,
                speed=0,
                duration=0,
                palette=[colour(0)],
            )

    async def advance(seconds: float) -> None:
        now[0] += seconds

    monkeypatch.setattr(runner.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(runner.asyncio, "sleep", advance)
    result = asyncio.run(
        runner._guided_operator_app_cycle(
            "source-tile",
            runner.ThemeSpec("mondrian", "Mondrian", "Art Series", [colour(0)], "hash"),
            1,
            Device(),
            settings=runner.RunnerSettings(
                operator_action_timeout=300,
                stability_timeout=1,
                poll_interval=1,
            ),
            run_directory=tmp_path,
            previous_app_palette=None,
            attested_role="source-tile",
            attested_initial_theme="cheerful",
        )
    )

    assert result.matches_expected
    event = json.loads((tmp_path / "trace.jsonl").read_text().splitlines()[-1])
    assert event["action_elapsed_seconds"] == 0.0
    assert event["stability_elapsed_seconds"] == 1.0
    assert event["elapsed_seconds"] == 1.0


def test_guided_operator_action_timeout_is_private_and_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No qualifying MORPH palette before the action deadline remains incomplete."""
    now = [0.0]

    class Device:
        async def get_effect(self) -> object:
            return off_effect()

    async def advance(seconds: float) -> None:
        now[0] += seconds

    monkeypatch.setattr(runner.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(runner.asyncio, "sleep", advance)
    result = asyncio.run(
        runner._guided_operator_app_cycle(
            "source-tile",
            runner.ThemeSpec("mondrian", "Mondrian", "Art Series", [colour(0)], "hash"),
            1,
            Device(),
            settings=runner.RunnerSettings(
                operator_action_timeout=2,
                stability_timeout=1,
                poll_interval=1,
            ),
            run_directory=tmp_path,
            previous_app_palette=None,
            attested_role="source-tile",
            attested_initial_theme="cheerful",
        )
    )

    assert result.stable_palette is None
    assert result.failure == "app readback did not stabilise"
    event = json.loads((tmp_path / "trace.jsonl").read_text().splitlines()[-1])
    assert event == {
        "action_elapsed_seconds": 2.0,
        "elapsed_seconds": 2.0,
        "event": "operator-action",
        "role": "source-tile",
        "stability_elapsed_seconds": 0.0,
        "status": "incomplete",
        "theme": "mondrian",
    }


def test_guided_stability_window_rejects_reversion_and_read_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A fresh action must survive its separate stability window without a reversion."""
    now = [0.0]
    responses: list[object] = [
        [colour(0)],
        [colour(9)],
        [colour(120)],
        runner.PreflightError("private"),
    ]

    class Device:
        async def get_effect(self) -> object:
            response = responses.pop(0)
            if isinstance(response, Exception):
                raise response
            return SimpleNamespace(
                effect_type=FirmwareEffect.MORPH,
                speed=0,
                duration=0,
                palette=response,
            )

    async def advance(seconds: float) -> None:
        now[0] += seconds

    monkeypatch.setattr(runner.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(runner.asyncio, "sleep", advance)
    stable, failure = asyncio.run(
        runner._wait_for_operator_morph_palette(
            Device(),
            previous_app_palette=[colour(120)],
            operator_action_timeout=300,
            stability_timeout=2,
            poll_interval=1,
        )
    )

    assert stable.stable_palette is None
    assert failure == "app readback was unchanged"
    assert stable.action_elapsed_seconds == 0.0
    assert stable.stability_elapsed_seconds == 3.0


def test_lifecycle_stops_after_the_designated_role_and_checkpoints_each_cycle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One invocation owns one role block, leaving the next for fresh attestation."""
    bindings, specs, provenance = _lifecycle_inputs()
    snapshot = runner.RestorationSnapshot(
        0,
        colour(0),
        runner.EffectSnapshot(runner.FirmwareEffect.OFF, 0, 0, None, None, 0, 0),
        [object()],
        [[colour(0)]],
        None,
        None,
    )

    class Adapter:
        async def connect(self, binding: runner.TargetBinding) -> object:
            return SimpleNamespace(role=binding.role)

        async def metadata(
            self, binding: runner.TargetBinding, device: object
        ) -> dict[str, object]:
            return {
                "product_id": 55 if binding.role == "source-tile" else 219,
                "is_matrix": True,
                "indoor": True,
                "emulator": False,
                "device_class": "MatrixLight",
                "model": "LIFX Tile" if binding.role == "source-tile" else "LIFX Luna",
            }

        async def close(self, device: object) -> None:
            return None

    class Store:
        def __init__(self) -> None:
            self.checkpoints: list[runner.RunCheckpoint] = []

        def write(self, path: Path, item: runner.RunCheckpoint) -> None:
            self.checkpoints.append(item)

        def load(self, path: Path) -> dict[str, object]:
            raise AssertionError("not used")

    async def capture(device: object) -> runner.RestorationSnapshot:
        return snapshot

    async def restore(device: object, snap: object, *, poll_interval: float) -> bool:
        return True

    async def verify(device: object, snap: object, **kwargs: object) -> bool:
        return True

    monkeypatch.setattr(runner, "capture_snapshot", capture)
    monkeypatch.setattr(runner, "restore_snapshot", restore)
    monkeypatch.setattr(runner, "verify_restoration", verify)
    calls: list[runner.CycleKey] = []

    async def cycle(
        role: str, spec: runner.ThemeSpec, index: int, device: object
    ) -> runner.CycleResult:
        source = "app" if len(calls) < 6 else "library"
        key = (role, spec.slug, source, index)
        calls.append(key)
        return runner.CycleResult(*key, [], [colour(index)], True, None)

    store = Store()
    result = asyncio.run(
        runner.run_designated_lifecycle(
            run_id="opaque",
            bindings=bindings,
            theme_specs=specs,
            provenance=provenance,
            device_adapter=Adapter(),  # type: ignore[arg-type]
            checkpoint_store=store,  # type: ignore[arg-type]
            checkpoint_path=tmp_path / "checkpoint.json",
            app_cycle=cycle,
            library_cycle=cycle,
            designated_role="source-tile",
        )
    )

    assert calls == runner.build_cycle_schedule()[:12]
    assert result.outcome == "incomplete"
    assert not result.finalisable
    assert store.checkpoints[-1].next_cycle == runner.build_cycle_schedule()[12]


def test_guided_observation_rejects_off_errors_and_bad_attestation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The passive observer never upgrades OFF, errors or a bad claim to a result."""

    class OffDevice:
        async def get_effect(self) -> object:
            return SimpleNamespace(
                effect_type=FirmwareEffect.OFF, speed=0, duration=0, palette=None
            )

    async def no_sleep(_: float) -> None:
        return None

    monkeypatch.setattr(runner.asyncio, "sleep", no_sleep)
    observed, failure = asyncio.run(
        runner._wait_for_operator_morph_palette(
            OffDevice(),
            previous_app_palette=None,
            operator_action_timeout=0.1,
            stability_timeout=0.1,
            poll_interval=0.1,
        )
    )
    assert observed.observations == []
    assert failure == "app readback did not stabilise"

    class ErrorDevice:
        async def get_effect(self) -> object:
            raise runner.PreflightError("private")

    observed, failure = asyncio.run(
        runner._wait_for_operator_morph_palette(
            ErrorDevice(),
            previous_app_palette=None,
            operator_action_timeout=0,
            stability_timeout=0,
            poll_interval=0,
        )
    )
    assert observed.observations == []
    assert failure == "app readback did not stabilise"
    with pytest.raises(runner.PreflightError):
        asyncio.run(
            runner._guided_operator_app_cycle(
                "source-tile",
                runner.ThemeSpec("mondrian", "Mondrian", "Art Series", [], "hash"),
                1,
                OffDevice(),
                settings=runner.RunnerSettings(),
                run_directory=tmp_path,
                previous_app_palette=None,
                attested_role="non-tile-matrix",
                attested_initial_theme="cheerful",
            )
        )


def test_guided_callback_carries_the_prior_app_palette_between_observations(
    tmp_path: Path,
) -> None:
    """Retained evidence prevents a resumed alternation accepting its prior palette."""
    first_key = runner.build_cycle_schedule()[0]
    prior = [colour(120)]
    callback = runner.guided_app_cycle_callback(
        settings=runner.RunnerSettings(stability_timeout=0, poll_interval=0),
        run_directory=tmp_path,
        completed={
            first_key: runner.CycleResult(*first_key, [], prior, False, "mismatch")
        },
        attested_role="source-tile",
        attested_initial_theme="cheerful",
    )

    class Device:
        async def get_effect(self) -> object:
            return SimpleNamespace(
                effect_type=FirmwareEffect.MORPH,
                speed=0,
                duration=0,
                palette=[colour(0)],
            )

    result = asyncio.run(
        callback("source-tile", runner.load_theme_specs()["cheerful"], 1, Device())
    )
    assert result.stable_palette == [colour(0)]

    class OffDevice:
        async def get_effect(self) -> object:
            return SimpleNamespace(
                effect_type=FirmwareEffect.OFF, speed=0, duration=0, palette=None
            )

    incomplete = asyncio.run(
        callback("source-tile", runner.load_theme_specs()["mondrian"], 2, OffDevice())
    )
    assert incomplete.stable_palette is None


def test_main_rejects_an_irrelevant_library_attestation_before_hardware(
    tmp_path: Path,
) -> None:
    """A stale role claim cannot ride along with a library-only resume."""
    targets = tmp_path / "targets.json"
    write_targets(targets, approved_targets())
    root = tmp_path / "runs"
    checkpoint_path = root / CANONICAL_RUN_ID / "checkpoint.json"
    provenance = runner.build_provenance(
        runner_revision="phase-08",
        app_version="private-checked",
        catalogue=runner._stable_digest({"manual-positioning": "phase-08"}),
        target_fingerprints={"source-tile": "one", "non-tile-matrix": "two"},
        firmware_by_role={"source-tile": "one", "non-tile-matrix": "two"},
        theme_specs=runner.load_theme_specs(),
        settings=runner.RunnerSettings(targets_path=targets, private_root=root),
    )
    completed = [
        runner.CycleResult(*key, [], None, True, None)
        for key in runner.build_cycle_schedule()[:6]
    ]
    runner.write_checkpoint(
        checkpoint_path,
        runner.RunCheckpoint(
            CANONICAL_RUN_ID,
            provenance,
            runner.build_cycle_schedule()[6],
            completed,
            None,
            False,
        ),
    )

    assert (
        asyncio.run(
            runner.main(
                [
                    "--resume",
                    CANONICAL_RUN_ID,
                    "--attest-role",
                    "non-tile-matrix",
                    "--targets",
                    str(targets),
                    "--private-root",
                    str(root),
                ]
            )
        )
        == runner.EXIT_INCOMPLETE
    )


def test_designated_lifecycle_retains_incomplete_cycle_in_private_terminal_diagnostics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed app key restores, but never becomes resumable schedule evidence."""
    bindings, specs, provenance = _lifecycle_inputs()
    snapshot = runner.RestorationSnapshot(
        0,
        colour(0),
        runner.EffectSnapshot(runner.FirmwareEffect.OFF, 0, 0, None, None, 0, 0),
        [object()],
        [[colour(0)]],
        None,
        None,
    )

    class Adapter:
        async def connect(self, binding: runner.TargetBinding) -> object:
            return SimpleNamespace(role=binding.role)

        async def metadata(
            self, binding: runner.TargetBinding, device: object
        ) -> dict[str, object]:
            return {
                "product_id": 55 if binding.role == "source-tile" else 219,
                "is_matrix": True,
                "indoor": True,
                "emulator": False,
                "device_class": "MatrixLight",
                "model": "LIFX Tile" if binding.role == "source-tile" else "LIFX Luna",
            }

        async def close(self, device: object) -> None:
            return None

    class Store:
        def __init__(self) -> None:
            self.checkpoints: list[runner.RunCheckpoint] = []

        def write(self, path: Path, item: runner.RunCheckpoint) -> None:
            self.checkpoints.append(item)

        def load(self, path: Path) -> dict[str, object]:
            return {}

    async def capture(device: object) -> runner.RestorationSnapshot:
        return snapshot

    async def restore(device: object, snap: object, *, poll_interval: float) -> bool:
        return True

    async def verify(device: object, snap: object, **kwargs: object) -> bool:
        return True

    monkeypatch.setattr(runner, "capture_snapshot", capture)
    monkeypatch.setattr(runner, "restore_snapshot", restore)
    monkeypatch.setattr(runner, "verify_restoration", verify)
    with pytest.raises(runner.PreflightError):
        asyncio.run(
            runner.run_designated_lifecycle(
                run_id="opaque",
                bindings=bindings,
                theme_specs=specs,
                provenance=provenance,
                device_adapter=Adapter(),  # type: ignore[arg-type]
                checkpoint_store=Store(),  # type: ignore[arg-type]
                checkpoint_path=tmp_path / "checkpoint.json",
                app_cycle=lambda *args: None,  # type: ignore[arg-type]
                library_cycle=lambda *args: None,  # type: ignore[arg-type]
                designated_role="not-a-role",
            )
        )

    with pytest.raises(runner.PreflightError):
        asyncio.run(
            runner.run_designated_lifecycle(
                run_id="opaque",
                bindings=bindings,
                theme_specs=specs,
                provenance=provenance,
                device_adapter=Adapter(),  # type: ignore[arg-type]
                checkpoint_store=Store(),  # type: ignore[arg-type]
                checkpoint_path=tmp_path / "mismatch.json",
                app_cycle=lambda *args: None,  # type: ignore[arg-type]
                library_cycle=lambda *args: None,  # type: ignore[arg-type]
                designated_role="non-tile-matrix",
            )
        )

    async def incomplete(
        role: str, spec: runner.ThemeSpec, index: int, device: object
    ) -> runner.CycleResult:
        return runner.CycleResult(
            role,
            spec.slug,
            "app",
            index,
            [],
            None,
            False,
            "app readback did not stabilise",
        )

    store = Store()
    result = asyncio.run(
        runner.run_designated_lifecycle(
            run_id="opaque",
            bindings=bindings,
            theme_specs=specs,
            provenance=provenance,
            device_adapter=Adapter(),  # type: ignore[arg-type]
            checkpoint_store=store,  # type: ignore[arg-type]
            checkpoint_path=tmp_path / "checkpoint.json",
            app_cycle=incomplete,
            library_cycle=incomplete,
            designated_role="source-tile",
        )
    )
    assert result.outcome == "incomplete"
    assert result.cycles == []
    checkpoint = store.checkpoints[-1]
    assert checkpoint.cycles == []
    assert checkpoint.next_cycle == runner.build_cycle_schedule()[0]
    assert checkpoint.terminal_cycle is not None
    assert (
        checkpoint.terminal_cycle.device_role,
        checkpoint.terminal_cycle.theme_slug,
        checkpoint.terminal_cycle.source,
        checkpoint.terminal_cycle.cycle_index,
    ) == runner.build_cycle_schedule()[0]


def test_designated_lifecycle_checkpoints_a_stable_mismatch_and_advances(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A complete non-matching palette is evidence, not an incomplete cycle."""
    bindings, specs, provenance = _lifecycle_inputs()
    snapshot = runner.RestorationSnapshot(
        0,
        colour(0),
        runner.EffectSnapshot(runner.FirmwareEffect.OFF, 0, 0, None, None, 0, 0),
        [object()],
        [[colour(0)]],
        None,
        None,
    )

    class Adapter:
        async def connect(self, binding: runner.TargetBinding) -> object:
            return SimpleNamespace(role=binding.role)

        async def metadata(
            self, binding: runner.TargetBinding, device: object
        ) -> dict[str, object]:
            return {
                "product_id": 55 if binding.role == "source-tile" else 219,
                "is_matrix": True,
                "indoor": True,
                "emulator": False,
                "device_class": "MatrixLight",
                "model": "LIFX Tile" if binding.role == "source-tile" else "LIFX Luna",
            }

        async def close(self, device: object) -> None:
            return None

    class Store:
        def __init__(self) -> None:
            self.checkpoints: list[runner.RunCheckpoint] = []

        def write(self, path: Path, item: runner.RunCheckpoint) -> None:
            self.checkpoints.append(item)

        def load(self, path: Path) -> dict[str, object]:
            return {}

    async def capture(device: object) -> runner.RestorationSnapshot:
        return snapshot

    async def restored(device: object, snap: object, *, poll_interval: float) -> bool:
        return True

    async def verified(device: object, snap: object, **kwargs: object) -> bool:
        return True

    monkeypatch.setattr(runner, "capture_snapshot", capture)
    monkeypatch.setattr(runner, "restore_snapshot", restored)
    monkeypatch.setattr(runner, "verify_restoration", verified)
    calls = [0]

    async def cycle(
        role: str, spec: runner.ThemeSpec, index: int, device: object
    ) -> runner.CycleResult:
        source = "app" if calls[0] == 0 else "library"
        calls[0] += 1
        if calls[0] == 1:
            return runner.CycleResult(
                role, spec.slug, source, index, [], [colour(120)], False, None
            )
        return runner.CycleResult(
            role, spec.slug, source, index, [], None, False, "incomplete"
        )

    store = Store()
    result = asyncio.run(
        runner.run_designated_lifecycle(
            run_id="opaque",
            bindings=bindings,
            theme_specs=specs,
            provenance=provenance,
            device_adapter=Adapter(),  # type: ignore[arg-type]
            checkpoint_store=store,  # type: ignore[arg-type]
            checkpoint_path=tmp_path / "checkpoint.json",
            app_cycle=cycle,
            library_cycle=cycle,
            designated_role="source-tile",
        )
    )

    assert len(result.cycles) == 1
    assert result.cycles[0].failure is None
    assert result.cycles[0].matches_expected is False
    assert store.checkpoints[1].cycles == result.cycles
    assert store.checkpoints[1].next_cycle == runner.build_cycle_schedule()[1]
    assert store.checkpoints[-1].next_cycle == runner.build_cycle_schedule()[1]


def test_role_only_schedule_and_cli_are_luna_only_and_never_resumable() -> None:
    """The post-Tile workflow has a distinct 12-key, non-finalisable surface."""
    keys = runner.build_role_only_schedule("non-tile-matrix")

    assert keys == runner.build_cycle_schedule()[12:]
    assert len(keys) == 12
    with pytest.raises(runner.PreflightError):
        runner.build_role_only_schedule("source-tile")
    parsed = runner.build_parser().parse_args(
        ["--role-only", "non-tile-matrix", "--run", "--attest-role", "non-tile-matrix"]
    )
    assert parsed.role_only == "non-tile-matrix"


def test_role_only_preflight_contacts_only_luna_and_restores_android_setting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A poison Tile binding proves the fresh preflight cannot touch prior history."""
    bindings, specs, _provenance = _lifecycle_inputs()
    events: list[str] = []
    controls = [
        {"resource-id": "app:id/detail_panel", "bounds": "[0,0][100,100]"},
        {
            "resource-id": "app:id/effect_name",
            "text": "Morph",
            "bounds": "[1,1][99,10]",
        },
        {
            "resource-id": "app:id/effect_subtitle",
            "text": "Effect",
            "bounds": "[1,11][99,20]",
        },
        {
            "resource-id": "app:id/effect_settings_controller_scroll_view",
            "bounds": "[1,21][99,90]",
        },
        {
            "resource-id": "app:id/theme_button",
            "clickable": "true",
            "enabled": "true",
            "bounds": "[1,30][50,40]",
        },
    ]

    class Adapter:
        async def connect(self, binding: runner.TargetBinding) -> object:
            assert binding.role == "non-tile-matrix"
            events.append("connect:luna")
            return SimpleNamespace(role=binding.role)

        async def metadata(
            self, binding: runner.TargetBinding, device: object
        ) -> dict[str, object]:
            assert binding.role == "non-tile-matrix"
            events.append("metadata:luna")
            return {
                "product_id": 219,
                "is_matrix": True,
                "indoor": True,
                "emulator": False,
                "model": "LIFX Luna",
                "device_class": "MatrixLight",
            }

        async def close(self, device: object) -> None:
            events.append("close:luna")

    snapshot = runner.RestorationSnapshot(
        0,
        colour(0),
        runner.EffectSnapshot(FirmwareEffect.OFF, 0, 0, None, None, 0, 0),
        [object()],
        [[colour(0)]],
        None,
        None,
    )

    async def capture(device: object) -> runner.RestorationSnapshot:
        events.append("snapshot:luna")
        return snapshot

    monkeypatch.setattr(runner, "capture_snapshot", capture)
    setting = {"value": "0"}

    def adb_command(*arguments: str) -> str:
        if arguments[-3:] == ("get", "global", "stay_on_while_plugged_in"):
            return setting["value"]
        if arguments[-3:-1] == ("put", "global"):
            setting["value"] = arguments[-1]
            return ""
        if arguments == ("devices",):
            return "List of devices attached\nserial\tdevice\n"
        if arguments == ("shell", "pm", "path", runner.LIFX_PACKAGE):
            return "package:private"
        if arguments[-2:] == ("dumpsys", "window"):
            return "mDreamingLockscreen=false"
        return "versionName=4.96.0"

    report = asyncio.run(
        runner.run_role_only_preflight(
            bindings=bindings,
            theme_specs=specs,
            settings=runner.RunnerSettings(),
            device_adapter=Adapter(),  # type: ignore[arg-type]
            adb_command=adb_command,
            dump_hierarchy=lambda: controls,
            attested_role="non-tile-matrix",
        )
    )
    assert set(report.metadata_by_role) == {"non-tile-matrix"}
    assert events == ["connect:luna", "metadata:luna", "snapshot:luna", "close:luna"]
    assert setting["value"] == "0"


def test_role_only_lifecycle_never_contacts_or_restores_tile_and_stays_private(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A fresh Luna run keeps all 12 observations local despite success."""
    bindings, specs, provenance = _lifecycle_inputs()
    events: list[str] = []
    snapshot = runner.RestorationSnapshot(
        0,
        colour(0),
        runner.EffectSnapshot(FirmwareEffect.OFF, 0, 0, None, None, 0, 0),
        [object()],
        [[colour(0)]],
        None,
        None,
    )

    class Adapter:
        async def connect(self, binding: runner.TargetBinding) -> object:
            assert binding.role == "non-tile-matrix"
            events.append("connect:luna")
            return SimpleNamespace(role=binding.role)

        async def metadata(
            self, binding: runner.TargetBinding, device: object
        ) -> dict[str, object]:
            assert binding.role == "non-tile-matrix"
            return {
                "product_id": 219,
                "is_matrix": True,
                "indoor": True,
                "emulator": False,
                "model": "LIFX Luna",
                "device_class": "MatrixLight",
            }

        async def close(self, device: object) -> None:
            events.append("close:luna")

    class Store:
        def __init__(self) -> None:
            self.checkpoints: list[runner.RunCheckpoint] = []

        def write(self, path: Path, checkpoint: runner.RunCheckpoint) -> None:
            self.checkpoints.append(checkpoint)

        def load(self, path: Path) -> dict[str, object]:
            raise AssertionError("role-only runs never resume")

    async def capture(device: object) -> runner.RestorationSnapshot:
        events.append("snapshot:luna")
        return snapshot

    async def restore(device: object, snap: object, *, poll_interval: float) -> bool:
        events.append("restore:luna")
        return True

    async def verify(device: object, snap: object, *, poll_interval: float = 0) -> bool:
        events.append("verify:luna")
        return True

    monkeypatch.setattr(runner, "capture_snapshot", capture)
    monkeypatch.setattr(runner, "restore_snapshot", restore)
    monkeypatch.setattr(runner, "verify_restoration", verify)

    async def cycle(
        role: str, spec: runner.ThemeSpec, index: int, device: object
    ) -> runner.CycleResult:
        # The runner checks the source against its locked key; derive it from the
        # cycle order retained by the callback's invocation count instead.
        key = runner.build_role_only_schedule(role)[len(cycles)]
        cycles.append(key)
        return runner.CycleResult(*key, [], [colour(0)], True, None)

    cycles: list[runner.CycleKey] = []
    store = Store()
    result = asyncio.run(
        runner.run_role_only_lifecycle(
            run_id="opaque",
            bindings=bindings,
            theme_specs=specs,
            provenance=provenance,
            device_adapter=Adapter(),  # type: ignore[arg-type]
            checkpoint_store=store,  # type: ignore[arg-type]
            checkpoint_path=tmp_path / "checkpoint.json",
            app_cycle=cycle,
            library_cycle=cycle,
        )
    )
    assert cycles == runner.build_role_only_schedule("non-tile-matrix")
    assert result.outcome == "role-complete/manual-reconciliation-needed"
    assert result.exit_code == runner.EXIT_ROLE_COMPLETE and not result.finalisable
    assert [item.device_role for item in result.restorations] == ["non-tile-matrix"]
    assert events == [
        "connect:luna",
        "snapshot:luna",
        "restore:luna",
        "verify:luna",
        "close:luna",
    ]
    assert set(store.checkpoints[-1].snapshots) == {"non-tile-matrix"}


@pytest.mark.parametrize(
    "metadata",
    [
        {
            "product_id": 176,
            "is_matrix": True,
            "indoor": True,
            "emulator": False,
            "model": "LIFX Ceiling",
            "device_class": "CeilingLight",
        },
        {
            "product_id": 219,
            "is_matrix": True,
            "indoor": True,
            "emulator": False,
            "model": "LIFX Path",
            "device_class": "MatrixLight",
        },
        {
            "product_id": 221,
            "is_matrix": True,
            "indoor": True,
            "emulator": False,
            "model": "LIFX Luna",
            "device_class": "MatrixLight",
        },
        {
            "product_id": 219,
            "is_matrix": True,
            "indoor": True,
            "emulator": False,
            "model": "LIFX Luna",
            "device_class": "CeilingLight",
        },
    ],
)
def test_role_only_lifecycle_rechecks_exact_luna_before_any_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, metadata: dict[str, object]
) -> None:
    """Ceiling, Path, and other matrix devices stop before snapshot or callbacks."""
    bindings, specs, provenance = _lifecycle_inputs()
    events: list[str] = []

    class Adapter:
        async def connect(self, binding: runner.TargetBinding) -> object:
            events.append("connect")
            return SimpleNamespace()

        async def metadata(
            self, binding: runner.TargetBinding, device: object
        ) -> dict[str, object]:
            events.append("metadata")
            return metadata

        async def close(self, device: object) -> None:
            events.append("close")

    class PoisonStore:
        def write(self, path: Path, checkpoint: runner.RunCheckpoint) -> None:
            raise AssertionError("identity failure must precede checkpointing")

        def load(self, path: Path) -> dict[str, object]:
            raise AssertionError("role-only runs never resume")

    async def poison_snapshot(device: object) -> runner.RestorationSnapshot:
        raise AssertionError("identity failure must precede snapshotting")

    async def poison_cycle(*args: object) -> runner.CycleResult:
        raise AssertionError("identity failure must precede light mutation")

    monkeypatch.setattr(runner, "capture_snapshot", poison_snapshot)
    result = asyncio.run(
        runner.run_role_only_lifecycle(
            run_id="opaque",
            bindings=bindings,
            theme_specs=specs,
            provenance=provenance,
            device_adapter=Adapter(),  # type: ignore[arg-type]
            checkpoint_store=PoisonStore(),  # type: ignore[arg-type]
            checkpoint_path=tmp_path / "checkpoint.json",
            app_cycle=poison_cycle,  # type: ignore[arg-type]
            library_cycle=poison_cycle,  # type: ignore[arg-type]
        )
    )

    assert result.exit_code == runner.EXIT_INCOMPLETE
    assert result.cycles == [] and result.restorations == []
    assert events == ["connect", "metadata", "close"]


@pytest.mark.parametrize(
    ("product_id", "model"),
    [(219, "LIFX Luna"), (220, "LIFX Luna Intl")],
)
def test_role_only_luna_metadata_accepts_only_the_two_registered_luna_models(
    product_id: int, model: str
) -> None:
    """The Luna-only guard is explicit about both accepted product identities."""
    runner.validate_role_only_luna_metadata(
        {
            "product_id": product_id,
            "is_matrix": True,
            "indoor": True,
            "emulator": False,
            "model": model,
            "device_class": "MatrixLight",
        }
    )


def test_role_only_result_cannot_be_finalised(tmp_path: Path) -> None:
    """A Luna-only result has no official projection, even after clean restore."""
    result = runner.LifecycleResult(
        "opaque",
        [],
        [],
        "role-complete/manual-reconciliation-needed",
        runner.EXIT_ROLE_COMPLETE,
        False,
    )
    output = tmp_path / "result.json"
    runner.write_private_run_result(
        result,
        provenance=_lifecycle_inputs()[2],
        theme_specs=_lifecycle_inputs()[1],
        output_path=output,
        role_only=True,
    )
    saved = json.loads(output.read_text())
    assert (
        saved["finalisable"] is False
        and saved["manual_reconciliation_required"] is True
    )
    with pytest.raises(runner.PreflightError):
        runner.finalise_private_results(output, output_directory=tmp_path)


def test_role_only_lifecycle_rejects_bad_keys_and_restores_after_incomplete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Bad role-only callbacks retain a terminal record and still restore Luna once."""
    bindings, specs, provenance = _lifecycle_inputs()
    snapshot = runner.RestorationSnapshot(
        0,
        colour(0),
        runner.EffectSnapshot(FirmwareEffect.OFF, 0, 0, None, None, 0, 0),
        [object()],
        [[colour(0)]],
        None,
        None,
    )
    events: list[str] = []

    class Adapter:
        async def connect(self, binding: runner.TargetBinding) -> object:
            assert binding.role == "non-tile-matrix"
            return SimpleNamespace(role=binding.role)

        async def metadata(
            self, binding: runner.TargetBinding, device: object
        ) -> dict[str, object]:
            return {
                "product_id": 219,
                "is_matrix": True,
                "indoor": True,
                "emulator": False,
                "model": "LIFX Luna",
                "device_class": "MatrixLight",
            }

        async def close(self, device: object) -> None:
            events.append("close")

    class Store:
        def write(self, path: Path, checkpoint: runner.RunCheckpoint) -> None:
            events.append("checkpoint")

        def load(self, path: Path) -> dict[str, object]:
            raise AssertionError("not used")

    async def capture(device: object) -> runner.RestorationSnapshot:
        return snapshot

    async def restore(device: object, snap: object, *, poll_interval: float) -> bool:
        events.append("restore")
        return True

    async def verify(device: object, snap: object, *, poll_interval: float = 0) -> bool:
        events.append("verify")
        return True

    monkeypatch.setattr(runner, "capture_snapshot", capture)
    monkeypatch.setattr(runner, "restore_snapshot", restore)
    monkeypatch.setattr(runner, "verify_restoration", verify)

    async def incomplete(
        role: str, spec: runner.ThemeSpec, index: int, device: object
    ) -> runner.CycleResult:
        return runner.CycleResult(
            role, spec.slug, "app", index, [], None, False, "incomplete"
        )

    result = asyncio.run(
        runner.run_role_only_lifecycle(
            run_id="opaque",
            bindings=bindings,
            theme_specs=specs,
            provenance=provenance,
            device_adapter=Adapter(),
            checkpoint_store=Store(),
            checkpoint_path=tmp_path / "checkpoint.json",
            app_cycle=incomplete,
            library_cycle=incomplete,
            activate_morph=lambda role, device: asyncio.sleep(0),
        )
    )  # type: ignore[arg-type]
    assert result.outcome == "incomplete" and result.exit_code == runner.EXIT_INCOMPLETE
    assert [item.device_role for item in result.restorations] == ["non-tile-matrix"]
    assert events[-4:] == ["restore", "verify", "close", "checkpoint"]

    async def wrong_key(
        role: str, spec: runner.ThemeSpec, index: int, device: object
    ) -> runner.CycleResult:
        return runner.CycleResult(
            role, spec.slug, "library", index, [], [], False, None
        )

    wrong = asyncio.run(
        runner.run_role_only_lifecycle(
            run_id="opaque",
            bindings=bindings,
            theme_specs=specs,
            provenance=provenance,
            device_adapter=Adapter(),
            checkpoint_store=Store(),
            checkpoint_path=tmp_path / "wrong.json",
            app_cycle=wrong_key,
            library_cycle=wrong_key,
        )
    )  # type: ignore[arg-type]
    assert wrong.exit_code == runner.EXIT_INCOMPLETE

    class FailingContact:
        async def connect(self, binding: runner.TargetBinding) -> object:
            raise runner.PreflightError("contact")

        async def metadata(
            self, binding: runner.TargetBinding, device: object
        ) -> dict[str, object]:
            raise AssertionError("not reached")

        async def close(self, device: object) -> None:
            raise AssertionError("not reached")

    pre_boundary = asyncio.run(
        runner.run_role_only_lifecycle(
            run_id="opaque",
            bindings=bindings,
            theme_specs=specs,
            provenance=provenance,
            device_adapter=FailingContact(),
            checkpoint_store=Store(),
            checkpoint_path=tmp_path / "contact.json",
            app_cycle=incomplete,
            library_cycle=incomplete,
        )
    )  # type: ignore[arg-type]
    assert (
        pre_boundary.restorations == []
        and pre_boundary.exit_code == runner.EXIT_INCOMPLETE
    )

    async def cancelled(
        role: str, spec: runner.ThemeSpec, index: int, device: object
    ) -> runner.CycleResult:
        raise asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(
            runner.run_role_only_lifecycle(
                run_id="opaque",
                bindings=bindings,
                theme_specs=specs,
                provenance=provenance,
                device_adapter=Adapter(),
                checkpoint_store=Store(),
                checkpoint_path=tmp_path / "cancel.json",
                app_cycle=cancelled,
                library_cycle=cancelled,
            )
        )  # type: ignore[arg-type]


def test_role_only_preflight_fail_closed_branches_are_tile_free(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Invalid role/configuration/tablet paths fail before any source adapter call."""
    bindings, specs, _provenance = _lifecycle_inputs()

    class PoisonAdapter:
        async def connect(self, binding: runner.TargetBinding) -> object:
            raise runner.PreflightError("luna contact failed")

        async def metadata(
            self, binding: runner.TargetBinding, device: object
        ) -> dict[str, object]:
            raise AssertionError("not reached")

        async def close(self, device: object) -> None:
            raise AssertionError("not reached")

    def adb_command(*arguments: str) -> str:
        if arguments == ("devices",):
            return "List of devices attached\nserial\tdevice\n"
        if arguments == ("shell", "pm", "path", runner.LIFX_PACKAGE):
            return "package:private"
        if arguments == ("shell", "dumpsys", "window"):
            return "mDreamingLockscreen=false"
        if arguments[-3:] == ("get", "global", "stay_on_while_plugged_in"):
            return "0"
        return "versionName=4.96.0"

    kwargs = dict(
        bindings=bindings,
        theme_specs=specs,
        settings=runner.RunnerSettings(),
        device_adapter=PoisonAdapter(),
        adb_command=adb_command,
        dump_hierarchy=lambda: [],
    )
    with pytest.raises(runner.PreflightError):
        asyncio.run(
            runner.run_role_only_preflight(**kwargs, attested_role="source-tile")
        )  # type: ignore[arg-type]
    with pytest.raises(runner.PreflightError):
        asyncio.run(
            runner.run_role_only_preflight(
                **{**kwargs, "theme_specs": {}}, attested_role="non-tile-matrix"
            )
        )  # type: ignore[arg-type]
    altered = dict(bindings)
    altered["non-tile-matrix"] = dataclasses.replace(
        altered["non-tile-matrix"], indoor_confirmed=False
    )
    with pytest.raises(runner.PreflightError):
        asyncio.run(
            runner.run_role_only_preflight(
                **{**kwargs, "bindings": altered}, attested_role="non-tile-matrix"
            )
        )  # type: ignore[arg-type]
    with pytest.raises(runner.RunnerError):
        asyncio.run(
            runner.run_role_only_preflight(**kwargs, attested_role="non-tile-matrix")
        )  # type: ignore[arg-type]
    monkeypatch.setattr(
        runner,
        "attest_manual_role_position",
        lambda binding, controls, **unused: runner.ManualRoleAttestation(
            "preflight",
            binding.role,
            runner.binding_digest(binding),
            "preflight",
            True,
            True,
            True,
            True,
            True,
            True,
        ),
    )
    with pytest.raises(runner.PreflightError):
        asyncio.run(
            runner.run_role_only_preflight(**kwargs, attested_role="non-tile-matrix")
        )  # type: ignore[arg-type]


def test_main_dispatches_role_only_preflight_and_run_without_full_run_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CLI role-only dispatch rejects old checkpoint and evidence paths."""
    bindings, specs, provenance = _lifecycle_inputs()
    controls: list[runner.Control] = []
    attestation = runner.ManualRoleAttestation(
        "opaque",
        "non-tile-matrix",
        runner.binding_digest(bindings["non-tile-matrix"]),
        "now",
        True,
        True,
        True,
        True,
        True,
        True,
    )
    report = runner.PreflightReport(
        "4.96.0",
        "catalogue",
        {
            "non-tile-matrix": {
                "device_class": "MatrixLight",
                "model": "LIFX Luna",
                "product_id": 219,
                "firmware": "1",
            }
        },
        attestation,
    )
    calls: list[str] = []
    monkeypatch.setattr(runner, "ensure_private_root", lambda path: None)
    monkeypatch.setattr(
        runner, "load_target_bindings", lambda *args, **kwargs: bindings
    )
    monkeypatch.setattr(runner, "load_theme_specs", lambda: specs)
    monkeypatch.setattr(runner, "_write_private_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        runner,
        "production_manual_position_callbacks",
        lambda *args: (lambda *args: "", lambda: controls),
    )

    async def preflight(**kwargs: object) -> runner.PreflightReport:
        calls.append("preflight")
        event_recorder = kwargs["record_event"]
        assert callable(event_recorder)
        event_recorder({"event": "test"})
        return report

    async def lifecycle(**kwargs: object) -> runner.LifecycleResult:
        calls.append("run")
        return runner.LifecycleResult(
            "opaque",
            [],
            [],
            "role-complete/manual-reconciliation-needed",
            runner.EXIT_ROLE_COMPLETE,
            False,
        )

    async def awake(action: Callable[[], object], **kwargs: object) -> object:
        result = action()
        return await result  # type: ignore[misc]

    monkeypatch.setattr(runner, "run_role_only_preflight", preflight)
    monkeypatch.setattr(runner, "run_role_only_lifecycle", lifecycle)
    monkeypatch.setattr(runner, "with_android_keep_awake", awake)
    assert (
        asyncio.run(
            runner.main(
                [
                    "--role-only",
                    "non-tile-matrix",
                    "--preflight-only",
                    "--attest-role",
                    "non-tile-matrix",
                    "--private-root",
                    str(tmp_path),
                ]
            )
        )
        == runner.EXIT_PASS
    )
    assert (
        asyncio.run(
            runner.main(
                [
                    "--role-only",
                    "non-tile-matrix",
                    "--run",
                    "--attest-role",
                    "non-tile-matrix",
                    "--attest-initial-theme",
                    "cheerful",
                    "--private-root",
                    str(tmp_path),
                ]
            )
        )
        == runner.EXIT_ROLE_COMPLETE
    )
    assert calls == ["preflight", "preflight", "run"]
    assert (
        asyncio.run(
            runner.main(
                ["--role-only", "non-tile-matrix", "--private-root", str(tmp_path)]
            )
        )
        == runner.EXIT_INCOMPLETE
    )
    assert (
        asyncio.run(
            runner.main(
                [
                    "--role-only",
                    "non-tile-matrix",
                    "--preflight-only",
                    "--private-root",
                    str(tmp_path),
                ]
            )
        )
        == runner.EXIT_INCOMPLETE
    )
    assert (
        asyncio.run(
            runner.main(
                [
                    "--role-only",
                    "non-tile-matrix",
                    "--run",
                    "--attest-role",
                    "non-tile-matrix",
                    "--private-root",
                    str(tmp_path),
                ]
            )
        )
        == runner.EXIT_INCOMPLETE
    )

    async def preflight_without_attestation(**kwargs: object) -> runner.PreflightReport:
        event_recorder = kwargs["record_event"]
        assert callable(event_recorder)
        event_recorder({"event": "test"})
        return dataclasses.replace(report, source_attestation=None)

    monkeypatch.setattr(
        runner, "run_role_only_preflight", preflight_without_attestation
    )
    assert (
        asyncio.run(
            runner.main(
                [
                    "--role-only",
                    "non-tile-matrix",
                    "--preflight-only",
                    "--attest-role",
                    "non-tile-matrix",
                    "--private-root",
                    str(tmp_path),
                ]
            )
        )
        == runner.EXIT_PASS
    )


def test_role_only_preflight_rejects_missing_app_and_locked_screen() -> None:
    """Tablet prerequisites fail before UI or either device adapter can run."""
    bindings, specs, _provenance = _lifecycle_inputs()

    class PoisonAdapter:
        async def connect(self, binding: runner.TargetBinding) -> object:
            raise AssertionError("no LAN contact")

        async def metadata(
            self, binding: runner.TargetBinding, device: object
        ) -> dict[str, object]:
            raise AssertionError("no LAN metadata")

        async def close(self, device: object) -> None:
            raise AssertionError("no LAN close")

    def command(package: str, window: str) -> Callable[..., str]:
        def adb(*arguments: str) -> str:
            if arguments == ("devices",):
                return "List of devices attached\nserial\tdevice\n"
            if arguments == ("shell", "pm", "path", runner.LIFX_PACKAGE):
                return package
            if arguments == ("shell", "dumpsys", "window"):
                return window
            return "versionName=4.96.0"

        return adb

    for package, window in (
        ("missing", "mDreamingLockscreen=false"),
        ("package:private", "locked"),
    ):
        with pytest.raises(runner.PreflightError):
            asyncio.run(
                runner.run_role_only_preflight(
                    bindings=bindings,
                    theme_specs=specs,
                    settings=runner.RunnerSettings(),
                    device_adapter=PoisonAdapter(),
                    adb_command=command(package, window),
                    dump_hierarchy=lambda: [],
                    attested_role="non-tile-matrix",
                )
            )  # type: ignore[arg-type]


def test_role_only_lifecycle_bad_binding_and_restore_failure_are_non_finalisable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Both pre-boundary schema rejection and post-write failure stay Luna-local."""
    bindings, specs, provenance = _lifecycle_inputs()
    with pytest.raises(runner.PreflightError):
        asyncio.run(
            runner.run_role_only_lifecycle(
                run_id="opaque",
                bindings={"non-tile-matrix": bindings["non-tile-matrix"]},
                theme_specs=specs,
                provenance=provenance,
                device_adapter=object(),  # type: ignore[arg-type]
                checkpoint_store=object(),
                checkpoint_path=tmp_path / "bad",
                app_cycle=None,
                library_cycle=None,  # type: ignore[arg-type]
            )
        )

    snapshot = runner.RestorationSnapshot(
        0,
        colour(0),
        runner.EffectSnapshot(FirmwareEffect.OFF, 0, 0, None, None, 0, 0),
        [object()],
        [[colour(0)]],
        None,
        None,
    )

    class Adapter:
        async def connect(self, binding: runner.TargetBinding) -> object:
            return SimpleNamespace()

        async def metadata(
            self, binding: runner.TargetBinding, device: object
        ) -> dict[str, object]:
            return {
                "product_id": 219,
                "is_matrix": True,
                "indoor": True,
                "emulator": False,
                "model": "LIFX Luna",
                "device_class": "MatrixLight",
            }

        async def close(self, device: object) -> None:
            raise RuntimeError("close")

    class Store:
        def write(self, path: Path, checkpoint: runner.RunCheckpoint) -> None:
            return None

        def load(self, path: Path) -> dict[str, object]:
            raise AssertionError("never resume")

    async def capture(device: object) -> runner.RestorationSnapshot:
        return snapshot

    async def restore(device: object, snap: object, *, poll_interval: float) -> bool:
        raise RuntimeError("restore")

    monkeypatch.setattr(runner, "capture_snapshot", capture)
    monkeypatch.setattr(runner, "restore_snapshot", restore)

    async def cycle(
        role: str, spec: runner.ThemeSpec, index: int, device: object
    ) -> runner.CycleResult:
        return runner.CycleResult(
            role, spec.slug, "app", index, [], None, False, "incomplete"
        )

    result = asyncio.run(
        runner.run_role_only_lifecycle(
            run_id="opaque",
            bindings=bindings,
            theme_specs=specs,
            provenance=provenance,
            device_adapter=Adapter(),
            checkpoint_store=Store(),
            checkpoint_path=tmp_path / "failure",
            app_cycle=cycle,
            library_cycle=cycle,
        )
    )  # type: ignore[arg-type]
    assert (
        result.outcome == "restoration_failure"
        and result.exit_code == runner.EXIT_RESTORATION_FAILURE
    )


def test_non_tile_guided_observation_discards_trigger_and_settles_before_stability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A Luna transition cannot become the retained app-cycle palette."""
    now = [0.0]
    sleeps: list[float] = []
    trigger = [colour(1)]
    intermediate = [colour(2)]
    final = [colour(3)]
    responses = [trigger, intermediate, final, final]

    class Device:
        async def get_effect(self) -> object:
            return SimpleNamespace(
                effect_type=FirmwareEffect.MORPH,
                speed=0,
                duration=0,
                palette=responses.pop(0),
            )

    async def advance(seconds: float) -> None:
        sleeps.append(seconds)
        now[0] += seconds

    monkeypatch.setattr(runner.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(runner.asyncio, "sleep", advance)
    observed, failure = asyncio.run(
        runner._wait_for_operator_morph_palette(
            Device(),
            role="non-tile-matrix",
            previous_app_palette=None,
            operator_action_timeout=300,
            stability_timeout=3,
            poll_interval=1,
            non_tile_settle_duration=5,
        )
    )

    assert failure is None
    assert observed.stable_palette == final
    assert [item.palette for item in observed.observations] == [
        intermediate,
        final,
        final,
    ]
    assert sleeps == [5, 1, 1, 1]
    assert observed.action_elapsed_seconds == 0
    assert observed.stability_elapsed_seconds == 3


def test_tile_guided_observation_has_no_extra_settle_delay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The faster source Tile retains the existing immediate stability contract."""
    sleeps: list[float] = []

    class Device:
        async def get_effect(self) -> object:
            return SimpleNamespace(
                effect_type=FirmwareEffect.MORPH,
                speed=0,
                duration=0,
                palette=[colour(0)],
            )

    async def record_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr(runner.asyncio, "sleep", record_sleep)
    observed, failure = asyncio.run(
        runner._wait_for_operator_morph_palette(
            Device(),
            role="source-tile",
            previous_app_palette=None,
            operator_action_timeout=300,
            stability_timeout=1,
            poll_interval=1,
            non_tile_settle_duration=5,
        )
    )

    assert failure is None
    assert observed.stable_palette == [colour(0)]
    assert sleeps == [1]


def test_non_tile_guided_prompt_includes_the_settle_instruction(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The role-only Luna prompt tells the operator about its required dwell."""

    class Device:
        async def get_effect(self) -> object:
            return SimpleNamespace(
                effect_type=FirmwareEffect.MORPH,
                speed=0,
                duration=0,
                palette=[colour(0)],
            )

    async def no_sleep(_: float) -> None:
        return None

    monkeypatch.setattr(runner.asyncio, "sleep", no_sleep)
    result = asyncio.run(
        runner._guided_operator_app_cycle(
            "non-tile-matrix",
            runner.ThemeSpec("mondrian", "Mondrian", "Art Series", [colour(0)], "hash"),
            1,
            Device(),
            settings=runner.RunnerSettings(
                stability_timeout=0, poll_interval=0, non_tile_settle_duration=5
            ),
            run_directory=tmp_path,
            previous_app_palette=None,
            attested_role="non-tile-matrix",
            attested_initial_theme="cheerful",
        )
    )

    assert result.stable_palette == [colour(0)]
    assert "allow 5 seconds to settle" in capsys.readouterr().err


def test_role_only_safe_settings_trace_retains_mode_role_and_settle_duration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A private first trace record makes the selected CLI mode diagnosable."""
    bindings, specs, _provenance = _lifecycle_inputs()
    events: list[dict[str, object]] = []
    report = runner.PreflightReport(
        "4.96.0",
        "catalogue",
        {
            "non-tile-matrix": {
                "device_class": "MatrixLight",
                "model": "LIFX Luna",
                "product_id": 219,
                "firmware": "1",
            }
        },
    )
    monkeypatch.setattr(
        runner, "load_target_bindings", lambda *args, **kwargs: bindings
    )
    monkeypatch.setattr(runner, "load_theme_specs", lambda: specs)
    monkeypatch.setattr(
        runner,
        "production_manual_position_callbacks",
        lambda *args: (lambda *unused: "", lambda: []),
    )
    monkeypatch.setattr(
        runner,
        "_write_private_event",
        lambda _path, event: events.append(dict(event)),
    )

    async def preflight(**kwargs: object) -> runner.PreflightReport:
        return report

    monkeypatch.setattr(runner, "run_role_only_preflight", preflight)

    assert (
        asyncio.run(
            runner.main(
                [
                    "--role-only",
                    "non-tile-matrix",
                    "--preflight-only",
                    "--attest-role",
                    "non-tile-matrix",
                    "--non-tile-settle-duration",
                    "2.5",
                    "--private-root",
                    str(tmp_path),
                ]
            )
        )
        == runner.EXIT_PASS
    )
    assert events[0]["mode"] == "role-only-non-tile-matrix"
    assert events[0]["role"] == "non-tile-matrix"
    assert events[0]["non_tile_settle_duration"] == 2.5


def test_role_only_generic_incomplete_progress_uses_the_selected_role(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """An outer failure must not falsely name the Tile during Luna-only work."""
    monkeypatch.setattr(
        runner,
        "load_target_bindings",
        lambda *args, **kwargs: (_ for _ in ()).throw(runner.PreflightError("private")),
    )

    assert (
        asyncio.run(
            runner.main(
                [
                    "--role-only",
                    "non-tile-matrix",
                    "--preflight-only",
                    "--attest-role",
                    "non-tile-matrix",
                    "--private-root",
                    str(tmp_path),
                ]
            )
        )
        == runner.EXIT_INCOMPLETE
    )
    assert "non-tile-matrix: incomplete" in capsys.readouterr().err


def test_non_tile_post_settle_off_or_prior_palette_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Luna cannot recover an invalid post-settle state into a measurement."""

    class Device:
        def __init__(self, responses: list[object]) -> None:
            self.responses = responses

        async def get_effect(self) -> object:
            response = self.responses.pop(0)
            if response == "off":
                return off_effect()
            return SimpleNamespace(
                effect_type=FirmwareEffect.MORPH,
                speed=0,
                duration=0,
                palette=response,
            )

    async def no_sleep(_: float) -> None:
        return None

    monkeypatch.setattr(runner.asyncio, "sleep", no_sleep)
    off_result, off_failure = asyncio.run(
        runner._wait_for_operator_morph_palette(
            Device([[colour(1)], "off"]),
            role="non-tile-matrix",
            previous_app_palette=None,
            operator_action_timeout=300,
            stability_timeout=0,
            poll_interval=0,
            non_tile_settle_duration=0,
        )
    )
    prior_result, prior_failure = asyncio.run(
        runner._wait_for_operator_morph_palette(
            Device([[colour(1)], [colour(0)]]),
            role="non-tile-matrix",
            previous_app_palette=[colour(0)],
            operator_action_timeout=300,
            stability_timeout=0,
            poll_interval=0,
            non_tile_settle_duration=0,
        )
    )

    assert off_result.stable_palette is None
    assert off_failure == "app readback did not stabilise"
    assert prior_result.stable_palette is None
    assert prior_failure == "app readback was unchanged"


def test_non_tile_settle_duration_must_be_finite_and_nonnegative(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Bad settle overrides stop before private configuration or hardware access."""

    assert (
        asyncio.run(
            runner.main(
                [
                    "--role-only",
                    "non-tile-matrix",
                    "--preflight-only",
                    "--attest-role",
                    "non-tile-matrix",
                    "--non-tile-settle-duration",
                    "nan",
                    "--private-root",
                    str(tmp_path),
                ]
            )
        )
        == runner.EXIT_INCOMPLETE
    )
    assert "non-tile-matrix: incomplete" in capsys.readouterr().err
