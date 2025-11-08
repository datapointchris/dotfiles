# Universal Menu System - Planning Document

**Created:** 2025-11-06
**Status:** Brainstorming
**Goal:** Create a universal, cross-platform menu system to access tools, aliases, functions, bookmarks, and other resources

---

## Current State Assessment

### Existing Systems

**1. Tools Discovery System** (`~/.local/bin/tools`)
- YAML-based registry (`docs/tools/registry.yml`) with 31 tools
- CLI interface: list, show, search, random, categories
- Works well but limited to tool discovery
- Not dynamic enough - requires manual YAML updates

**2. fzf Functions** (`common/.shell/fzf-functions.sh`)
- File picker (`f`)
- Find-in-file (`fif`)
- Git branch checkout (`fco_preview`, `fcoc_preview`)
- Git commit browser (`fshow_preview`)
- Git stash manager (`fstash`)
- Git status picker (`fgst`)
- GitHub watch (`gh-watch`)
- Tmux session switcher (`tm`)
- Man page browser (`fzf-man-widget`, Ctrl-H)

**3. Shell Aliases** (`common/.shell/aliases.sh`)
- Directory navigation (dots, nconf, dl, dt)
- File operations (ls variants using eza)
- Git shortcuts (gst, commitall)
- Python operations (checkpython, makevenv)
- System operations (reload, reload-dns)

**4. Bookmarks**
- Currently trapped in Safari
- Not easily accessible from terminal
- Mostly ignored due to friction

### Platforms to Support

1. **macOS** (primary) - Using Aerospace window manager, Alfred (limited)
2. **WSL** (work) - Windows corporate environment, no admin access
3. **Arch Linux** (new setup) - Full control, can use dmenu/rofi
4. **Ubuntu Server** - Headless, terminal-only

### Pain Points

- Too many disparate systems to remember
- Tools script not dynamic enough (hardcoded YAML)
- No unified interface for:
  - Aliases and functions
  - Git helpers
  - fzf functions
  - Bookmarks
  - Custom scripts
- Alfred on macOS is cumbersome to configure
- No OS-level menu on macOS (like dmenu on Linux)

---

## Requirements & Goals

### Core Requirements

1. **Quick Access** - Summon from anywhere with a hotkey (OS-level preferred)
2. **Cross-Platform** - Work on macOS, Linux, WSL (graceful degradation acceptable)
3. **Dynamic** - Auto-discover resources without manual updates
4. **Unified** - One interface for all "lists of things"
5. **Low Maintenance** - Minimal time updating/managing definitions
6. **Ergonomic** - Fuzzy search, previews, easy to navigate

### Things to Manage

- CLI tools (existing: 31 in registry)
- Shell aliases (20+ in aliases.sh)
- Shell functions (10+ fzf functions)
- Git helpers (branch switcher, commit browser, stash)
- Task commands (from Taskfile)
- Custom scripts (symlinks, theme-sync, tools)
- Bookmarks (currently in Safari)
- Documentation links
- Tmux sessions
- Project directories

---

## Research Findings

### OS-Level Launchers

#### Linux Options

**dmenu/rofi**
- Standard for X11 window managers
- Fast, lightweight, keyboard-driven
- rofi: more features, themeable, supports Wayland (v2.0+)
- Cross-platform: Linux only
- Use case: Arch Linux setup

**Wayland Alternatives**
- fuzzel - Application launcher for wlroots-based Wayland compositors
- Walker (used by Omarchy) - Fast, themeable
- Cross-platform: Linux Wayland only

#### macOS Options

**Alfred** (what you're using)
- Powerful but cumbersome workflow GUI
- Not scriptable/version-controllable easily
- Proprietary, paid powerpack required

**Raycast**
- Modern, extensible with scripts
- Proprietary, freemium model
- Better API than Alfred

**Ueli** - OPEN SOURCE WINNER
- Cross-platform: macOS, Windows, Linux
- Electron-based
- Fuzzy search, customizable
- Plugin system
- **Major advantage:** Can work across all your platforms
- Potential downside: Electron (memory usage)

**Choose/Choose-gui**
- dmenu-like for macOS
- Limited features compared to full launchers

#### Cross-Platform Open Source

**Ueli** (mentioned above)
- Best cross-platform option
- https://ueli.app/
- Extensible with plugins
- Can be configured via JSON files (version-controllable!)

**Kunkun**
- New player, cross-platform
- Built with web technologies
- Less mature than Ueli

**RunFlow**
- Windows/macOS
- No Linux support

### TUI Frameworks

If you go the TUI route instead of OS-level launcher:

#### Python

**Textual**
- Modern, CSS-like styling
- Rich ecosystem
- Built on Rich library
- Cross-platform
- Good for complex UIs
- Example: https://github.com/Textualize/textual

**Urwid**
- Mature, stable
- More verbose than Textual
- Good widget library

#### Rust

**Ratatui**
- Fork of tui-rs (actively maintained)
- Excellent performance
- Granular control
- Steeper learning curve
- Cross-platform
- Example: lazygit uses this

#### Go

**Bubble Tea**
- Elm Architecture-inspired
- Good for simple to complex apps
- Active community
- Cross-platform
- Example: lazydocker uses this

**tview**
- Simpler than Bubble Tea
- Good widget library
- Cross-platform

### Data Storage Options

#### YAML Registry (current approach)

**Pros:**
- Human-readable
- Easy to edit manually
- Version-controllable
- Works with yq for querying

**Cons:**
- Requires manual updates
- Not truly dynamic
- Can become maintenance burden

#### SQLite Database

**Pros:**
- Fast queries
- Relational data
- Can have scripts auto-populate
- Full-text search
- No server needed

**Cons:**
- Less human-readable
- Requires tooling to inspect
- Migration complexity

#### Hybrid Approach

- YAML for static definitions (tools, documentation)
- Auto-discovery for dynamic things (aliases, functions, scripts)
- SQLite for bookmarks and history
- Combine at runtime

### fzf-menu Pattern

**Concept:** Use fzf as the menu system with wrapper scripts

**Pros:**
- You already use fzf extensively
- Extremely fast and familiar
- Cross-platform (works everywhere)
- Highly customizable
- Can be triggered from terminal or hotkey

**Cons:**
- Terminal-based only (not true "OS-level")
- Requires wrapper scripts for each menu
- Less discoverability than GUI

**Implementation:**
- Main launcher script that presents categories
- Each category opens a sub-menu with fzf
- Bind to tmux prefix + key or system hotkey

### Bookmark Management

#### CLI Bookmark Managers

**bm** (by mehdidc)
- SQLite backend
- Tag support
- Simple CLI
- https://github.com/mehdidc/bm

**bm** (by gozeloglu)
- TUI version with SQLite
- https://github.com/gozeloglu/bm

**Buku**
- Full-featured bookmark manager
- SQLite backend
- Browser integration
- Tags, full-text search
- Cross-platform
- https://github.com/jarun/buku

---

## Proposed Solutions

### Option 1: OS-Level Launcher (Ueli) - RECOMMENDED FOR MOST USE CASES

**Architecture:**
```
Ueli (macOS/Linux/WSL)
  ├── Custom plugins/config
  ├── Auto-generated lists from dotfiles
  │   ├── Parse aliases.sh → menu items
  │   ├── Parse fzf-functions.sh → menu items
  │   ├── Read Taskfile → menu items
  │   ├── Scan ~/.local/bin → menu items
  │   └── Import bookmarks → searchable
  └── Trigger shell functions/scripts
```

**Workflow:**
1. Install Ueli on macOS and Linux
2. Create generation scripts:
   - `generate-menu-from-aliases.sh` - Parse aliases.sh, create Ueli shortcuts
   - `generate-menu-from-functions.sh` - Parse function names, create launchers
   - `generate-menu-from-tasks.sh` - Parse Taskfile, create shortcuts
3. Run generators on shell reload (or via pre-commit hook)
4. Ueli config stored in dotfiles, symlinked
5. System-wide hotkey (e.g., Cmd+Shift+Space)

**Pros:**
- True OS-level access (works outside terminal)
- Cross-platform (macOS, Arch, maybe WSL)
- Config can be version-controlled
- One unified interface
- Modern, actively maintained
- Can replace Alfred

**Cons:**
- Electron-based (memory usage)
- Requires setup on each platform
- WSL support uncertain (might need X11 or different approach)
- More complex than pure fzf

**Platform Support:**
- macOS: ✓ Full support
- Arch Linux: ✓ Full support
- WSL: ? Needs testing (may require Windows host integration)
- Ubuntu Server: ✗ GUI required

**Tradeoffs:**
- Complexity: Medium-High (initial setup)
- Maintenance: Low (auto-generated from dotfiles)
- Portability: High (except headless servers)
- Consistency: High (same interface everywhere)

---

### Option 2: fzf-menu System - RECOMMENDED FOR TERMINAL USERS

**Architecture:**
```
~/.local/bin/menu (main launcher)
  ├── Presents categories via fzf
  ├── Each selection opens sub-menu
  │   ├── tools → fzf list of tools → show details
  │   ├── aliases → fzf list of aliases → execute
  │   ├── functions → fzf list of functions → execute
  │   ├── tasks → fzf list of tasks → run task
  │   ├── bookmarks → fzf list of URLs → open
  │   ├── docs → fzf list of docs → open
  │   └── tmux → fzf list of sessions → attach
  └── Auto-discovery from dotfiles
```

**Dynamic Discovery:**
```bash
# aliases: grep '^alias' ~/.shell/aliases.sh
# functions: grep '^[a-z_-]*()' ~/.shell/fzf-functions.sh
# tasks: yq '.tasks | keys' Taskfile.yml
# scripts: ls ~/.local/bin
# bookmarks: query SQLite (using buku or custom)
```

**Workflow:**
1. Press hotkey (tmux prefix + m, or system hotkey via terminal)
2. fzf presents categories
3. Select category → sub-menu with items
4. Select item → preview shows details
5. Press Enter → execute/open

**Pros:**
- Fast (pure bash + fzf)
- Works everywhere (including SSH/servers)
- Truly dynamic (parses files at runtime)
- Minimal dependencies (just fzf, yq)
- Easy to customize and extend
- You already know fzf well

**Cons:**
- Terminal-only (must be in terminal)
- Not true "OS-level" on macOS
- Requires hotkey per context (tmux vs system)
- Less polished than GUI launchers

**Platform Support:**
- macOS: ✓ Full support (terminal-based)
- Arch Linux: ✓ Full support
- WSL: ✓ Full support
- Ubuntu Server: ✓ Full support

**Tradeoffs:**
- Complexity: Low
- Maintenance: Very Low (auto-discovery)
- Portability: Perfect (works everywhere)
- Consistency: Perfect (identical on all platforms)

**Implementation Script Skeleton:**
```bash
#!/usr/bin/env bash
# ~/.local/bin/menu - Universal menu system

show_main_menu() {
  cat <<EOF | fzf --height=20 --header="Select Category"
tools       → CLI tools and utilities
aliases     → Shell aliases
functions   → Shell functions
tasks       → Taskfile tasks
scripts     → Custom scripts
bookmarks   → Saved URLs
docs        → Documentation
tmux        → Tmux sessions
git         → Git helpers
EOF
}

show_aliases() {
  # Parse aliases.sh and present with fzf
  grep "^alias " ~/.shell/aliases.sh | \
    sed "s/alias //" | \
    column -t -s '=' | \
    fzf --preview 'echo {}' | \
    # Execute selected alias...
}

# ... similar functions for each category
```

---

### Option 3: Custom TUI Application - ONLY IF YOU WANT A PROJECT

**Architecture:**
```
menu-tui (written in Rust/Ratatui or Python/Textual)
  ├── Main dashboard view
  ├── Category navigation (vim keys)
  ├── SQLite backend for bookmarks/history
  ├── Auto-discovery of dotfile resources
  └── Plugin system for extensibility
```

**Pros:**
- Full control over UI/UX
- Can be as complex as needed
- Great learning experience
- Could publish as open-source tool
- Can include features like:
  - Usage tracking
  - Frecency sorting
  - Inline previews
  - Multi-select operations

**Cons:**
- Significant development time (weeks/months)
- Maintenance burden (your project to maintain)
- Temptation to over-engineer
- Delays solving the actual problem
- Terminal-only

**Platform Support:**
- macOS: ✓ Full support
- Arch Linux: ✓ Full support
- WSL: ✓ Full support
- Ubuntu Server: ✓ Full support

**Tradeoffs:**
- Complexity: Very High
- Maintenance: High (ongoing development)
- Portability: High (if done right)
- Consistency: Perfect
- **Time to Value: Poor (don't do this unless you want the project itself)**

---

### Option 4: Hybrid Approach - MOST FLEXIBLE

**Architecture:**
```
Primary: fzf-menu for terminal use
Secondary: Ueli for OS-level (macOS/Arch)
Fallback: Pure fzf on servers/WSL

Shared: Auto-generation scripts in dotfiles
  ├── generate-menu-data.sh
  │   ├── Outputs JSON/YAML consumed by both
  │   ├── Parses aliases, functions, tasks
  │   └── Builds unified registry
  └── Run on shell reload or pre-commit
```

**Pros:**
- Best of both worlds
- OS-level access on personal machines
- Terminal access everywhere
- Graceful degradation
- Single source of truth (generation scripts)

**Cons:**
- Most complex setup
- Two systems to configure
- Potential for inconsistency

**Platform Strategy:**
- macOS: Ueli + fzf-menu (choose based on context)
- Arch: Ueli + fzf-menu
- WSL: fzf-menu only
- Server: fzf-menu only

**Tradeoffs:**
- Complexity: High (two systems)
- Maintenance: Medium (shared generators)
- Portability: Perfect (fallback everywhere)
- Consistency: Medium (two interfaces)

---

## Bookmark Management Deep Dive

### Recommended: Buku

**Why Buku:**
- SQLite backend (fast, reliable)
- Browser import (get bookmarks out of Safari)
- Tag system
- Full-text search
- Encryption support
- fzf integration already exists
- Active development
- Cross-platform

**Workflow:**
1. Import Safari bookmarks: `buku --ai`
2. Access via fzf: `buku --print | fzf | buku --open`
3. Add to menu system
4. Optionally sync across machines (git + encrypted DB)

**Integration with Menu:**
```bash
show_bookmarks() {
  buku --print --format 4 | \
    fzf --preview 'buku --print {1}' \
        --bind 'enter:execute(buku --open {1})' \
        --bind 'ctrl-e:execute(buku --update {1})'
}
```

---

## Implementation Recommendations

### Recommended Path: Option 2 (fzf-menu) First, Option 1 (Ueli) Later

**Why this order:**

1. **Quick Win:** fzf-menu can be built in a few hours
2. **Universal:** Works on all platforms immediately
3. **Learn:** Understand what you actually need before committing to GUI
4. **Iterate:** Easy to refine and add features
5. **Fallback:** Even if you add Ueli later, fzf-menu stays useful for servers

**Phase 1: fzf-menu MVP (1-2 days)**

```
Day 1:
- Create ~/.local/bin/menu script
- Implement main menu with categories
- Add tools integration (reuse existing tools script)
- Add aliases discovery and execution
- Add tasks integration

Day 2:
- Add functions discovery
- Add bookmark support (buku integration)
- Add documentation browser
- Create hotkey binding (tmux prefix + m)
- Test on all platforms
```

**Phase 2: Polish (1 week)**
- Add preview windows for each category
- Improve execution (handle different types)
- Add history tracking
- Create update hook (auto-run on changes)
- Write documentation

**Phase 3: Optional Ueli (Later)**
- Evaluate if you still need it
- If yes, reuse menu generation scripts
- Keep fzf-menu for SSH/server work

---

## Auto-Discovery Strategy

### Aliases

```bash
# Extract aliases from aliases.sh
parse_aliases() {
  grep "^alias " "$DOTFILES/common/.shell/aliases.sh" | \
    sed 's/alias //' | \
    awk -F'=' '{printf "%s~%s\n", $1, $2}'
}
```

### Functions

```bash
# Extract functions from fzf-functions.sh
parse_functions() {
  grep -E "^[a-z_-]+\(\)" "$DOTFILES/common/.shell/fzf-functions.sh" | \
    sed 's/().*$//' | \
    while read -r func; do
      # Get description from comments above function
      desc=$(grep -B5 "^$func()" "$DOTFILES/common/.shell/fzf-functions.sh" | \
             grep "^#" | tail -1 | sed 's/^# *//')
      echo "$func~$desc"
    done
}
```

### Tasks

```bash
# Extract tasks from Taskfile
parse_tasks() {
  task --list-all | tail -n +3 | \
    awk '{printf "%s~%s\n", $1, substr($0, index($0,$2))}'
}
```

### Scripts

```bash
# Extract scripts from .local/bin
parse_scripts() {
  find "$HOME/.local/bin" -type f -executable | \
    while read -r script; do
      name=$(basename "$script")
      # Try to get description from header comment
      desc=$(head -20 "$script" | grep -E "^#.*description" -i | sed 's/^#.*description:* *//i')
      echo "$name~${desc:-Custom script}"
    done
}
```

---

## Hotkey Strategy

### macOS (Aerospace + BetterTouchTool)

**Option A: Terminal Hotkey (Cmd+Shift+M)**
- BetterTouchTool triggers:
  1. Focus Ghostty
  2. Send keys: `menu\n`

**Option B: Tmux Binding (Prefix + m)**
- Add to tmux.conf:
  ```
  bind-key m run-shell "menu"
  ```

### Linux (i3/sway + rofi)

**Hybrid Approach:**
- Bind Super+Space to rofi (normal app launcher)
- Bind Super+M to terminal + menu script
- In i3 config:
  ```
  bindsym $mod+m exec alacritty -e menu
  ```

### WSL

**Limited Options:**
- Terminal keybinding only
- Or Windows host integration (complex)
- Tmux binding most practical

---

## Data Storage Recommendation

### Hybrid Model (Best of Both Worlds)

**Static Registry (YAML):**
- Tool definitions (tools/registry.yml - already exists)
- Documentation links
- Rarely-changing reference data
- Version-controlled, easy to edit

**Dynamic Discovery (Runtime Parsing):**
- Aliases (parse from aliases.sh)
- Functions (parse from fzf-functions.sh)
- Tasks (query from Taskfile)
- Scripts (scan .local/bin)
- Tmux sessions (tmux list-sessions)

**SQLite (Bookmarks + History):**
- Bookmarks (via buku)
- Menu usage history (optional)
- Frecency tracking (optional)

**Why Hybrid:**
- Static data stays version-controlled and editable
- Dynamic data never gets out of sync
- Database only for data that truly benefits (bookmarks, history)
- No maintenance burden for things that auto-discover

---

## Platform-Specific Considerations

### macOS Specific

**Pros:**
- BetterTouchTool already configured
- Aerospace for window management
- Can use Ueli if desired

**Cons:**
- No native dmenu equivalent
- Alfred is your current solution (lacking)

**Recommendation:**
- Start with fzf-menu + terminal hotkey
- Consider Ueli later if you want GUI

### WSL Specific

**Constraints:**
- No admin access
- Windows host, Linux guest
- Limited system-level integration

**Recommendation:**
- fzf-menu only
- Tmux prefix binding
- Keep it terminal-based
- Possibly integrate with Windows Terminal hotkeys

### Arch Linux Specific

**Pros:**
- Full control
- Can use dmenu/rofi
- Native Linux environment

**Cons:**
- New setup, still configuring

**Recommendation:**
- fzf-menu for terminal
- rofi for GUI launcher (traditional apps)
- Could add Ueli later for unified experience

### Ubuntu Server Specific

**Constraints:**
- Headless
- SSH access only
- No GUI

**Recommendation:**
- fzf-menu only
- Tmux prefix binding
- Perfect use case for terminal-only solution

---

## Migration Path

### From Safari to Buku

```bash
# 1. Install buku
brew install buku

# 2. Export Safari bookmarks (File → Export Bookmarks)
# Saves as Bookmarks.html

# 3. Import to buku
buku --ai /path/to/Bookmarks.html

# 4. Verify
buku --print

# 5. Integrate with menu
# Add bookmarks category to menu script
```

### From Alfred to Ueli (Optional Future)

```bash
# 1. Install Ueli
brew install --cask ueli

# 2. Export Alfred workflows (if needed)
# Most will need recreation

# 3. Configure Ueli with JSON
# Store config in dotfiles

# 4. Test both in parallel

# 5. Switch when comfortable
```

---

---

## Updated Architecture: Layered Approach
