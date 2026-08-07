---
icon: material/target
---

# doit

**The menu suite moved out of this repository in August 2026.** `menu`, `menu-next`, `menu-review`,
`menu-labs`, `menu-dashboard` and `workflows` are now one tool, `doit`, at
[datapointchris/doit](https://github.com/datapointchris/doit) — where its documentation is now
maintained.

This page is a pointer, not a copy. Two copies get a chance to disagree, and the one shipping beside
the code is the one that will be right.

## Why it left

Every structural deformation signal at once: `menucore/` and `apppaths.py` sitting at the repo root,
three `sys.path.insert(parents[2])` hacks, a top-level `tests/menucore/`, five PEP 723 headers each
re-pinning the same revision, and a bash dispatcher that `exec`'d five separately-symlinked binaries
while pretending to be one tool. Around 5,800 lines, including the workflows browser that folded in.

The cards and Labs left too, to [datapointchris/doit-content](https://github.com/datapointchris/doit-content).
Content is authored far more often than code, and keeping it in the tool's repo would have meant a
release every time a card changed.

## What changed on this side

Six symlinked scripts became one `git_uv_tools` install, like `refcheck` and `safekeep` — category 4
in [App Installation Patterns](../learnings/app-installation-patterns.md). The same consequence
applies: **a machine gets `doit` only if its manifest lists it**, where a symlinked app arrived on
every machine that got `apps/` symlinks.

Two couplings stayed here and were rewired rather than removed:

- The shell startup nudge is now `cache_eval -b doit doit-nudge doit shell-init zsh`. `doit` emits
  the block and `.zshrc` only caches it — an `eval` would put a Python start in front of every
  shell, which is the one thing [Shell Libraries](../architecture/shell-libraries.md) does not allow.
- `bind m` and `bind t` in `tmux.conf` now call `doit launch` and `doit workflows show`.

`shell/common/completions.zsh` is gone entirely. It existed only to hand-write `_menu`, and `doit`
generates its own completion.

## Config and state

Both moved to `doit`'s own XDG paths, and both are Syncthing folders declared in
`homelab/containers/syncthing-lxc/folders-manifest.yml`:

| What | Where |
| --- | --- |
| `pursuits.yml`, `register.yml`, `sources.yml` | `~/.config/doit/` |
| review/labs state, draw history, nudge marker | `~/.local/state/doit/` |
| cards and Labs | `~/.local/share/doit/`, cloned on first run |

`register.yml` used to live under `$XDG_DATA_HOME/menu-review/` as a symlink into this repo. It is
hand-edited config that the tool only ever reads, it is personal, and both `doit` repos are public —
so it belongs in the config directory and outside version control.

## See Also

- [Toolbox](toolbox.md) — still here, and still what `doit launch` reads for the installed-tool list
- [Tool Composition](../architecture/tool-composition.md) — how the remaining tools compose
- [App Installation Patterns](../learnings/app-installation-patterns.md) — the four install patterns
