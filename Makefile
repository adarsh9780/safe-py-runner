SHELL := /bin/bash

VERSION ?=
POS_VERSION := $(word 2,$(MAKECMDGOALS))
EFFECTIVE_VERSION := $(if $(VERSION),$(VERSION),$(POS_VERSION))

.PHONY: help help-push help-release help-tag check-message check-version check-input-version check-version-different-from-pyproject check-no-version-arg check-pyproject-version check-tag-not-latest set-version metadata test test-docker git-add git-commit git-push git-tag push release

help:
	@echo "Usage:"
	@echo "  make test"
	@echo "  make test-docker"
	@echo "  make git-add"
	@echo "  make git-commit"
	@echo "  make git-push"
	@echo "  make set-version X.Y.Z"
	@echo "  make git-tag"
	@echo "  make push"
	@echo "  make release"
	@echo "  make help-push"
	@echo "  make help-release"
	@echo "  make help-tag"
	@echo ""
	@echo "Targets:"
	@echo "  help          Show available commands"
	@echo "  help-push     Show details for push workflow"
	@echo "  help-release  Show details for release workflow"
	@echo "  help-tag      Show details for tag workflow"
	@echo "  git-add       Stage all changes"
	@echo "  git-commit    Commit using commit_message.txt with validations"
	@echo "  git-push      Push current branch to origin main"
	@echo "  git-tag       Create and push release tag using pyproject.toml version"
	@echo "  set-version   Update pyproject.toml project version"
	@echo "  check-version Validate current version in pyproject.toml"
	@echo "  test          Run test suite"
	@echo "  test-docker   Run Docker integration tests (requires Docker daemon)"
	@echo "  push          Validate message, test, commit, and push to main"
	@echo "  release       Bump version, regenerate metadata, test, commit, push, and tag"

help-push:
	@echo "Manual commit flow:"
	@echo "1) make test"
	@echo "2) make git-add"
	@echo "3) make git-commit"
	@echo "4) make git-push"
	@echo ""
	@echo "Shortcut:"
	@echo "make push"
	@echo "Runs smart flow:"
	@echo "- if there are local file changes: check-message -> test -> git-add -> git-commit -> git-push"
	@echo "- if there are no local file changes: git-push only"
	@echo "Requirement for git-commit path: commit_message.txt must exist, be non-empty, and differ from the latest commit message."

help-release:
	@echo "Release flow:"
	@echo "1) make set-version X.Y.Z"
	@echo "2) make metadata"
	@echo "3) make test"
	@echo "4) make git-add"
	@echo "5) make git-commit"
	@echo "6) make git-push"
	@echo "7) make git-tag"
	@echo ""
	@echo "Shortcut:"
	@echo "make release"
	@echo "Runs (fail-fast): metadata -> test -> git-add -> git-commit -> git-push -> git-tag"
	@echo "Requirements: pyproject.toml version must be semantic (e.g., 0.1.2), commit_message.txt must exist, be non-empty, and differ from the latest commit message."
	@echo "Note: metadata generation is skipped when release_metadata.md is missing."

help-tag:
	@echo "make git-tag"
	@echo "Creates and pushes annotated tag using pyproject.toml version."
	@echo "Fails if a version argument is provided, if pyproject.toml version is invalid, or if it equals the latest tag."
	@echo "Example: make set-version 0.1.2 && make git-tag"

check-message:
	@test -s commit_message.txt || (echo "commit_message.txt is missing or empty."; exit 1)
	@last_msg="$$(git log -1 --pretty=%B 2>/dev/null || true)"; \
	current_msg="$$(cat commit_message.txt)"; \
	if [ -n "$$last_msg" ] && [ "$$current_msg" = "$$last_msg" ]; then \
		echo "commit_message.txt matches the latest commit message. Please write a new message."; \
		exit 1; \
	fi

check-input-version:
	@test -n "$(EFFECTIVE_VERSION)" || (echo "Usage: make set-version X.Y.Z"; exit 1)
	@echo "$(EFFECTIVE_VERSION)" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+$$' || (echo "Version must be X.Y.Z"; exit 1)

check-version:
	@$(MAKE) --no-print-directory check-no-version-arg
	@$(MAKE) --no-print-directory check-pyproject-version
	@echo "pyproject.toml version is valid."

check-version-different-from-pyproject: check-input-version
	@pyproject_version="$$(sed -n 's/^version = "\([^"]*\)"/\1/p' pyproject.toml | head -n1)"; \
	if [ "$$pyproject_version" = "$(EFFECTIVE_VERSION)" ]; then \
		echo "Requested version $(EFFECTIVE_VERSION) is already set in pyproject.toml."; \
		echo "Choose a new version."; \
		exit 1; \
	fi

check-no-version-arg:
	@test -z "$(VERSION)" && test -z "$(POS_VERSION)" || (echo "Do not pass a version to this target. Version is read from pyproject.toml."; exit 1)

check-pyproject-version:
	@pyproject_version="$$(sed -n 's/^version = "\([^"]*\)"/\1/p' pyproject.toml | head -n1)"; \
	test -n "$$pyproject_version" || (echo "Could not read version from pyproject.toml"; exit 1); \
	echo "$$pyproject_version" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+$$' || (echo "pyproject.toml version must be X.Y.Z, found: $$pyproject_version"; exit 1)

check-tag-not-latest: check-no-version-arg check-pyproject-version
	@pyproject_version="$$(sed -n 's/^version = "\([^"]*\)"/\1/p' pyproject.toml | head -n1)"; \
	tag="v$$pyproject_version"; \
	last_tag="$$(git describe --tags --abbrev=0 2>/dev/null || true)"; \
	if [ -n "$$last_tag" ] && [ "$$last_tag" = "$$tag" ]; then \
		echo "Tag $$tag matches the latest existing tag. Use a newer version."; \
		exit 1; \
	fi

set-version: check-input-version check-version-different-from-pyproject
	uv run python scripts/set_version.py --version "$(EFFECTIVE_VERSION)"

metadata:
	@if [ -f release_metadata.md ]; then \
		uv run python scripts/generate_release_metadata.py; \
	else \
		echo "release_metadata.md not found; skipping metadata generation."; \
	fi

test:
	uv run --extra dev pytest

test-docker:
	RUN_DOCKER_TESTS=1 uv run --extra dev pytest tests/integration/test_docker_backend.py

git-add:
	git add .

git-commit: check-message
	git commit -F commit_message.txt

git-push:
	git push origin master

git-tag: check-no-version-arg check-pyproject-version check-tag-not-latest
	@pyproject_version="$$(sed -n 's/^version = "\([^"]*\)"/\1/p' pyproject.toml | head -n1)"; \
	tag="v$$pyproject_version"; \
	git tag -a "$$tag" -m "Release $$tag"; \
	git push origin "$$tag"

push:
	@if git diff --quiet && git diff --cached --quiet; then \
		echo "No local changes to commit; running git-push only."; \
		$(MAKE) --no-print-directory git-push; \
	else \
		$(MAKE) --no-print-directory check-message; \
		$(MAKE) --no-print-directory test; \
		$(MAKE) --no-print-directory git-add; \
		$(MAKE) --no-print-directory git-commit; \
		$(MAKE) --no-print-directory git-push; \
	fi

release: check-no-version-arg check-pyproject-version metadata test git-add git-commit git-push git-tag

# Allow positional version args, e.g. `make set-version 0.1.2`.
%:
	@:
