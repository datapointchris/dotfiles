---
icon: material/safe-square-outline
---

# Safekeep

Config-driven file preservation tool that rsync-copies files and directories to a destination with dated snapshots and automatic retention pruning. Zero external dependencies — uses only Python stdlib (argparse, json, subprocess, pathlib).

Primary use case: backing up scattered config files, local scripts, and git-untracked WIP from a WSL work machine to a network drive for crash protection.

## Quick Start

```bash
safekeep --init             # Generate starter config at ~/.config/safekeep/default.json
safekeep --init work        # Generate starter config at ~/.config/safekeep/work.json
safekeep --dry-run          # Preview what would be copied
safekeep                    # Auto-detect config, run backup
safekeep --config work      # Use specific config
safekeep --show-config      # Display the resolved config
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
  "paths": [
    "~/notes",
    "~/.ssh/config",
    "~/code/ichrisbirch/xperiments",
    "/mnt/c/Users/chris/Documents/work-notes"
  ],
  "git_untracked": [
    "~/code/ichrisbirch",
    "~/code/api-project"
  ]
}
```

**Keys:**

- `dest` — base destination path (required)
- `keep` — number of dated snapshots to retain (required)
- `exclude` — exclusion patterns applied to all rsync calls (optional, has sensible defaults)
- `paths` — list of absolute paths to back up, `~` is expanded (optional)
- `git_untracked` — list of absolute paths to git repos to collect untracked files from (optional)

## Commands

```bash
safekeep [--config NAME] [--dry-run] [--init [NAME]] [--show-config]
```

**Options:**

- `-c, --config NAME` — Config name or absolute path (default: auto-detect)
- `-n, --dry-run` — Show what would be copied without doing it
- `--init [NAME]` — Generate a starter config with example structure (default name: `default`)
- `--show-config` — Display the resolved config and exit
- `-h, --help` — Show help and config format reference

## Destination Structure

A dated subdirectory is created for each day's backup. Full directory structure is preserved from filesystem root, so the origin of every file is unambiguous.

```text
/h/backups/
  2026-03-11/
    home/chris/
      notes/meeting.md
      .ssh/config
      code/ichrisbirch/xperiments/notebook.ipynb
      code/ichrisbirch/scratch.py          (from git_untracked)
    mnt/c/Users/chris/
      Documents/work-notes/report.docx
  2026-03-09/
    home/chris/
      ...
  latest -> 2026-03-11/
```

Path construction: `dest / YYYY-MM-DD / absolute-path-from-root`

## Key Behaviors

**Idempotent**: Running twice on the same day updates the same dated directory. rsync handles this efficiently — only changed files are transferred.

**Fail fast**: If the destination doesn't exist or isn't writable, exit immediately with a clear message about checking the network drive connection.

**Symlink dereferencing**: Symlinks are followed and copied as real files. Backups contain actual content, not symlinks that would break if the source machine is lost.

**Smart exclusions**: Default exclude list (.venv, node_modules, etc.) applied to all rsync calls. Override in config. For `git_untracked`, files are filtered through the exclude list before copying.

**Retention**: After a successful backup, dated directories beyond the `keep` count are pruned (oldest first). The `latest` symlink always points to the most recent backup.

**Clean output**: Minimal ANSI-colored output with no spinners or progress bars.

## See Also

- [Backmeup](backmeup.md) — Timestamped tar+zstd archives (complementary tool)
- [Tool Composition](../architecture/tool-composition.md) — How safekeep fits into the toolchain
