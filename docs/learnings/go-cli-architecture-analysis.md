# Go CLI/TUI Architecture Analysis

**Analysis Date:** 2025-11-06
**Purpose:** Extract patterns and best practices from real-world Go CLI/TUI tools for building our session manager

## Tools Analyzed

1. **sesh** (joshmedeski/sesh) - tmux session manager
2. **lazygit** (jesseduffield/lazygit) - large-scale TUI for git
3. **gum** (charmbracelet/gum) - CLI tool collection using Bubbletea

## Executive Summary

### Key Findings

**Architecture Patterns:**

- Interface-based dependency injection for testability
- Wrapper packages for stdlib (exec, os, path) to enable mocking
- Flat package structure with domain-based organization
- Configuration via TOML with strict mode validation
- Heavy use of Cobra (sesh/lazygit) or Kong (gum) for CLI parsing

**Testing Approach:**

- Mockery for generating mocks from interfaces
- Table-driven tests with testify/assert
- Integration tests separate from unit tests
- Test files colocated with implementation

**Build/Release:**

- GoReleaser for multi-platform builds
- GitHub Actions for CI/CD
- Homebrew tap auto-publishing
- Version injection via ldflags

## 1. sesh - tmux Session Manager

**Repository:** github.com/joshmedeski/sesh/v2
**Stars:** ~2.5k
**Go Version:** 1.24+

### Architecture Overview

```
sesh/
├── main.go                     # Minimal entry point, logging setup
├── seshcli/                    # CLI commands (cobra)
├── model/                      # Data structures (Config, Session, etc)
├── lister/                     # Session listing logic
├── connector/                  # Session connection strategies
├── tmux/                       # Tmux wrapper
├── tmuxinator/                 # Tmuxinator integration
├── zoxide/                     # Zoxide integration
├── namer/                      # Session naming logic
├── previewer/                  # Session preview logic
├── shell/                      # Shell command execution
├── execwrap/                   # os/exec wrapper for testing
├── oswrap/                     # os wrapper for testing
├── pathwrap/                   # path wrapper for testing
├── home/                       # Home directory handling
├── configurator/               # TOML config loading
└── git/                        # Git repository detection
```

### Key Design Patterns

#### 1. Interface-Based Architecture

Every package defines an interface and a "Real" implementation:

```go
// tmux/tmux.go
type Tmux interface {
    ListSessions() ([]*model.TmuxSession, error)
    NewSession(sessionName string, startDir string) (string, error)
    AttachSession(targetSession string) (string, error)
    // ... more methods
}

type RealTmux struct {
    os    oswrap.Os
    shell shell.Shell
}

func NewTmux(os oswrap.Os, shell shell.Shell) Tmux {
    return &RealTmux{os, shell}
}
```

**Why:** Enables easy mocking for tests without mockery complexity

#### 2. Wrapper Packages for Testability

```go
// execwrap/execwrap.go
type Exec interface {
    LookPath(executable string) (string, error)
    Command(name string, args ...string) ExecCmd
}

type OsExec struct{}

func (e *OsExec) LookPath(executable string) (string, error) {
    return exec.LookPath(executable)
}
```

**Why:** Wraps stdlib packages to make them mockable

#### 3. Manual Dependency Injection

```go
// seshcli/root_command.go
func NewRootCommand(version string) *cobra.Command {
    // wrapper dependencies
    exec := execwrap.NewExec()
    os := oswrap.NewOs()
    path := pathwrap.NewPath()

    // base dependencies
    home := home.NewHome(os)
    shell := shell.NewShell(exec, home)

    // resource dependencies
    tmux := tmux.NewTmux(os, shell)
    zoxide := zoxide.NewZoxide(shell)

    // core dependencies
    lister := lister.NewLister(config, home, tmux, zoxide, tmuxinator)
    connector := connector.NewConnector(config, dir, home, lister, namer, ...)

    // commands
    rootCmd.AddCommand(
        NewListCommand(icon, json, lister),
        NewConnectCommand(connector, icon, dir),
        // ...
    )
}
```

**Pros:**

- Explicit dependency graph
- No magic/reflection
- Easy to trace

**Cons:**

- Verbose for large apps
- Easy to create circular dependencies

#### 4. Configuration Management

```go
// model/config.go
type Config struct {
    StrictMode           bool                 `toml:"strict_mode"`
    ImportPaths          []string             `toml:"import"`
    DefaultSessionConfig DefaultSessionConfig `toml:"default_session"`
    SessionConfigs       []SessionConfig      `toml:"session"`
    // ...
}

// configurator/configurator.go
func (c *RealConfigurator) GetConfig() (model.Config, error) {
    // Read from ~/.config/sesh/sesh.toml
    // Support imports for splitting configs
    // Validate with strict mode
}
```

**Features:**

- TOML format (human-friendly)
- Import paths for modular configs
- Strict mode with helpful error messages
- Custom error type for user-facing messages

#### 5. Strategy Pattern for Connections

```go
// connector/connect.go
func (c *RealConnector) Connect(name string, opts model.ConnectOpts) (string, error) {
    strategies := []func(*RealConnector, string) (model.Connection, error){
        tmuxStrategy,
        tmuxinatorStrategy,
        configStrategy,
        dirStrategy,
        zoxideStrategy,
    }

    for _, strategy := range strategies {
        if connection, err := strategy(c, name); err != nil {
            return "", err
        } else if connection.Found {
            return connectStrategy[connection.Session.Src](c, connection, opts)
        }
    }

    return "", fmt.Errorf("no connection found for '%s'", name)
}
```

**Why:** Clean separation of connection sources

### Testing Patterns

#### Table-Driven Tests

```go
// lister/list_test.go
func TestHideDuplicates(t *testing.T) {
    tests := []struct {
        name              string
        tmuxSessions      []*model.TmuxSession
        zoxideResults     []*model.ZoxideResult
        expectedNames     []string
    }{
        {
            name: "no duplicates",
            tmuxSessions: []*model.TmuxSession{
                {Name: "session1", Path: "/path/to/session1"},
            },
            expectedNames: []string{"session1", "session2"},
        },
        // ... more test cases
    }

    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            // Setup mocks
            mockTmux := new(tmux.MockTmux)
            mockTmux.On("ListSessions").Return(tt.tmuxSessions, nil)

            // Run test
            result, err := lister.List(opts)

            // Assertions
            assert.NoError(t, err)
            assert.Equal(t, tt.expectedNames, actualNames)
            mockTmux.AssertExpectations(t)
        })
    }
}
```

#### Mock Generation

Uses **mockery** v3 to auto-generate mocks:

```yaml
# .mockery.yaml
with-expecter: true
all: true
dir: "{{.InterfaceDir}}"
filename: "mock_{{.InterfaceName}}.go"
mockname: "Mock{{.InterfaceName}}"
outpkg: "{{.PackageName}}"
```

Run with: `mockery` (generates `mock_*.go` files)

### Build & Release

#### GoReleaser Configuration

```yaml
# .goreleaser.yaml
builds:
  - env:
      - CGO_ENABLED=0
    goos: [linux, windows, darwin]
    ldflags:
      - -X main.version={{.Version}}

brews:
  - name: sesh
    homepage: "https://github.com/joshmedeski/sesh"
    repository:
      owner: joshmedeski
      name: homebrew-sesh
    dependencies:
      - tmux
      - zoxide
```

#### GitHub Actions Workflow

```yaml
jobs:
  tests:
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest]
    steps:
      - uses: actions/setup-go@v5
      - run: mockery
      - run: go test -cover -bench=. -benchmem -race ./...

  goreleaser:
    needs: tests
    if: contains(github.ref, 'refs/tags/')
    steps:
      - uses: goreleaser/goreleaser-action@v5
```

### Logging Strategy

```go
// main.go
func init() {
    // Create log file in $TMPDIR/.seshtmp/YYYY-MM-DD.log
    // Use JSON handler with configurable level
    // MultiWriter to stdout + file based on ENV var

    env := os.Getenv("ENV")
    switch strings.ToLower(env) {
    case "debug":
        handlerOptions.Level = slog.LevelDebug
    case "info":
        handlerOptions.Level = slog.LevelInfo
    default:
        handlerOptions.Level = slog.LevelWarn
        fileOnly = true  // Don't spam stdout in production
    }
}
```

**Features:**

- JSON structured logging
- Daily log rotation
- Environment-based levels
- Fallback to home dir if /tmp denied

## 2. lazygit - Large-Scale TUI

**Repository:** github.com/jesseduffield/lazygit
**Stars:** ~50k
**Go Version:** 1.22+

### Architecture Overview

```
pkg/
├── app/                    # Application bootstrap
├── gui/                    # TUI layer (gocui)
│   ├── controllers/        # Input handlers
│   ├── context/            # View contexts
│   ├── presentation/       # Rendering logic
│   ├── services/           # Business logic
│   └── types/              # GUI types
├── commands/               # Git command wrappers
│   ├── git_commands/       # Individual git operations
│   ├── oscommands/         # OS command execution
│   └── models/             # Domain models
├── config/                 # Configuration management
├── i18n/                   # Internationalization
├── integration/            # Integration tests
└── utils/                  # Shared utilities
```

### Key Patterns

#### 1. Layered Architecture

```
GUI Layer (views, controllers)
    ↓
Services Layer (business logic)
    ↓
Commands Layer (git wrappers)
    ↓
OS Commands Layer (execution)
```

**Why:** Clear separation of concerns for large codebase

#### 2. Context Pattern

```go
// gui/context/list_context.go
type ListContext struct {
    *BasicContext
    GetItemsLength      func() int
    GetSelectedLineIdx  func() int
    OnClickSelectedItem func() error
    // ... more hooks
}
```

**Why:** Each view has its own state/behavior bundle

#### 3. Controller Pattern

```go
// gui/controllers/files_controller.go
type FilesController struct {
    *baseController
    c *ControllerCommon
}

func (c *FilesController) GetKeybindings(opts types.KeybindingsOpts) []*types.Binding {
    return []*types.Binding{
        {Key: 'a', Handler: c.add},
        {Key: 'd', Handler: c.remove},
        // ...
    }
}
```

**Why:** Separation of keybinding logic from view rendering

#### 4. Common Dependencies Struct

```go
// pkg/common/common.go
type Common struct {
    Log      *logrus.Entry
    Tr       *i18n.TranslationSet
    AppState *config.AppState
    Fs       afero.Fs
    Debug    bool
}
```

**Why:** Avoid passing same deps everywhere

### Testing Strategy

- **Unit tests:** Colocated with implementation
- **Integration tests:** `pkg/integration/tests/`
- **Test helpers:** Reusable components in `pkg/integration/components/`
- **No heavy mocking:** Prefer integration tests over mocking git

## 3. gum - Modular CLI Tools

**Repository:** github.com/charmbracelet/gum
**Stars:** ~18k
**Go Version:** 1.24+

### Architecture Overview

```
gum/
├── main.go              # Kong CLI parser
├── choose/              # Choose command
│   ├── command.go       # Kong command struct
│   ├── choose.go        # Bubbletea model
│   └── options.go       # CLI options
├── confirm/             # Confirm command
├── filter/              # Filter command
├── input/               # Input command
└── internal/            # Shared utilities
    ├── stdin/           # Stdin handling
    ├── timeout/         # Timeout context
    └── tty/             # TTY detection
```

### Key Patterns

#### 1. Kong for CLI Parsing

```go
// gum.go
type Gum struct {
    Choose  choose.Command  `cmd:"" help:"Choose an item from a list"`
    Filter  filter.Command  `cmd:"" help:"Filter items"`
    Input   input.Command   `cmd:"" help:"Prompt for input"`
    // ... more commands
}

// main.go
gum := &Gum{}
ctx := kong.Parse(gum,
    kong.Description("A tool for glamorous shell scripts."),
    kong.UsageOnError(),
)
ctx.Run()
```

**Pros:**

- Declarative CLI definition
- Auto-generated help
- Subcommands as struct fields

**Cons:**

- Less flexible than Cobra
- Struct tags can get messy

#### 2. Command Pattern

```go
// choose/command.go
type Command struct {
    Options
}

type Options struct {
    Height    int      `help:"Height of list" default:"10"`
    Ordered   bool     `help:"Sort options" default:"false"`
    Limit     int      `help:"Max items" default:"1"`
    // ... more options
}

func (o Options) Run() error {
    // Build Bubbletea model
    m := model{ /* ... */ }

    // Run TUI
    tm, err := tea.NewProgram(m, tea.WithOutput(os.Stderr)).Run()

    // Handle output
    return nil
}
```

**Why:** Each command is self-contained

#### 3. Bubbletea Pattern

```go
// choose/choose.go
type model struct {
    index  int
    items  []item
    cursor string
    // ... state
}

func (m model) Init() tea.Cmd { return nil }

func (m model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
    switch msg := msg.(type) {
    case tea.KeyMsg:
        switch msg.String() {
        case "up", "k":
            m.index--
        case "enter":
            m.submitted = true
            return m, tea.Quit
        }
    }
    return m, nil
}

func (m model) View() string {
    // Render view
}
```

**The Elm Architecture:**

- Model: State
- Update: Handle events → return new state
- View: Render current state

#### 4. Internal Utilities

```go
// internal/stdin/stdin.go
func Read(stripANSI bool) (string, error) {
    // Read from stdin if available
    // Return empty string if TTY
}

// internal/timeout/timeout.go
func Context(timeout time.Duration) (context.Context, context.CancelFunc) {
    if timeout == 0 {
        return context.Background(), func() {}
    }
    return context.WithTimeout(context.Background(), timeout)
}
```

**Why:** Shared utilities without circular deps

## Comparison Matrix

| Feature | sesh | lazygit | gum |
|---------|------|---------|-----|
| **CLI Framework** | Cobra | Cobra | Kong |
| **TUI Framework** | - | gocui | Bubbletea |
| **Dependency Injection** | Manual | Manual | Minimal |
| **Testing** | Mockery + testify | Integration-heavy | Minimal |
| **Config Format** | TOML | YAML | None |
| **Logging** | slog (JSON) | logrus | - |
| **Build** | GoReleaser | GoReleaser | GoReleaser |
| **Package Structure** | Flat domains | Layered | Feature folders |

## Recommendations for Our Session Manager

### 1. Architecture

**Adopt sesh's flat domain structure:**

```
menu/
├── cmd/                    # Cobra commands
├── model/                  # Data structures
├── config/                 # TOML config
├── tmux/                   # Tmux wrapper
├── menu/                   # Menu TUI (Bubbletea)
├── executor/               # Command execution
├── shell/                  # Shell wrapper
└── internal/               # Non-exported helpers
```

**Why:**

- Clear domain boundaries
- Easy to navigate
- Scales well to medium projects

### 2. Dependency Injection

**Use sesh's interface + wrapper pattern:**

```go
// tmux/tmux.go
type Tmux interface {
    ListSessions() ([]*model.Session, error)
    NewSession(name, path string) error
}

type RealTmux struct {
    shell shell.Shell
}

func NewTmux(shell shell.Shell) Tmux {
    return &RealTmux{shell}
}

// shell/shell.go (wrapper for exec)
type Shell interface {
    Cmd(cmd string, args ...string) (string, error)
}

// In root command
func NewRootCommand() *cobra.Command {
    exec := execwrap.NewExec()
    shell := shell.NewShell(exec)
    tmux := tmux.NewTmux(shell)
    // ...
}
```

**Why:**

- Testable without complex mocking
- Explicit dependencies
- No magic

### 3. Testing Strategy

**Adopt sesh's approach:**

1. **Use mockery for generating mocks**

   ```bash
   # .mockery.yaml
   with-expecter: true
   all: true
   ```

2. **Table-driven tests**

   ```go
   func TestMenuFilter(t *testing.T) {
       tests := []struct {
           name     string
           input    string
           items    []Item
           expected []Item
       }{
           // test cases
       }
       for _, tt := range tests {
           t.Run(tt.name, func(t *testing.T) {
               // test
           })
       }
   }
   ```

3. **Integration tests separate**

   ```
   menu_test/
   ├── integration/
   │   ├── tmux_test.go
   │   └── menu_test.go
   └── testdata/
   ```

### 4. Configuration

**Use TOML with sesh's pattern:**

```toml
# ~/.config/menu/menu.toml
[general]
theme = "rose-pine"
default_shell = "zsh"

[[categories]]
name = "Sessions"
type = "tmux-sessions"

[[categories]]
name = "Projects"
type = "zoxide"
blacklist = ["node_modules", ".git"]

[[custom_commands]]
name = "Edit Config"
command = "nvim ~/.config/menu/menu.toml"
```

**Implementation:**

```go
// config/config.go
type Config struct {
    General      GeneralConfig    `toml:"general"`
    Categories   []CategoryConfig `toml:"categories"`
    CustomCmds   []CommandConfig  `toml:"custom_commands"`
}

// Use pelletier/go-toml/v2 (same as sesh)
```

### 5. Build & Release

**Adopt sesh's GoReleaser setup:**

```yaml
# .goreleaser.yaml
builds:
  - env: [CGO_ENABLED=0]
    goos: [linux, darwin]
    ldflags: [-X main.version={{.Version}}]

brews:
  - repository:
      owner: yourusername
      name: homebrew-menu
    dependencies:
      - tmux
      - fzf
```

### 6. TUI Framework

**Use Bubbletea (like gum) NOT gocui:**

**Why Bubbletea:**

- Modern, actively maintained
- The Elm Architecture is intuitive
- Great documentation
- Smaller, focused
- Works great with Lipgloss for styling

**Why NOT gocui:**

- Older, less active
- More complex API
- Harder to test

**Example:**

```go
// menu/menu.go
type Model struct {
    items    []Item
    selected int
    filter   string
}

func (m Model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
    switch msg := msg.(type) {
    case tea.KeyMsg:
        switch msg.String() {
        case "j", "down":
            m.selected++
        case "enter":
            return m, m.executeItem()
        }
    }
    return m, nil
}
```

### 7. Package Organization

```
menu/
├── main.go                      # Entry point, version injection
├── cmd/
│   ├── root.go                  # Root command + DI
│   ├── list.go                  # List categories
│   └── run.go                   # Run menu
├── model/
│   ├── config.go                # Configuration structs
│   ├── item.go                  # Menu item
│   └── category.go              # Category
├── config/
│   └── loader.go                # TOML config loading
├── tmux/
│   ├── tmux.go                  # Interface + impl
│   ├── tmux_test.go
│   └── mock_tmux.go             # Generated by mockery
├── menu/
│   ├── menu.go                  # Bubbletea model
│   ├── keys.go                  # Keybindings
│   └── styles.go                # Lipgloss styles
├── executor/
│   └── executor.go              # Execute selected items
├── shell/
│   ├── shell.go                 # Shell wrapper interface
│   └── mock_shell.go
└── internal/
    ├── fzf/                     # FZF integration
    └── theme/                   # Theme loading
```

## Anti-Patterns to Avoid

### 1. God Objects

**Bad:**

```go
// Everything in one App struct
type App struct {
    Config      Config
    Tmux        *Tmux
    DB          *Database
    Logger      *Logger
    // 30 more fields...
}
```

**Good:**

```go
// Focused structs with clear responsibilities
type MenuUI struct {
    items   []Item
    theme   Theme
}

type Executor struct {
    shell   shell.Shell
    tmux    tmux.Tmux
}
```

### 2. Circular Dependencies

**Bad:**

```
tmux/ imports menu/
menu/ imports tmux/  ← circular!
```

**Good:**

```
model/           # Shared types
  ├── item.go
  └── session.go

tmux/            # Imports model
  └── tmux.go

menu/            # Imports model and tmux
  └── menu.go
```

### 3. Over-mocking

**Bad:**

```go
// Mocking everything, even simple functions
mockStringTrimmer.On("Trim", " foo ").Return("foo")
```

**Good:**

```go
// Mock external dependencies (tmux, exec)
// Test pure functions directly
```

### 4. Magic Config Loading

**Bad:**

```go
// Config loaded from 10 different locations with complex merging
```

**Good:**

```go
// Single config file: ~/.config/menu/menu.toml
// Optional imports for splitting configs
```

## Key Learnings

1. **Interfaces everywhere for testability** - Even for stdlib wrappers
2. **Table-driven tests are the standard** - Readable, maintainable
3. **Mockery is the de-facto tool** - Auto-generate mocks, don't hand-write
4. **GoReleaser is standard** - Multi-platform builds, Homebrew publishing
5. **TOML > YAML for user configs** - More human-friendly
6. **Bubbletea for TUIs** - Modern, active, great DX
7. **Cobra for CLIs** - Unless you want declarative (Kong)
8. **Flat package structure** - For small/medium projects
9. **Manual DI is fine** - Wire/Dig add complexity
10. **Integration tests > heavy mocking** - Especially for git/tmux

## Files Worth Studying

**sesh:**

- `/tmp/sesh/seshcli/root_command.go` - DI setup
- `/tmp/sesh/connector/connect.go` - Strategy pattern
- `/tmp/sesh/lister/list_test.go` - Table-driven tests
- `/tmp/sesh/.goreleaser.yaml` - Release config

**lazygit:**

- `/tmp/lazygit/pkg/app/app.go` - Bootstrap
- `/tmp/lazygit/pkg/gui/gui.go` - Large TUI structure

**gum:**

- `/tmp/gum/choose/command.go` - Bubbletea integration
- `/tmp/gum/main.go` - Kong setup

## Next Steps

1. Set up basic project structure following sesh's pattern
2. Implement tmux wrapper with interface + tests
3. Create config loader using go-toml/v2
4. Build Bubbletea menu UI
5. Set up GoReleaser + GitHub Actions
6. Add mockery configuration
7. Write table-driven tests

## References

- sesh: <https://github.com/joshmedeski/sesh>
- lazygit: <https://github.com/jesseduffield/lazygit>
- gum: <https://github.com/charmbracelet/gum>
- Bubbletea: <https://github.com/charmbracelet/bubbletea>
- Cobra: <https://github.com/spf13/cobra>
- GoReleaser: <https://goreleaser.com>
- Mockery: <https://github.com/vektra/mockery>
