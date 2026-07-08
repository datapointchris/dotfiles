---
icon: material/magnify
---

# Menu

Search across your tools, workflows, and Claude skills in one place, then jump straight to the
right one. `menu` is a thin **pointer**: it federates your collections into one searchable index
and hands each result back to the tool that owns it. It stores no content of its own.

## Quick Start

```bash
menu                    # Interactive picker across everything
menu keybind            # Picker pre-filtered to a term
menu find keybind       # Same, explicit
```

**From tmux**: `Ctrl-Space` then `m` (opens `menu` in a popup at the current path).

## What it searches

`menu` builds a live index over three collections, each shown with a source tag so you know
where a result lives:

| Source | Collection | Where it comes from |
| --- | --- | --- |
| `[tool]` | tools registry | `$TOOLBOX_REGISTRY`, else `~/dev/tools.yml` |
| `[workflow]` | reference cards | `~/.local/share/workflows/*.md` (frontmatter tags) |
| `[skill]` | Claude skills | `~/.claude/skills/*/SKILL.md` |

Selecting a result opens it via the collection that owns it — `toolbox show` for a tool,
`workflows show` for a card, `bat` on the raw `SKILL.md` for a skill. Adding a new collection
later is one more index function; `menu` never grows heavy because the depth always lives in the
collections, not here.

## Search is biased toward names and tags

fuzzy matching runs over each entry's **source, name, and tags** — not its full description. Tool
descriptions are long and generate loose subsequence matches, so they are excluded from the
search (every tool in the registry is tagged, so nothing becomes unreachable); they still appear
in the list for context. Workflow *titles* and skill *descriptions* are included because those
collections carry the concept words that tags alone would miss (e.g. `restore` finds the
git-stash card, `motion` finds the neovim-motions card).

The practical consequence: **tags are the discovery contract.** A search returns everything that
carries the matching tag, ranked above looser matches. If something you expect doesn't surface,
the fix is a better tag on that entry, not a change to `menu`.

## Implementation

**Location**: `apps/common/menu`

**Dependencies**: `fzf` (picker), `yq` (registry), `bat` (skill preview), plus `toolbox` and
`workflows` for delegated display; `formatting.sh` shell library.

The `menu __index` subcommand prints the raw federated index (tab-separated: display, source,
name, search-key) — useful for debugging what is indexed or composing with other tools.

## See Also

- [Toolbox](toolbox.md) - Browse and show details for any tool in the registry
- [Theme](theme.md) - Theme management
- [Notes](notes.md) - Note-taking
