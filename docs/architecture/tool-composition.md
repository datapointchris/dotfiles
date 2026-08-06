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
- **theme/notes** are bash because: Simple text processing, YAML parsing with yq, shell integration

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

The federated search moved to [doit](../apps/doit.md) with the rest of the menu suite, but the
contract it depends on is still owned here, because `toolbox` is still here. Every collection is a
**registry** — a store of things with a searchable index — and the composer above them owns no
content of its own. Three rules keep it that way:

- **One registry is the vetted allow-list.** The search covers only your own collections, never
  tldr or cheat's universe. The alternative surfaces thirty backup tools you do not have.
- **Metadata lives once; content is pulled live.** The registry stores *why you would want it*
  (description, tags, why_use). What it *is* comes live from `--help`, `type`, or the
  tldr/cheat page. `toolbox check` guards registry ↔ PATH ↔ disk so nothing lives in two
  places and drifts.
- **Tags are the discovery contract.** Search is biased to name and tags. A missing result
  means a missing tag, not a change to the search tool.

`doit` reads `$XDG_DATA_HOME/toolbox/registry.yml` directly. That is the whole coupling: the
registry is a file with a documented shape, so neither tool has to know the other exists.

## Related

- [doit](../apps/doit.md) — the composer these rules govern, now in its own repo
- [Toolbox](../apps/toolbox.md) — the registry they read
- [Shell Libraries](shell-libraries.md) — the help grammar every tool shares
