# Universal Menu System - Function-Based Knowledge System

**Date:** 2025-11-06
**Status:** Planning - Revised
**Previous:** 05-comprehensive-redesign.md

## Executive Summary

Evolution from curated registry to **unified function-based knowledge and workflow system** that organizes information by *what you're trying to accomplish* rather than *what type of content it is*.

### Key Changes from Previous Plan

1. **No CLI registry tool** - Edit YAML files directly (like tmux.conf/aerospace.toml)
2. **Session manager renamed to `sess`** - Easy to type, intuitive commands
3. **Neovim workflows integrated** - Leverage existing workflows.lua system
4. **Function-based organization** - "Learning: Neovim" not "Bookmarks" + "Notes" + "Videos"
5. **nb + buku integration** - Proven CLI tools for notes and bookmarks
6. **Obsidian workflow streamlined** - Make it easier to actually use

---

## The Core Problem: Type vs Function Organization

### Current Fragmentation

You have multiple parallel systems for similar purposes:

**Learning Resources:**
- Bookmarks (Safari/buku) - articles to read, videos to watch, references
- Notes (Obsidian) - study guides, summaries, learning plans
- Dev notes - tutorials, workflows, code examples

**Remembering Workflows:**
- workflows.lua - Neovim keybindings and workflows
- Functions - Shell/fzf workflows
- Aliases - Git shortcuts

**Organizing by Type (Bad):**
```
Bookmarks/
├── neovim-tutorial.md
├── docker-cheatsheet.md
└── aws-lambda-guide.md

Notes/
├── neovim-learning.md
├── docker-notes.md
└── aws-study-guide.md
```

**Organizing by Function (Good):**
```
Learning: Neovim/
├── tutorials (bookmarks)
├── study notes
├── workflows & keybindings
└── practice exercises

Learning: Docker/
├── references (bookmarks)
├── personal notes
└── common commands

Reference: AWS Lambda/
├── official docs (bookmark)
├── quick reference (note)
└── deployment workflow
```

### The Mental Model

When you think "I need to learn about quickfix lists in Neovim":
- You don't care if it's a bookmark, note, or workflow
- You want ALL resources about quickfix lists in one place
- You want to see: tutorials, your notes, relevant keybindings, examples

When you think "How do I deploy a Lambda function?":
- You want the workflow steps (note)
- The AWS CLI commands (reference)
- Maybe a bookmark to docs
- All in one "AWS Lambda" knowledge node

---

## Research Findings

### Your Existing Systems

**Neovim workflows.lua (Excellent!):**
- Already organized by function: File Navigation, Code Intelligence, Git, etc.
- Telescope picker for browsing
- Preview with keybindings
- Can extend this pattern!

**Notes Script:**
- Simple but underutilized
- Opens Obsidian notes in neovim
- Has search functionality
- Directory: ~/Documents/notes/

**Obsidian Setup:**
- Workspaces configured
- Templates available
- dailies/, inbox/, dev/ subdirectories
- Not using it enough (key problem to solve!)

**Octo Plugin:**
- GitHub PR/Issue management in neovim
- Integrated with Telescope
- Could add GitHub workflow to menu

### CLI Knowledge Management Tools

**nb** (Highly Recommended - Fits Your Style):
```bash
# Plain text, markdown-based
nb                          # List notes
nb add                      # Create note
nb bookmark <url>           # Save bookmark (downloads & cleans HTML → markdown)
nb search <term>            # Full-text search
nb tag note learning        # Add tags
nb learning:               # Filter by tag
nb edit 5                   # Edit note #5
nb show 5 --render         # View rendered

# Git-backed (auto-commits, can sync)
# Supports [[wiki-links]] between notes
# Local web interface (nb browse)
# Encryption support
```

**Features that match your workflow:**
- Filesystem-based (can use with existing tools)
- Bookmarks → markdown (not separate system!)
- Tagging and search
- Git versioning
- Can integrate with Obsidian vault
- Single portable script

**buku** (For Bookmarks):
```bash
buku -a <url> <tags>        # Add bookmark
buku -s <tag>               # Search by tag
buku -p -f 10 | fzf         # Fuzzy search
buku --suggest              # Get tag suggestions
buku -p --np                # Print all, no prompts
```

**fzf integration:**
```bash
# Fuzzy search and open
firefox $(buku -p -f 10 | fzf | awk '{print $1}' | xargs buku -p | grep http | awk '{print $2}')
```

---

## Proposed Architecture

### Function-Based Categories

Instead of "Aliases", "Bookmarks", "Notes", organize by purpose:

```yaml
categories:
  # Quick Reference (things I forget)
  - name: Shell Commands
    purpose: reference
    icon:
    includes: [aliases, functions, scripts]

  - name: Git Workflows
    purpose: reference
    icon:
    includes: [aliases, forgit commands, workflows]

  - name: Neovim Workflows
    purpose: reference
    icon:
    includes: [keybindings, motions, plugins]

  # Learning (things I'm actively learning)
  - name: Learning: Neovim
    purpose: learning
    icon: 📚
    includes: [bookmarks, notes, tutorials, workflows]

  - name: Learning: Docker
    purpose: learning
    icon: 📚
    includes: [bookmarks, study notes, examples]

  - name: Learning: AWS
    purpose: learning
    icon: 📚
    includes: [bookmarks, notes, practice labs]

  # Project-Specific
  - name: Project: dotfiles
    purpose: project
    icon: ⚙️
    includes: [tasks, todos, notes, bookmarks]

  # Workflows (multi-step processes)
  - name: Workflows
    purpose: workflow
    icon: 🔄
    includes: [deployment, setup, troubleshooting]
```

### Registry Schema (Enhanced)

```yaml
# Shell command with examples
commands:
  - name: fcd
    type: function
    category: Shell Commands
    purpose: reference
    description: Fuzzy find directory and cd into it
    keywords: [navigate, directory, find, cd, fzf]
    examples:
      - fcd ~/code
      - fcd  # From current directory
    related: [fd, fzf, z]

# Neovim workflow
workflows:
  - name: Quickfix List Workflow
    type: neovim_workflow
    category: Neovim Workflows
    purpose: reference
    description: Search repo → quickfix list → batch changes
    keywords: [search, replace, quickfix, batch]
    steps:
      - "<leader>fg to search"
      - "Send results to quickfix: <C-q>"
      - ":cdo s/old/new/g to replace all"
      - ":cfdo update to save all"
    related_keybindings:
      - ":cn - next quickfix"
      - ":cp - previous quickfix"
      - ":copen - open quickfix window"
    resources:
      - type: bookmark
        url: "https://vimways.org/2018/colder-quickfix-lists/"
        title: "Colder Quickfix Lists"
      - type: note
        path: "~/Documents/notes/dev/workflows/quickfix.md"

# Learning topic
learning:
  - name: Docker Compose
    category: Learning: Docker
    purpose: learning
    status: active  # active, completed, paused
    description: Multi-container Docker applications
    keywords: [docker, compose, containers, orchestration]
    resources:
      bookmarks:
        - url: "https://docs.docker.com/compose/"
          title: "Official Documentation"
          tags: [reference, official]
        - url: "https://www.youtube.com/watch?v=..."
          title: "Docker Compose Tutorial"
          tags: [tutorial, video, to-watch]
      notes:
        - path: "~/Documents/notes/dev/docker-compose-study.md"
          description: "My study notes"
        - path: "~/Documents/notes/dev/docker-compose-examples.md"
          description: "Common patterns"
      practice:
        - "Set up multi-service app locally"
        - "Add healthchecks to services"

# Project-specific
projects:
  - name: dotfiles
    category: Project: dotfiles
    purpose: project
    git_root: ~/dotfiles
    sessions:
      default: dotfiles
      tmuxinator: null
    quick_links:
      tasks: "task --list-all"
      todo: "cat todo.md"
      docs: "cd docs && mkdocs serve"
    bookmarks:
      - url: "https://docs.mkdocs.org"
        tags: [reference, docs]
    notes:
      - path: "~/Documents/notes/dev/dotfiles-architecture.md"
```

### File Structure

```
~/.config/menu/
├── config.yml                    # Main config
├── categories.yml                # Category definitions
├── registry/
│   ├── commands.yml             # Shell commands, aliases, functions
│   ├── workflows.yml            # Multi-step workflows
│   ├── learning.yml             # Learning topics
│   └── projects.yml             # Project-specific
├── sessions/
│   ├── sessions-macos.yml
│   └── sessions-wsl.yml
└── keybindings.yml

~/dotfiles/common/.local/bin/
├── menu                          # Main menu
├── sess                          # Session manager (was menu-sessions)
├── learn                         # Learning resource manager
└── notes                         # Enhanced notes script

~/Documents/notes/                # Obsidian vault
├── inbox/                        # New notes
├── dailies/                      # Daily notes
├── dev/                          # Development notes
│   ├── workflows/               # Workflow documentation
│   ├── learning/                # Active learning
│   └── reference/               # Quick reference
├── templates/                    # Obsidian templates
└── .obsidian/                    # Obsidian config
```

---

## Component Design

### 1. Main Menu (`menu`)

**Navigation:**
```
Universal Menu
─────────────────────────────────
Quick Access
  s → Sessions
  t → Tasks (current project)
  n → Notes

Shell Reference
  c → Commands & Aliases
  g → Git Workflows
  f → File Operations

Neovim
  v → Vim Workflows
  k → Keybindings
  m → Motions & Tips

Learning
  l → Active Learning Topics
  r → Reading List

Projects
  p → Project Menu

✕ → Quit
```

**Single-key navigation from main menu** (like you requested):
- `prefix + m` opens menu
- `s` jumps to sessions
- `t` jumps to tasks
- `v` jumps to vim workflows
- etc.

### 2. Session Manager (`sess`)

**Usage:**
```bash
sess                    # List all sessions (gum chooser)
sess dotfiles          # Create or switch to "dotfiles" session
sess last              # Switch to last session
sess list              # List with details
sess kill old-project  # Kill session
sess defaults          # Show platform defaults
```

**Features:**
- Integrates tmux sessions + tmuxinator projects + default sessions
- Shows context (windows, panes, activity)
- Can launch tmuxinator projects
- Platform-specific defaults

**Config:**
```yaml
# ~/.config/menu/sessions/sessions-macos.yml
defaults:
  - name: dotfiles
    directory: ~/dotfiles
    description: Dotfiles development

  - name: ichrisbirch
    directory: ~/code/ichrisbirch
    tmuxinator: ichrisbirch-development
    description: Main project dev environment

  - name: monitoring
    directory: ~/code/ichrisbirch
    tmuxinator: ichrisbirch-prod-monitoring
    description: Production monitoring
```

### 3. Learning Manager (`learn`)

**Usage:**
```bash
learn                           # Browse learning topics (gum)
learn neovim                    # Show all neovim resources
learn add docker "Docker basics"  # Add new learning topic
learn bookmark <url> neovim    # Add bookmark to topic
learn note neovim              # Create note for topic
learn status                   # Show active learning
```

**Integration:**
- Uses nb for bookmarks (saves as markdown)
- Uses Obsidian for notes
- Links them together in registry

**Example topic view:**
```
Learning: Neovim Quickfix
─────────────────────────────────
Status: Active

Bookmarks (3):
  • Colder Quickfix Lists (vimways.org)
  • Vim Tips Wiki - Quickfix
  • YouTube: Mastering Quickfix

Notes (2):
  • ~/Documents/notes/dev/learning/quickfix.md
  • Practice exercises

Workflows (1):
  • Search → Quickfix → Batch Replace

Actions:
  v → View all resources
  n → Add note
  b → Add bookmark
  p → Mark as practiced
  ← Back
```

### 4. Enhanced Notes Script

**Integration with Obsidian:**
```bash
notes                  # Open notes menu (gum)
notes new              # New note from template
notes workflow         # New workflow note
notes reference        # New reference note
notes daily            # Open/create daily note
notes search <term>    # Search notes
notes vim              # Quick access to vim notes
```

**Obsidian Templates:**
```markdown
# templates/workflow.md
---
tags: [workflow, dev]
created: {{date}}
---

# {{title}}

## Purpose
What does this workflow accomplish?

## Steps
1.

## Commands/Keybindings


## Notes


## Related
-
```

### 5. Neovim Workflows Integration

**Extend existing workflows.lua:**

Add to menu registry:
```yaml
neovim_workflows:
  - name: Quickfix List Operations
    from: workflows.lua
    category: Neovim Workflows
    keybindings:
      - ":cn / :cp - Navigate"
      - ":copen - Open list"
      - ":cfdo <cmd> - Run on all"
```

**New telescope picker in menu:**
```lua
-- Accessible from menu
:Telescope workflows       -- Browse by category
:Telescope all_keymaps     -- Search all keybindings
```

---

## Implementation Phases

### Phase 2A: Core Infrastructure (Week 1)

**Tasks:**
1. Create category structure and config
2. Start registry with 20 entries:
   - 10 shell commands/aliases
   - 5 git workflows
   - 5 neovim workflows
3. Build main menu with single-key navigation
4. Integrate existing workflows.lua

**Files:**
- `~/.config/menu/config.yml`
- `~/.config/menu/categories.yml`
- `~/.config/menu/registry/commands.yml`
- `~/.config/menu/registry/workflows.yml`
- Updated `menu` script

### Phase 2B: Session Management (Week 1)

**Tasks:**
1. Build `sess` tool
2. Create platform session configs
3. Integrate tmuxinator
4. Remove sesh from tmux.conf
5. Update keybindings

**Files:**
- `~/.local/bin/sess`
- `~/.config/menu/sessions/sessions-macos.yml`
- Updated `tmux.conf`

### Phase 2C: Notes & Obsidian (Week 1)

**Tasks:**
1. Install nb (`brew install nb`)
2. Enhance notes script
3. Create Obsidian templates
4. Integrate with menu
5. Document workflow

**Files:**
- Enhanced `notes` script
- `~/Documents/notes/templates/workflow.md`
- `~/Documents/notes/templates/reference.md`
- `~/Documents/notes/templates/learning.md`

### Phase 2D: Forgit Integration (Week 1)

**Tasks:**
1. Clone forgit to `$ZSH_PLUGINS_DIR`
2. Source in zshrc
3. Add to install scripts
4. Add forgit commands to registry
5. Test git workflow

**Files:**
- `$ZSH_PLUGINS_DIR/forgit/`
- Updated `.zshrc`
- Updated install scripts

### Phase 3: Learning System (Week 2)

**Tasks:**
1. Install buku (`brew install buku`)
2. Build `learn` tool
3. Create learning registry structure
4. Integrate nb + buku + Obsidian
5. Migrate 5 learning topics

**Files:**
- `~/.local/bin/learn`
- `~/.config/menu/registry/learning.yml`
- Learning note templates

### Phase 4: Polish & Extend (Week 3)

**Tasks:**
1. Add search across all categories
2. Enhance previews
3. Add help system (`?`)
4. Create more registry entries
5. Document everything

---

## Example User Workflows

### Scenario 1: "I forget how to use quickfix lists"

**Before:** Google it, find tutorial, maybe take notes, forget again

**After:**
```bash
# In terminal
prefix + m              # Open menu
v                       # Vim workflows
[select "Quickfix"]     # See everything:
                        # - Keybindings
                        # - Step-by-step workflow
                        # - Links to tutorials
                        # - Your practice notes
```

### Scenario 2: "I want to learn Docker Compose"

**Before:** Bookmarks scattered, notes somewhere, no clear plan

**After:**
```bash
learn docker            # See learning topic with:
                        # - Bookmarked tutorials
                        # - Your study notes
                        # - Practice exercises
                        # - Related resources

# Add resources as you find them
learn bookmark https://... docker
learn note docker       # Opens Obsidian note
```

### Scenario 3: "Switch to my dev session"

**Before:** `tmux attach -t ichrisbirch` or complex sesh command

**After:**
```bash
sess                    # Gum list of all sessions
# OR
sess ichrisbirch       # Direct switch
# OR
prefix + m, s          # From tmux
```

### Scenario 4: "What's that git command for interactive staging?"

**Before:** Google or try to remember forgit

**After:**
```bash
prefix + m             # Open menu
g                      # Git workflows
[type "stag"]         # Fuzzy search
# Shows: ga - forgit interactive git add
#        gd - forgit interactive diff
#        etc.
```

---

## Migration Strategy

### From Current Setup

1. **Keep existing ls functions** - Add note at bottom: "See `menu` for full interface"
2. **Keep existing workflows.lua** - Integrate, don't replace
3. **Keep Obsidian setup** - Just make it easier to use
4. **Build incrementally** - Start with 20 entries, grow over time

### Adding Content

**High Priority (First 20 entries):**
- Your most-forgotten commands
- Git workflows you use daily
- Neovim workflows from workflows.lua
- Common file operations

**As You Go:**
- When you Google something → add to learning
- When you forget a command → add to registry
- When you learn something → document it

**Learning Topics to Start:**
- Neovim quickfix/location lists
- Docker/Docker Compose
- AWS services you use
- Anything from YouTube tutorials

---

## Success Criteria

### Phase 2A Complete:
- ✓ Menu with single-key navigation
- ✓ 20 registry entries across categories
- ✓ Neovim workflows integrated
- ✓ Search working

### Phase 2B Complete:
- ✓ `sess` command working
- ✓ All session sources integrated
- ✓ Sesh removed
- ✓ Keybindings updated

### Phase 2C Complete:
- ✓ nb installed and configured
- ✓ Obsidian workflow streamlined
- ✓ Notes easily accessible from menu
- ✓ Using it daily

### Phase 3 Complete:
- ✓ `learn` tool working
- ✓ 5 learning topics documented
- ✓ buku integrated
- ✓ Actually taking notes

---

## Open Questions

1. **nb vs Obsidian?**
   - Keep both: nb for bookmarks, Obsidian for notes
   - Link between them in registry
   - nb can work inside Obsidian vault

2. **How to handle "to-watch" videos?**
   - Tag in buku: `buku -a <url> youtube to-watch learning-docker`
   - Separate learning status: "planned", "in-progress", "completed"

3. **Registry maintenance?**
   - Edit YAML directly (no CLI tool)
   - Version control with git
   - Keep it curated (quality over quantity)

4. **Platform differences?**
   - Common registry shared
   - Platform overlays for specific commands
   - Use `platform: macos` field in entries

---

## Tools Decision Matrix

| Tool | Purpose | Install | Use Case |
|------|---------|---------|----------|
| nb | Bookmarks, quick notes | `brew install nb` | Saving web resources |
| buku | Bookmark manager | `brew install buku` | Organizing bookmarks with tags |
| Obsidian | Long-form notes | Already have | Study notes, learning plans |
| forgit | Interactive git | Manual clone | Git workflows |
| gum | Menu UI | Already have | Beautiful menus |
| fzf | Fuzzy finding | Already have | Search, selection |
| yazi | File browsing | Already have | Notes file navigation |

---

## Next Steps

1. ✓ Review this plan
2. Create Phase 2A structure:
   - config.yml
   - categories.yml
   - Initial registry entries
3. Build basic menu with single-key nav
4. Integrate workflows.lua
5. Test and iterate

Then we build incrementally from there!
