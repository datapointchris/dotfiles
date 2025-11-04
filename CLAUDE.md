# Claude AI Assistant - Neovim Development Context

## Critical Rules

**File Naming**:

- All markdown files MUST use lowercase names: `github-pages.md` NOT `GITHUB_PAGES_SETUP.md`
- Exception: README.md and CLAUDE.md (standard conventions)

**Documentation Organization**:

- NEVER create standalone troubleshooting/setup files in docs root
- Place in appropriate subdirectories: `docs/reference/`, `docs/troubleshooting/`, etc.
- ALWAYS add new documentation to `mkdocs.yml` navigation

**Problem Solving Philosophy**:

- Solve the actual root cause, don't create unnecessary guardrails
- Don't add band-aid solutions hoping they work
- If you know something isn't the real solution (like .nojekyll for a configuration issue), don't create it
- Focus on fixing the actual problem (like GitHub Pages settings) not symptoms

## About Me

I'm Chris, a software engineer who uses a dotfiles-based development environment across macOS, WSL, and Ubuntu. I prefer clean, maintainable code and enjoy optimizing developer experience.

## Development Environment

- **Editor**: Neovim 0.11+ with native LSP configuration
- **Shell**: Zsh with custom prompt and enhanced CLI tools
- **Platforms**: macOS Intel (primary), WSL Ubuntu, Arch Linux (upcoming)
- **Terminal**: Ghostty, iTerm2 on macOS
- **AI Coding**: CodeCompanion.nvim with Claude 3.5 Sonnet

## Package Management Philosophy

This dotfiles setup uses a **clear separation** between system package managers and language-specific version managers. This strategy provides cross-platform consistency while allowing each tool to do what it does best.

### System Package Managers

**Homebrew** (macOS), **apt** (Ubuntu/WSL), **pacman** (Arch):

- System utilities: bat, eza, fd, ripgrep, fzf, tmux, neovim, yazi
- Infrastructure tools: docker, terraform, awscli
- GUI applications (macOS casks): alfred, bettertouchtool, ghostty
- Compiled libraries and system dependencies

### Language-Specific Version Managers

**uv** for Python:

- Python version management (replaces pyenv, <python@X.XX> from brew)
- Python tool installation: ruff, mypy, basedpyright, sqlfluff, mdformat
- Virtual environment management
- Cross-platform, fast, modern

**nvm** for Node.js:

- Node/npm version management
- Project-specific versions via `.nvmrc`
- npm global packages: language servers, formatters, linters
- Cross-platform, industry standard

### Why This Split?

**Cross-platform consistency**: uv and nvm work identically on macOS, Ubuntu WSL, and Arch Linux. System package managers vary by platform but handle platform-specific concerns.

**Version flexibility**: Easy project-specific version switching with `.python-version` and `.nvmrc` files. System tools don't need this complexity.

**Clear separation of concerns**: System stability (brew/apt/pacman) vs development flexibility (uv/nvm). No conflicts between system Python and project Python.

**PATH simplicity**: Cleaner shell configuration with version manager shims for languages, direct binaries for system tools.

### Tool Installation Guidelines

When adding a new tool, ask:

- **Is it a system utility?** → Use brew/apt/pacman
- **Is it a Python tool?** → Use `uv tool install`
- **Is it a Node.js tool?** → Use `npm install -g` (with nvm)
- **Is it a language runtime?** → Use uv/nvm, NOT system package manager
- **Is it a language server?** → Usually npm for universal LSPs, language-specific package manager for others

### GNU Coreutils on macOS

GNU coreutils are installed via Homebrew but **NOT** in PATH by default to avoid conflicts with macOS system tools and potential build issues. They remain available with `g` prefix: `gls`, `gsed`, `gtar`, `ggrep`. This follows standard macOS Homebrew practice for Intel Macs.

### Python from Homebrew

Some Homebrew packages depend on specific Python versions. These are kept only if required by `brew uses --installed python@X.XX`. All development work uses uv-managed Python installations, not Homebrew Python.

## Current Project Context

Working on a cross-platform dotfiles repository with shared configurations and platform-specific overrides. Recently migrated from Mason-based LSP to Neovim 0.11 native LSP and enhanced CodeCompanion setup.

### Key Files

- `symlinks` - Core symlink management tool
- `common/` - Common dotfiles between all operating systems
- `macos/` - MacOS specific dotfiles and configuration
- `wsl/` - WSL using Ubuntu specific dotfiles for use on a slightly restricted work computer
- `docs/` - documentation for the dotfiles, stored in mkdocs style
- Platform-specific Git configs with different editors/credentials

### Symlink Management

This dotfiles repository uses a symlink system to deploy configuration files from the repo to their expected locations in the home directory. When files are added or removed from the dotfiles, the symlinks must be updated.

**Critical Rule**: After adding or removing any files in the dotfiles repository, you MUST run the symlink update command:

- macOS: `./symlinks relink macos`
- WSL: `./symlinks relink wsl`

**Common Symptoms of Outdated Symlinks**:

- "module not found" errors in Neovim after creating new files in `lua/` directories
- Configuration files not being picked up by applications
- Files existing in the dotfiles repo but not accessible in their expected locations

Always check symlinks first when encountering file-related issues after making structural changes to the repository.

## Coding Preferences

- **Architecture**: DRY principles, intelligent symlink management
- **LSP**: Native Neovim LSP over plugin ecosystems when possible
- **AI Assistance**: Prefer comprehensive explanations with implementation
- **Documentation**: Clear README files, inline comments for complex logic
- **Testing**: Pre-commit hooks, shell validation, configuration testing
- **Problem-Solving Approach**: Always err on the side of thinking through issues rather than adding extra code. When debugging, analyze what existing code does and test minimal changes first instead of adding complex filtering or workarounds

## Documentation Purpose and Philosophy

### Documentation Purpose

The dotfiles documentation serves as a comprehensive wiki-style technical resource designed for multiple audiences and use cases:

**Primary Audiences**:

1. **New User (Day 1)**: Quick start guide to install and configure dotfiles in 15 minutes
2. **Returning User (After 1 Year)**: Refresh understanding and be productive within a day
3. **Customizer**: Deep dive into configuration options for themes, tools, and workflows
4. **Contributor**: Understand architecture, testing framework, and development process
5. **Troubleshooter**: Quick reference for platform differences and common issues

**Documentation Structure** (inspired by [CodeCompanion.nvim](https://codecompanion.olimorris.dev)):

```text
docs/
├── index.md                    # 30-second overview with navigation
├── getting-started/            # Linear onboarding (15 minutes)
├── architecture/               # HOW and WHY everything works
├── configuration/              # Customization guides
├── development/                # Contributing and testing
├── reference/                  # Quick lookup (platforms, tools, tasks)
└── changelog/                  # Historical record (detailed)
```

**Key Principles**:

- **Task-oriented hierarchy**: Concepts → setup → usage → customization → development
- **Return-friendly**: Can leave for a year and be productive in a day
- **Interconnected**: Cross-references show how components work together
- **Why over What**: Explain decisions and rationale, not just commands
- **Discoverable**: Use collapsible navigation, search, breadcrumbs
- **Visual**: Diagrams, tables, admonitions for clarity

### Documentation Philosophy

When creating or updating documentation:

### Audience (for Context Documents)

- **Primary**: Future me (6+ months later) trying to remember why decisions were made
- **Secondary**: Technical developers familiar with the technology stack
- **Context**: Always within the broader dotfiles project ecosystem

### Content Focus

- **WHY over WHAT**: Architectural decisions, trade-offs
- **Context over Code**: How components fit together, not implementation details
- **Stability over Examples**: Principles that don't change vs code that does

### Documentation Structure

Avoid creating too many bulleted lists. A bulleted list loses a lot of information that long form sentences and explanations can maintain. Prefer to always talk in a person to person manner as if having a conversation with another developer on a pull request that was created to explain the code and how the project works.

**Documentation Guidelines:**

- Focus on **concise architectural explanations** rather than verbose step-by-step processes
- Emphasize **how systems work together** and **why they are designed that way**
- Use **paragraphs of explanation** as the primary structure for conveying context and reasoning
- Include **selective bulleted lists** for overviews only, not as the main documentation format
- Keep **code snippets minimal** - include command names or key concepts, not full implementations
- Maintain a **conversational tone** as if explaining technical decisions to another developer

Avoid documentation that is primarily bulleted lists or verbose procedural steps. Instead, focus on architectural understanding and the reasoning behind design decisions.

### Writing Style

- **Technical, not promotional**: State facts and reasoning, not "features"
- **Context-aware**: Reference other dotfiles components and decisions
- **Decision-focused**: Document the "why" behind choices made
- **Maintenance-oriented**: Help future maintenance and debugging

### Avoid

- ❌ Marketing language ("amazing", "powerful", "best")
- ❌ Step-by-step tutorials (they go stale)
- ❌ Extensive code examples (reference files instead)
- ❌ Feature lists without context or reasoning

## Theme Synchronization

This dotfiles setup uses **tinty** for Base16 theme synchronization across applications. The theme system works in parallel with your existing `ghostty-theme` script:

- **ghostty-theme**: For Ghostty-specific theme management with live preview
- **theme-sync**: For synchronized Base16 themes across tmux, bat, fzf, and shell

### Supported Applications

- **Tmux**: Base16 colors sourced via `~/.config/tmux/themes/current.conf`
- **Bat**: Themes in `$(bat --config-dir)/themes/` with automatic cache rebuild
- **FZF**: Colors via tinted-shell integration
- **Shell**: LS_COLORS and prompt colors via tinted-shell

### Your Favorite Themes

The theme system is configured with 12 Base16 themes matching your Ghostty and Neovim favorites:

- rose-pine, gruvbox-dark-hard, kanagawa, oceanicnext, github-dark, nord
- selenized-dark, everforest-dark-hard, tomorrow-night, tomorrow-night-eighties

### Commands

- `theme-sync apply <theme>` - Apply a Base16 theme
- `theme-sync current` - Show currently applied theme
- `theme-sync favorites` - List favorite themes
- `theme-sync random` - Apply random favorite theme
- `task themes:rose-pine` - Quick shortcuts for specific themes

### Original Tmux Colors

Your custom tmux color scheme before tinty was backed up to `themes/backup/tmux-original-colors.conf`. Use `task themes:restore-original` to view it.

## Tool Discovery System

The dotfiles include a **tool discovery system** to help learn about and remember the 30+ installed tools. The registry from Phase 2 provides structured documentation for each tool.

### Tools Command

- `tools` or `tools list` - List all 31 tools with categories
- `tools show <name>` - Show detailed info, examples, and docs for a tool
- `tools search <query>` - Search by description, tags, or use case
- `tools categories` - List tool categories with counts
- `tools count` - Detailed breakdown by category with tool names
- `tools random` - Discover a random tool (great for learning)
- `tools installed` - Check installation status of all tools

### Registry Location

Tools are documented in `docs/tools/registry.yml` with:

- Description and "why use" rationale
- Usage syntax and examples
- Related tools and tags
- Installation method (brew, npm, uv)
- Documentation URLs

### Philosophy

Focus on **discovery over tracking** - the system helps you remember what tools you have and when to use them, without complex usage tracking that clutters configs. Simple, helpful, and maintainable.

## Recent Work

1. Completed migration from Mason LSP to native vim.lsp.config()
2. Implemented 20+ language servers (Python, JavaScript, Lua, etc.)
3. Enhanced CodeCompanion with memory system and VSCode-like experience
4. Integrated Claude 3.5 Sonnet adapter with project context awareness
5. **Phase 4 Complete**: Base16 theme synchronization via tinty across tmux, bat, fzf, shell
6. **Phase 5 Complete**: Tool discovery system with `tools` command for 31 registered tools

## Communication Style

- Like to understand the "why" behind architectural decisions
- Prefer seeing the code changes implemented rather than just described
- Value cross-platform compatibility considerations

## Changelog Requirements

**IMPORTANT**: Automatically maintain changelog entries for all changes made to this dotfiles repository.

### Changelog Structure

1. **Summary File**: `docs/changelog.md`
   - High-level overview of changes
   - Entries organized by date in YYYY-MM-DD format
   - Each entry has an `id` matching the date: `## YYYY-MM-DD {#YYYY-MM-DD}`
   - Brief title and description of what changed
   - List of key changes and files modified
   - Link to detailed changelog

2. **Detailed File**: `docs/changelog/YYYY-MM-DD.md`
   - In-depth analysis of changes from our conversation
   - Multiple unrelated changes can be in the same file (one file per day)
   - Each change section has its own heading with anchor: `## Title {#anchor-name}`

### Required Content in Detailed Changelog

For each change, include:

1. **Problem Statement**: What was wrong or what needed to be changed
2. **Solution Overview**: High-level approach taken
3. **Errors Encountered**: All errors hit during implementation
   - Error messages (exact text)
   - Root cause analysis
   - The fix that was applied
   - Why that fix was chosen
4. **Testing Methodology**:
   - Scripts used to test changes
   - Why those specific testing approaches were chosen
   - What each test validated
5. **Files Modified**: Complete list with brief description of changes
6. **Final Resolution**: Summary of working state after all fixes
7. **Learnings**: Key insights, gotchas, and wisdom for future reference

### Changelog Entry Format Example

**Summary (docs/changelog.md):**

```markdown
## 2025-11-02 {#2025-11-02}

### Feature/Fix Title

Brief description of what changed and why.

**Key Changes:**
- Bullet point of major change
- Another major change

**Files Changed:**
- Created/Modified: path/to/file

See [detailed changelog](changelog/2025-11-02.md#anchor-name) for full details.
```

**Detailed (docs/changelog/YYYY-MM-DD.md):**

```markdown
## Feature/Fix Title {#anchor-name}

### Problem Statement
What was broken or needed...

### Solution Overview
How we approached it...

### Errors Encountered and Solutions

#### Error 1: Title
**Error Message:** ```exact error text```
**Root Cause:** Why it happened
**Fix:** What we changed
**Why This Fix:** Reasoning behind the solution

[Continue for all errors...]

### Testing Methodology
Scripts used, why chosen, what validated...

### Files Modified
List with descriptions...

### Final Resolution
Summary of working state...

### Learnings
Key insights and gotchas...
```

### When to Create Changelog Entries

Create changelog entries whenever:

- Adding new features or tools
- Fixing bugs or configuration issues
- Refactoring code or reorganizing files
- Updating plugins or dependencies
- Making architectural changes
- Any change that would be useful to remember or learn from

### Changelog Workflow

1. At the end of any work session where dotfiles were modified:
   - Update `docs/changelog.md` with high-level summary
   - Create or append to `docs/changelog/YYYY-MM-DD.md` with detailed analysis
2. Use insights from our conversation to document the journey, not just the destination
3. Be thorough with error documentation - future debugging will thank you
4. Include testing scripts and methodologies used
5. Always add a Learnings section with actionable insights

## Current Goals

- Optimize CodeCompanion workflow for seamless AI-assisted development
- Maintain clean, conflict-free native LSP configuration
- Document setup for future maintenance and sharing
- Create efficient development workflows across all platforms
- **Maintain comprehensive changelogs for all dotfiles changes**
