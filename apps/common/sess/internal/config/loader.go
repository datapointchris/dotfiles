package config

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/datapointchris/sess/internal/session"
	"gopkg.in/yaml.v3"
)

// Loader handles loading session configurations from YAML files
type Loader struct {
	// configDir is the base directory for configuration files
	// Defaults to ~/.config/sess
	configDir string
}

// NewLoader creates a new configuration loader
func NewLoader() *Loader {
	// Get the user's home directory
	// os.UserHomeDir() returns the current user's home directory
	home, err := os.UserHomeDir()
	if err != nil {
		// If we can't get home directory, use current directory
		// This shouldn't normally happen
		home = "."
	}

	// Default config directory is ~/.config/sess
	// We use filepath.Join() to build paths correctly on any OS
	// (it handles / vs \ on Windows)
	configDir := filepath.Join(home, ".config", "sess")

	// Check if XDG_CONFIG_HOME is set (Linux standard)
	if xdgConfig := os.Getenv("XDG_CONFIG_HOME"); xdgConfig != "" {
		configDir = filepath.Join(xdgConfig, "sess")
	}

	return &Loader{
		configDir: configDir,
	}
}

// LoadDefaultSessions loads default sessions for the given platform
func (l *Loader) LoadDefaultSessions(platform string) ([]session.SessionConfig, error) {
	// Build the path to the sessions config file
	// e.g., ~/.config/sess/sessions-macos.yml
	filename := fmt.Sprintf("sessions-%s.yml", platform)
	configPath := filepath.Join(l.configDir, filename)

	// Read the file
	// os.ReadFile() is the modern way to read an entire file into memory
	data, err := os.ReadFile(configPath)
	if err != nil {
		// If the file doesn't exist or can't be read, return an error
		return nil, fmt.Errorf("failed to read config file %s: %w", configPath, err)
	}

	// Parse the YAML
	// In Go, we unmarshal (decode) YAML into a struct
	// The YAML file uses "defaults:" as the top-level key
	var config struct {
		Defaults []session.SessionConfig `yaml:"defaults"`
	}

	// yaml.Unmarshal() parses the YAML into our struct
	if err := yaml.Unmarshal(data, &config); err != nil {
		return nil, fmt.Errorf("failed to parse YAML: %w", err)
	}

	// Expand ~ in directory paths to the actual home directory
	home, _ := os.UserHomeDir()
	for i := range config.Defaults {
		// If directory starts with ~, replace it with home directory
		if strings.HasPrefix(config.Defaults[i].Directory, "~") {
			config.Defaults[i].Directory = strings.Replace(
				config.Defaults[i].Directory,
				"~",
				home,
				1, // Only replace the first occurrence
			)
		}
	}

	return config.Defaults, nil
}

// GetSessionConfig retrieves a specific session configuration by name
func (l *Loader) GetSessionConfig(name string, platform string) (*session.SessionConfig, error) {
	// Load all sessions
	sessions, err := l.LoadDefaultSessions(platform)
	if err != nil {
		return nil, err
	}

	// Find the one with matching name
	for _, sess := range sessions {
		if sess.Name == name {
			// Return a pointer to the session
			// We need to create a copy because sess is a loop variable
			// and its memory address changes each iteration
			result := sess
			return &result, nil
		}
	}

	// If we didn't find it, return an error
	return nil, fmt.Errorf("session %q not found in config", name)
}

// Verify interface implementation at compile time
var _ session.ConfigLoader = (*Loader)(nil)
