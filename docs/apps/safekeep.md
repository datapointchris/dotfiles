---
icon: material/safe-square-outline
---

# Safekeep

Config-driven file preservation that rsync-copies files and directories to a destination as dated snapshots. Each snapshot carries a manifest describing what was collected, so a snapshot can be restored without the config that produced it. Zero external dependencies for backup — Python stdlib only. Restore shells out to fzf for interactive selection.

Primary use case: backing up scattered config files, local scripts, and git-untracked WIP from a WSL work machine to a network drive for crash protection, and restoring them onto a rebuilt machine.

## Quick Start

```bash
safekeep                    # Usage. Nothing writes without an explicit verb
safekeep init               # Generate starter config at ~/.config/safekeep/default.toml
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

Config files live at `~/.config/safekeep/<name>.toml`. If only one config exists, it auto-loads. With multiple configs, specify which one with `--config`, which is global and goes before the command: `safekeep --config work backup`.

`safekeep init` writes a complete annotated starter config; the shape it produces is:

```toml
back_up_to = "/mnt/h/backups"
skip_names_matching = [".venv", "node_modules", "*.pyc"]
skip_files_over_mb = 50

[[back_up_paths]]
path = "~/.ssh"
tags = ["secrets", "rebuild"]

[[back_up_paths]]
path = "~/notes"
tags = ["notes"]

[git]
back_up_untracked_files = true
back_up_ignored_files_matching = ["CLAUDE.md", ".planning"]

[[git.repos]]
path = "~/dotfiles"
tags = ["rebuild"]

[[git.repos]]
path = "~/code/side-project"
tags = ["wip"]
```

**Every key states what safekeep will do, so the file reads as a description of the backup rather than a list of this program's variables.** That is the standard in `~/dev/standards/configuration.md`, and safekeep is its worked example.

**TOML, not JSON, and the reason is `tomllib`.** safekeep takes no dependencies on the backup path because it has to run on a locked-down work machine where installing a package is a fight, and `tomllib` has been in the standard library since 3.11 while YAML has never had a stdlib parser and never will. Comments come free with that choice, and they are what turns the file into its own manual. YAML would additionally have been the wrong fit for a config full of glob patterns: an unquoted `*.pyc` is alias syntax rather than a string, and bare `~` is null.

`tomllib` reads but cannot write, so `init` emits a hand-authored template rather than serializing a dict — which is the better half of the trade, since a serialized dict cannot carry comments. `CONFIG_TEMPLATE` in the script is that file, and two tests assert it parses without warnings and demonstrates repetition rather than one of each key.

**The `[git]` keys must precede the first `[[git.repos]]` block.** TOML closes a table as soon as a subtable opens, so a `back_up_untracked_files` written after the repo blocks is read as part of the last repo. This fails loudly rather than silently, but it is the one ordering constraint the format imposes here.

**Keys:**

- `back_up_to` — base destination path (required, and the only required key)
- `back_up_paths` — absolute paths to copy whole, `~` is expanded (optional)
- `git` — `repos` names the subject; every other key states what is taken from them (optional)
  - `repos` — the git repos themselves
  - `back_up_untracked_files` — copy each repo's untracked files (default `true`)
  - `back_up_ignored_files_matching` — glob patterns matched against the *gitignored* files in those same repos, so `CLAUDE.md` and `.planning` survive a rebuild
- `skip_names_matching` — patterns no backup ever copies (optional, has sensible defaults)
- `skip_files_over_mb` — skip files larger than this many MB (optional)

Every `[[back_up_paths]]` and `[[git.repos]]` block takes a `path` and optional `tags`. Under JSON an entry could also be a bare path string, so there were two shapes to write and two to parse; an array of tables is uniform, and gives every entry a line of its own to be commented on.

**The repo options are nested because they only mean something relative to the repos beside them.** They were once two sibling keys, `git_untracked` and `git_ignored`, which read as two independent lists of things to back up — nothing in the config said the second was a filter scoped to the first, and the answer was only findable in the source. Structure carries that relationship where a name could not, which is why the parent key is a scope and the leaves are statements about it.

**Inside a scope, one key names the subject and the rest state what happens to it.** `repos` is that subject key. An earlier attempt called it `at`, on the theory that a preposition would let the key complete its parent's phrase — "git repos *at* `~/code/project`". It reads only while the parent is adjacent, and is opaque in every error message, doc reference, and line of code that names the leaf alone. A subject is a noun and resists being made to state an action; the rest of the block does that work.

**`back_up_untracked_files` exists even though nothing else can set it to `false`.** Copying untracked files is what the repo block did unconditionally before, and a config that leaves an outcome-shaping default unstated reads as though the tool does nothing but what is written. A key whose value never changes still earns its place when it is the only thing telling the reader what will be copied.

A repo's ignored files are found by set subtraction: `git ls-files --others` (untracked plus ignored) minus `git ls-files --others --exclude-standard` (untracked only), since git has no single flag that lists ignored files without the untracked ones. A pattern matches either the whole repo-relative path or any single component of it, which is why `.planning` catches everything beneath a `.planning/` directory at any depth.

**Tags are labels, not policy.** safekeep never interprets what a tag means — it displays them in the picker and accepts `--tag NAME` as a selector. That keeps scenario knowledge (which paths matter on a rebuild) in the config where it was written, rather than in the tool.

## Schema Changes

Unrecognized keys warn and are ignored rather than erroring, so a config can be edited ahead of the tool. A missing required key is still fatal.

A generic warning is adequate for a typo but not for a key that used to mean something. Retired keys therefore carry their own message, listed in `RETIRED_KEYS` in the script. Unrecognized keys are also recorded in the snapshot manifest as `config_warnings`, so a snapshot carries evidence that its config was partly ignored when it was taken.

Renamed keys are fatal rather than warned, and are listed separately in `RENAMED_KEYS`. The distinction is whether ignoring the key shrinks the backup: dropping a retired `keep` changes nothing about what gets copied, while ignoring an old `git_untracked` would skip every repo in the config. A run that fails loudly is fixed immediately; a backup that quietly gets smaller is not noticed until a restore needs the files that are not in it.

The config is hand-written and there are few of them, so it has no version field. The manifest is machine-written and outlives tool versions, so it does — and that same split is why the config moved to TOML while the manifest stayed JSON.

A config left behind as `.json` is named rather than reported as absent: `no configs found` is a bewildering thing to read when the file is sitting in the directory. `resolve_config` lists every leftover with the name it should have.

## Destination Structure

A dated subdirectory is created for each day's backup. Full directory structure is preserved from filesystem root, so the origin of every file is unambiguous and restore is a reverse rsync.

```text
/mnt/h/backups/
  2026-08-04/
    .safekeep-manifest.json
    home/chris/
      notes/meeting.md
      .ssh/config
      code/project/scratch.py          (untracked, from git.repos)
    mnt/c/Users/chris/
      Documents/work-notes/report.docx
  2026-08-01/
    ...
```

Path construction: `back_up_to / YYYY-MM-DD / absolute-path-from-root`

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

**Smart exclusions**: Default `skip_names_matching` list (`.venv`, `node_modules`, caches) applied to all rsync calls. Override in config.

**Sized from the source**: Totals come from the walk that builds the manifest, not from re-reading the destination, so the backup never stats the whole snapshot back over the network.

## See Also

- [Backmeup](backmeup.md) — Timestamped tar+zstd archives (complementary tool)
- [Tool Composition](../architecture/tool-composition.md) — How safekeep fits into the toolchain
