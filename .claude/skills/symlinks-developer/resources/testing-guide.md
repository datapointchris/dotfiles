# Symlinks Testing Guide

## Test Structure

```text
tools/symlinks/
├── tests/
│   ├── test_utils.py         # Unit tests for utilities
│   ├── test_integration.py   # Integration tests
│   └── conftest.py           # Pytest fixtures
└── symlinks/
    ├── manager.py            # Main symlink manager
    └── utils.py              # Utility functions
```

## Running Tests

```bash
# All tests
cd tools/symlinks
pytest -v

# Unit tests only
pytest tests/test_utils.py -v

# Integration tests only
pytest tests/test_integration.py -v

# With coverage
pytest --cov=symlinks --cov-report=term-missing
```

## Key Test Fixtures

**temp_repo**: Creates temporary dotfiles structure with common/ and platform/ directories

**mock_home**: Creates temporary HOME directory for testing symlinks

## Critical Test Cases

1. **Exclusion Pattern Matching**
   - Test that `.git/` doesn't exclude `.gitconfig`
   - Test that `.config/` doesn't exclude non-directory `.config` file
   - Test directory vs file pattern matching

2. **Relative Path Calculation**
   - Test symlinks at different nesting levels
   - Test cross-directory symlinks
   - Test symlinks with walk_up=True

3. **Platform Layering**
   - Test common/ files symlinked on all platforms
   - Test platform-specific overrides
   - Test conflict resolution

4. **Edge Cases**
   - Empty directories
   - Broken symlinks
   - Circular symlinks (should error)

## Test Coverage Target

Maintain >90% code coverage across all modules.
