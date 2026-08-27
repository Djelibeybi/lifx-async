"""Regression coverage for the Phase 8 16-colour ceiling documentation."""

import json
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
PHASE_DIRECTORY = REPOSITORY_ROOT / ".planning/phases/08-hardware-fidelity-validation"
SHIPPED_THEMES_PATH = REPOSITORY_ROOT / "data/themes.jsonl"
RAW_THEMES_PATH = REPOSITORY_ROOT / ".claude/theme-capture/themes.jsonl"
CEILING_DETERMINATIONS_PATH = PHASE_DIRECTORY / "08-CEILING-DETERMINATIONS.json"
EXCEPTION_OVERRIDE_PATH = PHASE_DIRECTORY / "08-EXCEPTION-OVERRIDE.json"
ACTIVE_DOCUMENTS = (
    REPOSITORY_ROOT / ".planning/PROJECT.md",
    REPOSITORY_ROOT / ".planning/REQUIREMENTS.md",
    REPOSITORY_ROOT / ".planning/ROADMAP.md",
    REPOSITORY_ROOT / ".claude/theme-capture/README.md",
)


def _load_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def test_ceiling_inventory_is_25_shipped_from_26_raw() -> None:
    shipped_records = _load_jsonl(SHIPPED_THEMES_PATH)
    raw_records = _load_jsonl(RAW_THEMES_PATH)

    shipped_slugs = sorted(
        record["slug"]
        for record in shipped_records
        if record["disposition"] == "lifx-app" and len(record["colors"]) == 16
    )
    raw_ceiling_records = [
        record for record in raw_records if len(record["colors"]) == 16
    ]
    raw_only_carlton = [
        (record["name"], record["category"])
        for record in raw_ceiling_records
        if record["name"].startswith("Carlton")
    ]

    assert len(shipped_slugs) == 25
    assert len(set(shipped_slugs)) == 25
    assert len(raw_ceiling_records) == 26
    assert raw_only_carlton == [("Carlton 🔵", "🏆 AUSSIE RULES")]
    assert "carlton" not in shipped_slugs


def test_active_phase_8_documents_use_correct_ceiling_counts() -> None:
    documents = {path.name: path.read_text() for path in ACTIVE_DOCUMENTS}

    for document in documents.values():
        normalised_document = " ".join(document.split())
        assert "25 shipped" in normalised_document
        assert "26 exactly-16-colour" in normalised_document
        assert "Carlton" in normalised_document

    readme = documents["README.md"]
    assert "cannot reveal a 17th colour" in " ".join(readme.split())

    active_claims = "\n".join(documents.values())
    assert "21 themes returned exactly 16" not in active_claims
    assert "26 themes that returned exactly 16" not in active_claims
    assert "Each of the 26 exactly-16-colour themes" not in active_claims


def test_committed_ceiling_determinations_are_the_runner_projection() -> None:
    """The privacy-safe table remains an exact deterministic source projection."""
    sys.path.insert(0, str(PHASE_DIRECTORY))
    try:
        from uat_theme_fidelity import derive_ceiling_determinations
    finally:
        sys.path.pop(0)

    payload = json.loads(CEILING_DETERMINATIONS_PATH.read_text())
    rows = payload["determinations"]
    expected_rows = [
        {
            "theme_slug": row["slug"],
            "determination": row["determination"],
        }
        for row in derive_ceiling_determinations()
    ]

    assert payload["schema_version"] == 1
    assert payload["source"] == "data/themes.jsonl"
    assert payload["selection"] == {
        "disposition": "lifx-app",
        "literal_palette_length": 16,
        "excluded_slug": "carlton",
        "expected_rows": 25,
    }
    assert payload["protocol_ceiling"]["determination"] == "device-ceiling-unresolvable"
    assert rows == expected_rows
    assert json.dumps(rows, separators=(",", ":"), sort_keys=True) == json.dumps(
        expected_rows, separators=(",", ":"), sort_keys=True
    )
    assert len(rows) == len({row["theme_slug"] for row in rows}) == 25
    assert [row["theme_slug"] for row in rows] == sorted(
        row["theme_slug"] for row in rows
    )
    assert "carlton" not in {row["theme_slug"] for row in rows}
    assert all(
        set(row) == {"theme_slug", "determination"}
        and row["determination"] == "device-ceiling-unresolvable"
        for row in rows
    )


def test_exception_override_records_acceptance_without_claiming_finalisation() -> None:
    """The closeout decision is reviewable but never a synthetic UAT result."""
    payload = json.loads(EXCEPTION_OVERRIDE_PATH.read_text())

    assert payload == {
        "schema_version": 1,
        "kind": "operator-approved-exception",
        "scope": "tile-restoration-and-two-role-finalisation",
        "decision": "accepted_exception",
        "authority": "operator",
        "date": "2026-08-16",
        "facts": {
            "tile_theme_fidelity_observations": "accepted",
            "luna_theme_fidelity_observations": "accepted",
            "luna_restoration": "verified",
            "tile_restoration": "unverified",
            "official_08_uat_results_json": "deliberately_absent",
            "synthetic_merge": "prohibited",
            "further_hardware_run": "not_required",
        },
    }
    assert not (PHASE_DIRECTORY / "08-UAT-RESULTS.json").exists()
    rendered = json.dumps(payload, sort_keys=True)
    assert all(
        term not in rendered.lower() for term in ("host", "serial", "mac", "adb")
    )
