# Menu

Knowledge management system organizing commands, workflows, and learning topics by function rather than type. Quick access to accumulated knowledge through single-key navigation.

## Quick Start

```bash
menu              # Launch menu
prefix + m        # From tmux (Ctrl-Space + m)
```

Single-key navigation:

- `s` - Sessions (tmux/tmuxinator)
- `t` - Tasks (current project)
- `n` - Notes (zk)
- `c` - Commands & Aliases
- `g` - Git Workflows
- `f` - File Operations
- `v` - Vim Workflows
- `k` - Vim Keybindings
- `l` - Learning Topics

## How It Works

Menu organizes knowledge by what you're trying to accomplish. Instead of hunting through bookmarks, notes, aliases, and functions separately, search for a topic and get all related resources in one place.

The system stores knowledge in three YAML files at `~/.config/menu/registry/`:

- `commands.yml` - Shell commands, aliases, functions, tools
- `workflows.yml` - Multi-step processes
- `learning.yml` - Learning topics with resources

### Commands Registry

Store tools and functions with examples:

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

Each entry captures what the command does, how to use it, when it's useful, and what other commands relate to it.

### Workflows Registry

Document multi-step processes:

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

Workflows capture techniques you've learned but might forget. The step-by-step format reminds you of the exact sequence.

### Learning Registry

Active learning topics organize all resources in one place:

```yaml
- name: Neovim Quickfix Lists
  category: Learning Topics
  status: active  # active, planned, completed
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

Learning topics capture the "what I'm studying" mindset. Everything related to learning that topic lives together.

## Adding Content

Edit YAML files directly at `~/.config/menu/registry/` (symlinked from dotfiles).

Add a command:

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

Add a workflow:

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

Add a learning topic:

```yaml
- name: New Topic
  category: Learning Topics
  status: active
  description: What you're learning
  resources:
    bookmarks:
      - url: "https://..."
        title: "Tutorial Name"
        tags: [tutorial]
    notes:
      - path: "~/Documents/notes/topic.md"
  practice_exercises:
    - "Exercise to practice"
```

## Configuration

**Main config:** `~/.config/menu/config.yml`

```yaml
menu:
  height: 20
  preview_enabled: true
  search_enabled: true

tools:
  gum: gum
  fzf: fzf
  zk: zk
  bat: bat
```

**Categories:** `~/.config/menu/categories.yml`

**File structure:**

```text
~/.config/menu/
├── config.yml              # Main configuration
├── categories.yml          # Category definitions
└── registry/
    ├── commands.yml        # Commands, aliases, functions
    ├── workflows.yml       # Multi-step processes
    └── learning.yml        # Learning topics
```

Source files live in `~/dotfiles/platforms/common/.config/menu/` under version control. Run `task symlinks:link` after editing.

## Integrated Tools

**Session Management:**

```bash
sess              # Interactive selection
sess dotfiles     # Direct switch by name
sess last         # Jump to previous session
```

See [Session Manager](sess.md) for details.

**Notes:**

```bash
notes             # Quick menu wrapper
zk journal "..."  # Create journal entry
zk devnote "..."  # Create dev note
```

See [Notes](notes.md) for details.

## Workflow

Find a forgotten command:

```bash
menu              # Open menu
c                 # Commands category
# Search or select command
# See details with examples
```

Learn a Vim technique:

```bash
menu              # Open menu
v                 # Vim Workflows
# Select workflow
# See step-by-step instructions
```

Review active learning:

```bash
menu              # Open menu
l                 # Learning Topics
# Select topic
# See resources and progress
```

## Best Practices

Add knowledge as you encounter it. When you Google something and find the answer, add it immediately. When you learn a new workflow, document it while it's fresh.

Only add things you actually forget. If you use a command every day, it doesn't need documentation. If you Google it monthly, add it to menu.

Link related items using the `related` field. This creates a web of knowledge where finding one thing helps you discover connected concepts.

## Troubleshooting

**Menu command not found**: Verify symlink with `which menu`. If not found, run `task symlinks:link`.

**Config files missing**: Check `ls ~/.config/menu/`. If missing, run `task symlinks:link`.

**Search YAML directly**: Use `rg "keyword" ~/.config/menu/registry/` to find and update entries.

## See Also

- [Session Manager](sess.md) - Complete sess reference
- [Toolbox](toolbox.md) - Tool registry system
- [Notes](notes.md) - zk note-taking workflow
- [Symlinks](../reference/symlinks.md) - Dotfiles deployment
