package registries

import (
	"context"
	"path/filepath"
	"testing"

	"github.com/ichrisbirch/menu/internal/integration"
	"github.com/ichrisbirch/menu/internal/registry"
	"github.com/ichrisbirch/menu/internal/testutil"
)

func TestCommandsIntegration_Load(t *testing.T) {
	// Setup
	tmpDir := testutil.CreateTempDir(t)
	registryDir := filepath.Join(tmpDir, ".config", "menu", "registry")
	commandsFile := filepath.Join(registryDir, "commands.yml")

	err := testutil.WriteYAMLFile(commandsFile, testutil.SampleCommandsYAML())
	testutil.AssertNoError(t, err)

	// Create loader with temp directory
	loader := registry.NewLoaderWithPath(registryDir)
	integ := NewCommandsIntegration(loader)

	// Test
	ctx := context.Background()
	items, err := integ.Load(ctx)

	// Assertions
	testutil.AssertNoError(t, err)
	integration.AssertItemsCount(t, items, 3) // ls, ll, gitlog

	// Check first item (ls)
	integration.AssertItemHasField(t, items[0], "Title", "ls")
	integration.AssertItemHasField(t, items[0], "Category", "File Operations") // Preserves original category
	integration.AssertItemHasField(t, items[0], "Icon", "🔧") // system_tool

	// Check second item (ll - alias)
	integration.AssertItemHasField(t, items[1], "Title", "ll")
	integration.AssertItemHasField(t, items[1], "Icon", "→") // alias

	// Check third item (gitlog - function)
	integration.AssertItemHasField(t, items[2], "Title", "gitlog")
	integration.AssertItemHasField(t, items[2], "Icon", "ƒ") // function
}

func TestCommandsIntegration_Get(t *testing.T) {
	tmpDir := testutil.CreateTempDir(t)
	registryDir := filepath.Join(tmpDir, ".config", "menu", "registry")
	commandsFile := filepath.Join(registryDir, "commands.yml")

	err := testutil.WriteYAMLFile(commandsFile, testutil.SampleCommandsYAML())
	testutil.AssertNoError(t, err)

	loader := registry.NewLoaderWithPath(registryDir)
	integ := NewCommandsIntegration(loader)

	ctx := context.Background()

	// Test getting existing command
	item, err := integ.Get(ctx, "ls")
	testutil.AssertNoError(t, err)
	testutil.AssertEqual(t, "ls", item.Title)
	testutil.AssertEqual(t, "List directory contents", item.Description)

	// Test getting non-existent command
	_, err = integ.Get(ctx, "nonexistent")
	testutil.AssertError(t, err)
}

func TestCommandsIntegration_Search(t *testing.T) {
	tmpDir := testutil.CreateTempDir(t)
	registryDir := filepath.Join(tmpDir, ".config", "menu", "registry")
	commandsFile := filepath.Join(registryDir, "commands.yml")

	err := testutil.WriteYAMLFile(commandsFile, testutil.SampleCommandsYAML())
	testutil.AssertNoError(t, err)

	loader := registry.NewLoaderWithPath(registryDir)
	integ := NewCommandsIntegration(loader)

	ctx := context.Background()

	tests := []struct {
		name     string
		query    string
		expected int
	}{
		{"Search by title", "ls", 2},       // ls and ll
		{"Search by description", "git", 1}, // gitlog
		{"Search by keyword", "files", 2},   // ls and ll
		{"No results", "nonexistent", 0},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			items, err := integ.Search(ctx, tt.query)
			testutil.AssertNoError(t, err)
			integration.AssertItemsCount(t, items, tt.expected)
		})
	}
}

func TestCommandsIntegration_Execute(t *testing.T) {
	tmpDir := testutil.CreateTempDir(t)
	registryDir := filepath.Join(tmpDir, ".config", "menu", "registry")
	commandsFile := filepath.Join(registryDir, "commands.yml")

	err := testutil.WriteYAMLFile(commandsFile, testutil.SampleCommandsYAML())
	testutil.AssertNoError(t, err)

	loader := registry.NewLoaderWithPath(registryDir)
	integ := NewCommandsIntegration(loader)

	ctx := context.Background()

	// Get a command item
	item, err := integ.Get(ctx, "ls")
	testutil.AssertNoError(t, err)

	// Execute should return the command string
	cmd, err := integ.Execute(ctx, *item)
	testutil.AssertNoError(t, err)
	testutil.AssertEqual(t, "ls -la", cmd)
}

func TestCommandsIntegration_Metadata(t *testing.T) {
	loader := registry.NewLoader()
	integ := NewCommandsIntegration(loader)

	testutil.AssertEqual(t, "commands", integ.Name())
	testutil.AssertEqual(t, integration.TypeStatic, integ.Type())
	testutil.AssertTrue(t, integ.SupportsExecution(), "should support execution")
}

func TestCommandsIntegration_IconMapping(t *testing.T) {
	tests := []struct {
		commandType string
		expectedIcon string
	}{
		{"function", "ƒ"},
		{"alias", "→"},
		{"system_tool", "🔧"},
		{"forgit_alias", "🌿"},
		{"unknown", "⚡"},
	}

	for _, tt := range tests {
		t.Run(tt.commandType, func(t *testing.T) {
			tmpDir := testutil.CreateTempDir(t)
			registryDir := filepath.Join(tmpDir, ".config", "menu", "registry")
			commandsFile := filepath.Join(registryDir, "commands.yml")

			yamlContent := `commands:
  - name: "test"
    type: "` + tt.commandType + `"
    category: "Test"
    description: "Test command"
    keywords: ["test"]
    command: "echo test"
    platform: "all"
`
			err := testutil.WriteYAMLFile(commandsFile, yamlContent)
			testutil.AssertNoError(t, err)

			loader := registry.NewLoaderWithPath(registryDir)
			integ := NewCommandsIntegration(loader)

			ctx := context.Background()
			items, err := integ.Load(ctx)
			testutil.AssertNoError(t, err)
			integration.AssertItemsCount(t, items, 1)
			integration.AssertItemHasField(t, items[0], "Icon", tt.expectedIcon)
		})
	}
}
