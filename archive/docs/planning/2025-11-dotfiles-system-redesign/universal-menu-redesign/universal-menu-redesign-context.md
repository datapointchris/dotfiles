# Universal Menu Redesign - Context

**Created:** 2025-11-07
**Last Updated:** 2025-11-07

## Quick Links

- [Plan Document](./universal-menu-redesign-plan.md) - Comprehensive redesign plan
- [Tasks Checklist](./universal-menu-redesign-tasks.md) - Implementation tasks

## Overview

Redesigning the universal menu system to combine Go's power with fzf's simplicity and preview capabilities.

## Key Files

### Existing Implementation

```
tools/menu-go/
├── cmd/menu/main.go                    # Current entry point (Bubble Tea)
├── internal/
│   ├── integration/                    # Keep: Integration system
│   ├── registry/                       # Keep: YAML parsing
│   ├── executor/                       # Keep: Command execution
│   ├── ui/menu.go                      # Replace: Bubble Tea UI
│   └── testutil/                       # Keep: Testing utilities
└── README.md                           # Update: Architecture

common/.local/bin/
├── sess                                # Fixed: BSD head compatibility
├── menu                                # Currently: Compiled Go binary
└── get-docs                            # Keep: Documentation parser

common/.config/menu/
├── config.yml                          # Keep: Menu configuration
├── categories.yml                      # Keep: Category definitions
└── registry/
    ├── commands.yml                    # Keep: Commands registry
    ├── workflows.yml                   # Keep: Workflows registry
    └── learning.yml                    # Keep: Learning topics
```

### New Structure

```
tools/menu-go/
├── cmd/menu/
│   └── main.go                         # New: Cobra CLI commands
├── scripts/
│   └── menu                            # New: Bash wrapper with fzf
├── internal/
│   ├── cli/                            # New: CLI command handlers
│   │   ├── root.go
│   │   ├── list.go
│   │   ├── preview.go
│   │   └── get.go
│   ├── formatter/                      # New: fzf output formatting
│   │   ├── fzf.go
│   │   └── preview.go
│   ├── integration/                    # Keep: Unchanged
│   ├── registry/                       # Keep: Unchanged
│   └── executor/                       # Keep: Unchanged
└── README.md                           # Update: New architecture

common/.local/bin/
├── menu-go                             # New: Go CLI binary
└── menu                                # New: Bash wrapper script
```

## Current Issues

1. ✅ **FIXED:** sess script uses `head -n -1` (GNU-only)
   - **Solution:** Changed to `sed '$d'` (BSD/GNU compatible)
   - **File:** common/.local/bin/sess:161

2. ❌ **No fzf previews** - Core requirement missing
   - menu-go uses Bubble Tea (no preview support)
   - Must see details while navigating

3. ❌ **Deep navigation** - Too many steps
   - Main → Submenu → Detail View → Execute
   - Should be: Main → Category → Select (2 levels)

4. ❌ **Hardcoded colors** - Pink lipgloss.Color("170")
   - Should use terminal colors
   - Should work with theme-sync

5. ❌ **Command execution** - Runs in menu
   - Should place command in terminal instead
   - User should control execution

6. ❌ **No hjkl navigation** - Arrow keys only
   - Need vim-like navigation
   - Should feel like yazi/lazygit

## Related Functions

### lsfunc Pattern (Keep Concept)

```bash
# From: common/.shell/functions.sh

function lsfunc() {
  # Simple grep-based filtering
  # Parses #@name and #--> description comments
  # Outputs colored list
  # Can pipe to other commands
}

function lsalias() {
  # Similar pattern for aliases
}

# Uses get-docs script:
# - Parses #@function_name
# - Parses #--> description
# - Extracts documentation
```

**Keep:** Simplicity, grep filtering, direct output
**Add:** fzf previews with full details

## Requirements Summary

### Must Have

1. **fzf with previews** - Preview shows description, examples, notes
2. **hjkl navigation** - Vim-like (like yazi)
3. **Shallow menus** - Maximum 2 levels deep
4. **Terminal colors** - No hardcoded colors
5. **Command placement** - Put in terminal, not execute
6. **Tmux integration** - Floating popup (80% width/height)

### Should Have

1. **Fast** - Open in <200ms, preview updates instantly
2. **Grep-style filtering** - `/` to search within category
3. **Simple actions** - Enter does the obvious thing
4. **Session switching** - Direct switch, no extra steps

### Nice to Have

1. **Favorites** - Star indicator in lists
2. **Recents** - Recently used items at top
3. **Syntax highlighting** - Code examples in previews
4. **Bash compatibility** - Works in bash (start with zsh)

## Design Principles

1. **Go for data, fzf for UI** - Use each tool for its strength
2. **Core first, features later** - Get basic functionality right
3. **Terminal native** - Should feel like part of the terminal
4. **Simple by default** - Common case should be easy
5. **Power when needed** - Advanced features available but not required

## Key Decisions

### Architecture: Hybrid Go + fzf

- **Go CLI:** Data parsing, formatting, preview generation
- **fzf:** UI, navigation, filtering, preview display
- **Bash wrapper:** Glue layer, tmux detection, command placement

**Rationale:** Go's testing/parsing + fzf's UX = best of both

### CLI Over TUI

- **Was:** Bubble Tea TUI (event loop, state management, custom UI)
- **Now:** CLI that outputs for fzf (stateless, composable)

**Rationale:** fzf does UI better and users know it

### Terminal Colors

- **Was:** Hardcoded lipgloss.Color("170")
- **Now:** ANSI codes, respects terminal theme

**Rationale:** Works with theme-sync, user control

### Command Placement vs Execution

- **Was:** Execute in menu, show result
- **Now:** Place in terminal buffer for editing

**Rationale:** User stays in control, can edit before running

## Migration Strategy

1. **Phase 1:** Build new system alongside old (`menu-new`)
2. **Phase 2:** Test thoroughly, gather feedback
3. **Phase 3:** Switch symlink (`menu` → `menu-new`)
4. **Phase 4:** Remove Bubble Tea code after proven stable

## Testing Strategy

1. **Unit tests:** CLI commands, formatters, preview generation
2. **Integration tests:** Full flow with fixtures
3. **Manual tests:** Different terminals, color schemes, tmux vs non-tmux
4. **Performance tests:** Large registries (100+ items)

## Success Criteria

✅ Can open menu (popup in tmux)
✅ Can navigate with hjkl (feels like vim)
✅ Preview updates instantly as you move
✅ Can filter with `/` within category
✅ Enter places command in terminal
✅ Works with terminal color scheme
✅ Opens in <200ms
✅ All tests pass

## Timeline

- **Week 1:** Core fzf integration + navigation
- **Week 2:** All categories + polish
- **Week 3:** Testing + documentation

## Resources

- [fzf documentation](https://github.com/junegunn/fzf)
- [Cobra CLI framework](https://github.com/spf13/cobra)
- [Original menu architecture](../../../../architecture/menu-system.md)
- [Menu reference guide](../../../../reference/menu-system.md)

## Notes

- The sess bug fix (BSD head compatibility) is a good example of why testing on macOS matters
- The lsfunc pattern shows that simple bash with grep can be very effective
- The get-docs script parsing pattern (#@ and #-->) is elegant and could inspire CLI output format
- Keep the YAML registries - they're working well and easy to maintain
- The integration system in menu-go is well-designed - don't throw it out
- Consider this a refactor of the UI layer, not a complete rewrite
