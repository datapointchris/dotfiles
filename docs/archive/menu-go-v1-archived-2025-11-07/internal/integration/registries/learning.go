package registries

import (
	"context"
	"fmt"
	"strings"

	"github.com/ichrisbirch/menu/internal/integration"
	"github.com/ichrisbirch/menu/internal/registry"
)

// LearningIntegration wraps the existing learning topics registry
type LearningIntegration struct {
	loader *registry.Loader
	cache  []integration.Item
}

// NewLearningIntegration creates a new learning integration
func NewLearningIntegration(loader *registry.Loader) *LearningIntegration {
	return &LearningIntegration{
		loader: loader,
	}
}

// Name returns the integration name
func (l *LearningIntegration) Name() string {
	return "learning"
}

// Type returns the integration type
func (l *LearningIntegration) Type() integration.IntegrationType {
	return integration.TypeStatic
}

// Load fetches all learning topics from the registry
func (l *LearningIntegration) Load(ctx context.Context) ([]integration.Item, error) {
	// Return cache if available
	if len(l.cache) > 0 {
		return l.cache, nil
	}

	topics, err := l.loader.LoadLearningTopics()
	if err != nil {
		return nil, err
	}

	items := make([]integration.Item, len(topics))
	for i, topic := range topics {
		items[i] = l.topicToItem(topic)
	}

	l.cache = items
	return items, nil
}

// topicToItem converts a registry.LearningTopic to an integration.Item
func (l *LearningIntegration) topicToItem(topic registry.LearningTopic) integration.Item {
	// Determine icon based on status
	icon := "📚"
	statusDisplay := topic.Status
	switch topic.Status {
	case "active":
		icon = "🎯"
		statusDisplay = "Active"
	case "completed":
		icon = "✓"
		statusDisplay = "Completed"
	case "planned":
		icon = "📋"
		statusDisplay = "Planned"
	case "paused":
		icon = "⏸"
		statusDisplay = "Paused"
	}

	// Build details map
	details := map[string]interface{}{
		"category": topic.Category,
		"status":   topic.Status,
	}

	if topic.Progress.Started != "" || topic.Progress.Confidence != "" {
		progress := map[string]interface{}{}
		if topic.Progress.Started != "" {
			progress["started"] = topic.Progress.Started
		}
		if topic.Progress.Confidence != "" {
			progress["confidence"] = topic.Progress.Confidence
		}
		details["progress"] = progress
	}

	if len(topic.Exercises) > 0 {
		details["exercises"] = topic.Exercises
	}

	// Convert LearningResources to interface{} for Details
	hasResources := false
	resourcesList := make([]interface{}, 0)

	// Add bookmarks
	for _, bookmark := range topic.Resources.Bookmarks {
		resourcesList = append(resourcesList, map[string]interface{}{
			"title":  bookmark.Title,
			"url":    bookmark.URL,
			"type":   "bookmark",
			"status": bookmark.Status,
		})
		hasResources = true
	}

	// Add notes
	for _, note := range topic.Resources.Notes {
		resourcesList = append(resourcesList, map[string]interface{}{
			"path":        note.Path,
			"description": note.Description,
			"type":        "note",
		})
		hasResources = true
	}

	// Add videos
	for _, video := range topic.Resources.Videos {
		resourcesList = append(resourcesList, map[string]interface{}{
			"title": video.Title,
			"url":   video.URL,
			"type":  "video",
		})
		hasResources = true
	}

	if hasResources {
		details["resources"] = resourcesList
	}

	// Related workflows instead of next_steps
	if len(topic.RelatedFlows) > 0 {
		details["related_workflows"] = topic.RelatedFlows
	}

	// Determine priority based on status
	priority := 0
	switch topic.Status {
	case "active":
		priority = 100
	case "planned":
		priority = 50
	case "paused":
		priority = 25
	case "completed":
		priority = 10
	}

	tags := append([]string{topic.Category, topic.Status}, topic.Keywords...)

	return integration.Item{
		ID:          topic.Name,
		Title:       topic.Name,
		Description: topic.Description,
		Category:    "Learning",
		Icon:        icon,
		Tags:        tags,
		Keywords:    topic.Keywords,
		Status:      statusDisplay,
		Priority:    priority,
		Source:      "learning",
		Executable:  false, // Learning topics are reference
		Details:     details,
	}
}

// Get retrieves a specific learning topic by name
func (l *LearningIntegration) Get(ctx context.Context, id string) (*integration.Item, error) {
	topic, err := l.loader.FindLearningTopic(id)
	if err != nil {
		return nil, err
	}

	if topic == nil {
		return nil, fmt.Errorf("learning topic %q not found", id)
	}

	item := l.topicToItem(*topic)
	return &item, nil
}

// Search filters learning topics by query
func (l *LearningIntegration) Search(ctx context.Context, query string) ([]integration.Item, error) {
	items, err := l.Load(ctx)
	if err != nil {
		return nil, err
	}

	query = strings.ToLower(query)
	filtered := make([]integration.Item, 0)

	for _, item := range items {
		if strings.Contains(strings.ToLower(item.Title), query) ||
			strings.Contains(strings.ToLower(item.Description), query) ||
			strings.Contains(strings.ToLower(item.Category), query) ||
			strings.Contains(strings.ToLower(item.Status), query) ||
			containsSearch(item.Tags, query) ||
			containsSearch(item.Keywords, query) {
			filtered = append(filtered, item)
		}
	}

	return filtered, nil
}

// Execute - learning topics are not executable
func (l *LearningIntegration) Execute(ctx context.Context, item integration.Item) (string, error) {
	// Could potentially open resources, but for now just return error
	return "", fmt.Errorf("learning topics are reference material and cannot be executed")
}

// SupportsExecution indicates that learning topics cannot be executed
func (l *LearningIntegration) SupportsExecution() bool {
	return false
}

// Refresh reloads learning topics from registry
func (l *LearningIntegration) Refresh(ctx context.Context) error {
	l.cache = nil
	_, err := l.Load(ctx)
	return err
}

// Helper function
func containsSearch(slice []string, query string) bool {
	for _, s := range slice {
		if strings.Contains(strings.ToLower(s), query) {
			return true
		}
	}
	return false
}
