#!/usr/bin/env python3
"""Assert changed-line and changed-branch coverage from a fixed Git base."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess  # nosec B404 - required for shell-free Git invocation
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

FULL_SHA = re.compile(r"[0-9a-fA-F]{40}")
GIT_EXECUTABLE = shutil.which("git")
HUNK_HEADER = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")
PROTECTED_COVERAGE_FILES = {
    ".coveragerc",
    "codecov.yml",
    "pyproject.toml",
    "setup.cfg",
    "tox.ini",
}
WEAKENING_PATTERNS = (
    ("coverage pragma", re.compile(r"#\s*pragma:\s*no\s+(?:cover|branch)\b")),
    ("coverage ignore", re.compile(r"#\s*coverage:\s*ignore\b")),
    ("pytest skip decorator", re.compile(r"@pytest\.mark\.skip(?:if)?\b")),
    ("pytest imperative skip", re.compile(r"\bpytest\.skip\s*\(")),
    ("pytest importorskip", re.compile(r"\bpytest\.importorskip\s*\(")),
    (
        "unittest skip decorator",
        re.compile(r"@unittest\.skip(?:If|Unless)?\b"),
    ),
)


class PatchCoverageError(RuntimeError):
    """A fail-closed patch-coverage validation error."""


@dataclass(frozen=True)
class AddedLine:
    """One added line from a zero-context Git diff."""

    path: str
    number: int
    content: str


@dataclass(frozen=True)
class CoverageEntry:
    """Validated coverage.py JSON data for one source file."""

    executed_lines: frozenset[int]
    missing_lines: frozenset[int]
    excluded_lines: frozenset[int]
    executed_branches: frozenset[tuple[int, int]]
    missing_branches: frozenset[tuple[int, int]]

    @property
    def executable_lines(self) -> frozenset[int]:
        """Return every line the coverage report classifies."""
        return self.executed_lines | self.missing_lines | self.excluded_lines


def _run_git(args: Sequence[str]) -> str:
    """Run Git and fail with its diagnostic rather than accepting partial data."""
    if GIT_EXECUTABLE is None:
        raise PatchCoverageError("git executable not found")
    result = subprocess.run(  # nosec B603 - fixed executable, no shell
        [GIT_EXECUTABLE, *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "unknown git error"
        raise PatchCoverageError(f"git {' '.join(args)} failed: {detail}")
    return result.stdout


def validate_base(base: str) -> str:
    """Require one full commit SHA and return Git's canonical object ID."""
    if FULL_SHA.fullmatch(base) is None:
        raise PatchCoverageError("--base must be one full 40-character hexadecimal SHA")
    return _run_git(["rev-parse", "--verify", f"{base}^{{commit}}"]).strip()


def parse_added_lines(diff: str) -> list[AddedLine]:
    """Parse added file content and its new-file line numbers from a unified diff."""
    added: list[AddedLine] = []
    path: str | None = None
    next_new_line: int | None = None

    for raw_line in diff.splitlines():
        if raw_line.startswith("+++ "):
            target = raw_line[4:]
            path = None if target == "/dev/null" else target.removeprefix("b/")
            continue
        match = HUNK_HEADER.match(raw_line)
        if match is not None:
            next_new_line = int(match.group(1))
            continue
        if path is None or next_new_line is None:
            continue
        if raw_line.startswith("+") and not raw_line.startswith("+++"):
            added.append(AddedLine(path, next_new_line, raw_line[1:]))
            next_new_line += 1
        elif raw_line.startswith(" "):
            next_new_line += 1
        elif raw_line.startswith("-") or raw_line.startswith("\\"):
            continue
        else:
            next_new_line = None

    return added


def diff_added_lines(
    base: str, sources: Sequence[str] | None = None
) -> list[AddedLine]:
    """Return added lines between the base and working HEAD."""
    args = ["diff", "--no-ext-diff", "--unified=0", f"{base}..HEAD"]
    if sources:
        args.extend(["--", *sources])
    return parse_added_lines(_run_git(args))


def _integer_set(value: Any, field: str, path: str) -> frozenset[int]:
    """Validate a required coverage line-number array."""
    if not isinstance(value, list) or any(
        not isinstance(item, int) or isinstance(item, bool) for item in value
    ):
        raise PatchCoverageError(f"{path}: {field} must be an array of integers")
    return frozenset(value)


def _branch_set(value: Any, field: str, path: str) -> frozenset[tuple[int, int]]:
    """Validate a required coverage branch-arc array."""
    if not isinstance(value, list):
        raise PatchCoverageError(
            f"{path}: {field} must be an array of [source, target]"
        )
    arcs: set[tuple[int, int]] = set()
    for arc in value:
        if (
            not isinstance(arc, list)
            or len(arc) != 2
            or any(not isinstance(item, int) or isinstance(item, bool) for item in arc)
        ):
            raise PatchCoverageError(
                f"{path}: {field} must be an array of integer [source, target] pairs"
            )
        arcs.add((arc[0], arc[1]))
    return frozenset(arcs)


def _normalise_report_path(path: str) -> str:
    """Normalise coverage keys to repository-relative POSIX paths."""
    candidate = Path(path)
    if candidate.is_absolute():
        try:
            candidate = candidate.relative_to(Path.cwd())
        except ValueError:
            return PurePosixPath(path).as_posix()
    return PurePosixPath(candidate.as_posix()).as_posix()


def load_coverage(path: Path) -> dict[str, CoverageEntry]:
    """Load and validate the branch-aware parts of coverage.py JSON."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise PatchCoverageError(
            f"cannot read coverage JSON {path}: {error}"
        ) from error

    if not isinstance(payload, dict):
        raise PatchCoverageError("coverage report root must be an object")
    meta = payload.get("meta")
    if not isinstance(meta, dict) or meta.get("branch_coverage") is not True:
        raise PatchCoverageError("coverage report lacks branch data")
    files = payload.get("files")
    if not isinstance(files, dict):
        raise PatchCoverageError("coverage report files must be an object")

    entries: dict[str, CoverageEntry] = {}
    for raw_path, raw_entry in files.items():
        if not isinstance(raw_path, str) or not isinstance(raw_entry, dict):
            raise PatchCoverageError("coverage file entries must map paths to objects")
        normalised = _normalise_report_path(raw_path)
        entries[normalised] = CoverageEntry(
            executed_lines=_integer_set(
                raw_entry.get("executed_lines"), "executed_lines", normalised
            ),
            missing_lines=_integer_set(
                raw_entry.get("missing_lines"), "missing_lines", normalised
            ),
            excluded_lines=_integer_set(
                raw_entry.get("excluded_lines"), "excluded_lines", normalised
            ),
            executed_branches=_branch_set(
                raw_entry.get("executed_branches"), "executed_branches", normalised
            ),
            missing_branches=_branch_set(
                raw_entry.get("missing_branches"), "missing_branches", normalised
            ),
        )
    return entries


def _added_numbers(lines: Iterable[AddedLine]) -> dict[str, set[int]]:
    """Group parsed additions by repository-relative path."""
    grouped: dict[str, set[int]] = {}
    for line in lines:
        grouped.setdefault(line.path, set()).add(line.number)
    return grouped


def check_coverage(base: str, coverage_path: Path, sources: Sequence[str]) -> None:
    """Fail unless every changed executable line and outgoing arc is covered."""
    if not sources:
        raise PatchCoverageError("at least one --source is required with --coverage")
    report = load_coverage(coverage_path)
    additions = _added_numbers(diff_added_lines(base, sources))
    total_lines = 0
    total_branches = 0

    for source in sources:
        source_path = PurePosixPath(source).as_posix()
        added = additions.get(source_path, set())
        if not added:
            raise PatchCoverageError(
                f"{source_path}: no added lines found from base to HEAD"
            )
        entry = report.get(source_path)
        if entry is None:
            raise PatchCoverageError(
                f"{source_path}: changed source absent from coverage JSON"
            )

        executable = added & entry.executable_lines
        excluded = added & entry.excluded_lines
        missing = executable & entry.missing_lines
        missing_arcs = sorted(
            arc for arc in entry.missing_branches if arc[0] in executable
        )
        all_arcs = entry.executed_branches | entry.missing_branches
        changed_arcs = {arc for arc in all_arcs if arc[0] in executable}

        if excluded:
            lines = ", ".join(str(number) for number in sorted(excluded))
            raise PatchCoverageError(
                f"{source_path}: changed excluded line(s): {lines}"
            )
        if missing:
            lines = ", ".join(str(number) for number in sorted(missing))
            raise PatchCoverageError(f"{source_path}: missing changed line(s): {lines}")
        if missing_arcs:
            arcs = ", ".join(
                f"{source_line}->{target}" for source_line, target in missing_arcs
            )
            raise PatchCoverageError(
                f"{source_path}: missing changed branch arc(s): {arcs}"
            )

        line_count = len(executable)
        branch_count = len(changed_arcs)
        total_lines += line_count
        total_branches += branch_count
        print(
            f"PASS {source_path}: {line_count} changed executable lines, "
            f"{branch_count} changed branches"
        )

    if total_lines == 0:
        raise PatchCoverageError("no changed executable lines were measured")
    print(
        f"PASS total: {total_lines} changed executable lines, "
        f"{total_branches} changed branches"
    )


def check_weakening(base: str) -> None:
    """Reject newly added coverage exemptions, skips, and gate weakening."""
    status_lines = _run_git(["diff", "--name-status", f"{base}..HEAD"]).splitlines()
    for status_line in status_lines:
        fields = status_line.split("\t")
        if len(fields) < 2:
            raise PatchCoverageError(
                f"cannot parse git name-status line: {status_line}"
            )
        status, changed_path = fields[0], fields[-1]
        if status.startswith("D") and (
            changed_path == "tests" or changed_path.startswith("tests/")
        ):
            raise PatchCoverageError(f"{changed_path}: test file deleted")
        if PurePosixPath(changed_path).name in PROTECTED_COVERAGE_FILES:
            raise PatchCoverageError(f"{changed_path}: coverage configuration changed")

    failures: list[str] = []
    for line in diff_added_lines(base):
        for category, pattern in WEAKENING_PATTERNS:
            if pattern.search(line.content):
                failures.append(f"{line.path}:{line.number}: {category}")
    if failures:
        raise PatchCoverageError(
            "coverage/test weakening added:\n" + "\n".join(failures)
        )
    print("PASS weakening scan: no added coverage exemptions, skips, or gate changes")


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True, help="full pre-gap commit SHA")
    parser.add_argument("--coverage", type=Path, help="coverage.py JSON report")
    parser.add_argument(
        "--source", action="append", default=[], help="changed source path"
    )
    parser.add_argument("--check-weakening-only", action="store_true")
    return parser


def run(argv: Sequence[str] | None = None) -> int:
    """Run the requested check and return a process exit status."""
    args = build_parser().parse_args(argv)
    try:
        base = validate_base(args.base)
        if args.check_weakening_only:
            if args.coverage is not None or args.source:
                raise PatchCoverageError(
                    "--check-weakening-only cannot be combined with "
                    "--coverage or --source"
                )
            check_weakening(base)
        else:
            if args.coverage is None:
                raise PatchCoverageError("--coverage is required")
            check_coverage(base, args.coverage, args.source)
    except PatchCoverageError as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    return 0


if "__main__" == __name__:
    raise SystemExit(run())
