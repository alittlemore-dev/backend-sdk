.DEFAULT_GOAL := help

TARGETS := install lock lock-check lint format format-check fix types test coverage bandit audit security build package-check quality clean
.PHONY: help $(TARGETS)

help:
	@printf '%s\n' \
	  'install        Install the package and locked development tools' \
	  'lock           Resolve dependencies intentionally' \
	  'lock-check     Check that uv.lock matches pyproject.toml' \
	  'lint           Check Python code with Ruff' \
	  'format-check   Check Python formatting' \
	  'format / fix   Format code / apply safe lint fixes' \
	  'types          Run strict mypy' \
	  'test           Run tests' \
	  'coverage       Run tests with a 95% branch coverage gate' \
	  'security       Run Bandit and audit locked dependencies' \
	  'build          Build and validate wheel and sdist metadata' \
	  'package-check  Build, install, and test wheel and sdist in isolation' \
	  'quality        Run all required quality gates' \
	  'clean          Remove generated build and coverage outputs'

install lock lock-check:
	bash scripts/install.sh $@

lint format format-check fix:
	bash scripts/lint.sh $@

types:
	bash scripts/types.sh

test coverage:
	bash scripts/test.sh $@

bandit audit security:
	bash scripts/security.sh $@

build package-check:
	bash scripts/build.sh $@

quality:
	bash scripts/quality.sh

clean:
	bash scripts/clean.sh
