.PHONY: test lint validate crosswalk generate check-generated oracle

test:
	uv run pytest

lint:
	uv run ruff check src tests
	uv run ruff format --check src tests

validate:
	uv run oab validate --tasks tasks

# Crosswalk records validate; prints framework coverage.
crosswalk:
	uv run oab crosswalk --dir crosswalks

generate:
	uv run oab generate --all --out tasks

# Fail if committed tasks drift from the generators.
check-generated: generate
	git diff --exit-code -- tasks

# Requires Harbor + Docker: solvability of every Stable task.
oracle:
	harbor run -p tasks -a oracle
