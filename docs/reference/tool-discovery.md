# Tool Discovery

The `toolbox` command helps discover and learn about the 98 tools installed in your dotfiles. Written in Go for speed and reliability, with beautiful interactive menus powered by gum.

## Quick Start

```bash
toolbox              # Show help
toolbox git          # Search for git tools (shortcut)
toolbox list         # List all tools by category
toolbox categories   # Interactive category browser (gum)
toolbox show bat     # Detailed info about bat
```

## Commands

### toolbox

Show help by default when run without arguments.

```bash
toolbox
toolbox --help
toolbox help
```

### toolbox list

List all tools grouped by category, sorted alphabetically.

```bash
toolbox list
```

Shows tools organized by category with descriptions. Categories and tools are both sorted alphabetically for easy browsing.

### toolbox show

Show detailed information about a specific tool.

```bash
toolbox show bat
toolbox show ripgrep
```

**Displays**:

- Description and why to use it
- Installation method (brew, npm, uv)
- Usage syntax
- Examples with explanations
- Related tools
- Documentation URL
- Installation status

### toolbox search

Search tools by description, tags, name, or why_use field. Case-insensitive.

```bash
toolbox search git
toolbox search syntax
toolbox search docker

# Shortcut: just type the query directly
toolbox git       # Same as: toolbox search git
toolbox python    # Same as: toolbox search python
```

Returns matching tools with category and description.

### toolbox categories

**Interactive mode** - Browse tools with gum's beautiful menus.

```bash
toolbox categories
```

Two-level interactive picker:

1. Select a category → Shows count and preview
2. Select a tool → Shows full tool details

Requires [gum](https://github.com/charmbracelet/gum) to be installed.

## Registry

Tools are defined in `~/.config/toolbox/registry.yml` (or `$DOTFILES_REGISTRY`) with structured YAML metadata.

**Tool entry format**:

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

**Categories**:

- file-viewer - bat, eza
- search - ripgrep, fzf
- navigation - zoxide
- version-control - git, gh, lazygit, git-delta
- editor - neovim
- terminal - tmux
- linter - ruff, eslint
- formatter - prettier, ruff-format
- language-server - typescript-language-server, basedpyright
- build - task, cmake
- container - docker
- system - htop, btop

## Adding Tools

Edit `platforms/common/.config/toolbox/registry.yml` and add new entry following the format above.

The registry is deployed via symlinks to `~/.config/toolbox/registry.yml`.

**Required fields**:

- category
- description
- installed_via
- usage

**Optional but recommended**:

- why_use (helps remember when to use it)
- examples (concrete usage patterns)
- see_also (discover related tools)
- tags (improve searchability)
- docs_url (quick reference)

After adding tools, run `toolbox list` to verify they appear.

## Implementation

Toolbox is written in **Go** for speed, reliability, and testability.

**Why Go**:

- **Fast**: Instant search (~1ms)
- **Type-safe**: Catches bugs at compile time
- **Testable**: Built-in testing framework
- **Reliable**: No bash string manipulation bugs
- **Cross-platform**: Single binary, no dependencies

**Architecture**:

```text
apps/common/toolbox/
├── main.go          # CLI commands (cobra)
├── types.go         # Data structures
├── registry.go      # YAML loading
├── search.go        # Search/filter logic
├── display.go       # Colored output
├── interactive.go   # Gum integration
└── search_test.go   # Test coverage
```

## Philosophy

The tool discovery system prioritizes **discovery over tracking**.

**What it does**:

- Help remember what tools are available
- Show usage examples when needed
- Search across 98 tools instantly
- Interactive browsing with gum
- Quick reference without leaving terminal

**What it doesn't do**:

- Track usage statistics
- Wrap commands with shell functions
- Modify PATH or aliases
- Auto-install tools

**Why**: Keeps shell configs clean, no performance impact, easy to maintain, solves the real problem (tool awareness).

## Examples

```bash
# Forgot what bat does?
toolbox show bat

# What git tools are available?
toolbox git              # Shortcut
toolbox search git       # Explicit

# Browse by category (interactive)
toolbox categories

# List everything
toolbox list

# Find network-related tools
toolbox network
```

## Integration

The `toolbox` command integrates with other dotfiles systems:

**Installation**: Built from source during `task symlinks:link`

```bash
# Binary compiled to: apps/common/toolbox/toolbox
# Symlinked to: ~/.local/bin/toolbox
```

**Registry**: Lives in `platforms/common/.config/toolbox/registry.yml`

- Synced via symlinks to `~/.config/toolbox/registry.yml`
- Version controlled for easy editing
- Currently contains 98 tools

**Task automation**: `task shell:install` handles building and linking

**Documentation**:

- Quick reference: `docs/reference/tools.md`
- Detailed reference: This file
- Code documentation: `apps/common/toolbox/README.md`

## Building from Source

```bash
cd apps/common/toolbox
go build -o toolbox
```

The binary is automatically built and symlinked during `task symlinks:link`.

## Testing

```bash
cd apps/common/toolbox
go test -v           # Run tests
go test -cover       # With coverage
```

## Troubleshooting

**Command not found**:

- Run `task symlinks:link` to rebuild and link
- Verify `~/.local/bin` is in PATH
- Check binary exists: `ls -la ~/.local/bin/toolbox`

**Tool shows as "Shell function" but it's a binary**:

- Shell functions (from `functions.sh`) won't be in PATH
- This is correct - they're sourced by your shell, not in PATH

**Registry not found**:

- Verify symlink: `ls -la ~/.config/toolbox/registry.yml`
- Should point to: `~/dotfiles/platforms/common/.config/toolbox/registry.yml`
- Run `task symlinks:link` if missing

**Search returns no results**:

- Search is case-insensitive and searches all fields
- Check exact tool name with `toolbox list`
- Try broader terms ("git" instead of "git-delta")

**Interactive categories not working**:

- Install gum: `brew install gum`
- Check it's in PATH: `which gum`

## See Also

- [Tool Reference](tools.md) - Quick overview of available tools
- [Task Reference](tasks.md) - Installation automation
- [Symlinks](symlinks.md) - How tools command gets deployed
