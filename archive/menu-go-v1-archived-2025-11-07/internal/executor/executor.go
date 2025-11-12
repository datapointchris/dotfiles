package executor

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"strings"
	"time"

	"github.com/ichrisbirch/menu/internal/integration"
)

// Executor handles command execution with various modes
type Executor struct {
	shell string // Shell to use for command execution
}

// NewExecutor creates a new command executor
func NewExecutor() *Executor {
	shell := os.Getenv("SHELL")
	if shell == "" {
		shell = "/bin/bash"
	}

	return &Executor{
		shell: shell,
	}
}

// Execute runs a command and returns the result
func (e *Executor) Execute(ctx context.Context, command string, interactive bool) (*integration.ExecutionResult, error) {
	start := time.Now()

	if interactive {
		// For interactive commands, we need to run them in the user's terminal
		// Return a special result indicating this should be run externally
		return &integration.ExecutionResult{
			Success: true,
			Output:  fmt.Sprintf("Run this command in your terminal:\n%s", command),
			ExitCode: 0,
			Duration: time.Since(start).Milliseconds(),
		}, nil
	}

	// For non-interactive commands, execute them and capture output
	cmd := exec.CommandContext(ctx, e.shell, "-c", command)

	// Capture both stdout and stderr
	output, err := cmd.CombinedOutput()

	exitCode := 0
	if err != nil {
		if exitErr, ok := err.(*exec.ExitError); ok {
			exitCode = exitErr.ExitCode()
		}
	}

	success := err == nil

	return &integration.ExecutionResult{
		Success:  success,
		Output:   string(output),
		Error:    err,
		ExitCode: exitCode,
		Duration: time.Since(start).Milliseconds(),
	}, nil
}

// ExecuteItem executes an integration item
func (e *Executor) ExecuteItem(ctx context.Context, item integration.Item, integ integration.Integration) (*integration.ExecutionResult, error) {
	if !item.Executable {
		return nil, fmt.Errorf("item %q is not executable", item.Title)
	}

	// Get the command to execute from the integration
	command, err := integ.Execute(ctx, item)
	if err != nil {
		return nil, err
	}

	// Execute the command
	return e.Execute(ctx, command, item.IsInteractive)
}

// ValidateCommand checks if a command is safe to execute
// This is a basic safety check - extend as needed
func (e *Executor) ValidateCommand(command string) error {
	// Check for obviously dangerous commands
	dangerous := []string{
		"rm -rf /",
		"dd if=/dev/zero",
		"mkfs.",
		":(){ :|:& };:", // Fork bomb
	}

	cmdLower := strings.ToLower(strings.TrimSpace(command))

	for _, danger := range dangerous {
		if strings.Contains(cmdLower, danger) {
			return fmt.Errorf("command contains potentially dangerous pattern: %s", danger)
		}
	}

	return nil
}

// Format result for display
func FormatResult(result *integration.ExecutionResult) string {
	var b strings.Builder

	if result.Success {
		b.WriteString("✓ Success")
	} else {
		b.WriteString("✗ Failed")
	}

	b.WriteString(fmt.Sprintf(" (took %dms, exit code: %d)\n\n", result.Duration, result.ExitCode))

	if result.Output != "" {
		b.WriteString("Output:\n")
		b.WriteString(result.Output)
	}

	if result.Error != nil && result.Error.Error() != "exit status "+fmt.Sprint(result.ExitCode) {
		b.WriteString("\n\nError:\n")
		b.WriteString(result.Error.Error())
	}

	return b.String()
}
