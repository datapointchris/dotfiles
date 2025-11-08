package tools

import (
	"context"
	"fmt"
	"os"
	"strings"

	"github.com/ichrisbirch/menu/internal/integration"
	"gopkg.in/yaml.v3"
)

// ToolsIntegration provides access to the tools registry
// This is a static integration that reads from docs/tools/registry.yml
type ToolsIntegration struct {
	registryPath string
	cache        []integration.Item
}

// NewIntegration creates a new tools integration
func NewIntegration(registryPath string) *ToolsIntegration {
	return &ToolsIntegration{
		registryPath: registryPath,
	}
}

// Name returns the integration name
func (t *ToolsIntegration) Name() string {
	return "tools"
}

// Type returns the integration type
func (t *ToolsIntegration) Type() integration.IntegrationType {
	return integration.TypeStatic
}

// Tool represents a tool from the registry
type Tool struct {
	Category     string   `yaml:"category"`
	Description  string   `yaml:"description"`
	InstalledVia string   `yaml:"installed_via"`
	Usage        string   `yaml:"usage"`
	WhyUse       string   `yaml:"why_use"`
	Examples     []struct {
		Cmd  string `yaml:"cmd"`
		Desc string `yaml:"desc"`
	} `yaml:"examples"`
	SeeAlso []string `yaml:"see_also"`
	Tags    []string `yaml:"tags"`
	DocsURL string   `yaml:"docs_url"`
}

// ToolRegistry represents the structure of registry.yml
type ToolRegistry struct {
	Version     string           `yaml:"version"`
	LastUpdated string           `yaml:"last_updated"`
	Tools       map[string]Tool  `yaml:"tools"`
}

// Load fetches all tools from the registry
func (t *ToolsIntegration) Load(ctx context.Context) ([]integration.Item, error) {
	// Return cache if available
	if len(t.cache) > 0 {
		return t.cache, nil
	}

	data, err := os.ReadFile(t.registryPath)
	if err != nil {
		return nil, fmt.Errorf("failed to read tools registry: %w", err)
	}

	var registry ToolRegistry
	if err := yaml.Unmarshal(data, &registry); err != nil {
		return nil, fmt.Errorf("failed to parse tools registry: %w", err)
	}

	items := make([]integration.Item, 0, len(registry.Tools))

	for name, tool := range registry.Tools {
		// Convert examples to interface{} for Details map
		examples := make([]interface{}, len(tool.Examples))
		for i, ex := range tool.Examples {
			examples[i] = map[string]interface{}{
				"command":     ex.Cmd,
				"description": ex.Desc,
			}
		}

		// Build comprehensive description
		description := tool.Description
		if tool.WhyUse != "" {
			description = tool.WhyUse
		}

		// Determine priority based on tags
		priority := 0
		if contains(tool.Tags, "essential") {
			priority = 100
		} else if contains(tool.Tags, "productivity") {
			priority = 50
		}

		details := map[string]interface{}{
			"category":      tool.Category,
			"installed_via": tool.InstalledVia,
			"usage":         tool.Usage,
			"why_use":       tool.WhyUse,
			"examples":      examples,
			"see_also":      tool.SeeAlso,
			"docs_url":      tool.DocsURL,
		}

		items = append(items, integration.Item{
			ID:          name,
			Title:       name,
			Description: description,
			Category:    tool.Category,
			Icon:        getCategoryIcon(tool.Category),
			Tags:        tool.Tags,
			Keywords:    append(tool.SeeAlso, tool.Category),
			Status:      "installed",
			Priority:    priority,
			Source:      "tools",
			Executable:  true,
			Command:     name, // Just the tool name
			IsInteractive: false,
			Details:     details,
		})
	}

	t.cache = items
	return items, nil
}

// Get retrieves a specific tool by name
func (t *ToolsIntegration) Get(ctx context.Context, id string) (*integration.Item, error) {
	items, err := t.Load(ctx)
	if err != nil {
		return nil, err
	}

	for _, item := range items {
		if item.ID == id {
			return &item, nil
		}
	}

	return nil, fmt.Errorf("tool %q not found", id)
}

// Search filters tools by query
func (t *ToolsIntegration) Search(ctx context.Context, query string) ([]integration.Item, error) {
	items, err := t.Load(ctx)
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

// Execute opens tool documentation or shows usage
func (t *ToolsIntegration) Execute(ctx context.Context, item integration.Item) (string, error) {
	if !item.Executable {
		return "", fmt.Errorf("item %q is not executable", item.ID)
	}

	// For tools, we can either:
	// 1. Show the tool's help: toolname --help
	// 2. Open the docs URL
	// 3. Show usage from registry

	// Return command to show help
	return fmt.Sprintf("%s --help", item.ID), nil
}

// SupportsExecution indicates that tools can show help
func (t *ToolsIntegration) SupportsExecution() bool {
	return true
}

// Refresh clears the cache and reloads from file
func (t *ToolsIntegration) Refresh(ctx context.Context) error {
	t.cache = nil
	_, err := t.Load(ctx)
	return err
}

// Helper functions

func getCategoryIcon(category string) string {
	icons := map[string]string{
		"file-viewer":         "👁",
		"file-management":     "📁",
		"search":              "🔍",
		"text-processing":     "📝",
		"navigation":          "🧭",
		"version-control":     "🌿",
		"editor":              "✏️",
		"terminal-multiplexer": "🪟",
		"language-manager":    "🔧",
		"linter-formatter":    "✨",
		"language-server":     "🔌",
		"containerization":    "📦",
		"infrastructure":      "🏗",
		"automation":          "⚡",
		"system-monitoring":   "📊",
	}

	if icon, ok := icons[category]; ok {
		return icon
	}

	return "🔧"
}

func contains(slice []string, item string) bool {
	for _, s := range slice {
		if s == item {
			return true
		}
	}
	return false
}

func containsAny(slice []string, query string) bool {
	for _, s := range slice {
		if strings.Contains(strings.ToLower(s), query) {
			return true
		}
	}
	return false
}
