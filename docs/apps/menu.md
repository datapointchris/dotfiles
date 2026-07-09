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

## `menu review` — what's due to revisit

Finding a tool once doesn't build retention; returning to it on a schedule does. `menu review` is
the temporal half: a terminal-native cadence register for the things you mean to revisit or run
periodically — a maintenance command, a skill, "relearn one neglected tool."

```bash
menu review               # what's due now, most overdue first
menu review list          # every registered item and its status
menu review done <id>     # mark an item done — advances its due date
menu review edit          # edit the register in $EDITOR
```

The register is deliberately **two files**, following the split between configuration you own and
state the tool manages:

- `~/dev/review.yml` — declarative config you hand-edit: each item's `description`, `cadence`
  (`2w`, `1mo`, `10d`, `1y`), and an optional `command` to show. `menu review` only ever reads
  it, so your comments and layout are never disturbed.
- `~/dev/review-state.json` — the last-done date per item, written by `done`.

The due date is **derived, never stored**: `next_due = last_done + cadence`. Marking something done
just stamps today, so there is no date to keep in sync and nothing to drift. A new item with no
recorded done shows as *never done* and sorts to the top. Both files live in `~/dev` (Syncthing-
synced) alongside the tools registry, so "due" is consistent across machines; override the paths
with `MENU_REVIEW_REGISTER` and `MENU_REVIEW_STATE`.

This half is written in Python (`apps/common/menu-review`), which `menu review` delegates to — date
arithmetic and JSON state are far cleaner there than in shell. The picker stays bash, because it is
just `fzf` glue.

### The startup nudge

`menu review` is pull — it only helps when you remember to run it. The nudge makes it push: the
first shell of each half-day (morning and afternoon, at most twice a day) surfaces what's due, and
stays silent when you are caught up. This replaces the old `workflows motd` random-card-on-startup —
scheduled return to a topic you chose beats random exposure to one you didn't.

The gate lives in `.zshrc`: a cheap `date +%F-%p` slot compare against a marker file decides whether
this is the first shell of a new slot, and only then spawns the reviewer. Keeping the gate in shell
means the Python script launches twice a day, not on every prompt. `menu-review nudge` is the
renderer it calls — it prints due items or nothing, and does no throttling of its own. The marker
lives in `$XDG_STATE_HOME/menu-review/nudge-slot` (machine-local, **not** Syncthing-synced), so each
machine's first-shell-of-the-day is independent.

## Implementation

**Location**: `apps/common/menu` (picker, bash) and `apps/common/menu-review` (register, Python)

**Dependencies**: `fzf` (picker) and `yq` (registry) drive search; the full view delegates to
`toolbox`, `workflows`, `tldr`, `cheat`, and `bat`; `formatting.sh` provides the shell styling. The
register runs as a `uv` single-file script depending only on `pyyaml`.

The index is a three-column tab-separated stream — display, source, name — built by
`build_index`. Two internal subcommands help with debugging and scripting: `menu __index` prints
the raw index, and `menu __show <name>` renders a subject's full view non-interactively.

## See Also

- [Toolbox](toolbox.md) - Browse and show details for any tool in the registry
- [Theme](theme.md) - Theme management
- [Notes](notes.md) - Note-taking
