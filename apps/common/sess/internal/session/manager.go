package session

import (
	"fmt"
	"sort"
)

// Manager orchestrates session operations using injected dependencies
// This is the dependency injection pattern - instead of creating its own
// tmux client, config loader, etc., the Manager receives them
// This makes testing easy - we can inject mocks instead of real implementations
type Manager struct {
	tmuxClient       TmuxClient
	tmuxinatorClient TmuxinatorClient
	configLoader     ConfigLoader
	platform         string
}

// NewManager creates a new session manager with the given dependencies
func NewManager(
	tmuxClient TmuxClient,
	tmuxinatorClient TmuxinatorClient,
	configLoader ConfigLoader,
	platform string,
) *Manager {
	return &Manager{
		tmuxClient:       tmuxClient,
		tmuxinatorClient: tmuxinatorClient,
		configLoader:     configLoader,
		platform:         platform,
	}
}

// ListAll returns all available sessions from all sources
// This aggregates:
// - Active tmux sessions
// - Tmuxinator projects (not already running)
// - Default sessions from config (not already running)
func (m *Manager) ListAll() ([]Session, error) {
	// Start with a slice to hold all sessions
	sessions := []Session{}

	// 1. Get active tmux sessions
	tmuxSessions, err := m.tmuxClient.ListSessions()
	if err != nil {
		// If we can't list tmux sessions, that's not fatal
		// Just log it and continue (we'll add logging later)
		// For now, we'll just ignore the error
	} else {
		sessions = append(sessions, tmuxSessions...)
	}

	// Build a map of session names we've already added
	// This prevents duplicates
	// A map in Go is like a dictionary - key -> value
	existingNames := make(map[string]bool)
	for _, sess := range sessions {
		existingNames[sess.Name] = true
	}

	// 2. Get tmuxinator projects (only if tmuxinator is installed)
	if m.tmuxinatorClient.IsInstalled() {
		projects, err := m.tmuxinatorClient.ListProjects()
		if err == nil {
			for _, projectName := range projects {
				// Only add if not already running as a tmux session
				if !existingNames[projectName] {
					sessions = append(sessions, Session{
						Name:     projectName,
						Type:     SessionTypeTmuxinator,
						IsActive: false,
					})
					existingNames[projectName] = true
				}
			}
		}
	}

	// 3. Get default sessions from config
	defaultSessions, err := m.configLoader.LoadDefaultSessions(m.platform)
	if err == nil {
		for _, config := range defaultSessions {
			// Only add if not already in the list
			if !existingNames[config.Name] {
				sessions = append(sessions, Session{
					Name:        config.Name,
					Type:        SessionTypeDefault,
					Description: config.Description,
					Directory:   config.Directory,
					IsActive:    false,
				})
				existingNames[config.Name] = true
			}
		}
	}

	// Sort sessions by name for consistent ordering
	// sort.Slice() sorts a slice using a custom comparison function
	sort.Slice(sessions, func(i, j int) bool {
		return sessions[i].Name < sessions[j].Name
	})

	return sessions, nil
}

// CreateOrSwitch creates a new session or switches to an existing one
// This is the main operation when a user selects a session
func (m *Manager) CreateOrSwitch(name string) error {
	// First, check if it's already an active tmux session
	exists, err := m.tmuxClient.SessionExists(name)
	if err != nil {
		return fmt.Errorf("failed to check if session exists: %w", err)
	}

	if exists {
		// Session exists, just switch to it
		inTmux := m.tmuxClient.IsInsideTmux()
		return m.tmuxClient.SwitchToSession(name, inTmux)
	}

	// Not an active session, check if it's a tmuxinator project
	if m.tmuxinatorClient.IsInstalled() {
		isProject, err := m.tmuxinatorClient.ProjectExists(name)
		if err == nil && isProject {
			// It's a tmuxinator project, start it
			inTmux := m.tmuxClient.IsInsideTmux()
			return m.tmuxinatorClient.StartProject(name, inTmux)
		}
	}

	// Check if it's a default session from config
	config, err := m.configLoader.GetSessionConfig(name, m.platform)
	if err == nil {
		// It's a default session, create it based on config
		return m.createDefaultSession(config)
	}

	// Not found in any source, create a new basic tmux session
	return m.tmuxClient.CreateSession(Session{
		Name: name,
		Type: SessionTypeTmux,
	})
}

// createDefaultSession creates a session from a YAML config
func (m *Manager) createDefaultSession(config *SessionConfig) error {
	// If the config specifies a tmuxinator project, use that
	if config.TmuxinatorProject != "" && m.tmuxinatorClient.IsInstalled() {
		inTmux := m.tmuxClient.IsInsideTmux()
		return m.tmuxinatorClient.StartProject(config.TmuxinatorProject, inTmux)
	}

	// Otherwise, create a simple session with the specified directory
	return m.tmuxClient.CreateSession(Session{
		Name:      config.Name,
		Type:      SessionTypeTmux,
		Directory: config.Directory,
	})
}

// SwitchToLast switches to the previously active session
func (m *Manager) SwitchToLast() error {
	return m.tmuxClient.SwitchToLastSession()
}

// SessionExists checks if a session exists in any source (tmux, tmuxinator, or default config)
func (m *Manager) SessionExists(name string) (bool, error) {
	// Check if it's an active tmux session
	exists, err := m.tmuxClient.SessionExists(name)
	if err != nil {
		return false, err
	}
	if exists {
		return true, nil
	}

	// Check if it's a tmuxinator project
	if m.tmuxinatorClient.IsInstalled() {
		isProject, err := m.tmuxinatorClient.ProjectExists(name)
		if err == nil && isProject {
			return true, nil
		}
	}

	// Check if it's a default session from config
	_, err = m.configLoader.GetSessionConfig(name, m.platform)
	if err == nil {
		return true, nil
	}

	return false, nil
}

// GoToSession opens a session if it exists, returns error if it doesn't
// This is different from CreateOrSwitch which creates a new session if not found
func (m *Manager) GoToSession(name string) error {
	exists, err := m.SessionExists(name)
	if err != nil {
		return err
	}
	if !exists {
		return fmt.Errorf("session '%s' not found", name)
	}

	return m.CreateOrSwitch(name)
}

// DeleteSession deletes an active tmux session
func (m *Manager) DeleteSession(name string) error {
	return m.tmuxClient.DeleteSession(name)
}

// GetSessionInfo returns detailed information about a session
// This is useful for displaying additional context in the UI
func (m *Manager) GetSessionInfo(name string) (string, error) {
	// Check if it's an active session
	exists, err := m.tmuxClient.SessionExists(name)
	if err != nil {
		return "", err
	}

	if exists {
		// Get the active sessions and find this one
		sessions, err := m.tmuxClient.ListSessions()
		if err != nil {
			return "", err
		}

		for _, sess := range sessions {
			if sess.Name == name {
				return sess.DisplayInfo(), nil
			}
		}
	}

	// Check if it's a tmuxinator project
	if m.tmuxinatorClient.IsInstalled() {
		isProject, err := m.tmuxinatorClient.ProjectExists(name)
		if err == nil && isProject {
			return "tmuxinator project", nil
		}
	}

	// Check if it's a default session
	config, err := m.configLoader.GetSessionConfig(name, m.platform)
	if err == nil {
		if config.Description != "" {
			return fmt.Sprintf("default: %s", config.Description), nil
		}
		return "default (not started)", nil
	}

	return "new session", nil
}
