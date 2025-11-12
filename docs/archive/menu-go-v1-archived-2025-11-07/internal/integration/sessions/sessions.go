package sessions

import (
	"context"
	"encoding/json"
	"fmt"
	"os/exec"
	"strings"

	"github.com/ichrisbirch/menu/internal/integration"
)

// SessionsIntegration integrates with the session-go binary
// This integration is TypeInteractive - it can list sessions and launch the session TUI
type SessionsIntegration struct {
	binaryPath string // Path to session binary
}

// NewIntegration creates a new sessions integration
// If binaryPath is empty, it will look for "session" in PATH
func NewIntegration(binaryPath string) *SessionsIntegration {
	if binaryPath == "" {
		binaryPath = "session"
	}

	return &SessionsIntegration{
		binaryPath: binaryPath,
	}
}

// Name returns the integration name
func (s *SessionsIntegration) Name() string {
	return "sessions"
}

// Type returns the integration type
func (s *SessionsIntegration) Type() integration.IntegrationType {
	return integration.TypeInteractive
}

// Load fetches all available sessions
// Uses "session list" command to get sessions in JSON format
func (s *SessionsIntegration) Load(ctx context.Context) ([]integration.Item, error) {
	// Try to run "session list" to get all sessions
	// For now, we'll parse the human-readable output
	// TODO: Add --json flag to session binary for easier parsing

	cmd := exec.CommandContext(ctx, s.binaryPath, "list")
	output, err := cmd.CombinedOutput()
	if err != nil {
		// If session binary doesn't exist or fails, return empty list
		// This allows the menu to work even without session installed
		return []integration.Item{}, nil
	}

	return s.parseSessions(string(output)), nil
}

// parseSessions parses the output from "session list"
// Expected format: "● session-name (3 windows) /path/to/dir"
func (s *SessionsIntegration) parseSessions(output string) []integration.Item {
	lines := strings.Split(strings.TrimSpace(output), "\n")
	items := make([]integration.Item, 0, len(lines))

	for _, line := range lines {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}

		item := s.parseSessionLine(line)
		if item.ID != "" {
			items = append(items, item)
		}
	}

	return items
}

// parseSessionLine parses a single line from session list output
func (s *SessionsIntegration) parseSessionLine(line string) integration.Item {
	// Expected format: "● session-name (3 windows) /path/to/dir"
	// or: "⚙ tmuxinator-project /path/to/dir"
	// or: "○ default-session /path/to/dir - Not started"

	var icon, name, status, description string

	// Extract icon (first character)
	if len(line) > 0 {
		icon = string([]rune(line)[0])
		line = strings.TrimSpace(line[len(icon):])
	}

	// Parse the rest
	parts := strings.Fields(line)
	if len(parts) == 0 {
		return integration.Item{}
	}

	name = parts[0]

	// Determine status based on icon
	switch icon {
	case "●":
		status = "active"
		description = "Active tmux session"
	case "⚙":
		status = "tmuxinator"
		description = "Tmuxinator project"
	case "○":
		status = "default"
		description = "Default session (not started)"
	default:
		status = "unknown"
		description = "Session"
	}

	// Extract additional info (windows count, directory)
	if len(parts) > 1 {
		// Join remaining parts as description
		desc := strings.Join(parts[1:], " ")
		if desc != "" {
			description = desc
		}
	}

	return integration.Item{
		ID:          name,
		Title:       name,
		Description: description,
		Category:    "Sessions",
		Icon:        icon,
		Tags:        []string{"tmux", "session"},
		Status:      status,
		Source:      "sessions",
		Executable:  true,
		Command:     fmt.Sprintf("%s %s", s.binaryPath, name),
		IsInteractive: true, // Needs to run in terminal
		Details: map[string]interface{}{
			"type": status,
		},
	}
}

// Get retrieves a specific session by name
func (s *SessionsIntegration) Get(ctx context.Context, id string) (*integration.Item, error) {
	// Load all sessions and find the one with matching ID
	items, err := s.Load(ctx)
	if err != nil {
		return nil, err
	}

	for _, item := range items {
		if item.ID == id {
			return &item, nil
		}
	}

	return nil, fmt.Errorf("session %q not found", id)
}

// Search filters sessions by query
func (s *SessionsIntegration) Search(ctx context.Context, query string) ([]integration.Item, error) {
	items, err := s.Load(ctx)
	if err != nil {
		return nil, err
	}

	query = strings.ToLower(query)
	filtered := make([]integration.Item, 0)

	for _, item := range items {
		if strings.Contains(strings.ToLower(item.Title), query) ||
			strings.Contains(strings.ToLower(item.Description), query) {
			filtered = append(filtered, item)
		}
	}

	return filtered, nil
}

// Execute switches to or creates a session
func (s *SessionsIntegration) Execute(ctx context.Context, item integration.Item) (string, error) {
	if !item.Executable {
		return "", fmt.Errorf("item %q is not executable", item.ID)
	}

	// For sessions, we need to execute in the user's terminal
	// Return the command to be executed by the caller
	return item.Command, nil
}

// SupportsExecution indicates that sessions can be executed
func (s *SessionsIntegration) SupportsExecution() bool {
	return true
}

// Refresh reloads session data
func (s *SessionsIntegration) Refresh(ctx context.Context) error {
	// For sessions, refresh just means we'll re-run Load next time
	// No persistent cache to clear
	return nil
}

// LaunchInteractive launches the interactive session selector
// This is a special method for this integration
func (s *SessionsIntegration) LaunchInteractive() (string, error) {
	// Return command to launch the interactive session selector
	return s.binaryPath, nil
}

// SessionData represents detailed session information
// This could be used if we add JSON output to session binary
type SessionData struct {
	Name        string `json:"name"`
	Type        string `json:"type"` // "tmux", "tmuxinator", "default"
	Windows     int    `json:"windows,omitempty"`
	Directory   string `json:"directory,omitempty"`
	Description string `json:"description,omitempty"`
	Active      bool   `json:"active"`
}

// parseJSONSessions parses JSON output from session binary
// This is for future use when session binary supports JSON output
func (s *SessionsIntegration) parseJSONSessions(jsonData string) ([]integration.Item, error) {
	var sessions []SessionData
	if err := json.Unmarshal([]byte(jsonData), &sessions); err != nil {
		return nil, fmt.Errorf("failed to parse session JSON: %w", err)
	}

	items := make([]integration.Item, 0, len(sessions))
	for _, session := range sessions {
		icon := "○"
		status := "inactive"
		if session.Active {
			icon = "●"
			status = "active"
		} else if session.Type == "tmuxinator" {
			icon = "⚙"
			status = "tmuxinator"
		}

		description := session.Description
		if session.Windows > 0 {
			description = fmt.Sprintf("(%d windows) %s", session.Windows, description)
		}

		items = append(items, integration.Item{
			ID:          session.Name,
			Title:       session.Name,
			Description: description,
			Category:    "Sessions",
			Icon:        icon,
			Tags:        []string{"tmux", "session", session.Type},
			Status:      status,
			Source:      "sessions",
			Executable:  true,
			Command:     fmt.Sprintf("%s %s", s.binaryPath, session.Name),
			IsInteractive: true,
			Details: map[string]interface{}{
				"type":      session.Type,
				"windows":   session.Windows,
				"directory": session.Directory,
			},
		})
	}

	return items, nil
}
