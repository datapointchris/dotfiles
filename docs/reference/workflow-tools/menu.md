# Menu System

The menu system provides instant access to your accumulated knowledge by organizing everything around what you're trying to accomplish rather than by type. Instead of hunting through bookmarks, notes, aliases, and functions separately, search for "quickfix" and get all resources about quickfix in one place.

## Why Menu Exists

Traditional knowledge management scatters information across tools. You bookmark a tutorial, write notes separately, save commands in aliases, and document workflows elsewhere. When you need information later, you check four different places hoping one has what you need.

Menu organizes by function instead. Learning Neovim? All tutorials, study notes, workflows, and keybindings live together under "Learning: Neovim". This mirrors how your brain works - you think "how do I batch replace files?" not "was that in my bookmarks or notes?"

## Opening the Menu

Launch menu from your terminal or directly from tmux:

```bash
menu              # From terminal
prefix + m        # From tmux (Ctrl-Space + m)
```

The menu opens with single-key navigation. No typing required for common tasks. Press a key, select what you need, done.

## Navigation

Menu uses single-key shortcuts for instant access:

- `s` - Sessions (tmux/tmuxinator)
- `t` - Tasks (current project)
- `n` - Notes (zk)
- `c` - Commands & Aliases
- `g` - Git Workflows
- `f` - File Operations
- `v` - Vim Workflows
- `k` - Vim Keybindings
- `l` - Learning Topics

Press a key to jump to that category. Select an item to see detailed information with examples and notes. Navigate back and forth between categories using the menu's loop navigation.

## Session Management

The session manager (`sess`) replaces complex session management with simple commands. Press `s` in menu or run `sess` directly for interactive session selection.

Start or switch to any session by name:

```bash
sess dotfiles     # Switch to dotfiles session
sess <name>       # Create or switch to any session
sess last         # Jump back to previous session
```

The interactive list shows three types of sessions with visual indicators:

- Active tmux sessions (●)
- Tmuxinator projects (⚙)
- Default sessions (○)

Default sessions come from `~/.config/sess/sessions-macos.yml` and define your common workspaces:

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

When you switch to a default session that isn't running, sess creates it in the specified directory. If a tmuxinator project is configured, sess starts that instead. This lets you define complex multi-window layouts for major projects while keeping simple single-window sessions for quick tasks.

See [Session Management](session.md) for complete details.

## Knowledge Registry

Menu stores knowledge in three YAML files organized by purpose. Commands hold tools and functions you use. Workflows capture multi-step processes. Learning topics organize study resources.

### Commands Registry

Store shell commands, aliases, functions, and tools in `~/.config/menu/registry/commands.yml`:

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

Each entry captures what the command does, how to use it, when it's useful, and what other commands relate to it. The `notes` field explains context that examples can't convey.

### Workflows Registry

Multi-step processes live in `~/.config/menu/registry/workflows.yml`:

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

Workflows document techniques you've learned but might forget. The step-by-step format reminds you of the exact sequence without re-reading tutorials.

### Learning Registry

Active learning topics organize all resources in one place in `~/.config/menu/registry/learning.yml`:

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

Learning topics capture the "what I'm studying" mindset. Bookmark a tutorial, link your study notes, define practice exercises. Everything related to learning that topic lives together.

## Adding Content

Edit the YAML files directly to add knowledge. The files live at `~/.config/menu/registry/` (symlinked from your dotfiles repo for version control).

### Add a Command

Open `~/.config/menu/registry/commands.yml` and add an entry:

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

The `keywords` field makes searching effective. The `related` field helps discover connected tools. The `notes` field captures why this command exists or when to use it instead of alternatives.

### Add a Workflow

Open `~/.config/menu/registry/workflows.yml`:

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

Document workflows when you Google "how to do X" and finally figure it out. Future you will thank you for capturing the exact steps.

### Add a Learning Topic

Open `~/.config/menu/registry/learning.yml`:

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

Start new topics when you commit to learning something. Capture resources as you find them. Add exercises to reinforce learning.

### Add a Default Session

Edit `~/.config/sess/sessions-macos.yml` to define default sessions:

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

Default sessions let you define workspaces without requiring tmuxinator. For simple projects, just set the directory. For complex setups, reference a tmuxinator project.

## Common Workflows

### Finding a Forgotten Command

Open menu and navigate to Commands. Search or select to find the command. Menu shows description, examples, notes, and related commands all in one place.

```bash
menu              # Open menu
c                 # Commands category
# Select or search for command
# See full details with examples
```

### Learning a Vim Technique

Navigate to Vim Workflows to see documented multi-step processes. Each workflow shows the exact sequence of keys to press and explains when to use it.

```bash
menu              # Open menu
v                 # Vim Workflows
# Select workflow
# See step-by-step instructions
```

### Reviewing Active Learning

Check Learning Topics to see what you're currently studying. Each topic shows all resources, notes, and exercises in one organized view.

```bash
menu              # Open menu
l                 # Learning Topics
# Select topic
# See all resources and progress
```

### Starting a Work Session

Use the session manager to switch to your development environment. Sess shows active sessions, available tmuxinator projects, and configured defaults.

```bash
sess              # Interactive selection
# OR
sess dotfiles     # Direct switch by name
```

## Best Practices

Start small when building your registry. Only add things you actually forget. If you use a command every day, it doesn't need documentation. If you Google it monthly, add it to menu.

Add knowledge as you encounter it. When you Google something and find the answer, add it immediately. When you learn a new workflow, document it while it's fresh. When you struggle with something, capture why and how you solved it.

Link related items using the `related` field. This creates a web of knowledge where finding one thing helps you discover connected concepts. Reference workflows in learning topics to connect theory with practice.

## Integrated Tools

Menu integrates with zk for note-taking. Create notes directly from menu or use zk commands:

```bash
zk journal "Daily standup"     # Create journal entry
zk devnote "Bug fix notes"     # Create dev note
zk list --match "API"          # Search notes
zk edit --interactive          # Browse and edit
notes                          # Quick menu wrapper
```

See [Notes System](notes.md) for complete zk documentation.

Git workflows use forgit for interactive operations. All forgit commands appear in the Git Workflows category:

- `ga` - Interactive git add
- `gd` - Interactive git diff
- `glo` - Interactive git log
- `gcf` - Interactive checkout file
- `gss` - Interactive stash show
- `gclean` - Interactive git clean

## File Structure

Menu configuration lives in `~/.config/menu/` (symlinked from your dotfiles):

```text
~/.config/menu/
├── config.yml              # Main configuration
├── categories.yml          # Category definitions
└── registry/
    ├── commands.yml        # Commands, aliases, functions
    ├── workflows.yml       # Multi-step processes
    └── learning.yml        # Learning topics

~/.config/sess/
└── sessions-macos.yml      # Default sessions
```

The source files live in `~/dotfiles/platforms/common/.config/menu/` under version control. Run `task symlinks:link` after editing to update symlinks.

## Configuration

Main config at `~/.config/menu/config.yml` controls menu behavior:

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

notes:
  directory: ~/notes
  editor: nvim

sessions:
  default_directory: ~
  tmuxinator_enabled: true
```

Categories are defined in `~/.config/menu/categories.yml`:

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

Use keyboard shortcuts consistently. In menu, arrow keys or j/k navigate, Enter selects, Esc or Ctrl-C goes back. In tmux, Ctrl-Space + m opens menu, Ctrl-Space + R reloads config.

When documenting complex workflows, find a similar example in menu first. Copy the YAML structure and fill in your details. This keeps formatting consistent and reminds you of available fields.

Search YAML files directly when you need to update multiple entries:

```bash
rg "quickfix" ~/.config/menu/registry/
```

## Troubleshooting

If menu command is not found, verify it's symlinked correctly:

```bash
which menu
# If not found:
task symlinks:link
```

If config files are missing:

```bash
ls ~/.config/menu/
# If not found:
task symlinks:link
```

If sess is not working:

```bash
which sess
# Check tmux is running:
tmux info
```

## See Also

- [Session Management](session.md) - Complete sess reference
- [Tool Discovery](toolbox.md) - Tool registry system
- [Notes System](notes.md) - zk note-taking workflow
- [Symlinks](/reference/symlinks.md) - Dotfiles deployment
