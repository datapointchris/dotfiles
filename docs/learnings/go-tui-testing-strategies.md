# Go TUI Testing Strategies

Comprehensive testing guide for Go applications, specifically focused on TUI (Terminal User Interface) applications built with Bubbletea.

## Go's Built-in Testing Package

### Testing Package Basics

Go includes a robust built-in testing framework in the `testing` package. Test files are named with a `_test.go` suffix and test functions follow the pattern `func TestXxx(t *testing.T)`.

```go
package mypackage

import "testing"

func TestAdd(t *testing.T) {
    result := Add(2, 3)
    if result != 5 {
        t.Errorf("Add(2, 3) = %d; want 5", result)
    }
}
```

Key functions:

- `t.Error()` / `t.Errorf()` - Mark test as failed but continue
- `t.Fatal()` / `t.Fatalf()` - Mark test as failed and stop immediately
- `t.Helper()` - Mark function as test helper (improves error location reporting)
- `t.Run()` - Run subtests with individual names

### Table-Driven Tests (Go Idiom)

Table-driven tests are a Go community best practice where you define test cases as data and iterate through them. This approach writes the test logic once and amortizes it across all test cases.

```go
func TestAdd(t *testing.T) {
    tests := []struct {
        name string
        a    int
        b    int
        want int
    }{
        {"positive numbers", 2, 3, 5},
        {"negative numbers", -2, -3, -5},
        {"mixed signs", -2, 3, 1},
        {"with zero", 0, 5, 5},
    }

    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            got := Add(tt.a, tt.b)
            if got != tt.want {
                t.Errorf("Add(%d, %d) = %d; want %d", tt.a, tt.b, got, tt.want)
            }
        })
    }
}
```

**Best Practices:**

1. **Use `t.Run()` for subtests** - Provides granular test output and allows running specific tests
2. **Avoid `t.Fatalf()` in table tests** - Use `t.Errorf()` so all test cases run
3. **Provide descriptive error messages** - Include both actual and expected values
4. **Name test cases clearly** - Makes failures immediately obvious
5. **Parallelize when appropriate** - Add `t.Parallel()` for independent tests

**Complexity Indicator:** If table tests become convoluted, it's a sign the function has too many dependencies or responsibilities.

### Test Coverage

```bash
# Run tests with coverage
go test -cover

# Generate detailed coverage report
go test -coverprofile=coverage.out
go tool cover -html=coverage.out
```

### Benchmark Tests

```go
func BenchmarkAdd(b *testing.B) {
    for i := 0; i < b.N; i++ {
        Add(2, 3)
    }
}
```

Run benchmarks: `go test -bench=.`

## Testing Bubbletea Applications

### Teatest Package (Official)

Teatest is an experimental testing library from Charm: `github.com/charmbracelet/x/exp/teatest`

**Installation:**

```bash
go get github.com/charmbracelet/x/exp/teatest@latest
```

**Important:** Teatest is experimental and has no backwards compatibility guarantees.

#### Pattern 1: Full Output Verification

Test complete application output against golden files:

```go
func TestFullOutput(t *testing.T) {
    m := initialModel(time.Second)
    tm := teatest.NewTestModel(
        t,
        m,
        teatest.WithInitialTermSize(300, 100),
    )

    out, err := io.ReadAll(tm.FinalOutput(t))
    if err != nil {
        t.Error(err)
    }

    teatest.RequireEqualOutput(t, out)
}
```

Golden files are stored in `testdata/` and updated with: `go test -v ./... -update`

**Best Practice:** Set consistent color profile to prevent CI failures:

```go
func init() {
    lipgloss.SetColorProfile(termenv.Ascii)
}
```

**Git Configuration:** Add to `.gitattributes` to prevent line-ending issues:

```gitattributes
*.golden -text
```

#### Pattern 2: Model State Testing

Assert against the final model instance after program completion:

```go
func TestModelState(t *testing.T) {
    tm := teatest.NewTestModel(t, initialModel())

    fm := tm.FinalModel(t)
    m, ok := fm.(model)
    if !ok {
        t.Fatal("unexpected model type")
    }

    if m.duration != time.Second {
        t.Errorf("duration = %v; want %v", m.duration, time.Second)
    }
}
```

#### Pattern 3: Interactive Testing

Test behavior during execution by sending messages and polling output:

```go
func TestInteractive(t *testing.T) {
    tm := teatest.NewTestModel(t, initialModel())

    // Wait for specific output
    teatest.WaitFor(
        t,
        tm.Output(),
        func(bts []byte) bool {
            return bytes.Contains(bts, []byte("expected text"))
        },
        teatest.WithCheckInterval(time.Millisecond*100),
        teatest.WithDuration(time.Second*3),
    )

    // Send user input
    tm.Send(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune("q")})

    // Wait for program to finish
    tm.WaitFinished(t, teatest.WithFinalTimeout(time.Second))
}
```

### Catwalk (Third-Party Alternative)

Catwalk is a unit test library for Bubbletea models: `github.com/knz/catwalk`

Key features:

- Verifies model state and View output as they process `tea.Msg` objects
- Built on top of `datadriven` (table-driven testing with data files)
- Contains both reference input and output in data files

### Testing Without Rendering

For pure unit tests, test the Update function directly:

```go
func TestUpdateOnKeyPress(t *testing.T) {
    m := initialModel()

    // Simulate key press
    updatedModel, cmd := m.Update(tea.KeyMsg{
        Type:  tea.KeyRunes,
        Runes: []rune("q"),
    })

    finalModel := updatedModel.(model)
    if !finalModel.quitting {
        t.Error("expected model to be quitting")
    }
}
```

### Testing tea.Cmd Side Effects

Commands can be tested by invoking them directly:

```go
func TestTickCommand(t *testing.T) {
    cmd := tick()

    // Execute command
    msg := cmd()

    // Assert message type
    if _, ok := msg.(tickMsg); !ok {
        t.Errorf("expected tickMsg, got %T", msg)
    }
}
```

For commands with dependencies, use dependency injection (see Mocking section).

## Mocking External Commands

### Pattern 1: Interface-Based Dependency Injection (Recommended)

The cleanest approach for application-level code:

```go
// Define interface
type CommandExecutor interface {
    Run(name string, args ...string) ([]byte, error)
}

// Production implementation
type RealExecutor struct{}

func (e *RealExecutor) Run(name string, args ...string) ([]byte, error) {
    return exec.Command(name, args...).Output()
}

// Mock implementation
type MockExecutor struct {
    Output []byte
    Err    error
}

func (e *MockExecutor) Run(name string, args ...string) ([]byte, error) {
    return e.Output, e.Err
}

// Usage in code
func ListSessions(executor CommandExecutor) ([]string, error) {
    output, err := executor.Run("tmux", "list-sessions")
    // ... process output
}

// Test
func TestListSessions(t *testing.T) {
    mock := &MockExecutor{
        Output: []byte("session1: 1 windows
session2: 2 windows
"),
        Err:    nil,
    }

    sessions, err := ListSessions(mock)
    if err != nil {
        t.Fatal(err)
    }

    if len(sessions) != 2 {
        t.Errorf("got %d sessions; want 2", len(sessions))
    }
}
```

**Benefits:**

- No magic or test helpers
- Clear dependency boundaries
- Easy to understand and maintain
- Works naturally with table-driven tests

### Pattern 2: Function Variable Wrapper

Replace `exec.Command` with a variable:

```go
// In production code
var execCommand = exec.Command

func runCommand(name string, args ...string) ([]byte, error) {
    return execCommand(name, args...).Output()
}

// In test code
func TestRunCommand(t *testing.T) {
    // Replace with mock
    execCommand = func(name string, args ...string) *exec.Cmd {
        return exec.Command("echo", "mocked output")
    }
    defer func() { execCommand = exec.Command }()

    output, err := runCommand("tmux", "list-sessions")
    // ... assertions
}
```

### Pattern 3: TestMain/TestHelper Pattern (From stdlib)

Used by Go's own `os/exec` tests. More complex but powerful:

```go
// Helper function that re-executes the test binary
func fakeExecCommand(command string, args ...string) *exec.Cmd {
    cs := []string{"-test.run=TestHelperProcess", "--", command}
    cs = append(cs, args...)
    cmd := exec.Command(os.Args[0], cs...)
    cmd.Env = []string{"GO_WANT_HELPER_PROCESS=1"}
    return cmd
}

func TestHelperProcess(t *testing.T) {
    if os.Getenv("GO_WANT_HELPER_PROCESS") != "1" {
        return
    }

    // Read command and args from os.Args
    args := os.Args
    for len(args) > 0 {
        if args[0] == "--" {
            args = args[1:]
            break
        }
        args = args[1:]
    }

    // Mock behavior based on command
    if args[0] == "tmux" && args[1] == "list-sessions" {
        fmt.Println("session1: 1 windows")
        fmt.Println("session2: 2 windows")
        os.Exit(0)
    }

    os.Exit(1)
}

// Usage
func TestListSessions(t *testing.T) {
    execCommand = fakeExecCommand
    defer func() { execCommand = exec.Command }()

    // Test code...
}
```

**Note:** This pattern is powerful but doesn't scale well for application-level code. Better suited for testing library code.

### Using Testify/Mock

For complex scenarios, testify provides mock generation:

```bash
go install github.com/vektra/mockery/v2@latest
```

```go
// Define interface
type CommandRunner interface {
    Run(cmd string, args ...string) (string, error)
}

// Generate mock: mockery --name=CommandRunner
// Use generated mock in tests

func TestWithMockery(t *testing.T) {
    mockRunner := new(MockCommandRunner)
    mockRunner.On("Run", "tmux", "list-sessions").
        Return("session1
session2
", nil)

    // Test code using mockRunner

    mockRunner.AssertExpectations(t)
}
```

**Recommendation:** For most Go code, hand-written mocks with interfaces are simpler and clearer. Use mockery for very complex mocking scenarios.

## Testing Best Practices

### Test File Organization

```text
mypackage/
├── session.go
├── session_test.go          # Unit tests
├── integration_test.go       # Integration tests
├── testdata/                 # Fixtures and golden files
│   ├── session-list.golden
│   └── fixtures/
└── test_helpers.go           # Shared test utilities
```

**Conventions:**

- `_test.go` suffix for test files
- Place tests in same package for white-box testing
- Use `package mypackage_test` for black-box testing
- `testdata/` directory for fixtures (ignored by `go build`)

### Test Helpers

Mark helper functions with `t.Helper()`:

```go
func assertSessionCount(t *testing.T, sessions []string, want int) {
    t.Helper()
    if got := len(sessions); got != want {
        t.Errorf("got %d sessions; want %d", got, want)
    }
}

func TestSessions(t *testing.T) {
    sessions := getSessions()
    assertSessionCount(t, sessions, 3) // Error shows line in TestSessions
}
```

### Golden File Testing

Golden files store expected test output:

```go
import "github.com/sebdah/goldie/v2"

func TestRenderOutput(t *testing.T) {
    g := goldie.New(t)

    output := renderComplexOutput()

    g.Assert(t, "render-output", output)
}
```

Update golden files: `go test -update ./...`

**Use Cases:**

- Large text output (JSON, XML, HTML)
- Complex string formatting
- Generated code
- Terminal output with ANSI codes

### Fixtures and Test Data

```go
// testdata/sessions.json
// testdata/config.yaml

func loadFixture(t *testing.T, name string) []byte {
    t.Helper()
    path := filepath.Join("testdata", name)
    data, err := os.ReadFile(path)
    if err != nil {
        t.Fatalf("failed to load fixture %s: %v", name, err)
    }
    return data
}

func TestWithFixture(t *testing.T) {
    data := loadFixture(t, "sessions.json")
    // Use fixture data in test
}
```

### Separating Unit and Integration Tests

Use build tags to separate test types:

```go
//go:build integration

package mypackage_test

import "testing"

func TestIntegration(t *testing.T) {
    if testing.Short() {
        t.Skip("skipping integration test")
    }
    // Integration test code
}
```

```bash
# Run only unit tests
go test -short ./...

# Run integration tests
go test -tags=integration ./...

# Run all tests
go test ./...
```

## CI/CD Integration

### GitHub Actions Workflow

```yaml
name: Test

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v4

    - name: Set up Go
      uses: actions/setup-go@v5
      with:
        go-version: '1.23'

    - name: Run tests
      run: go test -race -coverprofile=coverage.out -covermode=atomic ./...

    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v5
      with:
        file: ./coverage.out
        fail_ci_if_error: true
```

### Coverage Reporting with Codecov

**Setup:**

1. Sign up at [codecov.io](https://about.codecov.io/)
2. Add repository
3. For public repos, no token needed with Codecov v5
4. For private repos, add `CODECOV_TOKEN` to GitHub secrets

**Generate and view coverage locally:**

```bash
go test -coverprofile=coverage.out ./...
go tool cover -html=coverage.out
```

### Multiple Go Versions

```yaml
jobs:
  test:
    strategy:
      matrix:
        go-version: ['1.22', '1.23']
        os: [ubuntu-latest, macos-latest]

    runs-on: ${{ matrix.os }}

    steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-go@v5
      with:
        go-version: ${{ matrix.go-version }}
    - run: go test ./...
```

## Real-World Examples

### Lazygit's Integration Testing

Lazygit has evolved from manual regression testing to a sophisticated code-based integration test framework.

**Test Structure:**

```go
func TestCommit(t *testing.T) {
    NewTest(t).
        Setup(func(shell *Shell) {
            shell.CreateFile("file.txt", "content")
            shell.RunCommand("git add .")
        }).
        Run(func(t *TestDriver, keys config.KeybindingConfig) {
            t.Views().Commits().
                Focus().
                Lines(
                    Contains("Initial commit"),
                ).
                Press(keys.Universal.Select).
                Tap(func() {
                    t.Views().Main().Content(Contains("file.txt"))
                })
        })
}
```

**Running Tests:**

1. **CLI**: `go run cmd/integration_test/main.go cli [testname]`
2. **TUI**: `go run cmd/integration_test/main.go tui` (easiest)
3. **Go test**: `go test pkg/integration/clients/*.go` (for CI)

**Features:**

- Sandbox mode: Press 's' in TUI to run with manual control
- Slow motion: `--slow` flag or `INPUT_DELAY` env var
- Debugging: Press 'd' in TUI to attach debugger

**Best Practices:**

- Consolidate setup in shell portion
- Create shared helpers in `shared.go`
- Keep tests focused on single functionality
- Results stored in `test/_results/`

### Sesh Testing Approach

Sesh uses mockery for generating mocks of interfaces:

`.mockery.yaml`:

```yaml
# Mockery configuration for generating mocks
```

Tests follow standard Go patterns with interface-based dependency injection.

### Other Well-Tested Go TUI Projects

- **lazygit**: Comprehensive integration test framework with TUI runner
- **k9s**: Kubernetes TUI with extensive unit tests
- **lazydocker**: Docker TUI following similar patterns to lazygit
- **gitui**: Git TUI with focus on unit testability

## Summary: Testing Decision Tree

**For Bubbletea TUI Applications:**

1. **Unit test Update functions** - Test state transitions directly
2. **Use teatest for output verification** - Golden file testing for full renders
3. **Mock external commands** - Interface-based dependency injection
4. **Integration tests** - Lazygit-style framework for complex flows
5. **CI/CD** - GitHub Actions with coverage reporting

**Testing Levels:**

```text
Unit Tests (Fast)
├── Pure functions
├── Update function logic
├── Command functions with mocks
└── Business logic

Integration Tests (Slower)
├── Full TUI rendering (teatest)
├── External command integration
└── End-to-end workflows

CI/CD
├── Run all tests on PR
├── Coverage reporting
└── Multiple platforms/versions
```

**Key Takeaways:**

- Table-driven tests are the Go idiom
- Interface-based mocking is cleanest for most cases
- Teatest is official but experimental
- Lazygit's approach works well for complex TUIs
- Golden files excellent for complex output
- Separate unit and integration tests
- CI with coverage reporting is straightforward

## Additional Resources

- [Official Go Testing](https://pkg.go.dev/testing)
- [Table-Driven Tests Wiki](https://go.dev/wiki/TableDrivenTests)
- [Teatest Blog Post](https://charm.land/blog/teatest/)
- [Lazygit Integration Tests](https://github.com/jesseduffield/lazygit/blob/master/pkg/integration/README.md)
- [Testing os/exec](https://npf.io/2015/06/testing-exec-command/)
- [Golden Files](https://github.com/sebdah/goldie)
- [Codecov Go Guide](https://about.codecov.io/blog/getting-started-with-code-coverage-for-golang/)
