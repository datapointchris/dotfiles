# Tool Discovery Workflows

Modern development environments contain dozens of specialized tools that solve specific problems elegantly. The challenge isn't installing tools - it's remembering they exist and knowing when to use them. Tool discovery workflows help explore the available toolchain, learn what each tool does, and build awareness of capabilities.

## Discovering What's Installed

Start by seeing the complete inventory of tools available in the environment. The list command organizes tools by category with one-line descriptions.

```bash
toolbox list
```

Output groups tools into categories like file-viewer, search, version-control, linter, formatter, and language-server. Within each category, tools sort alphabetically for easy scanning. This overview reveals the complete toolchain in seconds.

Categories reflect how development tasks are thought about, not how tools are installed. Need to search files? Check the search category for ripgrep, fzf, and fd. Working with git? Check the version-control category for git, gh, lazygit, delta, and forgit commands.

The list command shows what's available, not what's currently running or recently used. This complete view helps discover tools that were installed months ago and forgotten.

## Learning About Specific Tools

When a tool name looks familiar but its purpose is unclear, get detailed information with the show command.

```bash
toolbox show bat
toolbox show ripgrep
```

The detail view explains what the tool does, why it's better than alternatives, how to use it, and provides concrete examples. This information answers the question "When should I use this?" instead of just "What is this?"

Examples show common usage patterns with explanations. Instead of generic syntax, they demonstrate actual scenarios. How to view a file with syntax highlighting using bat. How to search recursively while respecting .gitignore with ripgrep. How to find files by extension with fd.

Related tools appear in the see_also section, helping discover complementary capabilities. Looking at bat reveals eza for file listings. Examining ripgrep shows fd for file finding and fzf for interactive selection. These connections build awareness of tool combinations.

## Searching for Tools by Purpose

Finding tools for specific tasks works through the search command. Search looks across tool names, descriptions, tags, and purpose explanations.

```bash
toolbox search git
toolbox search syntax
toolbox search docker
```

Case-insensitive search matches any field. Searching for "git" finds git itself, lazygit, delta, gh, and all forgit commands. Searching for "syntax" finds bat, delta, and language servers. Searching for "docker" finds docker and docker-compose.

The shortcut syntax makes searches feel natural. Just type what's being thought about:

```bash
toolbox git       # Same as: toolbox search git
toolbox python    # Same as: toolbox search python
```

This removes command overhead. Think "I need something for Python", type `toolbox python`, see relevant tools immediately.

## Exploring Tools by Category

Browse tools interactively when the general area is known but the specific tool isn't. The categories command launches a two-level interactive picker.

```bash
toolbox categories
```

First, select a category - file-viewer, search, version-control, etc. The picker shows tool count and preview for each category. Second, select a tool from that category to see full details.

This workflow matches how tool discovery actually happens. "I need a better file viewer" leads to browsing the file-viewer category to see bat, eza, and yazi. "I want git help" leads to version-control category to discover lazygit and forgit.

Interactive browsing works best for exploration and learning. Command-line search works best for quick lookups when the tool name or purpose is partially known.

## Getting Random Tool Suggestions

Break out of tool usage ruts by exploring random suggestions. This surfaces tools that are installed but rarely used.

```bash
toolbox random
```

Random selection helps discover forgotten tools. That linter installed six months ago and never used. That formatter that might work better than the current one. That system utility that solves a problem currently being solved manually.

Run random selection periodically to maintain awareness of the complete toolchain. Make it part of weekly routines - check what random tool appears, read its description, try it out. This practice builds comprehensive tool knowledge over time.

## Building Tool Awareness

Tool discovery isn't a one-time activity. New tools get installed. Old tools get forgotten. Workflows change. Continuous discovery maintains awareness and enables using the right tool at the right time.

### Daily Discovery Pattern

When starting work, spend 30 seconds browsing tools. Run `toolbox list` while coffee brews. Skim the categories. Notice tools that might be useful for today's tasks. This regular exposure builds familiarity.

### Problem-Driven Discovery

When encountering a problem, search the toolbox before reaching for manual solutions or web searches. Need to format JSON? Search for formatters. Need to compare files? Search for diff. The tool might already be installed.

```bash
toolbox search format
toolbox search diff
```

This pattern shifts tool discovery from proactive exploration to reactive problem-solving. The search happens when motivation is high because there's an immediate need.

### Exploratory Discovery

Set aside time for deliberate tool exploration. Pick a category and read about every tool in it. Try examples. Compare related tools. Understand the differences.

```bash
toolbox categories          # Browse interactively
```

Select version-control category. Read about git, gh, lazygit, delta, and each forgit command. Try examples for tools that seem useful. This focused exploration builds deep knowledge of specific tool families.

## Integrating New Tools into Workflows

Discovery alone isn't enough - tools need to integrate into actual workflows. Learning about a tool requires trying it, understanding when it's better than alternatives, and remembering to use it.

### Experimentation Pattern

After discovering a tool through toolbox, experiment with it immediately. Don't just read the description - run the examples. Try it on real work, not synthetic tests.

```bash
toolbox show bat            # Read about bat
bat README.md               # Try it immediately
```

Immediate experimentation while the tool is fresh in mind builds muscle memory. Reading creates awareness. Using creates habit.

### Comparison Pattern

When discovering a tool that replaces something currently used, compare them directly. Use both on the same task. Notice differences in speed, output format, features.

```bash
cat README.md               # Old tool
bat README.md               # New tool
```

Direct comparison highlights advantages and disadvantages. Sometimes the new tool is clearly better. Sometimes the old tool works fine for specific use cases. Understanding these differences enables choosing the right tool for each situation.

### Alias Pattern

Create short aliases for frequently used tools discovered through toolbox. The tool registry shows full commands, but aliases make them faster to invoke.

```bash
alias bcat='bat'
alias rg='ripgrep'
```

Aliases reduce friction. Typing `bcat README.md` is faster than `bat README.md`. Lower friction means higher usage. Higher usage builds familiarity.

## Maintaining the Tool Registry

The tool registry at `~/.config/toolbox/registry.yml` defines what toolbox knows about. Add new tools to the registry as they're installed to maintain discovery capability.

Edit the registry file to add entries:

```bash
nvim ~/dotfiles/platforms/common/.config/toolbox/registry.yml
```

Each tool entry follows a consistent format:

```yaml
tool-name:
  category: appropriate-category
  description: "What the tool does"
  installed_via: brew
  usage: "command [options] <args>"
  why_use: "Why this tool over alternatives"
  examples:
    - cmd: "command --option"
      desc: "What this does"
  see_also: [related-tool1, related-tool2]
  tags: [tag1, tag2]
  docs_url: "https://..."
```

Required fields enable basic functionality. Optional fields improve discovery and learning. The why_use field is particularly valuable - it explains when to use this tool instead of alternatives.

After adding tools, verify they appear correctly:

```bash
toolbox list                # Check it appears
toolbox show new-tool       # Verify details display correctly
```

## Advanced Discovery Patterns

### Interactive Selection with FZF

Combine toolbox with fzf for enhanced interactive browsing.

```bash
toolbox list | fzf --preview='toolbox show {1}'
```

This pipeline lists all tools, presents them in fzf for selection, and shows detailed info in the preview pane. Browse tools with live previews, select one to see full details in the terminal.

### Filtering by Category

Extract tools from specific categories using standard Unix tools.

```bash
toolbox list | grep "^\[version-control\]"
toolbox list | grep "^\[search\]"
```

This pattern finds all tools in a category without using interactive mode. Useful for scripting or when working in environments without gum installed.

### Extracting Tool Names

Get just tool names for scripting or further processing.

```bash
toolbox list | awk '{print $1}'
toolbox search git | awk '{print $1}'
```

Use this to build custom scripts that operate on tool lists. Check installation status of all tools, verify all are up to date, or create custom selection interfaces.

## Learning Categories

Understanding tool categories helps navigate the toolchain efficiently. Each category groups tools by purpose and workflow context.

**file-viewer**: Tools for viewing file contents with enhancements like syntax highlighting, formatting, or navigation. Bat for syntax-highlighted viewing, eza for enhanced directory listings.

**search**: Tools for finding files or content. Ripgrep for content search, fd for file finding, fzf for interactive selection from any list.

**version-control**: Git and git-related tools. LazyGit for interactive git operations, forgit for fzf-powered git commands, delta for enhanced diffs, gh for GitHub operations.

**editor**: Text editors and related tools. Neovim with extensive configuration and plugins.

**linter-formatter**: Code quality tools. Ruff for Python linting and formatting, eslint for JavaScript, prettier for multiple languages, shellcheck for shell scripts.

**language-server**: LSP servers for editor integration. TypeScript language server, basedpyright for Python, lua-language-server for Lua.

**terminal**: Terminal multiplexers and enhancements. Tmux for session management and window splitting.

**build**: Build automation and task runners. Task for taskfile-based automation, make for traditional Makefiles.

Each category provides a lens for discovering tools. Need better code formatting? Check linter-formatter. Want enhanced terminal capabilities? Check terminal category.

## See Also

- [Menu System](../reference/workflow-tools/menu.md) - Knowledge and workflow management
- [Session Management](sessions.md) - Tmux session workflows
- [Tool Reference](/reference/tools.md) - Quick tool overview
- [Task Reference](/reference/tasks.md) - Installation automation
