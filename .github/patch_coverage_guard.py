#!/usr/bin/env python3
"""Fail a PR whose changed measured lines went unscored, counted from repo data."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess  # nosec B404 - required for shell-free gh invocation
import sys
import time
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any
from xml.etree import ElementTree  # nosec B405 - job-produced coverage.xml

try:
    import coverage
    import coverage.exceptions
except ModuleNotFoundError as error:  # pragma: no cover - environment guard
    print(f"FAIL: coverage package not available: {error}", file=sys.stderr)
    raise SystemExit(2) from error

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_patch_coverage import (  # noqa: E402
    CoverageEntry,
    PatchCoverageError,
    _added_numbers,
    _run_git,
    diff_added_lines,
    validate_base,
)

# Deliberate private-API reuse: _added_numbers and _run_git are
# underscore-prefixed in check_patch_coverage.py, but both modules live in
# .github/, ship together, and are exercised by the same --tooling test
# suite, so a signature change to either name is made across both files in
# one commit rather than duplicating the git invocation and the
# added-line-grouping walk here.

# The measured-tree rule (SPEC R3), expressed as data rather than prose.
# Kept in sync with pyproject.toml [tool.coverage.run] omit, the --cov=
# targets in [tool.pytest.ini_options] addopts, and codecov.yml's flag
# paths and ignore list by a dedicated configuration-drift test.
MEASURED_PREFIXES = ("src/lifx/",)
MEASURED_FILES = ("scripts/generate_theme_data.py",)
UNMEASURED_PATHS = (
    "src/lifx/protocol/generator.py",
    "src/lifx/protocol/protocol_types.py",
    "src/lifx/products/generator.py",
    "src/lifx/theme/data.py",
)

# The two codecov/patch description forms recorded from live data during the
# phase spec: the scored form and the vacuous form seen on PR #208.
SCORED_DESCRIPTION = re.compile(
    r"^(\d+(?:\.\d+)?)% of diff hit \(target (\d+(?:\.\d+)?)%\)$"
)
VACUOUS_DESCRIPTION = re.compile(r"^Coverage not affected when comparing \S+\.\.\.\S+$")

_STATUS_POLL_INTERVAL_S = 5.0


class VacuousGateError(RuntimeError):
    """The changed measured set is non-empty and the report classified none of it.

    Distinct from PatchCoverageError: this is the vacuous-gate condition
    itself (exit 1), not an operational failure (exit 2) such as a missing
    report or a malformed argument.
    """


def _is_measured(path: str) -> bool:
    """Return whether a repository-relative POSIX path is inside the measured tree."""
    if not path.endswith(".py"):
        return False
    if path in UNMEASURED_PATHS:
        return False
    if path in MEASURED_FILES:
        return True
    return path.startswith(MEASURED_PREFIXES)


_coverage_cache: dict[str, coverage.Coverage] = {}


def _coverage_for(repo_root: Path) -> coverage.Coverage:
    """Return a Coverage object bound to the project's configuration, cached per root.

    Building this once per repository root and reusing it across every
    changed file avoids re-parsing pyproject.toml's [tool.coverage.report]
    exclude_lines on every call.
    """
    key = str(repo_root)
    cached = _coverage_cache.get(key)
    if cached is not None:
        return cached
    config_path = repo_root / "pyproject.toml"
    try:
        cov = coverage.Coverage(config_file=str(config_path))
    except coverage.exceptions.CoverageException as error:
        raise PatchCoverageError(
            f"cannot load coverage configuration {config_path}: {error}"
        ) from error
    _coverage_cache[key] = cov
    return cov


def authoritative_statements(repo_root: str | Path, path: str) -> frozenset[int]:
    """Return the statement lines coverage.py's parser finds in the checked-out file.

    Taken from coverage.Coverage(config_file=...).analysis2() applied to the
    file on disk, never from the coverage report under judgement, so a
    report that omits a real statement can never shrink this denominator. The
    project's own [tool.coverage.report] exclude_lines is already applied by
    analysis2(), so a docstring-only, comment-only, or configured-exclusion
    change contributes nothing here.
    """
    root = Path(repo_root)
    cov = _coverage_for(root)
    try:
        _filename, statements, _excluded, _missing, _missing_formatted = cov.analysis2(
            str(root / path)
        )
    except coverage.exceptions.NoSource:
        print(
            f"WARNING: {path} not found on disk; contributing nothing to "
            "changed measured lines",
            file=sys.stderr,
        )
        return frozenset()
    except coverage.exceptions.CoverageException as error:
        raise PatchCoverageError(f"cannot analyse {path}: {error}") from error
    return frozenset(statements)


def _resolve_class_path(
    filename: str, source_roots: Sequence[Path], repo_root: Path
) -> str | None:
    """Resolve one Cobertura <class filename> against the document's <source> roots.

    Returns a repository-relative POSIX path. Falls back to the filename
    normalised as a POSIX path only when the document carried no <source>
    element at all. When one or more roots are present, a candidate that
    resolves outside repo_root is skipped rather than accepted; if every
    present root resolves outside repo_root, this returns None so an outside
    <source> paired with an inside-looking filename cannot be re-keyed to a
    path inside the repository through the fallback.
    """
    if not source_roots:
        return PurePosixPath(filename).as_posix()

    for root in source_roots:
        candidate = repo_root / root / filename
        try:
            relative = candidate.resolve().relative_to(repo_root)
        except ValueError:
            continue
        return relative.as_posix()

    return None


def load_coverage_xml(path: Path, repo_root: Path) -> dict[str, CoverageEntry]:
    """Parse a Cobertura coverage.xml into the CoverageEntry shape used elsewhere.

    Cobertura carries no notion of an excluded line and no branch arcs, so
    each entry's excluded_lines, executed_branches and missing_branches are
    always empty: the guard only asks whether a line is classified at all,
    which CoverageEntry.executable_lines answers regardless.
    """
    try:
        # coverage.xml is produced by pytest-cov in this same job, never
        # externally supplied.
        tree = ElementTree.parse(path)  # nosec B314
    except (OSError, ElementTree.ParseError) as error:
        raise PatchCoverageError(f"cannot read coverage XML {path}: {error}") from error

    root_element = tree.getroot()
    repo_root = repo_root.resolve()
    source_roots = [
        Path(source.text.strip())
        for source in root_element.findall("./sources/source")
        if source.text and source.text.strip()
    ]

    entries: dict[str, CoverageEntry] = {}
    for class_element in root_element.findall(".//class"):
        filename = class_element.get("filename")
        if not filename:
            continue
        resolved = _resolve_class_path(filename, source_roots, repo_root)
        if resolved is None:
            print(
                f"WARNING: coverage.xml entry for {filename!r} resolves outside "
                "the repository under every <source> root; contributing no "
                "entry for it",
                file=sys.stderr,
            )
            continue

        executed: set[int] = set()
        missing: set[int] = set()
        for line_element in class_element.findall("./lines/line"):
            number_text = line_element.get("number")
            hits_text = line_element.get("hits")
            if number_text is None or hits_text is None:
                raise PatchCoverageError(
                    f"{path}: <line> element for {filename!r} is missing a "
                    "number or hits attribute"
                )
            try:
                number = int(number_text)
                hits = int(hits_text)
            except ValueError as error:
                raise PatchCoverageError(
                    f"{path}: <line> element for {filename!r} has a "
                    "non-integer number or hits attribute"
                ) from error
            if hits > 0:
                executed.add(number)
            else:
                missing.add(number)

        entries[resolved] = CoverageEntry(
            executed_lines=frozenset(executed),
            missing_lines=frozenset(missing),
            excluded_lines=frozenset(),
            executed_branches=frozenset(),
            missing_branches=frozenset(),
        )
    return entries


def measured_changed_lines(
    added: Iterable[Any], report: Mapping[str, CoverageEntry], repo_root: Path
) -> tuple[int, int, list[str]]:
    """Intersect added lines with each measured file's authoritative statement set.

    Returns (changed_measured, scored, unscored_paths). changed_measured and
    scored are computed from the checked-out source, never from report,
    which is the artefact under judgement: a report that omits a statement
    must not be able to remove that statement from the count it is measured
    against. unscored_paths names every measured path in the diff whose
    changed measured lines the report did not fully classify, sorted for
    stable output.
    """
    grouped = _added_numbers(added)
    changed_measured = 0
    scored = 0
    unscored_paths: list[str] = []

    for path in sorted(grouped):
        if not _is_measured(path):
            continue
        statements = authoritative_statements(repo_root, path)
        contributed = grouped[path] & statements
        if not contributed:
            continue
        changed_measured += len(contributed)

        entry = report.get(path)
        path_scored = (
            contributed & entry.executable_lines if entry is not None else set()
        )
        scored += len(path_scored)
        if len(path_scored) < len(contributed):
            unscored_paths.append(path)

    return changed_measured, scored, sorted(unscored_paths)


def _find_patch_entry(payload: Mapping[str, Any]) -> Mapping[str, Any] | None:
    """Return the codecov/patch entry from a combined-status payload, if present."""
    statuses = payload.get("statuses")
    if not isinstance(statuses, list):
        return None
    for status in statuses:
        if isinstance(status, dict) and status.get("context") == "codecov/patch":
            return status
    return None


def _fetch_status_payload(
    head: str, repo: str, status_timeout: float
) -> Mapping[str, Any] | None:
    """Read the combined status via `gh api`, polling while pending or absent.

    A --status-timeout of zero performs exactly one bounded read and never
    polls. The CI invocation always passes zero, because codecov/patch is
    computed only after Codecov has merged the uploads from every matrix
    cell and this step runs inside one of those cells, so an absent or
    pending status is the expected common outcome there rather than a
    defect. A manual run after CI has settled can pass a non-zero timeout to
    wait for a settled result.
    """
    gh_executable = shutil.which("gh")
    if gh_executable is None:
        return None

    deadline = time.monotonic() + max(status_timeout, 0.0)
    while True:
        result = subprocess.run(  # nosec B603 - fixed executable, no shell
            [gh_executable, "api", f"repos/{repo}/commits/{head}/status"],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return None
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError:
            return None
        if not isinstance(payload, dict):
            return None
        entry = _find_patch_entry(payload)
        unresolved = entry is None or entry.get("state") == "pending"
        if not unresolved or time.monotonic() >= deadline:
            return payload
        time.sleep(_STATUS_POLL_INTERVAL_S)


def read_patch_status(
    *,
    head: str | None,
    repo: str | None,
    status_json_path: Path | None,
    status_timeout: float,
    changed_measured: int,
    scored: int,
) -> None:
    """Report the codecov/patch cross-check. Never changes the caller's exit code.

    Reads a recorded combined-status payload from --status-json when given,
    which is what makes the divergence evidence reproducible from fixtures
    with no network and no pull request. Otherwise reads the live status via
    `gh api` when both --head and --repo are given. Prints nothing at all
    when neither source is available. Only the entry's own context, state
    and description are ever printed; never the environment or a token.
    """
    payload: Mapping[str, Any] | None
    if status_json_path is not None:
        try:
            payload = json.loads(status_json_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            print(f"CROSS-CHECK UNUSABLE: cannot read --status-json: {error}")
            return
    elif head is not None and repo is not None:
        payload = _fetch_status_payload(head, repo, status_timeout)
    else:
        return

    if payload is None:
        print("CROSS-CHECK UNUSABLE: gh not on PATH or gh api did not return a report")
        return

    entry = _find_patch_entry(payload)
    if entry is None:
        print("CROSS-CHECK UNUSABLE: no codecov/patch entry in the status payload")
        return

    state = entry.get("state")
    description = entry.get("description") or ""
    if state == "pending":
        print(f"CROSS-CHECK UNUSABLE: codecov/patch is still pending: {description!r}")
        return

    if VACUOUS_DESCRIPTION.match(description):
        if changed_measured > 0:
            print(
                "CROSS-CHECK DIVERGENCE: codecov/patch reported "
                f"{description!r} while changed_measured={changed_measured} "
                f"scored={scored}"
            )
        else:
            print(f"CROSS-CHECK AGREE: codecov/patch reported {description!r}")
        return

    if SCORED_DESCRIPTION.match(description):
        if scored > 0:
            print(
                f"CROSS-CHECK AGREE: codecov/patch reported {description!r} "
                f"and scored={scored}"
            )
        else:
            print(
                "CROSS-CHECK DIVERGENCE: codecov/patch reported "
                f"{description!r} while changed_measured={changed_measured} "
                f"scored={scored}"
            )
        return

    print(
        "CROSS-CHECK UNUSABLE: codecov/patch description matches neither "
        f"recorded form: {description!r}"
    )


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True, help="merge-base ancestor commit SHA")
    parser.add_argument(
        "--coverage", type=Path, help="coverage.py Cobertura XML report"
    )
    parser.add_argument(
        "--head",
        help="pull request head commit SHA, used for the codecov/patch cross-check",
    )
    parser.add_argument(
        "--repo", help="owner/repo, used for the codecov/patch cross-check via gh api"
    )
    parser.add_argument(
        "--status-json",
        type=Path,
        help="replay a recorded combined-status JSON payload instead of calling gh",
    )
    parser.add_argument(
        "--status-timeout",
        type=float,
        default=120.0,
        help="seconds to poll for a settled status; 0 for one bounded read",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="repository root used to resolve changed measured files",
    )
    return parser


def run(argv: Sequence[str] | None = None) -> int:
    """Compute the vacuous-gate decision and return a process exit status."""
    args = build_parser().parse_args(argv)

    try:
        base = validate_base(args.base)
        head = validate_base(args.head) if args.head else None
        merge_base = _run_git(["merge-base", base, "HEAD"]).strip()
        added = diff_added_lines(merge_base)

        if args.coverage is None:
            raise PatchCoverageError("--coverage is required")
        repo_root = Path(args.repo_root).resolve()
        report = load_coverage_xml(args.coverage, repo_root)

        changed_measured, scored, unscored_paths = measured_changed_lines(
            added, report, repo_root
        )
    except PatchCoverageError as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 2

    exit_code = 0
    try:
        if changed_measured == 0:
            print(
                f"PASS: no changed measured lines (changed_measured=0 scored={scored})"
            )
        elif scored == 0:
            paths = ", ".join(unscored_paths) or "(none)"
            raise VacuousGateError(
                "VACUOUS COVERAGE GATE "
                f"changed_measured={changed_measured} scored={scored} "
                f"unscored paths: {paths}"
            )
        elif scored < changed_measured:
            print(
                "WARNING: partially scored "
                f"changed_measured={changed_measured} scored={scored}"
            )
        else:
            print(f"PASS: changed_measured={changed_measured} scored={scored}")
    except VacuousGateError as error:
        print(f"FAIL: {error}", file=sys.stderr)
        exit_code = 1

    read_patch_status(
        head=head,
        repo=args.repo,
        status_json_path=args.status_json,
        status_timeout=args.status_timeout,
        changed_measured=changed_measured,
        scored=scored,
    )

    return exit_code


if "__main__" == __name__:
    raise SystemExit(run())
