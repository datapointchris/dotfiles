# Tool Composition

The workflow tools are separate programs that compose at the shell, not one
application with subcommands. Each emits clean, parseable data and leaves
presentation to whatever is downstream — fzf, gum, or a script. The pattern is
borrowed from [sesh](https://github.com/joshmedeski/sesh): integration happens
at the shell level, never inside the tool.

`doit kit list` enumerates what exists; the per-tool pages are under
[Apps](../apps/index.md). This page is only the reasoning that spans them.

## Design Decisions

### Why not build fzf/gum INTO each tool?

**Anti-pattern**:

```bash
sesh --fzf              # Now sesh depends on fzf
theme --interactive     # Now theme needs gum
```

**Better**:

```bash
sesh list | fzf         # sesh is independent
theme list | gum choose # theme doesn't know about gum
```

**Benefits**:

- Tools stay lightweight (no UI dependencies)
- Users choose their UI (fzf, gum, rofi, dmenu)
- Easier to test (pure functions, predictable output)
- Works in scripts without interactive flags

### Why bash scripts instead of one Go application?

**Pragmatism over purity**:

- **sesh** is Go because: Complex logic, concurrent operations, type safety for config parsing
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
theme
notes
```

**Benefits**:

- Each tool has clear purpose and ownership
- Can be used independently or composed
- Easier to maintain (single responsibility)
- Natural command names (no subcommand memorization)

### The rules that keep the federation thin

The federated search lives in [doit](../apps/doit.md) and the collections it reads live in
`terminal-library`, so nothing about it is owned here any more. The contract is recorded here
because it is what the shell tools on this side are built to satisfy. Every collection is a
**registry** — a store of things with a searchable index — and the composer above them owns no
content of its own. Three rules keep it that way:

- **One registry is the vetted allow-list.** The search covers only your own collections, never
  tldr or cheat's universe. The alternative surfaces thirty backup tools you do not have.
- **Metadata lives once; content is pulled live.** The registry stores *why you would want it*
  (description, tags, why_use). What it *is* comes live from `--help`, `type`, or the
  tldr/cheat page, so nothing lives in two places and drifts.
- **Tags are the discovery contract.** Search is biased to name and tags. A missing result
  means a missing tag, not a change to the search tool.

`doit` reads `$XDG_DATA_HOME/terminal-library/tools/registry.yml` directly, resolved by
`library_dir()` and overridable with `DOIT_TOOLS_REGISTRY`. That is the whole coupling: the
registry is a file with a documented shape, so neither tool has to know the other exists.

The registry moved to `terminal-library` because the collection outlives any one tool that parses
it, and it is authored content rather than machine configuration — adding a tool is an edit to a
content repo `doit content sync` pulls, never a deploy from here.

## Related

- [doit](../apps/doit.md) — the composer these rules govern, now in its own repo
- [Shell Libraries](shell-libraries.md) — the help grammar every tool shares
