# External Integrations

**Analysis Date:** 2026-04-16

## APIs & External Services

**LIFX Protocol Specification (build-time only):**
- Service: LIFX public-protocol GitHub repository
- Purpose: Source of truth for protocol packet definitions
- URL: `https://raw.githubusercontent.com/LIFX/public-protocol/refs/heads/main/protocol.yml`
- Client: `urllib.request.urlopen` (stdlib) in `src/lifx/protocol/generator.py`
- Auth: None (public repository)
- Usage: Downloaded on-demand during code generation, never stored locally

**LIFX Products Registry (build-time only):**
- Service: LIFX products GitHub repository
- Purpose: Device capability database (product IDs, features, device class mapping)
- URL: `https://raw.githubusercontent.com/LIFX/products/refs/heads/master/products.json`
- Client: `urllib.request.urlopen` (stdlib) in `src/lifx/products/generator.py`
- Auth: None (public repository)
- Usage: Downloaded on-demand during code generation, never stored locally

**LIFX Devices (runtime - local network):**
- Service: LIFX smart light hardware on local network
- Purpose: Primary functionality - device discovery and control
- Protocol: LIFX LAN Protocol over UDP (port 56700)
- Discovery methods:
  - UDP broadcast (`src/lifx/network/discovery.py`)
  - mDNS/DNS-SD multicast at 224.0.0.251:5353 (`src/lifx/network/mdns/`)
- Auth: None (local network, no authentication)
- Connection: `src/lifx/network/connection.py` (lazy-opening, auto-retry)

## Data Storage

**Databases:**
- None. Library operates entirely in-memory with no persistence layer.

**File Storage:**
- Local filesystem only (no cloud storage)
- Auto-generated source files committed to repo:
  - `src/lifx/protocol/packets.py` - Generated packet classes
  - `src/lifx/protocol/protocol_types.py` - Generated enums and field structures
  - `src/lifx/products/registry.py` - Generated product database

**Caching:**
- In-memory state caching on device objects (configurable TTL)
- No external cache service

## Authentication & Identity

**Auth Provider:**
- Not applicable. LIFX LAN protocol requires no authentication.
- Local network UDP communication only.

## Monitoring & Observability

**Error Tracking:**
- None (library, not a service)
- Custom exception hierarchy in `src/lifx/exceptions.py`

**Logs:**
- No logging framework integrated
- Library consumers handle their own logging

**Coverage:**
- Codecov - Coverage tracking and PR reporting
  - Config: `codecov.yml`
  - Token: `CODECOV_TOKEN` secret in GitHub Actions
  - Flags: per-Python-version coverage (3.10, 3.11, 3.12, 3.13, 3.14)

## CI/CD & Deployment

**Hosting:**
- PyPI - Package distribution (`https://pypi.org/p/lifx-async`)
  - Trusted publisher (OIDC, no API token needed)
  - Published via `pypa/gh-action-pypi-publish`
- GitHub Pages - Documentation site (`https://djelibeybi.github.io/lifx-async`)
  - Deployed via `mkdocs gh-deploy`

**CI Pipeline:**
- GitHub Actions (3 workflows):
  - `ci.yml` - Quality checks, test matrix, semantic release, PyPI deploy
  - `docs.yml` - Documentation build, link validation, GitHub Pages deploy
  - `pr-automation.yml` - Auto-labelling, size labels, PR title validation
- pre-commit.ci - Automated hook execution and auto-fix on PRs

**Release Automation:**
- python-semantic-release - Automated version bumping from conventional commits
  - Config: `pyproject.toml` `[tool.semantic_release]`
  - Version source: `pyproject.toml:project.version`
  - Changelog: auto-generated to `docs/changelog.md`
  - Branch strategy: `main` = stable releases, other branches = dev pre-releases

**Dependency Automation:**
- Renovate Bot - Automated dependency PRs
  - Config: `renovate.json`
  - Schedule: weekday nights and weekends (Australia/Melbourne timezone)
  - Auto-merge: dev dependencies, patch/minor pytest updates, linting tools, GitHub Actions
  - Lock file maintenance: weekly (Monday before 5am)
  - Vulnerability alerts: auto-merged with no minimum release age

## Environment Configuration

**Required env vars:**
- None for library usage

**CI-specific secrets (GitHub Actions):**
- `GITHUB_TOKEN` - Standard GitHub token for releases, PR automation
- `DEPLOY_KEY` - SSH key for semantic-release git push
- `CODECOV_TOKEN` - Coverage upload authentication

**Optional env vars (testing):**
- `LIFX_EMULATOR_EXTERNAL` - Set to `1` to use external emulator instance
- `LIFX_EMULATOR_PORT` - Port for external emulator (default: 56700)

**Secrets location:**
- GitHub Actions secrets (repository settings)
- No local secrets files needed

## Webhooks & Callbacks

**Incoming:**
- Renovate Bot webhook (GitHub App) - Dependency update PRs
- pre-commit.ci webhook (GitHub App) - Hook auto-updates and auto-fixes

**Outgoing:**
- Codecov upload (from CI) - Coverage and test results
- PyPI publish (from CI) - Package distribution via OIDC trusted publisher

---

*Integration audit: 2026-04-16*
