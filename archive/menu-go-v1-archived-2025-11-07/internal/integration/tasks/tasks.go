package tasks

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"

	"github.com/ichrisbirch/menu/internal/integration"
	"gopkg.in/yaml.v3"
)

// TasksIntegration integrates with Taskfile (task.dev)
// Lists available tasks and allows execution
type TasksIntegration struct {
	taskfilePath string // Path to Taskfile.yml (or directory containing it)
	taskBinary   string // Path to task binary
}

// NewIntegration creates a new tasks integration
// If taskfilePath is empty, it will look for Taskfile.yml in current directory
func NewIntegration(taskfilePath, taskBinary string) *TasksIntegration {
	if taskBinary == "" {
		taskBinary = "task"
	}

	if taskfilePath == "" {
		// Look for Taskfile.yml in common locations
		candidates := []string{
			"Taskfile.yml",
			"taskfile.yml",
			"Taskfile.yaml",
		}

		for _, candidate := range candidates {
			if _, err := os.Stat(candidate); err == nil {
				taskfilePath = candidate
				break
			}
		}
	}

	return &TasksIntegration{
		taskfilePath: taskfilePath,
		taskBinary:   taskBinary,
	}
}

// Name returns the integration name
func (t *TasksIntegration) Name() string {
	return "tasks"
}

// Type returns the integration type
func (t *TasksIntegration) Type() integration.IntegrationType {
	return integration.TypeDynamic
}

// Load fetches all available tasks
func (t *TasksIntegration) Load(ctx context.Context) ([]integration.Item, error) {
	// Use "task --list" to get all tasks
	cmd := exec.CommandContext(ctx, t.taskBinary, "--list-all")

	// Set working directory if taskfilePath is a directory
	if t.taskfilePath != "" {
		dir := t.taskfilePath
		if !isDirectory(dir) {
			dir = filepath.Dir(dir)
		}
		cmd.Dir = dir
	}

	output, err := cmd.CombinedOutput()
	if err != nil {
		// If task binary doesn't exist or fails, try parsing Taskfile directly
		if t.taskfilePath != "" {
			return t.loadFromFile(ctx)
		}
		return []integration.Item{}, nil
	}

	return t.parseTasks(string(output)), nil
}

// loadFromFile parses Taskfile.yml directly
func (t *TasksIntegration) loadFromFile(ctx context.Context) ([]integration.Item, error) {
	if t.taskfilePath == "" {
		return []integration.Item{}, nil
	}

	filePath := t.taskfilePath
	if isDirectory(filePath) {
		filePath = filepath.Join(filePath, "Taskfile.yml")
	}

	data, err := os.ReadFile(filePath)
	if err != nil {
		return nil, fmt.Errorf("failed to read Taskfile: %w", err)
	}

	var taskfile struct {
		Tasks map[string]struct {
			Desc     string   `yaml:"desc"`
			Summary  string   `yaml:"summary"`
			Cmds     []interface{} `yaml:"cmds"`
			Deps     []string `yaml:"deps"`
			Sources  []string `yaml:"sources"`
			Generates []string `yaml:"generates"`
		} `yaml:"tasks"`
	}

	if err := yaml.Unmarshal(data, &taskfile); err != nil {
		return nil, fmt.Errorf("failed to parse Taskfile: %w", err)
	}

	items := make([]integration.Item, 0, len(taskfile.Tasks))

	for name, task := range taskfile.Tasks {
		description := task.Desc
		if description == "" {
			description = task.Summary
		}

		// Determine priority based on task name
		priority := 0
		if name == "default" {
			priority = 100
		} else if strings.Contains(name, "test") {
			priority = 50
		}

		details := map[string]interface{}{
			"commands": len(task.Cmds),
		}

		if len(task.Deps) > 0 {
			details["dependencies"] = task.Deps
		}

		if len(task.Sources) > 0 {
			details["sources"] = task.Sources
		}

		if len(task.Generates) > 0 {
			details["generates"] = task.Generates
		}

		items = append(items, integration.Item{
			ID:          name,
			Title:       name,
			Description: description,
			Category:    "Tasks",
			Icon:        "✓",
			Tags:        []string{"task", "build", "automation"},
			Status:      "available",
			Priority:    priority,
			Source:      "tasks",
			Executable:  true,
			Command:     fmt.Sprintf("task %s", name),
			IsInteractive: false,
			Details:     details,
		})
	}

	return items, nil
}

// parseTasks parses output from "task --list-all"
// Expected format: "task-name    Description of the task"
func (t *TasksIntegration) parseTasks(output string) []integration.Item {
	lines := strings.Split(strings.TrimSpace(output), "\n")
	items := make([]integration.Item, 0)

	for _, line := range lines {
		line = strings.TrimSpace(line)

		// Skip header lines
		if line == "" || strings.HasPrefix(line, "task:") || strings.HasPrefix(line, "---") {
			continue
		}

		item := t.parseTaskLine(line)
		if item.ID != "" {
			items = append(items, item)
		}
	}

	return items
}

// parseTaskLine parses a single line from task --list output
func (t *TasksIntegration) parseTaskLine(line string) integration.Item {
	// Split on multiple spaces to separate task name from description
	parts := strings.SplitN(line, "  ", 2)
	if len(parts) == 0 {
		return integration.Item{}
	}

	name := strings.TrimSpace(parts[0])
	if name == "" {
		return integration.Item{}
	}

	// Remove leading "* " if present
	name = strings.TrimPrefix(name, "* ")

	description := ""
	if len(parts) > 1 {
		description = strings.TrimSpace(parts[1])
	}

	// Determine priority
	priority := 0
	if name == "default" {
		priority = 100
	} else if strings.Contains(name, "test") {
		priority = 50
	}

	return integration.Item{
		ID:          name,
		Title:       name,
		Description: description,
		Category:    "Tasks",
		Icon:        "✓",
		Tags:        []string{"task", "build", "automation"},
		Status:      "available",
		Priority:    priority,
		Source:      "tasks",
		Executable:  true,
		Command:     fmt.Sprintf("task %s", name),
		IsInteractive: false,
	}
}

// Get retrieves a specific task by name
func (t *TasksIntegration) Get(ctx context.Context, id string) (*integration.Item, error) {
	items, err := t.Load(ctx)
	if err != nil {
		return nil, err
	}

	for _, item := range items {
		if item.ID == id {
			return &item, nil
		}
	}

	return nil, fmt.Errorf("task %q not found", id)
}

// Search filters tasks by query
func (t *TasksIntegration) Search(ctx context.Context, query string) ([]integration.Item, error) {
	items, err := t.Load(ctx)
	if err != nil {
		return nil, err
	}

	query = strings.ToLower(query)
	filtered := make([]integration.Item, 0)

	for _, item := range items {
		if strings.Contains(strings.ToLower(item.Title), query) ||
			strings.Contains(strings.ToLower(item.Description), query) {
			filtered = append(filtered, item)
		}
	}

	return filtered, nil
}

// Execute runs a task
func (t *TasksIntegration) Execute(ctx context.Context, item integration.Item) (string, error) {
	if !item.Executable {
		return "", fmt.Errorf("item %q is not executable", item.ID)
	}

	// Return the command to be executed by the caller
	return fmt.Sprintf("task %s", item.ID), nil
}

// SupportsExecution indicates that tasks can be executed
func (t *TasksIntegration) SupportsExecution() bool {
	return true
}

// Refresh reloads task data
func (t *TasksIntegration) Refresh(ctx context.Context) error {
	// Tasks are dynamic, so refresh is implicit on next Load
	return nil
}

// Helper function to check if path is a directory
func isDirectory(path string) bool {
	info, err := os.Stat(path)
	if err != nil {
		return false
	}
	return info.IsDir()
}
