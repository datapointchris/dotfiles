# Tool Composition Architecture

How the workflow tools in this dotfiles system work together, following the Unix philosophy.

## Core Philosophy

**Small, focused, composable tools.**

Each tool:

1. Does one thing well
2. Outputs clean, parseable data
3. Composes with external UI tools (fzf, gum)
4. Works in scripts and interactive use

**Separation of data and presentation**: Tools are data providers, not UI frameworks.

```text
Tool outputs data → External UI (fzf/gum) → Tool processes selection
```

Inspired by [sesh](https://github.com/joshmedeski/sesh) - integration happens at the shell level, not within the tool.

## The Tools

**sess** - Go application (installed via `go install`)

- Tmux session management
- Aggregates: tmux sessions, tmuxinator projects, default configs
- Commands: `sess`, `sess list`, `sess <name>`, `sess last`
- Development: `~/tools/sess/`

**toolbox** - Go application (installed via `go install`)

- CLI tool discovery and documentation
- Registry: `platforms/common/.config/toolbox/registry.yml`
- Commands: `list`, `show`, `search`, `random`, `installed`, `categories`
- Development: `~/tools/toolbox/`

**theme** - Bash tool (installed via git clone to `~/.local/share/`)

- Unified theme generation from theme.yml source files
- Applies themes across ghostty, tmux, btop, and Neovim
- Commands: `current`, `apply`, `list`, `preview`, `random`, `like`, `dislike`, `upgrade`
- Development: `~/tools/theme/`

**font** - Bash tool (installed via git clone to `~/.local/share/`)

- Font management and tracking
- Commands: `current`, `change`, `apply`, `like`, `dislike`, `rank`, `upgrade`
- Development: `~/tools/font/`

**notes** (`apps/common/notes`) - Bash wrapper

- Auto-discovers zk notebook sections
- Interactive gum menu for quick access
- Direct zk commands: `zk journal`, `zk devnote`, `zk learn`

**menu** (`apps/common/menu`) - Bash launcher

- Shows available tools and workflows
- Interactive gum menu with `menu launch`
- Documentation in executable form

## Composition Patterns

### Pattern 1: Interactive Selection with fzf

```bash
# Tools discovery
toolbox list | fzf --preview='toolbox show {1}'

# Theme picker
theme preview  # Built-in fzf preview

# Session switcher
sess list | fzf | xargs sess

# Note browser
zk list | fzf --preview='bat {-1}'
```

**Why this works**: Tools output clean data, fzf provides UI, xargs chains to action.

### Pattern 2: Filtering and Processing

```bash
# Find specific tools
toolbox list | grep cli-utility

# Get session names only
sess list | awk '{print $2}'

# Count matching notes
zk list --match "algorithm" | wc -l

# Check which tools are installed
toolbox installed | wc -l
```

**Why this works**: Structured output + standard Unix tools = powerful queries.

### Pattern 3: Scripting and Automation

```bash
# Auto-create session for current directory
sess $(basename "$PWD")

# Time-based theme switching
hour=$(date +%H)
if [ $hour -ge 6 ] && [ $hour -lt 18 ]; then
  theme apply rose-pine-dawn
else
  theme apply rose-pine
fi

# Create daily journal automatically
zk journal "$(date '+%Y-%m-%d')"
```

**Why this works**: Tools are scriptable, return predictable exit codes, output is parseable.

### Pattern 4: Interactive with gum

```bash
# Choose tool to explore
TOOL=$(toolbox list | awk '{print $1}' | gum choose)
toolbox show "$TOOL"

# Multi-step workflow
SESSION=$(sess list | gum choose --height=10)
sess "$SESSION"

# Input for note creation
TITLE=$(gum input --placeholder "Note title")
zk devnote "$TITLE"
```

**Why this works**: gum provides beautiful TUI, tools remain simple.

## Design Decisions

### Why not build fzf/gum INTO each tool?

**Anti-pattern**:

```bash
sess --fzf          # Now sess depends on fzf
toolbox --interactive  # Now toolbox needs gum
```

**Better**:

```bash
sess list | fzf     # sess is independent
toolbox list | gum choose  # toolbox doesn't know about gum
```

**Benefits**:

- Tools stay lightweight (no UI dependencies)
- Users choose their UI (fzf, gum, rofi, dmenu)
- Easier to test (pure functions, predictable output)
- Works in scripts without interactive flags

### Why bash scripts instead of one Go application?

**Pragmatism over purity**:

- **sess/toolbox** are Go because: Complex logic, concurrent operations, type safety for config parsing
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
sess
toolbox
theme
```

**Benefits**:

- Each tool has clear purpose and ownership
- Can be used independently or composed
- Easier to maintain (single responsibility)
- Natural command names (no subcommand memorization)

## Data Flow Example

**Interactive theme selection and application**:

```text
User runs:
  theme preview

Flow:
  1. theme preview
     → Scans themes/ directory
     → Launches fzf with theme list
     → User selects theme
     → Applies to ghostty, tmux, btop
     → Logs action to history
```

**Session creation**:

```text
User runs:
  sess dotfiles

Flow:
  1. sess checks if "dotfiles" session exists
     → tmux has-session -t dotfiles

  2. If exists: switch
     → tmux switch-client -t dotfiles

  3. If not: check for default config
     → Reads ~/.config/sess/sessions-macos.yml
     → Finds dotfiles entry with directory ~/dotfiles

  4. Create from config
     → tmux new-session -s dotfiles -c ~/dotfiles
     → tmux switch-client -t dotfiles
```

## Tool Relationships

```text
┌──────────┐
│   menu   │  Simple launcher, references all tools
└────┬─────┘
     │
     ├─────┐
     │     │
┌────▼─┐ ┌─▼────────┐ ┌────────────┐ ┌─────────┐
│ sess │ │ toolbox  │ │   theme    │ │ notes   │
└──────┘ └──────────┘ └────────────┘ └────┬────┘
   │         │              │               │
   │         │              │               │
┌──▼────┐ ┌─▼────────┐ ┌───▼──────┐ ┌─────▼───┐
│ tmux  │ │ registry │ │ themes/  │ │   zk    │
└───────┘ └──────────┘ └──────────┘ └─────────┘
```

**Independence**: Each tool works standalone. menu just provides discovery.

## Integration Points

### Shell Integration

**Bash/Shell scripts** are in `~/.local/bin/` (symlinked from `apps/common/` and `apps/{platform}/`):

```bash
# After task symlinks:link
ls ~/.local/bin/
# menu notes backup-dirs patterns printcolors
```

**Go binaries** are in `~/go/bin/` (installed via `go install`):

```bash
# Installed during dotfiles setup from GitHub
ls ~/go/bin/
# sess toolbox gum cheat lazydocker ...
```

**External bash tools** (theme, font) are cloned to `~/.local/share/` with binaries symlinked to `~/.local/bin/`.

All tools available in PATH (both `~/.local/bin/` and `~/go/bin/` are in PATH), callable from anywhere.

### Configuration Files

Tools read from XDG-compliant locations:

- `~/.config/sess/sessions-{platform}.yml` - Default sessions
- `~/.config/toolbox/registry.yml` - Tool definitions
- `~/.config/zk/config.toml` - Note configuration

Source files in `platforms/common/.config/` (symlinked to `~/.config/`).

### Data Sources

Each tool owns its data:

- **sess**: Aggregates tmux state + tmuxinator + config file
- **toolbox**: Reads YAML registry
- **theme**: Reads theme.yml files and generates app configs
- **notes**: Wraps zk (which manages `~/notes/`)

No shared database. No coupling.

## Best Practices

### For Tool Authors

**Output clean data**:

```bash
# Good: one item per line, easy to parse
toolbox list
# bat                       [file-viewer] ...
# eza                       [file-lister] ...

# Good: plain text for piping
theme list
# rose-pine
# gruvbox-dark-hard
```

**Provide structured and plain outputs**:

```bash
# Structured for humans
sess list
# ● dotfiles (4 windows)
# ○ learning (2 windows)

# But parseable for scripts
sess list | awk '{print $2}'  # Still works
```

**Return meaningful exit codes**:

```bash
if sess dotfiles; then
  echo "Switched successfully"
else
  echo "Session doesn't exist"
fi
```

### For Users

**Compose at the shell level**:

```bash
# Don't ask for tool flags like: sess --fuzzy
# Instead: compose with fzf
sess list | fzf
```

**Use aliases for common compositions**:

```bash
# In .zshrc
alias st='toolbox list | fzf --preview="toolbox show {1}"'
alias ts='theme preview'  # Built-in fzf picker
```

**Leverage tool output in scripts**:

```bash
#!/usr/bin/env bash
# Create session for each project
for project in ~/code/*; do
  sess "$(basename "$project")"
done
```

## Why This Architecture Works

**Simplicity**: Each tool is simple enough to understand in minutes.

**Testability**: Pure functions with predictable output are easy to test.

**Flexibility**: Compose tools in ways the author never imagined.

**Maintainability**: Tools are independent. Change one without breaking others.

**Portability**: Bash + standard Unix tools work everywhere.

**No Lock-in**: Don't like fzf? Use gum. Don't like either? Use grep and awk.

## Comparison with Alternatives

**vs. Integrated mega-tools** (like oh-my-zsh plugins):

- ✅ Simpler to understand and debug
- ✅ Can use tools independently
- ✅ No plugin manager needed
- ❌ Requires composing at shell level

**vs. GUI applications**:

- ✅ Faster (CLI startup time)
- ✅ Scriptable and automatable
- ✅ Works over SSH
- ❌ Steeper learning curve initially

**vs. Language-specific tools** (pure Go/Rust/Python):

- ✅ Easier to modify (bash is readable)
- ✅ Better shell integration
- ❌ Less type safety (use Go when needed like sess)

## Related Documentation

- [Toolbox](../apps/toolbox.md) - Tool discovery and composition
- [Menu](../apps/menu.md) - Simple launcher
- [Notes](../apps/notes.md) - zk workflow guide
