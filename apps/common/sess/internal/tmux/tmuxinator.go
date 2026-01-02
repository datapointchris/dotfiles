package tmux

import (
	"os/exec"
	"strings"

	"github.com/datapointchris/sess/internal/session"
)

// TmuxinatorClient handles tmuxinator project operations
type TmuxinatorClient struct {
	// We could add configuration here if needed
	tmuxClient *Client
}

// NewTmuxinatorClient creates a new tmuxinator client
func NewTmuxinatorClient(tmuxClient *Client) *TmuxinatorClient {
	return &TmuxinatorClient{
		tmuxClient: tmuxClient,
	}
}

// IsInstalled checks if tmuxinator is available
func (t *TmuxinatorClient) IsInstalled() bool {
	// Check if tmuxinator command exists
	// exec.LookPath searches for an executable in PATH
	_, err := exec.LookPath("tmuxinator")
	return err == nil
}

// ListProjects returns all available tmuxinator projects
func (t *TmuxinatorClient) ListProjects() ([]string, error) {
	if !t.IsInstalled() {
		// If tmuxinator isn't installed, return empty list
		return []string{}, nil
	}

	// Run: tmuxinator list
	cmd := exec.Command("tmuxinator", "list")
	output, err := cmd.CombinedOutput()
	if err != nil {
		// If command fails, return empty list
		return []string{}, nil
	}

	// Parse the output
	// tmuxinator list output looks like:
	// tmuxinator projects:
	// project1 project2 project3
	lines := strings.Split(strings.TrimSpace(string(output)), "\n")
	if len(lines) < 2 {
		return []string{}, nil
	}

	// Skip the first line (header) and get the project names
	// Projects are space-separated on subsequent lines
	var projects []string
	for _, line := range lines[1:] {
		// Split by whitespace and add all non-empty entries
		for _, project := range strings.Fields(line) {
			if project != "" {
				projects = append(projects, project)
			}
		}
	}

	return projects, nil
}

// ProjectExists checks if a tmuxinator project exists
func (t *TmuxinatorClient) ProjectExists(name string) (bool, error) {
	projects, err := t.ListProjects()
	if err != nil {
		return false, err
	}

	// Check if name is in the list of projects
	for _, project := range projects {
		if project == name {
			return true, nil
		}
	}

	return false, nil
}

// StartProject starts a tmuxinator project
func (t *TmuxinatorClient) StartProject(name string, fromTmux bool) error {
	var cmd *exec.Cmd

	if fromTmux {
		// If we're in tmux, start without attaching then switch
		// tmuxinator start <name> --no-attach
		cmd = exec.Command("tmuxinator", "start", name, "--no-attach")
		if err := cmd.Run(); err != nil {
			return err
		}

		// Switch to the newly created session
		// Tmuxinator creates a session with the same name as the project
		return t.tmuxClient.SwitchToSession(name, true)
	} else {
		// If we're not in tmux, start and attach
		// tmuxinator start <name>
		cmd = exec.Command("tmuxinator", "start", name)
		return cmd.Run()
	}
}

// Verify interface implementation at compile time
var _ session.TmuxinatorClient = (*TmuxinatorClient)(nil)
