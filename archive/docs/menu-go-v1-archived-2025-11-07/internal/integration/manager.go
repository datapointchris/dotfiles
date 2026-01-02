package integration

import (
	"context"
	"fmt"
	"sort"
	"strings"
	"sync"
)

// NewManager creates a new integration manager with the given config
func NewManager(config *Config) *Manager {
	if config == nil {
		config = &Config{
			EnableCache:     true,
			EnableFavorites: true,
			EnableRecents:   true,
			MaxRecentItems:  20,
		}
	}

	// Initialize state for favorites and recents
	state, err := NewState(config.ConfigDir)
	if err != nil {
		// If state initialization fails, continue without state
		// This prevents the app from crashing if there are permission issues
		state = nil
	}

	return &Manager{
		integrations: make(map[string]Integration),
		config:       config,
		state:        state,
	}
}

// Register adds an integration to the manager
func (m *Manager) Register(integration Integration) error {
	if integration == nil {
		return fmt.Errorf("cannot register nil integration")
	}

	name := integration.Name()
	if name == "" {
		return fmt.Errorf("integration name cannot be empty")
	}

	if _, exists := m.integrations[name]; exists {
		return fmt.Errorf("integration %q already registered", name)
	}

	m.integrations[name] = integration
	return nil
}

// Get retrieves a registered integration by name
func (m *Manager) Get(name string) (Integration, error) {
	integration, exists := m.integrations[name]
	if !exists {
		return nil, fmt.Errorf("integration %q not found", name)
	}
	return integration, nil
}

// List returns all registered integration names
func (m *Manager) List() []string {
	names := make([]string, 0, len(m.integrations))
	for name := range m.integrations {
		names = append(names, name)
	}
	sort.Strings(names)
	return names
}

// LoadAll loads items from all integrations concurrently
// Returns a map of integration name to items
func (m *Manager) LoadAll(ctx context.Context) (map[string][]Item, error) {
	results := make(map[string][]Item)
	var mu sync.Mutex
	var wg sync.WaitGroup
	errChan := make(chan error, len(m.integrations))

	for name, integration := range m.integrations {
		wg.Add(1)
		go func(n string, i Integration) {
			defer wg.Done()

			items, err := i.Load(ctx)
			if err != nil {
				errChan <- fmt.Errorf("%s: %w", n, err)
				return
			}

			mu.Lock()
			results[n] = items
			mu.Unlock()
		}(name, integration)
	}

	wg.Wait()
	close(errChan)

	// Check for errors
	var errs []error
	for err := range errChan {
		errs = append(errs, err)
	}

	if len(errs) > 0 {
		return results, fmt.Errorf("errors loading integrations: %v", errs)
	}

	return results, nil
}

// Search searches across all integrations
func (m *Manager) Search(ctx context.Context, query string) (map[string][]Item, error) {
	results := make(map[string][]Item)
	var mu sync.Mutex
	var wg sync.WaitGroup

	for name, integration := range m.integrations {
		wg.Add(1)
		go func(n string, i Integration) {
			defer wg.Done()

			items, err := i.Search(ctx, query)
			if err != nil {
				// Log error but don't fail the whole search
				return
			}

			if len(items) > 0 {
				mu.Lock()
				results[n] = items
				mu.Unlock()
			}
		}(name, integration)
	}

	wg.Wait()
	return results, nil
}

// FilterItems applies a filter to a list of items
func FilterItems(items []Item, filter Filter) []Item {
	if filter.Query == "" && len(filter.Categories) == 0 &&
	   len(filter.Tags) == 0 && filter.Status == "" &&
	   !filter.Favorites && !filter.Recent {
		return items // No filtering needed
	}

	filtered := make([]Item, 0, len(items))

	for _, item := range items {
		// Apply all filters - item must match ALL criteria
		if !matchesFilter(item, filter) {
			continue
		}
		filtered = append(filtered, item)
	}

	return filtered
}

// matchesFilter checks if an item matches all filter criteria
func matchesFilter(item Item, filter Filter) bool {
	// Text query filter
	if filter.Query != "" {
		query := strings.ToLower(filter.Query)
		if !strings.Contains(strings.ToLower(item.Title), query) &&
			!strings.Contains(strings.ToLower(item.Description), query) &&
			!containsAny(item.Tags, query) &&
			!containsAny(item.Keywords, query) {
			return false
		}
	}

	// Category filter
	if len(filter.Categories) > 0 && !contains(filter.Categories, item.Category) {
		return false
	}

	// Tags filter (item must have at least one of the filter tags)
	if len(filter.Tags) > 0 {
		hasTag := false
		for _, tag := range filter.Tags {
			if contains(item.Tags, tag) {
				hasTag = true
				break
			}
		}
		if !hasTag {
			return false
		}
	}

	// Status filter
	if filter.Status != "" && item.Status != filter.Status {
		return false
	}

	// Favorites filter
	if filter.Favorites && !item.Favorite {
		return false
	}

	// Recent filter
	if filter.Recent && !item.Recent {
		return false
	}

	return true
}

// SortItems sorts items by the given option
func SortItems(items []Item, sortBy SortOption) {
	switch sortBy {
	case SortByTitle:
		sort.Slice(items, func(i, j int) bool {
			return items[i].Title < items[j].Title
		})
	case SortByRecent:
		sort.Slice(items, func(i, j int) bool {
			// Items without LastAccessed go to the end
			if items[i].LastAccessed == nil {
				return false
			}
			if items[j].LastAccessed == nil {
				return true
			}
			return *items[i].LastAccessed > *items[j].LastAccessed
		})
	case SortByPriority:
		sort.Slice(items, func(i, j int) bool {
			return items[i].Priority > items[j].Priority
		})
	case SortByCategory:
		sort.Slice(items, func(i, j int) bool {
			if items[i].Category == items[j].Category {
				return items[i].Title < items[j].Title
			}
			return items[i].Category < items[j].Category
		})
	}
}

// MarkRecent marks an item as recently accessed
func (m *Manager) MarkRecent(integrationName string, itemID string) error {
	if m.state == nil {
		return nil // State not available
	}

	integration, err := m.Get(integrationName)
	if err != nil {
		return err
	}

	ctx := context.Background()
	_, err = integration.Get(ctx, itemID)
	if err != nil {
		return err
	}

	// Persist to state
	return m.state.AddRecent(integrationName, itemID)
}

// ToggleFavorite toggles an item's favorite status
func (m *Manager) ToggleFavorite(integrationName string, itemID string) error {
	if m.state == nil {
		return fmt.Errorf("state not available")
	}

	if m.state.IsFavorite(integrationName, itemID) {
		return m.state.RemoveFavorite(integrationName, itemID)
	}
	return m.state.AddFavorite(integrationName, itemID)
}

// IsFavorite checks if an item is favorited
func (m *Manager) IsFavorite(integrationName string, itemID string) bool {
	if m.state == nil {
		return false
	}
	return m.state.IsFavorite(integrationName, itemID)
}

// EnrichItems enriches items with favorite and recent status
func (m *Manager) EnrichItems(integrationName string, items []Item) []Item {
	if m.state == nil {
		return items
	}

	enriched := make([]Item, len(items))
	for i, item := range items {
		enriched[i] = item
		enriched[i].Favorite = m.state.IsFavorite(integrationName, item.ID)

		// Set recent status and timestamp
		if timestamp := m.state.GetRecentTimestamp(integrationName, item.ID); timestamp != nil {
			enriched[i].Recent = true
			enriched[i].LastAccessed = timestamp
		}
	}

	return enriched
}

// Helper functions

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
