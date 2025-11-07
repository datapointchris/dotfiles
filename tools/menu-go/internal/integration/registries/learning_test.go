package registries

import (
	"context"
	"path/filepath"
	"testing"

	"github.com/ichrisbirch/menu/internal/integration"
	"github.com/ichrisbirch/menu/internal/registry"
	"github.com/ichrisbirch/menu/internal/testutil"
)

func TestLearningIntegration_Load(t *testing.T) {
	tmpDir := testutil.CreateTempDir(t)
	registryDir := filepath.Join(tmpDir, ".config", "menu", "registry")
	learningFile := filepath.Join(registryDir, "learning.yml")

	err := testutil.WriteYAMLFile(learningFile, testutil.SampleLearningYAML())
	testutil.AssertNoError(t, err)

	loader := registry.NewLoaderWithPath(registryDir)
	integ := NewLearningIntegration(loader)

	ctx := context.Background()
	items, err := integ.Load(ctx)

	testutil.AssertNoError(t, err)
	integration.AssertItemsCount(t, items, 2) // Go Testing and Docker Basics

	// Check Go Testing (active)
	integration.AssertItemHasField(t, items[0], "Title", "Go Testing")
	integration.AssertItemHasField(t, items[0], "Category", "Learning")
	integration.AssertItemHasField(t, items[0], "Icon", "🎯") // active status
	integration.AssertItemHasField(t, items[0], "Executable", false)
	testutil.AssertEqual(t, "Active", items[0].Status)

	// Check priority based on status
	testutil.AssertTrue(t, items[0].Priority == 100, "active topic should have priority 100")
	testutil.AssertTrue(t, items[1].Priority == 50, "planned topic should have priority 50")
}

func TestLearningIntegration_StatusIcons(t *testing.T) {
	tests := []struct {
		status       string
		expectedIcon string
		priority     int
	}{
		{"active", "🎯", 100},
		{"completed", "✓", 10},
		{"planned", "📋", 50},
		{"paused", "⏸", 25},
		{"unknown", "📚", 0},
	}

	for _, tt := range tests {
		t.Run(tt.status, func(t *testing.T) {
			tmpDir := testutil.CreateTempDir(t)
			registryDir := filepath.Join(tmpDir, ".config", "menu", "registry")
			learningFile := filepath.Join(registryDir, "learning.yml")

			yamlContent := `learning:
  - name: "Test Topic"
    category: "Test"
    status: "` + tt.status + `"
    description: "Test description"
    keywords: ["test"]
    platform: "all"
    progress:
      confidence: "beginner"
`
			err := testutil.WriteYAMLFile(learningFile, yamlContent)
			testutil.AssertNoError(t, err)

			loader := registry.NewLoaderWithPath(registryDir)
			integ := NewLearningIntegration(loader)

			ctx := context.Background()
			items, err := integ.Load(ctx)
			testutil.AssertNoError(t, err)
			integration.AssertItemsCount(t, items, 1)
			integration.AssertItemHasField(t, items[0], "Icon", tt.expectedIcon)
			if items[0].Priority != tt.priority {
				t.Fatalf("expected priority %d, got %d", tt.priority, items[0].Priority)
			}
		})
	}
}

func TestLearningIntegration_Get(t *testing.T) {
	tmpDir := testutil.CreateTempDir(t)
	registryDir := filepath.Join(tmpDir, ".config", "menu", "registry")
	learningFile := filepath.Join(registryDir, "learning.yml")

	err := testutil.WriteYAMLFile(learningFile, testutil.SampleLearningYAML())
	testutil.AssertNoError(t, err)

	loader := registry.NewLoaderWithPath(registryDir)
	integ := NewLearningIntegration(loader)

	ctx := context.Background()

	item, err := integ.Get(ctx, "Go Testing")
	testutil.AssertNoError(t, err)
	testutil.AssertEqual(t, "Go Testing", item.Title)
	testutil.AssertEqual(t, "Learning Go testing best practices", item.Description)

	_, err = integ.Get(ctx, "nonexistent")
	testutil.AssertError(t, err)
}

func TestLearningIntegration_Search(t *testing.T) {
	tmpDir := testutil.CreateTempDir(t)
	registryDir := filepath.Join(tmpDir, ".config", "menu", "registry")
	learningFile := filepath.Join(registryDir, "learning.yml")

	err := testutil.WriteYAMLFile(learningFile, testutil.SampleLearningYAML())
	testutil.AssertNoError(t, err)

	loader := registry.NewLoaderWithPath(registryDir)
	integ := NewLearningIntegration(loader)

	ctx := context.Background()

	tests := []struct {
		name     string
		query    string
		expected int
	}{
		{"Search go", "go", 1},
		{"Search docker", "docker", 1},
		{"Search testing", "testing", 1},
		{"Search active status", "active", 1},
		{"No results", "kubernetes", 0},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			items, err := integ.Search(ctx, tt.query)
			testutil.AssertNoError(t, err)
			integration.AssertItemsCount(t, items, tt.expected)
		})
	}
}

func TestLearningIntegration_ResourcesParsing(t *testing.T) {
	tmpDir := testutil.CreateTempDir(t)
	registryDir := filepath.Join(tmpDir, ".config", "menu", "registry")
	learningFile := filepath.Join(registryDir, "learning.yml")

	err := testutil.WriteYAMLFile(learningFile, testutil.SampleLearningYAML())
	testutil.AssertNoError(t, err)

	loader := registry.NewLoaderWithPath(registryDir)
	integ := NewLearningIntegration(loader)

	ctx := context.Background()
	item, err := integ.Get(ctx, "Go Testing")
	testutil.AssertNoError(t, err)

	// Check that resources are in Details map
	resources, ok := item.Details["resources"].([]interface{})
	testutil.AssertTrue(t, ok, "resources should be in Details")
	testutil.AssertTrue(t, len(resources) == 2, "should have 2 resources (bookmark + note)")

	// Check progress
	progress, ok := item.Details["progress"].(map[string]interface{})
	testutil.AssertTrue(t, ok, "progress should be in Details")
	testutil.AssertTrue(t, progress["confidence"] == "intermediate", "confidence should be intermediate")

	// Check exercises
	exercises, ok := item.Details["exercises"].([]string)
	testutil.AssertTrue(t, ok, "exercises should be in Details")
	testutil.AssertTrue(t, len(exercises) == 2, "should have 2 exercises")
}

func TestLearningIntegration_Metadata(t *testing.T) {
	loader := registry.NewLoader()
	integ := NewLearningIntegration(loader)

	testutil.AssertEqual(t, "learning", integ.Name())
	testutil.AssertEqual(t, integration.TypeStatic, integ.Type())
	testutil.AssertFalse(t, integ.SupportsExecution(), "learning should not support execution")
}

func TestLearningIntegration_Execute(t *testing.T) {
	loader := registry.NewLoader()
	integ := NewLearningIntegration(loader)

	ctx := context.Background()
	item := integration.Item{ID: "test", Title: "test"}

	_, err := integ.Execute(ctx, item)
	testutil.AssertError(t, err) // Should return error for non-executable items
}
