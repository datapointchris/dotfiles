# Symlinks Manager

Cross-platform dotfiles symlink manager with layered architecture.

## Commands

### symlinks link

Deploy symlinks for a platform.

```bash
symlinks link common       # Link common base layer
symlinks link macos        # Link macOS overlay
symlinks link wsl          # Link WSL Ubuntu overlay
symlinks link arch         # Link Arch Linux overlay
```

Links common base first, then applies platform-specific overlay.

### symlinks relink

Complete refresh (unlink + link).

```bash
symlinks relink macos      # Clean slate, recommended after changes
```

Use after adding/removing files in dotfiles repo to ensure symlinks are current.

### symlinks check

Verify symlink integrity.

```bash
symlinks check             # Find broken symlinks
```

Shows broken symlinks in home directory.

### symlinks unlink

Remove platform symlinks.

```bash
symlinks unlink macos      # Clean up deployed links
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

## Installation

Install as uv tool for global availability:

```bash
cd ~/dotfiles/tools/symlinks
uv tool install .
```

Or run directly without installing:

```bash
cd ~/dotfiles/tools/symlinks
uv run symlinks --help
```

After installation, `symlinks` command available globally.

## When to Relink

Run `symlinks relink <platform>` after:

- Adding new files to dotfiles repo
- Removing files from dotfiles repo
- Moving files between directories
- Changing platform (macos → wsl, etc.)
- Symlink errors or broken links

**Symptom of outdated symlinks**: "module not found" errors in Neovim after creating new files in `common/.config/nvim/lua/` directories.

## Testing

The symlinks tool has comprehensive pytest test suite.

```bash
cd ~/dotfiles/tools/symlinks
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

Exclusion patterns in `tools/symlinks/symlinks/config.py`:

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

- Run with verbose flag: `symlinks link macos -v`
- Check for permission errors
- Verify source files exist in dotfiles repo

**Broken symlinks**:

- Run `symlinks check` to find them
- Remove: `find ~ -type l ! -exec test -e {} \; -delete`
- Re-run: `symlinks relink <platform>`

**File conflicts**:

- Manual resolution required
- Check conflict error message for paths
- Decide: keep existing file or use dotfiles version
- Move existing file to backup, then relink

**Module not found in Neovim**:

- Added new files in `common/.config/nvim/lua/`?
- Run: `symlinks relink macos`
- Restart Neovim

## Development

**Project structure**:

```text
tools/symlinks/
├── symlinks/               # Main package
│   ├── cli.py             # Click CLI
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

**Dependencies**: click (CLI framework)

**Python version**: 3.12+ (requires `Path.relative_to(walk_up=True)`)

## See Also

- [Learnings: Directory Pattern Matching](../learnings/directory-pattern-matching.md)
- [Learnings: Relative Path Calculation](../learnings/relative-path-calculation.md)
- [Learnings: Cross-Platform Symlinks](../learnings/cross-platform-symlink-considerations.md)
- [Skills System](skills.md) - symlinks-developer skill provides context-aware help
