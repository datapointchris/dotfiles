---
icon: material/toolbox
---

# Toolbox

CLI tool discovery for the installed toolchain — search tools, shell functions, and aliases, and resurface the ones you've forgotten. A standalone Go project: **[datapointchris/toolbox](https://github.com/datapointchris/toolbox)** is the source of truth for the full command reference (or run `toolbox --help`).

## In this system

- **Install** — `packages.yml` under `go_tools`, via `go install github.com/datapointchris/toolbox@latest`. The binary lands in `~/go/bin`.
- **Registry** — authored *data*, not config, and it **now lives in `terminal-library`**, which `doit` reads. Dotfiles still carries a copy at `configs/common/.local/share/toolbox/registry.yml`, symlinked under the XDG data dir (override with `$TOOLBOX_REGISTRY`), and that copy is what `toolbox show` reads — so an edit to only one of them diverges. The duplicate is deliberate: it is the rollback path while terminal-library proves itself, and `icb` 309 is the work that removes it. Add a tool to both until then.
- **Federated by `doit`** — `doit find` searches the registry, shell functions, and aliases alongside workflow cards and skills, delegating display back to `toolbox show`. See [doit](doit.md).
- **Rediscovery** — `toolbox remind` surfaces a forgotten tool, function, alias, git alias, or forgit shortcut (neglect-weighted, 90-day recency). It runs on a cadence through `menu review`'s `revisit-a-tool` item (`show: toolbox remind --brief`), not on every shell. `--brief` bounds the card to a few clipped lines because it renders inside that nudge; run bare, it shows the full detail view, which is the actual refresher.
