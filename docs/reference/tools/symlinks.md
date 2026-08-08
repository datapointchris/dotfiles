# Symlinks Manager

Cross-platform dotfiles symlink manager with layered architecture.

## Commands

All symlinks commands are run via Task from the dotfiles root directory. The tool uses `uv run` internally for project-local execution.

### task symlinks:link

Deploy symlinks for current platform (common + platform layers). Create-only: it
adds links and refreshes the ones it already owns, but **does not prune** a link
whose source is gone. Removing or renaming a file needs `relink`.

```bash
task symlinks:link         # Create and refresh; never prunes
```

Use when adding new dotfiles.

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

**Platform overlay** (`macos/`, `wsl/`, `archlinux/`, `linux/`):

- Platform-specific configs
- Overrides or extends common configs
- Linked second (can override common)
- Optional per layer: a minimal platform like `linux` ships only a shell
  overlay (`shell/linux/`) and no `configs/linux/` or `apps/linux/`. `link` and
  `relink` skip a missing layer instead of erroring; only a platform absent from
  every layer (a typo) fails.

**Conflict handling**:

- File vs file: Platform overlay wins
- Directory vs directory: Merged (both symlinked)
- File vs directory: Error (must resolve manually)

## Targets this manager did not create

A link pass replaces a target only when it owns it — a symlink pointing into the
repo, including a broken one left by a deleted source. Anything else (a real
file, or a symlink pointing somewhere else) is **refused, listed, and left
untouched**, and the run exits non-zero.

This is not politeness about a user's files. The write is an unlink followed by a
symlink, so it removes whatever is at the path, and `uv tool dir --bin` is
`~/.local/bin` — the same directory the apps layer links into. Without the check,
installing this project as a uv tool and then running a link pass means the
second silently deletes the executable that the first installed.

`--force` adopts refused targets, which is what a machine that already had
dotfiles of its own needs on first install:

```bash
uv run symlinks link macos --force
```

**A name `[project.scripts]` declares is skipped outright, `--force` or not.**
The two are competing for one path and the declaration wins; there is no state of
the machine in which linking an `apps/` file over the console script is right.
The names are read from `pyproject.toml` rather than from the installed
distribution, because during a bootstrap nothing is installed yet and the answer
has to be the same either way.

## Special Directory Handling

The symlinks manager maps `apps/` and `shell/` to specific target directories rather than `$HOME`, using the same `create_symlinks` function with a custom `target_dir`.

**Shell scripts** (`apps/common/notes`, `apps/common/review-diff`, etc.):

- Symlinked to `~/.local/bin/`
- Examples: `notes`, `patterns`, `_aws-profiles`
- An app whose job is to change the calling shell adds a function in `shell/common/functions.sh`;
  the symlinked command cannot export into the shell that ran it

**Shell source files** (`shell/common/functions.sh`, `shell/common/aliases.sh`, `shell/{platform}/{platform}.sh`):

- Symlinked to `~/.local/shell/`
- Common: `functions.sh` + `aliases.sh` on all platforms
- Platform-specific: `macos.sh`, `archlinux.sh`, `wsl.sh`, `linux.sh` — only the resolved platform's file is linked
- `~/.local/shell/local.sh` is the exception to everything here: a real file, not a symlink, holding machine-local shell code that exists in no repo. `remove_symlinks` only unlinks what resolves into the source tree, so `relink` leaves it alone
- These are shell code (functions + aliases), not config — `~/.local/shell/` is intentional

**Go apps** (toolbox, sesh):

- Installed from GitHub via `go install` (defined in `packages.yml`)
- Development in `~/tools/toolbox/`
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

Tests live under `tests/symlinks/`, with the rest of the suite, and run on every
commit:

```bash
uv run pytest tests/symlinks/
```

They sat in `symlinks/tests/` until 2026-08-08 and were collected by nothing —
`testpaths` names `tests` only, so the whole file ran for no one. A test
directory outside the collected root is worse than no tests, because the count
reads as coverage.

Tests cover:

- Link creation and unlinking
- Conflict detection
- Platform overlay logic
- Cross-platform path resolution
- Edge cases (loops, permissions)

## Configuration

Exclusion patterns in `src/dotfiles/symlinks/core.py` (`EXCLUDE_PATTERNS` constant):

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

See: `docs/learnings/symlinks-path-gotchas.md`

### Relative Path Calculation

**Problem**: Manual path calculation broke 122 symlinks

**Fix**: Use Python stdlib `Path.relative_to(walk_up=True)` (Python 3.12+)

See: `docs/learnings/symlinks-path-gotchas.md`

### Cross-Platform Files

**Problem**: Some files needed on all platforms weren't symlinked

**Fix**: Test edge cases - `.gitconfig`, `.gitignore`, `.gitattributes` should NEVER be excluded

See: `docs/learnings/symlinks-path-gotchas.md`

## Troubleshooting

**Symlinks not created**:

- Run with verbose flag: `uv run symlinks -v link macos`
- Check for permission errors
- Verify source files exist in dotfiles repo

**Broken symlinks**:

- Run `task symlinks:check`, which finds and removes them
- Re-run: `task symlinks:link`

Do not sweep them by hand with a `find -delete` across `$HOME`. That deletes
every broken link on the machine, including ones this manager never created and
is not responsible for; `check` only touches links resolving into the repo.

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

The manager is a subpackage of the repo's Python package, at
`src/dotfiles/symlinks/` — `cli.py` for the Typer interface, `core.py` for all
logic. Dependencies and the entry point are declared in the root
`pyproject.toml`. Run from anywhere with `uv run symlinks`.

It sat at `symlinks/` in the repo root until 2026-08-08, when the repo adopted a
single `src/dotfiles/` package. The version it reports now comes from the
installed distribution's metadata rather than a literal, so it cannot drift from
`pyproject.toml`.

**Dependencies**: typer (CLI framework), rich (console output)

**Python version**: whatever `requires-python` in the root `pyproject.toml` says.
The floor this module itself needs is 3.12, for `Path.relative_to(walk_up=True)`.

## See Also

- [Learnings: Symlinks Path Gotchas](../../learnings/symlinks-path-gotchas.md)
