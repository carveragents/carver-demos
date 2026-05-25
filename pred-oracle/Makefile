.PHONY: pull pull-carver pull-kalshi pull-polymarket pull-prices slice build serve clean test lint

# Pull all data sources (run rarely; outputs are checked in)
pull: pull-carver pull-kalshi pull-polymarket pull-prices

pull-carver:
	uv run python build/pull_carver.py

pull-kalshi:
	uv run python build/pull_kalshi.py

pull-polymarket:
	uv run python build/pull_polymarket.py

pull-prices:
	uv run python build/pull_prices.py

# Compute page slices from data/ (run after data/ edits)
slice:
	uv run python build/generate_slices.py

# Build deployable site/ (default daily command)
build: slice
	uv run python build/generate.py

# Local preview
serve: build
	cd site && python -m http.server 8000

# Run tests
test:
	uv run pytest -v

# Lint
lint:
	uv run ruff check build tests
	uv run ruff format --check build tests

# Clean generated output
clean:
	rm -rf build/page_data site .pytest_cache .ruff_cache .mypy_cache
