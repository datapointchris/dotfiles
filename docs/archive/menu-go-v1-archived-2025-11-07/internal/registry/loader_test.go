package registry

import (
	"os"
	"path/filepath"
	"testing"
)

// TestLoadCommands tests loading commands from a test YAML file
func TestLoadCommands(t *testing.T) {
	// Create a temporary test file
	tmpDir := t.TempDir()
	testFile := filepath.Join(tmpDir, "commands.yml")

	// Create test YAML content
	testYAML := `commands:
  - name: test-cmd
    type: function
    category: Test Category
    description: A test command
    keywords: [test, example]
    command: test-cmd [args]
    platform: all
`

	// Write test file
	if err := os.WriteFile(testFile, []byte(testYAML), 0644); err != nil {
		t.Fatalf("Failed to write test file: %v", err)
	}

	// Create loader with test directory
	loader := &Loader{
		configDir: tmpDir,
	}

	// Load commands
	commands, err := loader.LoadCommands()
	if err != nil {
		t.Fatalf("LoadCommands() returned error: %v", err)
	}

	// Verify we got exactly one command
	if len(commands) != 1 {
		t.Fatalf("Expected 1 command, got %d", len(commands))
	}

	// Verify command fields
	cmd := commands[0]
	if cmd.Name != "test-cmd" {
		t.Errorf("Expected name 'test-cmd', got %q", cmd.Name)
	}
	if cmd.Type != "function" {
		t.Errorf("Expected type 'function', got %q", cmd.Type)
	}
	if cmd.Description != "A test command" {
		t.Errorf("Expected description 'A test command', got %q", cmd.Description)
	}
}

// TestLoadWorkflows tests loading workflows
func TestLoadWorkflows(t *testing.T) {
	tmpDir := t.TempDir()
	testFile := filepath.Join(tmpDir, "workflows.yml")

	testYAML := `workflows:
  - name: Test Workflow
    category: Test Category
    description: A test workflow
    keywords: [test, workflow]
    steps:
      - key: "step1"
        description: "First step"
      - key: "step2"
        description: "Second step"
    platform: all
`

	if err := os.WriteFile(testFile, []byte(testYAML), 0644); err != nil {
		t.Fatalf("Failed to write test file: %v", err)
	}

	loader := &Loader{configDir: tmpDir}
	workflows, err := loader.LoadWorkflows()
	if err != nil {
		t.Fatalf("LoadWorkflows() returned error: %v", err)
	}

	if len(workflows) != 1 {
		t.Fatalf("Expected 1 workflow, got %d", len(workflows))
	}

	wf := workflows[0]
	if wf.Name != "Test Workflow" {
		t.Errorf("Expected name 'Test Workflow', got %q", wf.Name)
	}
	if len(wf.Steps) != 2 {
		t.Errorf("Expected 2 steps, got %d", len(wf.Steps))
	}
}

// TestLoadLearningTopics tests loading learning topics
func TestLoadLearningTopics(t *testing.T) {
	tmpDir := t.TempDir()
	testFile := filepath.Join(tmpDir, "learning.yml")

	testYAML := `learning:
  - name: Test Topic
    category: Learning Topics
    status: active
    description: A test learning topic
    keywords: [test, learning]
    progress:
      started: "2025-11-06"
      last_practiced: null
      confidence: beginner
    platform: all
`

	if err := os.WriteFile(testFile, []byte(testYAML), 0644); err != nil {
		t.Fatalf("Failed to write test file: %v", err)
	}

	loader := &Loader{configDir: tmpDir}
	topics, err := loader.LoadLearningTopics()
	if err != nil {
		t.Fatalf("LoadLearningTopics() returned error: %v", err)
	}

	if len(topics) != 1 {
		t.Fatalf("Expected 1 topic, got %d", len(topics))
	}

	topic := topics[0]
	if topic.Name != "Test Topic" {
		t.Errorf("Expected name 'Test Topic', got %q", topic.Name)
	}
	if topic.Status != "active" {
		t.Errorf("Expected status 'active', got %q", topic.Status)
	}
	if topic.Progress.Confidence != "beginner" {
		t.Errorf("Expected confidence 'beginner', got %q", topic.Progress.Confidence)
	}
}

// TestFindCommand tests finding a specific command
func TestFindCommand(t *testing.T) {
	tmpDir := t.TempDir()
	testFile := filepath.Join(tmpDir, "commands.yml")

	testYAML := `commands:
  - name: cmd1
    type: alias
    category: Test
    description: First command
    command: echo 1
    platform: all
  - name: cmd2
    type: function
    category: Test
    description: Second command
    command: echo 2
    platform: all
`

	if err := os.WriteFile(testFile, []byte(testYAML), 0644); err != nil {
		t.Fatalf("Failed to write test file: %v", err)
	}

	loader := &Loader{configDir: tmpDir}

	// Find existing command
	cmd, err := loader.FindCommand("cmd2")
	if err != nil {
		t.Fatalf("FindCommand() returned error: %v", err)
	}
	if cmd.Name != "cmd2" {
		t.Errorf("Expected name 'cmd2', got %q", cmd.Name)
	}

	// Try to find non-existent command
	_, err = loader.FindCommand("nonexistent")
	if err == nil {
		t.Error("Expected error for non-existent command, got nil")
	}
}
