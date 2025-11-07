# Testing Guide

This guide explains the testing infrastructure, patterns, and best practices used in the menu-go project.

## Test Coverage Overview

As of the latest implementation, the project has comprehensive test coverage:

| Package | Coverage | Test Files |
|---------|----------|------------|
| integration/registries | 84.0% | commands_test.go, workflows_test.go, learning_test.go |
| integration (manager) | 87.1% | manager_test.go |
| executor | 83.6% | executor_test.go |
| registry (loader) | 40.7% | loader_test.go |

**Total**: 35+ test functions with 80+ sub-tests, all passing.

## Test Infrastructure

### Directory Structure

```
internal/
├── testutil/                    # Shared test utilities
│   ├── fixtures.go             # Sample data for testing
│   └── helpers.go              # Assertion helpers
├── integration/
│   ├── manager_test.go         # Manager tests
│   ├── testhelpers.go          # Integration-specific helpers
│   └── registries/
│       ├── commands_test.go    # Commands integration tests
│       ├── workflows_test.go   # Workflows integration tests
│       └── learning_test.go    # Learning integration tests
├── executor/
│   └── executor_test.go        # Executor tests
└── registry/
    └── loader_test.go          # Registry loader tests
```

### Test Utilities Package

The `internal/testutil` package provides shared testing infrastructure.

#### Fixtures (`fixtures.go`)

Fixtures generate sample YAML data for testing:

```go
// Sample commands YAML with 3 commands (ls, ll, gitlog)
func SampleCommandsYAML() string {
    return `commands:
  - name: "ls"
    type: "system_tool"
    category: "File Operations"
    description: "List directory contents"
    keywords: ["list", "files", "directory"]
    command: "ls -la"
    platform: "all"
  # ... more commands
`
}

// Sample workflows YAML
func SampleWorkflowsYAML() string { /* ... */ }

// Sample learning topics YAML
func SampleLearningYAML() string { /* ... */ }
```

**Usage:**

```go
func TestCommandsIntegration_Load(t *testing.T) {
    // Create temp directory
    tmpDir := testutil.CreateTempDir(t)
    commandsFile := filepath.Join(tmpDir, "commands.yml")

    // Write sample YAML
    err := testutil.WriteYAMLFile(commandsFile, testutil.SampleCommandsYAML())
    testutil.AssertNoError(t, err)

    // Now test loading
    items, err := loadCommands(commandsFile)
    testutil.AssertNoError(t, err)
}
```

#### Helper Functions (`helpers.go`)

Generic assertion helpers for cleaner tests:

```go
// AssertNoError fails test if err is not nil
func AssertNoError(t *testing.T, err error) {
    t.Helper()  // Marks this as a helper function
    if err != nil {
        t.Fatalf("unexpected error: %v", err)
    }
}

// AssertEqual fails if expected != actual
func AssertEqual(t *testing.T, expected, actual interface{}) {
    t.Helper()
    if expected != actual {
        t.Fatalf("expected %v, got %v", expected, actual)
    }
}

// AssertTrue fails if condition is false
func AssertTrue(t *testing.T, condition bool, message string) {
    t.Helper()
    if !condition {
        t.Fatalf("assertion failed: %s", message)
    }
}
```

**Why `t.Helper()`?**

Marks the function as a helper, so test failures report the caller's location, not the helper's location:

```go
// Without t.Helper():
// helpers.go:25: expected 3, got 2

// With t.Helper():
// commands_test.go:42: expected 3, got 2
```

### Integration-Specific Helpers

Some helpers are specific to integration testing and live in `internal/integration/testhelpers.go`:

```go
// AssertItemsCount checks if slice has expected length
func AssertItemsCount(t *testing.T, items []Item, expected int) {
    t.Helper()
    if len(items) != expected {
        t.Fatalf("expected %d items, got %d", expected, len(items))
    }
}

// AssertItemHasField checks if item has expected field value
func AssertItemHasField(t *testing.T, item Item, field string, value interface{}) {
    t.Helper()
    // Uses reflection to check field values
    // ...
}
```

**Why separate file?**

To avoid import cycles: `testutil` can't import `integration`, but `integration/testhelpers.go` can import `integration` types.

### Mock Integrations

The test infrastructure includes a mock integration for testing the manager:

```go
// MockIntegration implements Integration interface for testing
type MockIntegration struct {
    NameVal              string
    TypeVal              IntegrationType
    LoadFunc             func(ctx context.Context) ([]Item, error)
    GetFunc              func(ctx context.Context, id string) (*Item, error)
    SearchFunc           func(ctx context.Context, query string) ([]Item, error)
    ExecuteFunc          func(ctx context.Context, item Item) (string, error)
    SupportsExecutionVal bool
    RefreshFunc          func(ctx context.Context) error
}

func (m *MockIntegration) Name() string { return m.NameVal }
func (m *MockIntegration) Type() IntegrationType { return m.TypeVal }
func (m *MockIntegration) Load(ctx context.Context) ([]Item, error) {
    if m.LoadFunc != nil {
        return m.LoadFunc(ctx)
    }
    return []Item{}, nil
}
// ... other interface methods
```

**Usage:**

```go
func TestManager_LoadAll(t *testing.T) {
    manager := NewManager(nil)

    // Create mock with custom behavior
    mock1 := &MockIntegration{
        NameVal: "test1",
        TypeVal: TypeStatic,
        LoadFunc: func(ctx context.Context) ([]Item, error) {
            return []Item{
                {ID: "item1", Title: "Item 1"},
                {ID: "item2", Title: "Item 2"},
            }, nil
        },
    }

    manager.Register(mock1)

    // Test
    results, err := manager.LoadAll(ctx)
    testutil.AssertNoError(t, err)
    testutil.AssertEqual(t, 2, len(results["test1"]))
}
```

## Go Testing Patterns

### 1. Table-Driven Tests

Table-driven tests allow testing multiple scenarios with minimal code duplication:

```go
func TestExecutor_ValidateCommand(t *testing.T) {
    exec := NewExecutor()

    tests := []struct {
        name      string
        command   string
        shouldErr bool
    }{
        {"Safe command", "ls -la", false},
        {"Safe git command", "git status", false},
        {"Dangerous rm -rf /", "rm -rf /", true},
        {"Dangerous dd", "dd if=/dev/zero of=/dev/sda", true},
        {"Dangerous mkfs", "mkfs.ext4 /dev/sda", true},
        {"Fork bomb", ":(){ :|:& };:", true},
        {"Safe rm", "rm file.txt", false},
    }

    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            err := exec.ValidateCommand(tt.command)
            if tt.shouldErr {
                testutil.AssertError(t, err)
            } else {
                testutil.AssertNoError(t, err)
            }
        })
    }
}
```

**Benefits:**

- Easy to add new test cases (just add to table)
- Each test case runs independently (using `t.Run`)
- Clear separation of test data from test logic
- Great readability (test cases as documentation)

**Pattern structure:**

```go
// 1. Define test structure
tests := []struct {
    name     string  // Test case name
    input    T       // Input data
    expected U       // Expected output
}{
    {"case 1", input1, expected1},
    {"case 2", input2, expected2},
}

// 2. Iterate and run sub-tests
for _, tt := range tests {
    t.Run(tt.name, func(t *testing.T) {
        // Test using tt.input and tt.expected
    })
}
```

### 2. Using t.TempDir() for Temporary Directories

Go 1.15+ provides `t.TempDir()` for automatic cleanup:

```go
func TestCommandsIntegration_Load(t *testing.T) {
    // Create temp directory - automatically cleaned up after test
    tmpDir := testutil.CreateTempDir(t)

    registryDir := filepath.Join(tmpDir, ".config", "menu", "registry")
    commandsFile := filepath.Join(registryDir, "commands.yml")

    // Write test data
    err := testutil.WriteYAMLFile(commandsFile, testutil.SampleCommandsYAML())
    testutil.AssertNoError(t, err)

    // Test with temp files
    // ...
}
// tmpDir is automatically deleted when test finishes
```

**Why use temp directories?**

- Isolates tests (no shared state between tests)
- Automatic cleanup (no manual `defer os.RemoveAll`)
- Prevents test pollution
- Safe parallel execution

### 3. Context Usage

Use `context.Background()` for tests:

```go
func TestManager_LoadAll(t *testing.T) {
    manager := NewManager(nil)
    // ...

    ctx := context.Background()
    results, err := manager.LoadAll(ctx)

    testutil.AssertNoError(t, err)
}
```

**Why context.Background()?**

- Tests don't need cancellation (they're fast)
- Satisfies interface requirements
- Could be enhanced to test timeouts:

```go
// Test timeout behavior
ctx, cancel := context.WithTimeout(context.Background(), 100*time.Millisecond)
defer cancel()
_, err := slowOperation(ctx)
// Expect error after 100ms
```

### 4. Subtests with t.Run

Subtests provide better test organization and granular control:

```go
func TestWorkflowsIntegration_Search(t *testing.T) {
    // Setup once
    integ := setupWorkflowsIntegration(t)

    tests := []struct {
        name     string
        query    string
        expected int
    }{
        {"Search git", "git", 1},
        {"Search vim", "vim", 1},
        {"No results", "docker", 0},
    }

    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            items, err := integ.Search(ctx, tt.query)
            testutil.AssertNoError(t, err)
            integration.AssertItemsCount(t, items, tt.expected)
        })
    }
}
```

**Benefits:**

- Run specific subtest: `go test -run TestWorkflowsIntegration_Search/Search_git`
- Clear test output showing which subtest failed
- Can run subtests in parallel with `t.Parallel()`

### 5. Testing Error Paths

Always test both success and failure paths:

```go
func TestManager_Register(t *testing.T) {
    manager := NewManager(nil)
    mockInteg := &MockIntegration{NameVal: "test"}

    // Test successful registration
    err := manager.Register(mockInteg)
    testutil.AssertNoError(t, err)

    // Test duplicate registration (error path)
    err = manager.Register(mockInteg)
    testutil.AssertError(t, err)

    // Test nil integration (error path)
    err = manager.Register(nil)
    testutil.AssertError(t, err)

    // Test empty name integration (error path)
    emptyInteg := &MockIntegration{NameVal: ""}
    err = manager.Register(emptyInteg)
    testutil.AssertError(t, err)
}
```

**Why test error paths?**

- Ensures error handling works correctly
- Catches panics and crashes
- Verifies error messages are helpful
- Tests "unhappy path" scenarios

## Integration Testing

### Testing with Real Files

Integration tests use real YAML files in temp directories:

```go
func TestCommandsIntegration_Load(t *testing.T) {
    // Create temp directory structure
    tmpDir := testutil.CreateTempDir(t)
    registryDir := filepath.Join(tmpDir, ".config", "menu", "registry")
    commandsFile := filepath.Join(registryDir, "commands.yml")

    // Write sample YAML
    err := testutil.WriteYAMLFile(commandsFile, testutil.SampleCommandsYAML())
    testutil.AssertNoError(t, err)

    // Create loader pointing to temp directory
    loader := registry.NewLoaderWithPath(registryDir)
    integ := NewCommandsIntegration(loader)

    // Test actual loading
    ctx := context.Background()
    items, err := integ.Load(ctx)

    // Verify results
    testutil.AssertNoError(t, err)
    integration.AssertItemsCount(t, items, 3) // ls, ll, gitlog
}
```

**This tests:**

- YAML parsing
- File I/O
- Directory structure handling
- Actual integration behavior

### Testing Command Execution

Executor tests run real commands:

```go
func TestExecutor_Execute_NonInteractive(t *testing.T) {
    exec := NewExecutor()
    ctx := context.Background()

    // Test simple command that should succeed
    result, err := exec.Execute(ctx, "echo 'hello world'", false)

    testutil.AssertNoError(t, err)
    testutil.AssertTrue(t, result.Success, "command should succeed")
    testutil.AssertEqual(t, 0, result.ExitCode)
    testutil.AssertTrue(t, strings.Contains(result.Output, "hello world"))
}
```

**Safety considerations:**

- Only run safe commands (`echo`, `ls`, etc.)
- Never run destructive commands in tests
- Use test fixtures, not real files
- Run in isolated temp directories

## Running Tests

### Run All Tests

```bash
go test ./...
```

### Run with Verbose Output

```bash
go test -v ./...
```

### Run Specific Package

```bash
go test ./internal/integration/registries
```

### Run Specific Test

```bash
go test -run TestCommandsIntegration_Load ./internal/integration/registries
```

### Run Specific Subtest

```bash
go test -run TestWorkflowsIntegration_Search/Search_git ./internal/integration/registries
```

### Generate Coverage Report

```bash
# Generate coverage profile
go test -coverprofile=coverage.out ./...

# View coverage in terminal
go tool cover -func=coverage.out

# View coverage in browser
go tool cover -html=coverage.out
```

### Run Tests in Parallel

```bash
# Run tests in parallel across packages
go test -parallel 4 ./...
```

## Best Practices

### 1. Test One Thing Per Test

```go
// Good: Tests one specific scenario
func TestManager_Register_Success(t *testing.T) {
    manager := NewManager(nil)
    mockInteg := &MockIntegration{NameVal: "test"}

    err := manager.Register(mockInteg)

    testutil.AssertNoError(t, err)
}

// Good: Tests one specific error case
func TestManager_Register_Duplicate(t *testing.T) {
    manager := NewManager(nil)
    mockInteg := &MockIntegration{NameVal: "test"}

    manager.Register(mockInteg)
    err := manager.Register(mockInteg)

    testutil.AssertError(t, err)
}
```

### 2. Use Descriptive Test Names

```go
// Good: Clearly describes what's being tested
func TestExecutor_Execute_CommandFailure(t *testing.T) { /* ... */ }
func TestExecutor_ValidateCommand_DangerousRmRf(t *testing.T) { /* ... */ }
func TestManager_LoadAll_ConcurrentIntegrations(t *testing.T) { /* ... */ }

// Bad: Unclear what's being tested
func TestExecutor1(t *testing.T) { /* ... */ }
func TestManagerTest(t *testing.T) { /* ... */ }
```

**Convention:** `Test<Type>_<Method>_<Scenario>`

### 3. Use Helpers for Common Assertions

```go
// Instead of repeating:
if err != nil {
    t.Fatalf("unexpected error: %v", err)
}
if len(items) != 3 {
    t.Fatalf("expected 3 items, got %d", len(items))
}

// Use helpers:
testutil.AssertNoError(t, err)
integration.AssertItemsCount(t, items, 3)
```

### 4. Clean Up Test Data

```go
// Good: Automatic cleanup with t.TempDir()
tmpDir := t.TempDir()

// Good: Explicit cleanup with defer
f, err := os.Create("test.txt")
if err != nil {
    t.Fatal(err)
}
defer os.Remove("test.txt")  // Cleanup even if test fails
defer f.Close()

// Bad: No cleanup (leaves test artifacts)
os.WriteFile("test.txt", data, 0644)
// ... test ...
// File remains after test
```

### 5. Test Edge Cases

```go
func TestFilterItems(t *testing.T) {
    items := []Item{
        {ID: "1", Title: "Go Testing"},
        {ID: "2", Title: "Docker Basics"},
    }

    tests := []struct {
        name     string
        filter   Filter
        expected int
    }{
        {"No filter", Filter{}, 2},              // Edge: Empty filter
        {"Filter by query", Filter{Query: "go"}, 1},
        {"No matches", Filter{Query: "xyz"}, 0},  // Edge: No results
        {"Case insensitive", Filter{Query: "GO"}, 1}, // Edge: Case handling
    }

    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            filtered := FilterItems(items, tt.filter)
            testutil.AssertEqual(t, tt.expected, len(filtered))
        })
    }
}
```

## Common Testing Challenges

### 1. Testing Concurrent Code

The manager's LoadAll method runs integrations concurrently. Testing this:

```go
func TestManager_LoadAll(t *testing.T) {
    manager := NewManager(nil)

    // Create multiple mock integrations
    for i := 0; i < 5; i++ {
        name := fmt.Sprintf("test%d", i)
        mockInteg := &MockIntegration{
            NameVal: name,
            TypeVal: TypeStatic,
            LoadFunc: func(ctx context.Context) ([]Item, error) {
                // Simulate some work
                time.Sleep(10 * time.Millisecond)
                return []Item{{ID: "item1"}}, nil
            },
        }
        manager.Register(mockInteg)
    }

    // LoadAll runs all integrations concurrently
    start := time.Now()
    results, err := manager.LoadAll(context.Background())
    duration := time.Since(start)

    // Verify all loaded
    testutil.AssertNoError(t, err)
    testutil.AssertEqual(t, 5, len(results))

    // Verify they ran concurrently (not sequentially)
    // If sequential: 5 * 10ms = 50ms
    // If concurrent: ~10ms
    if duration > 30*time.Millisecond {
        t.Errorf("LoadAll took too long, might not be concurrent: %v", duration)
    }
}
```

### 2. Testing External Dependencies

For integrations that depend on external binaries (session, nb, buku):

**Option 1: Skip if not available**

```go
func TestSessionsIntegration_Load(t *testing.T) {
    // Check if session binary is available
    if _, err := exec.LookPath("session"); err != nil {
        t.Skip("session binary not available")
    }

    // Run test
    items, err := loadSessions()
    testutil.AssertNoError(t, err)
}
```

**Option 2: Mock the integration**

```go
func TestManager_LoadAll_WithExternal(t *testing.T) {
    manager := NewManager(nil)

    // Use mock instead of real external integration
    mockSessions := &MockIntegration{
        NameVal: "sessions",
        LoadFunc: func(ctx context.Context) ([]Item, error) {
            return []Item{
                {ID: "session1", Title: "Session 1"},
            }, nil
        },
    }

    manager.Register(mockSessions)

    results, err := manager.LoadAll(context.Background())
    testutil.AssertNoError(t, err)
    testutil.AssertEqual(t, 1, len(results["sessions"]))
}
```

## Future Testing Enhancements

1. **Race Detection**: Run tests with `-race` flag to detect data races
2. **Benchmark Tests**: Add benchmarks for performance-critical paths
3. **Integration Tests**: End-to-end tests with real UI
4. **Fuzz Testing**: Fuzz YAML parsing and command validation
5. **CI/CD Integration**: Run tests automatically on commits

## Related Files

- `internal/testutil/` - Shared test infrastructure
- `internal/integration/testhelpers.go` - Integration-specific helpers
- `*_test.go` - All test files

## See Also

- [Integration System](../development/integration-system.md) - Architecture being tested
- [Architecture Overview](../architecture/overview.md) - System design
