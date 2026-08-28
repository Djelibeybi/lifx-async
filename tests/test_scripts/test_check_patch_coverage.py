"""Tests for the deterministic local patch-coverage gate."""

from __future__ import annotations

import json
import runpy
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from scripts import check_patch_coverage as checker


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
    """Create a Git repository with deterministic local identity and no signing."""
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.name", "Patch Coverage Test")
    _git(tmp_path, "config", "user.email", "patch-coverage@example.invalid")
    _git(tmp_path, "config", "commit.gpgsign", "false")
    return tmp_path


def _coverage_entry(
    *,
    executed: list[int] | None = None,
    missing: list[int] | None = None,
    excluded: list[int] | None = None,
    executed_branches: list[list[int]] | None = None,
    missing_branches: list[list[int]] | None = None,
) -> dict[str, Any]:
    """Build the required coverage.py JSON arrays for one source."""
    return {
        "executed_lines": executed or [],
        "missing_lines": missing or [],
        "excluded_lines": excluded or [],
        "executed_branches": executed_branches or [],
        "missing_branches": missing_branches or [],
    }


def _write_coverage(
    repo: Path, files: dict[str, Any], *, branches: bool = True
) -> Path:
    """Write a synthetic branch-aware coverage.py JSON report."""
    path = repo / "coverage.json"
    path.write_text(
        json.dumps({"meta": {"branch_coverage": branches}, "files": files}),
        encoding="utf-8",
    )
    return path


def _source_change(repo: Path) -> tuple[str, Path]:
    """Commit a base, then a small branch-bearing source addition."""
    _write(repo, "sample.py", "def existing():\n    return 1\n")
    base = _commit(repo, "base")
    _write(
        repo,
        "sample.py",
        "def existing():\n"
        "    return 1\n"
        "\n"
        "# explanatory comment\n"
        "def added(flag):\n"
        "    if flag:\n"
        "        return 2\n"
        "    return 3\n",
    )
    _commit(repo, "change")
    return base, repo / "sample.py"


def test_rejects_missing_changed_line(git_repo: Path, monkeypatch, capsys) -> None:
    """An added executable line reported missing fails with its location."""
    base, _ = _source_change(git_repo)
    report = _write_coverage(
        git_repo,
        {"sample.py": _coverage_entry(executed=[5, 6, 7], missing=[8])},
    )
    monkeypatch.chdir(git_repo)

    assert (
        checker.run(
            ["--base", base, "--coverage", str(report), "--source", "sample.py"]
        )
        == 1
    )
    assert "sample.py: missing changed line(s): 8" in capsys.readouterr().err


def test_rejects_missing_changed_branch(git_repo: Path, monkeypatch, capsys) -> None:
    """A missing arc originating on an added executable line fails."""
    base, _ = _source_change(git_repo)
    report = _write_coverage(
        git_repo,
        {
            "sample.py": _coverage_entry(
                executed=[5, 6, 7, 8],
                executed_branches=[[6, 7]],
                missing_branches=[[6, 8]],
            )
        },
    )
    monkeypatch.chdir(git_repo)

    assert (
        checker.run(
            ["--base", base, "--coverage", str(report), "--source", "sample.py"]
        )
        == 1
    )
    assert "sample.py: missing changed branch arc(s): 6->8" in capsys.readouterr().err


def test_accepts_covered_code_and_ignores_comments(
    git_repo: Path, monkeypatch, capsys
) -> None:
    """Covered executable additions pass while added comments need no execution."""
    base, _ = _source_change(git_repo)
    report = _write_coverage(
        git_repo,
        {
            "sample.py": _coverage_entry(
                executed=[5, 6, 7, 8],
                executed_branches=[[6, 7], [6, 8]],
            )
        },
    )
    monkeypatch.chdir(git_repo)

    assert (
        checker.run(
            ["--base", base, "--coverage", str(report), "--source", "sample.py"]
        )
        == 0
    )
    output = capsys.readouterr().out
    assert "4 changed executable lines, 2 changed branches" in output


def test_rejects_changed_source_absent_from_report(
    git_repo: Path, monkeypatch, capsys
) -> None:
    """A report cannot pass vacuously when it omits a requested changed file."""
    base, _ = _source_change(git_repo)
    report = _write_coverage(git_repo, {})
    monkeypatch.chdir(git_repo)

    assert (
        checker.run(
            ["--base", base, "--coverage", str(report), "--source", "sample.py"]
        )
        == 1
    )
    assert "changed source absent from coverage JSON" in capsys.readouterr().err


def test_rejects_added_excluded_line(git_repo: Path, monkeypatch, capsys) -> None:
    """An added executable line classified only as excluded fails explicitly."""
    base, _ = _source_change(git_repo)
    report = _write_coverage(
        git_repo,
        {"sample.py": _coverage_entry(executed=[5, 6, 7], excluded=[8])},
    )
    monkeypatch.chdir(git_repo)

    assert (
        checker.run(
            ["--base", base, "--coverage", str(report), "--source", "sample.py"]
        )
        == 1
    )
    assert "sample.py: changed excluded line(s): 8" in capsys.readouterr().err


@pytest.mark.parametrize(
    "marker",
    [
        "# pragma:" + " no cover",
        "# pragma:" + " no branch",
        "# coverage:" + " ignore",
        "@pytest.mark." + "skip",
        "@pytest.mark." + "skipif(True, reason='x')",
        "pytest." + "skip('x')",
        "pytest." + "importorskip('x')",
        "@unittest." + "skip('x')",
        "@unittest." + "skipIf(True, 'x')",
        "@unittest." + "skipUnless(False, 'x')",
    ],
)
def test_rejects_added_coverage_or_skip_marker(
    marker: str, git_repo: Path, monkeypatch, capsys
) -> None:
    """Every prohibited added exemption or skip form fails the full-diff scan."""
    _write(git_repo, "README.md", "base\n")
    base = _commit(git_repo, "base")
    _write(git_repo, "marker.py", f"{marker}\n")
    _commit(git_repo, "marker")
    monkeypatch.chdir(git_repo)

    assert checker.run(["--base", base, "--check-weakening-only"]) == 1
    assert "marker.py:1" in capsys.readouterr().err


def test_pre_base_marker_does_not_fail(git_repo: Path, monkeypatch, capsys) -> None:
    """The weakening scan considers additions after the supplied base only."""
    marker = "# pragma:" + " no cover"
    _write(git_repo, "legacy.py", f"value = 1  {marker}\n")
    base = _commit(git_repo, "base with legacy marker")
    _write(git_repo, "new.py", "value = 2\n")
    _commit(git_repo, "clean change")
    monkeypatch.chdir(git_repo)

    assert checker.run(["--base", base, "--check-weakening-only"]) == 0
    assert "PASS weakening scan" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("field", "bad_value"),
    [
        ("executed_lines", None),
        ("missing_lines", "bad"),
        ("excluded_lines", [False]),
        ("executed_branches", [[1]]),
        ("missing_branches", [[1, "two"]]),
    ],
)
def test_rejects_missing_or_malformed_coverage_arrays(
    field: str,
    bad_value: Any,
    git_repo: Path,
    monkeypatch,
    capsys,
) -> None:
    """Every line and branch array is required and structurally validated."""
    base, _ = _source_change(git_repo)
    entry = _coverage_entry(executed=[5, 6, 7, 8])
    entry[field] = bad_value
    report = _write_coverage(git_repo, {"sample.py": entry})
    monkeypatch.chdir(git_repo)

    assert (
        checker.run(
            ["--base", base, "--coverage", str(report), "--source", "sample.py"]
        )
        == 1
    )
    assert field in capsys.readouterr().err


def test_rejects_report_without_branch_data(
    git_repo: Path, monkeypatch, capsys
) -> None:
    """Line-only coverage reports cannot prove the branch gate."""
    base, _ = _source_change(git_repo)
    report = _write_coverage(git_repo, {}, branches=False)
    monkeypatch.chdir(git_repo)

    assert (
        checker.run(
            ["--base", base, "--coverage", str(report), "--source", "sample.py"]
        )
        == 1
    )
    assert "lacks branch data" in capsys.readouterr().err


def test_rejects_invalid_base(git_repo: Path, monkeypatch, capsys) -> None:
    """A syntactically valid but unknown commit SHA fails closed."""
    _write(git_repo, "README.md", "base\n")
    _commit(git_repo)
    monkeypatch.chdir(git_repo)

    assert checker.run(["--base", "0" * 40, "--check-weakening-only"]) == 1
    assert "rev-parse" in capsys.readouterr().err


def test_rejects_deleted_test_file(git_repo: Path, monkeypatch, capsys) -> None:
    """Deleting a test anywhere after the base fails the weakening scan."""
    _write(git_repo, "tests/test_example.py", "def test_example():\n    assert True\n")
    base = _commit(git_repo, "base")
    (git_repo / "tests/test_example.py").unlink()
    _commit(git_repo, "delete test")
    monkeypatch.chdir(git_repo)

    assert checker.run(["--base", base, "--check-weakening-only"]) == 1
    assert "test file deleted" in capsys.readouterr().err


def test_rejects_coverage_configuration_change(
    git_repo: Path, monkeypatch, capsys
) -> None:
    """Changing a coverage or patch-target configuration file fails."""
    _write(git_repo, "pyproject.toml", "[tool.coverage.run]\nbranch = true\n")
    base = _commit(git_repo, "base")
    _write(git_repo, "pyproject.toml", "[tool.coverage.run]\nbranch = false\n")
    _commit(git_repo, "weaken coverage")
    monkeypatch.chdir(git_repo)

    assert checker.run(["--base", base, "--check-weakening-only"]) == 1
    assert "coverage configuration changed" in capsys.readouterr().err


def test_git_diagnostics_cover_stderr_stdout_and_empty(monkeypatch) -> None:
    """Git failures retain the best available diagnostic and fail closed."""
    for result, expected in (
        (SimpleNamespace(returncode=1, stderr="stderr\n", stdout="stdout\n"), "stderr"),
        (SimpleNamespace(returncode=1, stderr="", stdout="stdout\n"), "stdout"),
        (SimpleNamespace(returncode=1, stderr="", stdout=""), "unknown git error"),
    ):
        monkeypatch.setattr(
            subprocess, "run", lambda *args, result=result, **kwargs: result
        )
        with pytest.raises(checker.PatchCoverageError, match=expected):
            checker._run_git(["status"])


def test_git_must_be_available(monkeypatch) -> None:
    """The checker fails closed when Git cannot be resolved."""
    monkeypatch.setattr(checker, "GIT_EXECUTABLE", None)
    with pytest.raises(checker.PatchCoverageError, match="git executable not found"):
        checker._run_git(["status"])


def test_rejects_non_full_base(capsys) -> None:
    """Abbreviated commit IDs cannot silently move the patch boundary."""
    assert checker.run(["--base", "abc123", "--check-weakening-only"]) == 1
    assert "full 40-character" in capsys.readouterr().err


def test_parse_added_lines_handles_all_unified_diff_line_forms() -> None:
    """The parser handles additions, context, removals, markers, and malformed hunks."""
    diff = "\n".join(
        (
            "diff --git a/sample.py b/sample.py",
            "--- a/sample.py",
            "+++ b/sample.py",
            "@@ -1,2 +1,3 @@",
            " context",
            "-removed",
            "+added",
            "\\ No newline at end of file",
            "? malformed",
            "+ignored outside active hunk",
            "+++ /dev/null",
            "@@ -1 +0,0 @@",
            "+ignored deleted target",
        )
    )

    assert checker.parse_added_lines(diff) == [
        checker.AddedLine("sample.py", 2, "added")
    ]


def test_branch_array_must_itself_be_a_list() -> None:
    """A scalar branch field is rejected before individual arc validation."""
    with pytest.raises(checker.PatchCoverageError, match="array of"):
        checker._branch_set(None, "executed_branches", "sample.py")


def test_normalises_absolute_report_paths(monkeypatch, tmp_path: Path) -> None:
    """Absolute in-repository report keys become relative; others stay absolute."""
    monkeypatch.chdir(tmp_path)
    assert (
        checker._normalise_report_path(str(tmp_path / "src/sample.py"))
        == "src/sample.py"
    )
    assert checker._normalise_report_path("/outside/sample.py") == "/outside/sample.py"


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ("not json", "cannot read coverage JSON"),
        ("[]", "root must be an object"),
        ('{"meta": {"branch_coverage": true}, "files": []}', "files must be an object"),
        (
            '{"meta": {"branch_coverage": true}, "files": {"sample.py": []}}',
            "entries must map paths to objects",
        ),
    ],
)
def test_rejects_malformed_coverage_document(
    payload: str, expected: str, tmp_path: Path
) -> None:
    """Malformed report containers fail before patch measurement."""
    report = tmp_path / "coverage.json"
    report.write_text(payload, encoding="utf-8")
    with pytest.raises(checker.PatchCoverageError, match=expected):
        checker.load_coverage(report)


def test_rejects_unreadable_coverage_document(tmp_path: Path) -> None:
    """A missing report fails closed with its path."""
    with pytest.raises(checker.PatchCoverageError, match="cannot read coverage JSON"):
        checker.load_coverage(tmp_path / "missing.json")


def test_coverage_requires_sources(git_repo: Path, monkeypatch, capsys) -> None:
    """Coverage mode cannot pass without an explicit changed-source target."""
    _write(git_repo, "README.md", "base\n")
    base = _commit(git_repo)
    report = _write_coverage(git_repo, {})
    monkeypatch.chdir(git_repo)

    assert checker.run(["--base", base, "--coverage", str(report)]) == 1
    assert "at least one --source" in capsys.readouterr().err


def test_rejects_requested_source_without_additions(
    git_repo: Path, monkeypatch, capsys
) -> None:
    """A requested source must have additions after the immutable base."""
    _write(git_repo, "sample.py", "value = 1\n")
    base = _commit(git_repo, "base")
    _write(git_repo, "README.md", "change\n")
    _commit(git_repo, "unrelated")
    report = _write_coverage(git_repo, {"sample.py": _coverage_entry(executed=[1])})
    monkeypatch.chdir(git_repo)

    assert (
        checker.run(
            ["--base", base, "--coverage", str(report), "--source", "sample.py"]
        )
        == 1
    )
    assert "no added lines found" in capsys.readouterr().err


def test_rejects_patch_without_executable_lines(
    git_repo: Path, monkeypatch, capsys
) -> None:
    """A comment-only patch cannot provide vacuous patch-coverage evidence."""
    _write(git_repo, "sample.py", "value = 1\n")
    base = _commit(git_repo, "base")
    _write(git_repo, "sample.py", "value = 1\n# comment only\n")
    _commit(git_repo, "comment")
    report = _write_coverage(git_repo, {"sample.py": _coverage_entry(executed=[1])})
    monkeypatch.chdir(git_repo)

    assert (
        checker.run(
            ["--base", base, "--coverage", str(report), "--source", "sample.py"]
        )
        == 1
    )
    assert "no changed executable lines" in capsys.readouterr().err


def test_rejects_malformed_name_status(monkeypatch) -> None:
    """Unexpected Git name-status output fails instead of weakening the scan."""
    monkeypatch.setattr(checker, "_run_git", lambda args: "malformed")
    with pytest.raises(checker.PatchCoverageError, match="cannot parse"):
        checker.check_weakening("0" * 40)


def test_rejects_exact_tests_directory_deletion(monkeypatch) -> None:
    """The top-level tests path receives the same deletion protection as its files."""
    monkeypatch.setattr(checker, "_run_git", lambda args: "D\ttests")
    with pytest.raises(checker.PatchCoverageError, match="test file deleted"):
        checker.check_weakening("0" * 40)


def test_rejects_conflicting_weakening_arguments(
    git_repo: Path, monkeypatch, capsys
) -> None:
    """Weakening-only mode cannot accept coverage-mode arguments."""
    _write(git_repo, "README.md", "base\n")
    base = _commit(git_repo)
    monkeypatch.chdir(git_repo)

    assert (
        checker.run(
            [
                "--base",
                base,
                "--check-weakening-only",
                "--coverage",
                "coverage.json",
            ]
        )
        == 1
    )
    assert "cannot be combined" in capsys.readouterr().err


def test_coverage_mode_requires_report(git_repo: Path, monkeypatch, capsys) -> None:
    """Default mode requires an explicit coverage.py JSON report."""
    _write(git_repo, "README.md", "base\n")
    base = _commit(git_repo)
    monkeypatch.chdir(git_repo)

    assert checker.run(["--base", base]) == 1
    assert "--coverage is required" in capsys.readouterr().err


def test_script_entrypoint_exits_with_run_status(git_repo: Path, monkeypatch) -> None:
    """Direct execution preserves the library entrypoint's process status."""
    _write(git_repo, "README.md", "base\n")
    base = _commit(git_repo)
    monkeypatch.chdir(git_repo)
    monkeypatch.setattr(
        sys,
        "argv",
        [str(Path(checker.__file__)), "--base", base, "--check-weakening-only"],
    )

    with pytest.raises(SystemExit, match="0"):
        runpy.run_path(str(Path(checker.__file__)), run_name="__main__")
