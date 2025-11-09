package session

import (
	"errors"
	"testing"
)

// Mock implementations for testing
// These implement our interfaces but with fake data instead of real tmux commands

// MockTmuxClient is a fake tmux client for testing
type MockTmuxClient struct {
	// These fields let us control what the mock returns
	sessions       []Session
	sessionExists  bool
	isInsideTmux   bool
	createErr      error
	switchErr      error
	lastSessionErr error
}

// Implement all TmuxClient interface methods
func (m *MockTmuxClient) ListSessions() ([]Session, error) {
	return m.sessions, nil
}

func (m *MockTmuxClient) SessionExists(name string) (bool, error) {
	// Check if the session is in our mock list
	for _, sess := range m.sessions {
		if sess.Name == name {
			return true, nil
		}
	}
	return m.sessionExists, nil
}

func (m *MockTmuxClient) CreateSession(session Session) error {
	return m.createErr
}

func (m *MockTmuxClient) SwitchToSession(name string, fromTmux bool) error {
	return m.switchErr
}

func (m *MockTmuxClient) AttachToSession(name string) error {
	return nil
}

func (m *MockTmuxClient) IsInsideTmux() bool {
	return m.isInsideTmux
}

func (m *MockTmuxClient) SwitchToLastSession() error {
	return m.lastSessionErr
}

// MockTmuxinatorClient is a fake tmuxinator client for testing
type MockTmuxinatorClient struct {
	projects      []string
	isInstalled   bool
	projectExists bool
	startErr      error
}

func (m *MockTmuxinatorClient) ListProjects() ([]string, error) {
	return m.projects, nil
}

func (m *MockTmuxinatorClient) ProjectExists(name string) (bool, error) {
	// Check if the project is in our mock list
	for _, proj := range m.projects {
		if proj == name {
			return true, nil
		}
	}
	return m.projectExists, nil
}

func (m *MockTmuxinatorClient) StartProject(name string, fromTmux bool) error {
	return m.startErr
}

func (m *MockTmuxinatorClient) IsInstalled() bool {
	return m.isInstalled
}

// MockConfigLoader is a fake config loader for testing
type MockConfigLoader struct {
	sessions []SessionConfig
	loadErr  error
}

func (m *MockConfigLoader) LoadDefaultSessions(platform string) ([]SessionConfig, error) {
	if m.loadErr != nil {
		return nil, m.loadErr
	}
	return m.sessions, nil
}

func (m *MockConfigLoader) GetSessionConfig(name string, platform string) (*SessionConfig, error) {
	// Find the session in our mock list
	for _, sess := range m.sessions {
		if sess.Name == name {
			// Return a copy
			result := sess
			return &result, nil
		}
	}
	return nil, errors.New("session not found")
}

// Test helper function to create a manager with mocks
func createTestManager(
	tmuxSessions []Session,
	tmuxinatorProjects []string,
	defaultSessions []SessionConfig,
) *Manager {
	tmuxClient := &MockTmuxClient{
		sessions: tmuxSessions,
	}

	tmuxinatorClient := &MockTmuxinatorClient{
		projects:    tmuxinatorProjects,
		isInstalled: len(tmuxinatorProjects) > 0,
	}

	configLoader := &MockConfigLoader{
		sessions: defaultSessions,
	}

	return NewManager(tmuxClient, tmuxinatorClient, configLoader, "macos")
}

// TestListAll tests the ListAll function
// This is a "table-driven test" - a common Go testing pattern
func TestListAll(t *testing.T) {
	// t is the testing object - it has methods like Error, Fatal, etc.

	// Define test cases
	// Each test case has a name and test data
	tests := []struct {
		name               string
		tmuxSessions       []Session
		tmuxinatorProjects []string
		defaultSessions    []SessionConfig
		wantCount          int
		wantTypes          map[SessionType]int
	}{
		{
			name: "all three types of sessions",
			tmuxSessions: []Session{
				{Name: "active1", Type: SessionTypeTmux, WindowCount: 2, IsActive: true},
				{Name: "active2", Type: SessionTypeTmux, WindowCount: 1, IsActive: true},
			},
			tmuxinatorProjects: []string{"proj1", "proj2"},
			defaultSessions: []SessionConfig{
				{Name: "default1", Directory: "~/dir1"},
				{Name: "default2", Directory: "~/dir2"},
			},
			wantCount: 6,
			wantTypes: map[SessionType]int{
				SessionTypeTmux:       2,
				SessionTypeTmuxinator: 2,
				SessionTypeDefault:    2,
			},
		},
		{
			name: "no duplicates when tmuxinator project is running",
			tmuxSessions: []Session{
				{Name: "proj1", Type: SessionTypeTmux, WindowCount: 2, IsActive: true},
			},
			tmuxinatorProjects: []string{"proj1", "proj2"},
			defaultSessions:    []SessionConfig{},
			wantCount:          2, // Only proj1 (active) and proj2 (tmuxinator)
			wantTypes: map[SessionType]int{
				SessionTypeTmux:       1,
				SessionTypeTmuxinator: 1,
			},
		},
		{
			name:               "no sessions",
			tmuxSessions:       []Session{},
			tmuxinatorProjects: []string{},
			defaultSessions:    []SessionConfig{},
			wantCount:          0,
			wantTypes:          map[SessionType]int{},
		},
	}

	// Run each test case
	// t.Run() creates a subtest - each one runs independently
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			// Create manager with test data
			manager := createTestManager(tt.tmuxSessions, tt.tmuxinatorProjects, tt.defaultSessions)

			// Call the function we're testing
			sessions, err := manager.ListAll()

			// Check for errors
			if err != nil {
				t.Fatalf("ListAll() returned error: %v", err)
			}

			// Check the count
			if len(sessions) != tt.wantCount {
				t.Errorf("ListAll() returned %d sessions, want %d", len(sessions), tt.wantCount)
			}

			// Count session types
			typeCounts := make(map[SessionType]int)
			for _, sess := range sessions {
				typeCounts[sess.Type]++
			}

			// Compare type counts
			for typ, wantCount := range tt.wantTypes {
				gotCount := typeCounts[typ]
				if gotCount != wantCount {
					t.Errorf("Got %d sessions of type %v, want %d", gotCount, typ, wantCount)
				}
			}
		})
	}
}

// TestCreateOrSwitch tests the CreateOrSwitch function
func TestCreateOrSwitch(t *testing.T) {
	tests := []struct {
		name           string
		sessionName    string
		existingSessions []Session
		tmuxinatorProjects []string
		defaultSessions []SessionConfig
		wantSwitchCall bool
		wantError      bool
	}{
		{
			name:        "switch to existing tmux session",
			sessionName: "existing",
			existingSessions: []Session{
				{Name: "existing", Type: SessionTypeTmux, IsActive: true},
			},
			wantSwitchCall: true,
			wantError:      false,
		},
		{
			name:               "start tmuxinator project",
			sessionName:        "proj1",
			existingSessions:   []Session{},
			tmuxinatorProjects: []string{"proj1"},
			wantError:          false,
		},
		{
			name:            "create default session",
			sessionName:     "default1",
			existingSessions: []Session{},
			defaultSessions: []SessionConfig{
				{Name: "default1", Directory: "~/dir1"},
			},
			wantError: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			manager := createTestManager(tt.existingSessions, tt.tmuxinatorProjects, tt.defaultSessions)

			err := manager.CreateOrSwitch(tt.sessionName)

			if tt.wantError && err == nil {
				t.Error("CreateOrSwitch() expected error but got none")
			}
			if !tt.wantError && err != nil {
				t.Errorf("CreateOrSwitch() unexpected error: %v", err)
			}
		})
	}
}

// TestGetSessionInfo tests the GetSessionInfo function
func TestGetSessionInfo(t *testing.T) {
	manager := createTestManager(
		[]Session{
			{Name: "active", Type: SessionTypeTmux, WindowCount: 3, IsActive: true},
		},
		[]string{"proj1"},
		[]SessionConfig{
			{Name: "default1", Directory: "~/dir1", Description: "Test default"},
		},
	)

	tests := []struct {
		name        string
		sessionName string
		wantInfo    string
	}{
		{
			name:        "active session",
			sessionName: "active",
			wantInfo:    "active (3 windows)",
		},
		{
			name:        "tmuxinator project",
			sessionName: "proj1",
			wantInfo:    "tmuxinator project",
		},
		{
			name:        "default session with description",
			sessionName: "default1",
			wantInfo:    "default: Test default",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			info, err := manager.GetSessionInfo(tt.sessionName)
			if err != nil {
				t.Fatalf("GetSessionInfo() returned error: %v", err)
			}

			if info != tt.wantInfo {
				t.Errorf("GetSessionInfo() = %q, want %q", info, tt.wantInfo)
			}
		})
	}
}
