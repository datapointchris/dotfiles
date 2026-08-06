# Tool Composition

The workflow tools are separate programs that compose at the shell, not one
application with subcommands. Each emits clean, parseable data and leaves
presentation to whatever is downstream — fzf, gum, or a script. The pattern is
borrowed from [sesh](https://github.com/joshmedeski/sesh): integration happens
at the shell level, never inside the tool.

`toolbox list` enumerates what exists; the per-tool pages are under
[Apps](../apps/index.md). This page is only the reasoning that spans them.

## Design Decisions

### Why not build fzf/gum INTO each tool?

**Anti-pattern**:

```bash
sesh --fzf          # Now sesh depends on fzf
toolbox --interactive  # Now toolbox needs gum
```

**Better**:

```bash
sesh list | fzf     # sesh is independent
toolbox list | gum choose  # toolbox doesn't know about gum
```

**Benefits**:

- Tools stay lightweight (no UI dependencies)
- Users choose their UI (fzf, gum, rofi, dmenu)
- Easier to test (pure functions, predictable output)
- Works in scripts without interactive flags

### Why bash scripts instead of one Go application?

**Pragmatism over purity**:

- **sesh/toolbox** are Go because: Complex logic, concurrent operations, type safety for config parsing
- **theme/notes/menu** are bash because: Simple text processing, YAML parsing with yq, shell integration

**Rule of thumb**: If it's mostly calling other CLI tools and processing text, bash is simpler.

### Why separate tools instead of one "workflow" command?

**Unix philosophy over convenience**:

```bash
# Anti-pattern: Mega-tool
workflow sessions    # subcommand
workflow tools      # another subcommand
workflow themes     # yet another subcommand

# Better: Focused tools
sesh
toolbox
theme
```

**Benefits**:

- Each tool has clear purpose and ownership
- Can be used independently or composed
- Easier to maintain (single responsibility)
- Natural command names (no subcommand memorization)

### The rules that keep the federation thin

Every collection is a **registry** — a store of things with a searchable index. `menu` is a
composer above them and owns no content of its own. Four rules keep it that way:

- **One registry is the vetted allow-list.** `menu` searches only your own collections, never
  tldr or cheat's universe. The alternative surfaces thirty backup tools you do not have.
- **Metadata lives once; content is pulled live.** The registry stores *why you would want it*
  (description, tags, why_use). What it *is* comes live from `--help`, `type`, or the
  tldr/cheat page. `toolbox check` guards registry ↔ PATH ↔ disk so nothing lives in two
  places and drifts.
- **Tags are the discovery contract.** Search is biased to name and tags. A missing result
  means a missing tag, not a change to `menu`.
- **The HELP lens fires only for own tools that resolve on PATH** (registry
  `category: custom-tools`), under `timeout 5`. Running `--help` on an arbitrary external
  command is not safe, so externals lean on tldr and cheat.

### Why two verbs and no `show`

`menu [term]` is the picker and Enter opens the full view — find and show are one motion.
`menu review` is the temporal half, the cadence-due list. A third `show` verb existed and was
collapsed: find-vs-show was too subtle a distinction to remember which one to type. Search is
WYSIWYG as a consequence — name, description, and tags live in the single displayed field, and
that field is exactly what fzf matches.

### Why the review register is Python

`apps/common/menu-review` is a uv single-file script; `menu` (bash) delegates to it via `exec`.
Bash was tried first and reversed mid-build — the register is data, dates, and state, which is
where bash fights you: IFS collapses empty columns, epoch math is manual, sorting is
error-prone. `datetime` and `json` make it correct without effort.

Two files, config and state split:

- `$XDG_DATA_HOME/menu-review/register.yml` — declarative, hand-edited, **read-only to the
  tool**. python-yq and pyyaml both strip comments on write, so config must never be
  machine-written.
- `$XDG_STATE_HOME/menu/review-state.json` — the `last_done` map, written by `done`.

`next_due = last_done + cadence` is derived, never stored.

## Related

- [Menu](../apps/menu.md) — the composer these rules govern
- [Toolbox](../apps/toolbox.md) — the registry they read
- [Shell Libraries](shell-libraries.md) — the help grammar every tool shares
