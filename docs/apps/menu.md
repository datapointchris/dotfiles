---
icon: material/magnify
---

# Menu

Search across your tools, workflows, and Claude skills in one place, then see everything known
about the one you pick. `menu` is a thin **pointer**: it federates your collections into one
searchable index and, on selection, assembles the full picture from whichever sources have it. It
stores no content of its own.

## Quick Start

```bash
menu                    # Interactive picker across everything
menu keybind            # Picker pre-filtered to a term
menu find keybind       # Same, explicit
```

Type to filter, and press **Enter** on any result to open its full view. **From tmux**:
`Ctrl-Space` then `m` (opens `menu` in a popup at the current path).

## What it searches

`menu` builds a live index over three collections, each shown with a source tag so you know where
a result lives:

| Source | Collection | Where it comes from |
| --- | --- | --- |
| `[tool]` | tools registry | `$TOOLBOX_REGISTRY`, else `~/dev/tools.yml` |
| `[workflow]` | reference cards | `~/.local/share/workflows/*.md` (frontmatter tags) |
| `[skill]` | Claude skills | `~/.claude/skills/*/SKILL.md` |

Adding a new collection later is one more index function; `menu` never grows heavy because the
depth always lives in the collections, not here.

## Search is what you see

Each result's line carries its **name, description or title, and tags** — and that whole line is
exactly what fuzzy matching runs over. Search is WYSIWYG: if a result surfaced, you can see the
word that matched it, right there in the line. This is a deliberate constraint of the picker
(`fzf` can only search the text it displays), turned into a feature.

The practical consequence: **tags are the discovery contract.** Because tags ride along in every
line, a search finds everything carrying a matching tag, and a name or tag hit ranks above a
looser match buried in a description. If something you expect doesn't surface, the fix is a better
tag on that entry, not a change to `menu`.

## Enter opens the full view

Finding a thing and understanding it are one motion. Pressing Enter assembles every **lens** that
has content for the selected subject, in priority order, showing only the sections that exist:

| Lens | Fires when | Answers |
| --- | --- | --- |
| `help` | the subject is one of *your own* tools and resolves on `PATH` | live flags, as of right now |
| `toolbox` | the subject is in the registry | why you'd reach for it, curated examples |
| `tldr` | a tldr page exists | common real-world invocations |
| `cheat` | a cheat sheet exists | your saved snippets |
| `workflow` | a card of the same name exists | your multi-step reference |
| `skill` | a skill of the same name exists | the raw `SKILL.md` |

So selecting your own `backmeup` shows its live `--help` alongside its registry entry, while an
external `bat` shows its registry entry with the tldr and cheat pages. The `--help` lens is
limited to your own tools on purpose: running `--help` against an arbitrary external command is
not safe, and externals are covered by tldr and cheat anyway.

## Implementation

**Location**: `apps/common/menu`

**Dependencies**: `fzf` (picker) and `yq` (registry) drive search; the full view delegates to
`toolbox`, `workflows`, `tldr`, `cheat`, and `bat`; `formatting.sh` provides the shell styling.

The index is a three-column tab-separated stream — display, source, name — built by
`build_index`. Two internal subcommands help with debugging and scripting: `menu __index` prints
the raw index, and `menu __show <name>` renders a subject's full view non-interactively.

## See Also

- [Toolbox](toolbox.md) - Browse and show details for any tool in the registry
- [Theme](theme.md) - Theme management
- [Notes](notes.md) - Note-taking
