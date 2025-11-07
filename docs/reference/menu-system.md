# Universal Menu System

The universal menu system is a function-based knowledge and workflow management tool that organizes information by *what you're trying to accomplish* rather than by type (bookmarks, notes, commands, etc.).

## Philosophy

Instead of organizing by type:
```
Bookmarks/ → Notes/ → Aliases/ → Functions/
```

Organize by function:
```
Learning: Neovim/
├── Tutorials (bookmarks)
├── Study notes
├── Workflows & keybindings
└── Practice exercises
```

When you search for "quickfix", you get ALL resources about quickfix: bookmarks, notes, keybindings, and workflows in one place.

## Components

### Main Menu (`menu`)

The primary interface for accessing all your knowledge and tools.

**Opening the Menu:**
```bash
menu              # From terminal
prefix + m        # From tmux (Ctrl-Space + m)
```

**Single-Key Navigation:**
- `s` → Sessions (tmux/tmuxinator)
- `t` → Tasks (current project)
- `n` → Notes (Obsidian)
- `c` → Commands & Aliases
- `g` → Git Workflows
- `f` → File Operations
- `v` → Vim Workflows
- `k` → Vim Keybindings
- `l` → Learning Topics

**Features:**
- Context-aware (shows project tasks if in git repo)
- Loop navigation (back and forth between categories)
- Beautiful gum-based UI
- Detailed previews with examples and notes

### Session Manager (`sess`)

Simple and fast tmux session management that replaces sesh.

**Usage:**
```bash
sess                # Interactive list of all sessions
sess <name>         # Create or switch to session
sess last           # Switch to last session
sess defaults       # Show default sessions
sess kill <name>    # Kill a session
```

**What It Shows:**
- Active tmux sessions
- Tmuxinator projects
- Default sessions (configured per platform)

**Default Sessions:**

Configured in `~/.config/menu/sessions/sessions-macos.yml`:
```yaml
defaults:
  - name: dotfiles
    directory: ~/dotfiles
    description: Dotfiles development

  - name: ichrisbirch-dev
    directory: ~/code/ichrisbirch
    tmuxinator_project: ichrisbirch-development
    description: Main project development
```

### Knowledge Registry

Three YAML files that store all your knowledge:

**1. Commands Registry** (`~/.config/menu/registry/commands.yml`)

Shell commands, aliases, functions, and tools.

```yaml
- name: fcd
  type: function
  category: File Operations
  description: Fuzzy find directory and cd into it
  keywords: [navigate, directory, find, cd, fzf]
  command: fcd [directory]
  examples:
    - command: fcd ~/code
      description: Search for directories in ~/code
  notes: |
    Uses fzf with preview. Respects .gitignore.
  related: [fd, fzf, z]
  platform: all
```

**2. Workflows Registry** (`~/.config/menu/registry/workflows.yml`)

Multi-step processes and techniques.

```yaml
- name: Quickfix List - Search and Replace
  category: Vim Workflows
  description: Search entire repo, send to quickfix, batch replace
  keywords: [search, replace, quickfix, batch]
  steps:
    - key: "<leader>fg"
      description: "Live grep to search repo"
    - key: "<C-q>"
      description: "Send results to quickfix list"
  notes: |
    Incredibly powerful for repo-wide refactoring.
```

**3. Learning Registry** (`~/.config/menu/registry/learning.yml`)

Active learning topics with bookmarks, notes, and exercises.

```yaml
- name: Neovim Quickfix Lists
  category: Learning Topics
  status: active
  description: Master quickfix lists for batch operations
  resources:
    bookmarks:
      - url: "https://vim.fandom.com/wiki/Quickfix"
        title: "Vim Tips Wiki"
        tags: [reference]
    notes:
      - path: "~/Documents/notes/dev/learning/neovim-quickfix.md"
  practice_exercises:
    - "Search for all TODOs, replace with DONE"
```

## File Structure

```
~/.config/menu/
├── config.yml              # Main configuration
├── categories.yml          # Category definitions
├── registry/
│   ├── commands.yml        # Commands, aliases, functions
│   ├── workflows.yml       # Multi-step processes
│   └── learning.yml        # Learning topics
└── sessions/
    └── sessions-macos.yml  # Default sessions

~/dotfiles/                 # Source files (version controlled)
└── common/.config/menu/    # Same structure (symlinked)
```

## Adding Content

### Add a Command

Edit `~/.config/menu/registry/commands.yml`:

```yaml
- name: my-command
  type: function
  category: Commands
  description: What it does
  keywords: [search, terms]
  command: the command
  examples:
    - command: example usage
      description: what this does
  notes: |
    Additional context
  related: [other, commands]
  platform: all
```

### Add a Workflow

Edit `~/.config/menu/registry/workflows.yml`:

```yaml
- name: My Workflow
  category: Vim Workflows
  description: Step-by-step process
  keywords: [relevant, keywords]
  steps:
    - key: "<leader>something"
      description: "What this step does"
  notes: |
    When to use this workflow
```

### Add a Learning Topic

Edit `~/.config/menu/registry/learning.yml`:

```yaml
- name: New Topic
  category: Learning Topics
  status: active  # or planned, completed
  description: What you're learning
  keywords: [topic, keywords]
  resources:
    bookmarks:
      - url: "https://..."
        title: "Tutorial Name"
        tags: [tutorial, video]
        status: to-read
    notes:
      - path: "~/Documents/notes/dev/topic.md"
        description: "My study notes"
  practice_exercises:
    - "Exercise to practice"
```

### Add a Default Session

Edit `~/.config/menu/sessions/sessions-macos.yml`:

```yaml
- name: my-project
  directory: ~/code/my-project
  description: Project description
  tmuxinator_project: null  # or tmuxinator project name
  windows:  # if not using tmuxinator
    - name: main
      panes:
        - nvim
```

## Common Workflows

### "I Forget a Command"

```bash
menu              # Open menu
c                 # Commands
[select or search]  # Find the command
# See: description, examples, notes, related commands
```

### "How Do I Do This in Vim?"

```bash
menu              # Open menu
v                 # Vim Workflows
[select workflow]   # See step-by-step process
```

### "What Am I Learning?"

```bash
menu              # Open menu
l                 # Learning Topics
[select topic]    # See all resources, notes, exercises
```

### "Switch to Dev Session"

```bash
sess              # Interactive menu
# OR
sess dotfiles     # Direct switch
```

## Best Practices

### Growing Your Registry

**Start small:**
- Only add things you actually forget
- Quality over quantity

**Add as you go:**
- When you Google something → add it
- When you learn a workflow → document it
- When you struggle with something → add it

**Link related items:**
- Use the `related` field to connect commands
- Reference workflows in learning topics

### Using Categories

**Commands:**
- Shell commands, aliases, functions
- Tools with usage examples

**Git Workflows:**
- Git commands
- Forgit interactive commands
- Git techniques

**Vim Workflows:**
- Multi-step Neovim processes
- Editor techniques

**Learning Topics:**
- Active learning projects
- Resources organized by topic
- Practice exercises

## Integrated Tools

### nb - Notes and Bookmarks

CLI tool for plain-text notes and bookmarks:

```bash
nb                          # List notes
nb add                      # Create note
nb bookmark <url>           # Save bookmark (downloads & cleans)
nb search <term>            # Full-text search
nb tag note learning        # Add tags
nb learning:               # Filter by tag
```

**Features:**
- Plain text, markdown-based
- Git-backed versioning
- Bookmarks → markdown
- [[Wiki-links]] between notes

### buku - Bookmark Manager

SQLite-backed bookmark manager:

```bash
buku -a <url> <tags>        # Add bookmark
buku -s <tag>               # Search by tag
buku -p -f 10 | fzf         # Fuzzy search
```

**fzf Integration:**
```bash
# Fuzzy search and open
firefox $(buku -p -f 10 | fzf | awk '{print $1}' | xargs buku -p | grep http | awk '{print $2}')
```

### forgit - Interactive Git

All forgit commands are in the Git Workflows category:

- `ga` - Interactive git add
- `gd` - Interactive git diff
- `glo` - Interactive git log
- `gcf` - Interactive checkout file
- `gss` - Interactive stash show
- `gclean` - Interactive git clean

## Configuration

### Main Config (`~/.config/menu/config.yml`)

```yaml
menu:
  height: 20
  preview_enabled: true
  search_enabled: true

tools:
  gum: gum
  fzf: fzf
  nb: nb
  buku: buku
  bat: bat

notes:
  directory: ~/Documents/notes
  editor: nvim
  obsidian_vault: ~/Documents/notes

sessions:
  default_directory: ~
  tmuxinator_enabled: true
```

### Categories (`~/.config/menu/categories.yml`)

```yaml
categories:
  - name: Sessions
    key: s
    icon: "🪟"
    description: Tmux sessions and tmuxinator projects
    type: quick_access
    priority: 1
```

## Tips

### Keyboard Shortcuts

**In Menu:**
- Arrow keys or j/k: Navigate
- Enter: Select
- Esc or Ctrl-C: Back/Quit

**In Tmux:**
- `Ctrl-Space + m`: Open menu
- `Ctrl-Space + R`: Reload tmux config

### Adding Lots of Content

When documenting a complex workflow:
1. Use the menu to find a similar example
2. Copy the YAML structure
3. Fill in your specific details
4. Keep notes concise but informative

### Searching

All YAML files support full-text search:
```bash
rg "quickfix" ~/.config/menu/registry/
```

## Troubleshooting

**Menu not found:**
```bash
which menu
# If not found:
task symlinks:link
```

**Config not found:**
```bash
ls ~/.config/menu/
# If not found:
task symlinks:link
```

**Sess not working:**
```bash
which sess
# Check tmux is running:
tmux info
```

## See Also

- [Tools Discovery](./tools.md) - CLI tools registry
- [Session Management](../configuration/tmux.md) - Tmux configuration
- [Symlinks](./symlinks.md) - Dotfiles deployment
