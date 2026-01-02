package main

import (
	"fmt"
	"os"
	"os/exec"
	"runtime"
	"strings"

	"github.com/datapointchris/sess/internal/config"
	"github.com/datapointchris/sess/internal/session"
	"github.com/datapointchris/sess/internal/tmux"
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
		Use:   "session [session-name]",
		Short: "Tmux session manager",
		Long: `A fast and lightweight tmux session manager.

USAGE:
  session                    Show interactive picker
  session <name>             Create or switch to session <name>
  session go <name>          Open session if it exists, otherwise show picker
  session delete <name>      Delete an active session
  session list               List all available sessions
  session last               Switch to last active session
  session reload             Reload tmux config in all sessions

SESSIONS:
  • Active tmux sessions (●)
  • Tmuxinator projects (⚙)
  • Default sessions from config (○)

CONFIG:
  Default sessions: ~/.config/sess/sessions-<platform>.yml
  Platform detected automatically (macos, wsl, etc.)`,
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
	rootCmd.AddCommand(goCmd())
	rootCmd.AddCommand(deleteCmd())

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
		Long: `List all available sessions with details.

Shows:
  ● Active tmux sessions (with window count)
  ⚙ Tmuxinator projects (not yet started)
  ○ Default sessions from config (not yet started)

Example:
  sess list`,
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
		Long: `Switch to the previously active tmux session.

Useful for quickly toggling between two sessions.
Must be run from inside tmux.

Example:
  sess last`,
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
		Long: `Reload tmux configuration file in all active sessions.

Useful after:
  • Changing tmux theme
  • Modifying tmux.conf
  • Updating keybindings

Example:
  sess reload`,
		Run: func(cmd *cobra.Command, args []string) {
			tmuxClient := tmux.NewClient()
			if err := tmuxClient.ReloadConfig(); err != nil {
				fmt.Fprintf(os.Stderr, "Error: %v\n", err)
				os.Exit(1)
			}
		},
	}
}

// goCmd creates the "session go" subcommand
func goCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "go [session-name]",
		Short: "Go to session if it exists, otherwise show picker",
		Long: `Open a session if it exists, otherwise show the interactive picker.

Different from 'session <name>' which creates a new session if not found.
This command will fall back to the picker instead of creating.

Examples:
  sess go dotfiles        # Open dotfiles if it exists, otherwise show picker
  sess go                 # Show picker (same as just 'sess')`,
		Args:  cobra.MaximumNArgs(1),
		Run: func(cmd *cobra.Command, args []string) {
			if len(args) == 0 {
				showInteractiveList()
				return
			}

			sessionName := args[0]
			manager := createSessionManager()

			err := manager.GoToSession(sessionName)
			if err != nil {
				// Session doesn't exist, show the picker
				showInteractiveList()
				return
			}
		},
	}
}

// deleteCmd creates the "session delete" subcommand
func deleteCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "delete <session-name>",
		Short: "Delete a tmux session",
		Long: `Delete an active tmux session.

Only works for active tmux sessions (●).
Cannot delete tmuxinator projects or default sessions.

Examples:
  sess delete old-project     # Delete the 'old-project' session
  sess delete test            # Delete the 'test' session`,
		Args:  cobra.ExactArgs(1),
		Run: func(cmd *cobra.Command, args []string) {
			sessionName := args[0]
			manager := createSessionManager()

			if err := manager.DeleteSession(sessionName); err != nil {
				fmt.Fprintf(os.Stderr, "Error: %v\n", err)
				os.Exit(1)
			}

			fmt.Printf("Session '%s' deleted successfully\n", sessionName)
		},
	}
}
