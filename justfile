default:
    @just --list

# Run all checks (type checking and linting)
check: fix
    uv run --dev ruff check src/
    uv run --dev pyright src/

# Format code
format:
    uv run --dev ruff format src/

# Fix code
fix:
    uv run --dev ruff format src/
    uv run --dev ruff check --fix --unsafe-fixes src/

# Run tests
test *ARGS:
    uv run --dev python -m pytest tests/ {{ARGS}}

# Type check
typecheck:
    uv run --dev pyright src/

# Install the package in development mode
install:
    uv pip install -e .
