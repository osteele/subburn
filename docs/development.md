# Development Guide

## Code Style

- Use type hints throughout the codebase
- Prefer `X | Y` syntax over `Union[X, Y]`
- Use `dict[K, V]` instead of `Dict[K, V]`
- Follow functional programming principles
  - Prefer comprehensions or map/filter over reduce
  - Keep functions pure where possible

## Testing

Tests are managed using pytest. Run the test suite:

```bash
just test
```

## Code Quality

We use several tools to maintain code quality:

- `black` - Code formatting
- `ruff` - Linting
- `mypy` - Type checking

Run all checks:

```bash
just check
```

## Development Dependencies

Development dependencies are managed in `pyproject.toml` under the `[dependency-groups]` section:

```toml
[dependency-groups]
dev = [
    "black>=23.12.1",
    "mypy>=1.8.0",
    "ruff>=0.1.9",
    "pytest>=7.4.4"
]
```

## Contributing

1. Create a new branch for your feature
2. Make your changes
3. Ensure all tests pass: `just test`
4. Run code quality checks: `just check`
5. Submit a pull request

## Release Process

1. Update version in `pyproject.toml`
2. Update changelog
3. Create a new release tag
4. Build and publish to PyPI
