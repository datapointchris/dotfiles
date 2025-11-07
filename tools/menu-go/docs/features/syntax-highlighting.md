# Syntax Highlighting

The menu system provides syntax highlighting for commands and code examples using the Glamour library, which renders markdown with syntax highlighting powered by Chroma.

## Overview

Syntax highlighting is automatically applied to:

1. **Commands** - In detail view, the main command is highlighted
2. **Examples** - Code examples in detail view are highlighted
3. **Multi-line scripts** - Commands with multiple lines get proper highlighting

## Implementation

### Core Function

The `renderCodeBlock` function handles all syntax highlighting:

```go
// renderCodeBlock renders a code block with syntax highlighting
func renderCodeBlock(code, language string) string {
    // Create markdown code block
    markdown := fmt.Sprintf("```%s\n%s\n```", language, code)

    // Create glamour renderer with dark style
    r, err := glamour.NewTermRenderer(
        glamour.WithStylePath("dark"),
        glamour.WithWordWrap(120),
    )
    if err != nil {
        // Fallback to plain code block if glamour fails
        codeStyle := lipgloss.NewStyle().
            Padding(1, 2).
            Border(lipgloss.RoundedBorder()).
            BorderForeground(lipgloss.Color("240"))
        return codeStyle.Render(code)
    }

    // Render with syntax highlighting
    out, err := r.Render(markdown)
    if err != nil {
        // Fallback to plain code block
        codeStyle := lipgloss.NewStyle().
            Padding(1, 2).
            Border(lipgloss.RoundedBorder()).
            BorderForeground(lipgloss.Color("240"))
        return codeStyle.Render(code)
    }

    return strings.TrimSpace(out)
}
```

### Integration Points

#### 1. Command Highlighting

In detail view, commands are highlighted with bash syntax:

```go
// Command if executable
if item.Executable && item.Command != "" {
    cmdStyle := lipgloss.NewStyle().
        Foreground(lipgloss.Color("46")).
        Bold(true)
    content.WriteString(cmdStyle.Render("Command:\n"))

    // Render command with syntax highlighting
    highlighted := renderCodeBlock(item.Command, "bash")
    content.WriteString(highlighted)
    content.WriteString("\n")
}
```

#### 2. Example Highlighting

Command examples are also highlighted:

```go
// Examples
if examples, ok := details["examples"].([]interface{}); ok && len(examples) > 0 {
    content.WriteString("Examples:\n")
    for _, ex := range examples {
        if exMap, ok := ex.(map[string]interface{}); ok {
            cmd := exMap["cmd"]
            desc := exMap["desc"]
            if cmdStr, ok := cmd.(string); ok {
                // Render command with syntax highlighting
                highlighted := renderCodeBlock(cmdStr, "bash")
                content.WriteString(highlighted)
                content.WriteString(fmt.Sprintf("\n  %v\n\n", desc))
            }
        }
    }
}
```

## Go Language Features

### 1. Markdown-Based Rendering

Glamour renders markdown, so we create markdown code blocks:

```go
// Convert code to markdown code block
markdown := fmt.Sprintf("```%s\n%s\n```", language, code)
```

**Supported languages:**

- bash
- go
- python
- javascript
- typescript
- yaml
- json
- and many more (via Chroma)

### 2. Error Handling with Fallback

The implementation uses a fallback pattern for resilience:

```go
// Try to create renderer
r, err := glamour.NewTermRenderer(options...)
if err != nil {
    return fallbackRender(code)  // Fallback on error
}

// Try to render
out, err := r.Render(markdown)
if err != nil {
    return fallbackRender(code)  // Fallback on error
}

return out  // Success
```

**Benefits:**

- Application never crashes due to syntax highlighting failure
- Graceful degradation if glamour is unavailable
- User always sees content, just without highlighting

### 3. Functional Options Pattern

Glamour uses functional options for configuration:

```go
r, err := glamour.NewTermRenderer(
    glamour.WithStylePath("dark"),     // Option 1
    glamour.WithWordWrap(120),         // Option 2
)
```

**Pattern explanation:**

```go
// Option function type
type Option func(*Renderer) error

// Option constructors
func WithStylePath(style string) Option {
    return func(r *Renderer) error {
        r.style = style
        return nil
    }
}

func WithWordWrap(width int) Option {
    return func(r *Renderer) error {
        r.wordWrap = width
        return nil
    }
}

// Constructor accepts options
func NewTermRenderer(options ...Option) (*Renderer, error) {
    r := &Renderer{}
    for _, opt := range options {
        if err := opt(r); err != nil {
            return nil, err
        }
    }
    return r, nil
}
```

**Benefits:**

- Extensible (easy to add new options)
- Optional (can omit any option)
- Type-safe (compile-time checking)
- Self-documenting (option names explain intent)

### 4. Type Assertions for Interface Handling

When extracting examples from the Details map:

```go
if examples, ok := details["examples"].([]interface{}); ok {
    // Type assertion successful - examples is []interface{}
    for _, ex := range examples {
        if exMap, ok := ex.(map[string]interface{}); ok {
            // Type assertion successful - ex is map[string]interface{}
            if cmdStr, ok := cmd.(string); ok {
                // Type assertion successful - cmd is string
                highlighted := renderCodeBlock(cmdStr, "bash")
            }
        }
    }
}
```

**Pattern: "comma ok" idiom**

```go
value, ok := interfaceValue.(ConcreteType)
if ok {
    // Type assertion succeeded, use value
} else {
    // Type assertion failed, value is zero value of ConcreteType
}
```

**Why needed:**

- Details map uses `interface{}` for flexibility
- Need to safely extract typed values
- Prevents panics from incorrect type assertions

## Visual Examples

### Before (No Syntax Highlighting)

```
Command: ls -la
```

### After (With Syntax Highlighting)

```
Command:
┌─────────────────────────────────────┐
│ ls -la                              │
│     ^                               │
│     └─ flags in different color     │
└─────────────────────────────────────┘
```

Colors applied:

- Commands: highlighted in primary color
- Flags/options: highlighted in secondary color
- Strings: highlighted in string color
- Comments: dimmed/gray

### Complex Example

**Git command with syntax highlighting:**

```bash
git log --oneline --graph --decorate --all
│   │   │         │       │          └─ option (yellow)
│   │   │         │       └─ option (yellow)
│   │   │         └─ option (yellow)
│   │   └─ flag (cyan)
│   └─ flag (cyan)
└─ command (green)
```

## Styling

### Dark Theme

The implementation uses the "dark" theme optimized for terminal displays:

```go
glamour.WithStylePath("dark")
```

### Available Styles

Glamour includes several built-in styles:

- `dark` - Dark theme (default, works well in terminals)
- `light` - Light theme
- `dracula` - Dracula color scheme
- `notty` - Plain text (no ANSI colors)
- `auto` - Automatically detect terminal theme

### Word Wrapping

Commands are wrapped at 120 characters:

```go
glamour.WithWordWrap(120)
```

This ensures long commands don't overflow the terminal width.

## Performance Considerations

### Renderer Caching

Currently, a new renderer is created for each code block. This could be optimized:

```go
// Create renderer once at startup
var renderer *glamour.TermRenderer

func init() {
    renderer, _ = glamour.NewTermRenderer(
        glamour.WithStylePath("dark"),
        glamour.WithWordWrap(120),
    )
}

// Reuse renderer
func renderCodeBlock(code, language string) string {
    if renderer == nil {
        return fallbackRender(code)
    }
    // ... use renderer ...
}
```

**Trade-offs:**

- **Pro**: Faster rendering (no initialization per block)
- **Con**: Uses more memory (renderer stays in memory)
- **Pro**: Simpler error handling (fail once at startup)

**Current approach**: Create per-request (acceptable for interactive UI)

### Render Cost

Syntax highlighting adds minimal overhead:

- First render: ~10-20ms (includes Chroma initialization)
- Subsequent renders: ~1-5ms (Chroma is cached)

For an interactive TUI, this is imperceptible to users.

## Dependencies

### Libraries

```go
import "github.com/charmbracelet/glamour"
```

**go.mod entry:**

```
github.com/charmbracelet/glamour v0.10.0
```

### Transitive Dependencies

Glamour brings in:

- `github.com/alecthomas/chroma` - Syntax highlighting engine
- `github.com/yuin/goldmark` - Markdown parser
- `github.com/microcosm-cc/bluemonday` - HTML sanitization
- `github.com/muesli/reflow` - Text wrapping

## Limitations

### 1. Terminal Color Support

Syntax highlighting requires terminal with ANSI color support:

- ✓ Modern terminals (iTerm2, Alacritty, Terminal.app)
- ✓ tmux/screen with 256 colors
- ✗ Very old terminals or restricted environments

Fallback: Plain text rendering without colors

### 2. Language Detection

Currently hardcoded to "bash" for all commands:

```go
highlighted := renderCodeBlock(item.Command, "bash")
```

Could be enhanced to detect language from context or file extension.

### 3. Style Customization

Style is hardcoded to "dark". Could be made configurable:

```go
style := os.Getenv("MENU_HIGHLIGHT_STYLE")
if style == "" {
    style = "dark"
}
r, err := glamour.NewTermRenderer(glamour.WithStylePath(style))
```

## Testing

### Manual Testing

```bash
# Run menu
go run cmd/menu/main.go

# Navigate to a command (e.g., "ls")
# Press Enter to view details
# Verify syntax highlighting appears correctly
```

### Fallback Testing

Test fallback rendering by temporarily breaking glamour:

```go
// Force fallback by returning error
func renderCodeBlock(code, language string) string {
    return fallbackRender(code)  // Skip glamour entirely
}
```

### Unit Testing

```go
func TestRenderCodeBlock(t *testing.T) {
    code := `ls -la`
    result := renderCodeBlock(code, "bash")

    // Verify output is non-empty
    if result == "" {
        t.Fatal("renderCodeBlock returned empty string")
    }

    // Verify output contains the code
    if !strings.Contains(result, "ls") {
        t.Fatal("renderCodeBlock output missing command")
    }
}
```

## Future Enhancements

### 1. Language Detection

Automatically detect language from context:

```go
func detectLanguage(code string, context Item) string {
    // Check for shebang
    if strings.HasPrefix(code, "#!/bin/bash") {
        return "bash"
    }
    if strings.HasPrefix(code, "#!/usr/bin/env python") {
        return "python"
    }

    // Check context
    if strings.Contains(context.Category, "Python") {
        return "python"
    }

    // Default
    return "bash"
}
```

### 2. Custom Themes

Allow users to specify custom Chroma styles:

```go
// ~/.config/menu/config.yml
syntax_highlighting:
  style: dracula
  word_wrap: 100
```

### 3. Diff Highlighting

For git workflows, highlight diffs:

```go
if strings.Contains(command, "git diff") {
    highlighted := renderCodeBlock(output, "diff")
}
```

### 4. Interactive Examples

Make examples executable directly:

```
Examples:
┌─────────────────────────────────┐
│ git log --oneline              │  Press Enter to execute
└─────────────────────────────────┘
```

## Related Files

- `internal/ui/menu.go` - UI integration and rendering
- `go.mod` - Dependency declaration

## See Also

- [Favorites and Recents](favorites-recents.md) - Persistent favorites
- [Clipboard Support](clipboard-support.md) - Copy commands to clipboard
- [Command Execution](../development/command-execution.md) - How commands run
