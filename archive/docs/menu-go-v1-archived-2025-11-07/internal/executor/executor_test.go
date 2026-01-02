package executor

import (
	"context"
	"fmt"
	"strings"
	"testing"

	"github.com/ichrisbirch/menu/internal/integration"
	"github.com/ichrisbirch/menu/internal/testutil"
)

func TestNewExecutor(t *testing.T) {
	exec := NewExecutor()
	testutil.AssertTrue(t, exec != nil, "executor should not be nil")
	testutil.AssertTrue(t, exec.shell != "", "shell should be set")
}

func TestExecutor_Execute_NonInteractive(t *testing.T) {
	exec := NewExecutor()
	ctx := context.Background()

	// Test simple command that should succeed
	result, err := exec.Execute(ctx, "echo 'hello world'", false)
	testutil.AssertNoError(t, err)
	testutil.AssertTrue(t, result.Success, "command should succeed")
	testutil.AssertEqual(t, 0, result.ExitCode)
	testutil.AssertTrue(t, strings.Contains(result.Output, "hello world"), "output should contain 'hello world'")
	testutil.AssertTrue(t, result.Duration > 0, "duration should be greater than 0")
}

func TestExecutor_Execute_Interactive(t *testing.T) {
	exec := NewExecutor()
	ctx := context.Background()

	// Test interactive command (should return special message)
	result, err := exec.Execute(ctx, "vim file.txt", true)
	testutil.AssertNoError(t, err)
	testutil.AssertTrue(t, result.Success, "should succeed")
	testutil.AssertEqual(t, 0, result.ExitCode)
	testutil.AssertTrue(t, strings.Contains(result.Output, "Run this command in your terminal"),
		"should contain interactive message")
	testutil.AssertTrue(t, strings.Contains(result.Output, "vim file.txt"),
		"should contain the command")
}

func TestExecutor_Execute_CommandFailure(t *testing.T) {
	exec := NewExecutor()
	ctx := context.Background()

	// Test command that should fail
	result, err := exec.Execute(ctx, "exit 1", false)
	testutil.AssertNoError(t, err) // Execute itself shouldn't error
	testutil.AssertFalse(t, result.Success, "command should fail")
	testutil.AssertEqual(t, 1, result.ExitCode)
	testutil.AssertTrue(t, result.Error != nil, "error should be set")
}

func TestExecutor_Execute_InvalidCommand(t *testing.T) {
	exec := NewExecutor()
	ctx := context.Background()

	// Test invalid command
	result, err := exec.Execute(ctx, "nonexistentcommand12345", false)
	testutil.AssertNoError(t, err) // Execute itself shouldn't error
	testutil.AssertFalse(t, result.Success, "command should fail")
	testutil.AssertTrue(t, result.ExitCode != 0, "exit code should be non-zero")
}

func TestExecutor_ValidateCommand(t *testing.T) {
	exec := NewExecutor()

	tests := []struct {
		name      string
		command   string
		shouldErr bool
	}{
		{
			name:      "Safe command",
			command:   "ls -la",
			shouldErr: false,
		},
		{
			name:      "Safe git command",
			command:   "git status",
			shouldErr: false,
		},
		{
			name:      "Dangerous rm -rf /",
			command:   "rm -rf /",
			shouldErr: true,
		},
		{
			name:      "Dangerous dd",
			command:   "dd if=/dev/zero of=/dev/sda",
			shouldErr: true,
		},
		{
			name:      "Dangerous mkfs",
			command:   "mkfs.ext4 /dev/sda",
			shouldErr: true,
		},
		{
			name:      "Fork bomb",
			command:   ":(){ :|:& };:",
			shouldErr: true,
		},
		{
			name:      "Safe rm",
			command:   "rm file.txt",
			shouldErr: false,
		},
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

func TestFormatResult(t *testing.T) {
	tests := []struct {
		name   string
		result *integration.ExecutionResult
	}{
		{
			name: "Successful execution",
			result: &integration.ExecutionResult{
				Success:  true,
				Output:   "command output",
				ExitCode: 0,
				Duration: 100,
			},
		},
		{
			name: "Failed execution",
			result: &integration.ExecutionResult{
				Success:  false,
				Output:   "error output",
				ExitCode: 1,
				Duration: 50,
				Error:    fmt.Errorf("command failed"),
			},
		},
		{
			name: "Empty output",
			result: &integration.ExecutionResult{
				Success:  true,
				Output:   "",
				ExitCode: 0,
				Duration: 10,
			},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			formatted := FormatResult(tt.result)

			// Check that formatted output contains expected elements
			if tt.result.Success {
				testutil.AssertTrue(t, strings.Contains(formatted, "Success") ||
					strings.Contains(formatted, "✓"), "should indicate success")
			} else {
				testutil.AssertTrue(t, strings.Contains(formatted, "Failed") ||
					strings.Contains(formatted, "✗"), "should indicate failure")
			}

			// Should contain timing info
			testutil.AssertTrue(t, strings.Contains(formatted, "ms"), "should contain duration")

			// Should contain output if present
			if tt.result.Output != "" {
				testutil.AssertTrue(t, strings.Contains(formatted, tt.result.Output),
					"should contain output")
			}
		})
	}
}

func TestExecutor_ExecuteItem(t *testing.T) {
	exec := NewExecutor()
	ctx := context.Background()

	// Create a mock integration that returns a command
	mockInteg := &integration.MockIntegration{
		NameVal: "test",
		TypeVal: integration.TypeStatic,
		ExecuteFunc: func(ctx context.Context, item integration.Item) (string, error) {
			return "echo 'test output'", nil
		},
		SupportsExecutionVal: true,
	}

	// Test executing an item
	item := integration.Item{
		ID:         "test-item",
		Title:      "Test Item",
		Executable: true,
		Source:     "test",
	}

	result, err := exec.ExecuteItem(ctx, item, mockInteg)
	testutil.AssertNoError(t, err)
	testutil.AssertTrue(t, result.Success, "execution should succeed")
	testutil.AssertTrue(t, strings.Contains(result.Output, "test output"),
		"output should contain expected text")
}

func TestExecutor_ExecuteItem_NonExecutable(t *testing.T) {
	exec := NewExecutor()
	ctx := context.Background()

	mockInteg := &integration.MockIntegration{
		NameVal:              "test",
		TypeVal:              integration.TypeStatic,
		SupportsExecutionVal: false,
	}

	// Test executing a non-executable item
	item := integration.Item{
		ID:         "test-item",
		Title:      "Test Item",
		Executable: false,
		Source:     "test",
	}

	_, err := exec.ExecuteItem(ctx, item, mockInteg)
	testutil.AssertError(t, err) // Should fail because item is not executable
}

func TestExecutor_MultilineOutput(t *testing.T) {
	exec := NewExecutor()
	ctx := context.Background()

	// Test command with multiline output
	result, err := exec.Execute(ctx, "echo 'line1'; echo 'line2'; echo 'line3'", false)
	testutil.AssertNoError(t, err)
	testutil.AssertTrue(t, result.Success, "command should succeed")
	testutil.AssertTrue(t, strings.Contains(result.Output, "line1"), "should contain line1")
	testutil.AssertTrue(t, strings.Contains(result.Output, "line2"), "should contain line2")
	testutil.AssertTrue(t, strings.Contains(result.Output, "line3"), "should contain line3")
}
