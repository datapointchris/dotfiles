# refcheck

Fast reference validator for codebases. Finds broken file references and old path patterns.

## What it does

`refcheck` validates file references across your codebase, checking for:

1. **Broken source statements** - Missing files in `source` commands
2. **Broken script references** - Missing files in `bash` or `sh` commands
3. **Old path patterns** - Stale references after refactoring

## Why use it

**Proactive error detection:**

- Catch broken references before running expensive test suites
- Find issues in seconds vs minutes for full e2e tests
- Validate changes before committing

**Refactoring safety:**

- After moving files, verify all references updated
- Find stale patterns across entire codebase
- Custom pattern checking for any refactoring

**Better than grep:**

- Validates file existence, not just pattern matching
- Automatically filters false positives (docs, planning, dynamic paths)
- Structured output with suggestions
- Exit codes for CI/CD integration

## Installation

Symlinked to `~/.local/bin/refcheck` via:

```bash
task symlinks:link
```

## Usage

```bash
# Validate all references in current directory
refcheck

# Check specific directory
refcheck management/

# Find old pattern after refactoring
refcheck --pattern "old/path/" --desc "Update to new/path/"

# Filter by file type (like fd -e)
refcheck --type sh apps/

# Skip documentation files
refcheck --skip-docs

# Combine filters
refcheck --pattern "FooClass" --type py --skip-docs src/
```

## Common workflows

### After moving files

```bash
# Moved management/tests/ to tests/install/
refcheck --pattern "management/tests/"
# Finds all stale references across repo
```

### Before running tests

```bash
# Quick validation (2 seconds vs 10+ minutes for e2e tests)
refcheck --skip-docs
# Catches broken references early
```

### Check specific component

```bash
# Validate management/ directory only
refcheck management/

# Check only shell scripts in apps/
refcheck apps/ --type sh
```

## Output

**When issues found:**

```yaml
❌ Found 3 broken reference(s)

Broken Source (1):
────────────────────────────────────────────────────────────
  src/install.sh:15
    Missing: /path/to/missing.sh
    → Verify path exists or update reference

Old Pattern (2):
────────────────────────────────────────────────────────────
  src/deploy.sh:42
    Found: old/path/
    → Update to new/path/
```

**When all valid:**

```text
✅ All file references valid
```

## Exit codes

- `0` - All references valid
- `1` - Found broken references

Use in scripts:

```bash
if refcheck; then
  echo "All references valid, safe to deploy"
else
  echo "Broken references found, fix before deploying"
  exit 1
fi
```

## Flags

| Flag | Description | Example |
|------|-------------|---------|
| `path` | Directory to check (positional) | `refcheck management/` |
| `--pattern PATTERN` | Find old pattern | `--pattern "old/"` |
| `--desc DESC` | Description for pattern | `--desc "Now new/"` |
| `--type, -t TYPE` | Filter by file type | `--type sh` |
| `--skip-docs` | Skip markdown files | `--skip-docs` |
| `--help, -h` | Show help | `--help` |

## Smart filtering

Automatically excludes:

- **Build artifacts**: `.git`, `node_modules`, `.venv`, `__pycache__`, `site/`
- **Historical files**: `.planning/`, `.claude/metrics/`
- **Dynamic paths**: Container paths (`/root/`, `/home/`), temp files (`/tmp/`)
- **Self-references**: Usage examples in scripts referencing themselves

## Testing

Comprehensive test suite:

```bash
bash tests/apps/test-refcheck.sh
# Tests all flags and combinations
```

## Implementation

**Location:** `apps/common/refcheck`
**Language:** Python 3
**Dependencies:** None (uses stdlib only)

See [source code](../../apps/common/refcheck) for implementation details.

## Comparison to alternatives

**vs grep:**

- `grep` finds patterns but doesn't validate file existence
- `refcheck` validates references point to real files
- `refcheck` auto-filters false positives

**vs shellcheck:**

- `shellcheck` checks literal paths in single files
- `refcheck` checks across entire codebase
- `refcheck` handles dynamic paths and patterns

**vs manual testing:**

- Manual testing requires running full test suite (minutes)
- `refcheck` validates in seconds
- Catches issues before expensive CI/CD runs
