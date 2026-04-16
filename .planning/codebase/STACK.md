# Technology Stack

**Analysis Date:** 2026-04-16

## Languages

**Primary:**
- Python >=3.10 - Entire codebase (tested on 3.10, 3.11, 3.12, 3.13, 3.14)

**Secondary:**
- YAML - Protocol specification source (`protocol.yml`, downloaded from LIFX GitHub)
- JSON - Product registry source (`products.json`, downloaded from LIFX GitHub)

## Runtime

**Environment:**
- CPython 3.10+ (CI default: 3.11)
- asyncio (stdlib) - Core async runtime, no third-party async framework

**Package Manager:**
- uv 0.9.4 (pinned in CI via `astral-sh/setup-uv`)
- Lockfile: `uv.lock` present and committed

## Frameworks

**Core:**
- asyncio (stdlib) - Async networking, UDP transport, device communication
- No external runtime dependencies (zero-dependency library)

**Testing:**
- pytest >=8.4.2 - Test runner (`pyproject.toml` `[tool.pytest.ini_options]`)
- pytest-asyncio >=0.24.0 - Async test support (mode: `auto`, loop scope: `function`)
- pytest-cov >=7.0.0 - Coverage reporting (target: 90% project, 100% patch)
- pytest-benchmark >=5.2.3 - Performance benchmarks (marker: `benchmark`)
- pytest-retry >=1.7.0 - Flaky test retry
- pytest-sugar >=1.1.1 - Progress bar output
- pytest-timeout >=2.4.0 - Test timeout enforcement (default: 30s, method: thread)
- lifx-emulator-core >=3.1.0 - Embedded in-process protocol emulator for integration tests

**Build/Dev:**
- hatchling >=1.27.0 - Build backend (`pyproject.toml` `[build-system]`)
- ruff >=0.14.2 - Linting and formatting (line-length: 88, target: py310)
- pyright >=1.1.407 - Static type checking (mode: `standard`, Python 3.10 target)
- bandit - Security scanning (skips: B101, B311)
- pre-commit - Git hooks (formatting, linting, security, spell check, conventional commits)
- codespell - Spell checking
- commitizen - Conventional commit enforcement

**Documentation:**
- mkdocs-material >=9.6.22 - Documentation site framework
- mkdocstrings[python] >=0.30.1 - Auto-generated API docs from docstrings (Google style)
- mkdocs-git-revision-date-localized-plugin >=1.4.7 - Git-based page dates
- mkdocs-llmstxt >=0.4.0 - LLM-friendly documentation output (`llms-full.txt`)

**Release:**
- python-semantic-release - Automated versioning and changelog (conventional commits)
- pypa/gh-action-pypi-publish - PyPI publishing via trusted publisher (OIDC)

## Key Dependencies

**Critical (Runtime):**
- None. Zero runtime dependencies. The library uses only Python stdlib.

**Critical (Dev/Build):**
- pyyaml >=6.0.3 - Protocol generator parses YAML specification
- lifx-emulator-core >=3.1.0 - Embedded emulator for integration testing
- typing-extensions >=4.15.0 - Backported typing features for Python 3.10 compatibility
- prek >=0.3.6 - Dev utility

**Infrastructure:**
- hatchling - Wheel/sdist build backend
- uv - Dependency resolution, virtual environment management, script running

## Configuration

**Environment:**
- No `.env` files detected or required
- `LIFX_EMULATOR_EXTERNAL` - Optional: use external emulator instance for testing
- `LIFX_EMULATOR_PORT` - Optional: port for external emulator (default: 56700)
- No secrets or API keys required for library operation (local network UDP only)

**Build:**
- `pyproject.toml` - All project metadata, tool configuration, build settings
- `uv.lock` - Locked dependency versions (committed to repo)
- `.pre-commit-config.yaml` - Pre-commit hook definitions
- `mkdocs.yml` - Documentation site configuration
- `codecov.yml` - Coverage reporting configuration (90% project target, 100% patch)
- `renovate.json` - Automated dependency update configuration

**Linting/Formatting (all in `pyproject.toml`):**
- Ruff format: double quotes, 4-space indent, 88 char line length
- Ruff lint rules: E, F, I, N, W, UP (pycodestyle, pyflakes, isort, naming, warnings, pyupgrade)
- Pyright: standard mode, Python 3.10 target, excludes generators and auto-generated files

**Code Generation:**
- `src/lifx/protocol/generator.py` - Downloads `protocol.yml` from GitHub, generates `packets.py` and `protocol_types.py`
- `src/lifx/products/generator.py` - Downloads `products.json` from GitHub, generates `registry.py`
- Generated files are committed but verified fresh in CI (`generated-files` job)

## Platform Requirements

**Development:**
- Python 3.10+ with uv installed
- `uv sync` installs all dev dependencies
- Pre-commit hooks: `pre-commit install`
- No OS-specific requirements (tested on Ubuntu, macOS, Windows in CI)

**Production:**
- Python 3.10+ (any OS)
- Zero external dependencies
- Local network access (UDP port 56700 for LIFX devices, mDNS port 5353 for discovery)
- Published on PyPI as `lifx-async`: `pip install lifx-async`

**CI/CD:**
- GitHub Actions (3 workflows: `ci.yml`, `docs.yml`, `pr-automation.yml`)
- Test matrix: 5 Python versions x 3 OSes (PRs with source changes) or Ubuntu-only (main pushes)
- pre-commit.ci for automated hook updates and auto-fixes

---

*Stack analysis: 2026-04-16*
