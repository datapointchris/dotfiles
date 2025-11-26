# Backup Dirs

Create timestamped compressed backups of important directories with progress tracking and smart exclusions. Automatically excludes development bloat (.venv, node_modules) while preserving version control data.

## Quick Start

```bash
backup-dirs .claude notes learning       # Backup to ~/Documents
backup-dirs --dest ~/Backups dotfiles    # Custom destination
backup-important                         # macOS alias (common dirs)
```

Use before potentially destructive operations:

```bash
backup-important              # Quick safety backup
git rebase -i HEAD~10        # Safe to proceed
```

## Commands

**Basic Usage**:

```bash
backup-dirs <dir1> [dir2] [dir3...]
```

**Common Options**:

- `-d, --dest <path>` - Destination directory (default: ~/Documents)
- `-a, --analyze` - Run analysis phase for percentage (slower, shows progress)
- `--no-analyze` - Skip analysis (default, faster)
- `--zstd` - Use zstd compression (default, 2-3x faster than gzip)
- `--gzip` - Use gzip compression (compatible)
- `--xz` - Use xz compression (best compression)
- `--fast` - Optimize for speed (zstd -1, no analysis)
- `--best` - Optimize for compression (zstd -19)
- `-j, --threads <N>` - Compression threads (default: auto)

**Path Handling**:

- Supports relative paths: `backup-dirs dotfiles .config`
- Supports absolute paths: `backup-dirs ~/code /tmp/projects`
- Automatically normalizes paths inside/outside home directory

## Archive Format

Archives use timestamped naming:

```text
backup-dirs_2025-11-25_143022.tar.zst
```

Format: `backup-dirs_YYYY-MM-DD_HHMMSS.tar.{zst|gz|xz}`

Default location: `~/Documents/` (iCloud synced on macOS)

Each backup gets unique timestamp - never overwrites existing archives.

## Smart Exclusions

Automatically excludes common bloat while keeping important data:

**Python**: .venv, **pycache**, *.pyc, .pytest_cache

**Node**: node_modules, .npm

**Build artifacts**: dist/, build/, target/

**Caches**: .cache, .DS_Store

**Keeps**: .git directories, source code, documentation

Exclude patterns defined in the script at `apps/common/backup-dirs`.

## How It Works

Uses modern tools for performance:

- `fd` for fast file discovery (respects .gitignore with --no-ignore flag)
- Multi-threaded zstd compression (2-3x faster than gzip)
- Background processes for responsive progress updates
- Rainbow progress indicators with organic time-based updates

Typical performance for ~3000 files:

- Analysis: 5-10 seconds (if enabled with --analyze)
- Compression: 15-30 seconds
- Compression ratio: 60-80% (depends on file types)

**Safety Features**:

- Validates all directories exist before starting
- Ctrl+C cleanly terminates background processes and removes temporary files
- No overwrites - unique timestamps prevent conflicts

## Workflow

Check backup size before running:

```bash
du -sh .claude notes learning obsession code
```

Create backup before risky operations:

```bash
backup-important
# Proceed with git rebase, major refactoring, etc.
```

On macOS, use the convenience alias:

```bash
# Defined in shell config
backup-important  # Backs up: .claude, learning, notes, obsession, code
```

Customize destination for external drives:

```bash
backup-dirs --dest /Volumes/External dotfiles code
```

## See Also

- [Tool Composition](../architecture/tool-composition.md) - How backup-dirs fits into the toolchain
- [Bash Script Testing](../learnings/bash-script-testing.md) - Development lessons
