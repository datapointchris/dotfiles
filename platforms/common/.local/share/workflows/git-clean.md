# git clean — remove untracked files and directories

```bash
# Preview what would be deleted (dry run, always do this first)
git clean -fdn                    # -n = dry run, shows what would go

# Remove untracked files and directories
git clean -fd                     # -f = force, -d = include directories

# Include ignored files too (nuclear option)
git clean -fdx                    # -x = also remove gitignored files (.venv, __pycache__, etc)

# Interactive mode — choose file by file
git clean -fdi                    # -i = interactive, asks for each item

# Clean specific path only
git clean -fd src/apps/old_module/
```

## Common combos: reset a repo to match remote

```bash
# Discard all modifications to tracked files
git checkout .                    # resets working tree to HEAD

# Full reset: discard modifications + delete untracked
git checkout .                    # reset tracked files
git clean -fd                     # delete untracked files/dirs

# Nuclear reset: match remote exactly (careful — deletes .venv, logs, etc)
git checkout .
git clean -fdx                    # also deletes gitignored files
```

## Flags

| Flag | What it does |
|------|-------------|
| `-f` | Force (required, safety measure) |
| `-d` | Include untracked directories (not just files) |
| `-n` | Dry run — show what would be deleted, delete nothing |
| `-x` | Also delete gitignored files (.venv, __pycache__, logs/) |
| `-X` | Delete ONLY gitignored files (opposite of default) |
| `-i` | Interactive — prompt before each deletion |
| `-e <pattern>` | Exclude pattern from cleaning (e.g. `-e "*.log"`) |

## Key difference from other reset commands

- `git checkout .` — resets tracked files to HEAD (undoes modifications)
- `git clean -fd` — deletes untracked files/dirs (things git doesn't know about)
- `git reset --hard` — resets tracked files AND staging area to HEAD
- Neither checkout nor reset touches untracked files — only clean does that
