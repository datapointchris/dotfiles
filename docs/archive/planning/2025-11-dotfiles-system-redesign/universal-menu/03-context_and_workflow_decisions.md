# Universal Menu System - Context & Workflow Decisions

**Created:** 2025-11-06
**Previous:** 02-architecture_refinement.md
**Status:** Refining implementation approach

---

## Decisions Made from Previous Research

Based on 01 and 02, we've decided on:

1. **Technology Stack:**
   - **gum** for main menu (beautiful, simple categories)
   - **fzf** for sub-menus (powerful previews)
   - **buku** for URL bookmarks (test run)
   - **Filesystem + yazi** for learning resources (deferred for now)

2. **Architecture:**
   - Layer 0: Direct CLI usage (always preferred)
   - Layer 1: Universal terminal menu (works everywhere)
   - Layer 2: Data organization (bookmarks, lists)
   - Layer 3: Platform-specific launchers

3. **Platform Strategy:**
   - Keep Alfred for macOS system management
   - Use Alfred to bridge to terminal menu when needed
   - Terminal interface is universal across all platforms

4. **Scope (Refined):**
   - Focus on **tools discovery** first (aliases, functions, scripts, tasks)
   - Add **bookmarks** (buku) for testing
   - **Defer:** Learning resources, todo lists, long-term planning
   - Keep it simple initially

---

## New Critical Insights

### 1. Dotfiles Tools vs Universal Tools (IMPORTANT)

**The Problem:** Mixing dotfiles-specific tools with universal tools creates context confusion.

**Examples of Dotfiles-Specific Tools:**
- `symlinks` - Only relevant in dotfiles project
- `task` commands in dotfiles Taskfile - Dotfiles management only
- Dotfiles-specific scripts in `.local/bin` that should be in `scripts/`

**Examples of Universal Tools:**
- `bat`, `eza`, `fd`, `rg` - Useful anywhere
- Git functions (`fco_preview`, `fshow_preview`) - Useful in any git project
- fzf functions - Useful anywhere

**The Issue:**
If I'm working in the `ichrisbirch` project and want to find a git function to use, I **don't** want to see:
- "task dotfiles:symlinks"
- "task dotfiles:install"
- "symlinks verify"

These are only relevant when working in the dotfiles project itself.

**Solution Approach:**
- Menu should be **context-aware**
- Detect if current directory is the dotfiles project (`~/dotfiles`)
- Show "Dotfiles" category **only** when in dotfiles context
- Universal tools (git functions, general aliases) always available
- Dotfiles tools separated from universal tools

**Implementation:**
```bash
# Detect dotfiles context
is_in_dotfiles() {
  local git_root=$(git rev-parse --show-toplevel 2>/dev/null)
  [[ "$git_root" == "$HOME/dotfiles" ]]
}

# Show different menus based on context
if is_in_dotfiles; then
  # Include dotfiles category
  show_menu_with_dotfiles
else
  # Universal menu only
  show_universal_menu
fi
```

### 2. Workflow Context: Terminal vs GUI Launch (CRITICAL)

**The Problem:** Opening a new terminal window breaks workflow when already in terminal.

**Scenario 1: Not in Terminal**
- User is in browser, editor, or GUI app
- Press hotkey (e.g., Alt+M via Aerospace)
- **Desired:** Open new Ghostty window with menu
- **Result:** Works perfectly - `aerospace: alt-m = 'exec-and-forget ghostty -e menu'`

**Scenario 2: Already in Terminal**
- User is in Ghostty, working in project directory
- Working on code, wants to check bookmarks or find a git function
- Press hotkey
- **Current behavior:** Opens NEW Ghostty window
- **Problem:** Context switch - loses current terminal, current directory
- **Desired:** Menu opens IN CURRENT terminal/tmux pane

**The Conflict:**
- Aerospace hotkey always launches new process: `ghostty -e menu`
- Can't detect "am I already in terminal?" from system-level hotkey
- Need different behavior based on context

**Possible Solutions:**

#### Option A: Two Different Hotkeys (Simple)

**System hotkey (Alt+M):** Launch new Ghostty with menu
- Used when NOT in terminal
- Aerospace binding: `alt-m = 'exec-and-forget ghostty -e menu'`

**Shell keybinding (Ctrl+M or similar):** Run menu in current shell
- Used when IN terminal
- Shell binding in `.zshrc`: `bindkey '^M' 'menu; zle reset-prompt'`
- Or tmux binding: `bind-key m run-shell 'menu'`

**Pros:**
- Simple to implement
- Clear separation of contexts
- Each hotkey optimized for its use case

**Cons:**
- Two hotkeys to remember
- User must choose which one to use

#### Option B: Smart Launcher Script (Complex)

Create `~/.local/bin/menu-launcher` that detects context:

```bash
#!/usr/bin/env bash
# Smart menu launcher - detects if in terminal

if [ -t 0 ]; then
  # Running in terminal - execute menu directly
  menu
else
  # Not in terminal - launch new Ghostty with menu
  open -na Ghostty --args -e menu
fi
```

Aerospace binding: `alt-m = 'exec-and-forget menu-launcher'`

**Problem:** When launched from Aerospace, `-t 0` will be false even if focus is on terminal window. Aerospace launches processes detached from terminal context.

**Verdict:** Won't work reliably for system-level hotkey.

#### Option C: Tmux New Window (Terminal Users)

When in terminal, have menu open in **new tmux window** instead of overlay:

```bash
# In menu script
if [ -n "$TMUX" ]; then
  # In tmux - could open new window
  tmux new-window -n "menu" menu
else
  # Not in tmux - run inline
  menu
fi
```

**Pros:**
- Keeps you in terminal
- New window = more space for menu
- Easy to close (just close window)

**Cons:**
- Adds complexity
- May not want new window every time

#### Option D: Overlay in Current Terminal (Recommended)

Keep it simple - when in terminal, menu just runs:

```bash
# Shell keybinding that runs menu inline
bindkey '^[m' 'menu'  # Alt+M in terminal
```

or tmux binding:

```tmux
# In tmux.conf
bind-key m run-shell -b 'menu'
```

**When NOT in terminal:** Use Aerospace hotkey to launch new Ghostty

**Pros:**
- Simple and predictable
- Menu runs in current context (preserves working directory)
- No window juggling

**Cons:**
- Different behavior depending on where you are

---

## Recommended Approach: Dual Hotkey System

### System-Level Hotkey (Aerospace)

**Binding:** `alt-shift-m = 'exec-and-forget ghostty -e menu'`

**Usage:** Press **Alt+Shift+M** when NOT in terminal
- Launches new Ghostty window with menu
- Works from any application
- Pattern matches existing: `alt-enter = 'exec-and-forget open -na Ghostty'`

### Terminal Hotkey (Shell/Tmux)

**Option 1: Tmux Binding (Recommended)**

```tmux
# In tmux.conf
bind-key m run-shell -b '$HOME/.local/bin/menu'
```

**Usage:** Press **prefix + m** when in terminal
- Runs menu in current tmux pane/window
- Preserves current directory context
- Easy to dismiss (Esc)

**Option 2: Shell Keybinding (Alternative)**

```zsh
# In .zshrc
menu-widget() {
  menu
  zle reset-prompt
}
zle -N menu-widget
bindkey '^[m' menu-widget  # Alt+M in shell
```

**Usage:** Press **Alt+M** when in terminal (not tmux)

---

## Context Detection Strategy

### Detecting Dotfiles Context

```bash
# Function to check if in dotfiles project
is_in_dotfiles() {
  local git_root
  git_root=$(git rev-parse --show-toplevel 2>/dev/null)

  if [[ -z "$git_root" ]]; then
    return 1  # Not in git repo
  fi

  # Check if git root is dotfiles
  if [[ "$git_root" == "$HOME/dotfiles" ]] || \
     [[ "$(basename "$git_root")" == "dotfiles" ]]; then
    return 0  # In dotfiles
  fi

  return 1  # In different project
}
```

### Detecting Tmux Context

```bash
# Check if running inside tmux
is_in_tmux() {
  [[ -n "$TMUX" ]]
}
```

### Detecting Terminal Context

```bash
# Check if running in a terminal
is_in_terminal() {
  [[ -t 0 ]]
}
```

### Detecting Git Project

```bash
# Get current git project name
get_project_name() {
  local git_root
  git_root=$(git rev-parse --show-toplevel 2>/dev/null)

  if [[ -n "$git_root" ]]; then
    basename "$git_root"
  else
    echo ""
  fi
}
```

---

## Menu Structure (Context-Aware)

### Universal Categories (Always Available)

```
Tools          → CLI tools (bat, eza, fd, rg, etc.)
Aliases        → Shell aliases (auto-parsed)
Functions      → Shell functions (auto-parsed)
Git            → Git helpers (fco_preview, fshow_preview, fstash, etc.)
Bookmarks      → Buku bookmarks
Tmux           → Tmux sessions (if in tmux)
Scripts        → General scripts in .local/bin (not dotfiles-specific)
```

### Dotfiles Category (Only in ~/dotfiles)

```
Dotfiles       → Dotfiles management
  ├── Tasks    → Taskfile commands (brew, npm, docs, symlinks)
  ├── Symlinks → symlinks verify, relink, status
  ├── Docs     → Generate/serve documentation
  └── Testing  → Run tests, pre-commit checks
```

### Menu Display Logic

```bash
show_main_menu() {
  local categories=(
    "Tools"
    "Aliases"
    "Functions"
    "Git"
    "Bookmarks"
    "Scripts"
  )

  # Add tmux category if in tmux
  if is_in_tmux; then
    categories+=("Tmux")
  fi

  # Add dotfiles category if in dotfiles project
  if is_in_dotfiles; then
    categories+=("Dotfiles")
  fi

  # Display with gum
  printf '%s\n' "${categories[@]}" | gum choose
}
```

---

## Aerospace Configuration

### Current Pattern (Terminal Launch)

```toml
# In aerospace.toml line 65
alt-enter = 'exec-and-forget open -na Ghostty'
```

This opens a new Ghostty window.

### Recommended Menu Binding

```toml
# Add to [mode.main.binding] section around line 66
alt-shift-m = 'exec-and-forget ghostty -e menu'
```

**Usage:**
- **Alt+Shift+M** - Launch menu in new Ghostty window (when outside terminal)
- **Prefix+M** - Run menu in current tmux pane (when in terminal)

**Why Alt+Shift+M?**
- Mnemonic: **M** for menu
- **Shift** modifier distinguishes from other alt bindings
- Doesn't conflict with existing aerospace bindings
- Matches pattern of modified alt keys for special actions

---

## Implementation Priority

### Phase 1: Basic Menu (Days 1-2)

1. **Create menu script** (`~/.local/bin/menu`)
   - Basic structure with gum
   - Universal categories only
   - No context awareness yet

2. **Implement core categories:**
   - Tools (integrate existing `tools` script)
   - Aliases (parse `aliases.sh` with fzf)
   - Functions (parse `fzf-functions.sh` with fzf)

3. **Add hotkeys:**
   - Aerospace: `alt-shift-m` → new Ghostty with menu
   - Tmux: `prefix+m` → menu in current pane

4. **Test workflow:**
   - Launch from outside terminal (Alt+Shift+M)
   - Launch from inside terminal (Prefix+M)
   - Verify both work smoothly

### Phase 2: Context Awareness (Day 3)

1. **Add detection functions:**
   - `is_in_dotfiles()`
   - `is_in_tmux()`
   - `get_project_name()`

2. **Context-aware menu:**
   - Show "Dotfiles" category only in dotfiles project
   - Show "Tmux" category only in tmux
   - Test in different directories

3. **Dotfiles category:**
   - Parse Taskfile for commands
   - Add symlinks commands
   - Only visible in ~/dotfiles

### Phase 3: Additional Features (Day 4-5)

1. **Bookmarks:**
   - Install buku
   - Import Safari bookmarks
   - Create fzf interface
   - Add to menu

2. **Git category:**
   - List existing git functions
   - Provide examples/descriptions
   - fzf interface with preview

3. **Polish:**
   - Preview windows for all categories
   - Help text
   - Better formatting

---

## Research Summary: Key Findings

### 1. Terminal Detection

**Method:** `[ -t 0 ]` checks if stdin is a terminal

**Limitation:** When launched from Aerospace, stdin is NOT a terminal even if terminal window has focus. Cannot reliably detect "user is in terminal" from system hotkey.

**Solution:** Use separate hotkeys for different contexts.

### 2. Tmux Detection

**Method:** `[[ -n "$TMUX" ]]` - tmux sets `$TMUX` environment variable

**Reliable:** Yes, always accurate

**Use case:** Show tmux-specific options, decide whether to use tmux commands

### 3. Git Root Detection

**Method:** `git rev-parse --show-toplevel`

**Returns:** Absolute path to repository root, or error if not in git repo

**Use case:** Detect if in dotfiles project vs other projects

### 4. Aerospace Patterns

**Current terminal launch:** `alt-enter = 'exec-and-forget open -na Ghostty'`

**Pattern for menu:** `alt-shift-m = 'exec-and-forget ghostty -e menu'`

**Note:** `exec-and-forget` launches process detached (doesn't block aerospace)

---

## Open Questions

### 1. Menu Display: Overlay vs New Window?

When running menu in terminal, should it:

**A) Run inline (overlay current pane)**
- Pro: Simple, no window management
- Con: Takes over current pane

**B) Open new tmux window**
- Pro: More space, easy to close
- Con: Adds tmux window to manage

**Recommendation:** Start with **inline (A)**, can add option for (B) later.

### 2. Scripts Organization

Should dotfiles-specific scripts move from `.local/bin` to `scripts/`?

**Current:** `~/.local/bin/symlinks` (dotfiles tool, but in universal location)

**Proposed:** `~/dotfiles/scripts/symlinks` (clearly dotfiles-specific)

**Consideration:** Scripts in `scripts/` would need to be called via task or full path, not directly from PATH.

**Recommendation:** Defer this refactor. Focus on menu first, reorganize later if needed.

### 3. Bookmarks: Separate by Context?

Should bookmarks be context-aware? E.g.:
- Show dev bookmarks when in code project
- Show learning bookmarks when in learning directory

**Recommendation:** No, keep bookmarks universal. Use buku's tag system for organization, let user filter with fzf.

---

## Next Steps

### Immediate (Today)

1. **Add aerospace binding:**
   ```toml
   # In macos/.config/aerospace/aerospace.toml
   alt-shift-m = 'exec-and-forget ghostty -e menu'
   ```

2. **Install dependencies:**
   ```bash
   brew install gum buku
   ```

3. **Create menu skeleton:**
   ```bash
   touch ~/.local/bin/menu
   chmod +x ~/.local/bin/menu
   ```

4. **Test gum:**
   ```bash
   printf '%s\n' "Tools" "Aliases" "Functions" | gum choose
   ```

### Short Term (This Week)

1. Build basic menu with universal categories
2. Implement context detection
3. Add tmux binding
4. Test both hotkey workflows
5. Add dotfiles category (context-aware)

### Deferred

- Learning resources organization
- Todo lists / project tracking
- Advanced buku integration
- Usage tracking / frecency

---

## Architecture Diagram (Updated)

```
┌─────────────────────── USER CONTEXT ───────────────────────┐
│                                                              │
│  Outside Terminal              Inside Terminal              │
│  (Browser, Editor, etc.)       (Ghostty + tmux)            │
│         │                              │                     │
│         ↓                              ↓                     │
│  Alt+Shift+M (Aerospace)        Prefix+M (tmux)            │
│         │                              │                     │
│         ↓                              ↓                     │
│  Launch: ghostty -e menu        Run: menu inline           │
│         │                              │                     │
└─────────┴──────────────────────────────┴────────────────────┘
                                  ↓
         ┌────────────────────────────────────────┐
         │     ~/.local/bin/menu (Layer 1)        │
         │                                         │
         │  1. Detect context:                    │
         │     - In tmux? ($TMUX)                 │
         │     - In dotfiles? (git root)          │
         │     - Current project                   │
         │                                         │
         │  2. Build category list:               │
         │     [Universal Categories]             │
         │     + Tmux (if in tmux)                │
         │     + Dotfiles (if in ~/dotfiles)      │
         │                                         │
         │  3. Display with gum choose            │
         └────────────────────────────────────────┘
                         ↓
         ┌────────────────────────────────────────┐
         │     Selected Category Sub-Menu          │
         │                                         │
         │  - Parse data source (files, commands)  │
         │  - Display with fzf (with preview)     │
         │  - Execute selected item               │
         └────────────────────────────────────────┘
                         ↓
         ┌────────────────────────────────────────┐
         │          Data Sources                   │
         │                                         │
         │  Universal:                             │
         │    - tools registry (YAML)              │
         │    - aliases.sh (parse)                 │
         │    - fzf-functions.sh (parse)           │
         │    - .local/bin scripts (scan)          │
         │    - buku database (query)              │
         │                                         │
         │  Dotfiles-Specific:                     │
         │    - Taskfile.yml (yq query)            │
         │    - symlinks commands                  │
         └────────────────────────────────────────┘
```

---

## Summary

**Key Decisions:**
1. Use **two hotkeys** for different contexts (system vs terminal)
2. Make menu **context-aware** (dotfiles vs universal)
3. Start simple with **universal tools**, add dotfiles category when in dotfiles project
4. Focus on **tools/aliases/functions/bookmarks** first, defer learning/todos

**Hotkey Strategy:**
- **Alt+Shift+M** (Aerospace) - Launch new Ghostty with menu (outside terminal)
- **Prefix+M** (tmux) - Run menu inline (inside terminal)

**Context Awareness:**
- Detect dotfiles project with `git rev-parse --show-toplevel`
- Show dotfiles category only when in `~/dotfiles`
- Show tmux category only when `$TMUX` is set

**Next Document:** Will cover implementation details and script examples once we have basic version working.
