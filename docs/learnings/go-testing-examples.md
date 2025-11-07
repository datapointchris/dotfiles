# Go Testing Examples for TUI Applications

Practical test file examples demonstrating testing patterns for Go TUI applications with external command dependencies (tmux, git, task).

## Example 1: Testing Session Manager with Mock Executor

### Production Code

```go
// session/session.go
package session

import (
    "fmt"
    "os/exec"
    "strings"
)

// CommandExecutor interface for dependency injection
type CommandExecutor interface {
    Run(name string, args ...string) ([]byte, error)
}

// RealExecutor uses actual exec.Command
type RealExecutor struct{}

func (e *RealExecutor) Run(name string, args ...string) ([]byte, error) {
    return exec.Command(name, args...).Output()
}

// SessionManager manages tmux sessions
type SessionManager struct {
    executor CommandExecutor
}

func NewSessionManager(executor CommandExecutor) *SessionManager {
    return &SessionManager{executor: executor}
}

func (sm *SessionManager) ListSessions() ([]string, error) {
    output, err := sm.executor.Run("tmux", "list-sessions", "-F", "#{session_name}")
    if err != nil {
        return nil, fmt.Errorf("failed to list sessions: %w", err)
    }

    lines := strings.Split(strings.TrimSpace(string(output)), "\n")
    return lines, nil
}

func (sm *SessionManager) CreateSession(name, path string) error {
    _, err := sm.executor.Run("tmux", "new-session", "-d", "-s", name, "-c", path)
    if err != nil {
        return fmt.Errorf("failed to create session %s: %w", name, err)
    }
    return nil
}

func (sm *SessionManager) AttachSession(name string) error {
    _, err := sm.executor.Run("tmux", "attach-session", "-t", name)
    if err != nil {
        return fmt.Errorf("failed to attach to session %s: %w", name, err)
    }
    return nil
}
```

### Test Code

```go
// session/session_test.go
package session

import (
    "fmt"
    "testing"
)

// MockExecutor for testing
type MockExecutor struct {
    RunFunc func(name string, args ...string) ([]byte, error)
}

func (m *MockExecutor) Run(name string, args ...string) ([]byte, error) {
    if m.RunFunc != nil {
        return m.RunFunc(name, args...)
    }
    return nil, fmt.Errorf("not implemented")
}

func TestListSessions(t *testing.T) {
    tests := []struct {
        name       string
        output     []byte
        err        error
        wantCount  int
        wantErr    bool
        wantNames  []string
    }{
        {
            name:      "multiple sessions",
            output:    []byte("dotfiles\nproject1\nproject2"),
            err:       nil,
            wantCount: 3,
            wantNames: []string{"dotfiles", "project1", "project2"},
            wantErr:   false,
        },
        {
            name:      "single session",
            output:    []byte("dotfiles"),
            err:       nil,
            wantCount: 1,
            wantNames: []string{"dotfiles"},
            wantErr:   false,
        },
        {
            name:      "no sessions",
            output:    []byte(""),
            err:       fmt.Errorf("no sessions"),
            wantCount: 0,
            wantErr:   true,
        },
    }

    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            mock := &MockExecutor{
                RunFunc: func(name string, args ...string) ([]byte, error) {
                    if name != "tmux" {
                        t.Errorf("expected command 'tmux', got '%s'", name)
                    }
                    return tt.output, tt.err
                },
            }

            sm := NewSessionManager(mock)
            sessions, err := sm.ListSessions()

            if (err != nil) != tt.wantErr {
                t.Errorf("ListSessions() error = %v, wantErr %v", err, tt.wantErr)
                return
            }

            if !tt.wantErr && len(sessions) != tt.wantCount {
                t.Errorf("got %d sessions, want %d", len(sessions), tt.wantCount)
            }

            if !tt.wantErr {
                for i, want := range tt.wantNames {
                    if sessions[i] != want {
                        t.Errorf("session[%d] = %s, want %s", i, sessions[i], want)
                    }
                }
            }
        })
    }
}

func TestCreateSession(t *testing.T) {
    tests := []struct {
        name        string
        sessionName string
        path        string
        mockErr     error
        wantErr     bool
    }{
        {
            name:        "successful creation",
            sessionName: "test-session",
            path:        "/home/user/project",
            mockErr:     nil,
            wantErr:     false,
        },
        {
            name:        "creation fails",
            sessionName: "test-session",
            path:        "/nonexistent/path",
            mockErr:     fmt.Errorf("command failed"),
            wantErr:     true,
        },
    }

    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            var capturedArgs []string
            mock := &MockExecutor{
                RunFunc: func(name string, args ...string) ([]byte, error) {
                    capturedArgs = args
                    return nil, tt.mockErr
                },
            }

            sm := NewSessionManager(mock)
            err := sm.CreateSession(tt.sessionName, tt.path)

            if (err != nil) != tt.wantErr {
                t.Errorf("CreateSession() error = %v, wantErr %v", err, tt.wantErr)
                return
            }

            if !tt.wantErr {
                // Verify correct arguments were passed
                expectedArgs := []string{"new-session", "-d", "-s", tt.sessionName, "-c", tt.path}
                if len(capturedArgs) != len(expectedArgs) {
                    t.Errorf("wrong number of args: got %v, want %v", capturedArgs, expectedArgs)
                }
            }
        })
    }
}
```

## Example 2: Testing Bubbletea Model

### Production Code

```go
// tui/model.go
package tui

import (
    tea "github.com/charmbracelet/bubbletea"
    "github.com/your/project/session"
)

type Model struct {
    sessions []string
    cursor   int
    manager  *session.SessionManager
}

func InitialModel(manager *session.SessionManager) Model {
    return Model{
        sessions: []string{},
        cursor:   0,
        manager:  manager,
    }
}

type sessionsLoadedMsg struct {
    sessions []string
}

func (m Model) Init() tea.Cmd {
    return loadSessions(m.manager)
}

func loadSessions(manager *session.SessionManager) tea.Cmd {
    return func() tea.Msg {
        sessions, err := manager.ListSessions()
        if err != nil {
            return errMsg{err}
        }
        return sessionsLoadedMsg{sessions}
    }
}

type errMsg struct{ err error }

func (m Model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
    switch msg := msg.(type) {
    case tea.KeyMsg:
        switch msg.String() {
        case "up", "k":
            if m.cursor > 0 {
                m.cursor--
            }
        case "down", "j":
            if m.cursor < len(m.sessions)-1 {
                m.cursor++
            }
        case "enter":
            if len(m.sessions) > 0 {
                return m, attachSession(m.manager, m.sessions[m.cursor])
            }
        case "q":
            return m, tea.Quit
        }

    case sessionsLoadedMsg:
        m.sessions = msg.sessions

    case errMsg:
        // Handle error
        return m, tea.Quit
    }

    return m, nil
}

func attachSession(manager *session.SessionManager, name string) tea.Cmd {
    return func() tea.Msg {
        err := manager.AttachSession(name)
        if err != nil {
            return errMsg{err}
        }
        return tea.Quit()
    }
}

func (m Model) View() string {
    s := "Select a tmux session:\n\n"

    for i, session := range m.sessions {
        cursor := " "
        if m.cursor == i {
            cursor = ">"
        }
        s += fmt.Sprintf("%s %s\n", cursor, session)
    }

    s += "\nPress q to quit.\n"
    return s
}
```

### Test Code

```go
// tui/model_test.go
package tui

import (
    "testing"

    tea "github.com/charmbracelet/bubbletea"
    "github.com/your/project/session"
)

func TestModelUpdate_Navigation(t *testing.T) {
    // Setup model with mock manager
    mock := &session.MockExecutor{
        RunFunc: func(name string, args ...string) ([]byte, error) {
            return []byte("session1\nsession2\nsession3"), nil
        },
    }
    manager := session.NewSessionManager(mock)
    model := InitialModel(manager)

    // Load sessions first
    model.sessions = []string{"session1", "session2", "session3"}

    tests := []struct {
        name       string
        key        string
        startPos   int
        wantCursor int
    }{
        {"move down", "down", 0, 1},
        {"move down again", "j", 1, 2},
        {"move up", "up", 2, 1},
        {"move up again", "k", 1, 0},
        {"cant go below 0", "up", 0, 0},
        {"cant go above max", "down", 2, 2},
    }

    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            model.cursor = tt.startPos

            updatedModel, _ := model.Update(tea.KeyMsg{
                Type:  tea.KeyRunes,
                Runes: []rune(tt.key),
            })

            m := updatedModel.(Model)
            if m.cursor != tt.wantCursor {
                t.Errorf("cursor = %d, want %d", m.cursor, tt.wantCursor)
            }
        })
    }
}

func TestModelUpdate_SessionsLoaded(t *testing.T) {
    mock := &session.MockExecutor{}
    manager := session.NewSessionManager(mock)
    model := InitialModel(manager)

    msg := sessionsLoadedMsg{
        sessions: []string{"dotfiles", "project"},
    }

    updatedModel, _ := model.Update(msg)
    m := updatedModel.(Model)

    if len(m.sessions) != 2 {
        t.Errorf("got %d sessions, want 2", len(m.sessions))
    }

    if m.sessions[0] != "dotfiles" {
        t.Errorf("first session = %s, want dotfiles", m.sessions[0])
    }
}

func TestModelUpdate_Quit(t *testing.T) {
    mock := &session.MockExecutor{}
    manager := session.NewSessionManager(mock)
    model := InitialModel(manager)

    _, cmd := model.Update(tea.KeyMsg{
        Type:  tea.KeyRunes,
        Runes: []rune("q"),
    })

    // Verify tea.Quit command was returned
    if cmd == nil {
        t.Error("expected quit command, got nil")
    }
}

func TestLoadSessionsCmd(t *testing.T) {
    tests := []struct {
        name        string
        mockOutput  []byte
        mockErr     error
        wantSessions int
        wantErr     bool
    }{
        {
            name:        "successful load",
            mockOutput:  []byte("session1\nsession2"),
            mockErr:     nil,
            wantSessions: 2,
            wantErr:     false,
        },
        {
            name:        "failed load",
            mockOutput:  nil,
            mockErr:     fmt.Errorf("tmux not running"),
            wantSessions: 0,
            wantErr:     true,
        },
    }

    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            mock := &session.MockExecutor{
                RunFunc: func(name string, args ...string) ([]byte, error) {
                    return tt.mockOutput, tt.mockErr
                },
            }
            manager := session.NewSessionManager(mock)

            cmd := loadSessions(manager)
            msg := cmd()

            switch msg := msg.(type) {
            case sessionsLoadedMsg:
                if tt.wantErr {
                    t.Error("expected error, got sessions")
                }
                if len(msg.sessions) != tt.wantSessions {
                    t.Errorf("got %d sessions, want %d", len(msg.sessions), tt.wantSessions)
                }
            case errMsg:
                if !tt.wantErr {
                    t.Errorf("unexpected error: %v", msg.err)
                }
            default:
                t.Errorf("unexpected message type: %T", msg)
            }
        })
    }
}
```

## Example 3: Testing with Teatest

```go
// tui/model_teatest_test.go
//go:build integration

package tui

import (
    "bytes"
    "io"
    "testing"
    "time"

    tea "github.com/charmbracelet/bubbletea"
    "github.com/charmbracelet/x/exp/teatest"
    "github.com/your/project/session"
)

func init() {
    // Ensure consistent output in tests
    lipgloss.SetColorProfile(termenv.Ascii)
}

func TestFullOutput(t *testing.T) {
    if testing.Short() {
        t.Skip("skipping integration test")
    }

    mock := &session.MockExecutor{
        RunFunc: func(name string, args ...string) ([]byte, error) {
            return []byte("dotfiles\nproject"), nil
        },
    }
    manager := session.NewSessionManager(mock)
    model := InitialModel(manager)

    tm := teatest.NewTestModel(
        t,
        model,
        teatest.WithInitialTermSize(80, 24),
    )

    // Wait for initial render
    time.Sleep(100 * time.Millisecond)

    // Send quit command
    tm.Send(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune("q")})

    // Read final output
    out, err := io.ReadAll(tm.FinalOutput(t))
    if err != nil {
        t.Fatal(err)
    }

    // Verify output contains expected text
    if !bytes.Contains(out, []byte("Select a tmux session")) {
        t.Error("output missing header text")
    }
    if !bytes.Contains(out, []byte("dotfiles")) {
        t.Error("output missing dotfiles session")
    }
    if !bytes.Contains(out, []byte("project")) {
        t.Error("output missing project session")
    }
}

func TestInteractiveNavigation(t *testing.T) {
    if testing.Short() {
        t.Skip("skipping integration test")
    }

    mock := &session.MockExecutor{
        RunFunc: func(name string, args ...string) ([]byte, error) {
            return []byte("session1\nsession2\nsession3"), nil
        },
    }
    manager := session.NewSessionManager(mock)
    model := InitialModel(manager)

    tm := teatest.NewTestModel(t, model)

    // Wait for sessions to load
    teatest.WaitFor(
        t,
        tm.Output(),
        func(bts []byte) bool {
            return bytes.Contains(bts, []byte("session1"))
        },
        teatest.WithDuration(time.Second),
    )

    // Navigate down
    tm.Send(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune("j")})
    tm.Send(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune("j")})

    // Verify cursor moved (check output contains cursor indicator)
    teatest.WaitFor(
        t,
        tm.Output(),
        func(bts []byte) bool {
            // Look for cursor on session3
            return bytes.Contains(bts, []byte("> session3"))
        },
        teatest.WithDuration(time.Second),
    )

    // Quit
    tm.Send(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune("q")})
    tm.WaitFinished(t, teatest.WithFinalTimeout(time.Second))
}
```

## Example 4: Golden File Testing

```go
// tui/render_test.go
package tui

import (
    "testing"

    "github.com/sebdah/goldie/v2"
    "github.com/your/project/session"
)

func TestRenderWithSessions(t *testing.T) {
    tests := []struct {
        name     string
        sessions []string
        cursor   int
        golden   string
    }{
        {
            name:     "three sessions cursor at start",
            sessions: []string{"dotfiles", "project1", "project2"},
            cursor:   0,
            golden:   "three-sessions-start",
        },
        {
            name:     "three sessions cursor in middle",
            sessions: []string{"dotfiles", "project1", "project2"},
            cursor:   1,
            golden:   "three-sessions-middle",
        },
        {
            name:     "single session",
            sessions: []string{"dotfiles"},
            cursor:   0,
            golden:   "single-session",
        },
        {
            name:     "no sessions",
            sessions: []string{},
            cursor:   0,
            golden:   "no-sessions",
        },
    }

    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            mock := &session.MockExecutor{}
            manager := session.NewSessionManager(mock)
            model := InitialModel(manager)

            model.sessions = tt.sessions
            model.cursor = tt.cursor

            output := model.View()

            g := goldie.New(t)
            g.Assert(t, tt.golden, []byte(output))
        })
    }
}
```

To update golden files: `go test -update ./...`

## Example 5: Test Helpers and Fixtures

```go
// testing/helpers.go
package testing

import (
    "os"
    "path/filepath"
    "testing"

    "github.com/your/project/session"
)

// LoadFixture loads test data from testdata directory
func LoadFixture(t *testing.T, name string) []byte {
    t.Helper()
    path := filepath.Join("testdata", name)
    data, err := os.ReadFile(path)
    if err != nil {
        t.Fatalf("failed to load fixture %s: %v", name, err)
    }
    return data
}

// MockSessionManager creates a session manager with predictable output
func MockSessionManager(sessions []string) *session.SessionManager {
    mock := &session.MockExecutor{
        RunFunc: func(name string, args ...string) ([]byte, error) {
            if name == "tmux" && args[0] == "list-sessions" {
                return []byte(strings.Join(sessions, "\n")), nil
            }
            return nil, nil
        },
    }
    return session.NewSessionManager(mock)
}

// AssertSessionCount verifies session count
func AssertSessionCount(t *testing.T, sessions []string, want int) {
    t.Helper()
    if got := len(sessions); got != want {
        t.Errorf("got %d sessions, want %d", got, want)
    }
}

// AssertContainsSession verifies a session exists in list
func AssertContainsSession(t *testing.T, sessions []string, name string) {
    t.Helper()
    for _, s := range sessions {
        if s == name {
            return
        }
    }
    t.Errorf("session %s not found in %v", name, sessions)
}
```

Usage:

```go
func TestWithHelpers(t *testing.T) {
    sessions := []string{"dotfiles", "project"}

    AssertSessionCount(t, sessions, 2)
    AssertContainsSession(t, sessions, "dotfiles")
}
```

## CI/CD Configuration

### `.github/workflows/test.yml`

```yaml
name: Test

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest]
        go-version: ['1.22', '1.23']

    steps:
    - name: Checkout code
      uses: actions/checkout@v4

    - name: Set up Go
      uses: actions/setup-go@v5
      with:
        go-version: ${{ matrix.go-version }}

    - name: Cache Go modules
      uses: actions/cache@v4
      with:
        path: ~/go/pkg/mod
        key: ${{ runner.os }}-go-${{ hashFiles('**/go.sum') }}
        restore-keys: |
          ${{ runner.os }}-go-

    - name: Run unit tests
      run: go test -short -race -coverprofile=coverage.out -covermode=atomic ./...

    - name: Run integration tests
      run: go test -tags=integration -race ./...

    - name: Upload coverage
      uses: codecov/codecov-action@v5
      with:
        file: ./coverage.out
        fail_ci_if_error: false

  lint:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-go@v5
      with:
        go-version: '1.23'

    - name: Run golangci-lint
      uses: golangci/golangci-lint-action@v4
      with:
        version: latest
```

### `.gitattributes`

```
*.golden -text
testdata/* -text
```

### `Taskfile.yml`

```yaml
version: '3'

tasks:
  test:
    desc: Run all tests
    cmds:
      - go test -v ./...

  test:unit:
    desc: Run unit tests only
    cmds:
      - go test -short -v ./...

  test:integration:
    desc: Run integration tests
    cmds:
      - go test -tags=integration -v ./...

  test:coverage:
    desc: Generate coverage report
    cmds:
      - go test -coverprofile=coverage.out ./...
      - go tool cover -html=coverage.out

  test:watch:
    desc: Run tests on file changes
    cmds:
      - watchexec -e go -c -- go test ./...

  test:update-golden:
    desc: Update golden files
    cmds:
      - go test -update ./...

  test:race:
    desc: Run tests with race detector
    cmds:
      - go test -race ./...

  test:bench:
    desc: Run benchmarks
    cmds:
      - go test -bench=. -benchmem ./...
```

## Summary

These examples demonstrate:

1. **Interface-based mocking** for external commands (tmux, git, task)
2. **Table-driven tests** for comprehensive test coverage
3. **Bubbletea model testing** with direct Update function calls
4. **Integration testing** with teatest
5. **Golden file testing** for complex output verification
6. **Test helpers** for DRY test code
7. **CI/CD configuration** with GitHub Actions and Codecov

Key principles:

- Mock external dependencies via interfaces
- Test business logic independently of I/O
- Use table-driven tests for multiple scenarios
- Separate unit and integration tests
- Use golden files for complex output
- Automate testing in CI/CD pipeline
