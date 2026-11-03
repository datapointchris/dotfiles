---
icon: material/target
---

# doit

**The menu suite moved out of this repository in August 2026.** `menu`, `menu-next`, `menu-review`,
`menu-labs`, `menu-dashboard` and `workflows` are one tool, `doit`, at
[datapointchris/doit](https://github.com/datapointchris/doit) — where its documentation is
maintained.

This page is a pointer, not a copy. Two copies get a chance to disagree, and the one shipping beside
the code is the one that will be right.

## Why it left

Every structural deformation signal at once: `menucore/` and `apppaths.py` sitting at the repo root,
three `sys.path.insert(parents[2])` hacks, a top-level `tests/menucore/`, five PEP 723 headers each
re-pinning the same revision, and a bash dispatcher that `exec`'d five separately-symlinked binaries
while pretending to be one tool. Around 5,800 lines, including the workflows browser that folded in.

The cards and Labs went to a second repo,
[datapointchris/terminal-library](https://github.com/datapointchris/terminal-library), rather than
traveling with the tool. Content is authored far more often than code. Co-locating them would have
meant cutting a release every time a card changed.

## A machine gets doit only if its manifest or a profile it takes names it

Six symlinked scripts became one `uv_tools` install from the owner's package index, alongside
`refcheck` and `safekeep` — category 4 in
[App Installation Patterns](../learnings/app-installation-patterns.md). That distinction is the one
to carry. A symlinked app lands on every machine that gets `apps/` symlinks, while a uv tool reaches
only the machines whose manifest, or a profile it composes, declares it.

## `register.yml` is config, and config stays out of the repo

`doit` reads and writes through its service, which holds the register, the pursuits, the sources and
the journal. A desk keeps only its login and its config file under `~/.config/doit`, so a new box
needs `doit auth login` once and nothing replicated.

## See Also

- [App Installation Patterns](../learnings/app-installation-patterns.md) — the four install patterns
