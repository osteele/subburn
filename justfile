default:
    @just --list

# Run all checks (type checking and linting)
check: fix
    uv run --dev python -m mypy src/
    uv run --dev ruff check src/
    uv run --dev python -m black --check src/

# Format code
fmt:
    uv run --dev python -m black src/
    uv run --dev python -m ruff check --fix src/

# Fix code
fix:
    uv run --dev python -m ruff check --fix src/

# Run tests
test:
    uv run --dev python -m pytest tests/

# Install the package in development mode
install:
    uv pip install -e ".[dev]"
