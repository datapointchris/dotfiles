package tmux

import (
	"fmt"
	"os"
	"os/exec"
	"strconv"
	"strings"
	"time"

	"github.com/datapointchris/sess/internal/session"
)

// Client is the real implementation of the TmuxClient interface
// It executes actual tmux commands
type Client struct {
	// In a real application, you might have configuration here
	// For now, we'll keep it simple
}

// NewClient creates a new tmux client
// This is a "constructor" function - Go doesn't have constructors like Java/C++
// Instead, we use functions that return initialized structs
func NewClient() *Client {
	// The & operator creates a pointer to the struct
	// Pointers are important in Go - they let you modify the original
	// instead of a copy
	return &Client{}
}

// ListSessions returns all active tmux sessions
// The (c *Client) is the receiver - it makes this a method on Client
// The * means it receives a pointer to Client
func (c *Client) ListSessions() ([]session.Session, error) {
	// exec.Command creates a command to run
	// We're running: tmux list-sessions -F "#{session_name}:#{session_windows}"
	cmd := exec.Command("tmux", "list-sessions", "-F", "#{session_name}:#{session_windows}")

	// Run the command and capture output
	output, err := cmd.CombinedOutput()
	if err != nil {
		// If tmux returns an error (like "no sessions"), that's not really an error
		// for us - it just means no sessions exist
		// We'll return an empty slice (Go's term for a dynamic array)
		return []session.Session{}, nil
	}

	// Parse the output into sessions
	// strings.TrimSpace removes leading/trailing whitespace
	lines := strings.Split(strings.TrimSpace(string(output)), "\n")

	// Make a slice to hold our sessions
	// make() allocates memory for a slice
	// We estimate capacity with len(lines) for efficiency
	sessions := make([]session.Session, 0, len(lines))

	for _, line := range lines {
		// range iterates over a slice
		// _ is a blank identifier - we don't need the index, just the value
		if line == "" {
			continue // skip empty lines
		}

		// Split each line into name and window count
		// Format is "name:count"
		parts := strings.Split(line, ":")
		if len(parts) != 2 {
			continue // skip malformed lines
		}

		name := parts[0]
		windowCount, err := strconv.Atoi(parts[1])
		if err != nil {
			// If we can't parse the number, default to 0
			windowCount = 0
		}

		// Append to our sessions slice
		sessions = append(sessions, session.Session{
			Name:        name,
			Type:        session.SessionTypeTmux,
			WindowCount: windowCount,
			IsActive:    true,
			CreatedAt:   time.Now(), // We could parse this from tmux if needed
		})
	}

	return sessions, nil
}

// SessionExists checks if a session exists
func (c *Client) SessionExists(name string) (bool, error) {
	// tmux has-session -t <name>
	// Returns 0 if session exists, 1 if it doesn't
	cmd := exec.Command("tmux", "has-session", "-t", name)

	// Run() executes the command and waits for it to complete
	err := cmd.Run()
	if err != nil {
		// If has-session returns error, session doesn't exist
		return false, nil
	}

	return true, nil
}

// CreateSession creates a new tmux session
func (c *Client) CreateSession(sess session.Session) error {
	// Determine if we're already in tmux
	inTmux := c.IsInsideTmux()

	var cmd *exec.Cmd
	if inTmux {
		// If we're in tmux, create a detached session then switch to it
		// tmux new-session -d -s <name> -c <directory>
		if sess.Directory != "" {
			cmd = exec.Command("tmux", "new-session", "-d", "-s", sess.Name, "-c", sess.Directory)
		} else {
			cmd = exec.Command("tmux", "new-session", "-d", "-s", sess.Name)
		}

		if err := cmd.Run(); err != nil {
			return fmt.Errorf("failed to create session: %w", err)
		}

		// Now switch to it
		return c.SwitchToSession(sess.Name, true)
	} else {
		// If we're not in tmux, create and attach in one command
		// tmux new-session -s <name> -c <directory>
		if sess.Directory != "" {
			cmd = exec.Command("tmux", "new-session", "-s", sess.Name, "-c", sess.Directory)
		} else {
			cmd = exec.Command("tmux", "new-session", "-s", sess.Name)
		}

		// For attach commands, we need to connect stdin/stdout/stderr
		// so the user can interact with tmux
		cmd.Stdin = os.Stdin
		cmd.Stdout = os.Stdout
		cmd.Stderr = os.Stderr

		return cmd.Run()
	}
}

// SwitchToSession switches to an existing session
func (c *Client) SwitchToSession(name string, fromTmux bool) error {
	var cmd *exec.Cmd
	if fromTmux {
		// If we're in tmux, use switch-client
		cmd = exec.Command("tmux", "switch-client", "-t", name)
	} else {
		// If we're not in tmux, use attach-session
		cmd = exec.Command("tmux", "attach-session", "-t", name)
		cmd.Stdin = os.Stdin
		cmd.Stdout = os.Stdout
		cmd.Stderr = os.Stderr
	}

	return cmd.Run()
}

// AttachToSession attaches to a session (used when not in tmux)
func (c *Client) AttachToSession(name string) error {
	cmd := exec.Command("tmux", "attach-session", "-t", name)
	cmd.Stdin = os.Stdin
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	return cmd.Run()
}

// IsInsideTmux checks if we're currently running inside tmux
func (c *Client) IsInsideTmux() bool {
	// tmux sets the TMUX environment variable when you're inside a session
	// In Go, os.Getenv() retrieves environment variables
	return os.Getenv("TMUX") != ""
}

// SwitchToLastSession switches to the previously active session
func (c *Client) SwitchToLastSession() error {
	if !c.IsInsideTmux() {
		return fmt.Errorf("not in a tmux session")
	}

	// tmux switch-client -l (l for "last")
	cmd := exec.Command("tmux", "switch-client", "-l")
	return cmd.Run()
}

// DeleteSession deletes a tmux session
func (c *Client) DeleteSession(name string) error {
	exists, err := c.SessionExists(name)
	if err != nil {
		return err
	}
	if !exists {
		return fmt.Errorf("session '%s' does not exist", name)
	}

	cmd := exec.Command("tmux", "kill-session", "-t", name)
	if err := cmd.Run(); err != nil {
		return fmt.Errorf("failed to delete session: %w", err)
	}

	return nil
}

// ReloadConfig reloads tmux configuration in all active sessions
func (c *Client) ReloadConfig() error {
	// Get all active sessions
	sessions, err := c.ListSessions()
	if err != nil {
		return fmt.Errorf("failed to list sessions: %w", err)
	}

	if len(sessions) == 0 {
		return fmt.Errorf("no active tmux sessions")
	}

	// Reload config in each session
	configPath := os.ExpandEnv("$HOME/.config/tmux/tmux.conf")
	for _, sess := range sessions {
		cmd := exec.Command("tmux", "source-file", "-t", sess.Name, configPath)
		if err := cmd.Run(); err != nil {
			return fmt.Errorf("failed to reload config for session %s: %w", sess.Name, err)
		}
		fmt.Printf("  ✓ Reloaded session: %s\n", sess.Name)
	}

	return nil
}

// Verify that Client implements the TmuxClient interface at compile time
// This is a Go idiom - if Client doesn't implement TmuxClient, this won't compile
// The _ means we're declaring a variable but never using it
var _ session.TmuxClient = (*Client)(nil)
