---
icon: material/backup-restore
---

# Backup

Two tools, `apps/common/packup` and `safekeep`, which lives in its own repo. Run
either with `--help` for flags. This page is about which one to reach for.

## Which one

**`packup`** makes one compressed archive of one or more paths, named on the
command line. Each run is a `.tar.zst` that stands alone, so restoring is
`tar -xf` with nothing else present. Use it before something you might want to
undo wholesale — a rebase, a risky refactor, a config migration — where the value
is a single file you can copy anywhere and unpack months later.

```sh
packup -n dotfiles -d ~/Documents --exclude .git dotfiles
```

**`safekeep`** backs up what a config file declares, as one timestamped snapshot
per run on a network drive, and restores them onto a rebuilt machine. Every snapshot carries a
manifest recording its groups, tags and file modes, so it restores without the
config that made it — which is the disaster-recovery case, where the config died
with the machine. Unchanged files are hard links into the previous snapshot, so
keeping every snapshot forever costs only what changed.

```sh
safekeep backup run
```

The distinction that matters is imperative versus declarative, not archive versus
snapshot. `packup` backs up what you name, right now, and forgets it. `safekeep`
backs up what its config says, on whatever schedule you run it, and knows how to
put it back.

## Restoring

A `packup` archive is `tar -xf backup.tar.zst`, anywhere, with nothing installed.

A `safekeep` snapshot is `safekeep restore --to <target>`, which picks the
snapshot and sources interactively and reapplies the recorded modes. Do not edit
files inside a snapshot: hard links mean a shared file is the same inode in every
snapshot holding it. Deleting a whole snapshot directory is safe.
