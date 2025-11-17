# Toolbox

Toolbox helps you discover and learn about the 98 tools installed in your dotfiles. When you forget what bat does or wonder which git tools are available, toolbox provides instant answers without leaving the terminal.

## Why Toolbox Exists

Modern development environments contain dozens of specialized tools. File viewers like bat and eza. Search tools like ripgrep and fzf. Git helpers like lazygit and delta. Language servers for every language. The list grows constantly.

The problem isn't installation - it's awareness. You install a tool, use it once, then forget it exists. Months later you manually solve a problem that tool would handle perfectly. You know the solution exists somewhere in your toolchain but can't remember which tool or how to use it.

Toolbox solves discovery, not tracking. It helps you remember what tools are available, shows usage examples when needed, and searches across your entire toolchain instantly. No usage statistics, no command wrapping, no PATH modifications. Just a fast reference when you need it.

## Quick Start

Run toolbox to see help, search for specific tools, or browse by category:

```bash
toolbox              # Show help
toolbox git          # Search for git tools (shortcut)
toolbox list         # List all tools by category
toolbox categories   # Interactive category browser (gum)
toolbox show bat     # Detailed info about bat
```

The search shortcut works for any query. Type `toolbox python` instead of `toolbox search python`. This makes quick lookups feel natural.

## Commands

### Show Help

Run toolbox without arguments to see available commands:

```bash
toolbox
toolbox --help
toolbox help
```

### List All Tools

See every tool organized by category, sorted alphabetically:

```bash
toolbox list
```

Output groups tools by category with one-line descriptions. Both categories and tools sort alphabetically for easy scanning. This gives you a complete view of your toolchain in seconds.

### Show Tool Details

Get comprehensive information about a specific tool:

```bash
toolbox show bat
toolbox show ripgrep
```

The detail view shows:

- Description and why to use it
- Installation method (brew, npm, uv)
- Usage syntax
- Examples with explanations
- Related tools
- Documentation URL
- Installation status

Use this when you remember a tool exists but forgot how to use it or what it's good for.

### Search Tools

Find tools by description, tags, name, or why_use field. Search is case-insensitive and searches all metadata:

```bash
toolbox search git
toolbox search syntax
toolbox search docker

# Shortcut: just type the query
toolbox git       # Same as: toolbox search git
toolbox python    # Same as: toolbox search python
```

Search returns matching tools with category and description. The shortcut syntax makes quick lookups feel effortless - just type what you're thinking about.

### Browse Categories

Launch interactive mode with gum's beautiful menus:

```bash
toolbox categories
```

Two-level interactive picker:

1. Select a category - Shows tool count and preview
2. Select a tool - Shows full tool details

This works best when you know the general area but not the specific tool. Looking for a file viewer? Browse the file-viewer category to see all options.

Requires gum to be installed (`brew install gum`).

## Registry Structure

Tools are defined in `~/.config/toolbox/registry.yml` using structured YAML metadata. Each tool entry follows this format:

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

Required fields are category, description, installed_via, and usage. Optional but recommended fields include why_use (helps remember when to use it), examples (concrete usage patterns), see_also (discover related tools), tags (improve searchability), and docs_url (quick reference).

### Categories

Tools organize into categories that reflect how you think about them:

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

These categories mirror workflows. Need to search files? Check the search category. Working with containers? Check the container category.

## Adding Tools

Edit `platforms/common/.config/toolbox/registry.yml` and add a new entry following the format above. The registry deploys via symlinks to `~/.config/toolbox/registry.yml`.

Required fields let toolbox display basic information. Optional fields make the tool easier to discover and use. Include why_use to explain when this tool beats alternatives. Add examples to show common use cases. Link related tools to help users discover your toolchain's capabilities.

After adding tools, run `toolbox list` to verify they appear correctly.

## Implementation

Toolbox is written in Go for speed, reliability, and testability. Why Go instead of bash?

Speed matters for interactive tools. Searching 98 tools happens in under 1ms. Type-safety catches bugs at compile time instead of at runtime. Go's built-in testing framework makes comprehensive test coverage natural. No bash string manipulation bugs. Cross-platform single binary with no dependencies.

### Architecture

The project follows Go best practices:

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

Commands use cobra for consistent CLI patterns. Registry loading validates YAML structure. Search logic handles case-insensitive matching across all fields. Display formatting uses color for readability. Interactive mode integrates gum for beautiful menus. Tests cover search logic with realistic data.

## Examples

Common workflows show how toolbox fits into your daily routine:

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

Toolbox integrates with other dotfiles systems following standard patterns.

### Installation

Build via Task and install to standard Go location:

```bash
cd apps/common/toolbox
task build    # Creates apps/common/toolbox/toolbox (gitignored)
task install  # Installs to ~/go/bin/toolbox (already in PATH)
```

The binary builds locally in the app directory but installs to `~/go/bin` where Go tools belong. This separates source code (version controlled) from build artifacts (gitignored) from installation location (standard Go path).

### Registry Location

The registry lives in `platforms/common/.config/toolbox/registry.yml` under version control. Symlinks deploy it to `~/.config/toolbox/registry.yml` where toolbox expects it. This lets you edit the registry in your dotfiles repo and have changes appear immediately.

Currently contains 98 tools across all categories.

### Build Pattern

Follows standard Go project structure, same as sess. Source code in dotfiles, build artifacts gitignored, installation outside the repo. No symlinks for binaries - binaries install to standard locations.

## Building from Source

Build and install toolbox from source:

```bash
cd apps/common/toolbox
task build    # Build binary locally (gitignored)
task install  # Install to ~/go/bin
```

See `apps/common/toolbox/README.md` for complete build instructions.

## Testing

Run tests with standard Go tools:

```bash
cd apps/common/toolbox
go test -v           # Run tests
go test -cover       # With coverage
```

Tests cover search functionality, filter logic, and registry loading.

## Troubleshooting

### Command Not Found

If toolbox isn't in your PATH:

- Run `cd apps/common/toolbox && task install` to rebuild and install
- Verify `~/go/bin` is in PATH
- Check binary exists: `which toolbox` or `ls -la ~/go/bin/toolbox`

### Tool Shows as "Shell function" but it's a binary

Shell functions from `functions.sh` won't be in PATH. This is correct - they're sourced by your shell, not in PATH. Toolbox shows installation method, not current status.

### Registry Not Found

If toolbox can't find the registry:

- Verify symlink: `ls -la ~/.config/toolbox/registry.yml`
- Should point to: `~/dotfiles/platforms/common/.config/toolbox/registry.yml`
- Run `task symlinks:link` if missing

### Search Returns No Results

Search is case-insensitive and searches all fields:

- Check exact tool name with `toolbox list`
- Try broader terms ("git" instead of "git-delta")
- Search works on description, tags, name, and why_use fields

### Interactive Categories Not Working

Interactive mode requires gum:

- Install gum: `brew install gum`
- Check it's in PATH: `which gum`

## Composition with Other Tools

Toolbox outputs clean data designed for piping and composition:

```bash
# Interactive selection with fzf
toolbox list | fzf --preview='toolbox show {1}'

# Filter by category
toolbox list | grep cli-utility

# Extract tool names
toolbox list | awk '{print $1}'

# Count tools by category
toolbox list | grep -c "^\[file-viewer\]"
```

This composability lets you build custom workflows. Pipe to fzf for interactive selection. Filter with grep for specific categories. Extract fields with awk for scripting.

## See Also

- [Menu System](menu.md) - Knowledge and workflow management
- [Session Management](session.md) - Tmux session manager
- [Tool Reference](/reference/tools.md) - Quick tool overview
- [Task Reference](/reference/tasks.md) - Installation automation
- [Symlinks](/reference/symlinks.md) - How tools deploy
