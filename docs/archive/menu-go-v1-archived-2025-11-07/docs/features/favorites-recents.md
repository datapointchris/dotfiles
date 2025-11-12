# Favorites and Recents System

The menu system provides persistent favorites and recents tracking across all integrations. This feature allows users to quickly access their most frequently used commands, workflows, and other items.

## Overview

The favorites and recents system consists of three main components:

1. **State Management** (`internal/integration/state.go`) - Persistent storage and thread-safe access
2. **Manager Integration** (`internal/integration/manager.go`) - High-level API for favorites/recents operations
3. **UI Integration** (`internal/ui/menu.go`) - Visual indicators and keyboard shortcuts

## Architecture

### State Storage

State is persisted to `~/.config/menu/state.json` in the following format:

```json
{
  "favorites": {
    "commands": ["ls", "gitlog", "fcd"],
    "workflows": ["Git Commit Workflow"],
    "learning": ["Go Testing"]
  },
  "recents": {
    "commands": [
      {"item_id": "ls", "last_accessed": 1699564800},
      {"item_id": "cd", "last_accessed": 1699564700}
    ]
  }
}
```

### Thread Safety

The State struct uses `sync.RWMutex` for thread-safe concurrent access:

- **Read operations** (checking favorites, getting recents) use `RLock()` - multiple readers allowed simultaneously
- **Write operations** (adding/removing favorites, updating recents) use `Lock()` - exclusive access

This design allows high-performance concurrent reads while ensuring data consistency during writes.

## Favorites System

### How It Works

Favorites are stored as a map of integration names to item ID slices:

```go
Favorites map[string][]string
// Example: {"commands": ["ls", "grep"], "workflows": ["Git Commit"]}
```

### Operations

#### Adding a Favorite

```go
err := manager.ToggleFavorite("commands", "ls")
```

The operation is idempotent - calling it multiple times with the same item is safe and won't create duplicates.

**Flow:**

1. Check if item is already favorited
2. If not favorited: append to favorites list
3. If favorited: remove from favorites list (toggle behavior)
4. Persist state to disk immediately
5. Return any errors encountered

#### Checking Favorite Status

```go
isFavorite := manager.IsFavorite("commands", "ls")
```

This is a fast read-only operation that checks if an item ID exists in the favorites list.

#### Enriching Items with Favorite Status

```go
enrichedItems := manager.EnrichItems("commands", items)
```

This method:

1. Takes a slice of items
2. Checks each item's favorite status
3. Sets the `Favorite` field on each item
4. Returns the enriched items

The UI uses enriched items to display the ★ indicator.

### UI Integration

In detail view, press `f` to toggle favorite status:

```go
case "f":
    err := m.manager.ToggleFavorite(m.selectedItem.Source, m.selectedItem.ID)
    if err == nil {
        m.selectedItem.Favorite = !m.selectedItem.Favorite
        // Reload list to show updated indicator
    }
```

Visual indicators:

- **List view**: `★ 🔧 ls → List directory contents`
- **Detail view**: `★ Favorite` line in yellow/gold color

## Recents System

### How It Works

Recents are stored as a map of integration names to recent item slices with timestamps:

```go
Recents map[string][]RecentItem
type RecentItem struct {
    ItemID       string `json:"item_id"`
    LastAccessed int64  `json:"last_accessed"` // Unix timestamp
}
```

Items are stored in **MRU (Most Recently Used) order** - newest first, oldest last.

### LRU Cache Behavior

The recents system implements an LRU (Least Recently Used) cache with a maximum of 20 items per integration:

1. **New item accessed**: Added to front of list
2. **Existing item accessed**: Moved to front of list, timestamp updated
3. **List exceeds 20 items**: Oldest items are automatically removed

### Operations

#### Tracking Recent Access

```go
err := manager.MarkRecent("commands", "ls")
```

This is called automatically when a command is successfully executed.

**Flow:**

1. Check if item already exists in recents
2. If exists: update timestamp and move to front
3. If new: add to front with current timestamp
4. Truncate list to 20 items maximum
5. Persist state to disk immediately

**Example sequence:**

```go
// Initial: []
AddRecent("commands", "ls")    // ["ls"]
AddRecent("commands", "cd")    // ["cd", "ls"]
AddRecent("commands", "pwd")   // ["pwd", "cd", "ls"]
AddRecent("commands", "ls")    // ["ls", "pwd", "cd"] - ls moved to front
```

#### Getting Recent Items

```go
recentIDs := state.GetRecents("commands")
// Returns: ["ls", "pwd", "cd"] - MRU order
```

#### Getting Access Timestamp

```go
timestamp := state.GetRecentTimestamp("commands", "ls")
if timestamp != nil {
    lastUsed := time.Unix(*timestamp, 0)
}
```

### Automatic Tracking

Recent items are tracked automatically on successful command execution:

```go
func (m Model) executeItem() (tea.Model, tea.Cmd) {
    // ... execute command ...

    // Mark as recent if execution was successful
    if result.Success {
        _ = m.manager.MarkRecent(m.selectedItem.Source, m.selectedItem.ID)
    }

    // ... show results ...
}
```

## Go Language Features

This implementation demonstrates several important Go concepts:

### 1. Mutex-Based Synchronization

```go
type State struct {
    mu sync.RWMutex  // Read-write mutex
    // ...
}

// Multiple readers allowed simultaneously
func (s *State) IsFavorite(integration, itemID string) bool {
    s.mu.RLock()         // Shared lock
    defer s.mu.RUnlock() // Guaranteed unlock
    // ... read state ...
}

// Exclusive access for writers
func (s *State) AddFavorite(integration, itemID string) error {
    s.mu.Lock()          // Exclusive lock
    defer s.mu.Unlock()  // Guaranteed unlock
    // ... modify state ...
}
```

**Why RWMutex?**

- Read-heavy workload (checking favorites is more common than modifying)
- Multiple goroutines can read simultaneously
- Only writers block (and block all readers/writers)

### 2. Idempotent Operations

```go
func (s *State) AddFavorite(integration, itemID string) error {
    // Check if already favorited
    for _, id := range s.Favorites[integration] {
        if id == itemID {
            return nil // No-op, already favorited
        }
    }
    // Add to favorites
}
```

**Benefits:**

- Safe to call multiple times
- No duplicate entries
- Simplifies UI code (don't need to check before calling)

### 3. Defensive Copying

```go
func (s *State) GetFavorites(integration string) []string {
    favorites := s.Favorites[integration]

    // Return a copy, not the original slice
    result := make([]string, len(favorites))
    copy(result, favorites)
    return result
}
```

**Why copy?**

- Prevents caller from modifying internal state
- Avoids race conditions if caller modifies while we're writing
- Maintains encapsulation

### 4. Pointer Returns for Optional Values

```go
func (s *State) GetRecentTimestamp(integration, itemID string) *int64 {
    for _, recent := range s.Recents[integration] {
        if recent.ItemID == itemID {
            timestamp := recent.LastAccessed
            return &timestamp  // Pointer indicates "found"
        }
    }
    return nil  // nil indicates "not found"
}
```

**Pattern:**

- `nil` = value doesn't exist
- `*int64` = value exists with this value
- Avoids need for `(value, found bool)` return style

### 5. Slice Manipulation Techniques

**Removing an element (without reallocation):**

```go
// Remove element at index i: [a,b,c,d] -> [a,b,d]
slice = append(slice[:i], slice[i+1:]...)
```

**Prepending an element:**

```go
// Add to front: [a,b,c] -> [x,a,b,c]
slice = append([]T{newItem}, slice...)
```

**Moving element to front:**

```go
// Move element at i to front
item := slice[i]
slice = append([]T{item}, append(slice[:i], slice[i+1:]...)...)
```

## Performance Considerations

### Time Complexity

| Operation | Complexity | Notes |
|-----------|-----------|-------|
| IsFavorite | O(n) | Linear search through favorites |
| AddFavorite | O(n) | Check for duplicates + append |
| RemoveFavorite | O(n) | Find + slice manipulation |
| AddRecent | O(n) | Find + move to front |
| GetRecents | O(n) | Copy slice |

Where n = number of favorites/recents per integration (typically small, < 100).

### Optimization Notes

1. **Small Data Sets**: Current implementation is optimized for small data sets (< 100 items per integration)
2. **Map for Fast Lookup**: Could optimize with `map[string]bool` for O(1) favorite checks if needed
3. **File I/O on Every Change**: Acceptable for user-driven operations (not high frequency)
4. **JSON Format**: Human-readable, easy to debug, sufficient performance for this use case

### Memory Usage

- State struct: ~few KB in memory
- JSON file: ~few KB on disk
- Per-integration overhead: minimal (just map keys)

## Error Handling

The system handles errors gracefully:

```go
// State initialization fails - continue without state
state, err := NewState(configDir)
if err != nil {
    state = nil  // Manager continues to work, just without persistence
}

// Toggle favorite fails - show error to user
err := manager.ToggleFavorite(integration, itemID)
if err != nil {
    m.err = fmt.Errorf("failed to toggle favorite: %v", err)
}
```

**Key principle**: Persistence failure should not crash the application.

## Testing

### Unit Tests

The state system has comprehensive unit tests covering:

- Favorite add/remove/check operations
- Recent item tracking with MRU behavior
- LRU eviction (20 item limit)
- Concurrent access (though not explicit race condition tests)
- Persistence (save/load cycle)

### Testing with Temporary Directories

```go
func TestFavorites(t *testing.T) {
    tmpDir := t.TempDir()  // Automatic cleanup
    state, err := NewState(tmpDir)
    // ... test operations ...
}
```

## Future Enhancements

Potential improvements to consider:

1. **Filter by favorites** - Add favorites filter to list views
2. **Favorite categories** - Group favorites by category
3. **Recents limit configuration** - Allow users to configure max recent items
4. **Export/import** - Backup/restore favorites and recents
5. **Sync across machines** - Store in cloud (Dropbox, etc.)
6. **Recent item ranking** - Weight by frequency + recency
7. **Search favorites** - Quick search through favorited items

## Related Files

- `internal/integration/state.go` - State management and persistence
- `internal/integration/manager.go` - Manager integration methods
- `internal/ui/menu.go` - UI integration and keyboard shortcuts
- `internal/integration/state_test.go` - Comprehensive unit tests (TODO)

## See Also

- [Clipboard Support](clipboard-support.md) - Copy commands to clipboard
- [Syntax Highlighting](syntax-highlighting.md) - Code highlighting in details
- [Integration System](../development/integration-system.md) - How integrations work
