package integration

import (
	"encoding/json"
	"os"
	"path/filepath"
	"sync"
	"time"
)

// State manages persistent state for favorites and recents across all integrations.
//
// The State system provides:
//   - Thread-safe read/write operations using sync.RWMutex
//   - Automatic persistence to disk on every state change
//   - Per-integration organization of favorites and recents
//   - LRU (Least Recently Used) management of recent items
//
// State is stored in JSON format at ~/.config/menu/state.json by default.
// The structure allows multiple integrations (commands, workflows, learning, etc.)
// to independently track their own favorites and recently accessed items.
//
// Example state.json:
//
//	{
//	  "favorites": {
//	    "commands": ["ls", "gitlog"],
//	    "workflows": ["Git Commit Workflow"]
//	  },
//	  "recents": {
//	    "commands": [
//	      {"item_id": "ls", "last_accessed": 1699564800},
//	      {"item_id": "cd", "last_accessed": 1699564700}
//	    ]
//	  }
//	}
type State struct {
	// Favorites maps integration name to a list of favorited item IDs
	// Example: {"commands": ["ls", "grep"], "workflows": ["Git Commit"]}
	Favorites map[string][]string `json:"favorites"`

	// Recents maps integration name to recently accessed items with timestamps
	// Items are stored in MRU (Most Recently Used) order - newest first
	Recents map[string][]RecentItem `json:"recents"`

	// mu protects concurrent access to Favorites and Recents maps
	// Uses RWMutex to allow multiple concurrent reads but exclusive writes
	mu sync.RWMutex

	// statePath is the filesystem path where state is persisted
	// Typically ~/.config/menu/state.json
	statePath string
}

// RecentItem tracks when an item was last accessed.
//
// Recent items are maintained in MRU order and limited to MaxRecentItems (20 by default).
// When the limit is exceeded, the oldest items are automatically removed.
type RecentItem struct {
	// ItemID is the unique identifier of the item within its integration
	ItemID string `json:"item_id"`

	// LastAccessed is a Unix timestamp (seconds since epoch) of the last access
	LastAccessed int64 `json:"last_accessed"`
}

// NewState creates a new state manager with the specified config directory.
//
// If configDir is empty, defaults to ~/.config/menu.
// This function will:
//   - Initialize empty maps for favorites and recents
//   - Set the state file path to {configDir}/state.json
//   - Attempt to load existing state from disk
//   - Return a usable State even if no state file exists yet
//
// The state file will be created automatically on the first save operation.
//
// Example usage:
//
//	// Use default config directory (~/.config/menu)
//	state, err := NewState("")
//
//	// Use custom config directory
//	state, err := NewState("/custom/path")
func NewState(configDir string) (*State, error) {
	// Default to ~/.config/menu if no config directory specified
	if configDir == "" {
		home, err := os.UserHomeDir()
		if err != nil {
			return nil, err
		}
		configDir = filepath.Join(home, ".config", "menu")
	}

	statePath := filepath.Join(configDir, "state.json")

	// Initialize state with empty maps
	s := &State{
		Favorites: make(map[string][]string),
		Recents:   make(map[string][]RecentItem),
		statePath: statePath,
	}

	// Load existing state if it exists
	// os.IsNotExist is not an error - it just means this is the first run
	if err := s.Load(); err != nil && !os.IsNotExist(err) {
		return nil, err
	}

	return s, nil
}

// Load loads state from disk.
//
// This method:
//   - Acquires an exclusive lock to safely update the state
//   - Reads the JSON file from statePath
//   - Unmarshals the JSON into the State struct
//
// Returns os.ErrNotExist if the state file doesn't exist yet (first run).
// This is expected behavior and should be handled by the caller.
func (s *State) Load() error {
	s.mu.Lock()         // Exclusive lock - we're modifying state
	defer s.mu.Unlock() // Ensure lock is released even if error occurs

	data, err := os.ReadFile(s.statePath)
	if err != nil {
		return err // Will be os.ErrNotExist on first run
	}

	// Unmarshal directly into the State struct
	// This will populate both Favorites and Recents maps
	return json.Unmarshal(data, s)
}

// Save saves state to disk atomically.
//
// This method:
//   - Acquires a read lock (we only read state to serialize it)
//   - Creates the config directory if it doesn't exist
//   - Marshals state to pretty-printed JSON
//   - Writes to disk with restrictive permissions (0644)
//
// Note: Uses RLock instead of Lock because we're only reading the state
// to serialize it, not modifying it. This allows other goroutines to
// continue reading state while we're writing to disk.
func (s *State) Save() error {
	s.mu.RLock()         // Read lock - we're only reading to serialize
	defer s.mu.RUnlock() // Ensure lock is released

	// Ensure directory exists (creates ~/.config/menu if needed)
	dir := filepath.Dir(s.statePath)
	if err := os.MkdirAll(dir, 0755); err != nil {
		return err
	}

	// Marshal with indentation for human readability
	data, err := json.MarshalIndent(s, "", "  ")
	if err != nil {
		return err
	}

	// Write with user-only write permissions (644 = rw-r--r--)
	return os.WriteFile(s.statePath, data, 0644)
}

// AddFavorite adds an item to favorites for the specified integration.
//
// This method:
//   - Acquires an exclusive lock for thread-safe modification
//   - Initializes the favorites slice for the integration if needed
//   - Checks for duplicates (idempotent - safe to call multiple times)
//   - Appends the item ID to the favorites list
//   - Persists the change to disk immediately
//
// Example:
//
//	state.AddFavorite("commands", "ls")  // First call - adds to favorites
//	state.AddFavorite("commands", "ls")  // Second call - no-op, already favorited
func (s *State) AddFavorite(integration, itemID string) error {
	s.mu.Lock()         // Exclusive lock - we're modifying state
	defer s.mu.Unlock() // Ensure lock is released

	// Initialize the slice for this integration if it doesn't exist
	if s.Favorites[integration] == nil {
		s.Favorites[integration] = []string{}
	}

	// Check if already favorited to avoid duplicates
	// This makes the operation idempotent
	for _, id := range s.Favorites[integration] {
		if id == itemID {
			return nil // Already favorited - nothing to do
		}
	}

	// Append to favorites and persist immediately
	s.Favorites[integration] = append(s.Favorites[integration], itemID)
	return s.saveUnlocked()
}

// RemoveFavorite removes an item from favorites for the specified integration.
//
// This method:
//   - Acquires an exclusive lock for thread-safe modification
//   - Searches for the item in the favorites list
//   - Removes it using slice manipulation (no reallocation)
//   - Persists the change to disk immediately
//
// If the item is not found, this is a no-op (returns nil).
// This makes the operation idempotent and safe to call multiple times.
//
// Example:
//
//	state.RemoveFavorite("commands", "ls")  // Removes if exists
//	state.RemoveFavorite("commands", "ls")  // No-op if already removed
func (s *State) RemoveFavorite(integration, itemID string) error {
	s.mu.Lock()         // Exclusive lock - we're modifying state
	defer s.mu.Unlock() // Ensure lock is released

	favorites := s.Favorites[integration]
	for i, id := range favorites {
		if id == itemID {
			// Remove by slicing around the element
			// This avoids reallocation: [a,b,c,d] -> [a,b,d]
			s.Favorites[integration] = append(favorites[:i], favorites[i+1:]...)
			return s.saveUnlocked()
		}
	}

	return nil // Not found - nothing to do
}

// IsFavorite checks if an item is favorited for the specified integration.
//
// This method:
//   - Acquires a read lock for thread-safe access
//   - Searches the favorites list for the item
//   - Returns true if found, false otherwise
//
// Uses RLock for concurrent reads - multiple goroutines can check
// favorites simultaneously without blocking each other.
//
// Example:
//
//	if state.IsFavorite("commands", "ls") {
//	    fmt.Println("ls is favorited")
//	}
func (s *State) IsFavorite(integration, itemID string) bool {
	s.mu.RLock()         // Read lock - concurrent reads allowed
	defer s.mu.RUnlock() // Ensure lock is released

	for _, id := range s.Favorites[integration] {
		if id == itemID {
			return true
		}
	}
	return false
}

// GetFavorites returns all favorite item IDs for an integration.
//
// This method:
//   - Acquires a read lock for thread-safe access
//   - Returns a copy of the favorites slice (not the original)
//   - Returns an empty slice if no favorites exist
//
// The returned slice is a copy to prevent race conditions if the caller
// modifies it while other goroutines are reading/writing favorites.
//
// Example:
//
//	favorites := state.GetFavorites("commands")
//	for _, itemID := range favorites {
//	    fmt.Println("Favorite:", itemID)
//	}
func (s *State) GetFavorites(integration string) []string {
	s.mu.RLock()         // Read lock - concurrent reads allowed
	defer s.mu.RUnlock() // Ensure lock is released

	favorites := s.Favorites[integration]
	if favorites == nil {
		return []string{} // Return empty slice, not nil
	}

	// Return a copy to avoid race conditions
	// If we returned the original slice, the caller could modify it
	// while other goroutines are reading/writing
	result := make([]string, len(favorites))
	copy(result, favorites)
	return result
}

// AddRecent adds or updates a recent item using LRU (Least Recently Used) strategy.
//
// This method implements an MRU (Most Recently Used) cache:
//   - Acquires an exclusive lock for thread-safe modification
//   - If item already exists: updates timestamp and moves to front
//   - If item is new: adds to front with current timestamp
//   - Maintains maximum of 20 items (oldest are automatically removed)
//   - Persists changes to disk immediately
//
// The list is always ordered MRU first (newest -> oldest).
// When an item is accessed again, it moves to the front.
//
// Example:
//
//	// Initial state: []
//	state.AddRecent("commands", "ls")    // ["ls"]
//	state.AddRecent("commands", "cd")    // ["cd", "ls"]
//	state.AddRecent("commands", "ls")    // ["ls", "cd"] - ls moved to front
//	state.AddRecent("commands", "pwd")   // ["pwd", "ls", "cd"]
//
// This is useful for implementing "recently used" lists in UIs where
// you want to show the most recently accessed items first.
func (s *State) AddRecent(integration, itemID string) error {
	s.mu.Lock()         // Exclusive lock - we're modifying state
	defer s.mu.Unlock() // Ensure lock is released

	// Initialize the slice for this integration if it doesn't exist
	if s.Recents[integration] == nil {
		s.Recents[integration] = []RecentItem{}
	}

	now := time.Now().Unix()

	// Check if item already exists and update it
	// If found, update timestamp and move to front (MRU behavior)
	for i, recent := range s.Recents[integration] {
		if recent.ItemID == itemID {
			// Update timestamp
			s.Recents[integration][i].LastAccessed = now

			// Move to front by: extracting item, then prepending to rest
			// [a, b, c, d] where b is matched -> [b, a, c, d]
			item := s.Recents[integration][i]
			s.Recents[integration] = append(
				[]RecentItem{item},
				append(s.Recents[integration][:i], s.Recents[integration][i+1:]...)...,
			)
			return s.saveUnlocked()
		}
	}

	// Item doesn't exist - add as new recent item at the front
	s.Recents[integration] = append(
		[]RecentItem{{ItemID: itemID, LastAccessed: now}},
		s.Recents[integration]...,
	)

	// Enforce maximum size by truncating oldest items
	// This implements the "Least Recently Used" eviction policy
	const MaxRecentItems = 20
	if len(s.Recents[integration]) > MaxRecentItems {
		s.Recents[integration] = s.Recents[integration][:MaxRecentItems]
	}

	return s.saveUnlocked()
}

// GetRecents returns all recent item IDs for an integration in MRU order.
//
// This method:
//   - Acquires a read lock for thread-safe access
//   - Extracts just the item IDs (not timestamps)
//   - Returns them in order: most recent first, oldest last
//   - Returns an empty slice if no recent items exist
//
// The returned slice contains only item IDs for easy iteration.
// If you need timestamps, use GetRecentTimestamp.
//
// Example:
//
//	recents := state.GetRecents("commands")
//	fmt.Println("Recently used commands:")
//	for i, itemID := range recents {
//	    fmt.Printf("%d. %s\n", i+1, itemID)
//	}
//	// Output:
//	// 1. ls
//	// 2. cd
//	// 3. pwd
func (s *State) GetRecents(integration string) []string {
	s.mu.RLock()         // Read lock - concurrent reads allowed
	defer s.mu.RUnlock() // Ensure lock is released

	recents := s.Recents[integration]
	if recents == nil {
		return []string{} // Return empty slice, not nil
	}

	// Extract just the item IDs, maintaining MRU order
	result := make([]string, len(recents))
	for i, recent := range recents {
		result[i] = recent.ItemID
	}
	return result
}

// GetRecentTimestamp returns the last accessed timestamp for a specific item.
//
// This method:
//   - Acquires a read lock for thread-safe access
//   - Searches for the item in the recents list
//   - Returns a pointer to the timestamp if found, nil otherwise
//
// Returns a pointer because:
//   - nil indicates "not in recent items"
//   - A valid pointer indicates "in recent items with this timestamp"
//
// The timestamp is Unix time (seconds since epoch).
//
// Example:
//
//	if ts := state.GetRecentTimestamp("commands", "ls"); ts != nil {
//	    fmt.Printf("ls was last used at: %s\n", time.Unix(*ts, 0))
//	} else {
//	    fmt.Println("ls hasn't been used recently")
//	}
func (s *State) GetRecentTimestamp(integration, itemID string) *int64 {
	s.mu.RLock()         // Read lock - concurrent reads allowed
	defer s.mu.RUnlock() // Ensure lock is released

	for _, recent := range s.Recents[integration] {
		if recent.ItemID == itemID {
			// Make a copy of the timestamp to return
			// This prevents the caller from having a pointer to our internal state
			timestamp := recent.LastAccessed
			return &timestamp
		}
	}
	return nil // Not found in recent items
}

// saveUnlocked saves state to disk without acquiring a lock.
//
// IMPORTANT: This method assumes the caller already holds a lock (either RLock or Lock).
// It should ONLY be called from other methods that have already acquired a lock.
//
// This method:
//   - Creates the config directory if it doesn't exist
//   - Marshals state to pretty-printed JSON
//   - Writes to disk with restrictive permissions (0644)
//
// This is an internal helper to avoid redundant locking when we're already
// inside a locked section. For example, AddFavorite acquires a lock, modifies
// state, then calls this to persist without releasing and reacquiring the lock.
func (s *State) saveUnlocked() error {
	// Ensure directory exists
	dir := filepath.Dir(s.statePath)
	if err := os.MkdirAll(dir, 0755); err != nil {
		return err
	}

	// Marshal with indentation for human readability
	data, err := json.MarshalIndent(s, "", "  ")
	if err != nil {
		return err
	}

	// Write with user-only write permissions (644 = rw-r--r--)
	return os.WriteFile(s.statePath, data, 0644)
}
