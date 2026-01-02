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
- <https://ueli.app/>
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
- Example: <https://github.com/Textualize/textual>

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
- <https://github.com/mehdidc/bm>

**bm** (by gozeloglu)

- TUI version with SQLite
- <https://github.com/gozeloglu/bm>

**Buku**

- Full-featured bookmark manager
- SQLite backend
- Browser integration
- Tags, full-text search
- Cross-platform
- <https://github.com/jarun/buku>

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

Based on additional context, the system should be thought of in distinct layers:

### Layer 0: Raw Layer (Direct Usage)

**Philosophy:** Prefer direct command-line usage when you remember the tool exists.

- CLI tools: `bat`, `eza`, `fd`, `rg`, etc.
- Shell functions: `fif`, `tm`, `fco_preview`, etc.
- Aliases: `gst`, `dots`, `reload`, etc.
- Scripts: `symlinks`, `theme-sync`, `tools`, etc.

**Goal:** No friction—just type the command. This layer should always be available.

### Layer 1: Discovery & Organization Layer (Terminal Interface)

**Philosophy:** Help you remember what exists when you forget.

**Purpose:**

- **Discovery:** "What tools/functions do I have for X?"
- **Preview:** Show examples (like tldr)
- **Quick Reference:** Search/filter/preview without leaving terminal

**Features:**

- List tools with descriptions
- Show alias definitions
- Display function usage examples
- Preview task descriptions
- Search across all resources

**Tools at this layer:**

- fzf (for search/filter)
- yazi (for file/bookmark browsing)
- buku (for bookmark storage)
- gum (for interactive menus)

**This is the core layer—the universal interface that works everywhere.**

### Layer 2: Data Organization Layer (Same Level as Discovery)

**Philosophy:** Organize things beyond just code tools.

**Data Types:**

- **Bookmarks:** Web URLs (using buku)
- **Learning Resources:** PDFs, videos, courses
- **Todo Lists:** Project tasks, personal todos
- **Learning Plans:** Long-term learning goals
- **Project List:** Active and archived projects

**Key Insight:** These need **editing/organizing** capabilities, not just viewing. You'll interact with these frequently to maintain them.

**Storage Considerations:**

- **Bookmarks:** Buku SQLite database
- **Learning Resources:** Filesystem + metadata (buku-like or custom)
- **Lists:** Plain text files (markdown) or SQLite
- **Interface:** TUI for editing (yazi plugins, custom tool, or text editor)

### Layer 3: Frontend Layer (Platform-Specific Launchers)

**Philosophy:** System-level hotkey to quickly access the terminal interface.

**macOS:**

- Alfred workflow to launch Ghostty with menu
- Or: Aerospace hotkey → Ghostty with menu
- Alfred handles macOS system stuff (apps, settings, etc.)
- Terminal interface handles dev tools, bookmarks, lists

**Arch Linux:**

- System hotkey → Terminal with menu
- Possibly rofi for GUI app launching
- dmenu as alternative

**WSL:**

- Terminal-only (no system-level hotkey likely)
- Tmux prefix binding
- Windows Terminal hotkey (maybe)

**Ubuntu Server:**

- Terminal-only
- Tmux prefix binding

**Key Insight:** Layer 3 varies by platform, but always launches the same Layer 1 interface (universal terminal menu).

---

## Alfred Integration (New Research)

Since you have a lifetime PowerPack license, **keep Alfred for macOS system management** and integrate it with your terminal workflow.

### Alfred + Ghostty Integration

**Available Solutions:**

1. **alfred-ghostty-script** (zeitlings) - Full-featured
   - Supports tabs, windows, splits, quick terminal
   - AppleScript: <https://github.com/zeitlings/alfred-ghostty-script>

2. **alfred-ghostty-applescript** (gowizzard) - Simpler
   - Opens command in existing window or creates new
   - <https://github.com/gowizzard/alfred-ghostty-applescript>

3. **Ghostty 1.2.0+ Apple Shortcuts**
   - Native macOS Shortcuts integration
   - Can trigger from Alfred via Run Script → shortcuts

**Setup Steps:**

1. Copy AppleScript to Alfred Preferences → Features → Terminal/Shell → Custom
2. Wrap in `alfred_script(q)` ... `end alfred_script`
3. Test with Alfred's built-in terminal command feature

### Alfred Workflow Strategy

**What Alfred Should Handle:**

- macOS app launching (what it's best at)
- System preferences and settings
- macOS-specific actions
- General web searches

**What Terminal Interface Should Handle:**

- Dev tools and CLI utilities
- Bookmarks and learning resources
- Project navigation
- Code-related tasks

**Bridge Between Them:**

Create Alfred workflows that launch your terminal menu with specific contexts:

```
Keyword: menu → Launch Ghostty with `menu`
Keyword: bk → Launch Ghostty with `menu` → bookmarks
Keyword: tools → Launch Ghostty with `menu` → tools
Keyword: tasks → Launch Ghostty with `menu` → tasks
```

**Implementation:**

```applescript
-- Alfred workflow to launch terminal menu
on alfred_script(q)
  tell application "Ghostty"
    activate
    tell application "System Events"
      keystroke "menu" & return
    end tell
  end tell
end alfred_script
```

This gives you **best of both worlds:**

- Alfred for macOS (keeps your investment)
- Terminal interface for dev workflow (universal)
- Hotkeys for both contexts

---

## Ghostty Optimization for Quick Launch

### The Problem

Loading full zsh config slows down Ghostty launch when used as a menu launcher.

### Solutions

**Option 1: Minimal zsh for Menu**

Create `~/.zshrc-minimal`:

```bash
# Minimal zsh config for quick menu launch
# No oh-my-zsh, no heavy plugins

# Essential PATH only
export PATH="$HOME/.local/bin:$PATH"

# Load menu immediately
if [[ -n "$MENU_MODE" ]]; then
  menu
  exit
fi
```

Launch with: `ZDOTDIR=~/.config/zsh-minimal ghostty`

**Option 2: Direct Execution (Fastest)**

Launch Ghostty directly running the menu script:

```bash
# Alfred or hotkey launches:
ghostty -e menu

# Or with bash (no zsh overhead):
ghostty -e bash -c menu
```

**Option 3: Separate "Menu Terminal"**

Use a lightweight terminal just for menus:

- kitty (very fast startup)
- alacritty (also fast)
- st (minimal, if you build from source)

Keep Ghostty for regular terminal work.

**Recommendation:** Option 2 (direct execution) is simplest and fastest.

---

## Gum: Quick Menu Building

**What is Gum?**

- Part of Charm CLI suite (Bubble Tea ecosystem)
- Creates beautiful interactive menus with minimal code
- Single binary, no framework needed
- Perfect for quick menu scripts

**Basic Example:**

```bash
#!/usr/bin/env bash
# Quick menu with gum

CATEGORY=$(gum choose \
  "Tools" \
  "Aliases" \
  "Functions" \
  "Bookmarks" \
  "Tasks")

case "$CATEGORY" in
  "Tools")
    tools list | gum filter
    ;;
  "Aliases")
    grep "^alias" ~/.shell/aliases.sh | gum filter
    ;;
  # ... etc
esac
```

**Advantages:**

- Beautiful by default (colors, formatting)
- Very fast
- Easy to compose with pipes
- Multi-select support
- Input fields, confirm dialogs, spinners

**Disadvantages:**

- Less powerful than full fzf
- Another dependency
- Not as widely known

**When to Use:**

- Quick prototyping
- Simple menus
- When aesthetics matter
- Scripts for others to use

**When to Use fzf Instead:**

- Complex preview windows
- Advanced filtering
- You're already familiar with it
- Need maximum performance

**Recommendation:** Try gum for the main menu (categories), use fzf for sub-menus with previews. Best of both worlds.

---

## Yazi Extensions for Bookmarks

**Good News:** Yazi has bookmark management plugins!

### Available Plugins

**whoosh.yazi** - Most Feature-Rich

- Persistent bookmarks (survive restarts)
- Temporary session bookmarks
- Directory history
- Fuzzy search via fzf integration
- Multi-select deletion
- Smart path truncation
- Install: `ya pkg add WhoSowSee/whoosh`

**yamb.yazi** - Simpler Alternative

- Persistent bookmarks
- Jump by key or fzf
- Basic but solid
- Install: `ya pkg add h-hg/yamb`

### Integration Strategy

**Use Yazi for Directory Bookmarks:**

- Quick jumping to frequently-used directories
- Visual file browsing when you get there
- Complements zoxide nicely

**Use Buku for URL Bookmarks:**

- Web URLs
- Documentation links
- Online resources

**Potential Yazi Use Cases:**

- Browse local markdown notes
- Navigate project directories
- View learning resource files (PDFs, videos)
- File-based bookmark organization

**Add to Your Menu:**

```bash
# In main menu
"bookmarks-dirs" → Launch yazi with whoosh plugin
"bookmarks-urls" → Launch buku fzf interface
"learning" → yazi in ~/learning-resources directory
```

---

## Buku Limitations & Alternatives

### Buku + file:// URLs

**Important Limitation:** Buku **ignores file:// URLs** during import.

This means buku is **not suitable** for managing local files (PDFs, videos, etc.) directly.

### Solutions for Learning Resources

**Option 1: Filesystem + Yazi**

Organize learning resources in directories:

```
~/learning/
  ├── courses/
  │   ├── rust-book/
  │   └── kubernetes-course/
  ├── books/
  │   ├── designing-data-intensive-apps.pdf
  │   └── rust-programming.pdf
  ├── videos/
  └── articles/
```

Use yazi to browse, open with appropriate apps.
Add metadata files (markdown) for descriptions.

**Option 2: Custom SQLite Database**

Similar to buku but for local resources:

```sql
CREATE TABLE resources (
  id INTEGER PRIMARY KEY,
  path TEXT NOT NULL,
  title TEXT,
  description TEXT,
  tags TEXT,
  resource_type TEXT, -- pdf, video, course, article
  added_date TEXT,
  last_accessed TEXT
);
```

Build simple CLI tool (Python script) to add/search/open.

**Option 3: Hybrid Buku Approach**

Use buku's tagging/search but store file paths as "URLs":

```bash
# Add with file path as "URL"
buku -a "/Users/chris/learning/rust-book.pdf" --title "Rust Book" --tags rust,programming

# Search and open
buku -s rust | fzf --preview 'cat {}' | awk '{print $2}' | xargs open
```

This works but is a hack (buku treats paths as malformed URLs).

**Recommendation:** **Option 1 (Filesystem + Yazi)** is simplest and most maintainable.

- Organize files in logical directories
- Use yazi for browsing/navigation
- Add `learning-resources.md` index file for searching
- Use ripgrep to search across markdown indexes
- Add to your menu as a category

**For URL bookmarks:** Use buku normally (it excels at this).

---

## TUI Consideration: When It Makes Sense

### The Question

If your hotkey launches a terminal that runs the menu, is a richer TUI worth it for complex tasks (editing bookmarks, managing learning plans)?

### Arguments FOR a TUI

**Good for:**

- Complex data editing (bookmarks with tags, descriptions)
- Viewing structured data (tables, lists)
- Multi-step workflows (add → tag → categorize)
- Visual organization

**Tools:**

- Textual (Python) - CSS-like styling, modern
- Bubble Tea (Go) - Well-established, many examples
- Ratatui (Rust) - Performance, if you know Rust

**Estimated Effort:**

- Basic TUI: 2-3 days
- Polished TUI: 1-2 weeks
- Feature-complete: 1+ month

### Arguments AGAINST a TUI

**Cons:**

- Development time (delays solving the actual problem)
- Maintenance burden (another project to maintain)
- Complexity (harder to debug than shell scripts)
- Overkill for simple tasks (most menu operations are simple)

**Simpler Alternatives:**

- **Gum + fzf:** Gets you 80% there with 10% effort
- **Yazi:** Already a polished TUI for file/directory work
- **Buku TUI:** Use bukubrow or buku-fzf scripts
- **Text editor:** Edit markdown lists in nvim (you're already proficient)

### Middle Ground: Scripted Interfaces

**Instead of building a TUI, compose existing tools:**

```bash
# Bookmark editor using gum
edit-bookmark() {
  local id=$(buku -p | fzf | awk '{print $1}')
  [[ -z "$id" ]] && return

  local title=$(gum input --placeholder "Title")
  local url=$(gum input --placeholder "URL")
  local tags=$(gum input --placeholder "Tags (comma-separated)")
  local desc=$(gum write --placeholder "Description")

  buku -u "$id" --title "$title" --tags "$tags" --comment "$desc"
}
```

This gives you TUI-like interaction without building a TUI framework.

### Recommendation

**Don't build a custom TUI (yet).**

1. Start with gum + fzf menus
2. Use yazi for file-based browsing
3. Use buku's built-in interface or fzf scripts for bookmarks
4. Edit lists in nvim (you're already fast at this)

**Re-evaluate in 1-2 months:**

- If you find yourself constantly fighting the tools
- If a specific workflow is painful
- If you want a coding project for learning

**If you do build a TUI later:**

- Use Textual (Python) - fastest development
- Focus on ONE use case (e.g., bookmark manager)
- Keep it simple and focused

---

## Revised Recommendations

### Core Architecture: Layered System

**Layer 0 (Raw):** Direct CLI usage (always available)

**Layer 1 (Discovery):** Terminal interface (universal)

- Main menu (gum + fzf)
- Auto-discovery of tools/aliases/functions/tasks
- Search and preview
- Quick reference

**Layer 2 (Data):** Organized resources (same as Layer 1)

- Bookmarks (buku for URLs)
- Learning resources (filesystem + yazi)
- Lists (markdown files + ripgrep)

**Layer 3 (Frontend):** Platform-specific launchers

- macOS: Alfred + Ghostty
- Arch: dmenu/rofi + terminal
- WSL: Terminal only
- Server: Terminal only

### Implementation Strategy

**Phase 1: Terminal Interface (Priority 1)**

Build the universal Layer 1 menu:

```bash
~/.local/bin/menu
  ├── Main menu (gum choose)
  ├── Tools category (reuse tools script)
  ├── Aliases category (parse + fzf)
  ├── Functions category (parse + fzf)
  ├── Tasks category (yq + fzf)
  ├── Bookmarks category (buku + fzf)
  └── Learning category (yazi ~/learning)
```

**Tech Stack:**

- Gum for main menu (beautiful, simple)
- fzf for sub-menus with preview (powerful, familiar)
- Existing tools: buku, yazi, yq

**Time Estimate:** 2-3 days

**Phase 2: Data Migration (Priority 2)**

Organize your data:

1. **Install buku:** `brew install buku`
2. **Import Safari bookmarks:** `buku --ai ~/Downloads/Bookmarks.html`
3. **Create learning directory structure:**

   ```bash
   mkdir -p ~/learning/{courses,books,videos,articles}
   ```

4. **Create index:** `~/learning/INDEX.md` with descriptions
5. **Install yazi bookmarks plugin:** `ya pkg add WhoSowSee/whoosh`

**Time Estimate:** 1 day

**Phase 3: Frontend Integration (Priority 3)**

Platform-specific launchers:

**macOS:**

1. Install Ghostty AppleScript for Alfred
2. Create Alfred workflow: keyword "menu" → Ghostty + menu
3. Optional: BetterTouchTool hotkey Cmd+Shift+M → same thing
4. Keep Alfred for macOS system stuff

**Arch:**

1. Add i3/sway keybinding: Super+M → terminal -e menu
2. Keep rofi for GUI app launching

**WSL:**

1. Tmux binding: prefix + m → run menu
2. Optionally: Windows Terminal keyboard shortcut

**Time Estimate:** 1 day per platform

### Tool Choices

| Purpose | Tool | Why |
|---------|------|-----|
| Main menu | gum | Beautiful, simple, fast |
| Sub-menus | fzf | Powerful, preview, familiar |
| URL bookmarks | buku | SQLite, tagging, mature |
| File browsing | yazi | Fast, plugins, beautiful |
| Directory bookmarks | yazi + whoosh | Plugin already exists |
| Learning resources | Filesystem + yazi | Simple, no special tool needed |
| Lists/notes | Markdown + nvim | Already proficient |
| Tasks | Taskfile + yq | Already in use |

### Platform Strategy

**macOS:**

- Alfred for system (keep your investment)
- Terminal interface for dev work
- Best of both worlds

**Arch:**

- Full control
- Can use dmenu/rofi for GUI
- Terminal interface for everything else

**WSL:**

- Terminal-only (constraints of corporate environment)
- Tmux as primary interface
- Keep it simple

**Server:**

- Terminal-only
- Tmux bindings
- Same interface as everywhere else

### Data Storage

**YAML (Static):**

- Tool registry (docs/tools/registry.yml)
- Documentation links
- Rarely changing data

**SQLite (Bookmarks):**

- Buku database for URLs
- Mature, proven solution

**Filesystem (Learning):**

- Organized directories
- Markdown indexes
- Use yazi for browsing

**Runtime Parsing (Dynamic):**

- Aliases (parse aliases.sh)
- Functions (parse fzf-functions.sh)
- Tasks (query Taskfile)
- Scripts (scan .local/bin)

**Markdown (Lists):**

- Todo lists
- Project lists
- Learning plans
- Edit in nvim, search with ripgrep

---

## Implementation Roadmap

### Week 1: Core Menu System

**Day 1-2: Build Main Menu**

- Install gum: `brew install gum`
- Create `~/.local/bin/menu` script
- Implement main category selection (gum choose)
- Add tools integration (reuse existing)

**Day 3: Dynamic Discovery**

- Parse aliases.sh → fzf menu
- Parse fzf-functions.sh → fzf menu
- Parse Taskfile → fzf menu
- Add preview windows

**Day 4: Bookmark Integration**

- Install buku
- Import Safari bookmarks
- Create buku + fzf interface
- Add to menu

**Day 5: Learning Resources**

- Create ~/learning directory structure
- Move existing learning materials
- Create INDEX.md
- Add yazi integration to menu

### Week 2: Frontend & Polish

**Day 1: macOS Alfred Integration**

- Install Ghostty AppleScript
- Create Alfred workflows
- Test integration
- Optional: BetterTouchTool hotkey

**Day 2: Cross-Platform Testing**

- Test on macOS
- If available: Test on Arch
- Document any platform quirks

**Day 3-4: Polish & Documentation**

- Add help text to menu
- Create keyboard shortcut reference
- Write docs/menu-system.md
- Add to CLAUDE.md

**Day 5: Refinement**

- User testing (you using it)
- Fix issues
- Optimize performance
- Add missing features

### Week 3+: Iterate

- Use the system daily
- Note pain points
- Refine interfaces
- Add features as needed

---

## Next Steps (Updated)

### Immediate Actions (This Week)

1. **Install dependencies:**

   ```bash
   brew install gum buku
   ya pkg add WhoSowSee/whoosh  # yazi bookmarks
   ```

2. **Data migration:**
   - Export Safari bookmarks
   - Import to buku
   - Create learning directory structure

3. **Prototype main menu:**
   - Create ~/.local/bin/menu script
   - Test gum choose interface
   - Wire up existing tools

### Short Term (2 Weeks)

1. **Build complete Layer 1 interface**
   - All categories implemented
   - Preview windows working
   - Search/filter functional

2. **Configure Layer 3 (Frontend)**
   - Alfred integration on macOS
   - Hotkey configuration
   - Tmux bindings

3. **Migrate data**
   - All bookmarks in buku
   - Learning resources organized
   - Lists in markdown

### Long Term (1+ Month)

1. **Daily usage & refinement**
   - Use exclusively for 2-4 weeks
   - Identify pain points
   - Iterate on design

2. **Cross-platform deployment**
   - Deploy to Arch when ready
   - Test on WSL
   - Ensure consistency

3. **Optional enhancements**
   - History tracking
   - Frecency sorting
   - Custom categories
   - TUI (only if needed)

---

## Open Questions (Updated)

1. **Menu tool preference: gum or fzf for main menu?**
   - Recommendation: gum (prettier, simpler) for main, fzf for sub-menus

2. **Ghostty launch optimization: minimal zsh or direct execution?**
   - Recommendation: Direct execution (`ghostty -e menu`) is fastest

3. **Learning resources: filesystem or database?**
   - Recommendation: Filesystem + yazi (simpler, visual)

4. **Alfred: deep integration or just launcher?**
   - Recommendation: Just launcher (keep it simple)

---

## Resources

### Tools

- fzf: <https://github.com/junegunn/fzf>
- buku: <https://github.com/jarun/buku>
- Ueli: <https://ueli.app/>
- Textual: <https://textual.textualize.io/>
- Ratatui: <https://ratatui.rs/>

### Inspiration

- Omarchy: <https://github.com/basecamp/omarchy>
- fzf examples: <https://github.com/junegunn/fzf/wiki/examples>
- Awesome TUIs: <https://github.com/rothgar/awesome-tuis>

### Dotfiles Examples

- Look for other dotfiles with menu systems:
  - <https://github.com/search?q=fzf+menu+dotfiles>

---

## Final Recommendations Summary

### The Layered Architecture (Refined)

Your mental model is excellent. Here's the refined architecture:

```
Layer 3 (Frontend - Platform Specific)
  macOS: Alfred keyword → Ghostty -e menu
  Arch:  Super+M → terminal -e menu
  WSL:   tmux prefix+m → menu
         ↓
Layer 1 (Universal Terminal Interface)
  Main Menu (gum choose) → Categories
    ├── Tools (existing tools script)
    ├── Aliases (auto-parsed)
    ├── Functions (auto-parsed)
    ├── Tasks (yq query)
    ├── Bookmarks (buku + fzf)
    ├── Learning (yazi ~/learning)
    └── Scripts (ls .local/bin + fzf)
         ↓
Layer 2 (Data Organization - Same Level)
  Bookmarks: buku SQLite (URLs only)
  Learning: ~/learning/... (filesystem + yazi)
  Lists: ~/lists/*.md (markdown + ripgrep)
         ↓
Layer 0 (Raw - Always Available)
  Direct command usage: bat, eza, fd, rg, gst, etc.
```

### Core Decision: Gum + fzf + Existing Tools

**Build this:**

- Main menu with gum (beautiful categories)
- Sub-menus with fzf (powerful previews)
- Buku for URL bookmarks
- Yazi + filesystem for learning resources
- Markdown for lists/todos/plans

**Don't build this:**

- Custom TUI (not worth the time)
- SQLite for everything (filesystem is simpler)
- Complex integration (keep Alfred simple)

### Platform Strategy (Updated)

**macOS - Best of Both Worlds:**

- **Alfred** handles: macOS apps, system settings, web search
- **Terminal menu** handles: dev tools, bookmarks, learning resources
- **Bridge:** Alfred keyword "menu" → launches Ghostty with menu
- **Keep your investment:** Alfred PowerPack still useful

**Arch - Full Power:**

- System hotkey launches menu
- Optionally: rofi for GUI apps
- Full control, unlimited options

**WSL - Terminal First:**

- Tmux prefix binding (most practical)
- No complex Windows integration needed
- Same interface as everywhere else

**Server - Same Interface:**

- Tmux binding
- Universal terminal menu works perfectly

### Technology Choices (Final)

| Component | Tool | Why | Alternative |
|-----------|------|-----|-------------|
| Main menu | **gum** | Beautiful, simple | fzf works too |
| Sub-menus | **fzf** | Powerful, previews | gum filter |
| URL bookmarks | **buku** | Mature, SQLite, tagging | Browser (current pain point) |
| Dir bookmarks | **yazi + whoosh** | Plugin exists, visual | zoxide (current) |
| Learning files | **Filesystem + yazi** | Simple, visual | Custom database (overkill) |
| Lists/plans | **Markdown + nvim** | You're already fast | SQLite (overcomplicated) |
| Frontend (macOS) | **Alfred → Ghostty** | Use what you have | New tool (unnecessary) |
| Quick launch | **`ghostty -e menu`** | Direct, fast | Full zsh (slower) |

### Implementation Timeline (Realistic)

**Week 1 - Core Menu (6-8 hours total):**

- Day 1-2: Install deps, build main menu, integrate tools
- Day 3: Parse aliases/functions, add tasks
- Day 4: Buku setup, Safari import, fzf interface
- Day 5: Learning directory, yazi integration

**Week 2 - Polish & Deploy (4-6 hours total):**

- Day 1: Alfred workflow setup
- Day 2: Cross-platform testing
- Day 3-4: Documentation, help text
- Day 5: Refinement based on usage

**Week 3+ - Iterate:**

- Use daily, note friction points
- Refine based on actual usage
- Deploy to other platforms when ready

### Key Insights from Research

1. **Alfred Integration:** Keep it, don't replace it. GitHub has AppleScript solutions for Ghostty integration.

2. **Ghostty Launch:** Use `ghostty -e menu` for fast startup, skip full zsh load.

3. **Gum is Perfect for This:** Charm's gum tool is made for exactly this use case—quick, beautiful menus.

4. **Buku's Limitation:** Ignores file:// URLs, so use filesystem for local learning resources.

5. **Yazi Plugins:** whoosh.yazi provides directory bookmarks, yamb.yazi is simpler alternative.

6. **Don't Build TUI:** Gum + fzf + existing tools gives you 90% of TUI benefits with 10% of the work.

7. **Layer 3 Flexibility:** Frontend varies by platform, but Layer 1 (terminal interface) is universal and identical everywhere.

### What Makes This Solution Good

**Addresses All Your Pain Points:**

- Unified interface for disparate systems ✓
- Dynamic discovery (no manual YAML updates) ✓
- Cross-platform (works everywhere) ✓
- Low maintenance (auto-parsing) ✓
- Keeps Alfred investment ✓
- Terminal-first (your preference) ✓

**Pragmatic:**

- Uses existing tools (minimal new dependencies)
- Fast to build (2-3 days, not weeks)
- Low maintenance (no custom framework to maintain)
- Flexible (easy to extend later)

**Future-Proof:**

- Can add TUI later if truly needed
- Can swap tools (gum → fzf or vice versa)
- Can add features incrementally
- Architecture supports growth

### Critical Success Factors

1. **Start Simple:** Don't over-engineer. Get the core menu working first.

2. **Use What You Have:** Leverage existing tools script, fzf functions, Alfred.

3. **Filesystem First:** Don't prematurely optimize with databases. Files + yazi works.

4. **Test Cross-Platform Early:** Make sure it works on macOS and WSL from day 1.

5. **Daily Usage:** Force yourself to use it exclusively for 2 weeks. You'll find the pain points.

6. **Iterate:** Don't try to build everything at once. Add categories as you need them.

### Potential Pitfalls to Avoid

**Don't:**

- Build a custom TUI (yet)
- Try to make Alfred do everything
- Create databases for things that don't need them
- Spend weeks perfecting before using
- Ignore Layer 0 (keep direct usage as priority)

**Do:**

- Start with gum + fzf
- Keep Alfred for macOS stuff
- Use filesystem + yazi for local files
- Ship and iterate quickly
- Maintain preference for direct command usage

---

## Conclusion (Updated)

Based on your additional context about the layered architecture, **here's the clear path forward:**

### Build This (In Order)

1. **Core terminal menu** (gum + fzf, 2-3 days)
   - Universal interface that works everywhere
   - Auto-discovery of tools/aliases/functions
   - Buku for URL bookmarks
   - Yazi for learning resources

2. **macOS frontend** (Alfred workflow, 1 day)
   - Keep Alfred for system stuff
   - Add workflow to launch menu
   - Best of both worlds

3. **Cross-platform deployment** (1 day per platform)
   - Same menu everywhere
   - Platform-specific launchers
   - Graceful degradation (WSL is terminal-only, that's fine)

### Your Insight is Correct

The **layered architecture** is the right mental model:

- **Layer 0:** Direct usage (always prefer this)
- **Layer 1:** Discovery when you forget (universal terminal menu)
- **Layer 2:** Data organization (bookmarks, learning, lists)
- **Layer 3:** Frontend launchers (platform-specific)

This gives you:

- **Universal interface** (terminal menu works everywhere)
- **Platform flexibility** (different frontends per OS)
- **Keeps Alfred** (you already paid for it)
- **Simple & maintainable** (no custom frameworks)
- **Fast to build** (2-3 days, not months)

The key insight from all this research: **You don't need to build much.** Compose gum + fzf + buku + yazi + your existing tools. That's the whole system. Everything else is just wiring it together with shell scripts.

---

## Next Action Items

Ready to start? Here's your first steps:

```bash
# 1. Install dependencies
brew install gum buku

# 2. Export Safari bookmarks
# Safari → File → Export Bookmarks → ~/Downloads/Bookmarks.html

# 3. Import to buku
buku --ai ~/Downloads/Bookmarks.html

# 4. Create learning directory
mkdir -p ~/learning/{courses,books,videos,articles}

# 5. Create menu script skeleton
touch ~/.local/bin/menu
chmod +x ~/.local/bin/menu

# 6. Test gum
gum choose "Tools" "Aliases" "Functions" "Bookmarks" "Tasks"
```

Once those basics work, you're ready to build the full menu. The planning doc has everything you need. Good luck!
