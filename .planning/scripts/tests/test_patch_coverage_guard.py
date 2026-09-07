"""Fixture-driven tests for the vacuous-gate guard, covering every branch locally."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import patch_coverage_guard as guard
import pytest
import yaml

# tomllib is stdlib from 3.11; this project supports 3.10, where the same reader
# ships as the tomli backport. Declared in the dev dependency group under the
# matching marker rather than relied on as somebody else's transitive dependency.
if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - exercised only on Python 3.10
    import tomli as tomllib

pytestmark = pytest.mark.tooling

# The two codecov/patch description forms recorded from live data in the phase
# spec (PR #208 and its follow-up), replayed here through --status-json with
# no network and no pull request.
_VACUOUS_DESCRIPTION_D68D36A = "Coverage not affected when comparing ed17fdb...d68d36a"
_SCORED_DESCRIPTION_0BE78E6 = "100.00% of diff hit (target 100.00%)"

# The project's own [tool.coverage.report] exclude_lines, reproduced verbatim
# so the fixture repository's coverage configuration matches the real one.
# Every fixture repository needs this file on disk: the guard constructs
# coverage.Coverage(config_file=repo_root/"pyproject.toml") and raises if it
# is absent.
_PYPROJECT_TOML = r"""[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "@overload",
    "if TYPE_CHECKING",
    "raise NotImplementedError",
    'if __name__ == "__main__":',
    '^\s*\.\.\.$',
]
"""


def _git(repo: Path, *args: str) -> str:
    """Run Git in a temporary repository and return stdout."""
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _write(repo: Path, relative: str, content: str) -> None:
    """Write one fixture file, creating its parent directory."""
    path = repo / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _commit(repo: Path, message: str = "fixture") -> str:
    """Commit every temporary-repository fixture change."""
    _git(repo, "add", "--all")
    _git(repo, "commit", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """Create a Git repository with deterministic identity and a matching pyproject.

    No commit signing. The pyproject.toml carries this project's own
    [tool.coverage.report] exclude_lines so authoritative_statements()
    behaves the same way here as it does against the real repository.
    """
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.name", "Patch Coverage Guard Test")
    _git(tmp_path, "config", "user.email", "patch-coverage-guard@example.invalid")
    _git(tmp_path, "config", "commit.gpgsign", "false")
    _write(tmp_path, "pyproject.toml", _PYPROJECT_TOML)
    return tmp_path


def _commit_module(
    repo: Path, relative: str, base_content: str, appended_content: str
) -> str:
    """Commit a base version of a measured module, then append content and commit again.

    Returns the base commit SHA. base_content is left untouched by the
    second commit, so the appended lines are pure git-diff additions
    starting immediately after it, mirroring check_patch_coverage.py's own
    test fixture shape.
    """
    _write(repo, relative, base_content)
    base = _commit(repo, "base")
    _write(repo, relative, base_content + appended_content)
    _commit(repo, "change")
    return base


def _write_coverage_xml(
    repo: Path,
    *,
    source_roots: list[str] | None,
    classes: dict[str, dict[int, int]],
) -> Path:
    """Write a synthetic Cobertura coverage.xml.

    classes maps a <class filename> to {line_number: hits}. Passing None
    for source_roots omits the <sources> element entirely, which is the
    one shape load_coverage_xml() falls back to the raw filename for.
    """
    class_blocks = []
    for filename, line_hits in classes.items():
        line_elements = "".join(
            f'<line number="{number}" hits="{hits}"/>'
            for number, hits in line_hits.items()
        )
        class_blocks.append(
            f'<class filename="{filename}" name="{filename}">'
            f"<lines>{line_elements}</lines>"
            "</class>"
        )

    if source_roots is None:
        sources_xml = ""
    else:
        sources_xml = (
            "<sources>"
            + "".join(f"<source>{root}</source>" for root in source_roots)
            + "</sources>"
        )

    document = (
        '<?xml version="1.0" ?>'
        "<coverage>"
        f"{sources_xml}"
        "<packages><package><classes>"
        + "".join(class_blocks)
        + "</classes></package></packages>"
        "</coverage>"
    )
    path = repo / "coverage.xml"
    path.write_text(document, encoding="utf-8")
    return path


def _write_status_json(repo: Path, statuses: list[dict[str, Any]]) -> Path:
    """Write a combined-status JSON payload in the same shape `gh api` returns."""
    path = repo / "status.json"
    payload = {"state": "success", "statuses": statuses}
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _build_vacuous_fixture(repo: Path) -> tuple[str, Path]:
    """Build a fixture the report does not classify at all."""
    relative = "src/lifx/cross_check_vacuous_module.py"
    base = _commit_module(repo, relative, "value = 1\n", "extra = 2\nmore = 3\n")
    report = _write_coverage_xml(repo, source_roots=[str(repo)], classes={})
    return base, report


def _build_scored_fixture(repo: Path) -> tuple[str, Path]:
    """Build a fixture whose changed measured lines the report fully classifies."""
    relative = "src/lifx/cross_check_scored_module.py"
    base = _commit_module(repo, relative, "value = 1\n", "extra = 2\nmore = 3\n")
    report = _write_coverage_xml(
        repo, source_roots=[str(repo)], classes={relative: {1: 1, 2: 1, 3: 1}}
    )
    return base, report


def _build_neutral_fixture(repo: Path) -> tuple[str, Path]:
    """Build an unmeasured-only fixture: passes regardless of report or cross-check."""
    _write(repo, "tests/test_neutral.py", "def test_neutral():\n    assert True\n")
    base = _commit(repo, "base")
    _write(
        repo,
        "tests/test_neutral.py",
        "def test_neutral():\n    assert True\n\n\ndef test_more():\n    assert True\n",
    )
    _commit(repo, "change")
    report = _write_coverage_xml(repo, source_roots=[str(repo)], classes={})
    return base, report


# --- Vacuous, scored, unmeasured-only, partial ------------------------------


def test_vacuous_file_absent_from_report(git_repo: Path, monkeypatch, capsys) -> None:
    """A changed measured file absent from the report fails, naming both counts."""
    relative = "src/lifx/vacuous_absent_module.py"
    base = _commit_module(git_repo, relative, "value = 1\n", "extra = 2\nmore = 3\n")
    report = _write_coverage_xml(git_repo, source_roots=[str(git_repo)], classes={})
    monkeypatch.chdir(git_repo)

    assert guard.run(["--base", base, "--coverage", str(report)]) == 1
    err = capsys.readouterr().err
    assert "VACUOUS COVERAGE GATE" in err
    assert "changed_measured=2 scored=0" in err


def test_vacuous_file_present_but_classifies_no_changed_lines(
    git_repo: Path, monkeypatch, capsys
) -> None:
    """A report with the file, but none of its changed lines classified, fails too."""
    relative = "src/lifx/vacuous_present_module.py"
    base = _commit_module(git_repo, relative, "value = 1\n", "extra = 2\nmore = 3\n")
    report = _write_coverage_xml(
        git_repo, source_roots=[str(git_repo)], classes={relative: {1: 1}}
    )
    monkeypatch.chdir(git_repo)

    assert guard.run(["--base", base, "--coverage", str(report)]) == 1
    assert "VACUOUS COVERAGE GATE" in capsys.readouterr().err


def test_scored_passes(git_repo: Path, monkeypatch, capsys) -> None:
    """A report classifying every changed measured line passes."""
    relative = "src/lifx/scored_module.py"
    base = _commit_module(git_repo, relative, "value = 1\n", "extra = 2\nmore = 3\n")
    report = _write_coverage_xml(
        git_repo, source_roots=[str(git_repo)], classes={relative: {1: 1, 2: 1, 3: 1}}
    )
    monkeypatch.chdir(git_repo)

    assert guard.run(["--base", base, "--coverage", str(report)]) == 0
    assert "changed_measured=2 scored=2" in capsys.readouterr().out


def test_unmeasured_only_passes_regardless_of_report(
    git_repo: Path, monkeypatch
) -> None:
    """A pull request touching only unmeasured files passes with an empty report."""
    base, report = _build_neutral_fixture(git_repo)
    _write(git_repo, "codecov.yml", "codecov:\n  require_ci_to_pass: false\n")
    _write(git_repo, "uv.lock", "# lock file placeholder\n")
    _write(git_repo, ".github/workflows/ci.yml", "name: CI\n")
    _commit(git_repo, "unmeasured files")
    monkeypatch.chdir(git_repo)

    assert guard.run(["--base", base, "--coverage", str(report)]) == 0


def test_partial_scoring_warns_and_passes(git_repo: Path, monkeypatch, capsys) -> None:
    """A report scoring one of two changed measured files warns but still passes."""
    relative_a = "src/lifx/partial_a.py"
    relative_b = "src/lifx/partial_b.py"
    _write(git_repo, relative_a, "value = 1\n")
    _write(git_repo, relative_b, "value = 1\n")
    base = _commit(git_repo, "base")
    _write(git_repo, relative_a, "value = 1\nextra = 2\nmore = 3\n")
    _write(git_repo, relative_b, "value = 1\nextra = 2\nmore = 3\n")
    _commit(git_repo, "change")
    report = _write_coverage_xml(
        git_repo, source_roots=[str(git_repo)], classes={relative_a: {1: 1, 2: 1, 3: 1}}
    )
    monkeypatch.chdir(git_repo)

    assert guard.run(["--base", base, "--coverage", str(report)]) == 0
    out = capsys.readouterr().out
    assert "WARNING: partially scored" in out
    assert "changed_measured=4 scored=2" in out


# --- Non-statement additions: comments, blank lines, configured exclusions --


def test_comment_and_blank_only_change_passes_when_report_contains_file(
    git_repo: Path, monkeypatch, capsys
) -> None:
    """A blank line and a comment pass even when the report has the file."""
    relative = "src/lifx/docstring_module.py"
    base = _commit_module(
        git_repo, relative, '"""Module docstring."""\nvalue = 1\n', "\n# a comment\n"
    )
    report = _write_coverage_xml(
        git_repo, source_roots=[str(git_repo)], classes={relative: {2: 1}}
    )
    monkeypatch.chdir(git_repo)

    assert guard.run(["--base", base, "--coverage", str(report)]) == 0
    assert "VACUOUS" not in capsys.readouterr().err


def test_comment_and_blank_only_change_passes_when_report_omits_file(
    git_repo: Path, monkeypatch, capsys
) -> None:
    """The same change passes even when the report has no entry for the file at all."""
    relative = "src/lifx/docstring_module_omitted.py"
    base = _commit_module(
        git_repo, relative, '"""Module docstring."""\nvalue = 1\n', "\n# a comment\n"
    )
    report = _write_coverage_xml(git_repo, source_roots=[str(git_repo)], classes={})
    monkeypatch.chdir(git_repo)

    assert guard.run(["--base", base, "--coverage", str(report)]) == 0
    assert "VACUOUS" not in capsys.readouterr().err


def test_configured_exclusion_only_change_passes(git_repo: Path, monkeypatch) -> None:
    """A configured-exclusion block passes: analysis2() removes it entirely."""
    relative = "src/lifx/exclusion_module.py"
    base = _commit_module(
        git_repo, relative, "value = 1\n", 'if __name__ == "__main__":\n    pass\n'
    )
    report = _write_coverage_xml(git_repo, source_roots=[str(git_repo)], classes={})
    monkeypatch.chdir(git_repo)

    assert guard.run(["--base", base, "--coverage", str(report)]) == 0


def test_missing_source_on_disk_warns_and_does_not_fail_alone(
    git_repo: Path, monkeypatch, capsys
) -> None:
    """A changed measured path missing on disk warns, contributing nothing, no fail."""
    relative = "src/lifx/missing_module.py"
    base = _commit_module(git_repo, relative, "value = 1\n", "extra = 2\n")
    (git_repo / relative).unlink()
    report = _write_coverage_xml(git_repo, source_roots=[str(git_repo)], classes={})
    monkeypatch.chdir(git_repo)

    assert guard.run(["--base", base, "--coverage", str(report)]) == 0
    assert "not found on disk" in capsys.readouterr().err


# --- Cobertura <source> resolution ------------------------------------------


def test_source_root_joining_src_rooted_shape(tmp_path: Path) -> None:
    """A <source> ending in src, joined with a lifx/... filename, resolves under src."""
    xml_path = _write_coverage_xml(
        tmp_path,
        source_roots=[str(tmp_path / "src")],
        classes={"lifx/example_module.py": {1: 1}},
    )

    report = guard.load_coverage_xml(xml_path, tmp_path)

    assert "src/lifx/example_module.py" in report


def test_source_root_joining_repo_rooted_shape(tmp_path: Path) -> None:
    """A <source> holding the repo root, with a src/lifx/... filename, resolves too."""
    xml_path = _write_coverage_xml(
        tmp_path,
        source_roots=[str(tmp_path)],
        classes={"src/lifx/example_module.py": {1: 1}},
    )

    report = guard.load_coverage_xml(xml_path, tmp_path)

    assert "src/lifx/example_module.py" in report


def test_source_root_traversal_refusal_contributes_no_entry(tmp_path: Path) -> None:
    """An outside <source> with an inside-looking filename is refused, not re-keyed."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    outside_root = tmp_path / "outside"
    outside_root.mkdir()
    xml_path = _write_coverage_xml(
        repo_root,
        source_roots=[str(outside_root)],
        classes={"src/lifx/example_module.py": {1: 1}},
    )

    report = guard.load_coverage_xml(xml_path, repo_root)

    assert report == {}


def test_no_sources_element_falls_back_to_raw_filename(tmp_path: Path) -> None:
    """A document with no <sources> element at all uses the raw-filename fallback."""
    xml_path = _write_coverage_xml(
        tmp_path,
        source_roots=None,
        classes={"src/lifx/example_module.py": {1: 1}},
    )

    report = guard.load_coverage_xml(xml_path, tmp_path)

    assert "src/lifx/example_module.py" in report


# --- The codecov/patch cross-check ------------------------------------------


def test_cross_check_divergence_on_vacuous_description(
    git_repo: Path, monkeypatch, capsys
) -> None:
    """The recorded vacuous description alongside a non-empty count logs divergence."""
    base, report = _build_vacuous_fixture(git_repo)
    status = _write_status_json(
        git_repo,
        [
            {
                "context": "codecov/patch",
                "state": "success",
                "description": _VACUOUS_DESCRIPTION_D68D36A,
            }
        ],
    )
    monkeypatch.chdir(git_repo)

    exit_code = guard.run(
        ["--base", base, "--coverage", str(report), "--status-json", str(status)]
    )

    assert exit_code == 1
    assert "CROSS-CHECK DIVERGENCE" in capsys.readouterr().out


def test_cross_check_agreement_on_scored_description(
    git_repo: Path, monkeypatch, capsys
) -> None:
    """The recorded scored description, alongside a matching count, logs agreement."""
    base, report = _build_scored_fixture(git_repo)
    status = _write_status_json(
        git_repo,
        [
            {
                "context": "codecov/patch",
                "state": "success",
                "description": _SCORED_DESCRIPTION_0BE78E6,
            }
        ],
    )
    monkeypatch.chdir(git_repo)

    exit_code = guard.run(
        ["--base", base, "--coverage", str(report), "--status-json", str(status)]
    )

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "CROSS-CHECK AGREE" in out
    assert "CROSS-CHECK DIVERGENCE" not in out


def test_cross_check_unusable_no_patch_entry(
    git_repo: Path, monkeypatch, capsys
) -> None:
    """A payload with no codecov/patch entry is unusable, not a decision either way."""
    base, report = _build_neutral_fixture(git_repo)
    status = _write_status_json(
        git_repo, [{"context": "other/check", "state": "success", "description": "n/a"}]
    )
    monkeypatch.chdir(git_repo)

    exit_code = guard.run(
        ["--base", base, "--coverage", str(report), "--status-json", str(status)]
    )

    assert exit_code == 0
    assert "CROSS-CHECK UNUSABLE" in capsys.readouterr().out


def test_cross_check_unusable_pending_entry(
    git_repo: Path, monkeypatch, capsys
) -> None:
    """A pending codecov/patch entry is unusable and does not change the exit code."""
    base, report = _build_neutral_fixture(git_repo)
    status = _write_status_json(
        git_repo,
        [
            {
                "context": "codecov/patch",
                "state": "pending",
                "description": "Collecting reports",
            }
        ],
    )
    monkeypatch.chdir(git_repo)

    exit_code = guard.run(
        [
            "--base",
            base,
            "--coverage",
            str(report),
            "--status-json",
            str(status),
            "--status-timeout",
            "0",
        ]
    )

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "CROSS-CHECK UNUSABLE" in out
    assert "pending" in out


def test_cross_check_unusable_unrecognised_description(
    git_repo: Path, monkeypatch, capsys
) -> None:
    """A description matching neither recorded form is unusable, not a divergence."""
    base, report = _build_neutral_fixture(git_repo)
    status = _write_status_json(
        git_repo,
        [
            {
                "context": "codecov/patch",
                "state": "success",
                "description": "Something unexpected",
            }
        ],
    )
    monkeypatch.chdir(git_repo)

    exit_code = guard.run(
        ["--base", base, "--coverage", str(report), "--status-json", str(status)]
    )

    assert exit_code == 0
    assert "CROSS-CHECK UNUSABLE" in capsys.readouterr().out


# --- Operational errors ------------------------------------------------------


def test_missing_coverage_report_is_operational_error(
    git_repo: Path, monkeypatch
) -> None:
    """A coverage report path that does not exist fails closed, not as an empty set."""
    base = _commit(git_repo, "base")
    monkeypatch.chdir(git_repo)

    assert guard.run(["--base", base, "--coverage", str(git_repo / "absent.xml")]) == 2


def test_malformed_base_is_operational_error() -> None:
    """A --base that is not one full hexadecimal SHA fails before any diff runs."""
    assert guard.run(["--base", "not-a-sha", "--coverage", "unused.xml"]) == 2


def test_invalid_head_is_operational_error_before_any_subprocess(
    git_repo: Path, monkeypatch
) -> None:
    """An invalid --head fails before shutil.which is ever consulted for gh."""
    base = _commit(git_repo, "base")
    monkeypatch.chdir(git_repo)

    def _raise_if_called(*_args: object, **_kwargs: object) -> str | None:
        raise AssertionError("shutil.which must not be called for an invalid --head")

    monkeypatch.setattr(guard.shutil, "which", _raise_if_called)

    exit_code = guard.run(
        ["--base", base, "--head", "not-a-sha", "--coverage", "unused.xml"]
    )

    assert exit_code == 2


def test_malformed_xml_report_is_operational_error(git_repo: Path, monkeypatch) -> None:
    """Coverage XML that does not parse is an operational error."""
    base = _commit(git_repo, "base")
    report = git_repo / "coverage.xml"
    report.write_text("<coverage><packages>", encoding="utf-8")
    monkeypatch.chdir(git_repo)

    assert guard.run(["--base", base, "--coverage", str(report)]) == 2


def test_non_integer_hits_attribute_is_operational_error(
    git_repo: Path, monkeypatch
) -> None:
    """A <line hits> attribute that is not an integer is an operational error."""
    base = _commit(git_repo, "base")
    report = git_repo / "coverage.xml"
    report.write_text(
        "<coverage><sources><source>" + str(git_repo) + "</source></sources>"
        "<packages><package><classes>"
        '<class filename="src/lifx/x.py" name="x">'
        '<lines><line number="1" hits="abc"/></lines>'
        "</class></classes></package></packages></coverage>",
        encoding="utf-8",
    )
    monkeypatch.chdir(git_repo)

    assert guard.run(["--base", base, "--coverage", str(report)]) == 2


def test_missing_pyproject_toml_is_operational_error(
    git_repo: Path, monkeypatch
) -> None:
    """A missing pyproject.toml fails closed: exclude_lines cannot silently stop."""
    relative = "src/lifx/pyproject_check_module.py"
    base = _commit_module(git_repo, relative, "value = 1\n", "extra = 2\n")
    report = _write_coverage_xml(git_repo, source_roots=[str(git_repo)], classes={})
    (git_repo / "pyproject.toml").unlink()
    monkeypatch.chdir(git_repo)

    assert guard.run(["--base", base, "--coverage", str(report)]) == 2


# --- Configuration drift and the CI wiring ----------------------------------


def test_measured_tree_constants_match_project_configuration() -> None:
    """The measured-tree constants must not drift from the configuration they encode."""
    repo_root = Path(__file__).resolve().parents[3]
    pyproject = tomllib.loads(
        (repo_root / "pyproject.toml").read_text(encoding="utf-8")
    )
    codecov = yaml.safe_load((repo_root / "codecov.yml").read_text(encoding="utf-8"))

    omit = set(pyproject["tool"]["coverage"]["run"]["omit"])
    assert set(guard.UNMEASURED_PATHS) == omit
    assert set(guard.UNMEASURED_PATHS) <= set(codecov["ignore"])

    addopts = pyproject["tool"]["pytest"]["ini_options"]["addopts"]
    cov_targets = {
        line.strip().removeprefix("--cov=")
        for line in addopts.splitlines()
        if line.strip().startswith("--cov=")
    }
    cov_to_prefix = {"lifx": "src/lifx/"}
    cov_to_file = {"generate_theme_data": "scripts/generate_theme_data.py"}
    assert cov_targets == set(cov_to_prefix) | set(cov_to_file)
    assert tuple(cov_to_prefix.values()) == guard.MEASURED_PREFIXES
    assert tuple(cov_to_file.values()) == guard.MEASURED_FILES

    combined_paths: set[str] = set()
    for flag_config in codecov["flags"].values():
        flag_paths = set(flag_config["paths"])
        assert flag_paths == {"src/lifx/", "scripts/"}
        combined_paths |= flag_paths
    assert guard.MEASURED_PREFIXES[0] in combined_paths
    assert any(guard.MEASURED_FILES[0].startswith(path) for path in combined_paths)


def test_ci_workflow_guard_step_carries_no_failure_tolerance() -> None:
    """Once wired into ci.yml, the guard step is structurally unable to soft-fail."""
    workflow_path = (
        Path(__file__).resolve().parents[3] / ".github" / "workflows" / "ci.yml"
    )
    workflow = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    steps = workflow["jobs"]["test"]["steps"]
    step = next(
        (s for s in steps if s.get("name") == "Guard against a vacuous coverage gate"),
        None,
    )
    if step is None:
        pytest.skip("guard step not yet wired into ci.yml")

    assert "continue-on-error" not in step
    assert "|| true" not in step.get("run", "")
    assert "set +e" not in step.get("run", "")
