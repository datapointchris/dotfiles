---
icon: material/safe-square-outline
---

# Safekeep

Config-driven file preservation tool that rsync-copies files and directories to a destination with dated snapshots and automatic retention pruning. Zero external dependencies — uses only Python stdlib (argparse, json, subprocess, pathlib).

Primary use case: backing up scattered config files, local scripts, and git-untracked WIP from a WSL work machine to a network drive for crash protection.

## Quick Start

```bash
safekeep                    # Auto-detect config, run backup
safekeep --config work      # Use specific config
safekeep --dry-run          # Preview what would be copied
```

## Config

Config files live at `~/.config/safekeep/<name>.json`. If only one config exists, it auto-loads. With multiple configs, specify which one with `--config`.

```json
{
  "dest": "/h/backups",
  "keep": 5,
  "exclude": [".venv", "node_modules", "__pycache__", ".mypy_cache",
              ".ruff_cache", ".pytest_cache", "build", "dist",
              "*.pyc", ".DS_Store"],
  "wsl": {
    "base": "~",
    "paths": [
      "notes",
      ".ssh/config",
      "code/ichrisbirch/xperiments"
    ],
    "git_untracked": [
      "code/ichrisbirch",
      "code/api-project"
    ]
  },
  "win": {
    "base": "/mnt/c/Users/chris",
    "paths": [
      "Documents/work-notes"
    ]
  }
}
```

**Top-level keys:**

- `dest` — base destination path (required)
- `keep` — number of dated snapshots to retain (required)
- `exclude` — exclusion patterns applied to all rsync calls (optional, has sensible defaults)

**Section keys** (any name that isn't `dest`, `keep`, or `exclude`):

- `base` — base path for resolving relative paths in this section (supports `~`)
- `paths` — list of files/directories relative to `base` (static, explicit)
- `git_untracked` — list of git repos relative to `base` to collect untracked files from (dynamic)

## Commands

```bash
safekeep [--config NAME] [--dry-run] [--help]
```

**Options:**

- `-c, --config NAME` — Config name or absolute path (default: auto-detect)
- `-n, --dry-run` — Show what would be copied without doing it
- `-h, --help` — Show help

## Destination Structure

```text
/h/backups/
  2026-03-11/
    wsl/
      notes/meeting.md
      .ssh/config
      code/ichrisbirch/xperiments/notebook.ipynb
      code/ichrisbirch/scratch.py          (from git_untracked)
    win/
      Documents/work-notes/report.docx
  2026-03-09/
    wsl/
      ...
  latest -> 2026-03-11/
```

Path construction: `dest / YYYY-MM-DD / section-name / relative-path`

## Key Behaviors

**Idempotent**: Running twice on the same day updates the same dated directory. rsync handles this efficiently — only changed files are transferred.

**Fail fast**: If the destination doesn't exist or isn't writable, exit immediately with a clear message about checking the network drive connection.

**Smart exclusions**: Default exclude list (.venv, node_modules, etc.) applied to all rsync calls. Override in config. For `git_untracked`, files are filtered through the exclude list before copying.

**Retention**: After a successful backup, dated directories beyond the `keep` count are pruned (oldest first). The `latest` symlink always points to the most recent backup.

**Clean output**: Simple print statements with no spinners or colors. Output is loggable and cron-friendly.

## See Also

- [Backmeup](backmeup.md) — Timestamped tar+zstd archives (complementary tool)
- [Tool Composition](../architecture/tool-composition.md) — How safekeep fits into the toolchain
