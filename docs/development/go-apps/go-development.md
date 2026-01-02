# Go Development Standards

Standards and best practices for Go development in the dotfiles project.

## Project Structure

Follow the [Standard Go Project Layout](https://github.com/golang-standards/project-layout):

```text
tools/sess/
├── cmd/                    # Main applications
│   ├── root.go            # Root command
│   ├── list.go            # Subcommands
│   └── create.go
├── internal/              # Private application code
│   ├── config/           # Configuration parsing
│   ├── session/          # Business logic
│   ├── tmux/             # External integrations
│   └── ui/               # User interface
├── pkg/                   # Public library code (if needed)
├── main.go               # Entry point
├── go.mod
├── go.sum
├── README.md
└── .gitignore
```

**Key Principles:**

- `internal/` prevents external imports (enforced by Go)
- `cmd/` contains CLI-specific code
- Business logic goes in `internal/`
- Only expose APIs in `pkg/` if reusable by other projects

## Dependencies

**Minimize dependencies:**

- Prefer standard library when possible
- Choose well-maintained, popular libraries
- Avoid bleeding-edge or experimental packages

**Approved Dependencies:**

Core:

- `gopkg.in/yaml.v3` - YAML parsing (robust, stable)
- `github.com/spf13/cobra` - CLI framework (industry standard)
- `github.com/charmbracelet/bubbletea` - TUI framework
- `github.com/charmbracelet/lipgloss` - Terminal styling

Testing:

- Standard library `testing`
- `github.com/stretchr/testify` (optional, for assertions)

**Adding New Dependencies:**

1. Check if standard library suffices
2. Research alternatives
3. Verify maintenance status (commits, issues)
4. Document reason in commit message

## Code Style

**Follow standard Go conventions:**

- `gofmt` for formatting (automatic)
- `golint` for linting
- `go vet` for static analysis

**Naming:**

```go
// Good
type SessionManager struct {}
func (sm *SessionManager) ListSessions() {}

// Bad
type session_manager struct {}
func (sm *session_manager) list_sessions() {}
```

**Comments:**

```go
// Package session provides tmux session management.
package session

// Manager handles session creation and switching.
type Manager struct {
    config *Config
}

// ListSessions returns all active tmux sessions.
// It returns an error if tmux is not running.
func (m *Manager) ListSessions() ([]Session, error) {
    // Implementation
}
```

**Error Handling:**

```go
// Good - wrap errors with context
if err := m.createSession(name); err != nil {
    return fmt.Errorf("create session %q: %w", name, err)
}

// Bad - lose context
if err := m.createSession(name); err != nil {
    return err
}
```

## Testing

**Test Coverage Goals:**

- New code: >80% coverage
- Critical paths: 100% coverage
- UI/CLI: Integration tests

**Test Organization:**

```text
internal/
├── config/
│   ├── config.go
│   └── config_test.go
├── session/
│   ├── manager.go
│   ├── manager_test.go
│   └── testdata/
│       └── sample_config.yml
```

**Test Patterns:**

Unit tests:

```go
func TestSessionManager_ListSessions(t *testing.T) {
    tests := []struct {
        name    string
        setup   func()
        want    []Session
        wantErr bool
    }{
        {
            name: "returns active sessions",
            setup: func() {
                // Setup mock
            },
            want: []Session{
                {Name: "dotfiles", Windows: 3},
            },
            wantErr: false,
        },
        {
            name:    "returns error when tmux not running",
            wantErr: true,
        },
    }

    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            if tt.setup != nil {
                tt.setup()
            }

            m := NewManager()
            got, err := m.ListSessions()

            if (err != nil) != tt.wantErr {
                t.Errorf("ListSessions() error = %v, wantErr %v", err, tt.wantErr)
                return
            }

            if !reflect.DeepEqual(got, tt.want) {
                t.Errorf("ListSessions() = %v, want %v", got, tt.want)
            }
        })
    }
}
```

Table-driven tests for multiple cases:

```go
func TestParseSessionConfig(t *testing.T) {
    tests := []struct {
        name    string
        input   string
        want    *SessionConfig
        wantErr bool
    }{
        {
            name: "valid config",
            input: `
defaults:
  - name: test
    directory: /tmp
`,
            want: &SessionConfig{
                Defaults: []Session{
                    {Name: "test", Directory: "/tmp"},
                },
            },
            wantErr: false,
        },
        {
            name:    "invalid YAML",
            input:   "invalid: [",
            wantErr: true,
        },
    }
    // Run tests...
}
```

Golden file tests for YAML parsing:

```go
func TestParseCommands_GoldenFiles(t *testing.T) {
    files, _ := filepath.Glob("testdata/*.yml")
    for _, file := range files {
        t.Run(filepath.Base(file), func(t *testing.T) {
            data, _ := os.ReadFile(file)
            _, err := ParseCommands(data)
            if err != nil {
                t.Errorf("failed to parse %s: %v", file, err)
            }
        })
    }
}
```

**Mocking External Commands:**

```go
// Use interfaces for testability
type TmuxClient interface {
    ListSessions() ([]Session, error)
    SwitchClient(name string) error
}

// Real implementation
type realTmuxClient struct{}

func (c *realTmuxClient) ListSessions() ([]Session, error) {
    // Call actual tmux
}

// Mock for tests
type mockTmuxClient struct {
    sessions []Session
    err      error
}

func (c *mockTmuxClient) ListSessions() ([]Session, error) {
    return c.sessions, c.err
}
```

## Error Handling

**Return errors, don't panic:**

```go
// Good
func LoadConfig() (*Config, error) {
    if _, err := os.Stat(configPath); err != nil {
        return nil, fmt.Errorf("config not found: %w", err)
    }
    // ...
}

// Bad - only panic for programmer errors
func LoadConfig() *Config {
    data := must(os.ReadFile(configPath))  // Don't do this
    // ...
}
```

**Wrap errors with context:**

```go
if err := yaml.Unmarshal(data, &config); err != nil {
    return nil, fmt.Errorf("parse config file %s: %w", path, err)
}
```

**Check errors explicitly:**

```go
// Good
sessions, err := client.ListSessions()
if err != nil {
    return fmt.Errorf("list sessions: %w", err)
}

// Bad - ignoring errors
sessions, _ := client.ListSessions()
```

**Custom error types when needed:**

```go
type SessionNotFoundError struct {
    Name string
}

func (e *SessionNotFoundError) Error() string {
    return fmt.Sprintf("session not found: %s", e.Name)
}

// Usage
if !exists {
    return &SessionNotFoundError{Name: name}
}

// Checking
var notFound *SessionNotFoundError
if errors.As(err, &notFound) {
    // Handle specifically
}
```

## Configuration

**Use YAML for user-facing configs:**

```go
type Config struct {
    Menu      MenuConfig      `yaml:"menu"`
    Sessions  SessionsConfig  `yaml:"sessions"`
}

type MenuConfig struct {
    Height  int  `yaml:"height"`
    Preview bool `yaml:"preview_enabled"`
}
```

**Validation:**

```go
func (c *Config) Validate() error {
    if c.Menu.Height < 5 || c.Menu.Height > 50 {
        return fmt.Errorf("menu height must be 5-50, got %d", c.Menu.Height)
    }
    return nil
}

func LoadConfig(path string) (*Config, error) {
    var cfg Config
    // ... parse YAML ...
    if err := cfg.Validate(); err != nil {
        return nil, fmt.Errorf("invalid config: %w", err)
    }
    return &cfg, nil
}
```

**Default values:**

```go
func DefaultConfig() *Config {
    return &Config{
        Menu: MenuConfig{
            Height:  20,
            Preview: true,
        },
    }
}

func LoadConfig(path string) (*Config, error) {
    cfg := DefaultConfig()
    if _, err := os.Stat(path); os.IsNotExist(err) {
        return cfg, nil  // Use defaults
    }
    // ... load and merge ...
}
```

## Logging

**Use structured logging:**

```go
// Consider using log/slog (Go 1.21+)
import "log/slog"

logger := slog.New(slog.NewTextHandler(os.Stderr, nil))

logger.Info("creating session",
    slog.String("name", name),
    slog.String("directory", dir),
)

logger.Error("failed to create session",
    slog.String("name", name),
    slog.Any("error", err),
)
```

**Log levels:**

- Debug: Verbose details (disabled by default)
- Info: Important events (session created)
- Warn: Unexpected but handled (deprecated config)
- Error: Failures (can't create session)

**No logs to stdout** (reserve for output):

```go
// Good - logs to stderr
logger := slog.New(slog.NewTextHandler(os.Stderr, nil))

// Bad - pollutes output
logger := slog.New(slog.NewTextHandler(os.Stdout, nil))
```

## Performance

**Startup time is critical:**

- Target: <100ms for menu, <50ms for session manager
- Profile if slow: `go build -ldflags="-s -w"` (strip debug info)
- Lazy load when possible

**Benchmarking:**

```go
func BenchmarkParseCommands(b *testing.B) {
    data, _ := os.ReadFile("testdata/commands.yml")
    b.ResetTimer()
    for i := 0; i < b.N; i++ {
        _, _ = ParseCommands(data)
    }
}
```

**Optimize hot paths:**

```go
// Cache expensive operations
type Registry struct {
    commands []Command
    index    map[string]*Command  // Name lookup
}

func (r *Registry) FindByName(name string) (*Command, error) {
    if cmd, ok := r.index[name]; ok {
        return cmd, nil
    }
    return nil, ErrNotFound
}
```

## CLI Design

**Use cobra for consistency:**

```go
var rootCmd = &cobra.Command{
    Use:   "sess",
    Short: "Fast tmux session manager",
    Long:  `A simple and fast tmux session manager built in Go.`,
}

var listCmd = &cobra.Command{
    Use:   "list",
    Short: "List all sessions",
    RunE: func(cmd *cobra.Command, args []string) error {
        // Implementation
        return nil
    },
}

func init() {
    rootCmd.AddCommand(listCmd)
}
```

**Flags and arguments:**

```go
var (
    flagAll     bool
    flagVerbose bool
)

func init() {
    listCmd.Flags().BoolVarP(&flagAll, "all", "a", false, "Show all sessions")
    listCmd.Flags().BoolVarP(&flagVerbose, "verbose", "v", false, "Verbose output")
}
```

**Exit codes:**

```go
// 0 - Success
// 1 - General error
// 2 - Invalid arguments
// 3 - Config error

func main() {
    if err := cmd.Execute(); err != nil {
        if errors.Is(err, ErrInvalidConfig) {
            os.Exit(3)
        }
        os.Exit(1)
    }
}
```

## TUI with Bubbletea

**Model-Update-View pattern:**

```go
type model struct {
    sessions []Session
    cursor   int
    selected map[int]struct{}
}

func (m model) Init() tea.Cmd {
    return nil
}

func (m model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
    switch msg := msg.(type) {
    case tea.KeyMsg:
        switch msg.String() {
        case "q", "esc":
            return m, tea.Quit
        case "up", "k":
            if m.cursor > 0 {
                m.cursor--
            }
        case "down", "j":
            if m.cursor < len(m.sessions)-1 {
                m.cursor++
            }
        }
    }
    return m, nil
}

func (m model) View() string {
    var s strings.Builder
    s.WriteString("Sessions:\n\n")
    for i, session := range m.sessions {
        cursor := " "
        if m.cursor == i {
            cursor = ">"
        }
        fmt.Fprintf(&s, "%s %s\n", cursor, session.Name)
    }
    return s.String()
}
```

**Testing TUIs:**

```go
func TestModel_Update(t *testing.T) {
    m := model{
        sessions: []Session{
            {Name: "dotfiles"},
            {Name: "notes"},
        },
        cursor: 0,
    }

    // Simulate down arrow
    newModel, _ := m.Update(tea.KeyMsg{Type: tea.KeyDown})
    m = newModel.(model)

    if m.cursor != 1 {
        t.Errorf("expected cursor=1, got %d", m.cursor)
    }
}
```

## Build & Release

**Build flags:**

```bash
# Development
go build -o sess .

# Production (smaller binary)
go build -ldflags="-s -w" -o sess .

# Static binary (no dependencies)
CGO_ENABLED=0 go build -ldflags="-s -w" -o sess .
```

**Versioning:**

```go
// Set at build time
var (
    version = "dev"
    commit  = "none"
    date    = "unknown"
)

// Build with:
// go build -ldflags="-X main.version=1.0.0 -X main.commit=abc123"
```

**App-level Task integration:**

Each Go app has its own `Taskfile.yml` for local development:

```yaml
# ~/tools/sess/Taskfile.yml
build:
  desc: Build sess
  vars:
    VERSION:
      sh: git describe --tags --always
    COMMIT:
      sh: git rev-parse --short HEAD
  cmds:
    - go build -ldflags="-s -w -X main.version={{.VERSION}} -X main.commit={{.COMMIT}}" -o sess ./cmd/sess

test:
  desc: Run tests
  cmds:
    - go test -v ./...
```

For installation, use `go install` from GitHub rather than local builds.

## Documentation

**Package documentation:**

```go
// Package session provides tmux session management.
//
// It supports creating, listing, switching, and killing sessions.
// It integrates with both tmux and tmuxinator.
//
// Example:
//
//  m := session.NewManager()
//  sessions, err := m.ListSessions()
//  if err != nil {
//      log.Fatal(err)
//  }
//  for _, s := range sessions {
//      fmt.Println(s.Name)
//  }
package session
```

**Function documentation:**

```go
// ListSessions returns all active tmux sessions.
//
// It returns an error if tmux is not running or if the
// tmux command fails.
func (m *Manager) ListSessions() ([]Session, error) {
    // ...
}
```

**README.md per tool:**

```markdown
# sess

Fast tmux session manager written in Go.

## Features
- List sessions
- Create sessions
- Switch sessions
- Tmuxinator integration

## Installation
\`\`\`bash
task go:install-session
\`\`\`

## Usage
\`\`\`bash
sess              # Interactive menu
sess list         # List sessions
sess create foo   # Create session
\`\`\`
```

## Common Patterns

**Reading YAML files:**

```go
func LoadCommands(path string) (*CommandRegistry, error) {
    data, err := os.ReadFile(path)
    if err != nil {
        return nil, fmt.Errorf("read file: %w", err)
    }

    var registry CommandRegistry
    if err := yaml.Unmarshal(data, &registry); err != nil {
        return nil, fmt.Errorf("parse YAML: %w", err)
    }

    return &registry, nil
}
```

**Executing shell commands:**

```go
func listTmuxSessions() ([]string, error) {
    cmd := exec.Command("tmux", "list-sessions", "-F", "#{session_name}")
    output, err := cmd.Output()
    if err != nil {
        var exitErr *exec.ExitError
        if errors.As(err, &exitErr) {
            return nil, fmt.Errorf("tmux command failed: %s", exitErr.Stderr)
        }
        return nil, fmt.Errorf("execute tmux: %w", err)
    }

    sessions := strings.Split(strings.TrimSpace(string(output)), "\n")
    return sessions, nil
}
```

**Checking if program exists:**

```go
func hasTmux() bool {
    _, err := exec.LookPath("tmux")
    return err == nil
}
```

**Platform detection:**

```go
func detectPlatform() string {
    switch runtime.GOOS {
    case "darwin":
        return "macos"
    case "linux":
        // Check for WSL
        if _, err := os.Stat("/proc/version"); err == nil {
            data, _ := os.ReadFile("/proc/version")
            if strings.Contains(strings.ToLower(string(data)), "microsoft") {
                return "wsl"
            }
        }
        return "linux"
    default:
        return "unknown"
    }
}
```

## Pre-Commit Hooks

**Setup:**

```bash
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/golangci/golangci-lint
    rev: v1.55.0
    hooks:
      - id: golangci-lint
        args: [--fix]

  - repo: local
    hooks:
      - id: go-test
        name: go test
        entry: go test ./...
        language: system
        pass_filenames: false
        files: \.go$
```

**Manual checks before commit:**

```bash
task go:test           # Run tests
task go:lint           # Run linter
task go:build          # Ensure it builds
```

## Resources

- [Effective Go](https://go.dev/doc/effective_go)
- [Go Code Review Comments](https://github.com/golang/go/wiki/CodeReviewComments)
- [Standard Go Project Layout](https://github.com/golang-standards/project-layout)
- [Cobra CLI Framework](https://github.com/spf13/cobra)
- [Bubbletea TUI Tutorial](https://github.com/charmbracelet/bubbletea/tree/master/tutorials)
