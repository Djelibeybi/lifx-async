# Technology Stack

**Analysis Date:** 2026-06-11

## Languages

**Primary:**
- Python 3.10, 3.11, 3.12, 3.13, 3.14 - Core library implementation, type-checked with Pyright in strict mode

**Secondary:**
- YAML - Protocol specification source format (downloaded, not stored)
- JSON - Product registry source format (downloaded, not stored)

## Runtime

**Environment:**
- Python built-in `asyncio` - Async/await event loop framework for concurrent device communication

**Package Manager:**
- `uv` (v0.9.4+) - Modern Python dependency manager for development and packaging
- Lockfile: `uv.lock` present

## Frameworks

**Core:**
- AsyncIO (built-in) - Single-threaded event loop for concurrent UDP communication with LIFX devices

**Testing:**
- pytest (8.4.2+) - Test runner and framework
  - pytest-asyncio (0.24.0+) - AsyncIO test fixture management
  - pytest-cov (7.0.0+) - Code coverage reporting with branch coverage
  - pytest-timeout (2.4.0+) - Test execution timeout protection
  - pytest-benchmark (5.2.3+) - Performance baseline benchmarking
  - pytest-retry (1.7.0+) - Flaky test retry support
  - pytest-sugar (1.1.1+) - Enhanced test output formatting

**Build/Dev:**
- hatchling (1.27.0+) - Build backend and package builder
- ruff (0.14.2+) - Unified Python formatter and linter (E, F, I, N, W, UP rules)
- pyright (1.1.407+) - Strict static type checker (standard mode, Python 3.10 target)
- bandit - Security vulnerability scanner (B101, B311 skipped)

**Documentation:**
- zensical (0.0.37+) - MkDocs site builder with hot reload
- mkdocstrings-python (2.0.3+) - Python docstring-to-docs with Google/NumPy style support
- llmstxt-standalone (0.2.0+) - LLM-optimized documentation generator
- MkDocs Material theme - Modern responsive documentation theme

**Code Generation:**
- pyyaml (6.0.3+) - YAML parsing for protocol generation from specification
- lifx-emulator-core (3.1.0+, dev only) - Embedded in-process LIFX device emulator for integration testing

## Key Dependencies

**Runtime (Zero Dependencies!):**
- None - Library is completely dependency-free for production use

**Development Dependencies (Selected Critical):**
- lifx-emulator-core (3.1.0+) - Provides embedded emulator for testing all device types without network hardware
- typing-extensions (4.15.0+) - Python 3.10 compatibility for newer typing features
- pyyaml (6.0.3+) - Required for auto-generating protocol and product registry from YAML/JSON specifications

## Configuration

**Environment:**
- Development: `uv sync` installs all dependencies including dev tools
- Production: `uv sync --no-dev` installs zero runtime dependencies
- Python version: Managed by `.python-version` file or explicit selection in CI/CD

**Build:**
- `pyproject.toml` - Single source of truth for project metadata, dependencies, and tool configuration
  - Semantic versioning with python-semantic-release
  - Tool configuration: ruff, pyright, pytest, coverage, bandit
- `uv.lock` - Frozen dependency lock file for reproducible installs

**Testing Configuration (`pyproject.toml`):**
- Test paths: `tests/` directory
- Python path: `src/` added for imports
- Test discovery: `test_*.py` files, `Test*` classes, `test_*` functions
- Coverage targets: 90% overall, 100% for patches
- Timeout: 30 seconds per test
- Markers: `@pytest.mark.emulator` for tests requiring lifx-emulator-core

**Type Checking:**
- Strict mode: `standard` (equivalent to mypy strict with some Pyright enhancements)
- Python target: 3.10
- Include: `src/` only
- Exclude: Generator files (untyped YAML parsing) and auto-generated registry

## Platform Requirements

**Development:**
- OS: macOS, Windows, Linux (tested on all three in CI)
- Python: 3.10+ (tested on 3.10, 3.11, 3.12, 3.13, 3.14 in parallel)
- uv: v0.9.4+ (installed via `astral-sh/setup-uv` GitHub Action)

**Production:**
- OS: Any (macOS, Linux, Windows via WSL)
- Python: 3.10+ (no external dependencies)
- Network: Local network access to LIFX devices (UDP port 56700, mDNS multicast 224.0.0.251:5353)

---

*Stack analysis: 2026-06-11*
