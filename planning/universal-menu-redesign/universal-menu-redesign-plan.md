# Universal Menu System - Redesign Plan

**Created:** 2025-11-07
**Status:** Planning
**Goal:** Create a unified menu system that combines the power of Go with the simplicity and preview capabilities of fzf

## Executive Summary

We have two menu implementations with different strengths:

1. **lsfunc/lsalias pattern** - Simple bash functions with grep filtering, direct output
2. **menu-go** - Powerful Go TUI with Bubble Tea, YAML registries, testing, but missing fzf previews

The goal is to **combine both approaches**: Keep Go for data management, parsing, and testing, but use fzf for the interface with previews. The result should feel like a native terminal tool (like yazi) with hjkl navigation, immediate previews, and shallow menu structure.

## Core Requirements (Non-Negotiable)

### 1. Shallow Menu Depth

- **Main menu** → **Select item** → **Action**
- NO deep navigation trees
- NO detail view as a separate screen
- Preview shows details inline with fzf

### 2. fzf Integration with Previews

- **Every list must have a preview**
- Preview shows: description, examples, notes, related items
- Preview uses terminal colors (theme-sync compatible)
- Preview updates as you navigate with hjkl

### 3. Navigation

- **hjkl** - Vim-like navigation (like yazi, lazygit, etc.)
- **/** - Search/filter within current view
- **Enter** - Put command in terminal (not execute)
- **Esc** - Back to previous level
- **Ctrl-C** - Quit

### 4. Terminal Integration

- Open in **tmux floating popup** if in tmux (80% width/height, centered)
- Otherwise open in current terminal
- Use **terminal colors** (no hardcoded pink/colors)
- Integrate with theme-sync for consistent theming

### 5. Command Output

- On Enter: **Print command to terminal** for user to edit/execute
- Like: `print -z "command here"` (zsh) or `bind '"\C-m": "command here\n"'` approach
- User stays in control of execution

### 6. Simplicity First

- Core functionality working before adding features
- Grep-style filtering like lsfunc (fast, intuitive)
- Direct, single-step actions

## Current State Analysis

### What We Have in menu-go (Keep)

✅ **Good Architecture:**

- Integration system (pluggable data sources)
- YAML registry loaders (commands.yml, workflows.yml, learning.yml)
- Executor with validation (useful for optional execution)
- Comprehensive testing (84%+ coverage)
- ~6,164 lines of well-structured Go code

✅ **Good Data Model:**

- Integration.Item type (standardized items across sources)
- Integration.Manager (favorites, recents, enrichment)
- Registry loaders (YAML parsing)
- State management (persistent favorites/recents)

### What We Have in menu-go (Replace/Change)

❌ **Bubble Tea TUI:**

- Multi-level navigation (MainMenu → Submenu → DetailView → ExecutionResult)
- No fzf previews
- Hardcoded colors (lipgloss.Color("170") = pink)
- Extra steps before action (select → view details → execute)

❌ **Navigation:**

- Arrow keys only (no hjkl binding)
- List filtering with `/` but no live preview
- Deep menu structure

❌ **Command Execution:**

- Executes in menu, shows result screen
- User wants command placed in terminal instead

### What We Have in lsfunc Pattern (Keep Concept)

✅ **Simplicity:**

```bash
lsfunc git          # Grep-style filtering
# Outputs colored list immediately
# Can pipe to other commands
```

✅ **Direct Output:**

- Prints to terminal, doesn't capture it
- Fast and straightforward
- Terminal-native feel

✅ **Parsing Pattern:**

- `#@function_name` - Function marker
- `#--> Description` - Short description
- Uses `get-docs` script for extraction

## Proposed Architecture

### High-Level Design

```
User → menu → Go CLI → Parse YAML → Generate fzf list → fzf with preview → Output command

Components:
1. Go CLI (menu-go) - Data parsing, formatting, preview generation
2. fzf - UI, navigation, filtering, preview display
3. Shell integration - Command output to terminal
```

### Menu Flow

```
┌─────────────────────────────────────────────────┐
│  menu                                           │
│  (opens in tmux popup if in tmux)               │
└─────────────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────┐
│  Main Menu (fzf)                                │
│  ┌─────────────────┬─────────────────────────┐  │
│  │ s → Sessions    │ Preview:                │  │
│  │ c → Commands    │ Browse and switch       │  │
│  │ w → Workflows   │ tmux sessions           │  │
│  │ l → Learning    │                         │  │
│  │ t → Tools       │ Integration: session-go │  │
│  └─────────────────┴─────────────────────────┘  │
└─────────────────────────────────────────────────┘
                     ↓ (select with Enter)
┌─────────────────────────────────────────────────┐
│  Commands List (fzf with preview)               │
│  ┌─────────────────┬─────────────────────────┐  │
│  │ > fcd           │ Preview:                │  │
│  │   fad           │ fcd - Fuzzy find dir    │  │
│  │   gdp           │                         │  │
│  │   listening     │ Description:            │  │
│  │   /git_         │ Uses fzf to search...   │  │
│  └─────────────────┴─────────────────────────┘  │
│  hjkl to navigate, / to filter, Enter to copy  │
└─────────────────────────────────────────────────┘
                     ↓ (select with Enter)
┌─────────────────────────────────────────────────┐
│  Terminal                                       │
│  $ fcd ~/code▊                                  │
│  (command ready to edit/execute)                │
└─────────────────────────────────────────────────┘
```

### Component Responsibilities

#### 1. Go CLI (menu)

**Purpose:** Data parsing, formatting, and preview generation

**Commands:**

```bash
menu                           # Main menu
menu sessions                  # List sessions with preview data
menu commands [--filter=git]   # List commands, optional filter
menu workflows                 # List workflows with preview data
menu learning                  # List learning topics
menu preview <type> <id>       # Generate preview for fzf
```

**Output Format:**

```
# List format (JSON Lines for structured data)
{"id": "fcd", "title": "fcd", "desc": "Fuzzy find directory", "category": "File Operations"}
{"id": "fad", "title": "fad", "desc": "Git add modified files", "category": "Git"}

# OR simple format for direct fzf consumption:
fcd → Fuzzy find directory
fad → Git add modified files matching pattern
```

**Preview Generation:**

```bash
menu preview command fcd
# Outputs formatted preview:
# Title: fcd
# Category: File Operations
# Description: Fuzzy find directory and cd into it
#
# Command:
#   fcd [directory]
#
# Examples:
#   fcd ~/code    # Search directories in ~/code
#
# Related: fd, z, cdi
```

#### 2. fzf Wrapper Script

**Purpose:** Launch fzf with proper configuration

**Location:** `~/.local/bin/menu` (bash script that calls Go binary)

**Responsibilities:**

- Detect if in tmux → use tmux popup
- Configure fzf with:
  - hjkl bindings
  - Preview command
  - Color scheme from terminal
  - Keybindings for actions

**Example:**

```bash
#!/usr/bin/env bash
# menu - Universal Menu System (fzf wrapper)

MENU_BIN="${MENU_BIN:-$HOME/.local/bin/menu-go}"

# Detect tmux
if [[ -n "$TMUX" ]]; then
  MENU_CMD="tmux display-popup -E -w 80% -h 80% -d '#{pane_current_path}'"
else
  MENU_CMD=""
fi

# fzf configuration
export FZF_DEFAULT_OPTS="
  --ansi
  --bind='ctrl-j:down,ctrl-k:up,ctrl-h:backward-char,ctrl-l:forward-char'
  --bind='ctrl-d:half-page-down,ctrl-u:half-page-up'
  --bind='ctrl-/:toggle-preview'
  --preview-window='right:50%:wrap'
  --layout=reverse
  --info=inline
  --border
"

# Main menu or direct category
case "${1:-}" in
  "")
    # Show main menu
    selected=$($MENU_BIN list-categories |
      fzf --preview="$MENU_BIN preview category {1}" \
          --header="Universal Menu - Select category")

    if [[ -n "$selected" ]]; then
      # Extract category key (first field)
      category=$(echo "$selected" | awk '{print $1}')
      menu "$category"
    fi
    ;;

  sessions|s)
    # Sessions list
    selected=$($MENU_BIN list sessions |
      fzf --preview="$MENU_BIN preview session {1}" \
          --header="Sessions - Enter to switch")

    if [[ -n "$selected" ]]; then
      session=$(echo "$selected" | awk '{print $1}')
      # For sessions, we do want to execute (switch)
      session "$session"
    fi
    ;;

  commands|c)
    # Commands list
    selected=$($MENU_BIN list commands |
      fzf --preview="$MENU_BIN preview command {1}" \
          --header="Commands - Enter to copy to terminal")

    if [[ -n "$selected" ]]; then
      cmd=$(echo "$selected" | awk '{print $1}')
      # Get the actual command
      command=$($MENU_BIN get command "$cmd")
      # Place in terminal buffer (zsh)
      print -z "$command"
    fi
    ;;

  # ... more categories
esac
```

#### 3. Shell Integration

**Purpose:** Place commands in terminal for user execution

**Methods:**

**ZSH:**

```bash
print -z "command here"  # Places in buffer, user can edit
```

**Bash:**

```bash
# More complex, need to use readline
# Option 1: Use history
history -s "command here"
# Option 2: Create a temp file and source it
```

**Tmux Popup:**

```bash
# When in tmux popup, need to send to parent pane
tmux send-keys -t {last} "command here" C-m  # Auto-execute
# OR
tmux send-keys -t {last} "command here"      # Place without executing
```

### YAML Registry (No Changes)

The YAML registries stay the same:

- `commands.yml`
- `workflows.yml`
- `learning.yml`
- `sessions.yml`

The Go code already parses these well.

### Go Code Refactoring

#### Keep (Minimal Changes)

- `internal/registry/` - YAML parsing ✅
- `internal/integration/` - Integration system ✅
- `internal/integration/registries/` - Built-in integrations ✅
- `internal/executor/` - Command execution (for optional use) ✅
- All tests ✅

#### Add

- `internal/cli/` - Cobra commands for list/preview/get operations
- `internal/formatter/` - Format items for fzf consumption
- `internal/preview/` - Generate previews for different item types

#### Remove/Don't Use

- `internal/ui/` - Bubble Tea UI (replaced by fzf)
- Hardcoded colors in lipgloss
- Multi-level navigation state machine

### New Go CLI Structure

```
cmd/menu/
  main.go                    # Cobra CLI setup

internal/
  cli/
    root.go                  # Root command
    list.go                  # list categories|sessions|commands|workflows|learning
    preview.go               # preview <type> <id>
    get.go                   # get <type> <id> (returns command string)

  formatter/
    fzf.go                   # Format items for fzf display
    preview.go               # Format previews (markdown-style)

  integration/               # Keep as-is
    types.go
    manager.go
    state.go
    registries/
      commands.go
      workflows.go
      learning.go
      sessions.go
      # ... etc

  registry/                  # Keep as-is
    loader.go
    types.go

  executor/                  # Keep as-is (optional execution)
    executor.go
```

### Example CLI Commands

```bash
# List categories
$ menu-go list-categories
s → Sessions
c → Commands
w → Workflows
l → Learning
t → Tools

# List commands
$ menu-go list commands
fcd → Fuzzy find directory and cd into it
fad → Git add modified files matching pattern
gdp → Git diff preview with fzf
listening → List applications listening on ports
hosts → View /etc/hosts file

# Preview command
$ menu-go preview command fcd
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
fcd
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Category: File Operations
Type: function

Description:
  Fuzzy find directory and cd into it using fzf

Command:
  fcd [directory]

Examples:
  fcd ~/code
    → Search for directories in ~/code

  fcd
    → Search from current directory

Notes:
  Uses fzf with preview. Respects .gitignore.
  Great for quickly navigating large directory trees.

Related Commands:
  • fd - Find files/directories
  • z - Jump to frecent directories
  • cdi - Interactive cd with fzf

Platform: all

# Get command (for execution)
$ menu-go get command fcd
fcd
```

## Implementation Plan

### Phase 1: Core fzf Integration (Week 1)

**Goal:** Get basic menu working with fzf and previews

#### Step 1.1: Create CLI Commands

- [ ] Add `internal/cli/` package
- [ ] Implement `list-categories` command
- [ ] Implement `list <integration>` command
- [ ] Implement `preview <type> <id>` command
- [ ] Implement `get <type> <id>` command

#### Step 1.2: Format Output for fzf

- [ ] Add `internal/formatter/` package
- [ ] Create `FormatForFzf(items []Item) string`
- [ ] Create `FormatPreview(item Item) string`
- [ ] Use terminal colors (no hardcoded styles)
- [ ] Test with different terminal themes

#### Step 1.3: Create Bash Wrapper

- [ ] Create new `menu` bash script in `tools/menu-go/scripts/`
- [ ] Detect tmux and use popup
- [ ] Configure fzf with hjkl bindings
- [ ] Wire up preview command
- [ ] Test main menu → commands list → preview flow

#### Step 1.4: Shell Integration

- [ ] Implement `print -z` for zsh
- [ ] Test command placement in terminal
- [ ] Handle tmux popup → parent pane communication
- [ ] Test in both tmux and non-tmux environments

**Success Criteria:**

- Can open menu (in popup if tmux)
- Can select "Commands" category
- Can navigate with hjkl
- Preview updates as you move
- Enter places command in terminal
- No execution happens in menu

### Phase 2: Polish & Navigation (Week 1-2)

#### Step 2.1: Enhanced Navigation

- [ ] Add `/` for filtering within fzf
- [ ] Add `Ctrl-/` to toggle preview
- [ ] Add `Ctrl-d/u` for page up/down
- [ ] Test vim muscle memory (should feel natural)

#### Step 2.2: Preview Enhancements

- [ ] Color syntax in code examples (if using bat/highlighting)
- [ ] Format steps in workflows as numbered list
- [ ] Show learning resources organized by type
- [ ] Show session preview with window list

#### Step 2.3: Sessions Integration

- [ ] Make sessions actually switch (not just copy)
- [ ] Show active sessions with indicator
- [ ] Preview shows session windows/panes
- [ ] Test rapid session switching

**Success Criteria:**

- hjkl navigation feels like yazi/vim
- Previews are informative and well-formatted
- Filtering with `/` works smoothly
- Sessions actually switch on Enter

### Phase 3: All Categories (Week 2)

#### Step 3.1: Implement Each Category

- [ ] Sessions (s)
- [ ] Commands (c)
- [ ] Workflows (w)
- [ ] Learning (l)
- [ ] Tools (t)
- [ ] Tasks (if in git repo with Taskfile)

#### Step 3.2: Category-Specific Behavior

- [ ] Sessions: execute switch
- [ ] Commands: place in terminal
- [ ] Workflows: show steps, optionally open related file
- [ ] Learning: show resources, open links/notes
- [ ] Tools: show tldr, open docs

**Success Criteria:**

- All categories work
- Each category has appropriate action
- Previews are consistent and informative

### Phase 4: Quality & Testing (Week 2-3)

#### Step 4.1: Testing

- [ ] Test CLI commands (list, preview, get)
- [ ] Test formatter output
- [ ] Test in different terminal emulators
- [ ] Test with different color schemes (theme-sync)
- [ ] Test tmux popup vs. fullscreen
- [ ] Test on macOS (primary platform)

#### Step 4.2: Error Handling

- [ ] Handle missing YAML files gracefully
- [ ] Handle empty categories
- [ ] Handle invalid item IDs
- [ ] Show helpful error messages

#### Step 4.3: Performance

- [ ] Ensure previews generate quickly (<100ms)
- [ ] Cache YAML parsing if needed
- [ ] Profile with large registries (100+ items)

**Success Criteria:**

- All tests pass
- No visible lag in preview generation
- Works across terminal emulators
- Respects terminal color scheme

### Phase 5: Documentation & Polish (Week 3)

#### Step 5.1: Documentation

- [ ] Update README with new architecture
- [ ] Document bash wrapper script
- [ ] Document CLI commands
- [ ] Add examples for extending registries
- [ ] Document tmux keybinding setup

#### Step 5.2: Tmux Integration

- [ ] Add tmux.conf snippet for `prefix + m`
- [ ] Test popup sizing (80% feels right?)
- [ ] Test popup positioning (centered)
- [ ] Ensure popup works in nested tmux

#### Step 5.3: Final Polish

- [ ] Add help text to fzf headers
- [ ] Consistent formatting across all previews
- [ ] Remove any old Bubble Tea code
- [ ] Clean up unused dependencies

**Success Criteria:**

- Documentation is clear and complete
- Tmux integration works perfectly
- Code is clean and maintainable

## Design Decisions & Rationale

### Why Keep Go?

✅ **Advantages:**

- Strong typing catches errors at compile time
- Fast binary (faster than bash for parsing YAML)
- Excellent testing story (current 84%+ coverage)
- Easy to maintain and extend
- Good structure with integrations system

❌ **What We're NOT Using from Go:**

- Bubble Tea TUI (replaced with fzf)
- Direct terminal control
- Event loop and state management

**Go Role:** Data layer - parsing, formatting, preparing data for fzf

### Why Use fzf?

✅ **Advantages:**

- Built-in preview support (core requirement!)
- Users already know it (muscle memory)
- Highly customizable (keybindings, colors)
- Fast and responsive
- Works in tmux popups
- Integrates with terminal color schemes

**fzf Role:** Presentation layer - UI, navigation, filtering

### Why Bash Wrapper?

✅ **Advantages:**

- Easy to modify without recompiling
- Natural shell integration (print -z)
- Can detect tmux and adjust
- Can read shell environment
- Simple to understand

**Bash Role:** Glue layer - connecting Go CLI with fzf and shell

### Why Not Bubble Tea?

❌ **Bubble Tea Issues:**

- No fzf preview support (core requirement missing)
- Must implement navigation ourselves (wheel reinvention)
- Color schemes must be hardcoded or configured
- More code to maintain
- Extra abstraction layer

### Color Strategy

**Use Terminal Colors:**

- fzf inherits from `$FZF_DEFAULT_OPTS`
- ANSI color codes for formatting (Go can output these)
- Compatible with theme-sync
- User's terminal theme applies automatically

**No Hardcoded Colors:**

- Remove lipgloss color definitions
- Use ANSI codes: `\033[34m` (blue), `\033[32m` (green), etc.
- Or use standard tput/terminfo

## Edge Cases & Considerations

### Tmux Popup Edge Cases

1. **Nested tmux sessions**
   - Test if popup works in nested tmux
   - May need to use `$TMUX_PANE` detection

2. **Popup size on small terminals**
   - 80% might be too large on small screens
   - Consider min/max sizing

3. **Command passing from popup to parent**
   - `tmux send-keys` to parent pane
   - May need to detect parent pane ID

### Shell Compatibility

1. **ZSH:** `print -z` works great ✅
2. **Bash:** More complex, need readline tricks
3. **Fish:** Different syntax

**Decision:** Start with ZSH (primary shell), add others later

### Category-Specific Actions

Different categories need different behaviors:

| Category  | Action on Enter | Notes |
|-----------|----------------|-------|
| Sessions  | Switch session | Execute immediately |
| Commands  | Place in terminal | User edits/executes |
| Workflows | Show steps | Informational |
| Learning  | Open resource? | TBD - maybe place URL |
| Tools     | Show tldr | Informational |

### Performance Considerations

1. **YAML Parsing:**
   - Cache parsed YAML in memory
   - Or parse on-demand (profile first)

2. **Preview Generation:**
   - Must be fast (<100ms)
   - Avoid complex formatting in hot path

3. **Large Registries:**
   - Test with 100+ commands
   - fzf handles filtering, we just provide data

## Success Metrics

### User Experience

✅ **Fast:** Menu opens in <200ms
✅ **Responsive:** Preview updates instantly
✅ **Intuitive:** hjkl works like vim/yazi
✅ **Shallow:** 2 levels max (main → category)
✅ **Visual:** Preview shows everything needed
✅ **Integrated:** Works in tmux popup naturally
✅ **Themed:** Respects terminal colors

### Technical

✅ **Testable:** CLI commands have unit tests
✅ **Maintainable:** Clear separation of concerns
✅ **Extensible:** Easy to add new categories
✅ **Reliable:** Handles edge cases gracefully

### Functional

✅ **Commands:** Can find and copy commands easily
✅ **Sessions:** Can switch sessions in 2 keystrokes
✅ **Workflows:** Can view multi-step processes
✅ **Learning:** Can see all resources for a topic

## Migration Path

### Phase 1: New System Alongside Old

- Keep current menu-go as `menu-old`
- Build new system as `menu-new`
- Test new system thoroughly
- Both binaries available

### Phase 2: Cutover

- Replace `menu` symlink → `menu-new`
- Keep old binary as backup
- Monitor for issues

### Phase 3: Cleanup

- Remove Bubble Tea code
- Remove unused UI code
- Update all documentation
- Archive old system

## Open Questions

1. **Preview Formatting:**
   - Use bat for syntax highlighting in previews?
   - Or keep it simple with ANSI colors?
   - **Decision:** Start simple, add bat later if needed

2. **Favorites/Recents:**
   - Show stars in list (★)?
   - Sort by recents?
   - **Decision:** Yes, add indicators in list format

3. **Workflows vs Commands:**
   - Should workflows be separate category?
   - Or filtered view of commands?
   - **Decision:** Separate - different data structure

4. **Learning Resources:**
   - Open URLs automatically?
   - Or just show in preview?
   - **Decision:** Show in preview, user copies if wanted

5. **Tasks Integration:**
   - Should tasks be in main menu?
   - Or separate command (keep existing `task`)?
   - **Decision:** In menu if Taskfile exists in current repo

## Risk Mitigation

### Risk: Performance Issues

**Mitigation:**

- Profile early and often
- Cache parsed YAML
- Keep preview generation simple
- Fallback to simpler formatting if slow

### Risk: Shell Integration Complexity

**Mitigation:**

- Start with ZSH only
- Document limitations clearly
- Add other shells incrementally
- Provide fallback (just print to stdout)

### Risk: Tmux Popup Issues

**Mitigation:**

- Make popup optional (env var to disable)
- Test extensively in tmux
- Provide non-popup fallback
- Document known issues

### Risk: User Confusion

**Mitigation:**

- Clear help text in fzf header
- Comprehensive documentation
- Examples in README
- Smooth transition from old system

## Next Steps

1. ✅ **Fix sess bug** - DONE
2. ✅ **Create this planning document** - DONE
3. 📝 **Review and approve plan** - PENDING
4. 🔨 **Start Phase 1: Core fzf Integration**

## Appendix: Code Examples

### Example: Formatter Output

```go
// internal/formatter/fzf.go

func FormatForFzf(items []integration.Item) string {
    var lines []string
    for _, item := range items {
        // Simple format: id → description
        line := fmt.Sprintf("%s → %s", item.ID, item.Description)
        lines = append(lines, line)
    }
    return strings.Join(lines, "\n")
}
```

### Example: Preview Generator

```go
// internal/formatter/preview.go

func FormatPreview(item integration.Item) string {
    var buf strings.Builder

    // Title with separator
    buf.WriteString(ColorBlue(item.Title))
    buf.WriteString("\n")
    buf.WriteString(strings.Repeat("━", 50))
    buf.WriteString("\n\n")

    // Basic info
    if item.Category != "" {
        buf.WriteString(fmt.Sprintf("Category: %s\n", item.Category))
    }

    // Description
    if item.Description != "" {
        buf.WriteString(fmt.Sprintf("\n%s\n", item.Description))
    }

    // Command
    if item.Command != "" {
        buf.WriteString("\nCommand:\n")
        buf.WriteString(fmt.Sprintf("  %s\n", ColorGreen(item.Command)))
    }

    // Examples
    if examples, ok := item.Details["examples"].([]interface{}); ok {
        buf.WriteString("\nExamples:\n")
        for _, ex := range examples {
            // Format example...
        }
    }

    return buf.String()
}
```

### Example: Bash Wrapper

```bash
#!/usr/bin/env bash
# menu - Universal Menu fzf wrapper

MENU_BIN="$HOME/.local/bin/menu-go"

# fzf configuration for vim-like navigation
FZF_OPTS=(
  --ansi
  --bind='ctrl-j:down,ctrl-k:up,ctrl-h:backward-char,ctrl-l:forward-char'
  --bind='j:down,k:up'  # Also allow bare j/k
  --bind='ctrl-d:half-page-down,ctrl-u:half-page-up'
  --bind='ctrl-/:toggle-preview'
  --preview-window='right:50%:wrap'
  --layout=reverse
  --border
)

# Main menu
main_menu() {
  local selected
  selected=$($MENU_BIN list-categories | \
    fzf "${FZF_OPTS[@]}" \
        --preview="$MENU_BIN preview category {1}" \
        --header="Universal Menu - hjkl to navigate, / to filter, Enter to select")

  if [[ -n "$selected" ]]; then
    category=$(echo "$selected" | awk '{print $1}')
    category_menu "$category"
  fi
}

# Category menu
category_menu() {
  local category="$1"
  local selected

  selected=$($MENU_BIN list "$category" | \
    fzf "${FZF_OPTS[@]}" \
        --preview="$MENU_BIN preview $category {1}" \
        --header="$category - Enter to select, Esc to go back")

  if [[ -n "$selected" ]]; then
    item=$(echo "$selected" | awk '{print $1}')
    handle_selection "$category" "$item"
  fi
}

# Handle selection based on category
handle_selection() {
  local category="$1"
  local item="$2"

  case "$category" in
    sessions)
      # Execute session switch
      session "$item"
      ;;
    commands)
      # Place in terminal
      cmd=$($MENU_BIN get command "$item")
      print -z "$cmd"
      ;;
    *)
      # Default: just copy
      $MENU_BIN get "$category" "$item"
      ;;
  esac
}

# Entry point
if [[ -n "$TMUX" ]]; then
  # In tmux: use popup
  tmux display-popup -E -w 80% -h 80% -d "#{pane_current_path}" "$0 --no-popup $*"
else
  main_menu "$@"
fi
```

## Conclusion

This redesign maintains the strengths of menu-go (Go's type safety, testing, YAML parsing) while adding the missing core requirement: **fzf previews**. The result is a hybrid system that feels like a native terminal tool while maintaining the power and maintainability of Go.

The key insight: **Go is great for data management, fzf is great for UI**. By separating concerns and using each tool for what it's best at, we get a system that's powerful, testable, maintainable, AND has the UX you wanted from the start.
