# Claude Code - Dotfiles Development Context

## Critical Rules

**Note**: The following universal rules are defined in `~/.claude/CLAUDE.md` and apply to ALL projects:

- System Environment (GNU tools)
- Git Safety Protocol, Git Commit Messages, Git Hygiene
- Commit Agent Workflow
- Never Commit Untested Fixes
- Problem Solving Philosophy (including "never repeat same test")
- Code Comments Philosophy
- Tools Over Instructions
- Command Output Handling
- Logsift Monitoring

**This file contains ONLY dotfiles-specific rules and patterns.**

**File Naming and Organization**:

- All markdown files use lowercase names: `github-pages.md` NOT `GITHUB_PAGES_SETUP.md`
- Exceptions: README.md and CLAUDE.md (standard conventions)
- ALWAYS add new documentation to `mkdocs.yml` navigation

**Shell Script Patterns**:

- ALWAYS use `DOTFILES_DIR="$(git rev-parse --show-toplevel)"` to get repo root
- NEVER use relative path navigation like `$(cd "$(dirname ...)/../.." && pwd)`

**App Installation Patterns** (⚠️ CRITICAL - Read this carefully, mistakes here are costly):

**This has caused issues 3+ times. Follow these rules exactly:**

1. **Go Apps** (sess/, toolbox/): Directories with source code
   - ✅ Built with `task install` → installs to `~/go/bin/`
   - ❌ **NEVER symlinked** - they install themselves
   - Added via Taskfile.yml: `cd apps/common/{app} && task install`

2. **Shell Script Apps** (menu, notes, etc.): Executable files
   - ✅ Symlinked from `apps/{platform}/` → `~/.local/bin/`
   - ✅ Handled by `link_apps()` in symlinks manager
   - Note: `link_apps()` skips directories, only symlinks files

**Test your understanding**: Before modifying app installation, re-read this section.

See `docs/learnings/app-installation-patterns.md` for full details.

**Critical Bash Gotcha - Arithmetic with set -e** (⚠️ This has caught us 4+ times):

- `((COUNTER++))` returns 0 (false) when COUNTER is 0, causing `set -e` to exit the script
- **Always use:** `COUNTER=$((COUNTER + 1))` instead of `((COUNTER++))`
- **Or use:** `((COUNTER++)) || true` to prevent exit
- This affects any arithmetic expression that evaluates to 0: `((VAR--))`, `((VAR *= 0))`, etc.
- Example that fails:

  ```bash
  set -e
  COUNT=0
  ((COUNT++))  # Exits here! Returns 0 before incrementing
  echo "This never runs"
  ```

- Example that works:

  ```bash
  set -e
  COUNT=0
  COUNT=$((COUNT + 1))  # Safe
  echo "This runs: COUNT=$COUNT"
  ```

**Shell Libraries** (⚠️ Three system-wide libraries for all scripts):

The dotfiles provide three shell libraries in `~/.local/shell/`:

1. **logging.sh** - Status messages with [LEVEL] prefixes for parseability
   - Use `log_info/success/warning/error/fatal()` for scripts that need logging
   - Always includes [LEVEL] prefix for log parsers (logsift, Grafana)
   - Use for: installation scripts, update scripts, CI/CD, any logged output

2. **formatting.sh** - Visual structure and purely visual status
   - Use `print_header/section/banner/title()` for visual structure
   - Use `print_success/error/warning/info()` ONLY for purely visual scripts
   - Use for: interactive menus, visual-only tools (never logged)

3. **error-handling.sh** - Error traps, cleanup, verification helpers
   - Source when scripts need: cleanup on exit, error trapping, retry logic
   - Functions: `enable_error_traps()`, `register_cleanup()`, `require_commands()`, etc.
   - Use for: complex installers, download scripts, anything creating temp files

**Decision Guide**:

| Scenario | Library | Functions |
|----------|---------|-----------|
| Script will be logged/monitored | logging.sh | log_info/success/warning/error/fatal |
| Script is purely visual/interactive | formatting.sh | print_success/error/warning/info |
| Script needs visual structure | formatting.sh | print_header/section/banner/title |
| Script needs cleanup/traps | error-handling.sh | enable_error_traps, register_cleanup |

See `docs/architecture/shell-libraries.md` for complete guide

**GitHub Release Installers** (⚠️ Use library for new installers):

- Use `management/common/lib/github-release-installer.sh` for installing binaries from GitHub releases
- Medium abstraction: 5 focused functions (platform detection, version fetching, idempotency, install from tarball/zip)
- Configuration stays inline in each script (explicit and traceable, no YAML parsing)
- Pattern reduces installer scripts from ~90-120 lines to ~40-50 lines
- Examples: `management/common/install/github-releases/{lazygit,duf,glow}.sh`
- Full documentation: `docs/architecture/github-release-installer.md`

**Zsh Configuration Setup** (⚠️ This is the CORRECT setup - do not second-guess it):

- `ZDOTDIR` is defined in `/etc/zshenv` (system-wide) pointing to `~/.config/zsh`
- There is NO `.zprofile` or `.zshenv` in the home directory (and there should NOT be)
- `.zshrc` is located in `~/.config/zsh/.zshrc` (symlinked from dotfiles repo)
- This XDG-compliant setup is intentional and correct
- Standalone shell scripts in `apps/` must source logging.sh library if they need logging (they run in their own bash process, not in the shell environment)

**run-and-summarize.sh Usage** (⚠️ Legacy - prefer logsift for new code):

- **Note**: This script predates logsift. For new code, use logsift instead (see universal CLAUDE.md)
- If using run-and-summarize.sh for existing code:
  - NEVER use `run_in_background: true` when calling it
  - NEVER add `&` to the end of the command
  - This script handles backgrounding internally and shows periodic updates
  - Correct usage: `bash management/run-and-summarize.sh "task install" /tmp/log.txt 30`

**Installation Script Testing Constraints**:

- `install.sh` requires sudo at the beginning and CANNOT be run in autonomous testing loops
- The script requests `sudo -v` upfront and maintains a background keep-alive loop
- Claude Code cannot provide interactive password input, so the script will hang
- For testing install phases:
  - Run individual phase scripts directly (they handle their own sudo if needed)
  - Test in Docker containers with passwordless sudo configured
  - Use `management/test-install.sh` which handles sudo appropriately
- Do NOT attempt to run `./install.sh` in background or in automated test loops

## Package Management Philosophy

This dotfiles setup maintains a clear separation between system package managers and language-specific version managers for cross-platform consistency.

**System Package Managers** (Homebrew/apt/pacman):

- System utilities: bat, eza, fd, ripgrep, fzf, tmux, neovim, yazi
- Infrastructure tools: docker, terraform, awscli
- GUI applications (macOS): alfred, bettertouchtool, ghostty
- Compiled libraries and system dependencies

**Language Version Managers**:

- **uv** for Python - version management, project dependencies, virtual environments
- **nvm** for Node.js - version management, npm global packages, language servers

**Installation Decision Tree**:

- System utility? → brew/apt/pacman
- Python tool/runtime? → uv
- Node.js tool/runtime? → nvm/npm
- Language server? → Usually npm (universal LSPs) or language-specific package manager

**Platform Notes**:

- GNU coreutils on macOS are prepended to PATH (unprefixed) for universal use in both interactive shells and scripts
- Homebrew Python only kept if required by `brew uses --installed python@X.XX`
- All development uses uv-managed Python, not system Python

## Project Overview

A cross-platform dotfiles repository with shared configurations and platform-specific overrides for macOS and Ubuntu WSL. The repository emphasizes automation, documentation, and ergonomic developer workflows.

**Directory Structure**:

- `platforms/` - Platform configurations (what gets deployed)
  - `common/` - Shared configurations (Neovim, tmux, zsh, git)
  - `macos/` - macOS-specific dotfiles and GUI app configs
  - `wsl/` - Ubuntu WSL configurations for restricted work environment
  - `arch/` - Arch Linux configurations
- `apps/` - Personal CLI applications
  - `common/` - Cross-platform tools (menu, notes, toolbox, theme)
  - `macos/` - macOS-specific tools (aws-profiles)
  - `sess/` - Session manager (Go application)
- `management/` - Repository management tools
  - `symlinks/` - Symlinks manager (Python)
  - `taskfiles/` - Modular Task automation
  - `*.sh` - Platform setup scripts
  - `packages.yml` - Package definitions
- `docs/` - MkDocs-based documentation site
- `.claude/` - Skills and hooks for Claude Code integration
- `.planning/` - **NOT TRACKED BY GIT** - Ephemeral planning guides, status tracking; moved to archive when done

**Key Systems**:

- **Symlink Manager** - Deploys dotfiles from repo to home directory via `task symlinks:link`
- **Theme System** (`theme`) - Unified theme management across ghostty, tmux, btop, and Neovim
- **Tools Discovery** (`toolbox`) - CLI for exploring 30+ installed development tools
- **Task Automation** - Modular Taskfile system for builds, tests, installations
- **Pre-commit Hooks** - Quality control with markdownlint, shellcheck, yamllint, prettier

**Symlink Management Critical Rule**:

After adding or removing files in the repository, run: `task symlinks:link`

Common symptoms of outdated symlinks: "module not found" errors in Neovim, configs not being picked up, files in repo but not accessible in expected locations.

## Documentation Philosophy

Documentation in this repository serves as a technical reference for future me (6+ months later) and follows these principles:

**Structure** (inspired by CodeCompanion.nvim docs):

```text
docs/
├── {topic.md}           # High level or top level topics that do not need a directory for organization
├── architecture/        # HOW and WHY everything works
├── configuration/       # Customization guides
├── development/         # Testing and contributing
├── reference/           # Quick lookup (platforms, tools, tasks)
├── learnings/           # Extracted wisdom from bugs and discoveries
└── changelog/           # Historical record
```

**Writing Guidelines**:

- ALWAYS write in the imperative tone.
  - Good: "Copy the config file"
  - Bad: "You should copy the config file"
  - Bad: "Now you can copy the config file"
- WHY over WHAT - explain decisions and trade-offs, not just commands
- Conversational paragraphs over bulleted lists - maintain context and reasoning
- Reference files instead of copying code examples
- Technical and factual, not promotional
- Add new docs to `mkdocs.yml` navigation

## Key Custom Tools

**Symlinks Manager**:

- Deploy/verify dotfiles from repo to home directory
- Platform-aware with platforms/common and platforms/{platform} configs
- Handles apps/ → ~/.local/bin/ symlinking
- Run via Task: `task symlinks:link`, `task symlinks:check`, `task symlinks:show`
- Location: `management/symlinks/`
- See `.claude/skills/symlinks-developer` for detailed documentation

**Theme System** (`theme`):

- Unified theme generation from `theme.yml` source files
- Applies themes across ghostty, tmux, btop, and Neovim
- Commands: `apply`, `current`, `list`, `preview`, `random`, `like`, `dislike`
- Themes stored in `apps/common/theme/themes/` with generated configs

**Tools Discovery** (`toolbox`):

- CLI for exploring 30+ installed development tools
- Registry at `docs/tools/registry.yml` with descriptions, examples, docs
- Commands: `list`, `show <name>`, `search <query>`, `random`, `installed`

**Task Automation**:

- Modular Taskfile system in `management/taskfiles/` directory
- Tasks for building, testing, package management, documentation
- Run `task --list-all` to see available tasks

## Learnings Directory

Document critical lessons learned in `docs/learnings/` as we encounter them. Learnings are quick-reference extracted wisdom - concise, skimmable, focused.

**When to create a learning**: Critical bugs, best practices to follow consistently, common pitfalls, tool gotchas

**Format (30-50 lines max)**:

1. Title and context (1-2 lines)
2. The Problem (2-4 lines + minimal code)
3. The Solution (2-4 lines + code)
4. Key Learnings (3-5 actionable bullets)
5. Testing (optional, 5-10 lines)
6. Related links (1-2 lines)

**Workflow**: Create `docs/learnings/descriptive-name.md`, add to `mkdocs.yml` navigation

Focus on what future you needs to remember, not comprehensive guides (that's what `docs/` is for).

- todo.md is for creating future work items, not to be used for planning, moved to .planning, or changed in any way
