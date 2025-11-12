package registries

import (
	"context"
	"path/filepath"
	"testing"

	"github.com/ichrisbirch/menu/internal/integration"
	"github.com/ichrisbirch/menu/internal/registry"
	"github.com/ichrisbirch/menu/internal/testutil"
)

func TestWorkflowsIntegration_Load(t *testing.T) {
	tmpDir := testutil.CreateTempDir(t)
	registryDir := filepath.Join(tmpDir, ".config", "menu", "registry")
	workflowsFile := filepath.Join(registryDir, "workflows.yml")

	err := testutil.WriteYAMLFile(workflowsFile, testutil.SampleWorkflowsYAML())
	testutil.AssertNoError(t, err)

	loader := registry.NewLoaderWithPath(registryDir)
	integ := NewWorkflowsIntegration(loader)

	ctx := context.Background()
	items, err := integ.Load(ctx)

	testutil.AssertNoError(t, err)
	integration.AssertItemsCount(t, items, 2) // Git and Vim workflows

	// Check Git workflow
	integration.AssertItemHasField(t, items[0], "Title", "Git Commit Workflow")
	integration.AssertItemHasField(t, items[0], "Category", "Git") // Preserves original category
	integration.AssertItemHasField(t, items[0], "Icon", "⚡") // Default icon (not "Git Workflows")
	integration.AssertItemHasField(t, items[0], "Executable", false)

	// Check Vim workflow
	integration.AssertItemHasField(t, items[1], "Title", "Vim Edit Workflow")
	integration.AssertItemHasField(t, items[1], "Icon", "⚡") // Default icon (not "Vim Workflows")
}

func TestWorkflowsIntegration_Get(t *testing.T) {
	tmpDir := testutil.CreateTempDir(t)
	registryDir := filepath.Join(tmpDir, ".config", "menu", "registry")
	workflowsFile := filepath.Join(registryDir, "workflows.yml")

	err := testutil.WriteYAMLFile(workflowsFile, testutil.SampleWorkflowsYAML())
	testutil.AssertNoError(t, err)

	loader := registry.NewLoaderWithPath(registryDir)
	integ := NewWorkflowsIntegration(loader)

	ctx := context.Background()

	item, err := integ.Get(ctx, "Git Commit Workflow")
	testutil.AssertNoError(t, err)
	testutil.AssertEqual(t, "Git Commit Workflow", item.Title)

	_, err = integ.Get(ctx, "nonexistent")
	testutil.AssertError(t, err)
}

func TestWorkflowsIntegration_Search(t *testing.T) {
	tmpDir := testutil.CreateTempDir(t)
	registryDir := filepath.Join(tmpDir, ".config", "menu", "registry")
	workflowsFile := filepath.Join(registryDir, "workflows.yml")

	err := testutil.WriteYAMLFile(workflowsFile, testutil.SampleWorkflowsYAML())
	testutil.AssertNoError(t, err)

	loader := registry.NewLoaderWithPath(registryDir)
	integ := NewWorkflowsIntegration(loader)

	ctx := context.Background()

	tests := []struct {
		name     string
		query    string
		expected int
	}{
		{"Search git", "git", 1},
		{"Search vim", "vim", 1},
		{"Search edit", "edit", 1},
		{"No results", "docker", 0},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			items, err := integ.Search(ctx, tt.query)
			testutil.AssertNoError(t, err)
			integration.AssertItemsCount(t, items, tt.expected)
		})
	}
}

func TestWorkflowsIntegration_Metadata(t *testing.T) {
	loader := registry.NewLoader()
	integ := NewWorkflowsIntegration(loader)

	testutil.AssertEqual(t, "workflows", integ.Name())
	testutil.AssertEqual(t, integration.TypeStatic, integ.Type())
	testutil.AssertFalse(t, integ.SupportsExecution(), "workflows should not support execution")
}

func TestWorkflowsIntegration_IconByCategory(t *testing.T) {
	tests := []struct {
		category     string
		expectedIcon string
	}{
		{"Git Workflows", "🌿"},
		{"Vim Workflows", "✏️"},
		{"File Operations", "📁"},
		{"Unknown Category", "⚡"}, // Default icon
	}

	for _, tt := range tests {
		t.Run(tt.category, func(t *testing.T) {
			tmpDir := testutil.CreateTempDir(t)
			registryDir := filepath.Join(tmpDir, ".config", "menu", "registry")
			workflowsFile := filepath.Join(registryDir, "workflows.yml")

			yamlContent := `workflows:
  - name: "Test Workflow"
    category: "` + tt.category + `"
    description: "Test description"
    keywords: ["test"]
    platform: "all"
    steps:
      - description: "Step 1"
`
			err := testutil.WriteYAMLFile(workflowsFile, yamlContent)
			testutil.AssertNoError(t, err)

			loader := registry.NewLoaderWithPath(registryDir)
			integ := NewWorkflowsIntegration(loader)

			ctx := context.Background()
			items, err := integ.Load(ctx)
			testutil.AssertNoError(t, err)
			integration.AssertItemsCount(t, items, 1)
			integration.AssertItemHasField(t, items[0], "Icon", tt.expectedIcon)
		})
	}
}
