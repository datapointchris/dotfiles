---
icon: material/safe-square-outline
---

# Safekeep

**safekeep moved out of this repository in August 2026.** It lives at
[datapointchris/safekeep](https://github.com/datapointchris/safekeep), and that repository is where
its documentation is now maintained — the README for the short version, and
[`docs/reference.md`](https://github.com/datapointchris/safekeep/blob/main/docs/reference.md) for
the full behaviour and the reasoning behind it, which moved there intact.

This page is a pointer, not a copy. Two copies get a chance to disagree, and the one shipping beside
the code is the one that will be right.

## Why it left

safekeep was the only thing in `apps/` that owns a data format living **outside the machine**.
Everything else there manipulates local state — menus, symlinks, package lists, theme files.
safekeep writes a manifest to a network drive that has to be read by a different safekeep, on a
different machine, on a different OS, possibly years later. `MANIFEST_VERSION = 1` was the tell: it
already versioned its data and had no version of its own.

## A machine gets safekeep only by declaring it

It installs through `git_uv_tools` in `install/packages.yml`, alongside `refcheck` and `syncer` —
category 4 in [App Installation Patterns](../learnings/app-installation-patterns.md).

That is the difference worth knowing. A symlinked app arrives on every machine that gets `apps/`
symlinks; a git uv tool arrives only where a manifest names it. `linux-lxc-server` deliberately
does not, because it takes no Python CLIs at all.

Its terminal style comes from [pytermstyle](https://github.com/datapointchris/pytermstyle), the
package extracted from this repo's former `appcore/formatting.py`. That extraction is what made the
move possible: a script cannot take a `sys.path` hack with it when it leaves.

## See Also

- [Backup](backup.md) — the archive and snapshot tools that stayed in this repo
- [App Installation Patterns](../learnings/app-installation-patterns.md) — the four install patterns
