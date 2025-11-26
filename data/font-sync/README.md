# Font Sync Data

This directory stores font-sync data files in your dotfiles repo for syncing across systems.

## Files

- `font-testing-log.md` - Testing history, likes/dislikes, notes (created automatically)

## Syncing Across Systems

The font testing log is stored here so it syncs with your dotfiles repo across macOS, Linux, and WSL.

**To sync testing decisions:**

- Commit `font-testing-log.md` to git (default)
- Testing decisions follow you across all systems

**To keep local per-system:**

- Add `font-testing-log.md` to `.gitignore` in this directory
- Each system maintains its own testing history

## XDG Compliance (Optional)

For XDG compliance, create a symlink:

```bash
mkdir -p ~/.local/share
ln -s ~/dotfiles/data/font-sync ~/.local/share/font-sync
```

This makes the data appear in the XDG standard location while keeping it in your dotfiles repo.

**Not required** - font-sync reads from `~/dotfiles/data/font-sync` directly.
