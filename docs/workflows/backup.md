# Backup Workflow

## Overview

Create compressed backups of important directories with progress tracking and smart exclusions. The backup system automatically excludes development bloat (.venv, node_modules, build artifacts) while preserving version control data.

## Quick Start

Backup directories to Documents folder (iCloud synced on macOS):

```bash
backup-dirs .claude notes learning obsession
```

On macOS, use the convenience alias for common directories:

```bash
backup-important
```

This backs up: .claude, learning, notes, obsession, code

## Features

**Smart Exclusions**: Automatically excludes common bloat while keeping important data:

- Python: .venv, **pycache**, *.pyc, .pytest_cache
- Node: node_modules, .npm
- Build artifacts: dist/, build/, target/
- Caches: .cache, .DS_Store
- Keeps: .git directories, source code, documentation

**Progress Tracking**:

- Rainbow progress indicators with organic time-based updates
- Accurate file and directory counting (99%+ accuracy)
- Compression statistics showing original vs compressed sizes
- Elapsed time tracking for both analysis and archiving

**Path Handling**:

- Supports both relative paths (dotfiles) and absolute paths (~/code)
- Automatically normalizes paths inside/outside home directory
- Validates all directories exist before starting

## Common Usage

Backup to default location (~/Documents):

```bash
backup-dirs dotfiles .config notes
```

Backup to custom destination:

```bash
backup-dirs --dest ~/Backups code projects
```

Backup with custom name prefix:

```bash
backup-dirs --name important-backup dotfiles code
```

## Archive Format

Archives are created as compressed tar.gz files with timestamps:

```text
backup-dirs_2025-11-25_143022.tar.gz
```

Format: `backup-dirs_YYYY-MM-DD_HHMMSS.tar.gz`

Default location: `~/Documents/`

## Performance

Uses modern tools for speed:

- `fd` for fast file discovery (respects .gitignore with --no-ignore flag)
- GNU `tar` for efficient compression
- Background processes for responsive progress updates

Typical performance:

- ~3000 files: 5-10 seconds analysis, 15-30 seconds compression
- Compression ratio: 60-80% (depends on file types)

## Safety Features

**Interrupt Handling**: Ctrl+C cleanly terminates all background processes and removes temporary files

**Validation**: Checks all directories exist before starting backup

**No Overwrites**: Each backup gets unique timestamp, never overwrites existing archives

## Tips

Run backup before potentially destructive operations:

```bash
backup-important              # Quick safety backup
git rebase -i HEAD~10        # Safe to proceed
```

Check backup size before running:

```bash
du -sh .claude notes learning obsession code
```

Exclude additional patterns (modify script configuration):

```bash
# Edit apps/common/backup-dirs
readonly EXCLUDE_PATTERNS=(
  # Add custom patterns here
)
```

## Related

- `tar` - Underlying compression tool
- `fd` - Fast file discovery
- `theme-sync` - Another custom dotfiles tool
- `docs/learnings/bash-script-testing.md` - Development lessons
