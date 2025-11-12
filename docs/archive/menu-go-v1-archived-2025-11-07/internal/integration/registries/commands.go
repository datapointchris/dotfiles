package registries

import (
	"context"
	"fmt"
	"strings"

	"github.com/ichrisbirch/menu/internal/integration"
	"github.com/ichrisbirch/menu/internal/registry"
)

// CommandsIntegration wraps the existing commands registry
type CommandsIntegration struct {
	loader *registry.Loader
	cache  []integration.Item
}

// NewCommandsIntegration creates a new commands integration
func NewCommandsIntegration(loader *registry.Loader) *CommandsIntegration {
	return &CommandsIntegration{
		loader: loader,
	}
}

// Name returns the integration name
func (c *CommandsIntegration) Name() string {
	return "commands"
}

// Type returns the integration type
func (c *CommandsIntegration) Type() integration.IntegrationType {
	return integration.TypeStatic
}

// Load fetches all commands from the registry
func (c *CommandsIntegration) Load(ctx context.Context) ([]integration.Item, error) {
	// Return cache if available
	if len(c.cache) > 0 {
		return c.cache, nil
	}

	commands, err := c.loader.LoadCommands()
	if err != nil {
		return nil, err
	}

	items := make([]integration.Item, len(commands))
	for i, cmd := range commands {
		items[i] = c.commandToItem(cmd)
	}

	c.cache = items
	return items, nil
}

// commandToItem converts a registry.Command to an integration.Item
func (c *CommandsIntegration) commandToItem(cmd registry.Command) integration.Item {
	// Convert examples to interface{} for Details
	examples := make([]interface{}, len(cmd.Examples))
	for i, ex := range cmd.Examples {
		examples[i] = map[string]interface{}{
			"command":     ex.Command,
			"description": ex.Description,
		}
	}

	// Determine icon based on type
	icon := "⚡"
	switch cmd.Type {
	case "function":
		icon = "ƒ"
	case "alias":
		icon = "→"
	case "system_tool":
		icon = "🔧"
	case "forgit_alias":
		icon = "🌿"
	}

	// Build details map
	details := map[string]interface{}{
		"type":    cmd.Type,
		"command": cmd.Command,
	}

	if len(examples) > 0 {
		details["examples"] = examples
	}

	if cmd.Notes != "" {
		details["notes"] = cmd.Notes
	}

	if len(cmd.Related) > 0 {
		details["related"] = cmd.Related
	}

	if cmd.ProvidedBy != "" {
		details["provided_by"] = cmd.ProvidedBy
	}

	// Determine if executable
	executable := true
	if cmd.Type == "alias" || cmd.Type == "function" {
		// These need to be run in current shell context
		executable = false
	}

	tags := cmd.Keywords
	if len(tags) == 0 {
		tags = []string{cmd.Type, cmd.Category}
	}

	return integration.Item{
		ID:          cmd.Name,
		Title:       cmd.Name,
		Description: cmd.Description,
		Category:    cmd.Category,
		Icon:        icon,
		Tags:        tags,
		Keywords:    cmd.Keywords,
		Source:      "commands",
		Executable:  executable,
		Command:     cmd.Command,
		IsInteractive: false,
		Details:     details,
	}
}

// Get retrieves a specific command by name
func (c *CommandsIntegration) Get(ctx context.Context, id string) (*integration.Item, error) {
	cmd, err := c.loader.FindCommand(id)
	if err != nil {
		return nil, err
	}

	if cmd == nil {
		return nil, fmt.Errorf("command %q not found", id)
	}

	item := c.commandToItem(*cmd)
	return &item, nil
}

// Search filters commands by query
func (c *CommandsIntegration) Search(ctx context.Context, query string) ([]integration.Item, error) {
	items, err := c.Load(ctx)
	if err != nil {
		return nil, err
	}

	query = strings.ToLower(query)
	filtered := make([]integration.Item, 0)

	for _, item := range items {
		if strings.Contains(strings.ToLower(item.Title), query) ||
			strings.Contains(strings.ToLower(item.Description), query) ||
			strings.Contains(strings.ToLower(item.Category), query) ||
			containsAny(item.Tags, query) ||
			containsAny(item.Keywords, query) {
			filtered = append(filtered, item)
		}
	}

	return filtered, nil
}

// Execute runs a command
func (c *CommandsIntegration) Execute(ctx context.Context, item integration.Item) (string, error) {
	if !item.Executable {
		return "", fmt.Errorf("command %q must be run in shell context (alias/function)", item.ID)
	}

	return item.Command, nil
}

// SupportsExecution indicates that some commands can be executed
func (c *CommandsIntegration) SupportsExecution() bool {
	return true
}

// Refresh reloads commands from registry
func (c *CommandsIntegration) Refresh(ctx context.Context) error {
	c.cache = nil
	_, err := c.Load(ctx)
	return err
}

// Helper function
func containsAny(slice []string, query string) bool {
	for _, s := range slice {
		if strings.Contains(strings.ToLower(s), query) {
			return true
		}
	}
	return false
}
