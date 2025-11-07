package registry

import (
	"fmt"
	"os"
	"path/filepath"

	"gopkg.in/yaml.v3"
)

// Loader handles loading YAML registries
type Loader struct {
	configDir string
}

// NewLoader creates a new registry loader
func NewLoader() *Loader {
	// Get config directory from environment or use default
	home, err := os.UserHomeDir()
	if err != nil {
		home = "."
	}

	configDir := filepath.Join(home, ".config", "menu", "registry")

	// Check if XDG_CONFIG_HOME is set
	if xdgConfig := os.Getenv("XDG_CONFIG_HOME"); xdgConfig != "" {
		configDir = filepath.Join(xdgConfig, "menu", "registry")
	}

	return &Loader{
		configDir: configDir,
	}
}

// NewLoaderWithPath creates a new registry loader with a custom path
// This is primarily used for testing
func NewLoaderWithPath(configDir string) *Loader {
	return &Loader{
		configDir: configDir,
	}
}

// LoadCommands loads all commands from commands.yml
func (l *Loader) LoadCommands() ([]Command, error) {
	filePath := filepath.Join(l.configDir, "commands.yml")

	data, err := os.ReadFile(filePath)
	if err != nil {
		return nil, fmt.Errorf("failed to read commands.yml: %w", err)
	}

	var registry CommandsRegistry
	if err := yaml.Unmarshal(data, &registry); err != nil {
		return nil, fmt.Errorf("failed to parse commands.yml: %w", err)
	}

	return registry.Commands, nil
}

// LoadWorkflows loads all workflows from workflows.yml
func (l *Loader) LoadWorkflows() ([]Workflow, error) {
	filePath := filepath.Join(l.configDir, "workflows.yml")

	data, err := os.ReadFile(filePath)
	if err != nil {
		return nil, fmt.Errorf("failed to read workflows.yml: %w", err)
	}

	var registry WorkflowsRegistry
	if err := yaml.Unmarshal(data, &registry); err != nil {
		return nil, fmt.Errorf("failed to parse workflows.yml: %w", err)
	}

	return registry.Workflows, nil
}

// LoadLearningTopics loads all learning topics from learning.yml
func (l *Loader) LoadLearningTopics() ([]LearningTopic, error) {
	filePath := filepath.Join(l.configDir, "learning.yml")

	data, err := os.ReadFile(filePath)
	if err != nil {
		return nil, fmt.Errorf("failed to read learning.yml: %w", err)
	}

	var registry LearningRegistry
	if err := yaml.Unmarshal(data, &registry); err != nil {
		return nil, fmt.Errorf("failed to parse learning.yml: %w", err)
	}

	return registry.Topics, nil
}

// FindCommand finds a specific command by name
func (l *Loader) FindCommand(name string) (*Command, error) {
	commands, err := l.LoadCommands()
	if err != nil {
		return nil, err
	}

	for _, cmd := range commands {
		if cmd.Name == name {
			return &cmd, nil
		}
	}

	return nil, fmt.Errorf("command %q not found", name)
}

// FindWorkflow finds a specific workflow by name
func (l *Loader) FindWorkflow(name string) (*Workflow, error) {
	workflows, err := l.LoadWorkflows()
	if err != nil {
		return nil, err
	}

	for _, wf := range workflows {
		if wf.Name == name {
			return &wf, nil
		}
	}

	return nil, fmt.Errorf("workflow %q not found", name)
}

// FindLearningTopic finds a specific learning topic by name
func (l *Loader) FindLearningTopic(name string) (*LearningTopic, error) {
	topics, err := l.LoadLearningTopics()
	if err != nil {
		return nil, err
	}

	for _, topic := range topics {
		if topic.Name == name {
			return &topic, nil
		}
	}

	return nil, fmt.Errorf("learning topic %q not found", name)
}
