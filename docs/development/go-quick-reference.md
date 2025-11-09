# Go CLI/TUI Quick Reference

Quick reference for building Go CLI/TUI applications based on analysis of sesh, lazygit, and gum.

## Essential Libraries

```bash
# CLI Framework
go get github.com/spf13/cobra           # Most popular, feature-rich
# OR
go get github.com/alecthomas/kong       # Declarative, simpler

# TUI Framework
go get github.com/charmbracelet/bubbletea   # Modern, Elm architecture
go get github.com/charmbracelet/lipgloss    # Styling
go get github.com/charmbracelet/bubbles     # Pre-built components

# Configuration
go get github.com/pelletier/go-toml/v2      # TOML parsing

# Testing
go get github.com/stretchr/testify/assert   # Assertions
go get github.com/stretchr/testify/mock     # Manual mocking
go install github.com/vektra/mockery/v3@latest  # Mock generation

# Logging
# Use stdlib: log/slog (Go 1.21+)
```

## Project Structure Template

```text
project/
├── main.go                      # Entry point + logging setup
├── cmd/                         # Cobra commands
│   ├── root.go                  # Root command + DI
│   ├── list.go
│   └── run.go
├── model/                       # Data structures
│   ├── config.go
│   └── item.go
├── config/                      # Config loading
│   └── loader.go
├── ui/                          # Bubbletea TUI
│   ├── menu.go                  # Main model
│   ├── keys.go
│   └── styles.go
├── executor/                    # Business logic
│   └── executor.go
├── tmux/                        # External adapters
│   ├── tmux.go                  # Interface + impl
│   ├── tmux_test.go
│   └── mock_tmux.go             # Generated
├── shell/                       # Shell wrapper
│   ├── shell.go
│   └── mock_shell.go
└── internal/                    # Non-exported helpers
    ├── execwrap/                # os/exec wrapper
    ├── oswrap/                  # os wrapper
    └── pathwrap/                # path wrapper
```

## Standard Patterns

### 1. Interface + Wrapper Pattern

```go
// tmux/tmux.go
package tmux

// Interface (for mocking)
type Tmux interface {
    ListSessions() ([]*Session, error)
    NewSession(name, path string) error
}

// Implementation
type RealTmux struct {
    shell shell.Shell  // Injected dependency
}

// Constructor
func NewTmux(shell shell.Shell) Tmux {
    return &RealTmux{shell: shell}
}

// Methods
func (t *RealTmux) ListSessions() ([]*Session, error) {
    output, err := t.shell.Cmd("tmux", "list-sessions", "-F", "...")
    if err != nil {
        return nil, fmt.Errorf("listing sessions: %w", err)
    }
    return parseSessions(output), nil
}
```

### 2. Shell Wrapper (for testability)

```go
// shell/shell.go
package shell

import "os/exec"

type Shell interface {
    Cmd(cmd string, args ...string) (string, error)
}

type RealShell struct {
    exec execwrap.Exec
}

func NewShell(exec execwrap.Exec) Shell {
    return &RealShell{exec: exec}
}

func (s *RealShell) Cmd(cmd string, args ...string) (string, error) {
    command := exec.Command(cmd, args...)
    output, err := command.Output()
    return strings.TrimSpace(string(output)), err
}
```

### 3. Dependency Injection in Root Command

```go
// cmd/root.go
package cmd

import "github.com/spf13/cobra"

func NewRootCommand() *cobra.Command {
    // 1. Create wrappers
    exec := execwrap.NewExec()
    os := oswrap.NewOs()

    // 2. Create base deps
    shell := shell.NewShell(exec)

    // 3. Create adapters
    tmux := tmux.NewTmux(shell)

    // 4. Load config
    cfg, _ := config.Load()

    // 5. Create services
    executor := executor.NewExecutor(tmux, cfg)

    // 6. Create commands
    rootCmd := &cobra.Command{
        Use:   "myapp",
        Short: "Description",
    }

    rootCmd.AddCommand(
        NewListCommand(tmux),
        NewRunCommand(executor),
    )

    return rootCmd
}
```

### 4. Table-Driven Tests

```go
// tmux/tmux_test.go
package tmux

import (
    "testing"
    "github.com/stretchr/testify/assert"
)

func TestListSessions(t *testing.T) {
    tests := []struct {
        name        string
        shellOutput string
        expected    []*Session
        expectError bool
    }{
        {
            name:        "single session",
            shellOutput: "session1::/path/to/project",
            expected: []*Session{
                {Name: "session1", Path: "/path/to/project"},
            },
            expectError: false,
        },
        {
            name:        "empty output",
            shellOutput: "",
            expected:    []*Session{},
            expectError: false,
        },
    }

    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            mockShell := new(shell.MockShell)
            mockShell.On("Cmd", "tmux", "list-sessions", "-F", "...").
                Return(tt.shellOutput, nil)

            tmux := NewTmux(mockShell)
            result, err := tmux.ListSessions()

            if tt.expectError {
                assert.Error(t, err)
            } else {
                assert.NoError(t, err)
                assert.Equal(t, tt.expected, result)
            }

            mockShell.AssertExpectations(t)
        })
    }
}
```

### 5. Bubbletea TUI Model

```go
// ui/menu.go
package ui

import tea "github.com/charmbracelet/bubbletea"

type Model struct {
    items    []Item
    selected int
    filter   string
}

func NewModel(items []Item) Model {
    return Model{
        items:    items,
        selected: 0,
    }
}

func (m Model) Init() tea.Cmd {
    return nil
}

func (m Model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
    switch msg := msg.(type) {
    case tea.KeyMsg:
        switch msg.String() {
        case "q", "ctrl+c":
            return m, tea.Quit
        case "j", "down":
            if m.selected < len(m.items)-1 {
                m.selected++
            }
        case "k", "up":
            if m.selected > 0 {
                m.selected--
            }
        case "enter":
            // Execute selected item
            return m, tea.Quit
        }
    }
    return m, nil
}

func (m Model) View() string {
    var s string
    for i, item := range m.items {
        cursor := " "
        if i == m.selected {
            cursor = ">"
        }
        s += fmt.Sprintf("%s %s\n", cursor, item.Name)
    }
    return s
}
```

### 6. TOML Configuration

```go
// config/loader.go
package config

import (
    "os"
    "path/filepath"
    "github.com/pelletier/go-toml/v2"
)

type Config struct {
    General    GeneralConfig    `toml:"general"`
    Categories []CategoryConfig `toml:"categories"`
}

type GeneralConfig struct {
    Theme string `toml:"theme"`
    Shell string `toml:"shell"`
}

type CategoryConfig struct {
    Name string `toml:"name"`
    Type string `toml:"type"`
}

func Load() (*Config, error) {
    home, _ := os.UserHomeDir()
    path := filepath.Join(home, ".config", "myapp", "config.toml")

    data, err := os.ReadFile(path)
    if err != nil {
        return nil, err
    }

    var cfg Config
    if err := toml.Unmarshal(data, &cfg); err != nil {
        return nil, err
    }

    return &cfg, nil
}
```

### 7. Mockery Configuration

```yaml
# .mockery.yaml
with-expecter: true
all: true
dir: "{{.InterfaceDir}}"
filename: "mock_{{.InterfaceName}}.go"
mockname: "Mock{{.InterfaceName}}"
outpkg: "{{.PackageName}}"
```

Run with:

```bash
mockery  # Generates mock_*.go files
```

### 8. GoReleaser Setup

```yaml
# .goreleaser.yaml
version: 1

before:
  hooks:
    - go mod tidy

builds:
  - env:
      - CGO_ENABLED=0
    goos:
      - linux
      - darwin
    ldflags:
      - -X main.version={{.Version}}

archives:
  - format: tar.gz
    name_template: >-
      {{ .ProjectName }}_
      {{- title .Os }}_
      {{- if eq .Arch "amd64" }}x86_64
      {{- else }}{{ .Arch }}{{ end }}

brews:
  - name: myapp
    homepage: "https://github.com/user/myapp"
    description: "Description"
    repository:
      owner: user
      name: homebrew-myapp
```

### 9. GitHub Actions CI/CD

```yaml
# .github/workflows/ci-cd.yml
name: Test and Release

on:
  push:
    branches: [main]
    tags: ["*"]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-go@v5
        with:
          go-version: "1.24"
      - run: go install github.com/vektra/mockery/v3@latest
      - run: mockery
      - run: go test -race -cover ./...

  release:
    needs: test
    if: startsWith(github.ref, 'refs/tags/')
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-go@v5
      - uses: goreleaser/goreleaser-action@v5
        with:
          args: release --clean
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

### 10. Structured Logging

```go
// main.go
package main

import (
    "log/slog"
    "os"
    "path/filepath"
)

func main() {
    setupLogging()

    // Your app
    cmd := cmd.NewRootCommand()
    if err := cmd.Execute(); err != nil {
        slog.Error("execution failed", "error", err)
        os.Exit(1)
    }
}

func setupLogging() {
    logDir := filepath.Join(os.TempDir(), ".myapp")
    os.MkdirAll(logDir, 0755)

    logFile := filepath.Join(logDir, "app.log")
    f, _ := os.OpenFile(logFile, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0644)

    level := slog.LevelWarn
    if os.Getenv("DEBUG") != "" {
        level = slog.LevelDebug
    }

    handler := slog.NewJSONHandler(f, &slog.HandlerOptions{
        Level: level,
    })

    slog.SetDefault(slog.New(handler))
}
```

## Common Gotchas

### 1. Circular Dependencies

**Problem:**

```text
tmux/ imports menu/
menu/ imports tmux/  ← ERROR
```

**Solution:**

```text
model/          # Shared types
  └── item.go

tmux/           # Imports model
  └── tmux.go

menu/           # Imports model and tmux
  └── menu.go
```

### 2. Testing External Commands

**Don't:**

```go
func TestTmux(t *testing.T) {
    // Actually calls tmux!
    output := exec.Command("tmux", "list-sessions").Output()
}
```

**Do:**

```go
func TestTmux(t *testing.T) {
    mockShell := new(shell.MockShell)
    mockShell.On("Cmd", "tmux", "list-sessions").Return("output", nil)

    tmux := NewTmux(mockShell)
    result, _ := tmux.ListSessions()
}
```

### 3. Bubbletea Message Handling

**Don't:**

```go
func (m Model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
    // Mutating outside switch
    m.selected++

    switch msg := msg.(type) {
    case tea.KeyMsg:
        // ...
    }
}
```

**Do:**

```go
func (m Model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
    switch msg := msg.(type) {
    case tea.KeyMsg:
        switch msg.String() {
        case "j":
            m.selected++  // Mutate inside switch
        }
    }
    return m, nil  // Return new state
}
```

## Checklist for New Project

- [ ] Initialize Go module: `go mod init github.com/user/project`
- [ ] Install Cobra: `go get github.com/spf13/cobra`
- [ ] Install Bubbletea: `go get github.com/charmbracelet/bubbletea`
- [ ] Install Lipgloss: `go get github.com/charmbracelet/lipgloss`
- [ ] Install TOML parser: `go get github.com/pelletier/go-toml/v2`
- [ ] Install testify: `go get github.com/stretchr/testify`
- [ ] Install mockery: `go install github.com/vektra/mockery/v3@latest`
- [ ] Create `.mockery.yaml`
- [ ] Create `.goreleaser.yaml`
- [ ] Create `.github/workflows/ci-cd.yml`
- [ ] Set up package structure
- [ ] Create interface-based wrappers
- [ ] Write first table-driven test
- [ ] Set up logging
- [ ] Create config loader

## Resources

- **Bubbletea:** <https://github.com/charmbracelet/bubbletea>
- **Cobra:** <https://github.com/spf13/cobra>
- **Mockery:** <https://github.com/vektra/mockery>
- **GoReleaser:** <https://goreleaser.com>
- **Go Testing:** <https://go.dev/doc/tutorial/add-a-test>

For detailed analysis, see:

- [Go CLI Architecture Analysis](../learnings/go-cli-architecture-analysis.md)
- [sesh Architecture Diagram](../architecture/sesh-architecture-diagram.md)
