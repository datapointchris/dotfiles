package main

import (
	"fmt"
	"os"
	"os/exec"
	"runtime"
	"strings"

	"github.com/ichrisbirch/sess/internal/config"
	"github.com/ichrisbirch/sess/internal/session"
	"github.com/ichrisbirch/sess/internal/tmux"
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
		Long: `A fast and lightweight tmux session manager.

Manages tmux sessions, tmuxinator projects, and default sessions from YAML configuration.
Built with Go, gum, and Cobra.`,
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
	rootCmd.AddCommand(reloadCmd())

	// Execute the root command
	// This parses command-line arguments and runs the appropriate command
	if err := rootCmd.Execute(); err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		os.Exit(1)
	}
}

// showInteractiveList displays the gum-based UI
func showInteractiveList() {
	// Check if gum is available
	if _, err := exec.LookPath("gum"); err != nil {
		fmt.Fprintln(os.Stderr, "Error: gum is not installed")
		fmt.Fprintln(os.Stderr, "Install with: brew install gum")
		os.Exit(1)
	}

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
		fmt.Println("Or add default sessions to ~/.config/sess/sessions-" + detectPlatform() + ".yml")
		return
	}

	// Format sessions for gum
	var options []string
	sessionMap := make(map[string]string) // Map display text to session name

	for _, sess := range sessions {
		displayText := fmt.Sprintf("%s %s", sess.Icon(), sess.DisplayInfo())
		options = append(options, displayText)
		sessionMap[displayText] = sess.Name
	}

	// Add "Create New Session" option
	options = append(options, "+ Create New Session")

	// Call gum choose
	cmd := exec.Command("gum", append([]string{"choose", "--header=Tmux Sessions"}, options...)...)
	cmd.Stderr = os.Stderr
	output, err := cmd.Output()
	if err != nil {
		// User cancelled or error occurred
		return
	}

	choice := strings.TrimSpace(string(output))
	if choice == "" {
		return
	}

	// Handle "Create New Session"
	if choice == "+ Create New Session" {
		newNameCmd := exec.Command("gum", "input", "--placeholder", "Session name")
		newNameCmd.Stderr = os.Stderr
		newNameOutput, err := newNameCmd.Output()
		if err != nil {
			return
		}
		newName := strings.TrimSpace(string(newNameOutput))
		if newName == "" {
			return
		}
		if err := manager.CreateOrSwitch(newName); err != nil {
			fmt.Fprintf(os.Stderr, "Error creating session: %v\n", err)
			os.Exit(1)
		}
		return
	}

	// Get the session name from the display text
	sessionName := sessionMap[choice]
	if sessionName == "" {
		// Extract name from display text (fallback)
		parts := strings.Fields(choice)
		if len(parts) >= 2 {
			sessionName = parts[1] // Skip icon
		}
	}

	// Create or switch to the chosen session
	if err := manager.CreateOrSwitch(sessionName); err != nil {
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

// reloadCmd creates the "session reload" subcommand
func reloadCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "reload",
		Short: "Reload tmux config in all sessions",
		Long:  "Reload tmux configuration file in all active sessions (useful after theme changes)",
		Run: func(cmd *cobra.Command, args []string) {
			tmuxClient := tmux.NewClient()
			if err := tmuxClient.ReloadConfig(); err != nil {
				fmt.Fprintf(os.Stderr, "Error: %v\n", err)
				os.Exit(1)
			}
		},
	}
}
