# Clipboard Support

The menu system provides cross-platform clipboard integration, allowing users to copy commands directly to their system clipboard without manual selection.

## Overview

Clipboard support is implemented using the `atotto/clipboard` library, which provides a cross-platform Go API for clipboard operations on:

- macOS (using `pbcopy`/`pbpaste`)
- Linux (using `xclip`, `xsel`, or Wayland)
- Windows (using Win32 API)

## Usage

### Copying Commands

In the detail view, press `c` to copy the currently displayed command to clipboard:

```
Detail View:
★ 🔧 ls

Category: File Operations
Command:
┌────────────────────────────┐
│ ls -la                     │
└────────────────────────────┘

Press 'c' to copy → "ls -la" copied to clipboard
```

### Keyboard Shortcut

- **Key**: `c` (lowercase)
- **Context**: Detail view only
- **Availability**: Only when item has a command (item.Command != "")

## Implementation

### UI Integration

The clipboard copy functionality is implemented in `internal/ui/menu.go`:

```go
func (m Model) handleDetailKeys(msg tea.KeyMsg) (tea.Model, tea.Cmd) {
    switch msg.String() {
    case "c":
        // Copy command to clipboard
        if m.selectedItem.Command != "" {
            err := clipboard.WriteAll(m.selectedItem.Command)
            if err != nil {
                m.err = fmt.Errorf("failed to copy to clipboard: %v", err)
            } else {
                // Success - clear any previous errors
                m.err = nil
            }
        }
        return m, nil
    // ... other keys ...
    }
}
```

### Error Handling

The implementation handles clipboard errors gracefully:

1. **Success**: Error state is cleared (m.err = nil)
2. **Failure**: Error is displayed to user but doesn't crash the app
3. **Unavailable**: If clipboard access fails, user sees error message

### Cross-Platform Considerations

The `atotto/clipboard` library automatically handles platform-specific implementations:

**macOS:**

```go
// Uses pbcopy internally
clipboard.WriteAll("ls -la")
// Equivalent to: echo "ls -la" | pbcopy
```

**Linux (X11):**

```go
// Uses xclip or xsel
clipboard.WriteAll("ls -la")
// Equivalent to: echo "ls -la" | xclip -selection clipboard
```

**Linux (Wayland):**

```go
// Uses wl-clipboard
clipboard.WriteAll("ls -la")
// Equivalent to: echo "ls -la" | wl-copy
```

**Windows:**

```go
// Uses Win32 OpenClipboard/SetClipboardData
clipboard.WriteAll("ls -la")
```

## Go Language Features

### Simple API Usage

The clipboard library provides a simple, idiomatic Go API:

```go
import "github.com/atotto/clipboard"

// Write to clipboard
err := clipboard.WriteAll("some text")

// Read from clipboard
text, err := clipboard.ReadAll()
```

### Error Handling Pattern

```go
if m.selectedItem.Command != "" {
    err := clipboard.WriteAll(m.selectedItem.Command)
    if err != nil {
        // Handle error gracefully
        m.err = fmt.Errorf("failed to copy to clipboard: %v", err)
    } else {
        // Clear previous errors on success
        m.err = nil
    }
}
```

**Pattern highlights:**

- Check for non-empty command before attempting copy
- Wrap error with context (`fmt.Errorf` with `%v`)
- Clear error state on success (don't leave stale errors)

## Use Cases

### 1. Quick Command Reuse

Copy a command to clipboard, then paste into a different terminal:

```
1. Navigate to command: fcd
2. Press Enter to view details
3. Press 'c' to copy: "fcd [directory]"
4. Switch to terminal
5. Paste (Cmd+V / Ctrl+Shift+V)
6. Execute
```

### 2. Documentation Sharing

Copy commands to share in documentation or chat:

```
1. Find useful git workflow command
2. Press 'c' to copy
3. Paste into team documentation
4. Share knowledge with teammates
```

### 3. Command Composition

Copy base command, modify in terminal:

```
1. Find command: "git log --oneline"
2. Copy to clipboard
3. Paste in terminal
4. Add additional flags: "git log --oneline --author=chris"
5. Execute
```

## Help Text Integration

The help text dynamically shows clipboard availability:

```go
case DetailView:
    copyHint := ""
    if m.selectedItem.Command != "" {
        copyHint = "  Copy: c"
    }
    help := helpStyle.Render(fmt.Sprintf("Back: Esc%s  Quit: Ctrl+C", copyHint))
```

**Result:**

- With command: `Back: Esc  Copy: c  Quit: Ctrl+C`
- Without command: `Back: Esc  Quit: Ctrl+C`

## Limitations

### 1. Clipboard Availability

Clipboard access may fail if:

- Running in a headless environment (no X server)
- Required clipboard tools not installed (xclip, xsel, wl-clipboard)
- Permission denied (restrictive security policies)

### 2. Text-Only

The implementation only supports plain text copying. Multi-line commands are copied as-is, including newlines.

### 3. No Visual Feedback

Currently there's no visual confirmation that copy succeeded beyond clearing the error state. Future enhancement could add a temporary "Copied!" message.

## Dependencies

### Library

```go
import "github.com/atotto/clipboard"
```

**go.mod entry:**

```
github.com/atotto/clipboard v0.1.4
```

### Platform Dependencies

**macOS:** Built-in (uses pbcopy/pbpaste)

**Linux:** Requires one of:

- `xclip` (X11)
- `xsel` (X11)
- `wl-clipboard` (Wayland)

**Windows:** Built-in (uses Win32 API)

## Testing

### Manual Testing

```bash
# Build and run
go run cmd/menu/main.go

# Navigate to any command
# Press Enter to view details
# Press 'c' to copy
# Verify clipboard contents:
pbpaste                 # macOS
xclip -selection clipboard -o  # Linux X11
wl-paste                # Linux Wayland
```

### Unit Testing Challenges

Clipboard operations are difficult to unit test because:

1. Requires actual clipboard access (platform-dependent)
2. State is global (shared with other applications)
3. May not be available in CI environments

Current approach: Manual testing and integration tests only.

**Potential solution:**

```go
// Create clipboard interface for dependency injection
type Clipboard interface {
    WriteAll(text string) error
    ReadAll() (string, error)
}

// Use mock clipboard in tests
type MockClipboard struct {
    contents string
    writeErr error
}

func (m *MockClipboard) WriteAll(text string) error {
    if m.writeErr != nil {
        return m.writeErr
    }
    m.contents = text
    return nil
}
```

## Future Enhancements

### 1. Visual Confirmation

Add temporary "Copied!" message:

```go
type CopiedMsg struct{}

func copyToClipboard(cmd string) tea.Cmd {
    return func() tea.Msg {
        if err := clipboard.WriteAll(cmd); err != nil {
            return err
        }
        return CopiedMsg{}
    }
}

// In Update:
case CopiedMsg:
    // Show temporary message, then clear after 2 seconds
    return m, tea.Tick(2*time.Second, func(time.Time) tea.Msg {
        return ClearCopiedMsg{}
    })
```

### 2. Rich Clipboard

Support copying with formatting (for documentation):

```go
// Copy as markdown code block
text := fmt.Sprintf("```bash\n%s\n```", command)
clipboard.WriteAll(text)
```

### 3. Clipboard History

Track recent clipboard operations:

```go
type ClipboardHistory struct {
    items    []string
    maxItems int
}

func (h *ClipboardHistory) Add(text string) {
    h.items = append([]string{text}, h.items...)
    if len(h.items) > h.maxItems {
        h.items = h.items[:h.maxItems]
    }
}
```

### 4. Multi-Item Copy

Allow copying multiple items at once:

```go
// Copy all examples from a command
var examples []string
for _, ex := range item.Examples {
    examples = append(examples, ex.Command)
}
text := strings.Join(examples, "\n")
clipboard.WriteAll(text)
```

## Related Files

- `internal/ui/menu.go` - UI integration and keyboard handling
- `go.mod` - Dependency declaration

## See Also

- [Favorites and Recents](favorites-recents.md) - Persistent favorites and recent items
- [Syntax Highlighting](syntax-highlighting.md) - Code highlighting in details
- [Command Execution](../development/command-execution.md) - How commands are executed
