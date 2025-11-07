# Go Migration Quick Start

Quick reference for getting started with the Go migration project.

## Prerequisites

**Install Go:**
```bash
# macOS
brew install go

# Verify
go version  # Should be 1.21+
```

## Phase 1: Session Manager (Start Here)

### 1. Create Project Structure

```bash
cd ~/dotfiles/tools
mkdir -p session-go/{cmd,internal/{config,session,tmux,ui}}
cd session-go
```

### 2. Initialize Go Module

```bash
go mod init session-go
```

### 3. Add Dependencies

```bash
go get github.com/spf13/cobra@latest
go get github.com/charmbracelet/bubbletea@latest
go get github.com/charmbracelet/lipgloss@latest
go get gopkg.in/yaml.v3@latest
```

### 4. Create Entry Point

Create `main.go`:
```go
package main

import (
    "fmt"
    "os"
    "session-go/cmd"
)

func main() {
    if err := cmd.Execute(); err != nil {
        fmt.Fprintf(os.Stderr, "Error: %v\n", err)
        os.Exit(1)
    }
}
```

### 5. Create Root Command

Create `cmd/root.go`:
```go
package cmd

import (
    "github.com/spf13/cobra"
)

var rootCmd = &cobra.Command{
    Use:   "session-go",
    Short: "Fast tmux session manager",
    Long:  "A simple and fast tmux session manager built in Go",
}

func Execute() error {
    return rootCmd.Execute()
}
```

### 6. Build and Test

```bash
# Build
go build -o ~/.local/bin/session-go .

# Test
session-go --help
```

### 7. Add to Taskfile

Create `taskfiles/go.yml`:
```yaml
version: '3'

tasks:
  build-session:
    desc: Build session-go binary
    dir: tools/session-go
    cmds:
      - go build -o {{.HOME}}/.local/bin/session-go .

  test-session:
    desc: Test session-go
    dir: tools/session-go
    cmds:
      - go test ./... -v -cover

  install-session:
    desc: Build and install session-go
    deps:
      - build-session
```

Include in main `Taskfile.yml`:
```yaml
includes:
  go:
    taskfile: ./taskfiles/go.yml
    optional: true
```

### 8. Development Workflow

```bash
# Build
task go:build-session

# Test
task go:test-session

# Install
task go:install-session
```

## Next Steps

1. **Parse Session Config** - Implement YAML parsing in `internal/config/`
2. **Tmux Integration** - Implement tmux commands in `internal/tmux/`
3. **Interactive UI** - Build TUI in `internal/ui/`
4. **Testing** - Add tests as you go

## Common Commands

**Development:**
```bash
# Format code
go fmt ./...

# Run tests
go test ./... -v

# Run tests with coverage
go test ./... -cover

# Build
go build -o session-go .

# Run without building
go run main.go
```

**Debugging:**
```bash
# Verbose output
go build -v

# Show what go build does
go build -x

# Check dependencies
go mod tidy
go mod verify
```

## File Templates

**Test file template:**
```go
package config

import "testing"

func TestLoadConfig(t *testing.T) {
    tests := []struct {
        name    string
        input   string
        want    *Config
        wantErr bool
    }{
        {
            name: "valid config",
            input: `defaults:
  - name: test
    directory: /tmp`,
            want: &Config{
                Defaults: []Session{
                    {Name: "test", Directory: "/tmp"},
                },
            },
            wantErr: false,
        },
    }

    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            // Test implementation
        })
    }
}
```

**Struct with YAML tags:**
```go
type SessionConfig struct {
    Defaults []Session `yaml:"defaults"`
}

type Session struct {
    Name             string   `yaml:"name"`
    Directory        string   `yaml:"directory"`
    Description      string   `yaml:"description,omitempty"`
    TmuxinatorProject string  `yaml:"tmuxinator_project,omitempty"`
    Windows          []Window `yaml:"windows,omitempty"`
}
```

## Troubleshooting

**Module not found:**
```bash
go mod tidy
```

**Import cycle:**
- Move shared code to a common package
- Use interfaces to break dependencies

**Tests not running:**
```bash
# Must be in package directory or use ./...
go test ./...
```

## Resources

- [Migration Strategy](./go-migration-strategy.md) - Full strategy document
- [Go Development Standards](./go-development.md) - Coding standards
- [Cobra Docs](https://github.com/spf13/cobra/blob/main/user_guide.md)
- [Bubbletea Tutorial](https://github.com/charmbracelet/bubbletea/tree/master/tutorials/basics)
