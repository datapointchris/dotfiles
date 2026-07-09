---
icon: material/toolbox
---

# Toolbox

CLI tool discovery for the installed toolchain — search tools, shell functions, and aliases, and resurface the ones you've forgotten. A standalone Go project: **[datapointchris/toolbox](https://github.com/datapointchris/toolbox)** is the source of truth for the full command reference (or run `toolbox --help`).

## In this system

- **Install** — `packages.yml` under `go_tools`, via `go install github.com/datapointchris/toolbox@latest`. The binary lands in `~/go/bin`.
- **Registry** — `~/dev/tools.yml` (override with `$TOOLBOX_REGISTRY`). It is Syncthing-synced *data*, not part of this repo: the dev paths (`~/tools`, `~/dotfiles`) don't exist on every machine but `~/dev` does. Edit it to add or update tools; the entry schema is in the repo.
- **Federated by `menu`** — `menu` searches the registry, shell functions, and aliases alongside workflows and skills, delegating display back to `toolbox show`. See [Menu](menu.md).
- **Rediscovery** — `toolbox remind` surfaces a forgotten tool, function, alias, git alias, or forgit shortcut (neglect-weighted, 90-day recency). It runs on a cadence through `menu review`'s `revisit-a-tool` item (`show: toolbox remind`), not on every shell.
