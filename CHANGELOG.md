# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Config-driven default policy via `src/safe_py_runner/default_policy.toml`.
- Policy modes: `allow` and `restrict` for imports, builtins, and globals.
- Policy file loading with `run_code(..., policy_file=...)`.
- `RunnerPolicy.from_file(...)` and `RunnerPolicy(config_path=...)`.
- Regression tests for policy mode behavior and policy-file loading.
- Expanded README examples and gotchas coverage.
- Regression tests for `Makefile` quality workflow and documented branch naming.

### Changed
- Removed unused `RestrictedPython` dependency.
- Updated package description wording to match actual execution model.
- `make test` now runs `ruff`, `mypy`, and `pytest`.
- Docs now align release/push guidance with the repository default branch (`master`).
- README and PyPI README now include explicit "good fit" and "not good alone" scope statements.
- "Common Gotchas" sections were refreshed to match current engine, policy, import, and package behavior.
- CI workflow triggers now include `master` (and `main`) to match repository branch usage.

## [0.1.5] - 2026-02-23

### Added
- PyPI-focused package README (`docs/README_PYPI.md`).
- Step-by-step push/release workflow documentation improvements.

### Changed
- Release and publish automation updates for GitHub Releases and PyPI.

## [0.1.4] - 2026-02-23

### Changed
- Finalized release workflow and publish automation.

## [0.1.3] - 2026-02-23

### Fixed
- Release metadata CI behavior and version-source handling.

## [0.1.2] - 2026-02-23

### Fixed
- Release metadata CI behavior and version-source handling.

## [0.1.1] - 2026-02-23

### Added
- Release metadata generator and related workflow documentation.
