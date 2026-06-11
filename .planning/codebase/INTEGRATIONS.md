# External Integrations

**Analysis Date:** 2026-06-11

## APIs & External Services

**LIFX Protocol Specification:**
- Service: GitHub (raw content)
- URL: `https://raw.githubusercontent.com/LIFX/public-protocol/refs/heads/main/protocol.yml`
- What it's used for: Source of truth for LIFX wire protocol (packet types, enums, fields, compound structures)
- Client: Python `urllib.request.urlopen()` (stdlib only, no external HTTP library)
- When: On-demand via `uv run python -m lifx.protocol.generator`
- Implementation: `src/lifx/protocol/generator.py` downloads and parses YAML, generates `src/lifx/protocol/packets.py` and `src/lifx/protocol/protocol_types.py`
- Never stored locally: Downloaded, parsed, and code-generated in a single pass

**LIFX Products Registry:**
- Service: GitHub (raw content)
- URL: `https://raw.githubusercontent.com/LIFX/products/refs/heads/master/products.json`
- What it's used for: Product definitions including device capabilities, feature flags, and product class mapping
- Client: Python `urllib.request.urlopen()` (stdlib only)
- When: On-demand via `uv run python -m lifx.products.generator`
- Implementation: `src/lifx/products/generator.py` downloads and parses JSON, generates `src/lifx/products/registry.py`
- Never stored locally: Downloaded, parsed, and code-generated in a single pass

## Data Storage

**Databases:**
- None - Library is stateless and passes-through to device queries

**File Storage:**
- Local filesystem only - No cloud storage integration
- Documentation assets: `docs/` directory (MkDocs)
- Generated code: `src/lifx/protocol/packets.py`, `src/lifx/protocol/protocol_types.py`, `src/lifx/products/registry.py`

**Caching:**
- None built-in - State caching is device-level and application-controlled
- Devices implement optional state TTL via `get_*()` methods (see `src/lifx/devices/base.py`)

## Authentication & Identity

**Auth Provider:**
- None - LIFX devices on local network require no authentication
- Network assumption: Closed local network (LAN) only; devices respond to all requesters

**Device Identification:**
- Serial number: 12-digit hex (MAC-derived, e.g., `d073d5123456`)
- Source ID: Random 4-byte identifier per request for response correlation
- Sequence numbers: 0-255, atomically allocated per request

## Networking

**Device Communication:**
- Protocol: UDP (User Datagram Protocol)
- Port: 56700 (LIFX standard UDP port)
- Address binding: `0.0.0.0` (all interfaces) with broadcast enabled for discovery
- Implementation: `src/lifx/network/transport.py` using asyncio DatagramProtocol
- Features:
  - Async UDP sendto/recvfrom via asyncio event loop
  - Queue-based packet buffering (max 1000 packets)
  - Dropped packet logging at 1st and every 100th loss
  - Configurable socket options: broadcast, reuseaddr

**Discovery Methods:**

1. **UDP Broadcast Discovery:**
   - Sends GetService packet to 255.255.255.255:56700
   - Collects StateService responses from all devices
   - Timeout: 15 seconds overall, 1 second per-response, 4x idle multiplier (4 seconds with no responses)
   - DoS Protection: Source ID validation, serial validation, broadcast filtering
   - Implementation: `src/lifx/network/discovery.py` → `discover_devices()`

2. **mDNS/DNS-SD Discovery:**
   - Multicast address: 224.0.0.251:5353 (standard mDNS)
   - Service type: `_lifx._udp.local`
   - Queries: PTR (service discovery), SRV (service records), A (IPv4 addresses), TXT (metadata)
   - DNS wire format parser: Fully custom, zero-dependency implementation in `src/lifx/network/mdns/dns.py`
   - Transport: `src/lifx/network/mdns/transport.py` using asyncio multicast UDP
   - Single query returns all devices (faster than UDP broadcast)
   - Implementation: `src/lifx/api.py` → `discover_mdns()`

**Connection Management:**
- Lazy connection opening: Device connections auto-open on first request
- Per-device connection: One UDP socket per device for concurrent operations
- Request serialization: `_request_lock` (asyncio.Lock) prevents response mixing on same socket
- Retry logic: Default 8 retries with exponential backoff (configurable per device)
- Timeout: 16 seconds default (configurable per device)

## Monitoring & Observability

**Error Tracking:**
- None (external) - Exceptions logged via Python `logging` module
- Exception types: `LifxError` base with subtypes: `LifxDeviceNotFoundError`, `LifxTimeoutError`, `LifxProtocolError`, `LifxConnectionError`, `LifxNetworkError`, `LifxUnsupportedCommandError`
- Implementation: `src/lifx/exceptions.py`

**Logs:**
- Standard Python `logging` module
- Logger names: `lifx.*` (module-level loggers)
- Log levels: INFO, WARNING, ERROR based on severity
- Structured logging: Dict-based messages with context (class, method, action, reason, counts)
- Example: UDP protocol warnings when packets dropped due to queue overflow

## CI/CD & Deployment

**Hosting:**
- PyPI (Python Package Index) - Standard Python package repository
  - Package name: `lifx-async`
  - Distribution: Wheel (`.whl`) and source (`.tar.gz`)
  - URL: `https://pypi.org/project/lifx-async/`

**CI Pipeline:**
- Platform: GitHub Actions
- Workflows: `.github/workflows/`
  - `ci.yml` - Main test and release pipeline
  - `docs.yml` - Documentation build and deploy
  - `pr-automation.yml` - Pull request automation

**Release Process:**
- Tool: python-semantic-release (conventional commits parser)
- Trigger: Automatic on push to `main` (semantic versioning)
- Steps:
  1. Detect version bump from conventional commits
  2. Update version in `pyproject.toml`
  3. Upgrade dependencies with `uv lock --upgrade-package`
  4. Build distribution with `uv build`
  5. Create GitHub release with changelog
  6. Publish to PyPI via `pypa/gh-action-pypi-publish`
- Manual trigger: Workflow dispatch with optional release tag override
- Concurrency: Serialized (cancel in-progress if new push)

**Test Matrix:**
- Python versions: 3.10, 3.11, 3.12, 3.13, 3.14 (5 versions)
- Operating systems (PR with source changes): ubuntu-latest, macos-latest, windows-latest
- Operating systems (main push): ubuntu-latest only (PRs already validated)
- Conditional matrix: Detects source vs CI-only changes to optimize test scope

**Coverage Reporting:**
- Tool: Codecov
- Token: `CODECOV_TOKEN` (GitHub Actions secret)
- Upload: Coverage reports and JUnit XML from each Python version
- Targets: 90% overall project coverage, 100% for patches
- Flags: Per-Python-version flags for carryforward and component breakdown
- Exclusions: Tests, generators, auto-generated files, benchmarks, docs

## Documentation

**Hosting:**
- GitHub Pages - Static site hosting
- Custom domain: https://djelibeybi.github.io/lifx-async
- Source: Built from `docs/` directory via MkDocs

**Build & Deploy:**
- Tool: Zensical (MkDocs wrapper) for local development and build
- Theme: Material for MkDocs (modern, responsive)
- LLM Export: llmstxt-standalone generates `llms-full.txt` for AI/LLM context
- Deployment: GitHub Pages workflow (`.github/workflows/docs.yml`) on push to `main`
- Site config: `mkdocs.yml` with navigation, plugins, extensions

**Site Features:**
- Search with suggestions and highlighting
- Dark/light mode toggle
- Sticky navigation tabs
- Breadcrumb navigation
- API reference via mkdocstrings (auto-generated from docstrings)
- Code copying, annotation, and tabbed examples
- Mermaid diagrams support
- Full-text content indexing

## Webhooks & Callbacks

**Incoming:**
- None - Library is request-driven (no server component)

**Outgoing:**
- None - Library does not call external webhooks

## Environment Configuration

**Required Environment Variables:**
- None - Library operates with zero external configuration
- Optional: `LIFX_EMULATOR_EXTERNAL=1` and `LIFX_EMULATOR_PORT=56700` for external emulator testing

**Secrets Location:**
- PyPI: `CODECOV_TOKEN` (GitHub Actions secret) for coverage reports
- GitHub: `DEPLOY_KEY` (GitHub Actions secret) for semantic-release git operations
- No application secrets required

## Dependabot & Dependency Management

**Dependency Updates:**
- Tool: GitHub Dependabot
- Config: `.github/dependabot.yml`
- Scope: GitHub Actions versions and Python package versions
- Frequency: Automatic PR creation on new releases

**Pre-commit Hooks:**
- Tool: pre-commit.ci (continuous integration)
- Config: `.pre-commit-config.yaml`
- Hooks: Ruff format/lint, uv dependency lock, Commitizen conventional commits, Pyright (manual), Bandit security, Codespell, YAML formatting
- Auto-fix PRs: Enabled - auto-commits fixes on PRs
- Auto-update: Weekly schedule for hook versions
- CI Skip: Expensive hooks (pyright, run-tests) skipped in CI to speed up feedback

---

*Integration audit: 2026-06-11*
