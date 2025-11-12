package integration

import (
	"context"
	"testing"

	"github.com/ichrisbirch/menu/internal/testutil"
)

func TestManager_Register(t *testing.T) {
	config := &Config{}
	manager := NewManager(config)

	mockInteg := &MockIntegration{
		NameVal: "test",
		TypeVal: TypeStatic,
	}

	// Test successful registration
	err := manager.Register(mockInteg)
	testutil.AssertNoError(t, err)

	// Test duplicate registration
	err = manager.Register(mockInteg)
	testutil.AssertError(t, err)

	// Test nil integration
	err = manager.Register(nil)
	testutil.AssertError(t, err)

	// Test empty name integration
	emptyNameInteg := &MockIntegration{
		NameVal: "",
		TypeVal: TypeStatic,
	}
	err = manager.Register(emptyNameInteg)
	testutil.AssertError(t, err)
}

func TestManager_Get(t *testing.T) {
	config := &Config{}
	manager := NewManager(config)

	mockInteg := &MockIntegration{
		NameVal: "test",
		TypeVal: TypeStatic,
	}

	manager.Register(mockInteg)

	// Test getting existing integration
	integ, err := manager.Get("test")
	testutil.AssertNoError(t, err)
	testutil.AssertEqual(t, "test", integ.Name())

	// Test getting non-existent integration
	_, err = manager.Get("nonexistent")
	testutil.AssertError(t, err)
}

func TestManager_List(t *testing.T) {
	config := &Config{}
	manager := NewManager(config)

	// Register multiple integrations
	integrations := []string{"commands", "workflows", "learning"}
	for _, name := range integrations {
		mockInteg := &MockIntegration{
			NameVal: name,
			TypeVal: TypeStatic,
		}
		manager.Register(mockInteg)
	}

	names := manager.List()
	testutil.AssertEqual(t, 3, len(names))

	// Check names are sorted
	testutil.AssertEqual(t, "commands", names[0])
	testutil.AssertEqual(t, "learning", names[1])
	testutil.AssertEqual(t, "workflows", names[2])
}

func TestManager_LoadAll(t *testing.T) {
	config := &Config{}
	manager := NewManager(config)

	// Create mock integrations with items
	mockInteg1 := &MockIntegration{
		NameVal: "test1",
		TypeVal: TypeStatic,
		LoadFunc: func(ctx context.Context) ([]Item, error) {
			return []Item{
				{ID: "item1", Title: "Item 1"},
				{ID: "item2", Title: "Item 2"},
			}, nil
		},
	}

	mockInteg2 := &MockIntegration{
		NameVal: "test2",
		TypeVal: TypeStatic,
		LoadFunc: func(ctx context.Context) ([]Item, error) {
			return []Item{
				{ID: "item3", Title: "Item 3"},
			}, nil
		},
	}

	manager.Register(mockInteg1)
	manager.Register(mockInteg2)

	ctx := context.Background()
	results, err := manager.LoadAll(ctx)
	testutil.AssertNoError(t, err)

	// Check we got results from both integrations
	testutil.AssertEqual(t, 2, len(results))
	testutil.AssertEqual(t, 2, len(results["test1"]))
	testutil.AssertEqual(t, 1, len(results["test2"]))
}

func TestManager_Search(t *testing.T) {
	config := &Config{}
	manager := NewManager(config)

	mockInteg := &MockIntegration{
		NameVal: "test",
		TypeVal: TypeStatic,
		SearchFunc: func(ctx context.Context, query string) ([]Item, error) {
			if query == "match" {
				return []Item{
					{ID: "item1", Title: "Matching Item"},
				}, nil
			}
			return []Item{}, nil
		},
	}

	manager.Register(mockInteg)

	ctx := context.Background()

	// Test search with results
	results, err := manager.Search(ctx, "match")
	testutil.AssertNoError(t, err)
	testutil.AssertEqual(t, 1, len(results))
	testutil.AssertEqual(t, 1, len(results["test"]))

	// Test search without results
	results, err = manager.Search(ctx, "nomatch")
	testutil.AssertNoError(t, err)
	testutil.AssertEqual(t, 0, len(results))
}

func TestFilterItems(t *testing.T) {
	items := []Item{
		{ID: "1", Title: "Go Testing", Category: "Programming", Tags: []string{"go", "testing"}},
		{ID: "2", Title: "Docker Basics", Category: "DevOps", Tags: []string{"docker"}},
		{ID: "3", Title: "Vim Tutorial", Category: "Editors", Tags: []string{"vim", "tutorial"}},
	}

	tests := []struct {
		name     string
		filter   Filter
		expected int
	}{
		{
			name:     "No filter",
			filter:   Filter{},
			expected: 3,
		},
		{
			name:     "Filter by query",
			filter:   Filter{Query: "go"},
			expected: 1,
		},
		{
			name:     "Filter by category",
			filter:   Filter{Categories: []string{"DevOps"}},
			expected: 1,
		},
		{
			name:     "Filter by tag",
			filter:   Filter{Tags: []string{"vim"}},
			expected: 1,
		},
		{
			name:     "Multiple filters",
			filter:   Filter{Query: "tutorial", Tags: []string{"vim"}},
			expected: 1,
		},
		{
			name:     "No matches",
			filter:   Filter{Query: "kubernetes"},
			expected: 0,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			filtered := FilterItems(items, tt.filter)
			testutil.AssertEqual(t, tt.expected, len(filtered))
		})
	}
}

func TestSortItems(t *testing.T) {
	now := int64(1000)
	earlier := int64(500)

	items := []Item{
		{ID: "1", Title: "C Item", Category: "Cat1", Priority: 10, LastAccessed: &earlier},
		{ID: "2", Title: "A Item", Category: "Cat2", Priority: 50, LastAccessed: &now},
		{ID: "3", Title: "B Item", Category: "Cat1", Priority: 30},
	}

	tests := []struct {
		name     string
		sortBy   SortOption
		expected []string
	}{
		{
			name:     "Sort by title",
			sortBy:   SortByTitle,
			expected: []string{"2", "3", "1"}, // A, B, C
		},
		{
			name:     "Sort by priority",
			sortBy:   SortByPriority,
			expected: []string{"2", "3", "1"}, // 50, 30, 10
		},
		{
			name:     "Sort by recent",
			sortBy:   SortByRecent,
			expected: []string{"2", "1", "3"}, // now, earlier, nil
		},
		{
			name:     "Sort by category",
			sortBy:   SortByCategory,
			expected: []string{"3", "1", "2"}, // Cat1(B), Cat1(C), Cat2(A)
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			// Make a copy to avoid modifying original
			testItems := make([]Item, len(items))
			copy(testItems, items)

			SortItems(testItems, tt.sortBy)

			for i, expectedID := range tt.expected {
				testutil.AssertEqual(t, expectedID, testItems[i].ID)
			}
		})
	}
}

func TestManager_MarkRecent(t *testing.T) {
	config := &Config{}
	manager := NewManager(config)

	mockInteg := &MockIntegration{
		NameVal: "test",
		TypeVal: TypeStatic,
		GetFunc: func(ctx context.Context, id string) (*Item, error) {
			return &Item{ID: id, Title: "Test Item"}, nil
		},
	}

	manager.Register(mockInteg)

	err := manager.MarkRecent("test", "item1")
	testutil.AssertNoError(t, err)

	// Test with non-existent integration
	err = manager.MarkRecent("nonexistent", "item1")
	testutil.AssertError(t, err)
}
