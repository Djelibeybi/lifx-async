# Workflow: lifx-async

## TDD Policy

**Strict** — Tests required before implementation.

- Modified code: 100% coverage required
- New code: >95% coverage required
- Tests mirror source structure: `tests/test_<module>/test_<file>.py`

## Commit Strategy

**Conventional Commits** — enforced by python-semantic-release.

Format: `type(scope): description`

Types: feat, fix, refactor, test, docs, chore, ci, style, build

Commits must be signed (`git commit -s`) with GPG key.

## Code Review

Required for non-trivial changes.

## Verification Checkpoints

At track completion only — no intermediate manual verification required.

## Task Lifecycle

1. **Pending** — Task created, not started
2. **In Progress** `[~]` — Work actively underway
3. **Complete** `[x]` — Implementation done, tests passing
4. **Blocked** — Waiting on dependency or decision

## Quality Gates

- `uv run ruff format .` — Code formatting
- `uv run ruff check . --fix` — Linting with auto-fix
- `uv run pyright` — Type checking
- `uv run --frozen pytest` — Full test suite
