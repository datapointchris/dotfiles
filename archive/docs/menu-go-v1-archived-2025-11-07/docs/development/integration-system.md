# Integration System

The menu system is built around a flexible integration architecture that allows easily adding new data sources and command providers.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    Manager                              │
│  - Registers integrations                              │
│  - Coordinates loading                                 │
│  - Manages favorites/recents                           │
└─────────────────────────────────────────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          │               │               │
          ▼               ▼               ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ Integration  │  │ Integration  │  │ Integration  │
│   Commands   │  │  Workflows   │  │   Learning   │
│              │  │              │  │              │
│ Type: Static │  │ Type: Static │  │ Type: Static │
└──────────────┘  └──────────────┘  └──────────────┘
        │                 │                 │
        ▼                 ▼                 ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ Registry     │  │ Registry     │  │ Registry     │
│ Loader       │  │ Loader       │  │ Loader       │
│              │  │              │  │              │
│ YAML Files   │  │ YAML Files   │  │ YAML Files   │
└──────────────┘  └──────────────┘  └──────────────┘
```

## Core Interfaces

### Integration Interface

All integrations must implement the `Integration` interface:

```go
type Integration interface {
    // Name returns the integration name (e.g., "sessions", "commands")
    Name() string

    // Type returns the integration type (Static, Dynamic, Interactive, External)
    Type() IntegrationType

    // Load fetches and returns all items from this integration
    Load(ctx context.Context) ([]Item, error)

    // Get retrieves a specific item by ID
    Get(ctx context.Context, id string) (*Item, error)

    // Search filters items by query string
    Search(ctx context.Context, query string) ([]Item, error)

    // Execute runs the action associated with an item
    // Returns the command to execute
    Execute(ctx context.Context, item Item) (string, error)

    // SupportsExecution indicates if this integration can execute items
    SupportsExecution() bool

    // Refresh reloads data from source
    Refresh(ctx context.Context) error
}
```

### Item Struct

The unified data model for all integration items:

```go
type Item struct {
    // Core identification
    ID          string  // Unique within integration
    Title       string  // Display name
    Description string  // Short description
    Category    string  // Category/group

    // Display metadata
    Icon      string   // Icon or prefix (●, ⚙, etc.)
    Tags      []string // Tags for filtering
    Keywords  []string // Search keywords
    Status    string   // Status indicator
    Priority  int      // Sorting priority
    Favorite  bool     // User favorited
    Recent    bool     // Recently accessed

    // Detail view content
    Details map[string]interface{} // Integration-specific data

    // Action configuration
    Executable    bool   // Can be executed?
    Command       string // Command to execute
    IsInteractive bool   // Needs terminal?

    // Metadata
    Source       string                 // Integration name
    RawData      interface{}            // Original data
    Metadata     map[string]interface{} // Additional metadata
    LastAccessed *int64                 // Unix timestamp
}
```

## Integration Types

### 1. Static Integrations (YAML-based)

Static integrations load from YAML configuration files.

**Examples:** commands, workflows, learning

**Characteristics:**

- Data loaded at startup
- Fast access (cached in memory)
- User-editable configuration files
- No external dependencies

**Implementation pattern:**

```go
type CommandsIntegration struct {
    loader *registry.Loader
}

func NewCommandsIntegration(loader *registry.Loader) *CommandsIntegration {
    return &CommandsIntegration{loader: loader}
}

func (c *CommandsIntegration) Name() string {
    return "commands"
}

func (c *CommandsIntegration) Type() IntegrationType {
    return TypeStatic
}

func (c *CommandsIntegration) Load(ctx context.Context) ([]Item, error) {
    // Load commands from YAML
    commands, err := c.loader.LoadCommands()
    if err != nil {
        return nil, err
    }

    // Convert to Item structs
    items := make([]Item, len(commands))
    for i, cmd := range commands {
        items[i] = Item{
            ID:          cmd.Name,
            Title:       cmd.Name,
            Description: cmd.Description,
            Category:    cmd.Category,
            Icon:        getCommandIcon(cmd.Type),
            Executable:  true,
            Command:     cmd.Command,
            Source:      "commands",
            Details: map[string]interface{}{
                "examples": cmd.Examples,
                "notes":    cmd.Notes,
            },
        }
    }

    return items, nil
}
```

### 2. Dynamic Integrations (Command-based)

Dynamic integrations execute external commands to fetch data.

**Examples:** tasks (Taskfile), tools (command output)

**Characteristics:**

- Data fetched on demand
- Always current (reflects real-time state)
- Requires external binary
- Slower (must execute command)

**Implementation pattern:**

```go
type TasksIntegration struct {
    executable string
}

func (t *TasksIntegration) Load(ctx context.Context) ([]Item, error) {
    // Execute external command
    cmd := exec.CommandContext(ctx, "task", "--list", "--json")
    output, err := cmd.Output()
    if err != nil {
        return nil, err
    }

    // Parse JSON output
    var tasks []TaskDefinition
    if err := json.Unmarshal(output, &tasks); err != nil {
        return nil, err
    }

    // Convert to Items
    items := make([]Item, len(tasks))
    for i, task := range tasks {
        items[i] = Item{
            ID:          task.Name,
            Title:       task.Name,
            Description: task.Summary,
            Executable:  true,
            Command:     fmt.Sprintf("task %s", task.Name),
            Source:      "tasks",
        }
    }

    return items, nil
}
```

### 3. Interactive Integrations (TUI-based)

Interactive integrations launch external TUI applications.

**Examples:** sessions (sesh), notes (nb)

**Characteristics:**

- Require full terminal control
- Run in subprocess
- Menu suspends while running
- Return to menu on exit

**Implementation pattern:**

```go
type SessionsIntegration struct {
    executable string
}

func (s *SessionsIntegration) Execute(ctx context.Context, item Item) (string, error) {
    // For interactive commands, return the raw command
    // The executor will handle terminal setup
    return "sesh connect " + item.ID, nil
}

func (s *SessionsIntegration) SupportsExecution() bool {
    return true
}
```

### 4. External Integrations (Tool-based)

External integrations query external tools/databases.

**Examples:** bookmarks (buku), tools (registry)

**Characteristics:**

- Data stored externally
- Rich query capabilities
- May have complex data models
- Requires tool installation

**Implementation pattern:**

```go
type BookmarksIntegration struct {
    executable string
}

func (b *BookmarksIntegration) Load(ctx context.Context) ([]Item, error) {
    // Query buku database
    cmd := exec.CommandContext(ctx, "buku", "--print", "--json")
    output, err := cmd.Output()
    if err != nil {
        return nil, err
    }

    // Parse bookmarks
    var bookmarks []Bookmark
    if err := json.Unmarshal(output, &bookmarks); err != nil {
        return nil, err
    }

    // Convert to Items
    items := make([]Item, len(bookmarks))
    for i, bm := range bookmarks {
        items[i] = Item{
            ID:          strconv.Itoa(bm.Index),
            Title:       bm.Title,
            Description: bm.Description,
            Executable:  true,
            Command:     bm.URL,
            Source:      "bookmarks",
            Details: map[string]interface{}{
                "url":  bm.URL,
                "tags": bm.Tags,
            },
        }
    }

    return items, nil
}
```

## Manager System

### Registration

Integrations are registered at startup:

```go
func main() {
    // Create manager
    config := &integration.Config{
        ConfigDir:       "~/.config/menu",
        EnableFavorites: true,
        EnableRecents:   true,
    }
    manager := integration.NewManager(config)

    // Register integrations
    loader := registry.NewLoader()

    // Static integrations
    manager.Register(registries.NewCommandsIntegration(loader))
    manager.Register(registries.NewWorkflowsIntegration(loader))
    manager.Register(registries.NewLearningIntegration(loader))

    // Dynamic integrations
    manager.Register(registries.NewTasksIntegration())
    manager.Register(registries.NewToolsIntegration())

    // Interactive integrations
    manager.Register(registries.NewSessionsIntegration())
    manager.Register(registries.NewNotesIntegration())

    // External integrations
    manager.Register(registries.NewBookmarksIntegration())

    // Use manager
    ui := ui.NewModelWithIntegrations(manager)
    // ...
}
```

### Concurrent Loading

The manager loads all integrations concurrently for performance:

```go
func (m *Manager) LoadAll(ctx context.Context) (map[string][]Item, error) {
    results := make(map[string][]Item)
    var mu sync.Mutex
    var wg sync.WaitGroup
    errChan := make(chan error, len(m.integrations))

    // Launch goroutine for each integration
    for name, integration := range m.integrations {
        wg.Add(1)
        go func(n string, i Integration) {
            defer wg.Done()

            // Load items
            items, err := i.Load(ctx)
            if err != nil {
                errChan <- fmt.Errorf("%s: %w", n, err)
                return
            }

            // Thread-safe result storage
            mu.Lock()
            results[n] = items
            mu.Unlock()
        }(name, integration)
    }

    // Wait for all to complete
    wg.Wait()
    close(errChan)

    // Check for errors
    var errs []error
    for err := range errChan {
        errs = append(errs, err)
    }

    if len(errs) > 0 {
        return results, fmt.Errorf("errors loading integrations: %v", errs)
    }

    return results, nil
}
```

**Key Go patterns:**

- `sync.WaitGroup` for goroutine coordination
- `sync.Mutex` for thread-safe map writes
- Buffered channel for error collection
- Context for cancellation support

### State Enrichment

The manager enriches items with favorites and recents:

```go
func (m *Manager) EnrichItems(integrationName string, items []Item) []Item {
    if m.state == nil {
        return items
    }

    enriched := make([]Item, len(items))
    for i, item := range items {
        enriched[i] = item

        // Add favorite status
        enriched[i].Favorite = m.state.IsFavorite(integrationName, item.ID)

        // Add recent status and timestamp
        if timestamp := m.state.GetRecentTimestamp(integrationName, item.ID); timestamp != nil {
            enriched[i].Recent = true
            enriched[i].LastAccessed = timestamp
        }
    }

    return enriched
}
```

## Creating a New Integration

### Step 1: Implement the Interface

Create a new file in `internal/integration/registries/`:

```go
package registries

import (
    "context"
    "github.com/ichrisbirch/menu/internal/integration"
)

type MyIntegration struct {
    // Add any required fields
}

func NewMyIntegration() *MyIntegration {
    return &MyIntegration{}
}

func (m *MyIntegration) Name() string {
    return "myintegration"
}

func (m *MyIntegration) Type() integration.IntegrationType {
    return integration.TypeStatic
}

func (m *MyIntegration) Load(ctx context.Context) ([]integration.Item, error) {
    // Implement loading logic
    items := []integration.Item{
        {
            ID:          "item1",
            Title:       "My Item",
            Description: "Description",
            Source:      "myintegration",
        },
    }
    return items, nil
}

func (m *MyIntegration) Get(ctx context.Context, id string) (*integration.Item, error) {
    // Load all and find by ID
    items, err := m.Load(ctx)
    if err != nil {
        return nil, err
    }
    for _, item := range items {
        if item.ID == id {
            return &item, nil
        }
    }
    return nil, fmt.Errorf("item not found: %s", id)
}

func (m *MyIntegration) Search(ctx context.Context, query string) ([]integration.Item, error) {
    // Load all and filter
    items, err := m.Load(ctx)
    if err != nil {
        return nil, err
    }

    query = strings.ToLower(query)
    var results []integration.Item
    for _, item := range items {
        if strings.Contains(strings.ToLower(item.Title), query) ||
           strings.Contains(strings.ToLower(item.Description), query) {
            results = append(results, item)
        }
    }
    return results, nil
}

func (m *MyIntegration) Execute(ctx context.Context, item integration.Item) (string, error) {
    if !m.SupportsExecution() {
        return "", fmt.Errorf("myintegration does not support execution")
    }
    return item.Command, nil
}

func (m *MyIntegration) SupportsExecution() bool {
    return true // or false if not executable
}

func (m *MyIntegration) Refresh(ctx context.Context) error {
    // Implement refresh logic if needed
    return nil
}
```

### Step 2: Register the Integration

In `cmd/menu/main.go`:

```go
func main() {
    manager := integration.NewManager(config)

    // ... existing registrations ...

    // Add new integration
    manager.Register(registries.NewMyIntegration())

    // ... rest of initialization ...
}
```

### Step 3: Add UI Support

In `internal/ui/menu.go`, add menu item and handler:

```go
// In newModelInternal:
items := []list.Item{
    // ... existing items ...
    menuItem{title: "My Integration", key: "m"},
}

// In handleMainMenuKeys:
case "m":
    return m.showIntegrationMenu("myintegration", "My Integration", MyIntegrationMenu)
```

### Step 4: Write Tests

Create `internal/integration/registries/myintegration_test.go`:

```go
package registries

import (
    "context"
    "testing"
    "github.com/ichrisbirch/menu/internal/testutil"
)

func TestMyIntegration_Load(t *testing.T) {
    integ := NewMyIntegration()

    ctx := context.Background()
    items, err := integ.Load(ctx)

    testutil.AssertNoError(t, err)
    testutil.AssertTrue(t, len(items) > 0, "should return items")
}

func TestMyIntegration_Search(t *testing.T) {
    integ := NewMyIntegration()
    ctx := context.Background()

    tests := []struct {
        name     string
        query    string
        expected int
    }{
        {"Find items", "item", 1},
        {"No results", "xyz", 0},
    }

    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            items, err := integ.Search(ctx, tt.query)
            testutil.AssertNoError(t, err)
            testutil.AssertEqual(t, tt.expected, len(items))
        })
    }
}
```

## Best Practices

### 1. Use Context for Cancellation

Always accept and respect context:

```go
func (i *Integration) Load(ctx context.Context) ([]Item, error) {
    // Check for cancellation
    select {
    case <-ctx.Done():
        return nil, ctx.Err()
    default:
    }

    // Do work, periodically checking context
    for _, item := range items {
        select {
        case <-ctx.Done():
            return nil, ctx.Err()
        default:
            // Process item
        }
    }

    return items, nil
}
```

### 2. Handle Errors Gracefully

Don't crash on missing data:

```go
func (i *Integration) Load(ctx context.Context) ([]Item, error) {
    data, err := loadData()
    if err != nil {
        if os.IsNotExist(err) {
            // Return empty list, not error
            return []Item{}, nil
        }
        // Return actual errors
        return nil, fmt.Errorf("failed to load: %w", err)
    }
    return data, nil
}
```

### 3. Cache When Appropriate

For expensive operations, cache results:

```go
type CachedIntegration struct {
    cache      []Item
    cacheTime  time.Time
    cacheTTL   time.Duration
}

func (c *CachedIntegration) Load(ctx context.Context) ([]Item, error) {
    // Return cached if still valid
    if time.Since(c.cacheTime) < c.cacheTTL {
        return c.cache, nil
    }

    // Refresh cache
    items, err := c.loadFresh(ctx)
    if err != nil {
        // Return stale cache on error if available
        if c.cache != nil {
            return c.cache, nil
        }
        return nil, err
    }

    c.cache = items
    c.cacheTime = time.Now()
    return items, nil
}
```

### 4. Use Consistent Item IDs

Ensure IDs are stable across loads:

```go
// Good: Stable ID
item.ID = command.Name

// Bad: Unstable ID
item.ID = fmt.Sprintf("%d", rand.Int())
```

Stable IDs enable:

- Favorites tracking
- Recents tracking
- Item references across sessions

### 5. Provide Rich Details

Use the Details map for integration-specific data:

```go
item := Item{
    // ... basic fields ...
    Details: map[string]interface{}{
        "examples": []Example{
            {Command: "ls -la", Description: "List all files"},
        },
        "notes": "Additional context",
        "url":   "https://example.com",
    },
}
```

The UI will automatically render these in the detail view.

## Advanced Features

### Custom Icons

Provide custom icons based on item type:

```go
func getIcon(itemType string) string {
    icons := map[string]string{
        "function":     "ƒ",
        "alias":        "→",
        "system_tool":  "🔧",
        "workflow":     "⚡",
        "learning":     "📚",
    }
    if icon, ok := icons[itemType]; ok {
        return icon
    }
    return "●" // default
}
```

### Priority-Based Sorting

Set priority for default sorting:

```go
item.Priority = 100  // High priority
item.Priority = 50   // Medium priority
item.Priority = 10   // Low priority
```

### Status Indicators

Use status for visual cues:

```go
item.Status = "active"    // Learning: currently studying
item.Status = "completed" // Learning: finished
item.Status = "paused"    // Learning: on hold
```

## Related Files

- `internal/integration/types.go` - Core types and interfaces
- `internal/integration/manager.go` - Manager implementation
- `internal/integration/registries/` - Built-in integrations

## See Also

- [Testing Guide](../testing/testing-guide.md) - How to test integrations
- [Favorites and Recents](../features/favorites-recents.md) - State management
- [Architecture Overview](../architecture/overview.md) - System design
