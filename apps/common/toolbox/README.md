# toolbox

Dotfiles tool discovery system written in Go.

## Features

- **Search**: Case-insensitive search across tool names, descriptions, tags, and usage
- **Browse**: Interactive category → tool browser using gum
- **Display**: Beautiful colored output with detailed tool information
- **Fast**: Instant search and filtering
- **Tested**: Comprehensive test coverage

## Usage

```bash
# Show help
toolbox

# Search for tools (shortcut)
toolbox git

# Explicit search
toolbox search git

# Show tool details
toolbox show ripgrep

# List all tools by category
toolbox list

# Interactive category browser (requires gum)
toolbox categories
```

## Commands

- `toolbox` - Show help
- `toolbox list` - List all tools grouped by category (alphabetically)
- `toolbox show <tool>` - Show detailed information about a tool
- `toolbox search <query>` - Search tools (case-insensitive)
- `toolbox categories` - Interactive category picker with gum
- `toolbox <query>` - Shortcut for search

## Building

```bash
go build -o toolbox
```

## Testing

```bash
go test -v
```

## Registry

Tools are defined in `~/.config/toolbox/registry.yml` (or `$DOTFILES_REGISTRY`)

## Dependencies

- [cobra](https://github.com/spf13/cobra) - CLI framework
- [yaml.v3](https://github.com/go-yaml/yaml) - YAML parser
- [gum](https://github.com/charmbracelet/gum) - Optional, for interactive menus

## Code Structure

- `main.go` - CLI entry point and commands
- `types.go` - Data structures
- `registry.go` - YAML loading
- `search.go` - Search and filter functions
- `display.go` - Output formatting
- `interactive.go` - Gum integration
- `search_test.go` - Tests

## Comments

This code includes extensive comments for learning Go, including:

- Comparisons with Python
- Explanations of Go idioms
- Gotchas and best practices
