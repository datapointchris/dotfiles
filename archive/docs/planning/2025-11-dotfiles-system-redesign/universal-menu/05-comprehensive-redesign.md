# Universal Menu System - Comprehensive Redesign

**Date:** 2025-11-06
**Status:** Planning
**Previous:** Phase 1 implementation with gum + loop mode

## Executive Summary

Evolution from auto-discovery tool listing to **curated personal knowledge base and command palette** with:

- Function-based grouping (not type-based)
- Rich documentation (descriptions, examples, notes, keywords)
- Searchable by capability (not just name)
- Integrated session management (replacing sesh)
- Tmuxinator workflow integration
- Custom keybinding navigation

---

## Problem Statement

### Current Limitations

1. **Auto-discovery is insufficient**
   - Showing all aliases/functions is overwhelming
   - No descriptions visible without selection
   - Can't distinguish important vs trivial commands
   - Missing context about when/why to use something

2. **Type-based organization doesn't match mental model**
   - Users search by *what they want to do*, not *what type of tool*
   - "Git operations" is more useful than "aliases" + "functions" + "commands"

3. **Multiple tools doing similar things**
   - sesh: Session management (heavy, external dependency)
   - tmuxinator: Project sessions (underutilized)
   - Manual session switching (primitive)
   - Need unified approach

4. **Documentation scattered**
   - get-docs system for scripts
   - Comments in functions
   - Plugins have no docs
   - No single source of truth

---

## Research Findings

### Command Palette Patterns

**kb (CLI Knowledge Base Manager)**

- Text-oriented, developer-focused
- Quick note collection and access
- Organized by topics/tags
- Searchable with filters

**Obsidian + Command Palette**

- Markdown-based (filesystem-native)
- Command palette for quick actions
- Tag and search integration
- Templates for consistent structure

**Key Insight:** Personal knowledge bases work best when they're:

1. Filesystem-native (plain text, version controlled)
2. Searchable by multiple dimensions (tags, keywords, content)
3. Easy to add/edit entries
4. Integrated into existing workflow

### Forgit Integration

**Installation Pattern:**

- Manual clone to `$ZSH_PLUGINS_DIR/forgit`
- Source in zshrc after fzf
- Environment variables for configuration
- Identical for bash/zsh

**Features:**

- Interactive git commands with fzf previews
- Git shortcuts: glo, gd, ga, etc.
- Would fit nicely in "Git Operations" category

### Tmuxinator Best Practices (2024)

**Workflow Pattern:**

1. YAML config per project in `~/.config/tmuxinator/`
2. Define windows, panes, layouts, startup commands
3. Project hooks: on_project_start, on_project_first_start, on_project_exit
4. `tmuxinator start <project>` - creates or attaches

**Integration Points:**

- List projects in menu
- Quick launch from menu
- Edit configs from menu
- Create new project templates

**Common Use Cases:**

- Development environments (app + api + logs + editor)
- Monitoring dashboards (multiple service logs)
- Research sessions (notes + research + terminal)

### Session Management Patterns

**Custom Keybinding Navigation:**

- Prefix + letter for category (prefix+s for sessions)
- Single-key selection within category
- Choose-tree with vim navigation (j/k/h/l)
- FZF integration for fuzzy matching

**Sesh Features Worth Keeping:**

- Session list with context (window count, etc.)
- Zoxide integration for directory-based sessions
- Config-based default sessions
- Kill session from menu

**What We Can Build Better:**

- Lighter weight (no external tool)
- Integrated with our menu system
- Platform-specific default sessions
- Tmuxinator integration

---

## Requirements

### Core Functionality

**1. Curated Registry System**

- YAML-based command registry
- Rich metadata per entry:
  - name, command, description
  - category, keywords, tags
  - examples (multiple)
  - notes (extensive if needed)
  - use_tldr (boolean)
  - platform_specific (macos/linux/all)

**2. Function-Based Organization**

```
Categories:
- Git Operations
- File System Navigation
- Search & Replace
- Process Management
- Development Tools
- System Management
- Tmux & Sessions
- Notes & Documentation
```

**3. Search Capabilities**

- Search by keyword
- Search by description
- Filter by category
- Filter by platform

**4. Session Management**

- Replace sesh entirely
- Custom keybinding (prefix+m, then 's')
- List all sessions with context
- Tmuxinator project listing
- Default/saved sessions (platform-specific)
- Quick create, switch, kill

**5. Tmuxinator Integration**

- List tmuxinator projects
- Launch project (create or attach)
- Edit project config
- Create new project from template
- Show project preview (windows/panes)

### Documentation Strategy

**Single Source of Truth:**

- All commands/tools/functions documented in `~/.config/menu/registry.yml`
- For `.local/bin` scripts: metadata in registry, implementation in script
- For shell functions: metadata in registry, implementation in functions.sh
- For plugins: metadata in registry only (can't modify plugin code)

**Registry Structure:**

```yaml
commands:
  - name: rg
    type: system_tool
    description: Ripgrep - fast recursive grep
    keywords: [search, grep, find, text]
    category: Search & Replace
    use_tldr: true
    custom_examples:
      - "rg 'TODO' --type py"
      - "rg 'pattern' -g '*.md'"
    notes: |
      My go-to for code searching. Much faster than grep.
      Use with --type flag to filter by language.
    platform: all

  - name: ghd
    type: alias
    command: git diff HEAD
    description: Show diff of all staged changes
    keywords: [git, diff, staged, changes]
    category: Git Operations
    platform: all

  - name: fcd
    type: function
    description: Fuzzy find directory and cd into it
    keywords: [navigate, directory, find, cd, fzf]
    category: File System Navigation
    examples:
      - "fcd ~/code  # Search in specific directory"
      - "fcd  # Search from current directory"
    notes: |
      Uses fzf to preview directories.
      Respects .gitignore by default.
    platform: all

  - name: ga
    type: forgit_alias
    description: Interactive git add with preview
    keywords: [git, stage, add, interactive]
    category: Git Operations
    provided_by: forgit
    platform: all
```

### Keybinding System

**Menu Navigation:**

- `prefix + m` - Open menu (current: main menu)
- `s` - Jump to sessions (from main menu)
- `t` - Jump to tasks (from main menu)
- `g` - Jump to git operations (from main menu)
- Single letters for categories

**Within Category:**

- `j/k` or arrow keys for navigation
- `/` for search
- `Enter` to select
- `?` to show help/keybindings
- `b` or `Esc` to go back
- `q` to quit

### Platform-Specific Features

**Default Sessions Config:**

```yaml
# ~/.config/menu/sessions-macos.yml
default_sessions:
  - name: dotfiles
    directory: ~/dotfiles
    tmuxinator_project: null
    auto_start: false

  - name: ichrisbirch
    directory: ~/code/ichrisbirch
    tmuxinator_project: ichrisbirch-development
    auto_start: true

  - name: monitoring
    directory: ~/code/ichrisbirch
    tmuxinator_project: ichrisbirch-prod-monitoring
    auto_start: false
```

---

## Proposed Architecture

### File Structure

```
~/.config/menu/
├── registry.yml              # Main command registry
├── sessions-macos.yml        # macOS default sessions
├── sessions-wsl.yml          # WSL default sessions
├── categories.yml            # Category definitions & icons
└── keybindings.yml           # Custom keybinding config

~/dotfiles/
├── common/.local/bin/
│   ├── menu                  # Main menu script
│   ├── menu-registry         # Registry management CLI
│   └── menu-sessions         # Session manager (replaces sesh)
├── common/.config/menu/
│   ├── registry.yml
│   └── categories.yml
├── macos/.config/menu/
│   └── sessions-macos.yml
└── wsl/.config/menu/
    └── sessions-wsl.yml
```

### Component Design

**1. Registry Management (`menu-registry`)**

```bash
menu-registry add alias ghd "git diff HEAD" \
  --description "Show diff of staged changes" \
  --category "Git Operations" \
  --keywords "git,diff,staged"

menu-registry add function fcd \
  --description "Fuzzy find and cd" \
  --category "File System Navigation" \
  --example "fcd ~/code  # Search in directory"

menu-registry list --category "Git Operations"
menu-registry search "find directory"
menu-registry edit ghd
```

**2. Session Manager (`menu-sessions`)**

```bash
menu-sessions list              # All sessions (tmux + tmuxinator + defaults)
menu-sessions create dotfiles   # Create from default or new
menu-sessions switch main       # Switch to session
menu-sessions kill old-project  # Kill session
menu-sessions defaults          # List platform default sessions
```

**3. Main Menu (`menu`)**

- Context-aware categories
- Gum-based UI
- Keybinding navigation
- Search integration
- Preview with tldr/custom examples

### Integration Points

**Forgit Integration:**

1. Clone to `$ZSH_PLUGINS_DIR/forgit`
2. Source in zshrc after fzf
3. Add forgit commands to registry:
   - ga (git add)
   - glo (git log)
   - gd (git diff)
   - gcf (git checkout file)
   - gss (git stash show)
   - gclean (git clean)

**Tmuxinator Integration:**

1. Scan `~/.config/tmuxinator/*.yml`
2. Show in sessions menu
3. Actions:
   - Launch (create or attach)
   - Edit config
   - Preview (show windows/panes)
   - Create new from template

**Existing ls Functions:**

- Keep lsfunc, lsalias, lsterm, lstmux, lsaero
- Add menu listing to them: "Or type `menu` for full interface"

---

## Implementation Phases

### Phase 2A: Registry System ✓ (Immediate)

**Tasks:**

1. Create registry.yml schema
2. Build menu-registry CLI tool
3. Migrate 10-15 most-used commands to registry
4. Update menu to read from registry
5. Add search functionality

**Files:**

- `~/.config/menu/registry.yml`
- `~/.local/bin/menu-registry`
- Updated `~/.local/bin/menu`

### Phase 2B: Session Manager (Week 1)

**Tasks:**

1. Build menu-sessions tool
2. Create platform session configs
3. Remove sesh from tmux.conf
4. Update tmux keybindings (prefix+s)
5. Integrate tmuxinator project listing

**Files:**

- `~/.local/bin/menu-sessions`
- `~/.config/menu/sessions-macos.yml`
- `~/.config/menu/sessions-wsl.yml`
- Updated `tmux.conf`

### Phase 2C: Forgit Integration (Week 1)

**Tasks:**

1. Clone forgit to plugins directory
2. Source in zshrc
3. Add to install scripts (macos + wsl)
4. Add forgit commands to registry
5. Test git workflow

**Files:**

- `$ZSH_PLUGINS_DIR/forgit/`
- Updated `.zshrc`
- Updated `install/macos.sh`
- Updated `install/wsl.sh`

### Phase 2D: Enhanced UI (Week 2)

**Tasks:**

1. Keybinding system (category shortcuts)
2. Search within categories
3. Better previews (tldr integration)
4. Help screen (`?` keybinding)
5. Custom category icons

**Files:**

- `~/.config/menu/keybindings.yml`
- `~/.config/menu/categories.yml`
- Updated `menu`

### Phase 3: Future Enhancements

**Later additions:**

- Bookmarks (buku integration)
- Learning resources (own registry)
- Todo tracking (project todos)
- Colorscheme switcher (theme-sync integration)
- Alfred workflow (macOS launcher integration)

---

## Data Model

### Registry Entry Schema

```yaml
# Full example with all fields
commands:
  - name: string (required)
    type: enum [alias, function, system_tool, script, forgit_alias]
    command: string (for aliases/scripts)
    description: string (required)
    keywords: array[string] (required)
    category: string (required)
    platform: enum [all, macos, linux, wsl]
    use_tldr: boolean (default: false)
    examples: array[string]
    notes: string (multiline)
    related: array[string] (related command names)
    provided_by: string (e.g., "forgit", "fzf")
```

### Session Config Schema

```yaml
default_sessions:
  - name: string (required)
    directory: path (required)
    tmuxinator_project: string | null
    auto_start: boolean
    windows: array[string] (if not using tmuxinator)
```

### Category Schema

```yaml
categories:
  - name: string
    icon: string (emoji or nerd font icon)
    description: string
    keybinding: string (single letter)
    priority: int (sort order)
```

---

## Migration Strategy

### From Current Menu

1. Keep existing menu script as `menu-old` during transition
2. Build new menu alongside
3. Test with small registry (10-15 commands)
4. Gradually expand registry
5. Remove old menu when complete

### From Sesh

1. Document current sesh usage patterns
2. Build equivalent features in menu-sessions
3. Test session management thoroughly
4. Update tmux.conf keybindings
5. Remove sesh from dependencies

### Documentation Consolidation

1. Start with most-used commands (80/20 rule)
2. Add commands as you use them
3. When you forget something, add it to registry
4. Periodic review of registry completeness

---

## Success Criteria

### Phase 2A Complete When

- ✓ Registry with 15+ commands
- ✓ menu-registry CLI working
- ✓ Menu reads from registry
- ✓ Search by keyword/description works
- ✓ Category grouping visible

### Phase 2B Complete When

- ✓ Session list shows all sources (tmux + tmuxinator + defaults)
- ✓ Can create/switch/kill sessions
- ✓ Tmuxinator projects integrated
- ✓ Sesh removed entirely
- ✓ prefix+s navigation works

### Phase 2C Complete When

- ✓ Forgit cloned and sourced
- ✓ Forgit commands in registry
- ✓ Install scripts updated
- ✓ Git workflow tested

---

## Open Questions

1. **Registry format:** YAML vs TOML vs JSON?
   - Leaning YAML (more readable, supports multiline)

2. **How to handle command execution?**
   - Show preview, then action menu (run/copy/edit)
   - Or direct execution for some types?

3. **Fuzzy search library?**
   - fzf (already installed)
   - gum filter (consistent with UI)
   - Both?

4. **Registry editing workflow?**
   - CLI tool (menu-registry add/edit)
   - Direct file editing
   - Both?

5. **Versioning registry across platforms?**
   - Common registry + platform overlays
   - Separate files per platform
   - Both with merge strategy?

---

## References

- [forgit GitHub](https://github.com/wfxr/forgit)
- [tmuxinator GitHub](https://github.com/tmuxinator/tmuxinator)
- [kb - CLI Knowledge Base](https://github.com/gnebbia/kb)
- [sesh GitHub](https://github.com/joshmedeski/sesh)
- Current menu: `common/.local/bin/menu`
- Existing tools registry: `docs/tools/registry.yml`

---

## Next Steps

1. Review and approve this plan
2. Start Phase 2A: Registry system
3. Create initial registry with 15 commands
4. Build menu-registry CLI
5. Update menu to use registry
