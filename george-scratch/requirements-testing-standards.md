# Requirements: Integrate Type Checking and Linting into Standard Testing

**Date:** 2026-02-12
**Requestor:** David Parker
**Priority:** High (Code Quality)
**Status:** New

## Problem Statement

Currently, type checking (mypy) and linting are not part of the standard test suite. This means:
1. Type errors can be introduced without detection
2. Code quality issues can slip through
3. Developers must remember to run type checking manually
4. CI/CD may not catch type/lint issues

## Requirements

### Functional Requirements

**FR1: Type Checking in Test Suite**
- `mypy` should run as part of the standard test command
- Type checking should fail the test suite if errors are found
- Should run on all source code: `src/logai/`

**FR2: Linting in Test Suite**
- Standard linter (ruff, flake8, or pylint) should run as part of tests
- Linting should fail the test suite if errors are found
- Should check for code quality, unused imports, etc.

**FR3: Pre-commit Integration**
- Type checking and linting should run on git commit
- Use pre-commit hooks to enforce before code is committed
- Allow developers to bypass in emergencies with `--no-verify`

**FR4: pytest Integration**
- Type checking and linting should integrate with pytest
- Should show clear error messages when failures occur
- Should be fast (parallel execution if possible)

## Implementation Options

### Option 1: pytest Plugin (Recommended)
Use pytest plugins to integrate type checking and linting:
- `pytest-mypy` for type checking
- `pytest-ruff` or `pytest-flake8` for linting

**Pros:**
- Seamless pytest integration
- Single command: `pytest` runs everything
- Clear test output format
- Easy to configure

**Cons:**
- Adds dependencies

### Option 2: tox
Use tox to orchestrate multiple test environments

**Pros:**
- Industry standard
- Good for CI/CD
- Multiple Python version testing

**Cons:**
- More complex setup
- Slower execution

### Option 3: Makefile/Script
Create a test script that runs pytest, mypy, and linter separately

**Pros:**
- Simple, no extra dependencies
- Full control

**Cons:**
- Not integrated with pytest
- Less convenient

## Recommendation

**Use Option 1: pytest plugins with pre-commit hooks**

This provides the best developer experience:
- Single command: `pytest` runs all checks
- Pre-commit catches issues before commit
- Standard Python ecosystem tools

## Implementation Plan

### 1. Add Dependencies

Add to `pyproject.toml`:
```toml
[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-asyncio>=0.21.0",
    "pytest-mock>=3.10.0",
    "pytest-mypy>=0.10.0",      # NEW
    "pytest-ruff>=0.2.0",        # NEW
    "mypy>=1.0.0",
    "ruff>=0.1.0",
    "pre-commit>=3.0.0",         # NEW
]
```

### 2. Configure mypy

Create/update `pyproject.toml`:
```toml
[tool.mypy]
python_version = "3.11"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = false  # Start lenient, tighten later
check_untyped_defs = true
warn_redundant_casts = true
warn_unused_ignores = true
strict_optional = true

[[tool.mypy.overrides]]
module = "boto3.*"
ignore_missing_imports = true

[[tool.mypy.overrides]]
module = "botocore.*"
ignore_missing_imports = true

[[tool.mypy.overrides]]
module = "aiofiles.*"
ignore_missing_imports = true
```

### 3. Configure ruff

Add to `pyproject.toml`:
```toml
[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = [
    "E",   # pycodestyle errors
    "W",   # pycodestyle warnings
    "F",   # pyflakes
    "I",   # isort
    "N",   # pep8-naming
    "UP",  # pyupgrade
]
ignore = [
    "E501",  # line too long (handled by formatter)
]

[tool.ruff.lint.per-file-ignores]
"__init__.py" = ["F401"]  # Allow unused imports in __init__
"tests/**/*" = ["F401", "F811"]  # Allow test fixtures
```

### 4. Configure pytest

Update `pyproject.toml`:
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
addopts = [
    "-v",
    "--mypy",           # NEW: Run mypy type checking
    "--ruff",           # NEW: Run ruff linting
    "--tb=short",
]
```

### 5. Setup pre-commit

Create `.pre-commit-config.yaml`:
```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files

  - repo: https://github.com/charliermarsh/ruff-pre-commit
    rev: v0.1.9
    hooks:
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.8.0
    hooks:
      - id: mypy
        additional_dependencies: [types-aiofiles]
        args: [--ignore-missing-imports]
```

### 6. Update Documentation

Update `README.md` and developer docs:
```markdown
## Development

### Running Tests

All tests, type checking, and linting:
```bash
pytest
```

Just unit/integration tests:
```bash
pytest tests/
```

Just type checking:
```bash
mypy src/logai/
```

Just linting:
```bash
ruff check src/logai/
```

### Pre-commit Hooks

Install pre-commit hooks:
```bash
pre-commit install
```

Run manually:
```bash
pre-commit run --all-files
```
```

### 7. Update CI/CD

Ensure CI runs the same checks:
```yaml
- name: Run tests with type checking and linting
  run: pytest
```

## Files to Modify

1. **`pyproject.toml`** - Add dependencies, configure tools
2. **`.pre-commit-config.yaml`** (NEW) - Pre-commit configuration
3. **`README.md`** - Update testing documentation
4. **`docs/development.md`** (if exists) - Add developer guidelines
5. **`.github/workflows/*.yml`** - Update CI to run all checks

## Acceptance Criteria

**AC1:** Running `pytest` executes unit tests, type checking, and linting
**AC2:** Type errors cause test suite to fail
**AC3:** Linting errors cause test suite to fail
**AC4:** Pre-commit hooks prevent committing code with type/lint errors
**AC5:** Clear error messages when checks fail
**AC6:** Documentation explains how to run checks
**AC7:** CI/CD runs all checks automatically

## Migration Strategy

Since we already have some type errors in the codebase:

**Phase 1: Setup Infrastructure (Now)**
- Add pytest plugins
- Configure mypy/ruff with lenient settings
- Setup pre-commit hooks

**Phase 2: Fix Existing Issues (Next)**
- Fix remaining test failures (11 tests)
- Address any critical lint issues
- Get to green state

**Phase 3: Tighten Rules (Future)**
- Gradually increase mypy strictness
- Enable more ruff rules
- Aim for `disallow_untyped_defs = true`

## Non-Goals

- 100% type coverage immediately (gradual improvement)
- Strict typing enforcement (start lenient)
- Reformatting entire codebase (focus on new code)

## References

- pytest-mypy: https://github.com/realpython/pytest-mypy
- pytest-ruff: https://github.com/businho/pytest-ruff
- pre-commit: https://pre-commit.com/
- ruff: https://github.com/astral-sh/ruff
