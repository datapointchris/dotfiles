# Go TUI Library Comparison - Quick Reference

## Decision Matrix

| Library | Stars | Best For | Complexity | Our Use Case Fit |
|---------|-------|----------|------------|------------------|
| **Bubbletea** | 27.7k | Complex TUIs | Medium-High | **Excellent** |
| tview | - | Simple widgets | Low-Medium | Good |
| tcell | - | Low-level control | High | Overkill |
| Reactea | - | React devs | Medium | Niche |

## Recommendation: Bubbletea

### Why Bubbletea?

1. **Production Ready** - Used by AWS, NVIDIA, Truffle Security
2. **Ecosystem** - Bubbles (components), Lipgloss (styling), Cobra integration
3. **Architecture** - Clean Elm Architecture pattern
4. **Community** - 10,000+ applications built with it
5. **Maintenance** - Active development (2025 updates)

### Perfect Match for Menu System

**Current bash system:**

```bash
# 420 lines of bash
# gum for all UI
# grep/sed/awk for YAML
# No type safety
```

**Bubbletea approach:**

```go
// Type-safe models
// Composable components
// Built-in YAML parsing
// Testable architecture
```

## Quick Code Comparison

### Current (Bash + Gum)

```bash
show_commands() {
  local commands=()
  while IFS= read -r line; do
    if [[ "$line" =~ ^[[:space:]]*-[[:space:]]*name:[[:space:]]*(.+)$ ]]; then
      local name="${BASH_REMATCH[1]}"
      local desc=$(grep -A 3 "name: $name" "$registry" | grep "description:")
      commands+=("$name → $desc")
    fi
  done < "$registry"

  choice=$(printf '%s\n' "${commands[@]}" | gum choose)
}
```

### With Bubbletea

```go
type commandModel struct {
    list     list.Model
    registry []Command
}

func (m commandModel) Init() tea.Cmd {
    return nil
}

func (m commandModel) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
    switch msg := msg.(type) {
    case tea.KeyMsg:
        switch msg.String() {
        case "enter":
            item := m.list.SelectedItem().(Command)
            return m, showDetails(item)
        }
    }

    var cmd tea.Cmd
    m.list, cmd = m.list.Update(msg)
    return m, cmd
}

func (m commandModel) View() string {
    return m.list.View()
}
```

## Integration Points

### Cobra CLI Structure

```
menu                    # Main menu UI
menu sess              # Session manager
menu list              # List items
menu search <query>    # Search all registries
```

### Viper Configuration

```go
type Config struct {
    Menu struct {
        Height int `mapstructure:"height"`
    }
    Registry struct {
        Commands string `mapstructure:"commands"`
    }
}

// Loads ~/.config/menu/config.yml
```

### Tmux Integration

```go
// Switch sessions with tea.ExecProcess
func switchSession(name string) tea.Cmd {
    cmd := exec.Command("tmux", "switch-client", "-t", name)
    return tea.ExecProcess(cmd, nil)
}
```

## Project Structure

```
menu/
├── cmd/
│   ├── root.go        # Main menu
│   └── sess.go        # Session subcommand
├── internal/
│   ├── config/        # Config loading
│   ├── registry/      # YAML registries
│   ├── tui/           # Bubbletea models
│   │   ├── main.go    # Main menu
│   │   ├── commands.go
│   │   ├── sessions.go
│   │   └── styles.go  # Lipgloss styles
│   └── tmux/          # Tmux operations
├── main.go
└── go.mod
```

## Benefits Over Current System

| Aspect | Bash | Go + Bubbletea |
|--------|------|----------------|
| Type Safety | None | Compile-time |
| Testing | Hard | teatest + unit tests |
| Performance | Good | Excellent (compiled) |
| Maintainability | Medium | High (modular) |
| Error Handling | Runtime | Compile + runtime |
| IDE Support | Basic | Full autocomplete |
| Refactoring | Risky | Safe |
| Extensibility | Limited | Easy |

## Learning Curve

**Time Investment:**

- Learn Elm Architecture: 2-4 hours
- Study Bubbletea examples: 4-8 hours
- Study gum source code: 2-4 hours
- Build prototype: 1-2 days

**Total:** ~1 week to proficiency

**Worth it because:**

- Easier to maintain long-term
- More features possible
- Better error handling
- Cleaner architecture

## Key Resources

**Must Read:**

1. Bubbletea README: github.com/charmbracelet/bubbletea
2. Tips for building programs: leg100.github.io
3. Gum source code: github.com/charmbracelet/gum

**Examples:**

- List menus: bubbletea/examples/list-simple
- External commands: bubbletea/examples/exec
- Cobra integration: elewis.dev/charming-cobras

## Next Steps

1. **Study Phase** (2-3 days)
   - Read Bubbletea docs
   - Study gum command implementations
   - Prototype list menu

2. **Core Rewrite** (1-2 weeks)
   - Implement main menu
   - Port registries
   - Add session management

3. **Polish** (1 week)
   - Tests
   - Documentation
   - Migration guide

**Total:** 3-4 weeks

## Alternative: Stick with Bash?

**Consider staying with bash if:**

- Don't want to learn Go
- Current system works well enough
- Limited time for rewrite

**But Go is better because:**

- You're already learning Go (symlinks tool)
- Menu system is core infrastructure
- Benefits compound over time
- More maintainable long-term

## Conclusion

Bubbletea is the right choice. The learning investment pays off with:

- Type safety
- Better testing
- Easier maintenance
- More possibilities for features
- Production-ready ecosystem

Start with gum source code as template and official list examples.

---

See [Go TUI Ecosystem Research](../learnings/go-tui-ecosystem-research.md) for comprehensive details.
