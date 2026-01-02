# Refcheck Conversion to Proper Python Project

## Overview

Convert refcheck from a single-file script to a self-contained Python project at `~/tools/refcheck`.

## Current State

- **Location**: `~/tools/refcheck` (modular Python package)
- **Tests**: `~/tools/refcheck/tests/` (pytest, 69 tests)
- **Config**: `~/.config/refcheck/config.toml` (user settings)
- **Rules**: `~/.config/refcheck/repos/{safe-path}/rules.json` (per-repo learned patterns)
- **Installation**: `uv tool install -e ~/tools/refcheck`

## Decisions

1. **Location**: `~/tools/refcheck` (standalone tool outside dotfiles)
2. **CLI framework**: Keep argparse (no Typer)
3. **Config format**: TOML for config, JSON for rules (current setup)
4. **Migration**: Rules files stay at `~/.config/refcheck/repos/*/rules.json`

## Project Structure

```text
~/tools/refcheck/
├── pyproject.toml
├── refcheck/
│   ├── __init__.py
│   ├── cli.py           # argparse CLI entry point
│   ├── config.py        # Config dataclass, load_config()
│   ├── checker.py       # ReferenceChecker class
│   ├── rules.py         # Rules loading/learning
│   ├── suggestions.py   # File similarity/suggestions
│   └── output.py        # Result formatting/printing
└── tests/
    ├── __init__.py
    ├── conftest.py          # pytest fixtures
    ├── test_config.py       # Config and duration parsing tests
    ├── test_rules.py        # Rules loading/saving tests
    ├── test_suggestions.py  # File similarity tests
    └── test_integration.py  # End-to-end CLI tests (ported from bash)
```

## Implementation Phases

### Phase 1: Quick Fixes (COMPLETE)

- [x] Remove hardcoded pattern check
- [x] Switch to time-based learning (6 months)
- [x] Add stale rules warning
- [x] Add config.toml support

### Phase 2: Project Restructure (COMPLETE)

- [x] Create ~/tools/refcheck directory structure
- [x] Add pyproject.toml with uv/pip install support
- [x] Split code into modules:
  - [x] config.py - Config dataclass, parse_duration_to_days, load_config
  - [x] rules.py - load_rules, get_rules_path, learn_rules_from_git
  - [x] suggestions.py - find_similar_files, build_file_index
  - [x] checker.py - ReferenceChecker class (core checking logic)
  - [x] output.py - print_results, Issue/Warning formatting
  - [x] cli.py - argparse setup, main()
- [x] Update dotfiles to install from ~/tools/refcheck (via uv tool install -e)
- [x] Remove old apps/common/refcheck

### Phase 3: Test Migration (COMPLETE)

- [x] Create pytest test suite in ~/tools/refcheck/tests/
- [x] Port existing bash tests to pytest (69 tests total)
- [x] Add unit tests per module (config, rules, suggestions)
- [x] Remove old tests/apps/test-refcheck.sh

## Notes

- Keep argparse for simplicity (no Typer dependency)
- No Pydantic needed - simple dataclass works fine
- Tool installed via `uv tool install` or symlink
