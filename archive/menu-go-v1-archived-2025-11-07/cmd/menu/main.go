package main

import (
	"fmt"
	"os"
	"path/filepath"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/ichrisbirch/menu/internal/integration"
	"github.com/ichrisbirch/menu/internal/integration/bookmarks"
	"github.com/ichrisbirch/menu/internal/integration/notes"
	"github.com/ichrisbirch/menu/internal/integration/registries"
	"github.com/ichrisbirch/menu/internal/integration/sessions"
	"github.com/ichrisbirch/menu/internal/integration/tasks"
	"github.com/ichrisbirch/menu/internal/integration/tools"
	"github.com/ichrisbirch/menu/internal/registry"
	"github.com/ichrisbirch/menu/internal/ui"
	"github.com/spf13/cobra"
)

// Version information (set via ldflags during build)
var (
	Version = "0.2.0"
	Commit  = "dev"
)

func main() {
	rootCmd := &cobra.Command{
		Use:   "menu",
		Short: "Universal menu for dotfiles",
		Long: `A universal menu system for managing commands, workflows, learning,
sessions, tasks, notes, bookmarks, and development tools.

Features:
- Commands & Aliases registry
- Workflows & Techniques
- Learning Topics
- Tmux Sessions (via session command)
- Task management (Taskfile.yml)
- Notes (nb integration)
- Bookmarks (buku integration)
- Tools discovery`,
		Version: fmt.Sprintf("%s (%s)", Version, Commit),
		Run: func(cmd *cobra.Command, args []string) {
			// Launch the interactive menu
			showMenu()
		},
	}

	if err := rootCmd.Execute(); err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		os.Exit(1)
	}
}

func showMenu() {
	// Create integration manager
	manager := createIntegrationManager()

	// Create and run the Bubbletea program with the integration manager
	model := ui.NewModelWithIntegrations(manager)
	program := tea.NewProgram(model, tea.WithAltScreen())

	if _, err := program.Run(); err != nil {
		fmt.Fprintf(os.Stderr, "Error running menu: %v\n", err)
		os.Exit(1)
	}
}

// createIntegrationManager sets up all integrations
func createIntegrationManager() *integration.Manager {
	// Get config directory
	homeDir, err := os.UserHomeDir()
	if err != nil {
		fmt.Fprintf(os.Stderr, "Warning: could not get home directory: %v\n", err)
		homeDir = "~"
	}

	configDir := filepath.Join(homeDir, ".config", "menu")

	// Create integration config
	config := &integration.Config{
		ConfigDir:       configDir,
		DataDir:         filepath.Join(homeDir, ".local", "share", "menu"),
		EnableCache:     true,
		EnableFavorites: true,
		EnableRecents:   true,
		MaxRecentItems:  20,
		IntegrationConfigs: make(map[string]interface{}),
	}

	// Create manager
	manager := integration.NewManager(config)

	// Create registry loader for YAML registries
	loader := registry.NewLoader()

	// Register all integrations
	// 1. Commands registry
	if err := manager.Register(registries.NewCommandsIntegration(loader)); err != nil {
		fmt.Fprintf(os.Stderr, "Warning: could not register commands: %v\n", err)
	}

	// 2. Workflows registry
	if err := manager.Register(registries.NewWorkflowsIntegration(loader)); err != nil {
		fmt.Fprintf(os.Stderr, "Warning: could not register workflows: %v\n", err)
	}

	// 3. Learning topics registry
	if err := manager.Register(registries.NewLearningIntegration(loader)); err != nil {
		fmt.Fprintf(os.Stderr, "Warning: could not register learning: %v\n", err)
	}

	// 4. Sessions integration (session-go binary)
	sessionBinary := filepath.Join(homeDir, ".local", "bin", "session")
	if err := manager.Register(sessions.NewIntegration(sessionBinary)); err != nil {
		fmt.Fprintf(os.Stderr, "Warning: could not register sessions: %v\n", err)
	}

	// 5. Tasks integration (Taskfile)
	// Look for Taskfile in current directory or parent directories
	taskfilePath := findTaskfile()
	if err := manager.Register(tasks.NewIntegration(taskfilePath, "task")); err != nil {
		fmt.Fprintf(os.Stderr, "Warning: could not register tasks: %v\n", err)
	}

	// 6. Tools integration (tools registry)
	toolsRegistry := filepath.Join(homeDir, "dotfiles", "docs", "tools", "registry.yml")
	if err := manager.Register(tools.NewIntegration(toolsRegistry)); err != nil {
		fmt.Fprintf(os.Stderr, "Warning: could not register tools: %v\n", err)
	}

	// 7. Notes integration (nb)
	notesDir := filepath.Join(homeDir, "Documents", "notes")
	if err := manager.Register(notes.NewIntegration("nb", notesDir)); err != nil {
		fmt.Fprintf(os.Stderr, "Warning: could not register notes: %v\n", err)
	}

	// 8. Bookmarks integration (buku)
	if err := manager.Register(bookmarks.NewIntegration("buku")); err != nil {
		fmt.Fprintf(os.Stderr, "Warning: could not register bookmarks: %v\n", err)
	}

	return manager
}

// findTaskfile searches for Taskfile.yml in current directory and parent directories
func findTaskfile() string {
	candidates := []string{
		"Taskfile.yml",
		"taskfile.yml",
		"Taskfile.yaml",
	}

	// Try current directory first
	for _, candidate := range candidates {
		if _, err := os.Stat(candidate); err == nil {
			return candidate
		}
	}

	// Try parent directories up to home
	dir, err := os.Getwd()
	if err != nil {
		return ""
	}

	homeDir, _ := os.UserHomeDir()

	for dir != "/" && dir != homeDir {
		for _, candidate := range candidates {
			path := filepath.Join(dir, candidate)
			if _, err := os.Stat(path); err == nil {
				return path
			}
		}

		// Move to parent directory
		parent := filepath.Dir(dir)
		if parent == dir {
			break
		}
		dir = parent
	}

	return ""
}
