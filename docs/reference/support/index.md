---
icon: material/lifebuoy
---

# Support

Run `dotfiles plan` and `dotfiles packages check` first. Then search the debugging record by the
error string on screen: `rg -i "<the error>" docs/learnings/`.

## Pages

- [Troubleshooting](troubleshooting.md) — the commands that diagnose most of it, then one section
  per symptom: a command not found, a config change not taking effect, a Neovim "module not found"
  that is a stale symlink
- [Restricted Networks](corporate.md) — the firewalled machine: measuring what is actually blocked,
  then building a bundle where the network is and carrying it in
