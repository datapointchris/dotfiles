---
icon: material/backup-restore
---

# Backmeup

Create timestamped compressed backups of specified paths with progress tracking and smart exclusions. Automatically excludes development bloat (.venv, node_modules) while preserving version control data. Uses zstd compression with auto-threading for fast, efficient archives.

## Quick Start

```bash
backmeup -n dotfiles -d ~/Documents dotfiles    # Backup to ~/Documents
backmeup -n configs -d ~/Backups .config        # Custom destination
```

Use before potentially destructive operations:

```bash
backmeup -n dotfiles -d ~/Documents dotfiles
git rebase -i HEAD~10        # Safe to proceed
```

## Commands

**Basic Usage**:

```bash
backmeup -n <name> -d <dest> <path1> [path2] [path3...]
```

**Options**:

- `-n, --name <name>` - Backup name (required)
- `-d, --dest <path>` - Destination directory (required)
- `-e, --exclude <pattern>` - Additional exclusion pattern (repeatable)
- `-h, --help` - Show help message

**Path Handling**:

- Supports relative paths: `backmeup -n configs -d ~/Documents dotfiles .config`
- Supports absolute paths: `backmeup -n projects -d ~/Documents ~/code /tmp/projects`
- Supports individual files: `backmeup -n dotfiles -d ~/Documents dotfiles ~/.zshrc`
- Automatically normalizes paths inside/outside home directory

## Archive Format

Archives use timestamped naming:

```text
dotfiles_2025-11-25_143022.tar.zst
learning-docs_2025-11-25_143022.tar.zst    # Custom name
```

Format: `<name>_YYYY-MM-DD_HHMMSS.tar.zst`

Destination must be specified with `-d` (no default). Each backup gets unique timestamp - never overwrites existing archives.

Use `--name` to create descriptive backups:

```bash
backmeup -n learning-docs -d ~/Documents learning
backmeup -n dotfiles-snapshot -d ~/Documents dotfiles .config
```

## Smart Exclusions

Automatically excludes common bloat while keeping important data:

**Python**: .venv, **pycache**, *.pyc, .pytest_cache

**Node**: node_modules

**Build artifacts**: dist/, build/

**Caches**: .mypy_cache, .ruff_cache, .DS_Store

**Keeps**: .git directories, source code, documentation

Add per-invocation exclusions with `--exclude`:

```bash
backmeup -n dotfiles -d ~/Documents --exclude .git --exclude '*.log' dotfiles
backmeup -n code -d ~/Documents --exclude 'target' code
```

Exclude patterns defined in the script at `apps/common/backmeup`.

## How It Works

Uses modern tools for performance:

- Multi-threaded zstd compression (level 3, auto-detect cores)
- Background processes for responsive progress updates
- Rainbow progress indicators with organic time-based updates

Typical performance for ~3000 files:

- Compression: 15-30 seconds
- Compression ratio: 60-80% (depends on file types)

**Safety Features**:

- Validates all paths exist before starting
- Ctrl+C cleanly terminates background processes and removes temporary files
- No overwrites - unique timestamps prevent conflicts

## Workflow

Check backup size before running:

```bash
du -sh .claude notes learning obsession code
```

Create backup before risky operations:

```bash
backmeup -n important -d ~/Documents .claude learning notes obsession code
# Proceed with git rebase, major refactoring, etc.
```

Customize destination for external drives:

```bash
backmeup -n dotfiles -d /Volumes/External dotfiles code
```

## See Also

- [Tool Composition](../architecture/tool-composition.md) - How backmeup fits into the toolchain
- [Bash Script Testing](../learnings/bash-script-testing.md) - Development lessons
