package session

import (
	"fmt"
	"time"
)

// SessionType represents the different types of sessions we support
// In Go, we use constants with a custom type for type-safe enumerations
type SessionType string

const (
	// SessionTypeTmux represents an active tmux session
	SessionTypeTmux SessionType = "tmux"

	// SessionTypeTmuxinator represents a tmuxinator project
	SessionTypeTmuxinator SessionType = "tmuxinator"

	// SessionTypeDefault represents a default session from YAML config
	SessionTypeDefault SessionType = "default"
)

// Session represents a tmux session with metadata
// In Go, we use structs to define data structures
// The fields with capital letters are "exported" (public)
type Session struct {
	// Name is the session name
	Name string

	// Type indicates the session type (tmux, tmuxinator, or default)
	Type SessionType

	// WindowCount is the number of windows (only for active sessions)
	WindowCount int

	// Directory is the starting directory (for default sessions)
	Directory string

	// Description provides additional context about the session
	Description string

	// IsActive indicates if the session is currently running
	IsActive bool

	// TmuxinatorProject is the tmuxinator project name (if applicable)
	TmuxinatorProject string

	// CreatedAt is when the session was created (for active sessions)
	CreatedAt time.Time
}

// SessionConfig represents a default session from YAML configuration
// This maps to the structure in ~/.config/sess/sessions-macos.yml
type SessionConfig struct {
	// Name is the session name
	Name string `yaml:"name"`

	// Description explains what the session is for
	Description string `yaml:"description"`

	// Directory is the starting directory (can use ~ for home)
	Directory string `yaml:"directory"`

	// TmuxinatorProject is the tmuxinator project to use (optional)
	// The backticks define "struct tags" - metadata about the field
	// yaml:"tmuxinator_project" tells the YAML parser what field name to look for
	TmuxinatorProject string `yaml:"tmuxinator_project,omitempty"`
}

// SessionsConfig represents the root YAML configuration
type SessionsConfig struct {
	// Sessions is the list of default session configurations
	Sessions []SessionConfig `yaml:"sessions"`
}

// DisplayInfo returns formatted information for display in the UI
// This is a "method" on the Session type - like a function that belongs to Session
// The (s Session) before the method name is called a "receiver"
func (s Session) DisplayInfo() string {
	// Switch statements in Go are cleaner than in many languages
	// You don't need break statements - they're automatic
	switch s.Type {
	case SessionTypeTmux:
		// If it's an active tmux session, show window count
		return s.Name + " (" + formatWindowCount(s.WindowCount) + ")"
	case SessionTypeTmuxinator:
		// If it's a tmuxinator project, indicate that
		return s.Name + " (tmuxinator)"
	case SessionTypeDefault:
		// If it's a default session, show it's not started
		return s.Name + " (not started)"
	default:
		// Default case if somehow we have an unknown type
		return s.Name
	}
}

// Icon returns the visual indicator for the session type
// This matches the bash version: ● for active, ⚙ for tmuxinator, ○ for default
func (s Session) Icon() string {
	switch s.Type {
	case SessionTypeTmux:
		return "●" // Filled circle for active sessions
	case SessionTypeTmuxinator:
		return "⚙" // Gear icon for tmuxinator projects
	case SessionTypeDefault:
		return "○" // Hollow circle for not-yet-started default sessions
	default:
		return " "
	}
}

// formatWindowCount formats the window count for display
// This is a private helper function (lowercase first letter = private in Go)
func formatWindowCount(count int) string {
	// In Go, we import "fmt" for string formatting
	// But for simple string building, we can use the + operator
	if count == 1 {
		return "1 window"
	}
	// For converting int to string, we need strconv.Itoa() or fmt.Sprintf()
	// We'll use fmt.Sprintf for clarity
	return fmt.Sprintf("%d windows", count)
}
