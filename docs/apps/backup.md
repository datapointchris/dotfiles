---
icon: material/backup-restore
---

# Backup

Two tools, `apps/common/backmeup` and `apps/common/backup-incremental`. Run
either with `--help` for flags. This page is about which one to reach for.

## Which one

**`backmeup`** makes one compressed archive of one or more paths. Each run is a
`.tar.gz` that stands alone, so restoring is `tar -xzf` with nothing else
present. Use it before something you might want to undo wholesale — a rebase, a
risky refactor, a config migration — where the value is a single file you can
copy anywhere and unpack months later.

```sh
backmeup -n dotfiles -d ~/Documents --exclude .git dotfiles
```

**`backup-incremental`** makes rsync snapshots where unchanged files are hard
links into the previous snapshot. Every snapshot browses as a complete tree
while costing only the changed files, so keeping many is cheap. Use it for
anything you back up repeatedly and want history for. `--network host:/path`
sends it to any SSH-accessible host.

```sh
backup-incremental --name learning --exclude books ~/learning
```

The distinction that matters: an archive is one restorable blob, a snapshot tree
is browsable history. Reach for `backmeup` when you want to carry the result
somewhere; reach for `backup-incremental` when you want to keep taking it.

## Restoring an incremental backup

The hard links are the whole trick and also the whole hazard. Each snapshot is a
real directory tree, so restoring is a plain `cp -a` or `rsync` out of the
snapshot you want — no replay, no chain to walk.

But because unchanged files are the *same inode* across snapshots, editing a
file in place inside a snapshot edits it in every snapshot that shares it. Copy
out before touching anything, and never edit in the backup directory. Deleting a
whole snapshot directory is safe: the data survives as long as any other
snapshot links it.
