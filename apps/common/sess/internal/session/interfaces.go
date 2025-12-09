package session

// Interfaces define "contracts" - they specify what methods a type must have
// without specifying HOW those methods work. This is crucial for testing
// because we can create "mock" versions that implement these interfaces.

// TmuxClient defines operations for interacting with tmux
// Any type that implements these methods can be used as a TmuxClient
type TmuxClient interface {
	// ListSessions returns all active tmux sessions
	// In Go, functions can return multiple values
	// The convention is (result, error) - if error is nil, everything worked
	ListSessions() ([]Session, error)

	// SessionExists checks if a session with the given name exists
	SessionExists(name string) (bool, error)

	// CreateSession creates a new tmux session
	// The Session parameter contains the configuration
	CreateSession(session Session) error

	// SwitchToSession switches to an existing session
	// fromTmux indicates if we're already inside tmux (affects the command used)
	SwitchToSession(name string, fromTmux bool) error

	// AttachToSession attaches to a session (used when not already in tmux)
	AttachToSession(name string) error

	// IsInsideTmux checks if we're currently running inside a tmux session
	IsInsideTmux() bool

	// SwitchToLastSession switches to the previously active session
	SwitchToLastSession() error

	// DeleteSession deletes a tmux session
	DeleteSession(name string) error

	// ReloadConfig reloads tmux configuration in all sessions
	ReloadConfig() error
}

// TmuxinatorClient defines operations for interacting with tmuxinator
type TmuxinatorClient interface {
	// ListProjects returns all available tmuxinator projects
	ListProjects() ([]string, error)

	// ProjectExists checks if a tmuxinator project exists
	ProjectExists(name string) (bool, error)

	// StartProject starts a tmuxinator project
	// fromTmux indicates if we're already inside tmux
	StartProject(name string, fromTmux bool) error

	// IsInstalled checks if tmuxinator is available on the system
	IsInstalled() bool
}

// ConfigLoader defines operations for loading session configurations
type ConfigLoader interface {
	// LoadDefaultSessions loads the default sessions from YAML config
	// platform would be "macos" or "wsl"
	LoadDefaultSessions(platform string) ([]SessionConfig, error)

	// GetSessionConfig retrieves a specific default session by name
	GetSessionConfig(name string, platform string) (*SessionConfig, error)
}

// Note on interfaces in Go:
// 1. You don't explicitly say "this type implements this interface"
// 2. If a type has all the methods in an interface, it automatically implements it
// 3. This is called "implicit interface satisfaction" or "duck typing"
// 4. It makes testing easy - create a mock type with the same methods
//
// Example:
//   type MockTmuxClient struct {}
//   func (m *MockTmuxClient) ListSessions() ([]Session, error) {
//     return []Session{{Name: "test"}}, nil
//   }
//   ... implement other methods ...
//   // Now MockTmuxClient automatically implements TmuxClient!
