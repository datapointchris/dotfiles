---
icon: material/toolbox
---

# Toolbox

Tool discovery system for the 98 tools in your dotfiles. Find tools by name, category, or purpose. Get usage examples and learn when to use each tool.

## Quick Start

```bash
toolbox              # Show help
toolbox git          # Search for git tools (shortcut)
toolbox list         # List all tools by category
toolbox categories   # Interactive category browser
toolbox show bat     # Detailed info about bat
```

Search shortcut: Type `toolbox python` instead of `toolbox search python` for quick lookups.

## Commands

### List All Tools

See every tool organized by category:

```bash
toolbox list
```

Output groups tools by category with one-line descriptions, sorted alphabetically. This provides a complete inventory of your toolchain.

Categories reflect how you think about tools:

- file-viewer (bat, eza, yazi)
- search (ripgrep, fzf, fd)
- version-control (git, gh, lazygit, delta)
- linter (shellcheck, markdownlint, yamllint)
- formatter (prettier, black, stylua)
- language-server (pyright, typescript-language-server)

### Show Tool Details

Get comprehensive information about a specific tool:

```bash
toolbox show bat
toolbox show ripgrep
```

Detail view shows:

- Description and why to use it
- Installation method (brew, npm, uv, cargo)
- Usage syntax
- Examples with explanations
- Related tools
- Documentation URL
- Installation status

### Search Tools

Find tools by description, tags, name, or purpose. Case-insensitive search across all metadata:

```bash
toolbox search git       # Find git-related tools
toolbox search syntax    # Find syntax highlighting tools
toolbox search docker    # Find Docker tools

# Shortcut syntax (recommended)
toolbox git              # Same as search git
toolbox python           # Same as search python
```

### Browse Categories

Interactive two-level picker with gum:

```bash
toolbox categories
```

1. Select a category (shows tool count and preview)
2. Select a tool (shows full details)

Requires gum (`brew install gum`).

## Registry Structure

Tools are defined in `~/dotfiles/docs/tools/registry.yml`:

```yaml
tool-name:
  category: file-viewer
  description: "Brief description"
  installed_via: brew              # brew, npm, uv, cargo, manual
  usage: "command [options] <args>"
  why_use: "Why this tool over alternatives"
  examples:
    - cmd: "command --option"
      desc: "What this does"
  see_also: [related-tool1, related-tool2]
  tags: [tag1, tag2]
  docs_url: "https://..."
```

Required fields: category, description, installed_via, usage.

Optional but recommended: why_use, examples, see_also, tags, docs_url.

## How It Works

Toolbox is a Go application that reads `registry.yml` and provides fast search and browsing. It doesn't track usage, wrap commands, or modify PATH - it's purely a reference tool.

The registry uses YAML for easy editing and human readability. Each tool entry captures:

- What it does (description)
- Why you'd use it (why_use)
- How to use it (usage, examples)
- What's related (see_also, category)
- Where to learn more (docs_url)

Search indexes all fields, making it easy to find tools by any aspect - name, purpose, category, or tags.

## Workflow

Discover what's available:

```bash
toolbox list              # See complete inventory
```

Find a tool for a specific task:

```bash
toolbox search format     # Find formatting tools
toolbox search diff       # Find diff tools
```

Learn about a forgotten tool:

```bash
toolbox show bat          # Refresh memory on bat
```

Browse a category:

```bash
toolbox categories        # Interactive browser
# Select "version-control"
# Explore git, gh, lazygit, delta
```

Explore randomly:

```bash
toolbox show $(toolbox list | grep -v "^#" | shuf -n 1 | awk '{print $1}')
# Discover a random tool
```

## Building from Source

Toolbox is a Go application:

```bash
cd apps/common/toolbox
task build    # Creates local binary
task install  # Installs to ~/go/bin/toolbox
task test     # Run tests
```

## Adding Tools

Edit `~/dotfiles/docs/tools/registry.yml` to add tools:

```yaml
new-tool:
  category: utility
  description: "What it does"
  installed_via: brew
  usage: "new-tool [options]"
  why_use: "Why you'd use this over alternatives"
  examples:
    - cmd: "new-tool --example"
      desc: "Example usage"
  see_also: [related-tool]
  tags: [tag1, tag2]
  docs_url: "https://..."
```

Commit changes to dotfiles repo. Toolbox reads the registry on each invocation.

## Best Practices

**Use the search shortcut**: Type `toolbox git` instead of `toolbox search git` for faster lookups.

**Add why_use field**: This helps you remember when to use a tool over alternatives. "Why bat over cat?" is more useful than just knowing bat exists.

**Provide concrete examples**: Generic syntax helps less than real-world usage. Show actual commands you'd run.

**Link related tools**: The see_also field helps discover tool combinations. Bat leads to eza, ripgrep leads to fd and fzf.

**Tag thoughtfully**: Tags improve searchability. A Python tool should have tags like [python, language, repl] so it appears in multiple searches.

## Troubleshooting

**Command not found**: Verify installation with `which toolbox`. If missing, run `cd apps/common/toolbox && task install`.

**Registry not found**: Check `ls ~/dotfiles/docs/tools/registry.yml`. The registry must exist for toolbox to work.

**Search returns nothing**: Verify tools are installed with `which <tool>`. Toolbox shows installed status but doesn't auto-detect.

## See Also

- [Menu System](menu.md) - Quick access to workflow tools
- [Tool Registry](../tools/registry.yml) - Complete tool database
