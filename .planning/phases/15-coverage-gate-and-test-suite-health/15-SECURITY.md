---
phase: "15"
slug: "coverage-gate-and-test-suite-health"
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
created: "2026-09-07"
---

# Phase 15 Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

The register was authored at plan time across the five plans' `<threat_model>` blocks and is
complete. This audit verified that each declared mitigation exists in the implementation. It did
not scan for new threats, with one exception: two findings from the independent code review in
`15-REVIEW.md` were evaluated because they bear directly on existing register rows.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Collection-time `sys.path` mutation | `.planning/scripts/tests/conftest.py` is an initial-argument conftest reached through `testpaths`, so its three inserts are session-wide | Module search path for every pytest run |
| Test selection policy | The collection hook decides which items run, so a defect changes what "the suite passed" means | Selected and deselected test node ids |
| Measured tree definition | `AGENTS.md`'s Measured Tree rule and `pyproject.toml`'s two `--cov` targets decide what coverage counts | Coverage configuration |
| The CI gate boundary | `.github/patch_coverage_guard.py` decides whether a build fails on a vacuous coverage gate | Merge-base diff, `coverage.xml`, `codecov/patch` status |
| GitHub REST API through `gh` | Advisory status read by the guard, plus two operator-approved issue writes | Commit status, public issue comments |
| Operator hardware tooling output | `.planning/scripts/` scripts and the TEST-02 observer capture live device and filesystem identifiers | Serials, MAC addresses, IP addresses, absolute paths |

---

## Threat Register

47 threats registered, T-15-01 through T-15-47. 44 verified closed, 2 closed by remediation during
this audit, 1 open below the blocking threshold. Full per-threat evidence is in the audit verdict
recorded in the trail below; the register rows themselves live in the five `15-0*-PLAN.md`
`<threat_model>` blocks and are not duplicated here.

| Severity | Registered | Closed | Open |
|----------|-----------|--------|------|
| high | 24 | 24 | 0 |
| medium | 17 | 17 | 0 |
| low | 6 | 5 | 1 |
| **Total** | **47** | **46** | **1** |

Dispositions as registered: 43 `mitigate`, 4 `accept` (T-15-09, T-15-14, T-15-16, T-15-31).

### Threats remediated during this audit

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-15-46 | Denial of Service | The coverage exemption sweep | high | mitigate | The sweep's pathspec included `.github` and `.planning/scripts/tests`, both outside the measured tree by this phase's own `AGENTS.md` rule, leaving it permanently red on two hits that cannot move a coverage number. Pathspec now excludes both while keeping `.planning/scripts` itself so plan 15-02's relocation still pairs as a rename. Commit `55a25c5` | closed |
| T-15-31 | Repudiation | The guard's own test suite outside CI | medium | accept → mitigate | The accepted residual covered `.planning/**` only, and named "a broken guard fails closed" as its compensating control. `.github/**` was also absent from `pull_request.paths`, so for a pull request confined to `.github/*.py` the guard itself did not run either, voiding that control. Filter now names `.github/**`. Commit `55a25c5` | closed |

T-15-46's narrowing was proved not to be a blinding. The sweep stays red on a `pragma` added to
`src/lifx/color.py`, on a `pragma` added at a post-move `.planning/scripts/` path, and on a skip
decorator in an untracked new test file. Its resolved-path floor reads 225 against a threshold
of 100.

T-15-31 was recorded at plan time as `accept` at medium. The auditor did not re-score a plan-time
register, which is the correct restraint, but established that the exposure was broader than the
acceptance covered and that it was phase-introduced rather than inherited: before the relocation,
`check_patch_coverage.py` matched `scripts/**` and its test matched `tests/**`. The operator
elected to fix rather than re-accept, so the row is closed by mitigation.

### Open threats

| Threat ID | Category | Component | Severity | Disposition | Status |
|-----------|----------|-----------|----------|-------------|--------|
| T-15-47 | Denial of Service | Em dash coverage of artefacts written after task 2 | low | mitigate | open, below the high threshold (non-blocking) |

T-15-47's own gate passes over the two files it enumerates, but the phase-level em dash sweep is
red on `15-REVIEW.md` and `15-VERIFICATION.md`, both written after task 2 by the review and
verification steps and neither in the row's two-file list nor in the sweep's exclusion set, which
excludes `15-REVIEWS.md` plural but not the singular code review report. The row's own text records
that it has mis-enumerated twice before; this is the third instance. It is a bookkeeping defect in a
prose style gate over generated audit artefacts, at low severity and below the blocking threshold.

*Status values: `open`, `closed`, or `open, below the high threshold (non-blocking)`*
*Severity ranks critical > high > medium > low. Only open threats at or above workflow.security_block_on count toward threats_open*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| R-15-01 | T-15-09 | Deleting `tests/test_scripts/__init__.py` removes a package marker no longer needed after the relocation. Residual confirmed as stated: `check_patch_coverage.py` is invoked by no workflow and no pre-commit hook | Plan 15-02 | 2026-09-06 |
| R-15-02 | T-15-14 | `xml.etree.ElementTree` parses a `coverage.xml` the job itself produced, so the input is not attacker-supplied. Provenance is stated at the `# nosec B405` and `# nosec B314` annotations | Plan 15-03 | 2026-09-06 |
| R-15-03 | T-15-16 | The guard evaluates a single matrix cell's report; matrix cells cannot union coverage without artefacts. The gap is bounded by measurement and the artefact-plus-union upgrade path is recorded at `ci.yml` | Plan 15-03 | 2026-09-06 |

R-15-04 was expected against T-15-31 but is not recorded: the operator elected to mitigate that
threat rather than accept it. See the remediation table above.

---

## Unregistered Observations

Surface with no register row, carried forward rather than silently dropped. None is a blocking
threat and none was introduced as a mitigation gap.

| # | Observation | Assessment |
|---|-------------|------------|
| 1 | CI's blocking bandit step is `bandit -c pyproject.toml -r src/` only, so every `# nosec` this phase added under `.github/` is unverified by any required CI job. `[tool.pyright] include` was extended to those files; bandit was not | Real gap, no register row. Now partially offset by the `.github/**` trigger fix, which at least makes the job run on those files |
| 2 | `check_weakening()` in `.github/check_patch_coverage.py` is rename-blind: a rename emits `R100 old new`, so the status never starts with `D` and only the new basename is tested. Reproduced against git 2.50.1 defaults | Latent robustness defect, not a live control failure. Predates the phase, unchanged across the fork (`similarity index 100%`), and the tool is invoked by no workflow and no pre-commit hook. Warrants a follow-up issue against the tool |
| 3 | `rich>=15.0.0` in `.planning/scripts/serial_mac_audit.py`'s PEP 723 header appears in neither `pyproject.toml` nor `uv.lock`, so `uv run` resolves it from PyPI outside the lock | Pre-existing and unchanged by the phase (`uv.lock` has a zero-line diff), but plan 02's T-15-SC asserts every declared name already appears in `pyproject.toml`, and that assertion is false for this one |
| 4 | `15-TEST-02-observe.py`'s redaction covers repository root, worktree root, venv root and home directory, but not the platform temp directory | Beyond the declared mitigation rather than a gap in it. T-15-30's four declared roots are all present and the committed records are clean. A future Linux capture could leak an account name via `/tmp/pytest-of-$USER/` |

All five `T-15-SC` supply-chain rows verified closed: `uv.lock` has zero changed lines across the
phase, the four new PEP 723 headers declare only `lifx-async` and `lifx-emulator-core`, and
`15-TEST-02-observe.py` carries no PEP 723 header and imports stdlib only. Observation 3 is the one
qualification on that.

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-09-07 | 47 | 44 | 3 | gsd-security-auditor (initial verdict: OPEN_THREATS) |
| 2026-09-07 | 47 | 46 | 1 | Operator-approved remediation of T-15-46 and T-15-31 in commit `55a25c5` |

Post-remediation gate state: pyright 0 errors, `ruff check .` clean, default suite 4256 passed and
631 deselected, tooling suite 619 passed, `codecov.yml` unchanged across the phase, and
`pyproject.toml`'s coverage `omit` and `exclude_lines` unchanged.

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed (T-15-47 is open at low severity, below the `high` block threshold)
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-09-07
