package registries

import (
	"context"
	"fmt"
	"strings"

	"github.com/ichrisbirch/menu/internal/integration"
	"github.com/ichrisbirch/menu/internal/registry"
)

// WorkflowsIntegration wraps the existing workflows registry
type WorkflowsIntegration struct {
	loader *registry.Loader
	cache  []integration.Item
}

// NewWorkflowsIntegration creates a new workflows integration
func NewWorkflowsIntegration(loader *registry.Loader) *WorkflowsIntegration {
	return &WorkflowsIntegration{
		loader: loader,
	}
}

// Name returns the integration name
func (w *WorkflowsIntegration) Name() string {
	return "workflows"
}

// Type returns the integration type
func (w *WorkflowsIntegration) Type() integration.IntegrationType {
	return integration.TypeStatic
}

// Load fetches all workflows from the registry
func (w *WorkflowsIntegration) Load(ctx context.Context) ([]integration.Item, error) {
	// Return cache if available
	if len(w.cache) > 0 {
		return w.cache, nil
	}

	workflows, err := w.loader.LoadWorkflows()
	if err != nil {
		return nil, err
	}

	items := make([]integration.Item, len(workflows))
	for i, wf := range workflows {
		items[i] = w.workflowToItem(wf)
	}

	w.cache = items
	return items, nil
}

// workflowToItem converts a registry.Workflow to an integration.Item
func (w *WorkflowsIntegration) workflowToItem(wf registry.Workflow) integration.Item {
	// Convert steps to interface{} for Details
	steps := make([]interface{}, len(wf.Steps))
	for i, step := range wf.Steps {
		steps[i] = map[string]interface{}{
			"key":         step.Key,
			"description": step.Description,
		}
	}

	// Determine icon based on category
	icon := "📋"
	switch wf.Category {
	case "Git Workflows":
		icon = "🌿"
	case "Vim Workflows":
		icon = "✏️"
	case "File Operations":
		icon = "📁"
	default:
		icon = "⚡"
	}

	// Build details map
	details := map[string]interface{}{
		"category": wf.Category,
	}

	if len(steps) > 0 {
		details["steps"] = steps
	}

	if len(wf.Resources) > 0 {
		resources := make([]interface{}, len(wf.Resources))
		for i, res := range wf.Resources {
			resources[i] = map[string]interface{}{
				"title": res.Title,
				"url":   res.URL,
				"type":  res.Type,
			}
		}
		details["resources"] = resources
	}

	tags := wf.Keywords
	if len(tags) == 0 {
		tags = []string{wf.Category, "workflow"}
	}

	return integration.Item{
		ID:          wf.Name,
		Title:       wf.Name,
		Description: wf.Description,
		Category:    wf.Category,
		Icon:        icon,
		Tags:        tags,
		Keywords:    wf.Keywords,
		Source:      "workflows",
		Executable:  false, // Workflows are reference, not executable
		Details:     details,
	}
}

// Get retrieves a specific workflow by name
func (w *WorkflowsIntegration) Get(ctx context.Context, id string) (*integration.Item, error) {
	wf, err := w.loader.FindWorkflow(id)
	if err != nil {
		return nil, err
	}

	if wf == nil {
		return nil, fmt.Errorf("workflow %q not found", id)
	}

	item := w.workflowToItem(*wf)
	return &item, nil
}

// Search filters workflows by query
func (w *WorkflowsIntegration) Search(ctx context.Context, query string) ([]integration.Item, error) {
	items, err := w.Load(ctx)
	if err != nil {
		return nil, err
	}

	query = strings.ToLower(query)
	filtered := make([]integration.Item, 0)

	for _, item := range items {
		if strings.Contains(strings.ToLower(item.Title), query) ||
			strings.Contains(strings.ToLower(item.Description), query) ||
			strings.Contains(strings.ToLower(item.Category), query) ||
			containsAnyString(item.Tags, query) ||
			containsAnyString(item.Keywords, query) {
			filtered = append(filtered, item)
		}
	}

	return filtered, nil
}

// Execute - workflows are not executable
func (w *WorkflowsIntegration) Execute(ctx context.Context, item integration.Item) (string, error) {
	return "", fmt.Errorf("workflows are reference material and cannot be executed")
}

// SupportsExecution indicates that workflows cannot be executed
func (w *WorkflowsIntegration) SupportsExecution() bool {
	return false
}

// Refresh reloads workflows from registry
func (w *WorkflowsIntegration) Refresh(ctx context.Context) error {
	w.cache = nil
	_, err := w.Load(ctx)
	return err
}

// Helper function
func containsAnyString(slice []string, query string) bool {
	for _, s := range slice {
		if strings.Contains(strings.ToLower(s), query) {
			return true
		}
	}
	return false
}
