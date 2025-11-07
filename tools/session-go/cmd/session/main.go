package main

import (
	"fmt"
	"os"
	"runtime"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/ichrisbirch/session/internal/config"
	"github.com/ichrisbirch/session/internal/session"
	"github.com/ichrisbirch/session/internal/tmux"
	"github.com/ichrisbirch/session/internal/ui"
	"github.com/spf13/cobra"
)

// Version information (can be set at build time)
var (
	Version = "0.1.0"
	Commit  = "dev"
)

// Detect the platform (macos or wsl)
func detectPlatform() string {
	// Check if we're on macOS
	if runtime.GOOS == "darwin" {
		return "macos"
	}

	// Check if we're in WSL
	// WSL sets the WSL_DISTRO_NAME environment variable
	if os.Getenv("WSL_DISTRO_NAME") != "" {
		return "wsl"
	}

	// Default to the OS name
	return runtime.GOOS
}

// createSessionManager is a factory function that creates a fully-configured session manager
// This is where we wire up all the dependencies (dependency injection)
func createSessionManager() *session.Manager {
	// Create the real implementations
	tmuxClient := tmux.NewClient()
	tmuxinatorClient := tmux.NewTmuxinatorClient(tmuxClient)
	configLoader := config.NewLoader()
	platform := detectPlatform()

	// Create the manager with all dependencies
	return session.NewManager(tmuxClient, tmuxinatorClient, configLoader, platform)
}

// main is the entry point of the program
func main() {
	// Create the root command
	// Cobra organizes commands in a tree structure
	// The root command is the base command (just "session")
	rootCmd := &cobra.Command{
		Use:   "session",
		Short: "Tmux session manager",
		Long: `A fast and beautiful tmux session manager.

Manages tmux sessions, tmuxinator projects, and default sessions from YAML configuration.
Built with Go, Bubbletea, and Cobra.`,
		Version: fmt.Sprintf("%s (%s)", Version, Commit),
		// Run is called when the user runs "session" with no subcommands
		Run: func(cmd *cobra.Command, args []string) {
			// If the user provided a session name as argument, create/switch to it
			if len(args) > 0 {
				sessionName := args[0]
				manager := createSessionManager()
				if err := manager.CreateOrSwitch(sessionName); err != nil {
					fmt.Fprintf(os.Stderr, "Error: %v\n", err)
					os.Exit(1)
				}
				return
			}

			// No arguments - show the interactive list
			showInteractiveList()
		},
	}

	// Add subcommands
	rootCmd.AddCommand(listCmd())
	rootCmd.AddCommand(lastCmd())

	// Execute the root command
	// This parses command-line arguments and runs the appropriate command
	if err := rootCmd.Execute(); err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		os.Exit(1)
	}
}

// showInteractiveList displays the Bubbletea UI
func showInteractiveList() {
	// Create session manager
	manager := createSessionManager()

	// Get all sessions
	sessions, err := manager.ListAll()
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error listing sessions: %v\n", err)
		os.Exit(1)
	}

	// If no sessions, show a helpful message
	if len(sessions) == 0 {
		fmt.Println("No sessions found.")
		fmt.Println("")
		fmt.Println("Create a new session with: session <name>")
		fmt.Println("Or add default sessions to ~/.config/menu/sessions/sessions-" + detectPlatform() + ".yml")
		return
	}

	// Create and run the Bubbletea program
	model := ui.NewModel(sessions)
	program := tea.NewProgram(model, tea.WithAltScreen())

	// Run the program and get the final model
	// tea.WithAltScreen() uses the "alternate screen" buffer
	// This means the TUI doesn't mess up your terminal scrollback
	finalModel, err := program.Run()
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error running UI: %v\n", err)
		os.Exit(1)
	}

	// Get the user's choice
	// We need a type assertion to get our Model type back
	// The program.Run() returns a tea.Model interface
	choice := finalModel.(ui.Model).GetChoice()
	if choice == "" {
		// User quit without selecting
		return
	}

	// Create or switch to the chosen session
	if err := manager.CreateOrSwitch(choice); err != nil {
		fmt.Fprintf(os.Stderr, "Error switching to session: %v\n", err)
		os.Exit(1)
	}
}

// listCmd creates the "session list" subcommand
func listCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "list",
		Short: "List all sessions",
		Long:  "List all available sessions with details (active, tmuxinator, default)",
		Run: func(cmd *cobra.Command, args []string) {
			manager := createSessionManager()
			sessions, err := manager.ListAll()
			if err != nil {
				fmt.Fprintf(os.Stderr, "Error: %v\n", err)
				os.Exit(1)
			}

			if len(sessions) == 0 {
				fmt.Println("No sessions found")
				return
			}

			// Print sessions in a simple format
			for _, sess := range sessions {
				fmt.Printf("%s %s\n", sess.Icon(), sess.DisplayInfo())
			}
		},
	}
}

// lastCmd creates the "session last" subcommand
func lastCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "last",
		Short: "Switch to last session",
		Long:  "Switch to the previously active tmux session",
		Run: func(cmd *cobra.Command, args []string) {
			manager := createSessionManager()
			if err := manager.SwitchToLast(); err != nil {
				fmt.Fprintf(os.Stderr, "Error: %v\n", err)
				os.Exit(1)
			}
		},
	}
}
