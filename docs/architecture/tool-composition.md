# Tool Composition Architecture

This document explains how the workflow tools in this dotfiles system are designed to work together, following the Unix philosophy of small, focused, composable tools.

## Core Philosophy

The workflow tools follow these architectural principles:

### 1. Separation of Data and Presentation

Tools are **data providers**, not UI frameworks. They output clean, parseable data that can be composed with external UI tools.

**Pattern: Data Provider + External UI**

```text
Tool outputs data → External UI (fzf/gum) → Tool processes selection
```text

**Example:**

```bash
# sess provides session data
sess list | fzf | xargs sess

# tools provides tool information
tools list | fzf --preview='tools show {1}'

# theme-sync provides theme names
theme-sync favorites | fzf | xargs theme-sync apply
```text

This pattern is inspired by [sesh](https://github.com/joshmedeski/sesh) - the integration happens at the shell level, not within the tool itself.

### 2. Single Responsibility

Each tool has one clear purpose:

- **sess** - Tmux session management (create, list, switch)
- **tools** - Tool discovery and documentation
- **theme-sync** - Base16 theme synchronization
- **nb** - Note taking and knowledge management
- **menu** - Quick reference and launcher (documentation in executable form)

No tool tries to do everything. No "mega-tool" that handles sessions AND themes AND notes.

### 3. Clean Output

Tools output clean, machine-readable data by default, with optional formatting.

**Good output (parseable):**

```bash
$ sess list
● dotfiles (4 windows)
● ichrisbirch (1 window)
○ learning (2 windows)
```text

**Good output (structured):**

```bash
$ tools list
bat                       [file-viewer] Syntax-highlighting cat replacement
eza                       [file-lister] Modern ls replacement with git integration
fd                        [file-finder] Fast, user-friendly alternative to find
```text

**Good output (plain text):**

```bash
$ theme-sync favorites
rose-pine
rose-pine-moon
gruvbox-dark-hard
kanagawa
```text

### 4. Composability Over Integration

Instead of building fzf/gum INTO each tool, we make tools that OUTPUT FOR them.

**Anti-pattern (integration):**

```bash
# Tool has built-in fzf mode
sess --fzf          # Bad: now sess depends on fzf
```text

**Better (composition):**

```bash
# Tool outputs clean data, shell composes with fzf
sess list | fzf     # Good: sess doesn't know about fzf
```text

**Benefits:**

- Tools stay lightweight
- Users can choose their UI (fzf, gum, rofi, dmenu, etc.)
- Easier to test (pure functions, predictable output)
- Works in scripts and interactive use

## How Tools Work Together

### Layer 1: Data Sources

Each tool manages its own data source:

```text
sess        → tmux sessions + tmuxinator projects + config file
tools       → YAML registry (docs/tools/registry.yml)
theme-sync  → tinty + Base16 themes
nb          → Git-backed markdown notebooks
```text

### Layer 2: Core Logic

Each tool provides commands for its domain:

```text
sess list           → Get all available sessions
sess <name>         → Create or switch to session

tools list          → Get all tools from registry
tools show <name>   → Get detailed tool info

theme-sync current  → Get active theme
theme-sync apply    → Set theme across applications

nb add              → Create note
nb search           → Find notes
```text

### Layer 3: Output Formats

Tools output in formats suitable for composition:

```text
Plain Text    → For piping to fzf, grep, awk
Structured    → For parsing (consistent format)
Rich          → For direct viewing (icons, colors)
```text

### Layer 4: External Composition

Users compose at the shell level:

```bash
# Filtering
tools list | grep cli-utility

# Interactive selection
sess list | fzf

# Transformation
theme-sync favorites | shuf | head -1

# Chaining
tools show $(tools list | fzf | awk '{print $1}')
```text

## Composition Patterns

### Pattern 1: Filter → Select → Execute

```bash
# List all items → Filter interactively → Execute action
tools list | fzf --preview='tools show {1}'
sess list | fzf | xargs sess
theme-sync favorites | fzf | xargs theme-sync apply
```text

### Pattern 2: Search → Process → Output

```bash
# Search across data → Process results → Format output
nb search "algorithm" --all | grep -i "binary" | wc -l
tools list | grep file-viewer | awk '{print $1}'
```text

### Pattern 3: Generate → Transform → Apply

```bash
# Generate data → Transform → Apply changes
theme-sync favorites | shuf | head -1 | xargs theme-sync apply
sess list | awk '{print $2}' | xargs -I {} tmux kill-session -t {}
```text

### Pattern 4: Conditional Logic

```bash
# Check state → Decide → Execute
if sess list | grep -q "dotfiles"; then
  sess dotfiles
else
  sess dotfiles
fi

# Time-based theme switching
hour=$(date +%H)
if [ $hour -ge 6 ] && [ $hour -lt 18 ]; then
  theme-sync apply rose-pine-dawn
else
  theme-sync apply rose-pine
fi
```text

## Integration Points

### Tmux Integration

Tools integrate with tmux through bindings and popups:

```bash
# tmux.conf example
bind-key "s" run-shell "tmux popup -E 'sess'"
bind-key "t" run-shell "tmux popup -E 'tools list | fzf'"
```text

### Shell Integration

Tools are available in the shell PATH:

```bash
# .zshrc - no aliases needed, commands are memorable
# Tools are in ~/.local/bin/ (symlinked from dotfiles)

# Optional compositions for frequent workflows
alias theme-pick='theme-sync favorites | fzf | xargs theme-sync apply'
alias tool-find='tools list | fzf --preview="tools show {1}"'
```text

### Alfred/Raycast Integration

Tools can be called from launcher applications:

```bash
# Alfred Script Filter
/usr/local/bin/sess list

# Alfred Run Script
/usr/local/bin/menu launch
```text

## Data Flow Example

Let's trace a complete workflow: "Switch to a tmux session"

**Step 1: User initiates**

```bash
sess
```text

**Step 2: sess gathers data**

- Check running tmux sessions (`tmux list-sessions`)
- Check tmuxinator projects (`~/.config/tmuxinator/`)
- Check default sessions config (`~/.config/menu/sessions/sessions-macos.yml`)

**Step 3: sess formats output**

```text
● dotfiles (4 windows)     # Active session
○ ichrisbirch (1 window)   # Inactive session
→ learning                 # Tmuxinator project
+ work                     # Default session (not running)
+ Create New Session
```text

**Step 4: sess calls gum**

```bash
gum choose --header="Tmux Sessions" <options>
```text

**Step 5: User selects**
User chooses "learning"

**Step 6: sess processes selection**

- If tmuxinator project: `tmuxinator start learning`
- If running session: `tmux switch-client -t learning`
- If default session: Create session based on config

**Step 7: Session switched**
User is now in the "learning" tmux session.

## Alternative Composition

The same workflow can be composed differently:

```bash
# Manual composition with fzf instead of gum
sess list | fzf | xargs sess

# Scripted composition
SESSION=$(sess list | awk '{print $2}' | sort | head -1)
sess "$SESSION"

# Filtered composition
sess list | grep -v dotfiles | fzf | xargs sess
```text

The tool doesn't care HOW you use it - it just provides clean data and accepts clean input.

## Design Decisions

### Why Not Build UI Into Tools?

**Considered:** Adding `sess --fzf` flag for built-in fzf integration

**Rejected because:**

- Adds dependency (what if user prefers gum? rofi? dmenu?)
- Increases code complexity
- Harder to test
- Less composable
- Goes against Unix philosophy

**Chosen approach:**

- Tools output clean data
- Shell scripts compose with preferred UI
- Users can swap UI tools without changing our tools

### Why No Shell Aliases by Default?

**Considered:** Creating aliases like `s` for `sess`, `t` for `tools`

**Rejected because:**

- User preference: full names easier to remember
- Clarity over brevity: `sess` is already short
- Self-documenting: `tools list` is clearer than `t l`
- Avoids conflicts: `s` might conflict with other tools

**Chosen approach:**

- Use full, memorable command names
- Users can create their own aliases if desired
- Document composition patterns instead

### Why Separate Workflow Tools from Dotfiles Management?

**Separation of concerns:**

**Workflow Tools** (sess, tools, theme-sync, nb, menu):

- Purpose: Daily development and note-taking workflows
- Storage: Live in dotfiles repo for convenience
- Usage: Direct commands (`sess`, `tools`)

**Dotfiles Management** (task commands):

- Purpose: Configuration deployment and system setup
- Storage: Taskfiles and install scripts in dotfiles repo
- Usage: Task runner (`task symlinks:link`, `task install:macos`)

These are **different concerns** that happen to share a repository. The tools help with daily work; the tasks help manage the dotfiles themselves.

## Comparison with Alternatives

### The Menu Approach (Archived)

**What we had:**

- 17MB Go binary with Bubbletea TUI
- Complex menu system with multiple implementations
- Tried to be "one tool to rule them all"

**Why it didn't work:**

- Added layer of indirection ("press 's' to see sessions, then select session")
- Too heavy (17MB for a launcher?)
- Maintenance burden (3 different implementations)
- Cognitive overhead (remembering menu structure)

**What we learned:**

- Menus add friction, not reduce it
- Better to have muscle memory for direct commands
- Documentation is a better "menu" than a TUI

### The Integration Approach

**What we could have done:**

- Add fzf integration to each tool
- Create "super tool" with all features
- Build custom TUI for everything

**Why we didn't:**

- Violates single responsibility principle
- Creates dependencies between unrelated domains
- Harder to maintain
- Less flexible for users

**What we chose instead:**

- Small, focused tools
- Clean data output
- Composition at shell level
- User choice of UI tools

## Best Practices

### For Tool Developers

When adding new tools to this system:

1. **Focus on one domain** - Don't create multi-purpose tools
2. **Output clean data** - Make output parseable and predictable
3. **Accept clean input** - Simple arguments, no complex parsing
4. **Don't integrate UI** - Output FOR fzf/gum, don't integrate WITH them
5. **Provide plain output** - Default to machine-readable, add formatting as option
6. **Document composition** - Show examples of piping to other tools

### For Users

When using these tools:

1. **Learn direct commands first** - Build muscle memory for `sess`, `tools`, etc.
2. **Compose as needed** - Add fzf/gum when you want interactivity
3. **Create your own workflows** - Tools are building blocks
4. **Don't rely on menu** - Use `menu` as reference, not as daily driver
5. **Script repetitive tasks** - These tools are designed for scripting

## Future Directions

As the system evolves, maintain these principles:

- Keep tools focused and lightweight
- Favor composition over integration
- Output clean, parseable data
- Let users choose their UI
- Document patterns, not prescribe workflows

## Related Documentation

- [Quick Reference](../reference/quick-reference.md) - Command reference for all tools
- [Note Taking Workflows](../workflows/note-taking.md) - nb usage patterns
- [Symlinks Management](../development/symlinks.md) - Dotfiles deployment
- Planning documents:
  - `planning/dotfiles-system-redesign-2025-11.md` - Overall redesign plan
  - `planning/phase1-complete-summary.md` - Menu simplification
  - `planning/phase2-complete-summary.md` - nb setup
