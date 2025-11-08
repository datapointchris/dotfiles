package integration

import (
	"context"
)

// IntegrationType defines the type of integration
type IntegrationType string

const (
	// TypeStatic - YAML-based registries (commands, workflows, learning)
	TypeStatic IntegrationType = "static"

	// TypeDynamic - External command integrations (tasks, tools)
	TypeDynamic IntegrationType = "dynamic"

	// TypeInteractive - TUI integrations that launch external programs (sessions, notes)
	TypeInteractive IntegrationType = "interactive"

	// TypeExternal - External tools that need command execution (buku bookmarks)
	TypeExternal IntegrationType = "external"
)

// Item represents a displayable menu item from any integration
// This is the common interface all integrations must provide
type Item struct {
	// Core identification
	ID          string // Unique identifier within the integration
	Title       string // Display title for list views
	Description string // Short description for list views
	Category    string // Category/group for filtering

	// Display metadata
	Icon      string   // Icon or prefix (●, ⚙, etc.)
	Tags      []string // Tags for searching/filtering
	Keywords  []string // Additional search keywords
	Status    string   // Status indicator (active, completed, etc.)
	Priority  int      // For sorting (higher = more important)
	Favorite  bool     // User has marked as favorite
	Recent    bool     // Recently accessed

	// Detail view content
	Details map[string]interface{} // Integration-specific detail data

	// Action configuration
	Executable bool   // Can this item be executed?
	Command    string // Command to execute (if executable)
	IsInteractive bool // Does command need interactive terminal?

	// Metadata
	Source      string                 // Which integration provided this
	RawData     interface{}            // Original data structure
	Metadata    map[string]interface{} // Additional metadata
	LastAccessed *int64                // Unix timestamp of last access
}

// Integration defines the interface all integrations must implement
type Integration interface {
	// Name returns the integration name (e.g., "sessions", "tasks", "commands")
	Name() string

	// Type returns the integration type
	Type() IntegrationType

	// Load fetches and returns all items from this integration
	// Context allows for cancellation and timeouts
	Load(ctx context.Context) ([]Item, error)

	// Get retrieves a specific item by ID
	Get(ctx context.Context, id string) (*Item, error)

	// Search filters items by query string
	// Returns items matching the query in title, description, tags, or keywords
	Search(ctx context.Context, query string) ([]Item, error)

	// Execute runs the action associated with an item
	// Returns output and error
	Execute(ctx context.Context, item Item) (string, error)

	// SupportsExecution indicates if this integration can execute items
	SupportsExecution() bool

	// Refresh reloads data from source (useful for dynamic integrations)
	Refresh(ctx context.Context) error
}

// DetailRenderer defines how to render detailed views for items
type DetailRenderer interface {
	// RenderDetail creates a formatted string for the detail view
	// Supports custom rendering per integration type
	RenderDetail(item Item) string

	// RenderCompact creates a compact one-line summary
	RenderCompact(item Item) string
}

// ExecutionResult holds the result of executing an item
type ExecutionResult struct {
	Success bool
	Output  string
	Error   error
	ExitCode int
	Duration int64 // milliseconds
}

// Filter defines common filtering options
type Filter struct {
	Query      string   // Text search query
	Categories []string // Filter by categories
	Tags       []string // Filter by tags
	Status     string   // Filter by status
	Favorites  bool     // Show only favorites
	Recent     bool     // Show only recent items
}

// SortOption defines how to sort items
type SortOption string

const (
	SortByTitle    SortOption = "title"
	SortByRecent   SortOption = "recent"
	SortByPriority SortOption = "priority"
	SortByCategory SortOption = "category"
)

// Manager handles all integrations and provides a unified interface
type Manager struct {
	integrations map[string]Integration
	config       *Config
	state        *State
}

// Config holds integration configuration
type Config struct {
	// Base paths
	ConfigDir string
	DataDir   string

	// Feature flags
	EnableCache      bool
	EnableFavorites  bool
	EnableRecents    bool
	MaxRecentItems   int

	// Integration-specific configs
	IntegrationConfigs map[string]interface{}
}
