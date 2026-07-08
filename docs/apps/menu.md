---
icon: material/menu
---

# Menu

List every personal CLI tool with its description, so forgotten tools resurface at a glance.
`menu` is the fast "what do I have" view; [`toolbox`](toolbox.md) is the deeper search-and-detail
browser over the same catalog.

## Quick Start

```bash
menu                    # List all personal tools with descriptions
```

**From tmux**: `Ctrl-Space` then `m` (opens `menu` in a popup at the current path).

## How it works

`menu` reads the tool registry and prints every tool in the `custom-tools` category, sorted by
name, as `name — description`. It is a non-interactive listing, not a launcher — run the tool
you spot directly.

The registry is the single source of truth shared with `toolbox` and `tool-usage`: it lives at
`$TOOLBOX_REGISTRY`, or `~/dev/tools.yml` by default. Because the registry is Syncthing-synced
rather than derived from the `~/tools` or `~/dotfiles` working trees, `menu` produces the same
list on every machine, not only ones with the dev repos checked out. Adding a tool to the
registry makes it appear in `menu`, `tool-usage`, and `toolbox` at once.

## Implementation

**Location**: `apps/common/menu`

**Dependencies**: `yq` (registry query), `formatting.sh` (shell library)

## See Also

- [Toolbox](toolbox.md) - Search and show details for any tool in the registry
- [Theme](theme.md) - Theme management
- [Font](font.md) - Font management
- [Notes](notes.md) - Note-taking
