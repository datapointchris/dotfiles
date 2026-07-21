---
icon: material/magnify
---

# Menu

Search across your tools, shell functions, aliases, git aliases, forgit shortcuts, tmux keybindings, workflows, and Claude skills in one place, then
see everything known about the one you pick. `menu` is a thin **pointer**: it federates your
collections into one searchable index and, on selection, assembles the full picture from whichever
sources have it. It stores no content of its own.

## Quick Start

```bash
menu                    # Launcher: your areas + every custom tool you own
menu keybind            # Search the federated index, pre-filtered to a term
menu find keybind       # Search, explicit
menu search keybind     # Same as menu find
```

Bare `menu` opens the **launcher** (see below). Passing a term goes straight to the federated
**search**; type to filter and press **Enter** on any result to open its full view in a pager.
**From tmux**: `Ctrl-Space` then `m` (opens `menu` in a popup at the current path).

## The launcher

Bare `menu` — no arguments — opens a picker of **your own areas and tools**, so "what can I even run
here" is one keystroke away. It lists menu's three areas (`find`, `review`, `labs`) followed by every
tool in the registry's `custom-tools` category, each previewed with its `toolbox` entry. Selecting an
area enters it; selecting a tool runs it with no arguments (which, by convention, shows that tool's
help or status). This is the fix for forgetting a tool exists — `packages`, `syncer`, `patterns`,
`notes`, and the rest are all right there. To skip straight to content search, give `menu` a term or
use `menu find` / `menu search`.

## What it searches

`menu` builds a live index over eight collections, each shown with a source tag so you know where
a result lives:

| Source | Collection | Where it comes from |
| --- | --- | --- |
| `[tool]` | tools registry | `$TOOLBOX_REGISTRY`, else the registry under the XDG data dir |
| `[func]` | shell functions | `~/.local/shell/functions.sh` + `$PLATFORM.sh` (`#@name` / `#-->desc` annotations) |
| `[alias]` | shell aliases | `~/.local/shell/aliases.sh` + `$PLATFORM.sh` |
| `[git]` | git aliases | `git config --get-regexp '^alias\.'` (invoke as `git <name>`) |
| `[forgit]` | forgit fzf-git shortcuts | the forgit plugin (`ga`, `gd`, `glo`, …) — sourced after `aliases.sh`, so in no shell file menu reads |
| `[tmux]` | tmux keybindings | the `tmux-commands` card (`~/.local/share/workflows/tmux-commands.md`), its two-column grid parsed into one row per binding |
| `[workflow]` | reference cards | `~/.local/share/workflows/*.md` (frontmatter tags) |
| `[skill]` | Claude skills | `~/.claude/skills/*/SKILL.md` |

Functions surface only if they carry the `#@name` / `#-->desc` annotation — the same convention
`toolbox funcs` reads. That annotation is the opt-in: unannotated functions are internal helpers and
stay hidden. Aliases are indexed by definition, with the preceding comment as the description.

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
| `function` | an annotated shell function of that name exists | its definition, syntax-highlighted |
| `alias` | an alias of that name is defined | its expansion |
| `git alias` | a git alias of that name is defined | its expansion (invoke as `git <name>`) |
| `forgit` | the name is a forgit plugin alias | the forgit action it runs (fzf-interactive git) |
| `tmux` | the name is a tmux keybinding | the `tmux-commands` keybinding reference card |

So selecting your own `backmeup` shows its live `--help` alongside its registry entry, while an
external `bat` shows its registry entry with the tldr and cheat pages. The `--help` lens is
limited to your own tools on purpose: running `--help` against an arbitrary external command is
not safe, and externals are covered by tldr and cheat anyway.

The full view is piped through a pager (`less -FRX`): short subjects print inline, long composites
scroll comfortably, and the output stays on screen after you quit so you can select and copy any
command from it. Every lens also names its source — extracted functions and aliases carry the file
path via `bat --file-name`, and the composite view prints a `↳ path` breadcrumb — so you always know
what you're looking at.

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

The register is deliberately **two files**, following the split between authored content you own and
state the tool manages:

- a **register** — declarative config you hand-edit: each item's `description`, `cadence`, an
  optional `command` to show, and an optional `show:` command to *run* (see the nudge below).
  `menu review` only ever reads it, so your comments and layout are never disturbed. It is owned by
  dotfiles and symlinked under the XDG data dir, so it is version-controlled and reaches every machine.
- a **state file** — the last-done date per item, written by `done`. It lives under the XDG state
  dir; keeping it out of git avoids a commit on every `done`.

The due date is **derived, never stored**: `next_due = last_done + cadence`. Marking something done
just stamps today, so there is no date to keep in sync and nothing to drift. A new item with no
recorded done shows as *never done* and sorts to the top. Replication of the state across machines is
arranged by the sync layer, not the tool; override either path with `MENU_REVIEW_REGISTER` /
`MENU_REVIEW_STATE`.

This half is written in Python (`apps/common/menu-review`), which `menu review` delegates to — date
arithmetic and JSON state are far cleaner there than in shell. The picker stays bash, because it is
just `fzf` glue.

### The startup nudge

`menu review` is pull — it only helps when you remember to run it. The nudge makes it push: at most
once per interval (default 4h, set with `menu review nudge-every <dur>`), a shell surfaces what's due
and stays silent when you are caught up. This replaces the old `workflows motd` random-card-on-startup
— scheduled return to a topic you chose beats random exposure to one you didn't.

The gate lives in `.zshrc`: a cheap check of the marker file's age against the interval decides
whether enough time has passed, and only then spawns the reviewer. Keeping the gate in shell means
the Python script launches at most once per interval, not on every prompt. `menu-review nudge` is the
renderer it calls — it prints due items or nothing, and does no throttling of its own. The marker and
interval live in the synced menu state dir, so the schedule is shared across machines — one rolling
nudge budget, not one per machine.

**Live content (`show:`).** A register item can carry a `show:` command whose output is run and
inlined *when that item is due in the nudge* — distinct from `command:`, which is only displayed.
This is what makes "relearn a neglected tool" concrete: the `revisit-a-tool` item sets
`show: toolbox remind`, so when it comes due the nudge shows the specific registry tool you have not
used in 90 days (`toolbox remind` picks it, weighted by neglect and round-robined so it cycles). The
`show:` command runs **only** in the nudge, never in `menu review` / `list`, because it has side
effects — `toolbox remind` advances its own history each call — and running it on every manual view
would burn through the rotation. It is timeout-guarded so a slow command cannot wedge startup. This
replaced the old standalone `toolbox remind` shell-startup block, which fired a passive tool card on
*every* shell; folding it into the register makes it one actionable, cadenced line instead.

## `menu labs` — hands-on practice

Reviewing a tool's card builds recognition; *using* it builds retention. `menu labs` is the
practice half: a small deck of hands-on **Labs** that walk you through a tool the way a senior
engineer walks a junior — do this, expect that, here's why, here's the alternative — while you type
along in a scratch directory.

```bash
menu labs                 # what's due to practice now
menu labs list            # every Lab and its schedule status
menu labs <id>            # open a Lab to read while you work in another pane
menu labs done <id>       # mark a Lab practiced — advances its schedule
menu labs new <name>      # scaffold a new Lab and open it in $EDITOR
menu labs flash [x]       # quick recall drill from your tool examples
```

**A Lab is one markdown file.** Labs live in `~/.local/share/menu-labs/*.md` (authored in the
dotfiles source at `configs/common/.local/share/menu-labs/` and deployed by the symlink manager —
the same convention as workflow cards). Each Lab teaches one tool or flow: a short copy-pasteable
**setup block** that stages a throwaway directory, then numbered steps giving the command, the
expected result, why it works, and alternatives. Frontmatter carries only `tags` (the same
discovery vocabulary the picker uses) and an optional `cadence`; the title is the file's first
`#` heading, exactly like a workflow card.

**You drive the panes.** The runner is deliberately minimal — it renders the Lab and tracks the
schedule, nothing more. Open two tmux panes yourself: read the Lab in one (`menu labs <id>` pipes
it through `bat`), copy its setup block into the other, and work through the steps at your own
keyboard. There is no grading, no sandbox automation, no keystroke capture — the point is the reps,
not a score.

**Scheduling reuses the review model.** A Lab with a `cadence` is scheduled exactly like a review
item — `next_due = last_done + cadence`, derived not stored — with state in `~/dev/labs-state.json`
(Syncthing-synced; override the deck path with `MENU_LABS_DIR` and state with `MENU_LABS_STATE`). A
Lab with no cadence is practice-on-demand and never shows as due. `menu labs` shows what's due; mark
one `done` once you've worked through it.

**Flashcards need no authoring.** `menu labs flash` builds a recall deck straight from the tool
registry's examples: it shows an example's description, you recall the command, then reveal and
self-mark. Scope it to one tool or tag with `menu labs flash <x>`. This gives every tool something
to drill from day one, before any Lab exists for it. Sessions stay short by design — a few minutes
daily beats cramming.

**Federation for a bare tool name.** `menu labs <tool>` (when the argument isn't a Lab) shells to
`menu __show` to assemble that tool's whole constellation across every lens — its registry entry,
a same-named workflow card, aliases, functions — then points you at its flashcards. So even with no
Lab written, asking to practice a tool surfaces everything you already have on it.

**In the nudge.** The review register carries a `practice-a-lab` item (`show: menu labs --due`), so
the twice-daily startup nudge advertises when Labs come due, right beside the neglected-tool
reminder — and stays silent when you're caught up.

## Implementation

**Location**: `apps/common/menu` (picker, bash), `apps/common/menu-review` (register, Python), and
`apps/common/menu-labs` (Labs, Python). The two Python halves share `menucore` — a small repo-root
package (cadence parsing, atomic state, the color palette) imported via each script's resolved path,
so no install step is needed and the register and Labs never drift apart on scheduling.

**Dependencies**: `fzf` (picker) and `yq` (registry) drive search and the launcher; the full view
delegates to `toolbox`, `workflows`, `tldr`, `cheat`, and `bat`, and is paged through `less`;
`formatting.sh` provides the shell styling. The register and Labs run as `uv` single-file scripts
depending only on `pyyaml`.

The index is a three-column tab-separated stream — display, source, name — built by
`build_index`. Two internal subcommands help with debugging and scripting: `menu __index` prints
the raw index, and `menu __show <name>` renders a subject's full view non-interactively.

## See Also

- [Toolbox](toolbox.md) - Browse and show details for any tool in the registry
- [Theme](theme.md) - Theme management
- [Notes](notes.md) - Note-taking
