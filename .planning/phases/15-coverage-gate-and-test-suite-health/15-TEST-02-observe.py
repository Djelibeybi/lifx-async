#!/usr/bin/env python3
"""Observe one pytest node in a child interpreter under a wall-clock watchdog.

Invocation (no PEP 723 header on this file; the child must import pytest,
``lifx`` and the plugin stack, and ``uv run`` on an inline-metadata script
resolves those into an isolated environment that carries none of them):

    uv run --frozen python \\
        .planning/phases/15-coverage-gate-and-test-suite-health/15-TEST-02-observe.py \\
        --node <pytest-node-id> --timeout <seconds> --output <path> [--repo-root <dir>]

Running it any other way (a bare ``python`` invocation, or ``uv run`` against
a header-carrying copy) resolves a different, unsynced interpreter and the
child dies at ``import pytest`` rather than observing anything.

The child interpreter is launched with ``sys.executable``, so it is whichever
interpreter this runner itself is running under. That is what lets one
runner file observe both the main checkout (interpreter resolved from the
main checkout's synced environment) and a scratch worktree (interpreter
resolved from that worktree's own ``uv sync --frozen``), depending only on
the working directory ``uv run`` was invoked from.

The recorded failure mode this runner exists to catch happens *after* pytest
reports a result, inside ``threading._shutdown`` awaiting
``concurrent.futures.thread._python_exit``. Suite-level ``pytest-timeout``
cannot fire on that: its thread-based method watches the test, not the
interpreter's shutdown sequence. So the watchdog lives in the child, armed
with ``faulthandler.dump_traceback_later(timeout, exit=True)`` before pytest
is even imported, which forces a hard process exit independent of whether
the interpreter can shut down normally.
"""

from __future__ import annotations

import argparse
import json
import platform
import re

# subprocess is used with fixed argv lists only (git, the child interpreter),
# never a shell.
import subprocess  # nosec B404
import sys
import time
from pathlib import Path

# The child never runs pytest.main(...) and discards the result. pytest.main()
# returns its exit status rather than raising, so a bare call leaves the child
# exiting 0 regardless of what pytest reported: a mistyped node id, a
# collection error or a genuinely failing test would all be recorded as a
# clean exit. The child's exit code is the evidence this whole experiment is
# built on, so it must be pytest's real verdict, propagated via SystemExit.
_CHILD_CODE = """
import faulthandler
import sys

node = sys.argv[1]
timeout = float(sys.argv[2])
# Armed before pytest is imported: the recorded hang happens after pytest
# reports its result, inside interpreter shutdown, where pytest-timeout's
# thread-based watchdog can no longer fire.
faulthandler.dump_traceback_later(timeout, exit=True)

import pytest

# Deliberately not a bare `pytest.main(...)` call. pytest.main() returns its
# exit status rather than raising; discarding that return value would leave
# this child exiting 0 whatever pytest reported, turning every invocation
# into an uninformative clean exit. Propagating it through SystemExit makes
# the child's exit code the evidence signal the parent records.
raise SystemExit(pytest.main([node, "--no-cov", "-p", "no:cacheprovider"]))
"""

_FAULTHANDLER_BANNER_RE = re.compile(r"Timeout \([^)]*\)!")
_STDERR_TAIL_CHARS = 4000
_BACKSTOP_MARGIN_SECONDS = 30.0


def _detect_real_repo_root() -> Path:
    """Return the repository root this runner file itself lives in.

    Used only to classify a ``--repo-root`` argument as "the repository" or
    "a scratch worktree" for redaction purposes; it never appears in the
    written record.
    """
    here = Path(__file__).resolve().parent
    result = subprocess.run(  # nosec B603 B607
        ["git", "-C", str(here), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=True,
    )
    return Path(result.stdout.strip()).resolve()


def _git_head_sha(repo_root: Path) -> str:
    """Return the resolved repo root's current HEAD commit SHA."""
    result = subprocess.run(  # nosec B603 B607
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _test_file_is_dirty(repo_root: Path, node: str) -> bool:
    """Return whether the node's source file has uncommitted changes."""
    test_file = node.split("::", 1)[0]
    result = subprocess.run(  # nosec B603 B607
        ["git", "-C", str(repo_root), "status", "--porcelain", "--", test_file],
        capture_output=True,
        text=True,
        check=True,
    )
    return bool(result.stdout.strip())


def _redact(text: str, replacements: list[tuple[str, str]]) -> str:
    """Replace every occurrence of each real path with its placeholder.

    Applied longest-source-first, so a path nested inside another (the
    virtual environment or the scratch worktree living under the home
    directory) is caught by its own, more specific placeholder before the
    broader one consumes it.
    """
    ordered = sorted(
        {(raw, placeholder) for raw, placeholder in replacements if raw},
        key=lambda item: len(item[0]),
        reverse=True,
    )
    for raw, placeholder in ordered:
        text = text.replace(raw, placeholder)
    return text


def _decode(value: object) -> str:
    """Coerce a captured stdout/stderr value (str, bytes or None) to text."""
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run one pytest node in a child interpreter under a wall-clock "
            "watchdog, recording the child's exit behaviour rather than "
            "only its test result."
        ),
    )
    parser.add_argument(
        "--node",
        required=True,
        help="pytest node id to observe, e.g. path/to/test_file.py::test_name",
    )
    parser.add_argument(
        "--timeout",
        required=True,
        type=float,
        help="in-child faulthandler watchdog in seconds",
    )
    parser.add_argument(
        "--output",
        required=True,
        help=(
            "path the JSON record is written to; required, with no default, "
            "so two observations can never overwrite one file by accident"
        ),
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help=(
            "working directory the child pytest run observes "
            "(default: current directory)"
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)

    resolved_repo_root = Path(args.repo_root).resolve()
    real_repo_root = _detect_real_repo_root()
    is_real_repo = resolved_repo_root == real_repo_root
    repo_root_placeholder = "<repo>" if is_real_repo else "<worktree>"

    venv_root = Path(sys.prefix).resolve()
    home_dir = Path.home().resolve()

    replacements: list[tuple[str, str]] = [
        (str(real_repo_root), "<repo>"),
        (str(resolved_repo_root), repo_root_placeholder),
        (str(venv_root), "<venv>"),
        (str(home_dir), "<home>"),
    ]

    watchdog_seconds = args.timeout
    backstop_seconds = watchdog_seconds + _BACKSTOP_MARGIN_SECONDS

    child_argv = [sys.executable, "-c", _CHILD_CODE, args.node, str(watchdog_seconds)]

    head_sha = _git_head_sha(resolved_repo_root)
    test_file_dirty = _test_file_is_dirty(resolved_repo_root, args.node)

    start = time.monotonic()
    bound_fired: str | None = None
    try:
        completed = subprocess.run(  # nosec B603
            child_argv,
            cwd=str(resolved_repo_root),
            capture_output=True,
            text=True,
            timeout=backstop_seconds,
        )
        elapsed_seconds = time.monotonic() - start
        exit_code: int | None = completed.returncode
        stderr_raw = _decode(completed.stderr)
    except subprocess.TimeoutExpired as exc:
        # subprocess.run has already killed the child and waited for it by
        # the time this fires; there is no process handle left to act on,
        # so this branch only records which bound fired and what elapsed.
        elapsed_seconds = time.monotonic() - start
        exit_code = None
        stderr_raw = _decode(exc.stderr)
        bound_fired = "parent_backstop"

    faulthandler_banner = bool(_FAULTHANDLER_BANNER_RE.search(stderr_raw))
    if bound_fired is None and faulthandler_banner:
        bound_fired = "child_watchdog"

    stderr_redacted = _redact(stderr_raw, replacements)
    stderr_tail = stderr_redacted[-_STDERR_TAIL_CHARS:]

    # child_argv's first element is sys.executable, an absolute path (the
    # venv interpreter). Redact every element the same way stderr is
    # redacted, or the committed record would carry that path unmasked.
    redacted_child_argv = [_redact(part, replacements) for part in child_argv]

    record = {
        "node": args.node,
        "child_argv": redacted_child_argv,
        "repo_root": repo_root_placeholder,
        "head_sha": head_sha,
        "test_file_dirty": test_file_dirty,
        "watchdog_seconds": watchdog_seconds,
        "backstop_seconds": backstop_seconds,
        "bound_fired": bound_fired,
        "exit_code": exit_code,
        "elapsed_seconds": elapsed_seconds,
        "faulthandler_banner": faulthandler_banner,
        "stderr_tail": stderr_tail,
        "platform": platform.platform(),
        "python_version": platform.python_version(),
    }

    output_path = Path(args.output)
    output_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")

    print(f"node: {record['node']}")
    print(f"repo_root: {record['repo_root']}")
    print(f"head_sha: {record['head_sha']}")
    print(f"test_file_dirty: {record['test_file_dirty']}")
    print(f"watchdog_seconds: {record['watchdog_seconds']}")
    print(f"backstop_seconds: {record['backstop_seconds']}")
    print(f"bound_fired: {record['bound_fired']}")
    print(f"exit_code: {record['exit_code']}")
    print(f"elapsed_seconds: {record['elapsed_seconds']:.3f}")
    print(f"faulthandler_banner: {record['faulthandler_banner']}")
    print(f"platform: {record['platform']}")
    print(f"python_version: {record['python_version']}")
    print(f"record written to: {output_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
