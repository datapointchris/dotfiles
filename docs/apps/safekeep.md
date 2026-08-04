---
icon: material/safe-square-outline
---

# Safekeep

Config-driven file preservation that rsync-copies files and directories to a destination as dated snapshots. Each snapshot carries a manifest describing what was collected, so a snapshot can be restored without the config that produced it. Zero external dependencies for backup — Python stdlib only. Restore shells out to fzf for interactive selection.

Primary use case: backing up scattered config files, local scripts, and git-untracked WIP from a WSL work machine to a network drive for crash protection, and restoring them onto a rebuilt machine.

## Quick Start

```bash
safekeep                    # Usage. Nothing writes without an explicit verb
safekeep init               # Generate starter config at ~/.config/safekeep/default.json
safekeep config             # Display the resolved config
safekeep backup --dry-run   # Preview what would be copied
safekeep backup             # Copy the configured paths into today's snapshot

safekeep snapshots                        # What is at the destination
safekeep restore --to /tmp/restore-test   # Rehearse: pick a snapshot and groups
safekeep restore --to / --tag wip         # Restore everything tagged 'wip'
```

Bare `safekeep` prints usage rather than picking an action, per the no-args-shows-help rule in
`~/dev/standards/cli-design.md`. A tool that did work bare could not gain a second command without
silently changing what the bare invocation means — and here that bare invocation was the one that
wrote.

## Config

Config files live at `~/.config/safekeep/<name>.json`. If only one config exists, it auto-loads. With multiple configs, specify which one with `--config`, which is global and goes before the command: `safekeep --config work backup`.

```json
{
  "dest": "/mnt/h/backups",
  "max_file_size_mb": 50,
  "paths": [
    "~/notes",
    { "path": "~/.ssh", "tags": ["secrets"] },
    { "path": "/mnt/c/Users/chris/Documents/work-notes", "tags": ["windows"] }
  ],
  "repos": {
    "paths": [{ "path": "~/code/project", "tags": ["wip"] }],
    "include_ignored": ["CLAUDE.md", ".planning"]
  }
}
```

**Keys:**

- `dest` — base destination path (required, and the only required key)
- `exclude` — exclusion patterns applied to all rsync calls (optional, has sensible defaults)
- `max_file_size_mb` — skip files larger than this (optional)
- `paths` — absolute paths to back up, `~` is expanded (optional)
- `repos` — git repos to collect files from (optional)
  - `repos.paths` — the repos; the untracked files in each are backed up
  - `repos.include_ignored` — glob patterns matched against the *gitignored* files in those same repos, so `CLAUDE.md` and `.planning` survive a rebuild

Entries in `paths` and `repos.paths` are either a plain string or an object with `path` and `tags`.

**The repo block is nested because the patterns only mean something relative to the repos beside them.** They were once two sibling keys, `git_untracked` and `git_ignored`, which read as two independent lists of things to back up — nothing in the config said the second was a filter scoped to the first, and the answer was only findable in the source. Structure carries that relationship where a name could not. A pattern list with no repos beside it now warns that it matches nothing, rather than silently doing nothing.

A repo's ignored files are found by set subtraction: `git ls-files --others` (untracked plus ignored) minus `git ls-files --others --exclude-standard` (untracked only), since git has no single flag that lists ignored files without the untracked ones. A pattern matches either the whole repo-relative path or any single component of it, which is why `.planning` catches everything beneath a `.planning/` directory at any depth.

**Tags are labels, not policy.** safekeep never interprets what a tag means — it displays them in the picker and accepts `--tag NAME` as a selector. That keeps scenario knowledge (which paths matter on a rebuild) in the config where it was written, rather than in the tool.

## Schema Changes

Unrecognized keys warn and are ignored rather than erroring, so a config can be edited ahead of the tool. A missing required key is still fatal.

A generic warning is adequate for a typo but not for a key that used to mean something. Retired keys therefore carry their own message, listed in `RETIRED_KEYS` in the script. Unrecognized keys are also recorded in the snapshot manifest as `config_warnings`, so a snapshot carries evidence that its config was partly ignored when it was taken.

Renamed keys are fatal rather than warned, and are listed separately in `RENAMED_KEYS`. The distinction is whether ignoring the key shrinks the backup: dropping a retired `keep` changes nothing about what gets copied, while ignoring an old `git_untracked` would skip every repo in the config. A run that fails loudly is fixed immediately; a backup that quietly gets smaller is not noticed until a restore needs the files that are not in it.

The config is hand-written and there are few of them, so it has no version field. The manifest is machine-written and outlives tool versions, so it does.

## Destination Structure

A dated subdirectory is created for each day's backup. Full directory structure is preserved from filesystem root, so the origin of every file is unambiguous and restore is a reverse rsync.

```text
/mnt/h/backups/
  2026-08-04/
    .safekeep-manifest.json
    home/chris/
      notes/meeting.md
      .ssh/config
      code/project/scratch.py          (untracked, from repos.paths)
    mnt/c/Users/chris/
      Documents/work-notes/report.docx
  2026-08-01/
    ...
```

Path construction: `dest / YYYY-MM-DD / absolute-path-from-root`

**Snapshots are never pruned.** Deciding how many backups to keep is not safekeep's job.

## The Manifest

`.safekeep-manifest.json` is written into each snapshot and is what makes it restorable on a machine that no longer has the config. It records the groups collected (kind, source, tags, counts, sizes), the source `home` for remapping, file modes, symlink origins, oversized files that were skipped, and any config warnings.

**Modes** are recorded only where they deviate from `0644` for files and `0755` for directories. The destination is typically SMB or DrvFs and cannot store Unix modes, so the backup is written with `--no-perms` and every file arrives with the same mode. Restore applies the defaults everywhere and then the recorded deviations, which collapses the map to just the interesting entries — `0600` secrets and executable scripts. Without this, restored SSH and GPG config files come back group-readable and those tools refuse to use them.

**Symlinks** are dereferenced on backup (`rsync --copy-links`) so a snapshot holds real content rather than links that break when the source machine is lost. The manifest records that the source *was* a symlink and where it pointed, so restore can report which restored files should be links and offer `--skip-symlinked`.

A snapshot with no manifest cannot be restored by safekeep — it says so and points at rsync.

## Restore

```bash
safekeep restore --to PATH [--from DATE] [--all | --group PATH | --tag NAME]
                           [--dry-run] [--on-conflict POLICY] [--skip-symlinked]
```

`--to` is required. `--to /` is a real restore; `--to /tmp/restore-test` stages one somewhere harmless, which is how the restore gets rehearsed before it is needed.

**Selection is always explicit.** With `--all`, `--group`, or `--tag`, restore runs non-interactively. With none of them on a terminal, fzf opens: first a snapshot picker previewing each manifest, then a multi-select group picker previewing each group's subtree. With none of them and no terminal, it exits non-zero listing the available groups rather than guessing.

`--on-conflict` chooses what happens when a target file already exists: `backup` (default, renames the existing file with a `.pre-restore` suffix), `skip`, `overwrite`, or `newer`.

If the snapshot's home differs from the restoring machine's, paths under it are remapped automatically — a snapshot taken as `/home/chris` restores into whatever `$HOME` is now.

## Key Behaviors

**Idempotent**: Running twice on the same day updates the same dated directory. rsync transfers only changed files.

**Fail fast**: If the destination doesn't exist or isn't writable, exit immediately.

**Smart exclusions**: Default exclude list (`.venv`, `node_modules`, caches) applied to all rsync calls. Override in config.

**Sized from the source**: Totals come from the walk that builds the manifest, not from re-reading the destination, so the backup never stats the whole snapshot back over the network.

## See Also

- [Backmeup](backmeup.md) — Timestamped tar+zstd archives (complementary tool)
- [Tool Composition](../architecture/tool-composition.md) — How safekeep fits into the toolchain
