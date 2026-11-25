---
icon: material/target
---

# doit

**The menu suite moved out of this repository in August 2026.** `menu`, `menu-next`, `menu-review`
and `menu-dashboard` are one tool, `doit`, at
[datapointchris/doit](https://github.com/datapointchris/doit) — where its documentation is
maintained. It covers what a person does themselves: the draw, the dashboard, the journal and the
review. `menu-labs` and `workflows` are `howto`, which also holds the tool registry.

This page is a pointer, not a copy. Two copies get a chance to disagree, and the one shipping beside
the code is the one that will be right.

## Why it left

Every structural deformation signal at once: `menucore/` and `apppaths.py` sitting at the repo root,
three `sys.path.insert(parents[2])` hacks, a top-level `tests/menucore/`, five PEP 723 headers each
re-pinning the same revision, and a bash dispatcher that `exec`'d five separately-symlinked binaries
while pretending to be one tool. Around 5,800 lines, including the workflows browser that folded in.

The cards and Labs went to a second repo,
[datapointchris/terminal-library](https://github.com/datapointchris/terminal-library), rather than
traveling with a tool. Content is authored far more often than code. Co-locating them would have
meant cutting a release every time a card changed. `howto` reads that repo, and `doit` reads nothing
from it.

## A machine gets doit only if its manifest or a profile it takes names it

A symlinked app lands on every machine that gets `apps/` symlinks, while a declared package reaches
only the machines whose manifest, or a profile it composes, names it — see
[App Installation Patterns](../learnings/app-installation-patterns.md). That distinction is the one
to carry.

`personal-desk-clis` declares `doit`, because it serves one person's own desks. A box that takes
`workstation` without `personal-desk` gets `howto` and no `doit`, and `wsl-work-workstation` is that
box.

## A desk installs one Go binary, which runs every verb

The `doit` on `PATH` is a Go binary from the repo's `cli/` releases, installed by a
`github_releases` row. It runs every verb, `tui` included, and its zsh completion autoloads like the
other cobra tools'.

The row's `supersedes` removes the Python package's uv tool and `~/go/bin/doit-tui` on a box that
still has them, once the release is installed. `uv:doit` names the uv tool by its package. Its
receipt lists only the `doit-python` script, so `uv tool uninstall doit` leaves the release's
`doit` in place.

## `register.yml` is config, and config stays out of the repo

`doit` reads and writes through its service, which holds the register, the pursuits, the sources and
the journal. A desk keeps only its login and its config file under `~/.config/doit`, so a new box
needs `doit auth login` once and nothing replicated.

## See Also

- [App Installation Patterns](../learnings/app-installation-patterns.md) — the four install patterns
