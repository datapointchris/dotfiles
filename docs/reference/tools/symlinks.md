# Symlinks Manager

Cross-platform dotfiles symlink manager with layered architecture.

## Commands

All symlinks commands are run via Task from the dotfiles root directory. The tool uses `uv run` internally for project-local execution.

### task symlinks:link

Deploy symlinks for current platform (common + platform layers). Additive only - creates new symlinks without removing existing ones.

```bash
task symlinks:link         # Create symlinks (safe, no removal)
```

Use when adding new dotfiles to create their symlinks without disturbing existing ones.

### task symlinks:relink

Complete refresh - removes all symlinks and recreates them.

```bash
task symlinks:relink       # Full refresh (removes + links)
```

Use after removing files from dotfiles repo or when you need a clean slate.

### task symlinks:check

Verify symlink integrity.

```bash
task symlinks:check        # Find broken symlinks
```

Shows broken symlinks in home directory.

### task symlinks:show

Display current symlinks.

```bash
task symlinks:show         # Show all symlinks
```

### task symlinks:unlink

Remove all symlinks.

```bash
task symlinks:unlink         # Remove all symlinks
```

### Direct Usage (Advanced)

If needed, run the tool directly from dotfiles root:

```bash
uv run symlinks link common
uv run symlinks link macos
uv run symlinks relink macos
uv run symlinks check
```

Pass `-v/--verbose` before the subcommand to show individual file operations:

```bash
uv run symlinks -v link macos      # Show each file as it's linked
uv run symlinks -v relink macos    # Show each file during full refresh
```

## Architecture

The symlinks tool uses a **layered architecture**: common base + platform overlay.

**Common base** (`common/`):

- Shared configs across all platforms
- .zshrc, .config/nvim, .config/tmux, etc.
- Linked first

**Platform overlay** (`macos/`, `wsl/`, `arch/`):

- Platform-specific configs
- Overrides or extends common configs
- Linked second (can override common)

**Conflict handling**:

- File vs file: Platform overlay wins
- Directory vs directory: Merged (both symlinked)
- File vs directory: Error (must resolve manually)

## Special Directory Handling

The symlinks manager has custom handling for `apps/` and `shell/` directories — both are mapped to specific targets rather than `$HOME`.

**Shell scripts** (`apps/common/menu`, `apps/common/notes`, etc.):

- Symlinked to `~/.local/bin/` automatically by `link_apps()`
- Examples: `menu`, `notes`, `patterns`, `aws-profiles`

**Shell source files** (`shell/functions.sh`, `shell/aliases.sh`, `shell/{platform}.sh`):

- Symlinked to `~/.local/shell/` automatically by `link_shell()`
- Common: `functions.sh` + `aliases.sh` on all platforms
- Platform-specific: `{platform}.sh` (macos.sh, arch.sh, wsl.sh)
- These are shell code (functions + aliases), not config — `~/.local/shell/` is intentional

**Go apps** (sess, toolbox):

- Installed from GitHub via `go install` (defined in `packages.yml`)
- Development in `~/tools/sess/`, `~/tools/toolbox/`
- NOT managed by symlinks - binaries go to `~/go/bin/`

**Personal CLI tools** (theme, font):

- Installed via custom installers that clone to `~/.local/share/`
- Symlink `~/.local/share/{tool}/bin/{tool}` → `~/.local/bin/{tool}`
- Development in `~/tools/theme/`, `~/tools/font/`
- NOT managed by symlinks manager - have their own installers

## Usage

The symlinks tool runs via `uv run` from the dotfiles root directory. Use Task commands for the best experience:

```bash
task symlinks:link     # Create symlinks (additive, safe)
task symlinks:relink   # Full refresh (removes + recreates)
task symlinks:check    # Verify symlinks
task symlinks:show     # Display current symlinks
```

No installation required - `uv run` executes the tool in-place.

## When to Link vs Relink

**Use `task symlinks:link`** (additive, safe):

- Adding new files to dotfiles repo
- Adding new dotfile directories
- After fresh install or setup

**Use `task symlinks:relink`** (full refresh):

- Removing files from dotfiles repo
- Moving files between directories
- Fixing broken or stale symlinks
- When you need a clean slate
- Changing platform (macos → wsl, etc.)
- Symlink errors or broken links

**Symptom of outdated symlinks**: "module not found" errors in Neovim after creating new files in `common/.config/nvim/lua/` directories.

## Testing

The symlinks tool has comprehensive pytest test suite.

```bash
cd ~/dotfiles/install/symlinks
pytest -v                              # Run all tests
pytest tests/test_manager.py           # Manager tests
pytest tests/test_integration.py       # Integration tests
pytest test_edge_cases.py              # Edge cases
```

Tests cover:

- Link creation and unlinking
- Conflict detection
- Platform overlay logic
- Cross-platform path resolution
- Edge cases (loops, permissions)

## Configuration

Exclusion patterns in `install/symlinks/symlinks/config.py`:

**Excluded by default**:

- `.git/` directories
- `.DS_Store` files
- `__pycache__/` directories
- `.pytest_cache/` directories
- `.venv/` virtual environments

**Platform-specific exclusions**: Each platform config can define additional exclusions.

## Critical Bugs to Avoid

### Substring Matching

**Problem**: Pattern `.git/` incorrectly excluded `.gitconfig`

**Fix**: Check for `/.git/` or starts with `.git/`, not substring match

See: `docs/learnings/directory-pattern-matching.md`

### Relative Path Calculation

**Problem**: Manual path calculation broke 122 symlinks

**Fix**: Use Python stdlib `Path.relative_to(walk_up=True)` (Python 3.12+)

See: `docs/learnings/relative-path-calculation.md`

### Cross-Platform Files

**Problem**: Some files needed on all platforms weren't symlinked

**Fix**: Test edge cases - `.gitconfig`, `.gitignore`, `.gitattributes` should NEVER be excluded

See: `docs/learnings/cross-platform-symlink-considerations.md`

## Troubleshooting

**Symlinks not created**:

- Run with verbose flag: `uv run symlinks -v link macos`
- Check for permission errors
- Verify source files exist in dotfiles repo

**Broken symlinks**:

- Run `task symlinks:check` to find them
- Remove: `find ~ -type l ! -exec test -e {} \; -delete`
- Re-run: `task symlinks:link`

**File conflicts**:

- Manual resolution required
- Check conflict error message for paths
- Decide: keep existing file or use dotfiles version
- Move existing file to backup, then relink

**Module not found in Neovim**:

- Added new files in `common/.config/nvim/lua/`?
- Run: `task symlinks:link`
- Restart Neovim

## Development

**Project structure**:

```text
install/symlinks/
├── symlinks/               # Main package
│   ├── cli.py             # Typer CLI
│   ├── config.py          # Configuration
│   ├── manager.py         # Core logic
│   └── utils.py           # Helper functions
├── tests/                 # Test suite
│   ├── test_manager.py    # Manager tests
│   ├── test_utils.py      # Utility tests
│   └── test_integration.py  # Integration tests
├── test_edge_cases.py     # Edge case tests
├── pyproject.toml         # uv configuration
├── uv.lock                # Locked dependencies
└── README.md              # Implementation docs
```

**Dependencies**: typer (CLI framework), rich (console output)

**Python version**: 3.12+ (requires `Path.relative_to(walk_up=True)`)

## See Also

- [Learnings: Directory Pattern Matching](../../learnings/directory-pattern-matching.md)
- [Learnings: Relative Path Calculation](../../learnings/relative-path-calculation.md)
- [Learnings: Cross-Platform Symlinks](../../learnings/cross-platform-symlink-considerations.md)
- [Skills System](skills.md) - global skills overview
