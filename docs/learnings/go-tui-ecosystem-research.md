# Go TUI Ecosystem Research for Menu System Rewrite

## Executive Summary

Research into building terminal user interfaces (TUI) with Go for rewriting the dotfiles menu system (currently bash + gum). **Bubbletea** is the clear winner for modern Go TUI development, offering a functional Elm Architecture approach with excellent tooling ecosystem.

## Current Menu System

The existing menu system is bash-based with the following characteristics:

**Implementation:**

- Single bash script (`/Users/chris/dotfiles/common/.local/bin/menu`) with 420 lines
- Uses `gum` for all interactive UI elements (choose, pager, style)
- Simple YAML parsing with grep/sed/awk
- Direct tmux/git/task integration

**Features:**

- Function-based organization (commands, workflows, learning topics)
- YAML registries for knowledge management
- Session management with `sess` command
- Context-aware (detects git repos, Taskfile presence)
- Single-key navigation

**Pain Points:**

- YAML parsing is brittle (regex-based extraction)
- Limited UI flexibility
- Hard to test
- No type safety
- Difficult to extend

## Library Comparison

### 1. Bubbletea (RECOMMENDED)

**Overview:**

- Based on The Elm Architecture (Model-View-Update pattern)
- Functional, stateful approach
- 27.7k GitHub stars
- Over 10,000 applications built with it
- Production-ready (used by AWS, NVIDIA, Truffle Security)

**Architecture:**

```go
type model struct {
    // State
}

func (m model) Init() tea.Cmd {
    // Initial command
}

func (m model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
    // Handle events, update state
}

func (m model) View() string {
    // Render UI
}
```

**Pros:**

- Clean, functional architecture
- Excellent component library (Bubbles)
- Beautiful styling (Lipgloss)
- Active development (2025 updates)
- Extensive documentation and examples
- Great for complex, interactive TUIs
- Built-in support for external command execution

**Cons:**

- Steeper learning curve than widget-based libraries
- Requires understanding of Elm Architecture
- More boilerplate than simple CLI tools

**When to Use:**

- Complex TUI applications
- Multi-view interfaces
- State-heavy applications
- When you want clean, maintainable code

### 2. tview

**Overview:**

- Traditional widget-based approach
- Built on tcell
- Similar to GUI frameworks

**Pros:**

- Easy for developers familiar with GUI frameworks
- Rich set of pre-built components
- Simpler API for basic UIs
- Less boilerplate

**Cons:**

- Less flexible than Bubbletea
- More object-oriented (less functional)
- Harder to manage complex state

**When to Use:**

- Simple widget-based UIs
- Quick prototypes
- When coming from GUI development

### 3. tcell

**Overview:**

- Lower-level terminal library
- Foundation for tview

**Pros:**

- Fine-grained control
- Wider platform support
- Direct terminal manipulation

**Cons:**

- Steeper learning curve
- More code required
- No high-level components

**When to Use:**

- Need low-level control
- Custom terminal behavior
- Building your own framework

### 4. Reactea

**Overview:**

- React-like component hierarchy
- Built on top of Bubbletea
- Two-way communication

**Pros:**

- Familiar for React developers
- Component-based architecture
- Lifecycle methods (6 vs 3 in Bubbletea)

**Cons:**

- Performance not main goal
- Smaller community
- Less documentation

**When to Use:**

- You know React well
- Need component hierarchy

## Bubbletea Deep Dive

### Core Concepts

**The Elm Architecture:**

1. **Model** - Application state
2. **Update** - Handle messages, update state
3. **View** - Render UI based on state
4. **Commands** - Side effects (async operations)

**Message Flow:**

```text
User Input → Msg → Update(model, msg) → (new model, Cmd)
                                             ↓
                                      View(model) → String
```

### Bubbles Component Library

Pre-built components for common UI patterns:

**List Component:**

```go
import "github.com/charmbracelet/bubbles/list"

type item struct {
    title, desc string
}

func (i item) Title() string       { return i.title }
func (i item) Description() string { return i.desc }
func (i item) FilterValue() string { return i.title }

// Create list
items := []list.Item{
    item{title: "Commands", desc: "Shell commands"},
    item{title: "Workflows", desc: "Multi-step processes"},
}

l := list.New(items, list.NewDefaultDelegate(), 80, 20)
l.Title = "Menu"
```

**Key Methods:**

- `SelectedItem()` - Get current selection
- `SetItems()` - Replace items
- `InsertItem()` / `RemoveItem()` - Modify list
- `SetFilteringEnabled()` - Enable fuzzy filtering
- `CursorUp()` / `CursorDown()` - Navigation

**Other Components:**

- `textinput` - Single-line input
- `textarea` - Multi-line editor
- `viewport` - Scrollable content
- `spinner` - Loading indicators
- `progress` - Progress bars
- `table` - Tabular data

### Lipgloss Styling

Declarative styling similar to CSS:

```go
import "github.com/charmbracelet/lipgloss"

var (
    titleStyle = lipgloss.NewStyle().
        Bold(true).
        Foreground(lipgloss.Color("212")).
        Padding(1, 2).
        Border(lipgloss.RoundedBorder())

    selectedStyle = lipgloss.NewStyle().
        Foreground(lipgloss.Color("170")).
        Bold(true)
)

// Use styles
titleStyle.Render("Menu System")
selectedStyle.Render("> Commands")
```

**Features:**

- Adaptive colors (light/dark themes)
- Automatic color degradation
- ANSI 16, ANSI 256, True Color support
- Borders, padding, alignment
- Layout helpers (`lipgloss.Height()`, `lipgloss.Width()`)

### External Command Execution

Two approaches:

**1. tea.Cmd for non-interactive I/O:**

```go
func runCommand() tea.Msg {
    cmd := exec.Command("git", "status")
    output, err := cmd.Output()
    return commandFinishedMsg{output, err}
}

// In Update
case tea.KeyEnter:
    return m, runCommand
```

**2. tea.ExecProcess for interactive commands:**

```go
type editorFinishedMsg struct{ err error }

func openEditor() tea.Cmd {
    editor := os.Getenv("EDITOR")
    c := exec.Command(editor, "file.txt")
    return tea.ExecProcess(c, func(err error) tea.Msg {
        return editorFinishedMsg{err}
    })
}

// In Update
case tea.KeyEnter:
    return m, openEditor()
```

**Use Cases:**

- `tea.Cmd` - git commands, task execution, file operations
- `tea.ExecProcess` - vim, tmux, interactive CLIs

### Best Practices

**Performance:**

- Keep `Update()` and `View()` fast
- Offload expensive operations to `tea.Cmd` functions
- Use goroutines for async work, send results as messages

**State Management:**

- Hierarchical model structure for complex apps
- Parent models route messages to child components
- Root model acts as compositor

**Message Ordering:**

- User input is sequential
- Concurrent commands produce unordered messages
- Use `tea.Sequence()` for guaranteed ordering

**Debugging:**

- Use `spew` library to dump messages to file
- Set `DEBUG=true` environment variable
- Use `teatest` library for end-to-end tests

**Layout:**

- Use `lipgloss.Height()` and `lipgloss.Width()` instead of hardcoded values
- Calculate remaining space dynamically
- Handle window resize with `tea.WindowSizeMsg`

**Development Workflow:**

- Use file watchers for live reload
- Run `reset` command if panic leaves terminal in raw mode
- Use VHS for recording demos

## Integration Patterns

### Cobra + Bubbletea

Perfect for CLI apps with subcommands:

```go
// Cobra command
var rootCmd = &cobra.Command{
    Use:   "menu",
    Short: "Universal menu system",
    RunE: func(cmd *cobra.Command, args []string) error {
        p := tea.NewProgram(newModel())
        if _, err := p.Run(); err != nil {
            return err
        }
        return nil
    },
}

// Subcommands
var sessCmd = &cobra.Command{
    Use:   "sess",
    Short: "Session management",
    RunE: func(cmd *cobra.Command, args []string) error {
        p := tea.NewProgram(newSessionModel())
        return p.Start()
    },
}
```

### Viper + YAML Configuration

Type-safe configuration loading:

```go
import "github.com/spf13/viper"

type Config struct {
    Menu struct {
        Height         int    `mapstructure:"height"`
        PreviewEnabled bool   `mapstructure:"preview_enabled"`
    } `mapstructure:"menu"`

    Registry struct {
        Commands  string `mapstructure:"commands"`
        Workflows string `mapstructure:"workflows"`
    } `mapstructure:"registry"`
}

func loadConfig() (*Config, error) {
    viper.SetConfigName("config")
    viper.SetConfigType("yaml")
    viper.AddConfigPath("$HOME/.config/menu")

    if err := viper.ReadInConfig(); err != nil {
        return nil, err
    }

    var config Config
    if err := viper.Unmarshal(&config); err != nil {
        return nil, err
    }

    return &config, nil
}
```

**Important:** Use `mapstructure` tags, not `yaml` tags!

### Tmux Integration

Bubbletea works seamlessly in tmux:

```go
// Detect tmux
func isInTmux() bool {
    return os.Getenv("TMUX") != ""
}

// Switch tmux session
func switchSession(name string) tea.Cmd {
    return func() tea.Msg {
        var cmd *exec.Cmd
        if isInTmux() {
            cmd = exec.Command("tmux", "switch-client", "-t", name)
        } else {
            cmd = exec.Command("tmux", "attach-session", "-t", name)
        }

        return tea.ExecProcess(cmd, func(err error) tea.Msg {
            return sessionSwitchedMsg{err}
        })
    }
}
```

## Project Structure Patterns

### Recommended Structure

```text
menu/
├── cmd/
│   ├── root.go           # Main command
│   ├── sess.go           # Session subcommand
│   └── list.go           # List subcommand
├── internal/
│   ├── config/
│   │   ├── config.go     # Configuration types
│   │   └── loader.go     # YAML loading
│   ├── registry/
│   │   ├── registry.go   # Registry interface
│   │   ├── commands.go   # Commands registry
│   │   └── workflows.go  # Workflows registry
│   ├── tui/
│   │   ├── main.go       # Main menu model
│   │   ├── commands.go   # Commands view
│   │   ├── sessions.go   # Sessions view
│   │   └── styles.go     # Lipgloss styles
│   └── tmux/
│       ├── tmux.go       # Tmux operations
│       └── sessions.go   # Session management
├── main.go
└── go.mod
```

### State Machine Pattern

For complex multi-view apps:

```go
type sessionState int

const (
    stateMenu sessionState = iota
    stateCommands
    stateSessions
    stateDetails
)

type model struct {
    state   sessionState
    menu    menuModel
    commands commandsModel
    sessions sessionsModel
    // ...
}

func (m model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
    switch m.state {
    case stateMenu:
        return m.updateMenu(msg)
    case stateCommands:
        return m.updateCommands(msg)
    // ...
    }
}
```

## Real-World Examples

**Production Applications Using Bubbletea:**

- **chezmoi** - Dotfiles manager
- **trufflehog** (Truffle Security) - Leaked credentials finder
- **container-canary** (NVIDIA) - Container validator
- **eks-node-viewer** (AWS) - EKS cluster visualizer
- **gum** (Charm) - Shell script UI components
- **soft-serve** (Charm) - Git server with TUI
- **vhs** (Charm) - Terminal GIF recorder

**Source Code References:**

- Bubbletea examples: `github.com/charmbracelet/bubbletea/examples`
- Gum source: `github.com/charmbracelet/gum` (modular command structure)
- List examples: `bubbletea/examples/list-simple`, `list-default`, `list-fancy`
- Exec example: `bubbletea/examples/exec/main.go`

## Comparison to Current System

### Advantages of Go + Bubbletea

**Type Safety:**

- Compile-time checks vs runtime errors
- No more "variable not found" surprises
- IDE autocomplete and refactoring

**Testing:**

- Unit tests for models and update logic
- `teatest` library for E2E tests
- Mock external commands

**Maintainability:**

- Clear separation of concerns
- Modular architecture
- Easy to extend

**Performance:**

- Faster startup (compiled binary)
- Efficient YAML parsing (gopkg.in/yaml.v3)
- Better memory management

**Flexibility:**

- Rich UI components
- Complex state management
- Multi-view navigation
- Custom styling

### Trade-offs

**Complexity:**

- More code initially (model, update, view)
- Learning curve for Elm Architecture
- Need to understand Go

**Dependencies:**

- Go toolchain required
- Compilation step
- Binary distribution

**Development:**

- Longer iteration cycle (compile + run)
- Need to learn Go if unfamiliar

### Migration Strategy

**Phase 1 - Core Rewrite:**

- Menu system with single-key navigation
- Commands/workflows/learning registries
- Basic YAML parsing
- Gum-like styling with Lipgloss

**Phase 2 - Enhanced Features:**

- Fuzzy search across registries
- Multi-select operations
- Enhanced previews with syntax highlighting
- Recent items tracking

**Phase 3 - Advanced Integration:**

- Real-time task output streaming
- Git integration (like forgit)
- Notebook-style learning notes
- Bookmark management

**Phase 4 - Polish:**

- Themes (matching theme system)
- Configuration UI
- Plugin system
- Statistics and analytics

## Recommendations

### For Menu System Rewrite

**Stack:**

- **Bubbletea** - TUI framework
- **Bubbles** - List component for menus
- **Lipgloss** - Styling (adaptive colors)
- **Cobra** - CLI framework with subcommands
- **Viper** - YAML configuration
- **gopkg.in/yaml.v3** - YAML parsing

**Architecture:**

- Single binary with subcommands (`menu`, `sess`)
- Hierarchical model (parent routes to child views)
- YAML registries loaded on demand
- External commands via `tea.ExecProcess`

**Starting Point:**

1. Study `gum` source code (similar use case)
2. Use `bubbletea/examples/list-default` as template
3. Implement single-key navigation like current menu
4. Port YAML registries with proper types
5. Integrate tmux/git/task commands

### Learning Resources

**Official Documentation:**

- Bubbletea README: github.com/charmbracelet/bubbletea
- Bubbles docs: pkg.go.dev/github.com/charmbracelet/bubbles
- Lipgloss docs: pkg.go.dev/github.com/charmbracelet/lipgloss
- Tutorials: bubbletea/tutorials/basics

**Community Resources:**

- "Tips for building Bubble Tea programs": leg100.github.io/en/posts/building-bubbletea-programs
- "Charming Cobras with Bubbletea": elewis.dev/charming-cobras-with-bubbletea-part-1
- "Processing user input with menu component": dev.to/andyhaskell/processing-user-input-in-bubble-tea-with-a-menu-component-222i

**Code Examples:**

- Gum commands: github.com/charmbracelet/gum (choose, filter, input, etc.)
- List selection: bubbletea/examples/list-simple/main.go
- External commands: bubbletea/examples/exec/main.go

## Next Steps

1. **Prototype Phase** (1-2 days)
   - Set up Go project structure
   - Implement basic list menu with Bubbles
   - Test YAML parsing with Viper
   - Verify tmux integration works

2. **Core Implementation** (1-2 weeks)
   - Port menu categories and navigation
   - Implement command/workflow/learning views
   - Add session management (sess command)
   - Style with Lipgloss

3. **Feature Parity** (1 week)
   - Context detection (git, taskfile)
   - Task integration
   - External command execution
   - Preview panes

4. **Polish & Testing** (1 week)
   - Add tests
   - Handle edge cases
   - Documentation
   - Migration guide

**Total Estimated Time:** 3-4 weeks for full rewrite

## Conclusion

**Bubbletea is the right choice** for rewriting the menu system in Go. It offers:

- Modern, maintainable architecture
- Excellent ecosystem (Bubbles, Lipgloss)
- Production-ready with large community
- Clean integration with Cobra and Viper
- Type safety and testability

The learning curve is worth it for a system that will be easier to maintain and extend. Start with gum's source code and the official list examples as templates.
