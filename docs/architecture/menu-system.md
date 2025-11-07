# Universal Menu System - Architecture

The universal menu system represents a fundamental shift in personal knowledge management - organizing information by function (what you're trying to accomplish) rather than by type (command, bookmark, note).

## Design Principles

### 1. Function Over Type

**Problem:** Traditional organization by type creates artificial barriers.

When learning Neovim quickfix lists, you have:

- Bookmarked tutorials (in browser)
- YouTube videos (in bookmarks)
- Study notes (in Obsidian)
- Keybindings (in Neovim config)
- Example workflows (scattered)

To access this knowledge, you search across 5 different systems.

**Solution:** Organize by what you're learning.

```
Learning: Neovim Quickfix/
├── Tutorials (bookmarks)
├── Videos (bookmarks with tags)
├── Study notes (Obsidian)
├── Keybindings (workflows)
└── Practice exercises
```

Now one search gives you everything about quickfix lists.

### 2. Single Source of Truth

All knowledge lives in version-controlled YAML files in your dotfiles:

- `commands.yml` - What commands do and when to use them
- `workflows.yml` - How to accomplish multi-step tasks
- `learning.yml` - What you're learning and all related resources

No duplicate information. No scattered notes. One place to search.

### 3. Progressive Disclosure

Start with a simple list, drill down for details:

```
Menu (10 categories)
  ↓
Commands (13 entries)
  ↓
fcd → Fuzzy find directory
  ↓
[Full details: description, examples, notes, related commands]
```

Only load what you need, when you need it.

## System Components

### Core Components

```
┌─────────────────────────────────────────────┐
│              User Interface                  │
│  ┌────────┐ ┌────────┐ ┌──────────────┐    │
│  │  menu  │ │  sess  │ │ notes (future)│   │
│  └───┬────┘ └───┬────┘ └──────┬───────┘    │
└──────┼──────────┼─────────────┼────────────┘
       │          │              │
┌──────┼──────────┼──────────────┼────────────┐
│      │   Configuration Layer   │            │
│  ┌───▼────────────────────┐ ┌──▼─────────┐ │
│  │  Registry YAML Files   │ │  Sessions  │ │
│  │ • commands.yml         │ │  Config    │ │
│  │ • workflows.yml        │ └────────────┘ │
│  │ • learning.yml         │                 │
│  └────────────────────────┘                 │
└─────────────────────────────────────────────┘
       │
┌──────┼─────────────────────────────────────┐
│      │      Tool Integration               │
│  ┌───▼────┐ ┌──────┐ ┌──────┐ ┌─────────┐ │
│  │  gum   │ │  nb  │ │ buku │ │ forgit  │ │
│  └────────┘ └──────┘ └──────┘ └─────────┘ │
│  ┌─────────┐ ┌────────────┐ ┌────────────┐│
│  │   fzf   │ │  Obsidian  │ │ tmuxinator ││
│  └─────────┘ └────────────┘ └────────────┘│
└─────────────────────────────────────────────┘
```

### Data Flow

**Opening a command:**

```
User presses: menu → c → fcd
  ↓
menu script parses commands.yml
  ↓
Extracts all command entries
  ↓
Displays list with gum choose
  ↓
User selects "fcd"
  ↓
Extracts fcd details from YAML
  ↓
Displays with gum pager:
  - Description
  - Examples
  - Notes
  - Related commands
```

**Session switching:**

```
User runs: sess
  ↓
sess gathers from 3 sources:
  1. Active tmux sessions
  2. Tmuxinator projects
  3. Default sessions (YAML)
  ↓
Displays combined list with gum
  ↓
User selects session
  ↓
sess determines type and:
  - Tmux: switch with tmux switch-client
  - Tmuxinator: launch with tmuxinator start
  - Default: create from YAML config
```

## Registry Schema

### Command Entry

```yaml
- name: string (required)
  type: enum [alias, function, system_tool, script, forgit_alias]
  category: string (required)
  description: string (required, 1-2 sentences)
  keywords: array[string] (required, for searching)
  command: string (the actual command)
  examples:
    - command: string
      description: string
  notes: string (multiline, optional)
  related: array[string] (related command names)
  provided_by: string (e.g., "forgit", "fzf")
  use_tldr: boolean (show tldr if available)
  platform: enum [all, macos, linux, wsl]
```

**Example:**

```yaml
- name: rg
  type: system_tool
  category: Commands
  description: Ripgrep - blazing fast recursive grep
  keywords: [search, grep, find, text, fast]
  command: rg [pattern] [path]
  use_tldr: true
  examples:
    - command: rg 'TODO' --type py
      description: Find TODOs in Python files
  notes: |
    Much faster than grep. Respects .gitignore by default.
    Use --type to filter by file type.
  related: [grep, fd]
  platform: all
```

### Workflow Entry

```yaml
- name: string (required)
  category: string (required)
  description: string (required)
  keywords: array[string] (required)
  steps:  # for sequential workflows
    - key: string
      description: string
  techniques:  # for alternative approaches
    - name: string
      key: string
      when: string
  keybindings:  # related keybindings
    - key: string
      description: string
  notes: string (multiline)
  related_workflows: array[string]
  platform: enum [all, macos, linux, wsl]
```

**Example:**

```yaml
- name: Quickfix List - Search and Replace
  category: Vim Workflows
  description: Search entire repo, send to quickfix, batch replace
  keywords: [search, replace, quickfix, batch, grep]
  steps:
    - key: "<leader>fg"
      description: "Live grep to search repo"
    - key: "<C-q>"
      description: "Send results to quickfix list"
    - key: ":cdo s/old/new/g"
      description: "Replace in all quickfix entries"
    - key: ":cfdo update"
      description: "Save all modified files"
  keybindings:
    - key: ":cn"
      description: "Next quickfix item"
    - key: ":copen"
      description: "Open quickfix window"
  notes: |
    Incredibly powerful for repo-wide refactoring.
    The quickfix list persists until you replace it.
  platform: all
```

### Learning Topic Entry

```yaml
- name: string (required)
  category: string (usually "Learning Topics")
  status: enum [planned, active, paused, completed]
  description: string (required)
  keywords: array[string] (required)
  progress:
    started: date
    last_practiced: date
    confidence: enum [beginner, intermediate, advanced]
  resources:
    bookmarks:
      - url: string
        title: string
        tags: array[string]
        status: enum [to-read, reading, completed, reference]
    notes:
      - path: string (~/Documents/notes/...)
        description: string
    videos:
      - url: string
        title: string
        tags: array[string]
        status: enum [to-watch, watching, completed]
        duration: string
  practice_exercises: array[string]
  related_workflows: array[string]
  platform: enum [all, macos, linux, wsl]
```

## Session Management Architecture

### Session Sources

`sess` aggregates three sources:

**1. Active Tmux Sessions:**

```bash
tmux list-sessions -F "#{session_name}:#{session_windows}"
```

**2. Tmuxinator Projects:**

```bash
tmuxinator list | tail -n +2
```

**3. Default Sessions (YAML):**

```yaml
defaults:
  - name: dotfiles
    directory: ~/dotfiles
    tmuxinator_project: null
    windows:
      - name: main
        panes: [nvim]
```

### Session Creation Logic

```
User selects: "dotfiles"
  ↓
Check: Is there a tmuxinator project?
  Yes → tmuxinator start dotfiles
  No ↓
Check: Is it in defaults YAML?
  Yes → Create from YAML config
  No ↓
Create simple tmux session
```

### Platform-Specific Sessions

Sessions can vary by platform:

**macOS:**

```yaml
# ~/.config/menu/sessions/sessions-macos.yml
- name: ichrisbirch-dev
  tmuxinator_project: ichrisbirch-development
```

**WSL:**

```yaml
# ~/.config/menu/sessions/sessions-wsl.yml
- name: work-project
  directory: /mnt/c/projects/work
  windows: [...]
```

## Tool Integration

### Forgit

Interactive git commands integrated into registry:

```yaml
- name: ga
  type: forgit_alias
  category: Git Workflows
  provided_by: forgit
  description: Interactive git add with preview
```

**Installation:**

1. Defined in `config/packages.yml`
2. Cloned via `task shell:install` to `~/.config/zsh/plugins/forgit`
3. Sourced in `.zshrc`
4. Commands added to registry

### nb (Notes & Bookmarks)

Plain-text notes and bookmarks:

```bash
nb bookmark https://example.com "Docker Tutorial" learning,docker,to-read
  ↓
Downloads and converts to markdown
  ↓
Saves as: ~/Documents/notes/bookmarks/example-com.md
  ↓
Can be referenced in learning registry:
resources:
  bookmarks:
    - path: bookmarks/example-com.md
```

### Obsidian

Notes are stored in Obsidian vault but can be referenced from anywhere:

```yaml
learning:
  - name: Neovim
    resources:
      notes:
        - path: "~/Documents/notes/dev/neovim-study.md"
```

## Future Enhancements

### Phase 3: Enhanced Notes Management

```bash
notes workflow quickfix    # Create workflow note
notes reference docker     # Create reference note
notes daily                # Open daily note
```

**Templates:**

- `workflow.md` - Multi-step processes
- `reference.md` - Quick reference guides
- `learning.md` - Learning resources

### Phase 4: Learning Manager

```bash
learn                      # Browse topics
learn neovim              # Show all neovim resources
learn add docker          # Add new topic
learn bookmark <url> docker  # Add bookmark to topic
learn note docker          # Create note for topic
```

**Integration:**

- Uses nb for bookmarks
- Uses Obsidian for notes
- Links everything in learning.yml

### Phase 5: Search & Discovery

```bash
menu search "quickfix"     # Search all registries
menu recent                # Recently accessed items
menu suggest               # Suggest related content
```

## Implementation Details

### YAML Parsing

Menu uses basic YAML parsing with fallback:

```bash
# Prefer yq if available
if command -v yq &>/dev/null; then
  yq eval ".commands[].name" commands.yml
else
  # Fallback to grep/sed
  grep "^  - name:" commands.yml | sed 's/.*name: //'
fi
```

### Error Handling

Graceful degradation:

```bash
if [[ ! -f "$registry" ]]; then
  gum style --foreground 196 "Registry not found: $registry"
  read -n 1 -s -r -p "Press any key to go back..."
  return
fi
```

### Context Detection

Menu adapts to current environment:

```bash
is_in_git_repo() {
  git rev-parse --is-inside-work-tree &>/dev/null
}

has_taskfile() {
  is_in_git_repo && [[ -f "$(git rev-parse --show-toplevel)/Taskfile.yml" ]]
}

# Show Tasks category only if in project with Taskfile
if has_taskfile; then
  categories+=("t → Tasks")
fi
```

## Best Practices

### Registry Maintenance

**Do:**

- Add commands you actually forget
- Document pain points you've struggled with
- Link related items together
- Keep descriptions concise but informative
- Update as you learn more

**Don't:**

- Add every possible command (quality > quantity)
- Copy entire man pages (link to tldr instead)
- Duplicate information across registries
- Leave TODOs or incomplete entries

### Workflow Documentation

**Good workflow:**

```yaml
- name: Quickfix List - Search and Replace
  steps:
    - key: "<leader>fg"
      description: "Live grep"
    - key: "<C-q>"
      description: "Send to quickfix"
  notes: |
    Use this for repo-wide refactoring.
    Example: Rename a function across all files.
```

**Bad workflow:**

```yaml
- name: Use quickfix
  description: For searching
  notes: It's useful
```

### Learning Topic Management

**Active learning:**

```yaml
- name: Docker Compose
  status: active
  resources:
    bookmarks: [tutorials...]
    notes: [study-guide.md]
  practice_exercises:
    - "Create multi-service app"
    - "Add healthchecks"
```

**Completed learning:**

```yaml
- name: Git Basics
  status: completed
  resources:
    notes: [git-reference.md]  # Keep as reference
  practice_exercises: []  # Clear exercises
```

## Security & Privacy

### Sensitive Information

**Never commit:**

- API keys
- Passwords
- Private URLs
- Confidential project names

**Instead:**

- Use placeholders: `export API_KEY=<your-key>`
- Reference documentation: `See 1Password for credentials`
- Keep private notes outside version control

### Git Ignore

```gitignore
# Private notes (not in dotfiles)
**/notes/private/
**/notes/work/

# Sensitive bookmarks
**/registry/private-*.yml
```

## Performance

### Startup Time

Menu is fast because it:

- Only parses YAML when needed
- Uses grep/sed for simple searches
- Loads categories dynamically
- No database or indexing overhead

### Memory Usage

Minimal memory footprint:

- No daemon processes
- Scripts exit after use
- YAML files loaded on demand

### Scaling

System scales well:

- 100+ commands: Still instant
- 50+ workflows: No slowdown
- 20+ learning topics: Fast browsing

YAML parsing is the bottleneck, but yq is very fast.

## See Also

- [Menu System Reference](../reference/menu-system.md) - User guide
- [Session Management](../configuration/tmux.md) - Tmux/tmuxinator setup
- [Tools Discovery](../reference/tools.md) - CLI tools registry
