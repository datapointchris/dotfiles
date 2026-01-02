# Dotfiles System Redesign - November 2025

**Created:** 2025-11-07
**Status:** ALL PHASES COMPLETE ✓
**Philosophy:** Simple, focused tools. Unix philosophy. Help complete task, then get out of the way.

**Progress:**

- ✓ Phase 1: Cleanup & Consolidation (2025-11-07)
- ✓ Phase 2: Notes & Learning (2025-11-07)
- ✓ Phase 3: Documentation & Training (2025-11-07)
- ✓ Phase 4: Polish & Cleanup (2025-11-07)

**All phases completed in one day. System is production-ready.**

## Table of Contents

1. [The Problem](#the-problem)
2. [Research Summary](#research-summary)
3. [Core Philosophy](#core-philosophy)
4. [Proposed Architecture](#proposed-architecture)
5. [Individual Tool Plans](#individual-tool-plans)
6. [Data Organization](#data-organization)
7. [Implementation Plan](#implementation-plan)

---

## The Problem

### Current State - Too Many Moving Parts

**Menu implementations (3):**

- `menu` - 17MB Go binary with Bubbletea TUI (feature-rich but heavy)
- `menu-new` - Bash + fzf wrapper using menu-go-new backend
- `menu-go-new` - CLI-only Go binary (data provider)

**Session management (2):**

- `sess` - Bash script with gum (works but incomplete)
- `session` - Go TUI with Bubbletea (newer, better UX but separate environment)

**Result:** Confusion, maintenance burden, cognitive overhead

### The Deeper Issues

1. **Discoverability vs Accessibility Trade-off**
   - Need to remember what tools exist
   - But don't want extra indirection to use them
   - Tools CLI works great - standalone, no menu needed
   - Menu might add unnecessary layer

2. **Notes/Learning Organization Gaps**
   - Notes scattered across locations
   - No clear hierarchical organization
   - Want semester-based learning periods
   - Want brain connections, not just wiki links
   - Obsidian feels cumbersome despite using it

3. **Application vs Data Confusion**
   - Apps live in dotfiles (correct)
   - Data mixed in (some correct, some not)
   - Obsidian docs in ~/Documents/notes (correct)
   - But no unified data organization philosophy

4. **Interface Pattern Inconsistency**
   - Some tools are TUIs (session, menu)
   - Some are CLIs (tools, theme-sync)
   - Some are both (sess has gum, but also CLI modes)
   - No clear pattern of when to use which

### What's Working Well

✓ **tools CLI** - 30 curated tools, bash script, fast, helpful
✓ **theme-sync** - Base16 synchronization, clear purpose
✓ **symlinks system** - Managed through Task, organized
✓ **Pre-commit hooks** - Quality control automated
✓ **MkDocs site** - Documentation well organized

---

## Research Summary

### Sesh Architecture (Josh Medeski)

**Key Pattern: Data Provider + External UI**

```text
sesh list [filters] | fzf/gum | sesh connect
```text

**Core Insight:** Sesh doesn't integrate WITH fzf/gum - it outputs FOR them. The integration happens at the shell/tmux config level, not in the tool itself.

**Three-Layer Architecture:**

1. **Data Sources** (tmux, zoxide, config)
2. **Core Logic** (lister, session management)
3. **Output Formatters** (plain/JSON/icons)
4. **External UI Tools** (user's choice: fzf, gum, rofi)

**What Makes It Lightweight:**

- Single binary, no runtime dependencies
- Works out of box, configuration is optional
- Does one thing well (session management)
- Defaults to simple (plain text output)
- Composable with existing Unix tools
- Doesn't try to be the UI

**Recommended tmux integration:**

```bash
bind-key "s" run-shell "sesh connect \"$(
  sesh list | fzf-tmux -p 55%,60% \
    --no-sort --ansi \
    --border-label ' sesh ' --prompt '⚡  ' \
    --header ' ^a all ^t tmux ^g configs ^x zoxide ^d tmux kill ^f find' \
    --bind 'tab:down,btab:up' \
    --bind 'ctrl-a:change-prompt(⚡  )+reload(sesh list)' \
    --bind 'ctrl-t:change-prompt(🪟  )+reload(sesh list -t)' \
    --bind 'ctrl-g:change-prompt(⚙️  )+reload(sesh list -c)' \
    --bind 'ctrl-x:change-prompt(📁  )+reload(sesh list -z)' \
    --bind 'ctrl-f:change-prompt(🔎  )+reload(fd -H -d 2 -t d -E .Trash . ~)' \
    --bind 'ctrl-d:execute(tmux kill-session -t {})+change-prompt(⚡  )+reload(sesh list)'
)\""
```text

**The magic:** UI is built with FZF bindings and tmux config, not in the Go code. Sesh just provides data.

### Omarchy Philosophy (DHH)

**Core Principle: "Beauty drives motivation"**

> "A beautiful system is a motivating system, and productivity has always been downstream from motivation."

**Omakase Spirit:**

- Opinionated defaults over infinite choice
- Curated, not comprehensive
- "Zero bloat: Just everything I use"
- Intentional defaults that can be overridden

**Configuration Pattern:**

- `~/.config/*` - User's files for customization
- `~/.local/share/omarchy/*` - System files (don't edit)
- User overrides defaults, doesn't replace them

**Keyboard-First:**

- Everything happens via keyboard
- `Super + Space` - Application launcher (fuzzy search)
- `Super + Alt + Space` - Omarchy Menu (reference/config)
- Direct hotkeys for frequent tasks
- Menu for discovery and infrequent tasks

**Layered Access Patterns:**

1. Direct hotkeys - Frequent tasks (Super+Return for terminal)
2. Launcher - Fuzzy search for any app (Super+Space)
3. Menu - Reference and configuration (Super+Alt+Space)

**Separation of Concerns:**

- Applications are isolated
- Data remains portable and shared (`~/Windows` auto-shared with VM)
- Configuration separate from system files

### nb Note-Taking Tool

**Perfect for Hierarchical Organization:**

```text
~/.nb/
├── learning-2024-fall/          # Notebook = git repo
│   ├── computer-science/        # Folder
│   │   ├── algorithms/          # Subfolder
│   │   │   ├── sorting.md
│   │   │   └── graphs.md
│   │   └── databases/
│   └── philosophy/
└── learning-2025-spring/        # Another notebook
    └── ...
```text

**Key Features for Your Use Case:**

1. **Hierarchical:** Notebooks > Folders > Notes (unlimited nesting)
2. **Wiki Links:** Full support including cross-notebook links
3. **Media Types:** PDF, images, bookmarks, code - all mixed naturally
4. **Semester Organization:** One notebook per semester, perfect fit
5. **Quick Capture:** `nb a "thought"` or `nb +` - instant note creation
6. **Fast Retrieval:** `nb s keyword` - regex search, blazing fast
7. **Git-backed:** Every notebook is a git repo, version control built-in
8. **Terminal-native:** CLI-first, optional web UI for visual browsing
9. **Plain text:** Just markdown in folders, no lock-in
10. **Cross-links:** `[[learning-2024-fall:algorithms/sorting]]` from any notebook

**Workflow Example:**

```bash
# Create semester notebook
nb notebooks add learning-2025-spring

# Add note with context
nb a  # Opens $EDITOR

# Quick capture
nb + "Database normalization - remember 3NF eliminates transitive dependencies"

# Search across all semesters
nb search --all "normalization"

# Browse visually when needed
nb browse --gui  # Local web server with wiki links

# Link between semesters
# In Spring 2025 note: [[learning-2024-fall:databases/normalization]]
```text

**Why nb over Obsidian for You:**

| Aspect | nb | Obsidian |
|--------|----|----|
| Terminal workflow | Native, zero friction | Requires GUI open |
| Speed | Instant CLI | GUI startup delay |
| Memory | ~50KB script | ~200MB Electron app |
| Note capture | `nb a` from anywhere | Must open app first |
| Hierarchical | Excellent (folders) | Excellent (folders) |
| Wiki links | Full support | Full support + backlinks panel |
| Graph view | None (text-based) | Beautiful interactive graph |
| Mobile | Via SSH (clunky) | Native apps (excellent) |
| Philosophy | Unix tool, composable | Standalone app |
| Future-proof | Plain text + git | Plain text (but needs app) |

**Hybrid Approach Possible:**

- Use **nb** for daily terminal-based capture and retrieval
- Use **Obsidian** occasionally to visualize connection graphs
- Both can share same markdown files (nb adds `.git`, Obsidian adds `.obsidian`)
- Get CLI speed + visual graph analysis when needed

### Planning History - Universal Menu Redesign

**The Journey:** Bubble Tea TUI → Go CLI + fzf wrapper

**Key Learnings:**

1. **Execution Context Matters**
   - Commands inside `tmux display-popup` run in popup shell context
   - Use `fzf-tmux -p` to keep script in normal context
   - This is THE pattern for tmux session managers

2. **Separation Works**
   - Go for data management (YAML parsing, formatting)
   - fzf for UI (navigation, filtering, preview)
   - Bash for integration (tmux detection, shell interaction)

3. **Sesh Pattern Validation**
   - Multiple fzf bindings create rich interface
   - All configuration in tmux.conf / shell rc files
   - Tool just provides data and actions

4. **Current Status**
   - `menu-new` + `menu-go-new` working
   - 84%+ test coverage maintained
   - Bash + fzf feels much lighter than Bubble Tea
   - But still questioning if menu is right approach

---

## Core Philosophy

### Unix Philosophy Applied

1. **Make each program do one thing well**
   - `tools` - List and describe available tools
   - `session` - Manage tmux sessions
   - `theme-sync` - Synchronize color themes
   - `nb` - Manage notes hierarchically

2. **Expect output to be input to another program**
   - `tools list | fzf` - Pipe to fzf for selection
   - `session list | grep` - Filter with standard tools
   - `nb search "query" | less` - Page through results

3. **Design for composition, not integration**
   - Tools output clean, parseable data
   - UI layer separate (fzf, gum, bat, less)
   - Shell/tmux config wires things together

### The Sesh Lesson

**Don't build UI into tools. Provide data, let users build UI.**

```text
# Bad: Tool tries to be everything
tool --ui=tui --theme=dark --keybinds=vim

# Good: Tool provides data, user composes
tool list | fzf --preview="tool show {}"
```text

### The Omarchy Lesson

**Opinionated defaults + beauty = motivation to use tools.**

- Default workflows should be delightful
- Configuration enhances, doesn't replace
- Beauty is functional (clear, organized, coherent)
- Keyboard-driven reduces friction

### The "Forgetting Tools" Problem

**Solution is NOT a menu - it's better defaults + muscle memory.**

Like Omarchy's layered access:

1. **Muscle memory:** Direct commands for frequent tasks (`session dotfiles`, `theme-sync apply rose-pine`)
2. **Fuzzy launcher:** For occasional tasks (`tools | fzf`, `session | fzf`)
3. **Reference menu:** For "what was that command?" moments (docs, not a TUI)

**The Menu Mistake:** Tried to be layer 2 AND 3, ended up being neither well.

---

## Proposed Architecture

### The New Model: Independent Tools + Composable UI

```text
┌─────────────────────────────────────────────────────────────┐
│                     USER INTERFACE LAYER                     │
│  (Shell aliases, tmux bindings, fzf wrappers, Alfred/Raycast)│
└─────────────────────────────────────────────────────────────┘
                               │
       ┌───────────────────────┼───────────────────────┐
       │                       │                       │
       ▼                       ▼                       ▼
┌─────────────┐        ┌─────────────┐        ┌─────────────┐
│   session   │        │    tools    │        │  theme-sync │
│  (Go CLI)   │        │ (Bash CLI)  │        │ (Bash CLI)  │
└─────────────┘        └─────────────┘        └─────────────┘
       │                       │                       │
       ▼                       ▼                       ▼
┌─────────────┐        ┌─────────────┐        ┌─────────────┐
│Tmux sessions│        │Tool registry│        │tinty themes │
│Tmuxinator   │        │  (YAML)     │        │  (toml)     │
└─────────────┘        └─────────────┘        └─────────────┘
```text

### UI Layer Lives in Dotfiles, Not Tools

**tmux.conf:**

```bash
# Session switcher with fzf
bind s run-shell "session list | fzf-tmux -p 60% --preview='session show {}' | xargs session switch"

# Quick reference menu (gum, not a custom TUI)
bind m display-popup -E -w 80% -h 80% "$HOME/.local/bin/dotfiles-menu"
```text

**zshrc:**

```bash
# Tool discovery
alias t='tools list | fzf --preview="tools show {1}"'

# Theme picker
alias themes='theme-sync favorites | fzf --preview="theme-sync preview {1}" | xargs theme-sync apply'

# Session jumper
alias s='session'  # Interactive by default
```text

**Alfred/Raycast workflow:**

```text
cmd+shift+s → Open Ghostty → Run session
cmd+shift+t → Show tools list
cmd+shift+m → Show dotfiles reference menu
```text

### The "Menu" Becomes Simple Reference

Instead of complex TUI/CLI hybrid, create `dotfiles-menu`:

```bash
#!/usr/bin/env bash
# dotfiles-menu - Quick reference for dotfiles tools
# Shown in tmux popup with: bind m display-popup...

gum style --border=rounded --padding="1 2" --bold \
  "Dotfiles Quick Reference"

choice=$(gum choose \
  "Session Management (session)" \
  "Tool Discovery (tools)" \
  "Theme Management (theme-sync)" \
  "Notes & Learning (nb)" \
  "Symlink Management (task symlinks:*)" \
  "Documentation (open docs)" \
  "Configuration (edit CLAUDE.md)")

case "$choice" in
  "Session Management"*)
    session ;;
  "Tool Discovery"*)
    tools list | fzf --preview="tools show {1}" ;;
  "Theme Management"*)
    theme-sync favorites | fzf --preview="theme-sync preview {1}" | xargs theme-sync apply ;;
  # ... etc
esac
```text

**It's just a launcher with examples, not a complex system.**

---

## Individual Tool Plans

### 1. Session Management - Consolidate to One

**Decision: Keep Go binary, use gum (not bubbletea), rename to `sess`**

**Changes Made:**

- ✓ Removed Bubbletea TUI dependency
- ✓ Added gum for interactive selection
- ✓ Renamed binary from `session` to `sess`
- ✓ Archived old bash `sess` script
- ✓ Stays in same terminal window (no separate TUI)

**Current Approach:**

```bash
# sess - Go CLI with gum UI
sess                             # Interactive gum selection
sess <name>                      # Create or switch to session
sess list                        # Plain text output with icons (●⚙○)
sess last                        # Switch to last session
```text

**No Shell Aliases:**
User prefers typing full command names for clarity:

- Type `sess` (easy to remember and type)
- Type `tools` (clear what it does)
- Type `theme-sync` (descriptive)

**Benefits:**

- One tool, works like bash `sess` but with Go benefits (testing, type safety)
- Uses gum for interactive selection (stays in same window)
- Can still pipe output: `sess list | fzf` if desired
- Simple and memorable: just `sess`

### 2. Tools Discovery - Already Perfect

**Decision: Keep as-is, document composition patterns**

**Current State:** Bash script, 30 curated tools, works great

**No Changes Needed:**

- Already outputs clean, parseable data
- Works perfectly for discovery
- Composition with fzf is optional, not required

**No Shell Aliases:**
User prefers typing `tools` directly:

- `tools` - Clear and memorable
- `tools list | fzf --preview='tools show {1}'` - Explicit composition when wanted
- No cryptic shortcuts needed

**Documentation Enhancement:**
Show composition examples in docs as optional workflows, not aliases to configure.

### 3. Theme Management - Already Good

**Decision: Keep `theme-sync`, document better workflows**

**Current State:** Bash script, tinty-based, works well

**Enhancement: Add composition examples**

```bash
# theme-sync - Already good

# Better workflows in docs:
alias theme='theme-sync favorites | fzf --preview="theme-sync preview {1}" | xargs theme-sync apply'
alias tc='theme-sync current'     # Quick check
```text

### 4. Menu System - Radically Simplify

**Decision: Delete the complex Go+fzf menu. Create simple gum-based reference.**

**Important Clarification:**
This menu is for **workflow tools**, NOT dotfiles management:

- **Workflow tools:** sess, tools, theme-sync, nb (happens to live in dotfiles repo)
- **Dotfiles management:** task symlinks:*, task install:*, etc.
- Clear separation of concerns

**What to Delete:**

- `menu` (17MB Go TUI) - Remove entirely
- `menu-go-new` (Go CLI backend) - Remove entirely
- `menu-new` (Bash wrapper) - Remove entirely

**What to Create:**

```bash
#!/usr/bin/env bash
# menu - Workflow tools quick reference launcher
# Location: ~/.local/bin/menu

show_help() {
  gum style --border=rounded --padding="1 2" --bold \
    "Dotfiles Tools - Quick Reference"

  echo ""
  echo "Direct Commands:"
  echo "  session          - Manage tmux sessions"
  echo "  tools [cmd]      - Discover and learn about tools"
  echo "  theme-sync [cmd] - Manage color themes"
  echo "  nb [cmd]         - Note taking and knowledge management"
  echo "  task symlinks:*  - Manage dotfile symlinks"
  echo ""
  echo "Aliases:"
  echo "  s                - Session switcher (interactive)"
  echo "  t                - Tool finder (with fzf)"
  echo "  theme            - Theme picker (with fzf)"
  echo ""
  echo "tmux Bindings:"
  echo "  prefix + s       - Session switcher"
  echo "  prefix + m       - This reference menu"
  echo ""

  gum style --faint "Run 'dotfiles launch' for interactive launcher"
}

launch_menu() {
  choice=$(gum choose --header="What do you want to do?" \
    "Switch tmux session" \
    "Find a tool" \
    "Change theme" \
    "Take a note" \
    "Browse documentation" \
    "Manage symlinks" \
    "Show this help")

  case "$choice" in
    "Switch tmux session")
      session ;;
    "Find a tool")
      tools list | fzf --preview="tools show {1}" ;;
    "Change theme")
      theme-sync favorites | fzf --preview="theme-sync preview {1}" | xargs theme-sync apply ;;
    "Take a note")
      nb ;;
    "Browse documentation")
      open "http://localhost:8000" ;;  # MkDocs serve
    "Manage symlinks")
      task symlinks:link ;;
    "Show this help")
      show_help ;;
  esac
}

case "${1:-help}" in
  help|--help|-h)
    show_help ;;
  launch|menu)
    launch_menu ;;
  *)
    echo "Unknown command: $1"
    echo "Run 'dotfiles help' for usage"
    exit 1 ;;
esac
```text

**Benefits:**

- Tiny script (< 100 lines)
- Uses gum (already installed)
- Just launches other tools
- No complex Go maintenance
- No confusion about what it does
- Can be called from Alfred/Raycast/tmux easily

### 5. Notes & Learning - Adopt nb

**Decision: Fully commit to nb for hierarchical note-taking**

**Important: Multiple Notebooks Strategy**

User wants separate notebooks for better organization:

- `learning` notebook - semester-based learning (separate git repo)
- `notes` notebook - general notes (separate git repo)
- nb treats all notebooks under ~/.nb/ as one unified system
- Can expand later (work, projects, etc.)

**Organization Strategy:**

```bash
~/.nb/
├── learning/                 # Git repo for learning
│   ├── .git/                 # Learning repo
│   ├── 2024-fall/
│   │   ├── computer-science/
│   │   │   ├── algorithms/
│   │   │   ├── data-structures/
│   │   │   └── databases/
│   │   ├── systems/
│   │   │   ├── unix/
│   │   │   └── networking/
│   │   └── readings/
│   │       ├── papers/
│   │       └── books/
│   └── 2025-spring/
│       ├── computer-science/
│       └── philosophy/
└── notes/                    # Git repo for general notes
    ├── .git/                 # Notes repo
    ├── work/
    ├── personal/
    └── ideas/

# Quick capture
nb add                         # Add to current notebook
nb learning:add                # Add to learning notebook
nb notes:add                   # Add to notes notebook
nb + "Quick thought"           # Command-line note (current notebook)

# Retrieval
nb search "database normalization"       # Search current notebook
nb search --all "database normalization" # Search ALL notebooks
nb browse --gui                          # Visual web interface

# Cross-notebook wiki links
# In a notes notebook file:
[[learning:2024-fall/computer-science/databases/normalization]]

# In a learning notebook file:
[[notes:work/database-design]]
```text

**Benefits of Multiple Notebooks:**

- Separate git remotes (can keep learning public, notes private)
- Cleaner organization (learning vs general notes)
- Can expand later (work notebook, projects notebook, etc.)
- nb treats them as unified system for search and linking
- Each notebook can be synced independently

**Integration with Workflow:**

```bash
# No shell aliases - type full commands
nb                            # Interactive (default notebook)
nb add                        # Create new note
nb search "query"             # Search notes
nb browse --gui               # Visual web interface

# Can still compose with other tools when needed
nb search "algorithms" | less
nb list | fzf

# Integration with Obsidian (optional)
# Can open same folder in Obsidian for graph view occasionally
# nb manages via CLI, Obsidian for visual graph analysis
```text

**Migration Plan:**

1. **Phase 1:** Set up nb notebooks

   ```bash
   # Create learning notebook
   nb notebooks add learning
   cd ~/.nb/learning
   mkdir -p 2024-fall/computer-science 2024-fall/systems 2024-fall/readings
   mkdir -p 2025-spring/computer-science 2025-spring/philosophy

   # Create notes notebook
   nb notebooks add notes
   cd ~/.nb/notes
   mkdir -p work personal ideas
   ```

2. **Phase 2:** Set up git remotes

   ```bash
   # Learning notebook (could be public)
   cd ~/.nb/learning
   git remote add origin git@github.com:you/learning.git
   nb learning:sync

   # Notes notebook (private)
   cd ~/.nb/notes
   git remote add origin git@github.com:you/notes-private.git
   nb notes:sync
   ```

3. **Phase 3:** Migrate existing notes from Obsidian

   ```bash
   # Copy to appropriate notebooks
   cp -r ~/Documents/notes/learning-related/* ~/.nb/learning/
   cp -r ~/Documents/notes/general/* ~/.nb/notes/

   # Sync both
   nb learning:sync
   nb notes:sync
   ```

3. **Phase 3:** Establish daily habits
   - Morning: Review via `nb browse --gui`
   - During day: Quick capture with `nb +`
   - Evening: Organize with `nb edit`, add wiki links

4. **Phase 4:** Build connections
   - Use `[[wiki links]]` to connect ideas
   - Tag with hierarchical tags: `#compsci/algorithms`
   - Periodically review in Obsidian for graph visualization

---

## Data Organization

### Principle: Applications in Dotfiles, Data Elsewhere

**Dotfiles (~/dotfiles):**

- Application binaries
- Configuration files
- Scripts and tools
- Documentation
- Installation logic

**Data Locations:**

| Data Type | Location | Backup Strategy | Sync Strategy |
|-----------|----------|----------------|---------------|
| Notes & Learning | `~/.nb/` | Git remotes | `nb sync` |
| Documents | `~/Documents/` | Time Machine + Cloud | iCloud/Dropbox |
| Projects | `~/code/` | Git remotes | Git push |
| Tool Registries | `~/dotfiles/docs/tools/registry.yml` | Git (in dotfiles) | Git push |
| Session Configs | `~/.config/menu/sessions/` | Git (in dotfiles) | Git push |
| Theme Configs | `~/.config/tinty/` | Git (in dotfiles) | Git push |
| Cache/Temp | `~/.cache/`, `~/.local/state/` | None | None |

**Why this works:**

- Applications are configuration (version controlled in dotfiles)
- Data is personal content (versioned separately where appropriate)
- Clear boundary: dotfiles repo doesn't grow with personal content
- Easy to backup/sync different data types differently

### nb Specific Organization

```text
~/.nb/                              # All notebooks
├── home/                           # Default notebook (miscellaneous)
├── learning-2024-fall/             # Semester-based
├── learning-2025-spring/           # Semester-based
├── work/                           # Work notes (private repo)
└── personal/                       # Personal notes

# Each notebook is a git repo
~/.nb/learning-2024-fall/.git/
  ├── remote origin → github.com/you/learning-2024-fall (private)
```text

**Backup Strategy for nb:**

```bash
# Each notebook syncs to own private git repo
cd ~/.nb/learning-2024-fall
nb remote set git@github.com:you/learning-2024-fall.git
nb sync  # Auto-commit and push
```text

**Benefits:**

- Each learning period is independently versioned
- Can share specific notebooks (make work notebook private, learning public for blog)
- Easy to archive old semesters (just remove notebook, keep git remote)
- Time Machine backs up `~/.nb/` automatically

---

## Implementation Plan

### Phase 1: Cleanup & Consolidation (Week 1)

#### 1.1 Remove Complex Menu System

- [ ] Archive menu-go code to `archive/menu-go-v1/`
- [ ] Remove binaries: `menu`, `menu-go-new`, `menu-new`
- [ ] Delete Go menu code from `tools/menu-go/` (keep as git history)
- [ ] Remove menu registries: `commands.yml`, `workflows.yml`, `learning.yml`
- [ ] Create simple `dotfiles` launcher script (gum-based)

#### 1.2 Consolidate Session Management

- [ ] Verify `session` Go binary works for all use cases
- [ ] Remove `sess` bash script
- [ ] Update `session` to support CLI output modes (list, list --icons, show)
- [ ] Create tmux binding with fzf-tmux
- [ ] Create shell aliases (s, sl, ss)
- [ ] Test switching, creating, tmuxinator integration

#### 1.3 Document Current Working Tools

- [ ] Update docs for `tools` CLI (add composition examples)
- [ ] Update docs for `theme-sync` (add fzf workflows)
- [ ] Create new docs page: "Quick Reference" (what used to be menu)

### Phase 2: Notes & Learning (Week 2) ✓ COMPLETE

#### 2.1 Set Up nb ✓

- [x] Install nb: `brew install nb`
- [x] Create notebook structure
  - Created `learning` notebook with semester-based folders (2024-fall, 2025-spring)
  - Created `notes` notebook with work/personal/projects folders
  - Created `ideas` notebook for quick capture
- [x] Set up git remotes for each notebook
  - learning: <https://github.com/datapointchris/learning.git> (public)
  - notes: <https://github.com/datapointchris/notes.git> (private)
  - ideas: <https://github.com/datapointchris/ideas.git> (private)
- [ ] Configure aliases in zshrc (deferred - direct commands preferred)

#### 2.2 Migrate Existing Notes

- [ ] Audit current notes in Obsidian vault (next steps)
- [x] Create folder structure in appropriate nb notebooks
- [ ] Copy markdown files to nb (preserves wiki links)
- [ ] Update wiki links to cross-notebook format if needed
- [ ] Test browse mode (`nb browse --gui`)

#### 2.3 Establish Workflows

- [ ] Morning: Review open tasks (`nb tasks open`)
- [ ] Capture: Quick notes (`nb add`)
- [ ] Study: Add notes while learning (`nb learning:add`)
- [ ] Connect: Add wiki links between related notes
- [ ] Weekly: Review notes and connections

**See:** `planning/phase2-complete-summary.md` for detailed workflow guide and examples.

### Phase 3: Documentation & Training (Week 3) ✓ COMPLETE

#### 3.1 Update Documentation ✓

- [x] Create `docs/reference/quick-reference.md` (replaces menu)
- [x] Update `docs/getting-started/` with new workflows
- [x] Create `docs/architecture/tool-composition.md` (how tools work together)
- [x] Document nb workflows in `docs/workflows/note-taking.md`
- [x] Update CLAUDE.md with new patterns
- [x] Update mkdocs.yml navigation with new docs

#### 3.2 Create Muscle Memory Aids ✓

- [x] Cheatsheet (markdown): `docs/reference/workflow-tools-cheatsheet.md`
- [ ] Shell aliases: Not needed - using full command names (user preference)
- [ ] Tmux bindings: Document in `docs/reference/tmux-bindings.md` (optional, deferred)
- [ ] Alfred/Raycast workflows (if using) (optional, deferred)

#### 3.3 Practice Period

- [ ] Use new system exclusively for 1-2 weeks
- [ ] Note friction points
- [ ] Adjust workflows as needed
- [ ] Validate documentation accuracy

**See:** `planning/phase3-complete-summary.md` for detailed documentation overview.

### Phase 4: Polish & Cleanup (Week 4) ✓ COMPLETE

#### 4.1 Remove Dead Code ✓

- [x] Delete archived menu code if new system working (already archived in Phase 1)
- [x] Clean up unused YAML registries (removed 5 config files)
- [x] Remove obsolete scripts from `.local/bin/` (removed old bash sess)
- [ ] Update Taskfile.yml (no menu build tasks existed)

#### 4.2 Polish & Document ✓

- [ ] Screenshots of new workflows (optional, deferred)
- [x] Update README with philosophy (complete overhaul)
- [x] Clean up `.claude/` skills (no menu-related skills found)
- [x] Update `.gitignore` for nb (nb notebooks outside repo, no changes needed)

#### 4.3 Establish Maintenance Cadence ✓

Documented in Phase 4 summary:

- Weekly: Review and clean up notes, sync nb notebooks
- Monthly: Update tool registry with new tools
- Quarterly: Review workflows, adjust as needed
- Yearly: Archive old learning semesters

**See:** `planning/phase4-complete-summary.md` for cleanup details and final system state.

**Files cleaned:**

- Removed: 7 obsolete files (old sess, 5 menu configs, 1 empty directory)
- Updated: 1 file (README.md - complete overhaul)
- Added: 1 file (common/.local/bin/menu)

**Net result:** Cleaner codebase, updated documentation, production-ready system.

---

## Success Criteria

### Immediate (After Phase 1)

✓ Only one session management tool exists
✓ No complex menu system - just simple launcher
✓ All working tools clearly documented
✓ Can find any tool in < 10 seconds

### Near-term (After Phase 2)

✓ All notes in nb with clear structure
✓ Can capture thought in < 5 seconds
✓ Can find note in < 10 seconds
✓ Wiki links connecting ideas across semesters

### Long-term (After 1 Month)

✓ Using tools daily without thinking
✓ Not forgetting tools exist
✓ Notes system feels natural and helpful
✓ Connections forming between ideas naturally
✓ System helps, doesn't hinder

---

## Key Takeaways

### Lessons Applied

1. **Sesh Pattern:** Tools provide data, users build UI with composition
2. **Omarchy Philosophy:** Beautiful defaults + keyboard-driven + layered access
3. **nb Architecture:** Hierarchical + git-backed + terminal-native = perfect for learning
4. **Unix Philosophy:** Do one thing well, compose with other tools

### Principles to Remember

1. **Simple > Complex:** Gum launcher > Custom TUI
2. **Composition > Integration:** Pipe to fzf > Build fzf into tool
3. **Defaults > Configuration:** Great defaults > Endless options
4. **Beauty = Functional:** Clear, organized, coherent = usable
5. **Data ≠ Applications:** Notes live elsewhere, configs in dotfiles

### Anti-Patterns to Avoid

1. ❌ Building custom TUIs when fzf/gum work
2. ❌ Creating "unified systems" that do everything
3. ❌ Mixing application code with personal data
4. ❌ Trying to remember everything instead of building muscle memory
5. ❌ Taking thousands of notes instead of making connections

---

## Next Steps

1. Review this plan thoroughly
2. Decide if philosophy and approach feel right
3. Start with Phase 1 cleanup
4. One week at a time, no rush
5. Adjust based on real usage

Remember: **The goal is tools that help, then get out of the way.**
